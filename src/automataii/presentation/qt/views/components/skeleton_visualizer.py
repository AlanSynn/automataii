"""
Skeleton Visualizer - Skeleton visualization and animation updates.

Extracted from EditorView. Handles skeleton rendering,
bone updates, and animation state visualization.

Design Pattern: Visualizer (rendering responsibilities)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QLineF, QObject, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsLineItem

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene


class SkeletonVisualizer(QObject):
    """
    Handles skeleton visualization and animation updates.

    Responsibilities:
    - Create skeleton visual items (bones, joints)
    - Update skeleton from animation data
    - Validate bone length preservation

    Signals:
        skeleton_updated: Emitted when skeleton visualization is updated
        validation_warning: Emitted when bone length validation fails
    """

    skeleton_updated = pyqtSignal()
    validation_warning = pyqtSignal(str)

    # Visual settings
    JOINT_RADIUS = 5.0
    BONE_WIDTH = 2.0
    JOINT_COLOR = QColor(70, 130, 180)  # Steel blue
    BONE_COLOR = QColor(100, 100, 100)  # Gray

    # Length preservation thresholds
    LENGTH_WARNING_THRESHOLD = 0.15  # 15% deviation warning
    LENGTH_ERROR_THRESHOLD = 0.25  # 25% deviation error

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize skeleton visualizer."""
        super().__init__(parent)

        self._scene: QGraphicsScene | None = None

        # Visual item tracking
        self._joint_items: dict[str, QGraphicsEllipseItem] = {}
        self._bone_items: dict[str, QGraphicsLineItem] = {}

        # Reference data for validation
        self._reference_bone_lengths: dict[str, float] = {}

        # Callbacks
        self._get_joint_map: Callable[[], dict[str, str] | None] = lambda: None

    def configure(
        self,
        scene: QGraphicsScene,
        get_joint_map: Callable[[], dict[str, str] | None] | None = None,
    ) -> None:
        """
        Configure visualizer with scene and callbacks.

        Args:
            scene: Graphics scene for skeleton items
            get_joint_map: Callback to get abstract→standard joint mapping
        """
        self._scene = scene
        if get_joint_map:
            self._get_joint_map = get_joint_map

    def visualize_skeleton(
        self,
        skeleton_data: dict[str, Any],
        parts_data: dict[str, Any] | None = None,
        part_items: dict[str, Any] | None = None,
    ) -> None:
        """
        Visualize skeleton structure.

        Args:
            skeleton_data: Skeleton data with joints and hierarchy
            parts_data: Optional parts data for positioning
            part_items: Optional graphics items for parts

        Time Complexity: O(j + b) where j = joints, b = bones
        """
        if not self._scene or not skeleton_data:
            return

        # Clear existing visualization
        self._clear_skeleton_visuals()

        joints = skeleton_data.get("joints", {})
        hierarchy = skeleton_data.get("hierarchy", {})

        if not joints:
            return

        # Store reference bone lengths
        self._calculate_reference_lengths(joints, hierarchy)

        # Create joint visuals
        for joint_id, joint_data in joints.items():
            pos = joint_data.get("position")
            if not pos:
                continue

            if isinstance(pos, list | tuple) and len(pos) >= 2:
                x, y = pos[0], pos[1]
            else:
                continue

            self._create_joint_item(joint_id, QPointF(x, y))

        # Create bone visuals from hierarchy
        for parent_id, children in hierarchy.items():
            if parent_id not in joints:
                continue

            parent_pos = joints[parent_id].get("position")
            if not parent_pos:
                continue

            p_pos = QPointF(parent_pos[0], parent_pos[1])

            for child_id in children:
                if child_id not in joints:
                    continue

                child_pos = joints[child_id].get("position")
                if not child_pos:
                    continue

                c_pos = QPointF(child_pos[0], child_pos[1])
                bone_key = f"{parent_id}_{child_id}"
                self._create_bone_item(bone_key, p_pos, c_pos)

        self.skeleton_updated.emit()

    def update_from_animation(
        self,
        joint_data: dict[str, dict[str, Any]],
        validate_lengths: bool = True,
    ) -> None:
        """
        Update skeleton visualization from animation data.

        Args:
            joint_data: Joint positions and states from animation
            validate_lengths: Whether to validate bone length preservation

        Time Complexity: O(j) where j = number of joints
        """
        if not self._scene or not joint_data:
            return

        # Update joint positions
        for joint_id, data in joint_data.items():
            pos = data.get("position")
            if not pos:
                continue

            if isinstance(pos, QPointF):
                new_pos = pos
            elif hasattr(pos, "x") and hasattr(pos, "y"):
                new_pos = QPointF(pos.x(), pos.y())
            elif isinstance(pos, list | tuple) and len(pos) >= 2:
                new_pos = QPointF(pos[0], pos[1])
            else:
                continue

            self._update_joint_position(joint_id, new_pos)

        # Update bone positions
        self._update_bone_positions(joint_data)

        # Validate bone lengths if requested
        if validate_lengths:
            self._validate_bone_lengths(joint_data)

        self.skeleton_updated.emit()

    def _create_joint_item(self, joint_id: str, pos: QPointF) -> None:
        """Create a joint visual item."""
        if not self._scene:
            return

        radius = self.JOINT_RADIUS
        item = QGraphicsEllipseItem(
            pos.x() - radius,
            pos.y() - radius,
            radius * 2,
            radius * 2,
        )
        item.setPen(QPen(self.JOINT_COLOR, 1))
        item.setBrush(self.JOINT_COLOR)
        item.setZValue(100)  # Above bones
        item.setData(0, f"joint_{joint_id}")

        self._scene.addItem(item)
        self._joint_items[joint_id] = item

    def _create_bone_item(
        self,
        bone_key: str,
        start: QPointF,
        end: QPointF,
    ) -> None:
        """Create a bone visual item."""
        if not self._scene:
            return

        item = QGraphicsLineItem(QLineF(start, end))
        item.setPen(QPen(self.BONE_COLOR, self.BONE_WIDTH))
        item.setZValue(50)  # Below joints
        item.setData(0, f"bone_{bone_key}")

        self._scene.addItem(item)
        self._bone_items[bone_key] = item

    def _update_joint_position(self, joint_id: str, pos: QPointF) -> None:
        """Update position of an existing joint item."""
        if joint_id not in self._joint_items:
            return

        item = self._joint_items[joint_id]
        radius = self.JOINT_RADIUS
        item.setRect(
            pos.x() - radius,
            pos.y() - radius,
            radius * 2,
            radius * 2,
        )

    def _update_bone_positions(
        self,
        joint_data: dict[str, dict[str, Any]],
    ) -> None:
        """Update bone positions based on joint data."""
        for bone_key, item in self._bone_items.items():
            parts = bone_key.split("_", 1)
            if len(parts) != 2:
                continue

            parent_id, child_id = parts

            parent_data = joint_data.get(parent_id, {})
            child_data = joint_data.get(child_id, {})

            parent_pos = parent_data.get("position")
            child_pos = child_data.get("position")

            if not parent_pos or not child_pos:
                continue

            # Convert to QPointF
            if isinstance(parent_pos, QPointF):
                p_pos = parent_pos
            elif hasattr(parent_pos, "x"):
                p_pos = QPointF(parent_pos.x(), parent_pos.y())
            else:
                p_pos = QPointF(parent_pos[0], parent_pos[1])

            if isinstance(child_pos, QPointF):
                c_pos = child_pos
            elif hasattr(child_pos, "x"):
                c_pos = QPointF(child_pos.x(), child_pos.y())
            else:
                c_pos = QPointF(child_pos[0], child_pos[1])

            item.setLine(QLineF(p_pos, c_pos))

    def _calculate_reference_lengths(
        self,
        joints: dict[str, Any],
        hierarchy: dict[str, list[str]],
    ) -> None:
        """Calculate reference bone lengths from initial skeleton."""
        self._reference_bone_lengths.clear()

        for parent_id, children in hierarchy.items():
            parent_data = joints.get(parent_id, {})
            parent_pos = parent_data.get("position")
            if not parent_pos:
                continue

            for child_id in children:
                child_data = joints.get(child_id, {})
                child_pos = child_data.get("position")
                if not child_pos:
                    continue

                dx = child_pos[0] - parent_pos[0]
                dy = child_pos[1] - parent_pos[1]
                length = (dx * dx + dy * dy) ** 0.5

                bone_key = f"{parent_id}_{child_id}"
                self._reference_bone_lengths[bone_key] = length

    def _validate_bone_lengths(
        self,
        joint_data: dict[str, dict[str, Any]],
    ) -> bool:
        """
        Validate that bone lengths are preserved within tolerance.

        Returns:
            True if all bones are within tolerance
        """
        all_valid = True

        for bone_key, ref_length in self._reference_bone_lengths.items():
            parts = bone_key.split("_", 1)
            if len(parts) != 2:
                continue

            parent_id, child_id = parts
            parent_data = joint_data.get(parent_id, {})
            child_data = joint_data.get(child_id, {})

            parent_pos = parent_data.get("position")
            child_pos = child_data.get("position")

            if not parent_pos or not child_pos:
                continue

            # Calculate current length
            if isinstance(parent_pos, QPointF):
                px, py = parent_pos.x(), parent_pos.y()
            elif hasattr(parent_pos, "x"):
                px, py = parent_pos.x(), parent_pos.y()
            else:
                px, py = parent_pos[0], parent_pos[1]

            if isinstance(child_pos, QPointF):
                cx, cy = child_pos.x(), child_pos.y()
            elif hasattr(child_pos, "x"):
                cx, cy = child_pos.x(), child_pos.y()
            else:
                cx, cy = child_pos[0], child_pos[1]

            dx = cx - px
            dy = cy - py
            current_length = (dx * dx + dy * dy) ** 0.5

            if ref_length > 0:
                deviation = abs(current_length - ref_length) / ref_length

                if deviation > self.LENGTH_ERROR_THRESHOLD:
                    self.validation_warning.emit(
                        f"Bone {bone_key}: {deviation * 100:.1f}% length deviation (error)"
                    )
                    all_valid = False
                elif deviation > self.LENGTH_WARNING_THRESHOLD:
                    logging.warning(f"Bone {bone_key}: {deviation * 100:.1f}% length deviation")

        return all_valid

    def _clear_skeleton_visuals(self) -> None:
        """Remove all skeleton visual items."""
        if not self._scene:
            return

        for item in self._joint_items.values():
            self._scene.removeItem(item)
        self._joint_items.clear()

        for item in self._bone_items.values():
            self._scene.removeItem(item)
        self._bone_items.clear()

    def clear(self) -> None:
        """Clear all skeleton visualization."""
        self._clear_skeleton_visuals()
        self._reference_bone_lengths.clear()
