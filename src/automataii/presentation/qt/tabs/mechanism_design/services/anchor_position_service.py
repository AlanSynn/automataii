"""
Anchor Position Service for mechanism handle positioning.

Extracted from MechanismDesignTab as part of god class decomposition.
Calculates anchor positions for parametric handles across all mechanism types.

Design Pattern: Strategy (mechanism-specific position calculation)
"""
from __future__ import annotations

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
            pass  # Return empty dict on error

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

        # Transform to scene coordinates
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
                anchor_positions["gear1_center"] = (
                    gear_circles[0].scenePos() + gear_circles[0].rect().center()
                )
                anchor_positions["gear2_center"] = (
                    gear_circles[1].scenePos() + gear_circles[1].rect().center()
                )
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
            anchor_positions["gear1_center"] = to_scene_coords(gear1_center_orig)
            anchor_positions["gear2_center"] = to_scene_coords(gear2_center_orig)
        else:
            anchor_positions["gear1_center"] = QPointF(gear1_center_orig[0], gear1_center_orig[1])
            anchor_positions["gear2_center"] = QPointF(gear2_center_orig[0], gear2_center_orig[1])

        return anchor_positions

    def _get_planetary_gear_anchors(
        self,
        layer_data: dict[str, Any],
        to_scene_coords: Callable[[np.ndarray], QPointF] | None,
    ) -> dict[str, QPointF]:
        """Calculate anchor positions for planetary gear mechanism."""
        anchor_positions: dict[str, QPointF] = {}
        visual_items = layer_data.get("visual_items", [])

        # First try to get positions from actual visual items
        if visual_items:
            gear_circles = [item for item in visual_items if isinstance(item, QGraphicsEllipseItem)]

            if len(gear_circles) >= 2:
                anchor_positions["sun_center"] = (
                    gear_circles[0].scenePos() + gear_circles[0].rect().center()
                )
                anchor_positions["planet_center"] = (
                    gear_circles[1].scenePos() + gear_circles[1].rect().center()
                )
                return anchor_positions

        # Fallback to calculation
        params = layer_data.get("params", {})
        r_sun = params.get("r_sun", 20)
        r_planet = params.get("r_planet", 30)

        # Check for simulation data or key points
        full_sim_data = layer_data.get("full_simulation_data", {})
        gear_positions = full_sim_data.get("gear_positions", {})

        if gear_positions and "sun_centers" in gear_positions:
            sun_center_orig = np.array(gear_positions["sun_centers"][0])
            planet_center_orig = np.array(gear_positions["planet_centers"][0])
        else:
            sun_center_orig = np.array([0, 0])
            planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array([1, 0])

        if to_scene_coords:
            anchor_positions["sun_center"] = to_scene_coords(sun_center_orig)
            anchor_positions["planet_center"] = to_scene_coords(planet_center_orig)
        else:
            anchor_positions["sun_center"] = QPointF(sun_center_orig[0], sun_center_orig[1])
            anchor_positions["planet_center"] = QPointF(planet_center_orig[0], planet_center_orig[1])

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
