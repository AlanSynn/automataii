# from typing import Dict, Any

# BODY_PARTS: Dict[str, Dict[str, Any]] = {
#     "head": {"joints": ["neck", "head_top"], "color": "rgba(255,0,0,0.5)", "z_value": 10, "fixed": False, "anchor_joint": "neck"},
#     "torso": {"joints": ["neck", "torso", "pelvis", "left_shoulder", "right_shoulder"], "color": "rgba(0,255,0,0.5)", "z_value": 0, "fixed": True, "anchor_joint": "torso"}, # Torso is often fixed

#     "left_arm_upper": {"joints": ["left_shoulder", "left_elbow"], "color": "rgba(0,0,255,0.5)", "z_value": 5, "fixed": False, "anchor_joint": "left_shoulder"},
#     "left_arm_lower": {"joints": ["left_elbow", "left_wrist"], "color": "rgba(255,255,0,0.5)", "z_value": 4, "fixed": False, "anchor_joint": "left_elbow"},
#     "left_hand": {"joints": ["left_wrist", "left_hand_tip"], "color": "rgba(255,165,0,0.5)", "z_value": 3, "fixed": False, "anchor_joint": "left_wrist"},

#     "right_arm_upper": {"joints": ["right_shoulder", "right_elbow"], "color": "rgba(255,0,255,0.5)", "z_value": 5, "fixed": False, "anchor_joint": "right_shoulder"},
#     "right_arm_lower": {"joints": ["right_elbow", "right_wrist"], "color": "rgba(0,255,255,0.5)", "z_value": 4, "fixed": False, "anchor_joint": "right_elbow"},
#     "right_hand": {"joints": ["right_wrist", "right_hand_tip"], "color": "rgba(0,128,128,0.5)", "z_value": 3, "fixed": False, "anchor_joint": "right_wrist"},

#     "left_leg_upper": {"joints": ["left_hip", "left_knee"], "color": "rgba(128,0,0,0.5)", "z_value": 2, "fixed": False, "anchor_joint": "left_hip"},
#     "left_leg_lower": {"joints": ["left_knee", "left_ankle"], "color": "rgba(0,128,0,0.5)", "z_value": 1, "fixed": False, "anchor_joint": "left_knee"},
#     "left_foot": {"joints": ["left_ankle", "left_foot_tip"], "color": "rgba(128,128,0,0.5)", "z_value": 0, "fixed": False, "anchor_joint": "left_ankle"},

#     "right_leg_upper": {"joints": ["right_hip", "right_knee"], "color": "rgba(0,0,128,0.5)", "z_value": 2, "fixed": False, "anchor_joint": "right_hip"},
#     "right_leg_lower": {"joints": ["right_knee", "right_ankle"], "color": "rgba(128,0,128,0.5)", "z_value": 1, "fixed": False, "anchor_joint": "right_knee"},
#     "right_foot": {"joints": ["right_ankle", "right_foot_tip"], "color": "rgba(0,128,128,0.5)", "z_value": 0, "fixed": False, "anchor_joint": "right_ankle"},

#     # Example of a non-standard part, like a tail or a weapon
#     # "tail": {"joints": ["pelvis", "tail_base", "tail_mid", "tail_tip"], "color": "rgba(100,100,100,0.5)", "z_value": -1, "fixed": False, "anchor_joint": "pelvis"},
# }

from typing import Any

BODY_PARTS: dict[str, dict[str, Any]] = {
    "head": {
        "joints": ["neck", "head_top"],
        "color": "rgba(255,0,0,0.5)",
        "z_value": 10,
        "fixed": False,
        "anchor_joint": "neck",
    },
    "torso": {
        "joints": ["neck", "torso", "pelvis", "left_shoulder", "right_shoulder"],
        "color": "rgba(0,255,0,0.5)",
        "z_value": 0,
        "fixed": True,
        "anchor_joint": "torso",
    },
    "left_arm_upper": {
        "joints": ["left_shoulder", "left_elbow"],
        "color": "rgba(0,0,255,0.5)",
        "z_value": 5,
        "fixed": False,
        "anchor_joint": "left_shoulder",
    },
    "left_arm_lower": {
        "joints": ["left_elbow", "left_wrist", "left_hand"],
        "color": "rgba(255,255,0,0.5)",
        "z_value": 4,
        "fixed": False,
        "anchor_joint": "left_elbow",
    },
    "right_arm_upper": {
        "joints": ["right_shoulder", "right_elbow"],
        "color": "rgba(255,0,255,0.5)",
        "z_value": 5,
        "fixed": False,
        "anchor_joint": "right_shoulder",
    },
    "right_arm_lower": {
        "joints": ["right_elbow", "right_wrist", "right_hand"],
        "color": "rgba(0,255,255,0.5)",
        "z_value": 4,
        "fixed": False,
        "anchor_joint": "right_elbow",
    },
    "left_leg_upper": {
        "joints": ["left_hip", "left_knee"],
        "color": "rgba(128,0,0,0.5)",
        "z_value": 2,
        "fixed": False,
        "anchor_joint": "left_hip",
    },
    "left_leg_lower": {
        "joints": ["left_knee", "left_ankle", "left_foot"],
        "color": "rgba(0,128,0,0.5)",
        "z_value": 1,
        "fixed": False,
        "anchor_joint": "left_knee",
    },
    "right_leg_upper": {
        "joints": ["right_hip", "right_knee"],
        "color": "rgba(0,0,128,0.5)",
        "z_value": 2,
        "fixed": False,
        "anchor_joint": "right_hip",
    },
    "right_leg_lower": {
        "joints": ["right_knee", "right_ankle", "right_foot"],
        "color": "rgba(128,0,128,0.5)",
        "z_value": 1,
        "fixed": False,
        "anchor_joint": "right_knee",
    },
}
