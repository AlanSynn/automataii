import { useCallback } from 'react'
import type { ProjectState } from '../../domain/project'
import { parseMechanismsJson } from './parseMechanisms'

export interface MechanismEditorResult {
  success: boolean
  error: string | null
}

export const useMechanismEditor = (
  state: ProjectState | null,
  setState: (state: ProjectState | null) => void
): {
  applyMechanismsJson: (json: string) => MechanismEditorResult
} => {
  const applyMechanismsJson = useCallback(
    (json: string): MechanismEditorResult => {
      if (!state) {
        return { success: false, error: 'No project loaded.' }
      }
      const parsed = parseMechanismsJson(json)
      if (!parsed.success || !parsed.mechanisms) {
        return { success: false, error: parsed.error }
      }
      const updated = state.withMechanisms(parsed.mechanisms)
      setState(updated)
      return { success: true, error: null }
    },
    [state, setState]
  )

  return { applyMechanismsJson }
}

