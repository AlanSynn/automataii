"""
Anchor Position Service for mechanism handle positioning.

Extracted from MechanismDesignTab as part of god class decomposition.
Calculates anchor positions for parametric handles across all mechanism types.

Design Pattern: Strategy (mechanism-specific position calculation)
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QGraphicsEllipseItem

from .transform_service import TransformService


class AnchorPositionService:
    """
    Calculates anchor positions for mechanism parametric handles.

    Responsibilities:
    - Determine handle positions for each mechanism type
    - Transform positions from mechanism space to scene space
    - Handle fallback positions when visual items not available

    Time Complexity: O(n) where n is number of visual items
    """

    def __init__(self, transform_service: TransformService) -> None:
        """
        Initialize with TransformService dependency.

        Args:
            transform_service: Service for coordinate transformations
        """
        self._transform_service = transform_service

    def get_anchor_positions(self, layer_data: dict[str, Any]) -> dict[str, QPointF]:
        """
        Get anchor positions for mechanism handles.

        Args:
            layer_data: Mechanism layer data containing type, params, visual_items

        Returns:
            Dictionary mapping anchor names to QPointF positions
        """
        anchor_positions: dict[str, QPointF] = {}
        mechanism_type = layer_data.get("type")

        try:
            # Get the transformation function for this mechanism
            to_scene_coords = self._transform_service.get_scene_transform(layer_data)

            if mechanism_type == "cam":
                anchor_positions = self._get_cam_anchors(layer_data, to_scene_coords)
            elif mechanism_type == "gear":
                anchor_positions = self._get_gear_anchors(layer_data, to_scene_coords)
            elif mechanism_type == "planetary_gear":
                anchor_positions = self._get_planetary_gear_anchors(layer_data, to_scene_coords)
            elif mechanism_type == "4_bar_linkage":
                anchor_positions = self._get_fourbar_anchors(layer_data, to_scene_coords)

        except Exception:
            logging.debug("Suppressed exception", exc_info=True)  # Return empty dict on error

        return anchor_positions

    def _get_cam_anchors(
        self,
        layer_data: dict[str, Any],
        to_scene_coords: Callable[[np.ndarray], QPointF] | None,
    ) -> dict[str, QPointF]:
        """Calculate anchor positions for CAM mechanism."""
        anchor_positions: dict[str, QPointF] = {}
        params = layer_data.get("params", {})
        base_radius = params.get("base_radius", 25.0)
        eccentricity = params.get("eccentricity", 10.0)
        rod_length = params.get("follower_rod_length", 40.0)

        # Use stored transform function if available
        if "cam_transform_function" in layer_data:
            cam_to_scene_coords = layer_data["cam_transform_function"]
        elif to_scene_coords:
            cam_to_scene_coords = to_scene_coords
        else:
            # Fallback transform
            def cam_to_scene_coords(p_orig: np.ndarray) -> QPointF:
                return QPointF(float(p_orig[0] * 2 + 300), float(p_orig[1] * 2 + 300))

        # Calculate handle positions
        rod_handle_orig = np.array([0.0, -(base_radius + rod_length)])
        size_handle_orig = np.array([base_radius + eccentricity, 0.0])
        center_orig = np.array([0.0, 0.0])

        # Transform to scene coordinates
        cam_center = cam_to_scene_coords(center_orig)
        cam_follower = cam_to_scene_coords(rod_handle_orig)
        anchor_positions["cam_center"] = cam_center
        anchor_positions["center"] = cam_center
        anchor_positions["cam_follower"] = cam_follower
        anchor_positions["follower"] = cam_follower
        anchor_positions["cam_rod_length"] = cam_to_scene_coords(rod_handle_orig)
        anchor_positions["cam_size"] = cam_to_scene_coords(size_handle_orig)

        return anchor_positions

    def _get_gear_anchors(
        self,
        layer_data: dict[str, Any],
        to_scene_coords: Callable[[np.ndarray], QPointF] | None,
    ) -> dict[str, QPointF]:
        """Calculate anchor positions for gear mechanism."""
        anchor_positions: dict[str, QPointF] = {}
        visual_items = layer_data.get("visual_items", [])

        # First try to get positions from actual visual items
        if visual_items:
            gear_circles = [item for item in visual_items if isinstance(item, QGraphicsEllipseItem)]

            if len(gear_circles) >= 2:
                g1_center = gear_circles[0].scenePos() + gear_circles[0].rect().center()
                g2_center = gear_circles[1].scenePos() + gear_circles[1].rect().center()
                r1 = gear_circles[0].rect().width() * 0.5
                r2 = gear_circles[1].rect().width() * 0.5
                anchor_positions["gear1_center"] = g1_center
                anchor_positions["gear2_center"] = g2_center
                anchor_positions["gear1_radius"] = QPointF(g1_center.x() + r1, g1_center.y())
                anchor_positions["gear2_radius"] = QPointF(g2_center.x() + r2, g2_center.y())
                return anchor_positions

        # Fallback to calculation
        params = layer_data.get("params", {})
        r1 = params.get("r1", 30)
        r2 = params.get("r2", 50)
        distance = r1 + r2

        gear1_center_orig = np.array([0, 0])
        gear2_center_orig = np.array([distance, 0])

        # Check for stored positions
        key_points = layer_data.get("key_points", {})
        if "gear1_center" in key_points:
            gear1_center_orig = np.array(key_points["gear1_center"])
        if "gear2_center" in key_points:
            gear2_center_orig = np.array(key_points["gear2_center"])

        if to_scene_coords:
            g1_center = to_scene_coords(gear1_center_orig)
            g2_center = to_scene_coords(gear2_center_orig)
            g1_edge = to_scene_coords(gear1_center_orig + np.array([r1, 0], dtype=float))
            g2_edge = to_scene_coords(gear2_center_orig + np.array([r2, 0], dtype=float))
            anchor_positions["gear1_center"] = g1_center
            anchor_positions["gear2_center"] = g2_center
            anchor_positions["gear1_radius"] = g1_edge
            anchor_positions["gear2_radius"] = g2_edge
        else:
            g1_center = QPointF(gear1_center_orig[0], gear1_center_orig[1])
            g2_center = QPointF(gear2_center_orig[0], gear2_center_orig[1])
            anchor_positions["gear1_center"] = g1_center
            anchor_positions["gear2_center"] = g2_center
            anchor_positions["gear1_radius"] = QPointF(g1_center.x() + r1, g1_center.y())
            anchor_positions["gear2_radius"] = QPointF(g2_center.x() + r2, g2_center.y())

        return anchor_positions

    def _get_planetary_gear_anchors(
        self,
        layer_data: dict[str, Any],
        to_scene_coords: Callable[[np.ndarray], QPointF] | None,
    ) -> dict[str, QPointF]:
        """Calculate anchor positions for planetary gear mechanism."""
        anchor_positions: dict[str, QPointF] = {}
        visual_items = layer_data.get("visual_items", [])
        params = layer_data.get("params", {})
        r_sun = float(params.get("r_sun", params.get("gear1_radius", 20.0)))
        r_planet = float(params.get("r_planet", params.get("gear2_radius", 30.0)))
        arm_length = float(params.get("arm_length", 15.0))

        sun_center_scene: QPointF | None = None
        planet_center_scene: QPointF | None = None
        tracking_scene: QPointF | None = None

        # First try to get positions from actual visual items
        if visual_items:
            gear_circles = [item for item in visual_items if isinstance(item, QGraphicsEllipseItem)]

            if len(gear_circles) >= 2:
                sun_center_scene = gear_circles[0].scenePos() + gear_circles[0].rect().center()
                planet_center_scene = gear_circles[1].scenePos() + gear_circles[1].rect().center()
                if len(gear_circles) >= 3:
                    tracking_scene = gear_circles[2].scenePos() + gear_circles[2].rect().center()

        if sun_center_scene is None or planet_center_scene is None:
            # Fallback to simulation/key_points/params
            full_sim_data = layer_data.get("full_simulation_data", {})
            gear_positions = full_sim_data.get("gear_positions", {})
            key_points = layer_data.get("key_points", {})

            if gear_positions and "sun_centers" in gear_positions:
                sun_center_orig = np.array(gear_positions["sun_centers"][0], dtype=float)
                planet_center_orig = np.array(gear_positions["planet_centers"][0], dtype=float)
                tracking_orig = None
                if "tracking_points" in gear_positions and gear_positions["tracking_points"]:
                    tracking_orig = np.array(gear_positions["tracking_points"][0], dtype=float)

                if to_scene_coords:
                    sun_center_scene = to_scene_coords(sun_center_orig)
                    planet_center_scene = to_scene_coords(planet_center_orig)
                    if tracking_orig is not None:
                        tracking_scene = to_scene_coords(tracking_orig)
                else:
                    sun_center_scene = QPointF(float(sun_center_orig[0]), float(sun_center_orig[1]))
                    planet_center_scene = QPointF(float(planet_center_orig[0]), float(planet_center_orig[1]))
                    if tracking_orig is not None:
                        tracking_scene = QPointF(float(tracking_orig[0]), float(tracking_orig[1]))
            elif "sun_center" in key_points:
                sun_raw = np.array(key_points["sun_center"], dtype=float)
                planet_raw = key_points.get("planet_center")
                if isinstance(planet_raw, (list, tuple, np.ndarray)) and len(planet_raw) >= 2:
                    planet_raw_arr = np.array(planet_raw, dtype=float)
                else:
                    planet_raw_arr = sun_raw + (r_sun + r_planet) * np.array([1.0, 0.0], dtype=float)

                if to_scene_coords:
                    sun_center_scene = to_scene_coords(sun_raw)
                    planet_center_scene = to_scene_coords(planet_raw_arr)
                else:
                    sun_center_scene = QPointF(float(sun_raw[0]), float(sun_raw[1]))
                    planet_center_scene = QPointF(float(planet_raw_arr[0]), float(planet_raw_arr[1]))
            else:
                # Params are maintained in scene space by parametric editor flows.
                if "sun_x" in params and "sun_y" in params:
                    sx = float(params.get("sun_x", 0.0))
                    sy = float(params.get("sun_y", 0.0))
                elif "gear1_x" in params and "gear1_y" in params:
                    sx = float(params.get("gear1_x", 0.0))
                    sy = float(params.get("gear1_y", 0.0))
                elif (
                    "m_sun_x" in params
                    and "m_sun_y" in params
                    and to_scene_coords is not None
                ):
                    sun_scene = to_scene_coords(
                        np.array([float(params["m_sun_x"]), float(params["m_sun_y"])], dtype=float)
                    )
                    sx = float(sun_scene.x())
                    sy = float(sun_scene.y())
                else:
                    sx = 0.0
                    sy = 0.0
                px = float(params.get("planet_x", params.get("gear2_x", sx + r_sun + r_planet)))
                py = float(params.get("planet_y", params.get("gear2_y", sy)))
                sun_center_scene = QPointF(sx, sy)
                planet_center_scene = QPointF(px, py)

        if sun_center_scene is None:
            sun_center_scene = QPointF(0.0, 0.0)
        if planet_center_scene is None:
            planet_center_scene = QPointF(sun_center_scene.x() + r_sun + r_planet, sun_center_scene.y())

        anchor_positions["sun_center"] = sun_center_scene
        anchor_positions["planet_center"] = planet_center_scene

        orbit_mech = max(1e-6, r_sun + r_planet)
        orbit_scene = np.hypot(
            planet_center_scene.x() - sun_center_scene.x(),
            planet_center_scene.y() - sun_center_scene.y(),
        )
        scene_scale = orbit_scene / orbit_mech if orbit_scene > 0 else 1.0

        planet_radius_scene = max(1.0, r_planet * scene_scale)
        anchor_positions["planet_radius"] = QPointF(
            planet_center_scene.x() + planet_radius_scene,
            planet_center_scene.y(),
        )
        if tracking_scene is None:
            tracking_scene = QPointF(
                planet_center_scene.x() + arm_length * scene_scale,
                planet_center_scene.y(),
            )
        anchor_positions["arm_length"] = tracking_scene
        anchor_positions["tracking_point"] = tracking_scene

        return anchor_positions

    def _get_fourbar_anchors(
        self,
        layer_data: dict[str, Any],
        to_scene_coords: Callable[[np.ndarray], QPointF] | None,
    ) -> dict[str, QPointF]:
        """Calculate anchor positions for 4-bar linkage mechanism."""
        anchor_positions: dict[str, QPointF] = {}
        visual_items = layer_data.get("visual_items", [])

        # First try to get positions from actual visual items
        if visual_items:
            pivot_items = [item for item in visual_items if isinstance(item, QGraphicsEllipseItem)]

            if len(pivot_items) >= 4:
                anchor_positions["ground_pivot_1"] = (
                    pivot_items[0].scenePos() + pivot_items[0].rect().center()
                )
                anchor_positions["ground_pivot_2"] = (
                    pivot_items[1].scenePos() + pivot_items[1].rect().center()
                )
                anchor_positions["crank_end"] = (
                    pivot_items[2].scenePos() + pivot_items[2].rect().center()
                )
                anchor_positions["rocker_end"] = (
                    pivot_items[3].scenePos() + pivot_items[3].rect().center()
                )
                return anchor_positions

        # Fallback to using transform and simulation data
        full_sim_data = layer_data.get("full_simulation_data", {})
        joint_positions = full_sim_data.get("joint_positions", {})

        required_keys = ["p1_positions", "p2_positions", "p3_positions", "p4_positions"]
        if all(key in joint_positions for key in required_keys):
            p1_pos = joint_positions["p1_positions"][0]
            p2_pos = joint_positions["p2_positions"][0]
            p3_pos = joint_positions["p3_positions"][0]
            p4_pos = joint_positions["p4_positions"][0]

            if to_scene_coords:
                if "ground_pivot_1" not in anchor_positions:
                    anchor_positions["ground_pivot_1"] = to_scene_coords(np.array(p1_pos))
                if "ground_pivot_2" not in anchor_positions:
                    anchor_positions["ground_pivot_2"] = to_scene_coords(np.array(p2_pos))
                if "crank_end" not in anchor_positions:
                    anchor_positions["crank_end"] = to_scene_coords(np.array(p3_pos))
                if "rocker_end" not in anchor_positions:
                    anchor_positions["rocker_end"] = to_scene_coords(np.array(p4_pos))

        # Create defaults if still missing
        if len(anchor_positions) < 2:
            scene_center = QPointF(400, 300)
            if "ground_pivot_1" not in anchor_positions:
                anchor_positions["ground_pivot_1"] = QPointF(scene_center.x() - 100, scene_center.y())
            if "ground_pivot_2" not in anchor_positions:
                anchor_positions["ground_pivot_2"] = QPointF(scene_center.x() + 100, scene_center.y())
            if "crank_end" not in anchor_positions:
                anchor_positions["crank_end"] = QPointF(scene_center.x() - 50, scene_center.y() - 80)
            if "rocker_end" not in anchor_positions:
                anchor_positions["rocker_end"] = QPointF(scene_center.x() + 50, scene_center.y() - 80)

        return anchor_positions
