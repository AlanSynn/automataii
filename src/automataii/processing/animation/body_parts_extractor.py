"""
Body parts extractor module - backward compatibility wrapper.

This module provides backward compatibility by importing from the refactored structure.
"""

# Import main class for backward compatibility
from .parts_extraction import BodyPartsExtractor

# Import other classes that might be used externally
from .parts_extraction.segmentation import SkeletonSegmenter as FastSkeletonSegmenter
from .parts_extraction.models import (
    PartInfo,
    ExtractionResult,
    CharacterData,
    AnimationInfo
)

# For command-line usage
from .body_parts_extractor_refactored import main

__all__ = [
    "BodyPartsExtractor",
    "FastSkeletonSegmenter",
    "PartInfo",
    "ExtractionResult",
    "CharacterData",
    "AnimationInfo",
    "main"
]

if __name__ == "__main__":
    main()