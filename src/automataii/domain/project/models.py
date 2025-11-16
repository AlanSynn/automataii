"""
Project domain models.

Pure Pydantic models for project data serialization/validation.
NO Qt dependencies allowed in this module.
"""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


@dataclass
class Part:
    """
    Domain entity for a character part.

    This is the runtime representation used by the application layer.
    NO Qt dependencies - pure Python types only.
    """

    name: str
    roi: list[float] | None = None
    image_path: str | None = None
    fill_color: str = "rgba(128,128,128,0.5)"
    z_value: float = 0.0
    fixed: bool = False
    opacity: float = 1.0
    group: str | None = None
    original_svg_path: str | None = None
    enhanced_svg_path: str | None = None
    effective_bbox_offset_x: float = 0.0
    effective_bbox_offset_y: float = 0.0
    show_anchor: bool = False
    local_pivot_offset: list[float] | None = None
    anchor_joint_id: str | None = None
    motion_path_points: list[tuple[float, float]] | None = None

    @property
    def x(self) -> float:
        """X position from ROI."""
        return self.roi[0] if self.roi and len(self.roi) >= 1 else 0.0

    @property
    def y(self) -> float:
        """Y position from ROI."""
        return self.roi[1] if self.roi and len(self.roi) >= 2 else 0.0

    @property
    def width(self) -> float:
        """Width from ROI."""
        return self.roi[2] if self.roi and len(self.roi) >= 3 else 0.0

    @property
    def height(self) -> float:
        """Height from ROI."""
        return self.roi[3] if self.roi and len(self.roi) >= 4 else 0.0

    @classmethod
    def from_model(cls, model: "PartInfoModel", resolved_image_path: str | None = None) -> "Part":
        """Create a Part from a PartInfoModel."""
        motion_points = None
        if model.motion_path_data and model.motion_path_data.path_points:
            motion_points = [p.to_tuple() for p in model.motion_path_data.path_points]

        return cls(
            name=model.name,
            roi=model.roi,
            image_path=resolved_image_path or model.image_path,
            fill_color=model.fill_color,
            z_value=model.z_value,
            fixed=model.fixed,
            opacity=model.opacity,
            group=model.group,
            original_svg_path=model.original_svg_path,
            enhanced_svg_path=model.enhanced_svg_path,
            effective_bbox_offset_x=model.effective_bbox_offset_x,
            effective_bbox_offset_y=model.effective_bbox_offset_y,
            show_anchor=model.show_anchor,
            local_pivot_offset=model.local_pivot_offset,
            anchor_joint_id=model.anchor_joint_id,
            motion_path_points=motion_points,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "roi": self.roi,
            "image_path": self.image_path,
            "fill_color": self.fill_color,
            "z_value": self.z_value,
            "fixed": self.fixed,
            "opacity": self.opacity,
            "group": self.group,
            "original_svg_path": self.original_svg_path,
            "enhanced_svg_path": self.enhanced_svg_path,
            "effective_bbox_offset_x": self.effective_bbox_offset_x,
            "effective_bbox_offset_y": self.effective_bbox_offset_y,
            "show_anchor": self.show_anchor,
            "local_pivot_offset": self.local_pivot_offset,
            "anchor_joint_id": self.anchor_joint_id,
            "motion_path_points": self.motion_path_points,
        }


class Point2DModel(BaseModel):
    """Represents a 2D point for serialization."""

    x: float
    y: float

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    @classmethod
    def from_tuple(cls, point: tuple[float, float]) -> "Point2DModel":
        return cls(x=point[0], y=point[1])


class MotionPathDataModel(BaseModel):
    """Motion path data for serialization."""

    path_points: list[Point2DModel] | None = None


class PartInfoModel(BaseModel):
    """Pydantic model for individual part data from project files."""

    name: str
    roi: list[float] | None = None
    z_value: float = 0.0
    image_path: str | None = None
    fill_color: str = "rgba(128,128,128,0.5)"
    fixed: bool = False
    opacity: float = 1.0
    group: str | None = None
    original_svg_path: str | None = None
    enhanced_svg_path: str | None = None
    effective_bbox_offset_x: float = 0.0
    effective_bbox_offset_y: float = 0.0
    motion_path_data: MotionPathDataModel | None = None
    show_anchor: bool = False
    local_pivot_offset: list[float] | None = Field(
        default=None,
        description="Local pivot offset [x, y] relative to the part's origin",
    )
    anchor_joint_id: str | None = Field(
        default=None,
        description="ID of the skeleton joint this part is anchored to",
    )


class SkeletonJointModel(BaseModel):
    """Pydantic model for skeleton joint data."""

    id: str
    name: str
    position: list[float]  # [x, y]
    parent: str | None = None
    color: list[int] | None = None  # [r, g, b, a]
    label_offset: list[float] | None = Field(None, alias="labelOffset")


class CharacterDataModel(BaseModel):
    """Pydantic model for character data in project files."""

    name: str
    parts: dict[str, PartInfoModel] = Field(default_factory=dict)
    skeleton_joints: list[SkeletonJointModel] = Field(
        default_factory=list, alias="skeleton"
    )


class ProjectMetadata(BaseModel):
    """Metadata for Automataii projects."""

    name: str
    description: str | None = None
    version: str = "1.0.0"
    created_at: str | None = None
    modified_at: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)


class ProjectFileModel(BaseModel):
    """Root Pydantic model for the entire project file."""

    character: CharacterDataModel
    metadata: ProjectMetadata | None = None
