import type { PathData } from '../../domain/project'
import type { Point, TimedPoint } from '../../domain/project'

export interface PathParseResult {
  success: boolean
  error: string | null
  paths: Record<string, PathData> | null
}

export const parsePathsJson = (json: string): PathParseResult => {
  let parsed: unknown
  try {
    parsed = JSON.parse(json)
  } catch (error) {
    return { success: false, error: errorMessage(error), paths: null }
  }
  if (!isRecord(parsed)) {
    return { success: false, error: 'Paths JSON must be an object.', paths: null }
  }
  const paths: Record<string, PathData> = {}
  for (const [key, value] of Object.entries(parsed)) {
    if (!isRecord(value)) {
      return { success: false, error: `Path ${key} must be an object.`, paths: null }
    }
    const entry = toPathData(key, value)
    if (!entry.success) {
      return { success: false, error: entry.error, paths: null }
    }
    paths[entry.path.partName] = entry.path
  }
  return { success: true, error: null, paths }
}

const toPathData = (
  key: string,
  value: Record<string, unknown>
): { success: true; path: PathData } | { success: false; error: string } => {
  const partName = typeof value.part_name === 'string'
    ? value.part_name
    : typeof value.partName === 'string'
      ? value.partName
      : key
  const points = parsePoints(value.points)
  if (!points) {
    return { success: false, error: `Path ${partName} points must be an array.` }
  }
  const timedPoints = parseTimedPoints(value.timed_points ?? value.timedPoints)
  const totalDuration =
    typeof value.total_duration === 'number' && Number.isFinite(value.total_duration)
      ? value.total_duration
      : typeof value.totalDuration === 'number' && Number.isFinite(value.totalDuration)
        ? value.totalDuration
        : null
  const isClosed = typeof value.is_closed === 'boolean'
    ? value.is_closed
    : typeof value.isClosed === 'boolean'
      ? value.isClosed
      : false
  const enabled = typeof value.enabled === 'boolean' ? value.enabled : true

  return {
    success: true,
    path: {
      partName,
      points,
      timedPoints,
      totalDuration,
      isClosed,
      enabled,
    },
  }
}

const parsePoints = (value: unknown): Point[] | null => {
  if (!Array.isArray(value)) {
    return null
  }
  return value
    .map((entry) => toPoint(entry))
    .filter((point): point is Point => point !== null)
}

const parseTimedPoints = (value: unknown): TimedPoint[] | null => {
  if (!Array.isArray(value)) {
    return null
  }
  const points = value
    .map((entry) => toTimedPoint(entry))
    .filter((point): point is TimedPoint => point !== null)
  return points.length > 0 ? points : null
}

const toPoint = (entry: unknown): Point | null => {
  if (Array.isArray(entry) && entry.length >= 2) {
    const x = Number(entry[0])
    const y = Number(entry[1])
    if (Number.isFinite(x) && Number.isFinite(y)) {
      return { x, y }
    }
  }
  if (isRecord(entry)) {
    const x = Number(entry.x)
    const y = Number(entry.y)
    if (Number.isFinite(x) && Number.isFinite(y)) {
      return { x, y }
    }
  }
  return null
}

const toTimedPoint = (entry: unknown): TimedPoint | null => {
  if (Array.isArray(entry) && entry.length >= 3) {
    const x = Number(entry[0])
    const y = Number(entry[1])
    const t = Number(entry[2])
    if (Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(t)) {
      return { x, y, t }
    }
  }
  if (isRecord(entry)) {
    const x = Number(entry.x)
    const y = Number(entry.y)
    const t = Number(entry.t)
    if (Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(t)) {
      return { x, y, t }
    }
  }
  return null
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const errorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message
  }
  return 'Invalid JSON'
}
