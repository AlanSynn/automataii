from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from scripts.generate_fabrication_templates import write_fabrication_templates

from automataii.shared.physical_kit import (
    CAM_PRESETS,
    DEFAULT_GRID_CELL_CM,
    DEFAULT_HOLE_DIAMETER_MM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    GEAR_PRESETS,
    LINKAGE_LENGTH_CELLS,
    grid_step_mm,
)

SVG_NS = "{http://www.w3.org/2000/svg}"
REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "profile_key",
    "grid_pitch_mm",
    "grid_cell_cm",
    "hole_diameter_mm",
    "generated_by",
    "generated_at",
    "source_ssot",
    "parts",
    "sheets",
    "managed_files",
}
EXPECTED_BRACKETS = {
    "brackets/bracket-2-hole-straight.svg": [[10.0, 10.0], [30.0, 10.0]],
    "brackets/bracket-3-hole-straight.svg": [[10.0, 10.0], [30.0, 10.0], [50.0, 10.0]],
    "brackets/bracket-l-3-hole.svg": [[10.0, 10.0], [30.0, 10.0], [10.0, 30.0]],
    "brackets/bracket-triangle-3-hole.svg": [
        [10.0, 10.0],
        [30.0, 10.0],
        [10.0, 30.0],
    ],
}
NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
COMMAND_RE = re.compile(r"([MLA])([^MLA]*)")
TRANSLATE_RE = re.compile(r"translate\(([-+0-9.eE]+)[ ,]+([-+0-9.eE]+)\)")


def _hash_managed_files(root: Path, managed_files: list[str]) -> dict[str, str]:
    return {
        rel: hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in sorted(managed_files)
    }


def _svg_root(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


def _has_class(root: ET.Element, class_name: str) -> bool:
    for element in root.iter():
        classes = set(element.attrib.get("class", "").split())
        if class_name in classes:
            return True
    return False


def _has_attr(root: ET.Element, name: str, value: str | None = None) -> bool:
    for element in root.iter():
        if name in element.attrib and (value is None or element.attrib[name] == value):
            return True
    return False


def _load_manifest(root: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((root / "manifest.json").read_text(encoding="utf-8")))


def _manifest_lists(manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], ...]:
    parts = manifest["parts"]
    assert isinstance(parts, dict)
    gears = parts["gears"]
    linkages = parts["linkages"]
    cams = parts["cams"]
    brackets = parts["brackets"]
    sheets = manifest["sheets"]
    assert isinstance(gears, list)
    assert isinstance(linkages, list)
    assert isinstance(cams, list)
    assert isinstance(brackets, list)
    assert isinstance(sheets, list)
    return (
        cast(list[dict[str, Any]], gears),
        cast(list[dict[str, Any]], linkages),
        cast(list[dict[str, Any]], cams),
        cast(list[dict[str, Any]], brackets),
        cast(list[dict[str, Any]], sheets),
    )


def _managed_files(manifest: dict[str, Any]) -> list[str]:
    managed_files = manifest["managed_files"]
    assert isinstance(managed_files, list)
    return [str(path) for path in managed_files]


def _floats(value: str) -> list[float]:
    return [float(match.group(0)) for match in NUMBER_RE.finditer(value)]


def _path_points(d_value: str) -> Iterable[tuple[float, float]]:
    current: tuple[float, float] | None = None
    for command, body in COMMAND_RE.findall(d_value):
        values = _floats(body)
        if command in {"M", "L"}:
            for idx in range(0, len(values) - 1, 2):
                current = (values[idx], values[idx + 1])
                yield current
        elif command == "A":
            for idx in range(0, len(values) - 6, 7):
                rx, ry, _rotation, _large_arc, sweep, end_x, end_y = values[idx : idx + 7]
                if current is not None:
                    start_x, start_y = current
                    if math.isclose(start_x, end_x, abs_tol=0.001):
                        center_y = (start_y + end_y) / 2.0
                        side = 1.0 if (end_y > start_y) == bool(int(sweep)) else -1.0
                        yield end_x + side * rx, center_y
                        yield end_x, center_y - ry
                        yield end_x, center_y + ry
                    elif math.isclose(start_y, end_y, abs_tol=0.001):
                        center_x = (start_x + end_x) / 2.0
                        side = -1.0 if (end_x > start_x) == bool(int(sweep)) else 1.0
                        yield center_x, end_y + side * ry
                        yield center_x - rx, end_y
                        yield center_x + rx, end_y
                current = (end_x, end_y)
                yield current


def _path_numeric_values(root: ET.Element, class_name: str) -> list[float]:
    for element in root.iter():
        if class_name in set(element.attrib.get("class", "").split()):
            return _floats(element.attrib["d"])
    raise AssertionError(f"missing path class {class_name}")


def _translated_offset(element: ET.Element, dx: float, dy: float) -> tuple[float, float]:
    transform = element.attrib.get("transform", "")
    match = TRANSLATE_RE.search(transform)
    if match is None:
        return dx, dy
    return dx + float(match.group(1)), dy + float(match.group(2))


def _assert_svg_geometry_inside_viewbox(root: ET.Element) -> None:
    _, _, width_text, height_text = root.attrib["viewBox"].split()
    width = float(width_text)
    height = float(height_text)
    tolerance = 0.001

    def visit(element: ET.Element, dx: float, dy: float) -> None:
        next_dx, next_dy = _translated_offset(element, dx, dy)
        tag = element.tag.removeprefix(SVG_NS)
        points: list[tuple[float, float]] = []
        if tag == "circle":
            cx = float(element.attrib["cx"]) + next_dx
            cy = float(element.attrib["cy"]) + next_dy
            radius = float(element.attrib["r"])
            points.extend(((cx - radius, cy - radius), (cx + radius, cy + radius)))
        elif tag == "line":
            points.extend(
                (
                    (float(element.attrib["x1"]) + next_dx, float(element.attrib["y1"]) + next_dy),
                    (float(element.attrib["x2"]) + next_dx, float(element.attrib["y2"]) + next_dy),
                )
            )
        elif tag == "path":
            points.extend((x + next_dx, y + next_dy) for x, y in _path_points(element.attrib["d"]))
        elif tag == "text":
            points.append(
                (float(element.attrib["x"]) + next_dx, float(element.attrib["y"]) + next_dy)
            )
        for x, y in points:
            assert -tolerance <= x <= width + tolerance, (tag, x, width, ET.tostring(element))
            assert -tolerance <= y <= height + tolerance, (tag, y, height, ET.tostring(element))
        for child in element:
            visit(child, next_dx, next_dy)

    visit(root, 0.0, 0.0)


def _hole_centers_for_role(root: ET.Element, role: str) -> list[tuple[float, float]]:
    centers: list[tuple[float, float]] = []
    for element in root.iter():
        if element.attrib.get("data-hole-role") == role:
            centers.append((float(element.attrib["cx"]), float(element.attrib["cy"])))
    return centers


def test_fabrication_generator_inventory_svg_contract_and_idempotence(tmp_path: Path) -> None:
    manifest = write_fabrication_templates(tmp_path)
    assert manifest == _load_manifest(tmp_path)
    assert set(manifest) == REQUIRED_TOP_LEVEL_KEYS
    assert manifest["schema_version"] == "automataii.fabrication.v1"
    assert manifest["grid_pitch_mm"] == 20.0
    assert manifest["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM

    gears, linkages, cams, brackets, sheets = _manifest_lists(manifest)
    managed_files = _managed_files(manifest)
    assert len(gears) == 4
    assert len(linkages) == 4
    assert len(cams) == 4
    assert len(brackets) == 4
    assert len(sheets) >= 6
    assert set(EXPECTED_BRACKETS) <= set(managed_files)
    assert any(path.startswith("sheets/06-bracket-set") for path in managed_files)

    for rel_path in managed_files:
        assert (tmp_path / rel_path).exists(), rel_path

    svg_paths = [Path(rel_path) for rel_path in managed_files if rel_path.endswith(".svg")]
    assert svg_paths
    for svg_path in svg_paths:
        root = _svg_root(tmp_path / svg_path)
        assert root.tag == f"{SVG_NS}svg"
        assert root.attrib["width"].endswith("mm")
        assert root.attrib["height"].endswith("mm")
        assert "viewBox" in root.attrib
        assert root.attrib["data-profile-key"]
        assert root.attrib["data-grid-pitch-mm"] == "20"
        assert root.attrib["data-hole-diameter-mm"] == "6"
        assert root.find(f"{SVG_NS}title") is not None
        assert root.find(f"{SVG_NS}desc") is not None
        _assert_svg_geometry_inside_viewbox(root)

    assert [gear["teeth"] for gear in gears] == [preset.teeth for preset in GEAR_PRESETS]
    for gear in gears:
        required = {
            "key",
            "teeth",
            "label",
            "path",
            "pitch_radius_mm",
            "outer_radius_mm",
            "root_radius_mm",
            "hole_diameter_mm",
            "attachment_hole_count",
            "attachment_kinds",
            "attachment_radii_mm",
            "attachment_hole_centers_mm",
        }
        assert required <= set(gear)
        assert gear["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM
        assert gear["attachment_hole_count"] >= 4
        assert len(gear["attachment_hole_centers_mm"]) == gear["attachment_hole_count"]
        assert gear["attachment_kinds"] == ["linkage", "bracket", "crank", "handle"]
        assert gear["attachment_radii_mm"] == sorted(
            {
                round(math.hypot(float(x), float(y)), 3)
                for x, y in gear["attachment_hole_centers_mm"]
            }
        )
        root = _svg_root(tmp_path / str(gear["path"]))
        assert _has_class(root, "gear-outline")
        assert _has_class(root, "axle-hole")
        assert _has_class(root, "linkage-hole")
        assert _has_class(root, "bracket-hole")
        assert _has_class(root, "crank-hole")
        assert _has_class(root, "handle-hole")
        assert _has_attr(root, "data-hole-role", "axle")
        assert _has_attr(root, "data-hole-role", "linkage-bracket-crank-handle")
        assert _has_attr(root, "data-attachment-kinds", "linkage bracket crank handle")
        for attr in (
            "data-teeth",
            "data-pitch-radius-mm",
            "data-root-radius-mm",
            "data-outer-radius-mm",
        ):
            assert _has_attr(root, attr)

    pitch_mm = grid_step_mm(DEFAULT_GRID_CELL_CM)
    assert [linkage["cells"] for linkage in linkages] == list(LINKAGE_LENGTH_CELLS)
    for linkage in linkages:
        cells = int(linkage["cells"])
        required = {
            "cells",
            "label",
            "path",
            "length_mm",
            "pitch_mm",
            "hole_diameter_mm",
            "hole_count",
        }
        assert required <= set(linkage)
        assert linkage["length_mm"] == round(cells * pitch_mm, 3)
        assert linkage["pitch_mm"] == round(pitch_mm, 3)
        assert linkage["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM
        assert linkage["hole_count"] == cells + 1
        root = _svg_root(tmp_path / str(linkage["path"]))
        assert _has_class(root, "linkage-outline")
        assert _has_class(root, "linkage-hole")
        assert _has_class(root, "bracket-hole")
        for attr in ("data-cells", "data-length-mm", "data-pitch-mm", "data-hole-count"):
            assert _has_attr(root, attr)
        seen_indices = {
            int(element.attrib["data-hole-index"])
            for element in root.iter()
            if element.attrib.get("data-hole-role") == "linkage-bracket"
        }
        assert seen_indices == set(range(cells + 1))

    assert [cam["key"] for cam in cams] == [preset.key for preset in CAM_PRESETS]
    for cam in cams:
        required = {
            "key",
            "label",
            "path",
            "base_radius_mm",
            "eccentricity_mm",
            "hole_diameter_mm",
            "attachment_hole_count",
            "attachment_kinds",
            "attachment_hole_centers_mm",
        }
        assert required <= set(cam)
        assert cam["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM
        assert cam["attachment_hole_count"] >= 4
        assert cam["attachment_kinds"] == ["linkage", "bracket", "crank", "handle"]
        root = _svg_root(tmp_path / str(cam["path"]))
        assert _has_class(root, "cam-outline")
        assert _has_class(root, "axle-hole")
        assert _has_class(root, "linkage-hole")
        assert _has_class(root, "bracket-hole")
        assert _has_class(root, "crank-hole")
        assert _has_class(root, "handle-hole")
        assert _has_attr(root, "data-hole-role", "axle")
        assert _has_attr(root, "data-hole-role", "linkage-bracket-crank-handle")
        assert _has_attr(root, "data-attachment-kinds", "linkage bracket crank handle")
        for attr in ("data-cam-key", "data-base-radius-mm", "data-eccentricity-mm"):
            assert _has_attr(root, attr)

    for bracket in brackets:
        required = {
            "key",
            "label",
            "path",
            "pitch_mm",
            "hole_diameter_mm",
            "hole_count",
            "hole_centers_mm",
        }
        assert required <= set(bracket)
        assert bracket["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM
        assert bracket["hole_centers_mm"] == EXPECTED_BRACKETS[bracket["path"]]
        centers = bracket["hole_centers_mm"]
        assert any(
            math.isclose(math.dist(first, second), 20.0, abs_tol=0.001)
            for idx, first in enumerate(centers)
            for second in centers[idx + 1 :]
        )
        root = _svg_root(tmp_path / str(bracket["path"]))
        assert _has_class(root, "bracket-outline")
        assert _has_class(root, "bracket-hole")
        assert _has_attr(root, "data-hole-role", "bracket")
        assert _hole_centers_for_role(root, "bracket") == [tuple(center) for center in centers]

    for sheet in sheets:
        required = {"key", "label", "path", "contains", "width_mm", "height_mm"}
        assert required <= set(sheet)
    assert any(
        str(sheet["path"]).startswith("sheets/06-bracket-set") and "brackets" in sheet["contains"]
        for sheet in sheets
    )
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "six workshop sheets" in readme
    assert "`gears/`, `linkages/`, `cams/`, and `brackets/`" in readme

    before = _hash_managed_files(tmp_path, managed_files)
    unrelated = tmp_path / "keep-me.txt"
    unrelated.write_text("not managed", encoding="utf-8")
    write_fabrication_templates(tmp_path)
    after_manifest = _load_manifest(tmp_path)
    after = _hash_managed_files(tmp_path, _managed_files(after_manifest))
    assert before == after
    assert unrelated.read_text(encoding="utf-8") == "not managed"


def test_fabrication_generator_supports_alternate_pitch_without_changing_holes(
    tmp_path: Path,
) -> None:
    manifest = write_fabrication_templates(tmp_path, grid_cell_cm=2.5)
    assert manifest["grid_pitch_mm"] == 25.0
    assert manifest["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM
    parts = manifest["parts"]
    assert isinstance(parts, dict)
    linkages = cast(list[dict[str, Any]], parts["linkages"])
    gears = cast(list[dict[str, Any]], parts["gears"])
    brackets = cast(list[dict[str, Any]], parts["brackets"])
    for linkage in linkages:
        cells = int(linkage["cells"])
        assert linkage["length_mm"] == round(cells * 25.0, 3)
        assert linkage["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM
    for bracket in brackets:
        assert bracket["hole_diameter_mm"] == DEFAULT_HOLE_DIAMETER_MM
    straight = next(
        bracket for bracket in brackets if bracket["path"] == "brackets/bracket-2-hole-straight.svg"
    )
    assert straight["hole_centers_mm"] == [[12.5, 12.5], [37.5, 12.5]]
    assert math.isclose(math.dist(*straight["hole_centers_mm"]), 25.0, abs_tol=0.001)
    straight_root = _svg_root(tmp_path / "brackets/bracket-2-hole-straight.svg")
    assert 37.5 in _path_numeric_values(straight_root, "bracket-outline")
    for bracket in brackets:
        _assert_svg_geometry_inside_viewbox(_svg_root(tmp_path / str(bracket["path"])))
    gear_path = tmp_path / str(gears[0]["path"])
    assert 'data-hole-diameter-mm="6"' in gear_path.read_text(encoding="utf-8")


def test_fabrication_generator_consumes_profile_hole_contract(tmp_path: Path) -> None:
    custom_profile = replace(
        DEFAULT_PHYSICAL_KIT_PROFILE,
        key="custom-7_5mm-hole",
        default_pitch_mm=30.0,
        hole_diameter_mm=7.5,
    )

    manifest = write_fabrication_templates(tmp_path, profile=custom_profile)

    assert manifest["profile_key"] == "custom-7_5mm-hole"
    assert manifest["grid_pitch_mm"] == 30.0
    assert manifest["hole_diameter_mm"] == 7.5
    root = _svg_root(tmp_path / "linkages/linkage-2-cell.svg")
    assert root.attrib["data-profile-key"] == "custom-7_5mm-hole"
    assert root.attrib["data-grid-pitch-mm"] == "30"
    assert root.attrib["data-hole-diameter-mm"] == "7.5"
    linkage_holes = [
        element
        for element in root.iter()
        if element.attrib.get("data-hole-role") == "linkage-bracket"
    ]
    assert linkage_holes
    assert all(math.isclose(float(element.attrib["r"]), 3.75) for element in linkage_holes)
    bracket = _load_manifest(tmp_path)["parts"]["brackets"][0]
    assert bracket["hole_centers_mm"] == [[15.0, 15.0], [45.0, 15.0]]
    assert "7.5 mm" in (tmp_path / "README.md").read_text(encoding="utf-8")


def test_committed_fabrication_package_matches_generator(tmp_path: Path) -> None:
    manifest = write_fabrication_templates(tmp_path)
    managed_files = set(_managed_files(manifest))
    committed_files = {
        path.relative_to(REPO_ROOT / "fabrication").as_posix()
        for path in (REPO_ROOT / "fabrication").rglob("*")
        if path.is_file()
    }
    assert committed_files == managed_files
    for rel_path in sorted(managed_files):
        assert (REPO_ROOT / "fabrication" / rel_path).read_text(encoding="utf-8") == (
            tmp_path / rel_path
        ).read_text(encoding="utf-8")


def test_fabrication_generator_cli(tmp_path: Path) -> None:
    output = tmp_path / "cli-output"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_fabrication_templates.py",
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "Generated" in result.stdout
    manifest = _load_manifest(output)
    assert manifest["schema_version"] == "automataii.fabrication.v1"
    assert len(_managed_files(manifest)) >= 24
