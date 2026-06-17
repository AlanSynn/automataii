from __future__ import annotations

import math
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.presentation.qt.parametric.components.fourbar_editor import FourBarEditor
from automataii.presentation.qt.tabs.parametric_editing_manager import ParametricEditingManager


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
    assert params["L2"] == pytest.approx(60.0, rel=1e-6)
    assert params["crank_angle"] == pytest.approx(0.0, rel=1e-6)
    assert editor.handles["crank"].constraints["fixed_distance"]["distance"] == pytest.approx(
        120.0, rel=1e-6
    )


def test_fourbar_degenerate_crank_drag_preserves_last_valid_state(qapp):
    editor = _create_editor_with_scaled_transform()
    valid_pos = QPointF(120.0, 0.0)

    editor.handles["crank"].setPos(valid_pos)
    editor._on_crank_moved("crank", valid_pos)

    params = editor.mechanism_data["params"]
    original = {
        "l2": params["l2"],
        "L2": params.get("L2"),
        "crank_x": params.get("crank_x"),
        "crank_y": params.get("crank_y"),
        "m_crank_x": params.get("m_crank_x"),
        "m_crank_y": params.get("m_crank_y"),
    }
    original_pos = editor.handles["crank"].scenePos()
    original_constraint = editor.handles["crank"].constraints["fixed_distance"]["distance"]
    anchor = editor.handles["anchor1"].scenePos()

    editor.handles["crank"].setPos(anchor)
    editor._on_crank_moved("crank", anchor)

    assert params["l2"] == pytest.approx(original["l2"], rel=1e-6)
    assert params["L2"] == pytest.approx(original["L2"], rel=1e-6)
    assert params.get("crank_x") == pytest.approx(original["crank_x"], rel=1e-6)
    assert params.get("crank_y") == pytest.approx(original["crank_y"], rel=1e-6)
    assert params.get("m_crank_x") == pytest.approx(original["m_crank_x"], rel=1e-6)
    assert params.get("m_crank_y") == pytest.approx(original["m_crank_y"], rel=1e-6)
    assert editor.handles["crank"].scenePos().x() == pytest.approx(original_pos.x(), rel=1e-6)
    assert editor.handles["crank"].scenePos().y() == pytest.approx(original_pos.y(), rel=1e-6)
    assert editor.handles["crank"].constraints["fixed_distance"]["distance"] == pytest.approx(
        original_constraint, rel=1e-6
    )


def test_fourbar_anchor_move_refreshes_constraint_anchor(qapp):
    editor = _create_editor_with_scaled_transform()
    new_anchor = QPointF(20.0, 10.0)

    editor.handles["anchor1"].setPos(new_anchor)
    editor._on_anchor1_moved("anchor1", new_anchor)

    constraint_anchor = editor.handles["crank"].constraints["fixed_distance"]["anchor"]
    assert constraint_anchor.x() == pytest.approx(new_anchor.x(), rel=1e-6)
    assert constraint_anchor.y() == pytest.approx(new_anchor.y(), rel=1e-6)


def test_fourbar_coupler_drag_without_transform_updates_coupler_offset(qapp):
    scene = QGraphicsScene()
    editor = FourBarEditor("plain_4bar", scene)
    mechanism_data = {
        "type": "4_bar_linkage",
        "params": {
            "anchor1_x": 0.0,
            "anchor1_y": 0.0,
            "anchor2_x": 200.0,
            "anchor2_y": 0.0,
            "crank_x": 50.0,
            "crank_y": 0.0,
            "rocker_x": 150.0,
            "rocker_y": 0.0,
            "l2": 50.0,
            "l3": 100.0,
            "l4": 50.0,
            "crank_angle": 0.0,
            "rocker_angle": 180.0,
            "coupler_point_x": 0.0,
            "coupler_point_y": 0.0,
        },
    }
    editor.create_handles(mechanism_data)

    new_coupler = QPointF(80.0, 25.0)
    editor.handles["coupler"].setPos(new_coupler)
    editor._on_coupler_moved("coupler", new_coupler)

    params = editor.mechanism_data["params"]
    assert params["coupler_x"] == pytest.approx(80.0)
    assert params["coupler_y"] == pytest.approx(25.0)
    assert params["coupler_point_x"] == pytest.approx(30.0)
    assert params["coupler_point_y"] == pytest.approx(25.0)


def _create_manager_with_scaled_transform() -> ParametricEditingManager:
    parent_tab = SimpleNamespace(
        _get_inverse_scene_transform_function=lambda _layer: (
            lambda point: np.array([float(point.x()) / 2.0, float(point.y()) / 2.0])
        ),
        _get_scene_transform_function=lambda _layer: (
            lambda point: QPointF(float(point[0]) * 2.0, float(point[1]) * 2.0)
        ),
    )
    return ParametricEditingManager(parent_tab)


def test_fourbar_regeneration_starts_at_dragged_crank_position(qapp):
    manager = _create_manager_with_scaled_transform()
    dragged_crank = np.array([60.0, 30.0])
    params = {
        "anchor1_x": 0.0,
        "anchor1_y": 0.0,
        "anchor2_x": 200.0,
        "anchor2_y": 0.0,
        "m_crank_x": dragged_crank[0],
        "m_crank_y": dragged_crank[1],
        "L2": float(np.linalg.norm(dragged_crank)),
        "L3": 80.0,
        "L4": 70.0,
        "l2": float(np.linalg.norm(dragged_crank)),
        "l3": 80.0,
        "l4": 70.0,
        "crank_angle": 0.0,
    }
    layer_data = {
        "type": "4_bar_linkage",
        "params": params,
        "transform_params": {"scale": 2.0},
    }

    manager._regenerate_4bar_simulation(layer_data, params)

    first_p3 = np.array(layer_data["full_simulation_data"]["joint_positions"]["p3_positions"][0])
    assert first_p3 == pytest.approx(dragged_crank, rel=1e-6)
    assert params["crank_angle"] == pytest.approx(math.degrees(math.atan2(30.0, 60.0)))
    assert params["crank_x"] == pytest.approx(120.0, rel=1e-6)
    assert params["crank_y"] == pytest.approx(60.0, rel=1e-6)


def test_fourbar_regeneration_prefers_dragged_rocker_branch(qapp):
    manager = _create_manager_with_scaled_transform()
    params = {
        "anchor1_x": 0.0,
        "anchor1_y": 0.0,
        "anchor2_x": 200.0,
        "anchor2_y": 0.0,
        "m_rocker_x": 70.0,
        "m_rocker_y": -40.0,
        "L2": 40.0,
        "L3": 50.0,
        "L4": 50.0,
        "l2": 40.0,
        "l3": 50.0,
        "l4": 50.0,
        "crank_angle": 0.0,
    }
    layer_data = {
        "type": "4_bar_linkage",
        "params": params,
        "transform_params": {"scale": 2.0},
    }

    manager._regenerate_4bar_simulation(layer_data, params)

    first_p4 = np.array(layer_data["full_simulation_data"]["joint_positions"]["p4_positions"][0])
    assert first_p4 == pytest.approx(np.array([70.0, -40.0]), rel=1e-6)
    assert params["rocker_x"] == pytest.approx(140.0, rel=1e-6)
    assert params["rocker_y"] == pytest.approx(-80.0, rel=1e-6)
