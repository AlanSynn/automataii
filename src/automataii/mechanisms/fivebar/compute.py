from __future__ import annotations

import math
from dataclasses import dataclass

from automataii.mechanisms.core.protocols import Mechanism
from automataii.mechanisms.core.state import MechanismState, SafetyLevel, SafetyStatus
from automataii.mechanisms.linkage.config import LinkageConfig, LinkageType


@dataclass(frozen=True)
class FiveBarParameters:
    ground_spacing: float
    left_crank: float
    right_crank: float
    floating_length: float
    input_angle: float


class FiveBarMechanism(Mechanism):
    def __init__(self, parameters: dict[str, float] | None = None) -> None:
        self._parameters = self._parse_parameters(parameters or {})

    @property
    def mechanism_type(self) -> str:
        return "fivebar"

    @property
    def required_parameters(self) -> frozenset[str]:
        return frozenset({"ground_link", "input_link", "coupler_link", "output_link"})

    def validate_parameters(self, parameters: dict[str, float]) -> None:
        for key in self.required_parameters:
            if key not in parameters:
                raise ValueError(f"Missing required parameter: {key}")
            if parameters[key] <= 0:
                raise ValueError(f"Parameter {key} must be positive")

    def compute_state(self, parameters: dict[str, float], input_angle: float) -> MechanismState:
        params = self._parse_parameters({**parameters, "input_angle": input_angle})
        positions = self._solve_positions(params)
        self._add_custom_point(positions, parameters.get("coupler_custom_fraction"))
        metadata = self._build_metadata(params, positions)

        safety = SafetyStatus(level=SafetyLevel.SAFE, message="Nominal")

        return MechanismState(
            positions=positions,
            forces=None,
            safety_status=safety,
            metadata=metadata,
        )

    def _parse_parameters(self, params: dict[str, float]) -> FiveBarParameters:
        ground = params.get("ground_link", 160.0)
        left = params.get("input_link", 70.0)
        floating = params.get("coupler_link", 120.0)
        right = params.get("output_link", 70.0)
        angle = params.get("input_angle", 30.0)

        return FiveBarParameters(
            ground_spacing=ground,
            left_crank=left,
            right_crank=right,
            floating_length=floating,
            input_angle=angle,
        )

    def _solve_positions(self, params: FiveBarParameters) -> dict[str, tuple[float, float]]:
        d = params.ground_spacing
        theta = math.radians(params.input_angle)
        phi = math.pi - theta

        g1 = (-d / 2.0, 0.0)
        g2 = (d / 2.0, 0.0)

        c1 = (
            g1[0] + params.left_crank * math.cos(theta),
            g1[1] + params.left_crank * math.sin(theta),
        )
        c2 = (
            g2[0] + params.right_crank * math.cos(phi),
            g2[1] + params.right_crank * math.sin(phi),
        )

        p = self._circle_intersection(c1, params.floating_length, c2, params.floating_length)
        if p is None:
            p = ((c1[0] + c2[0]) / 2.0, (c1[1] + c2[1]) / 2.0)

        positions = {
            "G1": g1,
            "G2": g2,
            "C1": c1,
            "C2": c2,
            "P": p,
        }

        return positions

    @staticmethod
    def _add_custom_point(
        positions: dict[str, tuple[float, float]], fraction: float | str | None
    ) -> None:
        """Add an interpolated custom point along the floating coupler chain."""
        if fraction is None:
            positions.pop("coupler_custom", None)
            return

        try:
            value = float(fraction)
        except (TypeError, ValueError):
            positions.pop("coupler_custom", None)
            return

        clamped = max(0.0, min(1.0, value))
        c1 = positions.get("C1")
        c2 = positions.get("C2")
        p = positions.get("P")

        if not c1 or not c2 or not p:
            positions.pop("coupler_custom", None)
            return

        if clamped <= 0.5:
            local_fraction = clamped * 2.0
            start, end = c1, p
        else:
            local_fraction = (clamped - 0.5) * 2.0
            start, end = p, c2

        sx, sy = start
        ex, ey = end
        positions["coupler_custom"] = (
            sx + (ex - sx) * local_fraction,
            sy + (ey - sy) * local_fraction,
        )

    def _build_metadata(
        self, params: FiveBarParameters, positions: dict[str, tuple[float, float]]
    ) -> dict[str, object]:
        linkage_config = LinkageConfig(
            type=LinkageType.FIVE_BAR,
            link_lengths=(
                params.ground_spacing,
                params.left_crank,
                params.floating_length,
                params.floating_length,
                params.right_crank,
            ),
            driver_index=1,
        )

        segments = (
            {"index": 1, "start": "G1", "end": "C1"},
            {"index": 2, "start": "C1", "end": "P"},
            {"index": 3, "start": "P", "end": "C2"},
            {"index": 4, "start": "C2", "end": "G2"},
            {"index": 0, "start": "G2", "end": "G1"},
        )

        metadata: dict[str, object] = {
            "driver": "Left crank",
            "ground_spacing": params.ground_spacing,
            "left_crank": params.left_crank,
            "right_crank": params.right_crank,
            "floating_length": params.floating_length,
            "linkage_segments": segments,
            "linkage_nodes": ("G1", "C1", "P", "C2", "G2"),
            "linkage_config": linkage_config,
        }

        custom = positions.get("coupler_custom")
        if custom:
            metadata["custom_point"] = custom

        return metadata

    @staticmethod
    def _circle_intersection(
        center_a: tuple[float, float],
        radius_a: float,
        center_b: tuple[float, float],
        radius_b: float,
    ) -> tuple[float, float] | None:
        ax, ay = center_a
        bx, by = center_b
        dx = bx - ax
        dy = by - ay
        d = math.hypot(dx, dy)

        if d < 1e-6:
            return None
        if d > radius_a + radius_b or d < abs(radius_a - radius_b):
            return None

        a = (radius_a**2 - radius_b**2 + d**2) / (2 * d)
        h_sq = radius_a**2 - a**2
        h = math.sqrt(max(h_sq, 0.0))

        xm = ax + a * dx / d
        ym = ay + a * dy / d

        rx = -dy * (h / d)
        ry = dx * (h / d)

        intersection1 = (xm + rx, ym + ry)
        intersection2 = (xm - rx, ym - ry)

        if intersection1[1] >= intersection2[1]:
            return intersection1
        return intersection2
