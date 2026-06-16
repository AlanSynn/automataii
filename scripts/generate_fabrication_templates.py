#!/usr/bin/env python3
"""Generate fabrication-ready SVG templates for the physical Automataii kit.

The committed ``fabrication/`` package is the default physical board pitch
(20.0 mm).  The generator can also be used with alternate board pitches for
custom output while preserving the nominal 6 mm bracket/axle hole contract.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from automataii.domain.mechanisms.cam.profile import (  # noqa: E402
    build_pear_cam_profile_from_params,
    cam_profile_to_drawing_points,
)
from automataii.shared.physical_kit import (  # noqa: E402
    DEFAULT_GRID_CELL_CM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    CamPreset,
    FollowerPreset,
    GearPreset,
    PhysicalKitProfile,
    gear_radius_for_teeth,
    grid_step_mm,
)

SCHEMA_VERSION = "automataii.fabrication.v1"
SOURCE_SSOT = "automataii.shared.physical_kit"
GENERATED_BY = "scripts/generate_fabrication_templates.py"
REPRODUCIBLE_GENERATED_AT = "reproducible"
CAM_PROFILE_SAMPLE_COUNT = 144
CAM_PROFILE_SOURCE = "automataii.domain.mechanisms.cam.profile.build_pear_cam_profile_from_params"
FABRICATION_PROFILE_COUNTS = {
    "gear_presets": 4,
    "linkage_length_cells": 4,
    "cam_presets": 4,
    "follower_presets": 4,
}
ATTACHMENT_KINDS = ("linkage", "bracket", "crank", "handle")
ATTACHMENT_KINDS_ATTR = " ".join(ATTACHMENT_KINDS)
CUT = "#ed1c24"
DRILL = "#0071bc"
SCORE = "#777777"
TEXT = "#333333"
FILL = "#ffffff"


@dataclass(frozen=True, slots=True)
class SvgTemplate:
    """In-memory SVG plus manifest metadata."""

    path: str
    title: str
    desc: str
    width_mm: float
    height_mm: float
    elements: tuple[str, ...]
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class GearGeometry:
    pitch_radius_mm: float
    root_radius_mm: float
    outer_radius_mm: float
    attachment_radii_mm: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class FabricationSpec:
    profile: PhysicalKitProfile
    pitch_mm: float
    hole_diameter_mm: float
    hole_radius_mm: float
    hole_diameter_attr: str


@dataclass(frozen=True, slots=True)
class BracketPreset:
    key: str
    label: str
    path: str
    hole_centers_mm: tuple[tuple[float, float], ...]
    outline_points_mm: tuple[tuple[float, float], ...] | None = None


BRACKET_PRESETS: tuple[BracketPreset, ...] = (
    BracketPreset(
        "2-hole-straight",
        "2-hole straight bracket",
        "brackets/bracket-2-hole-straight.svg",
        ((10.0, 10.0), (30.0, 10.0)),
    ),
    BracketPreset(
        "3-hole-straight",
        "3-hole straight bracket",
        "brackets/bracket-3-hole-straight.svg",
        ((10.0, 10.0), (30.0, 10.0), (50.0, 10.0)),
    ),
    BracketPreset(
        "l-3-hole",
        "L 3-hole bracket",
        "brackets/bracket-l-3-hole.svg",
        ((10.0, 10.0), (30.0, 10.0), (10.0, 30.0)),
        ((3.0, 3.0), (37.0, 3.0), (37.0, 17.0), (17.0, 17.0), (17.0, 37.0), (3.0, 37.0)),
    ),
    BracketPreset(
        "triangle-3-hole",
        "Triangle 3-hole bracket",
        "brackets/bracket-triangle-3-hole.svg",
        ((10.0, 10.0), (30.0, 10.0), (10.0, 30.0)),
        ((3.0, 3.0), (39.0, 3.0), (3.0, 39.0)),
    ),
)


def _fabrication_spec(
    grid_cell_cm: float | None,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> FabricationSpec:
    _validate_fabrication_profile(profile)
    hole_diameter_mm = float(profile.hole_diameter_mm)
    pitch_mm = (
        float(profile.default_pitch_mm) if grid_cell_cm is None else grid_step_mm(grid_cell_cm)
    )
    return FabricationSpec(
        profile=profile,
        pitch_mm=pitch_mm,
        hole_diameter_mm=hole_diameter_mm,
        hole_radius_mm=hole_diameter_mm / 2.0,
        hole_diameter_attr=_fmt(hole_diameter_mm),
    )


def _validate_fabrication_profile(profile: PhysicalKitProfile) -> None:
    """Fail fast when the fixed workshop-sheet layout cannot represent a profile."""
    actual_counts = {
        "gear_presets": len(profile.gear_presets),
        "linkage_length_cells": len(profile.linkage_length_cells),
        "cam_presets": len(profile.cam_presets),
        "follower_presets": len(profile.follower_presets),
    }
    mismatches = [
        f"{key}={actual_counts[key]} (expected {expected})"
        for key, expected in FABRICATION_PROFILE_COUNTS.items()
        if actual_counts[key] != expected
    ]
    if mismatches:
        raise ValueError(
            "Fabrication template sheets require exactly four gears, four linkage lengths, "
            "four cams, and four followers; "
            f"unsupported profile {profile.key!r}: {', '.join(mismatches)}"
        )


def _fmt(value: float | int) -> str:
    return f"{float(value):.3f}".rstrip("0").rstrip(".")


def _attrs(**values: object) -> str:
    parts: list[str] = []
    for key, value in values.items():
        attr_name = key.rstrip("_").replace("_", "-")
        parts.append(f'{attr_name}="{escape(str(value))}"')
    return " ".join(parts)


def _data_attrs(**values: object) -> str:
    return " ".join(
        f'data-{key.replace("_", "-")}="{escape(str(value))}"' for key, value in values.items()
    )


def _svg_document(template: SvgTemplate, spec: FabricationSpec) -> str:
    body = "\n".join(template.elements)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1"
     width="{_fmt(template.width_mm)}mm" height="{_fmt(template.height_mm)}mm"
     viewBox="0 0 {_fmt(template.width_mm)} {_fmt(template.height_mm)}"
     data-profile-key="{escape(spec.profile.key)}"
     data-grid-pitch-mm="{_fmt(spec.pitch_mm)}"
     data-hole-diameter-mm="{spec.hole_diameter_attr}">
  <title>{escape(template.title)}</title>
  <desc>{escape(template.desc)}</desc>
  <defs>
    <style>
      .cut {{ fill: none; stroke: {CUT}; stroke-width: 0.25; stroke-miterlimit: 10; }}
      .drill {{ fill: none; stroke: {DRILL}; stroke-width: 0.2; stroke-miterlimit: 10; }}
      .score {{ fill: none; stroke: {SCORE}; stroke-width: 0.15; stroke-dasharray: 2 1; }}
      .label {{ fill: {TEXT}; font-family: Arial, Helvetica, sans-serif; font-size: 4px; }}
      .tiny {{ fill: {TEXT}; font-family: Arial, Helvetica, sans-serif; font-size: 3px; }}
      .paper {{ fill: {FILL}; stroke: none; }}
    </style>
  </defs>
{body}
</svg>
'''


def _circle(
    cx: float,
    cy: float,
    radius: float,
    class_name: str,
    *,
    extra: dict[str, object] | None = None,
) -> str:
    attrs = _attrs(cx=_fmt(cx), cy=_fmt(cy), r=_fmt(radius), class_=class_name)
    if extra:
        attrs = f"{attrs} {_data_attrs(**extra)}"
    return f"  <circle {attrs}/>"


def _path(d: str, class_name: str, *, extra: dict[str, object] | None = None) -> str:
    attrs = _attrs(d=d, class_=class_name)
    if extra:
        attrs = f"{attrs} {_data_attrs(**extra)}"
    return f"  <path {attrs}/>"


def _text(
    x: float, y: float, value: str, *, class_name: str = "label", anchor: str = "middle"
) -> str:
    return (
        f"  <text {_attrs(x=_fmt(x), y=_fmt(y), class_=class_name, text_anchor=anchor)}>"
        f"{escape(value)}</text>"
    )


def _rounded_capsule_path(x1: float, y: float, x2: float, radius: float) -> str:
    return (
        f"M {_fmt(x1)} {_fmt(y - radius)} "
        f"L {_fmt(x2)} {_fmt(y - radius)} "
        f"A {_fmt(radius)} {_fmt(radius)} 0 0 1 {_fmt(x2)} {_fmt(y + radius)} "
        f"L {_fmt(x1)} {_fmt(y + radius)} "
        f"A {_fmt(radius)} {_fmt(radius)} 0 0 1 {_fmt(x1)} {_fmt(y - radius)} Z"
    )


def _vertical_capsule_path(cx: float, y1: float, y2: float, radius: float) -> str:
    return (
        f"M {_fmt(cx - radius)} {_fmt(y1)} "
        f"A {_fmt(radius)} {_fmt(radius)} 0 0 1 {_fmt(cx + radius)} {_fmt(y1)} "
        f"L {_fmt(cx + radius)} {_fmt(y2)} "
        f"A {_fmt(radius)} {_fmt(radius)} 0 0 1 {_fmt(cx - radius)} {_fmt(y2)} "
        f"Z"
    )


def _rounded_rect_path(x: float, y: float, width: float, height: float, radius: float) -> str:
    right = x + width
    bottom = y + height
    radius = min(radius, width / 2.0, height / 2.0)
    return (
        f"M {_fmt(x + radius)} {_fmt(y)} "
        f"L {_fmt(right - radius)} {_fmt(y)} "
        f"A {_fmt(radius)} {_fmt(radius)} 0 0 1 {_fmt(right)} {_fmt(y + radius)} "
        f"L {_fmt(right)} {_fmt(bottom - radius)} "
        f"A {_fmt(radius)} {_fmt(radius)} 0 0 1 {_fmt(right - radius)} {_fmt(bottom)} "
        f"L {_fmt(x + radius)} {_fmt(bottom)} "
        f"A {_fmt(radius)} {_fmt(radius)} 0 0 1 {_fmt(x)} {_fmt(bottom - radius)} "
        f"L {_fmt(x)} {_fmt(y + radius)} "
        f"A {_fmt(radius)} {_fmt(radius)} 0 0 1 {_fmt(x + radius)} {_fmt(y)} Z"
    )


def _polygon_path(points: tuple[tuple[float, float], ...]) -> str:
    first_x, first_y = points[0]
    commands = [f"M {_fmt(first_x)} {_fmt(first_y)}"]
    commands.extend(f"L {_fmt(x)} {_fmt(y)}" for x, y in points[1:])
    commands.append("Z")
    return " ".join(commands)


def _translate(element: str, dx: float, dy: float) -> str:
    return f'  <g transform="translate({_fmt(dx)} {_fmt(dy)})">\n{element}\n  </g>'


def _gear_geometry(preset: GearPreset, spec: FabricationSpec) -> GearGeometry:
    pitch_radius = gear_radius_for_teeth(preset.teeth, profile=spec.profile)
    tooth_depth = spec.profile.gear_radius_per_tooth_mm
    root_radius = max(spec.hole_radius_mm + 8.0, pitch_radius - tooth_depth * 1.25)
    outer_radius = pitch_radius + tooth_depth * 1.2
    max_attachment_radius = root_radius - spec.hole_radius_mm - 4.0
    candidate_radii = (spec.pitch_mm, spec.pitch_mm * 2.0, spec.pitch_mm * 3.0)
    attachment_radii = tuple(r for r in candidate_radii if r <= max_attachment_radius)
    if not attachment_radii:
        attachment_radii = (max(spec.hole_radius_mm + 5.0, max_attachment_radius),)
    return GearGeometry(
        pitch_radius_mm=pitch_radius,
        root_radius_mm=root_radius,
        outer_radius_mm=outer_radius,
        attachment_radii_mm=attachment_radii,
    )


def _grid_attachment_offsets(max_radius: float, pitch_mm: float) -> tuple[tuple[float, float], ...]:
    """Return board-grid offsets that fit within a circular usable radius."""
    max_cells = max(1, int(max_radius // pitch_mm))
    offsets: list[tuple[float, float]] = []
    clearance_radius = max(0.0, max_radius)
    for x_cell in range(-max_cells, max_cells + 1):
        for y_cell in range(-max_cells, max_cells + 1):
            if x_cell == 0 and y_cell == 0:
                continue
            dx = x_cell * pitch_mm
            dy = y_cell * pitch_mm
            distance = math.hypot(dx, dy)
            if distance <= clearance_radius:
                offsets.append((dx, dy))
    return tuple(sorted(offsets, key=lambda point: (math.hypot(*point), point[1], point[0])))


def _radial_attachment_offsets(radius: float, count: int = 4) -> tuple[tuple[float, float], ...]:
    """Return evenly spaced attachment offsets for parts too small for one board pitch."""
    usable_radius = max(0.0, radius)
    if usable_radius <= 0.0 or count <= 0:
        return ()
    return tuple(
        (
            usable_radius * math.cos(2.0 * math.pi * idx / count),
            usable_radius * math.sin(2.0 * math.pi * idx / count),
        )
        for idx in range(count)
    )


def _gear_attachment_offsets(
    geometry: GearGeometry,
    spec: FabricationSpec,
) -> tuple[tuple[float, float], ...]:
    """Return linkage/bracket/handle holes that remain inside the gear root profile.

    Larger gears use board-grid offsets so brackets and linkages align directly to
    the 20 mm pegboard pitch. The smallest 12T gear cannot physically fit a full
    20 mm ring while preserving 6 mm holes and material margins, so it gets a
    four-hole crank/handle ring inside the root circle instead of silently having
    no useful attachment holes.
    """
    max_attachment_radius = geometry.root_radius_mm - spec.hole_radius_mm - 4.0
    grid_offsets = _grid_attachment_offsets(max_attachment_radius, spec.pitch_mm)
    if len(grid_offsets) >= 4:
        return grid_offsets
    return _radial_attachment_offsets(max_attachment_radius, 4)


def _attachment_hole_pattern(
    attachment_offsets: tuple[tuple[float, float], ...],
    spec: FabricationSpec,
) -> str:
    if not attachment_offsets:
        return "none"

    def is_grid_value(value: float) -> bool:
        scaled = value / spec.pitch_mm
        return math.isclose(scaled, round(scaled), abs_tol=0.001)

    if all(is_grid_value(dx) and is_grid_value(dy) for dx, dy in attachment_offsets):
        return "grid"
    return "radial"


def _gear_outline_path(
    cx: float, cy: float, teeth: int, root_radius: float, outer_radius: float
) -> str:
    points: list[tuple[float, float]] = []
    for idx in range(teeth * 4):
        theta = 2.0 * math.pi * idx / (teeth * 4)
        radius = outer_radius if idx % 4 in (1, 2) else root_radius
        points.append((cx + radius * math.cos(theta), cy + radius * math.sin(theta)))
    first_x, first_y = points[0]
    commands = [f"M {_fmt(first_x)} {_fmt(first_y)}"]
    commands.extend(f"L {_fmt(x)} {_fmt(y)}" for x, y in points[1:])
    commands.append("Z")
    return " ".join(commands)


def _gear_elements(
    preset: GearPreset, spec: FabricationSpec, *, label: bool = True
) -> tuple[list[str], dict[str, object]]:
    geometry = _gear_geometry(preset, spec)
    margin = 8.0
    cx = geometry.outer_radius_mm + margin
    cy = geometry.outer_radius_mm + margin
    attachment_offsets = _gear_attachment_offsets(geometry, spec)
    attachment_pattern = _attachment_hole_pattern(attachment_offsets, spec)
    elements = [
        _path(
            _gear_outline_path(
                cx, cy, preset.teeth, geometry.root_radius_mm, geometry.outer_radius_mm
            ),
            "cut gear-outline",
            extra={
                "teeth": preset.teeth,
                "pitch_radius_mm": _fmt(geometry.pitch_radius_mm),
                "root_radius_mm": _fmt(geometry.root_radius_mm),
                "outer_radius_mm": _fmt(geometry.outer_radius_mm),
                "attachment_hole_pattern": attachment_pattern,
            },
        ),
        _circle(
            cx,
            cy,
            spec.hole_radius_mm,
            "drill axle-hole",
            extra={"hole_role": "axle", "hole_diameter_mm": spec.hole_diameter_attr},
        ),
        _circle(cx, cy, geometry.pitch_radius_mm, "score pitch-circle"),
    ]
    attachment_count = 0
    for dx, dy in attachment_offsets:
        elements.append(
            _circle(
                cx + dx,
                cy + dy,
                spec.hole_radius_mm,
                "drill linkage-hole bracket-hole crank-hole handle-hole",
                extra={
                    "hole_role": "linkage-bracket-crank-handle",
                    "attachment_kinds": ATTACHMENT_KINDS_ATTR,
                    "hole_diameter_mm": spec.hole_diameter_attr,
                    "hole_index": attachment_count,
                    "hole_x_offset_mm": _fmt(dx),
                    "hole_y_offset_mm": _fmt(dy),
                    "hole_radius_mm": _fmt(math.hypot(dx, dy)),
                },
            )
        )
        attachment_count += 1
    if label:
        elements.append(
            _text(cx, cy + geometry.outer_radius_mm + 6.0, f"{preset.label} / {preset.teeth}T")
        )
    metadata: dict[str, object] = {
        "key": preset.key,
        "teeth": preset.teeth,
        "label": preset.label,
        "pitch_radius_mm": round(geometry.pitch_radius_mm, 3),
        "outer_radius_mm": round(geometry.outer_radius_mm, 3),
        "root_radius_mm": round(geometry.root_radius_mm, 3),
        "hole_diameter_mm": spec.hole_diameter_mm,
        "attachment_hole_count": attachment_count,
        "attachment_hole_pattern": attachment_pattern,
        "attachment_kinds": list(ATTACHMENT_KINDS),
        "attachment_radii_mm": sorted(
            {round(math.hypot(dx, dy), 3) for dx, dy in attachment_offsets}
        ),
        "attachment_hole_centers_mm": [
            [round(dx, 3), round(dy, 3)] for dx, dy in attachment_offsets
        ],
    }
    return elements, metadata


def _gear_template(preset: GearPreset, spec: FabricationSpec) -> SvgTemplate:
    elements, metadata = _gear_elements(preset, spec)
    geometry = _gear_geometry(preset, spec)
    width = geometry.outer_radius_mm * 2.0 + 16.0
    height = width + 10.0
    path = f"gears/gear-{preset.teeth}t.svg"
    metadata["path"] = path
    return SvgTemplate(
        path=path,
        title=f"Automataii fabrication gear {preset.teeth} teeth",
        desc=(
            f"{preset.label} gear with {_fmt(spec.hole_diameter_mm)} mm axle and "
            "linkage/bracket/crank/handle holes."
        ),
        width_mm=width,
        height_mm=height,
        elements=tuple(elements),
        metadata=metadata,
    )


def _linkage_elements(
    cells: int, spec: FabricationSpec, *, label: bool = True
) -> tuple[list[str], dict[str, object]]:
    pitch_mm = spec.pitch_mm
    length = cells * pitch_mm
    width = 14.0
    radius = width / 2.0
    margin = 7.0
    x1 = margin + radius
    x2 = x1 + length
    y = margin + radius
    elements = [
        _path(
            _rounded_capsule_path(x1, y, x2, radius),
            "cut linkage-outline",
            extra={
                "cells": cells,
                "length_mm": _fmt(length),
                "pitch_mm": _fmt(pitch_mm),
                "hole_count": cells + 1,
            },
        )
    ]
    for idx in range(cells + 1):
        elements.append(
            _circle(
                x1 + idx * pitch_mm,
                y,
                spec.hole_radius_mm,
                "drill linkage-hole bracket-hole",
                extra={
                    "hole_role": "linkage-bracket",
                    "hole_diameter_mm": spec.hole_diameter_attr,
                    "hole_index": idx,
                },
            )
        )
    if label:
        elements.append(_text((x1 + x2) / 2.0, y + radius + 6.0, f"{cells}-cell linkage"))
    metadata: dict[str, object] = {
        "cells": cells,
        "label": f"{cells}-cell linkage",
        "length_mm": round(length, 3),
        "pitch_mm": round(pitch_mm, 3),
        "hole_diameter_mm": spec.hole_diameter_mm,
        "hole_count": cells + 1,
    }
    return elements, metadata


def _linkage_template(cells: int, spec: FabricationSpec) -> SvgTemplate:
    pitch_mm = spec.pitch_mm
    elements, metadata = _linkage_elements(cells, spec)
    width = cells * pitch_mm + 28.0
    height = 34.0
    path = f"linkages/linkage-{cells}-cell.svg"
    metadata["path"] = path
    return SvgTemplate(
        path=path,
        title=f"Automataii fabrication linkage {cells} cells",
        desc=(
            f"{cells}-cell linkage bar with {_fmt(spec.hole_diameter_mm)} mm holes at "
            f"{pitch_mm:.1f} mm board-pitch spacing."
        ),
        width_mm=width,
        height_mm=height,
        elements=tuple(elements),
        metadata=metadata,
    )


def _follower_outline_path(
    preset: FollowerPreset,
    cx: float,
    top_y: float,
    body_width: float,
    body_height: float,
    foot_width: float,
    foot_height: float,
) -> str:
    body_radius = body_width / 2.0
    if preset.contact_style == "flat_shoe":
        body_left = cx - body_width / 2.0
        body_right = cx + body_width / 2.0
        foot_left = cx - foot_width / 2.0
        foot_right = cx + foot_width / 2.0
        foot_top = top_y + body_height - foot_height
        bottom = top_y + body_height
        return _polygon_path(
            (
                (body_left, top_y + body_radius),
                (cx, top_y),
                (body_right, top_y + body_radius),
                (body_right, foot_top),
                (foot_right, foot_top),
                (foot_right, bottom),
                (foot_left, bottom),
                (foot_left, foot_top),
                (body_left, foot_top),
            )
        )
    return _vertical_capsule_path(
        cx, top_y + body_radius, top_y + body_height - body_radius, body_radius
    )


def _follower_guide_slot_centers(
    top_y: float,
    body_height: float,
    travel_mm: float,
    hole_diameter_mm: float,
) -> tuple[float, float]:
    half_total_slot = (travel_mm + hole_diameter_mm) / 2.0
    first = top_y + body_height * 0.47
    second = top_y + body_height * 0.78
    minimum_gap = half_total_slot * 2.0 + 8.0
    if second - first < minimum_gap:
        midpoint = (first + second) / 2.0
        first = midpoint - minimum_gap / 2.0
        second = midpoint + minimum_gap / 2.0
    return first, second


def _slot_path(cx: float, cy: float, travel_mm: float, radius: float) -> str:
    return _vertical_capsule_path(cx, cy - travel_mm / 2.0, cy + travel_mm / 2.0, radius)


def _follower_elements(
    preset: FollowerPreset,
    spec: FabricationSpec,
    *,
    label: bool = True,
) -> tuple[list[str], dict[str, object], float, float]:
    pitch_mm = spec.pitch_mm
    scale = pitch_mm / DEFAULT_PHYSICAL_KIT_PROFILE.default_pitch_mm
    body_width = 34.0 * scale
    foot_width = max(body_width, preset.foot_width_cells * pitch_mm)
    foot_height = 18.0 * scale
    body_height = preset.body_cells * pitch_mm + pitch_mm
    travel_mm = preset.guide_slot_travel_cells * pitch_mm
    margin = 8.0 * scale
    label_pad = 12.0 if label else 0.0
    width = foot_width + margin * 2.0
    height = body_height + margin * 2.0 + label_pad
    cx = width / 2.0
    top_y = margin
    output_y_values = tuple(top_y + pitch_mm * (idx + 1) for idx in range(preset.output_hole_count))
    guide_y_values = _follower_guide_slot_centers(
        top_y,
        body_height,
        travel_mm,
        spec.hole_diameter_mm,
    )
    contact_y = top_y + body_height
    contact_kind = "flat" if preset.contact_style == "flat_shoe" else "rounded"
    elements = [
        _path(
            _follower_outline_path(
                preset,
                cx,
                top_y,
                body_width,
                body_height,
                foot_width,
                foot_height,
            ),
            "cut follower-outline",
            extra={
                "follower_key": preset.key,
                "contact_style": preset.contact_style,
                "pitch_mm": _fmt(pitch_mm),
                "guide_slot_travel_mm": _fmt(travel_mm),
            },
        )
    ]
    for idx, y_value in enumerate(output_y_values):
        elements.append(
            _circle(
                cx,
                y_value,
                spec.hole_radius_mm,
                "drill linkage-hole follower-output-hole",
                extra={
                    "hole_role": "linkage-output",
                    "hole_diameter_mm": spec.hole_diameter_attr,
                    "hole_index": idx,
                    "hole_y_mm": _fmt(y_value - top_y),
                },
            )
        )
    for idx, y_value in enumerate(guide_y_values):
        elements.append(
            _path(
                _slot_path(cx, y_value, travel_mm, spec.hole_radius_mm),
                "cut guide-slot follower-guide-slot",
                extra={
                    "slot_role": "guide",
                    "hole_role": "guide-slot",
                    "slot_index": idx,
                    "slot_width_mm": spec.hole_diameter_attr,
                    "slot_travel_mm": _fmt(travel_mm),
                    "slot_center_y_mm": _fmt(y_value - top_y),
                },
            )
        )
    roller_axle_centers: list[list[float]] = []
    if preset.roller_axle:
        roller_y = contact_y - max(12.0 * scale, spec.hole_radius_mm + 7.0)
        elements.append(
            _circle(
                cx,
                roller_y,
                spec.hole_radius_mm,
                "drill roller-axle-hole follower-contact-hole",
                extra={
                    "hole_role": "roller-axle",
                    "hole_diameter_mm": spec.hole_diameter_attr,
                    "contact_style": preset.contact_style,
                },
            )
        )
        roller_axle_centers.append([round(0.0, 3), round(roller_y - top_y, 3)])
    if label:
        elements.append(_text(cx, height - 4.0, preset.label))
    metadata: dict[str, object] = {
        "key": preset.key,
        "label": preset.label,
        "contact_style": preset.contact_style,
        "contact_kind": contact_kind,
        "pitch_mm": round(pitch_mm, 3),
        "hole_diameter_mm": spec.hole_diameter_mm,
        "guide_slot_count": len(guide_y_values),
        "guide_slot_width_mm": spec.hole_diameter_mm,
        "guide_slot_travel_mm": round(travel_mm, 3),
        "guide_slot_centers_mm": [[0.0, round(y - top_y, 3)] for y in guide_y_values],
        "output_hole_count": len(output_y_values),
        "output_hole_centers_mm": [[0.0, round(y - top_y, 3)] for y in output_y_values],
        "roller_axle": preset.roller_axle,
        "roller_axle_hole_centers_mm": roller_axle_centers,
        "body_width_mm": round(body_width, 3),
        "body_height_mm": round(body_height, 3),
        "foot_width_mm": round(foot_width, 3),
    }
    return elements, metadata, width, height


def _follower_template(preset: FollowerPreset, spec: FabricationSpec) -> SvgTemplate:
    elements, metadata, width, height = _follower_elements(preset, spec)
    path = f"followers/follower-{preset.key}.svg"
    metadata["path"] = path
    return SvgTemplate(
        path=path,
        title=f"Automataii fabrication follower {preset.key}",
        desc=(
            f"{preset.label} with {_fmt(spec.hole_diameter_mm)} mm output/guide geometry. "
            "Guide slots slide on fixed pegboard pins or bracket hardware."
        ),
        width_mm=width,
        height_mm=height,
        elements=tuple(elements),
        metadata=metadata,
    )


def _bracket_elements(
    preset: BracketPreset, spec: FabricationSpec, *, label: bool = True
) -> tuple[list[str], dict[str, object], float, float]:
    pitch_mm = spec.pitch_mm
    scale = pitch_mm / DEFAULT_PHYSICAL_KIT_PROFILE.default_pitch_mm
    centers = tuple((x * scale, y * scale) for x, y in preset.hole_centers_mm)
    outline_bounds: tuple[tuple[float, float], ...]
    if preset.outline_points_mm is None:
        min_x = min(x for x, _ in centers)
        max_x = max(x for x, _ in centers)
        y = centers[0][1]
        radius = 7.0 * scale
        outline = _rounded_capsule_path(min_x, y, max_x, radius)
        outline_bounds = ((min_x - radius, y - radius), (max_x + radius, y + radius))
    else:
        scaled_outline_points = tuple((x * scale, y * scale) for x, y in preset.outline_points_mm)
        outline = _polygon_path(scaled_outline_points)
        outline_bounds = scaled_outline_points
    elements = [
        _path(
            outline,
            "cut bracket-outline",
            extra={
                "bracket_key": preset.key,
                "pitch_mm": _fmt(pitch_mm),
                "hole_count": len(centers),
            },
        )
    ]
    for idx, (cx, cy) in enumerate(centers):
        elements.append(
            _circle(
                cx,
                cy,
                spec.hole_radius_mm,
                "drill bracket-hole linkage-hole",
                extra={
                    "hole_role": "bracket",
                    "hole_diameter_mm": spec.hole_diameter_attr,
                    "hole_index": idx,
                    "hole_x_mm": _fmt(cx),
                    "hole_y_mm": _fmt(cy),
                },
            )
        )
    max_x = max(
        max(x + spec.hole_radius_mm for x, _ in centers),
        max(x for x, _ in outline_bounds),
    )
    max_y = max(
        max(y + spec.hole_radius_mm for _, y in centers),
        max(y for _, y in outline_bounds),
    )
    width = max(max_x + 4.0, 40.0)
    height = max(max_y + 4.0, 20.0)
    if label:
        elements.append(_text(width / 2.0, height + 6.0, preset.label))
        height += 10.0
    metadata: dict[str, object] = {
        "key": preset.key,
        "label": preset.label,
        "path": preset.path,
        "pitch_mm": round(pitch_mm, 3),
        "hole_diameter_mm": spec.hole_diameter_mm,
        "hole_count": len(centers),
        "hole_centers_mm": [[round(x, 3), round(y, 3)] for x, y in centers],
    }
    return elements, metadata, width, height


def _bracket_template(preset: BracketPreset, spec: FabricationSpec) -> SvgTemplate:
    elements, metadata, width, height = _bracket_elements(preset, spec)
    return SvgTemplate(
        path=preset.path,
        title=f"Automataii fabrication bracket {preset.key}",
        desc=(
            f"{preset.label} with {_fmt(spec.hole_diameter_mm)} mm holes on "
            f"{spec.pitch_mm:.1f} mm centers."
        ),
        width_mm=width,
        height_mm=height,
        elements=tuple(elements),
        metadata=metadata,
    )


def _cam_params_for_preset(preset: CamPreset, spec: FabricationSpec) -> dict[str, float]:
    return dict(preset.params_mm(spec.pitch_mm / 10.0))


def _cam_local_profile(preset: CamPreset, spec: FabricationSpec) -> np.ndarray:
    params = _cam_params_for_preset(preset, spec)
    return build_pear_cam_profile_from_params(params, num_samples=CAM_PROFILE_SAMPLE_COUNT)


def _max_profile_radius(profile: np.ndarray) -> float:
    rows = np.asarray(profile, dtype=float)[:, :2]
    return max(float(math.hypot(x, y)) for x, y in rows)


def _min_profile_radius(profile: np.ndarray) -> float:
    rows = np.asarray(profile, dtype=float)[:, :2]
    return min(float(math.hypot(x, y)) for x, y in rows)


def _profile_radius_at(profile: np.ndarray, theta: float) -> float:
    """Return nearest sampled local profile radius at ``theta`` radians."""
    best_radius = 0.0
    best_delta = math.inf
    rows = np.asarray(profile, dtype=float)[:, :2]
    for x, y in rows:
        angle = math.atan2(float(y), float(x))
        delta = abs(math.atan2(math.sin(angle - theta), math.cos(angle - theta)))
        if delta < best_delta:
            best_delta = delta
            best_radius = float(math.hypot(x, y))
    return best_radius


def _drawing_offset_to_local(dx: float, dy: float) -> tuple[float, float]:
    """Invert ``cam_profile_to_drawing_points`` for offset-only fit checks."""
    return -dy, dx


def _cam_attachment_offsets(
    spec: FabricationSpec,
    profile: np.ndarray,
    max_radius: float,
) -> tuple[tuple[float, float], ...]:
    """Return linkage/bracket/handle holes that fit inside the shared cam profile."""
    candidates = _grid_attachment_offsets(max_radius - spec.hole_radius_mm - 4.0, spec.pitch_mm)

    def fits(offset: tuple[float, float], margin: float) -> bool:
        dx, dy = offset
        local_x, local_y = _drawing_offset_to_local(dx, dy)
        theta = math.atan2(local_y, local_x)
        available = max(spec.hole_radius_mm + 1.0, _profile_radius_at(profile, theta))
        return math.hypot(local_x, local_y) + spec.hole_radius_mm + margin <= available

    offsets = tuple(offset for offset in candidates if fits(offset, 4.0))
    if len(offsets) >= 4:
        return offsets
    relaxed = tuple(offset for offset in candidates if fits(offset, 1.0))
    if len(relaxed) >= 4:
        return relaxed
    fallback_radius = _min_profile_radius(profile) - spec.hole_radius_mm - 4.0
    return tuple(
        offset for offset in _radial_attachment_offsets(fallback_radius, 4) if fits(offset, 1.0)
    )


def _cam_outline_path(points: list[tuple[float, float]]) -> str:
    first_x, first_y = points[0]
    commands = [f"M {_fmt(first_x)} {_fmt(first_y)}"]
    commands.extend(f"L {_fmt(x)} {_fmt(y)}" for x, y in points[1:])
    commands.append("Z")
    return " ".join(commands)


def _cam_elements(
    preset: CamPreset, spec: FabricationSpec, *, label: bool = True
) -> tuple[list[str], dict[str, object], float, float]:
    params = _cam_params_for_preset(preset, spec)
    base_radius = float(params["base_radius"])
    eccentricity = float(params["eccentricity"])
    profile = _cam_local_profile(preset, spec)
    actual_max_radius = _max_profile_radius(profile)
    margin = 8.0
    cx = actual_max_radius + margin
    cy = actual_max_radius + margin
    drawing_points = cam_profile_to_drawing_points(profile, cx, cy)
    outline = _cam_outline_path(drawing_points)
    elements = [
        _path(
            outline,
            "cut cam-outline",
            extra={
                "cam_key": preset.key,
                "base_radius_mm": _fmt(base_radius),
                "eccentricity_mm": _fmt(eccentricity),
                "cam_lobes": int(float(params["cam_lobes"])),
                "profile_harmonic": _fmt(params["profile_harmonic"]),
                "rise_deg": _fmt(params["rise_deg"]),
                "high_dwell_deg": _fmt(params["high_dwell_deg"]),
                "return_deg": _fmt(params["return_deg"]),
                "physical_cam_preset": preset.key,
                "profile_source": CAM_PROFILE_SOURCE,
                "profile_sample_count": CAM_PROFILE_SAMPLE_COUNT,
            },
        ),
        _circle(
            cx,
            cy,
            spec.hole_radius_mm,
            "drill axle-hole",
            extra={"hole_role": "axle", "hole_diameter_mm": spec.hole_diameter_attr},
        ),
        f"  <line {_attrs(x1=_fmt(cx), y1=_fmt(cy), x2=_fmt(cx + base_radius), y2=_fmt(cy), class_='score cam-base-radius')}/>",
        _circle(cx, cy, base_radius, "score cam-base-circle"),
    ]
    attachment_offsets = _cam_attachment_offsets(spec, profile, actual_max_radius)
    for hole_index, (dx, dy) in enumerate(attachment_offsets):
        elements.append(
            _circle(
                cx + dx,
                cy + dy,
                spec.hole_radius_mm,
                "drill linkage-hole bracket-hole crank-hole handle-hole",
                extra={
                    "hole_role": "linkage-bracket-crank-handle",
                    "attachment_kinds": ATTACHMENT_KINDS_ATTR,
                    "hole_diameter_mm": spec.hole_diameter_attr,
                    "hole_index": hole_index,
                    "hole_x_offset_mm": _fmt(dx),
                    "hole_y_offset_mm": _fmt(dy),
                },
            )
        )
    label_pad = 0.0
    if label:
        label_y = cy + actual_max_radius + 7.0
        elements.append(_text(cx, label_y, preset.label))
        label_pad = 12.0
    metadata: dict[str, object] = {
        "key": preset.key,
        "label": preset.label,
        "base_radius_mm": round(base_radius, 3),
        "eccentricity_mm": round(eccentricity, 3),
        "cam_lobes": int(float(params["cam_lobes"])),
        "profile_harmonic": round(float(params["profile_harmonic"]), 3),
        "rise_deg": round(float(params["rise_deg"]), 3),
        "high_dwell_deg": round(float(params["high_dwell_deg"]), 3),
        "return_deg": round(float(params["return_deg"]), 3),
        "physical_cam_preset": preset.key,
        "profile_source": CAM_PROFILE_SOURCE,
        "profile_sample_count": CAM_PROFILE_SAMPLE_COUNT,
        "hole_diameter_mm": spec.hole_diameter_mm,
        "attachment_hole_count": len(attachment_offsets),
        "attachment_kinds": list(ATTACHMENT_KINDS),
        "attachment_hole_centers_mm": [
            [round(dx, 3), round(dy, 3)] for dx, dy in attachment_offsets
        ],
    }
    size = actual_max_radius * 2.0 + margin * 2.0
    height = size + label_pad
    return elements, metadata, size, height


def _cam_template(preset: CamPreset, spec: FabricationSpec) -> SvgTemplate:
    elements, metadata, width, height = _cam_elements(preset, spec)
    path = f"cams/cam-{preset.key}.svg"
    metadata["path"] = path
    return SvgTemplate(
        path=path,
        title=f"Automataii fabrication cam {preset.key}",
        desc=(
            f"{preset.label} cam profile with {_fmt(spec.hole_diameter_mm)} mm axle and "
            "linkage/bracket/crank/handle holes."
        ),
        width_mm=width,
        height_mm=height,
        elements=tuple(elements),
        metadata=metadata,
    )


def _sheet_template(
    key: str,
    label: str,
    contains: list[str],
    elements: list[str],
    spec: FabricationSpec,
    *,
    width_mm: float = 420.0,
    height_mm: float = 320.0,
) -> SvgTemplate:
    title = f"Automataii fabrication sheet {key}: {label}"
    desc = (
        f"Workshop sheet containing: {', '.join(contains)}. "
        f"Nominal holes are {_fmt(spec.hole_diameter_mm)} mm."
    )
    metadata: dict[str, object] = {
        "key": key,
        "label": label,
        "path": f"sheets/{key}.svg",
        "contains": contains,
        "width_mm": width_mm,
        "height_mm": height_mm,
    }
    return SvgTemplate(
        path=f"sheets/{key}.svg",
        title=title,
        desc=desc,
        width_mm=width_mm,
        height_mm=height_mm,
        elements=tuple(elements),
        metadata=metadata,
    )


def _sheet_label(title: str, subtitle: str) -> list[str]:
    return [
        _text(12.0, 12.0, title, class_name="label", anchor="start"),
        _text(12.0, 18.0, subtitle, class_name="tiny", anchor="start"),
    ]


def _build_sheets(spec: FabricationSpec) -> list[SvgTemplate]:
    pitch_mm = spec.pitch_mm
    sheets: list[SvgTemplate] = []

    gear_sheet = _sheet_label(
        "01 Gear set",
        "Gears include 6 mm axle + linkage/bracket/crank/handle holes",
    )
    gear_positions = [(12.0, 28.0), (118.0, 28.0), (12.0, 150.0), (144.0, 150.0)]
    for gear_preset, (x, y) in zip(spec.profile.gear_presets, gear_positions, strict=True):
        elements, _ = _gear_elements(gear_preset, spec, label=False)
        gear_sheet.extend(_translate(element, x, y) for element in elements)
    sheets.append(_sheet_template("01-gear-set", "Gear set", ["gears"], gear_sheet, spec))

    linkage_sheet = _sheet_label("02 Linkage set", "2/4/6/8-cell board-compatible linkage bars")
    for idx, cells in enumerate(spec.profile.linkage_length_cells):
        elements, _ = _linkage_elements(cells, spec, label=False)
        linkage_sheet.extend(_translate(element, 10.0, 30.0 + idx * 38.0) for element in elements)
    sheets.append(
        _sheet_template("02-linkage-set", "Linkage set", ["linkages"], linkage_sheet, spec)
    )

    cam_sheet = _sheet_label("03 Cam set", "Circle, eccentric, oval, and pear cams")
    cam_positions = [(12.0, 24.0), (112.0, 24.0), (12.0, 116.0), (112.0, 116.0)]
    for cam_preset, (x, y) in zip(spec.profile.cam_presets, cam_positions, strict=True):
        elements, _, _, _ = _cam_elements(cam_preset, spec, label=False)
        cam_sheet.extend(_translate(element, x, y) for element in elements)
    sheets.append(_sheet_template("03-cam-set", "Cam set", ["cams"], cam_sheet, spec))

    prototype_a = _sheet_label(
        "04 Prototype set A", "Starter mix: two gears, two linkages, two cams, brackets"
    )
    for gear_preset, (x, y) in zip(
        spec.profile.gear_presets[:2], [(10.0, 28.0), (112.0, 28.0)], strict=True
    ):
        elements, _ = _gear_elements(gear_preset, spec, label=False)
        prototype_a.extend(_translate(element, x, y) for element in elements)
    for cells, (x, y) in zip((2, 4), [(10.0, 128.0), (10.0, 162.0)], strict=True):
        elements, _ = _linkage_elements(cells, spec, label=False)
        prototype_a.extend(_translate(element, x, y) for element in elements)
    for cam_preset, (x, y) in zip(
        spec.profile.cam_presets[:2], [(190.0, 28.0), (190.0, 112.0)], strict=True
    ):
        elements, _, _, _ = _cam_elements(cam_preset, spec, label=False)
        prototype_a.extend(_translate(element, x, y) for element in elements)
    for bracket_preset, (x, y) in zip(
        BRACKET_PRESETS[:2], [(10.0, 204.0), (80.0, 204.0)], strict=True
    ):
        elements, _, _, _ = _bracket_elements(bracket_preset, spec, label=False)
        prototype_a.extend(_translate(element, x, y) for element in elements)
    sheets.append(
        _sheet_template(
            "04-prototype-set-a",
            "Prototype set A",
            ["gears", "linkages", "cams", "brackets"],
            prototype_a,
            spec,
        )
    )

    prototype_b = _sheet_label(
        "05 Prototype set B", "Extended mix: larger gears, longer linkages, profile cams, brackets"
    )
    for gear_preset, (x, y) in zip(
        spec.profile.gear_presets[2:], [(10.0, 24.0), (132.0, 24.0)], strict=True
    ):
        elements, _ = _gear_elements(gear_preset, spec, label=False)
        prototype_b.extend(_translate(element, x, y) for element in elements)
    for cells, (x, y) in zip((6, 8), [(10.0, 150.0), (10.0, 178.0)], strict=True):
        elements, _ = _linkage_elements(cells, spec, label=False)
        prototype_b.extend(_translate(element, x, y) for element in elements)
    for cam_preset, (x, y) in zip(
        spec.profile.cam_presets[2:], [(218.0, 112.0), (218.0, 24.0)], strict=True
    ):
        elements, _, _, _ = _cam_elements(cam_preset, spec, label=False)
        prototype_b.extend(_translate(element, x, y) for element in elements)
    for bracket_preset, (x, y) in zip(
        BRACKET_PRESETS[2:], [(10.0, 210.0), (70.0, 210.0)], strict=True
    ):
        elements, _, _, _ = _bracket_elements(bracket_preset, spec, label=False)
        prototype_b.extend(_translate(element, x, y) for element in elements)
    sheets.append(
        _sheet_template(
            "05-prototype-set-b",
            "Prototype set B",
            ["gears", "linkages", "cams", "brackets"],
            prototype_b,
            spec,
        )
    )

    bracket_sheet = _sheet_label(
        "06 Bracket set",
        f"Bracket plates match the {pitch_mm:.0f} mm pegboard pitch and 6 mm holes",
    )
    bracket_positions = [(12.0, 30.0), (12.0, 62.0), (12.0, 96.0), (72.0, 96.0)]
    for bracket_preset, (x, y) in zip(BRACKET_PRESETS, bracket_positions, strict=True):
        elements, _, _, _ = _bracket_elements(bracket_preset, spec, label=False)
        bracket_sheet.extend(_translate(element, x, y) for element in elements)
    sheets.append(
        _sheet_template("06-bracket-set", "Bracket set", ["brackets"], bracket_sheet, spec)
    )

    follower_sheet = _sheet_label(
        "07 Follower set",
        "Slotted cam followers: guide on fixed 6 mm pins, output holes move with the cam",
    )
    follower_positions = [(10.0, 30.0), (110.0, 30.0), (210.0, 30.0), (310.0, 30.0)]
    for follower_preset, (x, y) in zip(
        spec.profile.follower_presets,
        follower_positions,
        strict=True,
    ):
        elements, _, _, _ = _follower_elements(follower_preset, spec, label=False)
        follower_sheet.extend(_translate(element, x, y) for element in elements)
    sheets.append(
        _sheet_template("07-follower-set", "Follower set", ["followers"], follower_sheet, spec)
    )

    return sheets


def _readme_text(spec: FabricationSpec, manifest: dict[str, object]) -> str:
    pitch_mm = spec.pitch_mm
    managed_count = (
        len(manifest["managed_files"]) if isinstance(manifest["managed_files"], list) else 0
    )
    gear_teeth = ", ".join(str(preset.teeth) for preset in spec.profile.gear_presets)
    linkage_lengths = ", ".join(str(cells) for cells in spec.profile.linkage_length_cells)
    cam_names = ", ".join(preset.key for preset in spec.profile.cam_presets)

    return f"""# Automataii fabrication templates

This directory contains fabrication-ready SVG masters for the physical Automataii pegboard kit.

## Two supported workflows

1. **Pre-fabricated prototyping kit** — cut/print the seven workshop sheets in `sheets/`, keep the parts as a classroom/workshop set, and mount them on the physical pegboard with the existing bracket hardware.
2. **Self-fabrication** — use the individual SVGs in `gears/`, `linkages/`, `cams/`, `followers/`, and `brackets/` to make replacement or custom parts with a laser cutter, CNC router, 3D-print workflow, scroll saw, table saw plus drill jig, or similar shop process.

## Physical assumptions

- Default committed pitch: `{pitch_mm:.1f} mm` (`{pitch_mm / 10.0:.2f} cm`) board spacing.
- Nominal axle/linkage/bracket hole diameter: `{spec.hole_diameter_mm:.1f} mm`.
- Gear presets: {gear_teeth} teeth.
- Linkage lengths: {linkage_lengths} board cells.
- Cam presets: {cam_names}.
- Follower presets: round-nose, roller-pin, flat-shoe, linkage-output.
- Bracket presets: 2-hole straight, 3-hole straight, L 3-hole, triangle 3-hole.
- Default profile key: `{spec.profile.key}`. Legacy `ms4n` / `motionsmith-ms4n`
  identifiers are compatibility labels; the committed fabrication contract is
  this 20.0 mm / 6.0 mm board unless a custom output directory is generated.
- Red paths are cuts, blue circles are drill/cut holes, gray lines are score/reference geometry.
- Gear attachment-hole pattern: larger gears use board-grid attachment holes where they fit.
  The compact 12T gear intentionally uses a radial four-hole crank/linkage/handle ring because
  a full 20 mm grid ring would not preserve enough material around 6 mm holes.
- Follower guide geometry: followers use 6 mm-wide vertical slots, not fixed round board holes,
  so fixed board pins/brackets can constrain the part while still allowing cam lift travel.

## Tolerance note

These files are nominal geometry, not material-specific kerf compensation. Before a workshop run, cut a small test coupon and adjust hole scaling/kerf for the chosen material, fasteners, printer, bit, or laser. The gears are educational/prototyping gears for automata experiments, not certified power-transmission gears.

## Relationship to `kit/`

`kit/` and `fabrication/` are intentionally separate physical-asset packages:

- `kit/` contains the existing educational/module-oriented MS4N activity sheets, prompt cards, checks, and broad classroom materials.
- `fabrication/` is the nominal-millimetre manufacturing package for the constrained physical parts requested here: gears, linkage bars, cams, followers, brackets, and workshop cut sheets.
- Shared physical assumptions should come from `automataii.shared.physical_kit`; do not hand-edit generated `fabrication/` SVGs without updating the generator and sync test.

## Contents

- `manifest.json` — machine-readable inventory and dimensions.
- `gears/` — one SVG per gear preset; each gear includes a 6 mm axle hole and 6 mm linkage/bracket/crank/handle attachment holes.
- `linkages/` — one SVG per linkage length; holes are spaced on the board pitch.
- `cams/` — one SVG per cam preset; each cam includes a 6 mm axle hole and 6 mm linkage/bracket/crank/handle attachment holes.
- `followers/` — slotted cam follower parts with 6 mm guide slots and 6 mm linkage/output holes.
- `brackets/` — bracket plates for the pegboard/bracket assembly style shown in the reference image.
- `sheets/` — seven workshop sheets for pre-fabricated sets.

Managed files in this generated package: {managed_count}.

## Regeneration

```bash
uv run python scripts/generate_fabrication_templates.py --output fabrication
```

For a custom 2.5 cm board pitch, generate to a separate directory instead of overwriting the committed package:

```bash
uv run python scripts/generate_fabrication_templates.py --output /tmp/automataii-fabrication-2_5cm --grid-cell-cm 2.5
```
"""


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _existing_managed_files(output_path: Path) -> set[str]:
    manifest_path = output_path / "manifest.json"
    if not manifest_path.exists():
        return set()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    managed_files = manifest.get("managed_files")
    if not isinstance(managed_files, list):
        return set()
    return {str(path) for path in managed_files}


def _managed_file_target(output_path: Path, rel_path: str) -> Path | None:
    relative = Path(rel_path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        return None
    try:
        output_root = output_path.resolve()
        target = (output_path / relative).resolve()
        target.relative_to(output_root)
    except (OSError, ValueError):
        return None
    return target


def _remove_stale_managed_files(
    output_path: Path,
    previous_managed_files: set[str],
    current_managed_files: set[str],
) -> None:
    for rel_path in sorted(previous_managed_files - current_managed_files):
        target = _managed_file_target(output_path, rel_path)
        if target is None:
            continue
        if target.is_file() or target.is_symlink():
            target.unlink()


def _round_float(value: float) -> float:
    return round(value, 3)


def write_fabrication_templates(
    output_dir: str | Path,
    grid_cell_cm: float | None = None,
    profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
) -> dict[str, object]:
    """Write fabrication SVGs and return the manifest dictionary."""

    output_path = Path(output_dir)
    spec = _fabrication_spec(grid_cell_cm, profile)

    gear_templates = [_gear_template(preset, spec) for preset in profile.gear_presets]
    linkage_templates = [_linkage_template(cells, spec) for cells in profile.linkage_length_cells]
    cam_templates = [_cam_template(preset, spec) for preset in profile.cam_presets]
    follower_templates = [_follower_template(preset, spec) for preset in profile.follower_presets]
    bracket_templates = [_bracket_template(preset, spec) for preset in BRACKET_PRESETS]
    sheet_templates = _build_sheets(spec)

    all_svg_templates = [
        *gear_templates,
        *linkage_templates,
        *cam_templates,
        *follower_templates,
        *bracket_templates,
        *sheet_templates,
    ]
    managed_files = sorted(
        [template.path for template in all_svg_templates] + ["README.md", "manifest.json"]
    )
    previous_managed_files = _existing_managed_files(output_path)

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "profile_key": profile.key,
        "grid_pitch_mm": _round_float(spec.pitch_mm),
        "grid_cell_cm": _round_float(spec.pitch_mm / 10.0),
        "hole_diameter_mm": spec.hole_diameter_mm,
        "generated_by": GENERATED_BY,
        "generated_at": REPRODUCIBLE_GENERATED_AT,
        "source_ssot": SOURCE_SSOT,
        "parts": {
            "gears": [template.metadata for template in gear_templates],
            "linkages": [template.metadata for template in linkage_templates],
            "cams": [template.metadata for template in cam_templates],
            "followers": [template.metadata for template in follower_templates],
            "brackets": [template.metadata for template in bracket_templates],
        },
        "sheets": [template.metadata for template in sheet_templates],
        "managed_files": managed_files,
    }

    _remove_stale_managed_files(output_path, previous_managed_files, set(managed_files))
    for template in all_svg_templates:
        _write_text(
            output_path / template.path,
            _svg_document(template, spec),
        )
    _write_text(
        output_path / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    _write_text(output_path / "README.md", _readme_text(spec, manifest))
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "fabrication",
        help="Output directory for generated fabrication files (default: fabrication/).",
    )
    parser.add_argument(
        "--grid-cell-cm",
        type=float,
        default=DEFAULT_GRID_CELL_CM,
        help="Board pitch in centimetres for generated geometry (default: 2.0).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manifest = write_fabrication_templates(args.output, grid_cell_cm=args.grid_cell_cm)
    files = manifest.get("managed_files", [])
    count = len(files) if isinstance(files, list) else 0
    print(f"Generated {count} fabrication files in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
