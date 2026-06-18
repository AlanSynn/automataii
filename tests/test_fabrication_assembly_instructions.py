from __future__ import annotations

import inspect
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, cast

import pytest
from scripts.generate_fabrication_templates import write_fabrication_templates

import automataii.application.fabrication.assembly_export as assembly_export
from automataii.application.fabrication import (
    FabricationAssemblyGuideExporter,
    FabricationLayerSelection,
    active_part_ids_from_layer,
)
from automataii.application.managers.blueprint_manager import BlueprintExportManager
from automataii.application.mechanism_foundry.controller import (
    MechanismFoundryController,
    build_mechanism_configs,
)
from automataii.application.mechanism_foundry.mechanism_types import (
    VISIBLE_FOUNDRY_MECHANISM_TYPES,
)
from automataii.application.mechanism_transfer.contract import SUPPORTED_EXPORT_TYPES
from automataii.presentation.qt.blueprint.exporter import BlueprintExporter
from automataii.shared.fabrication_assembly import (
    ASSEMBLY_SCHEMA_VERSION,
    BOARD_COLUMNS,
    BOARD_ROWS,
    AssemblyValidationError,
    manifest_part_index,
    validate_assembly_package,
)

SVG_NS = "{http://www.w3.org/2000/svg}"
EXPECTED_RECIPE_KEYS = {
    "gear-train-basic",
    "cam-follower-basic",
    "four-bar-basic",
    "gear-linkage-crank",
    "planetary-gear-basic",
    "slider-crank-basic",
}
REQUIRED_LAYER_IDS = {
    "layer-board-grid",
    "layer-previous-step-ghost",
    "layer-existing-parts",
    "layer-new-part-highlight",
    "layer-fasteners",
    "layer-spacers",
    "layer-motion-arrows",
    "layer-callouts",
    "layer-labels",
    "layer-stack-diagram",
}


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _svg_root(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


def _text_content(root: ET.Element) -> str:
    return "\n".join(element.text or "" for element in root.iter(f"{SVG_NS}text"))


def _layout_boxes(root: ET.Element) -> list[tuple[int, str, float, float, float, float]]:
    boxes: list[tuple[int, str, float, float, float, float]] = []
    for element in root.iter():
        raw = element.attrib.get("data-layout-box")
        if not raw:
            continue
        step_text, zone, x_text, y_text, width_text, height_text = raw.split(",")
        boxes.append(
            (
                int(step_text),
                zone,
                float(x_text),
                float(y_text),
                float(width_text),
                float(height_text),
            )
        )
    return boxes


def _overlaps(
    first: tuple[float, float, float, float], second: tuple[float, float, float, float]
) -> bool:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def test_assembly_recipe_package_schema_references_and_bidirectionality(tmp_path: Path) -> None:
    manifest = write_fabrication_templates(tmp_path)
    package = _load_json(tmp_path / "assembly" / "recipes.json")

    validate_assembly_package(package, manifest)
    assert package["schema_version"] == ASSEMBLY_SCHEMA_VERSION
    assert manifest["board_rows"] == 15
    assert manifest["board_columns"] == 15
    assert package["board"] == {
        "columns": 15,
        "column_labels": [str(column) for column in BOARD_COLUMNS],
        "origin": "top-left",
        "row_labels": list(BOARD_ROWS),
        "rows": 15,
    }
    assert package["hardware"]["part_hole_diameter_mm"] == 4.0
    assert package["hardware"]["fastener"] == "paper-fastener"

    part_index = manifest_part_index(manifest)
    assert "linkages:linkage-2-cell" in part_index
    raw_part_index = {
        f"{category}:{item['key']}"
        for category, raw_items in cast(dict[str, Any], manifest["parts"]).items()
        for item in cast(list[dict[str, Any]], raw_items)
        if isinstance(item.get("key"), str)
    }
    recipes = cast(list[dict[str, Any]], package["recipes"])
    assert {recipe["key"] for recipe in recipes} == EXPECTED_RECIPE_KEYS
    recipe_types = {recipe["mechanism_type"] for recipe in recipes}
    assert SUPPORTED_EXPORT_TYPES <= recipe_types
    assert VISIBLE_FOUNDRY_MECHANISM_TYPES <= recipe_types

    for recipe in recipes:
        assert recipe["mechanism_type"] in SUPPORTED_EXPORT_TYPES
        assert recipe["app_mapping"]["mechanism_type"] in SUPPORTED_EXPORT_TYPES
        assert (tmp_path / recipe["guide_svg"]).is_file()
        steps = cast(list[dict[str, Any]], recipe["steps"])
        assert [step["n"] for step in steps] == list(range(1, len(steps) + 1))
        for step in steps:
            assert step["app_mapping"]["mechanism_type"] in SUPPORTED_EXPORT_TYPES
            assert step["app_mapping"]["mechanism_type"] == recipe["mechanism_type"]
            coords = cast(list[str], step["coords"])
            coord_roles = cast(list[str], step["coord_roles"])
            assert coords
            assert len(coord_roles) == len(coords)
            for coord in coords:
                assert coord[0] in BOARD_ROWS
                assert int(coord[1:]) in BOARD_COLUMNS
            stack = cast(list[dict[str, Any]], step["stack"])
            orders = [layer["order"] for layer in stack]
            assert orders == sorted(orders)
            roles = {str(layer["role"]) for layer in stack}
            if step["action"] in {"add-part", "add-linkage", "add-guide", "test-motion"}:
                assert "paper-fastener" in roles
                assert {"spacer", "top-spacer"} & roles
            physical_parts = {
                str(part["part"]) for part in cast(list[dict[str, Any]], step["parts"])
            } | {str(layer["part"]) for layer in stack if isinstance(layer.get("part"), str)}
            active_parts = set(cast(list[str], step["visual_state"]["active_parts"]))
            highlight_ids = set(cast(list[str], step["app_mapping"]["highlight_ids"]))
            assert active_parts <= physical_parts
            assert highlight_ids <= physical_parts
            for part in physical_parts:
                assert part in part_index
                assert part in raw_part_index

    gear_recipe = next(recipe for recipe in recipes if recipe["key"] == "gear-train-basic")
    compat = gear_recipe["compatibility"][0]
    assert compat["compatible"] is True
    assert compat["first_coord_role"] == "board_axle"
    assert compat["second_coord_role"] == "board_axle"
    assert 1.0 <= float(compat["board_distance_cells"]) <= 3.0
    assert abs(float(compat["error_mm"])) <= float(compat["tolerance_mm"])

    four_bar_recipe = next(recipe for recipe in recipes if recipe["key"] == "four-bar-basic")
    assert (
        sum(
            int(part["count"])
            for part in cast(list[dict[str, Any]], four_bar_recipe["parts"])
            if part["part"] == "linkages:linkage-2-cell"
        )
        == 2
    )

    planetary_recipe = next(recipe for recipe in recipes if recipe["key"] == "planetary-gear-basic")
    planetary_defaults = build_mechanism_configs()["planetary_gear"].initial_parameters()
    assert planetary_defaults["planet_count"] == 1
    assert (
        sum(
            int(part["count"])
            for part in cast(list[dict[str, Any]], planetary_recipe["parts"])
            if part["part"] == "gears:g14"
        )
        == planetary_defaults["planet_count"]
    )
    assert planetary_recipe["app_mapping"]["mechanism_type"] == "planetary_gear"
    assert any(
        part["part"] == "ring_gears:ring-g12-g14"
        for part in cast(list[dict[str, Any]], planetary_recipe["parts"])
    )
    assert planetary_recipe["compatibility"][0]["compatible"] is True
    assert planetary_recipe["compatibility"][0]["second_coord_role"] == "carrier_reference"
    planet_step = next(
        step
        for step in cast(list[dict[str, Any]], planetary_recipe["steps"])
        if step["app_mapping"]["component_role"] == "planet-gear"
    )
    planet_step_roles = {
        str(layer["role"]) for layer in cast(list[dict[str, Any]], planet_step["stack"])
    }
    assert "carrier-hole" in planet_step_roles
    assert "board" not in planet_step_roles
    assert "not the board" in str(planet_step["instruction"])
    assert planet_step["coord_roles"] == ["carrier_reference"]
    ring_step = next(
        step
        for step in cast(list[dict[str, Any]], planetary_recipe["steps"])
        if step["app_mapping"]["component_role"] == "ring-gear"
    )
    assert ring_step["coord_roles"] == ["board", "board", "board", "board"]
    assert any(
        layer["role"] == "fixed-part" and layer["part"] == "ring_gears:ring-g12-g14"
        for layer in cast(list[dict[str, Any]], ring_step["stack"])
    )

    gear_linkage_recipe = next(
        recipe for recipe in recipes if recipe["key"] == "gear-linkage-crank"
    )
    output_link_step = next(
        step
        for step in cast(list[dict[str, Any]], gear_linkage_recipe["steps"])
        if step["app_mapping"]["component_role"] == "output-link"
    )
    output_link_roles = {
        str(layer["role"]) for layer in cast(list[dict[str, Any]], output_link_step["stack"])
    }
    assert "gear-handle-hole" in output_link_roles
    assert "board" not in output_link_roles
    assert "not the board" in str(output_link_step["instruction"])
    output_connector_step = next(
        step
        for step in cast(list[dict[str, Any]], gear_linkage_recipe["steps"])
        if step["app_mapping"]["component_role"] == "output-connector"
    )
    output_connector_roles = {
        str(layer["role"]) for layer in cast(list[dict[str, Any]], output_connector_step["stack"])
    }
    assert "link-end-hole" in output_connector_roles
    assert "board" not in output_connector_roles

    slider_recipe = next(recipe for recipe in recipes if recipe["key"] == "slider-crank-basic")
    assert slider_recipe["mechanism_type"] == "slider_crank"
    slider_block_step = next(
        step
        for step in cast(list[dict[str, Any]], slider_recipe["steps"])
        if step["app_mapping"]["component_role"] == "slider-block"
    )
    assert slider_block_step["coord_roles"] == ["slider_reference"]
    assert "board" not in {
        str(layer["role"]) for layer in cast(list[dict[str, Any]], slider_block_step["stack"])
    }


def test_assembly_svg_cards_have_testable_layers_and_non_overlapping_layout(
    tmp_path: Path,
) -> None:
    manifest = write_fabrication_templates(tmp_path)
    package = _load_json(tmp_path / "assembly" / "recipes.json")
    managed_files = set(cast(list[str], manifest["managed_files"]))

    board_root = _svg_root(tmp_path / "assembly" / "board-15x15.svg")
    assert (tmp_path / "assembly" / "index.html").is_file()
    assert (tmp_path / "assembly" / "parts-overview.svg").is_file()
    index_text = (tmp_path / "assembly" / "index.html").read_text(encoding="utf-8")
    assert "Quick start" in index_text
    assert "Assembly order" in index_text
    board_coords = {
        element.attrib["data-board-coord"]
        for element in board_root.iter()
        if "data-board-coord" in element.attrib
    }
    assert len(board_coords) == len(BOARD_ROWS) * len(BOARD_COLUMNS) == 225
    assert "A1" in board_coords
    assert "O15" in board_coords
    board_circles = {
        element.attrib["data-board-coord"]: element
        for element in board_root.iter(f"{SVG_NS}circle")
        if "data-board-coord" in element.attrib
    }
    assert len(board_circles) == 225
    assert float(board_circles["A1"].attrib["r"]) == 2.0
    assert float(board_circles["A2"].attrib["cx"]) - float(board_circles["A1"].attrib["cx"]) == 20.0
    assert float(board_circles["B1"].attrib["cy"]) - float(board_circles["A1"].attrib["cy"]) == 20.0

    for recipe in cast(list[dict[str, Any]], package["recipes"]):
        guide_svg = str(recipe["guide_svg"])
        assert guide_svg in managed_files
        root = _svg_root(tmp_path / guide_svg)
        ids = {element.attrib.get("id") for element in root.iter()}
        assert REQUIRED_LAYER_IDS <= ids
        assert any("data-step" in element.attrib for element in root.iter())
        assert any("data-board-coord" in element.attrib for element in root.iter())
        assert any("data-part-key" in element.attrib for element in root.iter())
        assert any("data-stack-layer" in element.attrib for element in root.iter())
        assert any("data-app-mechanism" in element.attrib for element in root.iter())
        visible_text = _text_content(root)
        assert "Parts to add now" in visible_text
        assert "Fastener stack" in visible_text
        assert "Metric" not in visible_text
        assert "Imperial" not in visible_text
        assert "inch" not in visible_text.lower()
        assert "mm" not in visible_text.lower()
        if recipe["key"] == "planetary-gear-basic":
            assert "Carrier ref" in visible_text
            assert "Carrier hole" in visible_text
            assert "R40" in visible_text
        if recipe["key"] == "gear-linkage-crank":
            assert "Gear/handle ref" in visible_text
            assert "Gear handle hole" in visible_text
            assert "Link-end ref" in visible_text
        if recipe["key"] == "slider-crank-basic":
            assert "Slider ref" in visible_text
            assert "Link-joint ref" in visible_text

        active_holes_by_step: dict[str, set[str]] = {}
        new_highlights_by_step: dict[str, set[str]] = {}
        reference_markers_by_step: dict[str, set[str]] = {}
        for element in root.iter(f"{SVG_NS}circle"):
            step = element.attrib.get("data-step")
            if not step:
                continue
            classes = set(element.attrib.get("class", "").split())
            if "active-board-hole" in classes and "data-board-coord" in element.attrib:
                active_holes_by_step.setdefault(step, set()).add(element.attrib["data-board-coord"])
            if "new-part-highlight" in classes and "data-board-coord" in element.attrib:
                new_highlights_by_step.setdefault(step, set()).add(
                    element.attrib["data-board-coord"]
                )
            if "reference-marker" in classes and "data-reference-coord" in element.attrib:
                reference_markers_by_step.setdefault(step, set()).add(
                    element.attrib["data-reference-coord"]
                )
        if recipe["key"] == "planetary-gear-basic":
            assert "H10" not in active_holes_by_step.get("5", set())
            assert "H10" not in new_highlights_by_step.get("5", set())
            assert "H10" in reference_markers_by_step.get("5", set())

        by_step: dict[int, list[tuple[str, float, float, float, float]]] = {}
        for step, zone, x, y, width, height in _layout_boxes(root):
            by_step.setdefault(step, []).append((zone, x, y, width, height))
        assert by_step
        for boxes in by_step.values():
            for idx, first in enumerate(boxes):
                for second in boxes[idx + 1 :]:
                    assert not _overlaps(first[1:], second[1:]), (first, second)


def test_application_exporter_lists_and_exports_pdf_board_guides(tmp_path: Path) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)

    summaries = exporter.list_guides()
    assert {summary.key for summary in summaries} == EXPECTED_RECIPE_KEYS
    assert all(summary.step_count >= 4 for summary in summaries)
    missing_guide = tmp_path / "assembly" / "04-gear-linkage-crank.svg"
    missing_guide.unlink()
    assert {
        summary.key for summary in FabricationAssemblyGuideExporter(tmp_path).list_guides()
    } == EXPECTED_RECIPE_KEYS - {"gear-linkage-crank"}
    write_fabrication_templates(tmp_path)
    for mechanism_type in VISIBLE_FOUNDRY_MECHANISM_TYPES:
        assert exporter.find_guides_for_mechanism(mechanism_type), mechanism_type
    assert exporter.find_guides_for_mechanism("slider_crank")[0].key == "slider-crank-basic"
    assert exporter.find_guides_for_mechanism("gear+linkage")[0].key == "gear-linkage-crank"
    resolved = exporter.resolve_app_state_to_guide(
        "gear+linkage",
        active_part_ids={"linkages:linkage-4-cell"},
    )
    assert resolved is not None
    assert resolved.key == "gear-linkage-crank"

    output_dir = tmp_path / "exported-guides"
    result = exporter.export_guides(output_dir, recipe_keys={"gear-train-basic"})

    package_dir = output_dir / "assembly"
    assert result.recipe_keys == ("gear-train-basic",)
    assert result.output_dir == output_dir
    assert result.package_dir == package_dir
    assert (package_dir / "recipes.json").is_file()
    assert (package_dir / "README.md").is_file()
    assert (package_dir / "assembly-guide.pdf").is_file()
    assert (package_dir / "kit-parts-to-cut.pdf").is_file()
    assert not (package_dir / "index.html").exists()
    assert not (package_dir / "parts").exists()
    assert not (package_dir / "01-gear-train-basic.svg").exists()
    assert set(result.pdf_files) == {
        package_dir / "assembly-guide.pdf",
        package_dir / "kit-parts-to-cut.pdf",
    }
    assert all(path.stat().st_size > 1000 for path in result.pdf_files)
    assert len(result.copied_files) >= 4
    exported_recipes = _load_json(package_dir / "recipes.json")
    assert [
        recipe["key"] for recipe in cast(list[dict[str, Any]], exported_recipes["recipes"])
    ] == ["gear-train-basic"]
    readme = (package_dir / "README.md").read_text(encoding="utf-8")
    assert "assembly-guide.pdf" in readme
    assert "kit-parts-to-cut.pdf" in readme
    assert "physical-contract.json" in readme
    assert "LEGO-style step cards" in readme

    exporter.export_guides(output_dir)
    all_recipes = _load_json(package_dir / "recipes.json")
    assert {
        recipe["key"] for recipe in cast(list[dict[str, Any]], all_recipes["recipes"])
    } == EXPECTED_RECIPE_KEYS
    exporter.export_guides(output_dir, recipe_keys={"cam-follower-basic"})
    selected_recipes = _load_json(package_dir / "recipes.json")
    assert [
        recipe["key"] for recipe in cast(list[dict[str, Any]], selected_recipes["recipes"])
    ] == ["cam-follower-basic"]
    assert not (package_dir / "svg-fallback").exists()


def test_export_guides_writes_package_for_each_recipe_key(tmp_path: Path) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)

    for recipe_key in EXPECTED_RECIPE_KEYS:
        output_dir = tmp_path / f"exported-{recipe_key}"
        result = exporter.export_guides(output_dir, recipe_keys={recipe_key})
        package_dir = output_dir / "assembly"
        selected_recipes = _load_json(package_dir / "recipes.json")

        assert [recipe["key"] for recipe in selected_recipes["recipes"]] == [recipe_key]
        assert result.recipe_keys == (recipe_key,)
        assert (package_dir / "assembly-guide.pdf").is_file()
        assert (package_dir / "kit-parts-to-cut.pdf").is_file()
        assert not (package_dir / "svg-fallback").exists()


def test_runtime_foundry_visible_mechanisms_have_assembly_guides(tmp_path: Path) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)
    controller = MechanismFoundryController()

    visible_types = {item.mechanism_type for item in controller.list_mechanisms()}

    assert visible_types == VISIBLE_FOUNDRY_MECHANISM_TYPES
    for mechanism_type in visible_types:
        assert exporter.find_guides_for_mechanism(mechanism_type), mechanism_type


def test_application_exporter_writes_contract_report_without_board_pdfs(tmp_path: Path) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)
    output_dir = tmp_path / "exported-guides"
    ready_result = exporter.export_guides(output_dir, recipe_keys={"gear-train-basic"})
    assert (ready_result.package_dir / "assembly-guide.pdf").is_file()
    assert (ready_result.package_dir / "kit-parts-to-cut.pdf").is_file()

    contract = {
        "schema_version": ASSEMBLY_SCHEMA_VERSION,
        "status": "warning",
        "warnings": ["custom gear teeth do not match fabrication preset"],
    }

    path = exporter.export_contract_report(output_dir, contract)

    package_dir = tmp_path / "exported-guides" / "assembly"
    assert path == package_dir / "physical-contract.json"
    assert _load_json(path)["warnings"] == ["custom gear teeth do not match fabrication preset"]
    assert not (package_dir / "assembly-guide.pdf").exists()
    assert not (package_dir / "kit-parts-to-cut.pdf").exists()
    assert not (package_dir / "svg-fallback").exists()
    assert not (package_dir / "recipes.json").exists()
    assert not (package_dir / "README.md").exists()


def test_application_exporter_clears_stale_package_when_no_recipe_matches(
    tmp_path: Path,
) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)
    output_dir = tmp_path / "exported-guides"
    ready_result = exporter.export_guides(output_dir, recipe_keys={"gear-train-basic"})
    package_dir = ready_result.package_dir
    assert (package_dir / "assembly-guide.pdf").is_file()
    (package_dir / "physical-contract.json").write_text("{}", encoding="utf-8")

    cleared_dir = exporter.clear_exported_package(output_dir)

    assert cleared_dir == package_dir
    assert not (package_dir / "assembly-guide.pdf").exists()
    assert not (package_dir / "kit-parts-to-cut.pdf").exists()
    assert not (package_dir / "physical-contract.json").exists()
    assert not (package_dir / "recipes.json").exists()
    assert not (package_dir / "README.md").exists()
    assert not (package_dir / "svg-fallback").exists()


def test_application_exporter_resolves_relative_root_through_packaged_base(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    write_fabrication_templates(bundle_root / "fabrication")

    def fake_resolve_path(relative_path: str | Path) -> Path:
        return bundle_root / relative_path

    monkeypatch.setattr(assembly_export, "resolve_path", fake_resolve_path)

    exporter = FabricationAssemblyGuideExporter("fabrication")

    assert exporter.fabrication_root == bundle_root / "fabrication"
    assert exporter.recipes_path == bundle_root / "fabrication" / "assembly" / "recipes.json"
    assert {summary.key for summary in exporter.list_guides()} == EXPECTED_RECIPE_KEYS


def test_application_exporter_rejects_recipe_path_traversal(tmp_path: Path) -> None:
    write_fabrication_templates(tmp_path)
    recipes_path = tmp_path / "assembly" / "recipes.json"
    package = _load_json(recipes_path)
    recipes = cast(list[dict[str, Any]], package["recipes"])
    recipes[0]["guide_svg"] = "../manifest.json"
    recipes_path.write_text(json.dumps(package), encoding="utf-8")

    exporter = FabricationAssemblyGuideExporter(tmp_path)
    with pytest.raises(ValueError, match="Unsafe assembly guide path"):
        exporter.export_guides(tmp_path / "exported-guides", recipe_keys={"gear-train-basic"})


def test_application_exporter_falls_back_to_svg_sources_when_pdf_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_fabrication_templates(tmp_path)

    def fake_render(_sources: object, pdf_path: Path) -> bool:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text("partial pdf", encoding="utf-8")
        return False

    monkeypatch.setattr(assembly_export, "render_svgs_to_pdf", fake_render)

    result = FabricationAssemblyGuideExporter(tmp_path).export_guides(
        tmp_path / "exported-guides",
        recipe_keys={"gear-train-basic"},
    )

    package_dir = tmp_path / "exported-guides" / "assembly"
    assert not result.pdf_files
    assert result.fallback_files
    assert not (package_dir / "assembly-guide.pdf").exists()
    assert not (package_dir / "kit-parts-to-cut.pdf").exists()
    assert not any(path.name.startswith(".assembly-guide.tmp") for path in package_dir.iterdir())
    assert (package_dir / "svg-fallback" / "assembly" / "01-checklist.svg").is_file()
    assert (package_dir / "svg-fallback" / "assembly" / "02-board-15x15.svg").is_file()
    assert (package_dir / "svg-fallback" / "assembly" / "03-01-gear-train-basic.svg").is_file()
    assert (package_dir / "svg-fallback" / "parts" / "02-gear-12t.svg").is_file()


def test_application_exporter_rejects_renderer_success_with_non_pdf_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_fabrication_templates(tmp_path)

    def fake_render(_sources: object, pdf_path: Path) -> bool:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text("not a pdf", encoding="utf-8")
        return True

    monkeypatch.setattr(assembly_export, "render_svgs_to_pdf", fake_render)

    result = FabricationAssemblyGuideExporter(tmp_path).export_guides(
        tmp_path / "exported-guides",
        recipe_keys={"gear-train-basic"},
    )

    package_dir = tmp_path / "exported-guides" / "assembly"
    assert not result.pdf_files
    assert result.fallback_files
    assert not (package_dir / "assembly-guide.pdf").exists()
    assert not (package_dir / "kit-parts-to-cut.pdf").exists()


def test_export_guides_without_contract_removes_stale_physical_contract(tmp_path: Path) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)
    output_dir = tmp_path / "exported-guides"
    package_dir = output_dir / "assembly"
    package_dir.mkdir(parents=True)
    (package_dir / "physical-contract.json").write_text('{"status":"stale"}', encoding="utf-8")

    exporter.export_guides(output_dir, recipe_keys={"gear-train-basic"})

    assert not (package_dir / "physical-contract.json").exists()


def test_fabrication_export_surface_defaults_to_integrated_pdf_package() -> None:
    blueprint_source = inspect.getsource(BlueprintExporter)
    manager_source = inspect.getsource(BlueprintExportManager._get_save_file_path)

    assert "Export Blueprint Package" in blueprint_source
    assert "PDF-first blueprint package" in blueprint_source
    assert "LEGO guide book" in blueprint_source
    assert "Blueprint Package Exported with Contract Warnings" in blueprint_source
    assert "assembly_contract_ready" not in blueprint_source
    assert "clear_exported_package" in blueprint_source
    assert "fallback_files" in blueprint_source
    assert "gated by physical contract warnings" not in blueprint_source
    assert "kit-parts-to-cut.pdf" in inspect.getsource(FabricationAssemblyGuideExporter)
    assert "physical-contract.json" in inspect.getsource(FabricationAssemblyGuideExporter)
    assert "index.html" not in inspect.getsource(FabricationAssemblyGuideExporter.export_guides)
    assert "Choose what you want to export" not in blueprint_source
    assert "Export Make Parts / Cut Sheets" in manager_source
    assert "current-design-cut-sheets.pdf" in manager_source
    assert "PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)" in manager_source
    assert "SVG Files (*.svg);;PDF Files (*.pdf);;All Files (*)" in manager_source


def test_assembly_export_readme_and_pdf_cover_explain_character_attachment(tmp_path: Path) -> None:
    exporter = FabricationAssemblyGuideExporter(tmp_path)
    package = {
        "recipes": [
            {
                "title": "Four-bar",
                "guide_svg": "03-four-bar-basic.svg",
                "steps": [
                    {
                        "n": 1,
                        "title": "Pin character arm",
                        "coords": ["H6"],
                        "coord_roles": ["board"],
                        "instruction": "Place the output linkage.",
                        "parts": [{"part": "linkages:linkage-2-cell"}],
                        "stack": [
                            {"label": "fastener head", "order": 1, "role": "paper-fastener"},
                            {"label": "character arm", "order": 2, "role": "moving-part"},
                            {"label": "spacer", "order": 3, "role": "spacer", "part": "spacers:s8"},
                            {"label": "board", "order": 4, "role": "board"},
                        ],
                    },
                ],
            }
        ]
    }
    cover = exporter._selected_parts_checklist_svg(package)
    readme = exporter._export_readme(())

    assert "Use it like a LEGO guide book" in cover
    assert "Needed parts and hardware only" in cover
    assert "linkages:linkage-2-cell" in cover
    assert "spacers:s8" in cover
    assert "x1" in cover
    assert "Paper Fastener" in cover
    assert "{y - 2}" not in cover
    assert "assembly-guide.pdf" in readme
    assert "kit-parts-to-cut.pdf" in readme
    assert "There is no" in readme
    assert "per-step stack order" in readme


def test_physical_contract_flags_when_app_parts_do_not_match_recipe(tmp_path: Path) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)

    assert (
        exporter.resolve_app_state_to_guide(
            "four_bar",
            required_part_ids={"linkages:linkage-2-cell", "linkages:linkage-6-cell"},
        )
        is None
    )

    contract = exporter.build_app_physical_contract(
        {
            "four-bar-default": {
                "type": "four_bar",
                "params": {
                    "grid_system_enabled": True,
                    "grid_cell_cm": 2.0,
                    "ground_link": 160.0,
                    "input_link": 40.0,
                    "coupler_link": 120.0,
                    "output_link": 120.0,
                },
            }
        },
        recipe_keys={"four-bar-basic"},
    )

    assert contract["status"] == "warning"
    warnings = "\n".join(cast(list[str], contract["warnings"]))
    assert "linkages:linkage-6-cell" in warnings
    layers = cast(list[dict[str, Any]], contract["layers"])
    assert layers[0]["status"] == "warning"
    assert layers[0]["recipe_key"] is None
    assert "linkages:linkage-6-cell" in layers[0]["expected_part_ids_from_app"]


def test_physical_contract_warns_when_active_part_ids_are_not_in_selected_recipe(
    tmp_path: Path,
) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)

    assert (
        exporter.resolve_app_state_to_guide(
            "cam_follower",
            active_part_ids={"followers:f4-roller"},
        )
        is None
    )

    contract = exporter.build_app_physical_contract(
        {
            "cam": {
                "type": "cam_follower",
                "active_part_ids": ["followers:f4-roller"],
                "params": {
                    "grid_system_enabled": True,
                    "grid_cell_cm": 2.0,
                    "cam_shape": "eccentric",
                    "follower_type": "roller",
                },
            }
        },
        recipe_keys={"cam-follower-basic"},
    )

    assert contract["status"] == "warning"
    warnings = "\n".join(cast(list[str], contract["warnings"]))
    assert "followers:f4-roller" in warnings
    layers = cast(list[dict[str, Any]], contract["layers"])
    assert layers[0]["status"] == "warning"
    assert layers[0]["recipe_key"] is None
    assert layers[0]["active_part_ids_missing_from_recipe"] == ["followers:f4-roller"]


def test_physical_contract_warns_when_cam_follower_params_need_unmatched_follower(
    tmp_path: Path,
) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)
    params = {
        "grid_system_enabled": True,
        "grid_cell_cm": 2.0,
        "cam_shape": "eccentric",
        "base_radius": 15.0,
        "eccentricity": 5.0,
        "follower_type": "roller",
    }

    assert exporter.expected_part_ids_for_layer("cam_follower", params) == (
        "cams:eccentric",
        "followers:f4-roller",
    )
    assert (
        exporter.resolve_app_state_to_guide(
            "cam_follower",
            required_part_ids=exporter.expected_part_ids_for_layer("cam_follower", params),
        )
        is None
    )

    contract = exporter.build_app_physical_contract(
        {"cam": {"type": "cam_follower", "params": params}},
        recipe_keys={"cam-follower-basic"},
    )

    assert contract["status"] == "warning"
    warnings = "\n".join(cast(list[str], contract["warnings"]))
    assert "followers:f4-roller" in warnings
    layers = cast(list[dict[str, Any]], contract["layers"])
    assert layers[0]["recipe_key"] is None
    assert layers[0]["expected_part_ids_from_app"] == [
        "cams:eccentric",
        "followers:f4-roller",
    ]


def test_physical_contract_records_snap_adjustments_without_gating_recipe(
    tmp_path: Path,
) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)

    contract = exporter.build_app_physical_contract(
        {
            "four-bar-near-preset": {
                "type": "four_bar",
                "params": {
                    "grid_system_enabled": True,
                    "grid_cell_cm": 2.0,
                    "ground_link": 83.0,
                    "input_link": 38.0,
                    "coupler_link": 81.0,
                    "output_link": 42.0,
                },
            }
        },
        recipe_keys={"four-bar-basic"},
    )

    assert contract["status"] == "matched"
    assert contract["warnings"] == []
    layers = cast(list[dict[str, Any]], contract["layers"])
    assert layers[0]["status"] == "matched"
    adjustments = "\n".join(cast(list[str], layers[0]["snapped_parameter_adjustments"]))
    assert "input_link=38.0 snaps to kit value 40.0" in adjustments
    assert layers[0]["expected_part_ids_from_app"] == [
        "linkages:linkage-2-cell",
        "linkages:linkage-4-cell",
    ]


def test_active_part_ids_helper_contract_and_physical_contract_echo(tmp_path: Path) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)

    assert active_part_ids_from_layer(
        {
            "active_part_ids": ["gears:g12", "gears:g12", 42],
            "app_highlight_ids": ["ignored:lower-precedence"],
        }
    ) == ("gears:g12",)
    assert active_part_ids_from_layer({"app_highlight_ids": ["gears:g16"]}) == ("gears:g16",)
    assert active_part_ids_from_layer(
        {"fabrication": {"active_part_ids": ["linkages:linkage-4-cell"]}}
    ) == ("linkages:linkage-4-cell",)
    assert active_part_ids_from_layer({"active_part_ids": "gears:g12"}) == ()
    selection = FabricationLayerSelection.from_layer_data(
        {"source_type": "gear_train", "fabrication_part_ids": ["gears:g12"]}
    )
    assert selection.mechanism_type == "gear_train"
    assert selection.active_part_ids == ("gears:g12",)
    assert selection.active_part_ids_source == "fabrication_part_ids"

    contract = exporter.build_app_physical_contract(
        {
            "gear": {
                "type": "gear_train",
                "active_part_ids": ["gears:g12", "gears:g16"],
                "params": {
                    "grid_system_enabled": True,
                    "grid_cell_cm": 2.0,
                    "gear1_teeth": 12,
                    "gear2_teeth": 16,
                },
            }
        },
        recipe_keys={"gear-train-basic"},
    )

    layers = cast(list[dict[str, Any]], contract["layers"])
    assert layers[0]["recipe_key"] == "gear-train-basic"
    assert layers[0]["active_part_ids_from_app"] == ["gears:g12", "gears:g16"]
    assert layers[0]["active_part_ids_source"] == "active_part_ids"


def test_foundry_default_mechanisms_match_physical_recipe_parts(tmp_path: Path) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)
    configs = build_mechanism_configs()

    for summary in exporter.list_guides():
        params = dict(configs[summary.mechanism_type].initial_parameters())
        params["grid_system_enabled"] = True
        params["grid_cell_cm"] = 2.0
        contract = exporter.build_app_physical_contract(
            {
                summary.key: {
                    "type": summary.mechanism_type,
                    "params": params,
                }
            },
            recipe_keys={summary.key},
        )

        assert contract["status"] == "matched", (summary.key, contract["warnings"])


def test_exported_guides_include_physical_contract_and_quantity_aware_part_pdf(
    tmp_path: Path,
) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)
    contract = exporter.build_app_physical_contract(
        {
            "gear": {
                "type": "gear_train",
                "params": {
                    "grid_system_enabled": True,
                    "grid_cell_cm": 2.0,
                    "gear1_teeth": 12,
                    "gear2_teeth": 16,
                },
            }
        },
        recipe_keys={"gear-train-basic"},
    )

    result = exporter.export_guides(
        tmp_path / "exported-guides",
        recipe_keys={"gear-train-basic"},
        app_contract=contract,
    )

    package_dir = result.package_dir
    assert (package_dir / "physical-contract.json").is_file()
    exported_contract = _load_json(package_dir / "physical-contract.json")
    assert exported_contract["status"] == "matched"
    assert (package_dir / "kit-parts-to-cut.pdf").is_file()
    assert package_dir / "kit-parts-to-cut.pdf" in result.pdf_files
    assert result.contract_warnings == ()


def test_export_guides_surfaces_active_part_recipe_mismatch_in_contract_report(
    tmp_path: Path,
) -> None:
    write_fabrication_templates(tmp_path)
    exporter = FabricationAssemblyGuideExporter(tmp_path)
    contract = exporter.build_app_physical_contract(
        {
            "cam": {
                "type": "cam_follower",
                "active_part_ids": ["followers:f4-roller"],
                "params": {"grid_system_enabled": True, "grid_cell_cm": 2.0},
            }
        },
        recipe_keys={"cam-follower-basic"},
    )

    result = exporter.export_guides(
        tmp_path / "exported-guides",
        recipe_keys={"cam-follower-basic"},
        app_contract=contract,
    )

    exported_contract = _load_json(result.package_dir / "physical-contract.json")
    assert exported_contract["status"] == "warning"
    assert any("followers:f4-roller" in warning for warning in result.contract_warnings)


def test_multi_hole_fixed_steps_call_out_every_fastener_site(tmp_path: Path) -> None:
    manifest = write_fabrication_templates(tmp_path)
    package = _load_json(tmp_path / "assembly" / "recipes.json")

    validate_assembly_package(package, manifest)
    recipes = cast(list[dict[str, Any]], package["recipes"])
    for recipe in recipes:
        for step in cast(list[dict[str, Any]], recipe["steps"]):
            coords = cast(list[str], step["coords"])
            coord_roles = cast(list[str], step["coord_roles"])
            stack = cast(list[dict[str, Any]], step["stack"])
            stack_text = " ".join(str(layer.get("label", "")) for layer in stack)
            board_sites = [
                coord for coord, role in zip(coords, coord_roles, strict=False) if role == "board"
            ]
            if (
                step["action"] != "test-motion"
                and len(board_sites) > 1
                and any(layer["role"] == "paper-fastener" for layer in stack)
            ):
                for coord in board_sites:
                    assert coord in stack_text

    guide_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (tmp_path / "assembly").glob("*.svg")
    )
    assert "Repeat this stack at I5, I9" in guide_text
    assert "Repeat this stack at D8, H4, H12, L8" in guide_text
    assert "Repeat this stack at G11, G12, G13" in guide_text


def test_validate_assembly_package_rejects_multi_hole_fixed_step_without_all_stack_sites(
    tmp_path: Path,
) -> None:
    manifest = write_fabrication_templates(tmp_path)
    package = _load_json(tmp_path / "assembly" / "recipes.json")
    recipe = next(
        recipe
        for recipe in cast(list[dict[str, Any]], package["recipes"])
        if recipe["key"] == "four-bar-basic"
    )
    step = cast(list[dict[str, Any]], recipe["steps"])[0]
    step["stack"] = [
        layer
        for layer in cast(list[dict[str, Any]], step["stack"])
        if layer["role"] != "repeat-fastener-sites"
    ]

    with pytest.raises(AssemblyValidationError, match="omits board site"):
        validate_assembly_package(package, manifest)


def test_committed_assembly_package_exists_and_matches_generator(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    generated_root = tmp_path / "generated"
    manifest = write_fabrication_templates(generated_root)
    managed_files = cast(list[str], manifest["managed_files"])
    assert len(managed_files) == len(set(managed_files))
    for rel_path in cast(list[str], manifest["managed_files"]):
        source = generated_root / rel_path
        committed = repo_root / "fabrication" / rel_path
        assert committed.is_file(), rel_path
        assert committed.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")

    copied_root = tmp_path / "copy"
    shutil.copytree(repo_root / "fabrication" / "assembly", copied_root)
    assert (copied_root / "recipes.json").is_file()
