export interface BodyPartDefinition {
  joints: string[]
  color: string
  zValue: number
  fixed: boolean
  anchorJoint: string | null
}

export const BODY_PARTS: Record<string, BodyPartDefinition> = {
  head: {
    joints: ['neck', 'head_top'],
    color: 'rgba(255,0,0,0.5)',
    zValue: 10,
    fixed: false,
    anchorJoint: 'neck',
  },
  torso: {
    joints: ['neck', 'torso', 'pelvis', 'left_shoulder', 'right_shoulder'],
    color: 'rgba(0,255,0,0.5)',
    zValue: 0,
    fixed: true,
    anchorJoint: 'torso',
  },
  left_arm_upper: {
    joints: ['left_shoulder', 'left_elbow'],
    color: 'rgba(0,0,255,0.5)',
    zValue: 5,
    fixed: false,
    anchorJoint: 'left_shoulder',
  },
  left_arm_lower: {
    joints: ['left_elbow', 'left_wrist', 'left_hand'],
    color: 'rgba(255,255,0,0.5)',
    zValue: 4,
    fixed: false,
    anchorJoint: 'left_elbow',
  },
  right_arm_upper: {
    joints: ['right_shoulder', 'right_elbow'],
    color: 'rgba(255,0,255,0.5)',
    zValue: 5,
    fixed: false,
    anchorJoint: 'right_shoulder',
  },
  right_arm_lower: {
    joints: ['right_elbow', 'right_wrist', 'right_hand'],
    color: 'rgba(0,255,255,0.5)',
    zValue: 4,
    fixed: false,
    anchorJoint: 'right_elbow',
  },
  left_leg_upper: {
    joints: ['left_hip', 'left_knee'],
    color: 'rgba(128,0,0,0.5)',
    zValue: 2,
    fixed: false,
    anchorJoint: 'left_hip',
  },
  left_leg_lower: {
    joints: ['left_knee', 'left_ankle', 'left_foot'],
    color: 'rgba(0,128,0,0.5)',
    zValue: 1,
    fixed: false,
    anchorJoint: 'left_knee',
  },
  right_leg_upper: {
    joints: ['right_hip', 'right_knee'],
    color: 'rgba(0,0,128,0.5)',
    zValue: 2,
    fixed: false,
    anchorJoint: 'right_hip',
  },
  right_leg_lower: {
    joints: ['right_knee', 'right_ankle', 'right_foot'],
    color: 'rgba(128,0,128,0.5)',
    zValue: 1,
    fixed: false,
    anchorJoint: 'right_knee',
  },
}
