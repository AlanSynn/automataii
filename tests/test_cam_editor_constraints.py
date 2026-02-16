from __future__ import annotations

import sys

import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.presentation.qt.parametric.components.cam_editor import CamEditor


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_cam_follower_drag_uses_mechanism_space_with_transforms(qapp):
    scene = QGraphicsScene()
    editor = CamEditor("cam_test", scene)
    editor.to_scene_coords = lambda arr: QPointF(float(arr[0]) * 2.0, float(arr[1]) * 2.0)
    editor.to_mech_coords = lambda arr: np.array([float(arr[0]) / 2.0, float(arr[1]) / 2.0])

    mechanism_data = {
        "type": "cam",
        "params": {
            "center_x": 0.0,
            "center_y": 0.0,
            "base_radius": 25.0,
            "eccentricity": 10.0,
            "follower_rod_length": 40.0,
        },
    }
    editor.create_handles(mechanism_data)

    new_scene_pos = QPointF(0.0, -200.0)
    editor.handles["follower"].setPos(new_scene_pos)
    editor._on_follower_moved("follower", new_scene_pos)

    # Scene y=-200 maps to mechanism y=-100, so rod length = |0 - (-100)| - base_radius(25) = 75.
    assert editor.mechanism_data["params"]["follower_rod_length"] == pytest.approx(75.0, rel=1e-6)
