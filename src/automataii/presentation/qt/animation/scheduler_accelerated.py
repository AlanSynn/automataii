"""
Accelerated Animation Scheduler.

Extends CentralAnimationScheduler with off-thread computation via
RealTimeAnimationEngine. Provides backwards-compatible API while
enabling high-performance animation.

Architecture: Presentation Layer
Pattern: Adapter + Decorator
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from automataii.presentation.qt.animation.compute_thread import FrameData
from automataii.presentation.qt.animation.realtime_engine import (
    EngineConfig,
    RealTimeAnimationEngine,
)
from automataii.presentation.qt.animation.scheduler import CentralAnimationScheduler

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

logger = logging.getLogger(__name__)


class AcceleratedAnimationScheduler(CentralAnimationScheduler):
    """
    Animation scheduler with accelerated off-thread computation.

    Extends CentralAnimationScheduler with RealTimeAnimationEngine for
    heavy computation (ARAP, IK, mechanisms) while maintaining the
    same subscription-based API for UI updates.

    Features:
    - All CentralAnimationScheduler features
    - Off-thread computation via RealTimeAnimationEngine
    - Frame data subscriptions for receiving computed data
    - Combined statistics from scheduler and engine

    Usage:
        scheduler = AcceleratedAnimationScheduler(target_fps=60)

        # Register animation sources
        scheduler.register_mechanism("mech_1", "4_bar_linkage", params)

        # Subscribe to frame data
        scheduler.subscribe_to_frames(on_frame_ready)

        # Traditional subscriptions still work
        scheduler.subscribe(callback, AnimationPriority.NORMAL, "my_tab")

        # Start/stop as usual
        scheduler.start()
        scheduler.stop()
    """

    def __init__(
        self,
        target_fps: int = 60,
        enable_threading: bool = True,
        parent: Any = None,
    ) -> None:
        """
        Initialize accelerated scheduler.

        Args:
            target_fps: Target frames per second
            enable_threading: Enable background computation thread
            parent: Qt parent object
        """
        super().__init__(parent)

        # Override target FPS
        self.target_fps = target_fps

        # Create real-time engine with matching config
        engine_config = EngineConfig(
            target_fps=target_fps,
            enable_threading=enable_threading,
        )
        self._engine = RealTimeAnimationEngine(engine_config)

        # Frame data subscribers
        self._frame_subscribers: list[Callable[[FrameData], None]] = []

        # Connect internal frame dispatch
        self._engine.on_frame_ready(self._dispatch_frame)

        logger.info(
            f"AcceleratedAnimationScheduler initialized "
            f"(fps={target_fps}, threading={enable_threading})"
        )

    # =========================================================================
    # SOURCE REGISTRATION (Delegate to Engine)
    # =========================================================================

    def register_mechanism(
        self,
        mechanism_id: str,
        mechanism_type: str,
        params: dict[str, Any],
        simulation_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a mechanism for computation.

        Args:
            mechanism_id: Unique identifier
            mechanism_type: Type of mechanism
            params: Mechanism parameters
            simulation_data: Pre-computed simulation data
        """
        self._engine.register_mechanism(
            mechanism_id=mechanism_id,
            mechanism_type=mechanism_type,
            params=params,
            simulation_data=simulation_data,
        )

    def unregister_mechanism(self, mechanism_id: str) -> None:
        """Remove a mechanism from computation."""
        self._engine.unregister_mechanism(mechanism_id)

    def register_skeleton(
        self,
        skeleton_id: str,
        joint_positions: npt.NDArray[np.float64],
        bone_connections: list[tuple[int, int]],
    ) -> None:
        """
        Register a skeleton for computation.

        Args:
            skeleton_id: Unique identifier
            joint_positions: (J, 2) joint positions
            bone_connections: List of (start, end) bone pairs
        """
        self._engine.register_skeleton(
            skeleton_id=skeleton_id,
            joint_positions=joint_positions,
            bone_connections=bone_connections,
        )

    def unregister_skeleton(self, skeleton_id: str) -> None:
        """Remove a skeleton from computation."""
        self._engine.unregister_skeleton(skeleton_id)

    def update_ik_target(
        self,
        skeleton_id: str,
        target_name: str,
        position: tuple[float, float],
    ) -> None:
        """
        Update an IK target position.

        Args:
            skeleton_id: Skeleton to update
            target_name: Name of the IK target
            position: New target position (x, y)
        """
        self._engine.update_ik_target(skeleton_id, target_name, position)

    # =========================================================================
    # FRAME DATA ACCESS
    # =========================================================================

    def subscribe_to_frames(
        self,
        callback: Callable[[FrameData], None],
    ) -> None:
        """
        Subscribe to computed frame data.

        Args:
            callback: Function called with FrameData each frame
        """
        self._frame_subscribers.append(callback)
        logger.debug(f"Frame subscriber added (total: {len(self._frame_subscribers)})")

    def unsubscribe_from_frames(
        self,
        callback: Callable[[FrameData], None],
    ) -> bool:
        """
        Unsubscribe from frame data.

        Args:
            callback: Previously registered callback

        Returns:
            True if callback was found and removed
        """
        try:
            self._frame_subscribers.remove(callback)
            return True
        except ValueError:
            return False

    def get_current_frame(self) -> FrameData | None:
        """
        Get the most recent computed frame.

        Returns:
            Latest frame data, or None if not available
        """
        return self._engine.get_current_frame()

    def _dispatch_frame(self, frame: FrameData) -> None:
        """Dispatch frame data to all subscribers."""
        for callback in self._frame_subscribers:
            try:
                callback(frame)
            except Exception as e:
                logger.exception(f"Frame subscriber error: {e}")

    # =========================================================================
    # LIFECYCLE (Extended)
    # =========================================================================

    def start(self) -> None:
        """Start both scheduler and compute engine."""
        self._engine.start()
        super().start()
        logger.info("AcceleratedAnimationScheduler started")

    def stop(self) -> None:
        """Stop both scheduler and compute engine."""
        super().stop()
        self._engine.stop()
        logger.info("AcceleratedAnimationScheduler stopped")

    def pause(self) -> None:
        """Pause both scheduler and compute engine."""
        super().pause()
        self._engine.pause()

    def resume(self) -> None:
        """Resume both scheduler and compute engine."""
        super().resume()
        self._engine.resume()

    # =========================================================================
    # SYNCHRONOUS OPERATION (For Testing / Single-Threaded Mode)
    # =========================================================================

    def start_engine_only(self) -> None:
        """
        Start only the compute engine (no QTimer).

        Use this for testing or single-threaded operation.
        """
        self._engine.start()
        self._running = True

    def stop_engine_only(self) -> None:
        """Stop only the compute engine."""
        self._engine.stop()
        self._running = False

    def compute_and_dispatch(self, delta_time: float) -> FrameData:
        """
        Compute a frame synchronously and dispatch to subscribers.

        Use this for single-threaded mode or testing.

        Args:
            delta_time: Time since last frame

        Returns:
            Computed frame data
        """
        frame = self._engine.compute_frame_sync(delta_time)
        self._dispatch_frame(frame)
        return frame

    def process_frame_manual(self, delta_time: float) -> None:
        """
        Manually process a frame (simulates QTimer callback).

        Dispatches to traditional subscriptions.

        Args:
            delta_time: Time since last frame
        """
        # Update timing
        self._total_time += delta_time
        self._frame_count += 1

        # Process subscriptions (sorted by priority)
        sorted_subs = sorted(
            self._subscriptions.values(),
            key=lambda s: s.priority,
        )

        for sub in sorted_subs:
            if not sub.enabled:
                continue

            sub._frame_counter += 1
            if sub._frame_counter < sub.frame_skip:
                continue
            sub._frame_counter = 0

            try:
                sub.callback(delta_time)
            except Exception as e:
                logger.exception(f"Animation callback error ({sub.owner_id}): {e}")

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_engine_stats(self) -> dict[str, Any]:
        """
        Get compute engine statistics.

        Returns:
            Engine performance and state info
        """
        return self._engine.get_stats()

    def get_combined_stats(self) -> dict[str, Any]:
        """
        Get combined scheduler and engine statistics.

        Returns:
            Merged statistics from both components
        """
        scheduler_stats = self.get_stats()
        engine_stats = self._engine.get_stats()

        return {
            # Scheduler stats
            "running": scheduler_stats["running"],
            "paused": scheduler_stats["paused"],
            "scheduler_frame_count": scheduler_stats["frame_count"],
            "total_time": scheduler_stats["total_time"],
            "target_fps": scheduler_stats["target_fps"],
            "subscriptions": scheduler_stats["subscriptions"],
            # Engine stats
            "engine_frame_count": engine_stats["frame_count"],
            "avg_compute_time_ms": engine_stats["avg_compute_time_ms"],
            "actual_fps": engine_stats["actual_fps"],
            "mechanism_count": engine_stats["mechanism_count"],
            "skeleton_count": engine_stats["skeleton_count"],
            "threading_enabled": engine_stats["threading_enabled"],
        }
