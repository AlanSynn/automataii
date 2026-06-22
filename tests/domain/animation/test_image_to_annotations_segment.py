import logging
import shutil
from pathlib import Path

import cv2
import numpy as np

from automataii.domain.animation.image_to_annotations import (
    IMAGE_TEMP_STEM_MAX_CHARS,
    _build_image_temp_session_id,
    _compute_skeleton_bbox,
    _reconcile_skeleton_to_mask,
    image_to_annotations,
    segment,
)
from automataii.utils.paths import get_session_temp_dir


def test_segment_alpha_keeps_disconnected_components() -> None:
    img = np.zeros((160, 160, 4), dtype=np.uint8)

    # Main body
    cv2.rectangle(img, (60, 50), (100, 130), (255, 255, 255, 255), -1)
    # Disconnected limbs (common with transparent sprite-like assets)
    cv2.rectangle(img, (20, 65), (45, 95), (255, 255, 255, 255), -1)
    cv2.rectangle(img, (115, 65), (140, 95), (255, 255, 255, 255), -1)

    mask = segment(img)

    assert mask[80, 80] > 0  # body
    assert mask[80, 30] > 0  # left limb must remain
    assert mask[80, 125] > 0  # right limb must remain


def test_segment_line_art_keeps_disconnected_components() -> None:
    img = np.full((180, 180, 3), 255, dtype=np.uint8)

    # Torso
    cv2.rectangle(img, (70, 40), (110, 150), (0, 0, 0), thickness=-1)
    # Disconnected arm-like islands
    cv2.rectangle(img, (15, 75), (45, 100), (0, 0, 0), thickness=-1)
    cv2.rectangle(img, (135, 75), (165, 100), (0, 0, 0), thickness=-1)

    mask = segment(img)

    assert mask[100, 90] > 0  # torso
    assert mask[85, 30] > 0  # left island
    assert mask[85, 150] > 0  # right island


def test_reconcile_skeleton_to_mask_refits_extreme_mismatch() -> None:
    mask = np.zeros((240, 240), dtype=np.uint8)
    cv2.rectangle(mask, (80, 50), (160, 220), 255, thickness=-1)

    skeleton = [
        {"name": "torso", "loc": [20, 20], "parent": "hip"},
        {"name": "neck", "loc": [30, 10], "parent": "torso"},
        {"name": "left_shoulder", "loc": [0, 30], "parent": "torso"},
        {"name": "right_shoulder", "loc": [180, 35], "parent": "torso"},
        {"name": "left_hand", "loc": [-20, 70], "parent": "left_shoulder"},
        {"name": "right_hand", "loc": [220, 75], "parent": "right_shoulder"},
        {"name": "hip", "loc": [40, 110], "parent": "root"},
        {"name": "left_foot", "loc": [10, 230], "parent": "hip"},
        {"name": "right_foot", "loc": [210, 235], "parent": "hip"},
    ]

    adjusted = _reconcile_skeleton_to_mask(skeleton, mask)
    bbox = _compute_skeleton_bbox(adjusted)
    assert bbox is not None
    x1, y1, x2, y2 = bbox

    # Refit should place skeleton around the silhouette region.
    assert x1 >= 60
    assert y1 >= 30
    assert x2 <= 180
    assert y2 <= 230


def test_reconcile_skeleton_to_mask_noop_when_already_aligned() -> None:
    mask = np.zeros((200, 200), dtype=np.uint8)
    cv2.rectangle(mask, (40, 30), (160, 190), 255, thickness=-1)
    skeleton = [
        {"name": "torso", "loc": [100, 90], "parent": "hip"},
        {"name": "neck", "loc": [100, 50], "parent": "torso"},
        {"name": "left_shoulder", "loc": [70, 90], "parent": "torso"},
        {"name": "right_shoulder", "loc": [130, 90], "parent": "torso"},
        {"name": "hip", "loc": [100, 130], "parent": "root"},
        {"name": "left_foot", "loc": [85, 180], "parent": "hip"},
        {"name": "right_foot", "loc": [115, 180], "parent": "hip"},
    ]
    original = [dict(joint) for joint in skeleton]

    adjusted = _reconcile_skeleton_to_mask(skeleton, mask)
    assert adjusted == original


def test_reconcile_skeleton_to_mask_handles_extreme_oversize_pose() -> None:
    mask = np.zeros((220, 220), dtype=np.uint8)
    cv2.rectangle(mask, (70, 45), (150, 205), 255, thickness=-1)

    # Deliberately oversized "human" pose against a small mascot silhouette.
    skeleton = [
        {"name": "root", "loc": [-800, -900], "parent": None},
        {"name": "hip", "loc": [-780, -600], "parent": "root"},
        {"name": "torso", "loc": [-760, -350], "parent": "hip"},
        {"name": "neck", "loc": [-730, -120], "parent": "torso"},
        {"name": "left_shoulder", "loc": [-1200, -300], "parent": "torso"},
        {"name": "right_shoulder", "loc": [200, -320], "parent": "torso"},
        {"name": "left_hand", "loc": [-1800, -100], "parent": "left_shoulder"},
        {"name": "right_hand", "loc": [900, -80], "parent": "right_shoulder"},
        {"name": "left_foot", "loc": [-1000, 1100], "parent": "hip"},
        {"name": "right_foot", "loc": [100, 1150], "parent": "hip"},
    ]

    adjusted = _reconcile_skeleton_to_mask(skeleton, mask)
    bbox = _compute_skeleton_bbox(adjusted)
    assert bbox is not None
    x1, y1, x2, y2 = bbox

    # Skeleton should be pulled back onto the silhouette neighborhood.
    assert x1 >= 45
    assert y1 >= 20
    assert x2 <= 175
    assert y2 <= 220


def test_same_stem_images_get_distinct_temp_session_dirs(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first_image = first_dir / "character.png"
    second_image = second_dir / "character.png"
    first_image.write_bytes(b"first")
    second_image.write_bytes(b"second")

    first_session = _build_image_temp_session_id(str(first_image))
    second_session = _build_image_temp_session_id(str(second_image))

    assert first_session is not None
    assert second_session is not None
    assert first_session != second_session
    assert first_session.startswith("character_")
    assert second_session.startswith("character_")

    first_output = get_session_temp_dir(first_session, clear_existing=False)
    second_output: Path | None = None
    try:
        marker = first_output / "marker.txt"
        marker.write_text("keep", encoding="utf-8")
        second_output = get_session_temp_dir(second_session, clear_existing=False)

        assert first_output != second_output
        assert marker.exists()
    finally:
        shutil.rmtree(first_output, ignore_errors=True)
        if second_output is not None:
            shutil.rmtree(second_output, ignore_errors=True)


def test_image_temp_session_id_truncates_long_stems(tmp_path: Path) -> None:
    long_stem = "a" * 300
    session_id = _build_image_temp_session_id(str(tmp_path / f"{long_stem}.png"))

    assert session_id is not None
    visible_stem, source_digest, run_suffix = session_id.rsplit("_", 2)
    assert visible_stem == "a" * IMAGE_TEMP_STEM_MAX_CHARS
    assert len(source_digest) == 12
    assert len(run_suffix) == 8
    assert len(session_id) < 120


def test_image_to_annotations_fails_when_required_pose_model_is_missing(
    tmp_path: Path,
    caplog,
) -> None:
    image_path = tmp_path / "missing_pose_character.png"
    image = np.full((160, 120, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (35, 20), (85, 145), (0, 0, 0), thickness=-1)
    assert cv2.imwrite(str(image_path), image)

    with caplog.at_level(logging.ERROR):
        result = image_to_annotations(
            str(image_path),
            detector_onnx=tmp_path / "missing_detector.onnx",
            pose_onnx=tmp_path / "missing_pose.onnx",
        )

    assert result is None
    assert "Required pose ONNX model not found" in caplog.text


def test_image_to_annotations_handles_unicode_paths(tmp_path: Path) -> None:
    image_dir = tmp_path / "windows_image_é"
    image_dir.mkdir()
    image_path = image_dir / "character_é.png"
    image = np.full((96, 96, 4), 0, dtype=np.uint8)
    cv2.circle(image, (48, 48), 32, (40, 80, 200, 255), thickness=-1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    encoded.tofile(str(image_path))

    result = image_to_annotations(str(image_path))

    assert result is not None
    output_dir = Path(result["output_dir"])
    try:
        assert Path(result["char_cfg_path"]).is_file()
        assert Path(result["texture_path"]).is_file()
        assert Path(result["mask_path"]).is_file()
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)
