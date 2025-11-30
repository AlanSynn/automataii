"""
Project domain models.

Pure Pydantic models for project data serialization/validation.
NO Qt dependencies allowed in this module.
"""

from pydantic import BaseModel, Field


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
