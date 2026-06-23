import type {
  BoneData,
  JointData,
  KitAsset,
  LabEpisode,
  MechanismConfig,
  MechanismPreset,
  MechanismType,
  PartData,
  PathData,
  Point,
  ProjectState,
  SkeletonData,
  TimelineKeyframe,
  TrackingAnnotation,
  Transform
} from '../types';
import { MAX_PATH_POINTS } from './geometry';
import { createMechanism } from './mechanisms';
import { defaultResourceManifestState } from './resourceManifest';
import { err, ok, type Result } from './result';
import { finiteNumberRecord, isRecord, safeBoolean, safeColor, safeInteger, safeNumber, safeString } from './sanitize';
import { smoothTrackingPoints } from './tracking';

const nowIso = (): string => new Date().toISOString();
const mechanismTypes = new Set<MechanismType>(['crank', 'four-bar', 'five-bar', 'six-bar', 'cam-follower', 'gear-pair', 'planetary-gear', 'slider-crank', 'quick-return', 'scotch-yoke']);

const pythonTypeMap: Record<string, MechanismType> = {
  fourbar: 'four-bar',
  '4bar': 'four-bar',
  '4_bar': 'four-bar',
  '4_bar_linkage': 'four-bar',
  fivebar: 'five-bar',
  '5bar': 'five-bar',
  '5_bar': 'five-bar',
  '5_bar_linkage': 'five-bar',
  sixbar: 'six-bar',
  '6bar': 'six-bar',
  '6_bar': 'six-bar',
  '6_bar_linkage': 'six-bar',
  cam: 'cam-follower',
  cam_follower: 'cam-follower',
  'cam-follower': 'cam-follower',
  crank: 'crank',
  rotary_crank: 'crank',
  basic_crank: 'crank',
  gear: 'gear-pair',
  gear_pair: 'gear-pair',
  gear_train: 'gear-pair',
  planetary_gear: 'planetary-gear',
  linkage: 'four-bar',
  linkages: 'four-bar',
  unified_linkage: 'four-bar',
  slider_crank: 'slider-crank',
  'slider-crank': 'slider-crank',
  crank_slider: 'slider-crank',
  crankslider: 'slider-crank',
  piston: 'slider-crank',
  quick_return: 'quick-return',
  'quick-return': 'quick-return',
  quickreturn: 'quick-return',
  slotted_crank: 'quick-return',
  scotch_yoke: 'scotch-yoke',
  'scotch-yoke': 'scotch-yoke',
  scotchyoke: 'scotch-yoke'
};

const safeMechanismType = (value: unknown, fallback: MechanismType = 'four-bar'): MechanismType => {
  if (typeof value !== 'string') return fallback;
  if (mechanismTypes.has(value as MechanismType)) return value as MechanismType;
  return pythonTypeMap[value.trim().toLowerCase()] ?? fallback;
};

const typeFromBarCount = (barCount: number | undefined): MechanismType | undefined => {
  if (barCount === 4) return 'four-bar';
  if (barCount === 5) return 'five-bar';
  if (barCount === 6) return 'six-bar';
  return undefined;
};

const pythonParamAliases: Record<string, string> = {
  bar_count: 'barCount',
  ground_length: 'groundLink',
  ground_link: 'groundLink',
  input_length: 'inputLink',
  input_link: 'inputLink',
  coupler_length: 'couplerLink',
  coupler_link: 'couplerLink',
  output_length: 'outputLink',
  output_link: 'outputLink',
  rocker_link: 'rockerLink',
  pivot_height: 'pivotHeight',
  cam_radius: 'camRadius',
  cam_offset: 'camOffset',
  follower_length: 'followerLength',
  cam_lobes: 'camLobes',
  input_radius: 'inputRadius',
  output_radius: 'outputRadius',
  output_teeth: 'outputTeeth',
  planet_count: 'planetCount',
  sun_radius: 'sunRadius',
  planet_radius: 'planetRadius',
  ring_radius: 'ringRadius',
  crank_radius: 'crankRadius',
  hub_radius: 'hubRadius',
  output_offset: 'outputOffset',
  rod_length: 'rodLength',
  rail_length: 'railLength',
  pivot_distance: 'pivotDistance',
  pivot_offset: 'pivotOffset',
  slider_offset: 'sliderOffset',
  slot_height: 'slotHeight',
  yoke_width: 'yokeWidth'
};

const normalizeParameterAliases = (params: Record<string, number>, barCount?: number): Record<string, number> => {
  const normalized: Record<string, number> = {};
  Object.entries(params).forEach(([key, value]) => {
    normalized[pythonParamAliases[key] ?? key] = value;
  });
  if (barCount !== undefined) normalized.barCount = barCount;
  return normalized;
};

const transform = (overrides: Partial<Transform> = {}): Transform => ({
  x: safeNumber(overrides.x, 0, -5000, 5000),
  y: safeNumber(overrides.y, 0, -5000, 5000),
  rotation: safeNumber(overrides.rotation, 0, -3600, 3600),
  scale: safeNumber(overrides.scale, 1, 0.05, 20)
});

const joint = (id: string, x: number, y: number, parent?: string, name = id): JointData => ({
  id,
  name,
  position: { x, y },
  parent,
  isLocked: false,
  bendDirection: 1
});

export const createHumanoidSkeleton = (): SkeletonData => {
  const joints: Record<string, JointData> = {
    root: joint('root', 0, 0, undefined, 'Root'),
    spine: joint('spine', 0, -58, 'root', 'Spine'),
    neck: joint('neck', 0, -106, 'spine', 'Neck'),
    head: joint('head', 0, -148, 'neck', 'Head'),
    left_shoulder: joint('left_shoulder', -34, -103, 'neck', 'Left shoulder'),
    left_elbow: joint('left_elbow', -75, -82, 'left_shoulder', 'Left elbow'),
    left_wrist: joint('left_wrist', -112, -62, 'left_elbow', 'Left wrist'),
    right_shoulder: joint('right_shoulder', 34, -103, 'neck', 'Right shoulder'),
    right_elbow: joint('right_elbow', 75, -82, 'right_shoulder', 'Right elbow'),
    right_wrist: joint('right_wrist', 112, -62, 'right_elbow', 'Right wrist'),
    left_hip: joint('left_hip', -24, 18, 'root', 'Left hip'),
    left_knee: joint('left_knee', -31, 79, 'left_hip', 'Left knee'),
    left_ankle: joint('left_ankle', -33, 139, 'left_knee', 'Left ankle'),
    right_hip: joint('right_hip', 24, 18, 'root', 'Right hip'),
    right_knee: joint('right_knee', 31, 79, 'right_hip', 'Right knee'),
    right_ankle: joint('right_ankle', 33, 139, 'right_knee', 'Right ankle')
  };
  const bones: BoneData[] = Object.values(joints)
    .filter((j) => j.parent)
    .map((j) => ({ fromJoint: j.parent as string, toJoint: j.id }));
  return { joints, bones, rootJoint: 'root' };
};

const part = (name: string, anchorJoint: string, fillColor: string, zIndex: number, t: Partial<Transform> = {}): PartData => ({
  name,
  texturePath: '',
  maskPath: '',
  anchorJoint,
  transform: transform(t),
  zIndex,
  fillColor,
  opacity: 0.9,
  fixed: false
});

export const createDefaultParts = (): Record<string, PartData> => ({
  torso: part('torso', 'spine', 'rgba(56,189,248,0.35)', 1, { x: 0, y: -46, scale: 1.1 }),
  head: part('head', 'head', 'rgba(251,146,60,0.42)', 3, { x: 0, y: -148 }),
  left_arm: part('left_arm', 'left_wrist', 'rgba(167,139,250,0.36)', 2, { x: -70, y: -80 }),
  right_arm: part('right_arm', 'right_wrist', 'rgba(52,211,153,0.36)', 2, { x: 70, y: -80 }),
  left_leg: part('left_leg', 'left_ankle', 'rgba(244,114,182,0.32)', 0, { x: -30, y: 88 }),
  right_leg: part('right_leg', 'right_ankle', 'rgba(250,204,21,0.3)', 0, { x: 30, y: 88 })
});

const defaultPath = (): PathData => ({
  partName: 'right_wrist',
  points: [
    { x: 450, y: 240 },
    { x: 515, y: 210 },
    { x: 580, y: 270 },
    { x: 530, y: 340 },
    { x: 455, y: 320 }
  ],
  totalDuration: 2.4,
  isClosed: true,
  enabled: true
});

const defaultEpisode = (): LabEpisode => ({
  id: 'episode-1',
  title: 'Trace mismatch autopsy',
  mechanismType: 'four-bar',
  symptom: 'Effector path diverges near upper-right lobe',
  suspectedCause: 'Coupler length and phase offset underfit the drawn target',
  repairAction: 'Adjust coupler point fraction or switch to five-bar search',
  evidenceOutputs: ['before_snapshot', 'after_snapshot', 'mechanical_change'],
  traceMetrics: { closure_error: 18, coverage: 0.74 },
  status: 'draft',
  notes: 'MS4N-ready notes can be exported with the project JSON.'
});

const defaultTimeline = (): TimelineKeyframe[] => [
  {
    id: 'keyframe-1',
    label: 'Opening pose',
    angle: 0,
    duration: 0.8,
    mechanismId: undefined,
    partName: 'right_wrist',
    notes: 'Start of the character motion loop.'
  },
  {
    id: 'keyframe-2',
    label: 'Peak action',
    angle: 180,
    duration: 0.8,
    mechanismId: undefined,
    partName: 'right_wrist',
    notes: 'Peak mechanical output for storyboard export.'
  }
];

export const createDefaultKitAssets = (): KitAsset[] => [
  {
    id: 'bar-board',
    label: 'Bar Board Base',
    filename: 'kit/bar-board.svg',
    assetType: 'laser_cut_svg',
    mechanismTypes: ['4_bar_linkage', 'crank_slider'],
    evidenceOutputs: ['before_snapshot', 'after_snapshot', 'breakdown_repair_episode'],
    description: 'Peg-board base plate for pivot placement, spacing, and linkage alignment experiments.',
    pilotPriority: 'P0'
  },
  {
    id: 'ms4n-01-linkage-bars',
    label: 'Inspectable Linkage Bars',
    filename: 'kit/ms4n-01-linkage-bars.svg',
    assetType: 'laser_cut_svg',
    mechanismTypes: ['4_bar_linkage'],
    evidenceOutputs: ['mechanical_change', 'motion_consequence'],
    description: 'Selectable linkage bars for one-change/one-motion repair episodes.',
    pilotPriority: 'P0'
  },
  {
    id: 'ms4n-02-cam-follower-kit',
    label: 'Cam and Follower Set',
    filename: 'kit/ms4n-02-cam-follower-kit.svg',
    assetType: 'laser_cut_svg',
    mechanismTypes: ['cam'],
    evidenceOutputs: ['mechanical_change', 'motion_consequence'],
    description: 'Cam profile variants for rise/fall explanation episodes.',
    pilotPriority: 'P1'
  },
  {
    id: 'ms4n-03-crank-slider-kit',
    label: 'Crank Slider Set',
    filename: 'kit/ms4n-03-crank-slider-kit.svg',
    assetType: 'laser_cut_svg',
    mechanismTypes: ['crank_slider'],
    evidenceOutputs: ['breakdown_repair_episode'],
    description: 'Linear push/pull mechanism kit for character actions.',
    pilotPriority: 'P1'
  },
  {
    id: 'ms4n-04-gears-pulleys-kit',
    label: 'Gears and Pulleys Set',
    filename: 'kit/ms4n-04-gears-pulleys-kit.svg',
    assetType: 'laser_cut_svg',
    mechanismTypes: ['gear', 'planetary_gear'],
    evidenceOutputs: ['coordination_relation'],
    description: 'Coordination parts for comparative gear and timing families.',
    pilotPriority: 'P1'
  },
  {
    id: 'ms4n-05-character-connectors',
    label: 'Character Connectors',
    filename: 'kit/ms4n-05-character-connectors.svg',
    assetType: 'laser_cut_svg',
    mechanismTypes: ['4_bar_linkage', 'cam', 'crank_slider', 'gear'],
    evidenceOutputs: ['character_action_mapping'],
    description: 'Connectors that make motion-to-character-action mappings visible and reversible.',
    pilotPriority: 'P0'
  }
];

export const createDefaultProject = (): ProjectState => {
  const createdAt = nowIso();
  const mechanisms = [
    createMechanism('four-bar', 0),
    createMechanism('cam-follower', 1),
    createMechanism('gear-pair', 2),
    createMechanism('slider-crank', 3),
    createMechanism('scotch-yoke', 4)
  ];
  mechanisms[0] = { ...mechanisms[0], name: 'Right wrist crank-rocker', anchor: { x: 360, y: 285 }, partName: 'right_wrist' };
  mechanisms[1] = { ...mechanisms[1], name: 'Follower test cam', anchor: { x: 690, y: 300 }, partName: 'head' };
  mechanisms[2] = { ...mechanisms[2], name: 'Timing gear pair', anchor: { x: 205, y: 180 }, partName: 'left_wrist' };
  mechanisms[3] = { ...mechanisms[3], name: 'Push-pull slider', anchor: { x: 250, y: 510 }, partName: 'right_ankle' };
  mechanisms[4] = { ...mechanisms[4], name: 'Yoke wave drive', anchor: { x: 690, y: 530 }, partName: 'left_ankle' };
  return {
    metadata: { version: 'web-0.1', name: 'Automataii Web Studio', createdAt, modifiedAt: createdAt },
    parts: createDefaultParts(),
    skeleton: createHumanoidSkeleton(),
    paths: { right_wrist: defaultPath() },
    mechanisms,
    selectedPathPart: 'right_wrist',
    settings: {
      theme: 'light',
      units: 'px',
      animationDuration: 4,
      showPhysicsSnap: true,
      physicsSnapMode: 'adaptive',
      gridSize: 32,
      showTraces: true,
      showForces: true,
      showSafetyZones: true,
      showSkeleton: true,
      showCharacterParts: true,
      reducedMotion: false,
      targetFps: 60,
      performancePreset: 'balanced',
      workflowMode: 'guided',
      viewport: { x: 0, y: 0, zoom: 1, panMode: false }
    },
    lab: { episodes: [defaultEpisode()], kitAssets: createDefaultKitAssets(), activeNotes: 'Capture breakdown/repair observations here.' },
    presets: mechanisms.slice(0, 3).map((mechanism, index) => ({
      id: `preset-${index + 1}`,
      name: mechanism.name,
      type: mechanism.type,
      config: { ...mechanism, params: { ...mechanism.params } },
      createdAt
    })),
    timeline: { keyframes: defaultTimeline() },
    imports: {},
    tracking: { annotations: [], showOverlay: true },
    compatibility: { desktopImportStatus: 'native', warnings: [] },
    resourceManifest: defaultResourceManifestState(),
    vision: { confidence: 0, warnings: [], inferredJointCount: 0, inferredPartCount: 0 }
  };
};

const asPoint = (value: unknown, fallback: Point): Point => {
  if (Array.isArray(value) && value.length >= 2) {
    return { x: safeNumber(value[0], fallback.x, -10000, 10000), y: safeNumber(value[1], fallback.y, -10000, 10000) };
  }
  if (!isRecord(value)) return fallback;
  return {
    x: safeNumber(value.x, fallback.x, -10000, 10000),
    y: safeNumber(value.y, fallback.y, -10000, 10000)
  };
};

const normalizeMechanism = (raw: unknown, index: number): MechanismConfig | null => {
  if (!isRecord(raw)) return null;
  const paramSource = { ...finiteNumberRecord(raw.parameters), ...finiteNumberRecord(raw.params) };
  const barCount = safeInteger(
    raw.barCount,
    safeInteger(raw.bar_count, safeInteger(paramSource.barCount, safeInteger(paramSource.bar_count, Number.NaN, 0, 12), 0, 12), 0, 12),
    0,
    12
  );
  const sourceType = safeString(raw.type, safeString(raw.mechanism_type));
  const type = typeFromBarCount(Number.isFinite(barCount) ? barCount : undefined) ?? safeMechanismType(sourceType);
  const defaults = createMechanism(type, index);
  const rawParams = normalizeParameterAliases(paramSource, Number.isFinite(barCount) ? barCount : undefined);
  const rawLayerData = isRecord(raw.layerData) ? raw.layerData : isRecord(raw.layer_data) ? raw.layer_data : undefined;
  return {
    ...defaults,
    id: safeString(raw.id, defaults.id),
    name: safeString(raw.name, defaults.name),
    type,
    partName: safeString(raw.partName, safeString(raw.part_name, defaults.partName)),
    color: safeColor(raw.color, defaults.color),
    enabled: safeBoolean(raw.enabled, defaults.enabled),
    anchor: asPoint(raw.anchor, defaults.anchor),
    rotationDeg: safeNumber(raw.rotationDeg, safeNumber(raw.rotation_deg, defaults.rotationDeg, -3600, 3600), -3600, 3600),
    speed: safeNumber(raw.speed, defaults.speed, -20, 20),
    params: { ...defaults.params, ...rawParams },
    layerData: {
      ...(rawLayerData ?? {}),
      python_import: sourceType === 'linkages' || sourceType === 'linkage' || sourceType === 'unified_linkage',
      bar_count: Number.isFinite(barCount) ? barCount : undefined
    }
  };
};

const normalizeMechanisms = (value: unknown, fallback: MechanismConfig[]): MechanismConfig[] => {
  const source = Array.isArray(value) ? value : isRecord(value) ? Object.entries(value).map(([id, raw]) => (isRecord(raw) ? { id, ...raw } : raw)) : [];
  const mechanisms = source
    .map((item, index) => normalizeMechanism(item, index))
    .filter((item): item is MechanismConfig => item !== null);
  return mechanisms.length > 0 ? mechanisms : fallback;
};

const normalizePart = (raw: unknown, nameFallback: string, fallback: PartData): PartData | null => {
  if (!isRecord(raw)) return null;
  const rawTransform = isRecord(raw.transform)
    ? raw.transform
    : Array.isArray(raw.default_transform)
      ? { x: raw.default_transform[0], y: raw.default_transform[1], rotation: raw.default_transform[2], scale: fallback.transform.scale }
      : {};
  return {
    ...fallback,
    name: safeString(raw.name, nameFallback),
    texturePath: safeString(raw.texturePath, safeString(raw.texture_path, safeString(raw.svg_path, fallback.texturePath))),
    maskPath: safeString(raw.maskPath, safeString(raw.mask_path, safeString(raw.svg_path, fallback.maskPath))),
    anchorJoint: safeString(raw.anchorJoint, safeString(raw.anchor_joint, fallback.anchorJoint)),
    transform: transform(rawTransform),
    zIndex: safeInteger(raw.zIndex, safeInteger(raw.z_index, fallback.zIndex, -100, 100), -100, 100),
    fillColor: safeColor(raw.fillColor, safeColor(raw.fill_color, fallback.fillColor)),
    opacity: safeNumber(raw.opacity, fallback.opacity, 0, 1),
    fixed: safeBoolean(raw.fixed, fallback.fixed),
    group: safeString(raw.group, fallback.group ?? '') || undefined,
    localPivotOffset: Array.isArray(raw.localPivotOffset) ? asPoint(raw.localPivotOffset, fallback.localPivotOffset ?? { x: 0, y: 0 }) : Array.isArray(raw.local_pivot_offset) ? asPoint(raw.local_pivot_offset, fallback.localPivotOffset ?? { x: 0, y: 0 }) : fallback.localPivotOffset
  };
};

const normalizeParts = (value: unknown, fallback: Record<string, PartData>): Record<string, PartData> => {
  if (!isRecord(value)) return fallback;
  const parts = Object.fromEntries(
    Object.entries(value)
      .map(([name, raw]) => [name, normalizePart(raw, name, fallback[name] ?? part(name, 'root', '#94a3b8', 0))] as const)
      .filter((entry): entry is readonly [string, PartData] => entry[1] !== null)
  );
  return Object.keys(parts).length > 0 ? parts : fallback;
};

const normalizePointArray = (value: unknown): Point[] => {
  if (!Array.isArray(value)) return [];
  const source = value.length <= MAX_PATH_POINTS
    ? value
    : Array.from({ length: MAX_PATH_POINTS }, (_, index) => value[Math.round((index * (value.length - 1)) / (MAX_PATH_POINTS - 1))]);
  return source.map((item) => asPoint(item, { x: 0, y: 0 })).filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
};

const normalizePath = (raw: unknown, key: string, fallback?: PathData): PathData | null => {
  if (!isRecord(raw)) return null;
  const partName = safeString(raw.partName, safeString(raw.part_name, fallback?.partName ?? key));
  return {
    partName,
    points: normalizePointArray(raw.points),
    totalDuration: safeNumber(raw.totalDuration, safeNumber(raw.total_duration, fallback?.totalDuration ?? 0.25, 0.25, 3600), 0.25, 3600),
    isClosed: safeBoolean(raw.isClosed, safeBoolean(raw.is_closed, fallback?.isClosed ?? false)),
    enabled: safeBoolean(raw.enabled, fallback?.enabled ?? true)
  };
};

const normalizePaths = (value: unknown, fallback: Record<string, PathData>): Record<string, PathData> => {
  const source = Array.isArray(value) ? value.map((pathItem, index) => [`path-${index}`, pathItem] as const) : isRecord(value) ? Object.entries(value) : [];
  const paths = Object.fromEntries(
    source
      .map(([key, raw]) => {
        const pathData = normalizePath(raw, key, fallback[key]);
        return [pathData?.partName ?? key, pathData] as const;
      })
      .filter((entry): entry is readonly [string, PathData] => entry[1] !== null)
  );
  return Object.keys(paths).length > 0 ? paths : fallback;
};

const normalizeSkeleton = (value: unknown, fallback?: SkeletonData): SkeletonData | undefined => {
  if (!isRecord(value) && !Array.isArray(value)) return fallback;
  const skeletonRecord = isRecord(value) ? value : {};
  const rawJoints = Array.isArray(value)
    ? Object.fromEntries(value.filter(isRecord).map((jointRecord, index) => [safeString(jointRecord.id, `joint-${index + 1}`), jointRecord]))
    : isRecord(skeletonRecord.joints)
      ? skeletonRecord.joints
      : {};
  const joints = Object.fromEntries(
    Object.entries(rawJoints)
      .filter(([, raw]) => isRecord(raw))
      .map(([id, raw]) => {
        const record = raw as Record<string, unknown>;
        return [
          id,
          {
            id: safeString(record.id, id),
            name: safeString(record.name, safeString(record.label, id)),
            position: asPoint(record.position, { x: 0, y: 0 }),
            parent: safeString(record.parent, safeString(record.parent_id, '')) || undefined,
            isLocked: safeBoolean(record.isLocked, safeBoolean(record.is_locked, false)),
            bendDirection: safeNumber(record.bendDirection, safeNumber(record.bend_direction, 1, -1, 1), -1, 1)
          }
        ] as const;
      })
  );
  const hierarchyBones = isRecord(skeletonRecord.hierarchy)
    ? Object.entries(skeletonRecord.hierarchy).flatMap(([fromJoint, children]) => Array.isArray(children) ? children.map((child) => ({ fromJoint, toJoint: safeString(child) })).filter((bone) => bone.toJoint) : [])
    : [];
  const bones = Array.isArray(skeletonRecord.bones)
    ? skeletonRecord.bones
        .filter(isRecord)
        .map((bone) => ({ fromJoint: safeString(bone.fromJoint, safeString(bone.from_joint)), toJoint: safeString(bone.toJoint, safeString(bone.to_joint)) }))
        .filter((bone) => bone.fromJoint && bone.toJoint)
    : hierarchyBones.length > 0
      ? hierarchyBones
      : Object.values(joints).flatMap((joint) => joint.parent ? [{ fromJoint: joint.parent, toJoint: joint.id }] : []);
  if (Object.keys(joints).length === 0) return fallback;
  const rootFromList = Array.isArray(skeletonRecord.root_joint_ids) ? safeString(skeletonRecord.root_joint_ids[0]) : '';
  const inferredRoot = Object.values(joints).find((joint) => !joint.parent)?.id ?? fallback?.rootJoint ?? 'root';
  return { joints, bones, rootJoint: safeString(skeletonRecord.rootJoint, safeString(skeletonRecord.root_joint, rootFromList || inferredRoot)) };
};

const normalizeSettings = (value: unknown, fallback: ProjectState['settings']): ProjectState['settings'] => {
  if (!isRecord(value)) return fallback;
  const theme = value.theme === 'light' ? 'light' : value.theme === 'dark' ? 'dark' : fallback.theme;
  const units = value.units === 'mm' || value.units === 'in' || value.units === 'px' ? value.units : fallback.units;
  return {
    theme,
    units,
    animationDuration: safeNumber(value.animationDuration, fallback.animationDuration, 0.25, 120),
    showPhysicsSnap: safeBoolean(value.showPhysicsSnap, fallback.showPhysicsSnap),
    physicsSnapMode: value.physicsSnapMode === 'off' || value.physicsSnapMode === 'grid' || value.physicsSnapMode === 'adaptive' ? value.physicsSnapMode : fallback.physicsSnapMode,
    gridSize: safeNumber(value.gridSize, safeNumber(value.grid_size, fallback.gridSize, 4, 128), 4, 128),
    showTraces: safeBoolean(value.showTraces, fallback.showTraces),
    showForces: safeBoolean(value.showForces, fallback.showForces),
    showSafetyZones: safeBoolean(value.showSafetyZones, fallback.showSafetyZones),
    showSkeleton: safeBoolean(value.showSkeleton, fallback.showSkeleton),
    showCharacterParts: safeBoolean(value.showCharacterParts, fallback.showCharacterParts),
    reducedMotion: safeBoolean(value.reducedMotion, fallback.reducedMotion),
    targetFps: safeInteger(value.targetFps, safeInteger(value.target_fps, fallback.targetFps, 12, 120), 12, 120),
    performancePreset: value.performancePreset === 'quality' || value.performancePreset === 'balanced' || value.performancePreset === 'performance' ? value.performancePreset : fallback.performancePreset,
    workflowMode: value.workflowMode === 'guided' || value.workflowMode === 'flexible' ? value.workflowMode : fallback.workflowMode,
    viewport: isRecord(value.viewport)
      ? {
          x: safeNumber(value.viewport.x, fallback.viewport.x, -2000, 2000),
          y: safeNumber(value.viewport.y, fallback.viewport.y, -2000, 2000),
          zoom: safeNumber(value.viewport.zoom, fallback.viewport.zoom, 0.35, 4),
          panMode: safeBoolean(value.viewport.panMode, fallback.viewport.panMode)
        }
      : fallback.viewport
  };
};

const normalizeKitAsset = (raw: unknown, fallback?: KitAsset): KitAsset | null => {
  if (!isRecord(raw)) return fallback ?? null;
  const priority = raw.pilotPriority === 'P0' || raw.pilotPriority === 'P1' || raw.pilotPriority === 'P2' ? raw.pilotPriority : raw.pilot_priority === 'P0' || raw.pilot_priority === 'P1' || raw.pilot_priority === 'P2' ? raw.pilot_priority : fallback?.pilotPriority ?? 'P1';
  return {
    id: safeString(raw.id, fallback?.id ?? `kit-${Date.now().toString(36)}`),
    label: safeString(raw.label, fallback?.label ?? 'Kit asset'),
    filename: safeString(raw.filename, fallback?.filename ?? ''),
    assetType: safeString(raw.assetType, safeString(raw.asset_type, fallback?.assetType ?? 'asset')),
    mechanismTypes: Array.isArray(raw.mechanismTypes) ? raw.mechanismTypes.map((item) => safeString(item)).filter(Boolean) : Array.isArray(raw.mechanism_types) ? raw.mechanism_types.map((item) => safeString(item)).filter(Boolean) : fallback?.mechanismTypes ?? [],
    evidenceOutputs: Array.isArray(raw.evidenceOutputs) ? raw.evidenceOutputs.map((item) => safeString(item)).filter(Boolean) : Array.isArray(raw.evidence_outputs) ? raw.evidence_outputs.map((item) => safeString(item)).filter(Boolean) : fallback?.evidenceOutputs ?? [],
    description: safeString(raw.description, fallback?.description ?? ''),
    pilotPriority: priority
  };
};

const normalizeLabEpisodes = (raw: unknown, fallback: LabEpisode[]): LabEpisode[] => {
  if (!Array.isArray(raw)) return fallback;
  const episodes = raw
    .filter(isRecord)
    .map((episode, index) => {
      const status: LabEpisode['status'] = episode.status === 'observed' || episode.status === 'repaired' || episode.status === 'draft' ? episode.status : 'draft';
      const rawMechanismType = safeString(episode.mechanismType, safeString(episode.mechanism_type));
      const mechanismType: LabEpisode['mechanismType'] = mechanismTypes.has(rawMechanismType as MechanismType)
        ? rawMechanismType as MechanismType
        : rawMechanismType === 'mixed'
          ? 'mixed'
          : undefined;
      return {
        id: safeString(episode.id, `episode-${index + 1}`),
        title: safeString(episode.title, 'Mechanism change episode'),
        mechanismType,
        symptom: safeString(episode.symptom),
        suspectedCause: safeString(episode.suspectedCause, safeString(episode.suspected_cause)),
        repairAction: safeString(episode.repairAction, safeString(episode.repair_action)),
        evidenceOutputs: Array.isArray(episode.evidenceOutputs)
          ? episode.evidenceOutputs.map((item) => safeString(item)).filter(Boolean)
          : Array.isArray(episode.evidence_outputs)
            ? episode.evidence_outputs.map((item) => safeString(item)).filter(Boolean)
            : undefined,
        traceMetrics: finiteNumberRecord(episode.traceMetrics ?? episode.trace_metrics),
        status,
        notes: safeString(episode.notes)
      };
    });
  return episodes.length > 0 ? episodes : fallback;
};

const normalizeTrackingAnnotation = (raw: unknown, index: number): TrackingAnnotation | null => {
  if (!isRecord(raw)) return null;
  const kind = raw.sourceKind === 'video' || raw.sourceKind === 'gif' || raw.sourceKind === 'image' ? raw.sourceKind : 'image';
  const closed = safeBoolean(raw.isClosed, safeBoolean(raw.is_closed, false));
  const points = normalizePointArray(raw.points);
  return {
    id: safeString(raw.id, `tracking-${index + 1}`),
    sourceName: safeString(raw.sourceName, safeString(raw.source_name, 'reference')),
    sourceKind: kind,
    points,
    smoothedPoints: normalizePointArray(raw.smoothedPoints).length > 0 ? normalizePointArray(raw.smoothedPoints) : smoothTrackingPoints(points, closed),
    isClosed: closed,
    duration: safeNumber(raw.duration, 2.4, 0.25, 120),
    createdAt: safeString(raw.createdAt, safeString(raw.created_at, nowIso()))
  };
};

const normalizeTracking = (raw: unknown, fallback: ProjectState['tracking']): ProjectState['tracking'] => {
  if (!isRecord(raw)) return fallback;
  const annotations = Array.isArray(raw.annotations)
    ? raw.annotations.map((item, index) => normalizeTrackingAnnotation(item, index)).filter((item): item is TrackingAnnotation => item !== null)
    : fallback.annotations;
  return {
    annotations,
    activeId: safeString(raw.activeId, safeString(raw.active_id, fallback.activeId ?? '')) || undefined,
    showOverlay: safeBoolean(raw.showOverlay, fallback.showOverlay)
  };
};

const safeReferenceUrl = (value: unknown): string | undefined => {
  const text = safeString(value).trim();
  if (/^(blob:|data:image\/|data:video\/|https?:\/\/)/i.test(text)) return text;
  return undefined;
};

const normalizePreset = (raw: unknown, index: number): MechanismPreset | null => {
  if (!isRecord(raw)) return null;
  const config = normalizeMechanism(raw.config, index);
  if (!config) return null;
  return {
    id: safeString(raw.id, `preset-${index + 1}`),
    name: safeString(raw.name, config.name),
    type: config.type,
    config,
    createdAt: safeString(raw.createdAt, safeString(raw.created_at, nowIso()))
  };
};

const normalizeTimelineKeyframe = (raw: unknown, index: number): TimelineKeyframe | null => {
  if (!isRecord(raw)) return null;
  return {
    id: safeString(raw.id, `keyframe-${index + 1}`),
    label: safeString(raw.label, `Keyframe ${index + 1}`),
    angle: safeNumber(raw.angle, 0, 0, 360),
    duration: safeNumber(raw.duration, 0.8, 0.05, 120),
    mechanismId: safeString(raw.mechanismId, safeString(raw.mechanism_id, '')) || undefined,
    partName: safeString(raw.partName, safeString(raw.part_name, '')) || undefined,
    notes: safeString(raw.notes)
  };
};

export const normalizeProject = (raw: unknown): ProjectState => {
  const fallback = createDefaultProject();
  if (!isRecord(raw)) return fallback;
  const rawMetadata = isRecord(raw.metadata) ? raw.metadata : {};
  const characterRecord = isRecord(raw.character)
    ? raw.character
    : isRecord(raw.character_preset)
      ? raw.character_preset
      : isRecord(raw.characterPreset)
        ? raw.characterPreset
        : {};
  const parts = normalizeParts(raw.parts ?? characterRecord.parts, fallback.parts);
  const paths = normalizePaths(raw.paths, fallback.paths);
  const selectedPathPart = safeString(raw.selectedPathPart, safeString(raw.selected_path_part, fallback.selectedPathPart));
  const desktopSignals = ['parts', 'skeleton', 'mechanisms', 'paths'].filter((key) => key in raw).length;
  const warnings = desktopSignals > 0 && raw.metadata === undefined ? ['Imported desktop-shaped data with best-effort web adapters'] : [];
  const rawLab = isRecord(raw.lab) ? raw.lab : {};
  const rawKitAssets = Array.isArray(rawLab.kitAssets) ? rawLab.kitAssets : Array.isArray(rawLab.kit_assets) ? rawLab.kit_assets : fallback.lab.kitAssets;
  const kitAssets = rawKitAssets.map((item, index) => normalizeKitAsset(item, fallback.lab.kitAssets[index])).filter((item): item is KitAsset => item !== null);
  const presets = Array.isArray(raw.presets) ? raw.presets.map((item, index) => normalizePreset(item, index)).filter((item): item is MechanismPreset => item !== null) : fallback.presets;
  const rawTimeline = isRecord(raw.timeline) ? raw.timeline : {};
  const keyframes = Array.isArray(rawTimeline.keyframes)
    ? rawTimeline.keyframes.map((item, index) => normalizeTimelineKeyframe(item, index)).filter((item): item is TimelineKeyframe => item !== null)
    : fallback.timeline.keyframes;
  const rawVision = isRecord(raw.vision) ? raw.vision : {};
  return {
    ...fallback,
    metadata: {
      version: safeString(rawMetadata.version, fallback.metadata.version),
      name: safeString(rawMetadata.name, fallback.metadata.name),
      createdAt: safeString(rawMetadata.createdAt, safeString(rawMetadata.created_at, fallback.metadata.createdAt)),
      modifiedAt: nowIso()
    },
    parts,
    skeleton: normalizeSkeleton(raw.skeleton ?? characterRecord.skeleton, fallback.skeleton),
    paths,
    mechanisms: normalizeMechanisms(raw.mechanisms, fallback.mechanisms),
    selectedPathPart: paths[selectedPathPart] ? selectedPathPart : Object.keys(paths)[0] ?? fallback.selectedPathPart,
    settings: normalizeSettings(raw.settings, fallback.settings),
    lab: isRecord(raw.lab)
      ? {
          episodes: normalizeLabEpisodes(rawLab.episodes, fallback.lab.episodes),
          kitAssets: kitAssets.length > 0 ? kitAssets : fallback.lab.kitAssets,
          activeNotes: safeString(rawLab.activeNotes, safeString(rawLab.active_notes, fallback.lab.activeNotes))
        }
      : fallback.lab,
    presets,
    timeline: {
      keyframes,
      activeKeyframeId: safeString(rawTimeline.activeKeyframeId, safeString(rawTimeline.active_keyframe_id, fallback.timeline.activeKeyframeId ?? '')) || undefined
    },
    imports: isRecord(raw.imports)
      ? {
          referenceName: safeString(raw.imports.referenceName) || undefined,
          referenceUrl: safeReferenceUrl(raw.imports.referenceUrl),
          referenceKind: raw.imports.referenceKind === 'video' || raw.imports.referenceKind === 'gif' || raw.imports.referenceKind === 'image' ? raw.imports.referenceKind : undefined
        }
      : fallback.imports,
    tracking: normalizeTracking(raw.tracking, fallback.tracking),
    compatibility: isRecord(raw.compatibility)
      ? {
          desktopImportStatus: raw.compatibility.desktopImportStatus === 'partial' || raw.compatibility.desktopImportStatus === 'none' || raw.compatibility.desktopImportStatus === 'native' ? raw.compatibility.desktopImportStatus : 'partial',
          warnings: Array.isArray(raw.compatibility.warnings) ? raw.compatibility.warnings.map((item) => safeString(item)).filter(Boolean) : warnings
        }
      : { desktopImportStatus: warnings.length > 0 ? 'partial' : 'native', warnings },
    resourceManifest: isRecord(raw.resourceManifest)
      ? {
          checkedAt: safeString(raw.resourceManifest.checkedAt, safeString(raw.resourceManifest.checked_at, fallback.resourceManifest.checkedAt)),
          desktopResources: Array.isArray(raw.resourceManifest.desktopResources)
            ? raw.resourceManifest.desktopResources.map((item) => safeString(item)).filter(Boolean)
            : fallback.resourceManifest.desktopResources,
          webResourceFamilies: Array.isArray(raw.resourceManifest.webResourceFamilies)
            ? raw.resourceManifest.webResourceFamilies.map((item) => safeString(item)).filter(Boolean)
            : fallback.resourceManifest.webResourceFamilies,
          webOnlyMechanisms: Array.isArray(raw.resourceManifest.webOnlyMechanisms)
            ? raw.resourceManifest.webOnlyMechanisms.map((item) => safeMechanismType(item, 'four-bar')).filter((type, index, list) => list.indexOf(type) === index)
            : fallback.resourceManifest.webOnlyMechanisms
        }
      : fallback.resourceManifest,
    vision: {
      lastRunAt: safeString(rawVision.lastRunAt, safeString(rawVision.last_run_at, fallback.vision.lastRunAt ?? '')) || undefined,
      confidence: safeNumber(rawVision.confidence, fallback.vision.confidence, 0, 1),
      warnings: Array.isArray(rawVision.warnings) ? rawVision.warnings.map((item) => safeString(item)).filter(Boolean) : fallback.vision.warnings,
      inferredJointCount: safeInteger(rawVision.inferredJointCount, safeInteger(rawVision.inferred_joint_count, fallback.vision.inferredJointCount, 0, 256), 0, 256),
      inferredPartCount: safeInteger(rawVision.inferredPartCount, safeInteger(rawVision.inferred_part_count, fallback.vision.inferredPartCount, 0, 256), 0, 256),
      parityMode: rawVision.parityMode === 'browser-safe' || rawVision.parity_mode === 'browser-safe'
        ? 'browser-safe'
        : rawVision.parityMode === 'insufficient-input' || rawVision.parity_mode === 'insufficient-input'
          ? 'insufficient-input'
          : fallback.vision.parityMode,
      nonWebInfrastructure: Array.isArray(rawVision.nonWebInfrastructure)
        ? rawVision.nonWebInfrastructure.map((item) => safeString(item)).filter(Boolean)
        : Array.isArray(rawVision.non_web_infrastructure)
          ? rawVision.non_web_infrastructure.map((item) => safeString(item)).filter(Boolean)
          : fallback.vision.nonWebInfrastructure
    }
  };
};

export const serializeProject = (project: ProjectState): string => JSON.stringify(
  { ...project, metadata: { ...project.metadata, modifiedAt: nowIso() } },
  null,
  2
).replace(/[<>&]/g, (char) => ({ '<': '\\u003c', '>': '\\u003e', '&': '\\u0026' })[char] ?? char);

export const parseProject = (text: string): ProjectState => normalizeProject(JSON.parse(text) as unknown);

export const parseProjectResult = (text: string): Result<ProjectState, { code: 'invalid-json' | 'normalization-failed'; message: string }> => {
  try {
    return ok(parseProject(text));
  } catch (error) {
    return err({
      code: error instanceof SyntaxError ? 'invalid-json' : 'normalization-failed',
      message: error instanceof Error ? error.message : 'Project import failed'
    });
  }
};
