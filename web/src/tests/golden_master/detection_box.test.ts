import { describe, expect, it } from 'vitest'

import { selectDetectionBox } from '../../application/onnx/detection'
import type { DetectionTransform } from '../../application/onnx/imagePreprocess'
import type { SerializedTensor } from '../../infra/onnx/onnxRuntime'

const transform: DetectionTransform = {
  scale: 0.5,
  resized: { width: 500, height: 400 },
  padded: { width: 512, height: 416 },
  original: { width: 1000, height: 800 },
}

describe('selectDetectionBox', () => {
  it('chooses highest score box and maps to original space', () => {
    const boxes: SerializedTensor = {
      name: 'boxes',
      type: 'float32',
      dims: [1, 2, 4],
      data: [0.1, 0.2, 0.3, 0.4, 0.5, 0.5, 0.9, 0.9],
    }
    const scores: SerializedTensor = {
      name: 'scores',
      type: 'float32',
      dims: [1, 2],
      data: [0.2, 0.9],
    }
    const result = selectDetectionBox({ boxes, scores }, transform)
    expect(result).not.toBeNull()
    if (!result) {
      return
    }
    expect(result.x1).toBeCloseTo(512)
    expect(result.y1).toBeCloseTo(416)
    expect(result.x2).toBeCloseTo(921.6)
    expect(result.y2).toBeCloseTo(748.8)
  })

  it('falls back to detection tensor format', () => {
    const detections: SerializedTensor = {
      name: 'detections',
      type: 'float32',
      dims: [1, 1, 6],
      data: [10, 20, 110, 120, 0.8, 1],
    }
    const result = selectDetectionBox(
      { detections },
      {
        scale: 1,
        resized: { width: 200, height: 200 },
        padded: { width: 200, height: 200 },
        original: { width: 200, height: 200 },
      }
    )
    expect(result).toEqual({ x1: 10, y1: 20, x2: 110, y2: 120 })
  })
})
