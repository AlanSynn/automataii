import math

import numpy as np
import pytest

from automataii.presentation.qt.tabs.mechanism_design.components.animation_cache import (
    AnimationCacheManager,
    CamCache,
    GearCache,
    LinkageCache,
    PlanetaryGearCache,
)


def test_linkage_cache_trims_required_position_arrays_to_common_length():
    cache = LinkageCache.from_simulation_data(
        {
            "p1_positions": [[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]],
            "p2_positions": [[10.0, 10.0]],
            "p3_positions": [[20.0, 20.0], [21.0, 21.0]],
            "p4_positions": [[30.0, 30.0], [31.0, 31.0]],
        }
    )

    assert cache.num_frames == 1
    p1, p2, p3, p4 = cache.get_frame_positions(10)
    assert p1.tolist() == [0.0, 0.0]
    assert p2.tolist() == [10.0, 10.0]
    assert p3.tolist() == [20.0, 20.0]
    assert p4.tolist() == [30.0, 30.0]


def test_linkage_cache_replaces_empty_or_malformed_positions_with_safe_fallback():
    cache = LinkageCache.from_simulation_data(
        {
            "p1_positions": [],
            "p2_positions": ["bad"],
            "p3_positions": [[20.0, 20.0, 99.0]],
            "p4_positions": [[30.0, 30.0]],
        },
        {"coupler_point_x": float("nan"), "coupler_point_y": "bad"},
    )

    p1, p2, p3, p4 = cache.get_frame_positions(0)
    assert p1.tolist() == [0.0, 0.0]
    assert p2.tolist() == [0.0, 0.0]
    assert p3.tolist() == [20.0, 20.0]
    assert p4.tolist() == [30.0, 30.0]
    assert cache.coupler_point_offset.tolist() == [0.0, 0.0]


def test_cam_cache_rejects_invalid_profile_point_count():
    with pytest.raises(ValueError, match="num_points"):
        CamCache.from_params({}, num_points=0)


def test_cam_cache_sanitizes_non_finite_and_negative_params():
    cache = CamCache.from_params(
        {
            "base_radius": float("nan"),
            "cam_offset": float("inf"),
            "cam_lobes": -2,
            "profile_harmonic": float("nan"),
            "follower_rod_length": -10.0,
        },
        scale_factor=float("nan"),
        rod_multiplier=-1.0,
        num_points=8,
    )

    assert cache.base_radius == 60.0
    assert cache.cam_offset == 20.0
    assert cache.cam_lobes == 1
    assert cache.profile_harmonic == 0.3
    assert cache.rod_length == 100.0
    assert cache.base_profile.shape == (8, 2)


def test_gear_cache_trims_mismatched_angle_arrays_and_sanitizes_radii():
    cache = GearCache.from_params(
        {"r1": float("nan"), "r2": -2.0},
        {"gear1_angles": [0.0, 1.0, 2.0], "gear2_angles": [0.0]},
    )

    assert cache.gear1_radius == 1.0
    assert cache.gear2_radius == 1.0
    assert cache.num_frames == 1
    assert cache.gear1_angles is not None
    assert cache.gear2_angles is not None
    assert len(cache.gear1_angles) == 1
    assert len(cache.gear2_angles) == 1


def test_gear_cache_disables_malformed_angle_arrays():
    cache = GearCache.from_params(
        {"r1": 10.0, "r2": 20.0},
        {"gear1_angles": 0.0, "gear2_angles": [float("nan")]},
    )

    assert cache.num_frames == 0
    assert cache.gear1_angles is None
    assert cache.gear2_angles is None
    theta1, theta2 = cache.get_angles(0.5)
    assert math.isfinite(theta1)
    assert math.isfinite(theta2)


def test_gear_cache_uses_layer_key_point_centers():
    cache = GearCache.from_params(
        {"r1": 10.0, "r2": 20.0},
        key_points={
            "gear1_center": [100.0, 50.0],
            "gear2_center": [130.0, 50.0],
        },
    )

    assert cache.gear1_center.tolist() == [100.0, 50.0]
    assert cache.gear2_center.tolist() == [130.0, 50.0]


def test_gear_cache_uses_simulation_centers_when_layer_centers_absent():
    cache = GearCache.from_params(
        {"r1": 10.0, "r2": 20.0},
        {
            "gear1_centers": [[40.0, 10.0], [41.0, 11.0]],
            "gear2_centers": [[70.0, 10.0], [71.0, 11.0]],
            "gear1_angles": [0.0, 1.0],
            "gear2_angles": [0.0, -0.5],
        },
    )

    assert cache.gear1_center.tolist() == [40.0, 10.0]
    assert cache.gear2_center.tolist() == [70.0, 10.0]


def test_animation_cache_manager_passes_gear_key_points():
    manager = AnimationCacheManager()

    manager.build_cache(
        "gear-layer",
        {
            "type": "gear",
            "params": {"r1": 10.0, "r2": 20.0},
            "key_points": {
                "gear1_center": [100.0, 50.0],
                "gear2_center": [130.0, 50.0],
            },
        },
    )

    cache = manager.get_gear_cache("gear-layer")
    assert cache is not None
    assert cache.gear1_center.tolist() == [100.0, 50.0]
    assert cache.gear2_center.tolist() == [130.0, 50.0]


def test_planetary_cache_uses_key_point_center_and_phase():
    cache = PlanetaryGearCache.from_params(
        {"r_sun": 20.0, "r_planet": 30.0, "arm_length": 15.0},
        key_points={
            "sun_center": [100.0, 100.0],
            "planet_center": [100.0, 150.0],
            "tracking_point": [100.0, 165.0],
        },
    )

    sun, planet, tracking = cache.get_positions(0.0)
    assert np.allclose(sun, [100.0, 100.0])
    assert np.allclose(planet, [100.0, 150.0])
    assert np.allclose(tracking, [100.0, 165.0])


def test_planetary_cache_sanitizes_zero_radius_and_trims_position_arrays():
    cache = PlanetaryGearCache.from_params(
        {"r_sun": float("nan"), "r_planet": 0.0, "arm_length": -5.0},
        {
            "sun_centers": [[0.0, 0.0], [1.0, 1.0]],
            "planet_centers": [[2.0, 2.0]],
            "tracking_points": [[3.0, 3.0], [4.0, 4.0], [5.0, 5.0]],
        },
    )

    assert cache.r_sun == 20.0
    assert cache.r_planet == 30.0
    assert cache.arm_length == 15.0
    assert cache.num_frames == 1
    sun, planet, tracking = cache.get_positions(math.pi)
    assert np.asarray(sun).tolist() == [0.0, 0.0]
    assert np.asarray(planet).tolist() == [2.0, 2.0]
    assert np.asarray(tracking).tolist() == [3.0, 3.0]
