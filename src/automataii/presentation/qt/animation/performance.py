"""
Performance Profiler for Real-Time Animation.

Provides frame time tracking, phase timing, and performance statistics
for monitoring animation system health.

Architecture: Presentation Layer
Pattern: Observer + Statistics
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class FrameRecord:
    """Record of a single frame's timing."""

    frame_id: int
    total_time_ms: float
    phase_times: dict[str, float] = field(default_factory=dict)
    was_slow: bool = False


class PerformanceProfiler:
    """
    Performance profiler for animation systems.

    Tracks frame times, compute phases, and provides rolling statistics
    for monitoring real-time performance.

    Features:
    - Frame time tracking with rolling averages
    - Individual phase timing (mechanism, ARAP, IK, etc.)
    - Slow frame detection
    - FPS calculation
    - Context manager interface for easy usage

    Usage:
        profiler = PerformanceProfiler(target_fps=60)

        with profiler.frame():
            with profiler.phase("mechanism"):
                compute_mechanisms()
            with profiler.phase("arap"):
                compute_arap()

        stats = profiler.get_stats()
        print(f"FPS: {stats['fps']:.1f}")
    """

    def __init__(
        self,
        target_fps: int = 60,
        window_size: int = 60,
        slow_threshold_factor: float = 1.5,
    ):
        """
        Initialize the profiler.

        Args:
            target_fps: Target frame rate
            window_size: Number of frames for rolling average
            slow_threshold_factor: Factor above target frame time to consider slow
        """
        self._target_fps = target_fps
        self._target_frame_time_ms = 1000.0 / target_fps
        self._window_size = window_size
        self._slow_threshold_ms = self._target_frame_time_ms * slow_threshold_factor

        # Frame tracking
        self._frame_count = 0
        self._frame_start_time: float = 0.0
        self._frame_times: deque[float] = deque(maxlen=window_size)
        self._slow_frame_count = 0

        # Phase tracking
        self._phase_start_times: dict[str, float] = {}
        self._current_phase_times: dict[str, float] = {}
        self._phase_histories: dict[str, deque[float]] = {}

        # Last frame record
        self._last_frame: FrameRecord | None = None

    # =========================================================================
    # FRAME TIMING
    # =========================================================================

    def start_frame(self) -> None:
        """Start timing a new frame."""
        self._frame_start_time = time.perf_counter()
        self._current_phase_times.clear()

    def end_frame(self) -> None:
        """End timing the current frame."""
        frame_time_ms = (time.perf_counter() - self._frame_start_time) * 1000.0
        self._frame_count += 1
        self._frame_times.append(frame_time_ms)

        # Check if slow
        was_slow = frame_time_ms > self._slow_threshold_ms
        if was_slow:
            self._slow_frame_count += 1

        # Create record
        self._last_frame = FrameRecord(
            frame_id=self._frame_count,
            total_time_ms=frame_time_ms,
            phase_times=self._current_phase_times.copy(),
            was_slow=was_slow,
        )

        # Log slow frames
        if was_slow:
            logger.warning(
                f"Slow frame {self._frame_count}: {frame_time_ms:.2f}ms "
                f"(target: {self._target_frame_time_ms:.2f}ms)"
            )

    @contextmanager
    def frame(self) -> Iterator[None]:
        """Context manager for frame timing."""
        self.start_frame()
        try:
            yield
        finally:
            self.end_frame()

    # =========================================================================
    # PHASE TIMING
    # =========================================================================

    def start_phase(self, phase_name: str) -> None:
        """Start timing a compute phase."""
        self._phase_start_times[phase_name] = time.perf_counter()

    def end_phase(self, phase_name: str) -> None:
        """End timing a compute phase."""
        if phase_name not in self._phase_start_times:
            return

        phase_time_ms = (time.perf_counter() - self._phase_start_times[phase_name]) * 1000.0
        self._current_phase_times[phase_name] = phase_time_ms

        # Update history
        if phase_name not in self._phase_histories:
            self._phase_histories[phase_name] = deque(maxlen=self._window_size)
        self._phase_histories[phase_name].append(phase_time_ms)

    @contextmanager
    def phase(self, phase_name: str) -> Iterator[None]:
        """Context manager for phase timing."""
        self.start_phase(phase_name)
        try:
            yield
        finally:
            self.end_phase(phase_name)

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def frame_count(self) -> int:
        """Get total frame count."""
        return self._frame_count

    @property
    def slow_frame_count(self) -> int:
        """Get count of slow frames."""
        return self._slow_frame_count

    @property
    def last_frame(self) -> FrameRecord | None:
        """Get the last frame record."""
        return self._last_frame

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """
        Get comprehensive performance statistics.

        Returns:
            Dict with frame count, timing, FPS, and phase statistics
        """
        # Calculate averages
        avg_frame_time = (
            sum(self._frame_times) / len(self._frame_times) if self._frame_times else 0.0
        )

        fps = 1000.0 / avg_frame_time if avg_frame_time > 0 else 0.0

        # Phase times from last frame
        phase_times = self._last_frame.phase_times if self._last_frame else {}

        # Phase averages
        phase_avg = {}
        for phase_name, history in self._phase_histories.items():
            if history:
                phase_avg[phase_name] = sum(history) / len(history)

        return {
            "frame_count": self._frame_count,
            "target_fps": self._target_fps,
            "fps": fps,
            "last_frame_time_ms": self._frame_times[-1] if self._frame_times else 0.0,
            "avg_frame_time_ms": avg_frame_time,
            "min_frame_time_ms": min(self._frame_times) if self._frame_times else 0.0,
            "max_frame_time_ms": max(self._frame_times) if self._frame_times else 0.0,
            "slow_frame_count": self._slow_frame_count,
            "slow_frame_threshold_ms": self._slow_threshold_ms,
            "phase_times": phase_times,
            "phase_avg": phase_avg,
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self._frame_count = 0
        self._frame_times.clear()
        self._slow_frame_count = 0
        self._phase_histories.clear()
        self._current_phase_times.clear()
        self._last_frame = None
        logger.debug("Performance profiler reset")

    # =========================================================================
    # REPORTING
    # =========================================================================

    def get_report(self) -> str:
        """
        Generate a human-readable performance report.

        Returns:
            Formatted string with performance summary
        """
        stats = self.get_stats()

        lines = [
            "=== Performance Report ===",
            f"Frames: {stats['frame_count']}",
            f"FPS: {stats['fps']:.1f} (target: {stats['target_fps']})",
            f"Frame time: {stats['avg_frame_time_ms']:.2f}ms avg "
            f"({stats['min_frame_time_ms']:.2f} - {stats['max_frame_time_ms']:.2f})",
            f"Slow frames: {stats['slow_frame_count']} (>{stats['slow_frame_threshold_ms']:.1f}ms)",
        ]

        if stats["phase_avg"]:
            lines.append("--- Phase Breakdown ---")
            for phase_name, avg_time in sorted(stats["phase_avg"].items()):
                lines.append(f"  {phase_name}: {avg_time:.2f}ms avg")

        return "\n".join(lines)
