from __future__ import annotations

from dataclasses import dataclass

from automataii.presentation.qt.main_window import (
    AutomataDesigner,
    _align_skeleton_bbox_to_parts_in_place,
    _calculate_parts_bbox,
    _calculate_skeleton_bbox,
    _scale_parts_in_place,
    _scale_skeleton_raw_in_place,
)


@dataclass
class _PartStub:
    roi: list[float]
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


def test_normalize_character_scale_prefers_parts_bbox_height() -> None:
    window = AutomataDesigner.__new__(AutomataDesigner)
    window._dummy_reference_height_px = 400.0

    parts = {"torso": _PartStub([0.0, 0.0, 100.0, 100.0])}
    skeleton = [
        {"name": "root", "position": [0.0, 0.0]},
        {"name": "tip", "position": [0.0, 1000.0]},
    ]

    parts_out, skeleton_out, scale = AutomataDesigner._normalize_character_scale_to_dummy(
        window,
        parts,
        skeleton,
    )

    assert parts_out is parts
    assert skeleton_out is skeleton
    assert abs(scale - 4.0) < 1e-6
    assert abs(parts["torso"].roi[2] - 400.0) < 1e-6
    normalized_bbox = _calculate_skeleton_bbox(skeleton)
    assert normalized_bbox is not None
