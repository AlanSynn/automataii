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
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    pass


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

    def __init__(self) -> None:
        """Initialize parameter mapper."""
        pass

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
        if "params" not in layer_data:
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
        key_points = layer_data.get("key_points", {})

        # If explicit scene-space center already exists, keep it as authoritative.
        if "center_x" in params and "center_y" in params:
            try:
                params["center_x"] = float(params["center_x"])
                params["center_y"] = float(params["center_y"])
                return
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

        # Try to get cam center from key_points (mechanism space)
        if "cam_center" in key_points and to_scene:
            cam_center = key_points["cam_center"]
            center_scene = to_scene(np.array(cam_center))
            params["center_x"], params["center_y"] = self.extract_coordinates(center_scene)
        elif cam_position and len(cam_position) >= 2:
            # cam_position is stored in scene space by instantiation/editor flows.
            params["center_x"] = float(cam_position[0])
            params["center_y"] = float(cam_position[1])
        else:
            params["center_x"] = params.get("center_x", 400)
            params["center_y"] = params.get("center_y", 300)

    def _setup_4bar_parameters(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        to_scene: Callable | None = None,
    ) -> None:
        """Setup parameters for 4-bar linkage mechanism."""
        full_sim_data = layer_data.get("full_simulation_data", {})

        if "joint_positions" in full_sim_data:
            joint_positions = full_sim_data["joint_positions"]
            if self._has_valid_joint_positions(joint_positions):
                self._extract_4bar_positions_from_simulation(
                    layer_data, params, joint_positions, to_scene
                )
                return

        if self._extract_4bar_positions_from_key_points(layer_data, params, to_scene):
            return

        self._set_default_4bar_parameters(params)

    def _extract_4bar_positions_from_key_points(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        to_scene: Callable | None = None,
    ) -> bool:
        """Extract 4-bar positions from key_points when simulation frames are unavailable."""
        key_points = layer_data.get("key_points", {})
        p1 = key_points.get("ground_pivot_1")
        p2 = key_points.get("ground_pivot_2")

        if not (
            isinstance(p1, (list, tuple, np.ndarray))
            and len(p1) >= 2
            and isinstance(p2, (list, tuple, np.ndarray))
            and len(p2) >= 2
        ):
            return False

        # Foundry imports often store scene-space key_points without generated_path.
        use_scene_points_directly = layer_data.get("generated_path") is None or to_scene is None

        def map_point(raw: list[float] | tuple[float, float] | np.ndarray):
            if use_scene_points_directly:
                return np.array([float(raw[0]), float(raw[1])], dtype=float)
            return to_scene(np.array(raw, dtype=float))

        p1_scene = map_point(p1)
        p2_scene = map_point(p2)
        params["anchor1_x"], params["anchor1_y"] = self.extract_coordinates(p1_scene)
        params["anchor2_x"], params["anchor2_y"] = self.extract_coordinates(p2_scene)

        p3 = key_points.get("crank_end")
        if isinstance(p3, (list, tuple, np.ndarray)) and len(p3) >= 2:
            p3_scene = map_point(p3)
            p3_x, p3_y = self.extract_coordinates(p3_scene)
            params["crank_x"] = p3_x
            params["crank_y"] = p3_y
            params["crank_angle"] = math.degrees(
                math.atan2(p3_y - params["anchor1_y"], p3_x - params["anchor1_x"])
            )

        p4 = key_points.get("rocker_end")
        if isinstance(p4, (list, tuple, np.ndarray)) and len(p4) >= 2:
            p4_scene = map_point(p4)
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
        return (
            "p1_positions" in joint_positions
            and len(joint_positions["p1_positions"]) > 0
            and "p2_positions" in joint_positions
            and len(joint_positions["p2_positions"]) > 0
        )

    def _extract_4bar_positions_from_simulation(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        joint_positions: dict[str, Any],
        to_scene: Callable | None = None,
    ) -> None:
        """Extract 4-bar linkage positions from simulation data."""
        p1 = joint_positions["p1_positions"][0]
        p2 = joint_positions["p2_positions"][0]
        p3 = joint_positions.get("p3_positions", [None])[0]
        p4 = joint_positions.get("p4_positions", [None])[0]

        if to_scene:
            p1_scene = to_scene(np.array(p1))
            p2_scene = to_scene(np.array(p2))

            params["anchor1_x"], params["anchor1_y"] = self.extract_coordinates(p1_scene)
            params["anchor2_x"], params["anchor2_y"] = self.extract_coordinates(p2_scene)

            if p3 is not None:
                p3_scene = to_scene(np.array(p3))
                p3_x, p3_y = self.extract_coordinates(p3_scene)

                dx = p3_x - params["anchor1_x"]
                dy = p3_y - params["anchor1_y"]
                params["crank_angle"] = math.degrees(math.atan2(dy, dx))
                params["crank_x"] = p3_x
                params["crank_y"] = p3_y

            if p4 is not None:
                p4_scene = to_scene(np.array(p4))
                p4_x, p4_y = self.extract_coordinates(p4_scene)

                dx = p4_x - params["anchor2_x"]
                dy = p4_y - params["anchor2_y"]
                params["rocker_angle"] = math.degrees(math.atan2(dy, dx))
                params["rocker_x"] = p4_x
                params["rocker_y"] = p4_y

                if p3 is not None:
                    self._calculate_coupler_position(
                        layer_data, params, p3_x, p3_y, p4_x, p4_y
                    )
        else:
            params["anchor1_x"] = p1[0] if isinstance(p1, list | tuple) else p1
            params["anchor1_y"] = p1[1] if isinstance(p1, list | tuple) else 0
            params["anchor2_x"] = p2[0] if isinstance(p2, list | tuple) else p2
            params["anchor2_y"] = p2[1] if isinstance(p2, list | tuple) else 0
            params["crank_angle"] = 0
            params["rocker_angle"] = 45
            params["coupler_x"] = 350
            params["coupler_y"] = 250

    def extract_coordinates(self, point: Any) -> tuple[float, float]:
        """Extract x,y coordinates from point object."""
        if hasattr(point, "x"):
            return point.x(), point.y()
        elif isinstance(point, np.ndarray):
            return float(point[0]), float(point[1])
        else:
            return float(point[0]), float(point[1])

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
        coupler_point_x = params.get("coupler_point_x", 0.0)
        coupler_point_y = params.get("coupler_point_y", 0.0)

        coupler_vec_x = p4_x - p3_x
        coupler_vec_y = p4_y - p3_y
        coupler_length = math.sqrt(coupler_vec_x**2 + coupler_vec_y**2)

        if coupler_length > 0:
            coupler_unit_x = coupler_vec_x / coupler_length
            coupler_unit_y = coupler_vec_y / coupler_length
            coupler_normal_x = -coupler_unit_y
            coupler_normal_y = coupler_unit_x

            scale = layer_data.get("transform_params", {}).get("scale", 1.0)
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
        l1 = params.get("l1", 100)
        params["anchor1_x"] = params.get("anchor1_x", 400)
        params["anchor1_y"] = params.get("anchor1_y", 300)
        params["anchor2_x"] = params.get("anchor2_x", 400 + l1)
        params["anchor2_y"] = params.get("anchor2_y", 300)
        params["crank_angle"] = params.get("crank_angle", 0)
        params["rocker_angle"] = params.get("rocker_angle", 45)
        params["coupler_x"] = params.get("coupler_x", 450)
        params["coupler_y"] = params.get("coupler_y", 250)

    def _setup_gear_parameters(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
        to_scene: Callable | None = None,
    ) -> None:
        """Setup parameters for gear mechanism."""
        full_sim_data = layer_data.get("full_simulation_data", {})

        if "gear1_radius" not in params and "r1" in params:
            params["gear1_radius"] = self._mech_radius_to_scene(float(params["r1"]), to_scene)
        elif "gear1_radius" in params and "r1" not in params:
            params["r1"] = float(params["gear1_radius"])

        if "gear2_radius" not in params and "r2" in params:
            params["gear2_radius"] = self._mech_radius_to_scene(float(params["r2"]), to_scene)
        elif "gear2_radius" in params and "r2" not in params:
            params["r2"] = float(params["gear2_radius"])

        if "gear_data" in full_sim_data and to_scene:
            self._extract_gear_positions_from_simulation(
                params, full_sim_data, to_scene
            )
        else:
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
            ox, oy = self.extract_coordinates(origin)
            ex, ey = self.extract_coordinates(edge)
            scene_radius = math.hypot(ex - ox, ey - oy)
            return float(scene_radius) if scene_radius > 0 else float(mech_radius)
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
        gear_data = full_sim_data["gear_data"]

        if "gear1_centers" in gear_data and len(gear_data["gear1_centers"]) > 0:
            g1_center = gear_data["gear1_centers"][0]
            g1_scene = to_scene(np.array(g1_center))
            params["gear1_x"], params["gear1_y"] = self.extract_coordinates(g1_scene)

        if "gear2_centers" in gear_data and len(gear_data["gear2_centers"]) > 0:
            g2_center = gear_data["gear2_centers"][0]
            g2_scene = to_scene(np.array(g2_center))
            params["gear2_x"], params["gear2_y"] = self.extract_coordinates(g2_scene)

    def _set_default_gear_positions(self, params: dict[str, Any]) -> None:
        """Set default positions for gear mechanism."""
        if "gear1_x" not in params:
            params["gear1_x"] = 400
        if "gear1_y" not in params:
            params["gear1_y"] = 300
        if "gear2_x" not in params:
            r1 = params.get("gear1_radius", params.get("r1", 40))
            r2 = params.get("gear2_radius", params.get("r2", 60))
            params["gear2_x"] = params["gear1_x"] + r1 + r2 + 2
        if "gear2_y" not in params:
            params["gear2_y"] = params["gear1_y"]

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
        full_sim_data = layer_data.get("full_simulation_data", {})

        # Setup r_sun (PlanetaryGearEditor expects this name)
        if "r_sun" not in params:
            if "sun_radius" in params:
                params["r_sun"] = params["sun_radius"]
            elif "gear1_radius" in params:
                params["r_sun"] = params["gear1_radius"]
            else:
                params["r_sun"] = 20.0
        params["r_sun"] = float(params["r_sun"])
        # Also set gear1_radius for backwards compatibility
        params["gear1_radius"] = float(params["r_sun"])

        # Setup r_planet (PlanetaryGearEditor expects this name)
        if "r_planet" not in params:
            if "planet_radius" in params:
                params["r_planet"] = params["planet_radius"]
            elif "gear2_radius" in params:
                params["r_planet"] = params["gear2_radius"]
            else:
                params["r_planet"] = 30.0
        params["r_planet"] = float(max(1.0, params["r_planet"]))
        # Also set gear2_radius for backwards compatibility
        params["gear2_radius"] = float(params["r_planet"])

        # Setup arm_length
        if "arm_length" not in params:
            params["arm_length"] = params.get("carrier_length", 15.0)
        params["arm_length"] = float(max(0.0, params["arm_length"]))

        if "gear_positions" in full_sim_data and to_scene:
            self._extract_planetary_positions_from_simulation(
                params, full_sim_data, to_scene
            )
        elif self._extract_planetary_positions_from_key_points(
            layer_data, params, to_scene
        ):
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
        gear_pos = full_sim_data["gear_positions"]

        if "sun_centers" in gear_pos and len(gear_pos["sun_centers"]) > 0:
            sun_center = gear_pos["sun_centers"][0]
            sun_scene = to_scene(np.array(sun_center))
            x, y = self.extract_coordinates(sun_scene)
            # PlanetaryGearEditor expects sun_x, sun_y
            params["sun_x"], params["sun_y"] = x, y
            # Also set gear1_x, gear1_y for backwards compatibility
            params["gear1_x"], params["gear1_y"] = x, y

        if "planet_centers" in gear_pos and len(gear_pos["planet_centers"]) > 0:
            planet_center = gear_pos["planet_centers"][0]
            planet_scene = to_scene(np.array(planet_center))
            x, y = self.extract_coordinates(planet_scene)
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
        key_points = layer_data.get("key_points", {})
        sun_center = key_points.get("sun_center")
        if not (
            isinstance(sun_center, (list, tuple, np.ndarray))
            and len(sun_center) >= 2
        ):
            return False

        use_scene_points_directly = layer_data.get("generated_path") is None or to_scene is None

        def map_point(raw: list[float] | tuple[float, float] | np.ndarray):
            if use_scene_points_directly:
                return np.array([float(raw[0]), float(raw[1])], dtype=float)
            return to_scene(np.array(raw, dtype=float))

        sun_scene = map_point(sun_center)
        sun_x, sun_y = self.extract_coordinates(sun_scene)
        params["sun_x"], params["sun_y"] = sun_x, sun_y
        params["gear1_x"], params["gear1_y"] = sun_x, sun_y

        planet_center = key_points.get("planet_center")
        if isinstance(planet_center, (list, tuple, np.ndarray)) and len(planet_center) >= 2:
            planet_scene = map_point(planet_center)
            planet_x, planet_y = self.extract_coordinates(planet_scene)
        else:
            planet_x = float(sun_x) + float(params.get("r_sun", 20.0)) + float(params.get("r_planet", 30.0))
            planet_y = float(sun_y)

        params["planet_x"], params["planet_y"] = planet_x, planet_y
        params["gear2_x"], params["gear2_y"] = planet_x, planet_y
        return True

    def _set_default_planetary_positions(self, params: dict[str, Any]) -> None:
        """Set default positions for planetary gear mechanism.

        Sets both sun_x/sun_y (for PlanetaryGearEditor) and gear1_x/gear1_y (for compatibility).
        """
        # Set sun center position (PlanetaryGearEditor expects sun_x, sun_y)
        if "sun_x" not in params:
            params["sun_x"] = params.get("gear1_x", 400.0)
        if "sun_y" not in params:
            params["sun_y"] = params.get("gear1_y", 300.0)
        # Also set gear1_x/gear1_y for backwards compatibility
        params["gear1_x"] = params["sun_x"]
        params["gear1_y"] = params["sun_y"]

        # Calculate planet position based on sun and planet radii
        r_sun = params.get("r_sun", 20.0)
        r_planet = params.get("r_planet", 30.0)

        if "planet_x" not in params:
            params["planet_x"] = params["sun_x"] + r_sun + r_planet
        if "planet_y" not in params:
            params["planet_y"] = params["sun_y"]
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
        transform_params = layer_data.get("transform_params", {})
        scale = float(transform_params.get("scale", 1.0))
        user_scale = 100.0

        if path_converter:
            try:
                user_path_np = path_converter(layer_data.get("generated_path"))
                if user_path_np is not None and len(user_path_np) > 0:
                    bbox = np.max(user_path_np, axis=0) - np.min(user_path_np, axis=0)
                    user_scale = float(np.max(bbox) / 2.0) if np.max(bbox) > 0 else 100.0
                    if user_scale < 10 or user_scale > 10000:
                        user_scale = float(np.clip(user_scale, 50, 1000))
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

        return TransformConfig(
            scale=scale,
            user_scale=user_scale,
            offset_x=float(transform_params.get("offset_x", 0.0)),
            offset_y=float(transform_params.get("offset_y", 0.0)),
        )

    def scene_to_mech_length(
        self,
        value: float,
        config: TransformConfig,
    ) -> float:
        """Convert scene length to mechanism length."""
        return float(value) * (config.scale / config.user_scale)

    def mech_to_scene_length(
        self,
        value: float,
        config: TransformConfig,
    ) -> float:
        """Convert mechanism length to scene length."""
        if config.scale == 0:
            return float(value)
        return float(value) * (config.user_scale / config.scale)
