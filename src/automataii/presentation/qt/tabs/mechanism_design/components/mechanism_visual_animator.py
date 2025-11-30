"""
Mechanism Visual Animator - Update visual elements during animation.

Extracted from MechanismDesignTab. Handles all visual updates for
4-bar, cam, gear, and planetary gear mechanisms during animation.

Design Pattern: Strategy (mechanism-type-specific visual updates)
"""
from __future__ import annotations

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

    Time Complexity: O(v) where v = number of visual items
    """

    def __init__(
        self,
        get_scene_transform: Callable[[dict], Callable | None],
        set_line_if_changed: Callable[[QGraphicsLineItem, QPointF, QPointF, float], None] | None = None,
    ) -> None:
        """
        Initialize animator.

        Args:
            get_scene_transform: Callback to get scene transform function
            set_line_if_changed: Optional callback for optimized line updates
        """
        self._get_scene_transform = get_scene_transform
        self._set_line_if_changed = set_line_if_changed or self._default_set_line

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
            if (abs(current.p1().x() - p1.x()) > eps or
                abs(current.p1().y() - p1.y()) > eps or
                abs(current.p2().x() - p2.x()) > eps or
                abs(current.p2().y() - p2.y()) > eps):
                line_item.setLine(QLineF(p1, p2))
        except Exception:
            try:
                line_item.setLine(QLineF(p1, p2))
            except Exception:
                pass

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

            if mech_type == "4_bar_linkage":
                self._update_4bar_visuals(time, layer_data, visual_items)
            elif mech_type == "cam":
                self._update_cam_visuals(time, layer_data, visual_items, visuals_factory)
            elif mech_type == "gear":
                self._update_gear_visuals(time, layer_data, visual_items)
            elif mech_type == "planetary_gear":
                self._update_planetary_gear_visuals(time, layer_data, visual_items)

        except Exception:
            pass

    def _update_4bar_visuals(
        self,
        time: float,
        layer_data: dict,
        visual_items: list,
    ) -> None:
        """Update 4-bar linkage visual elements."""
        if len(visual_items) < 13:
            return

        full_sim_data = layer_data.get("full_simulation_data", {})
        to_scene_coords = self._get_scene_transform(layer_data)

        if "joint_positions" not in full_sim_data or not to_scene_coords:
            return

        joint_positions = full_sim_data["joint_positions"]
        if "p1_positions" not in joint_positions:
            return

        num_frames = len(joint_positions["p1_positions"])
        normalized_time = time / (2 * math.pi)

        # Direction correction
        reverse_direction = layer_data.get("reverse_direction", False)
        if reverse_direction:
            normalized_time = 1.0 - normalized_time

        frame_index = int(normalized_time * (num_frames - 1))
        frame_index = max(0, min(frame_index, num_frames - 1))

        # Get exact positions from dataset
        p1 = np.array(joint_positions["p1_positions"][frame_index])
        p2 = np.array(joint_positions["p2_positions"][frame_index])
        p3 = np.array(joint_positions["p3_positions"][frame_index])
        p4 = np.array(joint_positions["p4_positions"][frame_index])

        # Calculate coupler point
        params = layer_data.get("params", {})
        coupler_point_x = params.get("coupler_point_x", 0.0)
        coupler_point_y = params.get("coupler_point_y", 0.0)

        coupler_vec = p4 - p3
        coupler_length = np.linalg.norm(coupler_vec)
        if coupler_length > 0:
            coupler_unit = coupler_vec / coupler_length
            coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
            p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
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

        # Update moving pivot positions (items 6-7 outer, 10-11 inner)
        moving_pivot_positions = [p3_t, p4_t]

        for i, pos in enumerate(moving_pivot_positions):
            outer_idx = 6 + i
            inner_idx = 10 + i

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

    def _update_cam_visuals(
        self,
        time: float,
        layer_data: dict,
        visual_items: list,
        visuals_factory: Any | None = None,
    ) -> None:
        """Update cam mechanism visual elements."""
        if len(visual_items) < 2:
            return

        params = layer_data.get("params", {})
        base_radius = params.get("base_radius", 25.0)
        eccentricity = params.get("eccentricity", 10.0)

        # Get scaling factors
        cam_scale_factor = layer_data.get('cam_scale_factor', 1.0)
        rod_length_multiplier = layer_data.get('rod_length_multiplier', 1.0)

        scaled_base_radius = base_radius * cam_scale_factor
        scaled_eccentricity = eccentricity * cam_scale_factor
        scaled_rod_length = params.get("follower_rod_length", 40.0) * rod_length_multiplier

        # Get transform function
        cam_to_scene_coords = layer_data.get('cam_transform_function')
        if not cam_to_scene_coords:
            return

        cam_profile_local = layer_data.get('cam_profile_local_points')
        cam_points_local = layer_data.get('cam_points_local')

        # Regenerate cam points if needed
        if cam_profile_local is not None and len(cam_profile_local) > 2 and visuals_factory:
            try:
                cam_points_local = visuals_factory._build_cam_from_template(
                    cam_profile_local,
                    scaled_base_radius,
                    scaled_eccentricity,
                    num_samples=180
                )
                layer_data['cam_points_local'] = cam_points_local
            except Exception:
                pass

        # Calculate rotated cam profile
        cam_polygon_points = []
        current_cam_center = np.array([0.0, 0.0])

        if cam_points_local is not None and len(cam_points_local) > 2:
            angle = time
            cos_r, sin_r = np.cos(angle), np.sin(angle)
            rot = np.array([[cos_r, -sin_r], [sin_r, cos_r]])
            rotated = cam_points_local @ rot.T

            for p in rotated:
                scene_point = cam_to_scene_coords(p)
                cam_polygon_points.append(scene_point)

            float(np.max(rotated[:, 1]))
        elif cam_profile_local is not None and len(cam_profile_local) > 2:
            angle = time
            cos_r, sin_r = np.cos(angle), np.sin(angle)
            rot = np.array([[cos_r, -sin_r], [sin_r, cos_r]])
            rotated = cam_profile_local @ rot.T

            for p in rotated:
                scene_point = cam_to_scene_coords(p)
                cam_polygon_points.append(scene_point)

            float(np.max(rotated[:, 1]))
        else:
            # Fallback: circular cam
            num_points = 120
            for i in range(num_points + 1):
                theta = 2 * np.pi * (i / num_points)
                point = current_cam_center + scaled_base_radius * np.array([np.cos(theta), np.sin(theta)])
                scene_point = cam_to_scene_coords(point)
                cam_polygon_points.append(scene_point)

        # Update cam shape polygon
        if len(visual_items) >= 1 and isinstance(visual_items[0], QGraphicsPolygonItem):
            if cam_polygon_points:
                cam_polygon = QPolygonF(cam_polygon_points)
                visual_items[0].setPolygon(cam_polygon)

        # Update follower position
        if len(visual_items) >= 2 and isinstance(visual_items[1], QGraphicsRectItem):
            if cam_polygon_points:
                idx = max(range(len(cam_polygon_points)), key=lambda i: cam_polygon_points[i].y())
                y_contact = cam_polygon_points[idx].y()
            else:
                pt = cam_to_scene_coords(np.array([0.0, 0.0]))
                y_contact = pt.y()

            # Calculate scene scale
            try:
                u0 = cam_to_scene_coords(np.array([0.0, 0.0]))
                u1 = cam_to_scene_coords(np.array([0.0, 1.0]))
                unit_scale = ((u1.x() - u0.x()) ** 2 + (u1.y() - u0.y()) ** 2) ** 0.5
            except Exception:
                unit_scale = 1.0

            rod_scene = scaled_rod_length * unit_scale
            follower_scene_x = layer_data.get('follower_fixed_x_scene')
            if follower_scene_x is None:
                center_scene = cam_to_scene_coords(current_cam_center)
                follower_scene_x = center_scene.x()

            follower_scene_y = y_contact - rod_scene
            follower_width, follower_height = 20, 15
            visual_items[1].setRect(
                follower_scene_x - follower_width / 2,
                follower_scene_y - follower_height / 2,
                follower_width, follower_height
            )

        # Update cam center marker
        if len(visual_items) >= 3 and isinstance(visual_items[2], QGraphicsEllipseItem):
            cam_center_scene = cam_to_scene_coords(current_cam_center)
            visual_items[2].setRect(
                cam_center_scene.x() - 3, cam_center_scene.y() - 3, 6, 6
            )

        # Update rod connection line
        if len(visual_items) >= 4 and isinstance(visual_items[3], QGraphicsLineItem):
            if cam_polygon_points:
                idx = max(range(len(cam_polygon_points)), key=lambda i: cam_polygon_points[i].y())
                x_contact = cam_polygon_points[idx].x()
                y_contact = cam_polygon_points[idx].y()
            else:
                pt = cam_to_scene_coords(np.array([0.0, 0.0]))
                x_contact, y_contact = pt.x(), pt.y()

            try:
                u0 = cam_to_scene_coords(np.array([0.0, 0.0]))
                u1 = cam_to_scene_coords(np.array([0.0, 1.0]))
                unit_scale = ((u1.x() - u0.x()) ** 2 + (u1.y() - u0.y()) ** 2) ** 0.5
            except Exception:
                unit_scale = 1.0

            rod_scene = scaled_rod_length * unit_scale
            follower_scene_x = layer_data.get('follower_fixed_x_scene')
            if follower_scene_x is None:
                center_scene = cam_to_scene_coords(current_cam_center)
                follower_scene_x = center_scene.x()

            follower_scene_y = y_contact - rod_scene
            visual_items[3].setLine(QLineF(
                QPointF(x_contact, y_contact),
                QPointF(follower_scene_x, follower_scene_y)
            ))

    def _update_gear_visuals(
        self,
        time: float,
        layer_data: dict,
        visual_items: list,
    ) -> None:
        """Update gear mechanism visual elements."""
        if len(visual_items) < 4:
            return

        params = layer_data.get("params", {})
        r1 = params.get("r1", 30)
        r2 = params.get("r2", 50)
        full_sim_data = layer_data.get("full_simulation_data", {})
        gear_data = full_sim_data.get("gear_data", {})
        to_scene_coords = self._get_scene_transform(layer_data)

        if not to_scene_coords:
            return

        # Fixed positions
        distance = r1 + r2
        gear1_center = np.array([0, 0])
        gear2_center = np.array([distance, 0])

        # Get rotation angles
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
        else:
            theta1 = time
            theta2 = -theta1 * (r1 / r2)

        # Transform to scene coordinates
        g1_center_scene = to_scene_coords(gear1_center)
        g2_center_scene = to_scene_coords(gear2_center)

        # Calculate screen-space radii
        gear1_edge_orig = gear1_center + np.array([r1, 0])
        gear1_edge_scene = to_scene_coords(gear1_edge_orig)
        r1_screen = QLineF(g1_center_scene, gear1_edge_scene).length()

        gear2_edge_orig = gear2_center + np.array([r2, 0])
        gear2_edge_scene = to_scene_coords(gear2_edge_orig)
        r2_screen = QLineF(g2_center_scene, gear2_edge_scene).length()

        # Update gear bodies
        if len(visual_items) >= 2:
            if hasattr(visual_items[0], 'setRect'):
                visual_items[0].setRect(
                    g1_center_scene.x() - r1_screen, g1_center_scene.y() - r1_screen,
                    r1_screen * 2, r1_screen * 2
                )
            if hasattr(visual_items[1], 'setRect'):
                visual_items[1].setRect(
                    g2_center_scene.x() - r2_screen, g2_center_scene.y() - r2_screen,
                    r2_screen * 2, r2_screen * 2
                )

        # Update rotation indicators
        if len(visual_items) >= 4:
            if isinstance(visual_items[2], QGraphicsLineItem):
                end1 = g1_center_scene + QPointF(r1_screen * math.cos(theta1), r1_screen * math.sin(theta1))
                visual_items[2].setLine(QLineF(g1_center_scene, end1))

            if isinstance(visual_items[3], QGraphicsLineItem):
                end2 = g2_center_scene + QPointF(r2_screen * math.cos(theta2), r2_screen * math.sin(theta2))
                visual_items[3].setLine(QLineF(g2_center_scene, end2))

    def _update_planetary_gear_visuals(
        self,
        time: float,
        layer_data: dict,
        visual_items: list,
    ) -> None:
        """Update planetary gear mechanism visual elements."""
        if len(visual_items) < 5:
            return

        params = layer_data.get("params", {})
        r_sun = params.get("r_sun", 20)
        r_planet = params.get("r_planet", 30)
        arm_length = params.get("arm_length", 15)
        to_scene_coords = self._get_scene_transform(layer_data)

        if not to_scene_coords:
            return

        # Calculate normalized time
        normalized_time = time / (2 * math.pi)

        # Direction correction
        reverse_direction = layer_data.get("reverse_direction", False)
        if reverse_direction:
            normalized_time = 1.0 - normalized_time

        # Use dataset positions if available
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
                # Fallback calculation
                planet_orbital_angle = time
                planet_rotation_angle = -time * (r_sun / r_planet)
                sun_center_orig = np.array([0, 0])
                planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array([
                    np.cos(planet_orbital_angle), np.sin(planet_orbital_angle)
                ])
                tracking_point_orig = planet_center_orig + arm_length * np.array([
                    np.cos(planet_rotation_angle), np.sin(planet_rotation_angle)
                ])
        else:
            # Fallback calculation
            planet_orbital_angle = time
            planet_rotation_angle = -time * (r_sun / r_planet)
            sun_center_orig = np.array([0, 0])
            planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array([
                np.cos(planet_orbital_angle), np.sin(planet_orbital_angle)
            ])
            tracking_point_orig = planet_center_orig + arm_length * np.array([
                np.cos(planet_rotation_angle), np.sin(planet_rotation_angle)
            ])

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
                r_planet_screen * 2
            )

        # Update arm line (item 2)
        if len(visual_items) > 2 and isinstance(visual_items[2], QGraphicsLineItem):
            visual_items[2].setLine(QLineF(planet_center_scene, tracking_scene))

        # Update tracking point marker (item 3)
        if len(visual_items) > 3 and isinstance(visual_items[3], QGraphicsEllipseItem):
            visual_items[3].setRect(
                tracking_scene.x() - 8,
                tracking_scene.y() - 8,
                16, 16
            )
