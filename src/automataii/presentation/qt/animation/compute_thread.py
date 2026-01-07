"""
Compute/Render Thread Separation Infrastructure.

This module provides thread-safe primitives for separating compute-intensive
animation calculations from the Qt render thread.

Architecture: Presentation Layer
Pattern: Producer-Consumer with Double Buffering

Components:
- FrameData: Immutable snapshot of computed frame state
- DoubleBuffer: Lock-free double buffer for frame exchange
- ComputeThread: Dedicated thread for animation computation

Usage:
    buffer = DoubleBuffer()

    def compute_fn(timestamp: float) -> FrameData:
        # Perform expensive computations
        return FrameData(...)

    thread = ComputeThread(buffer, compute_fn, target_fps=60)
    thread.start()

    # On render thread (Qt main thread):
    frame = buffer.read_front()
    if frame:
        # Update Qt graphics items with frame data
        pass

    # Cleanup:
    thread.stop()
    thread.join()
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


# =============================================================================
# FRAME DATA
# =============================================================================


@dataclass(frozen=True, slots=True)
class FrameData:
    """
    Immutable snapshot of computed frame state.

    This is the unit of exchange between compute and render threads.
    Immutability ensures thread safety without locks.

    Attributes:
        frame_id: Monotonically increasing frame identifier
        timestamp: Time when computation started (seconds)
        mechanism_positions: Dict mapping mechanism_id -> (N, 2) position array
        skeleton_joints: Optional (J, 2) joint positions
        arap_vertices: Optional (V, 2) ARAP-deformed vertices
    """

    frame_id: int
    timestamp: float
    mechanism_positions: dict[str, npt.NDArray[np.float64]]
    skeleton_joints: npt.NDArray[np.float64] | None
    arap_vertices: npt.NDArray[np.float64] | None


# =============================================================================
# DOUBLE BUFFER
# =============================================================================


class DoubleBuffer:
    """
    Lock-free double buffer for producer-consumer pattern.

    The producer (compute thread) writes to the back buffer,
    then swaps it to the front. The consumer (render thread)
    reads from the front buffer.

    Thread Safety:
    - swap() uses a lock to atomically exchange pointers
    - read_front() returns the current front (may be None)
    - write_back() only modifies the back buffer

    Performance:
    - O(1) swap (pointer exchange)
    - O(1) read (no copying)
    - Zero contention if producer and consumer are on different cores
    """

    __slots__ = ("_front", "_back", "_lock")

    def __init__(self) -> None:
        """Initialize empty double buffer."""
        self._front: FrameData | None = None
        self._back: FrameData | None = None
        self._lock = threading.Lock()

    def swap(self) -> None:
        """
        Atomically swap front and back buffers.

        After swap, the back buffer becomes the front buffer,
        making the most recent computed frame available for reading.
        """
        with self._lock:
            self._front, self._back = self._back, self._front

    def write_back(self, data: FrameData) -> None:
        """
        Write data to the back buffer.

        This does not block reading from the front buffer.

        Args:
            data: Frame data to write
        """
        self._back = data

    def read_front(self) -> FrameData | None:
        """
        Read the current front buffer.

        Returns None if no data has been swapped yet.

        Returns:
            Current front buffer frame data, or None
        """
        return self._front


# =============================================================================
# COMPUTE THREAD
# =============================================================================


class ComputeThread(threading.Thread):
    """
    Dedicated thread for animation computation.

    Runs a compute function at the target frame rate,
    writing results to a double buffer.

    Features:
    - Configurable target FPS (1-120)
    - Graceful shutdown via stop()
    - Handles slow compute functions (skips frames)
    - Daemon thread (won't block process exit)

    Usage:
        def compute_fn(timestamp: float) -> FrameData:
            # Expensive computations here
            return FrameData(...)

        buffer = DoubleBuffer()
        thread = ComputeThread(buffer, compute_fn, target_fps=60)
        thread.start()

        # Later:
        thread.stop()
        thread.join()
    """

    def __init__(
        self,
        buffer: DoubleBuffer,
        compute_fn: Callable[[float], FrameData],
        target_fps: int = 60,
    ) -> None:
        """
        Initialize compute thread.

        Args:
            buffer: Double buffer for frame exchange
            compute_fn: Function that computes a frame given timestamp
            target_fps: Target frames per second (1-120)
        """
        super().__init__(daemon=True, name="ComputeThread")
        self._buffer = buffer
        self._compute_fn = compute_fn
        self._target_fps = max(1, min(120, target_fps))
        self._running = False
        self._stop_event = threading.Event()

        logger.info(f"ComputeThread initialized (target_fps={self._target_fps})")

    @property
    def target_fps(self) -> int:
        """Get target frames per second."""
        return self._target_fps

    def run(self) -> None:
        """
        Main compute loop.

        Runs until stop() is called. Computes frames at target rate,
        handling slow computations gracefully.
        """
        self._running = True
        frame_time = 1.0 / self._target_fps
        start_time = time.perf_counter()

        logger.info("ComputeThread started")

        while not self._stop_event.is_set():
            loop_start = time.perf_counter()
            timestamp = loop_start - start_time

            try:
                # Compute new frame
                frame_data = self._compute_fn(timestamp)

                # Write to back buffer and swap
                self._buffer.write_back(frame_data)
                self._buffer.swap()

            except Exception:
                logger.exception("ComputeThread: compute function error")

            # Calculate sleep time to maintain target FPS
            compute_time = time.perf_counter() - loop_start
            sleep_time = frame_time - compute_time

            if sleep_time > 0:
                # Use Event.wait() for interruptible sleep
                self._stop_event.wait(sleep_time)
            else:
                # Compute took longer than frame time
                # Log warning but continue (frame skip)
                if compute_time > frame_time * 2:
                    logger.debug(
                        f"ComputeThread: frame took {compute_time*1000:.1f}ms "
                        f"(target: {frame_time*1000:.1f}ms)"
                    )

        self._running = False
        logger.info("ComputeThread stopped")

    def stop(self) -> None:
        """
        Signal the thread to stop.

        Call join() after this to wait for the thread to finish.
        """
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        """Check if the compute loop is currently running."""
        return self._running
