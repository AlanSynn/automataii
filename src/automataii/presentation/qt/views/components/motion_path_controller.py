"""
Motion Path Controller - Motion path drawing and spline generation.

Extracted from EditorView. Handles motion path creation,
preview updates, and spline path generation.

Design Pattern: Controller (motion path state management)
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import QObject, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsPathItem

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene


class MotionPathController(QObject):
    """
    Controls motion path drawing and spline generation.

    Responsibilities:
    - Start/stop motion path drawing mode
    - Track drawing points
    - Generate smooth spline paths
    - Update path preview

    Signals:
        path_completed: Emitted when path drawing is complete (QPainterPath)
        path_cancelled: Emitted when path drawing is cancelled
    """

    path_completed = pyqtSignal(object)  # QPainterPath
    path_cancelled = pyqtSignal()

    # Path drawing settings
    MIN_POINTS_FOR_PATH = 3
    SPLINE_TENSION = 0.5
    RESAMPLE_SEGMENT_LENGTH = 5.0

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize motion path controller."""
        super().__init__(parent)

        # Drawing state
        self._is_drawing: bool = False
        self._is_closed_path: bool = True
        self._draw_points: list[QPointF] = []
        self._target_item: Any = None

        # Visual items
        self._path_preview_item: QGraphicsPathItem | None = None
        self._scene: QGraphicsScene | None = None

        # Callbacks
        self._show_status: Callable[[str], None] = lambda msg: None

    def configure(
        self,
        scene: QGraphicsScene,
        show_status: Callable[[str], None] | None = None,
    ) -> None:
        """
        Configure controller with scene and callbacks.

        Args:
            scene: Graphics scene for path items
            show_status: Callback for status messages
        """
        self._scene = scene
        if show_status:
            self._show_status = show_status

    @property
    def is_drawing(self) -> bool:
        """Check if currently drawing a path."""
        return self._is_drawing

    @property
    def target_item(self) -> Any:
        """Get current target item for path."""
        return self._target_item

    def start_drawing(
        self,
        target_item: Any = None,
        is_closed: bool = True,
    ) -> bool:
        """
        Start motion path drawing mode.

        Args:
            target_item: Item to attach path to
            is_closed: Whether path should be closed loop

        Returns:
            True if drawing started successfully
        """
        if not self._scene:
            return False

        self._is_drawing = True
        self._is_closed_path = is_closed
        self._draw_points = []
        self._target_item = target_item

        # Create preview path item
        self._path_preview_item = QGraphicsPathItem()
        pen = QPen(QColor(100, 149, 237, 200))  # Cornflower blue
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        self._path_preview_item.setPen(pen)
        self._path_preview_item.setZValue(1000)
        self._scene.addItem(self._path_preview_item)

        self._show_status("Click to add path points. Right-click or press Escape to finish.")
        return True

    def add_point(self, point: QPointF) -> None:
        """
        Add a point to the current path.

        Args:
            point: Scene coordinate to add
        """
        if not self._is_drawing:
            return

        self._draw_points.append(point)
        self._update_preview()

    def finish_drawing(self) -> QPainterPath | None:
        """
        Finish path drawing and generate final path.

        Returns:
            Final QPainterPath or None if insufficient points
        """
        if not self._is_drawing:
            return None

        if len(self._draw_points) < self.MIN_POINTS_FOR_PATH:
            self._show_status(
                f"Need at least {self.MIN_POINTS_FOR_PATH} points for a path."
            )
            self.cancel_drawing()
            return None

        # Generate smooth spline path
        final_path = self._create_spline_path(
            self._draw_points,
            self._is_closed_path,
        )

        self._cleanup()
        self.path_completed.emit(final_path)

        return final_path

    def cancel_drawing(self) -> None:
        """Cancel current path drawing."""
        self._cleanup()
        self.path_cancelled.emit()
        self._show_status("Path drawing cancelled.")

    def update_preview(self, current_pos: QPointF | None = None) -> None:
        """
        Update path preview with optional current mouse position.

        Args:
            current_pos: Current mouse position (optional)
        """
        if not self._is_drawing or not self._path_preview_item:
            return

        self._update_preview(current_pos)

    def _update_preview(self, current_pos: QPointF | None = None) -> None:
        """Update preview path visualization."""
        if not self._path_preview_item:
            return

        preview_points = list(self._draw_points)
        if current_pos:
            preview_points.append(current_pos)

        if len(preview_points) < 2:
            self._path_preview_item.setPath(QPainterPath())
            return

        preview_path = self._create_spline_path(
            preview_points,
            closed=False,  # Preview is always open
        )
        self._path_preview_item.setPath(preview_path)

    def _cleanup(self) -> None:
        """Clean up drawing state and visuals."""
        self._is_drawing = False
        self._draw_points = []
        self._target_item = None

        if self._path_preview_item and self._scene:
            self._scene.removeItem(self._path_preview_item)
            self._path_preview_item = None

    def _create_spline_path(
        self,
        points: list[QPointF],
        closed: bool = True,
    ) -> QPainterPath:
        """
        Create smooth spline path from points.

        Uses Catmull-Rom spline interpolation.

        Args:
            points: Control points
            closed: Whether to close the path

        Returns:
            Smooth QPainterPath

        Time Complexity: O(n * s) where n = points, s = segments per span
        """
        if len(points) < 2:
            return QPainterPath()

        # Resample to even spacing
        resampled = self._resample_points(points)
        if len(resampled) < 2:
            return QPainterPath()

        path = QPainterPath()
        path.moveTo(resampled[0])

        if len(resampled) == 2:
            path.lineTo(resampled[1])
            return path

        # Catmull-Rom spline
        n = len(resampled)
        tension = self.SPLINE_TENSION

        for i in range(n - 1):
            p0 = resampled[(i - 1) % n] if closed or i > 0 else resampled[0]
            p1 = resampled[i]
            p2 = resampled[i + 1]
            p3 = resampled[(i + 2) % n] if closed or i < n - 2 else resampled[-1]

            # Calculate control points
            d1x = (p2.x() - p0.x()) * tension
            d1y = (p2.y() - p0.y()) * tension
            d2x = (p3.x() - p1.x()) * tension
            d2y = (p3.y() - p1.y()) * tension

            cp1 = QPointF(p1.x() + d1x / 3, p1.y() + d1y / 3)
            cp2 = QPointF(p2.x() - d2x / 3, p2.y() - d2y / 3)

            path.cubicTo(cp1, cp2, p2)

        if closed:
            path.closeSubpath()

        return path

    def _resample_points(
        self,
        points: list[QPointF],
    ) -> list[QPointF]:
        """
        Resample points to approximately even spacing.

        Args:
            points: Original points

        Returns:
            Resampled points

        Time Complexity: O(n) where n = number of points
        """
        if len(points) < 2:
            return points

        # Calculate total path length
        total_length = 0.0
        for i in range(len(points) - 1):
            dx = points[i + 1].x() - points[i].x()
            dy = points[i + 1].y() - points[i].y()
            total_length += math.sqrt(dx * dx + dy * dy)

        if total_length < self.RESAMPLE_SEGMENT_LENGTH:
            return points

        # Resample
        target_spacing = self.RESAMPLE_SEGMENT_LENGTH
        resampled = [points[0]]
        accumulated = 0.0
        current_idx = 0

        while current_idx < len(points) - 1:
            p1 = points[current_idx]
            p2 = points[current_idx + 1]
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            segment_length = math.sqrt(dx * dx + dy * dy)

            if segment_length < 1e-6:
                current_idx += 1
                continue

            while accumulated + segment_length >= target_spacing:
                t = (target_spacing - accumulated) / segment_length
                new_x = p1.x() + dx * t
                new_y = p1.y() + dy * t
                resampled.append(QPointF(new_x, new_y))

                # Update for next iteration
                p1 = QPointF(new_x, new_y)
                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()
                segment_length = math.sqrt(dx * dx + dy * dy)
                accumulated = 0.0

            accumulated += segment_length
            current_idx += 1

        # Add last point if not too close
        if resampled:
            last = resampled[-1]
            end = points[-1]
            dist = math.sqrt(
                (end.x() - last.x()) ** 2 + (end.y() - last.y()) ** 2
            )
            if dist > target_spacing * 0.5:
                resampled.append(end)

        return resampled


# Import Qt enum for pen style
from PyQt6.QtCore import Qt
