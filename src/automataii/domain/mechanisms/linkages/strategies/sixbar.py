"""Six-bar linkage computation strategy.

Lines: ~135
Public API: SixBarStrategy
Deps In: 0 (implements LinkageStrategy)
Deps Out: 4 (math, core.types, strategies.base, fivebar)
Coupling: Medium (depends on FiveBarStrategy)
Cohesion: Feature (six-bar kinematics)
Owner: Alan Synn
Last Updated: 2025-11-14
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from automataii.mechanisms.linkages.strategies.base import LinkageStrategy
from automataii.mechanisms.linkages.strategies.fivebar import FiveBarStrategy

if TYPE_CHECKING:
    from automataii.mechanisms.core.types import ForceVector


class SixBarStrategy(LinkageStrategy):
    """Six-bar linkage kinematics computation (Stephenson type).

    Builds on five-bar by adding:
    - Upper ground pivot G3
    - Rocker link from floating joint P to output Q
    - Ternary link structure
    """

    def __init__(self) -> None:
        """Initialize with embedded five-bar solver."""
        self._five_bar = FiveBarStrategy()

    @property
    def bar_count(self) -> int:
        """Six-bar linkage."""
        return 6

    def required_parameters(self) -> frozenset[str]:
        """Required parameters: five-bar + pivot_height.

        Note: pivot_height defines upper ground pivot location.
        """
        return frozenset([
            "ground_link",
            "input_link",
            "coupler_link",
            "output_link",
            "pivot_height",
        ])

    def compute_positions(
        self,
        parameters: dict[str, float],
        input_angle: float,
    ) -> dict[str, tuple[float, float]]:
        """Compute six-bar joint positions.

        Args:
            parameters: ground_link, input_link, coupler_link, output_link, pivot_height
            input_angle: Left crank angle in degrees

        Returns:
            Positions: {G1, G2, G3, C1, C2, P, Q}
        """
        # Solve base five-bar (G1, G2, C1, C2, P)
        base_positions = self._five_bar.compute_positions(parameters, input_angle)

        # Extract floating joint P
        p = base_positions["P"]

        # Upper ground pivot (centered, elevated)
        pivot_height = parameters.get("pivot_height", parameters["ground_link"] * 0.6)
        g3 = (0.0, pivot_height)

        # Rocker output Q (from P toward G3)
        rocker_length = parameters.get("output_link", 95.0)  # Reuse output_link param
        q = self._solve_rocker_point(p, g3, rocker_length)

        # Combine all positions
        positions = dict(base_positions)
        positions["G3"] = g3
        positions["Q"] = q

        return positions

    def compute_forces(
        self,
        positions: dict[str, tuple[float, float]],
        parameters: dict[str, float],
        input_angle: float,
    ) -> dict[str, ForceVector] | None:
        """Six-bar forces not implemented.

        Args:
            positions: Joint positions
            parameters: Mechanism parameters
            input_angle: Input angle

        Returns:
            None (force analysis TBD)
        """
        return None

    @staticmethod
    def _solve_rocker_point(
        floating_point: tuple[float, float],
        pivot: tuple[float, float],
        rocker_length: float,
    ) -> tuple[float, float]:
        """Compute rocker output Q from floating joint P.

        Args:
            floating_point: (x, y) of floating joint P
            pivot: (x, y) of upper ground pivot G3
            rocker_length: Length of rocker link

        Returns:
            (x, y) of output joint Q

        Note:
            If distance PG3 < rocker_length, Q is placed at max reach.
            This prevents solver instability near singularities.
        """
        fx, fy = floating_point
        px, py = pivot
        dx = fx - px
        dy = fy - py
        dist = math.hypot(dx, dy)

        if dist < 1e-6:
            return pivot  # Degenerate case

        # Scale to rocker length (cap at actual distance)
        scale = min(rocker_length, dist) / dist
        return (px + dx * scale, py + dy * scale)
