import { describe, expect, it } from 'vitest';
import { analyzePath, analyzePoints, snapPoint } from '../analysis';
import { exportBlueprintSvg, exportSceneDxf, exportSceneSvg, exportStudyBundle } from '../exporters';
import { applyMechanismHandleDrag, computeMechanismState, createMechanism, generateTrace, MAX_GEAR_TEETH, MAX_PLANET_COUNT, mechanismTemplates } from '../mechanisms';
import { fitMechanismToPath, scoreTraceToPath } from '../optimizer';
import { buildFeatureAudit, requiredMechanismTypes } from '../parity';
import { simulateMechanismPhysics } from '../physics';
import { createDefaultProject, normalizeProject, parseProject, serializeProject } from '../project';
import { createTrackingAnnotation, smoothTrackingPoints, trackingToPath } from '../tracking';
import { inferVisionAssistFromTracking } from '../vision';

const finitePoint = (point: { x: number; y: number }) => {
  expect(Number.isFinite(point.x)).toBe(true);
  expect(Number.isFinite(point.y)).toBe(true);
};

describe('mechanism state generation', () => {
  it.each(mechanismTemplates.map((template) => template.type))('computes finite state for %s', (type) => {
    const mechanism = createMechanism(type, 0);
    const state = computeMechanismState(mechanism, 42);
    expect(state.type).toBe(type);
    expect(state.valid).toBe(true);
    finitePoint(state.effector);
    expect(Object.keys(state.positions).length).toBeGreaterThan(1);
  });

  it('four-bar exposes Automataii-style O1/O4/A/B nodes', () => {
    const mechanism = createMechanism('four-bar', 0);
    const state = computeMechanismState(mechanism, 15);
    expect(Object.keys(state.positions)).toEqual(expect.arrayContaining(['O1', 'O4', 'A', 'B', 'effector']));
    expect(state.links.some((link) => link.role === 'coupler')).toBe(true);
  });

  it('five-bar and six-bar expose floating and rocker nodes', () => {
    const five = computeMechanismState(createMechanism('five-bar', 0), 15);
    const six = computeMechanismState(createMechanism('six-bar', 0), 15);
    expect(Object.keys(five.positions)).toEqual(expect.arrayContaining(['G1', 'G2', 'C1', 'C2', 'P']));
    expect(Object.keys(six.positions)).toEqual(expect.arrayContaining(['G3', 'Q']));
  });

  it('slider-crank and scotch-yoke expose linear motion nodes', () => {
    const slider = computeMechanismState(createMechanism('slider-crank', 0), 30);
    const yoke = computeMechanismState(createMechanism('scotch-yoke', 0), 30);
    expect(Object.keys(slider.positions)).toEqual(expect.arrayContaining(['O', 'crankPin', 'slider', 'railA', 'railB']));
    expect(slider.links.some((link) => link.role === 'slider')).toBe(true);
    expect(Object.keys(yoke.positions)).toEqual(expect.arrayContaining(['O', 'crankPin', 'yokeCenter', 'slotA', 'slotB']));
    finitePoint(slider.effector);
    finitePoint(yoke.effector);
  });

  it('preserves MechAnim crank and quick-return primitives as web templates', () => {
    const crank = computeMechanismState(createMechanism('crank', 0), 30);
    const quickReturn = computeMechanismState(createMechanism('quick-return', 0), 30);
    expect(Object.keys(crank.positions)).toEqual(expect.arrayContaining(['O', 'crankPin', 'effector']));
    expect(Object.keys(quickReturn.positions)).toEqual(expect.arrayContaining(['O', 'crankPin', 'pivot', 'rockerTip', 'slotOutput']));
    expect(crank.valid).toBe(true);
    expect(quickReturn.valid).toBe(true);
    finitePoint(crank.effector);
    finitePoint(quickReturn.effector);
  });

  it('marks five-bar closure fallback as invalid/caution instead of safe solved', () => {
    const mechanism = createMechanism('five-bar', 0);
    mechanism.params = { ...mechanism.params, groundLink: 900, inputLink: 10, outputLink: 10, couplerLink: 5 };
    const state = computeMechanismState(mechanism, 0);
    expect(state.valid).toBe(false);
    expect(state.safety.level).toBe('caution');
    expect(state.metadata.closureFallback).toBe(true);
  });

  it('clamps gear teeth and planet counts to rendering-safe maxima', () => {
    const gear = createMechanism('gear-pair', 0);
    gear.params = { ...gear.params, teeth: 1_000_000, outputTeeth: 1_000_000 };
    const gearState = computeMechanismState(gear, 15);
    expect(gearState.gears?.every((g) => g.teeth <= MAX_GEAR_TEETH)).toBe(true);

    const planetary = createMechanism('planetary-gear', 0);
    planetary.params = { ...planetary.params, planetCount: 1000 };
    const planetaryState = computeMechanismState(planetary, 15);
    expect(planetaryState.metadata.count).toBe(MAX_PLANET_COUNT);
  });

  it('generates traces without throwing', () => {
    const mechanism = createMechanism('cam-follower', 0);
    const trace = generateTrace(mechanism, 48);
    expect(trace.length).toBeGreaterThanOrEqual(48);
    trace.forEach(finitePoint);
  });

  it('maps four-bar node drags back into editable dimensions', () => {
    const mechanism = createMechanism('four-bar', 0);
    const inputEdited = applyMechanismHandleDrag(mechanism, 'A', { x: mechanism.anchor.x + 96, y: mechanism.anchor.y }, 0);
    expect(inputEdited.params.inputLink).toBeCloseTo(96);

    const state = computeMechanismState(inputEdited, 0);
    const effectorEdited = applyMechanismHandleDrag(inputEdited, 'effector', { x: state.positions.A.x + 30, y: state.positions.A.y + 40 }, 0);
    expect(effectorEdited.params.couplerPointDist).toBeCloseTo(50);
    expect(effectorEdited.params.couplerPointAngle).not.toBe(inputEdited.params.couplerPointAngle);
  });

  it('maps cam and gear handle drags into native parameters', () => {
    const cam = createMechanism('cam-follower', 0);
    const camState = computeMechanismState(cam, 0);
    const camEdited = applyMechanismHandleDrag(cam, 'followerBase', { x: camState.positions.contact.x, y: camState.positions.contact.y - 180 }, 0);
    expect(camEdited.params.followerLength).toBeCloseTo(180);

    const gear = createMechanism('gear-pair', 0);
    const gearEdited = applyMechanismHandleDrag(gear, 'outputCenter', { x: gear.anchor.x + 180, y: gear.anchor.y }, 0);
    expect(gearEdited.params.outputRadius).toBeCloseTo(132);
    expect(gearEdited.rotationDeg).toBeCloseTo(0);
  });

  it('maps linear mechanism handles into slider and yoke parameters', () => {
    const slider = createMechanism('slider-crank', 0);
    const sliderEdited = applyMechanismHandleDrag(slider, 'crankPin', { x: slider.anchor.x + 84, y: slider.anchor.y }, 0);
    expect(sliderEdited.params.crankRadius).toBeCloseTo(84);

    const yoke = createMechanism('scotch-yoke', 0);
    const yokeState = computeMechanismState(yoke, 0);
    const yokeEdited = applyMechanismHandleDrag(yoke, 'slotB', { x: yokeState.positions.yokeCenter.x, y: yokeState.positions.yokeCenter.y + 110 }, 0);
    expect(yokeEdited.params.slotHeight).toBeCloseTo(220);
  });

  it('maps crank and quick-return handles into MechAnim-compatible parameters', () => {
    const crank = createMechanism('crank', 0);
    const crankEdited = applyMechanismHandleDrag(crank, 'crankPin', { x: crank.anchor.x + 72, y: crank.anchor.y }, 0);
    expect(crankEdited.params.crankRadius).toBeCloseTo(72);

    const quickReturn = createMechanism('quick-return', 0);
    const quickState = computeMechanismState(quickReturn, 0);
    const pivotEdited = applyMechanismHandleDrag(quickReturn, 'pivot', { x: quickReturn.anchor.x + 180, y: quickReturn.anchor.y + 44 }, 0);
    expect(pivotEdited.params.pivotDistance).toBeCloseTo(180);
    expect(pivotEdited.params.pivotOffset).toBeCloseTo(44);
    const rockerEdited = applyMechanismHandleDrag(quickReturn, 'rockerTip', { x: quickState.positions.pivot.x + 120, y: quickState.positions.pivot.y }, 0);
    expect(rockerEdited.params.rockerLength).toBeCloseTo(120);
  });
});

describe('project serialization and svg export', () => {
  it('starts new web projects in the minimal light theme', () => {
    const project = createDefaultProject();
    expect(project.settings.theme).toBe('light');
    const importedDark = normalizeProject({ settings: { theme: 'dark' } });
    expect(importedDark.settings.theme).toBe('dark');
  });

  it('round-trips a default project', () => {
    const project = createDefaultProject();
    const parsed = parseProject(serializeProject(project));
    expect(parsed.metadata.name).toBe(project.metadata.name);
    expect(parsed.mechanisms.length).toBe(project.mechanisms.length);
    expect(Object.keys(parsed.parts)).toContain('torso');
  });

  it('imports Python-shaped mechanism maps without falling back to demo mechanisms', () => {
    const parsed = normalizeProject({
      mechanisms: {
        mech_1: { part_name: 'right_wrist', type: '4_bar_linkage', params: { groundLink: 123 }, color: '#123456' },
        mech_2: { part_name: 'left_ankle', type: 'crank_slider', parameters: { crankRadius: 44 } },
        mech_3: { part_name: 'right_ankle', type: 'scotch_yoke' }
      },
      paths: {
        right_wrist: { part_name: 'right_wrist', points: [[1, 2], [3, 4]], is_closed: false }
      }
    });
    expect(parsed.mechanisms).toHaveLength(3);
    expect(parsed.mechanisms[0].id).toBe('mech_1');
    expect(parsed.mechanisms[0].type).toBe('four-bar');
    expect(parsed.mechanisms[1].type).toBe('slider-crank');
    expect(parsed.mechanisms[2].type).toBe('scotch-yoke');
    expect(parsed.mechanisms[0].partName).toBe('right_wrist');
    expect(parsed.paths.right_wrist.points).toEqual([{ x: 1, y: 2 }, { x: 3, y: 4 }]);
  });

  it('ignores malformed project entries and sanitizes untrusted colors', () => {
    expect(() => normalizeProject({ mechanisms: [null, { type: 'gear-pair', color: '" onload="alert(1)', params: { teeth: 999999 } }], skeleton: { joints: null } })).not.toThrow();
    const parsed = normalizeProject({ mechanisms: [{ type: 'gear-pair', color: '" onload="alert(1)' }] });
    expect(parsed.mechanisms[0].color).toBe('#facc15');
    const svg = exportSceneSvg(parsed, 20);
    expect(svg).not.toContain('onload');
  });

  it('exports a scene svg with mechanisms and project name', () => {
    const project = createDefaultProject();
    const svg = exportSceneSvg(project, 20);
    expect(svg).toContain('<svg');
    expect(svg).toContain(project.metadata.name);
    expect(svg).toContain('data-mechanism');
  });

  it('exports DXF and study bundle evidence surfaces', () => {
    const project = createDefaultProject();
    project.paths['bad\n0\nLINE'] = { partName: 'bad\n0\nLINE', points: [{ x: 1, y: 2 }, { x: 3, y: 4 }], totalDuration: 1, isClosed: false, enabled: true };
    const dxf = exportSceneDxf(project, 20);
    const study = exportStudyBundle(project, 20);
    expect(dxf).toContain('SECTION');
    expect(dxf).toContain('ENTITIES');
    expect(dxf).not.toContain('bad\n0\nLINE');
    expect(study).toContain('automataii.web.study_bundle.v1');
    expect(study).toContain('episode_jsonl');
  });

  it('exports fabrication blueprint svg with escaped labels', () => {
    const project = createDefaultProject();
    project.metadata.name = '<bad blueprint>';
    const blueprint = exportBlueprintSvg(project, 20);
    expect(blueprint).toContain('automataii.web.blueprint.v1');
    expect(blueprint).toContain('data-layer="drill"');
    expect(blueprint).toContain('&lt;bad blueprint&gt;');
    expect(blueprint).not.toContain('<bad blueprint>');
  });

  it('round-trips presets and timeline keyframes', () => {
    const project = createDefaultProject();
    project.settings.viewport = { x: 42, y: -24, zoom: 1.7, panMode: true };
    const parsed = parseProject(serializeProject(project));
    expect(parsed.presets.length).toBeGreaterThan(0);
    expect(parsed.timeline.keyframes.length).toBeGreaterThan(0);
    expect(parsed.vision.confidence).toBeGreaterThanOrEqual(0);
    expect(parsed.settings.viewport).toEqual({ x: 42, y: -24, zoom: 1.7, panMode: true });
    const clamped = parseProject(JSON.stringify({ settings: { viewport: { x: 999999, y: -999999, zoom: 99, panMode: true } } }));
    expect(clamped.settings.viewport.zoom).toBe(4);
    expect(clamped.settings.viewport.x).toBe(2000);
  });
});

describe('feature integration audit', () => {
  it('reports full feature integration for the default web project', () => {
    const audit = buildFeatureAudit(createDefaultProject());
    expect(audit.complete).toBe(true);
    expect(audit.percent).toBe(100);
    expect(audit.missingRequired).toEqual([]);
    expect(audit.categories.every((category) => category.passed === category.total)).toBe(true);
    expect(audit.items.find((item) => item.id === 'physics-aware-simulation')?.passed).toBe(true);
  });

  it('covers every required mechanism template family', () => {
    const templateTypes = mechanismTemplates.map((template) => template.type);
    expect(templateTypes).toEqual(expect.arrayContaining(requiredMechanismTypes));
    expect(buildFeatureAudit(createDefaultProject()).items.find((item) => item.id === 'mechanism-library')?.passed).toBe(true);
  });

  it('surfaces actionable failures when integration data is missing', () => {
    const project = createDefaultProject();
    project.mechanisms = [];
    project.paths = {};
    const audit = buildFeatureAudit(project);
    expect(audit.complete).toBe(false);
    expect(audit.missingRequired.map((item) => item.id)).toEqual(expect.arrayContaining(['paths', 'mechanism-design', 'path-fitting']));
  });
});

describe('physics-aware animation simulation', () => {
  it('samples finite velocity, acceleration, and energy for a selected mechanism', () => {
    const mechanism = createMechanism('four-bar', 0);
    const report = simulateMechanismPhysics(mechanism, 4, 35, 64);
    expect(report.samples).toHaveLength(64);
    expect(report.current.valid).toBe(true);
    finitePoint(report.current.position);
    finitePoint(report.current.velocity);
    finitePoint(report.current.acceleration);
    expect(Number.isFinite(report.maxSpeed)).toBe(true);
    expect(Number.isFinite(report.maxAcceleration)).toBe(true);
    expect(Number.isFinite(report.peakKineticEnergy)).toBe(true);
    expect(report.stabilityScore).toBeGreaterThanOrEqual(0);
    expect(report.stabilityScore).toBeLessThanOrEqual(1);
  });

  it('warns when timing creates aggressive physics loads', () => {
    const mechanism = createMechanism('slider-crank', 0);
    const report = simulateMechanismPhysics(mechanism, 0.25, 90, 48);
    expect(report.warnings.join(' ')).toContain('Animation duration is very short');
    expect(['caution', 'danger']).toContain(report.status);
  });
});

describe('path fitting and tracking helpers', () => {
  it('fits a mechanism to a target path without worsening the score', () => {
    const project = createDefaultProject();
    const mechanism = createMechanism('slider-crank', 0);
    const path = project.paths.right_wrist;
    const initial = scoreTraceToPath(generateTrace(mechanism, 48), path.points);
    const result = fitMechanismToPath(mechanism, path, 24, 7);
    expect(result.score).toBeLessThanOrEqual(initial);
    finitePoint(result.candidate.anchor);
  });

  it('smooths tracking annotations and transfers them into paths', () => {
    const points = [{ x: 0, y: 0 }, { x: 50, y: 25 }, { x: 100, y: 0 }, { x: 125, y: 40 }];
    const smoothed = smoothTrackingPoints(points, false, 4);
    expect(smoothed.length).toBeGreaterThan(points.length);
    const annotation = createTrackingAnnotation('walk.gif', 'gif', points, true, 1.8);
    const path = trackingToPath(annotation, 'right_wrist');
    expect(path.partName).toBe('right_wrist');
    expect(path.points.length).toBeGreaterThan(points.length);
    expect(path.isClosed).toBe(true);
  });

  it('infers browser-side vision assist rig from tracking annotations', () => {
    const points = [{ x: 10, y: 80 }, { x: 40, y: 35 }, { x: 90, y: 20 }, { x: 130, y: 70 }, { x: 160, y: 105 }];
    const annotation = createTrackingAnnotation('capture.png', 'image', points, false, 2);
    const result = inferVisionAssistFromTracking(annotation);
    expect(result.status.confidence).toBeGreaterThan(0);
    expect(result.status.inferredJointCount).toBeGreaterThan(1);
    expect(Object.keys(result.parts)).toEqual(expect.arrayContaining(['torso', 'head']));
    expect(result.pathPoints.every((point) => Number.isFinite(point.x) && Number.isFinite(point.y))).toBe(true);
  });

  it('analyzes paths and reports deterministic snap behavior', () => {
    expect(snapPoint({ x: 9, y: 23 }, true, 16)).toEqual({ x: 16, y: 16 });
    expect(snapPoint({ x: 9, y: 23 }, false, 16)).toEqual({ x: 9, y: 23 });
    const analysis = analyzePoints([{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 100, y: 0 }], false);
    expect(analysis.pointCount).toBe(3);
    expect(analysis.pathLength).toBe(100);
    expect(analysis.maxStep).toBe(90);
    const empty = analyzePath(undefined);
    expect(empty.warnings).toContain('Need at least two points for motion analysis');
  });
});
