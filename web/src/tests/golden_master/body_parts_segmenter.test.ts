import { describe, expect, it } from 'vitest'

import { buildBodyPartsFromSkeleton } from '../../application/onnx/bodyPartsSegmenter'

const buildImageBundle = () => {
  const data = new Uint8ClampedArray([
    0, 0, 0, 0,
    0, 0, 0, 255,
    0, 0, 0, 255,
    0, 0, 0, 0,
  ])
  const image = { data, width: 2, height: 2 } as ImageData
  return { data: image, width: 2, height: 2 }
}

describe('buildBodyPartsFromSkeleton', () => {
  it('returns empty parts when skeleton is missing', () => {
    const result = buildBodyPartsFromSkeleton(buildImageBundle(), null)
    expect(Object.keys(result.parts)).toEqual([])
    expect(result.mask.width).toBe(2)
    expect(result.mask.height).toBe(2)
  })
})
