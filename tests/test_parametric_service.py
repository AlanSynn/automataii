from __future__ import annotations

import numpy as np

from automataii.application.mechanism_design.parametric_service import (
    ParametricContext,
    ParametricParameterService,
)


class DummyPoint:
    def __init__(self, x: float, y: float) -> None:
        self._x = x
        self._y = y

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y


def test_ensure_cam_parameters_with_position() -> None:
    service = ParametricParameterService()
    params = {}
    context = ParametricContext(
        mechanism_type="cam",
        params=params,
        full_simulation_data={},
        transform_params={},
        cam_position=(320, 240),
    )
    service.ensure_parameters(context)
    assert params["center_x"] == 320
    assert params["center_y"] == 240


def test_ensure_4bar_parameters_sets_scene_positions() -> None:
    service = ParametricParameterService()
    params = {"coupler_point_x": 5.0, "coupler_point_y": 2.0}

    def to_scene(arr: np.ndarray) -> DummyPoint:
        return DummyPoint(float(arr[0]) * 10, float(arr[1]) * 10)

    context = ParametricContext(
        mechanism_type="4_bar_linkage",
        params=params,
        full_simulation_data={
            "joint_positions": {
                "p1_positions": [[0.0, 0.0]],
                "p2_positions": [[1.0, 0.0]],
                "p3_positions": [[0.5, 0.5]],
                "p4_positions": [[1.0, 0.5]],
            }
        },
        transform_params={"scale": 1.0},
        cam_position=None,
        to_scene=to_scene,
    )
    service.ensure_parameters(context)
    assert params["anchor1_x"] == 0.0
    assert params["anchor2_x"] == 10.0
    assert "coupler_x" in params
    assert "rocker_angle" in params


def test_gear_defaults_without_simulation() -> None:
    service = ParametricParameterService()
    params = {"r1": 40, "r2": 60}
    context = ParametricContext(
        mechanism_type="gear",
        params=params,
        full_simulation_data={},
        transform_params={},
        cam_position=None,
        to_scene=None,
    )
    service.ensure_parameters(context)
    assert params["gear1_x"] == 400
    assert params["gear2_x"] > params["gear1_x"]


def test_planetary_defaults_include_editor_aliases() -> None:
    service = ParametricParameterService()
    params = {"r_sun": 20.0, "r_planet": 30.0, "arm_length": 15.0}
    context = ParametricContext(
        mechanism_type="planetary_gear",
        params=params,
        full_simulation_data={},
        transform_params={},
        cam_position=None,
        to_scene=None,
    )
    service.ensure_parameters(context)
    assert params["sun_x"] == params["gear1_x"]
    assert params["sun_y"] == params["gear1_y"]
    assert params["planet_x"] == params["gear2_x"]
    assert params["planet_y"] == params["gear2_y"]
    assert params["gear1_radius"] == params["r_sun"]
    assert params["gear2_radius"] == params["r_planet"]


def test_regenerate_4bar_keeps_lengths_without_inverse_transform() -> None:
    from automataii.presentation.qt.tabs.parametric_editing_manager import (
        ParametricEditingManager,
    )

    class _DummyParentTab:
        def _get_inverse_scene_transform_function(self, _layer_data):
            return None

    manager = ParametricEditingManager(_DummyParentTab())
    layer_data = {
        "transform_params": {"scale": 1.0},
        "generated_path": None,
    }
    params = {
        "ground_pivot_1": [0.0, 0.0],
        "ground_pivot_2": [100.0, 0.0],
        "l2": 40.0,
        "l3": 80.0,
        "l4": 70.0,
    }

    manager._regenerate_4bar_simulation(layer_data, params)
    joints = layer_data["full_simulation_data"]["joint_positions"]
    p3_0 = joints["p3_positions"][0]

    # At frame 0, p3 should be exactly one crank length from p1 along +X.
    assert p3_0[0] == 40.0


def test_parameter_mapper_4bar_uses_key_points_when_simulation_missing() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    params = {"l1": 140.0, "l2": 60.0, "l3": 100.0, "l4": 90.0}
    layer_data = {
        "generated_path": None,  # Foundry-style: key_points are already scene-space.
        "full_simulation_data": {},
        "key_points": {
            "ground_pivot_1": [510.0, 330.0],
            "ground_pivot_2": [650.0, 330.0],
            "crank_end": [560.0, 260.0],
            "rocker_end": [620.0, 270.0],
        },
        "params": params,
    }

    mapper.ensure_mechanism_parameters(
        layer_data,
        "4_bar_linkage",
        to_scene=lambda arr: DummyPoint(float(arr[0]) * 10.0, float(arr[1]) * 10.0),
    )

    assert params["anchor1_x"] == 510.0
    assert params["anchor1_y"] == 330.0
    assert params["anchor2_x"] == 650.0
    assert params["anchor2_y"] == 330.0
    assert params["crank_x"] == 560.0
    assert params["rocker_x"] == 620.0


def test_regenerate_planetary_uses_scene_center_over_stale_key_points() -> None:
    from automataii.presentation.qt.tabs.parametric_editing_manager import (
        ParametricEditingManager,
    )

    class _DummyParentTab:
        def _get_inverse_scene_transform_function(self, _layer_data):
            return lambda pt: np.array([float(pt.x()) / 2.0, float(pt.y()) / 2.0])

        def _get_scene_transform_function(self, _layer_data):
            return lambda arr: DummyPoint(float(arr[0]) * 2.0, float(arr[1]) * 2.0)

    manager = ParametricEditingManager(_DummyParentTab())
    layer_data = {
        "transform_params": {"scale": 1.0},
        "generated_path": None,
        "key_points": {"sun_center": [0.0, 0.0]},
    }
    params = {
        "sun_x": 100.0,
        "sun_y": 40.0,
        "r_sun": 20.0,
        "r_planet": 30.0,
        "arm_length": 15.0,
    }

    manager._regenerate_planetary_gear_simulation(layer_data, params)
    gear_positions = layer_data["full_simulation_data"]["gear_positions"]

    # Scene center (100,40) maps to mechanism center (50,20) through inverse transform.
    assert gear_positions["sun_centers"][0] == [50.0, 20.0]
    assert layer_data["key_points"]["sun_center"] == [50.0, 20.0]
    assert params["sun_x"] == 100.0
    assert params["sun_y"] == 40.0
    # First frame planet center at +X by r_sun+r_planet (50 mech units) -> scene x +100.
    assert params["planet_x"] == 200.0
    assert params["planet_y"] == 40.0


def test_parameter_mapper_planetary_uses_key_points_when_simulation_missing() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    params = {"r_sun": 20.0, "r_planet": 30.0, "arm_length": 15.0}
    layer_data = {
        "generated_path": None,  # Foundry-style: key_points are already scene-space.
        "full_simulation_data": {},
        "key_points": {
            "sun_center": [510.0, 330.0],
            "planet_center": [560.0, 330.0],
        },
        "params": params,
    }

    mapper.ensure_mechanism_parameters(
        layer_data,
        "planetary_gear",
        to_scene=lambda arr: DummyPoint(float(arr[0]) * 10.0, float(arr[1]) * 10.0),
    )

    assert params["sun_x"] == 510.0
    assert params["sun_y"] == 330.0
    assert params["gear1_x"] == 510.0
    assert params["gear1_y"] == 330.0
    assert params["planet_x"] == 560.0
    assert params["planet_y"] == 330.0
    assert params["gear2_x"] == 560.0
    assert params["gear2_y"] == 330.0


def test_regenerate_planetary_prefers_mechanism_alias_over_stale_scene_center() -> None:
    from automataii.presentation.qt.tabs.parametric_editing_manager import (
        ParametricEditingManager,
    )

    class _DummyParentTab:
        def _get_inverse_scene_transform_function(self, _layer_data):
            return lambda pt: np.array([float(pt.x()) / 2.0, float(pt.y()) / 2.0])

        def _get_scene_transform_function(self, _layer_data):
            return lambda arr: DummyPoint(float(arr[0]) * 2.0, float(arr[1]) * 2.0)

    manager = ParametricEditingManager(_DummyParentTab())
    layer_data = {
        "transform_params": {"scale": 1.0},
        "generated_path": None,
        "key_points": {"sun_center": [0.0, 0.0]},
    }
    params = {
        "m_sun_x": 10.0,
        "m_sun_y": 5.0,
        "sun_x": 999.0,  # stale scene-space center; should be ignored
        "sun_y": 888.0,
        "r_sun": 20.0,
        "r_planet": 30.0,
        "arm_length": 15.0,
    }

    manager._regenerate_planetary_gear_simulation(layer_data, params)
    gear_positions = layer_data["full_simulation_data"]["gear_positions"]

    assert gear_positions["sun_centers"][0] == [10.0, 5.0]
    # Scene aliases are recomputed from mechanism aliases via to_scene (x2 transform).
    assert params["sun_x"] == 20.0
    assert params["sun_y"] == 10.0
