"""
Path Geometry Utilities - Mathematical path creation functions.

Extracted from EditorTab. Pure functions for path creation and interpolation.

Design Pattern: Utility Module (stateless mathematical operations)
"""

from __future__ import annotations

import math

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath


def create_raw_path(points: list[QPointF], closed: bool = True) -> QPainterPath:
    """
    Create a path using raw points connected by straight lines.

    Args:
        points: List of path points
        closed: Whether to close the path

    Returns:
        QPainterPath with straight line segments

    Time Complexity: O(n) where n = number of points
    """
    path = QPainterPath()
    if points:
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        if closed and len(points) > 2:
            path.lineTo(points[0])
    return path


def create_perfect_ellipse_path(points: list[QPointF]) -> QPainterPath:
    """
    Create a perfect ellipse optimized for the original points' distribution and orientation.

    Uses PCA (Principal Component Analysis) to find the optimal ellipse orientation
    and size that best fits the given points.

    Args:
        points: List of sample points to fit

    Returns:
        QPainterPath representing an optimized ellipse

    Time Complexity: O(n) where n = number of points
    """
    if not points:
        return QPainterPath()

    # Convert points to numpy array
    coords = np.array([[p.x(), p.y()] for p in points])

    # Calculate center (centroid)
    center = np.mean(coords, axis=0)
    center_x, center_y = center[0], center[1]

    # Center the points
    centered_coords = coords - center

    # Calculate covariance matrix to find principal axes
    cov_matrix = np.cov(centered_coords.T)

    # Find eigenvalues and eigenvectors (principal components)
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

    # Sort by magnitude (largest first)
    sorted_indices = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[sorted_indices]
    eigenvectors = eigenvectors[:, sorted_indices]

    # Principal axes
    major_axis = eigenvectors[:, 0]

    # Calculate ellipse radii based on data spread
    major_projections = np.dot(centered_coords, major_axis)
    minor_projections = np.dot(centered_coords, eigenvectors[:, 1])

    # Use 1.2x standard deviation for size (keeps ellipse close to original)
    major_radius = 1.2 * np.std(major_projections)
    minor_radius = 1.2 * np.std(minor_projections)

    # Ensure minimum radius
    min_radius = 10.0
    major_radius = max(major_radius, min_radius)
    minor_radius = max(minor_radius, min_radius)

    # Calculate rotation angle
    rotation_angle = math.atan2(major_axis[1], major_axis[0])

    # Create ellipse path
    path = QPainterPath()
    num_points = max(36, len(points) * 3)

    for i in range(num_points + 1):
        t = 2 * math.pi * i / num_points

        # Ellipse in local coordinates
        local_x = major_radius * math.cos(t)
        local_y = minor_radius * math.sin(t)

        # Rotate by principal axis angle
        cos_rot = math.cos(rotation_angle)
        sin_rot = math.sin(rotation_angle)

        rotated_x = local_x * cos_rot - local_y * sin_rot
        rotated_y = local_x * sin_rot + local_y * cos_rot

        # Translate to center
        x = center_x + rotated_x
        y = center_y + rotated_y

        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)

    return path


def create_interpolated_path(
    points: list[QPointF],
    smoothness_percentage: int,
    spline_creator: callable | None = None,
) -> QPainterPath:
    """
    Create a path interpolated between raw points and perfect ellipse.

    Uses optimal point correspondence based on angular alignment to ensure
    smooth interpolation without crossovers.

    Args:
        points: Original path points
        smoothness_percentage: 0 = raw, 100 = perfect ellipse
        spline_creator: Optional spline creation function for final smoothing

    Returns:
        Interpolated QPainterPath

    Time Complexity: O(n) where n = number of points
    """
    if not points:
        return QPainterPath()

    # Get raw path points
    raw_path_points = points

    # Get ellipse path and calculate center
    ellipse_path = create_perfect_ellipse_path(points)
    coords = np.array([[p.x(), p.y()] for p in points])
    center = np.mean(coords, axis=0)
    center_x, center_y = center[0], center[1]

    # Find corresponding ellipse points using angular alignment
    ellipse_points = []
    for raw_point in raw_path_points:
        # Calculate angle of raw point relative to center
        raw_angle = math.atan2(raw_point.y() - center_y, raw_point.x() - center_x)

        # Normalize angle to [0, 2π]
        normalized_angle = (raw_angle + 2 * math.pi) % (2 * math.pi)
        percent = normalized_angle / (2 * math.pi)

        # Get point on ellipse at this parameter
        ellipse_point = ellipse_path.pointAtPercent(percent)
        ellipse_points.append(ellipse_point)

    # Interpolation factor
    factor = smoothness_percentage / 100.0

    # Interpolate between raw and ellipse points
    interpolated_points = []
    for i, raw_p in enumerate(raw_path_points):
        ellipse_p = ellipse_points[i]

        # Linear interpolation
        x = raw_p.x() * (1 - factor) + ellipse_p.x() * factor
        y = raw_p.y() * (1 - factor) + ellipse_p.y() * factor
        interpolated_points.append(QPointF(x, y))

    # Create final path
    if spline_creator:
        # Use custom spline creator for additional smoothness
        tension = 0.3 + 0.4 * factor
        return spline_creator(interpolated_points, closed_loop=True, tension=tension)
    else:
        return create_raw_path(interpolated_points, closed=True)


def extract_points_from_path(path: QPainterPath, num_samples: int | None = None) -> list[QPointF]:
    """
    Extract points from a QPainterPath by sampling at regular intervals.

    Args:
        path: Source path to sample
        num_samples: Number of samples (auto-calculated if None)

    Returns:
        List of sampled points

    Time Complexity: O(n) where n = number of samples
    """
    points = []
    length = path.length()

    if length > 0:
        if num_samples is None:
            num_samples = min(12, max(6, int(length / 20)))

        for i in range(num_samples):
            percent = i / (num_samples - 1) if num_samples > 1 else 0
            point = path.pointAtPercent(percent)
            points.append(point)

    return points


def calculate_path_center(points: list[QPointF]) -> tuple[float, float]:
    """
    Calculate the centroid of a set of points.

    Args:
        points: List of points

    Returns:
        Tuple of (center_x, center_y)

    Time Complexity: O(n)
    """
    if not points:
        return (0.0, 0.0)

    coords = np.array([[p.x(), p.y()] for p in points])
    center = np.mean(coords, axis=0)
    return (float(center[0]), float(center[1]))


def resample_path_points(
    points: list[QPointF],
    target_count: int,
) -> list[QPointF]:
    """
    Resample points to a target count using linear interpolation.

    Args:
        points: Original points
        target_count: Desired number of points

    Returns:
        Resampled points list

    Time Complexity: O(n) where n = max(len(points), target_count)
    """
    if not points or target_count <= 0:
        return []

    n = len(points)
    if n <= target_count:
        result = points.copy()
        while len(result) < target_count:
            result.append(result[-1])
        return result

    result = []
    for i in range(target_count):
        idx = int(i * n / target_count)
        result.append(points[idx])
    return result


def compute_path_bounds(points: list[QPointF]) -> tuple[float, float, float, float]:
    """
    Compute the bounding box of a set of points.

    Args:
        points: List of points

    Returns:
        Tuple of (min_x, min_y, max_x, max_y)

    Time Complexity: O(n)
    """
    if not points:
        return (0.0, 0.0, 0.0, 0.0)

    min_x = min(p.x() for p in points)
    min_y = min(p.y() for p in points)
    max_x = max(p.x() for p in points)
    max_y = max(p.y() for p in points)

    return (min_x, min_y, max_x, max_y)
