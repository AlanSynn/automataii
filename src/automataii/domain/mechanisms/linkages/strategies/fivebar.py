"""Five-bar linkage computation strategy."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from automataii.domain.mechanisms.linkages.strategies.base import LinkageStrategy

if TYPE_CHECKING:
    from automataii.domain.mechanisms.core.types import ForceVector


class FiveBarStrategy(LinkageStrategy):
    """Five-bar linkage kinematics computation.

    Dual-actuated planar five-bar with:
    - Two independent input cranks at ground pivots
    - Floating coupler chain (C1-P-C2) connecting cranks
    - Circle-circle intersection for joint P
    """

    @property
    def bar_count(self) -> int:
        """Five-bar linkage."""
        return 5

    def required_parameters(self) -> frozenset[str]:
        """Required link length parameters."""
        return frozenset(["ground_link", "input_link", "coupler_link", "output_link"])

    def compute_positions(
        self,
        parameters: dict[str, float],
        input_angle: float,
    ) -> dict[str, tuple[float, float]]:
        """Compute five-bar joint positions.

        Args:
            parameters: ground_link (spacing), input_link (left crank),
                        coupler_link (floating segments), output_link (right crank)
            input_angle: Left crank angle in degrees

        Returns:
            Positions: {G1, G2, C1, C2, P}
        """
        ground = parameters["ground_link"]
        left_crank = parameters["input_link"]
        floating = parameters["coupler_link"]
        right_crank = parameters["output_link"]

        # Ground pivots (centered)
        g1 = (-ground / 2.0, 0.0)
        g2 = (ground / 2.0, 0.0)

        # Left crank (driven by input_angle)
        theta = math.radians(input_angle)
        c1 = (
            g1[0] + left_crank * math.cos(theta),
            g1[1] + left_crank * math.sin(theta),
        )

        # Right crank (mirrored angle for symmetry)
        phi = math.pi - theta
        c2 = (
            g2[0] + right_crank * math.cos(phi),
            g2[1] + right_crank * math.sin(phi),
        )

        # Floating joint P (circle-circle intersection)
        p = self._circle_intersection(c1, floating, c2, floating)
        if p is None:
            # Fallback: midpoint if unreachable
            p = ((c1[0] + c2[0]) / 2.0, (c1[1] + c2[1]) / 2.0)

        return {
            "G1": g1,
            "G2": g2,
            "C1": c1,
            "C2": c2,
            "P": p,
        }

    def compute_forces(
        self,
        positions: dict[str, tuple[float, float]],
        parameters: dict[str, float],
        input_angle: float,
    ) -> dict[str, ForceVector] | None:
        """Five-bar forces not implemented.

        Args:
            positions: Joint positions
            parameters: Mechanism parameters
            input_angle: Input angle

        Returns:
            None (force analysis TBD)
        """
        return None

    @staticmethod
    def _circle_intersection(
        center_a: tuple[float, float],
        radius_a: float,
        center_b: tuple[float, float],
        radius_b: float,
    ) -> tuple[float, float] | None:
        """Find intersection of two circles (upper solution).

        Args:
            center_a: (x, y) of first circle
            radius_a: Radius of first circle
            center_b: (x, y) of second circle
            radius_b: Radius of second circle

        Returns:
            (x, y) of upper intersection, or None if no solution

        Algorithm:
            - Compute distance d between centers
            - Check triangle inequality (reachability)
            - Use law of cosines to find intersection
            - Return upper solution (prefer positive y)
        """
        ax, ay = center_a
        bx, by = center_b
        dx = bx - ax
        dy = by - ay
        d = math.hypot(dx, dy)

        # Degenerate or unreachable
        if d < 1e-6:
            return None
        if d > radius_a + radius_b or d < abs(radius_a - radius_b):
            return None

        # Law of cosines: distance along center line
        a = (radius_a**2 - radius_b**2 + d**2) / (2 * d)
        h_sq = radius_a**2 - a**2
        h = math.sqrt(max(h_sq, 0.0))

        # Midpoint along center line
        xm = ax + a * dx / d
        ym = ay + a * dy / d

        # Perpendicular offset
        rx = -dy * (h / d)
        ry = dx * (h / d)

        # Two intersection candidates
        intersection1 = (xm + rx, ym + ry)
        intersection2 = (xm - rx, ym - ry)

        # Prefer upper (higher y)
        return intersection1 if intersection1[1] >= intersection2[1] else intersection2
