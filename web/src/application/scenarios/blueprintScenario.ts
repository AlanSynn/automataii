import type { MechanismData, ProjectState } from '../../domain/project'
import { composeBlueprint } from '../blueprint/composeBlueprint'
import { downloadTextFile } from './downloads'

export interface BlueprintScenarioLayout {
  width_mm: number
  height_mm: number
  item_count: number
}

export interface BlueprintScenarioMechanism {
  mechanism_type: string
  display_name: string
  parameter_keys: string[]
}

export interface BlueprintScenarioAutomation {
  controller_mechanisms: Array<{ id: string; type: string }>
  parameter_specs: Record<string, unknown>
}

export interface BlueprintScenarioManifest {
  generated_at: string
  unit_system: 'metric' | 'imperial'
  layout: BlueprintScenarioLayout
  mechanism: BlueprintScenarioMechanism | null
  automation: BlueprintScenarioAutomation
}

export interface BlueprintScenarioMetrics {
  duration_ms: number
  unit_system: 'metric' | 'imperial'
  mechanism_type: string | null
  artifact_svg: string
  manifest: string
  timestamp: string
}

export interface BlueprintScenarioArtifacts {
  svg: string
  manifest: BlueprintScenarioManifest
  metrics: BlueprintScenarioMetrics
}

const resolvePrimaryMechanism = (
  mechanisms: Record<string, MechanismData>
): MechanismData | null => {
  const entries = Object.values(mechanisms)
  if (entries.length === 0) {
    return null
  }
  const enabled = entries.find((entry) => entry.enabled)
  return enabled ?? entries[0]
}

const buildAutomation = (mechanisms: Record<string, MechanismData>): BlueprintScenarioAutomation => {
  const controller_mechanisms = Object.values(mechanisms).map((mechanism) => ({
    id: mechanism.id,
    type: mechanism.type,
  }))

  const parameter_specs = Object.values(mechanisms).reduce<Record<string, unknown>>(
    (acc, mechanism) => {
      acc[mechanism.id] = mechanism.params
      return acc
    },
    {}
  )

  return { controller_mechanisms, parameter_specs }
}

export const buildBlueprintScenarioArtifacts = async (
  state: ProjectState,
  unitSystem: 'metric' | 'imperial' = 'metric'
): Promise<BlueprintScenarioArtifacts> => {
  const startedAt = performance.now()
  const composition = await composeBlueprint(state, { unitSystem })
  const generatedAt = new Date().toISOString()

  const primaryMechanism = resolvePrimaryMechanism(state.mechanisms)
  const mechanismInfo = primaryMechanism
    ? {
        mechanism_type: primaryMechanism.type,
        display_name: primaryMechanism.id,
        parameter_keys: Object.keys(primaryMechanism.params ?? {}),
      }
    : null

  const manifest: BlueprintScenarioManifest = {
    generated_at: generatedAt,
    unit_system: unitSystem,
    layout: {
      width_mm: composition.width,
      height_mm: composition.height,
      item_count: composition.itemCount,
    },
    mechanism: mechanismInfo,
    automation: buildAutomation(state.mechanisms),
  }

  const metrics: BlueprintScenarioMetrics = {
    duration_ms: Math.round(performance.now() - startedAt),
    unit_system: unitSystem,
    mechanism_type: primaryMechanism?.type ?? null,
    artifact_svg: 'foundry_blueprint.svg',
    manifest: 'foundry_blueprint_manifest.json',
    timestamp: generatedAt,
  }

  return {
    svg: composition.svg,
    manifest,
    metrics,
  }
}

export const downloadBlueprintScenarioArtifacts = (
  artifacts: BlueprintScenarioArtifacts,
  baseName = 'foundry_blueprint'
): void => {
  downloadTextFile(`${baseName}.svg`, artifacts.svg, 'image/svg+xml')
  downloadTextFile(
    `${baseName}_manifest.json`,
    JSON.stringify(artifacts.manifest, null, 2),
    'application/json'
  )
  downloadTextFile(
    `${baseName}_metrics.json`,
    JSON.stringify(artifacts.metrics, null, 2),
    'application/json'
  )
}
