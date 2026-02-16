"""Four-bar linkage validation with Grashof and transmission angle analysis.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from automataii.domain.mechanisms.linkages.validators.base import LinkageValidator
from automataii.domain.mechanisms.shared import (
    analyze_link_ratios,
    calculate_transmission_angle,
    classify_transmission_angle,
)

if TYPE_CHECKING:
    from automataii.domain.mechanisms.core.types import SafetyStatus


class FourBarValidator(LinkageValidator):
    """Four-bar linkage validation with Grashof and transmission angle checks.

    Validates:
    - Grashof condition (s + l ≤ p + q) for continuous rotation
    - Mechanism classification (Crank-Rocker, Double-Crank, etc.)
    - Transmission angle (optimal: 40°-140°)
    - Reachability (triangle inequality)
    - Link ratio quality (< 6:1 preferred)
    """

    @property
    def bar_count(self) -> int:
        """Four-bar linkage."""
        return 4

    def validate_safety(
        self,
        parameters: dict[str, float],
        positions: dict[str, tuple[float, float]],
        input_angle: float,
    ) -> SafetyStatus:
        """Evaluate four-bar safety and quality.

        Args:
            parameters: Link lengths (ground_link, input_link, coupler_link, output_link)
            positions: Joint positions (O1, O4, A, B)
            input_angle: Current input angle in degrees

        Returns:
            SafetyStatus with SAFE/WARNING/DANGER and detailed message
        """
        from automataii.domain.mechanisms.core.state import SafetyLevel, SafetyStatus

        try:
            ground = parameters["ground_link"]
            input_l = parameters["input_link"]
            coupler = parameters["coupler_link"]
            output = parameters["output_link"]

            # Grashof analysis
            grashof_ok, grashof_ratio, mech_class = self._analyze_grashof(
                ground, input_l, coupler, output
            )

            # Transmission angle quality (using shared analyzer)
            a_x, a_y = positions["A"]
            o4_x, o4_y = positions["O4"]

            dist_a_o4 = math.hypot(a_x - o4_x, a_y - o4_y)
            max_reach = coupler + output
            min_reach = abs(coupler - output)

            ta_deg_raw = calculate_transmission_angle(dist_a_o4, coupler, output)
            ta_result = classify_transmission_angle(ta_deg_raw)
            ta_deg = ta_result.angle_deg
            ta_quality = ta_result.quality.value

            # Link ratio quality (using shared analyzer)
            link_lengths = [ground, input_l, coupler, output]
            ratio_result = analyze_link_ratios(link_lengths)
            ratio_quality = ratio_result.quality
            ratio_messages = [ratio_result.message] if ratio_result.quality != "excellent" else []

            # Add check for very small input link
            if input_l < ground * 0.1:
                ratio_messages.append("Very small input link")
                if ratio_quality == "excellent":
                    ratio_quality = "fair"

            # Determine safety level and message
            return self._build_safety_status(
                grashof_ok,
                grashof_ratio,
                mech_class,
                dist_a_o4,
                max_reach,
                min_reach,
                ta_deg,
                ta_quality,
                ratio_quality,
                ratio_messages,
            )

        except Exception as e:
            from automataii.domain.mechanisms.core.state import SafetyLevel, SafetyStatus
            return SafetyStatus(
                level=SafetyLevel.DANGER,
                message=f"Validation error: {str(e)}",
                details={},
            )

    @staticmethod
    def _analyze_grashof(
        ground: float, input_l: float, coupler: float, output: float
    ) -> tuple[bool, float, str]:
        """Analyze Grashof condition and classify mechanism.

        Returns:
            (grashof_ok, grashof_ratio, mechanism_class)
        """
        links = [
            (ground, "ground"),
            (input_l, "input"),
            (coupler, "coupler"),
            (output, "output"),
        ]
        sorted_lengths = sorted([ground, input_l, coupler, output])
        shortest, mid1, mid2, longest = sorted_lengths

        grashof_sum = shortest + longest
        middle_sum = mid1 + mid2
        grashof_ok = grashof_sum <= middle_sum
        grashof_ratio = grashof_sum / middle_sum if middle_sum > 0 else float("inf")

        # Classify mechanism type
        shortest_link = min(links, key=lambda x: x[0])
        if grashof_ok:
            if shortest_link[1] == "ground":
                mech_class = "Double-Crank (Class III)"
            elif shortest_link[1] in ["input", "output"]:
                mech_class = "Crank-Rocker (Class I)"
            else:
                mech_class = "Double-Rocker (Class II)"
        else:
            mech_class = "Triple-Rocker (Class IV)"

        return grashof_ok, grashof_ratio, mech_class

    # NOTE: _analyze_transmission_angle and _analyze_link_ratios have been moved to
    # automataii.domain.mechanisms.shared.transmission_analyzer for reuse across validators

    @staticmethod
    def _build_safety_status(
        grashof_ok: bool,
        grashof_ratio: float,
        mech_class: str,
        dist_a_o4: float,
        max_reach: float,
        min_reach: float,
        ta_deg: float,
        ta_quality: str,
        ratio_quality: str,
        ratio_messages: list[str],
    ) -> SafetyStatus:
        """Build final SafetyStatus based on all checks."""
        from automataii.domain.mechanisms.core.state import SafetyLevel, SafetyStatus

        # Priority: most severe issue determines level
        if not grashof_ok and grashof_ratio > 1.1:
            return SafetyStatus(
                level=SafetyLevel.DANGER,
                message=f"No continuous rotation (Grashof: {grashof_ratio:.2f})",
                details={},
            )
        elif dist_a_o4 > max_reach:
            return SafetyStatus(
                level=SafetyLevel.DANGER,
                message=f"Links unreachable (dist: {dist_a_o4:.1f} > {max_reach:.1f})",
                details={},
            )
        elif dist_a_o4 < min_reach:
            return SafetyStatus(
                level=SafetyLevel.DANGER,
                message=f"Link interference (dist: {dist_a_o4:.1f} < {min_reach:.1f})",
                details={},
            )
        elif ta_quality == "critical":
            return SafetyStatus(
                level=SafetyLevel.DANGER,
                message=f"Critical transmission angle: {ta_deg:.1f}°",
                details={},
            )
        elif not grashof_ok:
            return SafetyStatus(
                level=SafetyLevel.WARNING,
                message=f"Limited motion (Grashof: {grashof_ratio:.2f})",
                details={},
            )
        elif ta_quality == "poor":
            return SafetyStatus(
                level=SafetyLevel.WARNING,
                message=f"Poor transmission angle: {ta_deg:.1f}°",
                details={},
            )
        elif dist_a_o4 > max_reach * 0.95:
            return SafetyStatus(
                level=SafetyLevel.WARNING,
                message="Near reach limit - approaching singularity",
                details={},
            )
        elif dist_a_o4 < min_reach * 1.05:
            return SafetyStatus(
                level=SafetyLevel.WARNING,
                message="Near interference - approaching singularity",
                details={},
            )
        elif ratio_quality == "poor":
            return SafetyStatus(
                level=SafetyLevel.WARNING,
                message=f"{mech_class} - Poor design quality",
                details={},
            )
        else:
            # All checks passed
            if ta_quality == "excellent":
                msg = f"{mech_class} - Optimal (T.A.: {ta_deg:.1f}°)"
            else:
                msg = f"{mech_class} - Good (T.A.: {ta_deg:.1f}°)"

            if ratio_messages:
                msg += f" - Note: {', '.join(ratio_messages)}"

            return SafetyStatus(level=SafetyLevel.SAFE, message=msg, details={})
