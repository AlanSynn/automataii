"""
Mechanism Output Calculator - Calculate mechanism positions for animation.

Extracted from MechanismDesignTab. Handles all mechanism output calculations
for 4-bar, cam, gear, and planetary gear mechanisms.

Design Pattern: Strategy (mechanism-type-specific calculations)
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

from automataii.presentation.qt.mechanism_parameter_utils import (
    finite_float as _finite_float,
)
from automataii.presentation.qt.mechanism_parameter_utils import (
    finite_param as _finite_param,
)
from automataii.presentation.qt.mechanism_parameter_utils import (
    positive_finite_float as _positive_finite_float,
)
from automataii.presentation.qt.mechanism_parameter_utils import (
    positive_finite_param as _positive_finite_param,
)
from automataii.presentation.qt.tabs.cam_geometry import (
    cam_contact_local_from_profile,
    cam_contact_local_from_rotated_profile,
    cam_follower_base_scene,
    cam_motion_angle,
    cam_scene_unit_scale,
)

if TYPE_CHECKING:
    pass


SceneTransform = Callable[[np.ndarray], QPointF]


def _point_array(raw: object) -> np.ndarray | None:
    try:
        point = np.asarray(raw, dtype=float)
    except (TypeError, ValueError):
        return None
    if point.ndim != 1 or len(point) < 2:
        return None
    point = point[:2]
    if not bool(np.isfinite(point).all()):
        return None
    return point


def _position_rows(raw: object) -> np.ndarray | None:
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


def _bounded_frame_index(
    time: float, num_frames: int, reverse_direction: bool = False
) -> int | None:
    if num_frames <= 0 or not math.isfinite(time):
        return None

    normalized_time = time / (2 * math.pi)
    if reverse_direction:
        normalized_time = 1.0 - normalized_time

    frame_index = int(normalized_time * (num_frames - 1))
    return max(0, min(frame_index, num_frames - 1))


def _finite_qpoint(point: QPointF) -> bool:
    return math.isfinite(point.x()) and math.isfinite(point.y())


def _is_foundry_scene_layer(layer_data: dict) -> bool:
    return (
        str(layer_data.get("source", "")).lower() == "foundry"
        and str(layer_data.get("coordinate_space", "")).lower() == "scene"
    )


def _is_initial_phase(time: float) -> bool:
    period = 2.0 * math.pi
    phase = math.fmod(time, period)
    if phase < 0:
        phase += period
    return math.isclose(phase, 0.0, abs_tol=1e-9) or math.isclose(
        phase,
        period,
        abs_tol=1e-9,
    )


def _scene_key_point(layer_data: dict, key: str) -> QPointF | None:
    key_points = layer_data.get("key_points", {})
    if not isinstance(key_points, dict):
        return None
    point = _point_array(key_points.get(key))
    if point is None:
        return None
    return QPointF(float(point[0]), float(point[1]))


class MechanismOutputCalculator:
    """
    Calculates mechanism output positions for animation.

    Responsibilities:
    - Extract key points from simulation data
    - Calculate mechanism output for all mechanism types
    - Generate joint motion paths

    Time Complexity: O(1) per frame for indexed lookups
    """

    def __init__(
        self,
        get_scene_transform: Callable[[dict], SceneTransform | None],
    ) -> None:
        """
        Initialize calculator.

        Args:
            get_scene_transform: Callback to get scene transform function
        """
        self._get_scene_transform = get_scene_transform

    @staticmethod
    def _normalize_output_mode(mechanism_type: str, mode: object) -> str | None:
        if not isinstance(mode, str) or not mode:
            return None

        normalized = mode.strip().lower()
        if mechanism_type == "4_bar_linkage":
            return {
                "joint_a": "joint_a",
                "a": "joint_a",
                "input": "joint_a",
                "joint_b": "joint_b",
                "b": "joint_b",
                "output": "joint_b",
                "coupler": "coupler",
                "coupler_point": "coupler",
            }.get(normalized)

        if mechanism_type == "cam":
            return {
                "follower_base": "follower_base",
                "follower_end": "follower_base",
                "contact_point": "contact_point",
                "contact": "contact_point",
            }.get(normalized)

        return normalized

    def extract_key_points_from_simulation(
        self,
        full_sim_data: dict,
        mechanism_type: str,
    ) -> dict:
        """
        Extract key_points from full_simulation_data.

        Args:
            full_sim_data: Full simulation data from mechanism generation
            mechanism_type: Type of mechanism

        Returns:
            Dictionary of key point positions

        Time Complexity: O(1)
        """
        key_points = {}

        try:
            if mechanism_type == "4_bar_linkage" and "joint_positions" in full_sim_data:
                joint_pos = full_sim_data["joint_positions"]
                if "p1_positions" in joint_pos and len(joint_pos["p1_positions"]) > 0:
                    key_points["ground_pivot_1"] = joint_pos["p1_positions"][0]
                if "p2_positions" in joint_pos and len(joint_pos["p2_positions"]) > 0:
                    key_points["ground_pivot_2"] = joint_pos["p2_positions"][0]
                if "p3_positions" in joint_pos and len(joint_pos["p3_positions"]) > 0:
                    key_points["crank_end"] = joint_pos["p3_positions"][0]
                if "p4_positions" in joint_pos and len(joint_pos["p4_positions"]) > 0:
                    key_points["rocker_end"] = joint_pos["p4_positions"][0]

            elif mechanism_type == "cam" and "cam_data" in full_sim_data:
                cam_data = full_sim_data["cam_data"]
                if "cam_centers" in cam_data and len(cam_data["cam_centers"]) > 0:
                    key_points["cam_center"] = cam_data["cam_centers"][0]
                if "follower_y_positions" in cam_data and len(cam_data["follower_y_positions"]) > 0:
                    key_points["follower_position"] = [0, cam_data["follower_y_positions"][0]]

            elif mechanism_type in ["gear", "planetary_gear"] and "gear_positions" in full_sim_data:
                gear_pos = full_sim_data["gear_positions"]
                if "sun_centers" in gear_pos and len(gear_pos["sun_centers"]) > 0:
                    key_points["sun_center"] = gear_pos["sun_centers"][0]
                if "planet_centers" in gear_pos and len(gear_pos["planet_centers"]) > 0:
                    key_points["planet_center"] = gear_pos["planet_centers"][0]

            elif mechanism_type == "simple_gear" and "gear_data" in full_sim_data:
                gear_data = full_sim_data["gear_data"]
                if "gear1_centers" in gear_data and len(gear_data["gear1_centers"]) > 0:
                    key_points["gear1_center"] = gear_data["gear1_centers"][0]
                if "gear2_centers" in gear_data and len(gear_data["gear2_centers"]) > 0:
                    key_points["gear2_center"] = gear_data["gear2_centers"][0]

        except (KeyError, IndexError, TypeError):
            key_points = {"center": [0, 0], "reference": [50, 0]}

        return key_points

    def calculate_output(
        self,
        mech_type: str,
        params: dict,
        time: float,
        layer_data: dict,
    ) -> QPointF | None:
        """
        Calculate mechanism output point.

        Uses dataset's joint positions for consistency with visuals.

        Args:
            mech_type: Mechanism type identifier
            params: Mechanism parameters
            time: Animation time (radians)
            layer_data: Layer data with simulation info

        Returns:
            Output position in scene coordinates, or None if calculation fails

        Time Complexity: O(1) for indexed lookup
        """
        full_sim_data = layer_data.get("full_simulation_data", {})
        if not math.isfinite(_finite_float(time, math.nan)):
            return None

        if mech_type == "4_bar_linkage":
            return self._calculate_4bar_output(params, time, layer_data, full_sim_data)
        elif mech_type == "5_bar_linkage":
            return self._calculate_5bar_output(params, time, layer_data, full_sim_data)
        elif mech_type == "6_bar_linkage":
            return self._calculate_6bar_output(params, time, layer_data, full_sim_data)
        elif mech_type == "cam":
            return self._calculate_cam_output(params, time, layer_data)
        elif mech_type == "gear":
            return self._calculate_gear_output(params, time, layer_data, full_sim_data)
        elif mech_type == "planetary_gear":
            return self._calculate_planetary_gear_output(params, time, layer_data, full_sim_data)
        else:
            return self._calculate_manual_output(mech_type, params, time, layer_data)

    def _calculate_4bar_output(
        self,
        params: dict,
        time: float,
        layer_data: dict,
        full_sim_data: dict,
    ) -> QPointF | None:
        """Calculate 4-bar linkage output using dataset positions."""
        if "joint_positions" not in full_sim_data:
            return self._calculate_manual_output("4_bar_linkage", params, time, layer_data)

        joint_positions = full_sim_data["joint_positions"]
        to_scene_coords = self._get_scene_transform(layer_data)

        if "p1_positions" not in joint_positions or not to_scene_coords:
            return None

        p3_positions = _position_rows(joint_positions.get("p3_positions"))
        p4_positions = _position_rows(joint_positions.get("p4_positions"))
        if p3_positions is None or p4_positions is None:
            return self._calculate_manual_output("4_bar_linkage", params, time, layer_data)

        num_frames = min(len(p3_positions), len(p4_positions))
        frame_index = _bounded_frame_index(
            time,
            num_frames,
            reverse_direction=bool(layer_data.get("reverse_direction", False)),
        )
        if frame_index is None:
            return None

        # Get exact positions from dataset
        p3 = p3_positions[frame_index]
        p4 = p4_positions[frame_index]

        output_mode = self._normalize_output_mode(
            "4_bar_linkage",
            params.get("output_point_mode"),
        )
        if output_mode == "joint_a":
            return to_scene_coords(p3)
        if output_mode == "joint_b":
            return to_scene_coords(p4)

        # Calculate coupler point
        # Support both param name conventions: coupler_point_x/y (internal) and p_x/p_y (JSON/dataset)
        coupler_point_x = _finite_param(params, "coupler_point_x", "p_x", default=0.0)
        coupler_point_y = _finite_param(params, "coupler_point_y", "p_y", default=0.0)

        coupler_vec = p4 - p3
        coupler_length = np.linalg.norm(coupler_vec)
        if coupler_length > 0:
            coupler_unit = coupler_vec / coupler_length
            coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
            p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
        else:
            p_coupler = p3

        return to_scene_coords(p_coupler)

    def _calculate_5bar_output(
        self,
        params: dict,
        time: float,
        layer_data: dict,
        full_sim_data: dict,
    ) -> QPointF | None:
        """Calculate 5-bar linkage output using simulation data or fallback."""
        # Try to use pre-computed simulation data
        if "joint_positions" in full_sim_data:
            joint_positions = full_sim_data["joint_positions"]
            to_scene_coords = self._get_scene_transform(layer_data)

            # 5-bar uses p5 (coupler point) if available
            if "p5_positions" in joint_positions and to_scene_coords:
                num_frames = len(joint_positions["p5_positions"])
                if num_frames > 0:
                    reverse_direction = layer_data.get("reverse_direction", False)

                    frame_index = _bounded_frame_index(time, num_frames, reverse_direction)
                    if frame_index is None:
                        return None

                    p5 = _point_array(joint_positions["p5_positions"][frame_index])
                    if p5 is None:
                        return None
                    return to_scene_coords(p5)

        # Fallback: use key_points center if available
        key_points = layer_data.get("key_points", {})
        to_scene_coords = self._get_scene_transform(layer_data)
        if "coupler_point" in key_points and to_scene_coords:
            coupler_point = _point_array(key_points["coupler_point"])
            if coupler_point is not None:
                return to_scene_coords(coupler_point)

        return None

    def _calculate_6bar_output(
        self,
        params: dict,
        time: float,
        layer_data: dict,
        full_sim_data: dict,
    ) -> QPointF | None:
        """Calculate 6-bar linkage output using simulation data or fallback."""
        # Try to use pre-computed simulation data
        if "joint_positions" in full_sim_data:
            joint_positions = full_sim_data["joint_positions"]
            to_scene_coords = self._get_scene_transform(layer_data)

            # 6-bar uses p6 (end effector point) if available
            if "p6_positions" in joint_positions and to_scene_coords:
                num_frames = len(joint_positions["p6_positions"])
                if num_frames > 0:
                    reverse_direction = layer_data.get("reverse_direction", False)

                    frame_index = _bounded_frame_index(time, num_frames, reverse_direction)
                    if frame_index is None:
                        return None

                    p6 = _point_array(joint_positions["p6_positions"][frame_index])
                    if p6 is None:
                        return None
                    return to_scene_coords(p6)

        # Fallback: use key_points end_effector if available
        key_points = layer_data.get("key_points", {})
        to_scene_coords = self._get_scene_transform(layer_data)
        if "end_effector" in key_points and to_scene_coords:
            end_effector = _point_array(key_points["end_effector"])
            if end_effector is not None:
                return to_scene_coords(end_effector)

        return None

    def _calculate_cam_output(
        self,
        params: dict,
        time: float,
        layer_data: dict,
    ) -> QPointF | None:
        """
        Calculate cam mechanism output with vertical follower.

        Uses pre-computed cam profile from factory when available,
        falling back to harmonic formula for compatibility.

        Returns selected cam output point.
        """
        output_mode = self._normalize_output_mode(
            "cam",
            params.get("output_point_mode"),
        )
        if _is_foundry_scene_layer(layer_data) and _is_initial_phase(time):
            if output_mode == "contact_point":
                contact_point = _scene_key_point(layer_data, "contact_point")
                if contact_point is not None:
                    return contact_point
            else:
                follower_base = (
                    _scene_key_point(layer_data, "follower_base")
                    or _scene_key_point(layer_data, "follower_end")
                    or _scene_key_point(layer_data, "follower_position")
                )
                if follower_base is not None:
                    return follower_base

        # Get rod length params
        follower_rod_length = _positive_finite_param(
            params,
            "follower_rod_length",
            "follower_length",
            default=40.0,
        )
        rod_len_mul = _positive_finite_float(layer_data.get("rod_length_multiplier", 1.0), 1.0)
        scaled_rod_length = follower_rod_length * rod_len_mul

        cam_to_scene = layer_data.get("cam_transform_function") or self._get_scene_transform(
            layer_data
        )
        if cam_to_scene is None:
            return None

        reverse_direction = layer_data.get(
            "reverse_direction",
            params.get("reverse_direction", False),
        )
        cam_angle = cam_motion_angle(time, reverse_direction)

        # Priority: Use pre-computed cam profile from factory
        cam_points_local = layer_data.get("cam_points_local")
        cam_profile = _position_rows(cam_points_local) if cam_points_local is not None else None

        if cam_profile is not None:
            contact_local = cam_contact_local_from_profile(cam_profile, cam_angle)
        else:
            # Fallback: Use harmonic formula
            base_radius = _positive_finite_param(params, "base_radius", "cam_radius", default=60.0)
            cam_offset = max(
                0.0,
                _finite_param(params, "eccentricity", "cam_offset", default=20.0),
            )
            cam_lobes = max(1, int(_positive_finite_param(params, "cam_lobes", default=1.0)))
            profile_harmonic = _finite_param(params, "profile_harmonic", default=0.3)

            cam_scale_factor = _positive_finite_float(layer_data.get("cam_scale_factor", 1.0), 1.0)

            scaled_base_radius = base_radius * cam_scale_factor
            scaled_cam_offset = cam_offset * cam_scale_factor

            thetas = np.linspace(0, 2 * math.pi, 72, endpoint=False)
            primary_var = scaled_cam_offset * np.cos(cam_lobes * thetas)
            secondary_var = (scaled_cam_offset * profile_harmonic) * np.cos(2 * cam_lobes * thetas)
            radii = scaled_base_radius + primary_var + secondary_var
            radii = np.maximum(radii, max(1e-6, scaled_base_radius * 0.05))
            rotated_thetas = thetas + cam_angle
            raw_points = np.column_stack(
                [radii * np.cos(rotated_thetas), radii * np.sin(rotated_thetas)]
            )
            contact_local = cam_contact_local_from_rotated_profile(raw_points)

        if not bool(np.isfinite(contact_local).all()):
            return None

        contact_scene = cam_to_scene(contact_local)

        # Calculate scene scale for rod length conversion
        unit_scale = cam_scene_unit_scale(cam_to_scene)

        # Follower X is fixed at cam center X
        follower_x = _finite_float(layer_data.get("follower_fixed_x_scene"), math.nan)
        if not math.isfinite(follower_x):
            center_scene = cam_to_scene(np.array([0.0, 0.0]))
            follower_x = center_scene.x()

        if output_mode == "contact_point":
            return QPointF(float(contact_scene.x()), float(contact_scene.y()))

        follower_base = cam_follower_base_scene(
            contact_scene, scaled_rod_length, unit_scale, fixed_x=follower_x
        )
        return QPointF(float(follower_base.x()), float(follower_base.y()))

    def _calculate_gear_output(
        self,
        params: dict,
        time: float,
        layer_data: dict,
        full_sim_data: dict,
    ) -> QPointF | None:
        """Calculate gear mechanism output using tracking points."""
        gear_data = full_sim_data.get("gear_data", {})
        to_scene_coords = self._get_scene_transform(layer_data)

        if gear_data and "tracking_points" in gear_data and to_scene_coords:
            tracking_points = gear_data["tracking_points"]
            num_frames = len(tracking_points)
            if num_frames > 0:
                normalized_time = (time / (2 * np.pi)) % 1.0
                frame_index = int(normalized_time * (num_frames - 1))
                frame_index = max(0, min(frame_index, num_frames - 1))

                tracking_point = np.array(tracking_points[frame_index])
                return to_scene_coords(tracking_point)

        # Fallback to manual calculation
        r1 = _positive_finite_param(params, "r1", "gear1_radius", default=30.0)
        key_points = layer_data.get("key_points", {})

        if to_scene_coords:
            gear1_center = _point_array(key_points.get("gear1_center"))
            if gear1_center is None:
                gear1_center = np.array([0.0, 0.0])
            theta1 = time
            output_point_orig = gear1_center + np.array([r1 * np.cos(theta1), r1 * np.sin(theta1)])
            return to_scene_coords(output_point_orig)

        return None

    def _calculate_planetary_gear_output(
        self,
        params: dict,
        time: float,
        layer_data: dict,
        full_sim_data: dict,
    ) -> QPointF | None:
        """Calculate planetary gear output using tracking points."""
        gear_positions = full_sim_data.get("gear_positions", {})
        to_scene_coords = self._get_scene_transform(layer_data)

        if gear_positions and "tracking_points" in gear_positions and to_scene_coords:
            tracking_points = gear_positions["tracking_points"]
            num_frames = len(tracking_points)
            if num_frames > 0:
                normalized_time = (time / (2 * np.pi)) % 1.0
                frame_index = int(normalized_time * (num_frames - 1))
                frame_index = max(0, min(frame_index, num_frames - 1))

                tracking_point = np.array(tracking_points[frame_index])
                return to_scene_coords(tracking_point)

        # Fallback calculation
        r_sun = _positive_finite_param(params, "r_sun", "gear1_radius", default=20.0)
        r_planet = _positive_finite_param(params, "r_planet", "gear2_radius", default=30.0)
        arm_length = _positive_finite_param(params, "arm_length", default=15.0)
        key_points = layer_data.get("key_points", {})

        if to_scene_coords:
            planet_orbital_angle = time
            planet_rotation_angle = -time * (r_sun / r_planet)

            sun_center = _point_array(key_points.get("sun_center"))
            if sun_center is not None:
                sun_center_orig = sun_center
            elif "m_sun_x" in params and "m_sun_y" in params:
                sun_center_orig = np.array(
                    [
                        _finite_param(params, "m_sun_x", default=0.0),
                        _finite_param(params, "m_sun_y", default=0.0),
                    ],
                    dtype=float,
                )
            elif "sun_x" in params and "sun_y" in params:
                sun_center_orig = np.array(
                    [
                        _finite_param(params, "sun_x", default=0.0),
                        _finite_param(params, "sun_y", default=0.0),
                    ],
                    dtype=float,
                )
            elif "gear1_x" in params and "gear1_y" in params:
                sun_center_orig = np.array(
                    [
                        _finite_param(params, "gear1_x", default=0.0),
                        _finite_param(params, "gear1_y", default=0.0),
                    ],
                    dtype=float,
                )
            else:
                sun_center_orig = np.array([0.0, 0.0], dtype=float)
            planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array(
                [np.cos(planet_orbital_angle), np.sin(planet_orbital_angle)]
            )
            tracking_point_orig = planet_center_orig + arm_length * np.array(
                [np.cos(planet_rotation_angle), np.sin(planet_rotation_angle)]
            )

            return to_scene_coords(tracking_point_orig)

        return None

    def _calculate_manual_output(
        self,
        mech_type: str,
        params: dict,
        time: float,
        layer_data: dict,
    ) -> QPointF | None:
        """Manual calculation fallback for 4-bar linkage."""
        if mech_type != "4_bar_linkage":
            return None

        key_points = layer_data.get("key_points")
        if not key_points or not params:
            return None

        l2, l3, l4 = params.get("l2"), params.get("l3"), params.get("l4")
        p1_coords = key_points.get("ground_pivot_1")
        p2_coords = key_points.get("ground_pivot_2")
        # Support both param name conventions: coupler_point_x/y (internal) and p_x/p_y (JSON/dataset)
        coupler_point_x = _finite_param(params, "coupler_point_x", "p_x", default=0.0)
        coupler_point_y = _finite_param(params, "coupler_point_y", "p_y", default=0.0)

        l2 = _positive_finite_float(l2, math.nan)
        l3 = _positive_finite_float(l3, math.nan)
        l4 = _positive_finite_float(l4, math.nan)
        p1 = _point_array(p1_coords)
        p2 = _point_array(p2_coords)
        if not all(math.isfinite(length) for length in (l2, l3, l4)) or p1 is None or p2 is None:
            return None

        p3 = p1 + np.array([l2 * math.cos(time), l2 * math.sin(time)])

        d_sq = np.sum((p2 - p3) ** 2)
        d = np.sqrt(d_sq)
        if not math.isfinite(float(d)) or np.isclose(d, 0.0):
            return None
        if not (abs(l3 - l4) <= d <= (l3 + l4)):
            return None

        a = (l3**2 - l4**2 + d_sq) / (2 * d)
        h = math.sqrt(max(0, l3**2 - a**2))
        p3_p2_unit = (p2 - p3) / d
        midpoint = p3 + a * p3_p2_unit
        p4 = midpoint + h * np.array([-p3_p2_unit[1], p3_p2_unit[0]])

        coupler_link_vec = p4 - p3
        coupler_link_len = np.linalg.norm(coupler_link_vec)
        if np.isclose(coupler_link_len, 0):
            return None

        coupler_local_x_axis = coupler_link_vec / coupler_link_len
        coupler_local_y_axis = np.array([-coupler_local_x_axis[1], coupler_local_x_axis[0]])

        coupler_point_offset = (
            coupler_point_x * coupler_local_x_axis + coupler_point_y * coupler_local_y_axis
        )
        output_point_orig = p3 + coupler_point_offset

        to_scene_coords = self._get_scene_transform(layer_data)
        if to_scene_coords:
            return to_scene_coords(output_point_orig)

        return None

    def generate_joint_motion_path(
        self,
        layer_data: dict,
        num_points: int = 180,
    ) -> QPainterPath | None:
        """
        Generate motion path for a skeleton joint.

        Args:
            layer_data: Layer data with mechanism info
            num_points: Number of points for path resolution

        Returns:
            QPainterPath of joint motion, or None if generation fails

        Time Complexity: O(n) where n = num_points
        """
        if isinstance(num_points, bool) or not isinstance(num_points, int) or num_points <= 0:
            return None

        joint_motion_path = QPainterPath()

        try:
            mech_type = layer_data.get("type")
            params = layer_data.get("params", {})
            if not isinstance(mech_type, str):
                return None
            if not isinstance(params, dict):
                params = {}

            for i in range(num_points + 1):
                angle = (i / num_points) * 2 * math.pi
                joint_pos = self.calculate_output(mech_type, params, angle, layer_data)

                if joint_pos is not None and _finite_qpoint(joint_pos):
                    if i == 0:
                        joint_motion_path.moveTo(joint_pos)
                    else:
                        joint_motion_path.lineTo(joint_pos)
                else:
                    return None

            return joint_motion_path

        except Exception:
            return None
