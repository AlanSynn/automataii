from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, Mapping, Tuple


Point = Tuple[float, float]


@dataclass(frozen=True)
class PartPath:
    """Immutable representation of a motion path."""

    points: Tuple[Point, ...]
    closed: bool = False

    @classmethod
    def from_points(cls, points: Iterable[Point], closed: bool = False) -> "PartPath":
        return cls(tuple((float(x), float(y)) for x, y in points), closed)


@dataclass(frozen=True)
class MechanismLayer:
    """Representation of a generated mechanism layer."""

    id: str
    type: str
    params: Mapping[str, Any]
    enabled: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Recommendation:
    """Mechanism recommendation returned by recommendation service."""

    id: str
    type: str
    params: Mapping[str, Any]
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MechanismDesignState:
    """
    View-model capturing the mutable state needed by MechanismDesignTab.
    Designed to be toolkit-agnostic so tests can run without PyQt.
    """

    paths: Mapping[str, PartPath] = field(default_factory=dict)
    path_enabled: Mapping[str, bool] = field(default_factory=dict)
    layers: Mapping[str, MechanismLayer] = field(default_factory=dict)
    selected_part: str | None = None
    selected_layer_id: str | None = None
    animation_running: bool = False
    parametric_mode: bool = False
    recommendations: Tuple[Recommendation, ...] = field(default_factory=tuple)

    def with_paths(self, paths: Mapping[str, PartPath]) -> "MechanismDesignState":
        default_enabled = {
            name: self.path_enabled.get(name, True) for name in paths.keys()
        }
        return replace(
            self,
            paths=dict(paths),
            path_enabled=default_enabled,
            # Reset selections that are no longer valid
            selected_part=self.selected_part if self.selected_part in paths else None,
        )

    def enable_part(self, part_name: str, enabled: bool) -> "MechanismDesignState":
        if part_name not in self.paths:
            raise KeyError(f"Unknown part '{part_name}'")
        updated = dict(self.path_enabled)
        updated[part_name] = enabled
        return replace(self, path_enabled=updated)

    def with_layers(self, layers: Mapping[str, MechanismLayer]) -> "MechanismDesignState":
        selected_layer = (
            self.selected_layer_id if self.selected_layer_id in layers else None
        )
        return replace(self, layers=dict(layers), selected_layer_id=selected_layer)

    def select_part(self, part_name: str | None) -> "MechanismDesignState":
        if part_name is not None and part_name not in self.paths:
            raise KeyError(f"Unknown part '{part_name}'")
        return replace(self, selected_part=part_name)

    def select_layer(self, layer_id: str | None) -> "MechanismDesignState":
        if layer_id is not None and layer_id not in self.layers:
            raise KeyError(f"Unknown layer '{layer_id}'")
        return replace(self, selected_layer_id=layer_id)

    def set_animation_running(self, running: bool) -> "MechanismDesignState":
        return replace(self, animation_running=running)

    def set_parametric_mode(self, enabled: bool) -> "MechanismDesignState":
        return replace(self, parametric_mode=enabled)

    def with_recommendations(
        self, recommendations: Iterable[Recommendation]
    ) -> "MechanismDesignState":
        return replace(self, recommendations=tuple(recommendations))

    @property
    def enabled_paths(self) -> Dict[str, PartPath]:
        return {
            name: path
            for name, path in self.paths.items()
            if self.path_enabled.get(name, True)
        }
