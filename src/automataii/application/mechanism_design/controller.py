from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Iterable, Mapping, Protocol

from automataii.core.telemetry import telemetry_span

from .state import (
    MechanismDesignState,
    MechanismLayer,
    PartPath,
    Recommendation,
)


class MechanismRecommendationService(Protocol):
    def recommend(self, part_name: str, path: PartPath) -> Iterable[Recommendation]:
        ...


class MechanismGenerationService(Protocol):
    def build_layer(
        self, part_name: str, recommendation: Recommendation
    ) -> MechanismLayer:
        ...

    def clear_layers_for_part(self, part_name: str) -> None:
        ...


MechanismDesignListener = Callable[[MechanismDesignState], None]


class MechanismDesignController:
    """Application-layer orchestrator for mechanism design workflows."""

    def __init__(
        self,
        recommendation_service: MechanismRecommendationService,
        generation_service: MechanismGenerationService,
        *,
        initial_state: MechanismDesignState | None = None,
    ) -> None:
        self._recommendation_service = recommendation_service
        self._generation_service = generation_service
        self._state = initial_state or MechanismDesignState()
        self._listeners: list[MechanismDesignListener] = []

    @property
    def state(self) -> MechanismDesignState:
        return self._state

    def add_listener(self, listener: MechanismDesignListener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: MechanismDesignListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _set_state(self, new_state: MechanismDesignState) -> None:
        if new_state is self._state:
            return
        self._state = new_state
        snapshot = self._state
        for listener in list(self._listeners):
            listener(snapshot)

    # state mutators
    def update_paths(self, part_paths: Mapping[str, PartPath]) -> MechanismDesignState:
        with telemetry_span(
            "application.mechanism_design.update_paths", part_count=len(part_paths)
        ):
            new_state = self._state.with_paths(part_paths)
            layers = {
                lid: layer
                for lid, layer in new_state.layers.items()
                if layer.id.split(":")[0] in new_state.paths
            }
            new_state = new_state.with_layers(layers)
            self._set_state(new_state)
            return self._state

    def enable_part(self, part_name: str, enabled: bool) -> MechanismDesignState:
        self._set_state(self._state.enable_part(part_name, enabled))
        return self._state

    def select_part(self, part_name: str | None) -> MechanismDesignState:
        self._set_state(self._state.select_part(part_name))
        return self._state

    def request_recommendations(
        self, part_name: str
    ) -> Iterable[Recommendation]:
        if part_name not in self._state.enabled_paths:
            raise KeyError(f"No enabled path for part '{part_name}'")

        path = self._state.enabled_paths[part_name]
        with telemetry_span(
            "application.mechanism_design.recommend",
            part_name=part_name,
            point_count=len(path.points),
        ) as span:
            recommendations = tuple(
                self._recommendation_service.recommend(part_name, path)
            )
            span.set(count=len(recommendations))
            self._set_state(self._state.with_recommendations(recommendations))
            return recommendations

    def apply_recommendation(
        self, part_name: str, recommendation_id: str
    ) -> MechanismLayer:
        rec = self._find_recommendation(recommendation_id)
        with telemetry_span(
            "application.mechanism_design.apply_recommendation",
            part_name=part_name,
            recommendation_id=recommendation_id,
            mechanism_type=rec.type,
            score=rec.score,
        ) as span:
            layer = self._generation_service.build_layer(part_name, rec)
            layers = dict(self._state.layers)
            layers[layer.id] = layer
            self._set_state(self._state.with_layers(layers))
            span.set(status="success", layer_id=layer.id)
            return layer

    def clear_part(self, part_name: str) -> MechanismDesignState:
        if part_name in self._state.paths:
            self._generation_service.clear_layers_for_part(part_name)
        layers = {
            lid: layer
            for lid, layer in self._state.layers.items()
            if not lid.startswith(f"{part_name}:")
        }
        new_paths = {
            name: path for name, path in self._state.paths.items() if name != part_name
        }
        new_state = (
            self._state.with_paths(new_paths)
            .with_layers(layers)
            .select_part(
                self._state.selected_part if self._state.selected_part != part_name else None
            )
        )
        self._set_state(new_state)
        return self._state

    def clear_layer(self, layer_id: str) -> MechanismDesignState:
        if layer_id not in self._state.layers:
            raise KeyError(f"Unknown layer '{layer_id}'")
        layers = dict(self._state.layers)
        del layers[layer_id]
        self._set_state(self._state.with_layers(layers))
        return self._state

    def set_animation_running(self, running: bool) -> MechanismDesignState:
        self._set_state(self._state.set_animation_running(running))
        return self._state

    def set_parametric_mode(self, enabled: bool) -> MechanismDesignState:
        self._set_state(self._state.set_parametric_mode(enabled))
        return self._state

    # helpers
    def _find_recommendation(self, recommendation_id: str) -> Recommendation:
        for rec in self._state.recommendations:
            if rec.id == recommendation_id:
                return rec
        raise KeyError(f"Unknown recommendation '{recommendation_id}'")


def state_to_serializable(state: MechanismDesignState) -> dict[str, Any]:
    """Convert state to JSON-serializable dict for debugging/tests."""
    return {
        "paths": {
            name: {"points": list(path.points), "closed": path.closed}
            for name, path in state.paths.items()
        },
        "path_enabled": dict(state.path_enabled),
        "layers": {
            layer_id: {
                "type": layer.type,
                "params": dict(layer.params),
                "enabled": layer.enabled,
                "metadata": dict(layer.metadata),
            }
            for layer_id, layer in state.layers.items()
        },
        "selected_part": state.selected_part,
        "selected_layer_id": state.selected_layer_id,
        "animation_running": state.animation_running,
        "parametric_mode": state.parametric_mode,
        "recommendations": [asdict(rec) for rec in state.recommendations],
    }
