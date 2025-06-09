"""Handler for view operations."""

import logging
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal, QPointF, QRectF

from automataii.gui.tabs.editor.state import EditorState, EditorMode
from automataii.events import event_bus, ViewZoomChangedEvent

class ViewHandler(QObject):
    """Handles view-related operations like zoom and pan."""

    # Signals
    zoom_changed = pyqtSignal(float)  # zoom_level
    view_centered = pyqtSignal(QPointF)  # center_point
    fit_requested = pyqtSignal()
    mode_changed = pyqtSignal(str)  # mode_name

    def __init__(self, state: EditorState):
        super().__init__()
        self._state = state
        self._min_zoom = 0.1
        self._max_zoom = 5.0

        logging.debug("ViewHandler initialized")

    def set_zoom(self, zoom_level: float) -> None:
        """Set zoom level.

        Args:
            zoom_level: Zoom factor (1.0 = 100%)
        """
        # Clamp zoom level
        zoom_level = max(self._min_zoom, min(self._max_zoom, zoom_level))

        if abs(self._state.zoom_level - zoom_level) < 0.001:
            return

        self._state.zoom_level = zoom_level
        self.zoom_changed.emit(zoom_level)

        # Publish event
        event = ViewZoomChangedEvent(
            zoom_factor=zoom_level,
            view_name="editor",
            source="view_handler"
        )
        event_bus.publish(event)

        logging.debug(f"ViewHandler: Zoom set to {zoom_level:.2f}")

    def zoom_in(self, factor: float = 1.25) -> None:
        """Zoom in by factor."""
        new_zoom = self._state.zoom_level * factor
        self.set_zoom(new_zoom)

    def zoom_out(self, factor: float = 0.8) -> None:
        """Zoom out by factor."""
        new_zoom = self._state.zoom_level * factor
        self.set_zoom(new_zoom)

    def reset_zoom(self) -> None:
        """Reset zoom to 100%."""
        self.set_zoom(1.0)

    def center_view(self, center: QPointF) -> None:
        """Center view on a point.

        Args:
            center: Point to center on
        """
        self._state.view_center = center
        self.view_centered.emit(center)
        logging.debug(f"ViewHandler: View centered at {center}")

    def fit_to_contents(self) -> None:
        """Request to fit view to contents."""
        self.fit_requested.emit()
        logging.debug("ViewHandler: Fit to contents requested")

    def set_mode(self, mode: EditorMode) -> None:
        """Set editor interaction mode.

        Args:
            mode: New editor mode
        """
        if self._state.mode == mode:
            return

        # Some modes require cleanup
        if self._state.mode == EditorMode.DRAW_PATH and mode != EditorMode.DRAW_PATH:
            # Cancel any active drawing
            self._state.is_drawing_path = False
            self._state.current_path_points.clear()

        self._state.mode = mode
        self.mode_changed.emit(mode.value)
        logging.info(f"ViewHandler: Mode changed to {mode.value}")

    def get_mode(self) -> EditorMode:
        """Get current editor mode."""
        return self._state.mode

    def toggle_grid(self) -> None:
        """Toggle grid visibility."""
        self._state.show_grid = not self._state.show_grid
        logging.debug(f"ViewHandler: Grid {'shown' if self._state.show_grid else 'hidden'}")

    def toggle_snap_to_grid(self) -> None:
        """Toggle snap to grid."""
        self._state.snap_to_grid = not self._state.snap_to_grid
        logging.debug(f"ViewHandler: Snap to grid {'enabled' if self._state.snap_to_grid else 'disabled'}")

    def set_grid_size(self, size: int) -> None:
        """Set grid size.

        Args:
            size: Grid size in pixels
        """
        if size > 0:
            self._state.grid_size = size
            logging.debug(f"ViewHandler: Grid size set to {size}")

    def snap_point_to_grid(self, point: QPointF) -> QPointF:
        """Snap a point to grid if enabled.

        Args:
            point: Point to snap

        Returns:
            Snapped point or original if snap disabled
        """
        if not self._state.snap_to_grid:
            return point

        grid_size = self._state.grid_size
        x = round(point.x() / grid_size) * grid_size
        y = round(point.y() / grid_size) * grid_size

        return QPointF(x, y)