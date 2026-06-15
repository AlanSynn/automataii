from __future__ import annotations

import sys

import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.presentation.qt.parametric.components.gear_editor import GearEditor
from automataii.shared import physical_kit
from automataii.shared.physical_kit import (
    CamPreset,
    GearPreset,
    GridPitchChoice,
    PhysicalKitProfile,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def _create_gear_editor() -> GearEditor:
    scene = QGraphicsScene()
    editor = GearEditor("gear_test", scene)
    mechanism_data = {
        "type": "gear",
        "params": {
            "gear1_x": 0.0,
            "gear1_y": 0.0,
            "gear2_x": 102.0,
            "gear2_y": 0.0,
            "gear1_radius": 40.0,
            "gear2_radius": 60.0,
        },
        "key_points": {
            "gear1_center": [0.0, 0.0],
            "gear2_center": [102.0, 0.0],
        },
    }
    editor.create_handles(mechanism_data)
    return editor


def test_gear_mesh_handle_updates_clearance_and_center_distance(qapp):
    editor = _create_gear_editor()

    editor._on_mesh_adjusted("mesh", QPointF(70.0, 0.0))

    params = editor.mechanism_data["params"]
    center1 = np.array([params["gear1_x"], params["gear1_y"]], dtype=float)
    center2 = np.array([params["gear2_x"], params["gear2_y"]], dtype=float)
    center_distance = float(np.linalg.norm(center2 - center1))

    assert params["gear_clearance"] == pytest.approx(32.0)
    assert params["mesh_clearance"] == pytest.approx(32.0)
    assert center_distance == pytest.approx(
        params["gear1_radius"] + params["gear2_radius"] + params["gear_clearance"]
    )
    assert editor.handles["mesh"].scenePos().x() == pytest.approx(center_distance / 2.0)
    assert editor.mechanism_data["key_points"]["gear2_center"] == pytest.approx(
        [center_distance, 0.0]
    )


def test_gear_center_drag_rejects_non_finite_position(qapp):
    editor = _create_gear_editor()
    params = editor.mechanism_data["params"]
    original_x = params["gear1_x"]
    original_y = params["gear1_y"]
    original_key_point = list(editor.mechanism_data["key_points"]["gear1_center"])
    original_pos = editor.handles["gear1_center"].scenePos()

    editor.handles["gear1_center"].setPos(QPointF(float("nan"), 5.0))
    editor._on_gear_center_moved("gear1", QPointF(float("nan"), 5.0))

    assert params["gear1_x"] == pytest.approx(original_x)
    assert params["gear1_y"] == pytest.approx(original_y)
    assert editor.mechanism_data["key_points"]["gear1_center"] == pytest.approx(
        original_key_point
    )
    assert editor.handles["gear1_center"].scenePos().x() == pytest.approx(original_pos.x())
    assert editor.handles["gear1_center"].scenePos().y() == pytest.approx(original_pos.y())
    assert np.isfinite([params["gear1_x"], params["gear1_y"]]).all()


def test_gear_radius_drag_updates_radius_aliases_and_handle_constraints(qapp):
    editor = _create_gear_editor()

    editor._on_mesh_adjusted("mesh", QPointF(70.0, 0.0))
    gear2_center = editor.handles["gear2_center"].scenePos()
    editor._on_gear_radius_changed("gear2", QPointF(gear2_center.x() + 102.0, gear2_center.y()))

    params = editor.mechanism_data["params"]
    assert params["gear2_radius"] == pytest.approx(96.0)
    assert params["gear2_teeth"] == 32
    assert params["r2"] == pytest.approx(96.0)

    center = QPointF(params["gear2_x"], params["gear2_y"])
    radius_handle = editor.handles["gear2_radius"]
    assert radius_handle.scenePos().x() == pytest.approx(center.x() + params["gear2_radius"])
    assert radius_handle.scenePos().y() == pytest.approx(center.y())
    assert radius_handle.constraints["center"].x() == pytest.approx(center.x())
    assert radius_handle.constraints["center"].y() == pytest.approx(center.y())

    center1 = np.array([params["gear1_x"], params["gear1_y"]], dtype=float)
    center2 = np.array([params["gear2_x"], params["gear2_y"]], dtype=float)
    assert np.linalg.norm(center2 - center1) == pytest.approx(
        params["gear1_radius"] + params["gear2_radius"] + params["gear_clearance"]
    )


def test_gear_editor_uses_profile_default_clearance(monkeypatch, qapp):
    profile = PhysicalKitProfile(
        key="clearance-kit",
        label="Clearance kit",
        default_pitch_mm=20.0,
        grid_pitch_choices=(GridPitchChoice("2cm", "2.0 cm board", 20.0),),
        linkage_length_cells=(2,),
        gear_presets=(GearPreset("g12", "G12", 12), GearPreset("g16", "G16", 16)),
        cam_presets=(
            CamPreset("circle", "Circle", 1.0, 0.0, 1, 0.0, 90.0, 90.0, 90.0),
        ),
        gear_radius_per_tooth_mm=2.0,
        default_gear_clearance_mm=7.0,
    )
    monkeypatch.setattr(physical_kit, "PHYSICAL_KIT_PROFILES", (profile,))

    scene = QGraphicsScene()
    editor = GearEditor("gear_profile_test", scene)
    mechanism_data = {
        "type": "gear",
        "params": {
            "physical_profile_key": "clearance-kit",
            "grid_system_enabled": True,
            "gear1_x": 0.0,
            "gear1_y": 0.0,
            "gear2_x": 60.0,
            "gear2_y": 0.0,
            "gear1_teeth": 12,
            "gear2_teeth": 16,
        },
        "key_points": {},
    }

    editor.create_handles(mechanism_data)
    params = editor.mechanism_data["params"]
    assert params["gear_clearance"] == pytest.approx(7.0)
    assert params["mesh_clearance"] == pytest.approx(7.0)

    params.pop("gear_clearance")
    params.pop("mesh_clearance")
    editor._auto_adjust_gear_mesh()

    assert params["gear_clearance"] == pytest.approx(7.0)
    assert params["mesh_clearance"] == pytest.approx(7.0)
