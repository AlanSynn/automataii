"""
Unit tests for PathCache module

Tests:
- Cache hit/miss behavior
- LRU eviction logic
- Size tracking accuracy
- Per-mechanism invalidation
- Key immutability and hashing
"""

import time
from unittest.mock import MagicMock

import pytest

from automataii.application.mechanism_foundry.path_cache import (
    CachedPath,
    PathCache,
    PathCacheKey,
)


class TestPathCacheKey:
    def test_from_dict_creates_sorted_tuple(self):
        params = {"b": 2.0, "a": 1.0, "c": 3.0}
        key = PathCacheKey.from_dict("fourbar", params, "coupler")

        assert key.mechanism_type == "fourbar"
        assert key.point_name == "coupler"
        assert key.parameters == (("a", 1.0), ("b", 2.0), ("c", 3.0))

    def test_keys_with_same_params_are_equal(self):
        key1 = PathCacheKey.from_dict("fourbar", {"a": 1.0, "b": 2.0}, "coupler")
        key2 = PathCacheKey.from_dict("fourbar", {"b": 2.0, "a": 1.0}, "coupler")

        assert key1 == key2
        assert hash(key1) == hash(key2)

    def test_keys_with_different_params_not_equal(self):
        key1 = PathCacheKey.from_dict("fourbar", {"a": 1.0}, "coupler")
        key2 = PathCacheKey.from_dict("fourbar", {"a": 2.0}, "coupler")

        assert key1 != key2

    def test_key_is_immutable(self):
        key = PathCacheKey.from_dict("fourbar", {"a": 1.0}, "coupler")

        with pytest.raises(AttributeError):
            key.mechanism_type = "cam"


class TestCachedPath:
    def test_cached_path_creation(self):
        points = ((0.0, 0.0), (1.0, 1.0), (2.0, 2.0))
        angles = (0.0, 90.0, 180.0)
        timestamp = time.time()

        cached = CachedPath(points=points, angles=angles, timestamp=timestamp)

        assert cached.points == points
        assert cached.angles == angles
        assert cached.timestamp == timestamp

    def test_cached_path_is_immutable(self):
        cached = CachedPath(points=((0.0, 0.0),), angles=(0.0,), timestamp=time.time())

        with pytest.raises(AttributeError):
            cached.points = ((1.0, 1.0),)


class TestPathCache:
    def test_initial_state(self):
        cache = PathCache()

        assert cache.entry_count == 0
        assert cache.size_bytes == 0
        assert cache.hit_rate == 0.0

    def test_cache_miss_increments_counter(self):
        cache = PathCache()
        key = PathCacheKey.from_dict("fourbar", {"a": 1.0}, "coupler")

        result = cache.get(key)

        assert result is None
        assert cache.hit_rate == 0.0

    def test_cache_hit_increments_counter(self):
        cache = PathCache()
        key = PathCacheKey.from_dict("fourbar", {"a": 1.0}, "coupler")
        path = CachedPath(
            points=((0.0, 0.0), (1.0, 1.0)), angles=(0.0, 180.0), timestamp=time.time()
        )

        cache.put(key, path)
        result = cache.get(key)

        assert result == path
        assert cache.hit_rate == 1.0

    def test_lru_eviction_when_size_exceeded(self):
        cache = PathCache(max_size_bytes=1000)

        key1 = PathCacheKey.from_dict("fourbar", {"a": 1.0}, "coupler")
        key2 = PathCacheKey.from_dict("fourbar", {"a": 2.0}, "coupler")
        key3 = PathCacheKey.from_dict("fourbar", {"a": 3.0}, "coupler")

        large_points = tuple((float(i), float(i)) for i in range(20))
        angles = tuple(range(20))

        path1 = CachedPath(points=large_points, angles=angles, timestamp=time.time())
        path2 = CachedPath(points=large_points, angles=angles, timestamp=time.time())
        path3 = CachedPath(points=large_points, angles=angles, timestamp=time.time())

        cache.put(key1, path1)
        cache.put(key2, path2)
        cache.put(key3, path3)

        assert cache.get(key1) is None
        assert cache.get(key2) is not None or cache.get(key3) is not None

    def test_size_tracking(self):
        cache = PathCache()
        key = PathCacheKey.from_dict("fourbar", {"a": 1.0}, "coupler")

        points = tuple((float(i), float(i)) for i in range(10))
        angles = tuple(range(10))
        path = CachedPath(points=points, angles=angles, timestamp=time.time())

        cache.put(key, path)

        expected_size = 10 * 2 * 8 + 10 * 8 + 8
        assert cache.size_bytes == expected_size
        assert cache.entry_count == 1

    def test_invalidate_mechanism_type(self):
        cache = PathCache()

        key1 = PathCacheKey.from_dict("fourbar", {"a": 1.0}, "coupler")
        key2 = PathCacheKey.from_dict("fourbar", {"a": 2.0}, "coupler")
        key3 = PathCacheKey.from_dict("cam", {"r": 10.0}, "follower")

        path = CachedPath(points=((0.0, 0.0),), angles=(0.0,), timestamp=time.time())

        cache.put(key1, path)
        cache.put(key2, path)
        cache.put(key3, path)

        cache.invalidate("fourbar")

        assert cache.get(key1) is None
        assert cache.get(key2) is None
        assert cache.get(key3) is not None

    def test_clear(self):
        cache = PathCache()
        key = PathCacheKey.from_dict("fourbar", {"a": 1.0}, "coupler")
        path = CachedPath(points=((0.0, 0.0),), angles=(0.0,), timestamp=time.time())

        cache.put(key, path)
        assert cache.entry_count == 1

        cache.clear()

        assert cache.entry_count == 0
        assert cache.size_bytes == 0

    def test_compute_and_cache_integration(self):
        cache = PathCache()

        mock_mechanism = MagicMock()
        mock_mechanism.mechanism_type = "fourbar"

        mock_state = MagicMock()
        mock_state.positions = {"coupler": (10.0, 20.0)}
        mock_mechanism.compute_state.return_value = mock_state

        params = {"a": 1.0, "b": 2.0}
        result = cache.compute_and_cache(mock_mechanism, params, "coupler", angle_samples=10)

        assert len(result.points) == 10
        assert len(result.angles) == 10
        assert result.points[0] == (10.0, 20.0)
        assert cache.entry_count == 1

    def test_compute_and_cache_handles_errors(self):
        cache = PathCache()

        mock_mechanism = MagicMock()
        mock_mechanism.mechanism_type = "fourbar"
        mock_mechanism.compute_state.side_effect = Exception("Compute failed")

        params = {"a": 1.0}
        result = cache.compute_and_cache(mock_mechanism, params, "coupler", angle_samples=5)

        assert len(result.points) == 5
        assert all(point == (0.0, 0.0) for point in result.points)

    def test_compute_and_cache_uses_cached_result(self):
        cache = PathCache()

        mock_mechanism = MagicMock()
        mock_mechanism.mechanism_type = "fourbar"

        mock_state = MagicMock()
        mock_state.positions = {"coupler": (10.0, 20.0)}
        mock_mechanism.compute_state.return_value = mock_state

        params = {"a": 1.0}
        result1 = cache.compute_and_cache(mock_mechanism, params, "coupler", angle_samples=5)
        result2 = cache.compute_and_cache(mock_mechanism, params, "coupler", angle_samples=5)

        assert result1 is result2
        assert mock_mechanism.compute_state.call_count == 5

    def test_compute_and_cache_keys_include_angle_sample_count(self):
        cache = PathCache()

        mock_mechanism = MagicMock()
        mock_mechanism.mechanism_type = "fourbar"

        mock_state = MagicMock()
        mock_state.positions = {"coupler": (10.0, 20.0)}
        mock_mechanism.compute_state.return_value = mock_state

        params = {"a": 1.0}
        result1 = cache.compute_and_cache(mock_mechanism, params, "coupler", angle_samples=5)
        result2 = cache.compute_and_cache(mock_mechanism, params, "coupler", angle_samples=9)

        assert result1 is not result2
        assert len(result1.points) == 5
        assert len(result2.points) == 9
        assert mock_mechanism.compute_state.call_count == 14

    @pytest.mark.parametrize("angle_samples", [0, -1, True])
    def test_compute_and_cache_rejects_invalid_angle_samples(self, angle_samples):
        cache = PathCache()
        mock_mechanism = MagicMock()
        mock_mechanism.mechanism_type = "fourbar"

        with pytest.raises(ValueError, match="angle_samples"):
            cache.compute_and_cache(
                mock_mechanism,
                {"a": 1.0},
                "coupler",
                angle_samples=angle_samples,
            )

    def test_compute_and_cache_accepts_numpy_position_values(self):
        import numpy as np

        cache = PathCache()
        mock_mechanism = MagicMock()
        mock_mechanism.mechanism_type = "fourbar"

        mock_state = MagicMock()
        mock_state.positions = {"coupler": np.array([10.0, 20.0])}
        mock_mechanism.compute_state.return_value = mock_state

        result = cache.compute_and_cache(mock_mechanism, {"a": 1.0}, "coupler", angle_samples=3)

        assert result.points == ((10.0, 20.0), (10.0, 20.0), (10.0, 20.0))

    def test_put_replaces_existing_key_without_size_leak(self):
        cache = PathCache()
        key = PathCacheKey.from_dict("fourbar", {"a": 1.0}, "coupler")
        small = CachedPath(points=((0.0, 0.0),), angles=(0.0,), timestamp=time.time())
        bigger = CachedPath(
            points=((0.0, 0.0), (1.0, 1.0)),
            angles=(0.0, 90.0),
            timestamp=time.time(),
        )

        cache.put(key, small)
        cache.put(key, bigger)

        assert cache.entry_count == 1
        assert cache.size_bytes == 2 * 2 * 8 + 2 * 8 + 8

    def test_put_does_not_cache_single_oversized_path(self):
        cache = PathCache(max_size_bytes=16)
        key = PathCacheKey.from_dict("fourbar", {"a": 1.0}, "coupler")
        oversized = CachedPath(
            points=tuple((float(i), float(i)) for i in range(10)),
            angles=tuple(float(i) for i in range(10)),
            timestamp=time.time(),
        )

        cache.put(key, oversized)

        assert cache.entry_count == 0
        assert cache.size_bytes == 0

    def test_lru_ordering_on_access(self):
        cache = PathCache()

        key1 = PathCacheKey.from_dict("fourbar", {"a": 1.0}, "coupler")
        key2 = PathCacheKey.from_dict("fourbar", {"a": 2.0}, "coupler")

        path = CachedPath(points=((0.0, 0.0),), angles=(0.0,), timestamp=time.time())

        cache.put(key1, path)
        cache.put(key2, path)

        cache.get(key1)

        assert list(cache._cache.keys())[-1] == key1
