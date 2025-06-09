"""Handler for path drawing operations."""

import logging
from typing import Optional, List

from PyQt6.QtCore import QObject, pyqtSignal, QPointF
from PyQt6.QtGui import QPainterPath

from automataii.gui.tabs.editor.state import EditorState, EditorMode
from automataii.services import PathDrawingService, DrawingMode
from automataii.events import event_bus, PathDrawingStartedEvent, PathDrawingCompletedEvent


class PathDrawingHandler(QObject):
    """Handles path drawing operations."""

    # Signals
    drawing_started = pyqtSignal(str)  # part_name
    drawing_updated = pyqtSignal(str, QPainterPath)  # part_name, current_path
    drawing_completed = pyqtSignal(str, QPainterPath)  # part_name, final_path
    drawing_cancelled = pyqtSignal()

    def __init__(self, state: EditorState, path_service: PathDrawingService):
        super().__init__()
        self._state = state
        self._path_service = path_service
        self._current_path_id: Optional[str] = None

        # Connect to service signals
        self._path_service.path_completed.connect(self._on_path_completed)

        logging.debug("PathDrawingHandler initialized")

    def start_drawing(self, start_point: QPointF) -> bool:
        """Start drawing a path for selected part.

        Args:
            start_point: Starting point for path

        Returns:
            True if drawing started successfully
        """
        if not self._state.can_draw_path():
            logging.warning("PathDrawingHandler: Cannot draw path in current state")
            return False

        part_name = self._state.selected_part_name
        if not part_name:
            return False

        # Start path in service
        path_id = self._path_service.start_path(part_name, start_point)
        if not path_id:
            return False

        # Update state
        self._current_path_id = path_id
        self._state.is_drawing_path = True
        self._state.mode = EditorMode.DRAW_PATH
        self._state.current_path_points = [start_point]

        # Set service mode
        self._path_service.set_mode(DrawingMode.DRAW_PATH)

        # Emit signals
        self.drawing_started.emit(part_name)

        # Publish event
        event = PathDrawingStartedEvent(
            part_name=part_name,
            start_point=start_point,
            source="path_drawing_handler"
        )
        event_bus.publish(event)

        logging.info(f"PathDrawingHandler: Started drawing for '{part_name}'")
        return True

    def add_point(self, point: QPointF) -> bool:
        """Add point to current path.

        Args:
            point: Point to add

        Returns:
            True if point added successfully
        """
        if not self._current_path_id:
            return False

        # Add to service
        if not self._path_service.add_point(self._current_path_id, point):
            return False

        # Update state
        self._state.current_path_points.append(point)

        # Get current path for preview
        part_name = self._state.selected_part_name
        if part_name:
            # Create preview path
            preview_path = QPainterPath()
            if self._state.current_path_points:
                preview_path.moveTo(self._state.current_path_points[0])
                for pt in self._state.current_path_points[1:]:
                    preview_path.lineTo(pt)

            self.drawing_updated.emit(part_name, preview_path)

        return True

    def complete_drawing(self) -> Optional[QPainterPath]:
        """Complete current path drawing.

        Returns:
            Completed path or None
        """
        if not self._current_path_id:
            return None

        # Complete in service
        final_path = self._path_service.complete_path(self._current_path_id)
        if not final_path:
            self.cancel_drawing()
            return None

        # Path completed signal will be handled by _on_path_completed
        return final_path

    def cancel_drawing(self) -> None:
        """Cancel current path drawing."""
        if self._current_path_id:
            self._path_service.cancel_path(self._current_path_id)
            self._current_path_id = None

        # Reset state
        self._state.is_drawing_path = False
        self._state.mode = EditorMode.SELECT
        self._state.current_path_points.clear()
        self._path_service.set_mode(DrawingMode.SELECT)

        self.drawing_cancelled.emit()
        logging.info("PathDrawingHandler: Drawing cancelled")

    def clear_path(self, part_name: Optional[str] = None) -> bool:
        """Clear path for a part.

        Args:
            part_name: Part name, or None for selected part

        Returns:
            True if cleared successfully
        """
        target_part = part_name or self._state.selected_part_name
        if not target_part:
            return False

        # Clear in service
        if not self._path_service.clear_path(target_part):
            return False

        # Update state
        if target_part in self._state.parts:
            part_state = self._state.parts[target_part]
            part_state.has_motion_path = False
            part_state.motion_path = None

        logging.info(f"PathDrawingHandler: Cleared path for '{target_part}'")
        return True

    def get_path(self, part_name: str) -> Optional[QPainterPath]:
        """Get path for a part."""
        return self._path_service.get_path(part_name)

    def has_path(self, part_name: str) -> bool:
        """Check if part has a path."""
        return self._path_service.has_path(part_name)

    def _on_path_completed(self, path_id: str, part_name: str, path: QPainterPath):
        """Handle path completion from service."""
        # Update state
        if part_name in self._state.parts:
            part_state = self._state.parts[part_name]
            part_state.has_motion_path = True
            part_state.motion_path = path

        # Reset drawing state
        self._current_path_id = None
        self._state.is_drawing_path = False
        self._state.mode = EditorMode.SELECT
        self._state.current_path_points.clear()
        self._path_service.set_mode(DrawingMode.SELECT)

        # Emit signal
        self.drawing_completed.emit(part_name, path)

        # Publish event
        event = PathDrawingCompletedEvent(
            part_name=part_name,
            path=path,
            point_count=len(self._state.current_path_points),
            source="path_drawing_handler"
        )
        event_bus.publish(event)

        logging.info(f"PathDrawingHandler: Completed path for '{part_name}'")