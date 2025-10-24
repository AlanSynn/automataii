from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


Point = tuple[float, float]


@dataclass(frozen=True)
class MechanismExportData:
    mechanism_type: str
    parameters: Mapping[str, float]
    visual_config: VisualConfiguration
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VisualConfiguration:
    pivot_point: Point
    scale: float = 1.0
    color_scheme: str = "default"
    show_forces: bool = False
    show_constraints: bool = True


@dataclass(frozen=True)
class AnimationConfiguration:
    cycle_duration_ms: int = 3000
    steps_per_cycle: int = 60
    loop: bool = True


@dataclass(frozen=True)
class MechanismTransferPackage:
    export_data: MechanismExportData
    animation_config: AnimationConfiguration
    source_tab: str = "foundry"
    timestamp: float | None = None
    version: str = "1.0.0"


SUPPORTED_EXPORT_TYPES: frozenset[str] = frozenset(["four_bar", "cam_follower"])


def validate_export_type(mechanism_type: str) -> bool:
    return mechanism_type in SUPPORTED_EXPORT_TYPES
