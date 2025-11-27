"""
Shared utility functions for cross-module operations.

Contains common utilities used across presentation and application layers.
"""
from __future__ import annotations

import math
from typing import Sequence

from automataii.shared.types import Coordinate, Point2D


def distance(p1: Point2D, p2: Point2D) -> float:
    """
    Calculate Euclidean distance between two points.

    Time Complexity: O(1)
    """
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def midpoint(p1: Point2D, p2: Point2D) -> Point2D:
    """
    Calculate midpoint between two points.

    Time Complexity: O(1)
    """
    return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)


def centroid(points: Sequence[Point2D]) -> Point2D:
    """
    Calculate centroid of a set of points.

    Time Complexity: O(n) where n = number of points
    """
    if not points:
        return (0.0, 0.0)
    x_sum = sum(p[0] for p in points)
    y_sum = sum(p[1] for p in points)
    n = len(points)
    return (x_sum / n, y_sum / n)


def normalize_angle(angle: float) -> float:
    """
    Normalize angle to [0, 360) range.

    Time Complexity: O(1)
    """
    return angle % 360.0


def degrees_to_radians(degrees: float) -> float:
    """Convert degrees to radians."""
    return math.radians(degrees)


def radians_to_degrees(radians: float) -> float:
    """Convert radians to degrees."""
    return math.degrees(radians)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp value to specified range.

    Time Complexity: O(1)
    """
    return max(min_val, min(value, max_val))


def lerp(a: float, b: float, t: float) -> float:
    """
    Linear interpolation between two values.

    Args:
        a: Start value
        b: End value
        t: Interpolation factor [0, 1]

    Time Complexity: O(1)
    """
    return a + (b - a) * clamp(t, 0.0, 1.0)


def lerp_point(p1: Point2D, p2: Point2D, t: float) -> Point2D:
    """
    Linear interpolation between two points.

    Time Complexity: O(1)
    """
    return (lerp(p1[0], p2[0], t), lerp(p1[1], p2[1], t))


__all__ = [
    "distance",
    "midpoint",
    "centroid",
    "normalize_angle",
    "degrees_to_radians",
    "radians_to_degrees",
    "clamp",
    "lerp",
    "lerp_point",
]
