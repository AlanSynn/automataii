from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsItem
from PyQt6.QtGui import QPen, QColor, QBrush
from PyQt6.QtCore import Qt, QLineF

from ...core.models import JOINT_COLORS # UPDATED path

class SkeletonJoint(QGraphicsEllipseItem):
    """Draggable skeleton joint for skeleton editing."""
    def __init__(self, joint_name: str, x: float, y: float, radius: float = 7, parent=None):
        super().__init__(-radius, -radius, 2 * radius, 2 * radius, parent)
        self.joint_name = joint_name
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

        # Set joint appearance
        self.setZValue(20) # Above lines and image
        self.setBrush(JOINT_COLORS.get(joint_name, QColor("white")))
        self.setPen(QPen(Qt.GlobalColor.black, 1))

        # Reference to connected lines
        self.lines = []

    def add_line(self, line):
        """Adds a connection line reference to this joint."""
        if line not in self.lines:
            self.lines.append(line)

    def remove_line(self, line):
        """Removes a connection line reference."""
        try:
            self.lines.remove(line)
        except ValueError:
            pass # Line not found

    def itemChange(self, change, value):
        """Handles position changes to update connected lines."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            # Update connected lines when joint position changes
            for line in self.lines:
                line.update_position()
        return super().itemChange(change, value)

    def __repr__(self):
        return f"<SkeletonJoint '{self.joint_name}' at ({self.pos().x():.1f}, {self.pos().y():.1f})>"

class SkeletonLine(QGraphicsLineItem):
    """Connection line between two skeleton joints."""
    def __init__(self, joint1: SkeletonJoint, joint2: SkeletonJoint, parent=None):
        super().__init__(parent)
        self.joint1 = joint1
        self.joint2 = joint2
        self.setPen(QPen(Qt.GlobalColor.darkGray, 2, Qt.PenStyle.SolidLine))
        self.setZValue(19) # Below joints but above image
        self.update_position()

        # Add reference to joints
        joint1.add_line(self)
        joint2.add_line(self)

    def update_position(self):
        """Updates line position based on the current positions of its connected joints."""
        if self.joint1 and self.joint2:
            self.setLine(QLineF(self.joint1.pos(), self.joint2.pos()))

    def __del__(self):
        """Ensure lines are removed from joint references when deleted."""
        if self.joint1:
            self.joint1.remove_line(self)
        if self.joint2:
            self.joint2.remove_line(self)

    def __repr__(self):
         return f"<SkeletonLine between '{self.joint1.joint_name if self.joint1 else 'None'}' and '{self.joint2.joint_name if self.joint2 else 'None'}'>"