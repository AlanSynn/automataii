from __future__ import annotations

import inspect
from pathlib import Path

from automataii.application.fabrication import FabricationGuideExportResult, FabricationGuideSummary
from automataii.application.managers import BlueprintExportResult
from automataii.presentation.qt.blueprint.exporter import BlueprintExporter


def test_blueprint_export_success_copy_is_production_facing() -> None:
    source = inspect.getsource(BlueprintExporter)

    assert "Fixed:" not in source
    assert "screen-calculated dimensions instead of defaults" not in source
    assert "Blueprint exported successfully" in source
    assert "Blueprint Package Exported" in source


def test_blueprint_package_does_not_gate_board_assembly_for_contract_warnings() -> None:
    source = inspect.getsource(BlueprintExporter)

    assert "fallback_files" in source
    assert "Blueprint Package Exported with Contract Warnings" in source
    assert "gated by physical contract warnings" not in source


def test_blueprint_package_accepts_svg_fallback_assembly_export(
    monkeypatch, tmp_path: Path
) -> None:
    from PyQt6 import QtWidgets

    import automataii.application.fabrication as fabrication_pkg
    from automataii.application.managers import BlueprintExportManager

    captured: dict[str, str] = {}

    def fake_directory(*_args, **_kwargs) -> str:
        return str(tmp_path / "export")

    def fake_information(_parent, title: str, text: str) -> None:
        captured["kind"] = "information"
        captured["title"] = title
        captured["text"] = text

    def fake_warning(_parent, title: str, text: str) -> None:
        captured["kind"] = "warning"
        captured["title"] = title
        captured["text"] = text

    class FakeBlueprintManager:
        def export_blueprint_to_path(self, *, file_path: Path, **_kwargs) -> bool:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("%PDF-1.4\n", encoding="utf-8")
            return True

    class FakeGuideExporter:
        def __init__(self, _root: str) -> None:
            pass

        def resolve_app_state_to_guide(self, _mechanism_type, **_kwargs):
            return FabricationGuideSummary(
                key="gear-train-basic",
                title="Gear train",
                mechanism_type="gear_train",
                guide_svg="assembly/01-gear-train-basic.svg",
                step_count=4,
                app_mechanism_type="gear_train",
                app_highlight_ids=("gears:g12",),
            )

        def build_app_physical_contract(self, _mechanism_layers, *, recipe_keys):
            return {
                "status": "matched",
                "warnings": [],
                "selected_recipe_keys": sorted(recipe_keys),
            }

        def export_guides(self, output_dir, *, recipe_keys, app_contract):
            package_dir = Path(output_dir) / "assembly"
            fallback = package_dir / "svg-fallback" / "assembly" / "01-checklist.svg"
            fallback.parent.mkdir(parents=True, exist_ok=True)
            fallback.write_text("<svg />", encoding="utf-8")
            return FabricationGuideExportResult(
                output_dir=Path(output_dir),
                package_dir=package_dir,
                copied_files=(fallback,),
                recipe_keys=tuple(sorted(recipe_keys)),
                pdf_files=(),
                fallback_files=(fallback,),
                contract_warnings=(),
            )

    monkeypatch.setattr(QtWidgets.QFileDialog, "getExistingDirectory", fake_directory)
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", fake_information)
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", fake_warning)
    monkeypatch.setattr(
        BlueprintExportManager, "get_instance", staticmethod(lambda: FakeBlueprintManager())
    )
    monkeypatch.setattr(fabrication_pkg, "FabricationAssemblyGuideExporter", FakeGuideExporter)

    layer = {"gear": {"type": "gear_train", "params": {"grid_system_enabled": True}}}
    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=None,
        get_mechanism_layers=lambda: layer,
        get_current_editor_items=lambda: {},
        get_scene_transform_function=lambda _layer: None,
    )
    monkeypatch.setattr(exporter, "_collect_part_items", lambda: [])
    monkeypatch.setattr(
        exporter,
        "calculate_screen_to_blueprint_scale",
        lambda: {"mechanism_scale_factors": {}, "mm_per_pixel": 1.0},
    )
    monkeypatch.setattr(exporter, "enhance_mechanism_layers_with_scale_info", lambda _info: layer)

    exporter.export_all()

    assert captured["kind"] == "information"
    assert captured["title"] == "Blueprint Package Exported"
    assert "SVG fallback generated" in captured["text"]
    assert "Blueprint Package Export Failed" not in captured["title"]


def test_blueprint_package_snaps_layers_before_physical_contract(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from PyQt6 import QtWidgets

    import automataii.application.fabrication as fabrication_pkg
    from automataii.application.managers import BlueprintExportManager

    output_dir = tmp_path / "export"
    seen_params: dict[str, object] = {}
    seen_real_world_params: dict[str, object] = {}
    captured: dict[str, str] = {}

    class FakeBlueprintManager:
        def export_blueprint_to_path(self, *, file_path: Path, **_kwargs) -> bool:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("%PDF-1.4\n", encoding="utf-8")
            return True

    class FakeGuideExporter:
        def __init__(self, _root: str) -> None:
            pass

        def resolve_app_state_to_guide(self, _mechanism_type, **_kwargs):
            return FabricationGuideSummary(
                key="four-bar-basic",
                title="Four-bar linkage",
                mechanism_type="four_bar",
                guide_svg="assembly/03-four-bar-basic.svg",
                step_count=5,
                app_mechanism_type="four_bar",
                app_highlight_ids=("linkages:linkage-2-cell", "linkages:linkage-4-cell"),
            )

        def build_app_physical_contract(self, mechanism_layers, *, recipe_keys):
            seen_params.update(mechanism_layers["four"]["params"])
            seen_real_world_params.update(mechanism_layers["four"]["real_world_params"])
            return {
                "status": "matched",
                "warnings": [],
                "selected_recipe_keys": sorted(recipe_keys),
            }

        def export_guides(self, output_dir_arg, *, recipe_keys, app_contract):
            package_dir = Path(output_dir_arg) / "assembly"
            pdf = package_dir / "assembly-guide.pdf"
            pdf.parent.mkdir(parents=True, exist_ok=True)
            pdf.write_text("%PDF-1.4\n", encoding="utf-8")
            return FabricationGuideExportResult(
                output_dir=Path(output_dir_arg),
                package_dir=package_dir,
                copied_files=(pdf,),
                recipe_keys=tuple(sorted(recipe_keys)),
                pdf_files=(pdf,),
                fallback_files=(),
                contract_warnings=(),
            )

    layer = {
        "four": {
            "type": "4_bar_linkage",
            "params": {
                "grid_system_enabled": False,
                "grid_cell_cm": 2.0,
                "l1": 83.0,
                "l2": 38.0,
                "l3": 81.0,
                "l4": 42.0,
            },
        }
    }
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(output_dir),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda _parent, title, text: captured.update({"title": title, "text": text}),
    )
    monkeypatch.setattr(
        BlueprintExportManager, "get_instance", staticmethod(lambda: FakeBlueprintManager())
    )
    monkeypatch.setattr(fabrication_pkg, "FabricationAssemblyGuideExporter", FakeGuideExporter)

    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=None,
        get_mechanism_layers=lambda: layer,
        get_current_editor_items=lambda: {},
        get_scene_transform_function=lambda _layer: None,
    )
    monkeypatch.setattr(exporter, "_collect_part_items", lambda: [])
    monkeypatch.setattr(
        exporter,
        "calculate_screen_to_blueprint_scale",
        lambda: {"mechanism_scale_factors": {}, "mm_per_pixel": 1.0},
    )
    monkeypatch.setattr(exporter, "enhance_mechanism_layers_with_scale_info", lambda _info: layer)

    exporter.export_all()

    assert seen_params["grid_system_enabled"] is True
    assert seen_params["l1"] == 80.0
    assert seen_params["l2"] == 40.0
    assert seen_params["l3"] == 80.0
    assert seen_params["l4"] == 40.0
    assert seen_real_world_params["l1_mm"] == 80.0
    assert seen_real_world_params["l2_mm"] == 40.0
    assert seen_real_world_params["l3_mm"] == 80.0
    assert seen_real_world_params["l4_mm"] == 40.0
    assert seen_real_world_params["mechanism_type"] == "4_bar_linkage"
    assert captured["title"] == "Blueprint Package Exported"
    assert "Assembly guide: assembly/assembly-guide.pdf" in captured["text"]


def test_blueprint_package_still_exports_assembly_pdf_with_contract_warnings(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from PyQt6 import QtWidgets

    import automataii.application.fabrication as fabrication_pkg
    from automataii.application.managers import BlueprintExportManager

    output_dir = tmp_path / "export"
    captured: dict[str, str] = {}
    export_called: dict[str, str] = {}

    class FakeBlueprintManager:
        def export_blueprint_to_path(self, *, file_path: Path, **_kwargs) -> bool:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("%PDF-1.4\n", encoding="utf-8")
            return True

    class FakeGuideExporter:
        def __init__(self, _root: str) -> None:
            pass

        def resolve_app_state_to_guide(self, _mechanism_type, **_kwargs):
            return FabricationGuideSummary(
                key="four-bar-basic",
                title="Four-bar linkage",
                mechanism_type="four_bar",
                guide_svg="assembly/03-four-bar-basic.svg",
                step_count=5,
                app_mechanism_type="four_bar",
                app_highlight_ids=("linkages:linkage-4-cell",),
            )

        def build_app_physical_contract(self, _mechanism_layers, *, recipe_keys):
            return {
                "status": "warning",
                "warnings": ["four: snapped to nearest board preset"],
                "selected_recipe_keys": sorted(recipe_keys),
            }

        def export_guides(self, output_dir_arg, *, recipe_keys, app_contract):
            export_called["yes"] = "yes"
            package_dir = Path(output_dir_arg) / "assembly"
            pdf = package_dir / "assembly-guide.pdf"
            pdf.parent.mkdir(parents=True, exist_ok=True)
            pdf.write_text("%PDF-1.4\n", encoding="utf-8")
            return FabricationGuideExportResult(
                output_dir=Path(output_dir_arg),
                package_dir=package_dir,
                copied_files=(pdf,),
                recipe_keys=tuple(sorted(recipe_keys)),
                pdf_files=(pdf,),
                fallback_files=(),
                contract_warnings=tuple(app_contract["warnings"]),
            )

    layer = {"four": {"type": "4_bar_linkage", "params": {"grid_system_enabled": True}}}
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(output_dir),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda _parent, title, text: captured.update({"title": title, "text": text}),
    )
    monkeypatch.setattr(
        BlueprintExportManager, "get_instance", staticmethod(lambda: FakeBlueprintManager())
    )
    monkeypatch.setattr(fabrication_pkg, "FabricationAssemblyGuideExporter", FakeGuideExporter)

    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=None,
        get_mechanism_layers=lambda: layer,
        get_current_editor_items=lambda: {},
        get_scene_transform_function=lambda _layer: None,
    )
    monkeypatch.setattr(exporter, "_collect_part_items", lambda: [])
    monkeypatch.setattr(
        exporter,
        "calculate_screen_to_blueprint_scale",
        lambda: {"mechanism_scale_factors": {}, "mm_per_pixel": 1.0},
    )
    monkeypatch.setattr(exporter, "enhance_mechanism_layers_with_scale_info", lambda _info: layer)

    exporter.export_all()

    assert export_called["yes"] == "yes"
    assert captured["title"] == "Blueprint Package Exported with Contract Warnings"
    assert "Assembly guide: assembly/assembly-guide.pdf" in captured["text"]
    assert "Assembly PDFs: 1" in captured["text"]


def test_blueprint_package_clears_stale_assembly_when_no_recipe_matches(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from PyQt6 import QtWidgets

    import automataii.application.fabrication as fabrication_pkg
    from automataii.application.managers import BlueprintExportManager

    output_dir = tmp_path / "export"
    stale_pdf = output_dir / "assembly" / "assembly-guide.pdf"
    stale_pdf.parent.mkdir(parents=True, exist_ok=True)
    stale_pdf.write_text("stale", encoding="utf-8")
    captured: dict[str, str] = {}

    class FakeBlueprintManager:
        def export_blueprint_to_path(self, *, file_path: Path, **_kwargs) -> bool:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("%PDF-1.4\n", encoding="utf-8")
            return True

    class FakeGuideExporter:
        def __init__(self, _root: str) -> None:
            pass

        def resolve_app_state_to_guide(self, _mechanism_type, **_kwargs):
            return None

        def build_app_physical_contract(self, _mechanism_layers, *, recipe_keys):
            return {
                "status": "matched",
                "warnings": [],
                "selected_recipe_keys": sorted(recipe_keys),
            }

        def export_contract_report(self, output_dir_arg, _contract):
            package_dir = Path(output_dir_arg) / "assembly"
            captured["contract_report_called"] = "yes"
            for path in package_dir.glob("*"):
                if path.is_file():
                    path.unlink()
            contract_path = package_dir / "physical-contract.json"
            contract_path.write_text("{}", encoding="utf-8")
            return contract_path

        def clear_exported_package(self, output_dir_arg):
            package_dir = Path(output_dir_arg) / "assembly"
            captured["clear_called"] = "yes"
            return package_dir

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(output_dir),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda _parent, title, text: captured.update({"title": title, "text": text}),
    )
    monkeypatch.setattr(
        BlueprintExportManager, "get_instance", staticmethod(lambda: FakeBlueprintManager())
    )
    monkeypatch.setattr(fabrication_pkg, "FabricationAssemblyGuideExporter", FakeGuideExporter)

    layer = {"unsupported": {"type": "unsupported_custom", "params": {}}}
    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=None,
        get_mechanism_layers=lambda: layer,
        get_current_editor_items=lambda: {},
        get_scene_transform_function=lambda _layer: None,
    )
    monkeypatch.setattr(exporter, "_collect_part_items", lambda: [])
    monkeypatch.setattr(
        exporter,
        "calculate_screen_to_blueprint_scale",
        lambda: {"mechanism_scale_factors": {}, "mm_per_pixel": 1.0},
    )
    monkeypatch.setattr(exporter, "enhance_mechanism_layers_with_scale_info", lambda _info: layer)

    exporter.export_all()

    assert captured["contract_report_called"] == "yes"
    assert not stale_pdf.exists()
    assert captured["title"] == "Blueprint Package Exported"
    assert "Assembly guide: not generated" in captured["text"]
    assert "Physical contract: assembly/physical-contract.json" in captured["text"]


def test_blueprint_package_cleans_stale_cut_sheet_svg_before_pdf_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from PyQt6 import QtWidgets

    import automataii.application.fabrication as fabrication_pkg
    from automataii.application.managers import BlueprintExportManager

    output_dir = tmp_path / "export"
    stale_svg = output_dir / "current-design-cut-sheets.svg"
    stale_svg.parent.mkdir(parents=True)
    stale_svg.write_text("<svg>stale</svg>", encoding="utf-8")
    captured: dict[str, str] = {}

    class FakeBlueprintManager:
        def export_blueprint_to_path(self, *, file_path: Path, **_kwargs) -> BlueprintExportResult:
            assert not stale_svg.exists()
            pdf_path = file_path.with_suffix(".pdf")
            pdf_path.write_text("%PDF-1.4\n", encoding="utf-8")
            return BlueprintExportResult(
                success=True,
                requested_format="pdf",
                actual_format="pdf",
                path=pdf_path,
            )

    class FakeGuideExporter:
        def __init__(self, _root: str) -> None:
            pass

        def resolve_app_state_to_guide(self, _mechanism_type, **_kwargs):
            return None

        def build_app_physical_contract(self, _mechanism_layers, *, recipe_keys):
            return {
                "status": "matched",
                "warnings": [],
                "selected_recipe_keys": sorted(recipe_keys),
            }

        def export_contract_report(self, output_dir_arg, _contract):
            package_dir = Path(output_dir_arg) / "assembly"
            package_dir.mkdir(parents=True, exist_ok=True)
            contract_path = package_dir / "physical-contract.json"
            contract_path.write_text("{}", encoding="utf-8")
            return contract_path

        def clear_exported_package(self, output_dir_arg):
            package_dir = Path(output_dir_arg) / "assembly"
            package_dir.mkdir(parents=True, exist_ok=True)
            return package_dir

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(output_dir),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda _parent, title, text: captured.update({"title": title, "text": text}),
    )
    monkeypatch.setattr(
        BlueprintExportManager, "get_instance", staticmethod(lambda: FakeBlueprintManager())
    )
    monkeypatch.setattr(fabrication_pkg, "FabricationAssemblyGuideExporter", FakeGuideExporter)

    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=None,
        get_mechanism_layers=lambda: {"unsupported": {"type": "unsupported_custom"}},
        get_current_editor_items=lambda: {},
        get_scene_transform_function=lambda _layer: None,
    )
    monkeypatch.setattr(exporter, "_collect_part_items", lambda: [])
    monkeypatch.setattr(
        exporter,
        "calculate_screen_to_blueprint_scale",
        lambda: {"mechanism_scale_factors": {}, "mm_per_pixel": 1.0},
    )
    monkeypatch.setattr(
        exporter,
        "enhance_mechanism_layers_with_scale_info",
        lambda _info: {"unsupported": {"type": "unsupported_custom"}},
    )

    exporter.export_all()

    assert captured["title"] == "Blueprint Package Exported"
    assert "PDF-first blueprint package exported successfully" in captured["text"]
    assert "Current design cut sheet: current-design-cut-sheets.pdf" in captured["text"]
    assert not stale_svg.exists()


def test_blueprint_package_reports_svg_selected_cut_sheet(monkeypatch, tmp_path: Path) -> None:
    from PyQt6 import QtWidgets

    import automataii.application.fabrication as fabrication_pkg
    from automataii.application.managers import BlueprintExportManager

    output_dir = tmp_path / "export"
    captured: dict[str, str] = {}

    class FakeBlueprintManager:
        def export_blueprint_to_path(self, *, file_path: Path, **_kwargs) -> BlueprintExportResult:
            svg_path = file_path.with_suffix(".svg")
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            svg_path.write_text("<svg />", encoding="utf-8")
            return BlueprintExportResult(
                success=True,
                requested_format="svg",
                actual_format="svg",
                path=svg_path,
            )

    class FakeGuideExporter:
        def __init__(self, _root: str) -> None:
            pass

        def resolve_app_state_to_guide(self, _mechanism_type, **_kwargs):
            return None

        def build_app_physical_contract(self, _mechanism_layers, *, recipe_keys):
            return {
                "status": "matched",
                "warnings": [],
                "selected_recipe_keys": sorted(recipe_keys),
            }

        def export_contract_report(self, output_dir_arg, _contract):
            package_dir = Path(output_dir_arg) / "assembly"
            package_dir.mkdir(parents=True, exist_ok=True)
            contract_path = package_dir / "physical-contract.json"
            contract_path.write_text("{}", encoding="utf-8")
            return contract_path

        def clear_exported_package(self, output_dir_arg):
            package_dir = Path(output_dir_arg) / "assembly"
            package_dir.mkdir(parents=True, exist_ok=True)
            return package_dir

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(output_dir),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda _parent, title, text: captured.update({"title": title, "text": text}),
    )
    monkeypatch.setattr(
        BlueprintExportManager, "get_instance", staticmethod(lambda: FakeBlueprintManager())
    )
    monkeypatch.setattr(fabrication_pkg, "FabricationAssemblyGuideExporter", FakeGuideExporter)

    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=None,
        get_mechanism_layers=lambda: {"unsupported": {"type": "unsupported_custom"}},
        get_current_editor_items=lambda: {},
        get_scene_transform_function=lambda _layer: None,
        get_blueprint_export_format=lambda: "svg",
    )
    monkeypatch.setattr(exporter, "_collect_part_items", lambda: [])
    monkeypatch.setattr(
        exporter,
        "calculate_screen_to_blueprint_scale",
        lambda: {"mechanism_scale_factors": {}, "mm_per_pixel": 1.0},
    )
    monkeypatch.setattr(
        exporter,
        "enhance_mechanism_layers_with_scale_info",
        lambda _info: {"unsupported": {"type": "unsupported_custom"}},
    )

    exporter.export_all()

    assert captured["title"] == "Blueprint Package Exported"
    assert "Blueprint package exported successfully with SVG cut sheet" in captured["text"]
    assert "PDF-first blueprint package exported successfully" not in captured["text"]
    assert "Current design cut sheet: current-design-cut-sheets.svg" in captured["text"]


def test_recipe_selection_passes_active_part_ids_to_guide_resolver() -> None:
    seen: dict[str, tuple[str, ...]] = {}

    class FakeGuideExporter:
        def resolve_app_state_to_guide(self, mechanism_type, *, active_part_ids=()):
            seen[str(mechanism_type)] = tuple(active_part_ids)
            if "linkages:linkage-4-cell" not in active_part_ids:
                return None
            return FabricationGuideSummary(
                key="gear-linkage-crank",
                title="Gear linkage",
                mechanism_type="gear_linkage",
                guide_svg="assembly/04-gear-linkage-crank.svg",
                step_count=4,
                app_mechanism_type="gear_linkage",
                app_highlight_ids=("linkages:linkage-4-cell",),
            )

    exporter = BlueprintExporter.__new__(BlueprintExporter)

    recipe_keys = exporter._assembly_recipe_keys_for_layers(  # type: ignore[attr-defined]
        FakeGuideExporter(),
        {
            "gear-link": {
                "type": "gear_linkage",
                "active_part_ids": ["linkages:linkage-4-cell"],
            }
        },
    )

    assert recipe_keys == {"gear-linkage-crank"}
    assert seen["gear_linkage"] == ("linkages:linkage-4-cell",)


def test_real_world_param_conversion_normalizes_fabrication_aliases() -> None:
    exporter = BlueprintExporter.__new__(BlueprintExporter)

    gear = exporter.calculate_real_world_mechanism_params(  # type: ignore[attr-defined]
        {"gear1_radius": 18.0, "gear2_radius": 21.0},
        2.0,
        "gear_train",
    )
    cam = exporter.calculate_real_world_mechanism_params(  # type: ignore[attr-defined]
        {"cam_radius": 20.0, "cam_offset": 4.0},
        1.5,
        "cam_follower",
    )
    gear_linkage = exporter.calculate_real_world_mechanism_params(  # type: ignore[attr-defined]
        {"gear1_radius": 18.0, "gear2_radius": 21.0, "linkage_arm_length": 80.0},
        1.0,
        "gear_linkage",
    )

    assert gear["mechanism_type"] == "gear"
    assert gear["r1_mm"] == 36.0
    assert gear["r2_mm"] == 42.0
    assert cam["mechanism_type"] == "cam"
    assert cam["base_radius_mm"] == 30.0
    assert cam["eccentricity_mm"] == 6.0
    assert gear_linkage["mechanism_type"] == "gear_linkage"
    assert gear_linkage["arm_length_mm"] == 80.0


def test_cam_blueprint_instructions_are_parameter_driven() -> None:
    exporter = BlueprintExporter.__new__(BlueprintExporter)

    instructions = exporter.generate_blueprint_instructions(
        "cam",
        {
            "base_radius_mm": 22.0,
            "lift_mm": 7.0,
            "follower_length": 50.0,
            "cam_lobes": 3,
            "profile_harmonic": 0.6,
        },
        scale_factor=1.0,
    )

    assert "Draw egg-shaped profile" not in instructions
    assert "Maximum radius" not in instructions
    assert "Minimum radius" not in instructions
    assert "generated CAM profile" in instructions
    assert "Base radius/reference: 22.0 mm" in instructions
    assert "Lift/eccentricity input: 7.0 mm" in instructions
    assert "Lobes: 3" in instructions
    assert "Harmonic: 0.60" in instructions


def test_gear_blueprint_instructions_preserve_grid_disabled_freeform_teeth() -> None:
    exporter = BlueprintExporter.__new__(BlueprintExporter)

    instructions = exporter.generate_blueprint_instructions(
        "gear",
        {
            "grid_system_enabled": False,
            "r1": 36.0,
            "r2": 54.0,
            "gear1_teeth": 12,
            "gear2_teeth": 18,
            "gear_clearance": 4.0,
        },
        scale_factor=1.0,
    )

    assert "Estimated teeth: 12" in instructions
    assert "Estimated teeth: 18" in instructions
    assert "Center distance: 94.0 mm" in instructions


def test_gear_blueprint_instructions_use_radius_aliases() -> None:
    exporter = BlueprintExporter.__new__(BlueprintExporter)

    instructions = exporter.generate_blueprint_instructions(
        "gear",
        {
            "grid_system_enabled": False,
            "gear1_radius": 36.0,
            "gear2_radius": 54.0,
            "gear1_teeth": 12,
            "gear2_teeth": 18,
            "gear_clearance": 4.0,
        },
        scale_factor=1.0,
    )

    assert "Pitch diameter: 72.0 mm" in instructions
    assert "Pitch diameter: 108.0 mm" in instructions
    assert "Estimated teeth: 12" in instructions
    assert "Estimated teeth: 18" in instructions
    assert "Center distance: 94.0 mm" in instructions


def test_gear_dimension_dialog_uses_explicit_clearance(monkeypatch) -> None:
    from automataii.presentation.qt.blueprint import exporter as exporter_module

    class _SceneRect:
        def width(self) -> float:
            return 8.5 * 25.4 * 0.9

        def height(self) -> float:
            return 11.0 * 25.4 * 0.9

    class _Scene:
        def itemsBoundingRect(self) -> _SceneRect:
            return _SceneRect()

    class _View:
        def scene(self) -> _Scene:
            return _Scene()

    captured: dict[str, str] = {}

    class _MessageBox:
        class Icon:
            Information = object()

        def setWindowTitle(self, value: str) -> None:
            captured["title"] = value

        def setText(self, value: str) -> None:
            captured["text"] = value

        def setDetailedText(self, value: str) -> None:
            captured["details"] = value

        def setIcon(self, _value: object) -> None:
            pass

        def exec(self) -> None:
            captured["exec"] = "called"

    monkeypatch.setattr(exporter_module, "QMessageBox", _MessageBox)

    exporter = BlueprintExporter(
        parent=None,
        mechanism_view=_View(),
        get_mechanism_layers=lambda: {
            "gear": {
                "type": "gear",
                "params": {"r1": 36.0, "r2": 54.0, "gear_clearance": 4.0},
            }
        },
        get_current_editor_items=lambda: {},
        get_scene_transform_function=lambda _layer: None,
    )

    exporter.show_mechanism_dimensions("gear")

    assert "Center Distance: 94.0 mm" in captured["text"]
    assert captured["exec"] == "called"


def test_gear_blueprint_svg_preserves_grid_disabled_freeform_teeth() -> None:
    from automataii.presentation.qt.mechanisms.blueprint.gear_blueprint import (
        GearBlueprintGenerator,
    )

    generator = GearBlueprintGenerator()

    svg = generator.generate_blueprint(
        {
            "params": {
                "grid_system_enabled": False,
                "gear1_radius": 36.0,
                "gear2_radius": 54.0,
                "gear1_teeth": 12,
                "gear2_teeth": 18,
                "gear_clearance": 4.0,
            }
        }
    )

    assert "12 TEETH" in svg
    assert "18 TEETH" in svg
    assert "94.0±0.05" in svg


def test_gear_svg_generator_preserves_grid_disabled_freeform_teeth() -> None:
    from automataii.domain.generation.layout import ScaledBounds
    from automataii.infrastructure.generation.svg.generators.gear import GearSVGGenerator

    svg = GearSVGGenerator().generate_gear_mesh_svg(
        {
            "params": {
                "grid_system_enabled": False,
                "gear1_teeth": 12,
                "gear2_teeth": 18,
                "gear_clearance": 4.0,
            },
            "real_world_params": {"r1_mm": 36.0, "r2_mm": 54.0},
        },
        ScaledBounds(0.0, 0.0, 240.0, 180.0),
    )

    assert "⌀72.0mm (12T)" in svg
    assert "⌀108.0mm (18T)" in svg
    assert "Center: 94.0mm" in svg


def test_gear_svg_generator_uses_active_profile_radius_pitch_label(monkeypatch) -> None:
    from automataii.domain.generation.layout import ScaledBounds
    from automataii.infrastructure.generation.svg.generators.gear import GearSVGGenerator
    from automataii.shared import physical_kit
    from automataii.shared.physical_kit import (
        CAM_PRESETS,
        DEFAULT_PHYSICAL_KIT_PROFILE,
        GearPreset,
        GridPitchChoice,
        PhysicalKitProfile,
    )

    custom_profile = PhysicalKitProfile(
        key="svg-test-kit",
        label="SVG test kit",
        default_pitch_mm=30.0,
        grid_pitch_choices=(GridPitchChoice("3cm", "3.0 cm board", 30.0),),
        linkage_length_cells=(2, 4),
        gear_presets=(GearPreset("g10", "G10", 10), GearPreset("g14", "G14", 14)),
        cam_presets=CAM_PRESETS,
        gear_radius_per_tooth_mm=2.0,
        default_gear_clearance_mm=5.0,
    )
    monkeypatch.setattr(
        physical_kit,
        "PHYSICAL_KIT_PROFILES",
        (custom_profile, DEFAULT_PHYSICAL_KIT_PROFILE),
    )

    svg = GearSVGGenerator().generate_gear_mesh_svg(
        {
            "params": {
                "physical_profile_key": "svg-test-kit",
                "gear1_teeth": 10,
                "gear2_teeth": 14,
            },
            "real_world_params": {"r1_mm": 20.0, "r2_mm": 28.0},
        },
        ScaledBounds(0.0, 0.0, 240.0, 180.0),
    )

    assert "Radius pitch: 2.0mm/tooth" in svg


def test_planetary_blueprint_accepts_float_planet_count() -> None:
    from automataii.presentation.qt.mechanisms.blueprint.planetary_gear_blueprint import (
        PlanetaryGearBlueprintGenerator,
    )

    generator = PlanetaryGearBlueprintGenerator()
    svg = generator.generate_blueprint(
        {
            "params": {
                "r_sun": 24.0,
                "r_planet": 18.0,
                "r_carrier": 42.0,
                "planet_count": 3.0,
            }
        }
    )

    assert "Planet Gear" in svg
    assert ">3<" in svg


def test_planetary_svg_generator_reads_nested_planet_count() -> None:
    from automataii.domain.generation.layout import ScaledBounds
    from automataii.infrastructure.generation.svg.generators.gear import GearSVGGenerator

    svg = GearSVGGenerator().generate_planetary_gear_svg(
        {
            "params": {"planet_count": 3.0, "sun_teeth": 12, "planet_teeth": 14},
            "real_world_params": {"r_sun_mm": 18.0, "r_planet_mm": 21.0},
        },
        ScaledBounds(0.0, 0.0, 240.0, 180.0),
    )

    assert ">P3<" in svg
    assert ">P4<" not in svg
