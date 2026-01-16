import { describe, expect, it } from 'vitest'

import { buildBlueprintScenarioArtifacts } from '../../application/scenarios'
import { ProjectState, type MechanismData } from '../../domain/project'

const buildMechanism = (): MechanismData => ({
  id: 'mechanism-1',
  type: 'fourbar',
  partName: 'arm',
  params: {
    l1: 10,
    l2: 20,
    l3: 15,
    l4: 12,
    base_x: 0,
    base_y: 0,
    num_samples: 20,
  },
  enabled: true,
})

describe('blueprint scenario artifacts', () => {
  it('builds manifest and metrics with mechanism info', async () => {
    const state = ProjectState.empty().withMechanisms({
      'mechanism-1': buildMechanism(),
    })

    const artifacts = await buildBlueprintScenarioArtifacts(state)
    expect(artifacts.svg).toContain('<svg')
    expect(artifacts.manifest.mechanism?.mechanism_type).toBe('fourbar')
    expect(artifacts.metrics.artifact_svg).toBe('foundry_blueprint.svg')
    expect(artifacts.manifest.layout.item_count).toBeGreaterThanOrEqual(0)
  })
})
