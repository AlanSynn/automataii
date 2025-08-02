# src/automataii/ui/views/image_processing/modes/pan_zoom_mode.py

import logging

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PyQt6.QtWidgets import QGraphicsView

from .base_mode import IImageProcessingMode

logger = logging.getLogger(__name__)


class PanZoomMode(IImageProcessingMode):
    """
    Default interaction mode for panning and zooming the image processing view.
    Handles basic navigation functionality.
    """

    def __init__(self, state_manager, view_ref: QGraphicsView | None = None):
        super().__init__(state_manager, view_ref)

        # Panning state
        self.is_panning = False
        self.last_pan_point: QPointF | None = None

        # Zoom settings
        self.zoom_factor = 1.15
        self.min_zoom = 0.1
        self.max_zoom = 10.0

        # Pinch gesture state
        self.pinch_mode = False
        self.pinch_start_scale = 1.0

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
        if not self.view_ref or self.pinch_mode:
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
        current_scale = current_transform.m11()
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

    def handle_viewport_event(self, event) -> bool:
        """Handle viewport events for gesture support."""
        from PyQt6.QtCore import QEvent

        if event.type() == QEvent.Type.Gesture:
            return self._handle_gesture_event(event)

        return False

    def handle_draw_background(self, painter, rect) -> bool:
        """Handle background drawing for grid."""
        if not self.view_ref:
            return False

        # Use the view's built-in grid drawing
        return False  # Let the view handle it

    def _handle_gesture_event(self, event) -> bool:
        """Handle pinch gesture events."""
        from PyQt6.QtCore import Qt

        gesture = event.gesture(Qt.GestureType.PinchGesture)
        if gesture:
            self._handle_pinch_gesture(gesture)
            return True
        return False

    def _handle_pinch_gesture(self, gesture) -> None:
        """Handle pinch gesture for zooming."""
        from PyQt6.QtCore import Qt

        if gesture.state() == Qt.GestureState.GestureStarted:
            self.pinch_mode = True
            self.pinch_start_scale = self.view_ref.transform().m11()

        elif gesture.state() == Qt.GestureState.GestureUpdated and self.pinch_mode:
            target_scale = self.pinch_start_scale * gesture.scaleFactor()

            # Clamp the target scale
            target_scale = max(self.min_zoom, min(target_scale, self.max_zoom))

            current_scale = self.view_ref.transform().m11()
            if abs(target_scale - current_scale) > 0.001:
                zoom_factor = target_scale / current_scale
                self.view_ref.scale(zoom_factor, zoom_factor)
                self.state.set_zoom_level(target_scale)

        elif gesture.state() == Qt.GestureState.GestureFinished:
            self.pinch_mode = False

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
        self.pinch_mode = False
        logger.debug("Exited pan/zoom mode")

    def update_mode_state(self) -> None:
        """Update pan/zoom mode state."""
        # No periodic updates needed for pan/zoom mode
        pass
