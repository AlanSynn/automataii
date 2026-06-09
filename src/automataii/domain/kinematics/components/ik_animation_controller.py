"""
IK Animation Controller - Animation timing and easing control.

Extracted from IKManager. Handles animation timing profiles
and easing curve calculations.

Design Pattern: Controller (animation state management)
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class TimingProfile(Enum):
    """Animation timing profiles."""

    LINEAR = "linear"
    EASE_IN_OUT = "ease_in_out"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    BOUNCE = "bounce"
    ELASTIC = "elastic"


@dataclass
class AnimationConfig:
    """Animation configuration."""

    duration_ms: int = 1000
    timing_profile: TimingProfile = TimingProfile.EASE_IN_OUT
    loop: bool = False


class IKAnimationController:
    """
    Controls animation timing and easing for IK systems.

    Responsibilities:
    - Manage animation duration and timing
    - Calculate easing curves
    - Track animation progress

    Time Complexity: O(1) for all operations
    """

    def __init__(self) -> None:
        """Initialize animation controller."""
        self._duration_ms: int = 1000
        self._timing_profile: TimingProfile = TimingProfile.EASE_IN_OUT
        self._is_playing: bool = False
        self._current_progress: float = 0.0
        self._loop: bool = False

        # Timing curve functions
        self._timing_curves: dict[TimingProfile, Callable[[float], float]] = {
            TimingProfile.LINEAR: self._linear,
            TimingProfile.EASE_IN_OUT: self._ease_in_out,
            TimingProfile.EASE_IN: self._ease_in,
            TimingProfile.EASE_OUT: self._ease_out,
            TimingProfile.BOUNCE: self._bounce,
            TimingProfile.ELASTIC: self._elastic,
        }

    @property
    def duration_ms(self) -> int:
        """Get animation duration in milliseconds."""
        return self._duration_ms

    @duration_ms.setter
    def duration_ms(self, value: int) -> None:
        """Set animation duration in milliseconds."""
        self._duration_ms = max(100, value)

    @property
    def timing_profile(self) -> TimingProfile:
        """Get current timing profile."""
        return self._timing_profile

    @timing_profile.setter
    def timing_profile(self, value: TimingProfile | str) -> None:
        """Set timing profile by enum or string name."""
        if isinstance(value, str):
            try:
                self._timing_profile = TimingProfile(value)
            except ValueError:
                self._timing_profile = TimingProfile.EASE_IN_OUT
        else:
            self._timing_profile = value

    @property
    def is_playing(self) -> bool:
        """Check if animation is currently playing."""
        return self._is_playing

    @property
    def progress(self) -> float:
        """Get current animation progress (0.0 to 1.0)."""
        return self._current_progress

    def start(self) -> None:
        """Start animation playback."""
        self._is_playing = True

    def stop(self) -> None:
        """Stop animation playback."""
        self._is_playing = False

    def reset(self) -> None:
        """Reset animation to beginning."""
        self._current_progress = 0.0
        self._is_playing = False

    def set_progress(self, progress: float) -> None:
        """
        Set animation progress directly.

        Args:
            progress: Progress value (0.0 to 1.0)
        """
        self._current_progress = max(0.0, min(1.0, progress))

    def advance(self, delta_ms: float) -> float:
        """
        Advance animation by time delta.

        Args:
            delta_ms: Time elapsed in milliseconds

        Returns:
            New eased progress value
        """
        if not self._is_playing:
            return self.apply_timing(self._current_progress)

        delta_progress = delta_ms / self._duration_ms
        self._current_progress += delta_progress

        if self._current_progress >= 1.0:
            if self._loop:
                self._current_progress = self._current_progress % 1.0
            else:
                self._current_progress = 1.0
                self._is_playing = False

        return self.apply_timing(self._current_progress)

    def apply_timing(self, t: float) -> float:
        """
        Apply timing curve to progress value.

        Args:
            t: Raw progress (0.0 to 1.0)

        Returns:
            Eased progress value
        """
        curve_func = self._timing_curves.get(self._timing_profile, self._ease_in_out)
        return curve_func(t)

    # Timing curve implementations

    @staticmethod
    def _linear(t: float) -> float:
        """Linear interpolation (no easing)."""
        return t

    @staticmethod
    def _ease_in_out(t: float) -> float:
        """
        Smooth ease-in-out curve (sine-based).

        Slow start, fast middle, slow end.
        """
        return 0.5 * (1.0 - math.cos(math.pi * t))

    @staticmethod
    def _ease_in(t: float) -> float:
        """
        Ease-in curve (quadratic).

        Slow start, accelerating.
        """
        return t * t

    @staticmethod
    def _ease_out(t: float) -> float:
        """
        Ease-out curve (quadratic).

        Fast start, decelerating.
        """
        return 1.0 - (1.0 - t) * (1.0 - t)

    @staticmethod
    def _bounce(t: float) -> float:
        """
        Bounce easing effect.

        Overshoots and bounces at the end.
        """
        if t < 0.5:
            return 2 * t * t
        else:
            # Bounce effect
            x = 2 * t - 1
            return 1.0 - (1.0 - x) * (1.0 - x) * 0.5 + 0.5

    @staticmethod
    def _elastic(t: float) -> float:
        """
        Elastic easing effect.

        Spring-like oscillation at the end.
        """
        if t == 0 or t == 1:
            return t

        p = 0.3  # Period
        s = p / 4  # Amplitude

        if t < 0.5:
            t2 = t * 2
            return -0.5 * (2 ** (10 * (t2 - 1))) * math.sin((t2 - 1 - s) * (2 * math.pi) / p)
        else:
            t2 = t * 2 - 1
            return 0.5 * (2 ** (-10 * t2)) * math.sin((t2 - s) * (2 * math.pi) / p) + 1.0

    def get_available_profiles(self) -> list[str]:
        """Get list of available timing profile names."""
        return [profile.value for profile in TimingProfile]

    def configure(self, config: AnimationConfig) -> None:
        """
        Configure animation from config object.

        Args:
            config: Animation configuration
        """
        self._duration_ms = config.duration_ms
        self._timing_profile = config.timing_profile
        self._loop = config.loop
