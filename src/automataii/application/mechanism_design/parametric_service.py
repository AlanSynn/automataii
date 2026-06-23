from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import numpy as np

from automataii.shared.physical_kit import (
    DEFAULT_PHYSICAL_KIT_PROFILE,
    PhysicalKitProfile,
    freeform_gear_teeth_for_radius,
    gear_center_distance,
    physical_profile_from_params,
)

ToSceneFn = Callable[[np.ndarray], Any] | None


@dataclass
class ParametricContext:
    mechanism_type: str
    params: dict[str, Any]
    full_simulation_data: Mapping[str, Any]
    transform_params: Mapping[str, Any]
    cam_position: Sequence[float] | None = None
    to_scene: ToSceneFn = None
    physical_profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE


class ParametricParameterService:
    """Pure calculation utilities for parametric editing parameters."""

    def ensure_parameters(self, context: ParametricContext) -> None:
        mech_type = context.mechanism_type
        if mech_type == "cam":
            self._ensure_cam_parameters(context)
        elif mech_type == "4_bar_linkage":
            self._setup_4bar_parameters(context)
        elif mech_type in {"gear", "simple_gear"}:
            self._setup_gear_parameters(context)
        elif mech_type == "planetary_gear":
            self._setup_planetary_gear(context)

    # --- Cam -----------------------------------------------------------------
    def _ensure_cam_parameters(self, context: ParametricContext) -> None:
        params = context.params
        cam_position = context.cam_position
        if cam_position and len(cam_position) >= 2:
            params["center_x"] = cam_position[0]
            params["center_y"] = cam_position[1]
        else:
            params.setdefault("center_x", 400)
            params.setdefault("center_y", 300)

    # --- 4-bar ---------------------------------------------------------------
    def _setup_4bar_parameters(self, context: ParametricContext) -> None:
        params = context.params
        if self._has_explicit_4bar_scene_positions(params):
            self._sync_explicit_4bar_angles(context)
            return

        sim_data = context.full_simulation_data
        if "joint_positions" not in sim_data:
            self._set_default_4bar_parameters(params)
            return

        joint_positions = sim_data["joint_positions"]
        if not self._has_valid_joint_positions(joint_positions):
            self._set_default_4bar_parameters(params)
            return

        self._extract_4bar_positions(context, joint_positions)

    @staticmethod
    def _has_explicit_4bar_scene_positions(params: Mapping[str, Any]) -> bool:
        keys = (
            "anchor1_x",
            "anchor1_y",
            "anchor2_x",
            "anchor2_y",
            "crank_x",
            "crank_y",
            "rocker_x",
            "rocker_y",
        )
        try:
            return all(math.isfinite(float(params[key])) for key in keys)
        except (KeyError, TypeError, ValueError):
            return False

    def _sync_explicit_4bar_angles(self, context: ParametricContext) -> None:
        params = context.params
        params["crank_angle"] = math.degrees(
            math.atan2(
                float(params["crank_y"]) - float(params["anchor1_y"]),
                float(params["crank_x"]) - float(params["anchor1_x"]),
            )
        )
        params["rocker_angle"] = math.degrees(
            math.atan2(
                float(params["rocker_y"]) - float(params["anchor2_y"]),
                float(params["rocker_x"]) - float(params["anchor2_x"]),
            )
        )
        self._sync_4bar_lengths_from_scene_points(params)
        if "coupler_x" not in params or "coupler_y" not in params:
            self._calculate_coupler_position(
                context,
                float(params["crank_x"]),
                float(params["crank_y"]),
                float(params["rocker_x"]),
                float(params["rocker_y"]),
            )

    @staticmethod
    def _sync_4bar_lengths_from_scene_points(params: dict[str, Any]) -> None:
        p1 = np.array([float(params["anchor1_x"]), float(params["anchor1_y"])], dtype=float)
        p2 = np.array([float(params["anchor2_x"]), float(params["anchor2_y"])], dtype=float)
        p3 = np.array([float(params["crank_x"]), float(params["crank_y"])], dtype=float)
        p4 = np.array([float(params["rocker_x"]), float(params["rocker_y"])], dtype=float)
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

    @staticmethod
    def _has_valid_joint_positions(joint_positions: Mapping[str, Any]) -> bool:
        return (
            "p1_positions" in joint_positions
            and len(joint_positions["p1_positions"]) > 0
            and "p2_positions" in joint_positions
            and len(joint_positions["p2_positions"]) > 0
        )

    def _extract_4bar_positions(
        self,
        context: ParametricContext,
        joint_positions: Mapping[str, Any],
    ) -> None:
        params = context.params
        p1 = joint_positions["p1_positions"][0]
        p2 = joint_positions["p2_positions"][0]
        p3 = joint_positions.get("p3_positions", [None])[0]
        p4 = joint_positions.get("p4_positions", [None])[0]

        to_scene = context.to_scene
        if to_scene:
            p1_scene = to_scene(np.array(p1))
            p2_scene = to_scene(np.array(p2))
            params["anchor1_x"], params["anchor1_y"] = self._extract_coordinates(p1_scene)
            params["anchor2_x"], params["anchor2_y"] = self._extract_coordinates(p2_scene)

            if p3 is not None:
                p3_scene = to_scene(np.array(p3))
                p3_x, p3_y = self._extract_coordinates(p3_scene)
                params["crank_x"], params["crank_y"] = p3_x, p3_y
                params["crank_angle"] = math.degrees(
                    math.atan2(p3_y - params["anchor1_y"], p3_x - params["anchor1_x"])
                )
            else:
                p3_x = params.get("crank_x", params["anchor1_x"])
                p3_y = params.get("crank_y", params["anchor1_y"])

            if p4 is not None:
                p4_scene = to_scene(np.array(p4))
                p4_x, p4_y = self._extract_coordinates(p4_scene)
                params["rocker_x"], params["rocker_y"] = p4_x, p4_y
                params["rocker_angle"] = math.degrees(
                    math.atan2(p4_y - params["anchor2_y"], p4_x - params["anchor2_x"])
                )
                if p3 is not None:
                    self._calculate_coupler_position(context, p3_x, p3_y, p4_x, p4_y)
            else:
                params.setdefault("rocker_angle", 45)
        else:
            params["anchor1_x"], params["anchor1_y"] = p1[0], p1[1] if len(p1) > 1 else 0
            params["anchor2_x"], params["anchor2_y"] = p2[0], p2[1] if len(p2) > 1 else 0
            if p3 is not None:
                params["crank_x"], params["crank_y"] = p3[0], p3[1] if len(p3) > 1 else 0
                params["crank_angle"] = math.degrees(
                    math.atan2(
                        params["crank_y"] - params["anchor1_y"],
                        params["crank_x"] - params["anchor1_x"],
                    )
                )
            else:
                params.setdefault("crank_angle", 0)
            if p4 is not None:
                params["rocker_x"], params["rocker_y"] = p4[0], p4[1] if len(p4) > 1 else 0
                params["rocker_angle"] = math.degrees(
                    math.atan2(
                        params["rocker_y"] - params["anchor2_y"],
                        params["rocker_x"] - params["anchor2_x"],
                    )
                )
                if p3 is not None:
                    self._calculate_coupler_position(
                        context,
                        params["crank_x"],
                        params["crank_y"],
                        params["rocker_x"],
                        params["rocker_y"],
                    )
            else:
                params.setdefault("rocker_angle", 45)
                params.setdefault("coupler_x", 350)
                params.setdefault("coupler_y", 250)

    @staticmethod
    def _extract_coordinates(point: Any) -> tuple[float, float]:
        if hasattr(point, "x") and hasattr(point, "y"):
            return float(point.x()), float(point.y())
        if isinstance(point, np.ndarray):
            return float(point[0]), float(point[1])
        return float(point[0]), float(point[1])

    def _calculate_coupler_position(
        self,
        context: ParametricContext,
        p3_x: float,
        p3_y: float,
        p4_x: float,
        p4_y: float,
    ) -> None:
        params = context.params
        coupler_point_x = params.get("coupler_point_x", 0.0)
        coupler_point_y = params.get("coupler_point_y", 0.0)

        vec_x = p4_x - p3_x
        vec_y = p4_y - p3_y
        length = math.hypot(vec_x, vec_y)
        if length <= 0:
            params["coupler_x"], params["coupler_y"] = p3_x, p3_y
            return

        unit_x = vec_x / length
        unit_y = vec_y / length
        normal_x = -unit_y
        normal_y = unit_x

        scale = context.transform_params.get("scale", 1.0)
        offset_x = coupler_point_x * scale
        offset_y = coupler_point_y * scale

        params["coupler_x"] = p3_x + offset_x * unit_x + offset_y * normal_x
        params["coupler_y"] = p3_y + offset_x * unit_y + offset_y * normal_y

    @staticmethod
    def _set_default_4bar_parameters(params: dict[str, Any]) -> None:
        params.setdefault("anchor1_x", 400)
        params.setdefault("anchor1_y", 300)
        l1 = params.get("l1", 100)
        params.setdefault("anchor2_x", 400 + l1)
        params.setdefault("anchor2_y", 300)
        params.setdefault("crank_angle", 0)
        params.setdefault("rocker_angle", 45)
        params.setdefault("coupler_x", 450)
        params.setdefault("coupler_y", 250)

    # --- Gear ----------------------------------------------------------------
    def _setup_gear_parameters(self, context: ParametricContext) -> None:
        params = context.params
        sim_data = context.full_simulation_data
        profile = (
            physical_profile_from_params(params)
            if "physical_profile_key" in params
            else context.physical_profile
        )
        params.setdefault("physical_profile_key", profile.key)
        default_radius = self._default_gear_radius(profile)
        r1 = self._first_positive_float(
            default_radius, params.get("gear1_radius"), params.get("r1")
        )
        r2 = self._first_positive_float(
            default_radius, params.get("gear2_radius"), params.get("r2")
        )
        params["gear1_radius"] = r1
        params["gear2_radius"] = r2
        params["r1"] = r1
        params["r2"] = r2
        params.setdefault("gear1_teeth", freeform_gear_teeth_for_radius(r1, profile=profile))
        params.setdefault("gear2_teeth", freeform_gear_teeth_for_radius(r2, profile=profile))

        to_scene = context.to_scene
        if "gear_data" in sim_data and to_scene:
            self._extract_gear_positions(params, sim_data["gear_data"], to_scene)
        else:
            self._set_default_gear_positions(params)

    @staticmethod
    def _default_gear_radius(profile: PhysicalKitProfile) -> float:
        if profile.gear_presets:
            preset = profile.gear_presets[min(1, len(profile.gear_presets) - 1)]
            return float(preset.teeth) * float(profile.gear_radius_per_tooth_mm)
        return 30.0

    @staticmethod
    def _first_positive_float(default: float, *values: object) -> float:
        for value in values:
            try:
                result = float(cast(Any, value))
            except (TypeError, ValueError):
                continue
            if math.isfinite(result) and result > 0.0:
                return result
        return default

    def _extract_gear_positions(
        self,
        params: dict[str, Any],
        gear_data: Mapping[str, Any],
        to_scene: Callable[[np.ndarray], Any],
    ) -> None:
        if "gear1_centers" in gear_data and gear_data["gear1_centers"]:
            g1_scene = to_scene(np.array(gear_data["gear1_centers"][0]))
            params["gear1_x"], params["gear1_y"] = self._extract_coordinates(g1_scene)
        if "gear2_centers" in gear_data and gear_data["gear2_centers"]:
            g2_scene = to_scene(np.array(gear_data["gear2_centers"][0]))
            params["gear2_x"], params["gear2_y"] = self._extract_coordinates(g2_scene)

    @staticmethod
    def _set_default_gear_positions(params: dict[str, Any]) -> None:
        params.setdefault("gear1_x", 400)
        params.setdefault("gear1_y", 300)
        if "gear2_x" not in params:
            r1 = params.get("gear1_radius", params.get("r1", 40))
            r2 = params.get("gear2_radius", params.get("r2", 60))
            params["gear2_x"] = params["gear1_x"] + gear_center_distance(
                r1,
                r2,
                params.get("gear_clearance"),
                profile=physical_profile_from_params(params),
            )
        params.setdefault("gear2_y", params.get("gear1_y", 300))

    # --- Planetary -----------------------------------------------------------
    def _setup_planetary_gear(self, context: ParametricContext) -> None:
        params = context.params
        sim_data = context.full_simulation_data
        params.setdefault("r_sun", params.get("gear1_radius") or params.get("sun_radius", 20))
        params.setdefault("r_planet", params.get("gear2_radius") or params.get("planet_radius", 30))
        params.setdefault("arm_length", params.get("carrier_length", 15))
        params["r_sun"] = float(params["r_sun"])
        params["r_planet"] = float(max(1.0, params["r_planet"]))
        params["arm_length"] = float(max(0.0, params["arm_length"]))
        params.setdefault("gear1_radius", params.get("r_sun") or params.get("sun_radius", 20))
        params.setdefault("gear2_radius", params.get("r_planet") or params.get("planet_radius", 30))
        params["gear1_radius"] = float(params["r_sun"])
        params["gear2_radius"] = float(params["r_planet"])

        to_scene = context.to_scene
        if "gear_positions" in sim_data and to_scene:
            self._extract_planetary_positions(params, sim_data["gear_positions"], to_scene)
        else:
            self._set_default_planetary_positions(params)

    def _extract_planetary_positions(
        self,
        params: dict[str, Any],
        gear_positions: Mapping[str, Any],
        to_scene: Callable[[np.ndarray], Any],
    ) -> None:
        if "sun_centers" in gear_positions and gear_positions["sun_centers"]:
            sun_scene = to_scene(np.array(gear_positions["sun_centers"][0]))
            params["gear1_x"], params["gear1_y"] = self._extract_coordinates(sun_scene)
            params["sun_x"], params["sun_y"] = params["gear1_x"], params["gear1_y"]
        if "planet_centers" in gear_positions and gear_positions["planet_centers"]:
            planet_scene = to_scene(np.array(gear_positions["planet_centers"][0]))
            params["gear2_x"], params["gear2_y"] = self._extract_coordinates(planet_scene)
            params["planet_x"], params["planet_y"] = params["gear2_x"], params["gear2_y"]

    @staticmethod
    def _set_default_planetary_positions(params: dict[str, Any]) -> None:
        params.setdefault("sun_x", params.get("gear1_x", 400))
        params.setdefault("sun_y", params.get("gear1_y", 300))
        params["gear1_x"] = params["sun_x"]
        params["gear1_y"] = params["sun_y"]
        params.setdefault(
            "planet_x",
            params["sun_x"] + params.get("gear1_radius", 20) + params.get("gear2_radius", 30),
        )
        params.setdefault("planet_y", params["sun_y"])
        params["gear2_x"] = params["planet_x"]
        params["gear2_y"] = params["planet_y"]
