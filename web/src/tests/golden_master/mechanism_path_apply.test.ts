import { describe, expect, it } from 'vitest'

import { applyMechanismPaths } from '../../application/motion_paths'
import { ProjectState } from '../../domain/project'

describe('applyMechanismPaths', () => {
  it('adds paths for enabled mechanisms', () => {
    const state = ProjectState.empty().withMechanisms({
      m1: { id: 'm1', partName: 'arm', type: '4_bar_linkage', params: { l1: 30, l2: 40, l3: 40, l4: 50, num_samples: 10 }, enabled: true },
    })
    const result = applyMechanismPaths(state)
    expect(result.state.paths.arm.points.length).toBe(10)
    expect(result.updates[0].success).toBe(true)
  })
})
