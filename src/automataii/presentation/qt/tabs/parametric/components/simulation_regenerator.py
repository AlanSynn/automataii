"""
Simulation Regenerator - Mechanism simulation regeneration logic.

Extracted from ParametricEditingManager. Handles regenerating
mechanism simulations when parameters change.

Design Pattern: Service (stateless computation)
"""
from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from automataii.presentation.qt.mechanism_parameter_utils import (
    finite_float,
    positive_finite_float,
)


class SimulationRegenerator:
    """
    Regenerates mechanism simulations from parameters.

    Responsibilities:
    - Regenerate 4-bar, 5-bar, 6-bar linkage simulations
    - Regenerate gear and planetary gear simulations
    - Regenerate cam simulations
    - Solve geometric intersection problems

    Time Complexity: O(n) where n = number of simulation steps
    """

    # Default simulation parameters
    DEFAULT_STEPS = 360
    DEFAULT_DURATION_MS = 2000

    def regenerate_4bar(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Regenerate 4-bar linkage simulation.

        Args:
            layer_data: Mechanism layer data
            params: Mechanism parameters

        Returns:
            Updated layer data with new simulation, or None on failure
        """
        try:
            # Get joint positions
            O0 = np.array(params.get("O0", [0, 0]), dtype=float)
            O1 = np.array(params.get("O1", [100, 0]), dtype=float)
            A = np.array(params.get("A", [30, -50]), dtype=float)
            B = np.array(params.get("B", [70, -50]), dtype=float)

            # Calculate link lengths
            L1 = float(np.linalg.norm(A - O0))  # Crank
            L2 = float(np.linalg.norm(B - A))  # Coupler
            L3 = float(np.linalg.norm(B - O1))  # Rocker
            L4 = float(np.linalg.norm(O1 - O0))  # Ground

            # Validate mechanism can be simulated
            if L1 <= 0 or L2 <= 0 or L3 <= 0 or L4 <= 0:
                logging.warning("Invalid link lengths for 4-bar simulation")
                return None

            # Generate simulation frames
            frames = []
            num_steps = params.get("simulation_steps", self.DEFAULT_STEPS)
            initial_angle = math.atan2(A[1] - O0[1], A[0] - O0[0])

            for i in range(num_steps):
                theta = initial_angle + (2 * math.pi * i / num_steps)

                # Calculate crank end position
                A_new = O0 + L1 * np.array([math.cos(theta), math.sin(theta)])

                # Solve for coupler-rocker joint using circle intersection
                B_new = self._solve_circle_intersection(
                    A_new, L2, O1, L3
                )

                if B_new is None:
                    continue

                frames.append({
                    "angle": math.degrees(theta),
                    "positions": {
                        "O0": O0.tolist(),
                        "O1": O1.tolist(),
                        "A": A_new.tolist(),
                        "B": B_new.tolist(),
                    },
                })

            if not frames:
                return None

            # Update layer data
            layer_data["simulation"] = {
                "frames": frames,
                "duration_ms": params.get("duration_ms", self.DEFAULT_DURATION_MS),
                "type": "4bar",
            }

            return layer_data

        except Exception as e:
            logging.error(f"SimulationRegenerator: 4-bar regeneration failed: {e}")
            return None

    def regenerate_5bar(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Regenerate 5-bar linkage simulation."""
        try:
            # 5-bar has two DOF - simplified single-input simulation
            O0 = np.array(params.get("O0", [0, 0]), dtype=float)
            O1 = np.array(params.get("O1", [100, 0]), dtype=float)
            A = np.array(params.get("A", [30, -50]), dtype=float)
            B = np.array(params.get("B", [70, -50]), dtype=float)
            C = np.array(params.get("C", [50, -80]), dtype=float)

            L1 = float(np.linalg.norm(A - O0))
            L2 = float(np.linalg.norm(B - A))
            L3 = float(np.linalg.norm(C - B))
            L4 = float(np.linalg.norm(C - O1))

            frames = []
            num_steps = params.get("simulation_steps", self.DEFAULT_STEPS)
            initial_angle = math.atan2(A[1] - O0[1], A[0] - O0[0])

            for i in range(num_steps):
                theta = initial_angle + (2 * math.pi * i / num_steps)
                A_new = O0 + L1 * np.array([math.cos(theta), math.sin(theta)])

                # Simplified: keep B relative to A, solve for C
                ba_norm = float(np.linalg.norm(B - A))
                direction = (B - A) / ba_norm if ba_norm > 0 else np.array([1, 0])
                B_new = A_new + L2 * direction

                C_new = self._solve_circle_intersection(B_new, L3, O1, L4)

                if C_new is None:
                    continue

                frames.append({
                    "angle": math.degrees(theta),
                    "positions": {
                        "O0": O0.tolist(),
                        "O1": O1.tolist(),
                        "A": A_new.tolist(),
                        "B": B_new.tolist(),
                        "C": C_new.tolist(),
                    },
                })

            if not frames:
                return None

            layer_data["simulation"] = {
                "frames": frames,
                "duration_ms": params.get("duration_ms", self.DEFAULT_DURATION_MS),
                "type": "5bar",
            }

            return layer_data

        except Exception as e:
            logging.error(f"SimulationRegenerator: 5-bar regeneration failed: {e}")
            return None

    def regenerate_6bar(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Regenerate 6-bar linkage simulation."""
        # Similar pattern to 5-bar with additional link
        try:
            O0 = np.array(params.get("O0", [0, 0]), dtype=float)
            O1 = np.array(params.get("O1", [100, 0]), dtype=float)

            frames = []
            num_steps = params.get("simulation_steps", self.DEFAULT_STEPS)

            # Simplified 6-bar simulation
            for i in range(num_steps):
                theta = 2 * math.pi * i / num_steps

                frames.append({
                    "angle": math.degrees(theta),
                    "positions": {
                        "O0": O0.tolist(),
                        "O1": O1.tolist(),
                    },
                })

            layer_data["simulation"] = {
                "frames": frames,
                "duration_ms": params.get("duration_ms", self.DEFAULT_DURATION_MS),
                "type": "6bar",
            }

            return layer_data

        except Exception as e:
            logging.error(f"SimulationRegenerator: 6-bar regeneration failed: {e}")
            return None

    def regenerate_gear(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Regenerate gear mesh simulation."""
        try:
            # Gear parameters
            r1 = params.get("r1", 30.0)
            r2 = params.get("r2", 20.0)
            c1 = np.array(params.get("center1", [0, 0]), dtype=float)
            c2 = np.array(params.get("center2", [r1 + r2, 0]), dtype=float)

            gear_ratio = r1 / r2 if r2 > 0 else 1.0

            frames = []
            num_steps = params.get("simulation_steps", self.DEFAULT_STEPS)

            for i in range(num_steps):
                theta1 = 2 * math.pi * i / num_steps
                theta2 = -theta1 * gear_ratio  # Counter-rotation

                frames.append({
                    "angle": math.degrees(theta1),
                    "gear1_angle": math.degrees(theta1),
                    "gear2_angle": math.degrees(theta2),
                    "positions": {
                        "center1": c1.tolist(),
                        "center2": c2.tolist(),
                    },
                })

            layer_data["simulation"] = {
                "frames": frames,
                "duration_ms": params.get("duration_ms", self.DEFAULT_DURATION_MS),
                "type": "gear",
                "gear_ratio": gear_ratio,
            }

            return layer_data

        except Exception as e:
            logging.error(f"SimulationRegenerator: gear regeneration failed: {e}")
            return None

    def regenerate_planetary_gear(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Regenerate planetary gear simulation."""
        try:
            r_sun = params.get("r_sun", 20.0)
            r_planet = params.get("r_planet", 12.0)
            num_planets = params.get("num_planets", 3)
            center = np.array(params.get("center", [0, 0]), dtype=float)

            planet_orbit_r = r_sun + r_planet

            frames = []
            num_steps = params.get("simulation_steps", self.DEFAULT_STEPS)

            for i in range(num_steps):
                carrier_angle = 2 * math.pi * i / num_steps
                sun_angle = carrier_angle * 2  # Sun rotates faster

                planet_positions = []
                for p in range(num_planets):
                    base_angle = 2 * math.pi * p / num_planets
                    planet_angle = base_angle + carrier_angle
                    px = center[0] + planet_orbit_r * math.cos(planet_angle)
                    py = center[1] + planet_orbit_r * math.sin(planet_angle)
                    planet_positions.append([px, py])

                frames.append({
                    "angle": math.degrees(carrier_angle),
                    "sun_angle": math.degrees(sun_angle),
                    "carrier_angle": math.degrees(carrier_angle),
                    "planet_positions": planet_positions,
                    "positions": {
                        "center": center.tolist(),
                    },
                })

            layer_data["simulation"] = {
                "frames": frames,
                "duration_ms": params.get("duration_ms", self.DEFAULT_DURATION_MS),
                "type": "planetary_gear",
            }

            return layer_data

        except Exception as e:
            logging.error(f"SimulationRegenerator: planetary gear failed: {e}")
            return None

    def regenerate_cam(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Regenerate cam-follower simulation."""
        try:
            base_r = positive_finite_float(params.get("base_radius"), 30.0)
            lift = max(0.0, finite_float(params.get("lift"), 15.0))
            center = np.array(params.get("center", [0.0, 0.0]), dtype=float)
            if center.ndim != 1 or center.size < 2 or not bool(np.isfinite(center[:2]).all()):
                center = np.array([0.0, 0.0], dtype=float)
            else:
                center = center[:2]

            frames = []
            num_steps = max(
                1,
                int(positive_finite_float(params.get("simulation_steps"), self.DEFAULT_STEPS)),
            )

            for i in range(num_steps):
                angle = 2 * math.pi * i / num_steps

                # Harmonic motion profile
                if angle < math.pi:
                    displacement = (lift / 2) * (1 - math.cos(angle))
                else:
                    displacement = (lift / 2) * (1 + math.cos(angle - math.pi))

                follower_y = center[1] - base_r - displacement

                frames.append({
                    "angle": math.degrees(angle),
                    "follower_displacement": displacement,
                    "positions": {
                        "center": center.tolist(),
                        "follower": [center[0], follower_y],
                    },
                })

            layer_data["simulation"] = {
                "frames": frames,
                "duration_ms": params.get("duration_ms", self.DEFAULT_DURATION_MS),
                "type": "cam",
            }

            return layer_data

        except Exception as e:
            logging.error(f"SimulationRegenerator: cam regeneration failed: {e}")
            return None

    def _solve_circle_intersection(
        self,
        center1: np.ndarray,
        radius1: float,
        center2: np.ndarray,
        radius2: float,
        prefer_lower: bool = True,
    ) -> np.ndarray | None:
        """
        Solve for intersection of two circles.

        Returns one of the two intersection points based on preference.

        Args:
            center1: First circle center
            radius1: First circle radius
            center2: Second circle center
            radius2: Second circle radius
            prefer_lower: If True, prefer the point with lower y-coordinate

        Returns:
            Intersection point as numpy array, or None if no solution

        Time Complexity: O(1)
        """
        d = np.linalg.norm(center2 - center1)

        # Check if circles intersect
        if d > radius1 + radius2 or d < abs(radius1 - radius2) or d == 0:
            return None

        # Calculate intersection using law of cosines
        a = (radius1 * radius1 - radius2 * radius2 + d * d) / (2 * d)
        h_sq = radius1 * radius1 - a * a

        if h_sq < 0:
            return None

        h = math.sqrt(h_sq)

        # Point along line between centers
        direction = (center2 - center1) / d
        perpendicular = np.array([-direction[1], direction[0]])

        p = center1 + a * direction

        # Two intersection points
        p1 = p + h * perpendicular
        p2 = p - h * perpendicular

        # Return preferred point
        if prefer_lower:
            return np.asarray(p1 if p1[1] > p2[1] else p2, dtype=float)
        return np.asarray(p1 if p1[1] < p2[1] else p2, dtype=float)
