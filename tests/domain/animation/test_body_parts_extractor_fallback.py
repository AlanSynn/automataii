from __future__ import annotations

import json
import logging

import cv2
import numpy as np
import yaml

from automataii.domain.animation.body_parts_extractor import BodyPartsExtractor
from automataii.domain.animation.part_definitions import BODY_PARTS


def _empty_masks(shape: tuple[int, int]) -> dict[str, np.ndarray]:
    return {name: np.zeros(shape, dtype=np.uint8) for name in BODY_PARTS}


def test_default_output_dir_uses_char_dir_bpe_output(tmp_path) -> None:
    char_dir = tmp_path / "character"
    char_dir.mkdir()

    extractor = BodyPartsExtractor(char_dir=str(char_dir))

    assert extractor.output_dir == char_dir / "bpe_output"


def test_missing_initial_data_logs_required_files(tmp_path, caplog) -> None:
    char_dir = tmp_path / "character"
    char_dir.mkdir()
    extractor = BodyPartsExtractor(char_dir=str(char_dir))

    caplog.set_level(logging.ERROR)

    assert extractor._load_initial_data() is False
    assert "BodyPartsExtractor input is incomplete" in caplog.text
    assert "char_cfg.yaml" in caplog.text
    assert "texture.png" in caplog.text
    assert "mask.png" in caplog.text


def test_create_joint_map_preserves_semantic_underscore_ids() -> None:
    extractor = BodyPartsExtractor(char_dir=".", output_dir=".")

    joint_map = extractor._create_joint_map(
        {
            "joints": {
                "left_shoulder": {"position": [10, 20]},
                "right_elbow_0": {"position": [30, 40]},
                "hand_slot": {"name": "right_hand", "position": [50, 60]},
            }
        }
    )

    assert joint_map["left_shoulder"] == (10, 20)
    assert "left" not in joint_map
    assert joint_map["right_elbow"] == (30, 40)
    assert joint_map["right_hand"] == (50, 60)


def _write_minimal_character(char_dir) -> None:
    char_dir.mkdir()
    texture = np.full((120, 120, 4), 220, dtype=np.uint8)
    texture[:, :, 3] = 255
    mask = np.zeros((120, 120), dtype=np.uint8)
    cv2.rectangle(mask, (8, 4), (112, 116), 255, thickness=-1)

    cv2.imwrite(str(char_dir / "texture.png"), texture)
    cv2.imwrite(str(char_dir / "image.png"), texture)
    cv2.imwrite(str(char_dir / "mask.png"), mask)

    positions = {
        "head_top": (60.5, 8.25),
        "neck": (60.25, 20.75),
        "torso": (60.5, 42.25),
        "pelvis": (60.5, 70.25),
        "left_shoulder": (42.25, 28.5),
        "left_elbow": (30.75, 45.5),
        "left_wrist": (24.25, 60.5),
        "left_hand": (20.75, 70.5),
        "right_shoulder": (78.25, 28.5),
        "right_elbow": (90.75, 45.5),
        "right_wrist": (96.25, 60.5),
        "right_hand": (100.75, 70.5),
        "left_hip": (48.25, 74.5),
        "left_knee": (44.75, 94.5),
        "left_ankle": (42.25, 112.5),
        "left_foot": (38.75, 116.5),
        "right_hip": (72.25, 74.5),
        "right_knee": (76.75, 94.5),
        "right_ankle": (78.25, 112.5),
        "right_foot": (82.75, 116.5),
    }
    parents = {
        "head_top": "neck_0",
        "neck": "torso_0",
        "torso": "pelvis_0",
        "left_shoulder": "torso_0",
        "left_elbow": "left_shoulder_0",
        "left_wrist": "left_elbow_0",
        "left_hand": "left_wrist_0",
        "right_shoulder": "torso_0",
        "right_elbow": "right_shoulder_0",
        "right_wrist": "right_elbow_0",
        "right_hand": "right_wrist_0",
        "left_hip": "pelvis_0",
        "left_knee": "left_hip_0",
        "left_ankle": "left_knee_0",
        "left_foot": "left_ankle_0",
        "right_hip": "pelvis_0",
        "right_knee": "right_hip_0",
        "right_ankle": "right_knee_0",
        "right_foot": "right_ankle_0",
    }
    joints = {}
    for name, position in positions.items():
        joint = {"position": [position[0], position[1]]}
        parent_id = parents.get(name)
        if parent_id:
            joint["parent_id"] = parent_id
        joints[f"{name}_0"] = joint

    (char_dir / "char_cfg.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "Fixture",
                "width": 120,
                "height": 120,
                "joints": joints,
            }
        ),
        encoding="utf-8",
    )


def test_process_cleanup_preserves_unrelated_output_files(tmp_path) -> None:
    char_dir = tmp_path / "character"
    _write_minimal_character(char_dir)
    output_dir = tmp_path / "shared-output"
    output_dir.mkdir()

    sentinels = {
        "notes.png": b"keep png",
        "manual.json": b'{"keep": true}',
        "old.html": b"<p>keep</p>",
        "animation.gif": b"GIF89a",
    }
    for filename, content in sentinels.items():
        (output_dir / filename).write_bytes(content)

    extractor = BodyPartsExtractor(char_dir=str(char_dir), output_dir=str(output_dir))
    extractor.process()

    for filename, content in sentinels.items():
        assert (output_dir / filename).read_bytes() == content
    assert (output_dir / "parts_info.json").exists()


def test_process_exports_normalized_parents_and_float_positions(tmp_path) -> None:
    char_dir = tmp_path / "character"
    _write_minimal_character(char_dir)
    output_dir = tmp_path / "bpe-output"

    extractor = BodyPartsExtractor(char_dir=str(char_dir), output_dir=str(output_dir))
    extractor.process()

    parts_info = json.loads((output_dir / "parts_info.json").read_text(encoding="utf-8"))
    joints = {joint["id"]: joint for joint in parts_info["character"]["skeleton_joints"]}

    assert joints["left_elbow"]["parent"] == "left_shoulder"
    assert joints["left_elbow"]["position"] == [30.75, 45.5]
    assert joints["left_shoulder"]["parent"] == "torso"


def test_synthesize_missing_limb_masks_creates_upper_arms() -> None:
    extractor = BodyPartsExtractor(char_dir=".", output_dir=".")
    extractor.mask = np.zeros((200, 200), dtype=np.uint8)
    cv2.rectangle(extractor.mask, (40, 30), (160, 190), 255, thickness=-1)
    extractor.texture_relative_joint_map = {
        # compact joints near torso (typical collapse case)
        "left_shoulder": (115, 95),
        "left_elbow": (120, 102),
        "left_hand": (124, 112),
        "right_shoulder": (85, 95),
        "right_elbow": (80, 102),
        "right_hand": (76, 112),
        "left_hip": (110, 130),
        "left_knee": (112, 150),
        "left_foot": (114, 170),
        "right_hip": (90, 130),
        "right_knee": (88, 150),
        "right_foot": (86, 170),
    }

    masks = _empty_masks(extractor.mask.shape)
    filled = extractor._synthesize_missing_limb_masks(masks)

    assert np.count_nonzero(filled["left_arm_upper"]) > 0
    assert np.count_nonzero(filled["right_arm_upper"]) > 0
    assert np.count_nonzero(filled["left_leg_upper"]) > 0
    assert np.count_nonzero(filled["right_leg_upper"]) > 0


def test_synthesize_missing_limb_masks_preserves_existing_mask() -> None:
    extractor = BodyPartsExtractor(char_dir=".", output_dir=".")
    extractor.mask = np.zeros((120, 120), dtype=np.uint8)
    cv2.rectangle(extractor.mask, (20, 20), (100, 110), 255, thickness=-1)
    extractor.texture_relative_joint_map = {
        "left_shoulder": (70, 50),
        "left_elbow": (80, 58),
        "left_hand": (90, 65),
    }

    masks = _empty_masks(extractor.mask.shape)
    cv2.rectangle(masks["left_arm_upper"], (62, 45), (72, 60), 255, thickness=-1)
    before = int(np.count_nonzero(masks["left_arm_upper"]))

    filled = extractor._synthesize_missing_limb_masks(masks)
    after = int(np.count_nonzero(filled["left_arm_upper"]))

    assert after >= before
