from __future__ import annotations

import os
from typing import Dict, Mapping

from PyQt6.QtGui import QPainterPath

from automataii.application.mechanism_design import (
    MechanismDesignController,
    MechanismDesignState,
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


def _convert_paths(paths: Mapping[str, QPainterPath]) -> Dict[str, PartPath]:
    converted: Dict[str, PartPath] = {}
    for name, path in paths.items():
        if path is None or path.isEmpty():
            continue
        coords = qpainterpath_to_numpy_array(path)
        if coords is None or len(coords) == 0:
            continue
        converted[name] = PartPath.from_points(coords)
    return converted


class MechanismDesignControllerAdapter:
    """Bridge between legacy MechanismDesignTab and new controller."""

    def __init__(
        self,
        controller: MechanismDesignController,
    ) -> None:
        self._controller = controller

    @property
    def state(self) -> MechanismDesignState:
        return self._controller.state

    def update_from_editor_paths(
        self, paths: Mapping[str, QPainterPath]
    ) -> MechanismDesignState:
        converted = _convert_paths(paths)
        return self._controller.update_paths(converted)

    def enable_part(self, part_name: str, enabled: bool) -> MechanismDesignState:
        return self._controller.enable_part(part_name, enabled)

    def request_recommendations(self, part_name: str) -> tuple[Recommendation, ...]:
        recs = tuple(self._controller.request_recommendations(part_name))
        return recs

    def apply_recommendation(self, part_name: str, recommendation_id: str):
        return self._controller.apply_recommendation(part_name, recommendation_id)


def build_controller_adapter(
    recommendation_service: MechanismRecommendationService,
    generation_service: MechanismGenerationService,
) -> MechanismDesignControllerAdapter:
    controller = MechanismDesignController(
        recommendation_service=recommendation_service,
        generation_service=generation_service,
    )
    return MechanismDesignControllerAdapter(controller)
