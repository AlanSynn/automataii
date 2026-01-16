import { useCallback } from 'react'
import type { ProjectState } from '../../domain/project'

import { parsePathsJson } from './parsePaths'

export interface PathJsonEditorResult {
  success: boolean
  error: string | null
}

export const usePathJsonEditor = (
  state: ProjectState | null,
  setState: (state: ProjectState | null) => void
): { applyPathsJson: (json: string) => PathJsonEditorResult } => {
  const applyPathsJson = useCallback(
    (json: string): PathJsonEditorResult => {
      if (!state) {
        return { success: false, error: 'No project loaded.' }
      }
      const parsed = parsePathsJson(json)
      if (!parsed.success || !parsed.paths) {
        return { success: false, error: parsed.error }
      }
      setState(state.withPaths(parsed.paths))
      return { success: true, error: null }
    },
    [state, setState]
  )

  return { applyPathsJson }
}
