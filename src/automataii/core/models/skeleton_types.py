"""
Skeleton type definitions and templates for different character types.
"""

from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field
from automataii.core.models.skeleton import StandardizedJointModel, StandardizedSkeletonModel


class SkeletonType(Enum):
    """Types of skeletons supported by the system."""
    HUMANOID = "humanoid"
    QUADRUPED = "quadruped"
    BIRD = "bird"
    INSECT = "insect"
    FISH = "fish"
    SNAKE = "snake"
    SPIDER = "spider"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class SkeletonTemplate(BaseModel):
    """Template for a specific skeleton type."""
    name: str = Field(..., description="Name of the skeleton template")
    type: SkeletonType = Field(..., description="Type of skeleton")
    description: str = Field(..., description="Description of the skeleton template")
    
    # Joint definitions for the template
    joint_definitions: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Definitions of joints including their names, default positions, and constraints"
    )
    
    # Bone connections
    bone_connections: List[Tuple[str, str]] = Field(
        default_factory=list,
        description="List of (parent_joint_id, child_joint_id) tuples defining bone connections"
    )
    
    # Animation constraints
    animation_constraints: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Constraints for joint movements and rotations"
    )
    
    # Mechanism recommendations
    mechanism_hints: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Recommended mechanism types for different body parts"
    )
    
    # Detection features
    detection_features: Dict[str, Any] = Field(
        default_factory=dict,
        description="Features used to detect this skeleton type from an image"
    )


class SkeletonClassificationResult(BaseModel):
    """Result of skeleton type classification."""
    primary_type: SkeletonType = Field(..., description="Most likely skeleton type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for the classification")
    alternative_types: Dict[SkeletonType, float] = Field(
        default_factory=dict,
        description="Alternative skeleton types with their confidence scores"
    )
    detected_features: Dict[str, Any] = Field(
        default_factory=dict,
        description="Features detected that led to the classification"
    )
    recommendation: str = Field(
        "",
        description="Recommendation for which skeleton type to use"
    )


# Define skeleton templates
SKELETON_TEMPLATES: Dict[SkeletonType, SkeletonTemplate] = {
    SkeletonType.HUMANOID: SkeletonTemplate(
        name="Humanoid",
        type=SkeletonType.HUMANOID,
        description="Standard humanoid skeleton with head, torso, arms, and legs",
        joint_definitions={
            "head": {"name": "Head", "default_position": (0.5, 0.85), "parent": "neck"},
            "neck": {"name": "Neck", "default_position": (0.5, 0.75), "parent": "torso"},
            "torso": {"name": "Torso", "default_position": (0.5, 0.6), "parent": None},
            "left_shoulder": {"name": "Left Shoulder", "default_position": (0.35, 0.7), "parent": "torso"},
            "right_shoulder": {"name": "Right Shoulder", "default_position": (0.65, 0.7), "parent": "torso"},
            "left_elbow": {"name": "Left Elbow", "default_position": (0.3, 0.5), "parent": "left_shoulder"},
            "right_elbow": {"name": "Right Elbow", "default_position": (0.7, 0.5), "parent": "right_shoulder"},
            "left_wrist": {"name": "Left Wrist", "default_position": (0.25, 0.35), "parent": "left_elbow"},
            "right_wrist": {"name": "Right Wrist", "default_position": (0.75, 0.35), "parent": "right_elbow"},
            "left_hip": {"name": "Left Hip", "default_position": (0.45, 0.45), "parent": "torso"},
            "right_hip": {"name": "Right Hip", "default_position": (0.55, 0.45), "parent": "torso"},
            "left_knee": {"name": "Left Knee", "default_position": (0.45, 0.25), "parent": "left_hip"},
            "right_knee": {"name": "Right Knee", "default_position": (0.55, 0.25), "parent": "right_hip"},
            "left_ankle": {"name": "Left Ankle", "default_position": (0.45, 0.1), "parent": "left_knee"},
            "right_ankle": {"name": "Right Ankle", "default_position": (0.55, 0.1), "parent": "right_knee"},
        },
        bone_connections=[
            ("torso", "neck"), ("neck", "head"),
            ("torso", "left_shoulder"), ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
            ("torso", "right_shoulder"), ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
            ("torso", "left_hip"), ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
            ("torso", "right_hip"), ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
        ],
        animation_constraints={
            "left_elbow": {"rotation_range": (-150, 0), "rotation_axis": "z"},
            "right_elbow": {"rotation_range": (-150, 0), "rotation_axis": "z"},
            "left_knee": {"rotation_range": (0, 150), "rotation_axis": "z"},
            "right_knee": {"rotation_range": (0, 150), "rotation_axis": "z"},
        },
        mechanism_hints={
            "arms": ["fourbar", "cam"],
            "legs": ["fourbar", "crankslider"],
            "head": ["cam", "gear"],
        },
        detection_features={
            "expected_joints": 15,
            "symmetry": "bilateral",
            "limb_count": {"arms": 2, "legs": 2},
            "aspect_ratio_range": (0.3, 0.6),
        }
    ),
    
    SkeletonType.QUADRUPED: SkeletonTemplate(
        name="Quadruped",
        type=SkeletonType.QUADRUPED,
        description="Four-legged animal skeleton",
        joint_definitions={
            "head": {"name": "Head", "default_position": (0.85, 0.7), "parent": "neck"},
            "neck": {"name": "Neck", "default_position": (0.75, 0.6), "parent": "front_torso"},
            "front_torso": {"name": "Front Torso", "default_position": (0.65, 0.5), "parent": "mid_torso"},
            "mid_torso": {"name": "Mid Torso", "default_position": (0.5, 0.5), "parent": None},
            "rear_torso": {"name": "Rear Torso", "default_position": (0.35, 0.5), "parent": "mid_torso"},
            "tail_base": {"name": "Tail Base", "default_position": (0.2, 0.5), "parent": "rear_torso"},
            "tail_mid": {"name": "Tail Mid", "default_position": (0.1, 0.45), "parent": "tail_base"},
            "tail_end": {"name": "Tail End", "default_position": (0.05, 0.4), "parent": "tail_mid"},
            # Front legs
            "front_left_shoulder": {"name": "Front Left Shoulder", "default_position": (0.65, 0.45), "parent": "front_torso"},
            "front_right_shoulder": {"name": "Front Right Shoulder", "default_position": (0.65, 0.55), "parent": "front_torso"},
            "front_left_elbow": {"name": "Front Left Elbow", "default_position": (0.65, 0.3), "parent": "front_left_shoulder"},
            "front_right_elbow": {"name": "Front Right Elbow", "default_position": (0.65, 0.3), "parent": "front_right_shoulder"},
            "front_left_paw": {"name": "Front Left Paw", "default_position": (0.65, 0.15), "parent": "front_left_elbow"},
            "front_right_paw": {"name": "Front Right Paw", "default_position": (0.65, 0.15), "parent": "front_right_elbow"},
            # Rear legs
            "rear_left_hip": {"name": "Rear Left Hip", "default_position": (0.35, 0.45), "parent": "rear_torso"},
            "rear_right_hip": {"name": "Rear Right Hip", "default_position": (0.35, 0.55), "parent": "rear_torso"},
            "rear_left_knee": {"name": "Rear Left Knee", "default_position": (0.35, 0.3), "parent": "rear_left_hip"},
            "rear_right_knee": {"name": "Rear Right Knee", "default_position": (0.35, 0.3), "parent": "rear_right_hip"},
            "rear_left_paw": {"name": "Rear Left Paw", "default_position": (0.35, 0.15), "parent": "rear_left_knee"},
            "rear_right_paw": {"name": "Rear Right Paw", "default_position": (0.35, 0.15), "parent": "rear_right_knee"},
        },
        bone_connections=[
            ("mid_torso", "front_torso"), ("front_torso", "neck"), ("neck", "head"),
            ("mid_torso", "rear_torso"), ("rear_torso", "tail_base"), ("tail_base", "tail_mid"), ("tail_mid", "tail_end"),
            ("front_torso", "front_left_shoulder"), ("front_left_shoulder", "front_left_elbow"), ("front_left_elbow", "front_left_paw"),
            ("front_torso", "front_right_shoulder"), ("front_right_shoulder", "front_right_elbow"), ("front_right_elbow", "front_right_paw"),
            ("rear_torso", "rear_left_hip"), ("rear_left_hip", "rear_left_knee"), ("rear_left_knee", "rear_left_paw"),
            ("rear_torso", "rear_right_hip"), ("rear_right_hip", "rear_right_knee"), ("rear_right_knee", "rear_right_paw"),
        ],
        animation_constraints={
            "front_left_elbow": {"rotation_range": (-150, 30), "rotation_axis": "z"},
            "front_right_elbow": {"rotation_range": (-150, 30), "rotation_axis": "z"},
            "rear_left_knee": {"rotation_range": (-30, 150), "rotation_axis": "z"},
            "rear_right_knee": {"rotation_range": (-30, 150), "rotation_axis": "z"},
        },
        mechanism_hints={
            "front_legs": ["fourbar", "cam"],
            "rear_legs": ["fourbar", "cam"],
            "tail": ["cam", "gear"],
            "head": ["cam"],
        },
        detection_features={
            "expected_joints": 20,
            "symmetry": "bilateral",
            "limb_count": {"legs": 4},
            "aspect_ratio_range": (1.5, 3.0),
            "horizontal_orientation": True,
        }
    ),
    
    SkeletonType.BIRD: SkeletonTemplate(
        name="Bird",
        type=SkeletonType.BIRD,
        description="Bird skeleton with wings, legs, and tail",
        joint_definitions={
            "head": {"name": "Head", "default_position": (0.5, 0.85), "parent": "neck"},
            "beak": {"name": "Beak", "default_position": (0.55, 0.87), "parent": "head"},
            "neck": {"name": "Neck", "default_position": (0.5, 0.75), "parent": "body"},
            "body": {"name": "Body", "default_position": (0.5, 0.6), "parent": None},
            "tail_base": {"name": "Tail Base", "default_position": (0.5, 0.45), "parent": "body"},
            "tail_end": {"name": "Tail End", "default_position": (0.5, 0.35), "parent": "tail_base"},
            # Wings
            "left_wing_shoulder": {"name": "Left Wing Shoulder", "default_position": (0.35, 0.65), "parent": "body"},
            "right_wing_shoulder": {"name": "Right Wing Shoulder", "default_position": (0.65, 0.65), "parent": "body"},
            "left_wing_elbow": {"name": "Left Wing Elbow", "default_position": (0.25, 0.6), "parent": "left_wing_shoulder"},
            "right_wing_elbow": {"name": "Right Wing Elbow", "default_position": (0.75, 0.6), "parent": "right_wing_shoulder"},
            "left_wing_tip": {"name": "Left Wing Tip", "default_position": (0.15, 0.55), "parent": "left_wing_elbow"},
            "right_wing_tip": {"name": "Right Wing Tip", "default_position": (0.85, 0.55), "parent": "right_wing_elbow"},
            # Legs
            "left_hip": {"name": "Left Hip", "default_position": (0.45, 0.5), "parent": "body"},
            "right_hip": {"name": "Right Hip", "default_position": (0.55, 0.5), "parent": "body"},
            "left_knee": {"name": "Left Knee", "default_position": (0.45, 0.35), "parent": "left_hip"},
            "right_knee": {"name": "Right Knee", "default_position": (0.55, 0.35), "parent": "right_hip"},
            "left_foot": {"name": "Left Foot", "default_position": (0.45, 0.2), "parent": "left_knee"},
            "right_foot": {"name": "Right Foot", "default_position": (0.55, 0.2), "parent": "right_knee"},
        },
        bone_connections=[
            ("body", "neck"), ("neck", "head"), ("head", "beak"),
            ("body", "tail_base"), ("tail_base", "tail_end"),
            ("body", "left_wing_shoulder"), ("left_wing_shoulder", "left_wing_elbow"), ("left_wing_elbow", "left_wing_tip"),
            ("body", "right_wing_shoulder"), ("right_wing_shoulder", "right_wing_elbow"), ("right_wing_elbow", "right_wing_tip"),
            ("body", "left_hip"), ("left_hip", "left_knee"), ("left_knee", "left_foot"),
            ("body", "right_hip"), ("right_hip", "right_knee"), ("right_knee", "right_foot"),
        ],
        animation_constraints={
            "left_wing_elbow": {"rotation_range": (-90, 90), "rotation_axis": "z"},
            "right_wing_elbow": {"rotation_range": (-90, 90), "rotation_axis": "z"},
            "left_knee": {"rotation_range": (-30, 150), "rotation_axis": "z"},
            "right_knee": {"rotation_range": (-30, 150), "rotation_axis": "z"},
        },
        mechanism_hints={
            "wings": ["cam", "fourbar"],
            "legs": ["fourbar", "cam"],
            "head": ["cam"],
            "tail": ["cam"],
        },
        detection_features={
            "expected_joints": 18,
            "symmetry": "bilateral",
            "limb_count": {"wings": 2, "legs": 2},
            "has_wings": True,
            "aspect_ratio_range": (0.6, 1.2),
        }
    ),
    
    SkeletonType.INSECT: SkeletonTemplate(
        name="Insect",
        type=SkeletonType.INSECT,
        description="Six-legged insect skeleton",
        joint_definitions={
            "head": {"name": "Head", "default_position": (0.8, 0.5), "parent": "thorax"},
            "thorax": {"name": "Thorax", "default_position": (0.6, 0.5), "parent": "abdomen"},
            "abdomen": {"name": "Abdomen", "default_position": (0.3, 0.5), "parent": None},
            # Antennae
            "left_antenna": {"name": "Left Antenna", "default_position": (0.85, 0.55), "parent": "head"},
            "right_antenna": {"name": "Right Antenna", "default_position": (0.85, 0.45), "parent": "head"},
            # Legs (6 total)
            "front_left_coxa": {"name": "Front Left Coxa", "default_position": (0.65, 0.4), "parent": "thorax"},
            "front_right_coxa": {"name": "Front Right Coxa", "default_position": (0.65, 0.6), "parent": "thorax"},
            "mid_left_coxa": {"name": "Mid Left Coxa", "default_position": (0.55, 0.4), "parent": "thorax"},
            "mid_right_coxa": {"name": "Mid Right Coxa", "default_position": (0.55, 0.6), "parent": "thorax"},
            "rear_left_coxa": {"name": "Rear Left Coxa", "default_position": (0.45, 0.4), "parent": "thorax"},
            "rear_right_coxa": {"name": "Rear Right Coxa", "default_position": (0.45, 0.6), "parent": "thorax"},
            # Leg segments
            "front_left_femur": {"name": "Front Left Femur", "default_position": (0.7, 0.3), "parent": "front_left_coxa"},
            "front_right_femur": {"name": "Front Right Femur", "default_position": (0.7, 0.7), "parent": "front_right_coxa"},
            "mid_left_femur": {"name": "Mid Left Femur", "default_position": (0.55, 0.3), "parent": "mid_left_coxa"},
            "mid_right_femur": {"name": "Mid Right Femur", "default_position": (0.55, 0.7), "parent": "mid_right_coxa"},
            "rear_left_femur": {"name": "Rear Left Femur", "default_position": (0.4, 0.3), "parent": "rear_left_coxa"},
            "rear_right_femur": {"name": "Rear Right Femur", "default_position": (0.4, 0.7), "parent": "rear_right_coxa"},
            # Tarsi
            "front_left_tarsus": {"name": "Front Left Tarsus", "default_position": (0.75, 0.2), "parent": "front_left_femur"},
            "front_right_tarsus": {"name": "Front Right Tarsus", "default_position": (0.75, 0.8), "parent": "front_right_femur"},
            "mid_left_tarsus": {"name": "Mid Left Tarsus", "default_position": (0.55, 0.2), "parent": "mid_left_femur"},
            "mid_right_tarsus": {"name": "Mid Right Tarsus", "default_position": (0.55, 0.8), "parent": "mid_right_femur"},
            "rear_left_tarsus": {"name": "Rear Left Tarsus", "default_position": (0.35, 0.2), "parent": "rear_left_femur"},
            "rear_right_tarsus": {"name": "Rear Right Tarsus", "default_position": (0.35, 0.8), "parent": "rear_right_femur"},
        },
        bone_connections=[
            ("abdomen", "thorax"), ("thorax", "head"),
            ("head", "left_antenna"), ("head", "right_antenna"),
            # Front legs
            ("thorax", "front_left_coxa"), ("front_left_coxa", "front_left_femur"), ("front_left_femur", "front_left_tarsus"),
            ("thorax", "front_right_coxa"), ("front_right_coxa", "front_right_femur"), ("front_right_femur", "front_right_tarsus"),
            # Mid legs
            ("thorax", "mid_left_coxa"), ("mid_left_coxa", "mid_left_femur"), ("mid_left_femur", "mid_left_tarsus"),
            ("thorax", "mid_right_coxa"), ("mid_right_coxa", "mid_right_femur"), ("mid_right_femur", "mid_right_tarsus"),
            # Rear legs
            ("thorax", "rear_left_coxa"), ("rear_left_coxa", "rear_left_femur"), ("rear_left_femur", "rear_left_tarsus"),
            ("thorax", "rear_right_coxa"), ("rear_right_coxa", "rear_right_femur"), ("rear_right_femur", "rear_right_tarsus"),
        ],
        animation_constraints={
            "front_left_femur": {"rotation_range": (-60, 60), "rotation_axis": "z"},
            "front_right_femur": {"rotation_range": (-60, 60), "rotation_axis": "z"},
            "mid_left_femur": {"rotation_range": (-60, 60), "rotation_axis": "z"},
            "mid_right_femur": {"rotation_range": (-60, 60), "rotation_axis": "z"},
            "rear_left_femur": {"rotation_range": (-60, 60), "rotation_axis": "z"},
            "rear_right_femur": {"rotation_range": (-60, 60), "rotation_axis": "z"},
        },
        mechanism_hints={
            "legs": ["cam", "gear"],
            "antennae": ["cam"],
            "abdomen": ["cam"],
        },
        detection_features={
            "expected_joints": 24,
            "symmetry": "bilateral",
            "limb_count": {"legs": 6},
            "body_segments": 3,
            "aspect_ratio_range": (1.5, 3.0),
        }
    ),
}


def get_skeleton_template(skeleton_type: SkeletonType) -> Optional[SkeletonTemplate]:
    """Get a skeleton template by type."""
    return SKELETON_TEMPLATES.get(skeleton_type)


def create_skeleton_from_template(
    template: SkeletonTemplate, 
    scale: float = 1.0,
    offset: Tuple[float, float] = (0.0, 0.0)
) -> StandardizedSkeletonModel:
    """Create a StandardizedSkeletonModel from a template."""
    joints = {}
    hierarchy = {}
    
    # Create joints from template definitions
    for joint_id, joint_def in template.joint_definitions.items():
        position = joint_def["default_position"]
        scaled_position = (
            position[0] * scale + offset[0],
            position[1] * scale + offset[1]
        )
        
        joint = StandardizedJointModel(
            id=joint_id,
            name=joint_def["name"],
            position=scaled_position,
            parent_id=joint_def.get("parent"),
            source_data={"template": template.type.value}
        )
        joints[joint_id] = joint
        
        # Build hierarchy
        parent_id = joint_def.get("parent")
        if parent_id:
            if parent_id not in hierarchy:
                hierarchy[parent_id] = []
            hierarchy[parent_id].append(joint_id)
    
    # Find root joints
    root_joint_ids = [
        joint_id for joint_id, joint_def in template.joint_definitions.items()
        if joint_def.get("parent") is None
    ]
    
    return StandardizedSkeletonModel(
        joints=joints,
        root_joint_ids=root_joint_ids,
        hierarchy=hierarchy,
        source_format=f"template_{template.type.value}",
        metadata={
            "template_type": template.type.value,
            "template_name": template.name,
            "scale": scale,
            "offset": offset,
            "animation_constraints": template.animation_constraints,
            "mechanism_hints": template.mechanism_hints,
        }
    )