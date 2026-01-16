import { describe, expect, it } from 'vitest'

import { samplePathsAtProgress } from '../../application/motion_paths'

const buildPath = () => ({
  partName: 'arm',
  points: [
    { x: 0, y: 0 },
    { x: 10, y: 0 },
  ],
  timedPoints: null,
  totalDuration: null,
  isClosed: false,
  enabled: true,
})

describe('samplePathsAtProgress', () => {
  it('samples path positions', () => {
    const samples = samplePathsAtProgress({ arm: buildPath() }, 0.5)
    expect(samples.arm.x).toBe(5)
    expect(samples.arm.y).toBe(0)
  })
})
