import type { BoneData, JointData, Point, SkeletonData } from '../../domain/project'

export const ensureSkeleton = (skeleton: SkeletonData | null): SkeletonData =>
  skeleton ?? { joints: {}, bones: [], rootJoint: null }

const removeBonesForJoint = (bones: BoneData[], jointId: string): BoneData[] =>
  bones.filter((bone) => bone.fromJoint !== jointId && bone.toJoint !== jointId)

const removeDuplicateBones = (bones: BoneData[]): BoneData[] => {
  const seen = new Set<string>()
  return bones.filter((bone) => {
    const key = `${bone.fromJoint}:${bone.toJoint}`
    if (seen.has(key)) {
      return false
    }
    seen.add(key)
    return true
  })
}

export const addJointToSkeleton = (
  skeleton: SkeletonData,
  joint: JointData
): SkeletonData => {
  if (skeleton.joints[joint.id]) {
    return skeleton
  }
  return {
    ...skeleton,
    joints: { ...skeleton.joints, [joint.id]: joint },
    rootJoint: skeleton.rootJoint ?? joint.id,
  }
}

export const moveJointInSkeleton = (
  skeleton: SkeletonData,
  jointId: string,
  point: Point
): SkeletonData => {
  const joint = skeleton.joints[jointId]
  if (!joint || joint.isLocked) {
    return skeleton
  }
  return {
    ...skeleton,
    joints: {
      ...skeleton.joints,
      [jointId]: { ...joint, position: point },
    },
  }
}

export const removeJointFromSkeleton = (
  skeleton: SkeletonData,
  jointId: string
): SkeletonData => {
  if (!skeleton.joints[jointId]) {
    return skeleton
  }
  const nextJoints = { ...skeleton.joints }
  delete nextJoints[jointId]
  return {
    ...skeleton,
    joints: nextJoints,
    bones: removeBonesForJoint(skeleton.bones, jointId),
    rootJoint: skeleton.rootJoint === jointId ? null : skeleton.rootJoint,
  }
}

export const setJointLocked = (
  skeleton: SkeletonData,
  jointId: string,
  value: boolean
): SkeletonData => {
  const joint = skeleton.joints[jointId]
  if (!joint) {
    return skeleton
  }
  return {
    ...skeleton,
    joints: {
      ...skeleton.joints,
      [jointId]: { ...joint, isLocked: value },
    },
  }
}

export const setBendDirection = (
  skeleton: SkeletonData,
  jointId: string,
  value: string
): SkeletonData => {
  const joint = skeleton.joints[jointId]
  if (!joint) {
    return skeleton
  }
  return {
    ...skeleton,
    joints: {
      ...skeleton.joints,
      [jointId]: { ...joint, bendDirection: value },
    },
  }
}

export const setParentJoint = (
  skeleton: SkeletonData,
  jointId: string,
  parentId: string | null
): SkeletonData => {
  const joint = skeleton.joints[jointId]
  if (!joint) {
    return skeleton
  }
  if (parentId && !skeleton.joints[parentId]) {
    return skeleton
  }
  return {
    ...skeleton,
    joints: {
      ...skeleton.joints,
      [jointId]: { ...joint, parent: parentId },
    },
  }
}

export const setRootJoint = (
  skeleton: SkeletonData,
  jointId: string | null
): SkeletonData => {
  if (jointId && !skeleton.joints[jointId]) {
    return skeleton
  }
  return {
    ...skeleton,
    rootJoint: jointId,
  }
}

export const addBoneToSkeleton = (
  skeleton: SkeletonData,
  fromJoint: string,
  toJoint: string
): SkeletonData => {
  if (fromJoint === toJoint) {
    return skeleton
  }
  if (!skeleton.joints[fromJoint] || !skeleton.joints[toJoint]) {
    return skeleton
  }
  return {
    ...skeleton,
    bones: removeDuplicateBones([...skeleton.bones, { fromJoint, toJoint }]),
  }
}

export const removeBoneFromSkeleton = (
  skeleton: SkeletonData,
  fromJoint: string,
  toJoint: string
): SkeletonData => ({
  ...skeleton,
  bones: skeleton.bones.filter(
    (bone) => !(bone.fromJoint === fromJoint && bone.toJoint === toJoint)
  ),
})
