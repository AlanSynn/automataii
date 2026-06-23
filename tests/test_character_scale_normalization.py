from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from automataii.infrastructure.generation.svg.optimizer import BlueprintLayoutOptimizer
from automataii.presentation.qt.main_window import (
    AutomataDesigner,
    _align_parts_bbox_to_skeleton_in_place,
    _align_skeleton_bbox_to_parts_in_place,
    _calculate_parts_bbox,
    _calculate_skeleton_bbox,
    _calculate_visible_parts_bbox,
    _scale_parts_in_place,
    _scale_skeleton_raw_in_place,
)
from automataii.shared.physical_kit import (
    LETTER_PAGE_HEIGHT_MM,
    LETTER_PAGE_SIZE_MM,
    letter_page_fit_scale,
)


@dataclass
class _PartStub:
    roi: list[float]
    image_path: str | None = None
    x: float = 0.0
    y: float = 0.0
    local_pivot_offset: list[float] | None = None
    effective_bbox_offset_x: float = 0.0
    effective_bbox_offset_y: float = 0.0


def test_calculate_parts_bbox_uses_roi_extents() -> None:
    parts = {
        "head": _PartStub([10.0, 20.0, 50.0, 60.0]),
        "torso": _PartStub([0.0, 40.0, 100.0, 200.0]),
    }

    bbox = _calculate_parts_bbox(parts)

    assert bbox == (0.0, 20.0, 100.0, 240.0)


def test_calculate_skeleton_bbox_supports_position_and_loc_keys() -> None:
    raw = [
        {"name": "root", "position": [100.0, 200.0]},
        {"name": "hand", "loc": [300.0, 500.0]},
    ]

    bbox = _calculate_skeleton_bbox(raw)

    assert bbox == (100.0, 200.0, 300.0, 500.0)


def test_scale_parts_and_skeleton_in_place_about_center() -> None:
    parts = {
        "torso": _PartStub(
            roi=[100.0, 100.0, 100.0, 200.0],
            local_pivot_offset=[10.0, -5.0],
            effective_bbox_offset_x=3.0,
            effective_bbox_offset_y=-4.0,
        )
    }
    skeleton = [{"name": "root", "position": [150.0, 200.0]}]

    _scale_parts_in_place(parts, scale_factor=2.0, center=(150.0, 200.0))
    _scale_skeleton_raw_in_place(skeleton, scale_factor=2.0, center=(150.0, 200.0))

    torso = parts["torso"]
    assert torso.roi == [50.0, 0.0, 200.0, 400.0]
    assert torso.x == 50.0
    assert torso.y == 0.0
    assert torso.local_pivot_offset == [20.0, -10.0]
    assert torso.effective_bbox_offset_x == 6.0
    assert torso.effective_bbox_offset_y == -8.0
    assert skeleton[0]["position"] == [150.0, 200.0]


def test_align_skeleton_bbox_to_parts_bbox_when_scale_mismatch() -> None:
    parts = {"torso": _PartStub([0.0, 0.0, 100.0, 100.0])}
    parts_bbox = _calculate_parts_bbox(parts)
    skeleton = [
        {"name": "root", "position": [0.0, 0.0]},
        {"name": "tip", "position": [0.0, 300.0]},
    ]

    aligned = _align_skeleton_bbox_to_parts_in_place(skeleton, parts_bbox)
    aligned_bbox = _calculate_skeleton_bbox(skeleton)

    assert aligned is True
    assert aligned_bbox is not None
    aligned_h = aligned_bbox[3] - aligned_bbox[1]
    aligned_center_x = (aligned_bbox[0] + aligned_bbox[2]) * 0.5
    aligned_center_y = (aligned_bbox[1] + aligned_bbox[3]) * 0.5
    assert abs(aligned_h - 100.0) < 1e-6
    assert abs(aligned_center_x - 50.0) < 1e-6
    assert abs(aligned_center_y - 50.0) < 1e-6


def test_normalize_character_scale_prefers_parts_bbox_and_fits_letter_sheet() -> None:
    window = AutomataDesigner.__new__(AutomataDesigner)

    parts = {"torso": _PartStub([0.0, 0.0, 100.0, 100.0])}
    skeleton = [
        {"name": "root", "position": [0.0, 0.0]},
        {"name": "tip", "position": [0.0, 1000.0]},
    ]

    parts_out, skeleton_out, scale = AutomataDesigner._normalize_character_scale_to_letter(
        window,
        parts,
        skeleton,
    )

    assert parts_out is parts
    assert skeleton_out is skeleton
    assert abs(scale - (LETTER_PAGE_SIZE_MM[0] / 100.0)) < 1e-6
    assert abs(parts["torso"].roi[2] - LETTER_PAGE_SIZE_MM[0]) < 1e-6
    normalized_bbox = _calculate_skeleton_bbox(skeleton)
    assert normalized_bbox is not None
    assert abs(normalized_bbox[3] - normalized_bbox[1] - LETTER_PAGE_SIZE_MM[0]) < 1e-6


def test_bundled_dummy_character_normalizes_to_fit_letter_sheet() -> None:
    payload = json.loads(
        Path("resources/presets/characters/dummy/parts_info.json").read_text(encoding="utf-8")
    )
    parts = {
        name: _PartStub([float(value) for value in part["roi"]])
        for name, part in payload["character"]["parts"].items()
    }
    window = AutomataDesigner.__new__(AutomataDesigner)

    _, _, scale = AutomataDesigner._normalize_character_scale_to_letter(window, parts, None)

    bbox = _calculate_parts_bbox(parts)
    assert bbox is not None
    assert scale < 1.0
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    portrait_fit = width <= LETTER_PAGE_SIZE_MM[0] and height <= LETTER_PAGE_SIZE_MM[1]
    landscape_fit = width <= LETTER_PAGE_SIZE_MM[1] and height <= LETTER_PAGE_SIZE_MM[0]
    assert portrait_fit or landscape_fit
    assert abs(height - LETTER_PAGE_SIZE_MM[0]) < 1e-6


def test_near_letter_height_still_normalizes_to_exact_letter_height() -> None:
    parts = {"torso": _PartStub([0.0, 0.0, 100.0, 300.0])}
    window = AutomataDesigner.__new__(AutomataDesigner)

    _, _, scale = AutomataDesigner._normalize_character_scale_to_letter(window, parts, None)

    bbox = _calculate_parts_bbox(parts)
    assert bbox is not None
    assert abs(scale - letter_page_fit_scale(100.0, 300.0)) < 1e-6
    assert abs(bbox[3] - bbox[1] - LETTER_PAGE_HEIGHT_MM) < 1e-6


def test_blueprint_character_parts_use_assembled_bbox_and_emit_pivot_drill_holes() -> None:
    dummy_dir = Path("resources/presets/characters/dummy")
    torso = _PartStub(
        roi=[610.0, 230.0, 316.0, 372.0],
        image_path=str(dummy_dir / "torso.png"),
        x=610.0,
        y=230.0,
        local_pivot_offset=[158.0, 140.0],
    )
    head = _PartStub(
        roi=[686.0, 54.0, 164.0, 190.0],
        image_path=str(dummy_dir / "head.png"),
        x=686.0,
        y=54.0,
        local_pivot_offset=[82.0, 186.0],
    )
    torso.name = "torso"  # type: ignore[attr-defined]
    head.name = "head"  # type: ignore[attr-defined]
    part_items = [
        type("PartItem", (), {"part_info": torso})(),
        type("PartItem", (), {"part_info": head})(),
    ]

    optimizer = BlueprintLayoutOptimizer(target_character_height_mm=LETTER_PAGE_HEIGHT_MM)
    layout_items = optimizer._process_character_parts(part_items)
    by_name = {item.name: item for item in layout_items}

    assert "pivot-drill-hole" in by_name["torso"].svg_content
    assert 'data-hole-diameter-mm="4"' in by_name["torso"].svg_content
    assert by_name["head"].group == "head_neck"
    assert 'data-group="head_neck"' in by_name["head"].svg_content
    # If the scale is computed from isolated torso bounds, torso becomes almost
    # 300mm tall.  The assembled character bbox keeps it proportional.
    assert by_name["torso"].bounds.height < 240.0


def test_blueprint_pivot_holes_use_roi_coordinate_space_for_resized_png(
    tmp_path: Path,
) -> None:
    img = np.zeros((100, 100, 4), dtype=np.uint8)
    img[:, :, :3] = 255
    img[:, :, 3] = 255
    part_path = tmp_path / "square.png"
    cv2.imwrite(str(part_path), img)

    part = _PartStub(
        roi=[0.0, 0.0, 200.0, 200.0],
        image_path=str(part_path),
        local_pivot_offset=[100.0, 100.0],
    )
    part.name = "square"  # type: ignore[attr-defined]
    part_item = type("PartItem", (), {"part_info": part})()

    optimizer = BlueprintLayoutOptimizer(target_character_height_mm=LETTER_PAGE_HEIGHT_MM)
    layout_items = optimizer._process_character_parts([part_item])

    assert len(layout_items) == 1
    item = layout_items[0]
    assert abs(item.bounds.width - LETTER_PAGE_SIZE_MM[0]) < 3.0
    assert abs(item.bounds.height - LETTER_PAGE_SIZE_MM[0]) < 3.0
    assert 'class="pivot-drill-hole"' in item.svg_content
    cx_match = re.search(r'cx="([0-9.]+)"', item.svg_content)
    cy_match = re.search(r'cy="([0-9.]+)"', item.svg_content)
    assert cx_match is not None
    assert cy_match is not None
    assert abs(float(cx_match.group(1)) - (LETTER_PAGE_SIZE_MM[0] / 2.0)) < 2.0
    assert abs(float(cy_match.group(1)) - (LETTER_PAGE_SIZE_MM[0] / 2.0)) < 2.0
    assert abs(float(cx_match.group(1)) - 300.0) > 100.0
    assert abs(float(cy_match.group(1)) - 300.0) > 100.0


def test_align_parts_bbox_to_skeleton_upscales_when_parts_too_small() -> None:
    parts = {"torso": _PartStub([0.0, 0.0, 60.0, 60.0])}
    skeleton = [
        {"name": "root", "position": [50.0, 0.0]},
        {"name": "tip", "position": [50.0, 200.0]},
    ]

    aligned = _align_parts_bbox_to_skeleton_in_place(parts, skeleton)
    assert aligned is True

    parts_bbox = _calculate_parts_bbox(parts)
    assert parts_bbox is not None
    parts_h = parts_bbox[3] - parts_bbox[1]
    assert abs(parts_h - 200.0) < 1e-6


def test_align_parts_bbox_to_skeleton_noop_when_parts_already_similar() -> None:
    parts = {"torso": _PartStub([0.0, 0.0, 100.0, 190.0])}
    skeleton = [
        {"name": "root", "position": [50.0, 0.0]},
        {"name": "tip", "position": [50.0, 200.0]},
    ]

    original_roi = list(parts["torso"].roi)
    aligned = _align_parts_bbox_to_skeleton_in_place(parts, skeleton)
    assert aligned is False
    assert parts["torso"].roi == original_roi


def test_calculate_visible_parts_bbox_uses_alpha_pixels(tmp_path) -> None:
    img = np.zeros((10, 10, 4), dtype=np.uint8)
    img[2:8, 3:9, 3] = 255
    part_path = tmp_path / "part.png"
    cv2.imwrite(str(part_path), img)

    parts = {
        "torso": _PartStub(
            roi=[100.0, 200.0, 50.0, 100.0],
            image_path=str(part_path),
        )
    }

    bbox = _calculate_visible_parts_bbox(parts)
    assert bbox is not None
    x1, y1, x2, y2 = bbox

    # local visible bbox is x:[3,9), y:[2,8) then mapped into ROI scale.
    assert abs(x1 - (100.0 + 3.0 * 5.0)) < 1e-6
    assert abs(x2 - (100.0 + 9.0 * 5.0)) < 1e-6
    assert abs(y1 - (200.0 + 2.0 * 10.0)) < 1e-6
    assert abs(y2 - (200.0 + 8.0 * 10.0)) < 1e-6
