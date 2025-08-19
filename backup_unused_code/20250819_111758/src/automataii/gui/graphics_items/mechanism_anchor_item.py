"""Draggable anchor item for mechanism pivots."""

from PyQt6.QtCore import QObject, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsSceneMouseEvent


class MechanismAnchorSignals(QObject):
    """Signal holder for MechanismAnchorItem."""

    position_changed = pyqtSignal(str, QPointF)  # anchor_id, new_position


class MechanismAnchorItem(QGraphicsEllipseItem):
    """A draggable anchor point for mechanism configuration."""

    def __init__(
        self, anchor_id: str, center: QPointF, radius: float = 8.0, parent=None
    ):
        super().__init__(
            center.x() - radius, center.y() - radius, radius * 2, radius * 2, parent
        )

        self.anchor_id = anchor_id
        self.radius = radius
        self.signals = MechanismAnchorSignals()

        # Visual styling
        self.default_color = QColor(255, 100, 100)
        self.hover_color = QColor(255, 150, 150)
        self.drag_color = QColor(255, 50, 50)

        self.setPen(QPen(Qt.GlobalColor.black, 2))
        self.setBrush(QBrush(self.default_color))

        # Make it interactive
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(
            QGraphicsEllipseItem.GraphicsItemFlag.ItemSendsGeometryChanges, True
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        # Higher z-value to appear on top
        self.setZValue(1000)

    def center_pos(self) -> QPointF:
        """Get the center position of the anchor."""
        rect = self.rect()
        return QPointF(rect.center())

    def set_center_pos(self, pos: QPointF):
        """Set the center position of the anchor."""
        self.setRect(
            pos.x() - self.radius,
            pos.y() - self.radius,
            self.radius * 2,
            self.radius * 2,
        )

    def hoverEnterEvent(self, event):
        """Handle mouse hover enter."""
        self.setBrush(QBrush(self.hover_color))
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Handle mouse hover leave."""
        self.setBrush(QBrush(self.default_color))
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.setBrush(QBrush(self.drag_color))
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.setBrush(QBrush(self.hover_color))
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            # Emit position changed signal
            self.signals.position_changed.emit(
                self.anchor_id, self.scenePos() + self.center_pos()
            )
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        """Handle item changes."""
        if change == QGraphicsEllipseItem.GraphicsItemChange.ItemPositionHasChanged:
            # Emit position update during drag
            self.signals.position_changed.emit(
                self.anchor_id, self.scenePos() + self.center_pos()
            )
        return super().itemChange(change, value)
