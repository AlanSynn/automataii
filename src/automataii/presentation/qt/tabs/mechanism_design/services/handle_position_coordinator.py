"""
Handle Position Coordinator for managing parametric handle positions.

Extracted from MechanismDesignTab as part of god class decomposition.
Coordinates handle creation, rotation, and position synchronization.

Design Pattern: Coordinator (orchestrates handle position operations)
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import Any

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsScene

_HANDLE_TO_KEY_POINT_ALIASES: dict[str, tuple[str, ...]] = {
    "anchor1": ("ground_pivot_1",),
    "anchor2": ("ground_pivot_2",),
    "crank": ("crank_end",),
    "rocker": ("rocker_end",),
    "coupler": ("coupler_point",),
    "center": ("cam_center",),
    "follower": ("follower_base", "follower_end"),
    "rod_length": ("follower_base", "follower_end"),
    "cam_rod_length": ("follower_base", "follower_end"),
    "cam_center": ("cam_center",),
}


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

    @staticmethod
    def _handle_anchor_name(handle: QGraphicsItem, mechanism_id: str) -> str:
        """Return the stable logical handle name used by key_points aliases."""
        for attr_name in ("anchor_name", "param_name"):
            raw = getattr(handle, attr_name, "")
            if isinstance(raw, str) and raw:
                return raw

        handle_id = getattr(handle, "handle_id", "")
        if not isinstance(handle_id, str) or not handle_id:
            return ""
        prefix = f"{mechanism_id}_"
        if handle_id.startswith(prefix):
            return handle_id[len(prefix):]
        return handle_id.rsplit("_", 1)[-1]

    @staticmethod
    def _point_from_key_points(
        anchor_name: str,
        key_points: dict[str, Any],
        layer_data: dict[str, Any],
    ) -> list[float] | tuple[float, float] | np.ndarray | None:
        """Resolve editor handle names such as `crank` to layer key_points."""
        if anchor_name in key_points:
            return key_points[anchor_name]

        for alias in _HANDLE_TO_KEY_POINT_ALIASES.get(anchor_name, ()):
            if alias in key_points:
                return key_points[alias]

        if anchor_name == "crank_length":
            p1 = HandlePositionCoordinator._finite_point_array(
                key_points.get("ground_pivot_1")
            )
            crank = HandlePositionCoordinator._finite_point_array(
                key_points.get("crank_end")
            )
            if p1 is not None and crank is not None:
                midpoint = (p1 + crank) / 2.0
                return midpoint

        if anchor_name == "coupler":
            return HandlePositionCoordinator._calculate_coupler_point(
                key_points,
                layer_data.get("params") if isinstance(layer_data, dict) else {},
            )

        return None

    @staticmethod
    def _finite_point_array(value: object) -> np.ndarray | None:
        try:
            point = np.asarray(value, dtype=float)
        except (TypeError, ValueError):
            return None
        if point.ndim != 1 or len(point) < 2:
            return None
        point = point[:2]
        if not bool(np.isfinite(point).all()):
            return None
        return point

    @staticmethod
    def _finite_float(value: object, default: float) -> float:
        if isinstance(value, bool):
            return default
        try:
            result = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
        return result if math.isfinite(result) else default

    @staticmethod
    def _calculate_coupler_point(
        key_points: dict[str, Any],
        params: object,
    ) -> np.ndarray | None:
        if not isinstance(params, dict):
            params = {}
        crank = HandlePositionCoordinator._finite_point_array(key_points.get("crank_end"))
        rocker = HandlePositionCoordinator._finite_point_array(key_points.get("rocker_end"))
        if crank is None or rocker is None:
            return None

        coupler_vec = rocker - crank
        coupler_length = float(np.linalg.norm(coupler_vec))
        if coupler_length <= 1e-9 or not math.isfinite(coupler_length):
            return crank
        coupler_unit = coupler_vec / coupler_length
        coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]], dtype=float)
        coupler_x = HandlePositionCoordinator._finite_float(
            params.get("coupler_point_x", params.get("p_x", coupler_length * 0.5)),
            coupler_length * 0.5,
        )
        coupler_y = HandlePositionCoordinator._finite_float(
            params.get("coupler_point_y", params.get("p_y", 0.0)),
            0.0,
        )
        return crank + coupler_x * coupler_unit + coupler_y * coupler_normal

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

                    anchor_name = self._handle_anchor_name(handle, mechanism_id)
                    if not anchor_name or anchor_name == moved_handle:
                        continue

                    point = self._point_from_key_points(anchor_name, key_points, layer_data)
                    if point is not None:
                        new_scene_pos = _scene_pos_from_mech(point)

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
            logging.debug("Suppressed exception", exc_info=True)

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
                anchor_name = self._handle_anchor_name(handle, mechanism_id)
                mech_pos = self._point_from_key_points(anchor_name, key_points, layer_data)

                if mech_pos is not None:
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
                    # Support both CamEditor naming (center, follower) and legacy (rod_length, cam_size)
                    if "center" in handle_id and "gear" not in handle_id:
                        new_pos = anchor_positions.get("cam_center") or anchor_positions.get("center")
                    elif "follower" in handle_id:
                        new_pos = (
                            anchor_positions.get("cam_follower")
                            or anchor_positions.get("follower")
                            or anchor_positions.get("cam_rod_length")
                        )
                    elif "size" in handle_id:
                        new_pos = anchor_positions.get("cam_size")
                    elif "rod_length" in handle_id:
                        new_pos = anchor_positions.get("cam_rod_length")
                    elif "cam_size" in handle_id:
                        new_pos = anchor_positions.get("cam_size")

                elif mechanism_type == "gear":
                    if "gear1_center" in handle_id:
                        new_pos = anchor_positions.get("gear1_center")
                    elif "gear2_center" in handle_id:
                        new_pos = anchor_positions.get("gear2_center")
                    elif "gear1_radius" in handle_id:
                        new_pos = anchor_positions.get("gear1_radius")
                    elif "gear2_radius" in handle_id:
                        new_pos = anchor_positions.get("gear2_radius")

                elif mechanism_type == "planetary_gear":
                    if "sun_center" in handle_id:
                        new_pos = anchor_positions.get("sun_center")
                    elif "planet_center" in handle_id:
                        new_pos = anchor_positions.get("planet_center")
                    elif "planet_radius" in handle_id:
                        new_pos = anchor_positions.get("planet_radius")
                    elif "arm_length" in handle_id:
                        new_pos = (
                            anchor_positions.get("arm_length")
                            or anchor_positions.get("tracking_point")
                        )

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
            # NOTE: Naming must match update_handles_for_mechanism() expectations
            center_x, center_y = 400, 300
            anchor_positions = {
                "gear1_center": QPointF(center_x - 60, center_y),
                "gear2_center": QPointF(center_x + 60, center_y),
                "gear1_radius": QPointF(center_x - 60, center_y - 50),
                "gear2_radius": QPointF(center_x + 60, center_y - 50)
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
