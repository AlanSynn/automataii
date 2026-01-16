import {
  buildBlueprintScenarioArtifacts,
  downloadBlueprintScenarioArtifacts,
  type BlueprintScenarioArtifacts,
} from './blueprintScenario'
import { type ProjectState } from '../../domain/project'

export type ScenarioName = 'blueprint' | 'image_processing'

export interface ScenarioRunResult<T> {
  success: boolean
  scenarioName: ScenarioName
  artifacts?: T
  error?: string
  durationMs: number
  skipped?: boolean
}

export interface ScenarioRunnerConfig {
  autoDownload?: boolean
}

export async function runScenario(
  scenarioName: ScenarioName,
  state: ProjectState,
  config: ScenarioRunnerConfig = {}
): Promise<ScenarioRunResult<BlueprintScenarioArtifacts>> {
  const startTime = performance.now()

  try {
    switch (scenarioName) {
      case 'blueprint': {
        const artifacts = await buildBlueprintScenarioArtifacts(state)
        if (config.autoDownload) {
          downloadBlueprintScenarioArtifacts(artifacts)
        }
        return {
          success: true,
          scenarioName,
          artifacts,
          durationMs: performance.now() - startTime,
        }
      }

      case 'image_processing':

        return {
          success: true,
          scenarioName,
          durationMs: performance.now() - startTime,
          skipped: true,
          error: 'image_processing requires ImageInferenceState, use buildImageProcessingScenarioArtifacts directly',
        }

      default:
        throw new Error(`Unknown scenario: ${scenarioName}`)
    }
  } catch (error) {
    return {
      success: false,
      scenarioName,
      error: error instanceof Error ? error.message : String(error),
      durationMs: performance.now() - startTime,
    }
  }
}

export async function runAllScenarios(
  state: ProjectState,
  config: ScenarioRunnerConfig = {}
): Promise<ScenarioRunResult<unknown>[]> {
  const scenarios: ScenarioName[] = ['blueprint']
  const results: ScenarioRunResult<unknown>[] = []

  for (const scenario of scenarios) {
    const result = await runScenario(scenario, state, config)
    results.push(result)
  }

  return results
}

export function getScenarioSummary(
  results: ScenarioRunResult<unknown>[]
): { passed: number; failed: number; skipped: number; totalMs: number } {
  return results.reduce(
    (acc, r) => ({
      passed: acc.passed + (r.success && !r.skipped ? 1 : 0),
      failed: acc.failed + (r.success ? 0 : 1),
      skipped: acc.skipped + (r.skipped ? 1 : 0),
      totalMs: acc.totalMs + r.durationMs,
    }),
    { passed: 0, failed: 0, skipped: 0, totalMs: 0 }
  )
}
