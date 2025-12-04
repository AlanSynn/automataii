from PyQt6.QtCore import QObject, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QApplication, QGraphicsEllipseItem, QGraphicsItem


# Internal class for handling signals
class AnchorSignals(QObject):
    anchorMoved = pyqtSignal(str, QPointF)
    anchorSelected = pyqtSignal(str)
    anchorLostFocus = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)


class AnchorItem(QGraphicsEllipseItem):  # Inherit only from QGraphicsEllipseItem
    """A draggable anchor point for defining mechanism constraints or targets."""

    def __init__(
        self,
        anchor_id: str,
        radius: float = 6,
        color: QColor | None = None,
        parent: QGraphicsItem | None = None,
    ):
        if color is None:
            color = QColor("red")

        rect = QRectF(-radius, -radius, radius * 2, radius * 2)
        super().__init__(rect, parent)  # Call QGraphicsEllipseItem constructor

        self.anchor_id = anchor_id
        self._radius = radius
        self._color = color

        # Create the internal QObject for signals
        self.signals = AnchorSignals()

        # Expose signals directly for convenience
        self.anchorMoved = self.signals.anchorMoved
        self.anchorSelected = self.signals.anchorSelected
        self.anchorLostFocus = self.signals.anchorLostFocus

        self.setBrush(QBrush(self._color))
        self.setPen(QPen(QColor("black"), 1))
        self.setZValue(1000)

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        self._is_dragging = False

    def __str__(self) -> str:
        return f"<AnchorItem '{self.anchor_id}' at ({self.scenePos().x():.1f}, {self.scenePos().y():.1f})>"



    def hoverEnterEvent(self, event):
        """Change cursor on hover."""
        self.setBrush(QBrush(self._color.lighter(130)))
        QApplication.setOverrideCursor(Qt.CursorShape.PointingHandCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Reset cursor on hover leave."""
        self.setBrush(QBrush(self._color))
        QApplication.restoreOverrideCursor()
        super().hoverLeaveEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        """Emit signal when position changes."""
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
            and self.scene()
        ):
            # This signal is emitted *after* the position has changed.
            self.signals.anchorMoved.emit(
                self.anchor_id, self.scenePos()
            )  # Emit via internal signals object
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        """Handle mouse press to initiate drag or selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self.setSelected(True)  # Ensure item is selected on click
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging."""
        if self._is_dragging:
            # The base class QGraphicsItem.ItemIsMovable handles the actual move.
            # We just ensure scene updates or other logic can happen here if needed.
            pass
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to finalize drag."""
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            # Position change is already handled by ItemPositionHasChanged in itemChange
        super().mouseReleaseEvent(event)


if __name__ == "__main__":
    # This is a QGraphicsItem, requires a QGraphicsScene and QGraphicsView to be visualized.
    # Example usage would typically be within a main application.

    import sys

    from PyQt6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView

    app = QApplication(sys.argv)

    scene = QGraphicsScene()
    scene.setSceneRect(0, 0, 400, 300)

    anchor1 = AnchorItem("test_anchor_1", radius=8, color=QColor("blue"))
    anchor1.setPos(50, 50)
    scene.addItem(anchor1)

    anchor2 = AnchorItem("test_anchor_2", radius=5, color=QColor("green"))
    anchor2.setPos(150, 100)
    scene.addItem(anchor2)

    def handle_anchor_move(anchor_id, pos):
        print(
            f"Anchor '{anchor_id}' moved to scene position: ({pos.x():.1f}, {pos.y():.1f})"
        )

    # Connections will now use the exposed signals from the AnchorItem instance
    anchor1.anchorMoved.connect(handle_anchor_move)
    anchor2.anchorMoved.connect(handle_anchor_move)

    view = QGraphicsView(scene)
    view.setWindowTitle("AnchorItem Test (Composition)")
    view.resize(420, 320)
    view.show()

    sys.exit(app.exec())
