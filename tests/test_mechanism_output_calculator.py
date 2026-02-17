from __future__ import annotations

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
