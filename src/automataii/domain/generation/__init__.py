"""
Domain Generation Module.

Pure domain logic for blueprint layout and contour extraction.
NO Qt or SVG dependencies allowed in this module.

Submodules:
- layout: Scale normalization and layout algorithms
- contour: Computer vision contour extraction
"""

from automataii.domain.generation.contour import (
    AdvancedContourExtractor,
    ManufacturingContour,
)
from automataii.domain.generation.layout import (
    LayoutItem,
    ScaleNormalizer,
    SmartLayoutManager,
)

__all__ = [
    # Layout
    "ScaleNormalizer",
    "SmartLayoutManager",
    "LayoutItem",
    # Contour
    "AdvancedContourExtractor",
    "ManufacturingContour",
]
