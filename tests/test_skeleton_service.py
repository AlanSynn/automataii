from __future__ import annotations

from types import SimpleNamespace

from automataii.application.mechanisms.skeleton_service import SkeletonService


def test_position_parts_does_not_apply_generic_joint_rotation() -> None:
    service = SkeletonService()

    part_item = SimpleNamespace()
    position_calls: list[tuple[float, float]] = []
    rotation_calls: list[float] = []

    def _set_pos(_item: object, pos: tuple[float, float]) -> None:
        position_calls.append(pos)

    def _set_rot(_item: object, rot: float) -> None:
        rotation_calls.append(rot)

    part_info = SimpleNamespace(anchor_joint_id="torso")
    positioned = service.position_parts_at_anchor_joints(
        current_editor_items={"torso": part_item},
        parts_data={"torso": part_info},
        initial_skeleton_data_cache={
            "joints": {
                "torso": {"position": [10.0, 20.0], "rotation": 90.0},
            }
        },
        position_setter=_set_pos,
        rotation_setter=_set_rot,
    )

    assert positioned == 1
    assert position_calls == [(10.0, 20.0)]
    assert rotation_calls == []


def test_position_parts_applies_explicit_part_rotation() -> None:
    service = SkeletonService()

    part_item = SimpleNamespace()
    rotation_calls: list[float] = []

    def _set_pos(_item: object, _pos: tuple[float, float]) -> None:
        return None

    def _set_rot(_item: object, rot: float) -> None:
        rotation_calls.append(rot)

    part_info = SimpleNamespace(anchor_joint_id="head")
    positioned = service.position_parts_at_anchor_joints(
        current_editor_items={"head": part_item},
        parts_data={"head": part_info},
        initial_skeleton_data_cache={
            "joints": {
                "head": {"position": [1.0, 2.0], "part_rotation_degrees": 12.5},
            }
        },
        position_setter=_set_pos,
        rotation_setter=_set_rot,
    )

    assert positioned == 1
    assert rotation_calls == [12.5]


def test_position_parts_uses_joint_map_like_editor_tab() -> None:
    service = SkeletonService()
    part_item = SimpleNamespace()
    position_calls: list[tuple[float, float]] = []

    part_info = SimpleNamespace(anchor_joint_id="left_hand")
    positioned = service.position_parts_at_anchor_joints(
        current_editor_items={"hand": part_item},
        parts_data={"hand": part_info},
        initial_skeleton_data_cache={
            "joint_map": {"left_hand": "left_wrist"},
            "joints": {"left_wrist": {"position": [30.0, 40.0]}},
        },
        position_setter=lambda _item, pos: position_calls.append(pos),
    )

    assert positioned == 1
    assert position_calls == [(30.0, 40.0)]


def test_position_parts_uses_prefixed_joint_and_scene_position() -> None:
    service = SkeletonService()
    part_item = SimpleNamespace()
    position_calls: list[tuple[float, float]] = []

    part_info = SimpleNamespace(anchor_joint_id="elbow")
    positioned = service.position_parts_at_anchor_joints(
        current_editor_items={"arm": part_item},
        parts_data={"arm": part_info},
        initial_skeleton_data_cache={
            "joints": {"elbow_1": {"scene_position": [12.0, 24.0]}},
        },
        position_setter=lambda _item, pos: position_calls.append(pos),
    )

    assert positioned == 1
    assert position_calls == [(12.0, 24.0)]


def test_position_parts_skips_invalid_joint_coordinates() -> None:
    service = SkeletonService()
    part_item = SimpleNamespace()

    part_info = SimpleNamespace(anchor_joint_id="head")
    positioned = service.position_parts_at_anchor_joints(
        current_editor_items={"head": part_item},
        parts_data={"head": part_info},
        initial_skeleton_data_cache={"joints": {"head": {"position": [float("nan"), 1.0]}}},
        position_setter=lambda _item, _pos: None,
    )

    assert positioned == 0
