from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence, Tuple

Point = Tuple[float, float]


@dataclass(frozen=True)
class VisualConfiguration:
    pivot_point: Point | None = None
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
class MechanismSpec:
    """Unified mechanism representation for transfer between UI surfaces."""

    mechanism_type: str
    parameters: Mapping[str, float]
    transform_params: Mapping[str, Any] | None = None
    visualization_params: Mapping[str, Any] | None = None
    key_points: Mapping[str, Any] | None = None
    full_simulation_data: Mapping[str, Any] | None = None
    generated_path_points: Sequence[Point] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    visual_config: VisualConfiguration = field(default_factory=VisualConfiguration)
    animation_config: AnimationConfiguration = field(default_factory=AnimationConfiguration)
    source_tab: str = "unknown"
    timestamp: float | None = None

    def with_metadata(self, extra: Mapping[str, Any]) -> "MechanismSpec":
        merged = dict(self.metadata)
        merged.update(extra)
        return replace(self, metadata=merged)


SUPPORTED_EXPORT_TYPES: frozenset[str] = frozenset(
    [
        # Legacy linkages (backward compatibility)
        "four_bar",
        "four_bar_linkage",
        "4_bar_linkage",
        # Unified linkage architecture
        "linkages",
        "unified_linkage",
        # Other mechanisms
        "cam",
        "cam_follower",
        "gear",
        "planetary_gear",
    ]
)


def validate_export_type(mechanism_type: str) -> bool:
    return mechanism_type in SUPPORTED_EXPORT_TYPES
