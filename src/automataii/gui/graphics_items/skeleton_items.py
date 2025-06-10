"""
Graphics items for representing skeleton joints and bones in a QGraphicsScene.
"""

import logging
from typing import Optional

from PyQt6.QtCore import QPointF, QLineF, Qt
from PyQt6.QtGui import QPen, QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsTextItem,
    QStyle,
)


class JointItem(QGraphicsEllipseItem):
    """A graphical representation of a single joint in the skeleton."""

    def __init__(self, joint_id: str, x: float, y: float, radius: int = 5, parent=None):
        super().__init__(
            x - radius, y - radius, radius * 2, radius * 2, parent=parent
        )
        self.joint_id = joint_id
        self.setBrush(QBrush(QColor("lightblue")))
        self.setPen(QPen(QColor("darkblue"), 2))
        self.setZValue(1)  # Ensure joints are drawn above bones
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(self.GraphicsItemFlag.ItemSendsGeometryChanges)

        # Add a label
        self.label = QGraphicsTextItem(self.joint_id, self)
        self.label.setDefaultTextColor(QColor("black"))
        font = QFont()
        font.setPointSize(8)
        self.label.setFont(font)
        self.update_label_position()

    def itemChange(self, change, value):
        """Override to update connected bones when moved."""
        if change == self.GraphicsItemChange.ItemPositionHasChanged:
            # Notify connected bones to update their lines
            for item in self.scene().items():
                if isinstance(item, BoneItem):
                    item.track_joints()
        return super().itemChange(change, value)

    def update_label_position(self):
        """Positions the label slightly offset from the joint center."""
        label_x = self.rect().width() / 2 - self.label.boundingRect().width() / 2
        label_y = self.rect().height()
        self.label.setPos(label_x, label_y)


class BoneItem(QGraphicsLineItem):
    """A graphical representation of a bone connecting two joints."""

    def __init__(self, p1_item: JointItem, p2_item: JointItem, parent=None):
        super().__init__(parent)
        self.p1_item = p1_item
        self.p2_item = p2_item
        self.setPen(QPen(QColor("darkgray"), 3))
        self.setZValue(0)  # Draw bones behind joints
        self.track_joints()

    def track_joints(self):
        """Updates the line's start and end points to match the joint centers."""
        self.setLine(QLineF(self.p1_item.pos(), self.p2_item.pos()))