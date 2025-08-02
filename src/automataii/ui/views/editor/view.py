# src/automataii/ui/views/editor/view.py

import logging
from typing import Any

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import QGraphicsView

from .input_handler import EditorInputHandler
from .state_manager import EditorMode, EditorViewState

logger = logging.getLogger(__name__)


class EditorView(QGraphicsView):
    """
    Refactored EditorView that follows the "dumb view" pattern.

    This view is responsible ONLY for:
    1. Rendering the QGraphicsScene
    2. Emitting signals for user interactions
    3. Drawing the background grid

    All interaction logic is delegated to the InputHandler via Strategy pattern.
    All business logic is handled by external services.
    """

    # Pure UI signals - emitted for external handling
    zoom_changed = pyqtSignal(float)
    mode_changed = pyqtSignal(str)

    # Legacy signals for backwards compatibility
    # These will eventually be replaced by service-based communication
    part_item_clicked = pyqtSignal(object)
    part_item_double_clicked = pyqtSignal(object)
    part_item_moved = pyqtSignal(object, QPointF)
    freehandPathCompleted = pyqtSignal(object)  # Signal for completed freehand path

    def __init__(self, scene, parent_window=None, mechanism_mode=False):
        super().__init__(scene, parent_window)

        # Store parameters
        self.parent_window = parent_window
        self.mechanism_mode = mechanism_mode

        # Initialize state and input handling
        self.state = EditorViewState(self)
        self.input_handler = EditorInputHandler(self.state, self, self)

        # View configuration
        self._setup_view()

        # Connect state signals
        self._connect_signals()

        logger.info(f"EditorView initialized (mechanism_mode={mechanism_mode})")

    def _setup_view(self) -> None:
        """Configure the view settings."""
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)

        # Set focus policy to receive key events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Connect state changes to UI updates
        self.state.zoom_changed.connect(self.zoom_changed.emit)
        self.state.mode_changed.connect(lambda mode: self.mode_changed.emit(mode.value))

    # Event handling - delegates to InputHandler

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press events."""
        handled = self.input_handler.handle_mouse_press(event)
        if not handled:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move events."""
        handled = self.input_handler.handle_mouse_move(event)
        if not handled:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release events."""
        handled = self.input_handler.handle_mouse_release(event)
        if not handled:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Handle mouse double click events."""
        handled = self.input_handler.handle_mouse_double_click(event)
        if not handled:
            super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle wheel events."""
        handled = self.input_handler.handle_wheel_event(event)
        if not handled:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        handled = self.input_handler.handle_key_press(event)
        if not handled:
            super().keyPressEvent(event)

    # Drawing methods - pure rendering

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """Draw the background grid."""
        super().drawBackground(painter, rect)

        # Draw grid if enabled
        self._draw_grid(painter, rect)

    def _draw_grid(self, painter: QPainter, rect: QRectF) -> None:
        """Draw the background grid."""
        # Grid settings
        grid_size = 20  # Base grid size in pixels

        # Convert display unit to scale factor
        unit = self.state.display_unit
        if unit == "inch":
            grid_size = int(grid_size * 2.54)  # Convert to inches
        elif unit == "px":
            grid_size = 10  # Smaller grid for pixels

        # Calculate grid bounds
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)

        # Create grid lines
        lines = []

        # Vertical lines
        x = left
        while x < rect.right():
            lines.append((int(x), int(rect.top()), int(x), int(rect.bottom())))
            x += grid_size

        # Horizontal lines
        y = top
        while y < rect.bottom():
            lines.append((int(rect.left()), int(y), int(rect.right()), int(y)))
            y += grid_size

        # Draw grid
        painter.save()

        # Set grid color based on zoom level
        zoom_level = self.state.zoom_level
        if zoom_level > 2.0:
            alpha = 100
        elif zoom_level > 1.0:
            alpha = 60
        else:
            alpha = 30

        grid_color = QColor(200, 200, 200, alpha)
        painter.setPen(QPen(grid_color, 0.5))

        for line in lines:
            painter.drawLine(line[0], line[1], line[2], line[3])

        painter.restore()

    # Public API methods for external control

    def set_mode(self, mode: str) -> None:
        """Set the interaction mode."""
        try:
            editor_mode = EditorMode(mode)
            self.state.set_mode(editor_mode)
        except ValueError:
            logger.warning(f"Unknown mode: {mode}")

    def set_display_unit(self, unit: str) -> None:
        """Set the display unit for the grid."""
        self.state.set_display_unit(unit)
        self.viewport().update()  # Trigger background redraw

    def set_joint_map(self, joint_map: dict[str, str] | None) -> None:
        """Set the joint mapping."""
        self.state.set_joint_map(joint_map)

    def get_selected_item(self):
        """Get the currently selected item."""
        return self.state.selected_item

    def set_selected_part(self, part_name: str | None, item=None) -> None:
        """Set the selected part."""
        self.state.set_selected_part(part_name, item)

    # View manipulation methods - delegate to input handler

    def zoom_in(self) -> None:
        """Zoom in."""
        self.input_handler.zoom_in()

    def zoom_out(self) -> None:
        """Zoom out."""
        self.input_handler.zoom_out()

    def reset_view(self) -> None:
        """Reset view to default."""
        self.input_handler.reset_view()

    def zoom_to_fit(self) -> None:
        """Zoom to fit all items."""
        self.input_handler.zoom_to_fit()

    def set_zoom_level(self, zoom_factor: float) -> None:
        """Set specific zoom level."""
        if zoom_factor <= 0:
            return

        # Calculate scale factor needed
        current_scale = self.transform().m11()
        scale_factor = zoom_factor / current_scale

        # Apply the scale
        self.scale(scale_factor, scale_factor)

        # Update state
        self.state.set_zoom_level(zoom_factor)

    # Legacy API methods for backwards compatibility
    # These maintain the same interface as the original EditorView

    def start_define_joint(self) -> None:
        """Start joint definition mode (legacy API)."""
        self.input_handler.set_joint_definition_mode()

    def start_define_motion_path(self, target_item) -> None:
        """Start motion path definition mode (legacy API)."""
        self.state.start_motion_path_drawing(target_item)

    def start_select_end_effector(self, target_item) -> None:
        """Start end effector selection mode (legacy API)."""
        self.state.start_end_effector_selection(target_item)

    def start_simulation(self) -> None:
        """Start simulation mode (legacy API)."""
        self.state.start_simulation()

    def stop_simulation(self) -> None:
        """Stop simulation mode (legacy API)."""
        self.state.stop_simulation()

    def reset_simulation(self) -> None:
        """Reset simulation (legacy API)."""
        self.state.stop_simulation()

    # Utility methods

    def get_camera_state(self) -> dict[str, Any]:
        """Get current camera/view state."""
        transform = self.transform()
        return {
            "zoom": transform.m11(),
            "pan_x": self.horizontalScrollBar().value(),
            "pan_y": self.verticalScrollBar().value(),
            "mode": self.state.current_mode.value,
        }

    def set_camera_state(self, state: dict[str, Any]) -> None:
        """Set camera/view state."""
        if "zoom" in state:
            self.set_zoom_level(state["zoom"])

        if "pan_x" in state:
            self.horizontalScrollBar().setValue(state["pan_x"])

        if "pan_y" in state:
            self.verticalScrollBar().setValue(state["pan_y"])

        if "mode" in state:
            self.set_mode(state["mode"])

    def resizeEvent(self, event) -> None:
        """Handle resize events."""
        super().resizeEvent(event)
        # Any resize-specific logic can go here
