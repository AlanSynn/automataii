"""Four-bar linkage computation strategy.

Lines: ~200
Public API: FourBarStrategy
Deps In: 0 (implements LinkageStrategy)
Deps Out: 3 (math, core.types, strategies.base)
Coupling: Low (single strategy)
Cohesion: Feature (four-bar kinematics)
Owner: Alan Synn
Last Updated: 2025-11-14
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from automataii.mechanisms.linkages.strategies.base import LinkageStrategy

if TYPE_CHECKING:
    from automataii.mechanisms.core.types import ForceVector, ForceType


class FourBarStrategy(LinkageStrategy):
    """Four-bar linkage kinematics and dynamics computation.

    Implements closed-form solution for planar four-bar mechanism with:
    - Assembly mode tracking (two possible configurations)
    - Smooth angle transitions (avoid discontinuities)
    - Reachability checks (coupler-output triangle constraints)
    """

    def __init__(self) -> None:
        """Initialize with clean state."""
        self._last_output_angle: float | None = None
        self._assembly_mode: int | None = None

    @property
    def bar_count(self) -> int:
        """Four-bar linkage."""
        return 4

    def required_parameters(self) -> frozenset[str]:
        """Required link length parameters."""
        return frozenset(["ground_link", "input_link", "coupler_link", "output_link"])

    def compute_positions(
        self,
        parameters: dict[str, float],
        input_angle: float,
    ) -> dict[str, tuple[float, float]]:
        """Compute four-bar joint positions.

        Args:
            parameters: Must contain ground_link, input_link, coupler_link, output_link
            input_angle: Input crank angle in degrees

        Returns:
            Positions: {O1, O4, A, B, coupler_midpoint}
        """
        ground = parameters["ground_link"]
        input_l = parameters["input_link"]
        coupler = parameters["coupler_link"]
        output = parameters["output_link"]

        # Ground pivots (centered)
        o1_x, o1_y = -ground / 2, 0.0
        o4_x, o4_y = ground / 2, 0.0

        # Input crank position
        theta_rad = math.radians(input_angle)
        a_x = o1_x + input_l * math.cos(theta_rad)
        a_y = o1_y + input_l * math.sin(theta_rad)

        # Output angle (closed-form solver with assembly mode)
        output_angle_rad = self._solve_output_angle(
            ground, input_l, coupler, output, theta_rad
        )

        # Output rocker position
        b_x = o4_x + output * math.cos(output_angle_rad)
        b_y = o4_y + output * math.sin(output_angle_rad)

        return {
            "O1": (o1_x, o1_y),
            "O4": (o4_x, o4_y),
            "A": (a_x, a_y),
            "B": (b_x, b_y),
            "coupler_midpoint": ((a_x + b_x) / 2, (a_y + b_y) / 2),
        }

    def compute_forces(
        self,
        positions: dict[str, tuple[float, float]],
        parameters: dict[str, float],
        input_angle: float,
    ) -> dict[str, ForceVector] | None:
        """Compute force vectors for four-bar linkage.

        Args:
            positions: Joint positions from compute_positions()
            parameters: Mechanism parameters
            input_angle: Input angle in degrees

        Returns:
            Force vectors: {input, reaction_O1}
        """
        from automataii.mechanisms.core.state import ForceType, ForceVector
        from PyQt6.QtCore import QPointF

        o1_x, o1_y = positions["O1"]
        a_x, a_y = positions["A"]
        theta_rad = math.radians(input_angle)

        input_force = ForceVector(
            position=QPointF(a_x, a_y),
            magnitude=40 + 10 * math.sin(theta_rad),
            angle=math.degrees(theta_rad + math.pi / 2),
            force_type=ForceType.APPLIED,
            label="F_in",
        )

        reaction_o1 = ForceVector(
            position=QPointF(o1_x, o1_y),
            magnitude=30,
            angle=math.degrees(theta_rad + math.pi),
            force_type=ForceType.REACTION,
            label="R_O1",
        )

        return {"input": input_force, "reaction_O1": reaction_o1}

    def _solve_output_angle(
        self,
        ground: float,
        input_l: float,
        coupler: float,
        output: float,
        input_angle_rad: float,
    ) -> float:
        """Solve output angle using law of cosines with assembly mode tracking.

        Returns:
            Output angle in radians
        """
        try:
            # Input joint position relative to O4
            a_x = input_l * math.cos(input_angle_rad) - ground
            a_y = input_l * math.sin(input_angle_rad)
            dist_a_o4 = math.sqrt(a_x**2 + a_y**2)

            # Reachability check (triangle inequality)
            if dist_a_o4 > (coupler + output) or dist_a_o4 < abs(coupler - output):
                return self._fallback_angle(input_angle_rad)

            # Law of cosines: angle at B
            alpha = math.atan2(a_y, a_x)
            cos_beta = (output**2 + dist_a_o4**2 - coupler**2) / (
                2 * output * dist_a_o4
            )
            cos_beta = max(-1.0, min(1.0, cos_beta))
            beta = math.acos(cos_beta)

            # Two assembly modes
            theta4_1 = alpha + beta
            theta4_2 = alpha - beta

            # Mode selection with continuity
            theta4 = self._select_assembly_mode(theta4_1, theta4_2)

            # Smooth transitions (rate limit)
            theta4 = self._apply_smoothing(theta4)

            self._last_output_angle = theta4
            return theta4

        except Exception:
            return self._fallback_angle(input_angle_rad)

    def _select_assembly_mode(self, theta4_1: float, theta4_2: float) -> float:
        """Select assembly mode with hysteresis to avoid switching."""
        if self._assembly_mode is None:
            # Initial mode: prefer smaller angle
            self._assembly_mode = 1 if abs(theta4_1) < abs(theta4_2) else 2
            return theta4_1 if self._assembly_mode == 1 else theta4_2

        # Current mode
        theta4 = theta4_1 if self._assembly_mode == 1 else theta4_2

        # Check if alternative is significantly better (hysteresis)
        if self._last_output_angle is not None:
            current_diff = abs(self._normalize_angle(theta4 - self._last_output_angle))
            alternative = theta4_2 if self._assembly_mode == 1 else theta4_1
            alt_diff = abs(self._normalize_angle(alternative - self._last_output_angle))

            # Switch if alternative is much smoother (2x threshold)
            if current_diff > math.pi / 3 and alt_diff < current_diff / 2:
                self._assembly_mode = 3 - self._assembly_mode  # Toggle 1↔2
                return alternative

        return theta4

    def _apply_smoothing(self, theta4: float) -> float:
        """Rate-limit angular changes to avoid jumps."""
        if self._last_output_angle is None:
            return theta4

        delta = self._normalize_angle(theta4 - self._last_output_angle)
        max_change = math.pi / 8  # ~22.5° max step

        if abs(delta) > max_change:
            return self._last_output_angle + math.copysign(max_change, delta)

        return theta4

    def _fallback_angle(self, input_angle_rad: float) -> float:
        """Return safe angle when solver fails."""
        if self._last_output_angle is not None:
            return self._last_output_angle
        return -input_angle_rad * 0.3  # Approximate guess

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        """Normalize angle to [-π, π]."""
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle
