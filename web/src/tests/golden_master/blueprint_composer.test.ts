import { describe, expect, it } from 'vitest'

import { composeBlueprint } from '../../application/blueprint'
import { ProjectState } from '../../domain/project'

const buildStateWithMechanism = () => {
  const state = ProjectState.empty()
  return state.withMechanisms({
    m1: {
      id: 'm1',
      partName: 'arm',
      type: 'gear',
      params: { r1_mm: 20, r2_mm: 10 },
      enabled: true,
    },
  })
}

describe('composeBlueprint', () => {
  it('returns empty blueprint when no items', async () => {
    const result = await composeBlueprint(ProjectState.empty())
    expect(result.itemCount).toBe(0)
    expect(result.svg).toContain('No items to export')
  })

  it('includes mechanism svg when mechanisms are present', async () => {
    const result = await composeBlueprint(buildStateWithMechanism())
    expect(result.itemCount).toBe(1)
    expect(result.svg).toContain('Automataii Blueprint')
    expect(result.svg).toContain('Gear Specifications')
  })
})
