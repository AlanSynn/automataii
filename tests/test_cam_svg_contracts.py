from __future__ import annotations

import inspect
import re

import numpy as np

from automataii.domain.generation.layout import ScaledBounds
from automataii.domain.mechanisms.cam import profile as cam_profile_module
from automataii.infrastructure.generation.mechanism.cam import CamGenerator
from automataii.infrastructure.generation.svg.generators.cam import CamSVGGenerator
from automataii.presentation.qt.mechanisms.blueprint.cam_blueprint import (
    CamBlueprintGenerator,
)


def _cam_profile_path_points(svg: str) -> np.ndarray:
    match = re.search(r'<path d="([^"]+)"\s+fill="url\(#cam-gradient\)"', svg, re.S)
    assert match is not None
    coords = [
        (float(x), float(y)) for x, y in re.findall(r"[ML]([-0-9.]+),([-0-9.]+)", match.group(1))
    ]
    assert coords
    return np.asarray(coords, dtype=float)


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


def test_cam_svg_generator_sanitizes_negative_and_non_finite_mm_params() -> None:
    svg = CamSVGGenerator().generate_cam_svg(
        {
            "real_world_params": {
                "base_radius_mm": float("nan"),
                "lift_mm": -5.0,
                "eccentricity_mm": float("inf"),
                "follower_radius_mm": -3.0,
            }
        },
        ScaledBounds(x=0.0, y=0.0, width=220.0, height=180.0),
    )

    assert "nan" not in svg.lower()
    assert not re.search(r"(?<![A-Za-z])inf(?:inity)?(?![A-Za-z])", svg.lower())
    assert not re.search(r'<circle[^>]*\sr="-', svg)
    assert "Lift: -5.0mm" not in svg


def test_legacy_cam_generator_sanitizes_invalid_svg_geometry() -> None:
    svg = CamGenerator().generate_svg(
        {
            "center": [float("nan"), 0.0],
            "base_radius": -20.0,
            "max_radius": float("nan"),
            "profile_points": [[float("nan"), 0.0], [1.0, float("inf")]],
        }
    )

    assert "nan" not in svg.lower()
    assert not re.search(r"(?<![A-Za-z])inf(?:inity)?(?![A-Za-z])", svg.lower())
    assert not re.search(r'<circle[^>]*\sr="-', svg)


def test_cam_blueprint_profile_stays_positive_when_eccentricity_exceeds_base() -> None:
    generator = CamBlueprintGenerator()
    cx, cy = 100.0, 120.0

    points = generator._generate_cam_profile(cx, cy, base_r=10.0, ecc=40.0)

    assert points
    for x, y in points:
        radius = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        assert radius > 0.0


def test_domain_cam_profile_helper_is_qt_free_and_honors_aliases() -> None:
    source = inspect.getsource(cam_profile_module)
    assert "PyQt" not in source

    profile = cam_profile_module.build_pear_cam_profile_from_params(
        {
            "base_radius_mm": 22.0,
            "lift_mm": 7.0,
            "cam_lobes": 2,
            "profile_harmonic": 0.5,
        },
        num_samples=36,
    )

    assert profile.shape == (36, 2)
    assert np.isfinite(profile).all()


def test_cam_svg_generator_profile_changes_with_lobe_parameters() -> None:
    generator = CamSVGGenerator()
    center = (100.0, 100.0)

    single_lobe = generator._calculate_cam_profile(
        center,
        30.0,
        12.0,
        36,
        params={"base_radius": 30.0, "eccentricity": 12.0, "cam_lobes": 1},
    )
    multi_lobe = generator._calculate_cam_profile(
        center,
        30.0,
        12.0,
        36,
        params={
            "base_radius": 30.0,
            "eccentricity": 12.0,
            "cam_lobes": 3,
            "profile_harmonic": 0.6,
        },
    )

    assert single_lobe != multi_lobe
    assert len(single_lobe) == len(multi_lobe) == 36
    for x, y in multi_lobe:
        radius = ((x - center[0]) ** 2 + (y - center[1]) ** 2) ** 0.5
        assert np.isfinite(radius)
        assert radius > 0.0


def test_cam_svg_generator_scaled_profile_stays_inside_canvas() -> None:
    svg = CamSVGGenerator().generate_cam_svg(
        {
            "real_world_params": {
                "base_radius_mm": 100.0,
                "lift_mm": 50.0,
                "follower_radius_mm": 10.0,
            },
            "params": {
                "cam_lobes": 3,
                "profile_harmonic": 0.6,
            },
        },
        ScaledBounds(x=0.0, y=0.0, width=100.0, height=100.0),
    )

    points = _cam_profile_path_points(svg)

    assert np.isfinite(points).all()
    assert float(points[:, 0].min()) >= 0.0
    assert float(points[:, 1].min()) >= 0.0
    assert float(points[:, 0].max()) <= 100.0
    assert float(points[:, 1].max()) <= 100.0


def test_cam_svg_spec_panel_uses_parameter_driven_profile_copy() -> None:
    svg = CamSVGGenerator().generate_cam_svg(
        {
            "real_world_params": {
                "base_radius_mm": 40.0,
                "lift_mm": 12.0,
                "follower_radius_mm": 5.0,
            },
            "params": {
                "cam_lobes": 3,
                "profile_harmonic": 0.6,
            },
        },
        ScaledBounds(x=0.0, y=0.0, width=220.0, height=180.0),
    )

    assert "Simple Harmonic Motion" not in svg
    assert "Rise: 0-180" not in svg
    assert "Parameter-driven lobe profile" in svg
    assert "Lobes: 3" in svg
    assert "Harmonic: 0.60" in svg


def test_cam_blueprint_profile_changes_with_lobe_parameters() -> None:
    generator = CamBlueprintGenerator()
    base = generator._generate_cam_profile(
        100.0,
        120.0,
        30.0,
        12.0,
        params={"base_radius": 30.0, "eccentricity": 12.0, "cam_lobes": 1},
    )
    varied = generator._generate_cam_profile(
        100.0,
        120.0,
        30.0,
        12.0,
        params={
            "base_radius": 30.0,
            "eccentricity": 12.0,
            "cam_lobes": 3,
            "profile_harmonic": 0.6,
        },
    )

    assert base != varied
    assert len(base) == len(varied) == 360
    for x, y in varied:
        radius = ((x - 100.0) ** 2 + (y - 120.0) ** 2) ** 0.5
        assert np.isfinite(radius)
        assert radius > 0.0


def test_cam_svg_and_blueprint_share_domain_drawing_point_conversion() -> None:
    params = {
        "base_radius": 30.0,
        "eccentricity": 12.0,
        "align_max_deg": 135.0,
        "rise_deg": 80.0,
        "high_dwell_deg": 40.0,
        "return_deg": 60.0,
    }
    local_profile = cam_profile_module.build_pear_cam_profile_from_params(params, num_samples=360)

    expected = cam_profile_module.cam_profile_to_drawing_points(local_profile, 100.0, 120.0)
    svg_points = CamSVGGenerator._to_svg_points(local_profile, 100.0, 120.0)
    blueprint_points = CamBlueprintGenerator()._generate_cam_profile(
        100.0,
        120.0,
        30.0,
        12.0,
        params=params,
    )

    assert np.allclose(np.asarray(svg_points), np.asarray(expected))
    assert np.allclose(np.asarray(blueprint_points), np.asarray(expected))


def test_cam_blueprint_profile_honors_alias_only_params() -> None:
    """Blueprint profile generation must accept manufacturing/Foundry aliases directly."""
    params = {
        "base_radius_mm": 22.0,
        "lift_mm": 7.0,
        "align_max_deg": 135.0,
        "rise_deg": 80.0,
        "high_dwell_deg": 40.0,
        "return_deg": 60.0,
    }
    local_profile = cam_profile_module.build_pear_cam_profile_from_params(params, num_samples=360)

    expected = cam_profile_module.cam_profile_to_drawing_points(local_profile, 100.0, 120.0)
    blueprint_points = CamBlueprintGenerator()._generate_cam_profile(
        100.0,
        120.0,
        30.0,
        15.0,
        params=params,
    )

    assert np.allclose(np.asarray(blueprint_points), np.asarray(expected))


def test_cam_blueprint_empty_profile_draws_no_path() -> None:
    assert CamBlueprintGenerator()._draw_cam_profile([], 100.0, 120.0, 30.0) == ""
