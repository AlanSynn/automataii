"""
Path Drawing Handler - Handles motion path drawing and visualization.

Extracted from EditorView. Manages freehand path drawing, spline creation,
and path overlay visualization.

Design Pattern: Handler (specialized path drawing operations)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsScene

if TYPE_CHECKING:
    from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem


TARGET_PATH_POINTS = 12


class PathDrawingHandler:
    """
    Handles motion path drawing and visualization.

    Responsibilities:
    - Manage freehand path drawing state
    - Create spline paths from points
    - Manage path overlay visualization (raw/corrected)
    - Resample path points

    Time Complexity: O(n) where n = number of path points
    """

    def __init__(self, scene: QGraphicsScene, z_path_line: int, z_path_preview: int):
        """
        Initialize path drawing handler.

        Args:
            scene: Graphics scene for path items
            z_path_line: Z-index for path lines
            z_path_preview: Z-index for path previews
        """
        self._scene = scene
        self._z_path_line = z_path_line
        self._z_path_preview = z_path_preview

        # Drawing state
        self._motion_path_points: list[QPointF] = []
        self._motion_preview_path_item: QGraphicsPathItem | None = None
        self._is_drawing_freehand = False
        self.current_target_item_for_path: CharacterPartItem | None = None
        self.current_path_is_closed = True

        # Path storage
        self.final_paths_map: dict[str, QGraphicsPathItem] = {}
        self._raw_paths_map: dict[str, QGraphicsPathItem] = {}
        self._corrected_paths_map: dict[str, QGraphicsPathItem] = {}

    @property
    def is_drawing(self) -> bool:
        """Check if currently drawing a path."""
        return self._is_drawing_freehand

    @property
    def path_points(self) -> list[QPointF]:
        """Get current path points."""
        return self._motion_path_points

    def start_drawing(self, scene_pos: QPointF) -> None:
        """Start a new path drawing session."""
        self._motion_path_points.clear()
        self._motion_path_points.append(scene_pos)
        self._is_drawing_freehand = True
        self.update_preview()

    def add_point(self, scene_pos: QPointF) -> None:
        """Add a point to the current path."""
        if self._is_drawing_freehand:
            self._motion_path_points.append(scene_pos)
            self.update_preview()

    def finish_drawing(self) -> tuple[list[QPointF], QPainterPath] | None:
        """
        Finish drawing and create the final spline path.

        Returns:
            Tuple of (resampled points, spline path) or None if path too short
        """
        num_original_points = len(self._motion_path_points)

        if num_original_points < 3:
            self.cancel_drawing()
            return None

        # Resample points
        if num_original_points < TARGET_PATH_POINTS:
            points_for_spline = list(self._motion_path_points)
        else:
            points_for_spline = self.resample_points(
                list(self._motion_path_points), TARGET_PATH_POINTS
            )

        if not points_for_spline or len(points_for_spline) < 3:
            self.cancel_drawing()
            return None

        # Create spline path
        final_path = self.create_spline_path(
            points_for_spline,
            closed_loop=self.current_path_is_closed,
            tension=0.5,
        )

        # Clean up preview
        self._cleanup_preview()
        self._motion_path_points.clear()
        self._is_drawing_freehand = False

        return points_for_spline, final_path

    def cancel_drawing(self) -> None:
        """Cancel current path drawing."""
        self.current_target_item_for_path = None
        self._is_drawing_freehand = False
        self._motion_path_points.clear()
        self._cleanup_preview()

    def update_preview(self) -> None:
        """Update the visual preview of the path being drawn."""
        if not self._is_drawing_freehand or not self._motion_path_points:
            self._cleanup_preview()
            return

        if len(self._motion_path_points) < 2:
            self._cleanup_preview()
            return

        path = QPainterPath()
        path.moveTo(self._motion_path_points[0])
        for point in self._motion_path_points[1:]:
            path.lineTo(point)

        if self._motion_preview_path_item is None:
            self._motion_preview_path_item = QGraphicsPathItem()
            pen = QPen(QColor(255, 0, 0, 180), 4.0)
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self._motion_preview_path_item.setPen(pen)
            self._motion_preview_path_item.setZValue(self._z_path_preview)
            self._scene.addItem(self._motion_preview_path_item)

        self._motion_preview_path_item.setPath(path)

    def _cleanup_preview(self) -> None:
        """Clean up preview path item."""
        if self._motion_preview_path_item:
            if self._motion_preview_path_item.scene():
                self._scene.removeItem(self._motion_preview_path_item)
            self._motion_preview_path_item = None

    def add_final_path(
        self,
        component_key: str,
        path: QPainterPath,
        pen: QPen | None = None,
    ) -> QGraphicsPathItem:
        """Add a finalized path to the scene."""
        # Remove existing
        if component_key in self.final_paths_map:
            old = self.final_paths_map.pop(component_key)
            if old and old.scene():
                self._scene.removeItem(old)

        path_item = QGraphicsPathItem(path)
        if pen is None:
            pen = QPen(QColor(0, 200, 0), 5.0)
            pen.setCosmetic(True)
        path_item.setPen(pen)
        path_item.setZValue(self._z_path_preview - 1)

        self._scene.addItem(path_item)
        self.final_paths_map[component_key] = path_item
        return path_item

    def clear_path_for_component(self, component_key: str) -> bool:
        """
        Clear the path for a specific component.

        Returns:
            True if a path was removed, False otherwise
        """
        path_item = self.final_paths_map.pop(component_key, None)
        if path_item:
            if path_item.scene():
                self._scene.removeItem(path_item)
            self.clear_overlays_for(component_key)
            return True
        return False

    # --- Overlay Management ---

    def set_raw_overlay_path(
        self, key: str, path: QPainterPath | None, pen: QPen | None = None
    ) -> None:
        """Set or clear the raw path overlay for a component."""
        if key in self._raw_paths_map:
            old = self._raw_paths_map.pop(key)
            try:
                self._scene.removeItem(old)
            except Exception:
                pass

        if path is None or path.isEmpty():
            return

        item = QGraphicsPathItem(path)
        if pen is None:
            pen = QPen(
                QColor("#6a4c93"), 3.0, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap
            )
        item.setPen(pen)
        item.setZValue(self._z_path_line)
        self._scene.addItem(item)
        self._raw_paths_map[key] = item

    def set_corrected_overlay_path(
        self, key: str, path: QPainterPath | None, pen: QPen | None = None
    ) -> None:
        """Set or clear the corrected path overlay for a component."""
        if key in self._corrected_paths_map:
            old = self._corrected_paths_map.pop(key)
            try:
                self._scene.removeItem(old)
            except Exception:
                pass

        if path is None or path.isEmpty():
            return

        item = QGraphicsPathItem(path)
        if pen is None:
            pen = QPen(
                QColor(255, 140, 0, 220),
                3.0,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        item.setPen(pen)
        item.setZValue(self._z_path_line)
        self._scene.addItem(item)
        self._corrected_paths_map[key] = item

    def clear_overlays_for(self, key: str) -> None:
        """Clear raw and corrected overlays for a component."""
        if key in self._raw_paths_map:
            try:
                self._scene.removeItem(self._raw_paths_map[key])
            except Exception:
                pass
            self._raw_paths_map.pop(key, None)

        if key in self._corrected_paths_map:
            try:
                self._scene.removeItem(self._corrected_paths_map[key])
            except Exception:
                pass
            self._corrected_paths_map.pop(key, None)

    def clear_corrected_overlay_for(self, key: str) -> None:
        """Clear only the corrected overlay for a component."""
        if key in self._corrected_paths_map:
            try:
                self._scene.removeItem(self._corrected_paths_map[key])
            except Exception:
                pass
            self._corrected_paths_map.pop(key, None)

    # --- Path Creation ---

    def create_spline_path(
        self,
        points: list[QPointF],
        closed_loop: bool = False,
        tension: float = 0.5,
    ) -> QPainterPath:
        """
        Create a spline path from points using Catmull-Rom approximation.

        Args:
            points: List of control points
            closed_loop: Whether to close the path
            tension: Spline tension (0.0-1.0)

        Returns:
            QPainterPath with smooth curves
        """
        path = QPainterPath()
        if not points or len(points) < 2:
            if len(points) == 1:
                path.moveTo(points[0])
            return path

        n = len(points)
        path.moveTo(points[0])

        if n == 2:
            path.lineTo(points[1])
            if closed_loop:
                path.lineTo(points[0])
            return path

        # Create extended point list for control point calculation
        plot_points = list(points)
        if closed_loop:
            plot_points.insert(0, points[n - 1])
            plot_points.append(points[0])
            plot_points.append(points[1])
        else:
            plot_points.insert(0, points[0])
            plot_points.append(points[n - 1])

        control_factor = tension / 3

        for i in range(1, len(plot_points) - 2):
            p0 = plot_points[i - 1]
            p1 = plot_points[i]
            p2 = plot_points[i + 1]
            p3 = plot_points[i + 2]

            # Calculate control points
            cp1_x = p1.x() + (p2.x() - p0.x()) * control_factor
            cp1_y = p1.y() + (p2.y() - p0.y()) * control_factor
            cp1 = QPointF(cp1_x, cp1_y)

            cp2_x = p2.x() - (p3.x() - p1.x()) * control_factor
            cp2_y = p2.y() - (p3.y() - p1.y()) * control_factor
            cp2 = QPointF(cp2_x, cp2_y)

            path.cubicTo(cp1, cp2, p2)

        return path

    def resample_points(
        self, points: list[QPointF], num_target: int
    ) -> list[QPointF]:
        """
        Resample points to a target count.

        Args:
            points: Original points
            num_target: Target number of points

        Returns:
            Resampled list of points
        """
        if not points or num_target <= 0:
            return []

        n = len(points)
        if n <= num_target:
            result = points.copy()
            while len(result) < num_target:
                result.append(result[-1])
            return result

        result = []
        for i in range(num_target):
            idx = int(i * n / num_target)
            result.append(points[idx])
        return result
