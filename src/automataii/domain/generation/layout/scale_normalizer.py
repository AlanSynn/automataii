"""
Scale Normalizer for manufacturing blueprints.

Normalizes character parts to standard real-world dimensions.
Pure Python implementation - NO Qt or SVG dependencies.
"""

from __future__ import annotations

import logging
import math
import re
from typing import TYPE_CHECKING, SupportsFloat, SupportsIndex, cast

from automataii.shared.physical_kit import LETTER_PAGE_HEIGHT_MM

if TYPE_CHECKING:
    from automataii.domain.generation.contour import ManufacturingContour

_FloatPayload = str | bytes | bytearray | SupportsFloat | SupportsIndex
_SVG_COORD_PATTERN = re.compile(
    r"([ML])\s+([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
    r"[\s,]+([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
)


def _finite_float(value: object, default: float) -> float:
    try:
        result = float(cast(_FloatPayload, value))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _positive_finite_float(value: object, default: float) -> float:
    result = _finite_float(value, default)
    return result if result > 0.0 else default


def _safe_int(value: object) -> int:
    return int(round(_finite_float(value, 0.0)))


class ScaleNormalizer:
    """
    Normalizes character parts to Letter-page physical height.
    Pure domain logic for scale calculations.
    """

    def __init__(self, target_character_height_mm: float = LETTER_PAGE_HEIGHT_MM):
        """
        Initialize scale normalizer.

        Args:
            target_character_height_mm: Target character height in millimeters
                (default: Letter page height)
        """
        self.target_height_mm = _positive_finite_float(
            target_character_height_mm,
            LETTER_PAGE_HEIGHT_MM,
        )
        self.logger = logging.getLogger(__name__)

    def calculate_scale_factor(self, original_height_pixels: float) -> float:
        """
        Calculate scale factor to convert pixels to target real-world size.

        Args:
            original_height_pixels: Original character height in pixels

        Returns:
            Scale factor (mm per pixel)
        """
        original_height_pixels = _finite_float(original_height_pixels, 0.0)
        if original_height_pixels <= 0:
            self.logger.warning("Invalid original height, using default scale")
            return 0.36  # Default: ~0.36mm per pixel for reasonable sizing

        scale_factor = self.target_height_mm / original_height_pixels
        if not math.isfinite(scale_factor) or scale_factor <= 0.0:
            self.logger.warning("Invalid scale factor, using default scale")
            return 0.36
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
        scale_factor = _positive_finite_float(scale_factor, 1.0)
        x, y, w, h = contour.bounding_rect
        new_x = x * scale_factor
        new_y = y * scale_factor
        new_w = max(0.0, w * scale_factor)
        new_h = max(0.0, h * scale_factor)

        # Scale the SVG path
        scaled_svg_path = self._scale_svg_path(contour.svg_path, scale_factor)

        # Create new contour with scaled properties
        scaled_contour = MC(
            contour=contour.contour,  # Keep original for reference
            simplified_contour=contour.simplified_contour,  # Keep original
            svg_path=scaled_svg_path,
        )

        # Update scaled properties
        scaled_contour.area = max(0.0, _finite_float(contour.area, 0.0) * (scale_factor**2))
        scaled_contour.perimeter = max(0.0, _finite_float(contour.perimeter, 0.0) * scale_factor)
        scaled_contour.bounding_rect = (
            _safe_int(new_x),
            _safe_int(new_y),
            _safe_int(new_w),
            _safe_int(new_h),
        )

        # Preserve source image path for texture embedding if available
        if hasattr(contour, "source_image_path"):
            scaled_contour.source_image_path = contour.source_image_path
        if hasattr(contour, "source_image_data_uri"):
            scaled_contour.source_image_data_uri = contour.source_image_data_uri
        if hasattr(contour, "source_image_size_px"):
            scaled_contour.source_image_size_px = contour.source_image_size_px
            try:
                source_w, source_h = contour.source_image_size_px
                scaled_contour.source_image_size_mm = (
                    _positive_finite_float(source_w, 0.0) * scale_factor,
                    _positive_finite_float(source_h, 0.0) * scale_factor,
                )
            except (TypeError, ValueError):
                pass
        if hasattr(contour, "coordinate_space"):
            scaled_contour.coordinate_space = contour.coordinate_space

        return scaled_contour

    def _scale_svg_path(self, svg_path: str, scale_factor: float) -> str:
        """Scale coordinates in SVG path data."""
        if not isinstance(svg_path, str) or not svg_path:
            return ""
        scale_factor = _positive_finite_float(scale_factor, 1.0)

        def scale_coords(match: re.Match[str]) -> str:
            command = match.group(1)
            x = _finite_float(match.group(2), math.nan) * scale_factor
            y = _finite_float(match.group(3), math.nan) * scale_factor
            if not math.isfinite(x) or not math.isfinite(y):
                return match.group(0)
            return f"{command} {x:.2f} {y:.2f}"

        # Scale coordinate patterns
        scaled_path = _SVG_COORD_PATTERN.sub(scale_coords, svg_path)

        return scaled_path
