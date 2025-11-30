"""
Manufacturing Contour models.

Pure data classes for contour representation.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


class ManufacturingContour:
    """Represents a manufacturing-precision contour with SVG path data."""

    def __init__(
        self,
        contour: np.ndarray,
        simplified_contour: np.ndarray,
        svg_path: str,
    ):
        self.contour = contour
        self.simplified_contour = simplified_contour
        self.svg_path = svg_path
        self.area: float = cv2.contourArea(contour)
        self.perimeter: float = cv2.arcLength(contour, True)
        x, y, w, h = cv2.boundingRect(contour)
        self.bounding_rect: tuple[int, int, int, int] = (x, y, w, h)
        # Optional: source image path for texture embedding
        self.source_image_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "svg_path": self.svg_path,
            "area": self.area,
            "perimeter": self.perimeter,
            "bounding_rect": list(self.bounding_rect),
            "source_image_path": self.source_image_path,
        }
