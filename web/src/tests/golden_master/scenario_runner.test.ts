import { describe, it, expect } from 'vitest'
import { runScenario, runAllScenarios, getScenarioSummary } from '../../application/scenarios/scenarioRunner'
import { ProjectState } from '../../domain/project'

describe('scenarioRunner golden master', () => {
  const createMinimalState = (): ProjectState => {
    return ProjectState.empty()
  }

  it('runs blueprint scenario successfully', async () => {
    const state = createMinimalState()
    const result = await runScenario('blueprint', state)

    expect(result.success).toBe(true)
    expect(result.scenarioName).toBe('blueprint')
    expect(result.artifacts).toBeDefined()
    expect(result.durationMs).toBeGreaterThanOrEqual(0)
  })

  it('skips image_processing scenario (requires inference state)', async () => {
    const state = createMinimalState()
    const result = await runScenario('image_processing', state)

    expect(result.scenarioName).toBe('image_processing')
    expect(result.skipped).toBe(true)
    expect(result.durationMs).toBeGreaterThanOrEqual(0)
  })

  it('runs blueprint scenario via runAllScenarios', async () => {
    const state = createMinimalState()
    const results = await runAllScenarios(state)

    expect(results).toHaveLength(1)
    expect(results[0].success).toBe(true)
    
    const summary = getScenarioSummary(results)
    expect(summary.passed).toBe(1)
    expect(summary.failed).toBe(0)
    expect(summary.totalMs).toBeGreaterThanOrEqual(0)
  })

  it('returns error for unknown scenario', async () => {
    const state = createMinimalState()
    const result = await runScenario('unknown' as never, state)

    expect(result.success).toBe(false)
    expect(result.error).toContain('Unknown scenario')
  })
})
