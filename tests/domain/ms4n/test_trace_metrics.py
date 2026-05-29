import math

import pytest

from automataii.domain.ms4n.trace import normalize_trace_points, summarize_trace


def test_trace_summary_handles_empty_trace():
    summary = summarize_trace(())
    assert summary.point_count == 0
    assert summary.bbox is None
    assert summary.motion_delta is None
    assert summary.was_downsampled is False


def test_trace_summary_handles_single_point_trace():
    summary = summarize_trace(((0, 10.0, 20.0),))
    assert summary.point_count == 1
    assert summary.bbox == (10.0, 20.0, 10.0, 20.0)
    assert summary.motion_delta == (0.0, 0.0)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_trace_summary_rejects_nan_and_infinite_coordinates(bad):
    with pytest.raises(ValueError):
        summarize_trace(((0, bad, 1.0),))


def test_trace_normalization_downsamples_over_500_points_deterministically():
    points = tuple((i, float(i), float(i * 2)) for i in range(777))
    first = normalize_trace_points(points)
    second = normalize_trace_points(points)
    assert len(first.points) == 500
    assert first.points == second.points
    assert first.original_point_count == 777
    assert first.was_downsampled is True
    assert first.sampling_rule == "uniform_downsample_to_500"


def test_trace_downsampling_preserves_first_and_last_points():
    points = tuple((i, float(i), float(i * 2)) for i in range(501))
    normalized = normalize_trace_points(points)
    assert normalized.points[0] == points[0]
    assert normalized.points[-1] == points[-1]
