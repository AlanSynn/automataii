"""
Path Vertex Editor - Draggable vertex handles for motion path editing.

Allows users to adjust motion paths by repositioning vertices.

Design Pattern: Observer (handles emit signals on position change)
Architecture: Hexagonal - Presentation Layer
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

# Re-export for type checking only
__all__ = ["PathVertexHandle", "PathVertexEditor"]

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene

# Z-index for vertex handles (above path but below UI elements)
Z_VERTEX_HANDLE = 1000


class PathVertexHandle(QGraphicsObject):
    """
    Draggable handle for editing a single vertex of a motion path.

    Signals:
        position_changed(int, QPointF): Emitted when handle is moved (index, new_pos)
        drag_finished(int, QPointF): Emitted when drag is complete (index, final_pos)
    """

    position_changed = pyqtSignal(int, QPointF)
    drag_finished = pyqtSignal(int, QPointF)

    # Visual constants
    HANDLE_RADIUS = 8.0  # Larger for better visibility
    HANDLE_COLOR = QColor("#2196F3")  # Blue (default)
    HANDLE_HOVER_COLOR = QColor("#64B5F6")  # Light blue
    HANDLE_SELECTED_COLOR = QColor("#1565C0")  # Dark blue when selected
    HANDLE_BORDER_COLOR = QColor("#0D47A1")  # Dark blue border
    HANDLE_BORDER_WIDTH = 2.0

    def __init__(
        self,
        index: int,
        position: QPointF,
        parent: QGraphicsItem | None = None,
    ) -> None:
        """
        Initialize vertex handle.

        Args:
            index: Index of this vertex in the path
            position: Initial position in scene coordinates
            parent: Optional parent graphics item
        """
        super().__init__(parent)
        self._index = index
        self._radius = self.HANDLE_RADIUS
        self._is_hovered = False
        self._is_dragging = False

        # Set position
        self.setPos(position)

        # Enable interaction
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setZValue(Z_VERTEX_HANDLE)

    @property
    def index(self) -> int:
        """Get the vertex index."""
        return self._index

    def boundingRect(self) -> QRectF:
        """Return bounding rectangle for the handle."""
        margin = self.HANDLE_BORDER_WIDTH
        size = (self._radius + margin) * 2
        return QRectF(-size / 2, -size / 2, size, size)

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        """Paint the vertex handle."""
        if painter is None:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Determine color based on state
        if self.isSelected():
            fill_color = self.HANDLE_SELECTED_COLOR
        elif self._is_hovered:
            fill_color = self.HANDLE_HOVER_COLOR
        else:
            fill_color = self.HANDLE_COLOR

        # Draw handle circle
        painter.setPen(QPen(self.HANDLE_BORDER_COLOR, self.HANDLE_BORDER_WIDTH))
        painter.setBrush(QBrush(fill_color))
        painter.drawEllipse(
            QPointF(0, 0),
            self._radius,
            self._radius,
        )

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Handle mouse hover enter."""
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Handle mouse hover leave."""
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse press - start dragging."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Handle mouse release - finish dragging."""
        if event and event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            self.drag_finished.emit(self._index, self.pos())
        super().mouseReleaseEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """Handle item changes, including position updates."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._is_dragging:
                self.position_changed.emit(self._index, self.pos())
        return super().itemChange(change, value)


class PathVertexEditor(QObject):
    """
    Manager for editing motion path vertices.

    Creates and manages vertex handles for a motion path, allowing users
    to drag vertices to modify the path shape.

    Signals:
        path_modified(str, QPainterPath): Emitted when path is modified (part_name, new_path)
        editing_finished(str, QPainterPath): Emitted when editing session ends
    """

    path_modified = pyqtSignal(str, QPainterPath)
    editing_finished = pyqtSignal(str, QPainterPath)

    def __init__(
        self,
        scene: QGraphicsScene,
        parent: QObject | None = None,
    ) -> None:
        """
        Initialize path vertex editor.

        Args:
            scene: The graphics scene
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._scene = scene
        self._handles: list[PathVertexHandle] = []
        self._vertices: list[QPointF] = []
        self._part_name: str | None = None
        self._is_closed_path: bool = True
        self._preview_path_item: QGraphicsPathItem | None = None
        self._tension: float = 0.5  # Catmull-Rom tension (0.0 = angular, 1.0 = very smooth)

        # Visual style for preview path
        self._preview_pen = QPen(
            QColor("#FF9800"),  # Orange
            2.0,
            Qt.PenStyle.DashLine,
        )

    def start_editing(
        self,
        part_name: str,
        path: QPainterPath,
        is_closed: bool = True,
        num_vertices: int = 12,
    ) -> None:
        """
        Start editing a motion path by creating vertex handles.

        Args:
            part_name: Name of the part this path belongs to
            path: The QPainterPath to edit
            is_closed: Whether the path is closed
            num_vertices: Number of vertices to create for editing
        """
        # Clear any existing handles without emitting signal
        self.stop_editing(emit_signal=False)

        if path.isEmpty():
            logging.warning(f"Cannot edit empty path for {part_name}")
            return

        self._part_name = part_name
        self._is_closed_path = is_closed

        # Sample vertices from path
        self._vertices = self._sample_path_vertices(path, num_vertices)

        if not self._vertices:
            logging.warning(f"Could not extract vertices from path for {part_name}")
            return

        # Create handles for each vertex
        for i, pos in enumerate(self._vertices):
            handle = PathVertexHandle(i, pos)
            handle.position_changed.connect(self._on_vertex_moved)
            handle.drag_finished.connect(self._on_vertex_drag_finished)
            self._scene.addItem(handle)
            self._handles.append(handle)
            logging.debug(f"Created vertex handle {i} at ({pos.x():.1f}, {pos.y():.1f})")

        # Create preview path item
        self._create_preview_path()

        # Force scene update to ensure handles are rendered
        self._scene.update()

        logging.info(
            f"Started path vertex editing for '{part_name}' with {len(self._vertices)} vertices"
        )

    def stop_editing(self, emit_signal: bool = True) -> None:
        """Stop editing and remove all handles.

        Args:
            emit_signal: Whether to emit editing_finished signal
        """
        # Emit final path if we were editing
        if emit_signal and self._part_name and self._vertices:
            final_path = self._build_path_from_vertices()
            self.editing_finished.emit(self._part_name, final_path)

        # Remove handles
        for handle in self._handles:
            try:
                if handle.scene():
                    self._scene.removeItem(handle)
            except RuntimeError:
                pass
        self._handles.clear()
        self._vertices.clear()

        # Remove preview path
        if self._preview_path_item:
            try:
                if self._preview_path_item.scene():
                    self._scene.removeItem(self._preview_path_item)
            except RuntimeError:
                pass
            self._preview_path_item = None

        self._part_name = None

    def is_editing(self) -> bool:
        """Check if currently editing a path."""
        return bool(self._handles)

    def get_current_path(self) -> QPainterPath | None:
        """Get the current edited path."""
        if not self._vertices:
            return None
        return self._build_path_from_vertices()

    def set_tension(self, tension: float) -> None:
        """
        Set the Catmull-Rom tension and update preview.

        Args:
            tension: Tension value (0.0 = angular, 1.0 = very smooth)
        """
        self._tension = max(0.0, min(1.0, tension))
        if self._vertices:
            self._create_preview_path()
            # Emit signal for live update
            if self._part_name:
                new_path = self._build_path_from_vertices()
                self.path_modified.emit(self._part_name, new_path)

    def get_tension(self) -> float:
        """Get the current tension value."""
        return self._tension

    def _sample_path_vertices(
        self,
        path: QPainterPath,
        num_vertices: int,
    ) -> list[QPointF]:
        """
        Sample evenly-spaced vertices from a path.

        Args:
            path: The path to sample
            num_vertices: Number of vertices to extract

        Returns:
            List of vertex positions
        """
        vertices: list[QPointF] = []
        length = path.length()

        if length <= 0:
            return vertices

        # For closed paths, we don't include the endpoint (it's the same as start)
        count = num_vertices if not self._is_closed_path else num_vertices
        for i in range(count):
            t = i / count if self._is_closed_path else i / max(1, count - 1)
            point = path.pointAtPercent(min(t, 1.0))
            vertices.append(point)

        return vertices

    def _build_path_from_vertices(self) -> QPainterPath:
        """
        Build a smooth path from the current vertices using Catmull-Rom splines.

        Returns:
            QPainterPath constructed from vertices
        """
        path = QPainterPath()

        if not self._vertices:
            return path

        if len(self._vertices) == 1:
            path.moveTo(self._vertices[0])
            return path

        if len(self._vertices) == 2:
            path.moveTo(self._vertices[0])
            path.lineTo(self._vertices[1])
            return path

        # Use Catmull-Rom spline for smooth curves
        points = self._vertices.copy()

        if self._is_closed_path:
            # For closed path, wrap around
            points = [points[-1]] + points + [points[0], points[1]]
        else:
            # For open path, duplicate endpoints
            points = [points[0]] + points + [points[-1]]

        path.moveTo(self._vertices[0])

        # Generate spline segments
        tension = self._tension
        segments_per_curve = 10

        for i in range(1, len(points) - 2):
            p0, p1, p2, p3 = points[i - 1], points[i], points[i + 1], points[i + 2]

            for j in range(1, segments_per_curve + 1):
                t = j / segments_per_curve
                point = self._catmull_rom_point(p0, p1, p2, p3, t, tension)
                path.lineTo(point)

        if self._is_closed_path:
            path.closeSubpath()

        return path

    @staticmethod
    def _catmull_rom_point(
        p0: QPointF,
        p1: QPointF,
        p2: QPointF,
        p3: QPointF,
        t: float,
        tension: float = 0.5,
    ) -> QPointF:
        """
        Calculate a point on a Catmull-Rom spline.

        Args:
            p0, p1, p2, p3: Control points
            t: Parameter (0-1)
            tension: Spline tension

        Returns:
            Point on the spline
        """
        t2 = t * t
        t3 = t2 * t

        # Catmull-Rom basis functions
        b0 = -tension * t3 + 2 * tension * t2 - tension * t
        b1 = (2 - tension) * t3 + (tension - 3) * t2 + 1
        b2 = (tension - 2) * t3 + (3 - 2 * tension) * t2 + tension * t
        b3 = tension * t3 - tension * t2

        x = b0 * p0.x() + b1 * p1.x() + b2 * p2.x() + b3 * p3.x()
        y = b0 * p0.y() + b1 * p1.y() + b2 * p2.y() + b3 * p3.y()

        return QPointF(x, y)

    def _create_preview_path(self) -> None:
        """Create or update the preview path item."""
        path = self._build_path_from_vertices()

        if self._preview_path_item is None:
            self._preview_path_item = QGraphicsPathItem()
            self._preview_path_item.setPen(self._preview_pen)
            self._preview_path_item.setZValue(Z_VERTEX_HANDLE - 1)
            self._scene.addItem(self._preview_path_item)

        self._preview_path_item.setPath(path)

    def _on_vertex_moved(self, index: int, new_pos: QPointF) -> None:
        """Handle vertex position change during drag."""
        if 0 <= index < len(self._vertices):
            self._vertices[index] = new_pos
            self._create_preview_path()

            # Emit path modified signal for live preview
            if self._part_name:
                new_path = self._build_path_from_vertices()
                self.path_modified.emit(self._part_name, new_path)

    def _on_vertex_drag_finished(self, index: int, final_pos: QPointF) -> None:
        """Handle vertex drag completion."""
        if 0 <= index < len(self._vertices):
            self._vertices[index] = final_pos
            self._create_preview_path()

            if self._part_name:
                new_path = self._build_path_from_vertices()
                self.path_modified.emit(self._part_name, new_path)
                logging.debug(f"Vertex {index} moved to {final_pos}")
