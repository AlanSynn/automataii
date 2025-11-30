"""
Skeleton domain models.

Pure Pydantic models for skeleton representation.
NO Qt dependencies allowed in this module.
"""

from automataii.domain.skeleton.models import (
    StandardizedJointModel,
    StandardizedSkeletonModel,
)
from automataii.domain.skeleton.constants import (
    SKELETON_JOINTS,
    JOINT_CONNECTIONS,
)

__all__ = [
    "StandardizedJointModel",
    "StandardizedSkeletonModel",
    "SKELETON_JOINTS",
    "JOINT_CONNECTIONS",
]
