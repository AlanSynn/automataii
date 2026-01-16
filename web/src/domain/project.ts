export type PointTuple = [number, number]

export interface Point {
  x: number
  y: number
}

export const PointUtils = {
  fromTuple: (tuple: PointTuple): Point => ({ x: tuple[0], y: tuple[1] }),
  toTuple: (point: Point): PointTuple => [point.x, point.y],
}

export interface Transform {
  x: number
  y: number
  rotation: number
  scale: number
}

export const DEFAULT_TRANSFORM: Transform = {
  x: 0,
  y: 0,
  rotation: 0,
  scale: 1,
}

export const DEFAULT_PIVOT: Point = {
  x: 0,
  y: 0,
}

export interface PartData {
  name: string
  texturePath: string | null
  maskPath: string | null
  anchorJoint: string | null
  pivot: Point
  transform: Transform
  zIndex: number
}

export interface JointData {
  id: string
  position: Point
  parent: string | null
  isLocked: boolean
  bendDirection: string
}

export interface BoneData {
  fromJoint: string
  toJoint: string
}

export interface SkeletonData {
  joints: Record<string, JointData>
  bones: BoneData[]
  rootJoint: string | null
}

export interface TimedPoint {
  x: number
  y: number
  t: number
}

export interface PathData {
  partName: string
  points: Point[]
  timedPoints: TimedPoint[] | null
  totalDuration: number | null
  isClosed: boolean
  enabled: boolean
}

export interface MechanismData {
  id: string
  partName: string
  type: string
  params: Record<string, MechanismParam>
  enabled: boolean
}

export type MechanismParam =
  | string
  | number
  | boolean
  | null
  | MechanismParam[]
  | { [key: string]: MechanismParam }

export interface ProjectMetadata {
  version: string
  name: string
  createdAt: string
  modifiedAt: string
}

export interface ProjectStateData {
  projectDir: string | null
  imagePath: string | null
  parts: Record<string, PartData>
  skeleton: SkeletonData | null
  paths: Record<string, PathData>
  mechanisms: Record<string, MechanismData>
  metadata: ProjectMetadata
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const toString = (value: unknown, fallback: string): string =>
  typeof value === 'string' ? value : fallback

const toNullableString = (value: unknown): string | null =>
  typeof value === 'string' ? value : null

const toNumber = (value: unknown, fallback: number): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : fallback

const toBoolean = (value: unknown, fallback: boolean): boolean =>
  typeof value === 'boolean' ? value : fallback

const toPointTuple = (value: unknown, fallback: Point): Point => {
  if (Array.isArray(value) && value.length >= 2) {
    const x = toNumber(value[0], fallback.x)
    const y = toNumber(value[1], fallback.y)
    return { x, y }
  }
  if (isRecord(value)) {
    return {
      x: toNumber(value.x, fallback.x),
      y: toNumber(value.y, fallback.y),
    }
  }
  return fallback
}

const toTransform = (value: unknown): Transform => {
  if (!isRecord(value)) {
    return { ...DEFAULT_TRANSFORM }
  }
  return {
    x: toNumber(value.x, DEFAULT_TRANSFORM.x),
    y: toNumber(value.y, DEFAULT_TRANSFORM.y),
    rotation: toNumber(value.rotation, DEFAULT_TRANSFORM.rotation),
    scale: toNumber(value.scale, DEFAULT_TRANSFORM.scale),
  }
}

const sanitizeMechanismParam = (value: unknown): MechanismParam => {
  if (
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean' ||
    value === null
  ) {
    return value
  }
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeMechanismParam(item))
  }
  if (isRecord(value)) {
    const output: Record<string, MechanismParam> = {}
    Object.entries(value).forEach(([key, entry]) => {
      output[key] = sanitizeMechanismParam(entry)
    })
    return output
  }
  return null
}

export const PathUtils = {
  getPointAtProgress: (path: PathData, progress: number): Point => {
    const safeProgress = Math.min(Math.max(progress, 0), 1)
    if (path.timedPoints && path.timedPoints.length > 0) {
      const totalDuration = path.totalDuration ?? 0
      if (totalDuration <= 0) {
        return { x: 0, y: 0 }
      }
      return PathUtils.interpolateAtTime(
        path.timedPoints,
        safeProgress * totalDuration
      )
    }
    return PathUtils.interpolateUniform(path.points, safeProgress)
  },
  interpolateAtTime: (timedPoints: TimedPoint[], time: number): Point => {
    if (timedPoints.length === 0) {
      return { x: 0, y: 0 }
    }
    if (timedPoints.length === 1) {
      return { x: timedPoints[0].x, y: timedPoints[0].y }
    }
    const clamped = Math.min(
      Math.max(time, timedPoints[0].t),
      timedPoints[timedPoints.length - 1].t
    )
    for (let index = 0; index < timedPoints.length - 1; index += 1) {
      const current = timedPoints[index]
      const next = timedPoints[index + 1]
      if (current.t <= clamped && clamped <= next.t) {
        const span = next.t - current.t
        const ratio = span === 0 ? 0 : (clamped - current.t) / span
        return {
          x: current.x + (next.x - current.x) * ratio,
          y: current.y + (next.y - current.y) * ratio,
        }
      }
    }
    const last = timedPoints[timedPoints.length - 1]
    return { x: last.x, y: last.y }
  },
  interpolateUniform: (points: Point[], progress: number): Point => {
    if (points.length === 0) {
      return { x: 0, y: 0 }
    }
    if (points.length === 1) {
      return { x: points[0].x, y: points[0].y }
    }
    const scaled = progress * (points.length - 1)
    const index = Math.floor(scaled)
    if (index >= points.length - 1) {
      return { x: points[points.length - 1].x, y: points[points.length - 1].y }
    }
    const ratio = scaled - index
    const current = points[index]
    const next = points[index + 1]
    return {
      x: current.x + (next.x - current.x) * ratio,
      y: current.y + (next.y - current.y) * ratio,
    }
  },
}

export class ProjectState {
  readonly projectDir: string | null
  readonly imagePath: string | null
  readonly parts: Record<string, PartData>
  readonly skeleton: SkeletonData | null
  readonly paths: Record<string, PathData>
  readonly mechanisms: Record<string, MechanismData>
  readonly metadata: ProjectMetadata

  constructor(data: ProjectStateData) {
    this.projectDir = data.projectDir
    this.imagePath = data.imagePath
    this.parts = data.parts
    this.skeleton = data.skeleton
    this.paths = data.paths
    this.mechanisms = data.mechanisms
    this.metadata = data.metadata
  }

  static empty(): ProjectState {
    return new ProjectState({
      projectDir: null,
      imagePath: null,
      parts: {},
      skeleton: null,
      paths: {},
      mechanisms: {},
      metadata: defaultMetadata(),
    })
  }

  static fromDict(raw: Record<string, unknown>, projectDir: string | null): ProjectState {
    const metadata = parseMetadata(raw.metadata)
    const imagePath = toNullableString(raw.image_path)
    const parts = parseParts(raw.parts)
    const skeleton = parseSkeleton(raw.skeleton)
    const paths = parsePaths(raw.paths)
    const mechanisms = parseMechanisms(raw.mechanisms)
    return new ProjectState({
      projectDir,
      imagePath,
      parts,
      skeleton,
      paths,
      mechanisms,
      metadata,
    })
  }

  toDict(): Record<string, unknown> {
    return {
      metadata: serializeMetadata(this.metadata),
      image_path: this.imagePath,
      parts: Object.fromEntries(
        Object.entries(this.parts).map(([key, value]) => [key, serializePart(value)])
      ),
      skeleton: this.skeleton ? serializeSkeleton(this.skeleton) : null,
      paths: Object.fromEntries(
        Object.entries(this.paths).map(([key, value]) => [key, serializePath(value)])
      ),
      mechanisms: Object.fromEntries(
        Object.entries(this.mechanisms).map(([key, value]) => [key, serializeMechanism(value)])
      ),
    }
  }

  withImagePath(imagePath: string | null): ProjectState {
    return new ProjectState({
      ...this,
      imagePath,
      metadata: touchMetadata(this.metadata),
    })
  }

  withParts(parts: Record<string, PartData>): ProjectState {
    return new ProjectState({
      ...this,
      parts,
      metadata: touchMetadata(this.metadata),
    })
  }

  withSkeleton(skeleton: SkeletonData | null): ProjectState {
    return new ProjectState({
      ...this,
      skeleton,
      metadata: touchMetadata(this.metadata),
    })
  }

  withPaths(paths: Record<string, PathData>): ProjectState {
    return new ProjectState({
      ...this,
      paths,
      metadata: touchMetadata(this.metadata),
    })
  }

  withMechanisms(mechanisms: Record<string, MechanismData>): ProjectState {
    return new ProjectState({
      ...this,
      mechanisms,
      metadata: touchMetadata(this.metadata),
    })
  }

  withMetadata(metadata: ProjectMetadata): ProjectState {
    return new ProjectState({
      ...this,
      metadata,
    })
  }

  hasParts(): boolean {
    return Object.keys(this.parts).length > 0
  }

  hasSkeleton(): boolean {
    return this.skeleton !== null
  }

  hasPaths(): boolean {
    return Object.keys(this.paths).length > 0
  }

  hasMechanisms(): boolean {
    return Object.keys(this.mechanisms).length > 0
  }

  getPart(partName: string): PartData | null {
    return this.parts[partName] ?? null
  }
}

const defaultMetadata = (): ProjectMetadata => {
  const now = new Date().toISOString()
  return {
    version: '2.0',
    name: 'Untitled',
    createdAt: now,
    modifiedAt: now,
  }
}

const touchMetadata = (metadata: ProjectMetadata): ProjectMetadata => ({
  ...metadata,
  modifiedAt: new Date().toISOString(),
})

const parseMetadata = (value: unknown): ProjectMetadata => {
  if (!isRecord(value)) {
    return defaultMetadata()
  }
  return {
    version: toString(value.version, '2.0'),
    name: toString(value.name, 'Untitled'),
    createdAt: toString(value.created_at ?? value.createdAt, new Date().toISOString()),
    modifiedAt: toString(value.modified_at ?? value.modifiedAt, new Date().toISOString()),
  }
}

const parseParts = (value: unknown): Record<string, PartData> => {
  if (!isRecord(value)) {
    return {}
  }
  const parts: Record<string, PartData> = {}
  Object.entries(value).forEach(([name, entry]) => {
    parts[name] = parsePart(name, entry)
  })
  return parts
}

const parsePart = (name: string, value: unknown): PartData => {
  if (!isRecord(value)) {
    return {
      name,
      texturePath: null,
      maskPath: null,
      anchorJoint: null,
      pivot: { ...DEFAULT_PIVOT },
      transform: { ...DEFAULT_TRANSFORM },
      zIndex: 0,
    }
  }
  return {
    name: toString(value.name, name),
    texturePath: toNullableString(value.texture_path),
    maskPath: toNullableString(value.mask_path),
    anchorJoint: toNullableString(value.anchor_joint),
    pivot: toPointTuple(value.local_pivot_offset ?? value.pivot, { ...DEFAULT_PIVOT }),
    transform: toTransform(value.transform),
    zIndex: toNumber(value.z_index, 0),
  }
}

const parseSkeleton = (value: unknown): SkeletonData | null => {
  if (!isRecord(value)) {
    return null
  }
  const jointsValue = value.joints
  const bonesValue = value.bones
  const joints: Record<string, JointData> = {}
  if (isRecord(jointsValue)) {
    Object.entries(jointsValue).forEach(([id, jointValue]) => {
      joints[id] = parseJoint(id, jointValue)
    })
  }
  const bones: BoneData[] = Array.isArray(bonesValue)
    ? bonesValue.map((bone) => parseBone(bone)).filter((bone): bone is BoneData => bone !== null)
    : []
  return {
    joints,
    bones,
    rootJoint: toNullableString(value.root_joint),
  }
}

const parseJoint = (id: string, value: unknown): JointData => {
  if (!isRecord(value)) {
    return {
      id,
      position: { x: 0, y: 0 },
      parent: null,
      isLocked: false,
      bendDirection: 'up',
    }
  }
  return {
    id: toString(value.id, id),
    position: toPointTuple(value.position, { x: 0, y: 0 }),
    parent: toNullableString(value.parent),
    isLocked: toBoolean(value.is_locked, false),
    bendDirection: toString(value.bend_direction, 'up'),
  }
}

const parseBone = (value: unknown): BoneData | null => {
  if (!isRecord(value)) {
    return null
  }
  const fromJoint = toNullableString(value.from_joint ?? value.from)
  const toJoint = toNullableString(value.to_joint ?? value.to)
  if (!fromJoint || !toJoint) {
    return null
  }
  return {
    fromJoint,
    toJoint,
  }
}

const parseTimedPoints = (value: unknown): TimedPoint[] | null => {
  if (!Array.isArray(value)) {
    return null
  }
  return value
    .map((entry) => {
      if (Array.isArray(entry) && entry.length >= 3) {
        return {
          x: toNumber(entry[0], 0),
          y: toNumber(entry[1], 0),
          t: toNumber(entry[2], 0),
        }
      }
      if (isRecord(entry)) {
        return {
          x: toNumber(entry.x, 0),
          y: toNumber(entry.y, 0),
          t: toNumber(entry.t, 0),
        }
      }
      return null
    })
    .filter((point): point is TimedPoint => point !== null)
}

const parsePaths = (value: unknown): Record<string, PathData> => {
  if (!isRecord(value)) {
    return {}
  }
  const paths: Record<string, PathData> = {}
  Object.entries(value).forEach(([name, entry]) => {
    paths[name] = parsePath(name, entry)
  })
  return paths
}

const parsePath = (name: string, value: unknown): PathData => {
  if (!isRecord(value)) {
    return {
      partName: name,
      points: [],
      timedPoints: null,
      totalDuration: null,
      isClosed: false,
      enabled: true,
    }
  }
  const pointsValue = Array.isArray(value.points) ? value.points : []
  const points = pointsValue
    .map((entry) => toPointTuple(entry, { x: 0, y: 0 }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
  return {
    partName: toString(value.part_name, name),
    points,
    timedPoints: parseTimedPoints(value.timed_points),
    totalDuration:
      typeof value.total_duration === 'number' && Number.isFinite(value.total_duration)
        ? value.total_duration
        : null,
    isClosed: toBoolean(value.is_closed, false),
    enabled: toBoolean(value.enabled, true),
  }
}

const parseMechanisms = (value: unknown): Record<string, MechanismData> => {
  if (!isRecord(value)) {
    return {}
  }
  const mechanisms: Record<string, MechanismData> = {}
  Object.entries(value).forEach(([key, entry]) => {
    mechanisms[key] = parseMechanism(key, entry)
  })
  return mechanisms
}

const parseMechanism = (id: string, value: unknown): MechanismData => {
  if (!isRecord(value)) {
    return {
      id,
      partName: '',
      type: '',
      params: {},
      enabled: true,
    }
  }
  const params: Record<string, MechanismParam> = {}
  if (isRecord(value.params)) {
    Object.entries(value.params).forEach(([key, entry]) => {
      params[key] = sanitizeMechanismParam(entry)
    })
  }
  return {
    id: toString(value.id, id),
    partName: toString(value.part_name, ''),
    type: toString(value.type, ''),
    params,
    enabled: toBoolean(value.enabled, true),
  }
}

const serializeMetadata = (metadata: ProjectMetadata): Record<string, unknown> => ({
  version: metadata.version,
  name: metadata.name,
  created_at: metadata.createdAt,
  modified_at: metadata.modifiedAt,
})

const serializePart = (part: PartData): Record<string, unknown> => ({
  name: part.name,
  texture_path: part.texturePath,
  mask_path: part.maskPath,
  anchor_joint: part.anchorJoint,
  local_pivot_offset: PointUtils.toTuple(part.pivot),
  transform: part.transform,
  z_index: part.zIndex,
})

const serializeJoint = (joint: JointData): Record<string, unknown> => ({
  id: joint.id,
  position: PointUtils.toTuple(joint.position),
  parent: joint.parent,
  is_locked: joint.isLocked,
  bend_direction: joint.bendDirection,
})

const serializeBone = (bone: BoneData): Record<string, unknown> => ({
  from: bone.fromJoint,
  to: bone.toJoint,
})

const serializeSkeleton = (skeleton: SkeletonData): Record<string, unknown> => ({
  joints: Object.fromEntries(
    Object.entries(skeleton.joints).map(([key, value]) => [key, serializeJoint(value)])
  ),
  bones: skeleton.bones.map((bone) => serializeBone(bone)),
  root_joint: skeleton.rootJoint,
})

const serializePath = (path: PathData): Record<string, unknown> => {
  const output: Record<string, unknown> = {
    part_name: path.partName,
    points: path.points.map((point) => PointUtils.toTuple(point)),
    is_closed: path.isClosed,
    enabled: path.enabled,
  }
  if (path.timedPoints && path.totalDuration !== null) {
    output.timed_points = path.timedPoints.map((point) => [point.x, point.y, point.t])
    output.total_duration = path.totalDuration
  }
  return output
}

const serializeMechanism = (mechanism: MechanismData): Record<string, unknown> => ({
  id: mechanism.id,
  part_name: mechanism.partName,
  type: mechanism.type,
  params: mechanism.params,
  enabled: mechanism.enabled,
})
