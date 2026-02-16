from __future__ import annotations

import math
import sys

import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.presentation.qt.parametric.components.fourbar_editor import FourBarEditor


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def _create_editor_with_scaled_transform() -> FourBarEditor:
    scene = QGraphicsScene()
    editor = FourBarEditor("test_4bar", scene)

    editor.to_scene_coords = lambda arr: QPointF(float(arr[0]) * 2.0, float(arr[1]) * 2.0)
    editor.to_mech_coords = lambda arr: np.array([float(arr[0]) / 2.0, float(arr[1]) / 2.0])

    mechanism_data = {
        "type": "4_bar_linkage",
        "params": {
            "anchor1_x": 0.0,
            "anchor1_y": 0.0,
            "anchor2_x": 200.0,
            "anchor2_y": 0.0,
            "l2": 40.0,
            "l3": 80.0,
            "l4": 70.0,
            "crank_angle": 0.0,
            "rocker_angle": 180.0,
            "coupler_point_x": 0.0,
            "coupler_point_y": 0.0,
        },
    }
    editor.create_handles(mechanism_data)
    return editor


def test_fourbar_crank_constraint_uses_scene_distance(qapp):
    editor = _create_editor_with_scaled_transform()
    anchor = editor.handles["anchor1"].scenePos()
    crank = editor.handles["crank"].scenePos()
    expected = math.hypot(crank.x() - anchor.x(), crank.y() - anchor.y())

    constraint = editor.handles["crank"].constraints["fixed_distance"]["distance"]
    assert constraint == pytest.approx(expected, rel=1e-6)
    assert constraint == pytest.approx(80.0, rel=1e-6)


def test_fourbar_crank_move_updates_mechanism_length_under_transform(qapp):
    editor = _create_editor_with_scaled_transform()
    new_scene_pos = QPointF(120.0, 0.0)

    editor.handles["crank"].setPos(new_scene_pos)
    editor._on_crank_moved("crank", new_scene_pos)

    params = editor.mechanism_data["params"]
    assert params["l2"] == pytest.approx(60.0, rel=1e-6)
    assert params["crank_angle"] == pytest.approx(0.0, rel=1e-6)
    assert editor.handles["crank"].constraints["fixed_distance"]["distance"] == pytest.approx(
        120.0, rel=1e-6
    )


def test_fourbar_anchor_move_refreshes_constraint_anchor(qapp):
    editor = _create_editor_with_scaled_transform()
    new_anchor = QPointF(20.0, 10.0)

    editor.handles["anchor1"].setPos(new_anchor)
    editor._on_anchor1_moved("anchor1", new_anchor)

    constraint_anchor = editor.handles["crank"].constraints["fixed_distance"]["anchor"]
    assert constraint_anchor.x() == pytest.approx(new_anchor.x(), rel=1e-6)
    assert constraint_anchor.y() == pytest.approx(new_anchor.y(), rel=1e-6)
