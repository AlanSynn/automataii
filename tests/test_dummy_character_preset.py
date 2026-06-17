"""Regression coverage for the bundled Image #1 dummy character preset."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from PIL import Image

DUMMY_DIR = Path("resources/presets/characters/dummy")
CANVAS_SIZE = (1536, 1024)


def test_dummy_segmentation_canvas_matches_landscape_reference() -> None:
    image = Image.open(DUMMY_DIR / "segmentation_vis.png")

    assert image.size == CANVAS_SIZE
    assert image.width > image.height
    assert image.getbbox() is not None


def test_dummy_character_config_and_parts_are_in_canvas_bounds() -> None:
    cfg = yaml.safe_load((DUMMY_DIR / "char_cfg.yaml").read_text())
    parts_info = json.loads((DUMMY_DIR / "parts_info.json").read_text())
    parts = parts_info["character"]["parts"]
    skeleton = parts_info["character"]["skeleton_joints"]

    assert (cfg["width"], cfg["height"]) == CANVAS_SIZE
    assert (cfg["bbox_origin_r"], cfg["bbox_origin_b"]) == CANVAS_SIZE

    skeleton_by_id = {joint["id"]: joint for joint in skeleton}
    for joint in skeleton:
        x, y = joint["position"]
        assert 0.0 <= float(x) <= CANVAS_SIZE[0]
        assert 0.0 <= float(y) <= CANVAS_SIZE[1]

    for part in parts.values():
        x, y, width, height = [float(value) for value in part["roi"]]
        assert 0.0 <= x < CANVAS_SIZE[0]
        assert 0.0 <= y < CANVAS_SIZE[1]
        assert width > 0.0
        assert height > 0.0
        assert x + width <= CANVAS_SIZE[0]
        assert y + height <= CANVAS_SIZE[1]

        part_image = Image.open(DUMMY_DIR / part["image_path"])
        assert part_image.size == pytest.approx((width, height), abs=0.5)
        assert part_image.getbbox() is not None

        pivot_x, pivot_y = [float(value) for value in part["local_pivot_offset"]]
        assert 0.0 <= pivot_x <= width
        assert 0.0 <= pivot_y <= height
        assert part["anchor_joint_id"] in skeleton_by_id
