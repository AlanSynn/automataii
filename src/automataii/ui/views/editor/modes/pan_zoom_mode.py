# src/automataii/ui/views/editor/modes/pan_zoom_mode.py

import logging
from typing import Optional

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent

from .base_mode import IInteractionMode

logger = logging.getLogger(__name__)


class PanZoomMode(IInteractionMode):
    """
    Default interaction mode for panning and zooming the view.
    Handles basic navigation functionality.
    """

    def __init__(self, state_manager, view_ref: Optional = None):
        super().__init__(state_manager, view_ref)

        # Panning state
        self.is_panning = False
        self.last_pan_point: QPointF | None = None

        # Zoom settings
        self.zoom_factor = 1.15
        self.min_zoom = 0.1
        self.max_zoom = 10.0

    def handle_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse press for panning initiation."""
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            # Start panning
            self.is_panning = True
            self.last_pan_point = event.pos()
            if self.view_ref:
                self.view_ref.setCursor(Qt.CursorShape.ClosedHandCursor)
            logger.debug("Started panning")
            return True

        return False

    def handle_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse move for panning."""
        if self.is_panning and self.last_pan_point and self.view_ref:
            # Calculate pan delta
            delta = event.pos() - self.last_pan_point
            self.last_pan_point = event.pos()

            # Apply panning
            h_bar = self.view_ref.horizontalScrollBar()
            v_bar = self.view_ref.verticalScrollBar()

            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())

            return True

        return False

    def handle_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse release to end panning."""
        if self.is_panning:
            self.is_panning = False
            self.last_pan_point = None
            if self.view_ref:
                self.view_ref.setCursor(self.get_cursor())
            logger.debug("Stopped panning")
            return True

        return False

    def handle_wheel_event(self, event: QWheelEvent) -> bool:
        """Handle wheel events for zooming."""
        if not self.view_ref:
            return False

        # Calculate zoom direction
        zoom_in = event.angleDelta().y() > 0

        # Calculate zoom factor
        if zoom_in:
            scale_factor = self.zoom_factor
        else:
            scale_factor = 1.0 / self.zoom_factor

        # Get current zoom level
        current_transform = self.view_ref.transform()
        current_scale = current_transform.m11()  # Get current scale
        new_scale = current_scale * scale_factor

        # Check zoom limits
        if new_scale < self.min_zoom or new_scale > self.max_zoom:
            return True  # Consume event but don't zoom

        # Apply zoom
        self.view_ref.scale(scale_factor, scale_factor)

        # Update state
        self.state.set_zoom_level(new_scale)

        logger.debug(f"Zoomed to {new_scale:.2f}x")
        return True

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle key presses for keyboard shortcuts."""
        if not self.view_ref:
            return False

        key = event.key()

        # Reset view with 'R' key
        if key == Qt.Key.Key_R:
            self.reset_view()
            return True

        # Zoom to fit with 'F' key
        elif key == Qt.Key.Key_F:
            self.zoom_to_fit()
            return True

        # Zoom in with '+'
        elif key == Qt.Key.Key_Plus:
            self.zoom_in()
            return True

        # Zoom out with '-'
        elif key == Qt.Key.Key_Minus:
            self.zoom_out()
            return True

        return False

    def zoom_in(self) -> None:
        """Zoom in programmatically."""
        if self.view_ref:
            current_scale = self.view_ref.transform().m11()
            new_scale = current_scale * self.zoom_factor

            if new_scale <= self.max_zoom:
                self.view_ref.scale(self.zoom_factor, self.zoom_factor)
                self.state.set_zoom_level(new_scale)
                logger.debug(f"Zoomed in to {new_scale:.2f}x")

    def zoom_out(self) -> None:
        """Zoom out programmatically."""
        if self.view_ref:
            current_scale = self.view_ref.transform().m11()
            scale_factor = 1.0 / self.zoom_factor
            new_scale = current_scale * scale_factor

            if new_scale >= self.min_zoom:
                self.view_ref.scale(scale_factor, scale_factor)
                self.state.set_zoom_level(new_scale)
                logger.debug(f"Zoomed out to {new_scale:.2f}x")

    def reset_view(self) -> None:
        """Reset view to default zoom and position."""
        if self.view_ref:
            self.view_ref.resetTransform()
            self.state.set_zoom_level(1.0)
            logger.debug("View reset to default")

    def zoom_to_fit(self) -> None:
        """Zoom to fit all items in the scene."""
        if not self.view_ref or not self.view_ref.scene():
            return

        scene = self.view_ref.scene()
        items_rect = scene.itemsBoundingRect()

        if items_rect.isEmpty():
            return

        # Add some padding
        padding = 50
        items_rect.adjust(-padding, -padding, padding, padding)

        # Fit the view
        self.view_ref.fitInView(items_rect, Qt.AspectRatioMode.KeepAspectRatio)

        # Update state with new zoom level
        new_scale = self.view_ref.transform().m11()
        self.state.set_zoom_level(new_scale)
        logger.debug(f"Zoomed to fit at {new_scale:.2f}x")

    def get_cursor(self):
        """Return the default cursor for pan/zoom mode."""
        return Qt.CursorShape.ArrowCursor

    def enter_mode(self) -> None:
        """Setup when entering pan/zoom mode."""
        if self.view_ref:
            self.view_ref.setCursor(self.get_cursor())
        logger.debug("Entered pan/zoom mode")

    def exit_mode(self) -> None:
        """Cleanup when exiting pan/zoom mode."""
        self.is_panning = False
        self.last_pan_point = None
        logger.debug("Exited pan/zoom mode")
