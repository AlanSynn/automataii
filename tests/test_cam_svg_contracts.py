from __future__ import annotations

import re

from automataii.domain.generation.layout import ScaledBounds
from automataii.infrastructure.generation.svg.generators.cam import CamSVGGenerator
from automataii.presentation.qt.mechanisms.blueprint.cam_blueprint import (
    CamBlueprintGenerator,
)


def test_cam_svg_generator_uses_eccentricity_mm_as_lift_alias() -> None:
    svg = CamSVGGenerator().generate_cam_svg(
        {
            "real_world_params": {
                "base_radius_mm": 22.0,
                "eccentricity_mm": 42.0,
                "follower_radius_mm": 6.0,
            }
        },
        ScaledBounds(x=0.0, y=0.0, width=220.0, height=180.0),
    )

    assert "Lift: 42.0mm" in svg
    assert "Maximum Lift: 42.0mm" in svg
    assert "Lift: 15.0mm" not in svg


def test_cam_blueprint_generator_never_emits_negative_circle_radius() -> None:
    svg = CamBlueprintGenerator().generate_blueprint(
        {
            "id": "cam-test",
            "type": "cam",
            "params": {
                "base_radius": 30.0,
                "eccentricity": 15.0,
                "follower_rod_length": 60.0,
            },
        }
    )

    radii = [float(value) for value in re.findall(r'<circle[^>]*\sr="([-0-9.]+)"', svg)]
    assert radii
    assert all(radius >= 0.0 for radius in radii)
