"""
Tests for threading infrastructure (DoubleBuffer, ComputeThread).

TDD: Write tests first, then implement.

These tests verify:
1. Thread-safe double buffering
2. Producer-consumer synchronization
3. Graceful shutdown
4. Frame data integrity
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    import numpy.typing as npt


# =============================================================================
# DOUBLE BUFFER TESTS
# =============================================================================


class TestDoubleBuffer:
    """Test the lock-free double buffer implementation."""

    def test_initial_state_is_none(self) -> None:
        """Buffer should be empty on creation."""
        from automataii.presentation.qt.animation.compute_thread import DoubleBuffer

        buffer = DoubleBuffer()
        assert buffer.read_front() is None

    def test_write_and_swap_makes_data_available(self) -> None:
        """After write and swap, data should be readable."""
        from automataii.presentation.qt.animation.compute_thread import (
            DoubleBuffer,
            FrameData,
        )

        buffer = DoubleBuffer()

        frame = FrameData(
            frame_id=1,
            timestamp=0.033,
            mechanism_positions={"mech_1": np.array([[1.0, 2.0]])},
            skeleton_joints=None,
        )

        buffer.write_back(frame)
        buffer.swap()

        result = buffer.read_front()
        assert result is not None
        assert result.frame_id == 1

    def test_multiple_swaps_update_front(self) -> None:
        """Multiple swaps should update front buffer correctly."""
        from automataii.presentation.qt.animation.compute_thread import (
            DoubleBuffer,
            FrameData,
        )

        buffer = DoubleBuffer()

        # Write first frame
        frame1 = FrameData(
            frame_id=1,
            timestamp=0.033,
            mechanism_positions={},
            skeleton_joints=None,
        )
        buffer.write_back(frame1)
        buffer.swap()

        # Write second frame
        frame2 = FrameData(
            frame_id=2,
            timestamp=0.066,
            mechanism_positions={},
            skeleton_joints=None,
        )
        buffer.write_back(frame2)
        buffer.swap()

        result = buffer.read_front()
        assert result is not None
        assert result.frame_id == 2

    def test_read_is_thread_safe(self) -> None:
        """Reading should be safe while writing happens."""
        from automataii.presentation.qt.animation.compute_thread import (
            DoubleBuffer,
            FrameData,
        )

        buffer = DoubleBuffer()
        results: list[int | None] = []
        errors: list[Exception] = []

        def reader() -> None:
            try:
                for _ in range(100):
                    front = buffer.read_front()
                    if front is not None:
                        results.append(front.frame_id)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def writer() -> None:
            try:
                for i in range(100):
                    frame = FrameData(
                        frame_id=i,
                        timestamp=float(i) * 0.033,
                        mechanism_positions={},
                        skeleton_joints=None,
                    )
                    buffer.write_back(frame)
                    buffer.swap()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        reader_thread = threading.Thread(target=reader)
        writer_thread = threading.Thread(target=writer)

        reader_thread.start()
        writer_thread.start()

        reader_thread.join()
        writer_thread.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        # Results should be monotonically increasing (no frame inversion)
        non_none_results = [r for r in results if r is not None]
        for i in range(1, len(non_none_results)):
            assert non_none_results[i] >= non_none_results[i - 1], (
                f"Frame inversion: {non_none_results[i - 1]} > {non_none_results[i]}"
            )


class TestFrameData:
    """Test the immutable frame data structure."""

    def test_frame_data_is_frozen(self) -> None:
        """FrameData should be immutable."""
        from automataii.presentation.qt.animation.compute_thread import FrameData

        frame = FrameData(
            frame_id=1,
            timestamp=0.033,
            mechanism_positions={},
            skeleton_joints=None,
        )

        with pytest.raises((AttributeError, TypeError)):
            frame.frame_id = 2  # type: ignore[misc]

    def test_frame_data_stores_numpy_arrays(self) -> None:
        """FrameData should correctly store numpy arrays."""
        from automataii.presentation.qt.animation.compute_thread import FrameData

        positions = {"mech_1": np.array([[1.0, 2.0], [3.0, 4.0]])}
        joints = np.array([[0.0, 0.0], [1.0, 1.0]])

        frame = FrameData(
            frame_id=1,
            timestamp=0.033,
            mechanism_positions=positions,
            skeleton_joints=joints,
        )

        assert np.array_equal(frame.mechanism_positions["mech_1"], positions["mech_1"])
        assert np.array_equal(frame.skeleton_joints, joints)


# =============================================================================
# COMPUTE THREAD TESTS
# =============================================================================


class TestComputeThread:
    """Test the compute thread implementation."""

    def test_thread_starts_and_stops(self) -> None:
        """Thread should start and stop cleanly."""
        from automataii.presentation.qt.animation.compute_thread import (
            ComputeThread,
            DoubleBuffer,
            FrameData,
        )

        buffer = DoubleBuffer()
        frame_count = 0

        def compute_fn(timestamp: float) -> FrameData:
            nonlocal frame_count
            frame_count += 1
            return FrameData(
                frame_id=frame_count,
                timestamp=timestamp,
                mechanism_positions={},
                skeleton_joints=None,
            )

        thread = ComputeThread(buffer, compute_fn, target_fps=60)

        assert not thread.is_alive()

        thread.start()
        time.sleep(0.1)  # Let it run for ~6 frames at 60 FPS
        assert thread.is_alive()

        thread.stop()
        thread.join(timeout=1.0)

        assert not thread.is_alive()
        assert frame_count > 0

    def test_thread_produces_frames_at_target_rate(self) -> None:
        """Thread should produce frames at approximately the target FPS."""
        from automataii.presentation.qt.animation.compute_thread import (
            ComputeThread,
            DoubleBuffer,
            FrameData,
        )

        buffer = DoubleBuffer()
        frame_count = 0
        target_fps = 30

        def compute_fn(timestamp: float) -> FrameData:
            nonlocal frame_count
            frame_count += 1
            return FrameData(
                frame_id=frame_count,
                timestamp=timestamp,
                mechanism_positions={},
                skeleton_joints=None,
            )

        thread = ComputeThread(buffer, compute_fn, target_fps=target_fps)

        thread.start()
        time.sleep(1.0)  # Run for 1 second
        thread.stop()
        thread.join(timeout=1.0)

        # Should have produced approximately 30 frames (+/- 10%)
        expected_frames = target_fps
        assert frame_count >= expected_frames * 0.8, (
            f"Expected ~{expected_frames} frames, got {frame_count}"
        )
        assert frame_count <= expected_frames * 1.2, (
            f"Expected ~{expected_frames} frames, got {frame_count}"
        )

    def test_buffer_receives_computed_frames(self) -> None:
        """Buffer should contain frames produced by compute thread."""
        from automataii.presentation.qt.animation.compute_thread import (
            ComputeThread,
            DoubleBuffer,
            FrameData,
        )

        buffer = DoubleBuffer()
        frame_count = 0

        def compute_fn(timestamp: float) -> FrameData:
            nonlocal frame_count
            frame_count += 1
            return FrameData(
                frame_id=frame_count,
                timestamp=timestamp,
                mechanism_positions={"test": np.array([[float(frame_count), 0.0]])},
                skeleton_joints=None,
            )

        thread = ComputeThread(buffer, compute_fn, target_fps=60)

        thread.start()
        time.sleep(0.2)  # Let some frames be produced
        thread.stop()
        thread.join(timeout=1.0)

        # Buffer should have the latest frame
        front = buffer.read_front()
        assert front is not None
        assert front.frame_id > 0

    def test_thread_handles_slow_compute_gracefully(self) -> None:
        """Thread should handle compute functions that take longer than frame time."""
        from automataii.presentation.qt.animation.compute_thread import (
            ComputeThread,
            DoubleBuffer,
            FrameData,
        )

        buffer = DoubleBuffer()
        frame_count = 0

        def slow_compute_fn(timestamp: float) -> FrameData:
            nonlocal frame_count
            frame_count += 1
            time.sleep(0.05)  # Slower than 30 FPS frame time
            return FrameData(
                frame_id=frame_count,
                timestamp=timestamp,
                mechanism_positions={},
                skeleton_joints=None,
            )

        thread = ComputeThread(buffer, slow_compute_fn, target_fps=30)

        thread.start()
        time.sleep(0.3)
        thread.stop()
        thread.join(timeout=1.0)

        # Should still produce frames, just slower than target
        assert frame_count > 0
        # At 50ms per frame, should have ~6 frames in 0.3 seconds
        assert frame_count <= 10


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestComputeRenderIntegration:
    """Test compute/render thread integration."""

    def test_producer_consumer_pattern(self) -> None:
        """Verify producer-consumer pattern works correctly."""
        from automataii.presentation.qt.animation.compute_thread import (
            ComputeThread,
            DoubleBuffer,
            FrameData,
        )

        buffer = DoubleBuffer()
        produced_frames: list[int] = []
        consumed_frames: list[int] = []

        def compute_fn(timestamp: float) -> FrameData:
            frame_id = len(produced_frames) + 1
            produced_frames.append(frame_id)
            return FrameData(
                frame_id=frame_id,
                timestamp=timestamp,
                mechanism_positions={},
                skeleton_joints=None,
            )

        def consumer() -> None:
            for _ in range(50):
                front = buffer.read_front()
                if front is not None:
                    consumed_frames.append(front.frame_id)
                time.sleep(0.02)

        thread = ComputeThread(buffer, compute_fn, target_fps=60)

        # Start producer
        thread.start()

        # Start consumer
        consumer_thread = threading.Thread(target=consumer)
        consumer_thread.start()

        # Wait for consumer to finish
        consumer_thread.join()

        # Stop producer
        thread.stop()
        thread.join(timeout=1.0)

        # Both should have processed frames
        assert len(produced_frames) > 0
        assert len(consumed_frames) > 0

        # Consumed frames should be a subset of produced frames
        for frame_id in consumed_frames:
            assert frame_id in produced_frames

    def test_no_data_loss_under_load(self) -> None:
        """Verify latest data is always available under load."""
        from automataii.presentation.qt.animation.compute_thread import (
            ComputeThread,
            DoubleBuffer,
            FrameData,
        )

        buffer = DoubleBuffer()
        max_frame_id = 0

        def compute_fn(timestamp: float) -> FrameData:
            nonlocal max_frame_id
            max_frame_id += 1
            return FrameData(
                frame_id=max_frame_id,
                timestamp=timestamp,
                mechanism_positions={},
                skeleton_joints=None,
            )

        thread = ComputeThread(buffer, compute_fn, target_fps=120)  # High FPS

        thread.start()
        time.sleep(0.5)
        thread.stop()
        thread.join(timeout=1.0)

        # Final buffer should have a recent frame
        front = buffer.read_front()
        assert front is not None
        # Should be close to max_frame_id (within a few frames)
        assert front.frame_id >= max_frame_id - 5
