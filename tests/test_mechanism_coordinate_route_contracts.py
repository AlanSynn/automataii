"""Route-level coordinate contracts for cam/linkage screen alignment."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import cast

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

from automataii.presentation.qt.tabs.cam_geometry import cam_contact_y_from_params
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_utils import (
    qpainterpath_to_numpy_array,
)
from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
    MechanismInstantiationService,
)
from automataii.presentation.qt.tabs.parametric.components import ParameterMapper
from automataii.presentation.qt.tabs.parametric_editing_manager import ParametricEditingManager


def _target_rect_path() -> QPainterPath:
    path = QPainterPath()
    path.addRect(100.0, 50.0, 80.0, 50.0)
    return path


def _params(layer_data: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], layer_data["params"])


def _key_points(layer_data: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], layer_data["key_points"])


def _cam_centers(layer_data: dict[str, object]) -> list[list[float]]:
    simulation_data = cast(dict[str, object], layer_data["full_simulation_data"])
    cam_data = cast(dict[str, object], simulation_data["cam_data"])
    return cast(list[list[float]], cam_data["cam_centers"])


def _assert_cam_center_aliases(
    layer_data: dict[str, object], expected_center: list[float]
) -> None:
    params = _params(layer_data)
    key_points = _key_points(layer_data)
    assert layer_data["cam_position"] == pytest.approx(expected_center)
    assert params["cam_center"] == pytest.approx(expected_center)
    assert key_points["cam_center"] == pytest.approx(expected_center)
    assert params["center_x"] == pytest.approx(expected_center[0])
    assert params["center_y"] == pytest.approx(expected_center[1])


class _TranslatedParent:
    def __init__(self, dx: float, dy: float) -> None:
        self._dx = dx
        self._dy = dy

    def _get_scene_transform_function(
        self, _layer_data: dict[str, object]
    ) -> Callable[[Sequence[float]], QPointF]:
        def to_scene(point: Sequence[float]) -> QPointF:
            return QPointF(float(point[0]) + self._dx, float(point[1]) + self._dy)

        return to_scene

    def _get_inverse_scene_transform_function(
        self, _layer_data: dict[str, object]
    ) -> Callable[[QPointF], list[float]]:
        def to_mech(point: QPointF) -> list[float]:
            return [float(point.x()) - self._dx, float(point.y()) - self._dy]

        return to_mech


class _BrokenSceneParent:
    def _get_scene_transform_function(
        self, _layer_data: dict[str, object]
    ) -> Callable[[Sequence[float]], QPointF]:
        def to_scene(_point: Sequence[float]) -> QPointF:
            raise ValueError("broken transform")

        return to_scene

    def _get_inverse_scene_transform_function(
        self, _layer_data: dict[str, object]
    ) -> None:
        return None


class _BrokenInverseParent(_TranslatedParent):
    def _get_inverse_scene_transform_function(
        self, _layer_data: dict[str, object]
    ) -> Callable[[QPointF], list[float]]:
        def to_mech(_point: QPointF) -> list[float]:
            raise ValueError("broken inverse transform")

        return to_mech


def test_recommendation_cam_route_aligns_contact_and_center_aliases() -> None:
    service = MechanismInstantiationService()
    service.set_path_converter(qpainterpath_to_numpy_array)
    path = _target_rect_path()

    layer_data, _graphics_data = service.create_layer_data_from_recommendation(
        mechanism_data={
            "type": "Cam & Follower",
            "parameters": {
                "base_radius": 25.0,
                "eccentricity": 10.0,
                "follower_rod_length": 40.0,
            },
        },
        target_path=path,
        fallback_position=[400.0, 300.0],
    )

    contact_y = cam_contact_y_from_params(
        _params(layer_data),
        scale=cast(float, layer_data["cam_scale_factor"]),
    )
    expected_center = [140.0, 100.0 - contact_y]
    _assert_cam_center_aliases(layer_data, expected_center)
    assert cast(float, _params(layer_data)["center_y"]) + contact_y == pytest.approx(100.0)


def test_candidate_cam_route_synchronizes_scene_center_aliases() -> None:
    service = MechanismInstantiationService()
    service.set_path_converter(qpainterpath_to_numpy_array)
    path = _target_rect_path()

    layer_data = service.create_layer_data_from_candidate(
        candidate_data={
            "type": "Cam Profile",
            "parameters": {
                "base_radius": 30.0,
                "eccentricity": 12.0,
                "follower_rod_length": 44.0,
            },
        },
        selected_part_name="torso",
        target_path=path,
        convert_params_fn=lambda _mechanism_type, params: dict(params),
        extract_key_points_fn=None,
    )

    contact_y = cam_contact_y_from_params(
        _params(layer_data),
        scale=cast(float, layer_data["cam_scale_factor"]),
    )
    expected_center = [140.0, 100.0 - contact_y]
    _assert_cam_center_aliases(layer_data, expected_center)
    assert cast(float, _params(layer_data)["center_y"]) + contact_y == pytest.approx(100.0)


def test_parametric_cam_regeneration_uses_existing_scene_center_not_origin() -> None:
    manager = ParametricEditingManager(parent_tab=object())
    layer_data: dict[str, object] = {
        "type": "cam",
        "cam_position": [240.0, 180.0],
        "cam_scale_factor": 1.25,
        "rod_length_multiplier": 1.25,
        "params": {
            "center_x": 240.0,
            "center_y": 180.0,
            "base_radius": 25.0,
            "eccentricity": 10.0,
            "follower_rod_length": 40.0,
        },
        "key_points": {},
    }

    manager._regenerate_cam_simulation(layer_data, _params(layer_data))

    _assert_cam_center_aliases(layer_data, [240.0, 180.0])
    assert _cam_centers(layer_data)[0] == pytest.approx([240.0, 180.0])
    contact_point = cast(list[float], _key_points(layer_data)["contact_point"])
    assert contact_point[0] == pytest.approx(240.0)


def test_parametric_cam_regeneration_prefers_scene_center_over_mechanism_keypoint() -> None:
    manager = ParametricEditingManager(parent_tab=_TranslatedParent(230.0, 160.0))
    layer_data: dict[str, object] = {
        "type": "cam",
        "cam_position": [240.0, 180.0],
        "cam_scale_factor": 1.0,
        "rod_length_multiplier": 1.0,
        "params": {
            "center_x": 240.0,
            "center_y": 180.0,
            "base_radius": 25.0,
            "eccentricity": 10.0,
            "follower_rod_length": 40.0,
        },
        "key_points": {"cam_center": [10.0, 20.0]},
    }

    manager._regenerate_cam_simulation(layer_data, _params(layer_data))

    params = _params(layer_data)
    key_points = _key_points(layer_data)
    assert layer_data["cam_position"] == pytest.approx([240.0, 180.0])
    assert params["cam_center"] == pytest.approx([240.0, 180.0])
    assert params["center_x"] == pytest.approx(240.0)
    assert params["center_y"] == pytest.approx(180.0)
    assert key_points["cam_center"] == pytest.approx([10.0, 20.0])
    assert _cam_centers(layer_data)[0] == pytest.approx([240.0, 180.0])


def test_parametric_cam_regeneration_maps_mechanism_keypoint_when_scene_alias_missing() -> None:
    manager = ParametricEditingManager(parent_tab=_TranslatedParent(230.0, 160.0))
    layer_data: dict[str, object] = {
        "type": "cam",
        "cam_scale_factor": 1.0,
        "rod_length_multiplier": 1.0,
        "params": {
            "base_radius": 25.0,
            "eccentricity": 10.0,
            "follower_rod_length": 40.0,
        },
        "key_points": {"cam_center": [10.0, 20.0]},
    }

    manager._regenerate_cam_simulation(layer_data, _params(layer_data))

    params = _params(layer_data)
    key_points = _key_points(layer_data)
    assert layer_data["cam_position"] == pytest.approx([240.0, 180.0])
    assert params["cam_center"] == pytest.approx([240.0, 180.0])
    assert params["center_x"] == pytest.approx(240.0)
    assert params["center_y"] == pytest.approx(180.0)
    assert key_points["cam_center"] == pytest.approx([10.0, 20.0])


def test_parametric_cam_regeneration_does_not_treat_unmapped_mech_keypoint_as_scene() -> None:
    manager = ParametricEditingManager(parent_tab=_BrokenSceneParent())
    layer_data: dict[str, object] = {
        "type": "cam",
        "cam_scale_factor": 1.0,
        "rod_length_multiplier": 1.0,
        "params": {
            "base_radius": 25.0,
            "eccentricity": 10.0,
            "follower_rod_length": 40.0,
        },
        "key_points": {"cam_center": [10.0, 20.0]},
    }

    manager._regenerate_cam_simulation(layer_data, _params(layer_data))

    params = _params(layer_data)
    key_points = _key_points(layer_data)
    assert layer_data["cam_position"] == pytest.approx([0.0, 0.0])
    assert params["cam_center"] == pytest.approx([0.0, 0.0])
    assert key_points["cam_center"] == pytest.approx([0.0, 0.0])


def test_parametric_cam_regeneration_preserves_keypoint_when_inverse_mapping_fails() -> None:
    manager = ParametricEditingManager(parent_tab=_BrokenInverseParent(230.0, 160.0))
    layer_data: dict[str, object] = {
        "type": "cam",
        "cam_position": [240.0, 180.0],
        "cam_scale_factor": 1.0,
        "rod_length_multiplier": 1.0,
        "params": {
            "center_x": 240.0,
            "center_y": 180.0,
            "base_radius": 25.0,
            "eccentricity": 10.0,
            "follower_rod_length": 40.0,
        },
        "key_points": {"cam_center": [10.0, 20.0]},
    }

    manager._regenerate_cam_simulation(layer_data, _params(layer_data))

    assert layer_data["cam_position"] == pytest.approx([240.0, 180.0])
    assert _params(layer_data)["cam_center"] == pytest.approx([240.0, 180.0])
    assert _key_points(layer_data)["cam_center"] == pytest.approx([10.0, 20.0])


def test_parameter_mapper_prefers_scene_cam_position_over_mechanism_keypoint() -> None:
    mapper = ParameterMapper()
    params: dict[str, float] = {}
    layer_data: dict[str, object] = {
        "cam_position": [240.0, 180.0],
        "key_points": {"cam_center": [10.0, 20.0]},
    }

    mapper._setup_cam_parameters(
        layer_data,
        params,
        to_scene=lambda point: QPointF(float(point[0]) + 300.0, float(point[1]) + 400.0),
    )

    assert params["center_x"] == pytest.approx(240.0)
    assert params["center_y"] == pytest.approx(180.0)


def test_parameter_mapper_maps_mechanism_keypoint_only_after_scene_aliases() -> None:
    mapper = ParameterMapper()
    params: dict[str, float] = {}
    layer_data: dict[str, object] = {"key_points": {"cam_center": [10.0, 20.0]}}

    mapper._setup_cam_parameters(
        layer_data,
        params,
        to_scene=lambda point: QPointF(float(point[0]) + 230.0, float(point[1]) + 160.0),
    )

    assert params["center_x"] == pytest.approx(240.0)
    assert params["center_y"] == pytest.approx(180.0)
