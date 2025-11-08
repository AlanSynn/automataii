"""Five-bar linkage validation with workspace and singularity analysis.

Implements:
- Link length closure constraint validation
- Workspace reachability analysis
- Singularity detection via Jacobian determinant
- Transmission angle quality assessment
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from automataii.domain.mechanisms.linkages.validators.base import LinkageValidator

if TYPE_CHECKING:
    from automataii.domain.mechanisms.core.types import SafetyStatus


class FiveBarValidator(LinkageValidator):
    """Five-bar linkage validation with comprehensive safety checks.

    Validates:
    - Closure constraint (links can form a valid mechanism)
    - Workspace reachability (end-effector position)
    - Singularity proximity (Jacobian determinant ≈ 0)
    - Transmission angles at both output joints
    - Link ratio quality
    """

    @property
    def bar_count(self) -> int:
        """Five-bar linkage."""
        return 5

    def validate_safety(
        self,
        parameters: dict[str, float],
        positions: dict[str, tuple[float, float]],
        input_angle: float,
    ) -> SafetyStatus:
        """Evaluate five-bar safety and quality.

        Args:
            parameters: Link lengths (L1 through L5 or ground, input1, coupler, input2, output)
            positions: Joint positions (O1, O2, A, B, P where P is coupler point)
            input_angle: Current input angle in degrees

        Returns:
            SafetyStatus with SAFE/WARNING/DANGER and detailed message
        """
        from automataii.domain.mechanisms.core.state import SafetyLevel, SafetyStatus

        try:
            # Extract link lengths
            ground = parameters.get("ground_link", parameters.get("L1", 100.0))
            input1 = parameters.get("input1_link", parameters.get("L2", 40.0))
            coupler = parameters.get("coupler_link", parameters.get("L3", 60.0))
            input2 = parameters.get("input2_link", parameters.get("L4", 45.0))
            output = parameters.get("output_link", parameters.get("L5", 55.0))

            # 1. Closure constraint check
            closure_ok, closure_msg = self._check_closure_constraint(
                ground, input1, coupler, input2, output
            )
            if not closure_ok:
                return SafetyStatus(
                    level=SafetyLevel.DANGER,
                    message=closure_msg,
                    details={"check": "closure"},
                )

            # 2. Workspace reachability (if positions provided)
            if "A" in positions and "B" in positions:
                a_pos = positions["A"]
                b_pos = positions["B"]
                reach_ok, reach_msg = self._check_reachability(
                    a_pos, b_pos, coupler
                )
                if not reach_ok:
                    return SafetyStatus(
                        level=SafetyLevel.DANGER,
                        message=reach_msg,
                        details={"check": "reachability"},
                    )

            # 3. Singularity detection
            if all(k in positions for k in ["O1", "O2", "A", "B"]):
                sing_level, sing_msg = self._check_singularity(
                    positions, input1, input2, coupler
                )
                if sing_level == "danger":
                    return SafetyStatus(
                        level=SafetyLevel.DANGER,
                        message=sing_msg,
                        details={"check": "singularity"},
                    )
                elif sing_level == "warning":
                    return SafetyStatus(
                        level=SafetyLevel.WARNING,
                        message=sing_msg,
                        details={"check": "singularity"},
                    )

            # 4. Transmission angle quality
            ta_quality, ta_msg = self._analyze_transmission_angles(positions, coupler)
            if ta_quality == "critical":
                return SafetyStatus(
                    level=SafetyLevel.DANGER,
                    message=ta_msg,
                    details={"check": "transmission_angle"},
                )
            elif ta_quality == "poor":
                return SafetyStatus(
                    level=SafetyLevel.WARNING,
                    message=ta_msg,
                    details={"check": "transmission_angle"},
                )

            # 5. Link ratio quality
            link_lengths = [ground, input1, coupler, input2, output]
            ratio_quality, ratio_msg = self._analyze_link_ratios(link_lengths)
            if ratio_quality == "poor":
                return SafetyStatus(
                    level=SafetyLevel.WARNING,
                    message=f"Five-bar nominal - {ratio_msg}",
                    details={"check": "link_ratio"},
                )

            # All checks passed
            return SafetyStatus(
                level=SafetyLevel.SAFE,
                message=f"Five-bar mechanism OK{' - ' + ta_msg if ta_quality != 'excellent' else ''}",
                details={},
            )

        except Exception as e:
            return SafetyStatus(
                level=SafetyLevel.DANGER,
                message=f"Validation error: {str(e)}",
                details={"error": str(e)},
            )

    @staticmethod
    def _check_closure_constraint(
        ground: float, input1: float, coupler: float, input2: float, output: float
    ) -> tuple[bool, str]:
        """Check if links can form a valid closed mechanism.

        For five-bar: The sum of any four links must be >= the fifth link.
        """
        links = [ground, input1, coupler, input2, output]
        total = sum(links)

        for i, link in enumerate(links):
            if link >= total - link:
                link_names = ["ground", "input1", "coupler", "input2", "output"]
                return False, f"Invalid closure: {link_names[i]} too long ({link:.1f} >= {total - link:.1f})"

        return True, "Closure OK"

    @staticmethod
    def _check_reachability(
        a_pos: tuple[float, float],
        b_pos: tuple[float, float],
        coupler: float,
    ) -> tuple[bool, str]:
        """Check if coupler can reach between points A and B."""
        dist_ab = math.hypot(a_pos[0] - b_pos[0], a_pos[1] - b_pos[1])

        if dist_ab > coupler * 1.5:
            return False, f"Coupler too short: dist={dist_ab:.1f}, coupler={coupler:.1f}"

        return True, "Reachable"

    @staticmethod
    def _check_singularity(
        positions: dict[str, tuple[float, float]],
        input1: float,
        input2: float,
        coupler: float,
    ) -> tuple[str, str]:
        """Detect singularity via simplified Jacobian analysis.

        Singularity occurs when links become collinear or folded.
        """
        o1 = positions["O1"]
        o2 = positions["O2"]
        a = positions["A"]
        b = positions["B"]

        # Vector from O1 to A (input1 direction)
        v1 = (a[0] - o1[0], a[1] - o1[1])
        # Vector from O2 to B (input2 direction)
        v2 = (b[0] - o2[0], b[1] - o2[1])
        # Vector from A to B (coupler direction)
        vc = (b[0] - a[0], b[1] - a[1])

        # Check for near-collinearity (cross product magnitude)
        def cross_2d(u: tuple[float, float], v: tuple[float, float]) -> float:
            return u[0] * v[1] - u[1] * v[0]

        # Jacobian determinant approximation via cross products
        cross1 = cross_2d(v1, vc)
        cross2 = cross_2d(v2, vc)

        len_v1 = math.hypot(*v1) or 1.0
        len_v2 = math.hypot(*v2) or 1.0
        len_vc = math.hypot(*vc) or 1.0

        # Normalized cross products (sin of angles)
        sin1 = abs(cross1) / (len_v1 * len_vc)
        sin2 = abs(cross2) / (len_v2 * len_vc)

        # Near singularity if either angle is very small
        if sin1 < 0.05 or sin2 < 0.05:
            return "danger", "At singularity: links collinear"
        elif sin1 < 0.15 or sin2 < 0.15:
            return "warning", "Near singularity: approaching collinear configuration"

        return "safe", "No singularity"

    @staticmethod
    def _analyze_transmission_angles(
        positions: dict[str, tuple[float, float]],
        coupler: float,
    ) -> tuple[str, str]:
        """Analyze transmission angle quality at both output joints."""
        if not all(k in positions for k in ["A", "B"]):
            return "unknown", "Positions incomplete"

        # For five-bar, we care about angles at A and B
        # This is a simplified check
        a = positions.get("A", (0, 0))
        b = positions.get("B", (0, 0))
        dist = math.hypot(a[0] - b[0], a[1] - b[1])

        # If coupler is stretched or compressed too much
        if dist < coupler * 0.2:
            return "critical", f"Near folded configuration (dist/coupler={dist/coupler:.2f})"
        elif dist < coupler * 0.4:
            return "poor", "Poor transmission angle region"
        elif dist < coupler * 0.6:
            return "fair", "Moderate transmission angle"

        return "excellent", "Good transmission angles"

    @staticmethod
    def _analyze_link_ratios(link_lengths: list[float]) -> tuple[str, str]:
        """Analyze link ratio quality."""
        if not link_lengths or min(link_lengths) <= 0:
            return "unknown", "Invalid link lengths"

        max_ratio = max(link_lengths) / min(link_lengths)

        if max_ratio > 10:
            return "poor", f"Extreme link ratio: {max_ratio:.1f}:1"
        elif max_ratio > 6:
            return "fair", f"High link ratio: {max_ratio:.1f}:1"

        return "excellent", "Good link ratios"
