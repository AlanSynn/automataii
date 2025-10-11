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
