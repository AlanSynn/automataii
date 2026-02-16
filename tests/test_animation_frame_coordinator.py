from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from PyQt6.QtCore import QPointF

from automataii.presentation.qt.tabs.mechanism_design.services.animation_frame_coordinator import (
    AnimationFrameCoordinator,
)


def test_update_frame_forwards_trace_tick_to_path_trace_manager() -> None:
    coordinator = AnimationFrameCoordinator()
    coordinator.configure_callbacks(
        calculate_output=lambda _t, _p, _time, _layer: QPointF(10.0, 20.0),
        get_target_joint=lambda _part, anchor: anchor,
        get_standardized_joint=lambda joint_id: joint_id,
        update_visuals=lambda _id, _time, _layer: None,
        stop_timer=lambda: None,
    )

    mechanism_layers = {
        "mech_1": {
            "part_name": "arm",
            "type": "4_bar_linkage",
            "params": {"l1": 100.0},
        }
    }
    part_enabled_state = {"arm": True}
    parts_data = {"arm": SimpleNamespace(anchor_joint_id="elbow")}
    path_trace_manager = MagicMock()
    scene = MagicMock()

    coordinator.update_frame(
        tab_active=True,
        mechanism_layers=mechanism_layers,
        part_enabled_state=part_enabled_state,
        parts_data=parts_data,
        ik_manager=None,
        path_trace_manager=path_trace_manager,
        scene=scene,
        initial_skeleton_cache=None,
    )

    path_trace_manager.update_trace.assert_called_once()
    args = path_trace_manager.update_trace.call_args.args
    assert args[0] == "mech_1"
    assert isinstance(args[1], QPointF)
    assert args[2] == coordinator.trace_frame_tick
    assert args[3] is scene
