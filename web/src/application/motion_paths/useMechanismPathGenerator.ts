import { useCallback, useState } from 'react'
import type { ProjectState } from '../../domain/project'

import { applyMechanismPaths, type MechanismPathUpdate } from './applyMechanismPaths'

export interface MechanismPathGeneratorState {
  updates: MechanismPathUpdate[]
  error: string | null
}

export const useMechanismPathGenerator = (
  state: ProjectState | null,
  setState: (state: ProjectState | null) => void
): {
  status: MechanismPathGeneratorState
  generatePaths: () => MechanismPathGeneratorState
} => {
  const [status, setStatus] = useState<MechanismPathGeneratorState>({
    updates: [],
    error: null,
  })

  const generatePaths = useCallback((): MechanismPathGeneratorState => {
    if (!state) {
      const next = { updates: [], error: 'No project loaded.' }
      setStatus(next)
      return next
    }
    const result = applyMechanismPaths(state)
    setState(result.state)
    const next = { updates: result.updates, error: null }
    setStatus(next)
    return next
  }, [state, setState])

  return { status, generatePaths }
}
