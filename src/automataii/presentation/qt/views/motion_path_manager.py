"""
MotionPathDrawer - Low-level path drawing and visualization.

Extracted from EditorView god class. Handles the mechanics of:
- Freehand drawing with mouse events
- Preview path visualization during drawing
- Catmull-Rom spline generation
- Scene item management for paths and overlays
- Timestamp recording for velocity-aware animation

This is distinct from MotionPathManager (in tabs/editor/components/) which
handles higher-level coordination, UI bindings, RDP smoothing, and feasibility.
"""

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsScene

from automataii.config.z_indices import Z_MOTION_PATH_LINE, Z_MOTION_PATH_PREVIEW

if TYPE_CHECKING:
    from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem

# Number of points to resample paths to for spline creation
TARGET_PATH_POINTS = 12


@dataclass
class TimedPoint:
    """Point with timestamp for velocity-aware animation."""

    point: QPointF
    timestamp: float  # Seconds from drawing start

    @property
    def x(self) -> float:
        return self.point.x()

    @property
    def y(self) -> float:
        return self.point.y()


class MotionPathDrawer(QObject):
    """
    Low-level motion path drawing and scene visualization.

    Handles the mechanics of path drawing (mouse input, preview, splines)
    and scene item management (adding/removing path graphics items).

    For high-level path management with UI coordination, see
    MotionPathManager in tabs/editor/components/.

    Signals:
        freehand_path_completed(list, list, float): Emitted when freehand drawing completes.
            - list of QPointF (resampled points for visual spline)
            - list of TimedPoint (original points with timestamps)
            - float (total drawing duration in seconds)
        drawing_cancelled(): Emitted when path drawing is cancelled.
        path_data_cleared(str): Emitted when path data is cleared for a component.
    """

    # Signal now includes timed points and duration for velocity-aware animation
    freehand_path_completed = pyqtSignal(list, list, float)
    drawing_cancelled = pyqtSignal()
    path_data_cleared = pyqtSignal(str)

    def __init__(self, scene: QGraphicsScene, parent: QObject | None = None):
        super().__init__(parent)
        self._scene = scene

        # Motion path drawing state
        self._motion_path_points: list[QPointF] = []
        self._timed_path_points: list[TimedPoint] = []  # Points with timestamps
        self._drawing_start_time: float = 0.0
        self._motion_preview_path_item: QGraphicsPathItem | None = None
        self._is_drawing_freehand = False
        self._current_path_is_closed = True
        self._current_target_item: CharacterPartItem | None = None

        # Finalized paths (component_key -> QGraphicsPathItem)
        self.final_paths_map: dict[str, QGraphicsPathItem] = {}

        # Overlay paths for dual-track visualization
        self._raw_paths_map: dict[str, QGraphicsPathItem] = {}
        self._corrected_paths_map: dict[str, QGraphicsPathItem] = {}

    @property
    def is_drawing(self) -> bool:
        """Returns True if currently in freehand drawing mode."""
        return self._is_drawing_freehand

    @property
    def current_target_item(self) -> "CharacterPartItem | None":
        """Returns the current target item for path drawing."""
        return self._current_target_item

    # --- Path Drawing ---

    def start_drawing(
        self,
        target_item: "CharacterPartItem | None",
        is_closed: bool = True,
        component_key: str | None = None,
    ) -> None:
        """
        Start freehand motion path drawing.

        Args:
            target_item: The CharacterPartItem this path is for (can be None)
            is_closed: Whether the path should be closed loop
            component_key: Optional component key for path association
        """
        # Clear existing path for this component before starting
        if component_key and component_key in self.final_paths_map:
            self._remove_final_path(component_key)
            logging.info(f"Cleared existing path for {component_key} before new drawing")
        elif target_item and hasattr(target_item, "part_info") and target_item.part_info:
            key = target_item.part_info.name
            if key in self.final_paths_map:
                self._remove_final_path(key)
                logging.info(f"Cleared existing path for {key} before new drawing")

        self._current_target_item = target_item
        self._current_path_is_closed = is_closed
        self._motion_path_points.clear()
        self._timed_path_points.clear()
        self._drawing_start_time = 0.0
        self._is_drawing_freehand = False  # Will be set True on first point

        logging.info(f"MotionPathManager: Ready for freehand drawing (closed={is_closed})")

    def add_point(self, scene_pos: QPointF) -> None:
        """
        Add a point to the current freehand path with timestamp.

        Args:
            scene_pos: The point position in scene coordinates
        """
        if not self._is_drawing_freehand and not self._motion_path_points:
            # First point starts the drawing - record start time
            self._is_drawing_freehand = True
            self._drawing_start_time = time.perf_counter()
            self._timed_path_points.append(TimedPoint(point=scene_pos, timestamp=0.0))
        else:
            # Subsequent points - record elapsed time
            elapsed = time.perf_counter() - self._drawing_start_time
            self._timed_path_points.append(TimedPoint(point=scene_pos, timestamp=elapsed))

        self._motion_path_points.append(scene_pos)
        self._update_preview()

    def finish_drawing(self, component_key: str | None = None) -> bool:
        """
        Finish the current freehand drawing and create the final path.

        Args:
            component_key: The key to associate the path with

        Returns:
            True if path was successfully created, False otherwise
        """
        if not self._is_drawing_freehand:
            return False

        num_original_points = len(self._motion_path_points)

        if num_original_points < 3:
            logging.debug(f"Path too short ({num_original_points} points), need at least 3")
            self.cancel_drawing()
            return False

        # Resample points for spline creation
        if num_original_points < TARGET_PATH_POINTS:
            points_for_spline = list(self._motion_path_points)
        else:
            points_for_spline = self._resample_points(
                list(self._motion_path_points), TARGET_PATH_POINTS
            )

        if len(points_for_spline) < 3:
            logging.warning(f"Not enough points after resampling ({len(points_for_spline)})")
            self.cancel_drawing()
            return False

        # Create the final spline path
        final_path_data = self._create_spline_path(
            points_for_spline, closed_loop=self._current_path_is_closed, tension=0.5
        )

        # Create the graphics item
        final_path_item = QGraphicsPathItem()
        final_pen = QPen(QColor(0, 200, 0), 5.0)  # Green, thick
        final_pen.setCosmetic(True)
        final_path_item.setPen(final_pen)
        final_path_item.setPath(final_path_data)
        final_path_item.setZValue(Z_MOTION_PATH_PREVIEW - 1)
        final_path_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        # Determine the component key
        if not component_key and self._current_target_item:
            if (
                hasattr(self._current_target_item, "part_info")
                and self._current_target_item.part_info
            ):
                component_key = self._current_target_item.part_info.name

        # Store and display the path
        if component_key:
            self._remove_final_path(component_key)
            self._scene.addItem(final_path_item)
            self.final_paths_map[component_key] = final_path_item
            logging.debug(f"Added final path for component '{component_key}'")
        else:
            self._scene.addItem(final_path_item)
            logging.warning("Final path created without component key (orphaned)")

        # Capture timed points and duration BEFORE clearing
        timed_points = list(self._timed_path_points)
        total_duration = timed_points[-1].timestamp if timed_points else 0.0

        # Emit completion signal with resampled points, timed points, and duration
        self.freehand_path_completed.emit(points_for_spline, timed_points, total_duration)

        path_type_str = "closed" if self._current_path_is_closed else "open"
        logging.debug(
            f"Completed {path_type_str} spline path with {len(points_for_spline)} points "
            f"(resampled from {num_original_points}), duration: {total_duration:.2f}s"
        )

        # Clean up drawing state
        self._cleanup_preview()
        self._motion_path_points.clear()
        self._timed_path_points.clear()
        self._is_drawing_freehand = False
        self._current_target_item = None

        return True

    def cancel_drawing(self) -> None:
        """Cancel the current motion path drawing."""
        logging.debug("Motion path drawing cancelled")
        had_active_state = (
            self._is_drawing_freehand
            or bool(self._motion_path_points)
            or bool(self._timed_path_points)
            or self._motion_preview_path_item is not None
            or self._current_target_item is not None
        )
        self._current_target_item = None
        self._is_drawing_freehand = False
        self._motion_path_points.clear()
        self._timed_path_points.clear()
        self._cleanup_preview()
        if had_active_state:
            self.drawing_cancelled.emit()

    # --- Path Overlays ---

    def set_raw_overlay_path(
        self, key: str, path: QPainterPath | None, pen: QPen | None = None
    ) -> None:
        """
        Set or clear the raw path overlay for a component.

        Args:
            key: Component key (part name)
            path: The path to display, or None to clear
            pen: Optional custom pen, defaults to dashed purple
        """
        # Remove existing
        if key in self._raw_paths_map:
            old = self._raw_paths_map.pop(key)
            try:
                self._scene.removeItem(old)
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

        if path is None or path.isEmpty():
            return

        item = QGraphicsPathItem(path)
        if pen is None:
            pen = QPen(QColor("#6a4c93"), 3.0, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
        item.setPen(pen)
        item.setZValue(Z_MOTION_PATH_LINE)
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._scene.addItem(item)
        self._raw_paths_map[key] = item

    def set_corrected_overlay_path(
        self, key: str, path: QPainterPath | None, pen: QPen | None = None
    ) -> None:
        """
        Set or clear the feasibility-corrected path overlay for a component.

        Args:
            key: Component key (part name)
            path: The path to display, or None to clear
            pen: Optional custom pen, defaults to semi-transparent orange
        """
        if key in self._corrected_paths_map:
            old = self._corrected_paths_map.pop(key)
            try:
                self._scene.removeItem(old)
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

        if path is None or path.isEmpty():
            return

        item = QGraphicsPathItem(path)
        if pen is None:
            pen = QPen(
                QColor(255, 140, 0, 220), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap
            )
        item.setPen(pen)
        item.setZValue(Z_MOTION_PATH_LINE)
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._scene.addItem(item)
        self._corrected_paths_map[key] = item

    def clear_overlays_for(self, key: str) -> None:
        """Clear raw and corrected overlays for a component."""
        if key in self._raw_paths_map:
            try:
                self._scene.removeItem(self._raw_paths_map[key])
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)
            self._raw_paths_map.pop(key, None)

        if key in self._corrected_paths_map:
            try:
                self._scene.removeItem(self._corrected_paths_map[key])
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)
            self._corrected_paths_map.pop(key, None)

    def clear_corrected_overlay_for(self, key: str) -> None:
        """Clear only the corrected overlay for a component."""
        if key in self._corrected_paths_map:
            try:
                self._scene.removeItem(self._corrected_paths_map[key])
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)
            self._corrected_paths_map.pop(key, None)

    def clear_visual_path_for_component(self, component_key: str) -> None:
        """
        Remove the final visual path for a component.

        Args:
            component_key: The component key to clear
        """
        if not component_key:
            logging.warning("clear_visual_path_for_component called with no key")
            return

        logging.info(f"Clearing visual path for component '{component_key}'")

        if self._remove_final_path(component_key):
            logging.debug(f"Removed visual path for '{component_key}' from scene")
        else:
            logging.debug(f"No visual path found for '{component_key}'")

        # Also clear overlays
        self.clear_overlays_for(component_key)

        # Emit signal for external listeners
        self.path_data_cleared.emit(component_key)

    # --- Private Methods ---

    def _remove_final_path(self, key: str) -> bool:
        """Remove a final path from the scene and map. Returns True if removed."""
        path_item = self.final_paths_map.pop(key, None)
        if path_item:
            if path_item.scene():
                self._scene.removeItem(path_item)
            return True
        return False

    def clear_all_visuals(self) -> None:
        """Remove every path/overlay/preview item owned by this drawer."""
        for key in list(self.final_paths_map):
            self._remove_final_path(key)
        for key in list(self._raw_paths_map):
            item = self._raw_paths_map.pop(key)
            if item.scene():
                self._scene.removeItem(item)
        for key in list(self._corrected_paths_map):
            item = self._corrected_paths_map.pop(key)
            if item.scene():
                self._scene.removeItem(item)
        self._cleanup_preview()
        self._motion_path_points.clear()
        self._timed_path_points.clear()
        self._is_drawing_freehand = False
        self._current_target_item = None

    def _update_preview(self) -> None:
        """Update the visual preview of the current drawing."""
        if not self._is_drawing_freehand or not self._motion_path_points:
            self._cleanup_preview()
            return

        if len(self._motion_path_points) < 2:
            self._cleanup_preview()
            return

        # Build the preview path
        path = QPainterPath()
        path.moveTo(self._motion_path_points[0])
        for point in self._motion_path_points[1:]:
            path.lineTo(point)

        # Create or update the preview item
        if self._motion_preview_path_item is None:
            self._motion_preview_path_item = QGraphicsPathItem()
            pen = QPen(QColor(255, 0, 0, 180), 4.0)  # Red, semi-transparent
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self._motion_preview_path_item.setPen(pen)
            self._motion_preview_path_item.setZValue(Z_MOTION_PATH_PREVIEW)
            self._motion_preview_path_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._scene.addItem(self._motion_preview_path_item)

        self._motion_preview_path_item.setPath(path)

    def _cleanup_preview(self) -> None:
        """Remove the preview path item from the scene."""
        if self._motion_preview_path_item:
            if self._motion_preview_path_item.scene():
                self._scene.removeItem(self._motion_preview_path_item)
            self._motion_preview_path_item = None

    def _create_spline_path(
        self, points: list[QPointF], closed_loop: bool = False, tension: float = 0.5
    ) -> QPainterPath:
        """
        Create a QPainterPath from points using Catmull-Rom splines.

        Args:
            points: List of QPointF control points
            closed_loop: Whether the path should form a closed loop
            tension: Spline tension parameter (0.0-1.0)

        Returns:
            QPainterPath with smooth curves through the points
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

        # Create extended point list for edge handling
        plot_points = list(points)
        if closed_loop:
            plot_points.insert(0, points[n - 1])
            plot_points.append(points[0])
            plot_points.append(points[1])
        else:
            plot_points.insert(0, points[0])
            plot_points.append(points[n - 1])

        # Control point scaling
        control_point_scale = tension / 3

        # Generate Bezier curves for each segment
        for i in range(1, len(plot_points) - 2):
            p0 = plot_points[i - 1]
            p1 = plot_points[i]
            p2 = plot_points[i + 1]
            p3 = plot_points[i + 2]

            # Calculate control points
            cp1_x = p1.x() + (p2.x() - p0.x()) * control_point_scale
            cp1_y = p1.y() + (p2.y() - p0.y()) * control_point_scale
            cp1 = QPointF(cp1_x, cp1_y)

            cp2_x = p2.x() - (p3.x() - p1.x()) * control_point_scale
            cp2_y = p2.y() - (p3.y() - p1.y()) * control_point_scale
            cp2 = QPointF(cp2_x, cp2_y)

            path.cubicTo(cp1, cp2, p2)

        return path

    def _resample_points(self, points: list[QPointF], num_target_points: int) -> list[QPointF]:
        """
        Resample points to a target count.

        Args:
            points: Original list of points
            num_target_points: Desired number of output points

        Returns:
            List of resampled QPointF
        """
        if not points:
            return []

        n = len(points)
        if n == 0 or num_target_points <= 0:
            return []

        if n <= num_target_points:
            # Pad with last point if needed
            result = points.copy()
            while len(result) < num_target_points:
                result.append(result[-1])
            return result

        # Downsample by selecting evenly distributed points
        result = []
        for i in range(num_target_points):
            idx = int(i * n / num_target_points)
            result.append(points[idx])

        return result
