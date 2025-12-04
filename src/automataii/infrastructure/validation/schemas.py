"""
Pydantic validation schemas for Automataii data structures.

These schemas validate JSON data before it's used in the application,
catching type errors and missing fields early with clear error messages.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


# Re-export ValidationError for convenience
__all__ = [
    "MechanismParameterSchema",
    "MechanismEntrySchema",
    "MechanismCategorySchema",
    "MechanismCatalogSchema",
    "validate_mechanism_catalog",
    "ValidationError",
]


class MechanismParameterSchema(BaseModel):
    """Schema for mechanism parameter definition."""

    name: str = ""
    type: str = "float"
    default: float | int | str | None = None
    min: float | int | None = Field(default=None, alias="min")
    max: float | int | None = Field(default=None, alias="max")
    unit: str | None = None
    description: str | None = None

    model_config = {"extra": "ignore"}  # Ignore unknown fields

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate parameter type is one of the allowed types."""
        allowed_types = {"float", "int", "bool", "str", "angle", "length"}
        if v.lower() not in allowed_types:
            logger.warning(f"Unknown parameter type: {v}, defaulting to 'float'")
            return "float"
        return v.lower()


class MechanismEntrySchema(BaseModel):
    """Schema for mechanism entry in catalog."""

    name: str = ""
    description: str = ""
    type: str = ""
    class_name: str = Field(default="", alias="class")
    tags: list[str] = Field(default_factory=list)
    complexity: str = "unknown"
    parameters: dict[str, MechanismParameterSchema] = Field(default_factory=dict)
    preview_size: list[int] | None = None
    animation_duration: int | None = None

    model_config = {"extra": "ignore", "populate_by_name": True}

    @field_validator("complexity")
    @classmethod
    def validate_complexity(cls, v: str) -> str:
        """Validate complexity level."""
        allowed = {"simple", "moderate", "complex", "unknown"}
        if v.lower() not in allowed:
            return "unknown"
        return v.lower()

    @field_validator("preview_size")
    @classmethod
    def validate_preview_size(cls, v: list[int] | None) -> list[int] | None:
        """Validate preview size is [width, height]."""
        if v is None:
            return None
        if len(v) != 2:
            logger.warning(f"Invalid preview_size length: {len(v)}, expected 2")
            return None
        if any(x <= 0 for x in v):
            logger.warning(f"Invalid preview_size values: {v}")
            return None
        return v


class MechanismCategorySchema(BaseModel):
    """Schema for mechanism category."""

    name: str = ""
    description: str = ""
    icon: str | None = None
    mechanisms: dict[str, MechanismEntrySchema] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}


class MechanismCatalogSchema(BaseModel):
    """Schema for the complete mechanism catalog."""

    version: str = "0.0.0"
    categories: dict[str, MechanismCategorySchema] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version string format."""
        parts = v.split(".")
        if len(parts) < 2:
            logger.warning(f"Invalid version format: {v}, using as-is")
        return v


def validate_mechanism_catalog(raw_data: dict[str, Any]) -> MechanismCatalogSchema:
    """Validate raw JSON data against MechanismCatalogSchema.

    Args:
        raw_data: Dictionary loaded from JSON

    Returns:
        Validated MechanismCatalogSchema instance

    Raises:
        ValidationError: If data doesn't match schema
    """
    return MechanismCatalogSchema.model_validate(raw_data)


# --- Project Data Schemas ---

class PartInfoSchema(BaseModel):
    """Schema for part information in project data."""

    name: str
    image_path: str | None = None
    mask_path: str | None = None
    anchor_joint_id: str | None = None
    position: list[float] | None = None
    rotation: float = 0.0
    scale: float = 1.0
    z_order: int = 0
    visible: bool = True

    model_config = {"extra": "ignore"}

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: list[float] | None) -> list[float] | None:
        """Validate position is [x, y]."""
        if v is None:
            return None
        if len(v) != 2:
            logger.warning(f"Invalid position length: {len(v)}")
            return [0.0, 0.0]
        return v


class JointSchema(BaseModel):
    """Schema for skeleton joint."""

    id: str
    name: str | None = None
    position: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    parent_id: str | None = None
    children: list[str] = Field(default_factory=list)
    bend_direction: float = 1.0
    is_locked: bool = False

    model_config = {"extra": "ignore"}

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: list[float]) -> list[float]:
        """Validate position is [x, y]."""
        if len(v) < 2:
            return [0.0, 0.0]
        return v[:2]

    @field_validator("bend_direction")
    @classmethod
    def validate_bend_direction(cls, v: float) -> float:
        """Validate bend direction is -1 or 1."""
        return 1.0 if v >= 0 else -1.0


class SkeletonDataSchema(BaseModel):
    """Schema for skeleton data."""

    joints: dict[str, JointSchema] = Field(default_factory=dict)
    joint_map: dict[str, str] = Field(default_factory=dict)
    hierarchy: dict[str, list[str]] = Field(default_factory=dict)
    root_joint_ids: list[str] = Field(default_factory=list)
    source_format: str = "unknown"

    model_config = {"extra": "ignore"}


class ProjectMetadataSchema(BaseModel):
    """Schema for project metadata."""

    name: str = "Untitled"
    version: str = "1.0.0"
    created_at: str | None = None
    modified_at: str | None = None
    description: str = ""

    model_config = {"extra": "ignore"}


def validate_part_info(raw_data: dict[str, Any]) -> PartInfoSchema:
    """Validate part info data."""
    return PartInfoSchema.model_validate(raw_data)


def validate_skeleton_data(raw_data: dict[str, Any]) -> SkeletonDataSchema:
    """Validate skeleton data."""
    return SkeletonDataSchema.model_validate(raw_data)


def validate_project_metadata(raw_data: dict[str, Any]) -> ProjectMetadataSchema:
    """Validate project metadata."""
    return ProjectMetadataSchema.model_validate(raw_data)
