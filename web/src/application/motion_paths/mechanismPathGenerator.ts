import type { MechanismData, PathData } from '../../domain/project'
import type { Point } from '../../domain/project'

export interface MechanismPathResult {
  points: Point[]
  error: string | null
}

const DEFAULT_SAMPLES = 360

export const generateMechanismPath = (mechanism: MechanismData): MechanismPathResult => {
  const keyPointsPath = readKeyPointPath(mechanism)
  if (keyPointsPath) {
    return { points: keyPointsPath, error: null }
  }

  const type = normalizeMechanismType(mechanism.type)
  if (type === 'fourbar') {
    return generateFourbarPath(mechanism)
  }
  if (type === 'threebar') {
    return generateThreebarPath(mechanism)
  }
  if (type === 'cam') {
    return generateCamPath(mechanism)
  }
  if (type === 'gear' || type === 'planetary_gear') {
    return generateGearPath(mechanism)
  }
  return { points: [], error: `Unsupported mechanism type: ${mechanism.type}` }
}

export const buildPathData = (
  mechanism: MechanismData,
  points: Point[]
): PathData => ({
  partName: mechanism.partName,
  points,
  timedPoints: null,
  totalDuration: null,
  isClosed: true,
  enabled: true,
})

const generateFourbarPath = (mechanism: MechanismData): MechanismPathResult => {
  const params = mechanism.params ?? {}
  const l1 = toNumber(params.l1, 50)
  const l2 = toNumber(params.l2, 70)
  const l3 = toNumber(params.l3, 60)
  const l4 = toNumber(params.l4, 80)
  const numSamples = toInteger(params.num_samples, DEFAULT_SAMPLES)

  const anchor1 = toPoint(params.anchor1_x, params.anchor1_y, 0, 0)
  const anchor2 = toPoint(params.anchor2_x, params.anchor2_y, anchor1.x + l4, anchor1.y)
  const baseX = toNumber(params.base_x, anchor1.x)
  const baseY = toNumber(params.base_y, anchor1.y)
  const p0 = anchor1.x === 0 && anchor1.y === 0 ? { x: baseX, y: baseY } : anchor1
  const p3 = anchor2

  const points: Point[] = []
  for (let i = 0; i < numSamples; i += 1) {
    const theta = (2 * Math.PI * i) / numSamples
    const p1 = { x: p0.x + l1 * Math.cos(theta), y: p0.y + l1 * Math.sin(theta) }
    const p2 = solveCircleIntersection(p1, l2, p3, l3)
    if (!p2) {
      continue
    }
    points.push(p2)
  }
  if (points.length === 0) {
    return { points, error: 'Non-constructible fourbar configuration.' }
  }
  return { points, error: null }
}

const generateThreebarPath = (mechanism: MechanismData): MechanismPathResult => {
  const params = mechanism.params ?? {}
  const l1 = toNumber(params.l1, 50)
  const l2 = toNumber(params.l2, 70)
  const numSamples = toInteger(params.num_samples, DEFAULT_SAMPLES)
  const baseX = toNumber(params.base_x, 0)
  const baseY = toNumber(params.base_y, 0)
  const couplerAngle = toNumber(params.coupler_angle_rel, -Math.PI / 4)

  const points: Point[] = []
  for (let i = 0; i < numSamples; i += 1) {
    const theta = (2 * Math.PI * i) / numSamples
    const p1 = { x: baseX + l1 * Math.cos(theta), y: baseY + l1 * Math.sin(theta) }
    const p2 = {
      x: p1.x + l2 * Math.cos(theta + couplerAngle),
      y: p1.y + l2 * Math.sin(theta + couplerAngle),
    }
    points.push(p2)
  }
  return { points, error: null }
}

const generateCamPath = (mechanism: MechanismData): MechanismPathResult => {
  const params = mechanism.params ?? {}
  const camCenter = toPoint(params.cam_center_x, params.cam_center_y, 0, 0)
  const followerRadius = toNumber(params.follower_radius, 5)
  const numSamples = toInteger(params.num_samples, DEFAULT_SAMPLES)
  const targetPath = readTargetPath(params)

  if (targetPath.length < 2) {
    return { points: [], error: 'Follower path too short.' }
  }

  const points: Point[] = []
  for (let i = 0; i < numSamples; i += 1) {
    const theta = (2 * Math.PI * i) / numSamples
    const pathIndex = Math.floor((i / numSamples) * targetPath.length) % targetPath.length
    const follower = targetPath[pathIndex]
    const vecX = follower.x - camCenter.x
    const vecY = follower.y - camCenter.y
    const cosTheta = Math.cos(-theta)
    const sinTheta = Math.sin(-theta)
    const pitchX = vecX * cosTheta - vecY * sinTheta
    const pitchY = vecX * sinTheta + vecY * cosTheta
    points.push({ x: pitchX + followerRadius, y: pitchY })
  }
  return { points, error: null }
}

const generateGearPath = (mechanism: MechanismData): MechanismPathResult => {
  const params = mechanism.params ?? {}
  const center = readGearCenter(params)
  const radius =
    toNumber(params.r1_mm, null) ??
    toNumber(params.r_sun_mm, null) ??
    toNumber(params.radius, 30)
  const numSamples = toInteger(params.num_samples, DEFAULT_SAMPLES)

  const points: Point[] = []
  for (let i = 0; i < numSamples; i += 1) {
    const theta = (2 * Math.PI * i) / numSamples
    points.push({
      x: center.x + radius * Math.cos(theta),
      y: center.y + radius * Math.sin(theta),
    })
  }
  return { points, error: null }
}

const solveCircleIntersection = (c1: Point, r1: number, c2: Point, r2: number): Point | null => {
  const dx = c2.x - c1.x
  const dy = c2.y - c1.y
  const dSq = dx * dx + dy * dy
  const d = Math.sqrt(dSq)
  if (d > r1 + r2 || d < Math.abs(r1 - r2) || d === 0) {
    return null
  }
  const a = (dSq - r2 * r2 + r1 * r1) / (2 * d)
  const hSq = r1 * r1 - a * a
  if (hSq < -1e-9) {
    return null
  }
  const h = Math.sqrt(Math.max(0, hSq))
  const midX = c1.x + (a * dx) / d
  const midY = c1.y + (a * dy) / d
  const perpX = -dy / d
  const perpY = dx / d
  return { x: midX + h * perpX, y: midY + h * perpY }
}

const readKeyPointPath = (mechanism: MechanismData): Point[] | null => {
  const params = mechanism.params ?? {}
  const keyPoints = params.key_points
  if (!keyPoints || typeof keyPoints !== 'object') {
    return null
  }
  const path = (keyPoints as Record<string, unknown>).coupler_point_path
  if (!Array.isArray(path)) {
    return null
  }
  const points = path
    .map((entry) =>
      Array.isArray(entry) && entry.length >= 2
        ? { x: Number(entry[0]), y: Number(entry[1]) }
        : null
    )
    .filter((point): point is Point => point !== null && Number.isFinite(point.x) && Number.isFinite(point.y))
  return points.length > 0 ? points : null
}

const readTargetPath = (params: Record<string, unknown>): Point[] => {
  const target = params.target_path
  if (!Array.isArray(target)) {
    return []
  }
  return target
    .map((entry) =>
      Array.isArray(entry) && entry.length >= 2
        ? { x: Number(entry[0]), y: Number(entry[1]) }
        : null
    )
    .filter((point): point is Point => point !== null && Number.isFinite(point.x) && Number.isFinite(point.y))
}

const readGearCenter = (params: Record<string, unknown>): Point => {
  const keyPoints = params.key_points
  if (keyPoints && typeof keyPoints === 'object') {
    const center = (keyPoints as Record<string, unknown>).gear1_center
    if (Array.isArray(center) && center.length >= 2) {
      return { x: Number(center[0]), y: Number(center[1]) }
    }
    const sun = (keyPoints as Record<string, unknown>).sun_center
    if (Array.isArray(sun) && sun.length >= 2) {
      return { x: Number(sun[0]), y: Number(sun[1]) }
    }
  }
  return { x: 0, y: 0 }
}

const normalizeMechanismType = (value: string): string => {
  if (value === 'four_bar' || value === 'fourbar' || value === '4_bar_linkage') {
    return 'fourbar'
  }
  if (value === 'three_bar') {
    return 'threebar'
  }
  if (value === 'cam_follower') {
    return 'cam'
  }
  if (value === 'gear_train' || value === 'simple_gear') {
    return 'gear'
  }
  if (value === 'planetary') {
    return 'planetary_gear'
  }
  return value
}

const toNumber = (value: unknown, fallback: number | null): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : (fallback ?? 0)

const toInteger = (value: unknown, fallback: number): number => {
  const parsed = typeof value === 'number' ? Math.trunc(value) : fallback
  return parsed > 0 ? parsed : fallback
}

const toPoint = (
  xValue: unknown,
  yValue: unknown,
  fallbackX: number,
  fallbackY: number
): Point => ({
  x: typeof xValue === 'number' && Number.isFinite(xValue) ? xValue : fallbackX,
  y: typeof yValue === 'number' && Number.isFinite(yValue) ? yValue : fallbackY,
})
