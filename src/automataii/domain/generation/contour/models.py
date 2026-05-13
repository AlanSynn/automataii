"""
Manufacturing Contour models.

Pure data classes for contour representation.
"""

from __future__ import annotations

import math
from typing import Any, SupportsFloat, SupportsIndex, cast

import cv2
import numpy as np

_FloatPayload = str | bytes | bytearray | SupportsFloat | SupportsIndex


def _finite_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(cast(_FloatPayload, value))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _nonnegative_finite_float(value: object) -> float:
    return max(0.0, _finite_float(value, 0.0))


def _safe_contour_array(contour: np.ndarray) -> np.ndarray:
    try:
        array = np.asarray(contour, dtype=np.float32)
    except (TypeError, ValueError):
        return np.zeros((0, 1, 2), dtype=np.float32)
    if array.size == 0:
        return np.zeros((0, 1, 2), dtype=np.float32)
    try:
        points = array.reshape(-1, 2)
    except ValueError:
        return np.zeros((0, 1, 2), dtype=np.float32)
    finite_points = points[np.isfinite(points).all(axis=1)]
    if finite_points.size == 0:
        return np.zeros((0, 1, 2), dtype=np.float32)
    return finite_points.reshape(-1, 1, 2).astype(np.float32)


class ManufacturingContour:
    """Represents a manufacturing-precision contour with SVG path data."""

    def __init__(
        self,
        contour: np.ndarray,
        simplified_contour: np.ndarray,
        svg_path: str,
    ):
        self.contour = _safe_contour_array(contour)
        self.simplified_contour = _safe_contour_array(simplified_contour)
        self.svg_path = svg_path
        self.area: float = _nonnegative_finite_float(cv2.contourArea(self.contour))
        self.perimeter: float = _nonnegative_finite_float(cv2.arcLength(self.contour, True))
        if len(self.contour) == 0:
            bounding_rect = (0, 0, 0, 0)
        else:
            x, y, w, h = cv2.boundingRect(self.contour)
            bounding_rect = (x, y, max(0, w), max(0, h))
        self.bounding_rect: tuple[int, int, int, int] = bounding_rect
        # Optional: source image path for texture embedding
        self.source_image_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "svg_path": self.svg_path,
            "area": _nonnegative_finite_float(self.area),
            "perimeter": _nonnegative_finite_float(self.perimeter),
            "bounding_rect": list(self.bounding_rect),
            "source_image_path": self.source_image_path,
        }
