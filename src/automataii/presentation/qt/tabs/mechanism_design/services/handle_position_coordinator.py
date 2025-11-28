"""
Handle Position Coordinator for managing parametric handle positions.

Extracted from MechanismDesignTab as part of god class decomposition.
Coordinates handle creation, rotation, and position synchronization.

Design Pattern: Coordinator (orchestrates handle position operations)
"""
from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsScene


class HandlePositionCoordinator:
    """
    Coordinates parametric handle positions across mechanism types.

    Responsibilities:
    - Rotate all anchor handles around a center point
    - Synchronize handle positions from key_points
    - Update handle positions when one handle moves
    - Create handles for specific mechanism types (gear, etc.)

    Time Complexity: O(n) where n is number of handles per mechanism
    """

    def __init__(self) -> None:
        """Initialize coordinator with empty state."""
        self._updating_handles_programmatically = False
        self._rotation_handle_class: type | None = None

    def set_rotation_handle_class(self, cls: type) -> None:
        """Set the RotationHandle class for creating rotation handles."""
        self._rotation_handle_class = cls

    @property
    def is_updating_programmatically(self) -> bool:
        """Check if handles are being updated programmatically."""
        return self._updating_handles_programmatically

    def rotate_mechanism_handles(
        self,
        mechanism_id: str,
        center: QPointF,
        angle_radians: float,
        handles: list[QGraphicsItem],
        mechanism_layers: dict[str, dict[str, Any]],
        scene: QGraphicsScene,
        show_feedback_fn: Callable[[str], None] | None = None,
    ) -> int:
        """
        Rotate all anchor handles around a center point.

        ULTRATHINK: User freedom mode - allow any configuration even if physically impossible.

        Args:
            mechanism_id: ID of the mechanism to rotate
            center: Center point for rotation (user's drag position)
            angle_radians: Angle to rotate in radians
            handles: List of handles for this mechanism
            mechanism_layers: Dictionary of mechanism layer data
            scene: Graphics scene for updates
            show_feedback_fn: Optional callback for visual feedback

        Returns:
            Number of handles rotated
        """
        try:
            cos_angle = math.cos(angle_radians)
            sin_angle = math.sin(angle_radians)

            rotated_count = 0

            # Apply rotation to all anchor handles - no constraints!
            for handle in handles:
                # Skip the rotation handle itself
                if hasattr(handle, 'handle_type') and handle.handle_type == 'rotation':
                    continue

                current_pos = handle.pos()

                # Translate to rotation center
                dx = current_pos.x() - center.x()
                dy = current_pos.y() - center.y()

                # Apply rotation matrix
                new_dx = dx * cos_angle - dy * sin_angle
                new_dy = dx * sin_angle + dy * cos_angle

                # Translate back
                new_pos = QPointF(center.x() + new_dx, center.y() + new_dy)

                # Apply new position immediately - no validation!
                handle.setPos(new_pos)
                rotated_count += 1

                # Update key_points in layer_data
                if hasattr(handle, 'anchor_name') and mechanism_id in mechanism_layers:
                    layer_data = mechanism_layers[mechanism_id]
                    if "key_points" not in layer_data:
                        layer_data["key_points"] = {}
                    layer_data["key_points"][handle.anchor_name] = [new_pos.x(), new_pos.y()]

            # Update visual feedback (always show as "approximate" in free mode)
            if rotated_count > 0 and show_feedback_fn:
                show_feedback_fn(mechanism_id)

            # Force scene update
            scene.update()

            return rotated_count

        except Exception:
            return 0

    def update_other_handles(
        self,
        mechanism_id: str,
        moved_handle: str,
        handles: list[QGraphicsItem],
        layer_data: dict[str, Any],
        transform_fn: Callable[[dict[str, Any]], Callable[[np.ndarray], QPointF] | None],
    ) -> None:
        """
        Update positions of other parametric handles when one handle is moved.

        Args:
            mechanism_id: Mechanism ID
            moved_handle: Name of handle that was moved (to skip)
            handles: List of handles for this mechanism
            layer_data: Mechanism layer data with key_points
            transform_fn: Function to get scene transform from layer_data
        """
        if not handles or not layer_data:
            return

        try:
            key_points = layer_data.get("key_points", {})
            to_scene = transform_fn(layer_data)

            def _scene_pos_from_mech(pos_list: list[float]) -> QPointF:
                if to_scene:
                    return to_scene(np.array(pos_list))
                return QPointF(float(pos_list[0]), float(pos_list[1]))

            # Prevent recursive callbacks during programmatic moves
            self._updating_handles_programmatically = True
            try:
                for handle in handles:
                    if getattr(handle, 'handle_type', '') == 'rotation':
                        continue

                    anchor_name = getattr(handle, 'anchor_name', '')
                    if not anchor_name:
                        handle_id = getattr(handle, 'handle_id', '')
                        parts = handle_id.split('_', 1)
                        anchor_name = parts[1] if len(parts) > 1 else ''

                    if not anchor_name or anchor_name == moved_handle:
                        continue

                    if anchor_name in key_points:
                        new_scene_pos = _scene_pos_from_mech(key_points[anchor_name])

                        # Temporarily disable callback if present
                        original_cb = getattr(handle, 'update_callback', None)
                        if original_cb is not None:
                            handle.update_callback = None
                        handle.setPos(new_scene_pos)
                        if original_cb is not None:
                            handle.update_callback = original_cb
            finally:
                self._updating_handles_programmatically = False

        except Exception:
            pass

    def update_handles_from_key_points(
        self,
        mechanism_id: str,
        handles: list[QGraphicsItem],
        layer_data: dict[str, Any],
        transform_fn: Callable[[dict[str, Any]], Callable[[np.ndarray], QPointF] | None],
    ) -> int:
        """
        Update scene handle positions to match updated key_points after kinematic constraints.

        ULTRATHINK: Prevents infinite recursion by temporarily disabling callbacks.

        Args:
            mechanism_id: Mechanism ID
            handles: List of handles for this mechanism
            layer_data: Layer data with updated key_points
            transform_fn: Function to get scene transform from layer_data

        Returns:
            Number of handles updated
        """
        if not handles:
            return 0

        try:
            to_scene = transform_fn(layer_data)
            key_points = layer_data.get("key_points", {})

            # ULTRATHINK: Set flag to prevent callback recursion
            self._updating_handles_programmatically = True

            updated_count = 0
            for handle in handles:
                handle_id = getattr(handle, 'handle_id', '')
                anchor_name = getattr(handle, 'anchor_name', '')

                # Extract anchor name from handle_id if anchor_name not available
                if not anchor_name and handle_id:
                    parts = handle_id.split('_', 1)
                    if len(parts) > 1:
                        anchor_name = parts[1]

                if anchor_name in key_points:
                    mech_pos = key_points[anchor_name]

                    if to_scene:
                        scene_pos = to_scene(np.array(mech_pos))
                    else:
                        scene_pos = QPointF(mech_pos[0], mech_pos[1])

                    # ULTRATHINK: Temporarily disable callback for DraggableHandle
                    original_callback = None
                    if hasattr(handle, 'update_callback'):
                        original_callback = handle.update_callback
                        handle.update_callback = None

                    handle.setPos(scene_pos)

                    if original_callback:
                        handle.update_callback = original_callback

                    updated_count += 1

            # Clear the flag
            self._updating_handles_programmatically = False
            return updated_count

        except Exception:
            self._updating_handles_programmatically = False
            return 0

    def update_handles_for_mechanism(
        self,
        mechanism_id: str,
        handles: list[QGraphicsItem],
        layer_data: dict[str, Any],
        anchor_positions: dict[str, QPointF],
    ) -> int:
        """
        Update handle positions to match mechanism's current state.

        Args:
            mechanism_id: Mechanism ID
            handles: List of handles for this mechanism
            layer_data: Current mechanism data
            anchor_positions: Pre-calculated anchor positions

        Returns:
            Number of handles updated
        """
        if not handles:
            return 0

        try:
            mechanism_type = layer_data.get("type")
            updated_count = 0

            for handle in handles:
                handle_id = getattr(handle, 'handle_id', None)
                if not handle_id:
                    continue

                new_pos = None

                # Map handle IDs to anchor positions based on mechanism type
                if mechanism_type == "cam":
                    if "rod_length" in handle_id:
                        new_pos = anchor_positions.get("cam_rod_length")
                    elif "cam_size" in handle_id:
                        new_pos = anchor_positions.get("cam_size")

                elif mechanism_type == "gear":
                    if "gear1_center" in handle_id:
                        new_pos = anchor_positions.get("gear1_center")
                    elif "gear2_center" in handle_id:
                        new_pos = anchor_positions.get("gear2_center")

                elif mechanism_type == "planetary_gear":
                    if "sun_center" in handle_id:
                        new_pos = anchor_positions.get("sun_center")
                    elif "planet_center" in handle_id:
                        new_pos = anchor_positions.get("planet_center")

                elif mechanism_type == "4_bar_linkage":
                    anchor_name = getattr(handle, 'anchor_name', None)
                    if anchor_name and anchor_name in anchor_positions:
                        new_pos = anchor_positions[anchor_name]

                if new_pos:
                    handle.setPos(new_pos)
                    updated_count += 1

            return updated_count

        except Exception:
            return 0

    def create_rotation_handle(
        self,
        parent_tab: Any,
        mechanism_id: str,
        center_pos: QPointF,
        radius: float = 60,
    ) -> QGraphicsItem | None:
        """
        Create a rotation handle using custom class with built-in drag logic.

        Args:
            parent_tab: Parent tab reference for callbacks
            mechanism_id: ID of the mechanism
            center_pos: Center position for the rotation handle
            radius: Distance from center for the handle

        Returns:
            QGraphicsItem: The rotation handle with built-in rotation logic, or None
        """
        if not self._rotation_handle_class:
            return None

        try:
            rotation_handle = self._rotation_handle_class(
                parent_tab=parent_tab,
                mechanism_id=mechanism_id,
                center_pos=center_pos,
                radius=radius
            )
            return rotation_handle

        except Exception:
            return None

    def create_gear_handles(
        self,
        mechanism_id: str,
        layer_data: dict[str, Any],
        scene: QGraphicsScene,
        add_rotation_handle_fn: Callable[[str, list, dict], None] | None = None,
    ) -> list[QGraphicsItem]:
        """
        Create handles for gear mechanism with rotation.

        Args:
            mechanism_id: Mechanism ID
            layer_data: Mechanism layer data
            scene: Graphics scene to add handles to
            add_rotation_handle_fn: Optional callback to add rotation handle

        Returns:
            List of created handles
        """
        try:
            handles: list[QGraphicsItem] = []

            # Define gear control points
            center_x, center_y = 400, 300
            anchor_positions = {
                "gear_center_1": QPointF(center_x - 60, center_y),
                "gear_center_2": QPointF(center_x + 60, center_y),
                "radius_control_1": QPointF(center_x - 60, center_y - 50),
                "radius_control_2": QPointF(center_x + 60, center_y - 50)
            }

            # Create anchor handles
            for anchor_name, anchor_pos in anchor_positions.items():
                anchor_handle = QGraphicsEllipseItem(-15, -15, 30, 30)
                anchor_handle.setPos(anchor_pos)
                anchor_handle.setBrush(QBrush(QColor(255, 50, 50)))
                anchor_handle.setPen(QPen(QColor(200, 40, 40), 2))
                anchor_handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                anchor_handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                anchor_handle.setZValue(1000000)

                anchor_handle.handle_id = f"{mechanism_id}_{anchor_name}"
                anchor_handle.anchor_name = anchor_name
                anchor_handle.setToolTip(f"Gear Mechanism: {anchor_name}")

                scene.addItem(anchor_handle)
                handles.append(anchor_handle)

            # Add rotation handle
            if add_rotation_handle_fn:
                add_rotation_handle_fn(mechanism_id, handles, anchor_positions)

            return handles

        except Exception:
            return []
