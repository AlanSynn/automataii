from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.presentation.qt.parametric.components.cam_editor import CamEditor
from automataii.presentation.qt.tabs.parametric_editing_manager import ParametricEditingManager


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def _create_cam_editor_with_scaled_transform() -> CamEditor:
    scene = QGraphicsScene()
    editor = CamEditor("cam_test", scene)
    editor.to_scene_coords = lambda arr: QPointF(float(arr[0]) * 2.0, float(arr[1]) * 2.0)
    editor.to_mech_coords = lambda arr: np.array([float(arr[0]) / 2.0, float(arr[1]) / 2.0])

    mechanism_data = {
        "type": "cam",
        "params": {
            "grid_system_enabled": False,
            "center_x": 0.0,
            "center_y": 0.0,
            "base_radius": 25.0,
            "eccentricity": 10.0,
            "follower_rod_length": 40.0,
        },
    }
    editor.create_handles(mechanism_data)
    return editor


def _create_cam_editor_with_identity_transform(
    *, cam_scale_factor: float = 1.0, rod_length_multiplier: float = 1.0
) -> CamEditor:
    scene = QGraphicsScene()
    editor = CamEditor("cam_scaled", scene)
    editor.to_scene_coords = lambda arr: QPointF(float(arr[0]), float(arr[1]))
    editor.to_mech_coords = lambda arr: np.array([float(arr[0]), float(arr[1])])

    mechanism_data = {
        "type": "cam",
        "cam_scale_factor": cam_scale_factor,
        "rod_length_multiplier": rod_length_multiplier,
        "params": {
            "grid_system_enabled": False,
            "center_x": 0.0,
            "center_y": 0.0,
            "base_radius": 25.0,
            "eccentricity": 10.0,
            "follower_rod_length": 40.0,
        },
    }
    editor.create_handles(mechanism_data)
    return editor


def test_cam_follower_handle_starts_at_visual_follower_head_with_transforms(qapp):
    editor = _create_cam_editor_with_scaled_transform()

    follower_pos = editor.handles["follower"].scenePos()

    # Default pear-cam profile has local +Y contact at 25; follower head is 40 above it.
    assert follower_pos.x() == pytest.approx(0.0, rel=1e-6)
    assert follower_pos.y() == pytest.approx(-30.0, rel=1e-6)


def test_cam_follower_drag_uses_mechanism_space_with_transforms(qapp):
    editor = _create_cam_editor_with_scaled_transform()

    new_scene_pos = QPointF(0.0, -200.0)
    editor.handles["follower"].setPos(new_scene_pos)
    editor._on_follower_moved("follower", new_scene_pos)

    # Scene y=-200 maps to mechanism y=-100; visual contact y is +25.
    assert editor.mechanism_data["params"]["follower_rod_length"] == pytest.approx(
        125.0, rel=1e-6
    )


def test_cam_follower_handle_uses_cam_scale_factor_with_transforms(qapp):
    editor = _create_cam_editor_with_identity_transform(
        cam_scale_factor=2.0,
        rod_length_multiplier=2.0,
    )

    follower_pos = editor.handles["follower"].scenePos()

    # Visual factory renders the scaled cam contact at y=50 and a scaled rod length of 80.
    assert follower_pos.x() == pytest.approx(0.0, rel=1e-6)
    assert follower_pos.y() == pytest.approx(-30.0, rel=1e-6)


def test_cam_follower_drag_uses_cam_scale_factor_with_transforms(qapp):
    editor = _create_cam_editor_with_identity_transform(
        cam_scale_factor=2.0,
        rod_length_multiplier=2.0,
    )

    new_scene_pos = QPointF(0.0, -150.0)
    editor.handles["follower"].setPos(new_scene_pos)
    editor._on_follower_moved("follower", new_scene_pos)

    # Scaled visual contact is y=50; (50 - -150) / rod multiplier 2 = 100.
    assert editor.mechanism_data["params"]["follower_rod_length"] == pytest.approx(
        100.0, rel=1e-6
    )


def test_cam_follower_constraint_boundary_matches_min_scaled_visual_rod(qapp):
    editor = _create_cam_editor_with_identity_transform(
        cam_scale_factor=2.0,
        rod_length_multiplier=2.0,
    )

    follower = editor.handles["follower"]
    boundary_pos = QPointF(follower.scenePos().x(), follower.constraints["max_y"])
    follower.setPos(boundary_pos)
    editor._on_follower_moved("follower", boundary_pos)

    assert boundary_pos.y() == pytest.approx(10.0, rel=1e-6)
    assert editor.mechanism_data["params"]["follower_rod_length"] == pytest.approx(
        20.0, rel=1e-6
    )

    contact_y = 50.0
    visual_follower_y = contact_y - (
        editor.mechanism_data["params"]["follower_rod_length"]
        * editor.mechanism_data["rod_length_multiplier"]
    )
    assert visual_follower_y == pytest.approx(boundary_pos.y(), rel=1e-6)


def test_cam_size_handle_repositions_to_clamped_radius(qapp):
    scene = QGraphicsScene()
    editor = CamEditor("cam_size", scene)
    mechanism_data = {
        "type": "cam",
        "cam_scale_factor": 1.0,
        "params": {
            "center_x": 0.0,
            "center_y": 0.0,
            "base_radius": 80.0,
            "eccentricity": 50.0,
            "follower_rod_length": 40.0,
        },
    }
    editor.create_handles(mechanism_data)

    oversized_pos = QPointF(200.0, 0.0)
    editor.handles["size"].setPos(oversized_pos)
    editor._on_size_moved("size", oversized_pos)

    params = editor.mechanism_data["params"]
    expected_visual_radius = params["base_radius"] + params["eccentricity"]
    size_pos = editor.handles["size"].scenePos()
    assert size_pos.x() == pytest.approx(expected_visual_radius, rel=1e-6)
    assert size_pos.y() == pytest.approx(0.0, rel=1e-6)


def test_cam_follower_handle_uses_scene_vertical_rod_under_rotated_transform(qapp):
    scene = QGraphicsScene()
    editor = CamEditor("cam_rotated", scene)
    editor.to_scene_coords = lambda arr: QPointF(-float(arr[1]), float(arr[0]))
    editor.to_mech_coords = lambda arr: np.array([float(arr[1]), -float(arr[0])])

    mechanism_data = {
        "type": "cam",
        "params": {
            "grid_system_enabled": False,
            "center_x": 0.0,
            "center_y": 0.0,
            "base_radius": 25.0,
            "eccentricity": 10.0,
            "follower_rod_length": 40.0,
        },
    }
    editor.create_handles(mechanism_data)

    follower_pos = editor.handles["follower"].scenePos()
    assert follower_pos.x() == pytest.approx(-25.0, rel=1e-6)
    assert follower_pos.y() == pytest.approx(-40.0, rel=1e-6)

    new_scene_pos = QPointF(-25.0, -100.0)
    editor.handles["follower"].setPos(new_scene_pos)
    editor._on_follower_moved("follower", new_scene_pos)

    assert editor.mechanism_data["params"]["follower_rod_length"] == pytest.approx(
        100.0, rel=1e-6
    )


def test_cam_regeneration_frame_zero_matches_visual_contact_y(qapp):
    manager = ParametricEditingManager(SimpleNamespace())
    params = {
        "base_radius": 25.0,
        "eccentricity": 10.0,
        "follower_rod_length": 40.0,
    }
    layer_data = {"type": "cam", "params": params, "key_points": {"cam_center": [0.0, 0.0]}}

    manager._regenerate_cam_simulation(layer_data, params)

    first_y = layer_data["full_simulation_data"]["cam_data"]["follower_y_positions"][0]
    assert first_y == pytest.approx(-15.0, rel=1e-6)


def test_cam_regeneration_respects_visual_scale_and_rod_multiplier(qapp):
    manager = ParametricEditingManager(SimpleNamespace())
    params = {
        "base_radius": 25.0,
        "eccentricity": 10.0,
        "follower_rod_length": 40.0,
    }
    layer_data = {
        "type": "cam",
        "params": params,
        "key_points": {"cam_center": [0.0, 0.0]},
        "cam_scale_factor": 2.0,
        "rod_length_multiplier": 2.0,
    }

    manager._regenerate_cam_simulation(layer_data, params)

    first_y = layer_data["full_simulation_data"]["cam_data"]["follower_y_positions"][0]
    assert first_y == pytest.approx(-30.0, rel=1e-6)
    assert layer_data["key_points"]["contact_point"] == pytest.approx([0.0, 50.0])
    assert layer_data["key_points"]["follower_base"] == pytest.approx([0.0, -30.0])
