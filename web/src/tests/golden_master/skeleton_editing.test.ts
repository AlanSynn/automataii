import { describe, expect, it } from 'vitest'

import {
  addBoneToSkeleton,
  addJointToSkeleton,
  ensureSkeleton,
  moveJointInSkeleton,
  removeJointFromSkeleton,
} from '../../application/skeleton/skeletonEditing'

const buildJoint = (id: string, x = 0, y = 0) => ({
  id,
  position: { x, y },
  parent: null,
  isLocked: false,
  bendDirection: 'up',
})

describe('skeleton editing helpers', () => {
  it('adds joints and sets root', () => {
    const empty = ensureSkeleton(null)
    const next = addJointToSkeleton(empty, buildJoint('root', 1, 2))
    expect(Object.keys(next.joints)).toContain('root')
    expect(next.rootJoint).toBe('root')
  })

  it('moves unlocked joints but keeps locked joints fixed', () => {
    const base = addJointToSkeleton(ensureSkeleton(null), buildJoint('a', 0, 0))
    const moved = moveJointInSkeleton(base, 'a', { x: 4, y: 5 })
    expect(moved.joints.a.position).toEqual({ x: 4, y: 5 })

    const locked = {
      ...moved,
      joints: {
        ...moved.joints,
        a: { ...moved.joints.a, isLocked: true },
      },
    }
    const lockedMove = moveJointInSkeleton(locked, 'a', { x: 10, y: 10 })
    expect(lockedMove.joints.a.position).toEqual({ x: 4, y: 5 })
  })

  it('adds and removes bones with joint cleanup', () => {
    const withJoints = addJointToSkeleton(
      addJointToSkeleton(ensureSkeleton(null), buildJoint('a')),
      buildJoint('b', 1, 1)
    )
    const withBone = addBoneToSkeleton(withJoints, 'a', 'b')
    expect(withBone.bones.length).toBe(1)

    const removed = removeJointFromSkeleton(withBone, 'a')
    expect(removed.bones.length).toBe(0)
    expect(removed.joints.a).toBeUndefined()
  })
})
