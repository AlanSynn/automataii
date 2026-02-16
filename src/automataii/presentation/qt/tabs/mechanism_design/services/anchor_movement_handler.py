"""
Anchor Movement Handler for processing interactive anchor point changes.

Extracted from MechanismDesignTab as part of god class decomposition.
Handles parameter recalculation when anchor points are moved.

Design Pattern: Strategy (mechanism-specific parameter calculation)
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from PyQt6.QtCore import QPointF


class AnchorMovementHandler:
    """
    Handles anchor point movement and parameter recalculation.

    Responsibilities:
    - Find which mechanism owns a moved anchor
    - Update key_points with new positions
    - Recalculate mechanism parameters for each type
    - Trigger visual regeneration via callbacks

    Time Complexity: O(n*m) where n is mechanisms and m is key_points per mechanism
    """

    def __init__(self) -> None:
        """Initialize handler with empty callbacks."""
        self._on_params_updated: Callable[[str, dict[str, Any]], None] | None = None
        self._on_visuals_recreate: Callable[[str, dict[str, Any]], None] | None = None
        self._on_handles_update: Callable[[str, str], None] | None = None
        self._on_view_refresh: Callable[[], None] | None = None

    def configure_callbacks(
        self,
        on_params_updated: Callable[[str, dict[str, Any]], None] | None = None,
        on_visuals_recreate: Callable[[str, dict[str, Any]], None] | None = None,
        on_handles_update: Callable[[str, str], None] | None = None,
        on_view_refresh: Callable[[], None] | None = None,
    ) -> None:
        """
        Configure callback functions for post-movement actions.

        Args:
            on_params_updated: Called after parameters are recalculated
            on_visuals_recreate: Called to recreate mechanism visuals
            on_handles_update: Called to update other handles
            on_view_refresh: Called to refresh the view
        """
        self._on_params_updated = on_params_updated
        self._on_visuals_recreate = on_visuals_recreate
        self._on_handles_update = on_handles_update
        self._on_view_refresh = on_view_refresh

    def handle_anchor_moved(
        self,
        anchor_name: str,
        new_position: QPointF,
        mechanism_layers: dict[str, dict[str, Any]],
        inverse_transform_fn: Callable[[str], Callable[[QPointF], np.ndarray] | None],
        is_updating_programmatically: bool = False,
    ) -> bool:
        """
        Handle anchor point movement from interactive manipulation.

        Args:
            anchor_name: Name of anchor that was moved
            new_position: New position in scene coordinates
            mechanism_layers: Dictionary of mechanism layer data
            inverse_transform_fn: Function to get inverse transform for mechanism
            is_updating_programmatically: Skip if updating handles programmatically

        Returns:
            True if anchor was found and updated, False otherwise
        """
        if is_updating_programmatically:
            return False

        try:
            for mechanism_id, layer_data in mechanism_layers.items():
                key_points = layer_data.get("key_points", {})

                if anchor_name in key_points:
                    # Update anchor position in mechanism coordinates
                    to_mech = inverse_transform_fn(layer_data)
                    if to_mech:
                        mech_xy = to_mech(new_position)
                        key_points[anchor_name] = [float(mech_xy[0]), float(mech_xy[1])]
                    else:
                        key_points[anchor_name] = [new_position.x(), new_position.y()]

                    # Recalculate mechanism parameters
                    mech_type = layer_data.get("type")
                    params = layer_data.get("params", {})
                    self._recalculate_params(mech_type, key_points, params)

                    # Trigger callbacks
                    if self._on_params_updated:
                        self._on_params_updated(mechanism_id, layer_data)

                    if self._on_visuals_recreate:
                        self._on_visuals_recreate(mechanism_id, layer_data)

                    if self._on_handles_update:
                        self._on_handles_update(mechanism_id, anchor_name)

                    if self._on_view_refresh:
                        self._on_view_refresh()

                    return True

            return False

        except Exception:
            return False

    def _recalculate_params(
        self,
        mech_type: str | None,
        key_points: dict[str, list[float]],
        params: dict[str, Any],
    ) -> None:
        """
        Recalculate mechanism parameters based on updated key points.

        Args:
            mech_type: Type of mechanism
            key_points: Dictionary of anchor positions
            params: Parameters dictionary to update in-place
        """
        if mech_type == "4_bar_linkage":
            self._recalculate_4bar_params(key_points, params)
        elif mech_type == "5_bar_linkage":
            self._recalculate_5bar_params(key_points, params)
        elif mech_type == "6_bar_linkage":
            self._recalculate_6bar_params(key_points, params)
        elif mech_type == "cam":
            self._recalculate_cam_params(key_points, params)
        elif mech_type == "gear":
            self._recalculate_gear_params(key_points, params)
        elif mech_type == "planetary_gear":
            self._recalculate_planetary_params(key_points, params)

    def _recalculate_4bar_params(
        self,
        key_points: dict[str, list[float]],
        params: dict[str, Any],
    ) -> None:
        """Recalculate 4-bar linkage parameters from key points."""
        required = ["ground_pivot_1", "ground_pivot_2", "crank_end", "rocker_end"]
        if not all(k in key_points for k in required):
            return

        p1 = np.array(key_points["ground_pivot_1"])
        p2 = np.array(key_points["ground_pivot_2"])
        p3 = np.array(key_points["crank_end"])
        p4 = np.array(key_points["rocker_end"])

        # Calculate new link lengths
        params["L1"] = float(np.linalg.norm(p2 - p1))  # Ground link
        params["L2"] = float(np.linalg.norm(p3 - p1))  # Crank
        params["L3"] = float(np.linalg.norm(p4 - p3))  # Coupler
        params["L4"] = float(np.linalg.norm(p4 - p2))  # Rocker

        # Keep lowercase aliases synchronized for Foundry/export mapping.
        params["l1"] = float(params["L1"])
        params["l2"] = float(params["L2"])
        params["l3"] = float(params["L3"])
        params["l4"] = float(params["L4"])

        # Update ground pivot positions
        params["ground_pivot_1"] = key_points["ground_pivot_1"]
        params["ground_pivot_2"] = key_points["ground_pivot_2"]

    def _recalculate_5bar_params(
        self,
        key_points: dict[str, list[float]],
        params: dict[str, Any],
    ) -> None:
        """Recalculate 5-bar linkage parameters from key points."""
        if not all(k in key_points for k in ["ground_pivot_1", "ground_pivot_2"]):
            return

        params["ground_pivot_1"] = key_points["ground_pivot_1"]
        params["ground_pivot_2"] = key_points["ground_pivot_2"]

        # Update link lengths if intermediate joints available
        required_joints = ["joint_3", "joint_4", "joint_5"]
        if all(k in key_points for k in required_joints):
            p1 = np.array(key_points["ground_pivot_1"])
            p2 = np.array(key_points["ground_pivot_2"])
            p3 = np.array(key_points["joint_3"])
            p4 = np.array(key_points["joint_4"])
            p5 = np.array(key_points["joint_5"])

            params["L2"] = float(np.linalg.norm(p3 - p1))  # Input link
            params["L3"] = float(np.linalg.norm(p4 - p3))  # Coupler 1
            params["L4"] = float(np.linalg.norm(p5 - p4))  # Coupler 2
            params["L5"] = float(np.linalg.norm(p5 - p2))  # Output link

    def _recalculate_6bar_params(
        self,
        key_points: dict[str, list[float]],
        params: dict[str, Any],
    ) -> None:
        """Recalculate 6-bar linkage parameters from key points."""
        required = ["ground_pivot_1", "ground_pivot_2", "ground_pivot_3"]
        if not all(k in key_points for k in required):
            return

        params["ground_pivot_1"] = key_points["ground_pivot_1"]
        params["ground_pivot_2"] = key_points["ground_pivot_2"]
        params["ground_pivot_3"] = key_points["ground_pivot_3"]

        # Update link lengths if intermediate joints available
        required_joints = ["joint_3", "joint_4", "joint_5"]
        if all(k in key_points for k in required_joints):
            p1 = np.array(key_points["ground_pivot_1"])
            p2 = np.array(key_points["ground_pivot_2"])
            p3 = np.array(key_points["joint_3"])
            p4 = np.array(key_points["joint_4"])
            p5 = np.array(key_points["joint_5"])
            p6 = np.array(key_points["ground_pivot_3"])

            params["L2"] = float(np.linalg.norm(p3 - p1))
            params["L3"] = float(np.linalg.norm(p4 - p3))
            params["L4"] = float(np.linalg.norm(p4 - p2))
            params["L5"] = float(np.linalg.norm(p5 - p4))
            params["L6"] = float(np.linalg.norm(p5 - p6))

    def _recalculate_cam_params(
        self,
        key_points: dict[str, list[float]],
        params: dict[str, Any],
    ) -> None:
        """Recalculate cam mechanism parameters from key points."""
        if "cam_center" not in key_points:
            return

        cam_center = np.array(key_points["cam_center"])
        params["cam_center"] = key_points["cam_center"]

        # Update eccentricity if follower position available
        if "follower_base" in key_points:
            follower = np.array(key_points["follower_base"])
            distance = np.linalg.norm(follower - cam_center)
            params["base_radius"] = max(10, distance - 20)  # Maintain minimum radius

    def _recalculate_gear_params(
        self,
        key_points: dict[str, list[float]],
        params: dict[str, Any],
    ) -> None:
        """Recalculate gear parameters from key points."""
        if not all(k in key_points for k in ["gear1_center", "gear2_center"]):
            return

        g1 = np.array(key_points["gear1_center"])
        g2 = np.array(key_points["gear2_center"])
        distance = np.linalg.norm(g2 - g1)

        # Maintain gear ratio but adjust sizes to fit distance
        ratio = params.get("r2", 50) / params.get("r1", 30)
        params["r1"] = distance / (1 + ratio)
        params["r2"] = params["r1"] * ratio

    def _recalculate_planetary_params(
        self,
        key_points: dict[str, list[float]],
        params: dict[str, Any],
    ) -> None:
        """Recalculate planetary gear parameters from key points."""
        if "sun_center" not in key_points:
            return

        sun_center = np.array(key_points["sun_center"])
        params["sun_center"] = key_points["sun_center"]

        # Update radii if planet position available
        if "planet_center" in key_points:
            planet = np.array(key_points["planet_center"])
            orbital_radius = np.linalg.norm(planet - sun_center)

            # Maintain ratio but adjust sizes
            ratio = params.get("r_planet", 30) / params.get("r_sun", 20)
            params["r_sun"] = orbital_radius / (1 + ratio)
            params["r_planet"] = params["r_sun"] * ratio
