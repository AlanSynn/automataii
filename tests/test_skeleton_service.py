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
