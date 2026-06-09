"""
ImageProcessingTab extracted components.

This package contains modules extracted from ImageProcessingTab
using the LLM-native refactoring approach.

Extracted Modules:
- ManualSegmentationHandler: Manual segmentation workflow and part generation
- SkeletonToolsHandler: Skeleton extension and joint locking operations
"""

from automataii.presentation.qt.tabs.image_processing.components.manual_segmentation_handler import (
    ManualSegmentationHandler,
)
from automataii.presentation.qt.tabs.image_processing.components.skeleton_tools_handler import (
    SkeletonToolsHandler,
)

__all__ = [
    "ManualSegmentationHandler",
    "SkeletonToolsHandler",
]
