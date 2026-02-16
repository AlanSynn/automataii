"""
Mechanism Visual Animator - Update visual elements during animation.

Extracted from MechanismDesignTab. Handles all visual updates for
4-bar, cam, gear, and planetary gear mechanisms during animation.

Design Pattern: Strategy (mechanism-type-specific visual updates)

Performance Optimizations:
- Uses AnimationCacheManager to avoid per-frame numpy allocations
- Caches pre-computed joint positions, cam profiles, gear angles
- Vectorized coordinate transforms where possible
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import numpy as np
from PyQt6.QtCore import QLineF, QPointF
from PyQt6.QtGui import QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
)

from .animation_cache import AnimationCacheManager

if TYPE_CHECKING:
    pass


class MechanismVisualAnimator:
    """
    Updates mechanism visual elements during animation.

    Responsibilities:
    - Update 4-bar linkage visuals (links, pivots, coupler)
    - Update cam mechanism visuals (profile, follower)
    - Update gear visuals (rotation indicators)
    - Update planetary gear visuals (orbiting planet)

    Performance: Uses AnimationCacheManager for O(1) position lookups
    instead of creating np.array() each frame.
    """

    def __init__(
        self,
        get_scene_transform: Callable[[dict], Callable | None],
        set_line_if_changed: Callable[[QGraphicsLineItem, QPointF, QPointF, float], None]
        | None = None,
        cache_manager: AnimationCacheManager | None = None,
    ) -> None:
        """
        Initialize animator.

        Args:
            get_scene_transform: Callback to get scene transform function
            set_line_if_changed: Optional callback for optimized line updates
            cache_manager: Optional cache manager for pre-computed data
        """
        self._get_scene_transform = get_scene_transform
        self._set_line_if_changed = set_line_if_changed or self._default_set_line
        self._cache_manager = cache_manager or AnimationCacheManager()
        # Helper to access TransformService's batch method if available
        # We assume get_scene_transform is bound method of TransformService, so we try to find the service instance
        self._transform_service_ref = getattr(get_scene_transform, "__self__", None)

    @property
    def mechanism_type(self) -> str:
        return "animator"

    def build_cache(self, mechanism_id: str, layer_data: dict[str, Any]) -> None:
        """Build animation cache for a mechanism. Call when mechanism is added."""
        self._cache_manager.build_cache(mechanism_id, layer_data)

    def remove_cache(self, mechanism_id: str) -> None:
        """Remove cache for a mechanism. Call when mechanism is removed."""
        self._cache_manager.remove_cache(mechanism_id)

    def clear_caches(self) -> None:
        """Clear all animation caches."""
        self._cache_manager.clear()

    @staticmethod
    def _default_set_line(
        line_item: QGraphicsLineItem,
        p1: QPointF,
        p2: QPointF,
        eps: float = 0.1,
    ) -> None:
        """Default line setter with epsilon check."""
        try:
            current = line_item.line()
            if (
                abs(current.p1().x() - p1.x()) > eps
                or abs(current.p1().y() - p1.y()) > eps
                or abs(current.p2().x() - p2.x()) > eps
                or abs(current.p2().y() - p2.y()) > eps
            ):
                line_item.setLine(QLineF(p1, p2))
        except Exception:
            try:
                line_item.setLine(QLineF(p1, p2))
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

    def update_visuals(
        self,
        mechanism_id: str,
        time: float,
        layer_data: dict,
        visuals_factory: Any | None = None,
    ) -> None:
        """
        Update mechanism visual elements for current animation time.

        Args:
            mechanism_id: Mechanism identifier
            time: Animation time (radians)
            layer_data: Layer data with visual items
            visuals_factory: Optional visuals factory for cam regeneration
        """
        try:
            mech_type = layer_data.get("type")
            visual_items = layer_data.get("visual_items", [])
            logging.debug(
                f"[VISUAL-ANIM] update_visuals called: type={mech_type}, items={len(visual_items)}, time={time:.3f}"
            )

            if mech_type == "4_bar_linkage":
                self._update_4bar_visuals(time, layer_data, visual_items, mechanism_id)
            elif mech_type == "5_bar_linkage":
                self._update_5bar_visuals(time, layer_data, visual_items, mechanism_id)
            elif mech_type == "6_bar_linkage":
                self._update_6bar_visuals(time, layer_data, visual_items, mechanism_id)
            elif mech_type == "cam":
                self._update_cam_visuals(
                    time, layer_data, visual_items, mechanism_id, visuals_factory
                )
            elif mech_type == "gear":
                self._update_gear_visuals(time, layer_data, visual_items, mechanism_id)
            elif mech_type == "planetary_gear":
                self._update_planetary_gear_visuals(time, layer_data, visual_items, mechanism_id)

        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

    def _update_4bar_visuals(
        self,
        time: float,
        layer_data: dict,
        visual_items: list,
        mechanism_id: str = "",
    ) -> None:
        """Update 4-bar linkage visual elements.

        Performance: Uses cached numpy arrays instead of per-frame allocation.
        """
        if len(visual_items) < 13:
            logging.debug(f"[4BAR-ANIM] Insufficient visual items: {len(visual_items)} < 13")
            return

        to_scene_coords = self._get_scene_transform(layer_data)
        if not to_scene_coords:
            return

        # Try to use cache first (O(1) lookup, no allocation)
        cache = self._cache_manager.get_linkage_cache(mechanism_id) if mechanism_id else None

        if cache and cache.num_frames > 0:
            normalized_time = time / (2 * math.pi)
            reverse_direction = layer_data.get("reverse_direction", False)
            if reverse_direction:
                normalized_time = 1.0 - normalized_time

            frame_index = int(normalized_time * (cache.num_frames - 1))
            p1, p2, p3, p4 = cache.get_frame_positions(frame_index)
            coupler_offset = cache.coupler_point_offset
        else:
            # Fallback to original method (for backwards compatibility)
            full_sim_data = layer_data.get("full_simulation_data", {})
            if "joint_positions" not in full_sim_data:
                return

            joint_positions = full_sim_data["joint_positions"]
            if "p1_positions" not in joint_positions:
                return

            num_frames = len(joint_positions["p1_positions"])
            normalized_time = time / (2 * math.pi)

            reverse_direction = layer_data.get("reverse_direction", False)
            if reverse_direction:
                normalized_time = 1.0 - normalized_time

            frame_index = int(normalized_time * (num_frames - 1))
            frame_index = max(0, min(frame_index, num_frames - 1))

            # Fallback: create arrays (less efficient)
            p1 = np.array(joint_positions["p1_positions"][frame_index])
            p2 = np.array(joint_positions["p2_positions"][frame_index])
            p3 = np.array(joint_positions["p3_positions"][frame_index])
            p4 = np.array(joint_positions["p4_positions"][frame_index])

            params = layer_data.get("params", {})
            # Support both param name conventions: coupler_point_x/y (internal) and p_x/p_y (JSON/dataset)
            coupler_offset = np.array(
                [
                    params.get("coupler_point_x") or params.get("p_x", 0.0),
                    params.get("coupler_point_y") or params.get("p_y", 0.0),
                ]
            )

        # Calculate coupler point (vectorized)
        coupler_vec = p4 - p3
        coupler_length = np.linalg.norm(coupler_vec)
        if coupler_length > 0:
            coupler_unit = coupler_vec / coupler_length
            coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
            p_coupler = p3 + coupler_offset[0] * coupler_unit + coupler_offset[1] * coupler_normal
        else:
            p_coupler = p3

        # Transform to scene coordinates
        p1_t = to_scene_coords(p1)
        p2_t = to_scene_coords(p2)
        p3_t = to_scene_coords(p3)
        p4_t = to_scene_coords(p4)
        p_coupler_t = to_scene_coords(p_coupler)

        # Update driver link (item 0)
        if len(visual_items) > 0:
            driver_link = visual_items[0]
            if isinstance(driver_link, QGraphicsLineItem):
                self._set_line_if_changed(driver_link, p1_t, p3_t, 0.1)

        # Update follower link (item 1)
        if len(visual_items) > 1:
            follower_link = visual_items[1]
            if isinstance(follower_link, QGraphicsLineItem):
                self._set_line_if_changed(follower_link, p2_t, p4_t, 0.1)

        # Update coupler triangle/line (item 2)
        if len(visual_items) > 2:
            coupler_item = visual_items[2]
            if isinstance(coupler_item, QGraphicsLineItem):
                coupler_item.setLine(QLineF(p3_t, p4_t))
            elif isinstance(coupler_item, QGraphicsPolygonItem):
                triangle_points = [p3_t, p4_t, p_coupler_t]
                triangle_polygon = QPolygonF(triangle_points)
                coupler_item.setPolygon(triangle_polygon)

        # Update moving pivot positions
        # Factory creates pivots in order: p1 outer(4), p1 inner(5), p2 outer(6), p2 inner(7),
        #                                  p3 outer(8), p3 inner(9), p4 outer(10), p4 inner(11)
        # Moving joints are p3 and p4, so:
        # - p3: outer at index 8, inner at index 9
        # - p4: outer at index 10, inner at index 11
        moving_pivot_positions = [p3_t, p4_t]

        for i, pos in enumerate(moving_pivot_positions):
            outer_idx = 8 + (i * 2)  # p3 at 8, p4 at 10
            inner_idx = 9 + (i * 2)  # p3 at 9, p4 at 11

            if len(visual_items) > outer_idx:
                outer_pivot = visual_items[outer_idx]
                if isinstance(outer_pivot, QGraphicsEllipseItem):
                    outer_pivot.setRect(pos.x() - 8, pos.y() - 8, 16, 16)

            if len(visual_items) > inner_idx:
                inner_pivot = visual_items[inner_idx]
                if isinstance(inner_pivot, QGraphicsEllipseItem):
                    inner_pivot.setRect(pos.x() - 4, pos.y() - 4, 8, 8)

        # Update coupler marker (item 12)
        if len(visual_items) > 12:
            coupler_marker = visual_items[12]
            if isinstance(coupler_marker, QGraphicsEllipseItem):
                coupler_marker.setRect(p_coupler_t.x() - 4, p_coupler_t.y() - 4, 8, 8)

        # Log successful update (only for first few frames to avoid spam)
        if time < 0.15:
            logging.debug(
                f"[4BAR-ANIM] Updated: p3={p3_t.x():.1f},{p3_t.y():.1f} p4={p4_t.x():.1f},{p4_t.y():.1f}"
            )

    def _update_5bar_visuals(
        self,
        time: float,
        layer_data: dict,
        visual_items: list,
        mechanism_id: str = "",
    ) -> None:
        """Update 5-bar linkage visual elements.

        Performance: Uses cached numpy arrays instead of per-frame allocation.
        """
        if len(visual_items) < 5:
            return

        to_scene_coords = self._get_scene_transform(layer_data)
        if not to_scene_coords:
            return

        # Try to use cache first
        cache = self._cache_manager.get_linkage_cache(mechanism_id) if mechanism_id else None

        if cache and cache.num_frames > 0:
            normalized_time = time / (2 * math.pi)
            reverse_direction = layer_data.get("reverse_direction", False)
            if reverse_direction:
                normalized_time = 1.0 - normalized_time

            frame_index = int(normalized_time * (cache.num_frames - 1))
            p1, p2, p3, p4, p5 = cache.get_frame_positions_5bar(frame_index)
        else:
            # Fallback
            full_sim_data = layer_data.get("full_simulation_data", {})
            if "joint_positions" not in full_sim_data:
                return

            joint_positions = full_sim_data["joint_positions"]
            if "p1_positions" not in joint_positions:
                return

            num_frames = len(joint_positions["p1_positions"])
            normalized_time = time / (2 * math.pi)

            reverse_direction = layer_data.get("reverse_direction", False)
            if reverse_direction:
                normalized_time = 1.0 - normalized_time

            frame_index = int(normalized_time * (num_frames - 1))
            frame_index = max(0, min(frame_index, num_frames - 1))

            p1 = np.array(joint_positions["p1_positions"][frame_index])
            p2 = np.array(joint_positions["p2_positions"][frame_index])
            p3 = np.array(joint_positions["p3_positions"][frame_index])
            p4 = np.array(joint_positions["p4_positions"][frame_index])
            p5 = np.array(joint_positions.get("p5_positions", [[0, 0]] * num_frames)[frame_index])

        # Transform to scene coordinates
        p1_t = to_scene_coords(p1)
        p2_t = to_scene_coords(p2)
        p3_t = to_scene_coords(p3)
        p4_t = to_scene_coords(p4)
        p5_t = to_scene_coords(p5)

        # Update links (items 0-3 are typically link lines)
        link_pairs = [(p1_t, p3_t), (p3_t, p4_t), (p4_t, p5_t), (p5_t, p2_t)]
        for i, (start, end) in enumerate(link_pairs):
            if len(visual_items) > i and isinstance(visual_items[i], QGraphicsLineItem):
                self._set_line_if_changed(visual_items[i], start, end, 0.1)

        # Update joint markers (items 4+)
        joint_positions_scene = [p3_t, p4_t, p5_t]
        for i, pos in enumerate(joint_positions_scene):
            item_idx = 4 + i
            if len(visual_items) > item_idx and isinstance(
                visual_items[item_idx], QGraphicsEllipseItem
            ):
                visual_items[item_idx].setRect(pos.x() - 6, pos.y() - 6, 12, 12)

    def _update_6bar_visuals(
        self,
        time: float,
        layer_data: dict,
        visual_items: list,
        mechanism_id: str = "",
    ) -> None:
        """Update 6-bar linkage visual elements.

        Performance: Uses cached numpy arrays instead of per-frame allocation.
        """
        if len(visual_items) < 6:
            return

        to_scene_coords = self._get_scene_transform(layer_data)
        if not to_scene_coords:
            return

        # Try to use cache first
        cache = self._cache_manager.get_linkage_cache(mechanism_id) if mechanism_id else None

        if cache and cache.num_frames > 0:
            normalized_time = time / (2 * math.pi)
            reverse_direction = layer_data.get("reverse_direction", False)
            if reverse_direction:
                normalized_time = 1.0 - normalized_time

            frame_index = int(normalized_time * (cache.num_frames - 1))
            p1, p2, p3, p4, p5, p6 = cache.get_frame_positions_6bar(frame_index)
        else:
            # Fallback
            full_sim_data = layer_data.get("full_simulation_data", {})
            if "joint_positions" not in full_sim_data:
                return

            joint_positions = full_sim_data["joint_positions"]
            if "p1_positions" not in joint_positions:
                return

            num_frames = len(joint_positions["p1_positions"])
            normalized_time = time / (2 * math.pi)

            reverse_direction = layer_data.get("reverse_direction", False)
            if reverse_direction:
                normalized_time = 1.0 - normalized_time

            frame_index = int(normalized_time * (num_frames - 1))
            frame_index = max(0, min(frame_index, num_frames - 1))

            p1 = np.array(joint_positions["p1_positions"][frame_index])
            p2 = np.array(joint_positions["p2_positions"][frame_index])
            p3 = np.array(joint_positions["p3_positions"][frame_index])
            p4 = np.array(joint_positions["p4_positions"][frame_index])
            p5 = np.array(joint_positions.get("p5_positions", [[0, 0]] * num_frames)[frame_index])
            p6 = np.array(joint_positions.get("p6_positions", [[0, 0]] * num_frames)[frame_index])

        # Transform to scene coordinates
        p1_t = to_scene_coords(p1)
        p2_t = to_scene_coords(p2)
        p3_t = to_scene_coords(p3)
        p4_t = to_scene_coords(p4)
        p5_t = to_scene_coords(p5)
        p6_t = to_scene_coords(p6)

        # Update links (items 0-4 are typically link lines)
        link_pairs = [(p1_t, p3_t), (p3_t, p4_t), (p4_t, p2_t), (p4_t, p5_t), (p5_t, p6_t)]
        for i, (start, end) in enumerate(link_pairs):
            if len(visual_items) > i and isinstance(visual_items[i], QGraphicsLineItem):
                self._set_line_if_changed(visual_items[i], start, end, 0.1)

        # Update joint markers (items 5+)
        joint_positions_scene = [p3_t, p4_t, p5_t]
        for i, pos in enumerate(joint_positions_scene):
            item_idx = 5 + i
            if len(visual_items) > item_idx and isinstance(
                visual_items[item_idx], QGraphicsEllipseItem
            ):
                visual_items[item_idx].setRect(pos.x() - 6, pos.y() - 6, 12, 12)

    def _update_cam_visuals(
        self,
        time: float,
        layer_data: dict,
        visual_items: list,
        mechanism_id: str = "",
        visuals_factory: Any | None = None,
    ) -> None:
        """
        Update cam mechanism visual elements (Foundry-compatible).

        Performance: Uses cached base profile and vectorized rotation.

        Visual items order:
        - Item 0: cam polygon (QGraphicsPolygonItem)
        - Item 1: contact point (QGraphicsEllipseItem)
        - Item 2: follower rod (QGraphicsLineItem)
        - Item 3: follower head (QGraphicsRectItem)
        - Item 4: follower anchor (QGraphicsRectItem)
        - Item 5: cam center pivot (QGraphicsEllipseItem)
        """
        if len(visual_items) < 4:
            return

        # Get transform function
        cam_to_scene_coords = layer_data.get("cam_transform_function")
        if not cam_to_scene_coords:
            cam_to_scene_coords = self._get_scene_transform(layer_data)
            if not cam_to_scene_coords:
                return

        cam_angle = time  # Cam rotation angle in radians

        # Get params for rod length calculation
        params = layer_data.get("params", {})
        follower_rod_length = params.get("follower_rod_length", params.get("follower_length", 40.0))
        rod_length_multiplier = layer_data.get("rod_length_multiplier", 1.0)
        scaled_rod_length = follower_rod_length * rod_length_multiplier

        # Prepare batch transform if available
        batch_transform = None
        if self._transform_service_ref and hasattr(
            self._transform_service_ref, "get_batch_scene_transform"
        ):
            batch_transform = self._transform_service_ref.get_batch_scene_transform(layer_data)

        # Priority: Use pre-computed cam profile from factory (pear-cam or custom profile)
        cam_points_local = layer_data.get("cam_points_local")

        if cam_points_local is not None and len(cam_points_local) > 0:
            # Apply rotation to the pre-computed profile
            cos_a = np.cos(cam_angle)
            sin_a = np.sin(cam_angle)

            # Vectorized rotation of all points
            if isinstance(cam_points_local, np.ndarray):
                rotated_x = cam_points_local[:, 0] * cos_a - cam_points_local[:, 1] * sin_a
                rotated_y = cam_points_local[:, 0] * sin_a + cam_points_local[:, 1] * cos_a
                rotated_profile = np.column_stack([rotated_x, rotated_y])
            else:
                pts_array = np.array(cam_points_local)
                rotated_x = pts_array[:, 0] * cos_a - pts_array[:, 1] * sin_a
                rotated_y = pts_array[:, 0] * sin_a + pts_array[:, 1] * cos_a
                rotated_profile = np.column_stack([rotated_x, rotated_y])

            # Transform to scene coordinates (Batch Optimized)
            if batch_transform:
                cam_polygon_points = batch_transform(rotated_profile)
            else:
                cam_polygon_points = [cam_to_scene_coords(pt) for pt in rotated_profile]

            # Calculate contact radius
            follower_angle_in_profile = -np.pi / 2 - cam_angle
            follower_angle_norm = follower_angle_in_profile % (2 * np.pi)
            num_pts = len(cam_points_local)
            profile_idx = int((follower_angle_norm / (2 * np.pi)) * num_pts) % num_pts

            # Safe indexing
            if isinstance(cam_points_local, list):
                contact_pt = cam_points_local[profile_idx]
            else:
                contact_pt = cam_points_local[profile_idx]
            contact_radius = float(np.sqrt(contact_pt[0] ** 2 + contact_pt[1] ** 2))

        else:
            # Fallback: Try to use cache (harmonic formula)
            cache = self._cache_manager.get_cam_cache(mechanism_id) if mechanism_id else None

            if cache:
                # Use cached base profile with vectorized rotation
                rotated_profile = cache.get_rotated_profile(cam_angle)
                contact_radius = cache.get_contact_radius(cam_angle)
                scaled_rod_length = cache.rod_length

                # Transform all points at once (Batch Optimized)
                if batch_transform:
                    cam_polygon_points = batch_transform(rotated_profile)
                else:
                    cam_polygon_points = [cam_to_scene_coords(pt) for pt in rotated_profile]
            else:
                # Last fallback: compute harmonic formula directly
                # (Keep legacy loop for robustness in edge cases)
                base_radius = params.get("base_radius", params.get("cam_radius", 60.0))
                cam_offset = params.get("eccentricity", params.get("cam_offset", 20.0))
                cam_lobes = int(params.get("cam_lobes", 1))
                profile_harmonic = params.get("profile_harmonic", 0.3)

                cam_scale_factor = layer_data.get("cam_scale_factor", 1.0)

                scaled_base_radius = base_radius * cam_scale_factor
                scaled_cam_offset = cam_offset * cam_scale_factor

                num_points = 72
                # Generate points
                thetas = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
                primary_var = scaled_cam_offset * np.cos(cam_lobes * thetas)
                secondary_var = (scaled_cam_offset * profile_harmonic) * np.cos(
                    2 * cam_lobes * thetas
                )
                radii = scaled_base_radius + primary_var + secondary_var

                rotated_thetas = thetas + cam_angle
                xs = radii * np.cos(rotated_thetas)
                ys = radii * np.sin(rotated_thetas)

                raw_points = np.column_stack([xs, ys])

                if batch_transform:
                    cam_polygon_points = batch_transform(raw_points)
                else:
                    cam_polygon_points = [cam_to_scene_coords(pt) for pt in raw_points]

                # Calculate contact radius for fallback
                follower_theta = -np.pi / 2 - cam_angle
                primary = scaled_cam_offset * np.cos(cam_lobes * follower_theta)
                secondary = (scaled_cam_offset * profile_harmonic) * np.cos(
                    2 * cam_lobes * follower_theta
                )
                contact_radius = scaled_base_radius + primary + secondary

        # Cam center in mechanism coordinates
        cam_center_local = np.array([0.0, 0.0])
        cam_center_scene = cam_to_scene_coords(cam_center_local)

        # Update cam shape polygon (item 0)
        if isinstance(visual_items[0], QGraphicsPolygonItem):
            cam_polygon = QPolygonF(cam_polygon_points)
            visual_items[0].setPolygon(cam_polygon)

        # Contact point position (contact_radius already calculated above)
        contact_local = np.array([0.0, -contact_radius])
        contact_scene = cam_to_scene_coords(contact_local)

        # Calculate scene scale for rod length conversion
        try:
            u0 = cam_to_scene_coords(np.array([0.0, 0.0]))
            u1 = cam_to_scene_coords(np.array([0.0, 1.0]))
            unit_scale = ((u1.x() - u0.x()) ** 2 + (u1.y() - u0.y()) ** 2) ** 0.5
        except Exception:
            unit_scale = 1.0

        rod_scene = scaled_rod_length * unit_scale

        # Follower X is fixed at cam center X
        follower_x = layer_data.get("follower_fixed_x_scene", cam_center_scene.x())

        # Follower base Y (at end of rod above contact due to gravity)
        # In scene coords, Y+ is down, so subtract rod_scene to move upward
        follower_base_y = contact_scene.y() - rod_scene

        # Update contact point (item 1)
        if len(visual_items) > 1 and isinstance(visual_items[1], QGraphicsEllipseItem):
            visual_items[1].setRect(contact_scene.x() - 5, contact_scene.y() - 5, 10, 10)

        # Update follower rod (item 2)
        if len(visual_items) > 2 and isinstance(visual_items[2], QGraphicsLineItem):
            visual_items[2].setLine(QLineF(contact_scene, QPointF(follower_x, follower_base_y)))

        # Update follower head (item 3)
        if len(visual_items) > 3 and isinstance(visual_items[3], QGraphicsRectItem):
            visual_items[3].setRect(follower_x - 15, follower_base_y - 8, 30, 15)

        # Update follower anchor (item 4) - fixed position
        if len(visual_items) > 4 and isinstance(visual_items[4], QGraphicsRectItem):
            visual_items[4].setRect(follower_x - 30, follower_base_y - 45, 60, 30)

        # Update cam center pivot (item 5)
        if len(visual_items) > 5 and isinstance(visual_items[5], QGraphicsEllipseItem):
            visual_items[5].setRect(cam_center_scene.x() - 8, cam_center_scene.y() - 8, 16, 16)

    def _update_gear_visuals(
        self,
        time: float,
        layer_data: dict,
        visual_items: list,
        mechanism_id: str = "",
    ) -> None:
        """Update gear mechanism visual elements.

        Performance: Uses cached gear parameters and angles.
        """
        if len(visual_items) < 4:
            return

        params = layer_data.get("params", {})
        use_scene_geometry = all(
            key in params for key in ("gear1_x", "gear1_y", "gear2_x", "gear2_y")
        )

        to_scene_coords = None
        if not use_scene_geometry:
            to_scene_coords = self._get_scene_transform(layer_data)
            if not to_scene_coords:
                return

        # Try to use cache first
        cache = self._cache_manager.get_gear_cache(mechanism_id) if mechanism_id else None

        r1 = float(params.get("gear1_radius", params.get("r1", 30)))
        r2 = float(params.get("gear2_radius", params.get("r2", 50)))
        if r1 <= 0:
            r1 = 1.0
        if r2 <= 0:
            r2 = 1.0

        theta1 = time
        theta2 = -theta1 * (r1 / r2)

        if cache:
            gear1_center = np.array(cache.gear1_center, dtype=float)
            gear2_center = np.array(cache.gear2_center, dtype=float)
            if not use_scene_geometry:
                r1 = cache.gear1_radius
                r2 = cache.gear2_radius
            theta1, theta2 = cache.get_angles(time)
        else:
            # Fallback
            full_sim_data = layer_data.get("full_simulation_data", {})
            gear_data = full_sim_data.get("gear_data", {})

            distance = r1 + r2
            gear1_center = np.array([0, 0])
            gear2_center = np.array([distance, 0])

            if gear_data and "gear1_angles" in gear_data and "gear2_angles" in gear_data:
                gear1_angles = gear_data["gear1_angles"]
                gear2_angles = gear_data["gear2_angles"]
                num_frames = len(gear1_angles)

                if num_frames > 0:
                    normalized_time = (time / (2 * np.pi)) % 1.0
                    frame_index = int(normalized_time * (num_frames - 1))
                    frame_index = max(0, min(frame_index, num_frames - 1))

                    full_rotations = int(time / (2 * np.pi))
                    theta1 = gear1_angles[frame_index] + full_rotations * 2 * np.pi
                    theta2 = gear2_angles[frame_index] + full_rotations * 2 * np.pi * (-r1 / r2)

        if use_scene_geometry:
            g1_center_scene = QPointF(float(params["gear1_x"]), float(params["gear1_y"]))
            g2_center_scene = QPointF(float(params["gear2_x"]), float(params["gear2_y"]))
            r1_screen = float(params.get("gear1_radius", r1))
            r2_screen = float(params.get("gear2_radius", r2))
            if r1_screen <= 0:
                r1_screen = r1
            if r2_screen <= 0:
                r2_screen = r2
        else:
            # Transform to scene coordinates from mechanism space.
            g1_center_scene = to_scene_coords(gear1_center)
            g2_center_scene = to_scene_coords(gear2_center)

            gear1_edge_orig = gear1_center + np.array([r1, 0])
            gear1_edge_scene = to_scene_coords(gear1_edge_orig)
            r1_screen = QLineF(g1_center_scene, gear1_edge_scene).length()

            gear2_edge_orig = gear2_center + np.array([r2, 0])
            gear2_edge_scene = to_scene_coords(gear2_edge_orig)
            r2_screen = QLineF(g2_center_scene, gear2_edge_scene).length()

        # Update gear bodies
        if len(visual_items) >= 2:
            if hasattr(visual_items[0], "setRect"):
                visual_items[0].setRect(
                    g1_center_scene.x() - r1_screen,
                    g1_center_scene.y() - r1_screen,
                    r1_screen * 2,
                    r1_screen * 2,
                )
            if hasattr(visual_items[1], "setRect"):
                visual_items[1].setRect(
                    g2_center_scene.x() - r2_screen,
                    g2_center_scene.y() - r2_screen,
                    r2_screen * 2,
                    r2_screen * 2,
                )

        # Update rotation indicators
        if len(visual_items) >= 4:
            if isinstance(visual_items[2], QGraphicsLineItem):
                end1 = g1_center_scene + QPointF(
                    r1_screen * math.cos(theta1), r1_screen * math.sin(theta1)
                )
                visual_items[2].setLine(QLineF(g1_center_scene, end1))

            if isinstance(visual_items[3], QGraphicsLineItem):
                end2 = g2_center_scene + QPointF(
                    r2_screen * math.cos(theta2), r2_screen * math.sin(theta2)
                )
                visual_items[3].setLine(QLineF(g2_center_scene, end2))

    def _update_planetary_gear_visuals(
        self,
        time: float,
        layer_data: dict,
        visual_items: list,
        mechanism_id: str = "",
    ) -> None:
        """Update planetary gear mechanism visual elements.

        Performance: Uses cached positions and parameters.
        """
        if len(visual_items) < 5:
            return

        to_scene_coords = self._get_scene_transform(layer_data)
        if not to_scene_coords:
            return

        # Try to use cache first
        cache = self._cache_manager.get_planetary_cache(mechanism_id) if mechanism_id else None
        reverse_direction = layer_data.get("reverse_direction", False)

        if cache:
            r_planet = cache.r_planet
            sun_center_orig, planet_center_orig, tracking_point_orig = cache.get_positions(
                time, reverse_direction
            )
        else:
            # Fallback
            params = layer_data.get("params", {})
            r_sun = float(params.get("r_sun", params.get("gear1_radius", 20.0)))
            r_planet = float(params.get("r_planet", params.get("gear2_radius", 30.0)))
            arm_length = float(params.get("arm_length", 15.0))
            if r_planet <= 0:
                r_planet = 1.0

            key_points = layer_data.get("key_points", {})
            if "sun_center" in key_points:
                base_sun_center = np.array(key_points["sun_center"], dtype=float)
            elif "m_sun_x" in params and "m_sun_y" in params:
                base_sun_center = np.array(
                    [float(params.get("m_sun_x", 0.0)), float(params.get("m_sun_y", 0.0))],
                    dtype=float,
                )
            elif "sun_x" in params and "sun_y" in params:
                base_sun_center = np.array(
                    [float(params.get("sun_x", 0.0)), float(params.get("sun_y", 0.0))],
                    dtype=float,
                )
            elif "gear1_x" in params and "gear1_y" in params:
                base_sun_center = np.array(
                    [float(params.get("gear1_x", 0.0)), float(params.get("gear1_y", 0.0))],
                    dtype=float,
                )
            else:
                base_sun_center = np.array([0.0, 0.0], dtype=float)

            normalized_time = time / (2 * math.pi)
            if reverse_direction:
                normalized_time = 1.0 - normalized_time

            full_sim_data = layer_data.get("full_simulation_data", {})
            gear_positions = full_sim_data.get("gear_positions", {})

            if gear_positions and "planet_centers" in gear_positions:
                planet_centers = gear_positions.get("planet_centers", [])
                sun_centers = gear_positions.get("sun_centers", [])
                tracking_points = gear_positions.get("tracking_points", [])

                if planet_centers and sun_centers and tracking_points:
                    num_frames = len(planet_centers)
                    frame_index = int(normalized_time * (num_frames - 1))
                    frame_index = max(0, min(frame_index, num_frames - 1))

                    sun_center_orig = np.array(sun_centers[frame_index])
                    planet_center_orig = np.array(planet_centers[frame_index])
                    tracking_point_orig = np.array(tracking_points[frame_index])
                else:
                    planet_orbital_angle = time
                    planet_rotation_angle = -time * (r_sun / r_planet)
                    sun_center_orig = base_sun_center
                    planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array(
                        [np.cos(planet_orbital_angle), np.sin(planet_orbital_angle)]
                    )
                    tracking_point_orig = planet_center_orig + arm_length * np.array(
                        [np.cos(planet_rotation_angle), np.sin(planet_rotation_angle)]
                    )
            else:
                planet_orbital_angle = time
                planet_rotation_angle = -time * (r_sun / r_planet)
                sun_center_orig = base_sun_center
                planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array(
                    [np.cos(planet_orbital_angle), np.sin(planet_orbital_angle)]
                )
                tracking_point_orig = planet_center_orig + arm_length * np.array(
                    [np.cos(planet_rotation_angle), np.sin(planet_rotation_angle)]
                )

        # Transform to scene coordinates
        planet_center_scene = to_scene_coords(planet_center_orig)
        tracking_scene = to_scene_coords(tracking_point_orig)

        # Update planet gear position (item 1)
        if len(visual_items) > 1 and isinstance(visual_items[1], QGraphicsEllipseItem):
            planet_edge_orig = planet_center_orig + np.array([r_planet, 0])
            planet_edge_scene = to_scene_coords(planet_edge_orig)
            r_planet_screen = QLineF(planet_center_scene, planet_edge_scene).length()

            visual_items[1].setRect(
                planet_center_scene.x() - r_planet_screen,
                planet_center_scene.y() - r_planet_screen,
                r_planet_screen * 2,
                r_planet_screen * 2,
            )

        # Update arm line (item 2)
        if len(visual_items) > 2 and isinstance(visual_items[2], QGraphicsLineItem):
            visual_items[2].setLine(QLineF(planet_center_scene, tracking_scene))

        # Update tracking point marker (item 3)
        if len(visual_items) > 3 and isinstance(visual_items[3], QGraphicsEllipseItem):
            visual_items[3].setRect(tracking_scene.x() - 8, tracking_scene.y() - 8, 16, 16)
