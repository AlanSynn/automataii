import { describe, expect, it } from 'vitest';
import { analyzeMechanismTrace, analyzePath, snapPoint } from '../analysis';
import { exportBlueprintSvg, exportProjectJson, exportSceneDxf, exportSceneSvg, exportStudyBundle } from '../exporters';
import { boundsOf, MAX_PATH_POINTS, MAX_RESAMPLE_POINTS, MAX_TRACKING_POINTS, pathLength, resamplePath } from '../geometry';
import { applyMechanismHandleDrag, computeMechanismState, createMechanism, generateTrace, mechanismTemplates } from '../mechanisms';
import { createRecommendedMechanism, fitMechanismToPath, recommendMechanismsForPath, scoreTraceToPath } from '../optimizer';
import { buildFeatureAudit, requiredMechanismTypes } from '../parity';
import { simulateMechanismPhysics } from '../physics';
import { createDefaultProject, normalizeProject, parseProject } from '../project';
import { createTrackingAnnotation, normalizeTrackerPoint, smoothTrackingPoints, trackingToPath } from '../tracking';
import { inferVisionAssistFromTracking } from '../vision';
import type { MechanismConfig, MechanismType, Point, ProjectState } from '../../types';

const expectFinitePoint = (point: Point): void => {
  expect(Number.isFinite(point.x)).toBe(true);
  expect(Number.isFinite(point.y)).toBe(true);
};

const allAngles = [0, 30, 90, 180, 270, 359];

const withAllMechanisms = (): ProjectState => {
  const project = createDefaultProject();
  return {
    ...project,
    mechanisms: mechanismTemplates.map((template, index) => ({
      ...createMechanism(template.type, index),
      id: `matrix-${template.type}`,
      name: `${template.label} matrix`,
      partName: index % 2 === 0 ? 'right_wrist' : 'left_wrist',
      anchor: { x: 140 + index * 92, y: 180 + (index % 3) * 96 }
    }))
  };
};

const editableHandleFor = (mechanism: MechanismConfig): string => {
  switch (mechanism.type) {
    case 'crank': return 'crankPin';
    case 'four-bar': return 'effector';
    case 'five-bar': return 'P';
    case 'six-bar': return 'Q';
    case 'cam-follower': return 'followerBase';
    case 'gear-pair': return 'outputCenter';
    case 'planetary-gear': return 'planet1';
    case 'slider-crank': return 'slider';
    case 'quick-return': return 'rockerTip';
    case 'scotch-yoke': return 'slotB';
  }
};

describe('full feature matrix across mechanisms, examples, and physics', () => {
  it('default examples expose project, character, path, foundry, lab, timeline, and audit surfaces', () => {
    const project = createDefaultProject();
    const audit = buildFeatureAudit(project);

    expect(project.metadata.name).toBe('Automataii Web Studio');
    expect(project.settings.theme).toBe('light');
    expect(Object.keys(project.parts)).toEqual(expect.arrayContaining(['torso', 'head', 'right_arm', 'left_arm']));
    expect(Object.keys(project.skeleton?.joints ?? {})).toEqual(expect.arrayContaining(['root', 'spine', 'right_wrist', 'left_wrist']));
    expect(project.paths.right_wrist.points.length).toBeGreaterThan(4);
    expect(project.mechanisms.map((mechanism) => mechanism.type)).toEqual(expect.arrayContaining(['four-bar', 'cam-follower', 'gear-pair', 'slider-crank', 'scotch-yoke']));
    expect(mechanismTemplates.map((template) => template.type)).toEqual(expect.arrayContaining(['crank', 'quick-return']));
    expect(project.presets.length).toBeGreaterThanOrEqual(3);
    expect(project.timeline.keyframes.length).toBeGreaterThanOrEqual(2);
    expect(project.lab.kitAssets.some((asset) => asset.pilotPriority === 'P0')).toBe(true);
    expect(audit.complete).toBe(true);
    expect(audit.percent).toBe(100);
  });

  it.each(mechanismTemplates)('simulates, traces, edits, analyzes, and physics-checks $type', (template) => {
    const mechanism = createMechanism(template.type, 7);

    allAngles.forEach((angle) => {
      const state = computeMechanismState(mechanism, angle);
      expect(state.type).toBe(template.type);
      expect(['safe', 'caution', 'danger']).toContain(state.safety.level);
      Object.values(state.positions).forEach(expectFinitePoint);
      expectFinitePoint(state.effector);
    });

    const trace = generateTrace(mechanism, 72);
    expect(trace.length).toBeGreaterThan(8);
    trace.forEach(expectFinitePoint);

    const analysis = analyzeMechanismTrace(mechanism, 72);
    expect(analysis.traceCoverage).toBeGreaterThanOrEqual(0);
    expect(Number.isFinite(analysis.pathLength)).toBe(true);

    const physics = simulateMechanismPhysics(mechanism, 4, 45, 96);
    expect(physics.samples.length).toBe(96);
    expect(Number.isFinite(physics.maxSpeed)).toBe(true);
    expect(Number.isFinite(physics.maxAcceleration)).toBe(true);
    expect(physics.stabilityScore).toBeGreaterThanOrEqual(0);
    expect(physics.stabilityScore).toBeLessThanOrEqual(1);

    const handle = editableHandleFor(mechanism);
    const stateAtEdit = computeMechanismState(mechanism, 30);
    const editBase = stateAtEdit.positions[handle] ?? stateAtEdit.effector;
    const edited = applyMechanismHandleDrag(mechanism, handle, { x: editBase.x + 18, y: editBase.y + 12 }, 30);
    expect(edited.type).toBe(template.type);
    expectFinitePoint(edited.anchor);
  });

  it('keeps mechanism template and audit requirements synchronized', () => {
    const templateTypes = mechanismTemplates.map((template) => template.type);
    expect(templateTypes).toEqual(expect.arrayContaining(requiredMechanismTypes));
    expect(new Set(templateTypes).size).toBe(templateTypes.length);
  });
});

describe('full workflow coverage: drawing, tracking, optimization, exports, and imports', () => {
  it('moves a MechAnim-inspired tracking path through smoothing, vision assist, recommendation, fitting, and physics', () => {
    const rawPoints: Point[] = [
      { x: 28, y: 110 },
      { x: 86, y: 38 },
      { x: 170, y: 26 },
      { x: 232, y: 92 },
      { x: 278, y: 148 },
      { x: 338, y: 104 }
    ];
    const trackerPoint = normalizeTrackerPoint({ x: 40, y: 55 }, { left: 20, top: 15, width: 200, height: 100 });
    expectFinitePoint(trackerPoint);

    const smoothed = smoothTrackingPoints(rawPoints, true, 6);
    expect(smoothed.length).toBeGreaterThan(rawPoints.length);

    const annotation = createTrackingAnnotation('walk-cycle.gif', 'gif', smoothed, true, 2.8);
    const path = trackingToPath(annotation, 'right_wrist');
    const pathStats = analyzePath(path);
    expect(path.isClosed).toBe(true);
    expect(pathStats.pathLength).toBeGreaterThan(100);

    const vision = inferVisionAssistFromTracking(annotation);
    expect(vision.status.inferredJointCount).toBeGreaterThanOrEqual(6);
    expect(Object.keys(vision.parts)).toEqual(expect.arrayContaining(['torso', 'head', 'right_arm']));

    const recommendations = recommendMechanismsForPath(path);
    expect(recommendations.length).toBeGreaterThan(0);
    const candidate = createRecommendedMechanism(path, 12);
    const initialScore = scoreTraceToPath(generateTrace(candidate, 48), path.points);
    const fitted = fitMechanismToPath(candidate, path, 32, 123);
    expect(fitted.score).toBeLessThanOrEqual(initialScore);
    expect(fitted.iterations).toBe(32);

    const physics = simulateMechanismPhysics(fitted.candidate, path.totalDuration, 120, 80);
    expect(physics.samples.length).toBe(80);
    expectFinitePoint(physics.current.position);
  });

  it('round-trips all web export formats for a project containing every mechanism family', () => {
    const project = withAllMechanisms();
    project.metadata.name = '<Automataii & MechAnim Test>';
    project.paths.left_wrist = {
      partName: 'left_wrist',
      points: resamplePath(project.paths.right_wrist.points, 18, true),
      totalDuration: 3.2,
      isClosed: true,
      enabled: true
    };

    const json = exportProjectJson(project);
    const parsed = parseProject(json);
    expect(parsed.mechanisms).toHaveLength(mechanismTemplates.length);

    const sceneSvg = exportSceneSvg(parsed, 75);
    const blueprintSvg = exportBlueprintSvg(parsed, 75);
    const dxf = exportSceneDxf(parsed, 75);
    const study = JSON.parse(exportStudyBundle(parsed, 75)) as {
      schema_version?: string;
      mechanism_snapshots?: unknown[];
      kit_assets?: unknown[];
      episode_jsonl?: string;
      coding_csv?: string;
    };

    expect(sceneSvg).toContain('<svg');
    expect(sceneSvg).toContain('data-mechanism');
    expect(sceneSvg).toContain('&lt;Automataii &amp; MechAnim Test&gt;');
    expect(blueprintSvg).toContain('automataii.web.blueprint.v1');
    expect(blueprintSvg).toContain('data-layer="kit-manifest"');
    expect(dxf).toContain('SECTION');
    expect(dxf).toContain('ENTITIES');
    expect(study.schema_version).toBe('automataii.web.study_bundle.v1');
    expect(study.mechanism_snapshots?.length).toBe(mechanismTemplates.length);
    expect(study.kit_assets?.length).toBeGreaterThan(0);
    expect(study.episode_jsonl).toContain('episode');
    expect(study.coding_csv).toContain('status');
  });

  it('imports desktop/Python-shaped examples, clamps hostile values, and avoids false-green audit states', () => {
    const aliases: Array<[MechanismType, string]> = [
      ['four-bar', '4_bar_linkage'],
      ['five-bar', '5_bar_linkage'],
      ['six-bar', '6_bar_linkage'],
      ['cam-follower', 'cam'],
      ['gear-pair', 'gear_train'],
      ['planetary-gear', 'planetary_gear'],
      ['slider-crank', 'piston'],
      ['crank', 'crank'],
      ['quick-return', 'quick_return'],
      ['scotch-yoke', 'scotch_yoke']
    ];

    const imported = normalizeProject({
      mechanisms: Object.fromEntries(aliases.map(([, alias], index) => [
        `m_${index}`,
        {
          type: alias,
          part_name: index % 2 === 0 ? 'right_wrist' : 'left_wrist',
          color: index === 0 ? 'javascript:alert(1)' : '#38bdf8',
          params: { inputLink: 40 + index, planetCount: 999, teeth: 99999 }
        }
      ])),
      paths: {
        right_wrist: { part_name: 'right_wrist', points: [[0, 0], ['bad', 20], [80, 12], [120, 40]], is_closed: true, total_duration: 2.4 }
      },
      settings: { theme: 'light', animationDuration: -100, viewport: { x: 999999, y: -999999, zoom: 999, panMode: true } },
      imports: { referenceName: 'unsafe.svg', referenceUrl: 'javascript:alert(1)', referenceKind: 'image' }
    });

    expect(imported.mechanisms.map((mechanism) => mechanism.type)).toEqual(aliases.map(([expectedType]) => expectedType));
    expect(imported.mechanisms[0].color).toBe('#38bdf8');
    expect(imported.imports.referenceUrl).toBeUndefined();
    expect(imported.settings.animationDuration).toBe(0.25);
    expect(imported.settings.viewport.zoom).toBe(4);
    expect(imported.settings.viewport.x).toBe(2000);

    const unsafeSvg = exportSceneSvg(imported, 20);
    expect(unsafeSvg).not.toContain('javascript:alert');

    const degraded = createDefaultProject();
    degraded.mechanisms = [];
    degraded.paths = {};
    const audit = buildFeatureAudit(degraded);
    expect(audit.complete).toBe(false);
    expect(audit.missingRequired.map((item) => item.id)).toEqual(expect.arrayContaining(['paths', 'mechanism-design', 'path-fitting']));
  });

  it('bounds adversarial path, optimization, and physics requests while keeping finite outputs', () => {
    const project = withAllMechanisms();
    const allPoints = project.mechanisms.flatMap((mechanism) => generateTrace(mechanism, 12));
    const bounds = boundsOf(allPoints);
    const resampled = resamplePath(allPoints, 1_000, true);
    const length = pathLength(resampled, true);

    expect(bounds.width).toBeGreaterThan(0);
    expect(bounds.height).toBeGreaterThan(0);
    expect(resampled).toHaveLength(1_000);
    expect(Number.isFinite(length)).toBe(true);

    const hugePhysics = simulateMechanismPhysics(project.mechanisms[0], 0.01, 180, 1_000_000);
    expect(hugePhysics.samples.length).toBeLessThanOrEqual(360);
    expect(hugePhysics.warnings.join(' ')).toContain('Animation duration is very short');

    const path = project.paths.right_wrist;
    const fitted = fitMechanismToPath(project.mechanisms[0], path, 99_999, 999);
    expect(fitted.iterations).toBeLessThanOrEqual(1200);
    expectFinitePoint(fitted.candidate.anchor);

    expect(snapPoint({ x: 31, y: 47 }, true, 16)).toEqual({ x: 32, y: 48 });
    expect(snapPoint({ x: 31, y: 47 }, false, 16)).toEqual({ x: 31, y: 47 });
  });

  it('caps hostile imported point clouds and avoids spread-stack geometry failures', () => {
    const hostilePoints = Array.from({ length: 200_000 }, (_, index) => [
      index,
      Math.sin(index / 12) * 120
    ]);

    const imported = normalizeProject({
      paths: {
        right_wrist: {
          part_name: 'right_wrist',
          points: hostilePoints,
          total_duration: -10,
          is_closed: true
        }
      },
      tracking: {
        annotations: [
          {
            sourceName: 'huge.csv',
            sourceKind: 'video',
            points: hostilePoints,
            smoothedPoints: hostilePoints,
            duration: -10,
            isClosed: true
          }
        ]
      }
    });

    const path = imported.paths.right_wrist;
    expect(path.points.length).toBeLessThanOrEqual(MAX_PATH_POINTS);
    expect(path.totalDuration).toBe(0.25);
    expect(imported.tracking.annotations[0].points.length).toBeLessThanOrEqual(MAX_PATH_POINTS);
    expect(imported.tracking.annotations[0].smoothedPoints.length).toBeLessThanOrEqual(MAX_TRACKING_POINTS);
    const bounds = boundsOf(path.points);
    expect(Number.isFinite(bounds.width)).toBe(true);

    const resampled = resamplePath(path.points, 1_000_000, true);
    expect(resampled.length).toBe(MAX_RESAMPLE_POINTS);

    const hugeDirectPointCloud = Array.from({ length: 200_000 }, (_, index) => ({
      x: index,
      y: Math.cos(index / 7) * 80
    }));
    expect(() => boundsOf(hugeDirectPointCloud)).not.toThrow();
    expect(boundsOf(hugeDirectPointCloud).width).toBe(199_999);
    expect(generateTrace(createMechanism('four-bar', 99), 1_000_000).length).toBeLessThanOrEqual(720);

    const smoothed = smoothTrackingPoints(path.points, true, 24);
    expect(smoothed.length).toBeLessThanOrEqual(MAX_TRACKING_POINTS);

    const transferred = trackingToPath(imported.tracking.annotations[0], 'right_wrist');
    expect(transferred.points.length).toBeLessThanOrEqual(MAX_TRACKING_POINTS);
    expect(analyzePath(transferred).pathLength).toBeGreaterThan(0);

    imported.metadata.name = '<script>alert("x")</script> & unsafe';
    imported.lab.activeNotes = 'note <tag> & value';
    const json = exportProjectJson(imported);
    const study = exportStudyBundle(imported, 0);
    [json, study].forEach((artifact) => {
      expect(artifact).toContain('\\u003c');
      expect(artifact).toContain('\\u003e');
      expect(artifact).toContain('\\u0026');
      expect(artifact).not.toContain('<script');
      expect(artifact).not.toContain('<tag>');
      expect(artifact).not.toContain('& unsafe');
    });
  });
});
