import { useCallback, useMemo, useState } from 'react'
import type { JointData, Point, SkeletonData } from '../../domain/project'
import type { ProjectState } from '../../domain/project'
import {
  addBoneToSkeleton,
  addJointToSkeleton,
  ensureSkeleton,
  moveJointInSkeleton,
  removeBoneFromSkeleton,
  removeJointFromSkeleton,
  setBendDirection as setBendDirectionInSkeleton,
  setJointLocked as setJointLockedInSkeleton,
  setParentJoint as setParentJointInSkeleton,
  setRootJoint as setRootJointInSkeleton,
} from './skeletonEditing'

export interface SkeletonEditorState {
  skeleton: SkeletonData | null
  selectedJointId: string | null
}

export interface SkeletonEditorActions {
  selectJoint: (jointId: string | null) => void
  addJoint: (point: Point, id?: string) => string | null
  moveJoint: (jointId: string, point: Point) => void
  removeJoint: (jointId: string) => void
  setJointLocked: (jointId: string, value: boolean) => void
  setBendDirection: (jointId: string, value: string) => void
  setParent: (jointId: string, parentId: string | null) => void
  setRoot: (jointId: string | null) => void
  addBone: (fromJoint: string, toJoint: string) => void
  removeBone: (fromJoint: string, toJoint: string) => void
}

const generateJointId = (): string => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `joint-${Date.now()}`
}

const updateSkeleton = (
  state: ProjectState,
  setState: (next: ProjectState) => void,
  skeleton: SkeletonData
): void => {
  setState(state.withSkeleton(skeleton))
}

export const useSkeletonEditor = (
  state: ProjectState | null,
  setState: (state: ProjectState | null) => void
): { state: SkeletonEditorState; actions: SkeletonEditorActions } => {
  const [selectedJointId, setSelectedJointId] = useState<string | null>(null)

  const skeleton = useMemo(() => (state ? ensureSkeleton(state.skeleton) : null), [state])

  const setSkeleton = useCallback(
    (nextSkeleton: SkeletonData) => {
      if (!state) {
        return
      }
      updateSkeleton(state, (next) => setState(next), nextSkeleton)
    },
    [state, setState]
  )

  const addJoint = useCallback(
    (point: Point, id?: string): string | null => {
      if (!state) {
        return null
      }
      const nextId = id ?? generateJointId()
      const current = ensureSkeleton(state.skeleton)
      const joint: JointData = {
        id: nextId,
        position: point,
        parent: null,
        isLocked: false,
        bendDirection: 'up',
      }
      const nextSkeleton = addJointToSkeleton(current, joint)
      updateSkeleton(state, (next) => setState(next), nextSkeleton)
      return nextId
    },
    [state, setState]
  )

  const moveJoint = useCallback(
    (jointId: string, point: Point) => {
      if (!state) {
        return
      }
      const current = ensureSkeleton(state.skeleton)
      const nextSkeleton = moveJointInSkeleton(current, jointId, point)
      updateSkeleton(state, (next) => setState(next), nextSkeleton)
    },
    [state, setState]
  )

  const removeJoint = useCallback(
    (jointId: string) => {
      if (!state) {
        return
      }
      const current = ensureSkeleton(state.skeleton)
      if (!current.joints[jointId]) {
        return
      }
      const nextSkeleton = removeJointFromSkeleton(current, jointId)
      updateSkeleton(state, (next) => setState(next), nextSkeleton)
      if (selectedJointId === jointId) {
        setSelectedJointId(null)
      }
    },
    [state, setState, selectedJointId]
  )

  const setJointLocked = useCallback(
    (jointId: string, value: boolean) => {
      if (!state) {
        return
      }
      const current = ensureSkeleton(state.skeleton)
      setSkeleton(setJointLockedInSkeleton(current, jointId, value))
    },
    [state, setSkeleton]
  )

  const setBendDirection = useCallback(
    (jointId: string, value: string) => {
      if (!state) {
        return
      }
      const current = ensureSkeleton(state.skeleton)
      setSkeleton(setBendDirectionInSkeleton(current, jointId, value))
    },
    [state, setSkeleton]
  )

  const setParent = useCallback(
    (jointId: string, parentId: string | null) => {
      if (!state) {
        return
      }
      const current = ensureSkeleton(state.skeleton)
      setSkeleton(setParentJointInSkeleton(current, jointId, parentId))
    },
    [state, setSkeleton]
  )

  const setRoot = useCallback(
    (jointId: string | null) => {
      if (!state) {
        return
      }
      const current = ensureSkeleton(state.skeleton)
      setSkeleton(setRootJointInSkeleton(current, jointId))
    },
    [state, setSkeleton]
  )

  const addBone = useCallback(
    (fromJoint: string, toJoint: string) => {
      if (!state) {
        return
      }
      const current = ensureSkeleton(state.skeleton)
      setSkeleton(addBoneToSkeleton(current, fromJoint, toJoint))
    },
    [state, setSkeleton]
  )

  const removeBone = useCallback(
    (fromJoint: string, toJoint: string) => {
      if (!state) {
        return
      }
      const current = ensureSkeleton(state.skeleton)
      setSkeleton(removeBoneFromSkeleton(current, fromJoint, toJoint))
    },
    [state, setSkeleton]
  )

  return {
    state: {
      skeleton,
      selectedJointId,
    },
    actions: {
      selectJoint: setSelectedJointId,
      addJoint,
      moveJoint,
      removeJoint,
      setJointLocked,
      setBendDirection,
      setParent,
      setRoot,
      addBone,
      removeBone,
    },
  }
}
