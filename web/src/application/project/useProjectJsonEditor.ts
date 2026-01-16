import { useCallback } from 'react'
import type { ProjectState } from '../../domain/project'
import { ProjectState as ProjectStateModel } from '../../domain/project'

export interface ProjectJsonEditorResult {
  success: boolean
  error: string | null
}

export const useProjectJsonEditor = (
  projectDir: string | null,
  setState: (state: ProjectState | null) => void
): { applyProjectJson: (json: string) => ProjectJsonEditorResult } => {
  const applyProjectJson = useCallback(
    (json: string): ProjectJsonEditorResult => {
      let parsed: unknown
      try {
        parsed = JSON.parse(json)
      } catch (error) {
        return { success: false, error: errorMessage(error) }
      }
      if (!isRecord(parsed)) {
        return { success: false, error: 'Project JSON must be an object.' }
      }
      try {
        const nextState = ProjectStateModel.fromDict(parsed, projectDir)
        setState(nextState)
        return { success: true, error: null }
      } catch (error) {
        return { success: false, error: errorMessage(error) }
      }
    },
    [projectDir, setState]
  )

  return { applyProjectJson }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const errorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message
  }
  return 'Invalid JSON'
}
