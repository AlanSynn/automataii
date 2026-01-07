"""
Tests for Performance Profiler.

These tests verify:
1. Frame time tracking
2. Compute time statistics
3. Rolling averages
4. Performance thresholds and alerts
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


class TestFrameTimeTracker:
    """Test frame time tracking."""

    def test_tracker_creation(self) -> None:
        """Tracker should be creatable."""
        from automataii.presentation.qt.animation.performance import (
            PerformanceProfiler,
        )

        profiler = PerformanceProfiler()
        assert profiler is not None

    def test_record_frame_time(self) -> None:
        """Should record frame times."""
        from automataii.presentation.qt.animation.performance import (
            PerformanceProfiler,
        )

        profiler = PerformanceProfiler()

        profiler.start_frame()
        time.sleep(0.01)  # 10ms
        profiler.end_frame()

        stats = profiler.get_stats()
        assert stats["frame_count"] == 1
        assert stats["last_frame_time_ms"] > 5

    def test_multiple_frames(self) -> None:
        """Should track multiple frames."""
        from automataii.presentation.qt.animation.performance import (
            PerformanceProfiler,
        )

        profiler = PerformanceProfiler()

        for _ in range(10):
            profiler.start_frame()
            time.sleep(0.005)  # 5ms
            profiler.end_frame()

        stats = profiler.get_stats()
        assert stats["frame_count"] == 10


class TestComputePhases:
    """Test compute phase timing."""

    def test_phase_timing(self) -> None:
        """Should time individual compute phases."""
        from automataii.presentation.qt.animation.performance import (
            PerformanceProfiler,
        )

        profiler = PerformanceProfiler()

        profiler.start_frame()

        profiler.start_phase("mechanism")
        time.sleep(0.005)
        profiler.end_phase("mechanism")

        profiler.start_phase("arap")
        time.sleep(0.003)
        profiler.end_phase("arap")

        profiler.end_frame()

        stats = profiler.get_stats()
        assert "mechanism" in stats["phase_times"]
        assert "arap" in stats["phase_times"]
        assert stats["phase_times"]["mechanism"] > 3
        assert stats["phase_times"]["arap"] > 1

    def test_phase_averages(self) -> None:
        """Should compute rolling averages for phases."""
        from automataii.presentation.qt.animation.performance import (
            PerformanceProfiler,
        )

        profiler = PerformanceProfiler()

        for _ in range(5):
            profiler.start_frame()
            profiler.start_phase("compute")
            time.sleep(0.004)
            profiler.end_phase("compute")
            profiler.end_frame()

        stats = profiler.get_stats()
        assert stats["phase_avg"]["compute"] > 2


class TestRollingStatistics:
    """Test rolling statistics computation."""

    def test_rolling_average(self) -> None:
        """Should compute rolling averages."""
        from automataii.presentation.qt.animation.performance import (
            PerformanceProfiler,
        )

        profiler = PerformanceProfiler(window_size=5)

        # Record 10 frames, but window is 5
        for _ in range(10):
            profiler.start_frame()
            time.sleep(0.01)
            profiler.end_frame()

        stats = profiler.get_stats()
        assert stats["avg_frame_time_ms"] > 5

    def test_fps_calculation(self) -> None:
        """Should calculate FPS from frame times."""
        from automataii.presentation.qt.animation.performance import (
            PerformanceProfiler,
        )

        profiler = PerformanceProfiler()

        # Target ~100 FPS (10ms frames)
        for _ in range(10):
            profiler.start_frame()
            time.sleep(0.01)
            profiler.end_frame()

        stats = profiler.get_stats()
        # Should be somewhere between 50-100 FPS given timing uncertainty
        assert 40 < stats["fps"] < 120


class TestPerformanceThresholds:
    """Test performance threshold monitoring."""

    def test_slow_frame_detection(self) -> None:
        """Should detect slow frames."""
        from automataii.presentation.qt.animation.performance import (
            PerformanceProfiler,
        )

        # Target 60 FPS = 16.67ms per frame, threshold at 20ms
        profiler = PerformanceProfiler(target_fps=60, slow_threshold_factor=1.2)

        # Normal frame
        profiler.start_frame()
        time.sleep(0.010)  # 10ms - under threshold
        profiler.end_frame()

        assert profiler.slow_frame_count == 0

        # Slow frame
        profiler.start_frame()
        time.sleep(0.030)  # 30ms - over threshold
        profiler.end_frame()

        assert profiler.slow_frame_count == 1

    def test_reset_stats(self) -> None:
        """Should reset all statistics."""
        from automataii.presentation.qt.animation.performance import (
            PerformanceProfiler,
        )

        profiler = PerformanceProfiler()

        for _ in range(5):
            profiler.start_frame()
            time.sleep(0.005)
            profiler.end_frame()

        profiler.reset()

        stats = profiler.get_stats()
        assert stats["frame_count"] == 0


class TestContextManager:
    """Test context manager interface."""

    def test_frame_context_manager(self) -> None:
        """Should work as context manager for frames."""
        from automataii.presentation.qt.animation.performance import (
            PerformanceProfiler,
        )

        profiler = PerformanceProfiler()

        with profiler.frame():
            time.sleep(0.01)

        stats = profiler.get_stats()
        assert stats["frame_count"] == 1

    def test_phase_context_manager(self) -> None:
        """Should work as context manager for phases."""
        from automataii.presentation.qt.animation.performance import (
            PerformanceProfiler,
        )

        profiler = PerformanceProfiler()

        with profiler.frame():
            with profiler.phase("test"):
                time.sleep(0.005)

        stats = profiler.get_stats()
        assert "test" in stats["phase_times"]
