"""
Project domain models.

Pure Pydantic models for project data representation.
NO Qt dependencies allowed in this module.
"""

from automataii.domain.project.models import (
    CharacterDataModel,
    MotionPathDataModel,
    PartInfoModel,
    Point2DModel,
    ProjectFileModel,
    ProjectMetadata,
    SkeletonJointModel,
)

__all__ = [
    "Point2DModel",
    "MotionPathDataModel",
    "PartInfoModel",
    "SkeletonJointModel",
    "CharacterDataModel",
    "ProjectMetadata",
    "ProjectFileModel",
]
