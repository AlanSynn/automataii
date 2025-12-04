"""
Skeleton Visual Handler - Handles skeleton visualization and animation.

Extracted from EditorView. Manages skeleton display, animated poses,
and bone length validation.

Design Pattern: Handler (specialized skeleton visualization)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QLineF, QPointF
from PyQt6.QtWidgets import QGraphicsScene

if TYPE_CHECKING:
    from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
    from automataii.presentation.qt.graphics_items.skeleton_item import (
        SkeletonGraphicsItem,
    )


class SkeletonVisualHandler:
    """
    Handles skeleton visualization and animation updates.

    Responsibilities:
    - Manage SkeletonGraphicsItem creation and updates
    - Update skeleton animated poses
    - Validate bone length preservation
    - Update CharacterPartItem visuals from joint data

    Time Complexity: O(n) where n = number of joints
    """

    # Bone length deviation tolerance (1% for floating point precision)
    MAX_BONE_LENGTH_DEVIATION = 0.01

    def __init__(
        self,
        scene: QGraphicsScene,
        z_skeleton_overlay: int,
        mechanism_mode: bool = False,
    ):
        """
        Initialize skeleton visual handler.

        Args:
            scene: Graphics scene for skeleton item
            z_skeleton_overlay: Z-index for skeleton overlay
            mechanism_mode: Whether in mechanism design mode
        """
        self._scene = scene
        self._z_skeleton_overlay = z_skeleton_overlay
        self._mechanism_mode = mechanism_mode
        self._skeleton_item: SkeletonGraphicsItem | None = None
        self._joint_map_original_to_std: dict[str, str] = {}

    @property
    def skeleton_item(self) -> SkeletonGraphicsItem | None:
        """Get the current skeleton graphics item."""
        return self._skeleton_item

    def set_joint_map(self, joint_map: dict[str, str] | None) -> None:
        """Set the joint map (original name to standardized ID)."""
        if joint_map:
            self._joint_map_original_to_std = joint_map
            logging.debug(f"SkeletonVisualHandler: Joint map set with {len(joint_map)} entries.")
        else:
            self._joint_map_original_to_std = {}

    def visualize_skeleton(
        self,
        skeleton_data: list[dict[str, Any]],
        hierarchy_data: dict[str, list[str]],
        on_joint_clicked: Any | None = None,
    ) -> None:
        """
        Visualize the skeleton using SkeletonGraphicsItem.

        Args:
            skeleton_data: List of joint dictionaries
            hierarchy_data: Joint hierarchy mapping
            on_joint_clicked: Optional callback for joint click events
        """
        # Import here to avoid circular imports
        from automataii.presentation.qt.graphics_items.skeleton_item import (
            SkeletonGraphicsItem,
        )

        logging.debug(
            f"SkeletonVisualHandler: Received skeleton_data (count: {len(skeleton_data)})"
        )

        if not skeleton_data:
            if self._skeleton_item:
                self._skeleton_item.load_skeleton_data([], {})
            return

        if self._skeleton_item is None:
            self._skeleton_item = SkeletonGraphicsItem(
                skeleton_data, hierarchy_data, mechanism_mode=self._mechanism_mode
            )
            self._scene.addItem(self._skeleton_item)
            self._skeleton_item.setZValue(self._z_skeleton_overlay)

            if on_joint_clicked:
                self._skeleton_item.joint_clicked.connect(on_joint_clicked)
        else:
            # Disconnect existing connections
            try:
                self._skeleton_item.joint_clicked.disconnect()
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

            self._skeleton_item.load_skeleton_data(skeleton_data, hierarchy_data)

            if on_joint_clicked:
                self._skeleton_item.joint_clicked.connect(on_joint_clicked)

        self._scene.update()

    def update_skeleton_animation(
        self, animated_joint_positions: dict[str, tuple[float, float]]
    ) -> None:
        """Update the skeleton with new animated joint positions."""
        if self._skeleton_item:
            self._skeleton_item.set_animated_pose(animated_joint_positions)
        else:
            logging.warning(
                "SkeletonVisualHandler: No skeleton item to update animation."
            )

    def update_visuals_from_animation_data(
        self,
        joint_data: dict[str, dict[str, Any]],
        editor_items: dict[str, CharacterPartItem],
    ) -> None:
        """
        Update skeleton and part visuals from joint-centric animation data.

        Args:
            joint_data: Animation data keyed by joint ID
            editor_items: Dictionary of CharacterPartItem instances
        """
        # Extract all joint positions for skeleton
        all_joint_positions: dict[str, tuple[float, float]] = {}
        for joint_id, data in joint_data.items():
            pos = data.get("scene_position")
            if pos and isinstance(pos, QPointF):
                all_joint_positions[joint_id] = (pos.x(), pos.y())

        if self._skeleton_item:
            self._skeleton_item.set_animated_pose(all_joint_positions)

        # Update CharacterPartItems
        for part_item in editor_items.values():
            self._update_part_from_joint_data(part_item, joint_data)

        self._scene.update()

    def _update_part_from_joint_data(
        self,
        part_item: CharacterPartItem,
        joint_data: dict[str, dict[str, Any]],
    ) -> None:
        """Update a single part item from joint animation data."""
        original_anchor_joint_name = part_item.anchor_joint_id
        if not original_anchor_joint_name:
            return

        standardized_id = self._joint_map_original_to_std.get(original_anchor_joint_name)
        if not standardized_id or standardized_id not in joint_data:
            return

        transform_data = joint_data[standardized_id]
        target_pos = transform_data.get("scene_position")
        target_rotation = transform_data.get(
            "world_rotation_degrees", part_item.rotation()
        )

        if not isinstance(target_pos, QPointF):
            return

        # Validate bone length preservation
        is_valid = self._validate_skeleton_length_preservation(
            part_item, target_pos, joint_data
        )

        if is_valid:
            part_item.setRotation(float(target_rotation))
            part_item.set_scene_position_from_anchor(target_pos, bypass_validation=True)
        else:
            logging.debug(
                f"Skeleton length constraint violation prevented for '{part_item.name()}'"
            )
            if target_rotation is not None:
                part_item.setRotation(float(target_rotation))

    def _validate_skeleton_length_preservation(
        self,
        part_item: CharacterPartItem,
        new_anchor_pos: QPointF,
        joint_data: dict[str, dict[str, Any]],
    ) -> bool:
        """
        Validate that new position preserves skeleton bone length constraints.

        Args:
            part_item: The part being moved
            new_anchor_pos: Proposed new anchor position
            joint_data: Current joint data with positions

        Returns:
            True if constraints are preserved, False otherwise
        """
        connected_joints = self._get_connected_joints_for_part(part_item, joint_data)

        for parent_id, child_id, expected_length in connected_joints:
            parent_data = joint_data.get(parent_id)
            child_data = joint_data.get(child_id)

            if not parent_data or not child_data:
                continue

            parent_pos = parent_data.get("scene_position")
            child_pos = child_data.get("scene_position")

            if not isinstance(parent_pos, QPointF) or not isinstance(child_pos, QPointF):
                continue

            current_length = QLineF(parent_pos, child_pos).length()

            if expected_length > 0:
                deviation = abs(current_length - expected_length) / expected_length
                if deviation > self.MAX_BONE_LENGTH_DEVIATION:
                    logging.debug(
                        f"Skeleton length violation: {parent_id}->{child_id} "
                        f"expected={expected_length:.1f}, current={current_length:.1f}"
                    )
                    return False

        return True

    def _get_connected_joints_for_part(
        self,
        part_item: CharacterPartItem,
        joint_data: dict[str, dict[str, Any]],
    ) -> list[tuple[str, str, float]]:
        """
        Get bone connections that this part participates in.

        Returns:
            List of (parent_joint_id, child_joint_id, expected_bone_length)
        """
        connections = []

        part_anchor_joint = part_item.anchor_joint_id
        if not part_anchor_joint:
            return connections

        standardized_id = self._joint_map_original_to_std.get(part_anchor_joint)
        if not standardized_id or standardized_id not in joint_data:
            return connections

        # Basic bone length estimation from current positions
        for other_id, other_data in joint_data.items():
            if other_id == standardized_id:
                continue

            other_pos = other_data.get("scene_position")
            current_pos = joint_data[standardized_id].get("scene_position")

            if isinstance(other_pos, QPointF) and isinstance(current_pos, QPointF):
                distance = QLineF(current_pos, other_pos).length()

                # Only consider reasonable bone lengths
                if 20 < distance < 200:
                    connections.append((standardized_id, other_id, distance))

        return connections
