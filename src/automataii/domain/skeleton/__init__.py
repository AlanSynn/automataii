"""
Skeleton domain models.

Pure Pydantic models for skeleton representation.
NO Qt dependencies allowed in this module.
"""

from automataii.domain.skeleton.constants import (
    JOINT_CONNECTIONS,
    SKELETON_JOINTS,
)
from automataii.domain.skeleton.models import (
    StandardizedJointModel,
    StandardizedSkeletonModel,
)

__all__ = [
    "StandardizedJointModel",
    "StandardizedSkeletonModel",
    "SKELETON_JOINTS",
    "JOINT_CONNECTIONS",
]
