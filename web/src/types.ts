export type WorkflowSection = 'welcome' | 'character' | 'paths' | 'studio' | 'foundry' | 'lab' | 'options';

export type MechanismType =
  | 'crank'
  | 'four-bar'
  | 'five-bar'
  | 'six-bar'
  | 'cam-follower'
  | 'gear-pair'
  | 'planetary-gear'
  | 'slider-crank'
  | 'quick-return'
  | 'scotch-yoke';

export type SafetyLevel = 'safe' | 'caution' | 'danger';

export interface Point {
  x: number;
  y: number;
}

export interface Transform {
  x: number;
  y: number;
  rotation: number;
  scale: number;
}

export interface PartData {
  name: string;
  texturePath: string;
  maskPath: string;
  anchorJoint: string;
  transform: Transform;
  zIndex: number;
  fillColor: string;
  opacity: number;
  fixed: boolean;
  group?: string;
  localPivotOffset?: Point;
}

export interface JointData {
  id: string;
  name: string;
  position: Point;
  parent?: string;
  isLocked: boolean;
  bendDirection: number;
}

export interface BoneData {
  fromJoint: string;
  toJoint: string;
}

export interface SkeletonData {
  joints: Record<string, JointData>;
  bones: BoneData[];
  rootJoint: string;
}

export interface TimedPoint extends Point {
  t: number;
}

export interface PathData {
  partName: string;
  points: Point[];
  timedPoints?: TimedPoint[];
  totalDuration: number;
  isClosed: boolean;
  enabled: boolean;
}

export interface TrackingAnnotation {
  id: string;
  sourceName: string;
  sourceKind: 'image' | 'video' | 'gif';
  points: Point[];
  smoothedPoints: Point[];
  isClosed: boolean;
  duration: number;
  createdAt: string;
}

export interface MechanismConfig {
  id: string;
  name: string;
  type: MechanismType;
  partName: string;
  color: string;
  enabled: boolean;
  anchor: Point;
  rotationDeg: number;
  speed: number;
  params: Record<string, number>;
  layerData?: Record<string, unknown>;
}

export interface SafetyStatus {
  level: SafetyLevel;
  message: string;
  details?: Record<string, unknown>;
}

export type ForceType = 'reaction' | 'applied' | 'constraint' | 'friction' | 'gravity';

export interface ForceVector {
  position: Point;
  magnitude: number;
  angle: number;
  forceType: ForceType;
  label: string;
  color: string;
}

export interface LinkSegment {
  start: string;
  end: string;
  role?: 'ground' | 'input' | 'coupler' | 'output' | 'helper' | 'slider';
}

export interface GearVisual {
  id: string;
  center: Point;
  radius: number;
  teeth: number;
  rotationDeg: number;
  role: 'sun' | 'planet' | 'ring' | 'input' | 'output';
}

export interface MechanismState {
  type: MechanismType;
  positions: Record<string, Point>;
  velocities?: Record<string, Point>;
  forces?: Record<string, ForceVector>;
  links: LinkSegment[];
  effector: Point;
  valid: boolean;
  safety: SafetyStatus;
  metadata: Record<string, unknown>;
  profile?: Point[];
  gears?: GearVisual[];
}

export interface ProjectMetadata {
  version: string;
  name: string;
  createdAt: string;
  modifiedAt: string;
}

export interface LabEpisode {
  id: string;
  title: string;
  mechanismType?: MechanismType | 'mixed';
  symptom: string;
  suspectedCause: string;
  repairAction: string;
  evidenceOutputs?: string[];
  traceMetrics?: Record<string, number>;
  status: 'draft' | 'observed' | 'repaired';
  notes: string;
}

export interface KitAsset {
  id: string;
  label: string;
  filename: string;
  assetType: string;
  mechanismTypes: string[];
  evidenceOutputs: string[];
  description: string;
  pilotPriority: 'P0' | 'P1' | 'P2';
}

export interface MechanismPreset {
  id: string;
  name: string;
  type: MechanismType;
  config: MechanismConfig;
  createdAt: string;
}

export interface TimelineKeyframe {
  id: string;
  label: string;
  angle: number;
  duration: number;
  mechanismId?: string;
  partName?: string;
  notes: string;
}

export interface VisionAssistState {
  lastRunAt?: string;
  confidence: number;
  warnings: string[];
  inferredJointCount: number;
  inferredPartCount: number;
  parityMode?: 'browser-safe' | 'insufficient-input';
  nonWebInfrastructure?: string[];
}

export interface ProjectState {
  metadata: ProjectMetadata;
  parts: Record<string, PartData>;
  skeleton?: SkeletonData;
  paths: Record<string, PathData>;
  mechanisms: MechanismConfig[];
  selectedPathPart: string;
  settings: {
    theme: 'dark' | 'light';
    units: 'px' | 'mm' | 'in';
    animationDuration: number;
    showPhysicsSnap: boolean;
    physicsSnapMode: 'off' | 'grid' | 'adaptive';
    gridSize: number;
    showTraces: boolean;
    showForces: boolean;
    showSafetyZones: boolean;
    showSkeleton: boolean;
    showCharacterParts: boolean;
    reducedMotion: boolean;
    targetFps: number;
    performancePreset: 'quality' | 'balanced' | 'performance';
    workflowMode: 'guided' | 'flexible';
    viewport: {
      x: number;
      y: number;
      zoom: number;
      panMode: boolean;
    };
  };
  lab: {
    episodes: LabEpisode[];
    kitAssets: KitAsset[];
    activeNotes: string;
  };
  presets: MechanismPreset[];
  timeline: {
    keyframes: TimelineKeyframe[];
    activeKeyframeId?: string;
  };
  imports: {
    referenceName?: string;
    referenceUrl?: string;
    referenceKind?: 'image' | 'video' | 'gif';
  };
  tracking: {
    annotations: TrackingAnnotation[];
    activeId?: string;
    showOverlay: boolean;
  };
  compatibility: {
    desktopImportStatus: 'native' | 'partial' | 'none';
    warnings: string[];
  };
  resourceManifest: {
    checkedAt: string;
    desktopResources: string[];
    webResourceFamilies: string[];
    webOnlyMechanisms: MechanismType[];
  };
  vision: VisionAssistState;
}

export interface MechanismTemplate {
  type: MechanismType;
  label: string;
  tagline: string;
  description: string;
  color: string;
  params: Record<string, number>;
  tags: string[];
  complexity: 'intro' | 'intermediate' | 'advanced';
}
