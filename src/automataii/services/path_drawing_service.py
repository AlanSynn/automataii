"""Service for handling path drawing operations."""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QPointF, QObject, pyqtSignal
from PyQt6.QtGui import QPainterPath


class DrawingMode(Enum):
    """Enumeration of drawing modes."""
    SELECT = "select"
    DRAW_PATH = "draw_path"
    EDIT_PATH = "edit_path"


@dataclass
class PathDrawing:
    """Data class representing a path being drawn."""
    id: str
    part_name: str
    points: List[QPointF]
    is_complete: bool = False

    def to_painter_path(self) -> QPainterPath:
        """Convert points to QPainterPath."""
        if not self.points:
            return QPainterPath()

        path = QPainterPath()
        path.moveTo(self.points[0])

        for i in range(1, len(self.points)):
            path.lineTo(self.points[i])

        return path


class PathDrawingService(QObject):
    """Service for managing path drawing operations.

    This service extracts path drawing logic from EditorTab,
    following the Single Responsibility Principle.
    """

    # Signals
    path_started = pyqtSignal(str, str)  # path_id, part_name
    path_updated = pyqtSignal(str, QPainterPath)  # path_id, current_path
    path_completed = pyqtSignal(str, str, QPainterPath)  # path_id, part_name, final_path
    path_cleared = pyqtSignal(str)  # part_name

    def __init__(self):
        super().__init__()
        self._active_drawings: Dict[str, PathDrawing] = {}
        self._completed_paths: Dict[str, QPainterPath] = {}  # part_name -> path
        self._current_mode = DrawingMode.SELECT
        self._path_counter = 0

        logging.info("PathDrawingService initialized")

    @property
    def current_mode(self) -> DrawingMode:
        """Get current drawing mode."""
        return self._current_mode

    def set_mode(self, mode: DrawingMode) -> None:
        """Set the drawing mode."""
        if self._current_mode != mode:
            self._current_mode = mode
            logging.info(f"PathDrawingService: Mode changed to {mode.value}")

    def start_path(self, part_name: str, start_point: QPointF) -> Optional[str]:
        """Start drawing a new path for a part.

        Args:
            part_name: Name of the part to draw path for
            start_point: Starting point of the path

        Returns:
            Path ID if started successfully, None otherwise
        """
        if not part_name:
            logging.warning("PathDrawingService: Cannot start path without part name")
            return None

        # Check if there's already an active drawing for this part
        for path_id, drawing in self._active_drawings.items():
            if drawing.part_name == part_name and not drawing.is_complete:
                logging.warning(f"PathDrawingService: Part '{part_name}' already has an active path")
                return None

        # Generate unique path ID
        self._path_counter += 1
        path_id = f"path_{self._path_counter}"

        # Create new drawing
        drawing = PathDrawing(
            id=path_id,
            part_name=part_name,
            points=[start_point]
        )

        self._active_drawings[path_id] = drawing
        self.path_started.emit(path_id, part_name)

        logging.info(f"PathDrawingService: Started path '{path_id}' for part '{part_name}'")
        return path_id

    def add_point(self, path_id: str, point: QPointF) -> bool:
        """Add a point to an active path.

        Args:
            path_id: ID of the path to add point to
            point: Point to add

        Returns:
            True if point added successfully
        """
        if path_id not in self._active_drawings:
            logging.warning(f"PathDrawingService: Path '{path_id}' not found")
            return False

        drawing = self._active_drawings[path_id]
        if drawing.is_complete:
            logging.warning(f"PathDrawingService: Path '{path_id}' is already complete")
            return False

        drawing.points.append(point)

        # Emit update signal
        current_path = drawing.to_painter_path()
        self.path_updated.emit(path_id, current_path)

        return True

    def complete_path(self, path_id: str) -> Optional[QPainterPath]:
        """Complete the current path drawing.

        Args:
            path_id: ID of the path to complete

        Returns:
            Completed QPainterPath or None if failed
        """
        if path_id not in self._active_drawings:
            logging.warning(f"PathDrawingService: Path '{path_id}' not found")
            return None

        drawing = self._active_drawings[path_id]
        if drawing.is_complete:
            logging.warning(f"PathDrawingService: Path '{path_id}' is already complete")
            return None

        if len(drawing.points) < 2:
            logging.warning(f"PathDrawingService: Path '{path_id}' needs at least 2 points")
            return None

        # Mark as complete and convert to painter path
        drawing.is_complete = True
        final_path = drawing.to_painter_path()

        # Store completed path
        self._completed_paths[drawing.part_name] = final_path

        # Emit completion signal
        self.path_completed.emit(path_id, drawing.part_name, final_path)

        logging.info(f"PathDrawingService: Completed path '{path_id}' for part '{drawing.part_name}'")
        return final_path

    def cancel_path(self, path_id: str) -> bool:
        """Cancel an active path drawing.

        Args:
            path_id: ID of the path to cancel

        Returns:
            True if cancelled successfully
        """
        if path_id not in self._active_drawings:
            return False

        drawing = self._active_drawings[path_id]
        del self._active_drawings[path_id]

        logging.info(f"PathDrawingService: Cancelled path '{path_id}' for part '{drawing.part_name}'")
        return True

    def clear_path(self, part_name: str) -> bool:
        """Clear the completed path for a part.

        Args:
            part_name: Name of the part to clear path for

        Returns:
            True if cleared successfully
        """
        if part_name not in self._completed_paths:
            return False

        del self._completed_paths[part_name]
        self.path_cleared.emit(part_name)

        logging.info(f"PathDrawingService: Cleared path for part '{part_name}'")
        return True

    def get_path(self, part_name: str) -> Optional[QPainterPath]:
        """Get the completed path for a part.

        Args:
            part_name: Name of the part

        Returns:
            QPainterPath or None if no path exists
        """
        return self._completed_paths.get(part_name)

    def get_all_paths(self) -> Dict[str, QPainterPath]:
        """Get all completed paths.

        Returns:
            Dictionary mapping part names to paths
        """
        return self._completed_paths.copy()

    def has_path(self, part_name: str) -> bool:
        """Check if a part has a completed path.

        Args:
            part_name: Name of the part

        Returns:
            True if part has a path
        """
        return part_name in self._completed_paths

    def get_active_drawing_for_part(self, part_name: str) -> Optional[str]:
        """Get the active drawing path ID for a part.

        Args:
            part_name: Name of the part

        Returns:
            Path ID if there's an active drawing, None otherwise
        """
        for path_id, drawing in self._active_drawings.items():
            if drawing.part_name == part_name and not drawing.is_complete:
                return path_id
        return None

    def clear_all(self) -> None:
        """Clear all paths and active drawings."""
        self._active_drawings.clear()
        self._completed_paths.clear()
        self._path_counter = 0
        logging.info("PathDrawingService: Cleared all paths")

    def get_path_statistics(self, part_name: str) -> Optional[Dict]:
        """Get statistics about a path.

        Args:
            part_name: Name of the part

        Returns:
            Dictionary with path statistics or None
        """
        path = self._completed_paths.get(part_name)
        if not path:
            return None

        bounds = path.boundingRect()
        return {
            'length': path.length(),
            'bounds': {
                'x': bounds.x(),
                'y': bounds.y(),
                'width': bounds.width(),
                'height': bounds.height()
            },
            'point_count': len([p for p in path.toSubpathPolygons()])
        }