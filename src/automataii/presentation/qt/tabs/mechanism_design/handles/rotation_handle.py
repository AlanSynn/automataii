"""
Rotation Handle for parametric mechanism editing.

Extracted from MechanismDesignTab as part of god class decomposition.
Provides rotation control for gear and other rotatable mechanisms.

Design Pattern: Strategy (rotation interaction behavior)
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem

if TYPE_CHECKING:
    from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab


class RotationHandle(QGraphicsEllipseItem):
    """
    Simple rotation handle that moves around a center point.

    ULTRATHINK: Don't modify the actual mechanism directly - delegate to parent tab
    for mechanism rotation to maintain separation of concerns.

    Responsibilities:
    - Track mouse drag for rotation gesture
    - Calculate rotation angle from drag movement
    - Delegate actual mechanism rotation to parent tab
    - Provide visual feedback (position, tooltip)

    Time Complexity: O(1) per mouse event
    """

    def __init__(
        self,
        parent_tab: MechanismDesignTab,
        mechanism_id: str,
        center_pos: QPointF,
        radius: float = 60,
    ) -> None:
        """
        Initialize rotation handle.

        Args:
            parent_tab: Parent MechanismDesignTab for callbacks
            mechanism_id: ID of mechanism this handle controls
            center_pos: Center point for rotation
            radius: Initial distance from center
        """
        super().__init__(-25, -25, 50, 50)  # Large circle

        self.parent_tab = parent_tab
        self.mechanism_id = mechanism_id
        self.rotation_center = center_pos
        self.is_dragging = False
        self.current_rotation = 0.0
        self._previous_angle: float | None = None

        # Position handle at radius distance from center
        handle_pos = QPointF(center_pos.x() + radius, center_pos.y())
        self.setPos(handle_pos)

        # Visual styling - bright yellow with orange border
        self.setBrush(QBrush(QColor(255, 255, 0)))
        self.setPen(QPen(QColor(255, 140, 0), 5))

        # Enable drag interaction
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(1000002)

        # Identification
        self.handle_id = f"{mechanism_id}_rotation"
        self.handle_type = "rotation"
        self.setToolTip("🔄 Rotation Handle: Drag to set rotation angle (visual only)")

    def mousePressEvent(self, event: Any) -> None:
        """Handle mouse press - start rotation tracking."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True

            # Initialize previous angle for rotation calculation
            scene_pos = event.scenePos()
            dx = scene_pos.x() - self.rotation_center.x()
            dy = scene_pos.y() - self.rotation_center.y()
            self._previous_angle = math.atan2(dy, dx)

            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        """Handle mouse move - rotate mechanism and move handle."""
        if self.is_dragging:
            scene_pos = event.scenePos()

            # Calculate position relative to center
            dx = scene_pos.x() - self.rotation_center.x()
            dy = scene_pos.y() - self.rotation_center.y()

            # Calculate current angle
            current_angle = math.atan2(dy, dx)

            # Calculate angle difference for mechanism rotation
            if self._previous_angle is not None:
                angle_diff = current_angle - self._previous_angle

                # Handle angle wrap-around (crossing 180° boundary)
                if angle_diff > math.pi:
                    angle_diff -= 2 * math.pi
                elif angle_diff < -math.pi:
                    angle_diff += 2 * math.pi

                # Apply rotation to mechanism if significant movement
                if abs(angle_diff) > 0.01:  # Lower threshold for responsive rotation
                    # Use current mouse position as rotation center for maximum user control
                    self.parent_tab._rotate_mechanism(
                        self.mechanism_id, scene_pos, angle_diff
                    )

            # Store current angle for next movement
            self._previous_angle = current_angle

            # Allow free positioning of rotation handle - not constrained to circle
            self.setPos(scene_pos)

            # Update display angle
            self.current_rotation = math.degrees(current_angle)
            self.setToolTip(
                f"🔄 Rotation Handle: {self.current_rotation:.1f}° (drag to rotate)"
            )

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        """Handle mouse release - end rotation tracking."""
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            self._previous_angle = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)
