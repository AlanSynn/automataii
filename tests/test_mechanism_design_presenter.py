from __future__ import annotations

from collections.abc import Iterable

from automataii.application.mechanism_design import (
    MechanismDesignController,
    MechanismDesignPresenter,
    MechanismLayer,
    PartPath,
    Recommendation,
)


class DummyRecommendationService:
    def recommend(self, part_name: str, path: PartPath) -> Iterable[Recommendation]:
        yield Recommendation(
            id=f"{part_name}:four_bar",
            type="four_bar",
            params={"length": 42.0},
            score=0.9,
        )


class DummyGenerationService:
    def __init__(self) -> None:
        self._layers: dict[str, MechanismLayer] = {}

    def build_layer(self, part_name: str, recommendation: Recommendation) -> MechanismLayer:
        layer_id = f"{part_name}:{recommendation.type}"
        layer = MechanismLayer(id=layer_id, type=recommendation.type, params=recommendation.params)
        self._layers[layer_id] = layer
        return layer

    def clear_layers_for_part(self, part_name: str) -> None:
        self._layers = {k: v for k, v in self._layers.items() if not k.startswith(f"{part_name}:")}


def make_controller() -> MechanismDesignController:
    return MechanismDesignController(
        recommendation_service=DummyRecommendationService(),
        generation_service=DummyGenerationService(),
    )


def test_presenter_initial_view_model_empty():
    presenter = MechanismDesignPresenter(make_controller())
    vm = presenter.view_model
    assert vm.parts == ()
    assert vm.layers == ()
    assert vm.animation_running is False
    presenter.dispose()


def test_presenter_updates_view_on_path_change():
    presenter = MechanismDesignPresenter(make_controller())
    updates: list = []
    presenter.add_view_listener(lambda vm: updates.append(vm))

    presenter.update_paths({"arm": PartPath.from_points([(0, 0), (10, 10)])})
    assert presenter.view_model.find_part("arm") is not None
    assert presenter.view_model.find_part("arm").enabled is True
    assert presenter.view_model.find_part("arm").has_layers is False
    presenter.dispose()


def test_presenter_apply_recommendation_updates_layers():
    presenter = MechanismDesignPresenter(make_controller())
    presenter.update_paths({"arm": PartPath.from_points([(0, 0), (10, 10)])})
    recs = presenter.request_recommendations("arm")
    rec = next(iter(recs))
    layer = presenter.apply_recommendation("arm", rec.id)

    vm = presenter.view_model
    assert vm.find_part("arm").has_layers is True
    assert vm.find_layer(layer.id) is not None
    presenter.dispose()


def test_presenter_select_part_updates_view():
    presenter = MechanismDesignPresenter(make_controller())
    presenter.update_paths({"arm": PartPath.from_points([(0, 0), (10, 10)])})
    presenter.select_part("arm")
    assert presenter.view_model.find_part("arm").is_selected is True
    presenter.dispose()
