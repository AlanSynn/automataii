from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPathItem

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


def test_ensure_4bar_parameters_uses_joint_positions_without_transform() -> None:
    service = ParametricParameterService()
    params = {"coupler_point_x": 0.0, "coupler_point_y": 0.0}
    context = ParametricContext(
        mechanism_type="4_bar_linkage",
        params=params,
        full_simulation_data={
            "joint_positions": {
                "p1_positions": [[0.0, 0.0]],
                "p2_positions": [[100.0, 0.0]],
                "p3_positions": [[30.0, 40.0]],
                "p4_positions": [[80.0, 50.0]],
            }
        },
        transform_params={},
    )

    service.ensure_parameters(context)

    assert params["crank_x"] == pytest.approx(30.0)
    assert params["crank_y"] == pytest.approx(40.0)
    assert params["rocker_x"] == pytest.approx(80.0)
    assert params["rocker_y"] == pytest.approx(50.0)


def test_ensure_4bar_parameters_syncs_stale_lengths_from_explicit_scene_positions() -> None:
    service = ParametricParameterService()
    params = {
        "anchor1_x": 0.0,
        "anchor1_y": 0.0,
        "anchor2_x": 100.0,
        "anchor2_y": 0.0,
        "crank_x": 30.0,
        "crank_y": 40.0,
        "rocker_x": 80.0,
        "rocker_y": 50.0,
        "l1": 999.0,
        "L1": 999.0,
        "l2": 999.0,
        "L2": 999.0,
        "l3": 999.0,
        "L3": 999.0,
        "l4": 999.0,
        "L4": 999.0,
    }
    context = ParametricContext(
        mechanism_type="4_bar_linkage",
        params=params,
        full_simulation_data={},
        transform_params={},
    )

    service.ensure_parameters(context)

    assert params["l1"] == params["L1"] == pytest.approx(100.0)
    assert params["l2"] == params["L2"] == pytest.approx(50.0)
    assert params["l3"] == params["L3"] == pytest.approx(math.hypot(50.0, 10.0))
    assert params["l4"] == params["L4"] == pytest.approx(math.hypot(-20.0, 50.0))
    assert params["input_angle"] == pytest.approx(params["crank_angle"])


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


def test_gear_setup_honors_string_false_grid_flag() -> None:
    service = ParametricParameterService()
    params = {
        "r1": 36.0,
        "r2": 54.0,
        "gear1_teeth": 12,
        "gear2_teeth": 18,
        "grid_system_enabled": "false",
    }
    context = ParametricContext(
        mechanism_type="gear",
        params=params,
        full_simulation_data={},
        transform_params={},
    )

    service.ensure_parameters(context)

    assert params["gear1_radius"] == 36.0
    assert params["gear2_radius"] == 54.0
    assert params["gear1_teeth"] == 12
    assert params["gear2_teeth"] == 18


def test_gear_setup_preserves_user_values_even_when_grid_enabled() -> None:
    service = ParametricParameterService()
    params = {
        "gear1_radius": 33.0,
        "gear2_radius": 47.0,
        "gear1_teeth": 13,
        "gear2_teeth": 17,
        "grid_system_enabled": True,
    }
    context = ParametricContext(
        mechanism_type="gear",
        params=params,
        full_simulation_data={},
        transform_params={},
    )

    service.ensure_parameters(context)

    assert params["gear1_radius"] == pytest.approx(33.0)
    assert params["gear2_radius"] == pytest.approx(47.0)
    assert params["r1"] == pytest.approx(33.0)
    assert params["r2"] == pytest.approx(47.0)
    assert params["gear1_teeth"] == 13
    assert params["gear2_teeth"] == 17


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


def test_fourbar_parametric_snap_does_not_force_full_rotation_grashof() -> None:
    from automataii.presentation.qt.tabs.parametric_editing_manager import (
        ParametricEditingManager,
    )

    manager = ParametricEditingManager(SimpleNamespace())
    params = {"L1": 200.0, "L2": 10.0, "L3": 10.0, "L4": 180.0}
    layer_data = {"type": "4_bar_linkage", "params": params}

    changed = manager._enforce_grashof_and_snap(layer_data)

    assert changed is False
    assert params == {"L1": 200.0, "L2": 10.0, "L3": 10.0, "L4": 180.0}


def test_parametric_manager_gear_snap_is_alert_only() -> None:
    from automataii.presentation.qt.tabs.parametric_editing_manager import (
        ParametricEditingManager,
    )

    manager = ParametricEditingManager(SimpleNamespace())
    params = {
        "gear1_x": 0.0,
        "gear1_y": 0.0,
        "gear2_x": 200.0,
        "gear2_y": 0.0,
        "gear1_radius": 20.0,
        "gear2_radius": 20.0,
    }

    changed = manager._enforce_gear_meshing_and_snap({"params": params})

    assert changed is False
    assert params["gear2_x"] == pytest.approx(200.0)
    assert params["gear2_y"] == pytest.approx(0.0)


def test_parametric_manager_cam_snap_is_alert_only() -> None:
    from automataii.presentation.qt.tabs.parametric_editing_manager import (
        ParametricEditingManager,
    )

    manager = ParametricEditingManager(SimpleNamespace())
    params = {"follower_rod_length": 2.0, "base_radius": -5.0}

    changed = manager._enforce_cam_follower_snap({"params": params})

    assert changed is False
    assert params == {"follower_rod_length": 2.0, "base_radius": -5.0}


def test_regenerate_4bar_uses_valid_angle_bounds_without_moving_current_pose() -> None:
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
        "l2": 80.0,
        "l3": 50.0,
        "l4": 50.0,
        "crank_angle": 30.0,
        "valid_angle_min": 0.0,
        "valid_angle_max": 72.0,
    }

    manager._regenerate_4bar_simulation(layer_data, params)
    joints = layer_data["full_simulation_data"]["joint_positions"]
    p3_positions = np.array(joints["p3_positions"], dtype=float)
    generated_angles = np.degrees(np.arctan2(p3_positions[:, 1], p3_positions[:, 0])) % 360.0

    assert generated_angles[0] == pytest.approx(30.0)
    assert generated_angles.min() >= 0.0
    assert generated_angles.max() <= 72.0


def test_regenerate_4bar_wrap_bounds_keep_normalized_current_pose() -> None:
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
        "l2": 80.0,
        "l3": 50.0,
        "l4": 50.0,
        "crank_angle": 330.0,
        "valid_angle_min": -65.0,
        "valid_angle_max": 65.0,
    }

    manager._regenerate_4bar_simulation(layer_data, params)
    joints = layer_data["full_simulation_data"]["joint_positions"]
    p3_positions = np.array(joints["p3_positions"], dtype=float)
    generated_angles = np.degrees(np.arctan2(p3_positions[:, 1], p3_positions[:, 0])) % 360.0

    assert generated_angles[0] == pytest.approx(330.0)


def test_regenerate_4bar_without_transform_preserves_explicit_scene_branch() -> None:
    from automataii.presentation.qt.tabs.parametric_editing_manager import (
        ParametricEditingManager,
    )

    class _DummyParentTab:
        def _get_inverse_scene_transform_function(self, _layer_data):
            return None

        def _get_scene_transform_function(self, _layer_data):
            return None

    manager = ParametricEditingManager(_DummyParentTab())
    layer_data = {
        "transform_params": {"scale": 1.0},
        "generated_path": None,
    }
    params = {
        "anchor1_x": 0.0,
        "anchor1_y": 0.0,
        "anchor2_x": 100.0,
        "anchor2_y": 0.0,
        "crank_x": 40.0,
        "crank_y": 0.0,
        "rocker_x": 70.0,
        "rocker_y": -40.0,
        "L2": 40.0,
        "L3": 50.0,
        "L4": 50.0,
        "l2": 40.0,
        "l3": 50.0,
        "l4": 50.0,
        "crank_angle": 0.0,
    }

    manager._regenerate_4bar_simulation(layer_data, params)

    assert layer_data["key_points"]["crank_end"] == pytest.approx([40.0, 0.0])
    assert layer_data["key_points"]["rocker_end"] == pytest.approx([70.0, -40.0])
    assert params["rocker_x"] == pytest.approx(70.0)
    assert params["rocker_y"] == pytest.approx(-40.0)


def test_regenerate_4bar_stores_scene_key_points_for_foundry_style_layer() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )
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
    }
    params = {
        "anchor1_x": 0.0,
        "anchor1_y": 0.0,
        "anchor2_x": 200.0,
        "anchor2_y": 0.0,
        "crank_x": 80.0,
        "crank_y": 0.0,
        "rocker_x": 140.0,
        "rocker_y": -80.0,
        "L2": 40.0,
        "L3": 50.0,
        "L4": 50.0,
    }

    manager._regenerate_4bar_simulation(layer_data, params)

    assert layer_data["key_points"]["ground_pivot_2"] == pytest.approx([200.0, 0.0])
    assert layer_data["key_points"]["crank_end"] == pytest.approx([80.0, 0.0])
    assert layer_data["key_points"]["rocker_end"] == pytest.approx([140.0, -80.0])

    reload_params = {"l1": 100.0, "l2": 40.0, "l3": 50.0, "l4": 50.0}
    reload_layer = {
        "generated_path": None,
        "full_simulation_data": {},
        "key_points": layer_data["key_points"],
        "params": reload_params,
    }
    ParameterMapper().ensure_mechanism_parameters(
        reload_layer,
        "4_bar_linkage",
        to_scene=lambda arr: DummyPoint(float(arr[0]) * 2.0, float(arr[1]) * 2.0),
    )

    assert reload_params["anchor2_x"] == pytest.approx(200.0)
    assert reload_params["crank_x"] == pytest.approx(80.0)
    assert reload_params["rocker_y"] == pytest.approx(-80.0)


def test_regenerate_4bar_does_not_double_scene_key_points_without_inverse() -> None:
    from automataii.presentation.qt.tabs.parametric_editing_manager import (
        ParametricEditingManager,
    )

    class _SceneOnlyParentTab:
        def _get_inverse_scene_transform_function(self, _layer_data):
            return None

        def _get_scene_transform_function(self, _layer_data):
            return lambda arr: DummyPoint(float(arr[0]) * 2.0, float(arr[1]) * 2.0)

    manager = ParametricEditingManager(_SceneOnlyParentTab())
    layer_data = {
        "generated_path": None,
        "key_points": {},
    }
    params = {
        "anchor1_x": 10.0,
        "anchor1_y": 20.0,
        "anchor2_x": 200.0,
        "anchor2_y": 20.0,
        "crank_x": 80.0,
        "crank_y": 60.0,
        "rocker_x": 140.0,
        "rocker_y": -80.0,
        "l3": math.hypot(60.0, -140.0),
    }

    manager._regenerate_4bar_simulation(layer_data, params)

    assert layer_data["key_points"]["ground_pivot_1"] == pytest.approx([10.0, 20.0])
    assert layer_data["key_points"]["ground_pivot_2"] == pytest.approx([200.0, 20.0])
    assert layer_data["key_points"]["crank_end"] == pytest.approx([80.0, 60.0])
    assert layer_data["key_points"]["rocker_end"] == pytest.approx([140.0, -80.0])


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


def test_parameter_mapper_4bar_keeps_explicit_scene_positions_over_stale_simulation() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    params = {
        "anchor1_x": 10.0,
        "anchor1_y": 20.0,
        "anchor2_x": 110.0,
        "anchor2_y": 20.0,
        "crank_x": 45.0,
        "crank_y": 60.0,
        "rocker_x": 95.0,
        "rocker_y": 55.0,
    }
    layer_data = {
        "params": params,
        "full_simulation_data": {
            "joint_positions": {
                "p1_positions": [[0.0, 0.0]],
                "p2_positions": [[100.0, 0.0]],
                "p3_positions": [[999.0, 999.0]],
                "p4_positions": [[888.0, 888.0]],
            }
        },
    }

    mapper.ensure_mechanism_parameters(layer_data, "4_bar_linkage")

    assert params["crank_x"] == pytest.approx(45.0)
    assert params["crank_y"] == pytest.approx(60.0)
    assert params["rocker_x"] == pytest.approx(95.0)
    assert params["rocker_y"] == pytest.approx(55.0)
    assert params["l1"] == params["L1"] == pytest.approx(100.0)
    assert params["l2"] == params["L2"] == pytest.approx(math.hypot(35.0, 40.0))
    assert params["l3"] == params["L3"] == pytest.approx(math.hypot(50.0, -5.0))
    assert params["l4"] == params["L4"] == pytest.approx(math.hypot(-15.0, 35.0))
    assert params["input_angle"] == pytest.approx(params["crank_angle"])


def test_parameter_mapper_4bar_uses_simulation_joints_without_transform() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    params = {"coupler_point_x": 0.0, "coupler_point_y": 0.0}
    layer_data = {
        "params": params,
        "full_simulation_data": {
            "joint_positions": {
                "p1_positions": [[0.0, 0.0]],
                "p2_positions": [[100.0, 0.0]],
                "p3_positions": [[30.0, 40.0]],
                "p4_positions": [[80.0, 50.0]],
            }
        },
    }

    mapper.ensure_mechanism_parameters(layer_data, "4_bar_linkage")

    assert params["crank_x"] == pytest.approx(30.0)
    assert params["crank_y"] == pytest.approx(40.0)
    assert params["rocker_x"] == pytest.approx(80.0)
    assert params["rocker_y"] == pytest.approx(50.0)


def test_parameter_mapper_replaces_malformed_params_container() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    layer_data = {
        "params": ["not", "a", "dict"],
        "key_points": None,
        "cam_position": [float("nan"), 240.0],
    }

    mapper.ensure_mechanism_parameters(layer_data, "cam")

    assert isinstance(layer_data["params"], dict)
    assert layer_data["params"]["center_x"] == 400.0
    assert layer_data["params"]["center_y"] == 300.0


def test_parameter_mapper_4bar_ignores_malformed_simulation_payload() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    params = {"l1": "bad", "anchor1_x": float("nan")}
    layer_data = {
        "params": params,
        "key_points": None,
        "full_simulation_data": {
            "joint_positions": {
                "p1_positions": None,
                "p2_positions": [[0.0, 0.0]],
            }
        },
    }

    mapper.ensure_mechanism_parameters(layer_data, "4_bar_linkage")

    assert params["anchor1_x"] == 400.0
    assert params["anchor2_x"] == 500.0
    assert params["coupler_x"] == 450.0


def test_parameter_mapper_sanitizes_gear_radius_aliases_and_positions() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    params = {
        "r1": "bad",
        "gear2_radius": float("nan"),
        "gear1_x": "left",
        "gear1_y": float("inf"),
    }
    layer_data = {"params": params, "full_simulation_data": {"gear_data": {"gear1_centers": []}}}

    mapper.ensure_mechanism_parameters(layer_data, "gear")

    assert params["gear1_radius"] == 30.0
    assert params["gear2_radius"] == 30.0
    assert params["gear1_teeth"] == 24
    assert params["gear2_teeth"] == 24
    assert params["gear1_x"] == 400.0
    assert params["gear1_y"] == 300.0
    assert params["gear2_x"] == 460.0


def test_parameter_mapper_honors_string_false_grid_flag() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    params = {
        "r1": 36.0,
        "r2": 54.0,
        "gear1_teeth": 12,
        "gear2_teeth": 18,
        "grid_system_enabled": "false",
    }

    mapper.ensure_mechanism_parameters({"params": params}, "gear")

    assert params["gear1_radius"] == 36.0
    assert params["gear2_radius"] == 54.0
    assert params["gear1_teeth"] == 12
    assert params["gear2_teeth"] == 18


def test_parameter_mapper_preserves_user_values_even_when_grid_enabled() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    params = {
        "gear1_radius": 33.0,
        "gear2_radius": 47.0,
        "gear1_teeth": 13,
        "gear2_teeth": 17,
        "grid_system_enabled": True,
    }

    mapper.ensure_mechanism_parameters({"params": params}, "gear")

    assert params["gear1_radius"] == pytest.approx(33.0)
    assert params["gear2_radius"] == pytest.approx(47.0)
    assert params["r1"] == pytest.approx(33.0)
    assert params["r2"] == pytest.approx(47.0)
    assert params["gear1_teeth"] == 13
    assert params["gear2_teeth"] == 17


def test_parametric_manager_regenerate_gear_honors_string_false_grid_flag() -> None:
    from automataii.presentation.qt.tabs.parametric_editing_manager import (
        ParametricEditingManager,
    )

    manager = ParametricEditingManager.__new__(ParametricEditingManager)
    layer_data: dict[str, object] = {}
    params = {
        "grid_system_enabled": "false",
        "gear1_radius": 36.0,
        "gear2_radius": 54.0,
        "gear1_teeth": 12,
        "gear2_teeth": 18,
    }

    manager._regenerate_gear_simulation(layer_data, params)

    assert params["gear1_radius"] == 36.0
    assert params["gear2_radius"] == 54.0
    assert params["gear1_teeth"] == 12
    assert params["gear2_teeth"] == 18
    assert "gear_data" in layer_data["full_simulation_data"]


def test_parametric_manager_regenerate_gear_preserves_user_values_when_grid_enabled() -> None:
    from automataii.presentation.qt.tabs.parametric_editing_manager import (
        ParametricEditingManager,
    )

    manager = ParametricEditingManager.__new__(ParametricEditingManager)
    layer_data: dict[str, object] = {}
    params = {
        "grid_system_enabled": True,
        "gear1_radius": 33.0,
        "gear2_radius": 47.0,
        "gear1_teeth": 13,
        "gear2_teeth": 17,
    }

    manager._regenerate_gear_simulation(layer_data, params)

    assert params["gear1_radius"] == pytest.approx(33.0)
    assert params["gear2_radius"] == pytest.approx(47.0)
    assert params["r1"] == pytest.approx(33.0)
    assert params["r2"] == pytest.approx(47.0)
    assert params["gear1_teeth"] == 13
    assert params["gear2_teeth"] == 17
    assert "gear_data" in layer_data["full_simulation_data"]


def test_parametric_manager_regenerate_gear_persists_scene_key_points() -> None:
    from automataii.presentation.qt.tabs.parametric_editing_manager import (
        ParametricEditingManager,
    )

    manager = ParametricEditingManager.__new__(ParametricEditingManager)
    layer_data: dict[str, object] = {
        "generated_path": None,
        "key_points": {
            "gear1_center": [5.0, 5.0],
            "gear2_center": [15.0, 5.0],
        },
    }
    params = {
        "gear1_x": 100.0,
        "gear1_y": 40.0,
        "gear2_x": 190.0,
        "gear2_y": 40.0,
        "gear1_radius": 33.0,
        "gear2_radius": 47.0,
    }

    manager._regenerate_gear_simulation(layer_data, params)

    assert layer_data["key_points"]["gear1_center"] == pytest.approx([100.0, 40.0])
    assert layer_data["key_points"]["gear2_center"] == pytest.approx([190.0, 40.0])


def test_parametric_manager_regenerate_gear_stores_mech_key_points_for_generated_path() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )
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
        "generated_path": object(),
        "key_points": {},
    }
    params = {
        "gear1_x": 100.0,
        "gear1_y": 40.0,
        "gear2_x": 190.0,
        "gear2_y": 40.0,
        "gear1_radius": 33.0,
        "gear2_radius": 47.0,
    }

    manager._regenerate_gear_simulation(layer_data, params)

    assert layer_data["key_points"]["gear1_center"] == pytest.approx([50.0, 20.0])
    assert layer_data["key_points"]["gear2_center"] == pytest.approx([95.0, 20.0])

    reload_params = {"gear1_radius": 33.0, "gear2_radius": 47.0}
    reload_layer = {
        "generated_path": object(),
        "params": reload_params,
        "full_simulation_data": {},
        "key_points": layer_data["key_points"],
    }
    ParameterMapper().ensure_mechanism_parameters(
        reload_layer,
        "gear",
        to_scene=lambda arr: DummyPoint(float(arr[0]) * 2.0, float(arr[1]) * 2.0),
    )
    assert reload_params["gear1_x"] == pytest.approx(100.0)
    assert reload_params["gear1_y"] == pytest.approx(40.0)
    assert reload_params["gear2_x"] == pytest.approx(190.0)
    assert reload_params["gear2_y"] == pytest.approx(40.0)


def test_parameter_mapper_gear_uses_scene_key_points_when_generated_path_none() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    params = {
        "gear1_radius": 33.0,
        "gear2_radius": 47.0,
    }
    layer_data = {
        "generated_path": None,
        "params": params,
        "full_simulation_data": {},
        "key_points": {
            "gear1_center": [100.0, 40.0],
            "gear2_center": [190.0, 40.0],
        },
    }

    ParameterMapper().ensure_mechanism_parameters(
        layer_data,
        "gear",
        to_scene=lambda arr: DummyPoint(float(arr[0]) * 2.0, float(arr[1]) * 2.0),
    )

    assert params["gear1_x"] == pytest.approx(100.0)
    assert params["gear1_y"] == pytest.approx(40.0)
    assert params["gear2_x"] == pytest.approx(190.0)
    assert params["gear2_y"] == pytest.approx(40.0)


def test_parametric_mode_does_not_leave_mechanism_visuals_draggable() -> None:
    import logging

    from automataii.presentation.qt.tabs.parametric_editing_manager import (
        ParametricEditingManager,
    )

    visual = QGraphicsPathItem()
    manager = ParametricEditingManager.__new__(ParametricEditingManager)
    manager.parent_tab = SimpleNamespace(
        mechanism_layers={"m1": {}},
        mechanism_path_items={"m1": [visual]},
        path_visual_items={},
    )
    manager._logger = logging.getLogger("test")

    manager._enable_mechanism_visual_interaction()

    assert bool(visual.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
    assert not bool(visual.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable)


def test_parameter_mapper_uses_valid_gear_radius_alias_when_primary_is_bad() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    params = {
        "gear1_radius": float("nan"),
        "r1": 12.0,
        "gear2_radius": "bad",
        "r2": 24.0,
    }

    mapper.ensure_mechanism_parameters({"params": params}, "gear")

    assert params["gear1_radius"] == 12.0
    assert params["gear2_radius"] == 24.0
    assert params["gear1_teeth"] == 10
    assert params["gear2_teeth"] == 19
    assert params["gear2_x"] == 436.0


def test_parameter_mapper_rejects_non_finite_radius_transform() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    params = {"r1": 10.0, "r2": 20.0}

    def to_scene(arr: np.ndarray) -> DummyPoint:
        if float(arr[0]) > 0:
            return DummyPoint(float("inf"), 0.0)
        return DummyPoint(0.0, 0.0)

    mapper.ensure_mechanism_parameters(
        {"params": params, "full_simulation_data": {}},
        "gear",
        to_scene=to_scene,
    )

    assert params["gear1_radius"] == 10.0
    assert params["gear2_radius"] == 20.0
    assert math.isfinite(params["gear2_x"])


def test_parameter_mapper_ignores_malformed_gear_simulation_centers() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()

    gear_params: dict[str, float] = {}
    mapper.ensure_mechanism_parameters(
        {
            "params": gear_params,
            "full_simulation_data": {
                "gear_data": {
                    "gear1_centers": object(),
                    "gear2_centers": [[float("nan"), 0.0]],
                }
            },
        },
        "gear",
        to_scene=lambda arr: DummyPoint(float(arr[0]), float(arr[1])),
    )

    assert gear_params["gear1_x"] == 400.0
    assert gear_params["gear2_x"] == 460.0

    planetary_params: dict[str, float] = {}
    mapper.ensure_mechanism_parameters(
        {
            "params": planetary_params,
            "full_simulation_data": {
                "gear_positions": {
                    "sun_centers": object(),
                    "planet_centers": [[float("inf"), 0.0]],
                }
            },
        },
        "planetary_gear",
        to_scene=lambda arr: DummyPoint(float(arr[0]), float(arr[1])),
    )

    assert planetary_params["sun_x"] == 400.0
    assert planetary_params["planet_x"] == 450.0


def test_parameter_mapper_accepts_numpy_simulation_center_arrays() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    gear_params: dict[str, float] = {}

    mapper.ensure_mechanism_parameters(
        {
            "params": gear_params,
            "full_simulation_data": {
                "gear_data": {
                    "gear1_centers": np.array([[10.0, 20.0]]),
                    "gear2_centers": np.array([[30.0, 40.0]]),
                }
            },
        },
        "gear",
        to_scene=lambda arr: DummyPoint(float(arr[0]), float(arr[1])),
    )

    assert gear_params["gear1_x"] == 10.0
    assert gear_params["gear1_y"] == 20.0
    assert gear_params["gear2_x"] == 30.0
    assert gear_params["gear2_y"] == 40.0


def test_parameter_mapper_sanitizes_planetary_aliases_and_positions() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    params = {
        "r_sun": "bad",
        "r_planet": float("nan"),
        "arm_length": -5.0,
        "sun_x": "bad",
        "sun_y": float("inf"),
        "planet_x": float("nan"),
    }
    layer_data = {"params": params, "full_simulation_data": {}, "key_points": None}

    mapper.ensure_mechanism_parameters(layer_data, "planetary_gear")

    assert params["r_sun"] == 20.0
    assert params["r_planet"] == 30.0
    assert params["arm_length"] == 15.0
    assert params["sun_x"] == 400.0
    assert params["sun_y"] == 300.0
    assert params["planet_x"] == 450.0
    assert params["gear2_x"] == 450.0


def test_parameter_mapper_uses_valid_planetary_alias_when_primary_is_bad() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
    )

    mapper = ParameterMapper()
    params = {
        "r_sun": float("nan"),
        "gear1_radius": 22.0,
        "r_planet": "bad",
        "planet_radius": 33.0,
        "arm_length": float("inf"),
        "carrier_length": 17.0,
        "sun_x": "bad",
        "gear1_x": 410.0,
        "planet_x": float("nan"),
        "gear2_x": 470.0,
    }

    mapper.ensure_mechanism_parameters({"params": params}, "planetary_gear")

    assert params["r_sun"] == 22.0
    assert params["r_planet"] == 33.0
    assert params["arm_length"] == 17.0
    assert params["sun_x"] == 410.0
    assert params["planet_x"] == 470.0


def test_parameter_mapper_transform_config_rejects_non_finite_payloads() -> None:
    from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
        ParameterMapper,
        TransformConfig,
    )

    mapper = ParameterMapper()
    config = mapper.get_transform_config(
        {
            "transform_params": {
                "scale": 0.0,
                "offset_x": float("nan"),
                "offset_y": "bad",
            },
            "generated_path": object(),
        },
        path_converter=lambda _path: [[0.0, 0.0], [float("inf"), 1.0]],
    )

    assert config.scale == 1.0
    assert config.user_scale == 100.0
    assert config.offset_x == 0.0
    assert config.offset_y == 0.0
    assert (
        mapper.scene_to_mech_length(float("inf"), TransformConfig(scale=0.0, user_scale=0.0)) == 0.0
    )
    assert math.isfinite(
        mapper.mech_to_scene_length(5.0, TransformConfig(scale=0.0, user_scale=0.0))
    )


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
    # Foundry-style generated_path=None layers persist scene-space key_points for reload.
    assert layer_data["key_points"]["sun_center"] == [100.0, 40.0]
    assert layer_data["key_points"]["planet_center"] == [200.0, 40.0]
    assert layer_data["key_points"]["tracking_point"] == [230.0, 40.0]
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
