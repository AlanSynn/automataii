from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.presentation.qt.animation import CentralAnimationScheduler
from automataii.presentation.qt.tabs.mechanism_design.components.animation_lifecycle_controller import (
    AnimationLifecycleController,
)


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _controller() -> AnimationLifecycleController:
    path_trace_manager = MagicMock()
    path_trace_manager.get_all_mechanism_ids.return_value = []
    return AnimationLifecycleController(
        mechanism_scene=QGraphicsScene(),
        path_trace_manager=path_trace_manager,
    )


def test_scheduler_owned_by_lifecycle_stops_after_stop(qapp: QApplication) -> None:
    scheduler = CentralAnimationScheduler()
    controller = _controller()
    controller.set_scheduler(scheduler)

    try:
        controller.start_animation({"m1": True})
        assert scheduler.is_running
        assert len(scheduler.list_subscriptions()) == 1

        controller.stop_animation()

        assert scheduler.list_subscriptions() == []
        assert not scheduler.is_running
        assert not controller.is_animation_running()
    finally:
        scheduler.stop()


def test_reentrant_start_preserves_scheduler_ownership(qapp: QApplication) -> None:
    scheduler = CentralAnimationScheduler()
    controller = _controller()
    controller.set_scheduler(scheduler)

    try:
        controller.start_animation({"m1": True})
        assert scheduler.is_running

        controller.start_animation({"m1": True})
        controller.stop_animation()

        assert scheduler.list_subscriptions() == []
        assert not scheduler.is_running
        assert not controller.is_animation_running()
    finally:
        scheduler.stop()


def test_scheduler_owned_by_lifecycle_stops_after_reset(qapp: QApplication) -> None:
    scheduler = CentralAnimationScheduler()
    controller = _controller()
    controller.set_scheduler(scheduler)

    try:
        controller.start_animation({"m1": True})
        assert scheduler.is_running

        controller.reset_animation()

        assert scheduler.list_subscriptions() == []
        assert not scheduler.is_running
        assert not controller.is_animation_running()
    finally:
        scheduler.stop()


def test_all_disabled_mechanisms_do_not_start_scheduler(qapp: QApplication) -> None:
    scheduler = CentralAnimationScheduler()
    controller = _controller()
    controller.set_scheduler(scheduler)

    try:
        controller.start_animation({"m1": False})

        assert scheduler.list_subscriptions() == []
        assert not scheduler.is_running
        assert not controller.is_animation_running()
    finally:
        scheduler.stop()


def test_disabled_mechanisms_are_skipped_during_frame_updates(qapp: QApplication) -> None:
    controller = _controller()
    visual_calls: list[str] = []

    controller.configure_callbacks(
        get_main_window=lambda: None,
        get_mechanism_layers=lambda: {
            "disabled": {"type": "cam", "params": {}, "part_name": "arm"},
            "enabled": {"type": "cam", "params": {}, "part_name": "leg"},
        },
        get_part_enabled_state=lambda: {"arm": True, "leg": True},
        get_parts_data=lambda: {"leg": SimpleNamespace(anchor_joint_id="knee")},
        get_presenter=lambda: None,
        get_ui_state_manager=lambda: None,
        calculate_mechanism_output=lambda *_args: QPointF(1.0, 2.0),
        update_mechanism_visuals_for_animation=lambda mechanism_id, *_args: visual_calls.append(
            mechanism_id
        ),
        get_target_joint_for_mechanism_control=lambda _part, joint: joint,
        get_standardized_joint_id=lambda joint: joint,
        ensure_skeleton_visualization=lambda _data: None,
        setup_mechanism_ik_integration=lambda: False,
        reset_skeleton_to_initial_state=lambda: None,
        position_parts_at_anchor_joints=lambda: None,
        clear_animation_cache=lambda: None,
    )
    controller.set_mechanism_update_fraction(1.0)

    controller.start_animation({"disabled": False, "enabled": True})
    controller._update_animation(0.1)

    assert visual_calls == ["enabled"]


def test_mechanism_enabled_state_reflects_live_toggles(qapp: QApplication) -> None:
    controller = _controller()
    visual_calls: list[str] = []
    enabled_state = {"m1": True}

    controller.configure_callbacks(
        get_main_window=lambda: None,
        get_mechanism_layers=lambda: {"m1": {"type": "cam", "params": {}, "part_name": "arm"}},
        get_part_enabled_state=lambda: {"arm": True},
        get_parts_data=lambda: {"arm": SimpleNamespace(anchor_joint_id="elbow")},
        get_presenter=lambda: None,
        get_ui_state_manager=lambda: None,
        calculate_mechanism_output=lambda *_args: QPointF(1.0, 2.0),
        update_mechanism_visuals_for_animation=lambda mechanism_id, *_args: visual_calls.append(
            mechanism_id
        ),
        get_target_joint_for_mechanism_control=lambda _part, joint: joint,
        get_standardized_joint_id=lambda joint: joint,
        ensure_skeleton_visualization=lambda _data: None,
        setup_mechanism_ik_integration=lambda: False,
        reset_skeleton_to_initial_state=lambda: None,
        position_parts_at_anchor_joints=lambda: None,
        clear_animation_cache=lambda: None,
    )

    controller.start_animation(enabled_state)
    controller._update_animation(0.1)
    enabled_state["m1"] = False
    controller._update_animation(0.1)

    assert visual_calls == ["m1"]
