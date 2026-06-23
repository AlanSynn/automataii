from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from automataii.presentation.qt.interactive_segmentation_editor import (
    InteractiveSegmentationEditor,
)


def test_interactive_segmentation_editor_preview_uses_image_dimensions() -> None:
    editor = SimpleNamespace(
        image_width=120,
        image_height=80,
        boundary_points={"torso": [(10, 10), (100, 10), (50, 60)]},
    )

    preview = InteractiveSegmentationEditor._generate_segmentation_preview(editor)

    assert preview["torso"] is not None
    assert isinstance(preview["torso"], np.ndarray)
    assert preview["torso"].shape == (80, 120)


def test_interactive_segmentation_editor_default_joints_use_image_dimensions() -> None:
    editor = SimpleNamespace(image_width=120, image_height=80)

    joints = InteractiveSegmentationEditor._create_default_joint_positions(editor)

    assert joints["neck"] == (60, 9)
    assert joints["right_wrist"] == (102, 33)


def test_interactive_segmentation_editor_preserves_underscore_joint_names() -> None:
    assert (
        InteractiveSegmentationEditor._joint_name_from_payload(
            "left_shoulder",
            {"position": [10, 20]},
        )
        == "left_shoulder"
    )
    assert (
        InteractiveSegmentationEditor._joint_name_from_payload(
            "right_elbow_0",
            {"position": [30, 20]},
        )
        == "right_elbow"
    )
    assert (
        InteractiveSegmentationEditor._joint_name_from_payload(
            "hand_slot",
            {"name": "right_hand", "position": [45, 25]},
        )
        == "right_hand"
    )


def test_interactive_segmentation_editor_accepts_alternate_joint_position_keys() -> None:
    editor = SimpleNamespace(
        skeleton_data={
            "joints": {
                "left_shoulder": {"loc": [10.5, 20.25]},
                "right_elbow_0": {"coordinates": [30.75, 40.5]},
            }
        },
        joint_positions={},
        _joint_name_from_payload=InteractiveSegmentationEditor._joint_name_from_payload,
    )

    InteractiveSegmentationEditor._extract_joint_positions(editor)

    assert editor.joint_positions["left_shoulder"] == (10.5, 20.25)
    assert editor.joint_positions["right_elbow"] == (30.75, 40.5)


def test_interactive_segmentation_editor_list_skeleton_uses_shared_position_parser() -> None:
    editor = SimpleNamespace(
        skeleton_data={
            "skeleton": [
                {"name": "left_shoulder", "position": [10.5, 20.25]},
                {"name": "right_elbow", "coordinates": [30.75, 40.5]},
            ]
        },
        joint_positions={},
    )

    InteractiveSegmentationEditor._extract_joint_positions(editor)

    assert editor.joint_positions["left_shoulder"] == (10.5, 20.25)
    assert editor.joint_positions["right_elbow"] == (30.75, 40.5)


def test_interactive_segmentation_editor_can_redefine_part_as_joint_box() -> None:
    editor = SimpleNamespace(
        selected_joints={"left_shoulder", "right_shoulder"},
        joint_positions={"left_shoulder": (20.0, 30.0), "right_shoulder": (80.0, 40.0)},
        image_width=100,
        image_height=80,
    )

    points = InteractiveSegmentationEditor._current_joint_box_points(editor, padding=10)

    assert points == [(10.0, 20.0), (90.0, 20.0), (90.0, 50.0), (10.0, 50.0)]
