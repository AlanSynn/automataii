"""Draggable anchor item for mechanism pivots."""

from PyQt6.QtCore import QObject, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsSceneMouseEvent


class MechanismAnchorSignals(QObject):
    """Signal holder for MechanismAnchorItem."""

    position_changed = pyqtSignal(str, QPointF)  # anchor_id, new_position


