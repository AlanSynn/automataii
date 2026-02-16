"""
Central Animation Scheduler.

Single animation loop for all tabs. Eliminates frame jitter from
multiple independent timers.

Architecture: Presentation Layer
Pattern: Observer + Singleton
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum, auto
from typing import TYPE_CHECKING

from PyQt6.QtCore import QElapsedTimer, QObject, QTimer, pyqtSignal

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AnimationPriority(IntEnum):
    """Animation update priority levels."""

    CRITICAL = auto()  # IK updates (must run every frame)
    HIGH = auto()  # Mechanism updates
    NORMAL = auto()  # Path traces, visual effects
    LOW = auto()  # Background updates, statistics


@dataclass
class AnimationSubscription:
    """Subscription to the animation scheduler."""

    callback: Callable[[float], None]  # Called with delta_time
    priority: AnimationPriority
    owner_id: str
    enabled: bool = True
    frame_skip: int = 1  # Process every N frames (1 = every frame)
    _frame_counter: int = 0


class CentralAnimationScheduler(QObject):
    """
    Central animation scheduler for unified frame updates.

    Features:
    - Single QTimer for all animations (33ms = ~30 FPS)
    - Priority-based update ordering
    - Frame skip support for non-critical updates
    - Synchronized delta time across all subscribers
    - Pause/resume for all animations

    Usage:
        scheduler = CentralAnimationScheduler()

        # Subscribe to animation updates
        scheduler.subscribe(
            callback=my_update_function,
            priority=AnimationPriority.HIGH,
            owner_id="mechanism_tab",
        )

        # Start the scheduler
        scheduler.start()

        # Pause/resume all animations
        scheduler.pause()
        scheduler.resume()
    """

    # Signals
    frame_started = pyqtSignal(float)  # delta_time
    frame_ended = pyqtSignal(float)  # frame_time

    # Default settings
    DEFAULT_FPS = 30
    DEFAULT_FRAME_TIME_MS = 33  # 1000 / 30

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        # Timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_frame)

        # Timing
        self._elapsed_timer = QElapsedTimer()
        self._last_frame_time: float = 0.0
        self._total_time: float = 0.0
        self._frame_count: int = 0

        # Subscriptions
        self._subscriptions: dict[str, AnimationSubscription] = {}
        self._sorted_subscriptions_cache: tuple[AnimationSubscription, ...] = ()
        self._subscriptions_dirty = False

        # State
        self._running = False
        self._paused = False
        self._target_fps = self.DEFAULT_FPS
        self._frame_time_ms = self.DEFAULT_FRAME_TIME_MS

        logger.info("CentralAnimationScheduler initialized")

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def total_time(self) -> float:
        return self._total_time

    @property
    def target_fps(self) -> int:
        return self._target_fps

    @target_fps.setter
    def target_fps(self, fps: int) -> None:
        self._target_fps = max(1, min(120, fps))
        self._frame_time_ms = 1000 // self._target_fps
        if self._running and not self._paused:
            self._timer.setInterval(self._frame_time_ms)

    # =========================================================================
    # SUBSCRIPTION MANAGEMENT
    # =========================================================================

    def subscribe(
        self,
        callback: Callable[[float], None],
        priority: AnimationPriority,
        owner_id: str,
        frame_skip: int = 1,
    ) -> str:
        """
        Subscribe to animation updates.

        Args:
            callback: Function called with delta_time each frame
            priority: Update priority (determines order)
            owner_id: Unique identifier for this subscription
            frame_skip: Process every N frames (1 = every frame)

        Returns:
            Subscription ID (same as owner_id)
        """
        if owner_id in self._subscriptions:
            logger.warning(f"Replacing existing subscription: {owner_id}")

        self._subscriptions[owner_id] = AnimationSubscription(
            callback=callback,
            priority=priority,
            owner_id=owner_id,
            enabled=True,
            frame_skip=max(1, frame_skip),
        )
        self._subscriptions_dirty = True

        logger.debug("Animation subscription added: %s (priority=%s)", owner_id, priority.name)
        return owner_id

    def unsubscribe(self, owner_id: str) -> bool:
        """Remove a subscription."""
        if owner_id in self._subscriptions:
            del self._subscriptions[owner_id]
            self._subscriptions_dirty = True
            logger.debug("Animation subscription removed: %s", owner_id)
            return True
        return False

    def enable_subscription(self, owner_id: str, enabled: bool = True) -> None:
        """Enable or disable a subscription without removing it."""
        if owner_id in self._subscriptions:
            self._subscriptions[owner_id].enabled = enabled

    def set_frame_skip(self, owner_id: str, frame_skip: int) -> None:
        """Set frame skip for a subscription."""
        if owner_id in self._subscriptions:
            self._subscriptions[owner_id].frame_skip = max(1, frame_skip)

    # =========================================================================
    # LIFECYCLE CONTROL
    # =========================================================================

    def start(self) -> None:
        """Start the animation scheduler."""
        if self._running:
            return

        self._running = True
        self._paused = False
        self._elapsed_timer.start()
        self._last_frame_time = 0.0
        self._timer.start(self._frame_time_ms)
        logger.info(f"Animation scheduler started ({self._target_fps} FPS)")

    def stop(self) -> None:
        """Stop the animation scheduler."""
        if not self._running:
            return

        self._timer.stop()
        self._running = False
        self._paused = False
        logger.info("Animation scheduler stopped")

    def pause(self) -> None:
        """Pause the scheduler without resetting state."""
        if not self._running or self._paused:
            return

        self._timer.stop()
        self._paused = True
        logger.debug("Animation scheduler paused")

    def resume(self) -> None:
        """Resume the scheduler from pause."""
        if not self._running or not self._paused:
            return

        self._elapsed_timer.restart()
        self._last_frame_time = 0.0
        self._timer.start(self._frame_time_ms)
        self._paused = False
        logger.debug("Animation scheduler resumed")

    def reset(self) -> None:
        """Reset timing counters."""
        self._total_time = 0.0
        self._frame_count = 0
        self._last_frame_time = 0.0
        if self._running:
            self._elapsed_timer.restart()
        logger.debug("Animation scheduler reset")

    # =========================================================================
    # FRAME UPDATE
    # =========================================================================

    def _on_frame(self) -> None:
        """Process a single animation frame."""
        # Calculate delta time
        current_time = self._elapsed_timer.elapsed() / 1000.0
        delta_time = current_time - self._last_frame_time
        self._last_frame_time = current_time
        self._total_time += delta_time
        self._frame_count += 1

        # Debug: Log frame processing (every 30 frames = ~1 second)
        if logger.isEnabledFor(logging.DEBUG) and self._frame_count % 30 == 1:
            logger.debug(
                "[SCHEDULER] Frame %d: %d subscriptions, dt=%.4f",
                self._frame_count,
                len(self._subscriptions),
                delta_time,
            )

        # Emit frame started
        self.frame_started.emit(delta_time)

        sorted_subs = self._get_sorted_subscriptions()

        if not sorted_subs:
            self.frame_ended.emit(0.0)
            return

        # Process each subscription
        frame_start = self._elapsed_timer.elapsed()

        for sub in sorted_subs:
            if not sub.enabled:
                continue

            # Frame skip check
            sub._frame_counter += 1
            if sub._frame_counter < sub.frame_skip:
                continue
            sub._frame_counter = 0

            # Debug: Log callback dispatch (first 5 frames only)
            if logger.isEnabledFor(logging.DEBUG) and self._frame_count <= 5:
                logger.debug("[SCHEDULER] Dispatching to %s", sub.owner_id)

            # Call the callback
            try:
                sub.callback(delta_time)
            except Exception as e:
                logger.exception("Animation callback error (%s): %s", sub.owner_id, e)

        # Calculate frame processing time
        frame_time = (self._elapsed_timer.elapsed() - frame_start) / 1000.0

        # Emit frame ended
        self.frame_ended.emit(frame_time)

    def _get_sorted_subscriptions(self) -> tuple[AnimationSubscription, ...]:
        """Get subscriptions ordered by priority with cache."""
        if self._subscriptions_dirty or len(self._sorted_subscriptions_cache) != len(
            self._subscriptions
        ):
            self._sorted_subscriptions_cache = tuple(
                sorted(
                    self._subscriptions.values(),
                    key=lambda s: s.priority,
                )
            )
            self._subscriptions_dirty = False
        return self._sorted_subscriptions_cache

    # =========================================================================
    # DEBUG / STATISTICS
    # =========================================================================

    def get_stats(self) -> dict:
        """Get scheduler statistics."""
        return {
            "running": self._running,
            "paused": self._paused,
            "frame_count": self._frame_count,
            "total_time": self._total_time,
            "target_fps": self._target_fps,
            "subscriptions": len(self._subscriptions),
            "enabled_subscriptions": sum(
                1 for s in self._subscriptions.values() if s.enabled
            ),
        }

    def list_subscriptions(self) -> list[dict]:
        """List all subscriptions with their status."""
        return [
            {
                "owner_id": s.owner_id,
                "priority": s.priority.name,
                "enabled": s.enabled,
                "frame_skip": s.frame_skip,
            }
            for s in self._get_sorted_subscriptions()
        ]
