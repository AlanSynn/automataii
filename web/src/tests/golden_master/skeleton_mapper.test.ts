import { describe, expect, it } from 'vitest'

import { buildProjectSkeleton } from '../../application/onnx/skeletonMapper'

const buildSample = () => [
  {
    name: 'root',
    parent: null,
    locOriginal: [10, 20] as [number, number],
    loc: [10, 20] as [number, number],
  },
  {
    name: 'child',
    parent: 'root',
    locOriginal: [30, 40] as [number, number],
    loc: [30, 40] as [number, number],
  },
]

describe('buildProjectSkeleton', () => {
  it('maps joints and bones', () => {
    const skeleton = buildProjectSkeleton(buildSample())
    expect(skeleton).not.toBeNull()
    if (!skeleton) {
      return
    }
    expect(Object.keys(skeleton.joints)).toEqual(['root', 'child'])
    expect(skeleton.rootJoint).toBe('root')
    expect(skeleton.bones).toEqual([{ fromJoint: 'root', toJoint: 'child' }])
    expect(skeleton.joints.root.position).toEqual({ x: 10, y: 20 })
  })

  it('returns null for empty input', () => {
    expect(buildProjectSkeleton([])).toBeNull()
  })
})
