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
