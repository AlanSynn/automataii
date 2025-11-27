"""
Shared state definitions for cross-component state management.

Contains state containers and adapters used across presentation components.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnimationState:
    """
    Animation playback state.

    Attributes:
        is_playing: Whether animation is currently playing
        current_angle: Current rotation angle in degrees
        frame_rate: Target frames per second
        speed_multiplier: Animation speed multiplier
    """

    is_playing: bool = False
    current_angle: float = 0.0
    frame_rate: int = 30
    speed_multiplier: float = 1.0

    def advance_frame(self, delta_degrees: float = 4.0) -> None:
        """Advance animation by delta degrees."""
        self.current_angle = (self.current_angle + delta_degrees * self.speed_multiplier) % 360.0

    def reset(self) -> None:
        """Reset to initial state."""
        self.current_angle = 0.0
        self.is_playing = False


@dataclass
class ViewState:
    """
    UI view state.

    Attributes:
        zoom_level: Current zoom level
        pan_offset: Current pan offset as (x, y)
        show_grid: Whether grid is visible
        show_labels: Whether labels are visible
    """

    zoom_level: float = 1.0
    pan_offset: tuple[float, float] = (0.0, 0.0)
    show_grid: bool = True
    show_labels: bool = True


@dataclass
class SelectionState:
    """
    Selection state for UI components.

    Attributes:
        selected_items: Set of selected item identifiers
        primary_selection: Primary/active selection
        hover_item: Currently hovered item
    """

    selected_items: set[str] = field(default_factory=set)
    primary_selection: str | None = None
    hover_item: str | None = None

    def select(self, item_id: str, primary: bool = True) -> None:
        """Add item to selection."""
        self.selected_items.add(item_id)
        if primary:
            self.primary_selection = item_id

    def deselect(self, item_id: str) -> None:
        """Remove item from selection."""
        self.selected_items.discard(item_id)
        if self.primary_selection == item_id:
            self.primary_selection = next(iter(self.selected_items), None)

    def clear(self) -> None:
        """Clear all selections."""
        self.selected_items.clear()
        self.primary_selection = None
        self.hover_item = None


__all__ = [
    "AnimationState",
    "ViewState",
    "SelectionState",
]
