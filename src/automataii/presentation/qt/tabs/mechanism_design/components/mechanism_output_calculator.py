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

if TYPE_CHECKING:
    pass


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
        get_scene_transform: Callable[[dict], Callable | None],
    ) -> None:
        """
        Initialize calculator.

        Args:
            get_scene_transform: Callback to get scene transform function
        """
        self._get_scene_transform = get_scene_transform

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

        num_frames = len(joint_positions["p1_positions"])
        normalized_time = time / (2 * math.pi)

        # Direction correction
        reverse_direction = layer_data.get("reverse_direction", False)
        if reverse_direction:
            normalized_time = 1.0 - normalized_time

        frame_index = int(normalized_time * (num_frames - 1))
        frame_index = max(0, min(frame_index, num_frames - 1))

        # Get exact positions from dataset
        p3 = np.array(joint_positions["p3_positions"][frame_index])
        p4 = np.array(joint_positions["p4_positions"][frame_index])

        # Calculate coupler point
        coupler_point_x = params.get("coupler_point_x", 0.0)
        coupler_point_y = params.get("coupler_point_y", 0.0)

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
                    normalized_time = time / (2 * math.pi)
                    reverse_direction = layer_data.get("reverse_direction", False)
                    if reverse_direction:
                        normalized_time = 1.0 - normalized_time

                    frame_index = int(normalized_time * (num_frames - 1))
                    frame_index = max(0, min(frame_index, num_frames - 1))

                    p5 = np.array(joint_positions["p5_positions"][frame_index])
                    return to_scene_coords(p5)

        # Fallback: use key_points center if available
        key_points = layer_data.get("key_points", {})
        to_scene_coords = self._get_scene_transform(layer_data)
        if "coupler_point" in key_points and to_scene_coords:
            return to_scene_coords(np.array(key_points["coupler_point"]))

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
                    normalized_time = time / (2 * math.pi)
                    reverse_direction = layer_data.get("reverse_direction", False)
                    if reverse_direction:
                        normalized_time = 1.0 - normalized_time

                    frame_index = int(normalized_time * (num_frames - 1))
                    frame_index = max(0, min(frame_index, num_frames - 1))

                    p6 = np.array(joint_positions["p6_positions"][frame_index])
                    return to_scene_coords(p6)

        # Fallback: use key_points end_effector if available
        key_points = layer_data.get("key_points", {})
        to_scene_coords = self._get_scene_transform(layer_data)
        if "end_effector" in key_points and to_scene_coords:
            return to_scene_coords(np.array(key_points["end_effector"]))

        return None

    def _calculate_cam_output(
        self,
        params: dict,
        time: float,
        layer_data: dict,
    ) -> QPointF | None:
        """
        Calculate cam mechanism output with vertical follower (Foundry-compatible).

        Uses harmonic formula: radius = base_radius + cam_offset * cos(lobes * θ)
                                      + (cam_offset * harmonic) * cos(2 * lobes * θ)

        Returns the follower base position (where part would attach).
        """
        # Get harmonic cam parameters (Foundry-compatible)
        base_radius = params.get("base_radius", params.get("cam_radius", 60.0))
        cam_offset = params.get("eccentricity", params.get("cam_offset", 20.0))
        follower_rod_length = params.get("follower_rod_length", params.get("follower_length", 100.0))
        cam_lobes = int(params.get("cam_lobes", 1))
        profile_harmonic = params.get("profile_harmonic", 0.3)

        # Get scaling factors
        cam_scale_factor = layer_data.get('cam_scale_factor', 1.0)
        rod_len_mul = layer_data.get('rod_length_multiplier', 1.0)

        scaled_base_radius = base_radius * cam_scale_factor
        scaled_cam_offset = cam_offset * cam_scale_factor
        scaled_rod_length = follower_rod_length * rod_len_mul

        cam_to_scene = layer_data.get('cam_transform_function') or self._get_scene_transform(layer_data)
        if cam_to_scene is None:
            return None

        # Calculate contact radius at follower position using harmonic formula
        # Follower is always at theta = -π/2 in the cam frame (bottom)
        # Account for cam rotation
        cam_angle = time  # Cam rotation angle in radians
        follower_contact_theta = -math.pi / 2 - cam_angle

        primary_var = scaled_cam_offset * math.cos(cam_lobes * follower_contact_theta)
        secondary_var = (scaled_cam_offset * profile_harmonic) * math.cos(2 * cam_lobes * follower_contact_theta)
        contact_radius = scaled_base_radius + primary_var + secondary_var

        # Contact point in mechanism coordinates (always at bottom)
        contact_local = np.array([0.0, -contact_radius])
        contact_scene = cam_to_scene(contact_local)

        # Calculate scene scale for rod length conversion
        try:
            u0 = cam_to_scene(np.array([0.0, 0.0]))
            u1 = cam_to_scene(np.array([0.0, 1.0]))
            unit_scale = ((u1.x() - u0.x()) ** 2 + (u1.y() - u0.y()) ** 2) ** 0.5
        except Exception:
            unit_scale = 1.0

        rod_scene = scaled_rod_length * unit_scale

        # Follower X is fixed at cam center X
        follower_x = layer_data.get('follower_fixed_x_scene')
        if follower_x is None:
            center_scene = cam_to_scene(np.array([0.0, 0.0]))
            follower_x = center_scene.x()

        # Follower base Y (at end of rod below contact point)
        # In scene coords, Y+ is typically down, so add rod_scene
        follower_base_y = contact_scene.y() + rod_scene

        return QPointF(float(follower_x), float(follower_base_y))

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
        r1 = params.get("r1", 30)
        key_points = layer_data.get("key_points", {})

        if to_scene_coords:
            gear1_center = np.array(key_points.get("gear1_center", [0, 0]))
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
        r_sun = params.get("r_sun", 20)
        r_planet = params.get("r_planet", 30)
        arm_length = params.get("arm_length", 15)

        if to_scene_coords:
            planet_orbital_angle = time
            planet_rotation_angle = -time * (r_sun / r_planet)

            sun_center_orig = np.array([0, 0])
            planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array([
                np.cos(planet_orbital_angle),
                np.sin(planet_orbital_angle)
            ])
            tracking_point_orig = planet_center_orig + arm_length * np.array([
                np.cos(planet_rotation_angle),
                np.sin(planet_rotation_angle)
            ])

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
        coupler_point_x = params.get("coupler_point_x", 0.0) or 0.0
        coupler_point_y = params.get("coupler_point_y", 0.0) or 0.0

        if not all([l2 is not None, l3 is not None, l4 is not None, p1_coords, p2_coords]):
            return None

        p1 = np.array(p1_coords, dtype=float)
        p2 = np.array(p2_coords, dtype=float)
        p3 = p1 + np.array([l2 * math.cos(time), l2 * math.sin(time)])

        d_sq = np.sum((p2 - p3) ** 2)
        d = np.sqrt(d_sq)
        if not (abs(l3 - l4) <= d <= (l3 + l4)):
            return None

        a = (l3 ** 2 - l4 ** 2 + d_sq) / (2 * d)
        h = math.sqrt(max(0, l3 ** 2 - a ** 2))
        p3_p2_unit = (p2 - p3) / d
        midpoint = p3 + a * p3_p2_unit
        p4 = midpoint + h * np.array([-p3_p2_unit[1], p3_p2_unit[0]])

        coupler_link_vec = p4 - p3
        coupler_link_len = np.linalg.norm(coupler_link_vec)
        if np.isclose(coupler_link_len, 0):
            return None

        coupler_local_x_axis = coupler_link_vec / coupler_link_len
        coupler_local_y_axis = np.array([-coupler_local_x_axis[1], coupler_local_x_axis[0]])

        coupler_point_offset = coupler_point_x * coupler_local_x_axis + coupler_point_y * coupler_local_y_axis
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
        joint_motion_path = QPainterPath()

        try:
            mech_type = layer_data.get("type")
            params = layer_data.get("params", {})

            for i in range(num_points + 1):
                angle = (i / num_points) * 2 * math.pi
                joint_pos = self.calculate_output(mech_type, params, angle, layer_data)

                if joint_pos:
                    if i == 0:
                        joint_motion_path.moveTo(joint_pos)
                    else:
                        joint_motion_path.lineTo(joint_pos)
                else:
                    return None

            return joint_motion_path

        except Exception:
            return None
