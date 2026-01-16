import { useCallback, useMemo, useState } from 'react'
import type { MechanismData, MechanismParam } from '../../domain/project'
import type { ProjectState } from '../../domain/project'

export interface MechanismFormState {
  selectedId: string | null
  mechanisms: Record<string, MechanismData>
}

export interface MechanismFormActions {
  selectMechanism: (id: string | null) => void
  addMechanism: (mechanism: MechanismData) => void
  removeMechanism: (id: string) => void
  updateMechanism: (id: string, updates: Partial<MechanismData>) => void
  updateParams: (id: string, params: Record<string, unknown>) => void
}

const setMechanismsOnState = (
  state: ProjectState,
  setState: (next: ProjectState) => void,
  mechanisms: Record<string, MechanismData>
): void => {
  setState(state.withMechanisms(mechanisms))
}

export const useMechanismForm = (
  state: ProjectState | null,
  setState: (state: ProjectState | null) => void
): { state: MechanismFormState; actions: MechanismFormActions } => {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const mechanisms = useMemo(() => state?.mechanisms ?? {}, [state])

  const setMechanisms = useCallback(
    (nextMechanisms: Record<string, MechanismData>) => {
      if (!state) {
        return
      }
      setMechanismsOnState(state, (next) => setState(next), nextMechanisms)
    },
    [state, setState]
  )

  const addMechanism = useCallback(
    (mechanism: MechanismData) => {
      if (!state) {
        return
      }
      setMechanisms({
        ...mechanisms,
        [mechanism.id]: mechanism,
      })
      setSelectedId(mechanism.id)
    },
    [state, mechanisms, setMechanisms]
  )

  const removeMechanism = useCallback(
    (id: string) => {
      if (!state) {
        return
      }
      const nextMechanisms = { ...mechanisms }
      delete nextMechanisms[id]
      setMechanisms(nextMechanisms)
      if (selectedId === id) {
        setSelectedId(null)
      }
    },
    [state, mechanisms, setMechanisms, selectedId]
  )

  const updateMechanism = useCallback(
    (id: string, updates: Partial<MechanismData>) => {
      if (!state) {
        return
      }
      const current = mechanisms[id]
      if (!current) {
        return
      }
      setMechanisms({
        ...mechanisms,
        [id]: { ...current, ...updates },
      })
    },
    [state, mechanisms, setMechanisms]
  )

  const updateParams = useCallback(
    (id: string, params: Record<string, unknown>) => {
      updateMechanism(id, { params: params as Record<string, MechanismParam> })
    },
    [updateMechanism]
  )

  return {
    state: { selectedId, mechanisms },
    actions: {
      selectMechanism: setSelectedId,
      addMechanism,
      removeMechanism,
      updateMechanism,
      updateParams,
    },
  }
}
