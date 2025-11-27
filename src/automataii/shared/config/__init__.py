"""
Shared configuration definitions.

Contains configuration dataclasses used across components.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnimationConfig:
    """
    Animation configuration settings.

    Attributes:
        default_frame_rate: Default FPS for animations
        default_angle_step: Default degrees per frame
        min_frame_interval_ms: Minimum frame interval in milliseconds
        throttle_interval_ms: IK update throttle interval
    """

    default_frame_rate: int = 30
    default_angle_step: float = 4.0
    min_frame_interval_ms: int = 16
    throttle_interval_ms: int = 50


@dataclass(frozen=True)
class RenderingConfig:
    """
    Rendering configuration settings.

    Attributes:
        show_forces: Whether to show force vectors
        show_velocity: Whether to show velocity vectors
        show_trail: Whether to show motion trails
        show_grid: Whether to show background grid
        grid_spacing: Grid spacing in pixels
    """

    show_forces: bool = True
    show_velocity: bool = False
    show_trail: bool = False
    show_grid: bool = True
    grid_spacing: int = 100


@dataclass(frozen=True)
class UIConfig:
    """
    UI layout configuration.

    Attributes:
        min_panel_width: Minimum panel width in pixels
        max_panel_width: Maximum panel width in pixels
        default_splitter_sizes: Default splitter panel sizes
    """

    min_panel_width: int = 250
    max_panel_width: int = 400
    default_splitter_sizes: tuple[int, ...] = (350, 600, 300)


# Default configurations
DEFAULT_ANIMATION_CONFIG = AnimationConfig()
DEFAULT_RENDERING_CONFIG = RenderingConfig()
DEFAULT_UI_CONFIG = UIConfig()


__all__ = [
    "AnimationConfig",
    "RenderingConfig",
    "UIConfig",
    "DEFAULT_ANIMATION_CONFIG",
    "DEFAULT_RENDERING_CONFIG",
    "DEFAULT_UI_CONFIG",
]
