from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QPointF

from automataii.presentation.qt.tabs.mechanism_design.components.mechanism_output_calculator import (
    MechanismOutputCalculator,
)


def _scene_transform(_layer_data: dict):
    return lambda point: QPointF(float(point[0]), float(point[1]))


def test_4bar_output_mode_joint_a_uses_input_joint_position() -> None:
    calculator = MechanismOutputCalculator(get_scene_transform=_scene_transform)
    layer_data = {
        "full_simulation_data": {
            "joint_positions": {
                "p1_positions": [[0.0, 0.0]],
                "p3_positions": [[12.0, 25.0]],
                "p4_positions": [[44.0, 55.0]],
            }
        }
    }

    point = calculator.calculate_output(
        mech_type="4_bar_linkage",
        params={"output_point_mode": "joint_a"},
        time=0.0,
        layer_data=layer_data,
    )

    assert point is not None
    assert point.x() == pytest.approx(12.0)
    assert point.y() == pytest.approx(25.0)


def test_4bar_output_mode_joint_b_uses_output_joint_position() -> None:
    calculator = MechanismOutputCalculator(get_scene_transform=_scene_transform)
    layer_data = {
        "full_simulation_data": {
            "joint_positions": {
                "p1_positions": [[0.0, 0.0]],
                "p3_positions": [[12.0, 25.0]],
                "p4_positions": [[44.0, 55.0]],
            }
        }
    }

    point = calculator.calculate_output(
        mech_type="4_bar_linkage",
        params={"output_point_mode": "joint_b"},
        time=0.0,
        layer_data=layer_data,
    )

    assert point is not None
    assert point.x() == pytest.approx(44.0)
    assert point.y() == pytest.approx(55.0)


def test_cam_output_mode_contact_point_returns_cam_contact_position() -> None:
    calculator = MechanismOutputCalculator(
        get_scene_transform=lambda _layer: (lambda point: QPointF(100.0 + float(point[0]), 200.0 + float(point[1])))
    )

    point = calculator.calculate_output(
        mech_type="cam",
        params={
            "base_radius": 20.0,
            "eccentricity": 0.0,
            "follower_rod_length": 30.0,
            "output_point_mode": "contact_point",
        },
        time=0.0,
        layer_data={},
    )

    assert point is not None
    assert point.x() == pytest.approx(100.0)
    assert point.y() == pytest.approx(180.0)


def test_cam_output_mode_follower_end_alias_returns_follower_base_position() -> None:
    calculator = MechanismOutputCalculator(
        get_scene_transform=lambda _layer: (lambda point: QPointF(float(point[0]), float(point[1])))
    )

    point = calculator.calculate_output(
        mech_type="cam",
        params={
            "base_radius": 20.0,
            "eccentricity": 0.0,
            "follower_rod_length": 30.0,
            "output_point_mode": "follower_end",
        },
        time=0.0,
        layer_data={},
    )

    assert point is not None
    assert point.x() == pytest.approx(0.0)
    assert point.y() == pytest.approx(-50.0)


def test_calculate_output_rejects_non_finite_time() -> None:
    calculator = MechanismOutputCalculator(get_scene_transform=_scene_transform)

    point = calculator.calculate_output(
        mech_type="gear",
        params={"r1": 30.0},
        time=float("nan"),
        layer_data={},
    )

    assert point is None


def test_4bar_output_trims_mismatched_simulation_frame_arrays() -> None:
    calculator = MechanismOutputCalculator(get_scene_transform=_scene_transform)
    layer_data = {
        "full_simulation_data": {
            "joint_positions": {
                "p1_positions": [[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]],
                "p3_positions": [[12.0, 25.0], [13.0, 26.0]],
                "p4_positions": [[44.0, 55.0]],
            }
        }
    }

    point = calculator.calculate_output(
        mech_type="4_bar_linkage",
        params={"output_point_mode": "joint_b"},
        time=2 * math.pi,
        layer_data=layer_data,
    )

    assert point is not None
    assert point.x() == pytest.approx(44.0)
    assert point.y() == pytest.approx(55.0)


def test_4bar_coupler_point_respects_explicit_zero_over_alias() -> None:
    calculator = MechanismOutputCalculator(get_scene_transform=_scene_transform)
    layer_data = {
        "full_simulation_data": {
            "joint_positions": {
                "p1_positions": [[0.0, 0.0]],
                "p3_positions": [[0.0, 0.0]],
                "p4_positions": [[10.0, 0.0]],
            }
        }
    }

    point = calculator.calculate_output(
        mech_type="4_bar_linkage",
        params={
            "coupler_point_x": 0.0,
            "p_x": 999.0,
            "coupler_point_y": 5.0,
        },
        time=0.0,
        layer_data=layer_data,
    )

    assert point is not None
    assert point.x() == pytest.approx(0.0)
    assert point.y() == pytest.approx(5.0)


def test_4bar_missing_simulation_points_falls_back_to_manual_output() -> None:
    calculator = MechanismOutputCalculator(get_scene_transform=_scene_transform)
    layer_data = {
        "key_points": {
            "ground_pivot_1": [0.0, 0.0],
            "ground_pivot_2": [100.0, 0.0],
        },
        "full_simulation_data": {"joint_positions": {"p1_positions": [[0.0, 0.0]]}},
    }

    point = calculator.calculate_output(
        mech_type="4_bar_linkage",
        params={"l2": 30.0, "l3": 80.0, "l4": 80.0, "coupler_point_x": 0.0},
        time=0.0,
        layer_data=layer_data,
    )

    assert point is not None
    assert math.isfinite(point.x())
    assert math.isfinite(point.y())


def test_cam_output_sanitizes_bad_profile_and_non_finite_params() -> None:
    calculator = MechanismOutputCalculator(get_scene_transform=_scene_transform)

    point = calculator.calculate_output(
        mech_type="cam",
        params={
            "base_radius": float("nan"),
            "cam_offset": float("inf"),
            "cam_lobes": -2,
            "profile_harmonic": float("nan"),
            "follower_rod_length": -10.0,
        },
        time=0.0,
        layer_data={
            "cam_points_local": [[float("nan"), 0.0]],
            "cam_scale_factor": float("nan"),
            "rod_length_multiplier": -1.0,
            "follower_fixed_x_scene": float("inf"),
        },
    )

    assert point is not None
    assert math.isfinite(point.x())
    assert math.isfinite(point.y())


def test_gear_fallback_sanitizes_bad_radius_and_center() -> None:
    calculator = MechanismOutputCalculator(get_scene_transform=_scene_transform)

    point = calculator.calculate_output(
        mech_type="gear",
        params={"r1": float("nan")},
        time=0.0,
        layer_data={"key_points": {"gear1_center": [float("nan"), 0.0]}},
    )

    assert point is not None
    assert point.x() == pytest.approx(30.0)
    assert point.y() == pytest.approx(0.0)


def test_planetary_fallback_sanitizes_bad_params_and_sun_center() -> None:
    calculator = MechanismOutputCalculator(get_scene_transform=_scene_transform)

    point = calculator.calculate_output(
        mech_type="planetary_gear",
        params={
            "r_sun": float("nan"),
            "r_planet": 0.0,
            "arm_length": -5.0,
            "gear1_x": float("nan"),
            "gear1_y": "bad",
        },
        time=0.0,
        layer_data={},
    )

    assert point is not None
    assert point.x() == pytest.approx(65.0)
    assert point.y() == pytest.approx(0.0)


@pytest.mark.parametrize("num_points", [0, -1, True])
def test_generate_joint_motion_path_rejects_invalid_num_points(num_points: int | bool) -> None:
    calculator = MechanismOutputCalculator(get_scene_transform=_scene_transform)

    path = calculator.generate_joint_motion_path(
        {
            "type": "4_bar_linkage",
            "params": {"l2": 30.0, "l3": 80.0, "l4": 80.0},
            "key_points": {
                "ground_pivot_1": [0.0, 0.0],
                "ground_pivot_2": [100.0, 0.0],
            },
        },
        num_points=num_points,
    )

    assert path is None


def test_generate_joint_motion_path_allows_origin_points() -> None:
    calculator = MechanismOutputCalculator(get_scene_transform=_scene_transform)

    path = calculator.generate_joint_motion_path(
        {
            "type": "4_bar_linkage",
            "params": {"output_point_mode": "joint_a"},
            "full_simulation_data": {
                "joint_positions": {
                    "p1_positions": [[0.0, 0.0]],
                    "p3_positions": [[0.0, 0.0]],
                    "p4_positions": [[10.0, 0.0]],
                }
            },
        },
        num_points=1,
    )

    assert path is not None
    assert path.elementCount() >= 1
    assert path.currentPosition().x() == pytest.approx(0.0)
    assert path.currentPosition().y() == pytest.approx(0.0)
