"""Computational geometry service for mechanism design.

Pure mathematical operations on 2D points and paths.
No dependencies on graphics libraries (PyQt, etc.).

All operations use tuple[float, float] for points to maintain immutability.
"""

from __future__ import annotations

import logging
import math
from typing import Protocol

from .types import BoundingBox, PathPoints, Point2D

logger = logging.getLogger(__name__)

# Epsilon for floating-point comparisons to avoid precision issues
_EPSILON = 1e-10

__all__ = ["GeometryMathProtocol", "GeometryMathService"]


class GeometryMathProtocol(Protocol):
    """Protocol for computational geometry operations.

    All operations are pure functions with no side effects.
    """

    def compute_bounding_box(self, points: PathPoints) -> BoundingBox:
        """Compute axis-aligned bounding box.

        Args:
            points: Sequence of (x, y) tuples

        Returns:
            BoundingBox containing all points

        Raises:
            ValueError: If points is empty

        Complexity: O(N) where N = number of points
        """
        ...

    def normalize_path(self, points: PathPoints, target_size: float = 1.0) -> PathPoints:
        """Normalize path to unit square [0, target_size].

        Centers path at origin and scales to fit within square.

        Args:
            points: Path points
            target_size: Size of normalization square

        Returns:
            Normalized path points

        Complexity: O(N)
        """
        ...

    def transform_point(
        self,
        point: Point2D,
        translation: Point2D = (0.0, 0.0),
        scale: float = 1.0,
        rotation_rad: float = 0.0,
    ) -> Point2D:
        """Apply affine transformation to point.

        Order: rotate → scale → translate

        Args:
            point: Input point
            translation: Translation vector
            scale: Scale factor
            rotation_rad: Rotation angle in radians

        Returns:
            Transformed point

        Complexity: O(1)
        """
        ...

    def compute_path_length(self, points: PathPoints) -> float:
        """Compute total path length (sum of segment lengths).

        Args:
            points: Path points

        Returns:
            Total length

        Complexity: O(N)
        """
        ...

    def resample_path(self, points: PathPoints, num_samples: int) -> PathPoints:
        """Resample path to uniform spacing.

        Uses linear interpolation between points.

        Args:
            points: Original path
            num_samples: Desired number of points

        Returns:
            Resampled path with num_samples points

        Complexity: O(N * M) where M = num_samples
        """
        ...


class GeometryMathService:
    """Pure computational geometry implementation.

    All methods are static/pure functions with no internal state.
    """

    def compute_bounding_box(self, points: PathPoints) -> BoundingBox:
        """Compute axis-aligned bounding box.

        Complexity: O(N)
        """
        if not points:
            raise ValueError("Cannot compute bounding box of empty point set")

        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]

        return BoundingBox(
            min_x=min(x_coords), min_y=min(y_coords), max_x=max(x_coords), max_y=max(y_coords)
        )

    def normalize_path(self, points: PathPoints, target_size: float = 1.0) -> PathPoints:
        """Normalize path to unit square [0, target_size].

        Complexity: O(N)
        """
        if not points:
            return points

        bbox = self.compute_bounding_box(points)

        # Handle degenerate case (single point or line)
        if bbox.width < _EPSILON and bbox.height < _EPSILON:
            # Single point: center at (target_size/2, target_size/2)
            center = target_size / 2
            return tuple((center, center) for _ in points)

        # Compute scale factor (uniform scaling)
        max_dim = max(bbox.width, bbox.height)
        if max_dim < _EPSILON:
            logger.debug(f"normalize_path: max_dim too small ({max_dim}), using scale=1.0")
            scale = 1.0
        else:
            scale = target_size / max_dim

        # Compute translation to center
        center_x, center_y = bbox.center
        target_center = target_size / 2

        # Apply transformation: translate to origin → scale → translate to center
        normalized = []
        for x, y in points:
            # Translate to origin
            nx = (x - center_x) * scale
            ny = (y - center_y) * scale
            # Translate to target center
            nx += target_center
            ny += target_center
            normalized.append((nx, ny))

        return tuple(normalized)

    def transform_point(
        self,
        point: Point2D,
        translation: Point2D = (0.0, 0.0),
        scale: float = 1.0,
        rotation_rad: float = 0.0,
    ) -> Point2D:
        """Apply affine transformation to point.

        Order: rotate → scale → translate

        Complexity: O(1)
        """
        x, y = point

        # Rotate
        if rotation_rad != 0.0:
            cos_theta = math.cos(rotation_rad)
            sin_theta = math.sin(rotation_rad)
            x_rot = x * cos_theta - y * sin_theta
            y_rot = x * sin_theta + y * cos_theta
            x, y = x_rot, y_rot

        # Scale
        x *= scale
        y *= scale

        # Translate
        x += translation[0]
        y += translation[1]

        return (x, y)

    def compute_path_length(self, points: PathPoints) -> float:
        """Compute total path length.

        Complexity: O(N)
        """
        if len(points) < 2:
            return 0.0

        total_length = 0.0
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            dx = x2 - x1
            dy = y2 - y1
            total_length += math.sqrt(dx * dx + dy * dy)

        return total_length

    def resample_path(self, points: PathPoints, num_samples: int) -> PathPoints:
        """Resample path to uniform spacing.

        Complexity: O(N * M) where M = num_samples
        """
        if not points:
            return points

        if num_samples <= 0:
            raise ValueError(f"num_samples must be positive, got {num_samples}")

        if num_samples == 1:
            # Return midpoint
            bbox = self.compute_bounding_box(points)
            return (bbox.center,)

        if len(points) == 1:
            # Single point: duplicate it
            return tuple(points[0] for _ in range(num_samples))

        # Compute cumulative arc length
        total_length = self.compute_path_length(points)

        if total_length < _EPSILON:
            # Degenerate path (all points same or very close): return duplicates
            logger.debug(f"resample_path: total_length too small ({total_length}), returning duplicates")
            return tuple(points[0] for _ in range(num_samples))

        # Build cumulative length array
        cumulative_lengths = [0.0]
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            dx = x2 - x1
            dy = y2 - y1
            segment_length = math.sqrt(dx * dx + dy * dy)
            cumulative_lengths.append(cumulative_lengths[-1] + segment_length)

        # Sample at uniform arc length intervals
        resampled = []
        for i in range(num_samples):
            # Target arc length
            target_length = (i / (num_samples - 1)) * total_length

            # Find segment containing target_length
            segment_idx = 0
            for j in range(len(cumulative_lengths) - 1):
                if cumulative_lengths[j] <= target_length <= cumulative_lengths[j + 1]:
                    segment_idx = j
                    break

            # Interpolate within segment
            if segment_idx >= len(points) - 1:
                # Edge case: at end
                resampled.append(points[-1])
            else:
                seg_start_length = cumulative_lengths[segment_idx]
                seg_end_length = cumulative_lengths[segment_idx + 1]
                seg_length = seg_end_length - seg_start_length

                if seg_length < _EPSILON:
                    # Degenerate segment (points very close)
                    resampled.append(points[segment_idx])
                else:
                    # Linear interpolation
                    t = (target_length - seg_start_length) / seg_length
                    x1, y1 = points[segment_idx]
                    x2, y2 = points[segment_idx + 1]
                    x = x1 + t * (x2 - x1)
                    y = y1 + t * (y2 - y1)
                    resampled.append((x, y))

        return tuple(resampled)

    def compute_distance(self, p1: Point2D, p2: Point2D) -> float:
        """Compute Euclidean distance between two points.

        Complexity: O(1)
        """
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        return math.sqrt(dx * dx + dy * dy)

    def compute_path_error_rms(self, target: PathPoints, generated: PathPoints) -> float:
        """Compute RMS error between two paths.

        Paths must have same number of points.

        Args:
            target: Target path
            generated: Generated path

        Returns:
            RMS error

        Raises:
            ValueError: If paths have different lengths

        Complexity: O(N)
        """
        if len(target) != len(generated):
            raise ValueError(
                f"Path length mismatch: target={len(target)}, generated={len(generated)}"
            )

        if not target:
            return 0.0

        sum_squared_error = 0.0
        for pt, pg in zip(target, generated, strict=False):
            dist = self.compute_distance(pt, pg)
            sum_squared_error += dist * dist

        # Safety check for numerical stability
        mean_squared_error = sum_squared_error / len(target)
        if mean_squared_error < 0:
            logger.warning(f"compute_path_error_rms: negative MSE ({mean_squared_error}), returning 0")
            return 0.0
        return math.sqrt(mean_squared_error)
