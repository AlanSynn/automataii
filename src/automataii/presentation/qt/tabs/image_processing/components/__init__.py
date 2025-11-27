"""
ImageProcessingTab extracted components.

This package contains modules extracted from ImageProcessingTab
using the LLM-native refactoring approach.

Extracted Modules:
- ManualSegmentationHandler: Manual segmentation workflow and part generation
- ImageSkeletonLoader: Image and skeleton data loading operations
"""
from automataii.presentation.qt.tabs.image_processing.components.manual_segmentation_handler import (
    ManualSegmentationHandler,
)

__all__ = [
    "ManualSegmentationHandler",
]
