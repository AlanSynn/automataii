"""
Real-Time Animation Engine.

This module provides a high-level facade that integrates:
- ComputeThread for off-main-thread computation
- DoubleBuffer for thread-safe frame exchange
- AcceleratedARAP for fast deformation
- OpenGL rendering (optional)

Architecture: Presentation Layer
Pattern: Facade + Observer

Usage:
    engine = RealTimeAnimationEngine()

    # Register animation sources
    engine.register_mechanism("mech_1", mechanism_data)
    engine.register_skeleton("skel_1", skeleton_data)

    # Start the engine
    engine.start()

    # Get latest frame for rendering (call from Qt main thread)
    frame = engine.get_current_frame()
    if frame:
        # Update Qt graphics items with frame data
        for mech_id, positions in frame.mechanism_positions.items():
            update_mechanism_visuals(mech_id, positions)

    # Stop when done
    engine.stop()
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from automataii.presentation.qt.animation.compute_thread import (
    ComputeThread,
    DoubleBuffer,
    FrameData,
)

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class MechanismSource:
    """Data source for mechanism animation."""

    mechanism_id: str
    mechanism_type: str  # "4_bar_linkage", "cam", "gear", etc.
    params: dict[str, Any]
    simulation_data: dict[str, Any] | None = None
    num_frames: int = 360


@dataclass
class SkeletonSource:
    """Data source for skeleton animation."""

    skeleton_id: str
    joint_positions: npt.NDArray[np.float64]  # (J, 2)
    bone_connections: list[tuple[int, int]]
    ik_targets: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass
class EngineConfig:
    """Configuration for the real-time engine."""

    target_fps: int = 60
    mechanism_batch_size: int = 10  # Max mechanisms to update per frame
    enable_arap: bool = True
    enable_ik: bool = True
    enable_threading: bool = True


# =============================================================================
# REAL-TIME ANIMATION ENGINE
# =============================================================================


class RealTimeAnimationEngine:
    """
    High-level facade for real-time animation.

    Integrates compute threading, accelerated ARAP, and frame buffering
    into a simple API.

    Features:
    - Off-main-thread computation
    - Thread-safe frame exchange via double buffering
    - Automatic backend selection (native > numba > numpy)
    - Performance monitoring

    Usage:
        engine = RealTimeAnimationEngine(config)
        engine.register_mechanism("mech_1", data)
        engine.start()

        # In render loop:
        frame = engine.get_current_frame()
        if frame:
            render(frame)

        engine.stop()
    """

    def __init__(self, config: EngineConfig | None = None):
        """
        Initialize the engine.

        Args:
            config: Engine configuration (uses defaults if None)
        """
        self._config = config or EngineConfig()

        # Animation sources
        self._mechanisms: dict[str, MechanismSource] = {}
        self._skeletons: dict[str, SkeletonSource] = {}

        # Threading infrastructure
        self._buffer = DoubleBuffer()
        self._compute_thread: ComputeThread | None = None

        # Animation state
        self._animation_time = 0.0
        self._frame_count = 0
        self._is_running = False
        self._is_paused = False

        # Performance stats
        self._last_compute_time = 0.0
        self._avg_compute_time = 0.0
        self._frame_times: list[float] = []

        # Callbacks
        self._on_frame_ready: list[Callable[[FrameData], None]] = []

        logger.info(f"RealTimeAnimationEngine initialized (fps={self._config.target_fps})")

    # =========================================================================
    # SOURCE REGISTRATION
    # =========================================================================

    def register_mechanism(
        self,
        mechanism_id: str,
        mechanism_type: str,
        params: dict[str, Any],
        simulation_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a mechanism for animation.

        Args:
            mechanism_id: Unique identifier
            mechanism_type: Type of mechanism
            params: Mechanism parameters
            simulation_data: Pre-computed simulation data
        """
        self._mechanisms[mechanism_id] = MechanismSource(
            mechanism_id=mechanism_id,
            mechanism_type=mechanism_type,
            params=params,
            simulation_data=simulation_data,
        )
        logger.debug(f"Registered mechanism: {mechanism_id} ({mechanism_type})")

    def unregister_mechanism(self, mechanism_id: str) -> None:
        """Remove a mechanism from animation."""
        if mechanism_id in self._mechanisms:
            del self._mechanisms[mechanism_id]
            logger.debug(f"Unregistered mechanism: {mechanism_id}")

    def register_skeleton(
        self,
        skeleton_id: str,
        joint_positions: npt.NDArray[np.float64],
        bone_connections: list[tuple[int, int]],
    ) -> None:
        """
        Register a skeleton for animation.

        Args:
            skeleton_id: Unique identifier
            joint_positions: (J, 2) joint positions
            bone_connections: List of (start, end) bone pairs
        """
        self._skeletons[skeleton_id] = SkeletonSource(
            skeleton_id=skeleton_id,
            joint_positions=joint_positions.copy(),
            bone_connections=bone_connections,
        )
        logger.debug(f"Registered skeleton: {skeleton_id}")

    def unregister_skeleton(self, skeleton_id: str) -> None:
        """Remove a skeleton from animation."""
        if skeleton_id in self._skeletons:
            del self._skeletons[skeleton_id]
            logger.debug(f"Unregistered skeleton: {skeleton_id}")

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
        if skeleton_id in self._skeletons:
            self._skeletons[skeleton_id].ik_targets[target_name] = position

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def start(self) -> None:
        """Start the animation engine."""
        if self._is_running:
            return

        self._is_running = True
        self._animation_time = 0.0
        self._frame_count = 0

        if self._config.enable_threading:
            self._compute_thread = ComputeThread(
                buffer=self._buffer,
                compute_fn=self._compute_frame,
                target_fps=self._config.target_fps,
            )
            self._compute_thread.start()
            logger.info("RealTimeAnimationEngine started (threaded mode)")
        else:
            logger.info("RealTimeAnimationEngine started (single-threaded mode)")

    def stop(self) -> None:
        """Stop the animation engine."""
        if not self._is_running:
            return

        self._is_running = False

        if self._compute_thread is not None:
            self._compute_thread.stop()
            self._compute_thread.join(timeout=1.0)
            self._compute_thread = None

        logger.info("RealTimeAnimationEngine stopped")

    def pause(self) -> None:
        """Pause animation (keeps thread alive)."""
        self._is_paused = True

    def resume(self) -> None:
        """Resume animation from pause."""
        self._is_paused = False

    @property
    def is_running(self) -> bool:
        """Check if engine is running."""
        return self._is_running

    @property
    def is_paused(self) -> bool:
        """Check if engine is paused."""
        return self._is_paused

    # =========================================================================
    # FRAME ACCESS
    # =========================================================================

    def get_current_frame(self) -> FrameData | None:
        """
        Get the most recent computed frame.

        This is thread-safe and should be called from the Qt main thread.

        Returns:
            Latest frame data, or None if no frame is ready
        """
        return self._buffer.read_front()

    def compute_frame_sync(self, delta_time: float) -> FrameData:
        """
        Compute a frame synchronously (for single-threaded mode).

        Args:
            delta_time: Time since last frame

        Returns:
            Computed frame data
        """
        self._animation_time += delta_time
        return self._compute_frame(self._animation_time)

    # =========================================================================
    # CALLBACKS
    # =========================================================================

    def on_frame_ready(self, callback: Callable[[FrameData], None]) -> None:
        """
        Register a callback for when a new frame is ready.

        Args:
            callback: Function to call with frame data
        """
        self._on_frame_ready.append(callback)

    # =========================================================================
    # INTERNAL COMPUTATION
    # =========================================================================

    def _compute_frame(self, timestamp: float) -> FrameData:
        """
        Compute a single animation frame.

        This runs on the compute thread (or main thread in sync mode).

        Args:
            timestamp: Animation time in seconds

        Returns:
            Computed frame data
        """
        start_time = time.perf_counter()

        if self._is_paused:
            # Return empty frame when paused
            return FrameData(
                frame_id=self._frame_count,
                timestamp=timestamp,
                mechanism_positions={},
                skeleton_joints=None,
                arap_vertices=None,
            )

        # Compute mechanism positions
        mechanism_positions = self._compute_mechanisms(timestamp)

        # Compute skeleton (if any)
        skeleton_joints = self._compute_skeleton(timestamp)

        # Compute ARAP deformation (if enabled)
        arap_vertices = None
        if self._config.enable_arap:
            arap_vertices = self._compute_arap(timestamp)

        self._frame_count += 1

        # Track performance
        compute_time = time.perf_counter() - start_time
        self._last_compute_time = compute_time
        self._frame_times.append(compute_time)
        if len(self._frame_times) > 60:
            self._frame_times.pop(0)
        self._avg_compute_time = sum(self._frame_times) / len(self._frame_times)

        return FrameData(
            frame_id=self._frame_count,
            timestamp=timestamp,
            mechanism_positions=mechanism_positions,
            skeleton_joints=skeleton_joints,
            arap_vertices=arap_vertices,
        )

    def _compute_mechanisms(self, timestamp: float) -> dict[str, npt.NDArray[np.float64]]:
        """Compute positions for all registered mechanisms."""
        positions = {}

        for mech_id, source in self._mechanisms.items():
            if source.simulation_data and "joint_positions" in source.simulation_data:
                # Use pre-computed simulation data
                joint_data = source.simulation_data["joint_positions"]
                num_frames = len(joint_data.get("p1_positions", []))

                if num_frames > 0:
                    # Map timestamp to frame index
                    normalized_time = (timestamp % (2 * np.pi)) / (2 * np.pi)
                    frame_idx = int(normalized_time * (num_frames - 1))

                    # Extract positions
                    if "p3_positions" in joint_data:
                        p3 = np.array(joint_data["p3_positions"][frame_idx])
                        p4 = np.array(joint_data["p4_positions"][frame_idx])
                        positions[mech_id] = np.array([p3, p4])
            else:
                # Compute analytically (placeholder for now)
                positions[mech_id] = np.array([[0.0, 0.0], [1.0, 1.0]])

        return positions

    def _compute_skeleton(self, timestamp: float) -> npt.NDArray[np.float64] | None:
        """Compute skeleton joint positions with IK."""
        if not self._skeletons:
            return None

        # For now, return first skeleton's joints
        # TODO: Integrate with IK solver
        first_skeleton = next(iter(self._skeletons.values()))
        return first_skeleton.joint_positions.copy()

    def _compute_arap(self, timestamp: float) -> npt.NDArray[np.float64] | None:
        """Compute ARAP deformation."""
        # Placeholder for ARAP integration
        # This would be used for body part deformation
        return None

    # =========================================================================
    # PERFORMANCE STATS
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """
        Get performance statistics.

        Returns:
            Dict with frame count, timing, and backend info
        """
        from automataii.domain.animation.arap_accelerated import get_backend

        return {
            "frame_count": self._frame_count,
            "animation_time": self._animation_time,
            "last_compute_time_ms": self._last_compute_time * 1000,
            "avg_compute_time_ms": self._avg_compute_time * 1000,
            "target_fps": self._config.target_fps,
            "actual_fps": 1.0 / self._avg_compute_time if self._avg_compute_time > 0 else 0,
            "mechanism_count": len(self._mechanisms),
            "skeleton_count": len(self._skeletons),
            "arap_backend": get_backend(),
            "threading_enabled": self._config.enable_threading,
        }
