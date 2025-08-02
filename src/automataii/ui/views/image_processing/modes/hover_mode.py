# src/automataii/ui/views/image_processing/modes/hover_mode.py

import logging

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QGraphicsView

from .base_mode import IImageProcessingMode

logger = logging.getLogger(__name__)


class HoverMode(IImageProcessingMode):
    """
    Persistent mode for handling hover effects and controls.
    This mode runs in the background and provides hover functionality.
    """

    def __init__(self, state_manager, view_ref: QGraphicsView | None = None):
        super().__init__(state_manager, view_ref)

        # Hover state
        self.hover_active = False
        self.hover_corner_size = 150

    def handle_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse press - hover mode doesn't consume press events."""
        return False

    def handle_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse move for hover effects."""
        if not self.view_ref:
            return False

        # Check if mouse is in hover control area
        self._update_hover_controls(event.pos())

        return False  # Don't consume the event

    def handle_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse release - hover mode doesn't consume release events."""
        return False

    def _update_hover_controls(self, position: QPointF) -> None:
        """Update hover controls visibility based on mouse position."""
        if not self.view_ref:
            return

        view_rect = self.view_ref.rect()
        corner_rect = view_rect.adjusted(
            view_rect.width() - self.hover_corner_size,
            view_rect.height() - self.hover_corner_size,
            0,
            0,
        )

        should_show = corner_rect.contains(position)

        if should_show != self.hover_active:
            self.hover_active = should_show
            self.state.hover_controls_visible = should_show

            if should_show:
                # Update zoom level display
                current_scale = self.view_ref.transform().m11()
                # TODO: Update hover controls with current zoom level
                logger.debug(f"Hover controls shown, zoom: {current_scale:.2f}x")
            else:
                logger.debug("Hover controls hidden")

    def get_cursor(self):
        """Return cursor for hover mode."""
        return Qt.CursorShape.ArrowCursor

    def enter_mode(self) -> None:
        """Setup when entering hover mode."""
        logger.debug("Entered hover mode")

    def exit_mode(self) -> None:
        """Cleanup when exiting hover mode."""
        self.hover_active = False
        self.state.hover_controls_visible = False
        logger.debug("Exited hover mode")

    def update_mode_state(self) -> None:
        """Update hover mode state."""
        # No periodic updates needed for hover mode
        pass
