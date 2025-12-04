"""
IK Path Handler - Handles motion path extraction and point calculations.

Extracted from IKManager. Manages QPainterPath operations and
path interpolation for IK animation.

Design Pattern: Handler (path data processing)
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath


class IKPathHandler:
    """
    Handles motion path operations for IK animation.

    Responsibilities:
    - Extract points from QPainterPath
    - Interpolate positions along paths
    - Calculate path lengths and segments

    Time Complexity: O(n) where n = number of path elements
    """

    def extract_points_from_painter_path(
        self, painter_path: QPainterPath | None
    ) -> list[QPointF]:
        """
        Extracts QPointF coordinates from a QPainterPath.

        Args:
            painter_path: Qt painter path to extract points from

        Returns:
            List of QPointF points from the path
        """
        points: list[QPointF] = []
        if (
            not painter_path
            or not hasattr(painter_path, "elementCount")
            or painter_path.elementCount() == 0
        ):
            return points

        for i in range(painter_path.elementCount()):
            element = painter_path.elementAt(i)
            points.append(QPointF(element.x, element.y))

        return points

    def get_point_on_path(
        self, path_obj: Any, progress: float
    ) -> QPointF | None:
        """
        Get interpolated point on a path at given progress.

        Args:
            path_obj: Path object (list of points, QPointF list, or QPainterPath)
            progress: Progress along path (0.0 to 1.0)

        Returns:
            Interpolated QPointF or None if path is invalid
        """
        path_points = self._normalize_path_points(path_obj)

        if not path_points:
            return None
        if len(path_points) == 1:
            return path_points[0]

        # Calculate segment lengths
        total_length, segment_lengths = self._calculate_path_lengths(path_points)

        if total_length < 1e-5:
            return path_points[0]

        # Find point at target distance
        target_dist = max(0, min(progress * total_length, total_length))

        return self._interpolate_along_segments(
            path_points, segment_lengths, target_dist
        )

    def _normalize_path_points(self, path_obj: Any) -> list[QPointF]:
        """Normalize various path formats to list of QPointF."""
        if isinstance(path_obj, list):
            if all(isinstance(p, QPointF) for p in path_obj):
                return path_obj
            try:
                return [
                    QPointF(p[0], p[1])
                    for p in path_obj
                    if isinstance(p, list | tuple) and len(p) == 2
                ]
            except (TypeError, IndexError):
                return []
        elif hasattr(path_obj, "elementCount"):
            return self.extract_points_from_painter_path(path_obj)
        return []

    def _calculate_path_lengths(
        self, path_points: list[QPointF]
    ) -> tuple[float, list[float]]:
        """Calculate total path length and individual segment lengths."""
        total_length = 0.0
        segment_lengths: list[float] = []

        for i in range(len(path_points) - 1):
            p1 = path_points[i]
            p2 = path_points[i + 1]
            segment_length = QPointF(p2 - p1).manhattanLength()
            segment_lengths.append(segment_length)
            total_length += segment_length

        return total_length, segment_lengths

    def _interpolate_along_segments(
        self,
        path_points: list[QPointF],
        segment_lengths: list[float],
        target_dist: float,
    ) -> QPointF:
        """Interpolate position at target distance along path segments."""
        current_dist = 0.0

        for i, segment_len in enumerate(segment_lengths):
            if current_dist + segment_len >= target_dist - 1e-5:
                p1 = path_points[i]
                p2 = path_points[i + 1]
                remaining_dist = target_dist - current_dist

                if segment_len < 1e-5:
                    return p1

                segment_progress = max(0.0, min(1.0, remaining_dist / segment_len))

                interpolated_x = p1.x() + (p2.x() - p1.x()) * segment_progress
                interpolated_y = p1.y() + (p2.y() - p1.y()) * segment_progress
                return QPointF(interpolated_x, interpolated_y)

            current_dist += segment_len

        return path_points[-1]

    def calculate_path_length(self, path_obj: Any) -> float:
        """Calculate total length of a path."""
        path_points = self._normalize_path_points(path_obj)
        if len(path_points) < 2:
            return 0.0

        total_length, _ = self._calculate_path_lengths(path_points)
        return total_length
