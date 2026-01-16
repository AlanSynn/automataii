import type { BoneData, PathData, Point, SkeletonData } from './project'

export interface LineSegment {
  start: Point
  end: Point
}

export interface Bounds {
  minX: number
  minY: number
  maxX: number
  maxY: number
}

export const buildSkeletonSegments = (skeleton: SkeletonData | null): LineSegment[] => {
  if (!skeleton) {
    return []
  }
  return skeleton.bones
    .map((bone) => toBoneSegment(bone, skeleton))
    .filter((segment): segment is LineSegment => segment !== null)
}

export const buildPathSegments = (paths: Record<string, PathData>): LineSegment[] => {
  const segments: LineSegment[] = []
  Object.values(paths).forEach((path) => {
    segments.push(...pathToSegments(path))
  })
  return segments
}

export const computeBounds = (points: Point[]): Bounds | null => {
  if (points.length === 0) {
    return null
  }
  let minX = points[0].x
  let maxX = points[0].x
  let minY = points[0].y
  let maxY = points[0].y
  points.forEach((point) => {
    minX = Math.min(minX, point.x)
    maxX = Math.max(maxX, point.x)
    minY = Math.min(minY, point.y)
    maxY = Math.max(maxY, point.y)
  })
  return { minX, minY, maxX, maxY }
}

export const collectPoints = (segments: LineSegment[]): Point[] =>
  segments.flatMap((segment) => [segment.start, segment.end])

const toBoneSegment = (bone: BoneData, skeleton: SkeletonData): LineSegment | null => {
  const start = skeleton.joints[bone.fromJoint]?.position
  const end = skeleton.joints[bone.toJoint]?.position
  if (!start || !end) {
    return null
  }
  return { start, end }
}

const pathToSegments = (path: PathData): LineSegment[] => {
  if (!path.enabled || path.points.length < 2) {
    return []
  }
  const segments: LineSegment[] = []
  for (let index = 0; index < path.points.length - 1; index += 1) {
    segments.push({
      start: path.points[index],
      end: path.points[index + 1],
    })
  }
  if (path.isClosed) {
    segments.push({
      start: path.points[path.points.length - 1],
      end: path.points[0],
    })
  }
  return segments
}
