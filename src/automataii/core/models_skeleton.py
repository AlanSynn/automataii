from typing import Any

from pydantic import BaseModel, Field


class StandardizedJointModel(BaseModel):
    """
    Represents a single joint in a standardized skeleton format.
    """

    id: str = Field(..., description="Unique identifier for the joint.")
    name: str = Field(..., description="Human-readable name for the joint.")
    position: tuple[float, float] = Field(
        ..., description="2D coordinates (x, y) of the joint."
    )
    parent_id: str | None = Field(
        None, description="ID of the parent joint, if any."
    )
    label: str | None = Field(
        None,
        description="Original name or label from the source format, if different from 'name'.",
    )
    source_data: dict[str, Any] | None = Field(
        None,
        description="Original unprocessed data for this joint from the source file for debugging or format-specific needs.",
    )
    is_locked: bool = Field(
        False,
        description="Whether this joint is locked/fixed and should not be moved during IK solving.",
    )
    bend_direction: float | None = Field(
        None,
        description="Bend direction for middle joints (elbow/knee). 1.0 for default direction, -1.0 for inverted. Only applicable to elbow and knee joints.",
    )
    # Children will be derived and stored in the main skeleton model's hierarchy for clarity


class StandardizedSkeletonModel(BaseModel):
    """
    Represents a complete skeleton in a standardized format.
    """

    joints: dict[str, StandardizedJointModel] = Field(
        default_factory=dict,
        description="Dictionary mapping joint IDs to their StandardizedJointModel.",
    )
    root_joint_ids: list[str] = Field(
        default_factory=list,
        description="List of joint IDs that are roots of the skeleton hierarchy.",
    )
    hierarchy: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Dictionary mapping parent joint IDs to a list of their child joint IDs.",
    )

    # Optional metadata and format-specific information
    limb_lengths: dict[str, float] | None = Field(
        default_factory=dict,
        description="Optional mapping of descriptive limb names (e.g., 'left_forearm', 'head') to their calculated or defined lengths. Useful for IK.",
    )
    joint_map: dict[str, str] | None = Field(
        default_factory=dict,
        description="Optional mapping from original joint names/keys (e.g., from char_cfg.yaml joint names) to standardized joint IDs. Helps preserve original naming context and aids in mapping to IK definitions.",
    )
    source_format: str | None = Field(
        None,
        description="Identifier for the original source format of the skeleton (e.g., 'animated_drawings', 'project_json').",
    )
    metadata: dict[str, Any] | None = Field(
        default_factory=dict,
        description="Any other relevant metadata, like source file path, processing notes, etc.",
    )



