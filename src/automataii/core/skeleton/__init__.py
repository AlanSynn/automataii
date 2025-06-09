"""
Skeleton management package for Automataii.

This package provides modular components for managing skeleton data,
including data models, format conversion, joint management, and operations.
"""

from .models import StandardizedJointModel, StandardizedSkeletonModel
from .manager import SkeletonManager
from .format_converter import SkeletonFormatConverter
from .joint_manager import JointManager
from .hierarchy_manager import HierarchyManager
from .operations import SkeletonOperations
from .serializer import SkeletonSerializer

__all__ = [
    "StandardizedJointModel",
    "StandardizedSkeletonModel",
    "SkeletonManager",
    "SkeletonFormatConverter",
    "JointManager",
    "HierarchyManager",
    "SkeletonOperations",
    "SkeletonSerializer",
]