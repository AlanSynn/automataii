"""
Mechanism Instantiation Service for creating and configuring mechanism layers.

Extracted from MechanismDesignTab as part of god class decomposition.
Handles mechanism type mapping, CAM positioning, and layer data creation.

Design Pattern: Factory (mechanism layer creation)
"""
from __future__ import annotations

import logging
import math
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from PyQt6.QtGui import QPainterPath

from automataii.utils.paths import resolve_path

# Mapping from display names to internal mechanism types
MECHANISM_TYPE_MAPPING: dict[str, str] = {
    # Four-bar linkage variants
    "4-Bar Linkage": "4_bar_linkage",
    "4-bar Coupler": "4_bar_linkage",
    "Four-Bar Linkage": "4_bar_linkage",
    "Four-Bar": "4_bar_linkage",
    "3-bar Output": "4_bar_linkage",
    # Cam mechanism variants
    "Cam & Follower": "cam",
    "Cam-Follower": "cam",
    "Cam Profile": "cam",
    "Cam": "cam",
    # Gear mechanism variants
    "Gears": "gear",  # Family name from recommendation dialog
    "Gears (Simple Pair)": "gear",
    "Gear Train": "gear",
    "Gear Contact": "gear",
    "Simple Gear": "gear",
    "Planetary Gear": "planetary_gear",
}


class MechanismInstantiationService:
    """
    Service for creating and configuring mechanism layer data.

    Responsibilities:
    - Map mechanism display names to internal types
    - Calculate CAM positioning from path bounds
    - Create layer data structures
    - Handle parameter normalization

    Time Complexity: O(n) where n is path points for CAM calculations
    """

    def __init__(self) -> None:
        """Initialize service."""
        self._qpainterpath_to_numpy: Any = None

    def set_path_converter(self, converter: Any) -> None:
        """Set the QPainterPath to numpy converter function."""
        self._qpainterpath_to_numpy = converter

    def map_mechanism_type(self, display_type: str, original_json_type: str | None = None) -> str:
        """
        Map display mechanism type to internal type.

        Args:
            display_type: Display name (e.g., "4-Bar Linkage", "Gears")
            original_json_type: Original specific type from recommendation (e.g., "Planetary Gear")

        Returns:
            Internal type string (e.g., "4_bar_linkage", "gear", "planetary_gear")
        """
        # First try original_json_type for more specific mapping (e.g., Planetary Gear)
        if original_json_type:
            mapped = MECHANISM_TYPE_MAPPING.get(original_json_type)
            if mapped:
                return mapped
        # Fall back to display type mapping
        return MECHANISM_TYPE_MAPPING.get(display_type, "4_bar_linkage")

    def generate_mechanism_id(self, short: bool = False) -> str:
        """
        Generate a unique mechanism ID.

        Args:
            short: If True, return shortened 8-char ID

        Returns:
            UUID string (full or shortened)
        """
        full_id = str(uuid.uuid4())
        return full_id[:8] if short else full_id

    def calculate_cam_position_from_path(
        self,
        path: QPainterPath | None,
        fallback_position: list[float] | None = None,
    ) -> tuple[list[float], dict[str, float]]:
        """
        Calculate CAM center position from path bounds.

        Places CAM directly below the path's lowest point.

        Args:
            path: QPainterPath to analyze
            fallback_position: Position to use if path analysis fails

        Returns:
            Tuple of (cam_position, params_update) where params_update
            contains center_x and center_y
        """
        default_pos = fallback_position or [400.0, 300.0]

        if not path or path.isEmpty():
            return default_pos, {"center_x": default_pos[0], "center_y": default_pos[1]}

        try:
            if self._qpainterpath_to_numpy:
                path_np = self._qpainterpath_to_numpy(path)
                if path_np is not None and len(path_np) > 0:
                    # Get X center and lowest Y point
                    path_x_center = float(np.mean(path_np[:, 0]))
                    path_y_max = float(np.max(path_np[:, 1]))

                    # Place CAM below path
                    cam_pos = [path_x_center, path_y_max + 80]
                    return cam_pos, {"center_x": cam_pos[0], "center_y": cam_pos[1]}
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        return default_pos, {"center_x": default_pos[0], "center_y": default_pos[1]}

    def calculate_cam_eccentricity_from_path(
        self,
        path: QPainterPath | None,
    ) -> dict[str, float]:
        """
        Calculate CAM eccentricity and base_radius from path lift.

        Args:
            path: QPainterPath to analyze

        Returns:
            Dict with eccentricity and base_radius parameters
        """
        if not path or path.isEmpty():
            return {}

        try:
            if self._qpainterpath_to_numpy:
                path_np = self._qpainterpath_to_numpy(path)
                if path_np is not None and len(path_np) > 0:
                    # Compute total lift from target path
                    path_y_min = float(np.min(path_np[:, 1]))
                    path_y_max = float(np.max(path_np[:, 1]))
                    total_lift_screen = path_y_max - path_y_min

                    # Calculate user_scale for normalization
                    x_min, y_min = float(np.min(path_np[:, 0])), float(np.min(path_np[:, 1]))
                    x_max, y_max = float(np.max(path_np[:, 0])), float(np.max(path_np[:, 1]))
                    user_bbox_w = x_max - x_min
                    user_bbox_h = y_max - y_min
                    user_scale = max(user_bbox_w, user_bbox_h) / 2.0 if max(user_bbox_w, user_bbox_h) > 0 else 1.0

                    # Normalize eccentricity
                    ecc_norm = total_lift_screen / user_scale if user_scale > 0 else total_lift_screen

                    return {
                        "eccentricity": max(1e-6, ecc_norm),
                        "base_radius": 0.3 * ecc_norm,
                    }
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        return {}

    def get_cam_template_path(self) -> str | None:
        """
        Get the default CAM template SVG path.

        Returns:
            Path string to template SVG or None if not found
        """
        try:
            template_rel = Path("resources/blueprints/tom/pear_cam_4.3in.svg")
            template_path = resolve_path(template_rel)
            if template_path.exists():
                return str(template_path)
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)
        return None

    def calculate_cam_scale_factor(
        self,
        path: QPainterPath | None,
        base_radius: float,
        eccentricity: float,
    ) -> float:
        """
        Calculate CAM scale factor based on user's path dimensions.

        Scales the cam so its visual size is proportional to the path height.
        The follower motion range (eccentricity) should match the path height,
        while keeping the overall cam visually appropriate.

        Args:
            path: User-drawn path to match
            base_radius: Cam base radius
            eccentricity: Cam eccentricity (lift height)

        Returns:
            Scale factor (clamped to 0.3 - 3.0 range)
        """
        if not path or path.isEmpty():
            return 1.0

        try:
            if self._qpainterpath_to_numpy:
                path_np = self._qpainterpath_to_numpy(path)
                if path_np is not None and len(path_np) > 0:
                    # Get path height (vertical motion range)
                    path_y_min = float(np.min(path_np[:, 1]))
                    path_y_max = float(np.max(path_np[:, 1]))
                    path_height = abs(path_y_max - path_y_min)

                    # Calculate cam's total visual height
                    # Cam max radius = base_radius + eccentricity
                    # Visual height ≈ 2 * (base_radius + eccentricity)
                    cam_visual_height = 2.0 * (base_radius + eccentricity)

                    if cam_visual_height > 1e-6 and path_height > 1e-6:
                        # Scale so cam visual height roughly matches path height
                        # Use a factor to keep cam reasonably sized relative to motion
                        scale_factor = path_height / cam_visual_height
                        # Clamp to reasonable range (more conservative)
                        return float(np.clip(scale_factor, 0.3, 3.0))

        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        return 1.0

    def calculate_cam_params_for_vertical_path(
        self,
        path: QPainterPath | None,
    ) -> dict[str, Any]:
        """
        Auto-calculate cam parameters for a nearly vertical path.

        For paths that are predominantly vertical (height > 2x width), generates
        cam parameters that match the vertical oscillation:
        - eccentricity = path_height / 2 (cam lift matches half the path range)
        - base_radius = eccentricity * 0.6 (reasonable cam size)
        - rod_length calculated to position cam below the path
        - cam_position at path bottom

        Args:
            path: User-drawn path to analyze

        Returns:
            Dictionary with auto-generated cam parameters, or empty dict if not vertical

        Time Complexity: O(n) where n is path points
        """
        if not path or path.isEmpty():
            return {}

        try:
            if not self._qpainterpath_to_numpy:
                return {}

            path_np = self._qpainterpath_to_numpy(path)
            if path_np is None or len(path_np) < 2:
                return {}

            # Calculate path bounds
            x_min, x_max = float(np.min(path_np[:, 0])), float(np.max(path_np[:, 0]))
            y_min, y_max = float(np.min(path_np[:, 1])), float(np.max(path_np[:, 1]))
            path_width = abs(x_max - x_min)
            path_height = abs(y_max - y_min)

            # Check if path is predominantly vertical (height > 2x width)
            is_vertical = path_height > 2 * max(path_width, 1.0)

            if not is_vertical:
                # Not a vertical path - return empty to use default matching
                return {}

            # Calculate cam parameters for vertical oscillation
            # eccentricity determines the lift (oscillation range)
            eccentricity = path_height / 2.0  # Half of total vertical range

            # Base radius is proportional to eccentricity
            # Using golden ratio for aesthetics
            base_radius = eccentricity * 0.6

            # Rod length: determines where follower attaches relative to cam
            # Set rod length to match path height for proper positioning
            # Preset multipliers: short (0.8), medium (1.0), long (1.5)
            rod_length_preset = 1.0  # Medium preset
            rod_length = path_height * rod_length_preset

            # Cam position: center X at path center, Y below path bottom
            # Cam should be positioned so follower can reach the path
            path_center_x = (x_min + x_max) / 2.0
            cam_y = y_max + base_radius + eccentricity  # Below path bottom (y_max is bottom in Qt coords)

            # Rod length multiplier to scale rod independently
            rod_length_multiplier = 1.0

            return {
                "base_radius": base_radius,
                "eccentricity": eccentricity,
                "follower_rod_length": rod_length,
                "rod_length_multiplier": rod_length_multiplier,
                "cam_position": [path_center_x, cam_y],
                "center_x": path_center_x,
                "center_y": cam_y,
                "is_auto_generated": True,
                "path_height": path_height,
                "path_width": path_width,
            }

        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        return {}

    def create_layer_data_from_recommendation(
        self,
        mechanism_data: dict[str, Any],
        target_path: QPainterPath | None,
        fallback_position: list[float] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Create layer data and graphics data from recommendation dialog output.

        Args:
            mechanism_data: Raw mechanism data from recommendation
            target_path: User-drawn path for the part
            fallback_position: Fallback position for CAM

        Returns:
            Tuple of (layer_data, graphics_data)
        """
        mechanism_type_value = mechanism_data.get("type", "Unknown")
        original_json_type = mechanism_data.get("original_json_type")
        internal_type = self.map_mechanism_type(mechanism_type_value, original_json_type)
        mechanism_id = self.generate_mechanism_id()

        # IMPORTANT: Always prefer user_motion_path_local from the dialog over target_path from path_data.
        # The dialog stores the exact path the user drew for THIS mechanism recommendation.
        # The path_data might contain a STALE path from a previous interaction.
        effective_target_path = mechanism_data.get("user_motion_path_local") or target_path
        if effective_target_path is None:
            effective_target_path = QPainterPath()

        # Create graphics data structure
        graphics_data = {
            "mechanism_id": mechanism_id,
            "mechanism_type": internal_type,
            "params": mechanism_data.get("parameters", {}),
            "transform_params": mechanism_data.get("transform_params"),
            "generated_path": effective_target_path,
            "visualization_params": mechanism_data.get("visualization_params"),
            "full_simulation_data": mechanism_data.get("full_simulation_data", {}),
            "key_points": mechanism_data.get("key_points", {}),
            "name": mechanism_data.get("name", f"{mechanism_type_value} Mechanism"),
            "type": mechanism_type_value,
        }

        # Create layer data structure
        layer_data = {
            "id": mechanism_id,
            "name": graphics_data["name"],
            "type": internal_type,
            "params": graphics_data["params"].copy() if graphics_data["params"] else {},
            "transform_params": graphics_data["transform_params"],
            "generated_path": graphics_data["generated_path"],
            "visualization_params": graphics_data["visualization_params"],
            "full_simulation_data": graphics_data["full_simulation_data"],
            "key_points": graphics_data["key_points"],
            "visual_items": [],
        }

        # Apply CAM-specific configuration
        if internal_type == "cam":
            self._configure_cam_layer(layer_data, graphics_data, effective_target_path, fallback_position)

        return layer_data, graphics_data

    def create_layer_data_from_candidate(
        self,
        candidate_data: dict[str, Any],
        selected_part_name: str,
        target_path: QPainterPath | None,
        convert_params_fn: Any,
        extract_key_points_fn: Any,
    ) -> dict[str, Any]:
        """
        Create layer data from mechanism candidate.

        Args:
            candidate_data: Candidate data from recommendation
            selected_part_name: Name of the selected part
            target_path: User-drawn path for the part
            convert_params_fn: Function to convert JSON params to internal format
            extract_key_points_fn: Function to extract key points from simulation

        Returns:
            Layer data dictionary
        """
        mechanism_type_value = candidate_data.get("type", "Unknown")
        original_json_type = candidate_data.get("original_json_type")
        internal_type = self.map_mechanism_type(mechanism_type_value, original_json_type)
        mechanism_id = self.generate_mechanism_id(short=True)

        raw_params = candidate_data.get("parameters", {})
        params = convert_params_fn(mechanism_type_value, raw_params) if convert_params_fn else raw_params

        # IMPORTANT: Always prefer user_motion_path_local from the dialog over target_path from path_data.
        # The dialog stores the exact path the user drew for THIS mechanism recommendation.
        # The path_data might contain a STALE path from a previous interaction.
        # This ensures the mechanism is placed at the correct location matching the recommendation preview.
        user_path_local = candidate_data.get("user_motion_path_local")
        effective_target_path = user_path_local or target_path  # Dialog path takes priority!

        layer_data = {
            "id": mechanism_id,
            "type": internal_type,
            "part_name": selected_part_name,
            "params": params,
            "visual_items": [],
            "generated_path": effective_target_path,
            "transform_params": candidate_data.get("transform_params"),
            "visualization_params": candidate_data.get("visualization_params"),
            "key_points": candidate_data.get("key_points"),
            "original_json_type": candidate_data.get("original_json_type"),
            "path_normalization": candidate_data.get("path_normalization", {}),
            "full_simulation_data": candidate_data.get("full_simulation_data", {}),
            "reverse_direction": False,
        }

        # Generate key_points from simulation if missing
        if not layer_data.get("key_points") and layer_data.get("full_simulation_data"):
            if extract_key_points_fn:
                layer_data["key_points"] = extract_key_points_fn(
                    layer_data["full_simulation_data"], internal_type
                )

        # Apply CAM-specific configuration
        if internal_type == "cam":
            self._configure_cam_candidate(layer_data, effective_target_path)

        return layer_data

    def _configure_cam_layer(
        self,
        layer_data: dict[str, Any],
        graphics_data: dict[str, Any],
        path: QPainterPath | None,
        fallback_position: list[float] | None,
    ) -> None:
        """Configure CAM-specific layer data from recommendation.

        For vertical paths (height > 2x width), auto-generates cam parameters:
        - eccentricity matches half the path height (vertical oscillation)
        - rod_length calculated for proper positioning
        - cam position placed below the path
        """
        # First, try auto-generation for vertical paths
        auto_params = self.calculate_cam_params_for_vertical_path(path)

        if auto_params:
            # Use auto-generated params for vertical path
            logging.debug("Auto-generating CAM params for vertical path: %s", auto_params)
            layer_data["params"]["base_radius"] = auto_params["base_radius"]
            layer_data["params"]["eccentricity"] = auto_params["eccentricity"]
            layer_data["params"]["follower_rod_length"] = auto_params["follower_rod_length"]
            layer_data["params"]["center_x"] = auto_params["center_x"]
            layer_data["params"]["center_y"] = auto_params["center_y"]
            layer_data["cam_position"] = auto_params["cam_position"]
            layer_data["cam_scale_factor"] = 1.0  # No scaling needed for auto-generated
            layer_data["rod_length_multiplier"] = auto_params["rod_length_multiplier"]
            layer_data["is_auto_generated_cam"] = True
        else:
            # Standard cam configuration for non-vertical paths
            params = layer_data.get("params", {})
            base_radius = float(params.get("base_radius", 40.0))
            eccentricity = float(params.get("eccentricity", 20.0))

            # Calculate scale factor based on user's path dimensions
            cam_scale_factor = self.calculate_cam_scale_factor(path, base_radius, eccentricity)
            layer_data["cam_scale_factor"] = cam_scale_factor
            layer_data["rod_length_multiplier"] = cam_scale_factor  # Scale rod proportionally

            cam_pos, params_update = self.calculate_cam_position_from_path(path, fallback_position)
            layer_data["cam_position"] = cam_pos
            layer_data["params"].update(params_update)

        if not graphics_data.get("transform_params"):
            graphics_data["transform_params"] = {
                "center": [0, 0],
                "scale": 1.0,
                "rotation": 0,
            }

    def _configure_cam_candidate(
        self,
        layer_data: dict[str, Any],
        path: QPainterPath | None,
    ) -> None:
        """Configure CAM-specific layer data from candidate.

        For vertical paths (height > 2x width), auto-generates cam parameters.
        """
        # First, try auto-generation for vertical paths
        auto_params = self.calculate_cam_params_for_vertical_path(path)

        if auto_params:
            # Use auto-generated params for vertical path
            logging.debug("Auto-generating CAM params for vertical path (candidate): %s", auto_params)
            layer_data["params"]["base_radius"] = auto_params["base_radius"]
            layer_data["params"]["eccentricity"] = auto_params["eccentricity"]
            layer_data["params"]["follower_rod_length"] = auto_params["follower_rod_length"]
            layer_data["params"]["center_x"] = auto_params["center_x"]
            layer_data["params"]["center_y"] = auto_params["center_y"]
            layer_data["cam_position"] = auto_params["cam_position"]
            layer_data["cam_scale_factor"] = 1.0
            layer_data["rod_length_multiplier"] = auto_params["rod_length_multiplier"]
            layer_data["is_auto_generated_cam"] = True
        else:
            # Standard cam configuration
            cam_pos, params_update = self.calculate_cam_position_from_path(path, [400, 300])
            layer_data["cam_position"] = cam_pos
            layer_data["params"].update(params_update)

            # Calculate eccentricity from path
            ecc_params = self.calculate_cam_eccentricity_from_path(path)
            if ecc_params:
                layer_data["params"]["eccentricity"] = ecc_params.get("eccentricity", layer_data["params"].get("eccentricity", 10))
                br = layer_data["params"].get("base_radius")
                ecc = ecc_params.get("eccentricity", 10)
                if br is None or br <= 0 or br > 3 * ecc:
                    layer_data["params"]["base_radius"] = ecc_params.get("base_radius", 0.3 * ecc)

            # Calculate scale factor based on user's path dimensions
            params = layer_data.get("params", {})
            base_radius = float(params.get("base_radius", 40.0))
            eccentricity = float(params.get("eccentricity", 20.0))
            cam_scale_factor = self.calculate_cam_scale_factor(path, base_radius, eccentricity)
            layer_data["cam_scale_factor"] = cam_scale_factor
            layer_data["rod_length_multiplier"] = cam_scale_factor  # Scale rod proportionally

        # Set template path
        template_path = self.get_cam_template_path()
        if template_path:
            layer_data["cam_template_svg_path"] = template_path
            layer_data["params"]["cam_template_svg_path"] = template_path

    def create_layer_data_from_foundry(
        self,
        mechanism_type: str,
        parameters: dict[str, Any],
        pivot_point: tuple[float, float],
        part_name: str | None = None,
        scene_position: tuple[float, float] | None = None,
        foundry_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create layer data from Mechanism Foundry export.

        Maps Foundry mechanism types to internal Design tab types and creates
        properly structured layer data for integration.

        Args:
            mechanism_type: Foundry mechanism type (e.g., "four_bar", "cam_follower")
            parameters: Mechanism parameters from Foundry
            pivot_point: Pivot point coordinates
            part_name: Optional part name to associate mechanism with
            scene_position: Optional scene position (defaults to center)

        Returns:
            Layer data dictionary ready for add_mechanism_layer
        """
        # Map Foundry type to internal type
        type_mapping = {
            "four_bar": "4_bar_linkage",
            "cam_follower": "cam",
            "gear_train": "gear",
            "slider_crank": "4_bar_linkage",  # Approximate with 4-bar for now
        }
        internal_type = type_mapping.get(mechanism_type, "4_bar_linkage")

        mechanism_id = self.generate_mechanism_id(short=True)

        # Map Foundry parameter names to internal parameter names
        params = self.map_foundry_params_to_internal(mechanism_type, parameters)
        normalized_part_name = (
            part_name.strip() if isinstance(part_name, str) and part_name.strip() else None
        )
        snapshot_positions = {}
        if isinstance(foundry_snapshot, dict):
            raw_positions = foundry_snapshot.get("positions")
            if isinstance(raw_positions, dict):
                snapshot_positions = raw_positions

        # Default scene position if not provided
        pos = scene_position or (400.0, 300.0)

        layer_data: dict[str, Any] = {
            "id": mechanism_id,
            "type": internal_type,
            "part_name": normalized_part_name,
            "params": params,
            "visual_items": [],
            "generated_path": None,
            "transform_params": {
                "center": list(pivot_point),
                "scale": 1.0,
                "rotation": 0,
            },
            "key_points": {},
            "full_simulation_data": {},
            "reverse_direction": False,
            "source": "foundry",
            "coordinate_space": "scene",
        }

        # Type-specific configuration
        if internal_type == "4_bar_linkage":
            o1 = self._snapshot_point(snapshot_positions, "O1")
            o4 = self._snapshot_point(snapshot_positions, "O4")
            a = self._snapshot_point(snapshot_positions, "A")
            b = self._snapshot_point(snapshot_positions, "B")
            coupler_point = self._snapshot_point(snapshot_positions, "coupler_point")
            dx = 0.0
            dy = 0.0

            if o1 and o4:
                center = ((o1[0] + o4[0]) * 0.5, (o1[1] + o4[1]) * 0.5)
                reference = coupler_point or center
                dx, dy = pos[0] - reference[0], pos[1] - reference[1]
                gp1 = (o1[0] + dx, o1[1] + dy)
                gp2 = (o4[0] + dx, o4[1] + dy)
                crank = (a[0] + dx, a[1] + dy) if a else None
                rocker = (b[0] + dx, b[1] + dy) if b else None
            else:
                l1 = float(params.get("l1", params.get("L1", 150.0)))
                l2 = float(params.get("l2", params.get("L2", 40.0)))
                l3 = float(params.get("l3", params.get("L3", 120.0)))
                l4 = float(params.get("l4", params.get("L4", 130.0)))
                input_angle = float(params.get("input_angle", params.get("crank_angle", 30.0)))
                theta = math.radians(input_angle)

                gp1 = (pos[0] - l1 * 0.5, pos[1])
                gp2 = (pos[0] + l1 * 0.5, pos[1])
                crank = (gp1[0] + l2 * math.cos(theta), gp1[1] + l2 * math.sin(theta))
                rocker = self._solve_circle_intersection(crank, l3, gp2, l4)
                if rocker is None:
                    rocker = (gp2[0], gp2[1] - l4)

            layer_data["key_points"] = {
                "ground_pivot_1": [gp1[0], gp1[1]],
                "ground_pivot_2": [gp2[0], gp2[1]],
                "crank_end": [crank[0], crank[1]] if crank else [gp1[0], gp1[1]],
                "rocker_end": [rocker[0], rocker[1]] if rocker else [gp2[0], gp2[1]],
            }

            gp1_arr = layer_data["key_points"]["ground_pivot_1"]
            gp2_arr = layer_data["key_points"]["ground_pivot_2"]
            crank_arr = layer_data["key_points"]["crank_end"]
            rocker_arr = layer_data["key_points"]["rocker_end"]
            l1 = math.hypot(gp2_arr[0] - gp1_arr[0], gp2_arr[1] - gp1_arr[1])
            l2 = math.hypot(crank_arr[0] - gp1_arr[0], crank_arr[1] - gp1_arr[1])
            l3 = math.hypot(rocker_arr[0] - crank_arr[0], rocker_arr[1] - crank_arr[1])
            l4 = math.hypot(rocker_arr[0] - gp2_arr[0], rocker_arr[1] - gp2_arr[1])
            params["l1"] = params["L1"] = float(l1)
            params["l2"] = params["L2"] = float(l2)
            params["l3"] = params["L3"] = float(l3)
            params["l4"] = params["L4"] = float(l4)
            params["ground_pivot_1"] = [gp1_arr[0], gp1_arr[1]]
            params["ground_pivot_2"] = [gp2_arr[0], gp2_arr[1]]

            if coupler_point and crank and rocker:
                coupler_world = (coupler_point[0] + dx, coupler_point[1] + dy)
                coupler_vec = (
                    rocker_arr[0] - crank_arr[0],
                    rocker_arr[1] - crank_arr[1],
                )
                coupler_len = math.hypot(coupler_vec[0], coupler_vec[1])
                if coupler_len > 1e-9:
                    coupler_unit = (
                        coupler_vec[0] / coupler_len,
                        coupler_vec[1] / coupler_len,
                    )
                    coupler_normal = (-coupler_unit[1], coupler_unit[0])
                    coupler_to_point = (
                        coupler_world[0] - crank_arr[0],
                        coupler_world[1] - crank_arr[1],
                    )
                    point_x = (
                        coupler_to_point[0] * coupler_unit[0]
                        + coupler_to_point[1] * coupler_unit[1]
                    )
                    point_y = (
                        coupler_to_point[0] * coupler_normal[0]
                        + coupler_to_point[1] * coupler_normal[1]
                    )
                    params["coupler_point_x"] = float(point_x)
                    params["coupler_point_y"] = float(point_y)
                    params["p_x"] = float(point_x)
                    params["p_y"] = float(point_y)

        elif internal_type == "cam":
            cam_center = self._snapshot_point(snapshot_positions, "cam_center")
            if cam_center:
                dx, dy = pos[0] - cam_center[0], pos[1] - cam_center[1]
                translated_center = (cam_center[0] + dx, cam_center[1] + dy)
                layer_data["cam_position"] = [translated_center[0], translated_center[1]]
                translated_key_points: dict[str, list[float]] = {}
                for key in ("cam_center", "follower_base", "follower_end", "contact_point"):
                    source = self._snapshot_point(snapshot_positions, key)
                    if source:
                        translated_key_points[key] = [source[0] + dx, source[1] + dy]
                if translated_key_points:
                    layer_data["key_points"] = translated_key_points
            else:
                layer_data["cam_position"] = list(pos)

            layer_data["cam_scale_factor"] = 1.0
            layer_data["rod_length_multiplier"] = 1.0
            params["center_x"] = layer_data["cam_position"][0]
            params["center_y"] = layer_data["cam_position"][1]
            # Ensure harmonic parameters are present
            params.setdefault("cam_lobes", 1)
            params.setdefault("profile_harmonic", 0.3)

        elif internal_type == "gear":
            r1 = float(params.get("gear1_radius", params.get("r1", 36.0)))
            r2 = float(params.get("gear2_radius", params.get("r2", 54.0)))
            center_distance = max(10.0, r1 + r2 + 2.0)
            layer_data["key_points"] = {
                "gear1_center": [pos[0] - center_distance / 2.0, pos[1]],
                "gear2_center": [pos[0] + center_distance / 2.0, pos[1]],
            }
            params.setdefault("gear1_x", float(layer_data["key_points"]["gear1_center"][0]))
            params.setdefault("gear1_y", float(layer_data["key_points"]["gear1_center"][1]))
            params.setdefault("gear2_x", float(layer_data["key_points"]["gear2_center"][0]))
            params.setdefault("gear2_y", float(layer_data["key_points"]["gear2_center"][1]))

        return layer_data

    @staticmethod
    def _snapshot_point(
        positions: dict[str, Any],
        key: str,
    ) -> tuple[float, float] | None:
        raw = positions.get(key)
        if isinstance(raw, list | tuple) and len(raw) >= 2:
            try:
                return (float(raw[0]), float(raw[1]))
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _solve_circle_intersection(
        p1: tuple[float, float],
        r1: float,
        p2: tuple[float, float],
        r2: float,
    ) -> tuple[float, float] | None:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        d = math.hypot(dx, dy)
        if d <= 1e-9 or d > (r1 + r2) or d < abs(r1 - r2):
            return None

        a = ((r1 * r1) - (r2 * r2) + (d * d)) / (2.0 * d)
        h_sq = (r1 * r1) - (a * a)
        if h_sq < 0.0:
            return None
        h = math.sqrt(h_sq)

        xm = p1[0] + (a * dx / d)
        ym = p1[1] + (a * dy / d)
        rx = -dy * (h / d)
        ry = dx * (h / d)
        return (xm + rx, ym + ry)

    def map_foundry_params_to_internal(
        self,
        foundry_type: str,
        foundry_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Public adapter for Foundry -> Design parameter mapping."""
        return self._map_foundry_params_to_internal(foundry_type, foundry_params)

    def _map_foundry_params_to_internal(
        self,
        foundry_type: str,
        foundry_params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Map Foundry parameter names to internal Design tab parameter names.

        Args:
            foundry_type: Foundry mechanism type
            foundry_params: Parameters from Foundry

        Returns:
            Parameters with internal naming convention
        """
        params: dict[str, Any] = {}

        normalized_type = {
            "fourbar": "four_bar",
            "4_bar_linkage": "four_bar",
            "cam": "cam_follower",
            "gear": "gear_train",
            "slidercrank": "slider_crank",
            "slider-crank": "slider_crank",
        }.get(foundry_type, foundry_type)

        if normalized_type == "four_bar":
            # Map: ground_link -> l1, input_link -> l2, coupler_link -> l3, output_link -> l4
            params["l1"] = foundry_params.get("ground_link", 150.0)
            params["l2"] = foundry_params.get("input_link", 40.0)
            params["l3"] = foundry_params.get("coupler_link", 120.0)
            params["l4"] = foundry_params.get("output_link", 130.0)
            params["coupler_point_x"] = foundry_params.get("coupler_point_x", 60.0)
            params["coupler_point_y"] = foundry_params.get("coupler_point_y", 30.0)
            if "input_angle" in foundry_params:
                angle = float(foundry_params["input_angle"])
                params["input_angle"] = angle
                params["crank_angle"] = angle
            output_mode = foundry_params.get("output_point_mode")
            if isinstance(output_mode, str):
                normalized_mode = output_mode.strip().lower()
                if normalized_mode in {"joint_a", "joint_b", "coupler", "coupler_point"}:
                    params["output_point_mode"] = (
                        "coupler" if normalized_mode == "coupler_point" else normalized_mode
                    )

        elif normalized_type == "cam_follower":
            # Map Foundry cam params to internal
            params["base_radius"] = foundry_params.get("cam_radius", 60.0)
            params["eccentricity"] = foundry_params.get("cam_offset", 20.0)
            params["follower_rod_length"] = foundry_params.get("follower_length", 100.0)
            params["cam_lobes"] = int(foundry_params.get("cam_lobes", 1))
            params["profile_harmonic"] = foundry_params.get("profile_harmonic", 0.3)
            if "input_angle" in foundry_params:
                params["input_angle"] = float(foundry_params["input_angle"])
            output_mode = foundry_params.get("output_point_mode")
            if isinstance(output_mode, str):
                normalized_mode = output_mode.strip().lower()
                if normalized_mode in {"follower_base", "follower_end"}:
                    params["output_point_mode"] = "follower_base"
                elif normalized_mode == "contact_point":
                    params["output_point_mode"] = "contact_point"

        elif normalized_type == "gear_train":
            params["gear1_teeth"] = int(foundry_params.get("gear1_teeth", 12))
            params["gear2_teeth"] = int(foundry_params.get("gear2_teeth", 18))
            params["r1"] = foundry_params.get("gear1_teeth", 12) * 3  # tooth * module
            params["r2"] = foundry_params.get("gear2_teeth", 18) * 3
            params["gear1_radius"] = float(params["r1"])
            params["gear2_radius"] = float(params["r2"])
            if "input_torque" in foundry_params:
                params["input_torque"] = float(foundry_params["input_torque"])
            if "input_angle" in foundry_params:
                params["input_angle"] = float(foundry_params["input_angle"])

        elif normalized_type == "slider_crank":
            # Approximate slider-crank with a 4-bar payload for current Design internals.
            crank_length = float(foundry_params.get("crank_length", 80.0))
            rod_length = float(foundry_params.get("rod_length", 140.0))

            params["l2"] = crank_length
            params["l3"] = rod_length
            params["l4"] = rod_length
            params["l1"] = max(1.0, crank_length + rod_length)
            params["coupler_point_x"] = rod_length * 0.5
            params["coupler_point_y"] = 0.0

            if "input_angle" in foundry_params:
                angle = float(foundry_params["input_angle"])
                params["input_angle"] = angle
                params["crank_angle"] = angle
            if "gas_pressure" in foundry_params:
                params["gas_pressure"] = float(foundry_params["gas_pressure"])

        else:
            # Copy params as-is for unknown types
            params = dict(foundry_params)

        return params
