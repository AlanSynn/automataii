# src/automataii/ui/views/image_processing/input_handler.py

import logging

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QPainter, QResizeEvent, QWheelEvent
from PyQt6.QtWidgets import QGraphicsView

from .modes import (
    DebugMode,
    HoverMode,
    IImageProcessingMode,
    JointDragMode,
    PanZoomMode,
)
from .state_manager import ImageProcessingMode, ImageProcessingViewState

logger = logging.getLogger(__name__)


class ImageProcessingInputHandler(QObject):
    """
    Handles input events and delegates them to the appropriate interaction mode.
    Implements the Strategy pattern - different modes handle events differently.
    """

    def __init__(
        self,
        state_manager: ImageProcessingViewState,
        view_ref: QGraphicsView | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)

        self.state = state_manager
        self.view_ref = view_ref

        # Initialize available modes
        self._modes: dict[ImageProcessingMode, IImageProcessingMode] = {
            ImageProcessingMode.PAN_ZOOM: PanZoomMode(state_manager, view_ref),
            ImageProcessingMode.JOINT_DRAG: JointDragMode(state_manager, view_ref),
            ImageProcessingMode.HOVER: HoverMode(state_manager, view_ref),
            ImageProcessingMode.DEBUG: DebugMode(state_manager, view_ref),
        }

        # Current active mode
        self._current_mode: IImageProcessingMode = self._modes[ImageProcessingMode.PAN_ZOOM]

        # Persistent modes (always active in background)
        self._persistent_modes: list[IImageProcessingMode] = [
            self._modes[ImageProcessingMode.HOVER],
            self._modes[ImageProcessingMode.DEBUG],
        ]

        # Connect to state changes
        self.state.mode_changed.connect(self._on_mode_changed)

        logger.info("ImageProcessingInputHandler initialized")

    def add_mode(self, mode_type: ImageProcessingMode, mode_instance: IImageProcessingMode) -> None:
        """Add a new interaction mode."""
        self._modes[mode_type] = mode_instance
        logger.debug(f"Added mode: {mode_type.value}")

    def get_current_mode(self) -> IImageProcessingMode:
        """Get the currently active mode."""
        return self._current_mode

    def set_view_reference(self, view_ref: QGraphicsView) -> None:
        """Set the view reference for all modes."""
        self.view_ref = view_ref
        for mode in self._modes.values():
            mode.view_ref = view_ref

    def _on_mode_changed(self, new_mode: ImageProcessingMode) -> None:
        """Handle mode changes from the state manager."""
        if new_mode in self._modes:
            # Exit current mode
            self._current_mode.exit_mode()

            # Switch to new mode
            self._current_mode = self._modes[new_mode]

            # Enter new mode
            self._current_mode.enter_mode()

            logger.info(f"Switched to mode: {new_mode.value}")
        else:
            logger.warning(f"Mode {new_mode.value} not implemented, staying in current mode")

    # Event handling methods that delegate to current mode and persistent modes

    def handle_mouse_press(self, event: QMouseEvent) -> bool:
        """Handle mouse press events."""
        if not self.view_ref:
            return False

        scene_pos = self.view_ref.mapToScene(event.pos())

        # Try current mode first
        if self._current_mode.handle_mouse_press(event, scene_pos):
            return True

        # Try persistent modes
        for mode in self._persistent_modes:
            if mode.handle_mouse_press(event, scene_pos):
                return True

        return False

    def handle_mouse_move(self, event: QMouseEvent) -> bool:
        """Handle mouse move events."""
        if not self.view_ref:
            return False

        scene_pos = self.view_ref.mapToScene(event.pos())

        # Try current mode first
        if self._current_mode.handle_mouse_move(event, scene_pos):
            return True

        # Try persistent modes
        for mode in self._persistent_modes:
            if mode.handle_mouse_move(event, scene_pos):
                return True

        return False

    def handle_mouse_release(self, event: QMouseEvent) -> bool:
        """Handle mouse release events."""
        if not self.view_ref:
            return False

        scene_pos = self.view_ref.mapToScene(event.pos())

        # Try current mode first
        if self._current_mode.handle_mouse_release(event, scene_pos):
            return True

        # Try persistent modes
        for mode in self._persistent_modes:
            if mode.handle_mouse_release(event, scene_pos):
                return True

        return False

    def handle_mouse_double_click(self, event: QMouseEvent) -> bool:
        """Handle mouse double click events."""
        if not self.view_ref:
            return False

        scene_pos = self.view_ref.mapToScene(event.pos())

        # Try current mode first
        if self._current_mode.handle_mouse_double_click(event, scene_pos):
            return True

        # Try persistent modes
        for mode in self._persistent_modes:
            if mode.handle_mouse_double_click(event, scene_pos):
                return True

        return False

    def handle_wheel_event(self, event: QWheelEvent) -> bool:
        """Handle wheel events."""
        # Try current mode first
        if self._current_mode.handle_wheel_event(event):
            return True

        # Try persistent modes
        for mode in self._persistent_modes:
            if mode.handle_wheel_event(event):
                return True

        return False

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle key press events."""
        # Try current mode first
        if self._current_mode.handle_key_press(event):
            return True

        # Try persistent modes
        for mode in self._persistent_modes:
            if mode.handle_key_press(event):
                return True

        return False

    def handle_resize_event(self, event: QResizeEvent) -> bool:
        """Handle resize events."""
        # Try current mode first
        if self._current_mode.handle_resize_event(event):
            return True

        # Try persistent modes
        for mode in self._persistent_modes:
            if mode.handle_resize_event(event):
                return True

        return False

    def handle_viewport_event(self, event: QEvent) -> bool:
        """Handle viewport events."""
        # Try current mode first
        if self._current_mode.handle_viewport_event(event):
            return True

        # Try persistent modes
        for mode in self._persistent_modes:
            if mode.handle_viewport_event(event):
                return True

        return False

    def handle_draw_background(self, painter: QPainter, rect) -> bool:
        """Handle background drawing."""
        # Try current mode first
        if self._current_mode.handle_draw_background(painter, rect):
            return True

        # Try persistent modes
        for mode in self._persistent_modes:
            if mode.handle_draw_background(painter, rect):
                return True

        return False

    def handle_draw_foreground(self, painter: QPainter, rect) -> bool:
        """Handle foreground drawing."""
        # Try current mode first
        if self._current_mode.handle_draw_foreground(painter, rect):
            return True

        # Try persistent modes
        for mode in self._persistent_modes:
            if mode.handle_draw_foreground(painter, rect):
                return True

        return False

    # Public API for mode switching

    def set_pan_zoom_mode(self) -> None:
        """Switch to pan/zoom mode."""
        self.state.set_mode(ImageProcessingMode.PAN_ZOOM)

    def set_joint_drag_mode(self) -> None:
        """Switch to joint drag mode."""
        self.state.set_mode(ImageProcessingMode.JOINT_DRAG)

    def set_hover_mode(self) -> None:
        """Switch to hover mode."""
        self.state.set_mode(ImageProcessingMode.HOVER)

    def set_debug_mode(self, enabled: bool) -> None:
        """Toggle debug mode."""
        self.state.set_debug_mode(enabled)

    # Convenience methods for common operations

    def zoom_in(self) -> None:
        """Zoom in if in pan/zoom mode."""
        if isinstance(self._current_mode, PanZoomMode):
            self._current_mode.zoom_in()

    def zoom_out(self) -> None:
        """Zoom out if in pan/zoom mode."""
        if isinstance(self._current_mode, PanZoomMode):
            self._current_mode.zoom_out()

    def reset_view(self) -> None:
        """Reset view if in pan/zoom mode."""
        if isinstance(self._current_mode, PanZoomMode):
            self._current_mode.reset_view()

    def zoom_to_fit(self) -> None:
        """Zoom to fit if in pan/zoom mode."""
        if isinstance(self._current_mode, PanZoomMode):
            self._current_mode.zoom_to_fit()

    def update_all_modes(self) -> None:
        """Update all modes' internal state."""
        for mode in self._modes.values():
            mode.update_mode_state()
