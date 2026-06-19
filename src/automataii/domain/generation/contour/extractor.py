"""
Advanced Contour Extractor using computer vision.

Pure domain logic using OpenCV/NumPy - NO Qt dependencies.
"""

from __future__ import annotations

import logging
import math
import os
import re
from typing import SupportsFloat, SupportsIndex, cast

import cv2
import numpy as np

from automataii.domain.generation.contour.models import ManufacturingContour

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


def _nonnegative_finite_float(value: object, default: float) -> float:
    result = _finite_float(value, default)
    return result if result >= 0.0 else default


def _as_uint8_mask(mask: np.ndarray) -> np.ndarray:
    if mask.dtype == np.uint8:
        return mask
    try:
        numeric_mask = mask.astype(np.float64, copy=False)
    except (TypeError, ValueError):
        return np.zeros(mask.shape, dtype=np.uint8)
    finite = np.nan_to_num(numeric_mask, nan=0.0, posinf=255.0, neginf=0.0)
    return np.clip(finite, 0.0, 255.0).astype(np.uint8)


class AdvancedContourExtractor:
    """Computer vision-based contour extraction from PNG files."""

    def __init__(self, tolerance: float = 2.0, min_area: float = 100.0):
        """
        Initialize the contour extractor.

        Args:
            tolerance: Douglas-Peucker simplification tolerance
            min_area: Minimum contour area to consider (filters noise)
        """
        self.tolerance = _nonnegative_finite_float(tolerance, 2.0)
        self.min_area = _nonnegative_finite_float(min_area, 100.0)
        self.logger = logging.getLogger(__name__)

    def extract_manufacturing_contours(self, png_path: str) -> list[ManufacturingContour]:
        """
        Extract manufacturing-precision contours from PNG file.

        Args:
            png_path: Path to PNG file with alpha channel

        Returns:
            List of ManufacturingContour objects
        """
        if not isinstance(png_path, str | bytes | os.PathLike):
            self.logger.error("PNG path must be path-like, got %r", png_path)
            return []
        if not os.path.exists(png_path):
            self.logger.error(f"PNG file not found: {png_path}")
            return []

        try:
            # 1. Load PNG with alpha channel
            image = cv2.imread(png_path, cv2.IMREAD_UNCHANGED)
            if image is None:
                self.logger.error(f"Failed to load image: {png_path}")
                return []

            # Handle different image formats
            alpha_mask = self._extract_alpha_mask(image)
            if alpha_mask is None:
                self.logger.error(f"Unsupported image format: {image.shape}")
                return []

            # 2. Apply edge detection and preprocessing
            processed_mask = self._preprocess_mask(alpha_mask)

            # 3. Find contours using cv2.findContours with RETR_EXTERNAL
            contours, _ = cv2.findContours(
                processed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            # 4. Process and simplify contours
            manufacturing_contours: list[ManufacturingContour] = []
            for contour in contours:
                # Filter by area
                area = cv2.contourArea(contour)
                if area < self.min_area:
                    continue

                # 5. Simplify contours using Douglas-Peucker algorithm
                epsilon = _nonnegative_finite_float(self.tolerance, 2.0)
                simplified_contour = cv2.approxPolyDP(contour, epsilon, True)

                # 6. Convert to manufacturing-precision SVG paths
                svg_path = self._contour_to_svg_path(simplified_contour)

                manufacturing_contour = ManufacturingContour(contour, simplified_contour, svg_path)
                manufacturing_contours.append(manufacturing_contour)

            self.logger.info(f"Extracted {len(manufacturing_contours)} contours from {png_path}")
            return manufacturing_contours

        except Exception as e:
            self.logger.error(f"Error extracting contours from {png_path}: {e}")
            return []

    def extract_manufacturing_contours_from_alpha_mask(
        self, alpha_mask: np.ndarray
    ) -> list[ManufacturingContour]:
        """Extract manufacturing contours from an already-loaded alpha mask.

        The editor renders ``CharacterPartItem`` from its current pixmap, not
        necessarily from a pristine file on disk.  Blueprint export can pass
        that pixmap's alpha mask here so the cut sheet follows the same visible
        shape the user sees in the editor.
        """
        if not isinstance(alpha_mask, np.ndarray) or alpha_mask.size == 0:
            return []

        try:
            processed_mask = self._preprocess_mask(alpha_mask)
            contours, _ = cv2.findContours(
                processed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            manufacturing_contours: list[ManufacturingContour] = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self.min_area:
                    continue
                epsilon = _nonnegative_finite_float(self.tolerance, 2.0)
                simplified_contour = cv2.approxPolyDP(contour, epsilon, True)
                svg_path = self._contour_to_svg_path(simplified_contour)
                manufacturing_contours.append(
                    ManufacturingContour(contour, simplified_contour, svg_path)
                )
            return manufacturing_contours
        except Exception as e:
            self.logger.error("Error extracting contours from alpha mask: %s", e)
            return []

    def _extract_alpha_mask(self, image: np.ndarray) -> np.ndarray | None:
        """Extract alpha mask from image based on format."""
        if not isinstance(image, np.ndarray) or image.size == 0:
            return None
        if len(image.shape) == 2:
            # Grayscale image
            return _as_uint8_mask(image)
        elif len(image.shape) < 3:
            # Invalid image format (1D array or similar)
            return None
        elif image.shape[2] == 3:
            # RGB image - create mask from non-background pixels
            gray = cv2.cvtColor(_as_uint8_mask(image), cv2.COLOR_BGR2GRAY)

            # Use adaptive thresholding for better edge detection
            alpha_mask = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )

            # Alternative: use Otsu's method for automatic threshold
            _, otsu_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Combine both methods for robust segmentation
            alpha_mask = cv2.bitwise_or(alpha_mask, otsu_mask)

            # Remove potential background noise
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            alpha_mask = cv2.morphologyEx(alpha_mask, cv2.MORPH_OPEN, kernel)
            alpha_mask = cv2.morphologyEx(alpha_mask, cv2.MORPH_CLOSE, kernel)
            return alpha_mask
        elif image.shape[2] == 4:
            # RGBA image - use alpha channel
            return _as_uint8_mask(image[:, :, 3])
        return None

    def _preprocess_mask(self, alpha_mask: np.ndarray) -> np.ndarray:
        """
        Preprocess alpha mask for optimal contour detection.
        Applies Canny edge detection and adaptive thresholding.
        """
        # Ensure binary mask
        if not isinstance(alpha_mask, np.ndarray) or alpha_mask.size == 0 or alpha_mask.ndim < 2:
            return np.zeros((1, 1), dtype=np.uint8)
        if len(alpha_mask.shape) > 2:
            alpha_mask = alpha_mask[:, :, 0]
        alpha_mask = _as_uint8_mask(alpha_mask)

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(alpha_mask, (5, 5), 0)

        # Apply adaptive thresholding for better edge detection
        _, binary_mask = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)

        # Apply morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        cleaned = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        # For better contour detection, use the cleaned binary mask directly
        edges = cleaned

        # Optional: Apply Canny edge detection for outline-based detection
        canny_edges = cv2.Canny(cleaned, 50, 150)

        # Combine both approaches
        edges = cv2.bitwise_or(edges, canny_edges)

        # Dilate edges slightly to ensure connected contours
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        edges = cv2.dilate(edges, dilate_kernel, iterations=1)

        return edges

    def _contour_to_svg_path(self, contour: np.ndarray) -> str:
        """
        Convert OpenCV contour to SVG path data string.

        Args:
            contour: OpenCV contour array

        Returns:
            SVG path data string

        Performance: Uses list comprehension + join instead of string concatenation
        for O(N) vs O(N²) complexity.
        """
        if not isinstance(contour, np.ndarray) or contour.size == 0 or contour.ndim == 0:
            return ""

        try:
            points = np.asarray(contour, dtype=float).reshape(-1, 2)
        except (TypeError, ValueError):
            return ""
        finite_points = points[np.isfinite(points).all(axis=1)]
        if finite_points.size == 0:
            return ""

        # OPTIMIZATION: Use list + join instead of string concatenation
        # String concatenation in Python is O(N²) due to immutable strings
        # List append + join is O(N)
        parts = []

        # Start with MoveTo command
        first_point = finite_points[0]
        parts.append(f"M {first_point[0]:.2f} {first_point[1]:.2f}")

        # Add LineTo commands for each subsequent point using list comprehension
        parts.extend(
            f"L {finite_points[i][0]:.2f} {finite_points[i][1]:.2f}"
            for i in range(1, len(finite_points))
        )

        # Close the path
        parts.append("Z")

        return " ".join(parts)

    def apply_offset_to_path(self, svg_path: str, offset_x: float, offset_y: float) -> str:
        """Apply offset to SVG path coordinates."""
        if not isinstance(svg_path, str) or not svg_path:
            return ""
        offset_x = _finite_float(offset_x, 0.0)
        offset_y = _finite_float(offset_y, 0.0)

        def offset_coords(match: re.Match[str]) -> str:
            command = match.group(1)
            x = _finite_float(match.group(2), math.nan) + offset_x
            y = _finite_float(match.group(3), math.nan) + offset_y
            if not math.isfinite(x) or not math.isfinite(y):
                return match.group(0)
            return f"{command} {x:.2f} {y:.2f}"

        # Match coordinate patterns like "M 123.45 67.89" or "L 123.45 67.89"
        offset_path = _SVG_COORD_PATTERN.sub(offset_coords, svg_path)

        return offset_path

    # Backward compatibility alias
    def _apply_offset_to_path(self, svg_path: str, offset_x: float, offset_y: float) -> str:
        """Alias for apply_offset_to_path for backward compatibility."""
        return self.apply_offset_to_path(svg_path, offset_x, offset_y)
