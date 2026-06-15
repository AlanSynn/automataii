from __future__ import annotations

import inspect

from automataii.presentation.qt.blueprint.exporter import BlueprintExporter


def test_blueprint_export_success_copy_is_production_facing() -> None:
    source = inspect.getsource(BlueprintExporter)

    assert "Fixed:" not in source
    assert "screen-calculated dimensions instead of defaults" not in source
    assert "Blueprint exported successfully" in source
    assert "Units:" in source


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
