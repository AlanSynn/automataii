from __future__ import annotations

from dataclasses import replace
from typing import Callable, Iterable, Mapping, Sequence

from automataii.core.telemetry import telemetry_span

from .controller import MechanismDesignController
from .state import MechanismDesignState, MechanismLayer, PartPath, Recommendation
from .view_model import MechanismDesignViewModel, view_model_from_state

ViewCallback = Callable[[MechanismDesignViewModel], None]


class MechanismDesignPresenter:
    """Adapter between MechanismDesignController and UI layer."""

    def __init__(self, controller: MechanismDesignController) -> None:
        self._controller = controller
        self._view_listeners: list[ViewCallback] = []
        self._view_model: MechanismDesignViewModel = view_model_from_state(controller.state)
        self._controller.add_listener(self._on_state_changed)

    def dispose(self) -> None:
        self._controller.remove_listener(self._on_state_changed)
        self._view_listeners.clear()

    # --- View binding -----------------------------------------------------
    def add_view_listener(self, callback: ViewCallback) -> None:
        if callback not in self._view_listeners:
            self._view_listeners.append(callback)
            callback(self._view_model)

    def remove_view_listener(self, callback: ViewCallback) -> None:
        if callback in self._view_listeners:
            self._view_listeners.remove(callback)

    @property
    def view_model(self) -> MechanismDesignViewModel:
        return self._view_model

    # --- Controller delegation ops ---------------------------------------
    def update_paths(self, part_paths: Mapping[str, PartPath]) -> MechanismDesignState:
        with telemetry_span("ui.mechanism_design.update_paths", part_count=len(part_paths)):
            return self._controller.update_paths(part_paths)

    def enable_part(self, part_name: str, enabled: bool) -> MechanismDesignState:
        with telemetry_span("ui.mechanism_design.enable_part", part=part_name, enabled=enabled):
            return self._controller.enable_part(part_name, enabled)

    def select_part(self, part_name: str | None) -> MechanismDesignState:
        with telemetry_span("ui.mechanism_design.select_part", part=part_name):
            return self._controller.select_part(part_name)

    def request_recommendations(self, part_name: str) -> Iterable[Recommendation]:
        with telemetry_span("ui.mechanism_design.request_recommendations", part=part_name):
            return self._controller.request_recommendations(part_name)

    def apply_recommendation(self, part_name: str, recommendation_id: str) -> MechanismLayer:
        with telemetry_span(
            "ui.mechanism_design.apply_recommendation",
            part=part_name,
            recommendation=recommendation_id,
        ):
            return self._controller.apply_recommendation(part_name, recommendation_id)

    def clear_part(self, part_name: str) -> MechanismDesignState:
        with telemetry_span("ui.mechanism_design.clear_part", part=part_name):
            return self._controller.clear_part(part_name)

    def clear_layer(self, layer_id: str) -> MechanismDesignState:
        with telemetry_span("ui.mechanism_design.clear_layer", layer=layer_id):
            return self._controller.clear_layer(layer_id)

    def set_animation_running(self, running: bool) -> MechanismDesignState:
        with telemetry_span("ui.mechanism_design.animation_toggle", running=running):
            return self._controller.set_animation_running(running)

    def set_parametric_mode(self, enabled: bool) -> MechanismDesignState:
        with telemetry_span("ui.mechanism_design.parametric_mode", enabled=enabled):
            return self._controller.set_parametric_mode(enabled)

    # --- State propagation -------------------------------------------------
    def _on_state_changed(self, state: MechanismDesignState) -> None:
        self._view_model = view_model_from_state(state)
        for callback in list(self._view_listeners):
            callback(self._view_model)
