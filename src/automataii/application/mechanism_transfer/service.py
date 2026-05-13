from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from typing import Any

from automataii.infrastructure.telemetry import telemetry_span

from .contract import (
    AnimationConfiguration,
    MechanismExportData,
    MechanismTransferPackage,
    Point,
    VisualConfiguration,
    validate_export_type,
)


class TransferValidationError(Exception):
    pass


class MechanismTransferService:
    def __init__(self) -> None:
        self._last_export: MechanismTransferPackage | None = None

    def create_export_package(
        self,
        mechanism_type: str,
        parameters: Mapping[str, float],
        pivot_point: Point,
        *,
        scale: float = 1.0,
        color_scheme: str = "default",
        show_forces: bool = False,
        show_constraints: bool = True,
        cycle_duration_ms: int = 3000,
        steps_per_cycle: int = 60,
        loop: bool = True,
        metadata: Mapping[str, Any] | None = None,
    ) -> MechanismTransferPackage:
        with telemetry_span(
            "application.mechanism_transfer.create_export",
            mechanism_type=mechanism_type,
            param_count=len(parameters),
        ) as span:
            if not validate_export_type(mechanism_type):
                msg = f"Unsupported mechanism type for export: {mechanism_type}"
                span.set(status="error", error=msg)
                raise TransferValidationError(msg)

            self._validate_parameters(mechanism_type, parameters)
            normalized_pivot_point, normalized_scale = self._validate_visual_config(
                pivot_point, scale
            )
            self._validate_animation_config(cycle_duration_ms, steps_per_cycle)

            visual_config = VisualConfiguration(
                pivot_point=normalized_pivot_point,
                scale=normalized_scale,
                color_scheme=color_scheme,
                show_forces=show_forces,
                show_constraints=show_constraints,
            )

            animation_config = AnimationConfiguration(
                cycle_duration_ms=cycle_duration_ms,
                steps_per_cycle=steps_per_cycle,
                loop=loop,
            )

            export_data = MechanismExportData(
                mechanism_type=mechanism_type,
                parameters=dict(parameters),
                visual_config=visual_config,
                metadata=dict(metadata or {}),
            )

            package = MechanismTransferPackage(
                export_data=export_data,
                animation_config=animation_config,
                source_tab="foundry",
                timestamp=time.time(),
            )

            self._last_export = package
            span.set(status="success")
            return package

    def validate_import_package(self, package: MechanismTransferPackage) -> bool:
        with telemetry_span(
            "application.mechanism_transfer.validate_import",
            mechanism_type=package.export_data.mechanism_type,
        ) as span:
            try:
                if not validate_export_type(package.export_data.mechanism_type):
                    raise TransferValidationError(
                        f"Unsupported mechanism type: {package.export_data.mechanism_type}"
                    )

                self._validate_parameters(
                    package.export_data.mechanism_type,
                    package.export_data.parameters,
                )
                self._validate_visual_config(
                    package.export_data.visual_config.pivot_point,
                    package.export_data.visual_config.scale,
                )
                self._validate_animation_config(
                    package.animation_config.cycle_duration_ms,
                    package.animation_config.steps_per_cycle,
                )

                span.set(status="success")
                return True
            except TransferValidationError as e:
                span.set(status="error", error=str(e))
                return False

    def get_last_export(self) -> MechanismTransferPackage | None:
        return self._last_export

    def _validate_parameters(self, mechanism_type: str, parameters: Mapping[str, float]) -> None:
        required_params = self._get_required_parameters(mechanism_type)
        missing = set(required_params) - set(parameters.keys())
        if missing:
            raise TransferValidationError(
                f"Missing required parameters for {mechanism_type}: {missing}"
            )

        for key, value in parameters.items():
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise TransferValidationError(f"Parameter {key} must be numeric, got {type(value)}")
            if not math.isfinite(float(value)):
                raise TransferValidationError(f"Parameter {key} must be finite, got {value}")

    def _validate_visual_config(self, pivot_point: Point, scale: float) -> tuple[Point, float]:
        if (
            not isinstance(pivot_point, Sequence)
            or isinstance(pivot_point, str | bytes | bytearray)
            or len(pivot_point) != 2
        ):
            raise TransferValidationError(f"pivot_point must contain two numeric values: {pivot_point}")

        normalized_pivot: list[float] = []
        for index, value in enumerate(pivot_point):
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise TransferValidationError(
                    f"pivot_point[{index}] must be numeric, got {type(value)}"
                )
            if not math.isfinite(float(value)):
                raise TransferValidationError(f"pivot_point[{index}] must be finite, got {value}")
            normalized_pivot.append(float(value))

        if isinstance(scale, bool) or not isinstance(scale, int | float):
            raise TransferValidationError(f"scale must be numeric, got {type(scale)}")
        if not math.isfinite(float(scale)) or float(scale) <= 0.0:
            raise TransferValidationError(f"scale must be a positive finite value, got {scale}")
        return (normalized_pivot[0], normalized_pivot[1]), float(scale)

    def _validate_animation_config(self, cycle_duration_ms: int, steps_per_cycle: int) -> None:
        for key, value in (
            ("cycle_duration_ms", cycle_duration_ms),
            ("steps_per_cycle", steps_per_cycle),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TransferValidationError(f"{key} must be an integer, got {type(value)}")
            if value <= 0:
                raise TransferValidationError(f"{key} must be positive, got {value}")

    def _get_required_parameters(self, mechanism_type: str) -> set[str]:
        param_map = {
            "four_bar": {
                "ground_link",
                "input_link",
                "coupler_link",
                "output_link",
                "input_angle",
            },
            "cam_follower": {
                "cam_radius",
                "cam_offset",
                "follower_length",
                "input_angle",
            },
            "gear_train": {
                "gear1_teeth",
                "gear2_teeth",
                "input_torque",
                "input_angle",
            },
            "slider_crank": {
                "crank_length",
                "rod_length",
                "gas_pressure",
                "input_angle",
            },
        }
        return param_map.get(mechanism_type, set())
