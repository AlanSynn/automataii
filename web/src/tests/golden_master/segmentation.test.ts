import { describe, expect, it } from 'vitest'

import { segmentImage } from '../../application/onnx/segmentation'

const buildImageData = (): ImageData => {
  const data = new Uint8ClampedArray([
    255, 255, 255, 0,
    255, 255, 255, 0,
    255, 255, 255, 255,
    255, 255, 255, 0,
  ])
  return { data, width: 2, height: 2 } as ImageData
}

describe('segmentImage', () => {
  it('returns a binary mask', () => {
    const image = buildImageData()
    const mask = segmentImage(image)
    expect(mask.width).toBe(2)
    expect(mask.height).toBe(2)
    expect(mask.data.length).toBe(4)
    expect(mask.data.some((value) => value === 255)).toBe(true)
    expect(mask.data.every((value) => value === 0 || value === 255)).toBe(true)
  })
})
