"""
Animation domain layer.

This module provides animation processing and body part extraction.

Performance:
    - AcceleratedARAP: 2-10x faster ARAP with auto-backend selection
    - Use AUTOMATAII_USE_ACCELERATED_ARAP=0 to disable acceleration
"""

from automataii.domain.animation.body_parts_extractor import BodyPartsExtractor

__all__ = [
    "BodyPartsExtractor",
]
