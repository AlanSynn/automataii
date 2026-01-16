import { describe, expect, it } from 'vitest'

import { generateMechanismPath } from '../../application/motion_paths'

const buildMechanism = () => ({
  id: 'm1',
  partName: 'arm',
  type: '4_bar_linkage',
  params: { l1: 40, l2: 40, l3: 40, l4: 40, num_samples: 36 },
  enabled: true,
})

describe('generateMechanismPath', () => {
  it('generates a fourbar path', () => {
    const result = generateMechanismPath(buildMechanism())
    expect(result.error).toBeNull()
    expect(result.points.length).toBeGreaterThan(0)
    result.points.forEach((point) => {
      expect(Number.isFinite(point.x)).toBe(true)
      expect(Number.isFinite(point.y)).toBe(true)
    })
  })

  it('prefers keypoint paths when provided', () => {
    const mechanism = {
      ...buildMechanism(),
      params: {
        ...buildMechanism().params,
        key_points: {
          coupler_point_path: [
            [1, 2],
            [3, 4],
            [5, 6],
          ],
        },
      },
    }
    const result = generateMechanismPath(mechanism)
    expect(result.error).toBeNull()
    expect(result.points).toEqual([
      { x: 1, y: 2 },
      { x: 3, y: 4 },
      { x: 5, y: 6 },
    ])
  })
})
