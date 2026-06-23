import { describe, expect, it } from 'vitest';
import { actionForKeyboardEvent, appActionDefinitions, enabledActionIds } from '../actions';
import { exportStudyBundle } from '../exporters';
import {
  canRedoProject,
  canUndoProject,
  commitProjectCommand,
  createProjectHistory,
  redoProjectHistory,
  undoProjectHistory
} from '../history';
import { createMechanism, computeMechanismState, mechanismTemplates } from '../mechanisms';
import { buildMS4NExportPayload, MS4N_SCHEMA_VERSION, validateMS4NEpisode } from '../ms4n';
import { applyRuntimeWebShellEvidence, buildFeatureAudit, defaultFeatureAuditCapabilities, pythonDesktopMechanismTypes, webExtensionMechanismTypes } from '../parity';
import { createDefaultProject } from '../project';
import { defaultResourceManifestState, mechanismResourceStatus } from '../resourceManifest';
import { createSchedulerPolicy, orderSchedulerTasks, planAnimationFrame } from '../scheduler';
import { createTrackingAnnotation } from '../tracking';
import { inferVisionAssistFromTracking } from '../vision';

describe('project-state command history and action registry', () => {
  it('undoes, redoes, and clears redo for project-state-only commands', () => {
    const initial = createDefaultProject();
    const history = createProjectHistory(initial);
    const edited = commitProjectCommand(history, 'Add mechanism', {
      ...initial,
      mechanisms: [...initial.mechanisms, createMechanism('five-bar', 99)]
    });

    expect(canUndoProject(edited)).toBe(true);
    expect(canRedoProject(edited)).toBe(false);
    expect(edited.past).toHaveLength(1);
    expect(edited.past[0].command.projectOnly).toBe(true);

    const undone = undoProjectHistory(edited);
    expect(undone.present).toBe(initial);
    expect(canRedoProject(undone)).toBe(true);

    const redone = redoProjectHistory(undone);
    expect(redone.present.mechanisms).toHaveLength(initial.mechanisms.length + 1);

    const branched = commitProjectCommand(undone, 'Rename project', {
      ...undone.present,
      metadata: { ...undone.present.metadata, name: 'Branch after undo' }
    });
    expect(branched.future).toHaveLength(0);
  });

  it('maps shortcuts through the action registry', () => {
    expect(appActionDefinitions.map((action) => action.id)).toEqual(expect.arrayContaining([
      'saveJson',
      'importProject',
      'exportSvg',
      'exportBlueprint',
      'exportDxf',
      'exportStudy',
      'resetView',
      'undo',
      'redo'
    ]));
    expect(enabledActionIds({ undo: false, redo: true })).not.toContain('undo');
    expect(enabledActionIds({ undo: false, redo: true })).toContain('redo');
    expect(actionForKeyboardEvent({ key: 'z', ctrlKey: true })).toBe('undo');
    expect(actionForKeyboardEvent({ key: 'Z', ctrlKey: true, shiftKey: true })).toBe('redo');
    expect(actionForKeyboardEvent({ key: 'y', metaKey: true })).toBe('redo');
    expect(actionForKeyboardEvent({ key: 's', ctrlKey: true })).toBe('saveJson');
    expect(actionForKeyboardEvent({ key: '0', ctrlKey: true })).toBe('resetView');
  });
});

describe('single scheduler playback policy', () => {
  it('plans target-FPS frame steps, task priority, reduced motion, and preset budgets', () => {
    const project = createDefaultProject();
    const policy = createSchedulerPolicy(project.settings);
    const plan = planAnimationFrame(policy, 50, project.settings.animationDuration, [
      { id: 'render', priority: 1 },
      { id: 'compute', priority: 10 },
      { id: 'bind', priority: 10 }
    ]);

    expect(policy.frameIntervalMs).toBeCloseTo(1000 / 60, 2);
    expect(plan.steps.length).toBeGreaterThanOrEqual(2);
    expect(plan.orderedTaskIds).toEqual(['compute', 'bind', 'render']);

    const performancePolicy = createSchedulerPolicy({ ...project.settings, performancePreset: 'performance' });
    const overloaded = planAnimationFrame(performancePolicy, 500, 2);
    expect(overloaded.steps.length).toBeLessThanOrEqual(performancePolicy.maxStepsPerFrame);
    expect(overloaded.skippedFrames).toBeGreaterThan(0);

    const reduced = planAnimationFrame(createSchedulerPolicy({ ...project.settings, reducedMotion: true }), 500, 2);
    expect(reduced.steps).toHaveLength(0);

    expect(createSchedulerPolicy({ ...project.settings, performancePreset: 'quality' }).maxStepsPerFrame)
      .toBeGreaterThan(createSchedulerPolicy({ ...project.settings, performancePreset: 'performance' }).maxStepsPerFrame);
    expect(orderSchedulerTasks([{ id: 'low', priority: 1 }, { id: 'high', priority: 3 }]).map((task) => task.id)).toEqual(['high', 'low']);
  });
});

describe('ms4n-web-v1 lab schema and study export enrichment', () => {
  it('validates episodes and embeds versioned MS4N payloads in study exports', () => {
    const project = createDefaultProject();
    const valid = validateMS4NEpisode(project.lab.episodes[0], project.lab.kitAssets, { closure_error: 4 });
    expect(valid.valid).toBe(true);
    expect(valid.evidenceOutputs.length).toBeGreaterThan(0);
    expect(valid.traceMetrics.closure_error).toBe(4);

    const invalid = validateMS4NEpisode({
      ...project.lab.episodes[0],
      symptom: '',
      suspectedCause: '',
      repairAction: '',
      evidenceOutputs: []
    }, project.lab.kitAssets);
    expect(invalid.valid).toBe(false);
    expect(invalid.evidenceOutputs).toEqual([]);
    expect(invalid.warnings).toEqual(expect.arrayContaining(['Missing symptom', 'Missing suspected cause', 'Missing repair action', 'Missing evidence output']));
    expect(invalid.suggestedEvidenceOutputs.length).toBeGreaterThan(0);

    const ms4n = buildMS4NExportPayload(project, { average_trace_points: 64 });
    expect(ms4n.schema_version).toBe(MS4N_SCHEMA_VERSION);
    expect(ms4n.trace_summary.episode_count).toBe(project.lab.episodes.length);
    expect(ms4n.kit_evidence_map['bar-board']).toEqual(expect.any(Array));

    const study = JSON.parse(exportStudyBundle(project, 45)) as { schema_version: string; ms4n: ReturnType<typeof buildMS4NExportPayload> };
    expect(study.schema_version).toBe('automataii.web.study_bundle.v1');
    expect(study.ms4n.schema_version).toBe(MS4N_SCHEMA_VERSION);
    expect(study.ms4n.episodes).toHaveLength(project.lab.episodes.length);
    expect(study.ms4n.validation_warnings).toEqual(expect.any(Array));
  });
});

describe('browser-safe vision parity and scotch-yoke classification', () => {
  it('returns staged browser-safe vision output and honest non-web ML classification', () => {
    const annotation = createTrackingAnnotation('walk-cycle.gif', 'gif', [
      { x: 20, y: 140 },
      { x: 86, y: 38 },
      { x: 170, y: 26 },
      { x: 232, y: 92 },
      { x: 278, y: 148 },
      { x: 338, y: 104 }
    ], true, 2.8);
    const result = inferVisionAssistFromTracking(annotation);
    expect(result.stages.map((stage) => stage.id)).toEqual([
      'preprocess',
      'tracking-normalization',
      'skeleton-inference',
      'part-classification',
      'parity-classification'
    ]);
    expect(result.status.confidence).toBeGreaterThan(0);
    expect(result.status.inferredJointCount).toBeGreaterThanOrEqual(6);
    expect(result.status.warnings.join(' ')).toContain('Browser-safe vision parity');
    expect(result.parity.nonWebInfrastructure.join(' ')).toContain('ONNX');

    const empty = inferVisionAssistFromTracking();
    expect(empty.status.confidence).toBe(0);
    expect(empty.stages.some((stage) => stage.status === 'blocked')).toBe(true);
  });

  it('keeps MechAnim-only primitives available while excluding them from Python desktop parity requirements', () => {
    expect(mechanismTemplates.map((template) => template.type)).toEqual(expect.arrayContaining(['crank', 'quick-return', 'scotch-yoke']));
    expect(computeMechanismState(createMechanism('scotch-yoke', 0), 30).valid).toBe(true);
    expect(computeMechanismState(createMechanism('quick-return', 0), 30).valid).toBe(true);
    expect(computeMechanismState(createMechanism('crank', 0), 30).valid).toBe(true);
    expect(pythonDesktopMechanismTypes).toEqual(expect.arrayContaining([
      'four-bar',
      'five-bar',
      'six-bar',
      'cam-follower',
      'gear-pair',
      'planetary-gear',
      'slider-crank'
    ]));
    expect(pythonDesktopMechanismTypes).not.toContain('scotch-yoke');
    expect(pythonDesktopMechanismTypes).not.toContain('quick-return');
    expect(pythonDesktopMechanismTypes).not.toContain('crank');
    expect(webExtensionMechanismTypes).toEqual(expect.arrayContaining(['crank', 'quick-return', 'scotch-yoke']));
    expect(mechanismResourceStatus('scotch-yoke')?.status).toBe('web-only');
    expect(mechanismResourceStatus('quick-return')?.status).toBe('web-only');
    expect(mechanismResourceStatus('crank')?.status).toBe('web-only');
    expect(defaultResourceManifestState().webOnlyMechanisms).toEqual(expect.arrayContaining(['crank', 'quick-return', 'scotch-yoke']));
  });

  it('can back web-shell audit claims with runtime probes', () => {
    const project = createDefaultProject();
    const failedAudit = buildFeatureAudit(project, applyRuntimeWebShellEvidence(defaultFeatureAuditCapabilities, {
      manifestLinked: false,
      serviceWorkerAvailable: true,
      actionRegistryWired: true
    }));
    const passedAudit = buildFeatureAudit(project, applyRuntimeWebShellEvidence(defaultFeatureAuditCapabilities, {
      manifestLinked: true,
      serviceWorkerAvailable: true,
      actionRegistryWired: true
    }));

    expect(failedAudit.complete).toBe(false);
    expect(failedAudit.missingRequired.map((item) => item.id)).toContain('web-shell');
    expect(passedAudit.complete).toBe(true);
  });
});
