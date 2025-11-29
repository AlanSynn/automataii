"""
Scale Normalizer for manufacturing blueprints.

Normalizes character parts to standard real-world dimensions.
Pure Python implementation - NO Qt or SVG dependencies.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automataii.domain.generation.contour import ManufacturingContour


class ScaleNormalizer:
    """
    Normalizes character parts to standard 30cm height.
    Pure domain logic for scale calculations.
    """

    def __init__(self, target_character_height_mm: float = 300.0):
        """
        Initialize scale normalizer.

        Args:
            target_character_height_mm: Target character height in millimeters (default: 30cm)
        """
        self.target_height_mm = target_character_height_mm
        self.logger = logging.getLogger(__name__)

    def calculate_scale_factor(self, original_height_pixels: float) -> float:
        """
        Calculate scale factor to convert pixels to target real-world size.

        Args:
            original_height_pixels: Original character height in pixels

        Returns:
            Scale factor (mm per pixel)
        """
        if original_height_pixels <= 0:
            self.logger.warning("Invalid original height, using default scale")
            return 0.36  # Default: ~0.36mm per pixel for reasonable sizing

        scale_factor = self.target_height_mm / original_height_pixels
        self.logger.info(
            f"Calculated scale factor: {scale_factor:.3f} mm/pixel "
            f"(target: {self.target_height_mm}mm)"
        )
        return scale_factor

    def normalize_contour(
        self, contour: ManufacturingContour, scale_factor: float
    ) -> ManufacturingContour:
        """Normalize a manufacturing contour to real-world scale."""
        from automataii.domain.generation.contour import ManufacturingContour as MC

        # Scale the bounding rect
        x, y, w, h = contour.bounding_rect
        new_x = x * scale_factor
        new_y = y * scale_factor
        new_w = w * scale_factor
        new_h = h * scale_factor

        # Scale the SVG path
        scaled_svg_path = self._scale_svg_path(contour.svg_path, scale_factor)

        # Create new contour with scaled properties
        scaled_contour = MC(
            contour=contour.contour,  # Keep original for reference
            simplified_contour=contour.simplified_contour,  # Keep original
            svg_path=scaled_svg_path,
        )

        # Update scaled properties
        scaled_contour.area = contour.area * (scale_factor**2)
        scaled_contour.perimeter = contour.perimeter * scale_factor
        scaled_contour.bounding_rect = (int(new_x), int(new_y), int(new_w), int(new_h))

        # Preserve source image path for texture embedding if available
        if hasattr(contour, "source_image_path"):
            scaled_contour.source_image_path = contour.source_image_path

        return scaled_contour

    def _scale_svg_path(self, svg_path: str, scale_factor: float) -> str:
        """Scale coordinates in SVG path data."""

        def scale_coords(match: re.Match[str]) -> str:
            command = match.group(1)
            x = float(match.group(2)) * scale_factor
            y = float(match.group(3)) * scale_factor
            return f"{command} {x:.2f} {y:.2f}"

        # Scale coordinate patterns
        pattern = r"([ML]) ([\d\.-]+) ([\d\.-]+)"
        scaled_path = re.sub(pattern, scale_coords, svg_path)

        return scaled_path
