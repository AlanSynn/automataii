"""
Contour extraction for manufacturing blueprints.

Computer vision-based contour extraction from PNG files.
Uses OpenCV/NumPy - NO Qt or SVG dependencies.
"""

from automataii.domain.generation.contour.extractor import AdvancedContourExtractor
from automataii.domain.generation.contour.models import ManufacturingContour

__all__ = [
    "ManufacturingContour",
    "AdvancedContourExtractor",
]
