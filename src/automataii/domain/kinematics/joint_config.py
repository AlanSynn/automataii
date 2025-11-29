"""
Joint Configuration - Pure domain constants for IK joint mappings.

Extracted from IKManager. Contains the mapping between IK joint IDs
and part names, as well as source skeleton names.

Design Pattern: Configuration (immutable data definitions)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Mapping from IK part names to actual part names in the character
IK_PART_TO_ACTUAL_PART: Final[dict[str, str]] = {
    "head": "head",
    "torso": "torso",
    "left_upper_arm": "left_arm_upper",
    "left_forearm": "left_arm_lower",
    "right_upper_arm": "right_arm_upper",
    "right_forearm": "right_arm_lower",
    "left_thigh": "left_leg_upper",
    "left_calf": "left_leg_lower",
    "right_thigh": "right_leg_upper",
    "right_calf": "right_leg_lower",
}

# Mapping from IK joint IDs to source skeleton joint names
IK_JOINT_TO_SOURCE_NAME: Final[dict[str, str]] = {
    "j_neck_base": "hip",
    "j_head_tip": "head",
    "j_left_shoulder": "left_shoulder",
    "j_right_shoulder": "right_shoulder",
    "j_left_hip": "left_hip",
    "j_right_hip": "right_hip",
    "j_left_elbow": "left_elbow",
    "j_left_wrist": "left_hand",
    "j_right_elbow": "right_elbow",
    "j_right_wrist": "right_hand",
    "j_left_knee": "left_knee",
    "j_left_ankle": "left_foot",
    "j_right_knee": "right_knee",
    "j_right_ankle": "right_foot",
}

# Reverse mapping: source name to IK joint ID
SOURCE_NAME_TO_IK_JOINT: Final[dict[str, str]] = {v: k for k, v in IK_JOINT_TO_SOURCE_NAME.items()}

# Limb chain definitions for IK solving
LIMB_CHAINS: Final[dict[str, list[str]]] = {
    "left_arm": ["j_left_shoulder", "j_left_elbow", "j_left_wrist"],
    "right_arm": ["j_right_shoulder", "j_right_elbow", "j_right_wrist"],
    "left_leg": ["j_left_hip", "j_left_knee", "j_left_ankle"],
    "right_leg": ["j_right_hip", "j_right_knee", "j_right_ankle"],
}

# Effector joints (end of limb chains that can be positioned)
EFFECTOR_JOINTS: Final[set[str]] = {
    "j_left_wrist",
    "j_right_wrist",
    "j_left_ankle",
    "j_right_ankle",
}


@dataclass(frozen=True)
class LimbConfig:
    """Configuration for a limb chain."""

    name: str
    root_joint: str
    mid_joint: str
    end_joint: str
    part_names: tuple[str, str]  # (upper_part, lower_part)

    @property
    def joints(self) -> tuple[str, str, str]:
        """Get all joints in the chain."""
        return (self.root_joint, self.mid_joint, self.end_joint)


# Pre-configured limb definitions
LIMB_CONFIGS: Final[dict[str, LimbConfig]] = {
    "left_arm": LimbConfig(
        name="left_arm",
        root_joint="j_left_shoulder",
        mid_joint="j_left_elbow",
        end_joint="j_left_wrist",
        part_names=("left_arm_upper", "left_arm_lower"),
    ),
    "right_arm": LimbConfig(
        name="right_arm",
        root_joint="j_right_shoulder",
        mid_joint="j_right_elbow",
        end_joint="j_right_wrist",
        part_names=("right_arm_upper", "right_arm_lower"),
    ),
    "left_leg": LimbConfig(
        name="left_leg",
        root_joint="j_left_hip",
        mid_joint="j_left_knee",
        end_joint="j_left_ankle",
        part_names=("left_leg_upper", "left_leg_lower"),
    ),
    "right_leg": LimbConfig(
        name="right_leg",
        root_joint="j_right_hip",
        mid_joint="j_right_knee",
        end_joint="j_right_ankle",
        part_names=("right_leg_upper", "right_leg_lower"),
    ),
}


def get_limb_for_effector(effector_joint: str) -> LimbConfig | None:
    """Get the limb configuration for a given effector joint."""
    for limb in LIMB_CONFIGS.values():
        if limb.end_joint == effector_joint:
            return limb
    return None


def get_actual_part_name(ik_part_name: str) -> str:
    """Get the actual part name for an IK part name."""
    return IK_PART_TO_ACTUAL_PART.get(ik_part_name, ik_part_name)


def get_source_joint_name(ik_joint_id: str) -> str | None:
    """Get the source skeleton joint name for an IK joint ID."""
    return IK_JOINT_TO_SOURCE_NAME.get(ik_joint_id)
