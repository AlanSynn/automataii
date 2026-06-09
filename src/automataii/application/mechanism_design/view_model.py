from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .state import MechanismDesignState, MechanismLayer, PartPath, Recommendation


@dataclass(frozen=True)
class PartViewModel:
    name: str
    enabled: bool
    has_layers: bool
    is_selected: bool


@dataclass(frozen=True)
class MechanismLayerViewModel:
    id: str
    part_name: str
    type: str
    enabled: bool
    is_selected: bool
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class RecommendationViewModel:
    id: str
    type: str
    score: float
    params: Mapping[str, object]
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class MechanismDesignViewModel:
    parts: tuple[PartViewModel, ...]
    layers: tuple[MechanismLayerViewModel, ...]
    recommendations: tuple[RecommendationViewModel, ...]
    animation_running: bool
    parametric_mode: bool

    def find_part(self, name: str) -> PartViewModel | None:
        return next((p for p in self.parts if p.name == name), None)

    def find_layer(self, layer_id: str) -> MechanismLayerViewModel | None:
        return next((layer for layer in self.layers if layer.id == layer_id), None)


def view_model_from_state(state: MechanismDesignState) -> MechanismDesignViewModel:
    parts_vm = tuple(_part_vm(name, path, state) for name, path in state.paths.items())
    layers_vm = tuple(_layer_vm(layer_id, layer, state) for layer_id, layer in state.layers.items())
    rec_vm = tuple(_recommendation_vm(rec) for rec in state.recommendations)
    return MechanismDesignViewModel(
        parts=parts_vm,
        layers=layers_vm,
        recommendations=rec_vm,
        animation_running=state.animation_running,
        parametric_mode=state.parametric_mode,
    )


def _part_vm(name: str, path: PartPath, state: MechanismDesignState) -> PartViewModel:
    enabled = state.path_enabled.get(name, True)
    has_layers = any(layer_id.startswith(f"{name}:") for layer_id in state.layers.keys())
    is_selected = state.selected_part == name
    return PartViewModel(name=name, enabled=enabled, has_layers=has_layers, is_selected=is_selected)


def _layer_vm(
    layer_id: str, layer: MechanismLayer, state: MechanismDesignState
) -> MechanismLayerViewModel:
    part_name = layer_id.split(":", 1)[0] if ":" in layer_id else layer_id
    is_selected = state.selected_layer_id == layer_id
    return MechanismLayerViewModel(
        id=layer_id,
        part_name=part_name,
        type=layer.type,
        enabled=layer.enabled,
        is_selected=is_selected,
        metadata=dict(layer.metadata),
    )


def _recommendation_vm(rec: Recommendation) -> RecommendationViewModel:
    return RecommendationViewModel(
        id=rec.id,
        type=rec.type,
        score=rec.score,
        params=dict(rec.params),
        metadata=dict(rec.metadata),
    )
