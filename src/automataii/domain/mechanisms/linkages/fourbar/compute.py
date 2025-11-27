from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from PyQt6.QtCore import QPointF

from automataii.domain.mechanisms.core.protocols import Mechanism
from automataii.domain.mechanisms.core.state import (
    ForceType,
    ForceVector,
    MechanismState,
    SafetyLevel,
    SafetyStatus,
)


@dataclass(frozen=True)
class FourBarParameters:
    ground_link: float
    input_link: float
    coupler_link: float
    output_link: float
    input_angle: float
    ground_pivot1: QPointF | None = None
    ground_pivot2: QPointF | None = None


class FourBarMechanism(Mechanism):
    def __init__(self, parameters: dict[str, float] | None = None):
        self._parameters = self._parse_parameters(parameters or {})
        self._last_output_angle: float | None = None
        self._assembly_mode: int | None = None

    @property
    def mechanism_type(self) -> str:
        return "fourbar"

    @property
    def required_parameters(self) -> frozenset[str]:
        return frozenset(["ground_link", "input_link", "coupler_link", "output_link"])

    def validate_parameters(self, parameters: dict[str, float]) -> None:
        required = self.required_parameters
        missing = required - parameters.keys()
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")

        for param in required:
            if parameters[param] <= 0:
                raise ValueError(f"Parameter {param} must be positive, got {parameters[param]}")

    def _parse_parameters(self, params: dict) -> FourBarParameters:
        if "ground_pivot1" in params and "ground_pivot2" in params:
            gp1 = params["ground_pivot1"]
            gp2 = params["ground_pivot2"]
            ground_pivot1 = gp1 if isinstance(gp1, QPointF) else QPointF(gp1[0], gp1[1])
            ground_pivot2 = gp2 if isinstance(gp2, QPointF) else QPointF(gp2[0], gp2[1])
            ground_link = math.hypot(
                ground_pivot2.x() - ground_pivot1.x(), ground_pivot2.y() - ground_pivot1.y()
            )
        else:
            ground_link = params.get("ground_link", 150.0)
            ground_pivot1 = None
            ground_pivot2 = None

        return FourBarParameters(
            ground_link=ground_link,
            input_link=params.get("input_link", 40.0),
            coupler_link=params.get("coupler_link", 120.0),
            output_link=params.get("output_link", 130.0),
            input_angle=params.get("input_angle", 0.0),
            ground_pivot1=ground_pivot1,
            ground_pivot2=ground_pivot2,
        )

    def compute_state(self, parameters: dict[str, float], input_angle: float) -> MechanismState:
        params_with_angle = {**parameters, "input_angle": input_angle}
        self._parameters = self._parse_parameters(params_with_angle)
        params = self._parameters

        if params.ground_pivot1 is not None and params.ground_pivot2 is not None:
            O1 = params.ground_pivot1
            O4 = params.ground_pivot2
        else:
            O1 = QPointF(-params.ground_link / 2, 0)
            O4 = QPointF(params.ground_link / 2, 0)

        input_angle_rad = math.radians(params.input_angle)
        A = QPointF(
            O1.x() + params.input_link * math.cos(input_angle_rad),
            O1.y() + params.input_link * math.sin(input_angle_rad),
        )

        output_angle = self._solve_output_angle(
            params.ground_link,
            params.input_link,
            params.coupler_link,
            params.output_link,
            input_angle_rad,
        )

        B = QPointF(
            O4.x() + params.output_link * math.cos(output_angle),
            O4.y() + params.output_link * math.sin(output_angle),
        )

        positions = {
            "O1": (O1.x(), O1.y()),
            "O4": (O4.x(), O4.y()),
            "A": (A.x(), A.y()),
            "B": (B.x(), B.y()),
        }

        safety = self._evaluate_safety(
            params.ground_link,
            params.input_link,
            params.coupler_link,
            params.output_link,
            input_angle_rad,
        )

        forces = self._calculate_forces(O1, A, B, O4, input_angle_rad)

        metadata = {
            "input_angle": params.input_angle,
            "output_angle": math.degrees(output_angle),
            "ground_link": params.ground_link,
            "input_link": params.input_link,
            "coupler_link": params.coupler_link,
            "output_link": params.output_link,
        }

        return MechanismState(
            positions=positions, forces=forces, safety_status=safety, metadata=metadata
        )

    def _solve_output_angle(
        self, ground: float, input_l: float, coupler: float, output: float, input_angle: float
    ) -> float:
        try:
            r1, r2, r3, r4 = ground, input_l, coupler, output
            theta2 = input_angle

            Ax = r2 * math.cos(theta2)
            Ay = r2 * math.sin(theta2)

            O4x = r1
            O4y = 0

            L = math.sqrt((O4x - Ax) ** 2 + (O4y - Ay) ** 2)

            if L > (r3 + r4) or L < abs(r3 - r4):
                return (
                    self._last_output_angle
                    if self._last_output_angle is not None
                    else -input_angle * 0.3
                )

            vec_O4A_x = Ax - O4x
            vec_O4A_y = Ay - O4y

            alpha = math.atan2(vec_O4A_y, vec_O4A_x)

            try:
                cos_gamma = (r3 * r3 + r4 * r4 - L * L) / (2 * r3 * r4)
                cos_gamma = max(-1.0, min(1.0, cos_gamma))
                gamma = math.acos(cos_gamma)
            except (ValueError, ZeroDivisionError):
                gamma = 0

            try:
                cos_beta = (r4 * r4 + L * L - r3 * r3) / (2 * r4 * L)
                cos_beta = max(-1.0, min(1.0, cos_beta))
                beta = math.acos(cos_beta)
            except (ValueError, ZeroDivisionError):
                beta = 0

            theta4_1 = alpha + beta
            theta4_2 = alpha - beta

            if self._assembly_mode is None:
                if abs(theta4_1) < abs(theta4_2):
                    self._assembly_mode = 1
                    theta4 = theta4_1
                else:
                    self._assembly_mode = 2
                    theta4 = theta4_2
            else:
                theta4 = theta4_1 if self._assembly_mode == 1 else theta4_2

                if self._last_output_angle is not None:
                    current_diff = abs(theta4 - self._last_output_angle)

                    while current_diff > math.pi:
                        current_diff -= 2 * math.pi
                    current_diff = abs(current_diff)

                    if current_diff > math.pi / 3:
                        alternative_theta4 = theta4_2 if self._assembly_mode == 1 else theta4_1
                        alternative_diff = abs(alternative_theta4 - self._last_output_angle)

                        while alternative_diff > math.pi:
                            alternative_diff -= 2 * math.pi
                        alternative_diff = abs(alternative_diff)

                        if alternative_diff < current_diff / 2:
                            self._assembly_mode = 2 if self._assembly_mode == 1 else 1
                            theta4 = alternative_theta4

            if self._last_output_angle is not None:
                angular_change = theta4 - self._last_output_angle

                while angular_change > math.pi:
                    angular_change -= 2 * math.pi
                while angular_change < -math.pi:
                    angular_change += 2 * math.pi

                max_change = math.pi / 8
                if abs(angular_change) > max_change:
                    if angular_change > 0:
                        theta4 = self._last_output_angle + max_change
                    else:
                        theta4 = self._last_output_angle - max_change

            self._last_output_angle = theta4

            if math.isnan(theta4) or math.isinf(theta4):
                return self._last_output_angle if self._last_output_angle is not None else 0

            return theta4

        except Exception:
            return self._last_output_angle if self._last_output_angle is not None else 0

    def _evaluate_safety(
        self, ground: float, input_l: float, coupler: float, output: float, input_angle: float
    ) -> SafetyStatus:
        try:
            links = [
                (ground, "ground"),
                (input_l, "input"),
                (coupler, "coupler"),
                (output, "output"),
            ]
            link_lengths = [ground, input_l, coupler, output]
            sorted_links = sorted(link_lengths)
            s, p, q, l = sorted_links

            grashof_sum = s + l
            middle_sum = p + q
            grashof_condition = grashof_sum <= middle_sum
            grashof_ratio = grashof_sum / middle_sum if middle_sum > 0 else float("inf")

            shortest_link = min(links, key=lambda x: x[0])
            mechanism_class = "Unknown"

            if grashof_condition:
                if shortest_link[1] == "ground":
                    mechanism_class = "Double-Crank (Class III)"
                elif shortest_link[1] in ["input", "output"]:
                    mechanism_class = "Crank-Rocker (Class I)"
                else:
                    mechanism_class = "Double-Rocker (Class II)"
            else:
                mechanism_class = "Triple-Rocker (Class IV)"

            O1 = (-ground / 2, 0)
            O4 = (ground / 2, 0)
            A = (O1[0] + input_l * math.cos(input_angle), O1[1] + input_l * math.sin(input_angle))

            distance_AO4 = math.sqrt((A[0] - O4[0]) ** 2 + (A[1] - O4[1]) ** 2)

            max_reach_AB = coupler + output
            min_reach_AB = abs(coupler - output)

            if distance_AO4 <= max_reach_AB and distance_AO4 >= min_reach_AB:
                try:
                    cos_gamma = (
                        coupler * coupler + output * output - distance_AO4 * distance_AO4
                    ) / (2 * coupler * output)
                    cos_gamma = max(-1.0, min(1.0, cos_gamma))

                    transmission_angle = math.degrees(math.acos(abs(cos_gamma)))
                    transmission_quality = (
                        "excellent"
                        if 40 <= transmission_angle <= 140
                        else "good"
                        if 30 <= transmission_angle <= 150
                        else "poor"
                        if 20 <= transmission_angle <= 160
                        else "critical"
                    )
                except:
                    transmission_angle = 90
                    transmission_quality = "unknown"
            else:
                transmission_angle = 0
                transmission_quality = "impossible"

            link_ratio_quality = "excellent"
            quality_messages = []

            max_ratio = (
                max(link_lengths) / min(link_lengths) if min(link_lengths) > 0 else float("inf")
            )
            if max_ratio > 10:
                link_ratio_quality = "poor"
                quality_messages.append(f"Extreme link ratio: {max_ratio:.1f}:1")
            elif max_ratio > 6:
                link_ratio_quality = "fair"
                quality_messages.append(f"High link ratio: {max_ratio:.1f}:1")

            if input_l < ground * 0.1:
                quality_messages.append("Very small input link")
                if link_ratio_quality == "excellent":
                    link_ratio_quality = "fair"

            safety_level = SafetyLevel.SAFE
            safety_message = mechanism_class

            if not grashof_condition:
                if grashof_ratio > 1.1:
                    safety_level = SafetyLevel.DANGER
                    safety_message = (
                        f"No continuous rotation possible (Grashof ratio: {grashof_ratio:.2f})"
                    )
                else:
                    safety_level = SafetyLevel.WARNING
                    safety_message = f"Limited motion, no continuous rotation (Grashof ratio: {grashof_ratio:.2f})"
            elif distance_AO4 > max_reach_AB:
                safety_level = SafetyLevel.DANGER
                safety_message = f"Links cannot reach current position (distance: {distance_AO4:.1f} > max: {max_reach_AB:.1f})"
            elif distance_AO4 < min_reach_AB:
                safety_level = SafetyLevel.DANGER
                safety_message = (
                    f"Links interference (distance: {distance_AO4:.1f} < min: {min_reach_AB:.1f})"
                )
            elif transmission_quality == "critical":
                safety_level = SafetyLevel.DANGER
                safety_message = f"Critical transmission angle: {transmission_angle:.1f}° (force transmission very poor)"
            elif transmission_quality == "poor":
                safety_level = SafetyLevel.WARNING
                safety_message = (
                    f"Poor transmission angle: {transmission_angle:.1f}° (low force efficiency)"
                )
            elif distance_AO4 > max_reach_AB * 0.95:
                safety_level = SafetyLevel.WARNING
                safety_message = "Near reach limit - approaching singular position"
            elif distance_AO4 < min_reach_AB * 1.05:
                safety_level = SafetyLevel.WARNING
                safety_message = "Near interference - approaching singular position"
            elif link_ratio_quality == "poor":
                safety_level = SafetyLevel.WARNING
                safety_message = f"{mechanism_class} - Design quality: {link_ratio_quality}"
            else:
                if transmission_quality == "excellent":
                    safety_message = (
                        f"{mechanism_class} - Optimal design (T.A.: {transmission_angle:.1f}°)"
                    )
                else:
                    safety_message = (
                        f"{mechanism_class} - Good design (T.A.: {transmission_angle:.1f}°)"
                    )

            if quality_messages and safety_level == SafetyLevel.SAFE:
                safety_message += f" - Note: {', '.join(quality_messages)}"

            return SafetyStatus(level=safety_level, message=safety_message, details={})

        except Exception as e:
            return SafetyStatus(
                level=SafetyLevel.DANGER, message=f"Safety evaluation error: {str(e)}", details={}
            )

    def _calculate_forces(
        self, O1: QPointF, A: QPointF, B: QPointF, O4: QPointF, angle: float
    ) -> dict[str, ForceVector]:
        input_force = ForceVector(
            position=A,
            magnitude=40 + 10 * math.sin(angle),
            angle=math.degrees(angle + math.pi / 2),
            force_type=ForceType.APPLIED,
            label="F_in",
        )

        reaction_O1 = ForceVector(
            position=O1,
            magnitude=30,
            angle=math.degrees(angle + math.pi),
            force_type=ForceType.REACTION,
            label="R_O1",
        )

        return {"input": input_force, "reaction_O1": reaction_O1}
