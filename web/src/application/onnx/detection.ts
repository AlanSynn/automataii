import type { SerializedTensor } from '../../infra/onnx/onnxRuntime'
import type { BoundingBox, DetectionTransform } from './imagePreprocess'

interface DetectionCandidate {
  box: BoundingBox
  score: number
}

const SCORE_THRESHOLD = 0.2

const toNumber = (value: unknown): number =>
  typeof value === 'number' ? value : Number(value)

const toNumberArray = (data: Array<number | string | bigint>): number[] =>
  data.map((value) => toNumber(value))

const isFiniteBox = (box: BoundingBox): boolean =>
  Number.isFinite(box.x1) &&
  Number.isFinite(box.y1) &&
  Number.isFinite(box.x2) &&
  Number.isFinite(box.y2)

const normalizeBoxIfNeeded = (box: BoundingBox): BoundingBox => {
  if (box.x2 >= box.x1 && box.y2 >= box.y1) {
    return box
  }
  const width = box.x2
  const height = box.y2
  if (width <= 0 || height <= 0) {
    return box
  }
  return {
    x1: box.x1 - width / 2,
    y1: box.y1 - height / 2,
    x2: box.x1 + width / 2,
    y2: box.y1 + height / 2,
  }
}

const mapBoxToOriginal = (
  box: BoundingBox,
  transform: DetectionTransform,
  normalized: boolean
): BoundingBox => {
  const inputWidth = transform.padded.width
  const inputHeight = transform.padded.height
  const scaleX = normalized ? inputWidth : 1
  const scaleY = normalized ? inputHeight : 1

  const rawX1 = box.x1 * scaleX
  const rawY1 = box.y1 * scaleY
  const rawX2 = box.x2 * scaleX
  const rawY2 = box.y2 * scaleY

  const clamp = (value: number, maxValue: number): number =>
    Math.min(Math.max(value, 0), maxValue)

  const resizedX1 = clamp(rawX1, transform.resized.width)
  const resizedY1 = clamp(rawY1, transform.resized.height)
  const resizedX2 = clamp(rawX2, transform.resized.width)
  const resizedY2 = clamp(rawY2, transform.resized.height)

  const originalX1 = resizedX1 / transform.scale
  const originalY1 = resizedY1 / transform.scale
  const originalX2 = resizedX2 / transform.scale
  const originalY2 = resizedY2 / transform.scale

  return {
    x1: clamp(originalX1, transform.original.width),
    y1: clamp(originalY1, transform.original.height),
    x2: clamp(originalX2, transform.original.width),
    y2: clamp(originalY2, transform.original.height),
  }
}

const buildCandidatesFromTensors = (
  boxes: SerializedTensor | null,
  scores: SerializedTensor | null,
  transform: DetectionTransform
): DetectionCandidate[] => {
  if (!boxes) {
    return []
  }
  const data = toNumberArray(boxes.data as Array<number | string | bigint>)
  const boxCount = Math.floor(data.length / 4)
  if (boxCount === 0) {
    return []
  }
  const scoreData = scores
    ? toNumberArray(scores.data as Array<number | string | bigint>)
    : null
  const maxCoord = data.reduce((max, value) => Math.max(max, value), 0)
  const minCoord = data.reduce((min, value) => Math.min(min, value), 0)
  const normalized = maxCoord <= 1.5 && minCoord >= -0.5

  const candidates: DetectionCandidate[] = []
  for (let index = 0; index < boxCount; index += 1) {
    const offset = index * 4
    const raw = normalizeBoxIfNeeded({
      x1: data[offset],
      y1: data[offset + 1],
      x2: data[offset + 2],
      y2: data[offset + 3],
    })
    if (!isFiniteBox(raw)) {
      continue
    }
    const box = mapBoxToOriginal(raw, transform, normalized)
    const score = scoreData && scoreData[index] !== undefined ? scoreData[index] : 1
    candidates.push({ box, score })
  }
  return candidates
}

const buildCandidatesFromDetections = (
  tensor: SerializedTensor,
  transform: DetectionTransform
): DetectionCandidate[] => {
  const data = toNumberArray(tensor.data as Array<number | string | bigint>)
  const stride = tensor.dims[tensor.dims.length - 1] ?? 0
  if (stride < 6) {
    return []
  }
  const count = Math.floor(data.length / stride)
  if (count === 0) {
    return []
  }
  const maxCoord = data.reduce((max, value) => Math.max(max, value), 0)
  const minCoord = data.reduce((min, value) => Math.min(min, value), 0)
  const normalized = maxCoord <= 1.5 && minCoord >= -0.5

  const candidates: DetectionCandidate[] = []
  for (let index = 0; index < count; index += 1) {
    const offset = index * stride
    const raw = normalizeBoxIfNeeded({
      x1: data[offset],
      y1: data[offset + 1],
      x2: data[offset + 2],
      y2: data[offset + 3],
    })
    if (!isFiniteBox(raw)) {
      continue
    }
    const score = data[offset + 4] ?? 1
    candidates.push({ box: mapBoxToOriginal(raw, transform, normalized), score })
  }
  return candidates
}

const findOutput = (
  outputs: Record<string, SerializedTensor>,
  matcher: (name: string) => boolean
): SerializedTensor | null => {
  const entry = Object.entries(outputs).find(([name]) => matcher(name))
  return entry ? entry[1] : null
}

const findBoxTensor = (outputs: Record<string, SerializedTensor>): SerializedTensor | null =>
  findOutput(outputs, (name) => name.toLowerCase().includes('box'))

const findScoreTensor = (outputs: Record<string, SerializedTensor>): SerializedTensor | null =>
  findOutput(outputs, (name) => name.toLowerCase().includes('score'))

const findDetectionTensor = (outputs: Record<string, SerializedTensor>): SerializedTensor | null =>
  findOutput(outputs, (name) => {
    const lower = name.toLowerCase()
    return lower.includes('detection') || lower.includes('output')
  })

const pickBestCandidate = (candidates: DetectionCandidate[]): DetectionCandidate | null => {
  const filtered = candidates.filter((candidate) => candidate.score >= SCORE_THRESHOLD)
  const usable = filtered.length > 0 ? filtered : candidates
  if (usable.length === 0) {
    return null
  }
  return usable.reduce((best, candidate) => (candidate.score > best.score ? candidate : best), usable[0])
}

export const selectDetectionBox = (
  outputs: Record<string, SerializedTensor> | null,
  transform: DetectionTransform
): BoundingBox | null => {
  if (!outputs) {
    return null
  }
  const boxTensor = findBoxTensor(outputs)
  const scoreTensor = findScoreTensor(outputs)
  const detectionTensor = findDetectionTensor(outputs)

  let candidates: DetectionCandidate[] = []
  if (boxTensor) {
    candidates = buildCandidatesFromTensors(boxTensor, scoreTensor, transform)
  }
  if (candidates.length === 0 && detectionTensor) {
    candidates = buildCandidatesFromDetections(detectionTensor, transform)
  }
  const best = pickBestCandidate(candidates)
  if (!best || !isFiniteBox(best.box)) {
    return null
  }
  if (best.box.x2 <= best.box.x1 || best.box.y2 <= best.box.y1) {
    return null
  }
  return best.box
}
