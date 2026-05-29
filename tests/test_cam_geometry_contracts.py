from __future__ import annotations

import math

import numpy as np
import pytest

from automataii.presentation.qt.tabs.cam_geometry import (
    build_pear_cam_profile,
    build_pear_cam_profile_from_params,
    cam_contact_local_from_profile,
    normalized_cam_timing,
)


def test_cam_timing_normalization_includes_return_segment_in_total_budget() -> None:
    rise, high, ret, low = normalized_cam_timing(
        {
            "rise_deg": 200.0,
            "high_dwell_deg": 100.0,
            "return_deg": 100.0,
            "low_dwell_deg": 100.0,
        }
    )

    assert rise + high + ret + low == pytest.approx(360.0)
    assert ret > 0.0


def test_pear_cam_profile_uses_explicit_return_duration() -> None:
    common = {
        "base_radius": 25.0,
        "eccentricity": 10.0,
        "rise_deg": 90.0,
        "high_dwell_deg": 30.0,
        "dwell_low_deg": 120.0,
        "align_max_to_deg": 90.0,
        "num_samples": 360,
    }

    quick_return = build_pear_cam_profile(**common, return_deg=30.0)
    slow_return = build_pear_cam_profile(**common, return_deg=120.0)

    assert not np.allclose(quick_return, slow_return)
    assert cam_contact_local_from_profile(quick_return, math.radians(180.0))[1] != pytest.approx(
        cam_contact_local_from_profile(slow_return, math.radians(180.0))[1]
    )


def test_pear_cam_profile_from_params_sanitizes_malformed_values() -> None:
    profile = build_pear_cam_profile_from_params(
        {
            "base_radius": float("nan"),
            "eccentricity": -5.0,
            "rise_deg": float("inf"),
            "return_deg": "bad",
            "low_dwell_deg": 999.0,
            "align_max_deg": float("-inf"),
        },
        scale=float("nan"),
    )

    assert profile.shape == (360, 2)
    assert bool(np.isfinite(profile).all())
    assert np.min(np.linalg.norm(profile, axis=1)) > 0.0
