"""
Mechanism Instantiation Service for creating and configuring mechanism layers.

Extracted from MechanismDesignTab as part of god class decomposition.
Handles mechanism type mapping, CAM positioning, and layer data creation.

Design Pattern: Factory (mechanism layer creation)
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import numpy as np
from PyQt6.QtGui import QPainterPath

from automataii.utils.paths import resolve_path

# Mapping from display names to internal mechanism types
MECHANISM_TYPE_MAPPING: dict[str, str] = {
    "4-Bar Linkage": "4_bar_linkage",
    "4-bar Coupler": "4_bar_linkage",
    "Cam & Follower": "cam",
    "Cam-Follower": "cam",
    "Gears (Simple Pair)": "gear",
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

    def map_mechanism_type(self, display_type: str) -> str:
        """
        Map display mechanism type to internal type.

        Args:
            display_type: Display name (e.g., "4-Bar Linkage")

        Returns:
            Internal type string (e.g., "4_bar_linkage")
        """
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
            pass

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
            pass

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
            pass
        return None

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
        internal_type = self.map_mechanism_type(mechanism_type_value)
        mechanism_id = self.generate_mechanism_id()

        # Create graphics data structure
        graphics_data = {
            "mechanism_id": mechanism_id,
            "mechanism_type": internal_type,
            "params": mechanism_data.get("parameters", {}),
            "transform_params": mechanism_data.get("transform_params"),
            "generated_path": target_path if target_path else QPainterPath(),
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
            self._configure_cam_layer(layer_data, graphics_data, target_path, fallback_position)

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
        internal_type = self.map_mechanism_type(mechanism_type_value)
        mechanism_id = self.generate_mechanism_id(short=True)

        raw_params = candidate_data.get("parameters", {})
        params = convert_params_fn(mechanism_type_value, raw_params) if convert_params_fn else raw_params

        layer_data = {
            "id": mechanism_id,
            "type": internal_type,
            "part_name": selected_part_name,
            "params": params,
            "visual_items": [],
            "generated_path": target_path,
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
            self._configure_cam_candidate(layer_data, target_path)

        return layer_data

    def _configure_cam_layer(
        self,
        layer_data: dict[str, Any],
        graphics_data: dict[str, Any],
        path: QPainterPath | None,
        fallback_position: list[float] | None,
    ) -> None:
        """Configure CAM-specific layer data from recommendation."""
        layer_data["cam_scale_factor"] = 1.0
        layer_data["rod_length_multiplier"] = 1.0

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
        """Configure CAM-specific layer data from candidate."""
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

        # Set template path
        template_path = self.get_cam_template_path()
        if template_path:
            layer_data["cam_template_svg_path"] = template_path
            layer_data["params"]["cam_template_svg_path"] = template_path

    def create_layer_data_from_foundry(
        self,
        mechanism_type: str,
        parameters: dict[str, float],
        pivot_point: tuple[float, float],
        part_name: str | None = None,
        scene_position: tuple[float, float] | None = None,
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
        params = self._map_foundry_params_to_internal(mechanism_type, parameters)

        # Default scene position if not provided
        pos = scene_position or (400.0, 300.0)

        layer_data: dict[str, Any] = {
            "id": mechanism_id,
            "type": internal_type,
            "part_name": part_name,
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
        }

        # Type-specific configuration
        if internal_type == "4_bar_linkage":
            layer_data["key_points"] = {
                "ground_pivot_1": [pos[0] - 50, pos[1]],
                "ground_pivot_2": [pos[0] + 50, pos[1]],
                "crank_end": [pos[0] - 50, pos[1] - 40],
                "rocker_end": [pos[0] + 50, pos[1] - 80],
            }

        elif internal_type == "cam":
            layer_data["cam_position"] = list(pos)
            layer_data["cam_scale_factor"] = 1.0
            layer_data["rod_length_multiplier"] = 1.0
            params["center_x"] = pos[0]
            params["center_y"] = pos[1]
            # Ensure harmonic parameters are present
            params.setdefault("cam_lobes", 1)
            params.setdefault("profile_harmonic", 0.3)

        elif internal_type == "gear":
            layer_data["key_points"] = {
                "gear1_center": [pos[0] - 60, pos[1]],
                "gear2_center": [pos[0] + 60, pos[1]],
            }

        return layer_data

    def _map_foundry_params_to_internal(
        self,
        foundry_type: str,
        foundry_params: dict[str, float],
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

        if foundry_type == "four_bar":
            # Map: ground_link -> l1, input_link -> l2, coupler_link -> l3, output_link -> l4
            params["l1"] = foundry_params.get("ground_link", 150.0)
            params["l2"] = foundry_params.get("input_link", 40.0)
            params["l3"] = foundry_params.get("coupler_link", 120.0)
            params["l4"] = foundry_params.get("output_link", 130.0)
            params["coupler_point_x"] = foundry_params.get("coupler_point_x", 60.0)
            params["coupler_point_y"] = foundry_params.get("coupler_point_y", 30.0)

        elif foundry_type == "cam_follower":
            # Map Foundry cam params to internal
            params["base_radius"] = foundry_params.get("cam_radius", 60.0)
            params["eccentricity"] = foundry_params.get("cam_offset", 20.0)
            params["follower_rod_length"] = foundry_params.get("follower_length", 100.0)
            params["cam_lobes"] = int(foundry_params.get("cam_lobes", 1))
            params["profile_harmonic"] = foundry_params.get("profile_harmonic", 0.3)

        elif foundry_type == "gear_train":
            params["gear1_teeth"] = int(foundry_params.get("gear1_teeth", 12))
            params["gear2_teeth"] = int(foundry_params.get("gear2_teeth", 18))
            params["r1"] = foundry_params.get("gear1_teeth", 12) * 3  # tooth * module
            params["r2"] = foundry_params.get("gear2_teeth", 18) * 3

        else:
            # Copy params as-is for unknown types
            params = dict(foundry_params)

        return params
