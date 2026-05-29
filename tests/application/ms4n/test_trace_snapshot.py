import math

import pytest

from automataii.application.ms4n import points_to_trace_points


class PointLike:
    def __init__(self, x, y):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y


def test_trace_points_are_frame_x_y_tuples():
    points = [(120.0, 80.0), (121.5, 80.5), (122.0, 81.0)]
    assert points_to_trace_points(points, start_frame=10) == (
        (10, 120.0, 80.0),
        (11, 121.5, 80.5),
        (12, 122.0, 81.0),
    )


def test_trace_conversion_preserves_order():
    assert points_to_trace_points([(3.0, 0.0), (1.0, 0.0), (2.0, 0.0)]) == (
        (0, 3.0, 0.0),
        (1, 1.0, 0.0),
        (2, 2.0, 0.0),
    )


def test_trace_conversion_applies_start_frame_offset():
    assert points_to_trace_points([(0.0, 0.0)], start_frame=10)[0][0] == 10


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_trace_conversion_rejects_nan_and_infinite_coordinates(bad):
    with pytest.raises(ValueError):
        points_to_trace_points([(bad, 0.0)])


def test_trace_conversion_rejects_runtime_point_objects_at_application_boundary():
    with pytest.raises(ValueError):
        points_to_trace_points([PointLike(1.0, 2.0)])


@pytest.mark.parametrize("bad_point", [[1.0, 2.0, object()], [1.0, 2.0, 3.0]])
def test_trace_conversion_rejects_extra_point_fields(bad_point):
    with pytest.raises(ValueError):
        points_to_trace_points([bad_point])
