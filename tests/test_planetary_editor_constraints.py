from __future__ import annotations

import sys

import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.presentation.qt.parametric.components.gear_editor import (
    PlanetaryGearEditor,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def _create_editor_with_scaled_transform() -> PlanetaryGearEditor:
    scene = QGraphicsScene()
    editor = PlanetaryGearEditor("planetary_test", scene)
    editor.to_scene_coords = lambda arr: QPointF(float(arr[0]) * 2.0, float(arr[1]) * 2.0)
    editor.to_mech_coords = lambda arr: np.array([float(arr[0]) / 2.0, float(arr[1]) / 2.0])

    mechanism_data = {
        "type": "planetary_gear",
        "params": {
            "grid_system_enabled": False,
            "sun_x": 0.0,
            "sun_y": 0.0,
            "r_sun": 20.0,
            "r_planet": 30.0,
            "arm_length": 15.0,
        },
        "key_points": {},
    }
    editor.create_handles(mechanism_data)
    return editor


def test_planetary_radius_handle_uses_transform_scaled_distance(qapp):
    editor = _create_editor_with_scaled_transform()
    planet_radius_handle = editor.handles["planet_radius"]

    # r_planet=30 mech units -> 60 scene units with x2 transform.
    assert planet_radius_handle.scenePos().x() == pytest.approx(60.0, rel=1e-6)
    assert planet_radius_handle.scenePos().y() == pytest.approx(0.0, rel=1e-6)


def test_planetary_editor_key_point_fallback_uses_scene_points_for_foundry_style_layer(qapp):
    scene = QGraphicsScene()
    editor = PlanetaryGearEditor("planetary_keypoint_test", scene)
    editor.to_scene_coords = lambda arr: QPointF(float(arr[0]) * 2.0, float(arr[1]) * 2.0)
    editor.to_mech_coords = lambda arr: np.array([float(arr[0]) / 2.0, float(arr[1]) / 2.0])
    mechanism_data = {
        "type": "planetary_gear",
        "generated_path": None,
        "params": {
            "grid_system_enabled": False,
            "r_sun": 20.0,
            "r_planet": 30.0,
            "arm_length": 15.0,
        },
        "key_points": {
            "sun_center": [100.0, 40.0],
        },
    }

    editor.create_handles(mechanism_data)

    params = editor.mechanism_data["params"]
    assert params["sun_x"] == pytest.approx(100.0)
    assert params["sun_y"] == pytest.approx(40.0)
    assert params["gear1_x"] == pytest.approx(100.0)
    assert params["gear1_y"] == pytest.approx(40.0)


def test_planetary_radius_drag_updates_mech_radius_and_key_points(qapp):
    editor = _create_editor_with_scaled_transform()
    new_scene_pos = QPointF(80.0, 0.0)  # 40 mech units from center

    editor.handles["planet_radius"].setPos(new_scene_pos)
    editor._on_planet_radius_changed("planet_radius", new_scene_pos)

    params = editor.mechanism_data["params"]
    key_points = editor.mechanism_data["key_points"]
    assert params["r_planet"] == pytest.approx(40.0, rel=1e-6)
    # generated_path=None layers persist key_points in scene space for reload.
    assert key_points["planet_center"][0] == pytest.approx(120.0, rel=1e-6)
    assert key_points["planet_center"][1] == pytest.approx(0.0, rel=1e-6)


def test_planetary_sun_drag_updates_key_points_and_dependent_handles(qapp):
    editor = _create_editor_with_scaled_transform()
    new_center_scene = QPointF(100.0, 40.0)

    editor.handles["sun_center"].setPos(new_center_scene)
    editor._on_sun_center_moved("sun_center", new_center_scene)

    params = editor.mechanism_data["params"]
    key_points = editor.mechanism_data["key_points"]
    # generated_path=None layers persist key_points in scene space for reload.
    assert key_points["sun_center"][0] == pytest.approx(100.0, rel=1e-6)
    assert key_points["sun_center"][1] == pytest.approx(40.0, rel=1e-6)
    assert params["gear1_x"] == pytest.approx(100.0, rel=1e-6)
    assert params["gear1_y"] == pytest.approx(40.0, rel=1e-6)
    # Planet center at + (r_sun + r_planet) = +50 mech -> +100 scene on X.
    assert params["gear2_x"] == pytest.approx(200.0, rel=1e-6)
    assert params["gear2_y"] == pytest.approx(40.0, rel=1e-6)


def test_planetary_arm_drag_uses_mechanism_space_with_transform(qapp):
    editor = _create_editor_with_scaled_transform()
    # arm center in scene is at (r_sun+r_planet)*2 = 100. Move handle to x=150 => arm_length=25 mech.
    new_scene_pos = QPointF(150.0, 0.0)

    editor.handles["arm_length"].setPos(new_scene_pos)
    editor._on_arm_length_changed("arm_length", new_scene_pos)

    assert editor.mechanism_data["params"]["arm_length"] == pytest.approx(25.0, rel=1e-6)


def test_planetary_editor_preserves_geometry_when_grid_enabled(qapp):
    scene = QGraphicsScene()
    editor = PlanetaryGearEditor("planetary_snap", scene)
    mechanism_data = {
        "type": "planetary_gear",
        "params": {
            "grid_system_enabled": True,
            "grid_cell_cm": 2.0,
            "sun_x": 0.0,
            "sun_y": 0.0,
            "r_sun": 19.0,
            "r_planet": 35.0,
            "arm_length": 13.0,
        },
        "key_points": {},
    }

    editor.create_handles(mechanism_data)

    params = editor.mechanism_data["params"]
    assert params["r_sun"] == pytest.approx(19.0)
    assert params["r_planet"] == pytest.approx(35.0)
    assert params["arm_length"] == pytest.approx(13.0)
    assert params["sun_teeth"] > 0
    assert params["planet_teeth"] > 0


def test_planetary_key_points_do_not_double_transform_without_inverse(qapp):
    scene = QGraphicsScene()
    editor = PlanetaryGearEditor("planetary_scene_only", scene)
    editor.to_scene_coords = lambda arr: QPointF(float(arr[0]) * 2.0, float(arr[1]) * 2.0)
    editor.to_mech_coords = None
    mechanism_data = {
        "type": "planetary_gear",
        "generated_path": None,
        "params": {
            "grid_system_enabled": False,
            "sun_x": 100.0,
            "sun_y": 40.0,
            "r_sun": 20.0,
            "r_planet": 30.0,
            "arm_length": 15.0,
        },
        "key_points": {},
    }

    editor.create_handles(mechanism_data)

    key_points = editor.mechanism_data["key_points"]
    assert key_points["sun_center"] == pytest.approx([100.0, 40.0])
    assert key_points["planet_center"] == pytest.approx([150.0, 40.0])
    assert key_points["tracking_point"] == pytest.approx([165.0, 40.0])
