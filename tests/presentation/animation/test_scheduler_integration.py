"""
Tests for CentralAnimationScheduler + RealTimeAnimationEngine integration.

These tests verify:
1. Scheduler can use accelerated computation
2. Frame data flows from compute thread to UI callbacks
3. Backwards compatibility with existing subscriptions
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass


class TestAcceleratedScheduler:
    """Test scheduler with accelerated computation."""

    def test_accelerated_mode_creation(self) -> None:
        """Accelerated scheduler should be creatable."""
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        scheduler = AcceleratedAnimationScheduler()
        assert scheduler is not None
        assert not scheduler.is_running

    def test_accelerated_mode_inherits_scheduler(self) -> None:
        """Accelerated scheduler should inherit from base scheduler."""
        from automataii.presentation.qt.animation.scheduler import (
            CentralAnimationScheduler,
        )
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        scheduler = AcceleratedAnimationScheduler()
        assert isinstance(scheduler, CentralAnimationScheduler)

    def test_register_mechanism_source(self) -> None:
        """Should register mechanism sources for computation."""
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        scheduler = AcceleratedAnimationScheduler()

        scheduler.register_mechanism(
            mechanism_id="mech_1",
            mechanism_type="4_bar_linkage",
            params={"r1": 30},
        )

        stats = scheduler.get_engine_stats()
        assert stats["mechanism_count"] == 1

    def test_register_skeleton_source(self) -> None:
        """Should register skeleton sources for computation."""
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        scheduler = AcceleratedAnimationScheduler()

        joints = np.array([[0.0, 0.0], [0.0, 50.0]])
        scheduler.register_skeleton(
            skeleton_id="skel_1",
            joint_positions=joints,
            bone_connections=[(0, 1)],
        )

        stats = scheduler.get_engine_stats()
        assert stats["skeleton_count"] == 1

    def test_frame_data_available_after_start(self) -> None:
        """Frame data should be available after starting."""
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        scheduler = AcceleratedAnimationScheduler(target_fps=60)

        scheduler.start()
        time.sleep(0.2)  # Let engine produce frames

        frame = scheduler.get_current_frame()
        scheduler.stop()

        assert frame is not None


class TestFrameDataDispatch:
    """Test frame data dispatch to subscribers."""

    def test_frame_callback_receives_data(self) -> None:
        """Frame callbacks should receive computed data via manual dispatch."""
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        # Use non-threading mode to avoid Qt event loop requirement
        scheduler = AcceleratedAnimationScheduler(
            target_fps=60,
            enable_threading=False,
        )

        # Track callback invocations
        callback_data = []

        def on_frame(frame_data):
            callback_data.append(frame_data)

        scheduler.subscribe_to_frames(on_frame)

        # Add a mechanism
        sim_data = {
            "joint_positions": {
                "p1_positions": [[0, 0]] * 10,
                "p3_positions": [[10, 20]] * 10,
                "p4_positions": [[30, 40]] * 10,
            }
        }
        scheduler.register_mechanism(
            mechanism_id="mech_1",
            mechanism_type="4_bar_linkage",
            params={},
            simulation_data=sim_data,
        )

        scheduler.start_engine_only()

        # Manually compute and dispatch frames
        for _ in range(5):
            frame = scheduler.compute_and_dispatch(0.016)
            assert frame is not None

        scheduler.stop_engine_only()

        assert len(callback_data) == 5

    def test_multiple_frame_subscribers(self) -> None:
        """Multiple subscribers should receive frame data."""
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        scheduler = AcceleratedAnimationScheduler(
            target_fps=60,
            enable_threading=False,
        )

        counts = {"a": 0, "b": 0}

        def callback_a(frame):
            counts["a"] += 1

        def callback_b(frame):
            counts["b"] += 1

        scheduler.subscribe_to_frames(callback_a)
        scheduler.subscribe_to_frames(callback_b)

        scheduler.start_engine_only()

        for _ in range(3):
            scheduler.compute_and_dispatch(0.016)

        scheduler.stop_engine_only()

        assert counts["a"] == 3
        assert counts["b"] == 3


class TestBackwardsCompatibility:
    """Test backwards compatibility with existing scheduler API."""

    def test_traditional_subscription_still_works(self) -> None:
        """Traditional subscriptions should still work via manual dispatch."""
        from automataii.presentation.qt.animation.scheduler import AnimationPriority
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        scheduler = AcceleratedAnimationScheduler(enable_threading=False)

        call_count = 0

        def update(delta_time: float) -> None:
            nonlocal call_count
            call_count += 1

        scheduler.subscribe(
            callback=update,
            priority=AnimationPriority.NORMAL,
            owner_id="test_subscriber",
        )

        scheduler.start_engine_only()

        # Manually trigger frame processing (simulates QTimer callback)
        for _ in range(5):
            scheduler.process_frame_manual(0.033)

        scheduler.stop_engine_only()

        assert call_count == 5

    def test_manual_frame_processing_clamps_invalid_delta_time(self) -> None:
        from automataii.presentation.qt.animation.scheduler import AnimationPriority
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        scheduler = AcceleratedAnimationScheduler(enable_threading=False)
        deltas: list[float] = []
        scheduler.subscribe(
            callback=lambda dt: deltas.append(dt),
            priority=AnimationPriority.NORMAL,
            owner_id="delta_recorder",
        )

        scheduler.process_frame_manual(float("nan"))
        scheduler.process_frame_manual(999.0)

        assert deltas[0] == scheduler._frame_time_ms / 1000.0
        assert deltas[1] == scheduler.MAX_DELTA_TIME_SECONDS

    def test_manual_frame_processing_disables_repeatedly_failing_callbacks(self) -> None:
        from automataii.presentation.qt.animation.scheduler import AnimationPriority
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        scheduler = AcceleratedAnimationScheduler(enable_threading=False)
        calls = 0

        def callback(_dt: float) -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError("boom")

        scheduler.subscribe(callback, AnimationPriority.NORMAL, "flaky")

        for _ in range(scheduler.CALLBACK_ERROR_DISABLE_THRESHOLD + 1):
            scheduler.process_frame_manual(0.016)

        sub = scheduler.list_subscriptions()[0]
        assert calls == scheduler.CALLBACK_ERROR_DISABLE_THRESHOLD
        assert sub["enabled"] is False

    def test_pause_resume_works(self) -> None:
        """Pause/resume should work with accelerated mode."""
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        scheduler = AcceleratedAnimationScheduler()

        scheduler.start()
        assert scheduler.is_running

        scheduler.pause()
        assert scheduler.is_paused

        scheduler.resume()
        assert not scheduler.is_paused

        scheduler.stop()
        assert not scheduler.is_running


class TestPerformanceStats:
    """Test performance statistics."""

    def test_engine_stats_available(self) -> None:
        """Engine stats should be available."""
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        scheduler = AcceleratedAnimationScheduler()
        stats = scheduler.get_engine_stats()

        assert "mechanism_count" in stats
        assert "skeleton_count" in stats

    def test_combined_stats(self) -> None:
        """Combined scheduler and engine stats should be available."""
        from automataii.presentation.qt.animation.scheduler_accelerated import (
            AcceleratedAnimationScheduler,
        )

        scheduler = AcceleratedAnimationScheduler()
        stats = scheduler.get_combined_stats()

        # Scheduler stats
        assert "running" in stats
        assert "subscriptions" in stats

        # Engine stats
        assert "engine_frame_count" in stats
