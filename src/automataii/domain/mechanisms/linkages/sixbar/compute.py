from __future__ import annotations

import math
from dataclasses import dataclass

from automataii.domain.mechanisms.core.protocols import Mechanism
from automataii.domain.mechanisms.core.state import MechanismState, SafetyLevel, SafetyStatus
from automataii.domain.mechanisms.linkages.fivebar.compute import (
    FiveBarMechanism,
    FiveBarParameters,
)
from automataii.domain.mechanisms.linkage.config import LinkageConfig, LinkageType


@dataclass(frozen=True)
class SixBarParameters(FiveBarParameters):
    rocker_length: float
    pivot_height: float


class SixBarMechanism(Mechanism):
    def __init__(self, parameters: dict[str, float] | None = None) -> None:
        self._parameters = self._parse_parameters(parameters or {})
        self._five_bar = FiveBarMechanism()

    @property
    def mechanism_type(self) -> str:
        return "sixbar"

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
        base_params = FiveBarParameters(
            ground_spacing=params.ground_spacing,
            left_crank=params.left_crank,
            right_crank=params.right_crank,
            floating_length=params.floating_length,
            input_angle=params.input_angle,
        )
        base_positions = self._five_bar._solve_positions(base_params)

        p = base_positions["P"]
        g3 = (0.0, params.pivot_height)
        q = self._solve_rocker_point(p, g3, params.rocker_length)

        positions = dict(base_positions)
        positions["G3"] = g3
        positions["Q"] = q
        self._five_bar._add_custom_point(
            positions, parameters.get("coupler_custom_fraction")
        )

        metadata = self._build_metadata(params, positions)

        safety = SafetyStatus(level=SafetyLevel.SAFE, message="Nominal")

        return MechanismState(
            positions=positions,
            forces=None,
            safety_status=safety,
            metadata=metadata,
        )

    def _parse_parameters(self, params: dict[str, float]) -> SixBarParameters:
        ground = params.get("ground_link", 210.0)
        left = params.get("input_link", 55.0)
        floating = params.get("coupler_link", 160.0)
        right = params.get("output_link", 75.0)
        rocker = params.get("rocker_link", 95.0)
        angle = params.get("input_angle", 18.0)
        pivot_height = params.get("pivot_height", 0.6 * ground)

        return SixBarParameters(
            ground_spacing=ground,
            left_crank=left,
            right_crank=right,
            floating_length=floating,
            input_angle=angle,
            rocker_length=rocker,
            pivot_height=pivot_height,
        )

    @staticmethod
    def _solve_rocker_point(
        floating_point: tuple[float, float],
        pivot: tuple[float, float],
        rocker_length: float,
    ) -> tuple[float, float]:
        fx, fy = floating_point
        px, py = pivot
        dx = fx - px
        dy = fy - py
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            return pivot
        scale = min(rocker_length, dist) / dist
        return (px + dx * scale, py + dy * scale)

    def _build_metadata(
        self, params: SixBarParameters, positions: dict[str, tuple[float, float]]
    ) -> dict[str, object]:
        linkage_config = LinkageConfig(
            type=LinkageType.SIX_BAR,
            link_lengths=(
                params.ground_spacing,
                params.left_crank,
                params.floating_length,
                params.floating_length,
                params.right_crank,
                params.rocker_length,
            ),
            driver_index=1,
        )

        segments = (
            {"index": 1, "start": "G1", "end": "C1"},
            {"index": 2, "start": "C1", "end": "P"},
            {"index": 3, "start": "P", "end": "C2"},
            {"index": 4, "start": "C2", "end": "G2"},
            {"index": 5, "start": "G3", "end": "Q"},
            {"index": 6, "start": "P", "end": "Q"},  # Fixed: was duplicate index 3
            {"index": 0, "start": "G2", "end": "G1"},
        )

        metadata: dict[str, object] = {
            "driver": "Left crank",
            "ground_spacing": params.ground_spacing,
            "left_crank": params.left_crank,
            "right_crank": params.right_crank,
            "floating_length": params.floating_length,
            "rocker_length": params.rocker_length,
            "pivot_height": params.pivot_height,
            "linkage_segments": segments,
            "linkage_nodes": ("G1", "C1", "P", "Q", "C2", "G2", "G3"),
            "linkage_config": linkage_config,
        }

        custom = positions.get("coupler_custom")
        if custom:
            metadata["custom_point"] = custom

        return metadata
