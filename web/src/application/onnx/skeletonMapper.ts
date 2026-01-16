import type { SkeletonData } from '../../domain/project'
import type { SkeletonJoint } from './keypoints'

export const buildProjectSkeleton = (skeleton: SkeletonJoint[]): SkeletonData | null => {
  if (skeleton.length === 0) {
    return null
  }
  const joints = skeleton.reduce<SkeletonData['joints']>((acc, joint) => {
    acc[joint.name] = {
      id: joint.name,
      position: { x: joint.locOriginal[0], y: joint.locOriginal[1] },
      parent: joint.parent,
      isLocked: false,
      bendDirection: 'up',
    }
    return acc
  }, {})
  const bones = skeleton
    .filter((joint) => Boolean(joint.parent))
    .map((joint) => ({ fromJoint: joint.parent as string, toJoint: joint.name }))
  const root = skeleton.find((joint) => joint.parent === null)?.name ?? null
  return {
    joints,
    bones,
    rootJoint: root,
  }
}
