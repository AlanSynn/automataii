from __future__ import annotations

import pytest

from automataii.application.mechanism_design import (
    MechanismDesignController,
    MechanismLayer,
    PartPath,
    Recommendation,
)


class DummyRecommendationService:
    def __init__(self, recommendations: list[Recommendation] | None = None) -> None:
        self.recommendations = recommendations or []
        self.calls: list[str] = []

    def recommend(self, part_name: str, path: PartPath):
        self.calls.append(part_name)
        return list(self.recommendations)


class DummyGenerationService:
    def __init__(self) -> None:
        self.built: list[tuple[str, Recommendation]] = []
        self.cleared_parts: list[str] = []

    def build_layer(self, part_name: str, recommendation: Recommendation) -> MechanismLayer:
        self.built.append((part_name, recommendation))
        return MechanismLayer(
            id=f"{part_name}:{recommendation.id}",
            type=recommendation.type,
            params=recommendation.params,
            enabled=True,
            metadata={"score": recommendation.score},
        )

    def clear_layers_for_part(self, part_name: str) -> None:
        self.cleared_parts.append(part_name)


@pytest.fixture()
def controller() -> MechanismDesignController:
    rec = Recommendation(
        id="rec-1",
        type="4_bar_linkage",
        params={"l1": 10},
        score=0.1,
    )
    recommendation_service = DummyRecommendationService([rec])
    generation_service = DummyGenerationService()
    controller = MechanismDesignController(recommendation_service, generation_service)
    controller.update_paths({"arm": PartPath.from_points([(0, 0), (10, 10)])})
    return controller


def test_update_paths_sets_state(controller: MechanismDesignController) -> None:
    assert "arm" in controller.state.paths
    assert controller.state.path_enabled["arm"] is True


def test_enable_part_updates_flag(controller: MechanismDesignController) -> None:
    controller.enable_part("arm", False)
    assert controller.state.path_enabled["arm"] is False


def test_request_recommendations_returns_and_updates_state(
    controller: MechanismDesignController,
) -> None:
    recs = controller.request_recommendations("arm")
    assert len(tuple(recs)) == 1
    assert controller.state.recommendations[0].id == "rec-1"


def test_apply_recommendation_builds_layer(controller: MechanismDesignController) -> None:
    controller.request_recommendations("arm")
    layer = controller.apply_recommendation("arm", "rec-1")
    assert layer.id == "arm:rec-1"
    assert layer.id in controller.state.layers


def test_clear_part_removes_paths_and_layers(controller: MechanismDesignController) -> None:
    controller.request_recommendations("arm")
    controller.apply_recommendation("arm", "rec-1")
    controller.clear_part("arm")
    assert "arm" not in controller.state.paths
    assert controller.state.layers == {}
