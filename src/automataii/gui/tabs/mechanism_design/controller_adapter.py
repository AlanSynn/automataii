from __future__ import annotations

import os
from typing import Dict, Mapping

from PyQt6.QtGui import QPainterPath

from automataii.application.mechanism_design import (
    MechanismDesignController,
    MechanismDesignState,
    MechanismLayer,
    MechanismDesignPresenter,
    PartPath,
    Recommendation,
)
from automataii.application.mechanism_design.controller import (
    MechanismGenerationService,
    MechanismRecommendationService,
)
from automataii.gui.tabs.mechanism_design.mechanism_design_utils import (
    qpainterpath_to_numpy_array,
)


def feature_enabled() -> bool:
    flag = os.getenv("AUTOMATAII_MECH_CONTROLLER", "0").lower()
    return flag in {"1", "true", "yes", "on"}


def convert_paths(paths: Mapping[str, QPainterPath]) -> Dict[str, PartPath]:
    converted: Dict[str, PartPath] = {}
    for name, path in paths.items():
        if path is None or path.isEmpty():
            continue
        coords = qpainterpath_to_numpy_array(path)
        if coords is None or len(coords) == 0:
            continue
        converted[name] = PartPath.from_points(coords)
    return converted


class _LegacyRecommendationService(MechanismRecommendationService):
    """Placeholder recommendation service until presenter wiring is complete."""

    def __init__(self, tab) -> None:
        self._tab = tab

    def recommend(self, part_name: str, path: PartPath):
        # TODO: Integrate with MechanismService once legacy flow is migrated.
        return ()


class _LegacyGenerationService(MechanismGenerationService):
    """Placeholder generation service that creates stub layers."""

    def __init__(self, tab) -> None:
        self._tab = tab
        self._counter = 0

    def build_layer(self, part_name: str, recommendation: Recommendation) -> MechanismLayer:
        self._counter += 1
        layer_id = f"{part_name}:{recommendation.type or 'legacy'}:{self._counter}"
        return MechanismLayer(
            id=layer_id,
            type=recommendation.type or "legacy",
            params=dict(recommendation.params),
            metadata=dict(recommendation.metadata),
        )

    def clear_layers_for_part(self, part_name: str) -> None:
        # Legacy tab still manages layer removal; no-op here.
        return


def build_presenter(tab) -> MechanismDesignPresenter:
    controller = MechanismDesignController(
        recommendation_service=_LegacyRecommendationService(tab),
        generation_service=_LegacyGenerationService(tab),
    )
    return MechanismDesignPresenter(controller)
