"""
Animation domain layer.

This module provides animation processing and body part extraction.
"""

from automataii.domain.animation.arap import ARAP
from automataii.domain.animation.body_parts_extractor import (
    BodyPartsExtractor,
    FastSkeletonSegmenter,
)
from automataii.domain.animation.image_to_annotations import (
    AnnotationResults,
    ONNXImageProcessor,
)

__all__ = [
    "ARAP",
    "BodyPartsExtractor",
    "FastSkeletonSegmenter",
    "AnnotationResults",
    "ONNXImageProcessor",
]
