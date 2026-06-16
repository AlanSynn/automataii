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

from automataii.presentation.qt.tabs.cam_geometry import cam_contact_y_from_params
from automataii.presentation.qt.tabs.mechanism_design.services.foundry_scene_contract import (
    FOURBAR_ANCHOR_COUPLER_POINT,
    FOURBAR_ANCHOR_GROUND_MIDPOINT,
    mark_scene_space,
    sync_fourbar_scene_params_from_key_points,
)
from automataii.shared.physical_kit import (
    DEFAULT_GRID_CELL_CM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    GEAR_PRESETS,
    PhysicalKitContext,
    PhysicalKitProfile,
    freeform_gear_radius_for_teeth,
    gear_center_distance,
    gear_clearance_from_params,
    gear_radius_for_teeth,
    grid_cell_cm_from_params,
    grid_enabled_from_params,
    nearest_gear_teeth,
    physical_context_from_settings,
    physical_profile_from_params,
    snap_cam_params,
    snap_gear_params,
)
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


FOUNDRY_TO_DESIGN_TYPE_MAPPING: dict[str, str] = {
    "four_bar": "4_bar_linkage",
    "cam_follower": "cam",
    "gear_train": "gear",
    "gear_linkage": "gear",
    "slider_crank": "4_bar_linkage",  # Approximate with 4-bar for now
}

FOUNDRY_TYPE_ALIASES: dict[str, str] = {
    "fourbar": "four_bar",
    "four_bar_linkage": "four_bar",
    "4_bar_linkage": "four_bar",
    "cam": "cam_follower",
    "gear": "gear_train",
    "gear+linkage": "gear_linkage",
    "gear_linkage_train": "gear_linkage",
    "slider-crank": "slider_crank",
    "slidercrank": "slider_crank",
}


class UnsupportedMechanismTypeError(ValueError):
    """Raised when a mechanism factory receives an unsupported type."""


def _finite_float(value: Any, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _positive_finite_float(value: Any, default: float) -> float:
    result = _finite_float(value, default)
    return result if result > 0.0 else default


def _positive_int(value: Any, default: int, minimum: int = 1) -> int:
    if isinstance(value, bool):
        return default
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result >= minimum else default


def _bool_flag(value: Any, default: bool = False) -> bool:
    """Coerce common persisted/UI boolean payloads without treating junk as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "true", "yes", "y", "on", "reverse", "reversed"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", "forward"}:
            return False
        return default
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return bool(value)
    return default


def _finite_point(
    value: Any, default: tuple[float, float] | None = None
) -> tuple[float, float] | None:
    if not isinstance(value, list | tuple) or len(value) < 2:
        return default
    x = _finite_float(value[0], math.nan)
    y = _finite_float(value[1], math.nan)
    if not math.isfinite(x) or not math.isfinite(y):
        return default
    return x, y


def _finite_path_rows(raw: Any) -> np.ndarray | None:
    try:
        rows = np.asarray(raw, dtype=float)
    except (TypeError, ValueError):
        return None
    if rows.ndim != 2 or rows.shape[0] == 0 or rows.shape[1] < 2:
        return None
    rows = rows[:, :2]
    if not bool(np.isfinite(rows).all()):
        return None
    return rows


def _mapping_lookup(mapping: dict[str, str], value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    direct = mapping.get(stripped)
    if direct:
        return direct
    normalized = stripped.casefold()
    for key, mapped in mapping.items():
        if key.casefold() == normalized:
            return mapped
    return None


def _normalize_foundry_type(foundry_type: str) -> str:
    """Normalize Foundry type aliases while rejecting malformed type payloads."""
    if not isinstance(foundry_type, str) or not foundry_type.strip():
        raise UnsupportedMechanismTypeError(f"Unsupported Foundry mechanism type: {foundry_type}")

    foundry_type_key = foundry_type.strip().lower()
    return FOUNDRY_TYPE_ALIASES.get(foundry_type_key, foundry_type_key)


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
        self._physical_profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE
        self._grid_system_enabled = True
        self._grid_cell_cm = DEFAULT_GRID_CELL_CM
        self._grid_pitch_choice = physical_context_from_settings(
            True,
            DEFAULT_GRID_CELL_CM,
            profile=DEFAULT_PHYSICAL_KIT_PROFILE,
        ).grid_pitch_choice

    def set_path_converter(self, converter: Any) -> None:
        """Set the QPainterPath to numpy converter function."""
        self._qpainterpath_to_numpy = converter

    def set_physical_profile(self, profile: PhysicalKitProfile) -> None:
        """Set the active physical-kit profile for runtime snapping."""
        self._physical_profile = profile

    def set_physical_context(self, context: PhysicalKitContext) -> None:
        """Set the active grid/profile context for newly created layers."""
        self._grid_system_enabled = context.enabled
        self._grid_cell_cm = context.grid_cell_cm
        self._grid_pitch_choice = context.grid_pitch_choice
        self._physical_profile = context.profile

    def set_grid_system(
        self,
        enabled: bool,
        cell_cm: float,
        *,
        pitch_choice_key: str | None = None,
        profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
    ) -> None:
        """Set grid defaults used when recommendations omit physical-kit params."""
        self.set_physical_context(
            physical_context_from_settings(
                enabled,
                cell_cm,
                pitch_choice_key,
                profile=profile,
            )
        )

    def _profile_for_params(self, params: dict[str, Any]) -> PhysicalKitProfile:
        if "physical_profile_key" in params:
            return physical_profile_from_params(params)
        return self._physical_profile

    def _apply_physical_context_defaults(self, params: dict[str, Any]) -> dict[str, Any]:
        """Inject current grid/profile defaults without overriding explicit payload state."""
        params.setdefault("grid_system_enabled", self._grid_system_enabled)
        params.setdefault("grid_cell_cm", self._grid_cell_cm)
        params.setdefault("grid_pitch_choice", self._grid_pitch_choice)
        params.setdefault("physical_profile_key", self._physical_profile.key)
        params.setdefault("hole_diameter_mm", self._physical_profile.hole_diameter_mm)
        return params

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
        mapped = _mapping_lookup(MECHANISM_TYPE_MAPPING, original_json_type)
        if mapped:
            return mapped
        # Fall back to display type mapping
        mapped = _mapping_lookup(MECHANISM_TYPE_MAPPING, display_type)
        if mapped:
            return mapped
        raise UnsupportedMechanismTypeError(f"Unsupported mechanism type: {display_type}")

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
        params: dict[str, Any] | None = None,
        cam_scale_factor: float = 1.0,
    ) -> tuple[list[float], dict[str, float]]:
        """
        Calculate CAM center position from path bounds.

        Places the CAM so its follower/contact point uses the same scene-vertical
        contact convention as the visual factory.  When no CAM params are
        supplied, falls back to the legacy "below the path" placement.

        Args:
            path: QPainterPath to analyze
            fallback_position: Position to use if path analysis fails
            params: Optional CAM params for shared contact-height alignment
            cam_scale_factor: Scale factor applied to the CAM profile

        Returns:
            Tuple of (cam_position, params_update) where params_update
            contains center_x and center_y
        """
        fallback = _finite_point(fallback_position, (400.0, 300.0))
        default_pos = [fallback[0], fallback[1]] if fallback is not None else [400.0, 300.0]

        if not path or path.isEmpty():
            return default_pos, {"center_x": default_pos[0], "center_y": default_pos[1]}

        try:
            if self._qpainterpath_to_numpy:
                path_np = _finite_path_rows(self._qpainterpath_to_numpy(path))
                if path_np is not None:
                    # Match QPainterPath.boundingRect() semantics used by
                    # MechanismVisualsFactory: center X of bounds + bottom Y.
                    path_x_center = float((np.min(path_np[:, 0]) + np.max(path_np[:, 0])) * 0.5)
                    path_y_max = float(np.max(path_np[:, 1]))

                    contact_y: float | None = None
                    if isinstance(params, dict):
                        try:
                            scale = _positive_finite_float(cam_scale_factor, 1.0)
                            contact_y = cam_contact_y_from_params(params, scale=scale)
                            if not math.isfinite(contact_y):
                                contact_y = None
                        except Exception:
                            logging.debug("Suppressed exception", exc_info=True)
                            contact_y = None

                    if contact_y is None:
                        # Legacy fallback when we do not have enough CAM
                        # geometry to align the follower contact.
                        cam_y = path_y_max + 80.0
                    else:
                        cam_y = path_y_max - contact_y

                    cam_pos = [path_x_center, float(cam_y)]
                    return cam_pos, {"center_x": cam_pos[0], "center_y": cam_pos[1]}
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        return default_pos, {"center_x": default_pos[0], "center_y": default_pos[1]}

    @staticmethod
    def _sync_cam_center_aliases(
        layer_data: dict[str, Any],
        center: list[float] | tuple[float, float],
    ) -> None:
        """Keep all cam center aliases on the same scene-space point."""
        point = _finite_point(center, (400.0, 300.0))
        if point is None:
            point = (400.0, 300.0)
        center_list = [float(point[0]), float(point[1])]
        if not isinstance(layer_data.get("params"), dict):
            layer_data["params"] = {}
        if not isinstance(layer_data.get("key_points"), dict):
            layer_data["key_points"] = {}
        params = layer_data["params"]
        key_points = layer_data["key_points"]
        layer_data["cam_position"] = center_list
        params["center_x"] = center_list[0]
        params["center_y"] = center_list[1]
        params["cam_center"] = list(center_list)
        key_points["cam_center"] = list(center_list)

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
                path_np = _finite_path_rows(self._qpainterpath_to_numpy(path))
                if path_np is not None:
                    # Compute total lift from target path
                    path_y_min = float(np.min(path_np[:, 1]))
                    path_y_max = float(np.max(path_np[:, 1]))
                    total_lift_screen = path_y_max - path_y_min

                    # Calculate user_scale for normalization
                    x_min, y_min = float(np.min(path_np[:, 0])), float(np.min(path_np[:, 1]))
                    x_max, y_max = float(np.max(path_np[:, 0])), float(np.max(path_np[:, 1]))
                    user_bbox_w = x_max - x_min
                    user_bbox_h = y_max - y_min
                    user_scale = (
                        max(user_bbox_w, user_bbox_h) / 2.0
                        if max(user_bbox_w, user_bbox_h) > 0
                        else 1.0
                    )

                    # Normalize eccentricity
                    ecc_norm = (
                        total_lift_screen / user_scale if user_scale > 0 else total_lift_screen
                    )
                    ecc_norm = _positive_finite_float(ecc_norm, 1e-6)

                    return {
                        "eccentricity": ecc_norm,
                        "base_radius": max(1e-6, 0.3 * ecc_norm),
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
                path_np = _finite_path_rows(self._qpainterpath_to_numpy(path))
                if path_np is not None:
                    # Get path height (vertical motion range)
                    path_y_min = float(np.min(path_np[:, 1]))
                    path_y_max = float(np.max(path_np[:, 1]))
                    path_height = abs(path_y_max - path_y_min)

                    # Calculate cam's total visual height
                    # Cam max radius = base_radius + eccentricity
                    # Visual height ≈ 2 * (base_radius + eccentricity)
                    base_radius = _positive_finite_float(base_radius, 40.0)
                    eccentricity = _positive_finite_float(eccentricity, 20.0)
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

            path_np = _finite_path_rows(self._qpainterpath_to_numpy(path))
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
            cam_y = (
                y_max + base_radius + eccentricity
            )  # Below path bottom (y_max is bottom in Qt coords)

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
        raw_params = mechanism_data.get("parameters", {})
        raw_params = raw_params if isinstance(raw_params, dict) else {}
        params = raw_params.copy()
        self._apply_physical_context_defaults(params)
        reverse_direction = _bool_flag(
            mechanism_data.get(
                "reverse_direction",
                params.get("reverse_direction", raw_params.get("reverse_direction", False)),
            )
        )
        params["reverse_direction"] = reverse_direction

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
            "params": params,
            "transform_params": mechanism_data.get("transform_params"),
            "generated_path": effective_target_path,
            "visualization_params": mechanism_data.get("visualization_params"),
            "full_simulation_data": mechanism_data.get("full_simulation_data", {}),
            "key_points": mechanism_data.get("key_points", {}),
            "name": mechanism_data.get("name", f"{mechanism_type_value} Mechanism"),
            "type": mechanism_type_value,
            "reverse_direction": reverse_direction,
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
            "reverse_direction": reverse_direction,
        }

        # Apply CAM-specific configuration
        if internal_type == "cam":
            self._configure_cam_layer(
                layer_data, graphics_data, effective_target_path, fallback_position
            )
        elif internal_type == "gear" and grid_enabled_from_params(layer_data["params"]):
            profile = self._profile_for_params(layer_data["params"])
            layer_data["params"].update(snap_gear_params(layer_data["params"], profile=profile))

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
        raw_params = raw_params if isinstance(raw_params, dict) else {}
        params = (
            convert_params_fn(mechanism_type_value, raw_params) if convert_params_fn else raw_params
        )
        if not isinstance(params, dict):
            params = {}
        else:
            params = dict(params)
        self._apply_physical_context_defaults(params)
        reverse_direction = _bool_flag(
            candidate_data.get(
                "reverse_direction",
                params.get("reverse_direction", raw_params.get("reverse_direction", False)),
            )
        )
        params["reverse_direction"] = reverse_direction

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
            "reverse_direction": reverse_direction,
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
        elif internal_type == "gear" and grid_enabled_from_params(layer_data["params"]):
            profile = self._profile_for_params(layer_data["params"])
            layer_data["params"].update(snap_gear_params(layer_data["params"], profile=profile))

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
            if grid_enabled_from_params(layer_data["params"]):
                profile = self._profile_for_params(layer_data["params"])
                layer_data["params"].update(
                    snap_cam_params(
                        layer_data["params"],
                        grid_cell_cm_from_params(layer_data["params"]),
                        profile=profile,
                    )
                )
            layer_data["cam_scale_factor"] = 1.0  # No scaling needed for auto-generated
            layer_data["rod_length_multiplier"] = auto_params["rod_length_multiplier"]
            layer_data["is_auto_generated_cam"] = True
            cam_pos, params_update = self.calculate_cam_position_from_path(
                path,
                auto_params["cam_position"],
                params=layer_data["params"],
                cam_scale_factor=1.0,
            )
            layer_data["params"].update(params_update)
            self._sync_cam_center_aliases(layer_data, cam_pos)
        else:
            # Standard cam configuration for non-vertical paths
            params = layer_data.get("params", {})
            if grid_enabled_from_params(params):
                profile = self._profile_for_params(params)
                params.update(
                    snap_cam_params(
                        params,
                        grid_cell_cm_from_params(params),
                        profile=profile,
                    )
                )
            base_radius = _positive_finite_float(params.get("base_radius", 40.0), 40.0)
            eccentricity = _positive_finite_float(params.get("eccentricity", 20.0), 20.0)

            # Calculate scale factor based on user's path dimensions
            cam_scale_factor = self.calculate_cam_scale_factor(path, base_radius, eccentricity)
            layer_data["cam_scale_factor"] = cam_scale_factor
            layer_data["rod_length_multiplier"] = cam_scale_factor  # Scale rod proportionally

            cam_pos, params_update = self.calculate_cam_position_from_path(
                path,
                fallback_position,
                params=layer_data["params"],
                cam_scale_factor=cam_scale_factor,
            )
            layer_data["params"].update(params_update)
            self._sync_cam_center_aliases(layer_data, cam_pos)

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
            logging.debug(
                "Auto-generating CAM params for vertical path (candidate): %s", auto_params
            )
            layer_data["params"]["base_radius"] = auto_params["base_radius"]
            layer_data["params"]["eccentricity"] = auto_params["eccentricity"]
            layer_data["params"]["follower_rod_length"] = auto_params["follower_rod_length"]
            if grid_enabled_from_params(layer_data["params"]):
                profile = self._profile_for_params(layer_data["params"])
                layer_data["params"].update(
                    snap_cam_params(
                        layer_data["params"],
                        grid_cell_cm_from_params(layer_data["params"]),
                        profile=profile,
                    )
                )
            layer_data["cam_scale_factor"] = 1.0
            layer_data["rod_length_multiplier"] = auto_params["rod_length_multiplier"]
            layer_data["is_auto_generated_cam"] = True
            cam_pos, params_update = self.calculate_cam_position_from_path(
                path,
                auto_params["cam_position"],
                params=layer_data["params"],
                cam_scale_factor=1.0,
            )
            layer_data["params"].update(params_update)
            self._sync_cam_center_aliases(layer_data, cam_pos)
        else:
            # Standard cam configuration.  First derive lift/scale, then use
            # the same contact-height rule as visual rendering for placement.
            ecc_params = self.calculate_cam_eccentricity_from_path(path)
            if ecc_params:
                layer_data["params"]["eccentricity"] = ecc_params.get(
                    "eccentricity", layer_data["params"].get("eccentricity", 10)
                )
                br = _positive_finite_float(layer_data["params"].get("base_radius"), math.nan)
                ecc = _positive_finite_float(ecc_params.get("eccentricity", 10), 10.0)
                if not math.isfinite(br) or br > 3 * ecc:
                    layer_data["params"]["base_radius"] = ecc_params.get("base_radius", 0.3 * ecc)

            # Calculate scale factor based on user's path dimensions
            params = layer_data.get("params", {})
            if grid_enabled_from_params(params):
                profile = self._profile_for_params(params)
                params.update(
                    snap_cam_params(
                        params,
                        grid_cell_cm_from_params(params),
                        profile=profile,
                    )
                )
            base_radius = _positive_finite_float(params.get("base_radius", 40.0), 40.0)
            eccentricity = _positive_finite_float(params.get("eccentricity", 20.0), 20.0)
            cam_scale_factor = self.calculate_cam_scale_factor(path, base_radius, eccentricity)
            layer_data["cam_scale_factor"] = cam_scale_factor
            layer_data["rod_length_multiplier"] = cam_scale_factor  # Scale rod proportionally
            cam_pos, params_update = self.calculate_cam_position_from_path(
                path,
                [400, 300],
                params=layer_data["params"],
                cam_scale_factor=cam_scale_factor,
            )
            layer_data["params"].update(params_update)
            self._sync_cam_center_aliases(layer_data, cam_pos)

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
        canonical_foundry_type = _normalize_foundry_type(mechanism_type)

        # Map Foundry type to internal type. Unknown types must fail explicitly;
        # silently treating catalog drift as a 4-bar linkage hides factory bugs.
        try:
            internal_type = FOUNDRY_TO_DESIGN_TYPE_MAPPING[canonical_foundry_type]
        except KeyError as exc:
            raise UnsupportedMechanismTypeError(
                f"Unsupported Foundry mechanism type: {mechanism_type}"
            ) from exc

        mechanism_id = self.generate_mechanism_id(short=True)

        # Map Foundry parameter names to internal parameter names
        safe_parameters = parameters if isinstance(parameters, dict) else {}
        params = self.map_foundry_params_to_internal(canonical_foundry_type, safe_parameters)
        reverse_direction = _bool_flag(
            params.get("reverse_direction", safe_parameters.get("reverse_direction", False))
        )
        params["reverse_direction"] = reverse_direction
        normalized_part_name = (
            part_name.strip() if isinstance(part_name, str) and part_name.strip() else None
        )
        snapshot_positions = {}
        if isinstance(foundry_snapshot, dict):
            raw_positions = foundry_snapshot.get("positions")
            if isinstance(raw_positions, dict):
                snapshot_positions = raw_positions

        # Default scene position if not provided
        pos = _finite_point(scene_position, (400.0, 300.0))
        if pos is None:
            pos = (400.0, 300.0)
        pivot = _finite_point(pivot_point, (0.0, 0.0))
        if pivot is None:
            pivot = (0.0, 0.0)

        layer_data: dict[str, Any] = {
            "id": mechanism_id,
            "type": internal_type,
            "part_name": normalized_part_name,
            "params": params,
            "visual_items": [],
            "generated_path": None,
            "transform_params": {
                "center": list(pivot),
                "scale": 1.0,
                "rotation": 0,
            },
            "key_points": {},
            "full_simulation_data": {},
            "reverse_direction": reverse_direction,
            "source": "foundry",
            "source_type": canonical_foundry_type,
        }
        mark_scene_space(layer_data, pos)
        if canonical_foundry_type == "slider_crank":
            layer_data["approximated_as"] = internal_type

        # Type-specific configuration
        if internal_type == "4_bar_linkage":
            o1 = self._snapshot_point(snapshot_positions, "O1")
            o4 = self._snapshot_point(snapshot_positions, "O4")
            a = self._snapshot_point(snapshot_positions, "A")
            b = self._snapshot_point(snapshot_positions, "B")
            coupler_point = self._snapshot_point(snapshot_positions, "coupler_point")
            dx = 0.0
            dy = 0.0
            gp1: tuple[float, float]
            gp2: tuple[float, float]
            crank: tuple[float, float]
            rocker: tuple[float, float] | None

            if o1 is not None and o4 is not None and a is not None and b is not None:
                center = ((o1[0] + o4[0]) * 0.5, (o1[1] + o4[1]) * 0.5)
                reference = coupler_point or center
                dx, dy = pos[0] - reference[0], pos[1] - reference[1]
                gp1 = (o1[0] + dx, o1[1] + dy)
                gp2 = (o4[0] + dx, o4[1] + dy)
                crank = (a[0] + dx, a[1] + dy)
                rocker = (b[0] + dx, b[1] + dy)
            else:
                l1 = _positive_finite_float(params.get("l1", params.get("L1", 150.0)), 150.0)
                l2 = _positive_finite_float(params.get("l2", params.get("L2", 40.0)), 40.0)
                l3 = _positive_finite_float(params.get("l3", params.get("L3", 120.0)), 120.0)
                l4 = _positive_finite_float(params.get("l4", params.get("L4", 130.0)), 130.0)
                input_angle = _finite_float(
                    params.get("input_angle", params.get("crank_angle", 30.0)), 30.0
                )
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
            params["anchor1_x"] = float(gp1_arr[0])
            params["anchor1_y"] = float(gp1_arr[1])
            params["anchor2_x"] = float(gp2_arr[0])
            params["anchor2_y"] = float(gp2_arr[1])
            params["crank_x"] = float(crank_arr[0])
            params["crank_y"] = float(crank_arr[1])
            params["rocker_x"] = float(rocker_arr[0])
            params["rocker_y"] = float(rocker_arr[1])

            if coupler_point is not None and crank is not None and rocker is not None:
                layer_data["scene_anchor_key"] = FOURBAR_ANCHOR_COUPLER_POINT
                coupler_world = (coupler_point[0] + dx, coupler_point[1] + dy)
                layer_data["key_points"]["coupler_point"] = [
                    float(coupler_world[0]),
                    float(coupler_world[1]),
                ]
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
                    params["coupler_x"] = float(coupler_world[0])
                    params["coupler_y"] = float(coupler_world[1])
            else:
                layer_data["scene_anchor_key"] = FOURBAR_ANCHOR_GROUND_MIDPOINT
                coupler_x = _finite_float(
                    params.get("coupler_point_x", params.get("p_x", l3 * 0.5)), l3 * 0.5
                )
                coupler_y = _finite_float(
                    params.get("coupler_point_y", params.get("p_y", 0.0)), 0.0
                )
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
                    coupler_world = (
                        crank_arr[0] + coupler_x * coupler_unit[0] + coupler_y * coupler_normal[0],
                        crank_arr[1] + coupler_x * coupler_unit[1] + coupler_y * coupler_normal[1],
                    )
                    layer_data["key_points"]["coupler_point"] = [
                        float(coupler_world[0]),
                        float(coupler_world[1]),
                    ]
                    params["coupler_x"] = float(coupler_world[0])
                    params["coupler_y"] = float(coupler_world[1])

            sync_fourbar_scene_params_from_key_points(layer_data, params)

        elif internal_type == "cam":
            cam_center = self._snapshot_point(snapshot_positions, "cam_center")
            if cam_center is not None:
                dx, dy = pos[0] - cam_center[0], pos[1] - cam_center[1]
                translated_center = (cam_center[0] + dx, cam_center[1] + dy)
                layer_data["cam_position"] = [translated_center[0], translated_center[1]]
                translated_key_points: dict[str, list[float]] = {}
                for key in ("cam_center", "follower_base", "follower_end", "contact_point"):
                    source = self._snapshot_point(snapshot_positions, key)
                    if source is not None:
                        translated_key_points[key] = [source[0] + dx, source[1] + dy]
                if translated_key_points:
                    layer_data["key_points"] = translated_key_points
            else:
                layer_data["cam_position"] = list(pos)

            layer_data["cam_scale_factor"] = 1.0
            layer_data["rod_length_multiplier"] = 1.0
            params["center_x"] = layer_data["cam_position"][0]
            params["center_y"] = layer_data["cam_position"][1]
            params["cam_center"] = list(layer_data["cam_position"])
            layer_data.setdefault("key_points", {})
            if "cam_center" not in layer_data["key_points"]:
                layer_data["key_points"]["cam_center"] = list(layer_data["cam_position"])
            self._sync_cam_center_aliases(layer_data, layer_data["cam_position"])
            # Ensure harmonic parameters are present
            params.setdefault("cam_lobes", 1)
            params.setdefault("profile_harmonic", 0.3)

        elif internal_type == "gear":
            profile = self._profile_for_params(params)
            if grid_enabled_from_params(params):
                params.update(snap_gear_params(params, profile=profile))
            r1 = _positive_finite_float(params.get("gear1_radius", params.get("r1", 48.0)), 48.0)
            r2 = _positive_finite_float(params.get("gear2_radius", params.get("r2", 72.0)), 72.0)
            center_distance = max(
                10.0,
                gear_center_distance(
                    r1,
                    r2,
                    params.get("gear_clearance", params.get("mesh_clearance")),
                    profile=profile,
                ),
            )
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
        return _finite_point(positions.get(key))

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
        if (
            not all(math.isfinite(value) for value in (p1[0], p1[1], p2[0], p2[1], r1, r2))
            or r1 <= 0.0
            or r2 <= 0.0
            or d <= 1e-9
            or d > (r1 + r2)
            or d < abs(r1 - r2)
        ):
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
        grid_enabled = grid_enabled_from_params(foundry_params)
        profile = physical_profile_from_params(foundry_params)
        if "grid_system_enabled" in foundry_params:
            params["grid_system_enabled"] = grid_enabled
        if "grid_cell_cm" in foundry_params:
            params["grid_cell_cm"] = grid_cell_cm_from_params(foundry_params)
        if "grid_pitch_choice" in foundry_params:
            params["grid_pitch_choice"] = foundry_params["grid_pitch_choice"]
        if "physical_profile_key" in foundry_params:
            params["physical_profile_key"] = profile.key

        normalized_type = _normalize_foundry_type(foundry_type)

        if normalized_type == "four_bar":
            # Map: ground_link -> l1, input_link -> l2, coupler_link -> l3, output_link -> l4
            params["l1"] = _positive_finite_float(foundry_params.get("ground_link", 150.0), 150.0)
            params["l2"] = _positive_finite_float(foundry_params.get("input_link", 40.0), 40.0)
            params["l3"] = _positive_finite_float(foundry_params.get("coupler_link", 120.0), 120.0)
            params["l4"] = _positive_finite_float(foundry_params.get("output_link", 130.0), 130.0)
            params["coupler_point_x"] = _finite_float(
                foundry_params.get("coupler_point_x", 60.0), 60.0
            )
            params["coupler_point_y"] = _finite_float(
                foundry_params.get("coupler_point_y", 30.0), 30.0
            )
            if "input_angle" in foundry_params:
                angle = _finite_float(foundry_params["input_angle"], 30.0)
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
            params["base_radius"] = _positive_finite_float(
                foundry_params.get("cam_radius", 60.0), 60.0
            )
            params["eccentricity"] = _finite_float(foundry_params.get("cam_offset", 20.0), 20.0)
            if params["eccentricity"] < 0.0:
                params["eccentricity"] = 20.0
            params["follower_rod_length"] = _positive_finite_float(
                foundry_params.get("follower_length", 100.0), 100.0
            )
            params["cam_lobes"] = _positive_int(foundry_params.get("cam_lobes", 1), 1)
            params["profile_harmonic"] = _finite_float(
                foundry_params.get("profile_harmonic", 0.3), 0.3
            )
            if "input_angle" in foundry_params:
                params["input_angle"] = _finite_float(foundry_params["input_angle"], 0.0)
            if "reverse_direction" in foundry_params:
                params["reverse_direction"] = _bool_flag(foundry_params["reverse_direction"])
            output_mode = foundry_params.get("output_point_mode")
            if isinstance(output_mode, str):
                normalized_mode = output_mode.strip().lower()
                if normalized_mode in {"follower_base", "follower_end"}:
                    params["output_point_mode"] = "follower_base"
                elif normalized_mode == "contact_point":
                    params["output_point_mode"] = "contact_point"

        elif normalized_type in {"gear_train", "gear_linkage"}:
            gear_presets = profile.gear_presets or GEAR_PRESETS
            default_gear1 = gear_presets[0].teeth
            default_gear2 = gear_presets[min(2, len(gear_presets) - 1)].teeth
            gear1_raw = foundry_params.get("gear1_teeth", default_gear1)
            gear2_raw = foundry_params.get("gear2_teeth", default_gear2)
            gear1_teeth = _positive_int(gear1_raw, default_gear1)
            gear2_teeth = _positive_int(gear2_raw, default_gear2)
            if grid_enabled:
                gear1_teeth = nearest_gear_teeth(gear1_teeth, profile=profile)
                gear2_teeth = nearest_gear_teeth(gear2_teeth, profile=profile)
                radius_1 = gear_radius_for_teeth(gear1_teeth, profile=profile)
                radius_2 = gear_radius_for_teeth(gear2_teeth, profile=profile)
            else:
                default_radius_1 = freeform_gear_radius_for_teeth(
                    gear1_teeth,
                    profile=profile,
                )
                default_radius_2 = freeform_gear_radius_for_teeth(
                    gear2_teeth,
                    profile=profile,
                )
                radius_1 = _positive_finite_float(
                    foundry_params.get(
                        "gear1_radius",
                        foundry_params.get("r1", default_radius_1),
                    ),
                    default_radius_1,
                )
                radius_2 = _positive_finite_float(
                    foundry_params.get(
                        "gear2_radius",
                        foundry_params.get("r2", default_radius_2),
                    ),
                    default_radius_2,
                )
            params["gear1_teeth"] = gear1_teeth
            params["gear2_teeth"] = gear2_teeth
            params["r1"] = radius_1
            params["r2"] = radius_2
            params["gear1_radius"] = float(params["r1"])
            params["gear2_radius"] = float(params["r2"])
            params["gear_clearance"] = gear_clearance_from_params(foundry_params, profile=profile)
            params["mesh_clearance"] = params["gear_clearance"]
            if "input_torque" in foundry_params:
                params["input_torque"] = _finite_float(foundry_params["input_torque"], 0.0)
            if "input_angle" in foundry_params:
                params["input_angle"] = _finite_float(foundry_params["input_angle"], 0.0)
            if normalized_type == "gear_linkage":
                params["gear_linkage_enabled"] = True
                if "linkage_pin_radius" in foundry_params:
                    params["linkage_pin_radius"] = _positive_finite_float(
                        foundry_params["linkage_pin_radius"],
                        radius_2 * 0.72,
                    )
                if "linkage_arm_length" in foundry_params:
                    params["linkage_arm_length"] = _positive_finite_float(
                        foundry_params["linkage_arm_length"],
                        grid_cell_cm_from_params(foundry_params) * 20.0,
                    )

        elif normalized_type == "slider_crank":
            # Approximate slider-crank with a 4-bar payload for current Design internals.
            crank_length = _positive_finite_float(foundry_params.get("crank_length", 80.0), 80.0)
            rod_length = _positive_finite_float(foundry_params.get("rod_length", 140.0), 140.0)

            params["l2"] = crank_length
            params["l3"] = rod_length
            params["l4"] = rod_length
            params["l1"] = max(1.0, crank_length + rod_length)
            params["coupler_point_x"] = rod_length * 0.5
            params["coupler_point_y"] = 0.0

            if "input_angle" in foundry_params:
                angle = _finite_float(foundry_params["input_angle"], 0.0)
                params["input_angle"] = angle
                params["crank_angle"] = angle
            if "gas_pressure" in foundry_params:
                params["gas_pressure"] = _finite_float(foundry_params["gas_pressure"], 0.0)

        else:
            # Copy params as-is for unknown types
            params = dict(foundry_params)

        if normalized_type == "cam_follower" and grid_enabled:
            profile = self._profile_for_params(params)
            params.update(
                snap_cam_params(
                    params,
                    grid_cell_cm_from_params(foundry_params),
                    profile=profile,
                )
            )

        return params
