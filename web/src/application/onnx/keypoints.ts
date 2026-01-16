import type { SerializedTensor } from '../../infra/onnx/onnxRuntime'

export interface BoundingBox {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface Keypoint {
  x: number
  y: number
  score: number
}

export interface SkeletonJoint {
  name: string
  parent: string | null
  loc: [number, number]
  locOriginal: [number, number]
}

export const buildFullImageBox = (width: number, height: number): BoundingBox => ({
  x1: 0,
  y1: 0,
  x2: width,
  y2: height,
})

export const applyMargin = (
  box: BoundingBox,
  width: number,
  height: number,
  margin = 0.2
): BoundingBox => {
  const left = Math.max(0, box.x1 - Math.trunc(margin * box.x1))
  const top = Math.max(0, box.y1 - Math.trunc(margin * box.y1))
  const right = Math.min(width, box.x2 + Math.trunc(margin * box.x2))
  const bottom = Math.min(height, box.y2 + Math.trunc(margin * box.y2))
  return { x1: left, y1: top, x2: right, y2: bottom }
}

export const extractKeypointsFromHeatmap = (
  heatmap: SerializedTensor,
  bbox: BoundingBox
): Keypoint[] => {
  const dims = heatmap.dims
  if (dims.length < 3) {
    return []
  }
  const channelsIndex = dims.length === 4 ? 1 : 0
  const heightIndex = dims.length === 4 ? 2 : 1
  const widthIndex = dims.length === 4 ? 3 : 2
  const jointCount = dims[channelsIndex]
  const heatmapHeight = dims[heightIndex]
  const heatmapWidth = dims[widthIndex]

  if (!jointCount || !heatmapHeight || !heatmapWidth) {
    return []
  }

  const data = heatmap.data.map((value) => Number(value))
  const planeSize = heatmapHeight * heatmapWidth

  const keypoints: Keypoint[] = []
  const boxWidth = bbox.x2 - bbox.x1
  const boxHeight = bbox.y2 - bbox.y1

  for (let joint = 0; joint < jointCount; joint += 1) {
    const base = joint * planeSize
    let maxVal = -Infinity
    let maxIndex = 0
    for (let idx = 0; idx < planeSize; idx += 1) {
      const value = data[base + idx]
      if (value > maxVal) {
        maxVal = value
        maxIndex = idx
      }
    }
    const yHeat = Math.floor(maxIndex / heatmapWidth)
    const xHeat = maxIndex - yHeat * heatmapWidth
    const xBox = (xHeat / heatmapWidth) * boxWidth
    const yBox = (yHeat / heatmapHeight) * boxHeight
    keypoints.push({
      x: bbox.x1 + xBox,
      y: bbox.y1 + yBox,
      score: maxVal,
    })
  }

  return keypoints
}

export const createSkeletonConfig = (
  keypoints: Keypoint[],
  bbox: BoundingBox
): SkeletonJoint[] => {
  if (keypoints.length < 17) {
    return []
  }
  const kpts = keypoints.map((point) => [point.x, point.y] as [number, number])

  const skeleton: { loc: [number, number]; name: string; parent: string | null }[] = []
  skeleton.push({
    loc: midpoint(kpts[11], kpts[12]),
    name: 'root',
    parent: null,
  })
  skeleton.push({
    loc: midpoint(kpts[11], kpts[12]),
    name: 'hip',
    parent: 'root',
  })
  skeleton.push({
    loc: midpoint(kpts[5], kpts[6]),
    name: 'torso',
    parent: 'hip',
  })
  skeleton.push({
    loc: toPoint(kpts[0]),
    name: 'neck',
    parent: 'torso',
  })
  skeleton.push({
    loc: toPoint(kpts[6]),
    name: 'right_shoulder',
    parent: 'torso',
  })
  skeleton.push({
    loc: toPoint(kpts[8]),
    name: 'right_elbow',
    parent: 'right_shoulder',
  })
  skeleton.push({
    loc: toPoint(kpts[10]),
    name: 'right_hand',
    parent: 'right_elbow',
  })
  skeleton.push({
    loc: toPoint(kpts[5]),
    name: 'left_shoulder',
    parent: 'torso',
  })
  skeleton.push({
    loc: toPoint(kpts[7]),
    name: 'left_elbow',
    parent: 'left_shoulder',
  })
  skeleton.push({
    loc: toPoint(kpts[9]),
    name: 'left_hand',
    parent: 'left_elbow',
  })
  skeleton.push({
    loc: toPoint(kpts[12]),
    name: 'right_hip',
    parent: 'root',
  })
  skeleton.push({
    loc: toPoint(kpts[14]),
    name: 'right_knee',
    parent: 'right_hip',
  })
  skeleton.push({
    loc: toPoint(kpts[16]),
    name: 'right_foot',
    parent: 'right_knee',
  })
  skeleton.push({
    loc: toPoint(kpts[11]),
    name: 'left_hip',
    parent: 'root',
  })
  skeleton.push({
    loc: toPoint(kpts[13]),
    name: 'left_knee',
    parent: 'left_hip',
  })
  skeleton.push({
    loc: toPoint(kpts[15]),
    name: 'left_foot',
    parent: 'left_knee',
  })

  return skeleton.map((joint) => ({
    name: joint.name,
    parent: joint.parent,
    locOriginal: joint.loc,
    loc: [joint.loc[0] - bbox.x1, joint.loc[1] - bbox.y1],
  }))
}

const midpoint = (a: [number, number], b: [number, number]): [number, number] =>
  toPoint([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2])

const toPoint = (value: [number, number]): [number, number] => [
  Math.trunc(value[0]),
  Math.trunc(value[1]),
]
