from __future__ import annotations

import time
from typing import Any, Mapping

from automataii.core.telemetry import telemetry_span

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

            visual_config = VisualConfiguration(
                pivot_point=pivot_point,
                scale=scale,
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
            if not isinstance(value, (int, float)):
                raise TransferValidationError(f"Parameter {key} must be numeric, got {type(value)}")

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
                "spring_constant",
                "input_angle",
            },
        }
        return param_map.get(mechanism_type, set())
