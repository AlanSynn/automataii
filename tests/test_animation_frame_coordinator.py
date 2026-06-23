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


def test_update_frame_allows_origin_output_points() -> None:
    coordinator = AnimationFrameCoordinator()
    coordinator.configure_callbacks(
        calculate_output=lambda _t, _p, _time, _layer: QPointF(0.0, 0.0),
        get_target_joint=lambda _part, anchor: anchor,
        get_standardized_joint=lambda joint_id: joint_id,
        update_visuals=lambda _id, _time, _layer: None,
        stop_timer=lambda: None,
    )
    path_trace_manager = MagicMock()
    ik_manager = MagicMock()

    coordinator.update_frame(
        tab_active=True,
        mechanism_layers={"mech_1": {"part_name": "arm", "type": "4_bar_linkage", "params": {}}},
        part_enabled_state={"arm": True},
        parts_data={"arm": SimpleNamespace(anchor_joint_id="elbow")},
        ik_manager=ik_manager,
        path_trace_manager=path_trace_manager,
        scene=MagicMock(),
        initial_skeleton_cache=None,
    )

    path_trace_manager.update_trace.assert_called_once()


def test_update_frame_uses_body_part_anchor_fallback_for_ik_target() -> None:
    coordinator = AnimationFrameCoordinator()
    seen_anchor: list[str] = []
    coordinator.configure_callbacks(
        calculate_output=lambda _t, _p, _time, _layer: QPointF(5.0, 6.0),
        get_target_joint=lambda _part, anchor: seen_anchor.append(anchor) or "left_elbow",
        get_standardized_joint=lambda joint_id: joint_id,
        update_visuals=lambda _id, _time, _layer: None,
        stop_timer=lambda: None,
    )
    ik_manager = MagicMock()

    coordinator.update_frame(
        tab_active=True,
        mechanism_layers={
            "mech_1": {"part_name": "left_arm_upper", "type": "4_bar_linkage", "params": {}}
        },
        part_enabled_state={"left_arm_upper": True},
        parts_data={"left_arm_upper": SimpleNamespace(anchor_joint_id=None)},
        ik_manager=ik_manager,
        path_trace_manager=MagicMock(),
        scene=MagicMock(),
        initial_skeleton_cache=None,
    )

    assert seen_anchor == ["left_shoulder"]
    ik_manager.set_mechanism_position_target.assert_called_once_with(
        "left_elbow", QPointF(5.0, 6.0)
    )


def test_mechanism_id_cache_refreshes_same_dict_same_length_key_replacement() -> None:
    coordinator = AnimationFrameCoordinator()
    mechanism_layers = {"old": {"type": "4_bar_linkage"}}

    assert coordinator._get_mechanism_id_cache(mechanism_layers) == ("old",)

    del mechanism_layers["old"]
    mechanism_layers["new"] = {"type": "cam"}

    assert coordinator._get_mechanism_id_cache(mechanism_layers) == ("new",)


def test_joint_id_cache_invalidates_same_size_skeleton_content_changes() -> None:
    coordinator = AnimationFrameCoordinator()
    skeleton_cache = {
        "joint_map": {"elbow": "joint_a"},
        "joints": {"joint_a": {}},
    }

    assert coordinator._get_standardized_joint_id("elbow", skeleton_cache) == "joint_a"

    skeleton_cache["joint_map"] = {"elbow": "joint_b"}
    skeleton_cache["joints"] = {"joint_b": {}}

    assert coordinator._get_standardized_joint_id("elbow", skeleton_cache) == "joint_b"


def _configured_coordinator() -> AnimationFrameCoordinator:
    coordinator = AnimationFrameCoordinator(mechanism_update_fraction=1.0)
    coordinator.configure_callbacks(
        calculate_output=lambda _t, _p, _time, layer: layer["output"],
        get_target_joint=lambda _part, anchor: anchor,
        get_standardized_joint=lambda joint_id: joint_id,
        update_visuals=lambda _id, _time, _layer: None,
        stop_timer=lambda: None,
    )
    return coordinator


def test_coordinator_first_ik_target_sends_immediately() -> None:
    coordinator = AnimationFrameCoordinator()
    ik_manager = MagicMock()

    coordinator._apply_ik_targets(
        active_joint_updates={"elbow": QPointF(1.0, 2.0)},
        ik_manager=ik_manager,
    )

    ik_manager.set_mechanism_position_target.assert_called_once_with("elbow", QPointF(1.0, 2.0))


def test_coordinator_disabled_part_clears_stale_targets_and_resends_active() -> None:
    coordinator = _configured_coordinator()
    ik_manager = MagicMock()
    path_trace_manager = MagicMock()
    scene = MagicMock()
    part_enabled_state = {"arm": True, "leg": True}
    mechanism_layers = {
        "stale": {
            "part_name": "arm",
            "type": "4_bar_linkage",
            "params": {},
            "output": QPointF(1.0, 2.0),
        },
        "active": {
            "part_name": "leg",
            "type": "4_bar_linkage",
            "params": {},
            "output": QPointF(3.0, 4.0),
        },
    }
    parts_data = {
        "arm": SimpleNamespace(anchor_joint_id="elbow"),
        "leg": SimpleNamespace(anchor_joint_id="knee"),
    }

    coordinator.update_frame(
        tab_active=True,
        mechanism_layers=mechanism_layers,
        part_enabled_state=part_enabled_state,
        parts_data=parts_data,
        ik_manager=ik_manager,
        path_trace_manager=path_trace_manager,
        scene=scene,
        initial_skeleton_cache=None,
    )
    assert ik_manager.set_mechanism_position_target.call_count == 2
    ik_manager.clear_mechanism_position_targets.reset_mock()
    ik_manager.set_mechanism_position_target.reset_mock()

    part_enabled_state["arm"] = False
    coordinator.update_frame(
        tab_active=True,
        mechanism_layers=mechanism_layers,
        part_enabled_state=part_enabled_state,
        parts_data=parts_data,
        ik_manager=ik_manager,
        path_trace_manager=path_trace_manager,
        scene=scene,
        initial_skeleton_cache=None,
    )

    ik_manager.clear_mechanism_position_targets.assert_called_once()
    ik_manager.set_mechanism_position_target.assert_called_once()
    assert ik_manager.set_mechanism_position_target.call_args.args[0] == "knee"
