from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.presentation.qt.tabs.mechanism_design.components.skeleton_visualization_handler import (
    SkeletonVisualizationHandler,
)


class _DummyView:
    def __init__(self) -> None:
        self.set_joint_map = MagicMock()
        self.visualize_skeleton = MagicMock()
        self.skeleton_graphics_item = MagicMock()


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _handler() -> tuple[SkeletonVisualizationHandler, _DummyView]:
    view = _DummyView()
    scene = QGraphicsScene()
    handler = SkeletonVisualizationHandler(view, scene)
    return handler, view


def test_cache_initial_skeleton_none_clears_visualization_state(qapp: QApplication) -> None:
    handler, view = _handler()

    handler.initial_skeleton_data_cache = {"joints": {"dummy": {"position": [0, 0]}}}
    handler.cache_initial_skeleton(None)

    view.set_joint_map.assert_called_with(None)
    view.visualize_skeleton.assert_called_with([], {})
    assert handler.initial_skeleton_data_cache is None


def test_cache_initial_skeleton_deep_copies_rest_pose(qapp: QApplication) -> None:
    handler, _view = _handler()
    skeleton = {
        "joint_map": {"head": "joint-head"},
        "joints": {"joint-head": {"position": [10.0, 20.0]}},
    }

    handler.cache_initial_skeleton(skeleton)
    skeleton["joints"]["joint-head"]["position"][0] = 999.0

    assert handler.initial_skeleton_data_cache is not skeleton
    assert handler.initial_skeleton_data_cache == {
        "joint_map": {"head": "joint-head"},
        "joints": {"joint-head": {"position": [10.0, 20.0]}},
    }


def test_on_skeleton_updated_empty_data_clears_visualization(qapp: QApplication) -> None:
    handler, view = _handler()

    handler.on_skeleton_updated({})

    view.set_joint_map.assert_called_with(None)
    view.visualize_skeleton.assert_called_with([], {})


def test_on_skeleton_manager_updated_none_clears_visualization(qapp: QApplication) -> None:
    handler, view = _handler()

    handler.on_skeleton_manager_updated(None)

    view.set_joint_map.assert_called_with(None)
    view.visualize_skeleton.assert_called_with([], {})
