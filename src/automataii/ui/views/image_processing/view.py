# src/automataii/ui/views/image_processing/view.py

import logging

from PyQt6.QtCore import QLineF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QResizeEvent, QWheelEvent
from PyQt6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView

from .input_handler import ImageProcessingInputHandler
from .state_manager import ImageProcessingViewState

logger = logging.getLogger(__name__)


class ImageProcessingView(QGraphicsView):
    """
    Refactored ImageProcessingView that follows the "dumb view" pattern.

    This view is responsible ONLY for:
    1. Rendering the QGraphicsScene with grid background
    2. Emitting signals for user interactions
    3. Delegating all event handling to InputHandler

    All interaction logic is delegated to the InputHandler via Strategy pattern.
    All business logic is handled by external services.
    """

    # Signals for external communication
    image_load_requested = pyqtSignal(str)  # image_path
    skeleton_load_requested = pyqtSignal(dict)  # skeleton_data
    joint_position_changed = pyqtSignal(str, object)  # joint_id, new_position
    character_parts_load_requested = pyqtSignal(dict, dict, object)  # parts_data, mapping, offset
    display_unit_change_requested = pyqtSignal(str)  # unit
    debug_mode_toggle_requested = pyqtSignal(bool)  # enabled
    view_reset_requested = pyqtSignal()
    zoom_fit_requested = pyqtSignal()

    def __init__(self, scene: QGraphicsScene | None = None, parent=None):
        super().__init__(scene, parent)

        # Initialize state manager
        self.state = ImageProcessingViewState()

        # Initialize input handler
        self.input_handler = ImageProcessingInputHandler(self.state, self, self)

        # Configure the view
        self._setup_view()

        # Connect state signals
        self._connect_state_signals()

        logger.info("ImageProcessingView initialized with new architecture")

    def _setup_view(self) -> None:
        """Setup the view configuration."""
        # Rendering settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Viewport settings
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        # Scroll bars
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Drag mode
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        # Touch and gestures
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.grabGesture(Qt.GestureType.PinchGesture)

        # Styling
        self.viewport().setStyleSheet("background-color: white; border-radius: 10px;")

        # Mouse tracking for hover effects
        self.setMouseTracking(True)

        # Initialize DPI
        try:
            self.state.dpi = QApplication.primaryScreen().logicalDotsPerInch()
        except AttributeError:
            self.state.dpi = 96
            logger.warning(f"Could not get screen DPI, defaulting to {self.state.dpi} DPI")

    def _connect_state_signals(self) -> None:
        """Connect state manager signals."""
        self.state.display_unit_changed.connect(self._on_display_unit_changed)
        self.state.debug_mode_changed.connect(self._on_debug_mode_changed)
        self.state.zoom_changed.connect(self._on_zoom_changed)

    def _on_display_unit_changed(self, unit: str) -> None:
        """Handle display unit changes."""
        self.viewport().update()  # Trigger background redraw
        logger.info(f"Display unit changed to: {unit}")

    def _on_debug_mode_changed(self, enabled: bool) -> None:
        """Handle debug mode changes."""
        self.viewport().update()  # Trigger foreground redraw
        logger.info(f"Debug mode changed to: {enabled}")

    def _on_zoom_changed(self, zoom_level: float) -> None:
        """Handle zoom level changes."""
        logger.debug(f"Zoom changed to: {zoom_level:.2f}x")

    # Grid background drawing
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """Draw grid background based on display unit."""
        super().drawBackground(painter, rect)

        # Let input handler handle background drawing
        if self.input_handler.handle_draw_background(painter, rect):
            return

        # Fallback to default grid drawing
        self._draw_default_grid(painter, rect)

    def _draw_default_grid(self, painter: QPainter, rect: QRectF) -> None:
        """Draw default grid background."""
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Calculate grid size based on display unit
        if self.state.display_unit == "cm":
            cm_to_inch = 1 / 2.54
            grid_size_pixels = int(self.state.dpi * cm_to_inch)
        elif self.state.display_unit == "inch":
            grid_size_pixels = int(self.state.dpi)
        else:  # px
            grid_size_pixels = 20

        if grid_size_pixels <= 0:
            grid_size_pixels = 20

        # Grid styling
        light_pen = QPen(QColor(230, 230, 230), 1)
        dark_pen = QPen(QColor(200, 200, 200), 1.5)
        major_interval = 1 if self.state.display_unit in ["cm", "inch"] else 5

        # Get visible rectangle
        visible_rect = self.mapToScene(self.viewport().rect()).boundingRect()

        left = int(visible_rect.left() / grid_size_pixels) * grid_size_pixels
        top = int(visible_rect.top() / grid_size_pixels) * grid_size_pixels
        right = visible_rect.right()
        bottom = visible_rect.bottom()

        # Draw vertical lines
        x = left
        count_v = int(round(visible_rect.left() / grid_size_pixels))
        while x < right:
            painter.setPen(dark_pen if count_v % major_interval == 0 else light_pen)
            painter.drawLine(QLineF(x, top, x, bottom))
            x += grid_size_pixels
            count_v += 1

        # Draw horizontal lines
        y = top
        count_h = int(round(visible_rect.top() / grid_size_pixels))
        while y < bottom:
            painter.setPen(dark_pen if count_h % major_interval == 0 else light_pen)
            painter.drawLine(QLineF(left, y, right, y))
            y += grid_size_pixels
            count_h += 1

        painter.restore()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        """Draw foreground elements (debug info, etc.)."""
        super().drawForeground(painter, rect)

        # Let input handler handle foreground drawing
        self.input_handler.handle_draw_foreground(painter, rect)

    # Event handling - all delegated to input handler
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press events."""
        if not self.input_handler.handle_mouse_press(event):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move events."""
        if not self.input_handler.handle_mouse_move(event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release events."""
        if not self.input_handler.handle_mouse_release(event):
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Handle mouse double click events."""
        if not self.input_handler.handle_mouse_double_click(event):
            super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle wheel events."""
        if not self.input_handler.handle_wheel_event(event):
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        if not self.input_handler.handle_key_press(event):
            super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle resize events."""
        if not self.input_handler.handle_resize_event(event):
            super().resizeEvent(event)

    def viewportEvent(self, event) -> bool:
        """Handle viewport events (gestures, etc.)."""
        if self.input_handler.handle_viewport_event(event):
            return True
        return super().viewportEvent(event)

    # Public API methods (these emit signals for external handling)
    def load_image(self, image_path: str) -> None:
        """Request image loading via signal."""
        self.image_load_requested.emit(image_path)

    def load_skeleton(self, skeleton_data: dict) -> None:
        """Request skeleton loading via signal."""
        self.skeleton_load_requested.emit(skeleton_data)

    def set_display_unit(self, unit: str) -> None:
        """Request display unit change via signal."""
        self.display_unit_change_requested.emit(unit)

    def set_debug_mode(self, enabled: bool) -> None:
        """Request debug mode toggle via signal."""
        self.debug_mode_toggle_requested.emit(enabled)

    def reset_view(self) -> None:
        """Request view reset via signal."""
        self.view_reset_requested.emit()

    def zoom_to_fit(self) -> None:
        """Request zoom to fit via signal."""
        self.zoom_fit_requested.emit()

    def set_zoom_scale(self, scale_factor: float) -> None:
        """Set the zoom scale factor."""
        from PyQt6.QtGui import QTransform

        transform = QTransform()
        transform.scale(scale_factor, scale_factor)
        self.setTransform(transform)
        self.state.zoom_level = scale_factor

    # Convenience methods for external access
    def zoom_in(self) -> None:
        """Zoom in via input handler."""
        self.input_handler.zoom_in()

    def zoom_out(self) -> None:
        """Zoom out via input handler."""
        self.input_handler.zoom_out()

    def get_current_mode(self) -> str:
        """Get the current interaction mode."""
        return self.state.get_current_mode().value

    def get_zoom_level(self) -> float:
        """Get the current zoom level."""
        return self.state.zoom_level

    def get_display_unit(self) -> str:
        """Get the current display unit."""
        return self.state.display_unit

    def is_debug_mode(self) -> bool:
        """Check if debug mode is enabled."""
        return self.state.debug_mode
