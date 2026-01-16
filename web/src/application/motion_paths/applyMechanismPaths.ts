import type { MechanismData, ProjectState } from '../../domain/project'
import { buildPathData, generateMechanismPath } from './mechanismPathGenerator'

export interface MechanismPathUpdate {
  mechanismId: string
  partName: string
  success: boolean
  error: string | null
}

export const applyMechanismPaths = (
  state: ProjectState
): { state: ProjectState; updates: MechanismPathUpdate[] } => {
  const nextPaths = { ...state.paths }
  const updates: MechanismPathUpdate[] = []

  Object.values(state.mechanisms).forEach((mechanism) => {
    if (!mechanism.enabled) {
      return
    }
    const partName = mechanism.partName || mechanism.id
    const result = generateMechanismPath(mechanism)
    if (result.error || result.points.length === 0) {
      updates.push({
        mechanismId: mechanism.id,
        partName,
        success: false,
        error: result.error ?? 'No path generated',
      })
      return
    }
    nextPaths[partName] = buildPathData({ ...mechanism, partName }, result.points)
    updates.push({ mechanismId: mechanism.id, partName, success: true, error: null })
  })

  return { state: state.withPaths(nextPaths), updates }
}

export const applyMechanismPathToPart = (
  state: ProjectState,
  mechanism: MechanismData
): { state: ProjectState; update: MechanismPathUpdate } => {
  const partName = mechanism.partName || mechanism.id
  const result = generateMechanismPath(mechanism)
  if (result.error || result.points.length === 0) {
    return {
      state,
      update: {
        mechanismId: mechanism.id,
        partName,
        success: false,
        error: result.error ?? 'No path generated',
      },
    }
  }
  const nextPaths = { ...state.paths }
  nextPaths[partName] = buildPathData({ ...mechanism, partName }, result.points)
  return {
    state: state.withPaths(nextPaths),
    update: {
      mechanismId: mechanism.id,
      partName,
      success: true,
      error: null,
    },
  }
}
