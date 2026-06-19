from __future__ import annotations

import json
from pathlib import Path

import pytest
from pdf_helpers import (
    assert_pdf_has_printable_pages,
    assert_pdf_page_uses_area,
    assert_pdf_pages_fit_standard_print_sheet,
)

from automataii.application.mechanism_foundry.controller import build_mechanism_configs
from automataii.presentation.qt.blueprint.exporter import BlueprintExporter


@pytest.mark.parametrize(
    ("mechanism_type", "recipe_key"),
    [
        ("four_bar", "four-bar-basic"),
        ("cam_follower", "cam-follower-basic"),
        ("gear_train", "gear-train-basic"),
        ("gear_linkage", "gear-linkage-crank"),
        ("planetary_gear", "planetary-gear-basic"),
        ("slider_crank", "slider-crank-basic"),
    ],
)
def test_export_all_writes_real_package_for_each_supported_family(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mechanism_type: str,
    recipe_key: str,
) -> None:
    from PyQt6 import QtWidgets

    output_dir = tmp_path / mechanism_type
    messages: list[tuple[str, str]] = []
    configs = build_mechanism_configs()
    params = configs[mechanism_type].initial_parameters()
    params.update({"grid_system_enabled": True, "grid_cell_cm": 2.0})
    layers = {mechanism_type: {"type": mechanism_type, "params": params}}

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(output_dir),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda _parent, title, text: messages.append((str(title), str(text))),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda _parent, title, text: messages.append((str(title), str(text))),
    )

    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=None,
        get_mechanism_layers=lambda: layers,
        get_current_editor_items=lambda: {},
        get_scene_transform_function=lambda _layer: None,
    )
    monkeypatch.setattr(
        exporter,
        "calculate_screen_to_blueprint_scale",
        lambda: {"mechanism_scale_factors": {}, "mm_per_pixel": 1.0},
    )
    monkeypatch.setattr(exporter, "enhance_mechanism_layers_with_scale_info", lambda _info: layers)

    exporter.export_all()

    assembly_dir = output_dir / "assembly"
    assert (output_dir / "current-design-cut-sheets.pdf").is_file() or (
        output_dir / "current-design-cut-sheets.svg"
    ).is_file()
    if (output_dir / "current-design-cut-sheets.pdf").is_file():
        assert_pdf_has_printable_pages(output_dir / "current-design-cut-sheets.pdf")
        assert_pdf_page_uses_area(output_dir / "current-design-cut-sheets.pdf")
    assert (assembly_dir / "recipes.json").is_file()
    assert (assembly_dir / "physical-contract.json").is_file()
    assert (assembly_dir / "assembly-guide.pdf").is_file() or (
        assembly_dir / "svg-fallback" / "assembly"
    ).is_dir()
    if (assembly_dir / "assembly-guide.pdf").is_file():
        assert_pdf_has_printable_pages(assembly_dir / "assembly-guide.pdf")
        assert_pdf_pages_fit_standard_print_sheet(assembly_dir / "assembly-guide.pdf")
        assert_pdf_page_uses_area(
            assembly_dir / "assembly-guide.pdf", min_width_ratio=0.55, min_height_ratio=0.35
        )
    assert (assembly_dir / "kit-parts-to-cut.pdf").is_file() or (
        assembly_dir / "svg-fallback" / "parts"
    ).is_dir()
    if (assembly_dir / "kit-parts-to-cut.pdf").is_file():
        assert_pdf_has_printable_pages(assembly_dir / "kit-parts-to-cut.pdf")
        assert_pdf_pages_fit_standard_print_sheet(assembly_dir / "kit-parts-to-cut.pdf")

    recipes = json.loads((assembly_dir / "recipes.json").read_text(encoding="utf-8"))
    assert [recipe["key"] for recipe in recipes["recipes"]] == [recipe_key]
    contract = json.loads((assembly_dir / "physical-contract.json").read_text(encoding="utf-8"))
    assert contract["selected_recipe_keys"] == [recipe_key]
    assert messages
    assert recipe_key in messages[-1][1]


def test_export_all_writes_integrated_pdf_manuals_for_multiple_supported_mechanisms(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from PyQt6 import QtWidgets

    expected_recipes = {
        "four-bar-basic",
        "cam-follower-basic",
        "gear-train-basic",
        "gear-linkage-crank",
        "planetary-gear-basic",
        "slider-crank-basic",
    }
    output_dir = tmp_path / "all-supported-mechanisms"
    messages: list[tuple[str, str]] = []
    configs = build_mechanism_configs()
    layers = {}
    for mechanism_type in (
        "four_bar",
        "cam_follower",
        "gear_train",
        "gear_linkage",
        "planetary_gear",
        "slider_crank",
    ):
        params = configs[mechanism_type].initial_parameters()
        params.update({"grid_system_enabled": True, "grid_cell_cm": 2.0})
        layers[f"{mechanism_type}-layer"] = {"type": mechanism_type, "params": params}

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(output_dir),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda _parent, title, text: messages.append((str(title), str(text))),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda _parent, title, text: messages.append((str(title), str(text))),
    )

    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=None,
        get_mechanism_layers=lambda: layers,
        get_current_editor_items=lambda: {},
        get_scene_transform_function=lambda _layer: None,
    )
    monkeypatch.setattr(
        exporter,
        "calculate_screen_to_blueprint_scale",
        lambda: {"mechanism_scale_factors": {}, "mm_per_pixel": 1.0},
    )
    monkeypatch.setattr(exporter, "enhance_mechanism_layers_with_scale_info", lambda _info: layers)

    exporter.export_all()

    cut_sheet = output_dir / "current-design-cut-sheets.pdf"
    assembly_dir = output_dir / "assembly"
    assert cut_sheet.is_file()
    assert_pdf_has_printable_pages(cut_sheet)
    assert_pdf_page_uses_area(cut_sheet)
    assert not (assembly_dir / "svg-fallback").exists()
    assert (assembly_dir / "assembly-guide.pdf").is_file()
    assert (assembly_dir / "kit-parts-to-cut.pdf").is_file()
    assert (assembly_dir / "recipes.json").is_file()
    assert (assembly_dir / "physical-contract.json").is_file()

    recipes = json.loads((assembly_dir / "recipes.json").read_text(encoding="utf-8"))
    assert {recipe["key"] for recipe in recipes["recipes"]} == expected_recipes
    expected_guide_pages = 3 + sum(len(recipe["steps"]) for recipe in recipes["recipes"])
    assert_pdf_has_printable_pages(
        assembly_dir / "assembly-guide.pdf",
        expected_pages=expected_guide_pages,
    )
    assert_pdf_pages_fit_standard_print_sheet(
        assembly_dir / "assembly-guide.pdf",
        expected_pages=expected_guide_pages,
    )
    assert_pdf_page_uses_area(
        assembly_dir / "assembly-guide.pdf",
        min_width_ratio=0.55,
        min_height_ratio=0.35,
    )
    assert_pdf_has_printable_pages(assembly_dir / "kit-parts-to-cut.pdf")
    assert_pdf_pages_fit_standard_print_sheet(assembly_dir / "kit-parts-to-cut.pdf")

    contract = json.loads((assembly_dir / "physical-contract.json").read_text(encoding="utf-8"))
    assert contract["status"] == "matched"
    assert set(contract["selected_recipe_keys"]) == expected_recipes
    assert messages
    assert "PDF-first blueprint package exported successfully" in messages[-1][1]


class _PartInfo:
    def __init__(self, *, name: str, roi: list[float], image_path: str, pivot: list[float]) -> None:
        self.name = name
        self.roi = roi
        self.image_path = image_path
        self.x = roi[0]
        self.y = roi[1]
        self.local_pivot_offset = pivot
        self.effective_bbox_offset_x = 0.0
        self.effective_bbox_offset_y = 0.0


class _PartItem:
    def __init__(self, part_info: _PartInfo) -> None:
        self.part_info = part_info

    def shape(self) -> object:
        return object()


def test_export_all_combines_character_cut_sheet_with_board_assembly_package(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from PyQt6 import QtWidgets

    output_dir = tmp_path / "character-and-four-bar"
    dummy_dir = Path("resources/presets/characters/dummy")
    torso = _PartItem(
        _PartInfo(
            name="torso",
            roi=[610.0, 230.0, 316.0, 372.0],
            image_path=str(dummy_dir / "torso.png"),
            pivot=[158.0, 140.0],
        )
    )
    head = _PartItem(
        _PartInfo(
            name="head",
            roi=[686.0, 54.0, 164.0, 190.0],
            image_path=str(dummy_dir / "head.png"),
            pivot=[82.0, 186.0],
        )
    )

    configs = build_mechanism_configs()
    params = configs["four_bar"].initial_parameters()
    params.update({"grid_system_enabled": True, "grid_cell_cm": 2.0})
    layers = {"four_bar": {"type": "four_bar", "params": params}}
    messages: list[tuple[str, str]] = []

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(output_dir),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda _parent, title, text: messages.append((str(title), str(text))),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda _parent, title, text: messages.append((str(title), str(text))),
    )

    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=None,
        get_mechanism_layers=lambda: layers,
        get_current_editor_items=lambda: {"torso": torso, "head": head},
        get_scene_transform_function=lambda _layer: None,
        get_blueprint_export_format=lambda: "svg",
    )
    monkeypatch.setattr(
        exporter,
        "calculate_screen_to_blueprint_scale",
        lambda: {"mechanism_scale_factors": {}, "mm_per_pixel": 1.0},
    )
    monkeypatch.setattr(exporter, "enhance_mechanism_layers_with_scale_info", lambda _info: layers)

    exporter.export_all()

    cut_sheet = output_dir / "current-design-cut-sheets.svg"
    assert cut_sheet.is_file()
    cut_sheet_text = cut_sheet.read_text(encoding="utf-8")
    assert "Character body component cut sheets" in cut_sheet_text
    assert "pivot-drill-hole" in cut_sheet_text
    assert 'data-hole-diameter-mm="4"' in cut_sheet_text
    assert "assembly-guide.pdf" in cut_sheet_text
    assert (output_dir / "assembly" / "assembly-guide.pdf").is_file()
    assert (output_dir / "assembly" / "kit-parts-to-cut.pdf").is_file()
    contract = json.loads(
        (output_dir / "assembly" / "physical-contract.json").read_text(encoding="utf-8")
    )
    assert contract["status"] == "matched"
    assert contract["selected_recipe_keys"] == ["four-bar-basic"]
    assert messages
    assert "Blueprint package exported successfully with SVG cut sheet" in messages[-1][1]


def test_export_all_writes_contract_report_when_app_selected_parts_have_no_board_recipe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from PyQt6 import QtWidgets

    output_dir = tmp_path / "mismatched-active-part"
    layers = {
        "cam": {
            "type": "cam_follower",
            "active_part_ids": ["followers:f4-roller"],
            "params": {
                "grid_system_enabled": True,
                "grid_cell_cm": 2.0,
                "cam_shape": "eccentric",
                "base_radius": 15.0,
                "eccentricity": 5.0,
                "follower_type": "roller",
            },
        }
    }
    messages: list[tuple[str, str]] = []

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(output_dir),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda _parent, title, text: messages.append((str(title), str(text))),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda _parent, title, text: messages.append((str(title), str(text))),
    )

    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=None,
        get_mechanism_layers=lambda: layers,
        get_current_editor_items=lambda: {},
        get_scene_transform_function=lambda _layer: None,
        get_blueprint_export_format=lambda: "svg",
    )
    monkeypatch.setattr(
        exporter,
        "calculate_screen_to_blueprint_scale",
        lambda: {"mechanism_scale_factors": {}, "mm_per_pixel": 1.0},
    )
    monkeypatch.setattr(exporter, "enhance_mechanism_layers_with_scale_info", lambda _info: layers)

    exporter.export_all()

    assert (output_dir / "current-design-cut-sheets.svg").is_file()
    assembly_dir = output_dir / "assembly"
    assert (assembly_dir / "physical-contract.json").is_file()
    assert not (assembly_dir / "assembly-guide.pdf").exists()
    assert not (assembly_dir / "kit-parts-to-cut.pdf").exists()
    contract = json.loads((assembly_dir / "physical-contract.json").read_text(encoding="utf-8"))
    assert contract["status"] == "warning"
    assert contract["selected_recipe_keys"] == []
    assert any("followers:f4-roller" in warning for warning in contract["warnings"])
    assert messages
    assert messages[-1][0] == "Blueprint Package Exported with Contract Warnings"
    assert "Physical contract: assembly/physical-contract.json" in messages[-1][1]
    assert "Assembly PDFs: none" in messages[-1][1]


def test_export_all_writes_contract_report_when_cam_follower_params_need_unmatched_follower(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from PyQt6 import QtWidgets

    output_dir = tmp_path / "roller-follower-param"
    layers = {
        "cam": {
            "type": "cam_follower",
            "params": {
                "grid_system_enabled": True,
                "grid_cell_cm": 2.0,
                "cam_shape": "eccentric",
                "follower_type": "roller",
            },
        }
    }
    messages: list[tuple[str, str]] = []

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(output_dir),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda _parent, title, text: messages.append((str(title), str(text))),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda _parent, title, text: messages.append((str(title), str(text))),
    )

    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=None,
        get_mechanism_layers=lambda: layers,
        get_current_editor_items=lambda: {},
        get_scene_transform_function=lambda _layer: None,
        get_blueprint_export_format=lambda: "svg",
    )
    monkeypatch.setattr(
        exporter,
        "calculate_screen_to_blueprint_scale",
        lambda: {"mechanism_scale_factors": {}, "mm_per_pixel": 1.0},
    )
    monkeypatch.setattr(exporter, "enhance_mechanism_layers_with_scale_info", lambda _info: layers)

    exporter.export_all()

    assembly_dir = output_dir / "assembly"
    assert (output_dir / "current-design-cut-sheets.svg").is_file()
    assert (assembly_dir / "physical-contract.json").is_file()
    assert not (assembly_dir / "assembly-guide.pdf").exists()
    assert not (assembly_dir / "kit-parts-to-cut.pdf").exists()
    contract = json.loads((assembly_dir / "physical-contract.json").read_text(encoding="utf-8"))
    assert contract["status"] == "warning"
    assert contract["selected_recipe_keys"] == []
    assert any("followers:f4-roller" in warning for warning in contract["warnings"])
    assert messages[-1][0] == "Blueprint Package Exported with Contract Warnings"
    assert "Assembly PDFs: none" in messages[-1][1]


def test_export_all_writes_contract_only_when_snapped_params_do_not_match_recipe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from PyQt6 import QtWidgets

    output_dir = tmp_path / "four-bar-custom-linkage"
    layers = {
        "four_bar": {
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
    }
    messages: list[tuple[str, str]] = []

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(output_dir),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda _parent, title, text: messages.append((str(title), str(text))),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda _parent, title, text: messages.append((str(title), str(text))),
    )

    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=None,
        get_mechanism_layers=lambda: layers,
        get_current_editor_items=lambda: {},
        get_scene_transform_function=lambda _layer: None,
        get_blueprint_export_format=lambda: "svg",
    )
    monkeypatch.setattr(
        exporter,
        "calculate_screen_to_blueprint_scale",
        lambda: {"mechanism_scale_factors": {}, "mm_per_pixel": 1.0},
    )
    monkeypatch.setattr(exporter, "enhance_mechanism_layers_with_scale_info", lambda _info: layers)

    exporter.export_all()

    assembly_dir = output_dir / "assembly"
    assert (output_dir / "current-design-cut-sheets.svg").is_file()
    assert (assembly_dir / "physical-contract.json").is_file()
    assert not (assembly_dir / "assembly-guide.pdf").exists()
    assert not (assembly_dir / "kit-parts-to-cut.pdf").exists()
    contract = json.loads((assembly_dir / "physical-contract.json").read_text(encoding="utf-8"))
    assert contract["status"] == "warning"
    assert contract["selected_recipe_keys"] == []
    assert any("linkages:linkage-6-cell" in warning for warning in contract["warnings"])
    assert messages
    assert messages[-1][0] == "Blueprint Package Exported with Contract Warnings"
    assert "Assembly PDFs: none" in messages[-1][1]
