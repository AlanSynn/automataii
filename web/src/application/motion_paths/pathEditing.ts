import type { PathData, Point, TimedPoint } from '../../domain/project'

export interface PathEditConfig {
  partName: string
  isClosed: boolean
  smoothness: number
  timed: boolean
  totalDuration: number
  enabled?: boolean
}

const isFinitePoint = (point: Point): boolean =>
  Number.isFinite(point.x) && Number.isFinite(point.y)

export const sanitizePoints = (points: Point[]): Point[] =>
  points.filter((point) => isFinitePoint(point))

const clampSmoothness = (value: number): number =>
  Math.min(100, Math.max(0, Number.isFinite(value) ? value : 0))

const clampDuration = (value: number): number =>
  Number.isFinite(value) && value > 0 ? value : 0

export const buildTimedPoints = (points: Point[], totalDuration: number): TimedPoint[] | null => {
  const safeDuration = clampDuration(totalDuration)
  if (safeDuration <= 0 || points.length < 2) {
    return null
  }
  const distances = points.map((point, index) => {
    if (index === 0) {
      return 0
    }
    const prev = points[index - 1]
    const dx = point.x - prev.x
    const dy = point.y - prev.y
    return Math.sqrt(dx * dx + dy * dy)
  })
  const totalLength = distances.reduce((sum, value) => sum + value, 0)
  if (totalLength <= 0) {
    return points.map((point, index) => ({
      x: point.x,
      y: point.y,
      t: (safeDuration * index) / (points.length - 1),
    }))
  }
  let accumulated = 0
  return points.map((point, index) => {
    if (index > 0) {
      accumulated += distances[index]
    }
    return {
      x: point.x,
      y: point.y,
      t: (safeDuration * accumulated) / totalLength,
    }
  })
}

const getPoint = (points: Point[], index: number, isClosed: boolean): Point => {
  if (isClosed) {
    const wrapped = ((index % points.length) + points.length) % points.length
    return points[wrapped]
  }
  const clamped = Math.min(points.length - 1, Math.max(0, index))
  return points[clamped]
}

const catmullRomPoint = (
  p0: Point,
  p1: Point,
  p2: Point,
  p3: Point,
  t: number,
  tension: number
): Point => {
  const t2 = t * t
  const t3 = t2 * t
  const scale = 1 - tension
  const m1x = (p2.x - p0.x) * 0.5 * scale
  const m1y = (p2.y - p0.y) * 0.5 * scale
  const m2x = (p3.x - p1.x) * 0.5 * scale
  const m2y = (p3.y - p1.y) * 0.5 * scale

  const a = 2 * t3 - 3 * t2 + 1
  const b = t3 - 2 * t2 + t
  const c = -2 * t3 + 3 * t2
  const d = t3 - t2

  return {
    x: a * p1.x + b * m1x + c * p2.x + d * m2x,
    y: a * p1.y + b * m1y + c * p2.y + d * m2y,
  }
}

export const smoothPathPoints = (
  points: Point[],
  isClosed: boolean,
  smoothness: number
): Point[] => {
  if (points.length < 3) {
    return points
  }
  const safeSmoothness = clampSmoothness(smoothness)
  if (safeSmoothness === 0) {
    return points
  }
  const tension = 0.2 + (safeSmoothness / 100) * 0.6
  const samplesPerSegment = Math.max(4, Math.round(6 + (safeSmoothness / 100) * 10))
  const lastIndex = points.length - 1
  const segmentCount = isClosed ? points.length : lastIndex
  const smoothed: Point[] = []

  for (let index = 0; index < segmentCount; index += 1) {
    const p0 = getPoint(points, index - 1, isClosed)
    const p1 = getPoint(points, index, isClosed)
    const p2 = getPoint(points, index + 1, isClosed)
    const p3 = getPoint(points, index + 2, isClosed)
    for (let sample = 0; sample < samplesPerSegment; sample += 1) {
      const t = sample / samplesPerSegment
      smoothed.push(catmullRomPoint(p0, p1, p2, p3, t, tension))
    }
  }

  if (!isClosed) {
    smoothed.push(points[lastIndex])
  }
  return sanitizePoints(smoothed)
}

export const buildPathDataFromPoints = (
  points: Point[],
  config: PathEditConfig
): PathData => {
  const sanitized = sanitizePoints(points)
  const smoothed = smoothPathPoints(sanitized, config.isClosed, config.smoothness)
  const timedPoints = config.timed
    ? buildTimedPoints(smoothed, config.totalDuration)
    : null

  return {
    partName: config.partName,
    points: smoothed,
    timedPoints,
    totalDuration: timedPoints ? clampDuration(config.totalDuration) : null,
    isClosed: config.isClosed,
    enabled: config.enabled ?? true,
  }
}
