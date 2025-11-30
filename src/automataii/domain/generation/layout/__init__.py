"""
Layout algorithms for blueprint generation.

Pure Python/NumPy implementations - NO Qt or SVG dependencies.
"""

from automataii.domain.generation.layout.scale_normalizer import ScaleNormalizer
from automataii.domain.generation.layout.layout_manager import (
    LayoutItem,
    ScaledBounds,
    SmartLayoutManager,
)

__all__ = [
    "ScaleNormalizer",
    "SmartLayoutManager",
    "LayoutItem",
    "ScaledBounds",
]
