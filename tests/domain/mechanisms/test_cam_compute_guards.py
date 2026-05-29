from __future__ import annotations

import math

import pytest

from automataii.domain.mechanisms.cam.compute import CamFollowerMechanism


def test_cam_compute_state_sanitizes_non_finite_runtime_parameters() -> None:
    mechanism = CamFollowerMechanism()

    state = mechanism.compute_state(
        {
            "cam_radius": float("nan"),
            "cam_offset": float("inf"),
            "follower_length": -1.0,
            "cam_lobes": 0,
            "profile_harmonic": float("nan"),
        },
        input_angle=float("nan"),
    )

    assert math.isfinite(state.metadata["contact_radius"])
    for point in state.positions.values():
        assert all(math.isfinite(coord) for coord in point)


def test_cam_profile_cache_uses_sanitized_parameter_tuple_not_hash_only() -> None:
    mechanism = CamFollowerMechanism()

    mechanism.compute_state({"cam_radius": 50.0, "cam_offset": 10.0}, 0.0)
    first_cache_key = mechanism._cached_profile_params
    first_profile = mechanism._cached_base_profile

    mechanism.compute_state({"cam_radius": 50.0, "cam_offset": 10.0}, 90.0)
    assert mechanism._cached_profile_params == first_cache_key
    assert mechanism._cached_base_profile is first_profile

    mechanism.compute_state({"cam_radius": 55.0, "cam_offset": 10.0}, 90.0)
    assert mechanism._cached_profile_params != first_cache_key


def test_cam_compute_state_clips_foundry_visible_extreme_profile_to_positive_radii() -> None:
    mechanism = CamFollowerMechanism()

    state = mechanism.compute_state(
        {
            "cam_radius": 20.0,
            "cam_offset": 60.0,
            "follower_length": 30.0,
            "cam_lobes": 4,
            "profile_harmonic": 0.8,
        },
        input_angle=0.0,
    )

    radii = [math.hypot(x, y) for x, y in state.metadata["cam_profile"]]
    assert min(radii) > 0.0
    assert state.metadata["contact_radius"] > 0.0
    for point in state.positions.values():
        assert all(math.isfinite(coord) for coord in point)


@pytest.mark.parametrize(
    "params,match",
    [
        ({"cam_radius": "bad", "cam_offset": 1.0, "follower_length": 1.0}, "numeric"),
        ({"cam_radius": float("nan"), "cam_offset": 1.0, "follower_length": 1.0}, "finite"),
        ({"cam_radius": 1.0, "cam_offset": -1.0, "follower_length": 1.0}, "non-negative"),
        ({"cam_radius": 1.0, "cam_offset": 1.0, "follower_length": 0.0}, "positive"),
        (
            {"cam_radius": 1.0, "cam_offset": 1.0, "follower_length": 1.0, "cam_lobes": 0},
            "positive integer",
        ),
        (
            {"cam_radius": 1.0, "cam_offset": 1.0, "follower_length": 1.0, "cam_lobes": 1.5},
            "positive integer",
        ),
        (
            {
                "cam_radius": 1.0,
                "cam_offset": 1.0,
                "follower_length": 1.0,
                "cam_lobes": True,
            },
            "positive integer",
        ),
        (
            {
                "cam_radius": 1.0,
                "cam_offset": 1.0,
                "follower_length": 1.0,
                "profile_harmonic": float("inf"),
            },
            "finite",
        ),
    ],
)
def test_cam_validate_parameters_rejects_malformed_numeric_values(
    params: dict[str, float],
    match: str,
) -> None:
    mechanism = CamFollowerMechanism()

    with pytest.raises(ValueError, match=match):
        mechanism.validate_parameters(params)
