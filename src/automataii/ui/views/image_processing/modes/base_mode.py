# src/automataii/ui/views/image_processing/modes/base_mode.py

from abc import ABC, abstractmethod

from PyQt6.QtCore import QEvent, QPointF
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QPainter, QResizeEvent, QWheelEvent
from PyQt6.QtWidgets import QGraphicsView


class IImageProcessingMode(ABC):
    """
    Interface for all image processing interaction modes.
    Each mode implements specific behavior for user interactions.
    """

    def __init__(self, state_manager, view_ref: QGraphicsView | None = None):
        """
        Initialize the interaction mode.

        Args:
            state_manager: The image processing state manager
            view_ref: Optional reference to the view for direct manipulation
        """
        self.state = state_manager
        self.view_ref = view_ref

    @abstractmethod
    def handle_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """
        Handle mouse press events.

        Args:
            event: The original QMouseEvent
            scene_pos: Position in scene coordinates

        Returns:
            bool: True if the event was handled, False otherwise
        """
        pass

    @abstractmethod
    def handle_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """
        Handle mouse move events.

        Args:
            event: The original QMouseEvent
            scene_pos: Position in scene coordinates

        Returns:
            bool: True if the event was handled, False otherwise
        """
        pass

    @abstractmethod
    def handle_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """
        Handle mouse release events.

        Args:
            event: The original QMouseEvent
            scene_pos: Position in scene coordinates

        Returns:
            bool: True if the event was handled, False otherwise
        """
        pass

    def handle_mouse_double_click(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """
        Handle mouse double click events.
        Default implementation does nothing.

        Args:
            event: The original QMouseEvent
            scene_pos: Position in scene coordinates

        Returns:
            bool: True if the event was handled, False otherwise
        """
        return False

    def handle_wheel_event(self, event: QWheelEvent) -> bool:
        """
        Handle wheel events.
        Default implementation does nothing.

        Args:
            event: The QWheelEvent

        Returns:
            bool: True if the event was handled, False otherwise
        """
        return False

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """
        Handle key press events.
        Default implementation does nothing.

        Args:
            event: The QKeyEvent

        Returns:
            bool: True if the event was handled, False otherwise
        """
        return False

    def handle_resize_event(self, event: QResizeEvent) -> bool:
        """
        Handle resize events.
        Default implementation does nothing.

        Args:
            event: The QResizeEvent

        Returns:
            bool: True if the event was handled, False otherwise
        """
        return False

    def handle_viewport_event(self, event: QEvent) -> bool:
        """
        Handle viewport events (gestures, etc.).
        Default implementation does nothing.

        Args:
            event: The QEvent

        Returns:
            bool: True if the event was handled, False otherwise
        """
        return False

    def handle_draw_background(self, painter: QPainter, rect) -> bool:
        """
        Handle background drawing.
        Default implementation does nothing.

        Args:
            painter: The QPainter
            rect: The rectangle to draw

        Returns:
            bool: True if the drawing was handled, False otherwise
        """
        return False

    def handle_draw_foreground(self, painter: QPainter, rect) -> bool:
        """
        Handle foreground drawing.
        Default implementation does nothing.

        Args:
            painter: The QPainter
            rect: The rectangle to draw

        Returns:
            bool: True if the drawing was handled, False otherwise
        """
        return False

    @abstractmethod
    def enter_mode(self) -> None:
        """
        Called when entering this mode.
        Override for mode-specific setup.
        """
        pass

    @abstractmethod
    def exit_mode(self) -> None:
        """
        Called when exiting this mode.
        Override for mode-specific cleanup.
        """
        pass

    def get_cursor(self):
        """
        Get the cursor that should be displayed for this mode.
        Override to provide mode-specific cursors.

        Returns:
            Qt.CursorShape or QCursor
        """
        from PyQt6.QtCore import Qt

        return Qt.CursorShape.ArrowCursor

    @abstractmethod
    def update_mode_state(self) -> None:
        """
        Update internal mode state.
        Called periodically to allow modes to update their state.
        """
        pass
