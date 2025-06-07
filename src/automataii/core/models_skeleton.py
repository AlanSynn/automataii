from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field


class StandardizedJointModel(BaseModel):
    """
    Represents a single joint in a standardized skeleton format.
    """

    id: str = Field(..., description="Unique identifier for the joint.")
    name: str = Field(..., description="Human-readable name for the joint.")
    position: Tuple[float, float] = Field(
        ..., description="2D coordinates (x, y) of the joint."
    )
    parent_id: Optional[str] = Field(
        None, description="ID of the parent joint, if any."
    )
    label: Optional[str] = Field(
        None,
        description="Original name or label from the source format, if different from 'name'.",
    )
    source_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Original unprocessed data for this joint from the source file for debugging or format-specific needs.",
    )
    is_locked: bool = Field(
        False,
        description="Whether this joint is locked/fixed and should not be moved during IK solving.",
    )
    # Children will be derived and stored in the main skeleton model's hierarchy for clarity


class StandardizedSkeletonModel(BaseModel):
    """
    Represents a complete skeleton in a standardized format.
    """

    joints: Dict[str, StandardizedJointModel] = Field(
        default_factory=dict,
        description="Dictionary mapping joint IDs to their StandardizedJointModel.",
    )
    root_joint_ids: List[str] = Field(
        default_factory=list,
        description="List of joint IDs that are roots of the skeleton hierarchy.",
    )
    hierarchy: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Dictionary mapping parent joint IDs to a list of their child joint IDs.",
    )

    # Optional metadata and format-specific information
    limb_lengths: Optional[Dict[str, float]] = Field(
        default_factory=dict,
        description="Optional mapping of descriptive limb names (e.g., 'left_forearm', 'head') to their calculated or defined lengths. Useful for IK.",
    )
    joint_map: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Optional mapping from original joint names/keys (e.g., from char_cfg.yaml joint names) to standardized joint IDs. Helps preserve original naming context and aids in mapping to IK definitions.",
    )
    source_format: Optional[str] = Field(
        None,
        description="Identifier for the original source format of the skeleton (e.g., 'animated_drawings', 'project_json').",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Any other relevant metadata, like source file path, processing notes, etc.",
    )

    class Config:
        validate_assignment = True  # Ensure fields are validated on assignment

    def get_joint_children(self, joint_id: str) -> List[StandardizedJointModel]:
        """Helper to get child joint models for a given joint_id."""
        child_ids = self.hierarchy.get(joint_id, [])
        return [
            self.joints[child_id] for child_id in child_ids if child_id in self.joints
        ]

    def get_joint_parent(self, joint_id: str) -> Optional[StandardizedJointModel]:
        """Helper to get the parent joint model for a given joint_id."""
        parent_id = self.joints.get(joint_id, {}).get("parent_id")
        if parent_id and parent_id in self.joints:
            return self.joints[parent_id]
        return None
