import { useEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode, type RefObject } from 'react';
import {
  Activity,
  Boxes,
  Camera,
  CirclePlay,
  Crosshair,
  Download,
  FileArchive,
  FileCode2,
  FileUp,
  Gauge,
  Pause,
  RefreshCw,
  Route,
  Save,
  Settings,
  Sparkles,
  Zap,
  UserRoundCog,
  WandSparkles,
  Workflow,
  Wrench
} from 'lucide-react';
import { StudioCanvas } from './components/StudioCanvas';
import { actionForKeyboardEvent, appActionDefinitions, enabledActionIds, isEditableTarget, type AppActionId } from './domain/actions';
import { exportBlueprintSvg, exportProjectJson, exportSceneDxf, exportSceneSvg, exportStudyBundle } from './domain/exporters';
import { boundsOf, pathLength, resamplePath } from './domain/geometry';
import { canRedoProject, canUndoProject, commitProjectCommand, createProjectHistory, historySummary, redoProjectHistory, replaceProjectHistoryRoot, undoProjectHistory } from './domain/history';
import { analyzeMechanismTrace, analyzePath, snapPoint, type MechanismAnalysis, type MotionAnalysis } from './domain/analysis';
import { applyMechanismHandleDrag, computeMechanismState, createMechanism, generateTrace, mechanismTemplates } from './domain/mechanisms';
import { createRecommendedMechanism, fitMechanismToPath, recommendMechanismsForPath, type FitResult } from './domain/optimizer';
import { applyRuntimeWebShellEvidence, buildFeatureAudit, defaultFeatureAuditCapabilities, type FeatureAuditCapabilities, type FeatureAuditSummary } from './domain/parity';
import { simulateMechanismPhysics, type PhysicsReport } from './domain/physics';
import { createDefaultProject, normalizeProject, parseProject } from './domain/project';
import { createSchedulerPolicy, planAnimationFrame, schedulerStatusText } from './domain/scheduler';
import { createTrackingAnnotation, normalizeTrackerPoint, smoothTrackingPoints, trackingToPath } from './domain/tracking';
import { inferVisionAssistFromTracking } from './domain/vision';
import type { MechanismConfig, MechanismType, PartData, Point, ProjectState, WorkflowSection } from './types';
import { downloadText } from './utils/download';

const sectionMeta: Array<{ id: WorkflowSection; label: string; icon: ReactNode; summary: string }> = [
  { id: 'welcome', label: 'Welcome', icon: <Sparkles />, summary: 'Project launchpad, parity map, and workflow overview.' },
  { id: 'character', label: 'Character Selection', icon: <UserRoundCog />, summary: 'Image/reference import, manual tracking, parts, skeleton, and anchors.' },
  { id: 'paths', label: 'Path Editor', icon: <Route />, summary: 'Draw, smooth, resample, close, and assign motion paths.' },
  { id: 'studio', label: 'Mechanism Design', icon: <Gauge />, summary: 'Animate mechanisms, traces, path fitting, and character binding.' },
  { id: 'foundry', label: 'Mechanism Foundry', icon: <Boxes />, summary: 'Catalog-driven mechanism creation, recommendations, and fabrication metadata.' },
  { id: 'lab', label: 'Lab', icon: <Activity />, summary: 'MS4N trace autopsy, kit catalog, episode notes, and study exports.' },
  { id: 'options', label: 'Options', icon: <Settings />, summary: 'Units, theme, animation, physics snap, and display toggles.' }
];

const format = (value: number, digits = 1): string => Number.isFinite(value) ? value.toFixed(digits) : '—';
const slug = (value: string): string => value.trim().replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').toLowerCase() || 'automataii-web';

const updateProject = (project: ProjectState, patch: Partial<ProjectState>): ProjectState => ({
  ...project,
  ...patch,
  metadata: { ...project.metadata, ...(patch.metadata ?? {}), modifiedAt: new Date().toISOString() }
});

const numeric = (value: string, fallback: number): number => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

const AUTOSAVE_KEY = 'automataii-web-autosave-v1';
const AUTOSAVE_RECOVERY_KEY = `${AUTOSAVE_KEY}:recovery`;

interface InitialProjectLoad {
  project: ProjectState;
  autosaveBlocked: boolean;
  status: string;
}

const loadInitialProject = (): InitialProjectLoad => {
  if (typeof window === 'undefined') {
    return { project: createDefaultProject(), autosaveBlocked: false, status: 'Restored local workspace' };
  }
  try {
    const saved = window.localStorage.getItem(AUTOSAVE_KEY);
    return {
      project: saved ? parseProject(saved) : createDefaultProject(),
      autosaveBlocked: false,
      status: saved ? 'Restored local workspace' : 'Started demo workspace'
    };
  } catch (error) {
    try {
      const raw = window.localStorage.getItem(AUTOSAVE_KEY);
      if (raw) window.localStorage.setItem(AUTOSAVE_RECOVERY_KEY, raw);
    } catch {
      // Keep loading the demo project even if recovery storage is unavailable.
    }
    return {
      project: createDefaultProject(),
      autosaveBlocked: true,
      status: `Autosave recovery needed: ${error instanceof Error ? error.message : 'saved project could not be parsed'}`
    };
  }
};

function App() {
  const [initialLoad] = useState<InitialProjectLoad>(() => loadInitialProject());
  const [history, setHistory] = useState(() => createProjectHistory(initialLoad.project));
  const project = history.present;
  const [activeSection, setActiveSection] = useState<WorkflowSection>('welcome');
  const [selectedId, setSelectedId] = useState<string | undefined>();
  const [selectedPartName, setSelectedPartName] = useState('right_arm');
  const [angle, setAngle] = useState(35);
  const [isPlaying, setIsPlaying] = useState(false);
  const [drawingPath, setDrawingPath] = useState(false);
  const [trackingDraft, setTrackingDraft] = useState<Point[]>([]);
  const [trackingClosed, setTrackingClosed] = useState(true);
  const [fitResult, setFitResult] = useState<FitResult | undefined>();
  const [foundryFilter, setFoundryFilter] = useState('all');
  const [importError, setImportError] = useState<string>();
  const [cameraStream, setCameraStream] = useState<MediaStream | undefined>();
  const [cameraError, setCameraError] = useState<string>();
  const [autosaveStatus, setAutosaveStatus] = useState(initialLoad.status);
  const [autosaveBlocked, setAutosaveBlocked] = useState(initialLoad.autosaveBlocked);
  const [skippedFrames, setSkippedFrames] = useState(0);
  const [runtimeCapabilities, setRuntimeCapabilities] = useState<FeatureAuditCapabilities>(defaultFeatureAuditCapabilities);
  const referenceUrlRef = useRef<string | undefined>(undefined);
  const cameraVideoRef = useRef<HTMLVideoElement | null>(null);
  const projectInputRef = useRef<HTMLInputElement | null>(null);
  const referenceInputRef = useRef<HTMLInputElement | null>(null);

  const selected = project.mechanisms.find((m) => m.id === selectedId) ?? project.mechanisms[0];
  const selectedState = selected ? computeMechanismState(selected, angle) : undefined;
  const selectedTrace = useMemo(() => selected ? generateTrace(selected, 128) : [], [selected]);
  const currentPath = project.paths[project.selectedPathPart];
  const recommendations = useMemo(() => recommendMechanismsForPath(currentPath), [currentPath]);
  const pathAnalysis = useMemo(() => analyzePath(currentPath), [currentPath]);
  const mechanismAnalysis = useMemo(() => selected ? analyzeMechanismTrace(selected, 96) : undefined, [selected]);
  const jointOptions = useMemo(() => Object.keys(project.skeleton?.joints ?? project.parts), [project.skeleton, project.parts]);
  const featureAudit = useMemo(() => buildFeatureAudit(project, runtimeCapabilities), [project, runtimeCapabilities]);
  const schedulerPolicy = useMemo(() => createSchedulerPolicy(project.settings), [project.settings]);
  const schedulerStatus = useMemo(() => schedulerStatusText(schedulerPolicy, skippedFrames), [schedulerPolicy, skippedFrames]);
  const physicsReport = useMemo(
    () => selected ? simulateMechanismPhysics(selected, project.settings.animationDuration, angle, 128) : undefined,
    [selected, project.settings.animationDuration, angle]
  );

  const executeProjectCommand = (label: string, updater: ProjectState | ((prev: ProjectState) => ProjectState)): void => {
    setHistory((prev) => {
      const next = typeof updater === 'function' ? updater(prev.present) : updater;
      return commitProjectCommand(prev, label, next);
    });
  };

  const setProject = (updater: ProjectState | ((prev: ProjectState) => ProjectState)): void => {
    executeProjectCommand('Project edit', updater);
  };

  const undoProject = (): void => setHistory((prev) => undoProjectHistory(prev));
  const redoProject = (): void => setHistory((prev) => redoProjectHistory(prev));
  const replaceProjectRoot = (nextProject: ProjectState): void => {
    setHistory((prev) => replaceProjectHistoryRoot(prev, nextProject));
  };

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const manifestLinked = Boolean(document.querySelector('link[rel="manifest"]'));
    const serviceWorkerAvailable = typeof navigator !== 'undefined' && 'serviceWorker' in navigator;
    setRuntimeCapabilities(applyRuntimeWebShellEvidence(defaultFeatureAuditCapabilities, {
      manifestLinked,
      serviceWorkerAvailable,
      actionRegistryWired: appActionDefinitions.length >= 10
    }));
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const timer = window.setTimeout(() => {
      try {
        if (autosaveBlocked) {
          setAutosaveStatus('Autosave paused: recover or reset the previous saved workspace first');
          return;
        }
        window.localStorage.setItem(AUTOSAVE_KEY, exportProjectJson(project));
        setAutosaveStatus(`Autosaved ${new Date().toLocaleTimeString()}`);
      } catch {
        setAutosaveStatus('Autosave unavailable');
      }
    }, 300);
    return () => window.clearTimeout(timer);
  }, [autosaveBlocked, project]);

  useEffect(() => () => {
    if (referenceUrlRef.current) URL.revokeObjectURL(referenceUrlRef.current);
  }, []);

  useEffect(() => () => {
    cameraStream?.getTracks().forEach((track) => track.stop());
  }, [cameraStream]);

  useEffect(() => {
    if (cameraVideoRef.current && cameraStream) {
      cameraVideoRef.current.srcObject = cameraStream;
      void cameraVideoRef.current.play();
    }
    return () => {
      if (cameraVideoRef.current) cameraVideoRef.current.srcObject = null;
    };
  }, [cameraStream]);

  const stopCamera = (): void => {
    cameraStream?.getTracks().forEach((track) => track.stop());
    setCameraStream(undefined);
  };

  useEffect(() => {
    if (!isPlaying || !schedulerPolicy.animationEnabled) return undefined;
    let frame = 0;
    let last = performance.now();
    let accumulator = 0;
    const tick = (time: number) => {
      accumulator += time - last;
      last = time;
      const plan = planAnimationFrame(
        schedulerPolicy,
        accumulator,
        project.settings.animationDuration,
        [
          { id: 'mechanism-compute', priority: 100 },
          { id: 'character-binding', priority: 80 },
          { id: 'trace-render', priority: 40 }
        ]
      );
      accumulator = plan.remainingMs;
      setSkippedFrames((value) => value + plan.skippedFrames);
      if (plan.angleDeltaDeg > 0) {
        setAngle((prev) => (prev + plan.angleDeltaDeg) % 360);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [isPlaying, project.settings.animationDuration, schedulerPolicy]);

  const mutateMechanism = (id: string, updater: (m: MechanismConfig) => MechanismConfig): void => {
    setProject((prev) => updateProject(prev, { mechanisms: prev.mechanisms.map((m) => (m.id === id ? updater(m) : m)) }));
  };

  const patchPart = (name: string, patch: Partial<PartData>): void => {
    setProject((prev) => {
      const current = prev.parts[name];
      if (!current) return prev;
      return updateProject(prev, { parts: { ...prev.parts, [name]: { ...current, ...patch, transform: { ...current.transform, ...(patch.transform ?? {}) } } } });
    });
  };

  const addMechanism = (type: MechanismType): void => {
    const mechanism = createMechanism(type, project.mechanisms.length);
    setProject((prev) => updateProject(prev, { mechanisms: [...prev.mechanisms, mechanism] }));
    setSelectedId(mechanism.id);
    setActiveSection('studio');
  };

  const addRecommended = (): void => {
    const mechanism = createRecommendedMechanism(currentPath, project.mechanisms.length);
    const candidate = { ...mechanism, name: `${mechanism.name} fit candidate`, partName: project.selectedPathPart };
    setProject((prev) => updateProject(prev, { mechanisms: [...prev.mechanisms, candidate] }));
    setSelectedId(candidate.id);
    setActiveSection('studio');
  };

  const duplicateSelected = (): void => {
    if (!selected) return;
    const clone = { ...selected, id: `${selected.type}-${Date.now().toString(36)}`, name: `${selected.name} copy`, anchor: { x: selected.anchor.x + 32, y: selected.anchor.y + 24 }, params: { ...selected.params } };
    setProject((prev) => updateProject(prev, { mechanisms: [...prev.mechanisms, clone] }));
    setSelectedId(clone.id);
  };

  const deleteSelected = (): void => {
    if (!selected) return;
    const nextSelectedId = project.mechanisms.find((m) => m.id !== selected.id)?.id;
    setProject((prev) => updateProject(prev, { mechanisms: prev.mechanisms.filter((m) => m.id !== selected.id) }));
    setSelectedId(nextSelectedId);
  };

  const fitSelectedToPath = (): void => {
    if (!selected || !currentPath || currentPath.points.length < 3) return;
    const result = fitMechanismToPath(selected, currentPath, 260, selected.id.length * 97 + currentPath.points.length);
    setFitResult(result);
    setProject((prev) => updateProject(prev, { mechanisms: prev.mechanisms.map((m) => (m.id === selected.id ? result.candidate : m)) }));
  };

  const addPathPoint = (point: Point): void => {
    const snapEnabled = project.settings.showPhysicsSnap && project.settings.physicsSnapMode !== 'off';
    const nextPoint = snapPoint(point, snapEnabled, project.settings.gridSize);
    setProject((prev) => {
      const partName = prev.selectedPathPart;
      const current = prev.paths[partName] ?? { partName, points: [], totalDuration: 0, isClosed: false, enabled: true };
      const elapsed = current.totalDuration + 0.12;
      const timedPoints = [...(current.timedPoints ?? []), { ...nextPoint, t: elapsed }];
      return updateProject(prev, { paths: { ...prev.paths, [partName]: { ...current, points: [...current.points, nextPoint], timedPoints, totalDuration: elapsed } } });
    });
  };

  const patchCurrentPath = (patch: Partial<ProjectState['paths'][string]>): void => {
    setProject((prev) => {
      const partName = prev.selectedPathPart;
      const current = prev.paths[partName] ?? { partName, points: [], totalDuration: 0, isClosed: false, enabled: true };
      return updateProject(prev, { paths: { ...prev.paths, [partName]: { ...current, ...patch } } });
    });
  };

  const patchViewport = (patch: Partial<ProjectState['settings']['viewport']>): void => {
    setProject((prev) => updateProject(prev, {
      settings: {
        ...prev.settings,
        viewport: {
          ...prev.settings.viewport,
          ...patch,
          zoom: Math.max(0.35, Math.min(4, patch.zoom ?? prev.settings.viewport.zoom))
        }
      }
    }));
  };

  const selectPathPart = (partName: string): void => {
    setProject((prev) => updateProject(prev, { selectedPathPart: partName, paths: { ...prev.paths, [partName]: prev.paths[partName] ?? { partName, points: [], totalDuration: 0, isClosed: false, enabled: true } } }));
  };

  const handleReferenceUpload = (file: File): void => {
    if (referenceUrlRef.current) URL.revokeObjectURL(referenceUrlRef.current);
    const url = URL.createObjectURL(file);
    referenceUrlRef.current = url;
    const kind = file.type.includes('video') ? 'video' : file.type.includes('gif') ? 'gif' : 'image';
    setTrackingDraft([]);
    setProject((prev) => updateProject(prev, { imports: { referenceName: file.name, referenceUrl: url, referenceKind: kind } }));
  };

  const startCamera = async (): Promise<void> => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        setCameraError('Camera capture is not available in this browser context');
        return;
      }
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      setCameraStream(stream);
      setCameraError(undefined);
    } catch (error) {
      setCameraError(error instanceof Error ? error.message : 'Camera permission failed');
    }
  };

  const captureCameraReference = (): void => {
    const video = cameraVideoRef.current;
    if (!video || video.videoWidth <= 0 || video.videoHeight <= 0) return;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    if (referenceUrlRef.current) {
      URL.revokeObjectURL(referenceUrlRef.current);
      referenceUrlRef.current = undefined;
    }
    const dataUrl = canvas.toDataURL('image/png');
    setTrackingDraft([]);
    setProject((prev) => updateProject(prev, { imports: { referenceName: `camera-capture-${Date.now().toString(36)}.png`, referenceUrl: dataUrl, referenceKind: 'image' } }));
  };

  const handleProjectUpload = async (file: File): Promise<void> => {
    try {
      const text = await file.text();
      const next = parseProject(text);
      if (referenceUrlRef.current) {
        URL.revokeObjectURL(referenceUrlRef.current);
        referenceUrlRef.current = undefined;
      }
      replaceProjectRoot(next);
      setSelectedId(next.mechanisms[0]?.id);
      setSelectedPartName(Object.keys(next.parts)[0] ?? 'right_arm');
      setImportError(undefined);
      setAutosaveBlocked(false);
    } catch (error) {
      setImportError(error instanceof Error ? error.message : 'Project import failed');
    }
  };

  const handleTrackerClick = (event: MouseEvent<HTMLElement>): void => {
    if (!project.imports.referenceUrl) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const point = normalizeTrackerPoint({ x: event.clientX, y: event.clientY }, bounds);
    setTrackingDraft((prev) => [...prev, point]);
  };

  const saveTrackingAnnotation = (): void => {
    if (!project.imports.referenceName || !project.imports.referenceKind || trackingDraft.length === 0) return;
    const annotation = createTrackingAnnotation(project.imports.referenceName, project.imports.referenceKind, trackingDraft, trackingClosed, currentPath?.totalDuration ?? 2.4);
    setProject((prev) => updateProject(prev, { tracking: { annotations: [...prev.tracking.annotations, annotation], activeId: annotation.id, showOverlay: true } }));
  };

  const transferTrackingToPath = (): void => {
    if (!project.imports.referenceName || !project.imports.referenceKind || trackingDraft.length === 0) return;
    const annotation = createTrackingAnnotation(project.imports.referenceName, project.imports.referenceKind, trackingDraft, trackingClosed, currentPath?.totalDuration ?? 2.4);
    const path = trackingToPath(annotation, project.selectedPathPart);
    setProject((prev) => updateProject(prev, { paths: { ...prev.paths, [prev.selectedPathPart]: path }, tracking: { annotations: [...prev.tracking.annotations, annotation], activeId: annotation.id, showOverlay: true } }));
    setActiveSection('paths');
  };

  const runVisionAssist = (): void => {
    const lastAnnotation = project.tracking.annotations.find((annotation) => annotation.id === project.tracking.activeId) ?? project.tracking.annotations.at(-1);
    const draftAnnotation = project.imports.referenceName && project.imports.referenceKind && trackingDraft.length > 1
      ? createTrackingAnnotation(project.imports.referenceName, project.imports.referenceKind, trackingDraft, trackingClosed, currentPath?.totalDuration ?? 2.4)
      : undefined;
    const annotation = draftAnnotation ?? lastAnnotation;
    const result = inferVisionAssistFromTracking(annotation);
    setProject((prev) => updateProject(prev, {
      skeleton: result.skeleton,
      parts: Object.keys(result.parts).length > 0 ? result.parts : prev.parts,
      paths: result.pathPoints.length > 1 ? { ...prev.paths, [prev.selectedPathPart]: { partName: prev.selectedPathPart, points: result.pathPoints, totalDuration: currentPath?.totalDuration ?? 2.4, isClosed: annotation?.isClosed ?? false, enabled: true } } : prev.paths,
      tracking: draftAnnotation ? { annotations: [...prev.tracking.annotations, draftAnnotation], activeId: draftAnnotation.id, showOverlay: true } : prev.tracking,
      vision: result.status
    }));
  };

  const savePreset = (): void => {
    if (!selected) return;
    const preset = { id: `preset-${Date.now().toString(36)}`, name: `${selected.name} preset`, type: selected.type, config: { ...selected, params: { ...selected.params } }, createdAt: new Date().toISOString() };
    setProject((prev) => updateProject(prev, { presets: [...prev.presets, preset] }));
  };

  const applyPreset = (presetId: string): void => {
    const preset = project.presets.find((item) => item.id === presetId);
    if (!preset) return;
    const config = { ...preset.config, id: `${preset.config.type}-${Date.now().toString(36)}`, name: preset.name, params: { ...preset.config.params } };
    setProject((prev) => updateProject(prev, { mechanisms: [...prev.mechanisms, config] }));
    setSelectedId(config.id);
    setActiveSection('studio');
  };

  const addKeyframe = (): void => {
    const keyframe = {
      id: `keyframe-${Date.now().toString(36)}`,
      label: selected ? `${selected.name} @ ${format(angle, 0)}°` : `Pose @ ${format(angle, 0)}°`,
      angle,
      duration: 0.8,
      mechanismId: selected?.id,
      partName: selected?.partName ?? project.selectedPathPart,
      notes: selectedState?.safety.message ?? 'Storyboard keyframe'
    };
    setProject((prev) => updateProject(prev, { timeline: { keyframes: [...prev.timeline.keyframes, keyframe], activeKeyframeId: keyframe.id } }));
  };

  const resetAnimation = (): void => {
    setIsPlaying(false);
    setAngle(0);
  };

  const exportProject = (): void => downloadText(`${slug(project.metadata.name)}.automataii-web.json`, exportProjectJson(project), 'application/json');
  const exportSvg = (): void => downloadText(`${slug(project.metadata.name)}.svg`, exportSceneSvg(project, angle), 'image/svg+xml');
  const exportBlueprint = (): void => downloadText(`${slug(project.metadata.name)}-blueprint.svg`, exportBlueprintSvg(project, angle), 'image/svg+xml');
  const exportDxf = (): void => downloadText(`${slug(project.metadata.name)}.dxf`, exportSceneDxf(project, angle), 'application/dxf');
  const exportStudy = (): void => downloadText(`${slug(project.metadata.name)}-study-bundle.json`, exportStudyBundle(project, angle), 'application/json');

  const actionAvailability = useMemo(() => ({
    undo: canUndoProject(history),
    redo: canRedoProject(history)
  }), [history]);
  const availableActions = useMemo(() => enabledActionIds(actionAvailability), [actionAvailability]);

  const runAction = (actionId: AppActionId): void => {
    if (!availableActions.includes(actionId)) return;
    switch (actionId) {
      case 'playPause':
        setIsPlaying((value) => !value);
        return;
      case 'importProject':
        projectInputRef.current?.click();
        return;
      case 'saveJson':
        exportProject();
        return;
      case 'exportSvg':
        exportSvg();
        return;
      case 'exportBlueprint':
        exportBlueprint();
        return;
      case 'exportDxf':
        exportDxf();
        return;
      case 'exportStudy':
        exportStudy();
        return;
      case 'resetView':
        patchViewport({ x: 0, y: 0, zoom: 1 });
        return;
      case 'undo':
        undoProject();
        return;
      case 'redo':
        redoProject();
        return;
    }
  };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent): void => {
      if (isEditableTarget(event.target)) return;
      const actionId = actionForKeyboardEvent(event);
      if (!actionId) return;
      event.preventDefault();
      runAction(actionId);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  });

  const traceStats = selectedState ? boundsOf([selectedState.effector, ...Object.values(selectedState.positions)]) : undefined;
  const pathStats = currentPath ? { count: currentPath.points.length, length: pathLength(currentPath.points, currentPath.isClosed) } : { count: 0, length: 0 };

  return (
    <main className={`app theme-${project.settings.theme}`}>
      <input ref={projectInputRef} className="hidden" type="file" accept="application/json,.json,.automataii" onChange={(event) => { const file = event.target.files?.[0]; if (file) void handleProjectUpload(file); event.currentTarget.value = ''; }} />
      <input ref={referenceInputRef} className="hidden" type="file" accept="image/*,video/*,.gif" onChange={(event) => { const file = event.target.files?.[0]; if (file) handleReferenceUpload(file); event.currentTarget.value = ''; }} />

      <aside className="sidebar">
        <div className="brand-card">
          <div className="brand-mark"><Sparkles size={22} /></div>
          <div>
            <p className="eyebrow">Automataii</p>
            <h1>Native Web Studio</h1>
          </div>
        </div>
        <nav className="section-nav" aria-label="Web app sections">
          {sectionMeta.map((section) => (
            <button key={section.id} className={activeSection === section.id ? 'active' : ''} onClick={() => setActiveSection(section.id)}>
              {section.icon}
              <span>{section.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button onClick={() => projectInputRef.current?.click()}><FileUp size={16} /> Import</button>
          <button onClick={exportProject}><Save size={16} /> JSON</button>
          <button onClick={exportSvg}><Download size={16} /> SVG</button>
          <button onClick={exportBlueprint}><FileCode2 size={16} /> Blueprint</button>
          <button onClick={exportDxf}><FileCode2 size={16} /> DXF</button>
          <button onClick={exportStudy}><FileArchive size={16} /> Study</button>
        </div>
      </aside>

      <section className="workspace">
      <header className="topbar">
          <div>
            <p className="eyebrow">{sectionMeta.find((s) => s.id === activeSection)?.summary}</p>
            <h2>{project.metadata.name}</h2>
          </div>
          <div className="status-pills">
            <span>{project.mechanisms.length} mechanisms</span>
            <span>{Object.keys(project.parts).length} parts</span>
            <span>{format(angle, 0)}°</span>
            <span>{schedulerStatus}</span>
            <span>{historySummary(history)}</span>
            {physicsReport && <span className={physicsReport.status}>Physics {format(physicsReport.stabilityScore * 100, 0)}%</span>}
            <span className={selectedState?.safety.level ?? 'safe'}>{selectedState?.safety.message ?? 'Ready'}</span>
            {importError && <span className="danger">Import: {importError}</span>}
            {autosaveBlocked && <span className="danger">Autosave recovery paused</span>}
          </div>
        </header>

        <div className="studio-grid">
          <div className="canvas-stack">
            <div className="viewport-toolbar">
              <button onClick={() => patchViewport({ zoom: project.settings.viewport.zoom * 1.18 })}>Zoom +</button>
              <button onClick={() => patchViewport({ zoom: project.settings.viewport.zoom / 1.18 })}>Zoom −</button>
              <button onClick={() => patchViewport({ x: 0, y: 0, zoom: 1 })}>Reset view</button>
              <button className={project.settings.viewport.panMode ? 'active' : ''} onClick={() => patchViewport({ panMode: !project.settings.viewport.panMode })}>Pan mode</button>
              <span>{format(project.settings.viewport.zoom * 100, 0)}%</span>
            </div>
            <StudioCanvas
              project={project}
              angle={angle}
              selectedId={selected?.id}
              physicsReport={physicsReport}
              drawingPath={drawingPath}
              onSelect={setSelectedId}
              onMoveMechanism={(id, delta) => mutateMechanism(id, (m) => ({ ...m, anchor: snapPoint({ x: m.anchor.x + delta.x, y: m.anchor.y + delta.y }, project.settings.showPhysicsSnap && project.settings.physicsSnapMode !== 'off', project.settings.gridSize) }))}
              onMoveMechanismHandle={(id, handleName, point) => mutateMechanism(id, (m) => applyMechanismHandleDrag(m, handleName, point, angle))}
              onMovePathPoint={(partName, index, point) => setProject((prev) => {
                const path = prev.paths[partName];
                if (!path || !path.points[index]) return prev;
                const snapped = snapPoint(point, prev.settings.showPhysicsSnap && prev.settings.physicsSnapMode !== 'off', prev.settings.gridSize);
                const points = path.points.map((item, pointIndex) => pointIndex === index ? snapped : item);
                const timedPoints = path.timedPoints?.map((item, pointIndex) => pointIndex === index ? { ...snapped, t: item.t } : item);
                return updateProject(prev, { paths: { ...prev.paths, [partName]: { ...path, points, timedPoints } } });
              })}
              onPanViewport={(delta) => patchViewport({ x: project.settings.viewport.x + delta.x, y: project.settings.viewport.y + delta.y })}
              onAddPathPoint={addPathPoint}
            />
          </div>
          <aside className="inspector">
            {activeSection === 'welcome' && <WelcomePanel project={project} audit={featureAudit} onSection={setActiveSection} />}
            {activeSection === 'studio' && selected && (
              <StudioPanel
                selected={selected}
                angle={angle}
                isPlaying={isPlaying}
                onAngle={setAngle}
                onPlay={() => setIsPlaying((v) => !v)}
                onStop={() => setIsPlaying(false)}
                onReset={resetAnimation}
                onExportBlueprint={exportBlueprint}
                onDuplicate={duplicateSelected}
                onDelete={deleteSelected}
                onFit={fitSelectedToPath}
                onSavePreset={savePreset}
                onAddKeyframe={addKeyframe}
                fitResult={fitResult}
                pathAnalysis={pathAnalysis}
                mechanismAnalysis={mechanismAnalysis}
                physicsReport={physicsReport}
                onPatch={(patch) => mutateMechanism(selected.id, (m) => ({ ...m, ...patch }))}
                onParam={(key, value) => mutateMechanism(selected.id, (m) => ({ ...m, params: { ...m.params, [key]: value } }))}
                state={selectedState}
                tracePointCount={selectedTrace.length}
                jointOptions={jointOptions}
              />
            )}
            {activeSection === 'foundry' && <FoundryPanel recommendations={recommendations} presets={project.presets} filter={foundryFilter} onFilter={setFoundryFilter} onAdd={addMechanism} onAddRecommended={addRecommended} onApplyPreset={applyPreset} />}
            {activeSection === 'character' && (
              <CharacterPanel
                project={project}
                selectedPartName={selectedPartName}
                trackingDraft={trackingDraft}
                trackingClosed={trackingClosed}
                cameraVideoRef={cameraVideoRef}
                cameraActive={Boolean(cameraStream)}
                cameraError={cameraError}
                onSelectPart={setSelectedPartName}
                onPatchPart={patchPart}
                onUpload={() => referenceInputRef.current?.click()}
                onStartCamera={() => void startCamera()}
                onStopCamera={stopCamera}
                onCaptureCamera={captureCameraReference}
                onTrackerClick={handleTrackerClick}
                onClearTracking={() => setTrackingDraft([])}
                onSmoothTracking={() => setTrackingDraft((prev) => smoothTrackingPoints(prev, trackingClosed))}
                onToggleClosed={() => setTrackingClosed((v) => !v)}
                onSaveTracking={saveTrackingAnnotation}
                onTransferTracking={transferTrackingToPath}
                onVisionAssist={runVisionAssist}
              />
            )}
            {activeSection === 'paths' && (
              <PathsPanel
                pathStats={pathStats}
                drawing={drawingPath}
                closed={currentPath?.isClosed ?? false}
                selectedPathPart={project.selectedPathPart}
                pathOptions={jointOptions}
                recommendations={recommendations}
                pathAnalysis={pathAnalysis}
                onSelectPathPart={selectPathPart}
                onDraw={() => setDrawingPath((v) => !v)}
                onClear={() => patchCurrentPath({ points: [], timedPoints: [], totalDuration: 0 })}
                onClose={() => patchCurrentPath({ isClosed: !(currentPath?.isClosed ?? false) })}
                onResample={() => currentPath && patchCurrentPath({ points: resamplePath(currentPath.points, 64, currentPath.isClosed) })}
                onSmooth={() => currentPath && patchCurrentPath({ points: smoothTrackingPoints(currentPath.points, currentPath.isClosed) })}
              />
            )}
            {activeSection === 'lab' && <LabPanel project={project} audit={featureAudit} physicsReport={physicsReport} traceStats={traceStats} pathAnalysis={pathAnalysis} mechanismAnalysis={mechanismAnalysis} onNotes={(notes) => setProject((prev) => updateProject(prev, { lab: { ...prev.lab, activeNotes: notes } }))} onExportStudy={exportStudy} onAddKeyframe={addKeyframe} />}
            {activeSection === 'options' && <OptionsPanel project={project} autosaveStatus={autosaveStatus} autosaveBlocked={autosaveBlocked} schedulerStatus={schedulerStatus} availableActions={availableActions} onRecoverAutosave={() => setAutosaveBlocked(false)} onProject={setProject} onReplaceProject={replaceProjectRoot} />}
          </aside>
        </div>
      </section>
    </main>
  );
}

const FeatureAuditPanel = ({ audit, compact = false }: { audit: FeatureAuditSummary; compact?: boolean }) => (
  <div className={`panel-card audit-card ${compact ? 'compact' : ''}`}>
    <div className="audit-summary">
      <div>
        <p className="eyebrow">Feature integration audit</p>
        <h3>{audit.complete ? 'All required workflows integrated' : `${audit.missingRequired.length} workflows need attention`}</h3>
        <p>{audit.passed}/{audit.required} required checks pass across desktop parity, mechanisms, MechAnim-inspired flows, and web-native shell.</p>
      </div>
      <strong className={audit.complete ? 'complete' : 'attention'}>{audit.percent}%</strong>
    </div>
    <div className="audit-categories">
      {audit.categories.map((item) => (
        <span key={item.category} className={item.passed === item.total ? 'complete' : 'attention'}>{item.category}: {item.passed}/{item.total}</span>
      ))}
    </div>
    {!compact && (
      <div className="audit-grid">
        {audit.items.map((item) => (
          <div key={item.id} className={item.passed ? 'passed' : 'failed'}>
            <strong>{item.passed ? '✓' : '!'}</strong>
            <span>{item.label}</span>
            <small>{item.evidence}</small>
          </div>
        ))}
      </div>
    )}
    {audit.missingRequired.length > 0 && <p className="warning-line">Missing: {audit.missingRequired.map((item) => item.label).join(', ')}</p>}
  </div>
);

const WelcomePanel = ({ project, audit, onSection }: { project: ProjectState; audit: FeatureAuditSummary; onSection: (section: WorkflowSection) => void }) => (
  <div className="panel-stack">
    <div className="panel-card welcome-hero">
      <p className="eyebrow">Full React migration</p>
      <h3>Desktop Automataii, rebuilt as a rich web-native studio.</h3>
      <p>The workflow mirrors the Qt app tabs while adding MechAnim-style path fitting, manual tracking, richer catalog cards, DXF/SVG/study exports, and live character binding.</p>
      <div className="hero-badges">
        <span>Light-first UI</span>
        <span>{project.mechanisms.length} live mechanisms</span>
        <span>Direct handles</span>
        <span>Offline-ready PWA</span>
      </div>
      <div className="button-row"><button className="primary" onClick={() => onSection('character')}><Camera size={16} /> Start character</button><button onClick={() => onSection('foundry')}><Workflow size={16} /> Open foundry</button></div>
    </div>
    <FeatureAuditPanel audit={audit} />
    <div className="feature-matrix">
      {sectionMeta.slice(1).map((section) => <button key={section.id} onClick={() => onSection(section.id)}><strong>{section.label}</strong><span>{section.summary}</span></button>)}
    </div>
    <div className="metric-grid"><div><span>Mechanisms</span><strong>{project.mechanisms.length}</strong></div><div><span>Tracking clips</span><strong>{project.tracking.annotations.length}</strong></div></div>
  </div>
);

const StudioPanel = ({ selected, angle, isPlaying, state, tracePointCount, fitResult, pathAnalysis, mechanismAnalysis, physicsReport, jointOptions, onAngle, onPlay, onStop, onReset, onExportBlueprint, onDuplicate, onDelete, onFit, onSavePreset, onAddKeyframe, onPatch, onParam }: {
  selected: MechanismConfig;
  angle: number;
  isPlaying: boolean;
  state?: ReturnType<typeof computeMechanismState>;
  tracePointCount: number;
  fitResult?: FitResult;
  pathAnalysis: MotionAnalysis;
  mechanismAnalysis?: MechanismAnalysis;
  physicsReport?: PhysicsReport;
  jointOptions: string[];
  onAngle: (angle: number) => void;
  onPlay: () => void;
  onStop: () => void;
  onReset: () => void;
  onExportBlueprint: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onFit: () => void;
  onSavePreset: () => void;
  onAddKeyframe: () => void;
  onPatch: (patch: Partial<MechanismConfig>) => void;
  onParam: (key: string, value: number) => void;
}) => (
  <div className="panel-stack">
    <div className="panel-card hero-panel">
      <p className="eyebrow">Selected mechanism</p>
      <input className="title-input" value={selected.name} onChange={(e) => onPatch({ name: e.target.value })} />
      <p>{selected.type} · {state?.safety.message}</p>
      <div className="button-row">
        <button className="primary" onClick={onPlay}>{isPlaying ? <Pause size={16} /> : <CirclePlay size={16} />} {isPlaying ? 'Pause' : 'Play'}</button>
        <button onClick={onStop}>Stop</button>
        <button onClick={onReset}>Reset</button>
        <button onClick={onFit}><WandSparkles size={16} /> Fit path</button>
        <button onClick={onExportBlueprint}><FileCode2 size={16} /> Export blueprint</button>
        <button onClick={onSavePreset}>Save preset</button>
        <button onClick={onAddKeyframe}>Keyframe</button>
        <button onClick={onDuplicate}>Duplicate</button>
        <button className="danger-button" onClick={onDelete}>Delete</button>
      </div>
    </div>
    {fitResult && <div className="panel-card fit-card"><strong>Path fit</strong><p>Score {format(fitResult.initialScore, 3)} → {format(fitResult.score, 3)} across {fitResult.iterations} seeded search iterations.</p></div>}
    <div className="panel-card analysis-card">
      <div className="panel-heading"><Activity size={16} /><span>Motion analysis</span></div>
      <div className="metric-grid"><div><span>Path length</span><strong>{format(pathAnalysis.pathLength, 0)}</strong></div><div><span>Trace coverage</span><strong>{mechanismAnalysis ? format(mechanismAnalysis.traceCoverage, 0) : '—'}</strong></div></div>
      {[...pathAnalysis.warnings, ...(mechanismAnalysis?.warnings ?? [])].slice(0, 3).map((warning) => <p key={warning} className="warning-line">{warning}</p>)}
    </div>
    {physicsReport && (
      <div className={`panel-card physics-card ${physicsReport.status}`}>
        <div className="panel-heading"><Zap size={16} /><span>Physics-aware simulation</span></div>
        <div className="physics-score">
          <strong>{format(physicsReport.stabilityScore * 100, 0)}%</strong>
          <span>{physicsReport.status} stability · {physicsReport.samples.length} sampled frames</span>
        </div>
        <div className="physics-bars">
          <label><span>Load</span><meter min="0" max="1" value={physicsReport.loadScore} /></label>
          <label><span>Smoothness</span><meter min="0" max="1" value={physicsReport.smoothnessScore} /></label>
          <label><span>Stability</span><meter min="0" max="1" value={physicsReport.stabilityScore} /></label>
        </div>
        <div className="metric-grid">
          <div><span>Peak speed</span><strong>{format(physicsReport.maxSpeed, 0)} px/s</strong></div>
          <div><span>Peak accel</span><strong>{format(physicsReport.maxAcceleration, 0)}</strong></div>
          <div><span>Energy</span><strong>{format(physicsReport.peakKineticEnergy / 1000, 1)}k</strong></div>
          <div><span>Now</span><strong>{format(physicsReport.current.speed, 0)} px/s</strong></div>
        </div>
        {physicsReport.warnings.slice(0, 3).map((warning) => <p key={warning} className="warning-line">{warning}</p>)}
      </div>
    )}
    <div className="panel-card two-col-controls">
      <label>Target joint<select value={selected.partName} onChange={(e) => onPatch({ partName: e.target.value })}>{jointOptions.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
      <label>Timeline angle <strong>{format(angle, 0)}°</strong><input type="range" min="0" max="360" value={angle} onChange={(e) => onAngle(numeric(e.target.value, angle))} /></label>
      <label>Speed<input type="number" value={selected.speed} step="0.1" onChange={(e) => onPatch({ speed: numeric(e.target.value, selected.speed) })} /></label>
      <label>Rotation<input type="number" value={selected.rotationDeg} onChange={(e) => onPatch({ rotationDeg: numeric(e.target.value, selected.rotationDeg) })} /></label>
    </div>
    <div className="panel-card params-card">
      <div className="panel-heading"><Wrench size={16} /><span>Parameters</span></div>
      {Object.entries(selected.params).map(([key, value]) => (
        <label key={key} className="param-row"><span>{key}</span><input type="number" value={format(value, 2)} step="1" onChange={(e) => onParam(key, numeric(e.target.value, value))} /></label>
      ))}
    </div>
    <div className="metric-grid"><div><span>Trace points</span><strong>{tracePointCount}</strong></div><div><span>Effector</span><strong>{state ? `${format(state.effector.x)}, ${format(state.effector.y)}` : '—'}</strong></div></div>
  </div>
);

const FoundryPanel = ({ recommendations, presets, filter, onFilter, onAdd, onAddRecommended, onApplyPreset }: { recommendations: ReturnType<typeof recommendMechanismsForPath>; presets: ProjectState['presets']; filter: string; onFilter: (value: string) => void; onAdd: (type: MechanismType) => void; onAddRecommended: () => void; onApplyPreset: (presetId: string) => void }) => {
  const visible = mechanismTemplates.filter((template) => filter === 'all' || template.tags.includes(filter) || template.complexity === filter);
  const filters = ['all', 'linkage', 'linear', 'cam', 'gear', 'intro', 'intermediate', 'advanced'];
  return (
    <div className="panel-stack">
      <div className="panel-card hero-panel"><p className="eyebrow">Mechanism Foundry</p><h3>Choose, recommend, optimize, fabricate.</h3><p>Catalog entries cover the desktop families plus MechAnim-style piston/yoke primitives.</p><button className="primary" onClick={onAddRecommended}><WandSparkles size={16} /> Add best match for current path</button></div>
      <div className="filter-row">{filters.map((item) => <button key={item} className={filter === item ? 'active' : ''} onClick={() => onFilter(item)}>{item}</button>)}</div>
      <div className="recommendation-list">{recommendations.map((rec) => <div key={rec.type}><strong>{rec.label}</strong><span>{format(rec.score, 2)}</span><p>{rec.reason}</p></div>)}</div>
      <div className="panel-card">
        <div className="panel-heading"><Sparkles size={16} /><span>Presets</span></div>
        <div className="preset-grid">{presets.map((preset) => <button key={preset.id} onClick={() => onApplyPreset(preset.id)}><strong>{preset.name}</strong><small>{preset.type}</small></button>)}</div>
      </div>
      <div className="template-list">
        {visible.map((template) => (
          <button key={template.type} className="template-card" onClick={() => onAdd(template.type)}>
            <span className="swatch" style={{ background: template.color }} />
            <strong>{template.label}</strong>
            <small>{template.tagline} · {template.complexity}</small>
            <p>{template.description}</p>
          </button>
        ))}
      </div>
    </div>
  );
};

const CharacterPanel = ({ project, selectedPartName, trackingDraft, trackingClosed, cameraVideoRef, cameraActive, cameraError, onSelectPart, onPatchPart, onUpload, onStartCamera, onStopCamera, onCaptureCamera, onTrackerClick, onClearTracking, onSmoothTracking, onToggleClosed, onSaveTracking, onTransferTracking, onVisionAssist }: {
  project: ProjectState;
  selectedPartName: string;
  trackingDraft: Point[];
  trackingClosed: boolean;
  cameraVideoRef: RefObject<HTMLVideoElement | null>;
  cameraActive: boolean;
  cameraError?: string;
  onSelectPart: (name: string) => void;
  onPatchPart: (name: string, patch: Partial<PartData>) => void;
  onUpload: () => void;
  onStartCamera: () => void;
  onStopCamera: () => void;
  onCaptureCamera: () => void;
  onTrackerClick: (event: MouseEvent<HTMLElement>) => void;
  onClearTracking: () => void;
  onSmoothTracking: () => void;
  onToggleClosed: () => void;
  onSaveTracking: () => void;
  onTransferTracking: () => void;
  onVisionAssist: () => void;
}) => {
  const part = project.parts[selectedPartName] ?? Object.values(project.parts)[0];
  const joints = Object.keys(project.skeleton?.joints ?? {});
  return (
    <div className="panel-stack">
      <div className="panel-card hero-panel"><p className="eyebrow">Character Selection + Tracking</p><h3>{Object.keys(project.parts).length} parts · {project.skeleton ? Object.keys(project.skeleton.joints).length : 0} joints</h3><p>Upload image/video/GIF references, capture from camera, infer a browser-side rig, transfer paths, and bind parts to mechanisms.</p><div className="button-row"><button className="primary" onClick={onUpload}><FileUp size={16} /> Upload reference</button><button onClick={onStartCamera}><Camera size={16} /> Camera</button><button onClick={onVisionAssist}><WandSparkles size={16} /> Infer rig</button></div></div>
      <div className="panel-card processing-card">
        <div className="panel-heading"><Sparkles size={16} /><span>Processing stages</span></div>
        <p>Web-native parity controls for the Qt image workflow: process image, edit skeleton, save skeleton, generate body parts, extend skeleton, and lock/unlock joints.</p>
        <div className="button-row">
          <button onClick={onVisionAssist}>Process image</button>
          <button onClick={onVisionAssist}>Generate body parts</button>
          <button onClick={onVisionAssist}>Extend skeleton</button>
          <button onClick={() => part && onPatchPart(part.name, { fixed: !part.fixed })}>{part?.fixed ? 'Unlock part' : 'Lock part'}</button>
        </div>
      </div>
      {(cameraActive || cameraError) && <div className="panel-card camera-card"><video ref={cameraVideoRef} muted playsInline /><p>{cameraError ?? 'Live camera is ready for browser-native capture.'}</p><div className="button-row"><button className="primary" onClick={onCaptureCamera}>Capture still</button><button onClick={onStopCamera}>Stop camera</button></div></div>}
      {project.imports.referenceUrl && <ReferenceTracker project={project} points={trackingDraft} closed={trackingClosed} onClick={onTrackerClick} />}
      <div className="button-row"><button onClick={onSmoothTracking}><RefreshCw size={16} /> Smooth</button><button onClick={onToggleClosed}>{trackingClosed ? 'Open track' : 'Close loop'}</button><button onClick={onSaveTracking}>Save track</button><button className="primary" onClick={onTransferTracking}>Transfer to path</button><button className="danger-button" onClick={onClearTracking}>Clear</button></div>
      <div className="metric-grid"><div><span>Vision confidence</span><strong>{format(project.vision.confidence, 2)}</strong></div><div><span>Inferred rig</span><strong>{project.vision.inferredJointCount}/{project.vision.inferredPartCount}</strong></div></div>
      <div className="template-list part-list">{Object.values(project.parts).sort((a, b) => b.zIndex - a.zIndex).map((item) => <button key={item.name} className={`part-row ${item.name === selectedPartName ? 'active' : ''}`} onClick={() => onSelectPart(item.name)}><span style={{ background: item.fillColor }} /><strong>{item.name}</strong><small>anchor: {item.anchorJoint}</small></button>)}</div>
      {part && <div className="panel-card two-col-controls"><label>Anchor joint<select value={part.anchorJoint} onChange={(e) => onPatchPart(part.name, { anchorJoint: e.target.value })}>{joints.map((joint) => <option key={joint} value={joint}>{joint}</option>)}</select></label><label>Color<input value={part.fillColor} onChange={(e) => onPatchPart(part.name, { fillColor: e.target.value })} /></label><label>Opacity<input type="range" min="0" max="1" step="0.05" value={part.opacity} onChange={(e) => onPatchPart(part.name, { opacity: numeric(e.target.value, part.opacity) })} /></label><label>Scale<input type="number" step="0.05" value={part.transform.scale} onChange={(e) => onPatchPart(part.name, { transform: { ...part.transform, scale: numeric(e.target.value, part.transform.scale) } })} /></label><label>X<input type="number" value={part.transform.x} onChange={(e) => onPatchPart(part.name, { transform: { ...part.transform, x: numeric(e.target.value, part.transform.x) } })} /></label><label>Y<input type="number" value={part.transform.y} onChange={(e) => onPatchPart(part.name, { transform: { ...part.transform, y: numeric(e.target.value, part.transform.y) } })} /></label></div>}
    </div>
  );
};

const ReferenceTracker = ({ project, points, closed, onClick }: { project: ProjectState; points: Point[]; closed: boolean; onClick: (event: MouseEvent<HTMLElement>) => void }) => (
  <div className="tracker-surface" onClick={onClick} role="button" tabIndex={0}>
    {project.imports.referenceKind === 'video' ? <video src={project.imports.referenceUrl} controls /> : <img src={project.imports.referenceUrl} alt="Imported reference" />}
    <svg viewBox="0 0 1120 760" aria-hidden="true">
      {points.length > 1 && <path className="tracker-path" d={`M ${points.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' L ')}${closed ? ' Z' : ''}`} />}
      {points.map((point, index) => <circle key={index} cx={point.x} cy={point.y} r="8" />)}
    </svg>
    <span><Crosshair size={14} /> Click reference to annotate motion points</span>
  </div>
);

const PathsPanel = ({ pathStats, drawing, closed, selectedPathPart, pathOptions, recommendations, pathAnalysis, onSelectPathPart, onDraw, onClear, onClose, onResample, onSmooth }: { pathStats: { count: number; length: number }; drawing: boolean; closed: boolean; selectedPathPart: string; pathOptions: string[]; recommendations: ReturnType<typeof recommendMechanismsForPath>; pathAnalysis: MotionAnalysis; onSelectPathPart: (partName: string) => void; onDraw: () => void; onClear: () => void; onClose: () => void; onResample: () => void; onSmooth: () => void }) => (
  <div className="panel-stack">
    <div className="panel-card hero-panel"><p className="eyebrow">Path Editor</p><h3>{pathStats.count} points · {format(pathStats.length, 0)} px</h3><p>Draw target motion directly on the canvas, close it, smooth it, and fit mechanisms to it.</p><label>Target joint<select value={selectedPathPart} onChange={(e) => onSelectPathPart(e.target.value)}>{pathOptions.map((name) => <option key={name} value={name}>{name}</option>)}</select></label><div className="button-row"><button className="primary" onClick={onDraw}>{drawing ? 'Stop drawing' : 'Draw path'}</button><button onClick={onClose}>{closed ? 'Open path' : 'Close path'}</button></div></div>
    <div className="panel-card"><button onClick={onSmooth}>Smooth Catmull-Rom</button><button onClick={onResample}>Resample to 64 points</button><button className="danger-button" onClick={onClear}>Clear path</button></div>
    <div className="panel-card"><strong>Path diagnostics</strong><p>Mean step {format(pathAnalysis.meanStep, 1)} · Max step {format(pathAnalysis.maxStep, 1)} · Closure {format(pathAnalysis.closureError, 1)}</p>{pathAnalysis.warnings.map((warning) => <p key={warning} className="warning-line">{warning}</p>)}</div>
    <div className="recommendation-list">{recommendations.slice(0, 3).map((rec) => <div key={rec.type}><strong>{rec.label}</strong><span>{format(rec.score, 2)}</span><p>{rec.reason}</p></div>)}</div>
  </div>
);

const LabPanel = ({ project, audit, physicsReport, traceStats, pathAnalysis, mechanismAnalysis, onNotes, onExportStudy, onAddKeyframe }: { project: ProjectState; audit: FeatureAuditSummary; physicsReport?: PhysicsReport; traceStats?: ReturnType<typeof boundsOf>; pathAnalysis: MotionAnalysis; mechanismAnalysis?: MechanismAnalysis; onNotes: (notes: string) => void; onExportStudy: () => void; onAddKeyframe: () => void }) => (
  <div className="panel-stack">
    <div className="panel-card hero-panel"><p className="eyebrow">Lab / MS4N</p><h3>Trace autopsy + storyboard bundle</h3><p>Kit assets, before/after mechanism snapshots, keyframes, repair explanations, and JSONL/CSV-ready evidence live together.</p><div className="button-row"><button className="primary" onClick={onExportStudy}><FileArchive size={16} /> Export study bundle</button><button onClick={onAddKeyframe}>Add keyframe</button></div></div>
    <FeatureAuditPanel audit={audit} compact />
    <div className="metric-grid"><div><span>Trace width</span><strong>{traceStats ? format(traceStats.width, 0) : '—'}</strong></div><div><span>Trace height</span><strong>{traceStats ? format(traceStats.height, 0) : '—'}</strong></div></div>
    <div className="metric-grid"><div><span>Path jumps</span><strong>{format(pathAnalysis.maxStep, 0)}</strong></div><div><span>Coverage</span><strong>{mechanismAnalysis ? format(mechanismAnalysis.traceCoverage, 0) : '—'}</strong></div></div>
    {physicsReport && <div className="metric-grid"><div><span>Physics stability</span><strong>{format(physicsReport.stabilityScore * 100, 0)}%</strong></div><div><span>Peak load</span><strong>{format(physicsReport.loadScore * 100, 0)}%</strong></div></div>}
    <div className="timeline-list">{project.timeline.keyframes.map((keyframe) => <div key={keyframe.id} className="episode-card"><strong>{keyframe.label}</strong><p><b>Angle:</b> {format(keyframe.angle, 0)}° · <b>Duration:</b> {format(keyframe.duration, 2)}s</p><p>{keyframe.notes}</p><span>{keyframe.partName ?? 'scene'}</span></div>)}</div>
    <div className="kit-grid">{project.lab.kitAssets.map((asset) => <div key={asset.id} className="roadmap-card"><span>{asset.pilotPriority}</span><strong>{asset.label}</strong><p>{asset.description}</p><small>{asset.filename}</small></div>)}</div>
    {project.lab.episodes.map((episode) => <div key={episode.id} className="episode-card"><strong>{episode.title}</strong><p><b>Symptom:</b> {episode.symptom}</p><p><b>Repair:</b> {episode.repairAction}</p><span>{episode.status}</span></div>)}
    <textarea value={project.lab.activeNotes} onChange={(e) => onNotes(e.target.value)} rows={6} />
  </div>
);

const OptionsPanel = ({ project, autosaveStatus, autosaveBlocked, schedulerStatus, availableActions, onRecoverAutosave, onProject, onReplaceProject }: {
  project: ProjectState;
  autosaveStatus: string;
  autosaveBlocked: boolean;
  schedulerStatus: string;
  availableActions: AppActionId[];
  onRecoverAutosave: () => void;
  onProject: (project: ProjectState) => void;
  onReplaceProject: (project: ProjectState) => void;
}) => {
  const patchSettings = (patch: Partial<ProjectState['settings']>): void => onProject(updateProject(project, { settings: { ...project.settings, ...patch } }));
  return (
    <div className="panel-stack">
      <div className="panel-card hero-panel"><p className="eyebrow">Options</p><h3>Native-feeling controls</h3><p>Theme, units, physics snap, traces, skeleton, character parts, reduced motion, and timing settings.</p></div>
      <div className="panel-card">
        <strong>{autosaveStatus}</strong>
        <p>Shortcuts: Space play/pause · Cmd/Ctrl+O import · Cmd/Ctrl+S save JSON · Cmd/Ctrl+B export blueprint · Cmd/Ctrl+0 reset view · Cmd/Ctrl+Z undo · Cmd/Ctrl+Y redo.</p>
        {autosaveBlocked && <button className="danger-button" onClick={onRecoverAutosave}>Resume autosave with current demo</button>}
      </div>
      <div className="panel-card">
        <strong>Scheduler and action registry</strong>
        <p>{schedulerStatus}</p>
        <p>Action registry: {appActionDefinitions.map((action) => action.id).join(', ')}</p>
        <p>Available now: {availableActions.join(', ')}</p>
      </div>
      <div className="panel-card option-list">
        <label>Project name<input value={project.metadata.name} onChange={(e) => onProject(updateProject(project, { metadata: { ...project.metadata, name: e.target.value } }))} /></label>
        <label>Theme<select value={project.settings.theme} onChange={(e) => patchSettings({ theme: e.target.value as ProjectState['settings']['theme'] })}><option value="dark">Dark</option><option value="light">Light</option></select></label>
        <label>Units<select value={project.settings.units} onChange={(e) => patchSettings({ units: e.target.value as ProjectState['settings']['units'] })}><option value="px">px</option><option value="mm">mm</option><option value="in">in</option></select></label>
        <label>Animation duration<input type="number" min="0.25" step="0.25" value={project.settings.animationDuration} onChange={(e) => patchSettings({ animationDuration: numeric(e.target.value, project.settings.animationDuration) })} /></label>
        <label>Target FPS<input type="number" min="12" max="120" step="1" value={project.settings.targetFps} onChange={(e) => patchSettings({ targetFps: numeric(e.target.value, project.settings.targetFps) })} /></label>
        <label>Performance<select value={project.settings.performancePreset} onChange={(e) => patchSettings({ performancePreset: e.target.value as ProjectState['settings']['performancePreset'] })}><option value="quality">Quality</option><option value="balanced">Balanced</option><option value="performance">Performance</option></select></label>
        <label>Workflow<select value={project.settings.workflowMode} onChange={(e) => patchSettings({ workflowMode: e.target.value as ProjectState['settings']['workflowMode'] })}><option value="guided">Guided</option><option value="flexible">Flexible</option></select></label>
        <label>Snap mode<select value={project.settings.physicsSnapMode} onChange={(e) => patchSettings({ physicsSnapMode: e.target.value as ProjectState['settings']['physicsSnapMode'] })}><option value="adaptive">Adaptive physics snap</option><option value="grid">Grid snap</option><option value="off">Off</option></select></label>
        <label>Grid size<input type="number" min="4" max="128" step="4" value={project.settings.gridSize} onChange={(e) => patchSettings({ gridSize: numeric(e.target.value, project.settings.gridSize) })} /></label>
        <label className="check"><input type="checkbox" checked={project.settings.showTraces} onChange={(e) => patchSettings({ showTraces: e.target.checked })} /> Show traces</label>
        <label className="check"><input type="checkbox" checked={project.settings.showForces} onChange={(e) => patchSettings({ showForces: e.target.checked })} /> Show forces</label>
        <label className="check"><input type="checkbox" checked={project.settings.showSafetyZones} onChange={(e) => patchSettings({ showSafetyZones: e.target.checked })} /> Show safety zones</label>
        <label className="check"><input type="checkbox" checked={project.settings.showSkeleton} onChange={(e) => patchSettings({ showSkeleton: e.target.checked })} /> Show skeleton</label>
        <label className="check"><input type="checkbox" checked={project.settings.showCharacterParts} onChange={(e) => patchSettings({ showCharacterParts: e.target.checked })} /> Show character parts</label>
        <label className="check"><input type="checkbox" checked={project.settings.showPhysicsSnap} onChange={(e) => patchSettings({ showPhysicsSnap: e.target.checked })} /> Physics snap</label>
        <label className="check"><input type="checkbox" checked={project.settings.reducedMotion} onChange={(e) => patchSettings({ reducedMotion: e.target.checked })} /> Reduced motion</label>
      </div>
      {project.compatibility.warnings.length > 0 && <div className="panel-card"><strong>Compatibility warnings</strong>{project.compatibility.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}
      <button onClick={() => { onRecoverAutosave(); onReplaceProject(normalizeProject(createDefaultProject())); }}>Reset to demo project</button>
    </div>
  );
};

export default App;
