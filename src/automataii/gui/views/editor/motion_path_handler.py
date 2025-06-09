"""Motion path drawing handler for the editor view."""

import logging
from typing import List, Optional
from PyQt6.QtCore import QObject, QPointF, pyqtSignal, Qt
from PyQt6.QtWidgets import QGraphicsPathItem
from PyQt6.QtGui import QPen, QColor, QPainterPath

from ...graphics_items.part_item import CharacterPartItem
from .constants import TARGET_PATH_POINTS, EditorMode
from ....config.z_indices import Z_MOTION_PATH_PREVIEW


class MotionPathHandler(QObject):
    """Handles motion path drawing operations."""

    freehandPathCompleted = pyqtSignal(list)  # Emits list of QPointF
    drawing_cancelled = pyqtSignal()
    path_data_cleared_for_component = pyqtSignal(str)  # Component key

    def __init__(self, view):
        super().__init__()
        self.view = view

        # Motion path state
        self._path_points: List[QPointF] = []
        self._preview_path_item: Optional[QGraphicsPathItem] = None
        self._is_drawing = False
        self._target_item: Optional[CharacterPartItem] = None

        # Final paths storage
        self._final_paths_map = {}  # component_key -> QGraphicsPathItem

    def start_path_drawing(self, target_item: Optional[CharacterPartItem] = None):
        """Starts motion path drawing mode."""
        self._target_item = target_item
        self._path_points.clear()
        self._is_drawing = False

        logging.info("Motion path drawing mode activated")
        if target_item:
            logging.info(f"Target item: {target_item.part_info.name}")

    def begin_drawing(self, start_pos: QPointF):
        """Begins drawing from the given position."""
        self._path_points.clear()
        self._path_points.append(start_pos)
        self._is_drawing = True
        self._update_preview()

    def add_point(self, pos: QPointF):
        """Adds a point to the current path."""
        if not self._is_drawing:
            return

        self._path_points.append(pos)
        self._update_preview()

    def finish_drawing(self) -> bool:
        """Finishes the current path. Returns True if successful."""
        if not self._is_drawing:
            return False

        num_points = len(self._path_points)
        if num_points < 3:
            logging.debug(f"Path too short ({num_points} points), need at least 3")
            self.cancel_drawing()
            return False

        # Resample points
        points_for_spline = self._prepare_points_for_spline()

        if not points_for_spline or len(points_for_spline) < 3:
            logging.warning("Not enough points for spline after resampling")
            self.cancel_drawing()
            return False

        # Create final path
        final_path = self._create_spline_path(points_for_spline, closed_loop=True)
        self._create_final_path_item(final_path)

        # Emit completed signal
        self.freehandPathCompleted.emit(points_for_spline)

        logging.debug(
            f"Completed path with {len(points_for_spline)} points "
            f"(resampled from {num_points})"
        )

        # Cleanup
        self._cleanup_preview()
        self._path_points.clear()
        self._is_drawing = False

        return True

    def cancel_drawing(self):
        """Cancels the current drawing."""
        logging.debug("Motion path drawing cancelled")

        self._cleanup_preview()
        self._path_points.clear()
        self._is_drawing = False
        self._target_item = None

        self.drawing_cancelled.emit()
        self._show_status_message("Motion path definition cancelled.")

    def clear_path_for_component(self, component_key: str):
        """Removes the path for a specific component."""
        if not component_key:
            logging.warning("clear_path_for_component called with no key")
            return

        path_item = self._final_paths_map.pop(component_key, None)

        if path_item:
            if path_item.scene():
                self.view.scene().removeItem(path_item)
                logging.debug(f"Removed path for component '{component_key}'")
            else:
                logging.debug(f"Path for '{component_key}' was not in scene")

        self.path_data_cleared_for_component.emit(component_key)
        self._show_status_message(f"Path cleared for {component_key}")

    def _prepare_points_for_spline(self) -> List[QPointF]:
        """Prepares points for spline creation."""
        num_points = len(self._path_points)

        if num_points < TARGET_PATH_POINTS:
            # Use original points if we have fewer than target
            return list(self._path_points)
        else:
            # Resample to target number
            return self._resample_points(self._path_points, TARGET_PATH_POINTS)

    def _resample_points(self, points: List[QPointF], num_target: int) -> List[QPointF]:
        """Resamples points to target number."""
        if not points or num_target <= 0:
            return []

        n = len(points)
        if n <= num_target:
            # Pad with last point if needed
            result = points.copy()
            while len(result) < num_target and result:
                result.append(result[-1])
            return result
        else:
            # Downsample
            result = []
            for i in range(num_target):
                idx = int(i * n / num_target)
                result.append(points[idx])
            return result

    def _create_spline_path(
        self, points: List[QPointF],
        closed_loop: bool = False,
        tension: float = 0.5
    ) -> QPainterPath:
        """Creates a smooth spline path from points."""
        path = QPainterPath()

        if not points:
            return path

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

        # Create Catmull-Rom spline using cubic Bezier approximation
        plot_points = list(points)

        if closed_loop:
            # Extend for closed loop
            plot_points.insert(0, points[-1])
            plot_points.append(points[0])
            plot_points.append(points[1])
        else:
            # Duplicate endpoints for open curve
            plot_points.insert(0, points[0])
            plot_points.append(points[-1])

        # Generate curve segments
        for i in range(1, len(plot_points) - 2):
            p0 = plot_points[i - 1]
            p1 = plot_points[i]
            p2 = plot_points[i + 1]
            p3 = plot_points[i + 2]

            # Calculate control points
            scale = tension / 3

            cp1 = QPointF(
                p1.x() + (p2.x() - p0.x()) * scale,
                p1.y() + (p2.y() - p0.y()) * scale
            )

            cp2 = QPointF(
                p2.x() - (p3.x() - p1.x()) * scale,
                p2.y() - (p3.y() - p1.y()) * scale
            )

            path.cubicTo(cp1, cp2, p2)

        return path

    def _create_final_path_item(self, path: QPainterPath):
        """Creates the final path graphics item."""
        # Determine component key
        component_key = self._get_component_key()

        if component_key:
            # Remove old path if exists
            old_path = self._final_paths_map.pop(component_key, None)
            if old_path and old_path.scene():
                self.view.scene().removeItem(old_path)

        # Create new path item
        path_item = QGraphicsPathItem()
        pen = QPen(QColor(0, 200, 0), 5.0)  # Green, thick
        pen.setCosmetic(True)
        path_item.setPen(pen)
        path_item.setPath(path)
        path_item.setZValue(Z_MOTION_PATH_PREVIEW - 1)

        self.view.scene().addItem(path_item)

        if component_key:
            self._final_paths_map[component_key] = path_item
            logging.debug(f"Added final path for component '{component_key}'")
        else:
            logging.warning("Final path created without component key")

    def _update_preview(self):
        """Updates the preview path."""
        if not self._is_drawing or len(self._path_points) < 2:
            self._cleanup_preview()
            return

        # Create preview path
        path = QPainterPath()
        path.moveTo(self._path_points[0])
        for point in self._path_points[1:]:
            path.lineTo(point)

        if not self._preview_path_item:
            self._preview_path_item = QGraphicsPathItem()
            pen = QPen(QColor(255, 0, 0, 180), 4.0)  # Red, semi-transparent
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self._preview_path_item.setPen(pen)
            self._preview_path_item.setZValue(Z_MOTION_PATH_PREVIEW)
            self.view.scene().addItem(self._preview_path_item)

        self._preview_path_item.setPath(path)

    def _cleanup_preview(self):
        """Removes the preview path."""
        if self._preview_path_item:
            if self._preview_path_item.scene():
                self.view.scene().removeItem(self._preview_path_item)
            self._preview_path_item = None

    def _get_component_key(self) -> Optional[str]:
        """Gets the component key for the current path."""
        # Check parent window for selected component
        if hasattr(self.view, 'parent_window') and self.view.parent_window:
            if hasattr(self.view.parent_window, 'sim_selected_component_key'):
                return self.view.parent_window.sim_selected_component_key

        # Fall back to target item
        if self._target_item:
            return self._target_item.part_info.name

        return None

    def _show_status_message(self, message: str):
        """Shows a status message."""
        if hasattr(self.view, 'parent_window') and self.view.parent_window:
            if hasattr(self.view.parent_window, 'statusBar'):
                self.view.parent_window.statusBar().showMessage(message, 5000)
        else:
            logging.info(f"Status: {message}")