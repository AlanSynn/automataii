"""
Animation Coordinator - Animation control during parametric editing.

Extracted from ParametricEditingManager. Handles coordinating animation
state when entering/exiting parametric mode.

Design Pattern: Coordinator (manages state transitions)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QPushButton


class AnimationController(Protocol):
    """Protocol for animation controller."""

    def is_animation_running(self) -> bool: ...
    def stop_animation(self) -> None: ...
    def start_animation(self) -> None: ...


class AnimationCoordinator:
    """
    Coordinates animation state during parametric editing.

    Responsibilities:
    - Disable animation controls when entering parametric mode
    - Re-enable animation controls when exiting parametric mode
    - Save and restore animation state
    - Manage mechanism visual interaction flags

    Time Complexity: O(n) where n = number of mechanism items
    """

    def __init__(self) -> None:
        """Initialize animation coordinator."""
        self._animation_was_running: bool = False
        self._logger = logging.getLogger(__name__)

        # Button references (set by parent)
        self._play_btn: QPushButton | None = None
        self._stop_btn: QPushButton | None = None
        self._reset_btn: QPushButton | None = None

    def set_buttons(
        self,
        play_btn: QPushButton | None = None,
        stop_btn: QPushButton | None = None,
        reset_btn: QPushButton | None = None,
    ) -> None:
        """Set button references for enabling/disabling."""
        self._play_btn = play_btn
        self._stop_btn = stop_btn
        self._reset_btn = reset_btn

    def on_enter_parametric_mode(
        self,
        animation_controller: AnimationController | None = None,
    ) -> bool:
        """
        Handle entering parametric mode.

        Args:
            animation_controller: Optional animation controller

        Returns:
            True if animation was running before entering
        """
        self._animation_was_running = False

        if animation_controller:
            try:
                self._animation_was_running = animation_controller.is_animation_running()
                if self._animation_was_running:
                    animation_controller.stop_animation()
            except Exception as e:
                self._logger.warning(f"Error stopping animation: {e}")

        self._disable_animation_controls()
        return self._animation_was_running

    def on_exit_parametric_mode(
        self,
        animation_controller: AnimationController | None = None,
        restore_animation: bool = True,
    ) -> None:
        """
        Handle exiting parametric mode.

        Args:
            animation_controller: Optional animation controller
            restore_animation: Whether to restore previous animation state
        """
        self._enable_animation_controls()

        if restore_animation and self._animation_was_running and animation_controller:
            try:
                animation_controller.start_animation()
            except Exception as e:
                self._logger.warning(f"Error restarting animation: {e}")

        self._animation_was_running = False

    def _disable_animation_controls(self) -> None:
        """Disable animation control buttons during parametric mode."""
        try:
            if self._play_btn:
                self._play_btn.setEnabled(False)
            if self._stop_btn:
                self._stop_btn.setEnabled(False)
            if self._reset_btn:
                self._reset_btn.setEnabled(False)
        except Exception as e:
            self._logger.warning(f"Error disabling animation controls: {e}")

    def _enable_animation_controls(self) -> None:
        """Re-enable animation control buttons after parametric mode."""
        try:
            if self._play_btn:
                self._play_btn.setEnabled(True)
            if self._stop_btn:
                self._stop_btn.setEnabled(True)
            if self._reset_btn:
                self._reset_btn.setEnabled(True)
        except Exception as e:
            self._logger.warning(f"Error enabling animation controls: {e}")

    def disable_mechanism_interaction(
        self,
        mechanism_layers: dict[str, Any],
        path_items: dict[str, list],
        visual_items: dict[str, list],
    ) -> None:
        """
        Disable interaction on mechanism visual items.

        Args:
            mechanism_layers: Dictionary of mechanism layer data
            path_items: Dictionary of path visual items
            visual_items: Dictionary of other visual items
        """
        try:
            for mechanism_id in mechanism_layers:
                for item_list in [
                    path_items.get(mechanism_id, []),
                    visual_items.get(mechanism_id, []),
                ]:
                    for item in item_list:
                        if hasattr(item, "setFlag"):
                            item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, False)
                            item.setFlag(item.GraphicsItemFlag.ItemIsMovable, False)
        except Exception as e:
            self._logger.warning(f"Error disabling mechanism interaction: {e}")

    def enable_mechanism_interaction(
        self,
        mechanism_layers: dict[str, Any],
        path_items: dict[str, list],
        visual_items: dict[str, list],
    ) -> None:
        """
        Re-enable interaction on mechanism visual items.

        Args:
            mechanism_layers: Dictionary of mechanism layer data
            path_items: Dictionary of path visual items
            visual_items: Dictionary of other visual items
        """
        try:
            for mechanism_id in mechanism_layers:
                for item_list in [
                    path_items.get(mechanism_id, []),
                    visual_items.get(mechanism_id, []),
                ]:
                    for item in item_list:
                        if hasattr(item, "setFlag"):
                            item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, True)
                            item.setFlag(item.GraphicsItemFlag.ItemIsMovable, False)
        except Exception as e:
            self._logger.warning(f"Error enabling mechanism interaction: {e}")

    @property
    def was_animation_running(self) -> bool:
        """Check if animation was running before entering parametric mode."""
        return self._animation_was_running
