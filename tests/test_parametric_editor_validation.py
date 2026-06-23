from __future__ import annotations

import sys

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.presentation.qt.parametric_editor import ParametricEditor


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_validation_reads_current_cam_handle_position(qapp):
    editor = ParametricEditor(QGraphicsScene())
    cam_editor = editor.create_editor(
        "cam_1",
        {
            "type": "cam",
            "params": {
                "center_x": 0.0,
                "center_y": 0.0,
                "base_radius": 25.0,
                "eccentricity": 10.0,
                "follower_rod_length": 40.0,
            },
        },
    )
    assert cam_editor is not None

    invalid_follower = QPointF(0.0, 5.0)
    cam_editor.handles["follower"].setPos(invalid_follower)

    valid, message = editor.validate_physics_constraints()

    assert valid is False
    assert "Follower must be above cam center" in message


def test_fourbar_validation_allows_non_grashof_partial_motion(qapp):
    editor = ParametricEditor(QGraphicsScene())
    fourbar_editor = editor.create_editor(
        "bad_4bar",
        {
            "type": "4_bar_linkage",
            "params": {
                "anchor1_x": 0.0,
                "anchor1_y": 0.0,
                "anchor2_x": 200.0,
                "anchor2_y": 0.0,
                "crank_x": 10.0,
                "crank_y": 0.0,
                "rocker_x": 20.0,
                "rocker_y": 0.0,
                "l2": 10.0,
                "l3": 10.0,
                "l4": 180.0,
                "crank_angle": 0.0,
                "rocker_angle": 180.0,
                "coupler_point_x": 0.0,
                "coupler_point_y": 0.0,
            },
        },
    )
    assert fourbar_editor is not None

    valid, message = editor.validate_physics_constraints()

    assert valid is True
    assert message == ""


def test_handle_callback_queues_update_even_when_mechanism_callback_raises(qapp):
    editor = ParametricEditor(QGraphicsScene())

    def broken_callback(_handle_id: str, _position: QPointF) -> None:
        raise RuntimeError("callback failed")

    wrapped = editor._wrap_handle_callback(broken_callback, "mechanism_1")

    with pytest.raises(RuntimeError, match="callback failed"):
        wrapped("handle", QPointF(1.0, 2.0))

    assert "mechanism_1" in editor._pending_updates


def test_validation_ignores_malformed_fourbar_fallback_params_when_handles_missing(qapp):
    editor = ParametricEditor(QGraphicsScene())
    fourbar_editor = editor.create_editor(
        "malformed_4bar",
        {
            "type": "4_bar_linkage",
            "params": {
                "anchor1_x": "bad",
                "anchor1_y": "bad",
                "anchor2_x": float("nan"),
                "anchor2_y": "bad",
                "crank_x": "bad",
                "crank_y": "bad",
                "rocker_x": "bad",
                "rocker_y": "bad",
            },
        },
    )
    assert fourbar_editor is not None
    fourbar_editor.handles.clear()

    valid, message = editor.validate_physics_constraints()

    assert valid is True
    assert message == ""
