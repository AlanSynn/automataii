"""
Animation domain layer.

This module provides animation processing and body part extraction.

Performance:
    - AcceleratedARAP: 2-10x faster ARAP with auto-backend selection
    - Use AUTOMATAII_USE_ACCELERATED_ARAP=0 to disable acceleration
"""

from automataii.domain.animation.arap import ARAP
from automataii.domain.animation.arap_accelerated import (
    AcceleratedARAP,
    batch_transform_points,
    compute_rotation_matrices,
    get_backend,
)
from automataii.domain.animation.body_parts_extractor import (
    BodyPartsExtractor,
    FastSkeletonSegmenter,
)
from automataii.domain.animation.image_to_annotations import (
    AnnotationResults,
    ONNXImageProcessor,
)

__all__ = [
    # ARAP solvers
    "ARAP",
    "AcceleratedARAP",
    # Accelerated functions
    "compute_rotation_matrices",
    "batch_transform_points",
    "get_backend",
    # Body parts
    "BodyPartsExtractor",
    "FastSkeletonSegmenter",
    # Image processing
    "AnnotationResults",
    "ONNXImageProcessor",
]
