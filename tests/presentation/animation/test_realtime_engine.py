"""
Tests for RealTimeAnimationEngine.

These tests verify:
1. Engine lifecycle (start/stop/pause)
2. Source registration (mechanisms, skeletons)
3. Frame computation
4. Threading integration
5. Performance stats
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    pass


class TestEngineLifecycle:
    """Test engine start/stop/pause."""

    def test_engine_creation(self) -> None:
        """Engine should be creatable with default config."""
        from automataii.presentation.qt.animation.realtime_engine import (
            RealTimeAnimationEngine,
        )

        engine = RealTimeAnimationEngine()
        assert engine is not None
        assert not engine.is_running

    def test_engine_start_stop(self) -> None:
        """Engine should start and stop cleanly."""
        from automataii.presentation.qt.animation.realtime_engine import (
            EngineConfig,
            RealTimeAnimationEngine,
        )

        config = EngineConfig(target_fps=30, enable_threading=True)
        engine = RealTimeAnimationEngine(config)

        engine.start()
        assert engine.is_running

        time.sleep(0.1)  # Let it run briefly

        engine.stop()
        assert not engine.is_running

    def test_engine_pause_resume(self) -> None:
        """Engine should pause and resume."""
        from automataii.presentation.qt.animation.realtime_engine import (
            EngineConfig,
            RealTimeAnimationEngine,
        )

        config = EngineConfig(enable_threading=False)
        engine = RealTimeAnimationEngine(config)

        engine.start()
        assert not engine.is_paused

        engine.pause()
        assert engine.is_paused

        engine.resume()
        assert not engine.is_paused

        engine.stop()

    def test_engine_single_threaded_mode(self) -> None:
        """Engine should work in single-threaded mode."""
        from automataii.presentation.qt.animation.realtime_engine import (
            EngineConfig,
            RealTimeAnimationEngine,
        )

        config = EngineConfig(enable_threading=False)
        engine = RealTimeAnimationEngine(config)

        engine.start()
        assert engine.is_running

        # Compute frame synchronously
        frame = engine.compute_frame_sync(0.033)
        assert frame is not None
        assert frame.frame_id == 1

        engine.stop()


class TestSourceRegistration:
    """Test mechanism and skeleton registration."""

    def test_register_mechanism(self) -> None:
        """Should register mechanisms."""
        from automataii.presentation.qt.animation.realtime_engine import (
            RealTimeAnimationEngine,
        )

        engine = RealTimeAnimationEngine()

        engine.register_mechanism(
            mechanism_id="mech_1",
            mechanism_type="4_bar_linkage",
            params={"r1": 30, "r2": 50},
        )

        stats = engine.get_stats()
        assert stats["mechanism_count"] == 1

    def test_unregister_mechanism(self) -> None:
        """Should unregister mechanisms."""
        from automataii.presentation.qt.animation.realtime_engine import (
            RealTimeAnimationEngine,
        )

        engine = RealTimeAnimationEngine()

        engine.register_mechanism(
            mechanism_id="mech_1",
            mechanism_type="4_bar_linkage",
            params={},
        )
        engine.unregister_mechanism("mech_1")

        stats = engine.get_stats()
        assert stats["mechanism_count"] == 0

    def test_register_skeleton(self) -> None:
        """Should register skeletons."""
        from automataii.presentation.qt.animation.realtime_engine import (
            RealTimeAnimationEngine,
        )

        engine = RealTimeAnimationEngine()

        joints = np.array([
            [0.0, 0.0],
            [0.0, 50.0],
            [25.0, 100.0],
        ])
        bones = [(0, 1), (1, 2)]

        engine.register_skeleton(
            skeleton_id="skel_1",
            joint_positions=joints,
            bone_connections=bones,
        )

        stats = engine.get_stats()
        assert stats["skeleton_count"] == 1

    def test_update_ik_target(self) -> None:
        """Should update IK targets."""
        from automataii.presentation.qt.animation.realtime_engine import (
            RealTimeAnimationEngine,
        )

        engine = RealTimeAnimationEngine()

        joints = np.array([[0.0, 0.0], [0.0, 50.0]])
        engine.register_skeleton("skel_1", joints, [(0, 1)])

        engine.update_ik_target("skel_1", "hand", (100.0, 100.0))

        # IK target should be stored
        assert "hand" in engine._skeletons["skel_1"].ik_targets


class TestFrameComputation:
    """Test frame computation."""

    def test_compute_frame_returns_data(self) -> None:
        """Computed frame should have valid data."""
        from automataii.presentation.qt.animation.realtime_engine import (
            EngineConfig,
            RealTimeAnimationEngine,
        )

        config = EngineConfig(enable_threading=False)
        engine = RealTimeAnimationEngine(config)

        engine.start()
        frame = engine.compute_frame_sync(0.033)

        assert frame is not None
        assert frame.frame_id >= 1
        assert frame.timestamp >= 0

        engine.stop()

    def test_frame_contains_mechanism_positions(self) -> None:
        """Frame should contain mechanism positions."""
        from automataii.presentation.qt.animation.realtime_engine import (
            EngineConfig,
            RealTimeAnimationEngine,
        )

        config = EngineConfig(enable_threading=False)
        engine = RealTimeAnimationEngine(config)

        # Register mechanism with simulation data
        sim_data = {
            "joint_positions": {
                "p1_positions": [[0, 0]] * 10,
                "p3_positions": [[10, 20]] * 10,
                "p4_positions": [[30, 40]] * 10,
            }
        }
        engine.register_mechanism(
            mechanism_id="mech_1",
            mechanism_type="4_bar_linkage",
            params={},
            simulation_data=sim_data,
        )

        engine.start()
        frame = engine.compute_frame_sync(0.0)

        assert "mech_1" in frame.mechanism_positions
        assert len(frame.mechanism_positions["mech_1"]) == 2

        engine.stop()

    def test_frame_contains_skeleton_joints(self) -> None:
        """Frame should contain skeleton joints."""
        from automataii.presentation.qt.animation.realtime_engine import (
            EngineConfig,
            RealTimeAnimationEngine,
        )

        config = EngineConfig(enable_threading=False)
        engine = RealTimeAnimationEngine(config)

        joints = np.array([[0.0, 0.0], [0.0, 50.0]])
        engine.register_skeleton("skel_1", joints, [(0, 1)])

        engine.start()
        frame = engine.compute_frame_sync(0.033)

        assert frame.skeleton_joints is not None
        assert len(frame.skeleton_joints) == 2

        engine.stop()


class TestThreadedExecution:
    """Test threaded frame computation."""

    def test_threaded_produces_frames(self) -> None:
        """Threaded engine should produce frames."""
        from automataii.presentation.qt.animation.realtime_engine import (
            EngineConfig,
            RealTimeAnimationEngine,
        )

        config = EngineConfig(target_fps=60, enable_threading=True)
        engine = RealTimeAnimationEngine(config)

        engine.start()
        time.sleep(0.2)  # Let it produce some frames

        frame = engine.get_current_frame()
        engine.stop()

        assert frame is not None
        assert frame.frame_id > 0

    def test_frame_ids_are_monotonic(self) -> None:
        """Frame IDs should increase monotonically."""
        from automataii.presentation.qt.animation.realtime_engine import (
            EngineConfig,
            RealTimeAnimationEngine,
        )

        config = EngineConfig(target_fps=60, enable_threading=True)
        engine = RealTimeAnimationEngine(config)

        engine.start()

        frame_ids = []
        for _ in range(20):
            time.sleep(0.02)
            frame = engine.get_current_frame()
            if frame:
                frame_ids.append(frame.frame_id)

        engine.stop()

        # Check monotonicity
        for i in range(1, len(frame_ids)):
            assert frame_ids[i] >= frame_ids[i - 1]


class TestPerformanceStats:
    """Test performance monitoring."""

    def test_stats_are_available(self) -> None:
        """Stats should be available."""
        from automataii.presentation.qt.animation.realtime_engine import (
            RealTimeAnimationEngine,
        )

        engine = RealTimeAnimationEngine()
        stats = engine.get_stats()

        assert "frame_count" in stats
        assert "arap_backend" in stats
        assert "target_fps" in stats

    def test_stats_update_with_frames(self) -> None:
        """Stats should update as frames are computed."""
        from automataii.presentation.qt.animation.realtime_engine import (
            EngineConfig,
            RealTimeAnimationEngine,
        )

        config = EngineConfig(enable_threading=False)
        engine = RealTimeAnimationEngine(config)

        engine.start()

        for i in range(10):
            engine.compute_frame_sync(float(i) * 0.033)

        stats = engine.get_stats()
        engine.stop()

        assert stats["frame_count"] == 10
        assert stats["avg_compute_time_ms"] > 0
