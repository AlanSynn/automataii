"""
Parameter Mapper - Mechanism parameter setup and coordinate transformation.

Extracted from ParametricEditingManager. Handles extracting positions from
simulation data and mapping between scene and mechanism coordinate spaces.

Design Pattern: Service (coordinate transformation and parameter initialization)
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import numpy as np

from automataii.shared.physical_kit import (
    DEFAULT_PHYSICAL_KIT_PROFILE,
    PhysicalKitProfile,
    freeform_gear_teeth_for_radius,
    gear_center_distance,
    physical_profile_from_params,
)

if TYPE_CHECKING:
    pass


def _finite_float(value: object, default: float) -> float:
    """Return a finite float or a safe default for user/catalog supplied values."""
    if isinstance(value, bool):
        return default
    try:
        result = float(cast(Any, value))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _positive_finite_float(value: object, default: float, minimum: float = 1e-6) -> float:
    """Return a positive finite float, clamping invalid values to a default."""
    result = _finite_float(value, default)
    return result if result >= minimum else default


def _first_finite_float(default: float, *values: object) -> float:
    """Return the first finite value from alias candidates, otherwise default."""
    for value in values:
        result = _finite_float(value, math.nan)
        if math.isfinite(result):
            return result
    return default


def _first_positive_finite_float(
    default: float,
    *values: object,
    minimum: float = 1e-6,
) -> float:
    """Return the first positive finite value from alias candidates, otherwise default."""
    for value in values:
        result = _finite_float(value, math.nan)
        if math.isfinite(result) and result >= minimum:
            return result
    return default


def _first_nonnegative_finite_float(default: float, *values: object) -> float:
    """Return the first non-negative finite value from alias candidates, otherwise default."""
    for value in values:
        result = _finite_float(value, math.nan)
        if math.isfinite(result) and result >= 0.0:
            return result
    return default


def _dict_or_empty(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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


@dataclass
class TransformConfig:
    """Configuration for coordinate transformation."""

    scale: float = 1.0
    user_scale: float = 100.0
    offset_x: float = 0.0
    offset_y: float = 0.0


class ParameterMapper:
    """
    Maps mechanism parameters between scene and mechanism coordinate spaces.

    Responsibilities:
    - Extract positions from simulation data
    - Transform coordinates between spaces
    - Initialize default parameters for each mechanism type

    Time Complexity: O(1) for all operations
    """

    def __init__(
        self,
        physical_profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
    ) -> None:
        """Initialize parameter mapper."""
        self._physical_profile = physical_profile

    def set_physical_profile(self, profile: PhysicalKitProfile) -> None:
        self._physical_profile = profile

    def _profile_for_params(self, params: dict[str, Any]) -> PhysicalKitProfile:
        if "physical_profile_key" in params:
            return physical_profile_from_params(params)
        return self._physical_profile

    def ensure_mechanism_parameters(
        self,
        layer_data: dict[str, Any],
        mechanism_type: str,
        to_scene: Callable | None = None,
    ) -> None:
        """
        Ensure all required parameters are present for a mechanism type.

        Args:
            layer_data: Mechanism layer data dictionary
            mechanism_type: Type of mechanism (cam, 4_bar_linkage, gear, etc.)
            to_scene: Optional transform function to scene coordinates
        """
        if not isinstance(layer_data.get("params"), dict):
            layer_data["params"] = {}

        params = layer_data["params"]

        if mechanism_type == "cam":
            self._setup_cam_parameters(layer_data, params, to_scene)
        elif mechanism_type == "4_bar_linkage":
            self._setup_4bar_parameters(layer_data, params, to_scene)
        elif mechanism_type in ["gear", "simple_gear"]:
            self._setup_gear_parameters(layer_data, params, to_scene)
        elif mechanism_type == "planetary_gear":
            self._setup_planetary_gear_parameters(layer_data, params, to_scene)

    def _setup_cam_parameters(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        to_scene: Callable | None = None,
    ) -> None:
        """Setup parameters for cam mechanism."""
        cam_position = layer_data.get("cam_position")
        key_points = _dict_or_empty(layer_data.get("key_points", {}))

        # If explicit scene-space center already exists, keep it as authoritative.
        if "center_x" in params and "center_y" in params:
            center_x = _finite_float(params["center_x"], math.nan)
            center_y = _finite_float(params["center_y"], math.nan)
            if math.isfinite(center_x) and math.isfinite(center_y):
                params["center_x"] = center_x
                params["center_y"] = center_y
                return

        cam_position_point = _finite_point_array(cam_position)
        if cam_position_point is not None:
            # cam_position is stored in scene space by instantiation/editor flows.
            params["center_x"] = float(cam_position_point[0])
            params["center_y"] = float(cam_position_point[1])
            return

        params_cam_center = _finite_point_array(params.get("cam_center"))
        if params_cam_center is not None:
            params["center_x"] = float(params_cam_center[0])
            params["center_y"] = float(params_cam_center[1])
            return

        # Try key_points last. It is mechanism-space when transform functions exist.
        cam_center = _finite_point_array(key_points.get("cam_center"))
        if cam_center is not None and to_scene:
            center_scene = self._to_scene_point(cam_center, to_scene)
            if center_scene is not None:
                params["center_x"], params["center_y"] = center_scene
                return
        if cam_center is not None and to_scene is None:
            params["center_x"] = float(cam_center[0])
            params["center_y"] = float(cam_center[1])
            return

        params["center_x"] = _finite_float(params.get("center_x"), 400.0)
        params["center_y"] = _finite_float(params.get("center_y"), 300.0)

    def _setup_4bar_parameters(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        to_scene: Callable | None = None,
    ) -> None:
        """Setup parameters for 4-bar linkage mechanism."""
        if self._extract_4bar_positions_from_explicit_params(layer_data, params):
            return

        full_sim_data = _dict_or_empty(layer_data.get("full_simulation_data", {}))

        if "joint_positions" in full_sim_data:
            joint_positions = _dict_or_empty(full_sim_data["joint_positions"])
            if self._has_valid_joint_positions(joint_positions):
                self._extract_4bar_positions_from_simulation(
                    layer_data, params, joint_positions, to_scene
                )
                return

        if self._extract_4bar_positions_from_key_points(layer_data, params, to_scene):
            return

        self._set_default_4bar_parameters(params)

    def _extract_4bar_positions_from_explicit_params(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
    ) -> bool:
        """Keep existing scene-space 4-bar editor coordinates authoritative."""
        required_keys = (
            "anchor1_x",
            "anchor1_y",
            "anchor2_x",
            "anchor2_y",
            "crank_x",
            "crank_y",
            "rocker_x",
            "rocker_y",
        )
        values = {key: _finite_float(params.get(key), math.nan) for key in required_keys}
        if not all(math.isfinite(value) for value in values.values()):
            return False

        params.update(values)
        params["crank_angle"] = math.degrees(
            math.atan2(
                values["crank_y"] - values["anchor1_y"], values["crank_x"] - values["anchor1_x"]
            )
        )
        params["rocker_angle"] = math.degrees(
            math.atan2(
                values["rocker_y"] - values["anchor2_y"],
                values["rocker_x"] - values["anchor2_x"],
            )
        )
        self._sync_4bar_lengths_from_scene_points(params, values)

        has_explicit_coupler = math.isfinite(
            _finite_float(params.get("coupler_x"), math.nan)
        ) and math.isfinite(_finite_float(params.get("coupler_y"), math.nan))
        if not has_explicit_coupler:
            self._calculate_coupler_position(
                layer_data,
                params,
                values["crank_x"],
                values["crank_y"],
                values["rocker_x"],
                values["rocker_y"],
            )
        return True

    @staticmethod
    def _sync_4bar_lengths_from_scene_points(
        params: dict[str, Any],
        values: dict[str, float],
    ) -> None:
        """Sync numeric 4-bar length aliases from visible scene coordinates."""
        p1 = np.array([values["anchor1_x"], values["anchor1_y"]], dtype=float)
        p2 = np.array([values["anchor2_x"], values["anchor2_y"]], dtype=float)
        p3 = np.array([values["crank_x"], values["crank_y"]], dtype=float)
        p4 = np.array([values["rocker_x"], values["rocker_y"]], dtype=float)
        lengths = {
            "l1": float(np.linalg.norm(p2 - p1)),
            "l2": float(np.linalg.norm(p3 - p1)),
            "l3": float(np.linalg.norm(p4 - p3)),
            "l4": float(np.linalg.norm(p4 - p2)),
        }
        for lower, length in lengths.items():
            params[lower] = length
            params[lower.upper()] = length
        params["input_angle"] = params["crank_angle"]

    def _extract_4bar_positions_from_key_points(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        to_scene: Callable | None = None,
    ) -> bool:
        """Extract 4-bar positions from key_points when simulation frames are unavailable."""
        key_points = _dict_or_empty(layer_data.get("key_points", {}))
        p1 = _finite_point_array(key_points.get("ground_pivot_1"))
        p2 = _finite_point_array(key_points.get("ground_pivot_2"))

        if p1 is None or p2 is None:
            return False

        # Foundry imports often store scene-space key_points without generated_path.
        use_scene_points_directly = layer_data.get("generated_path") is None or to_scene is None

        def map_point(raw: np.ndarray) -> tuple[float, float] | None:
            if use_scene_points_directly:
                return float(raw[0]), float(raw[1])
            return self._to_scene_point(raw, to_scene)

        p1_scene = map_point(p1)
        p2_scene = map_point(p2)
        if p1_scene is None or p2_scene is None:
            return False
        params["anchor1_x"], params["anchor1_y"] = p1_scene
        params["anchor2_x"], params["anchor2_y"] = p2_scene

        p3 = _finite_point_array(key_points.get("crank_end"))
        if p3 is not None:
            p3_scene = map_point(p3)
            if p3_scene is None:
                return True
            p3_x, p3_y = self.extract_coordinates(p3_scene)
            params["crank_x"] = p3_x
            params["crank_y"] = p3_y
            params["crank_angle"] = math.degrees(
                math.atan2(p3_y - params["anchor1_y"], p3_x - params["anchor1_x"])
            )

        p4 = _finite_point_array(key_points.get("rocker_end"))
        if p4 is not None:
            p4_scene = map_point(p4)
            if p4_scene is None:
                return True
            p4_x, p4_y = self.extract_coordinates(p4_scene)
            params["rocker_x"] = p4_x
            params["rocker_y"] = p4_y
            params["rocker_angle"] = math.degrees(
                math.atan2(p4_y - params["anchor2_y"], p4_x - params["anchor2_x"])
            )

            if "crank_x" in params and "crank_y" in params:
                self._calculate_coupler_position(
                    layer_data,
                    params,
                    float(params["crank_x"]),
                    float(params["crank_y"]),
                    p4_x,
                    p4_y,
                )

        return True

    def _has_valid_joint_positions(self, joint_positions: dict[str, Any]) -> bool:
        """Check if joint positions data is valid."""
        if not isinstance(joint_positions, dict):
            return False
        p1_positions = joint_positions.get("p1_positions")
        p2_positions = joint_positions.get("p2_positions")
        if not isinstance(p1_positions, list | tuple) or not isinstance(p2_positions, list | tuple):
            return False
        if len(p1_positions) == 0 or len(p2_positions) == 0:
            return False
        return (
            _finite_point_array(p1_positions[0]) is not None
            and _finite_point_array(p2_positions[0]) is not None
        )

    def _extract_4bar_positions_from_simulation(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        joint_positions: dict[str, Any],
        to_scene: Callable | None = None,
    ) -> None:
        """Extract 4-bar linkage positions from simulation data."""
        p1 = _finite_point_array(joint_positions["p1_positions"][0])
        p2 = _finite_point_array(joint_positions["p2_positions"][0])
        p3 = self._first_finite_point(joint_positions.get("p3_positions"))
        p4 = self._first_finite_point(joint_positions.get("p4_positions"))
        if p1 is None or p2 is None:
            self._set_default_4bar_parameters(params)
            return

        if to_scene:
            p1_scene = self._to_scene_point(p1, to_scene)
            p2_scene = self._to_scene_point(p2, to_scene)
            if p1_scene is None or p2_scene is None:
                self._set_default_4bar_parameters(params)
                return

            params["anchor1_x"], params["anchor1_y"] = p1_scene
            params["anchor2_x"], params["anchor2_y"] = p2_scene

            if p3 is not None:
                p3_scene = self._to_scene_point(p3, to_scene)
                if p3_scene is None:
                    p3 = None
                else:
                    p3_x, p3_y = p3_scene

                    dx = p3_x - params["anchor1_x"]
                    dy = p3_y - params["anchor1_y"]
                    params["crank_angle"] = math.degrees(math.atan2(dy, dx))
                    params["crank_x"] = p3_x
                    params["crank_y"] = p3_y

            if p4 is not None:
                p4_scene = self._to_scene_point(p4, to_scene)
                if p4_scene is None:
                    params.setdefault("rocker_angle", 45.0)
                    return
                p4_x, p4_y = p4_scene

                dx = p4_x - params["anchor2_x"]
                dy = p4_y - params["anchor2_y"]
                params["rocker_angle"] = math.degrees(math.atan2(dy, dx))
                params["rocker_x"] = p4_x
                params["rocker_y"] = p4_y

                if p3 is not None:
                    self._calculate_coupler_position(layer_data, params, p3_x, p3_y, p4_x, p4_y)
        else:
            params["anchor1_x"] = float(p1[0])
            params["anchor1_y"] = float(p1[1])
            params["anchor2_x"] = float(p2[0])
            params["anchor2_y"] = float(p2[1])
            if p3 is not None:
                p3_x = float(p3[0])
                p3_y = float(p3[1])
                params["crank_x"] = p3_x
                params["crank_y"] = p3_y
                params["crank_angle"] = math.degrees(
                    math.atan2(p3_y - params["anchor1_y"], p3_x - params["anchor1_x"])
                )
            else:
                params.setdefault("crank_angle", 0)

            if p4 is not None:
                p4_x = float(p4[0])
                p4_y = float(p4[1])
                params["rocker_x"] = p4_x
                params["rocker_y"] = p4_y
                params["rocker_angle"] = math.degrees(
                    math.atan2(p4_y - params["anchor2_y"], p4_x - params["anchor2_x"])
                )
                if p3 is not None:
                    self._calculate_coupler_position(layer_data, params, p3_x, p3_y, p4_x, p4_y)
            else:
                params.setdefault("rocker_angle", 45)
                params.setdefault("coupler_x", 350)
                params.setdefault("coupler_y", 250)

    def extract_coordinates(self, point: Any) -> tuple[float, float]:
        """Extract x,y coordinates from point object."""
        if hasattr(point, "x"):
            return point.x(), point.y()
        elif isinstance(point, np.ndarray):
            return float(point[0]), float(point[1])
        else:
            return float(point[0]), float(point[1])

    def _extract_finite_coordinates(self, point: Any) -> tuple[float, float] | None:
        """Extract coordinates and reject non-finite transform output."""
        try:
            x, y = self.extract_coordinates(point)
        except (TypeError, ValueError, IndexError):
            return None
        x = _finite_float(x, math.nan)
        y = _finite_float(y, math.nan)
        if not math.isfinite(x) or not math.isfinite(y):
            return None
        return x, y

    def _to_scene_point(
        self,
        point: np.ndarray,
        to_scene: Callable | None,
    ) -> tuple[float, float] | None:
        """Transform a mechanism-space point to scene coordinates with validation."""
        if to_scene is None:
            return float(point[0]), float(point[1])
        try:
            return self._extract_finite_coordinates(to_scene(np.array(point, dtype=float)))
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)
            return None

    @staticmethod
    def _first_finite_point(points: object) -> np.ndarray | None:
        try:
            rows = np.asarray(points, dtype=float)
        except (TypeError, ValueError):
            return None
        if rows.ndim == 1:
            return _finite_point_array(rows)
        if rows.ndim != 2 or rows.shape[0] == 0:
            return None
        return _finite_point_array(rows[0])

    def _calculate_coupler_position(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        p3_x: float,
        p3_y: float,
        p4_x: float,
        p4_y: float,
    ) -> None:
        """Calculate coupler position for 4-bar linkage."""
        coupler_point_x = _finite_float(params.get("coupler_point_x", 0.0), 0.0)
        coupler_point_y = _finite_float(params.get("coupler_point_y", 0.0), 0.0)

        coupler_vec_x = p4_x - p3_x
        coupler_vec_y = p4_y - p3_y
        coupler_length = math.sqrt(coupler_vec_x**2 + coupler_vec_y**2)

        if coupler_length > 0:
            coupler_unit_x = coupler_vec_x / coupler_length
            coupler_unit_y = coupler_vec_y / coupler_length
            coupler_normal_x = -coupler_unit_y
            coupler_normal_y = coupler_unit_x

            transform_params = _dict_or_empty(layer_data.get("transform_params", {}))
            scale = _positive_finite_float(transform_params.get("scale", 1.0), 1.0)
            scaled_offset_x = coupler_point_x * scale
            scaled_offset_y = coupler_point_y * scale

            params["coupler_x"] = (
                p3_x + scaled_offset_x * coupler_unit_x + scaled_offset_y * coupler_normal_x
            )
            params["coupler_y"] = (
                p3_y + scaled_offset_x * coupler_unit_y + scaled_offset_y * coupler_normal_y
            )
        else:
            params["coupler_x"] = p3_x
            params["coupler_y"] = p3_y

    def _set_default_4bar_parameters(self, params: dict[str, Any]) -> None:
        """Set default parameters for 4-bar linkage."""
        l1 = _positive_finite_float(params.get("l1", 100.0), 100.0)
        anchor1_x = _finite_float(params.get("anchor1_x", 400.0), 400.0)
        anchor1_y = _finite_float(params.get("anchor1_y", 300.0), 300.0)
        params["anchor1_x"] = anchor1_x
        params["anchor1_y"] = anchor1_y
        params["anchor2_x"] = _finite_float(params.get("anchor2_x"), anchor1_x + l1)
        params["anchor2_y"] = _finite_float(params.get("anchor2_y"), anchor1_y)
        params["crank_angle"] = _finite_float(params.get("crank_angle", 0.0), 0.0)
        params["rocker_angle"] = _finite_float(params.get("rocker_angle", 45.0), 45.0)
        params["coupler_x"] = _finite_float(params.get("coupler_x", 450.0), 450.0)
        params["coupler_y"] = _finite_float(params.get("coupler_y", 250.0), 250.0)

    def _setup_gear_parameters(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        to_scene: Callable | None = None,
    ) -> None:
        """Setup parameters for gear mechanism."""
        full_sim_data = _dict_or_empty(layer_data.get("full_simulation_data", {}))
        profile = self._profile_for_params(params)
        default_gear_radius = 30.0
        if profile.gear_presets:
            default_gear_preset = profile.gear_presets[min(1, len(profile.gear_presets) - 1)]
            default_gear_radius = default_gear_preset.teeth * profile.gear_radius_per_tooth_mm

        radius_1 = _first_positive_finite_float(
            default_gear_radius,
            params.get("gear1_radius"),
            params.get("r1"),
        )
        radius_2 = _first_positive_finite_float(
            default_gear_radius,
            params.get("gear2_radius"),
            params.get("r2"),
        )

        if "gear1_radius" not in params and "r1" in params:
            radius_1 = self._mech_radius_to_scene(radius_1, to_scene)
        if "gear2_radius" not in params and "r2" in params:
            radius_2 = self._mech_radius_to_scene(radius_2, to_scene)

        params["gear1_radius"] = radius_1
        params["gear2_radius"] = radius_2
        params["r1"] = radius_1
        params["r2"] = radius_2
        params.setdefault("gear1_teeth", freeform_gear_teeth_for_radius(radius_1, profile=profile))
        params.setdefault("gear2_teeth", freeform_gear_teeth_for_radius(radius_2, profile=profile))

        if isinstance(full_sim_data.get("gear_data"), dict) and to_scene:
            self._extract_gear_positions_from_simulation(params, full_sim_data, to_scene)
        self._extract_gear_positions_from_key_points(layer_data, params, to_scene)
        self._set_default_gear_positions(params)

    def _mech_radius_to_scene(
        self,
        mech_radius: float,
        to_scene: Callable | None,
    ) -> float:
        """Convert mechanism-space radius to scene-space radius."""
        if to_scene is None:
            return float(mech_radius)
        try:
            origin = to_scene(np.array([0.0, 0.0], dtype=float))
            edge = to_scene(np.array([float(mech_radius), 0.0], dtype=float))
            origin_coords = self._extract_finite_coordinates(origin)
            edge_coords = self._extract_finite_coordinates(edge)
            if origin_coords is None or edge_coords is None:
                return float(mech_radius)
            ox, oy = origin_coords
            ex, ey = edge_coords
            scene_radius = math.hypot(ex - ox, ey - oy)
            return (
                float(scene_radius)
                if math.isfinite(scene_radius) and scene_radius > 0
                else float(mech_radius)
            )
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)
            return float(mech_radius)

    def _extract_gear_positions_from_simulation(
        self,
        params: dict[str, Any],
        full_sim_data: dict[str, Any],
        to_scene: Callable,
    ) -> None:
        """Extract gear positions from simulation data."""
        gear_data = _dict_or_empty(full_sim_data.get("gear_data", {}))

        g1_center = self._first_finite_point(gear_data.get("gear1_centers"))
        if g1_center is not None:
            g1_scene = self._to_scene_point(g1_center, to_scene)
            if g1_scene is not None:
                params["gear1_x"], params["gear1_y"] = g1_scene

        g2_center = self._first_finite_point(gear_data.get("gear2_centers"))
        if g2_center is not None:
            g2_scene = self._to_scene_point(g2_center, to_scene)
            if g2_scene is not None:
                params["gear2_x"], params["gear2_y"] = g2_scene

    def _extract_gear_positions_from_key_points(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        to_scene: Callable | None = None,
    ) -> None:
        """Extract simple gear center positions from key_points when available."""
        key_points = _dict_or_empty(layer_data.get("key_points", {}))
        use_scene_points_directly = layer_data.get("generated_path") is None or to_scene is None

        def map_point(raw: object) -> tuple[float, float] | None:
            point = _finite_point_array(raw)
            if point is None:
                return None
            if use_scene_points_directly:
                return float(point[0]), float(point[1])
            return self._to_scene_point(point, to_scene)

        def needs_position(x_key: str, y_key: str) -> bool:
            return not (
                math.isfinite(_finite_float(params.get(x_key), math.nan))
                and math.isfinite(_finite_float(params.get(y_key), math.nan))
            )

        if needs_position("gear1_x", "gear1_y"):
            gear1 = map_point(key_points.get("gear1_center"))
            if gear1 is not None:
                params["gear1_x"], params["gear1_y"] = gear1

        if needs_position("gear2_x", "gear2_y"):
            gear2 = map_point(key_points.get("gear2_center"))
            if gear2 is not None:
                params["gear2_x"], params["gear2_y"] = gear2

    def _set_default_gear_positions(self, params: dict[str, Any]) -> None:
        """Set default positions for gear mechanism."""
        gear1_x = _finite_float(params.get("gear1_x"), 400.0)
        gear1_y = _finite_float(params.get("gear1_y"), 300.0)
        profile = self._profile_for_params(params)
        default_gear_radius = 30.0
        if profile.gear_presets:
            default_gear_preset = profile.gear_presets[min(1, len(profile.gear_presets) - 1)]
            default_gear_radius = default_gear_preset.teeth * profile.gear_radius_per_tooth_mm
        r1 = _first_positive_finite_float(
            default_gear_radius, params.get("gear1_radius"), params.get("r1")
        )
        r2 = _first_positive_finite_float(
            default_gear_radius, params.get("gear2_radius"), params.get("r2")
        )

        params["gear1_x"] = gear1_x
        params["gear1_y"] = gear1_y
        params["gear2_x"] = _finite_float(
            params.get("gear2_x"),
            gear1_x + gear_center_distance(r1, r2, params.get("gear_clearance"), profile=profile),
        )
        params["gear2_y"] = _finite_float(params.get("gear2_y"), gear1_y)

    def _setup_planetary_gear_parameters(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        to_scene: Callable | None = None,
    ) -> None:
        """Setup parameters for planetary gear mechanism.

        Note: PlanetaryGearEditor expects sun_x, sun_y, r_sun, r_planet, arm_length.
        We map both naming conventions for compatibility.
        """
        full_sim_data = _dict_or_empty(layer_data.get("full_simulation_data", {}))

        # Setup r_sun (PlanetaryGearEditor expects this name)
        params["r_sun"] = _first_positive_finite_float(
            20.0,
            params.get("r_sun"),
            params.get("sun_radius"),
            params.get("gear1_radius"),
        )
        # Also set gear1_radius for backwards compatibility
        params["gear1_radius"] = params["r_sun"]

        # Setup r_planet (PlanetaryGearEditor expects this name)
        params["r_planet"] = _first_positive_finite_float(
            30.0,
            params.get("r_planet"),
            params.get("planet_radius"),
            params.get("gear2_radius"),
            minimum=1.0,
        )
        # Also set gear2_radius for backwards compatibility
        params["gear2_radius"] = params["r_planet"]

        # Setup arm_length
        params["arm_length"] = _first_nonnegative_finite_float(
            15.0,
            params.get("arm_length"),
            params.get("carrier_length"),
        )

        if isinstance(full_sim_data.get("gear_positions"), dict) and to_scene:
            self._extract_planetary_positions_from_simulation(params, full_sim_data, to_scene)
            self._set_default_planetary_positions(params)
        elif self._extract_planetary_positions_from_key_points(layer_data, params, to_scene):
            pass
        else:
            self._set_default_planetary_positions(params)

    def _extract_planetary_positions_from_simulation(
        self,
        params: dict[str, Any],
        full_sim_data: dict[str, Any],
        to_scene: Callable,
    ) -> None:
        """Extract planetary gear positions from simulation data.

        Sets both sun_x/sun_y (for PlanetaryGearEditor) and gear1_x/gear1_y (for compatibility).
        """
        gear_pos = _dict_or_empty(full_sim_data.get("gear_positions", {}))

        sun_center = self._first_finite_point(gear_pos.get("sun_centers"))
        if sun_center is not None:
            sun_scene = self._to_scene_point(sun_center, to_scene)
            if sun_scene is not None:
                x, y = sun_scene
                # PlanetaryGearEditor expects sun_x, sun_y
                params["sun_x"], params["sun_y"] = x, y
                # Also set gear1_x, gear1_y for backwards compatibility
                params["gear1_x"], params["gear1_y"] = x, y

        planet_center = self._first_finite_point(gear_pos.get("planet_centers"))
        if planet_center is not None:
            planet_scene = self._to_scene_point(planet_center, to_scene)
            if planet_scene is not None:
                x, y = planet_scene
                # Set both naming conventions
                params["planet_x"], params["planet_y"] = x, y
                params["gear2_x"], params["gear2_y"] = x, y

    def _extract_planetary_positions_from_key_points(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        to_scene: Callable | None = None,
    ) -> bool:
        """Extract planetary positions from key_points when simulation frames are unavailable."""
        key_points = _dict_or_empty(layer_data.get("key_points", {}))
        sun_center = _finite_point_array(key_points.get("sun_center"))
        if sun_center is None:
            return False

        use_scene_points_directly = layer_data.get("generated_path") is None or to_scene is None

        def map_point(raw: np.ndarray) -> tuple[float, float] | None:
            if use_scene_points_directly:
                return float(raw[0]), float(raw[1])
            return self._to_scene_point(raw, to_scene)

        sun_scene = map_point(sun_center)
        if sun_scene is None:
            return False
        sun_x, sun_y = sun_scene
        params["sun_x"], params["sun_y"] = sun_x, sun_y
        params["gear1_x"], params["gear1_y"] = sun_x, sun_y

        planet_center = _finite_point_array(key_points.get("planet_center"))
        if planet_center is not None:
            planet_scene = map_point(planet_center)
            if planet_scene is None:
                planet_x = sun_x + params["r_sun"] + params["r_planet"]
                planet_y = sun_y
            else:
                planet_x, planet_y = planet_scene
        else:
            planet_x = float(sun_x) + params["r_sun"] + params["r_planet"]
            planet_y = float(sun_y)

        params["planet_x"], params["planet_y"] = planet_x, planet_y
        params["gear2_x"], params["gear2_y"] = planet_x, planet_y
        return True

    def _set_default_planetary_positions(self, params: dict[str, Any]) -> None:
        """Set default positions for planetary gear mechanism.

        Sets both sun_x/sun_y (for PlanetaryGearEditor) and gear1_x/gear1_y (for compatibility).
        """
        # Set sun center position (PlanetaryGearEditor expects sun_x, sun_y)
        params["sun_x"] = _first_finite_float(400.0, params.get("sun_x"), params.get("gear1_x"))
        params["sun_y"] = _first_finite_float(300.0, params.get("sun_y"), params.get("gear1_y"))
        # Also set gear1_x/gear1_y for backwards compatibility
        params["gear1_x"] = params["sun_x"]
        params["gear1_y"] = params["sun_y"]

        # Calculate planet position based on sun and planet radii
        r_sun = _positive_finite_float(params.get("r_sun", 20.0), 20.0)
        r_planet = _positive_finite_float(params.get("r_planet", 30.0), 30.0, minimum=1.0)

        params["planet_x"] = _first_finite_float(
            params["sun_x"] + r_sun + r_planet,
            params.get("planet_x"),
            params.get("gear2_x"),
        )
        params["planet_y"] = _first_finite_float(
            params["sun_y"],
            params.get("planet_y"),
            params.get("gear2_y"),
        )
        # Also set gear2_x/gear2_y for backwards compatibility
        params["gear2_x"] = params["planet_x"]
        params["gear2_y"] = params["planet_y"]

    def get_transform_config(
        self,
        layer_data: dict[str, Any],
        path_converter: Callable[[Any], np.ndarray | None] | None = None,
    ) -> TransformConfig:
        """
        Get transform configuration from layer data.

        Args:
            layer_data: Mechanism layer data
            path_converter: Optional function to convert path to numpy array

        Returns:
            TransformConfig with scale and offset values
        """
        transform_params = _dict_or_empty(layer_data.get("transform_params", {}))
        scale = _positive_finite_float(transform_params.get("scale", 1.0), 1.0)
        user_scale = 100.0

        if path_converter:
            try:
                user_path_np = path_converter(layer_data.get("generated_path"))
                user_path_np = self._finite_rows(user_path_np)
                if user_path_np is not None and len(user_path_np) > 0:
                    bbox = np.max(user_path_np, axis=0) - np.min(user_path_np, axis=0)
                    bbox_max = float(np.max(bbox))
                    user_scale = bbox_max / 2.0 if bbox_max > 0 else 100.0
                    if user_scale < 10 or user_scale > 10000:
                        user_scale = float(np.clip(user_scale, 50, 1000))
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

        return TransformConfig(
            scale=scale,
            user_scale=user_scale,
            offset_x=_finite_float(transform_params.get("offset_x", 0.0), 0.0),
            offset_y=_finite_float(transform_params.get("offset_y", 0.0), 0.0),
        )

    def scene_to_mech_length(
        self,
        value: float,
        config: TransformConfig,
    ) -> float:
        """Convert scene length to mechanism length."""
        safe_value = _finite_float(value, 0.0)
        scale = _positive_finite_float(config.scale, 1.0)
        user_scale = _positive_finite_float(config.user_scale, 100.0)
        return safe_value * (scale / user_scale)

    def mech_to_scene_length(
        self,
        value: float,
        config: TransformConfig,
    ) -> float:
        """Convert mechanism length to scene length."""
        safe_value = _finite_float(value, 0.0)
        scale = _positive_finite_float(config.scale, 1.0)
        user_scale = _positive_finite_float(config.user_scale, 100.0)
        return safe_value * (user_scale / scale)

    @staticmethod
    def _finite_rows(value: object) -> np.ndarray | None:
        try:
            rows = np.asarray(value, dtype=float)
        except (TypeError, ValueError):
            return None
        if rows.ndim != 2 or rows.shape[0] == 0 or rows.shape[1] < 2:
            return None
        rows = rows[:, :2]
        if not bool(np.isfinite(rows).all()):
            return None
        return rows
