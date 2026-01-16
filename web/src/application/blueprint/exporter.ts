import type { ProjectState } from '../../domain/project'
import { composeBlueprint } from './composeBlueprint'

export interface BlueprintExportResult {
  success: boolean
  error: string | null
  filename: string | null
  svg: string | null
}

export const exportBlueprint = async (
  state: ProjectState,
  filename = 'blueprint',
  unitSystem: 'metric' | 'imperial' = 'metric'
): Promise<BlueprintExportResult> => {
  try {
    const result = await composeBlueprint(state, { unitSystem })
    const svg = result.svg
    const blob = new Blob([svg], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${filename}.svg`
    link.click()
    URL.revokeObjectURL(url)
    return { success: true, error: null, filename: `${filename}.svg`, svg }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Export failed',
      filename: null,
      svg: null,
    }
  }
}
