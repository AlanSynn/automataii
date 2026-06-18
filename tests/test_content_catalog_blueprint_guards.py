from __future__ import annotations

import json
import math
from dataclasses import dataclass

from automataii.application.blueprint import BlueprintComposer
from automataii.application.mechanism_foundry.catalog import load_catalog
from automataii.application.mechanism_foundry.content_loader import ContentLoader
from automataii.domain.generation.contour import ManufacturingContour
from automataii.domain.generation.layout import ScaledBounds
from automataii.infrastructure.generation.processors.png_blueprint import PNGBlueprintProcessor
from automataii.infrastructure.generation.svg.blueprint import generate_single_large_blueprint
from automataii.scenarios.blueprint import ScenarioLayoutItem, ScenarioOptimizer


def test_content_loader_sanitizes_keys_caches_defaults_and_lists_sorted(tmp_path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (tmp_path / "secret.json").write_text(
        json.dumps({"title": "Secret", "goal": "Should not be read"}),
        encoding="utf-8",
    )
    (content_dir / "b.json").write_text("{}", encoding="utf-8")
    (content_dir / "a.json").write_text("{}", encoding="utf-8")

    loader = ContentLoader(content_dir=content_dir)
    content = loader.load_content("../secret")
    again = loader.load_content("../secret")

    assert content.goal != "Should not be read"
    assert content.goal == "No description available"
    assert content is again
    assert loader.list_available_content() == ["a", "b"]


def test_content_loader_tolerates_malformed_content_payload(tmp_path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "case.json").write_text(
        json.dumps(
            {
                "title": "  Derived  ",
                "goal": None,
                "parts": "lever",
                "tags": "rotary",
                "motions": [],
                "diagram_path": 42,
                "gallery_summary": ["bad"],
                "parameter_options": {
                    "length": [
                        {"value": "10", "label": " Ten ", "description": 9},
                        {"value": math.nan, "label": "bad"},
                        {"value": 12, "label": ""},
                        [],
                    ],
                    "broken": None,
                },
            }
        ),
        encoding="utf-8",
    )

    content = ContentLoader(content_dir=content_dir).load_content("case")

    assert content.title == "Derived"
    assert content.goal == "No description available"
    assert content.parts == ("lever",)
    assert content.motions == ("Circular",)
    assert content.diagram_path == "42"
    assert content.parameter_options["length"][0].value == 10.0
    assert content.parameter_options["length"][0].label == "Ten"
    assert content.parameter_options["length"][0].description == "9"


def test_catalog_loader_fails_closed_on_non_object_root(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text("[]", encoding="utf-8")

    catalog = load_catalog(catalog_path)

    assert catalog.version == "0.0.0"
    assert catalog.categories == {}


def test_catalog_loader_skips_malformed_nested_entries(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "version": 3,
                "categories": {
                    "bad": [],
                    "cat": {
                        "name": None,
                        "icon": 7,
                        "mechanisms": {
                            "broken": [],
                            "mech": {
                                "name": None,
                                "tags": "basic",
                                "preview_size": [120, "bad", -1],
                                "animation_duration": "2500",
                                "parameters": {
                                    "bad_param": [],
                                    "length": {
                                        "name": None,
                                        "default": "12.5",
                                        "min": "0",
                                        "max": "nan",
                                        "unit": "mm",
                                    },
                                },
                            },
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    catalog = load_catalog(catalog_path)
    entry = catalog.categories["cat"].mechanisms["mech"]

    assert catalog.version == "3"
    assert entry.name == "mech"
    assert entry.tags == ("basic",)
    assert entry.preview_size == (120,)
    assert entry.animation_duration == 2500
    assert set(entry.parameters) == {"length"}
    assert entry.parameters["length"].min == 0.0
    assert entry.parameters["length"].max is None


def test_scenario_optimizer_handles_empty_and_malformed_inputs() -> None:
    optimizer = ScenarioOptimizer()

    assert optimizer.optimize_blueprint_layout([], {}, "metric") == ([], 400.0, 300.0)

    items, width, height = optimizer.optimize_blueprint_layout(
        [{"name": "<Part>", "width_mm": math.nan, "height_mm": -5}],
        {"mech<script>": {"display_name": "<Mech>", "type": "<type>", "params": {"bad": "x"}}},
        "metric",
    )

    assert len(items) == 2
    assert width > 0
    assert height > 0
    assert "&lt;Part&gt;" in items[0].svg_content
    assert "&lt;Mech&gt;" in items[1].svg_content
    assert "&lt;type&gt;" in items[1].svg_content


@dataclass
class _Bounds:
    width: float
    height: float


@dataclass
class _LayoutItem:
    bounds: _Bounds
    svg_content: str
    item_type: str = "part"
    name: str = "item"


class _BadOptimizer:
    def optimize_blueprint_layout(self, part_items, mechanism_layers, unit_system):
        return [_LayoutItem(_Bounds(10.0, 10.0), "<rect />")], math.nan, math.inf


def test_blueprint_composer_normalizes_nonfinite_optimizer_dimensions() -> None:
    seen: dict[str, float | str | None] = {}

    def generator(layout_items, width, height, title, scale_info, snapshot_data_uri, unit_system):
        seen.update(width=width, height=height, unit=unit_system, snapshot=snapshot_data_uri)
        return "<svg/>"

    result = BlueprintComposer(
        optimizer=_BadOptimizer(), svg_generator=generator
    ).compose_single_page([], {}, unit_system="bad", snapshot_png_bytes=b"png")

    assert result.width_mm == 800.0
    assert result.height_mm == 600.0
    assert seen["width"] == 800.0
    assert seen["height"] == 600.0
    assert seen["unit"] == "metric"
    assert str(seen["snapshot"]).startswith("data:image/png;base64,")


def test_single_large_blueprint_escapes_header_and_rejects_bad_snapshot() -> None:
    svg = generate_single_large_blueprint(
        [ScenarioLayoutItem("part", ScaledBounds(0, 0, math.nan, -1), "<rect />", "part")],
        math.nan,
        -1,
        title="<Title>",
        scale_info="<Scale>",
        snapshot_data_uri="data:image/svg+xml,<svg onload='x'/>",
        unit_system="bad",
    )

    assert 'width="800.0mm"' in svg
    assert 'viewBox="0 0 800.0 600.0"' in svg
    assert "&lt;Title&gt;" in svg
    assert "&lt;Scale&gt;" in svg
    assert "onload" not in svg


def test_single_large_blueprint_separates_cut_sheets_from_board_assembly() -> None:
    svg = generate_single_large_blueprint(
        [
            ScenarioLayoutItem(
                "Head",
                ScaledBounds(0, 0, 20.0, 30.0),
                "<rect width='20' height='30' />",
                "part",
            )
        ],
        800,
        600,
        title="Make Parts / Cut Sheets",
        scale_info="Character body components + mechanisms",
        unit_system="metric",
    )

    assert "Current Design Cut Sheets" not in svg
    assert "Units: Metric" not in svg
    assert "Board preset: 15×15 holes" in svg
    assert "Make Parts / Cut Sheets boundary" in svg
    assert "this sheet is not the board assembly order" in svg
    assert "Character body components: 1" in svg
    assert "Drill 4mm holes when shown" in svg
    assert "Paper fasteners are hardware, not cut parts" in svg
    assert "Fastener/spacer location is assigned in the Assembly Guide" in svg


def test_png_blueprint_processor_escapes_part_names_and_invalid_metrics() -> None:
    processor = PNGBlueprintProcessor()
    contour = ManufacturingContour(
        contour=__import__("numpy").array([[[0, 0]], [[10, 0]], [[10, 10]], [[0, 10]]]),
        simplified_contour=__import__("numpy").array([[[0, 0]], [[10, 0]], [[10, 10]], [[0, 10]]]),
        svg_path='M 0 0 L 10 0 L 10 10 Z" onload="x',
    )
    contour.area = math.nan
    contour.perimeter = math.inf

    svg = processor._create_manufacturing_part_svg(contour, math.nan, -5.0, '<Part "A">')

    assert "&lt;Part &quot;A&quot;&gt;" in svg
    assert 'onload="x' not in svg
    assert "nan" not in svg.lower()
    assert "Area: 0mm² | Perimeter: 0.0mm" in svg
