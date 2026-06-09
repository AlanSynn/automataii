"""
Simulation Controller - Animation playback control and state management.

Extracted from EditorTab god class. Manages simulation state transitions,
button state updates, and part movement locking during animation.

Design Pattern: State Machine (implicit via state_string transitions)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, Qt, pyqtSignal, pyqtSlot

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene, QLabel, QPushButton, QSlider

    from automataii.presentation.qt.views.editor_view import EditorView


class SimulationController(QObject):
    """
    Controls animation simulation state and UI.

    Manages the state machine for play/stop/reset transitions,
    updates button enabled states, and coordinates part movement
    locking during animation playback.

    State Transitions:
        stopped → playing (via play)
        playing → stopped (via stop)
        playing → reset (via reset, goes through stopped)
        stopped → reset (via reset)
        reset → stopped (implicit)

    Signals:
        request_play: Emitted when play is requested
        request_stop: Emitted when stop is requested
        request_reset: Emitted when reset is requested
    """

    # Signals for simulation control requests
    request_play = pyqtSignal()
    request_stop = pyqtSignal()
    request_reset = pyqtSignal()

    def __init__(
        self,
        editor_view: EditorView,
        editor_scene: QGraphicsScene,
        parent: QObject | None = None,
    ) -> None:
        """
        Initialize simulation controller.

        Args:
            editor_view: The EditorView for part movement locking
            editor_scene: The graphics scene
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._editor_view = editor_view
        self._editor_scene = editor_scene

        # State
        self._current_state: str = "stopped"
        self._ik_log_counter: dict[str, int] = {}

        # UI references (set via configure_ui)
        self._play_btn: QPushButton | None = None
        self._stop_btn: QPushButton | None = None
        self._reset_btn: QPushButton | None = None
        self._status_label: QLabel | None = None
        self._smoothness_slider: QSlider | None = None

        # Callbacks for external state access
        self._has_editor_items: Callable[[], bool] = lambda: False
        self._has_any_path: Callable[[], bool] = lambda: False
        self._get_path_count: Callable[[], int] = lambda: 0
        self._apply_corrections: Callable[[], None] = lambda: None
        self._position_parts_at_anchor: Callable[[], None] = lambda: None
        self._on_skeleton_updated: Callable[[dict], None] = lambda x: None
        self._update_part_list_styles: Callable[[], None] = lambda: None

        # Cache reference
        self._initial_skeleton_cache: dict | None = None

    def configure_ui(
        self,
        play_btn: QPushButton,
        stop_btn: QPushButton,
        reset_btn: QPushButton,
        status_label: QLabel,
        smoothness_slider: QSlider | None = None,
    ) -> None:
        """
        Configure UI element references.

        Args:
            play_btn: Play button widget
            stop_btn: Stop button widget
            reset_btn: Reset button widget
            status_label: Animation status label
            smoothness_slider: Optional smoothness slider
        """
        self._play_btn = play_btn
        self._stop_btn = stop_btn
        self._reset_btn = reset_btn
        self._status_label = status_label
        self._smoothness_slider = smoothness_slider

    def configure_callbacks(
        self,
        has_editor_items: Callable[[], bool],
        has_any_path: Callable[[], bool],
        get_path_count: Callable[[], int],
        apply_corrections: Callable[[], None],
        position_parts_at_anchor: Callable[[], None],
        on_skeleton_updated: Callable[[dict], None],
        update_part_list_styles: Callable[[], None],
        initial_skeleton_cache_getter: Callable[[], dict | None],
    ) -> None:
        """
        Configure callback functions for external state access.

        Args:
            has_editor_items: Returns True if editor items exist
            has_any_path: Returns True if any motion path exists
            get_path_count: Returns count of motion paths
            apply_corrections: Applies feasibility corrections
            position_parts_at_anchor: Positions parts at anchor joints
            on_skeleton_updated: Skeleton update callback
            update_part_list_styles: Updates part list visual styles
            initial_skeleton_cache_getter: Returns initial skeleton cache
        """
        self._has_editor_items = has_editor_items
        self._has_any_path = has_any_path
        self._get_path_count = get_path_count
        self._apply_corrections = apply_corrections
        self._position_parts_at_anchor = position_parts_at_anchor
        self._on_skeleton_updated = on_skeleton_updated
        self._update_part_list_styles = update_part_list_styles
        self._get_skeleton_cache = initial_skeleton_cache_getter

    @property
    def current_state(self) -> str:
        """Get current simulation state."""
        return self._current_state

    @property
    def ik_log_counter(self) -> dict[str, int]:
        """Get IK log counter for rate limiting."""
        return self._ik_log_counter

    # --- Button Click Handlers ---

    def play_clicked(self) -> None:
        """
        Handle play button click.

        Locks part movement, applies feasibility corrections,
        and emits play request signal.
        """
        # Lock part movement during animation
        self._lock_part_movement(True)

        # Auto-apply feasibility snapping for all parts before playing
        try:
            self._apply_corrections()
        except Exception as e:
            logging.debug(f"Auto-apply feasibility corrections failed: {e}")

        # Emit signal for IK manager
        self.request_play.emit()

    def stop_clicked(self) -> None:
        """
        Handle stop button click.

        Unlocks part movement and updates button states.
        """
        logging.info("SimulationController: Stop button clicked")

        # Unlock part movement
        self._lock_part_movement(False)

        self.request_stop.emit()

        if self._play_btn:
            self._play_btn.setEnabled(True)
        if self._stop_btn:
            self._stop_btn.setEnabled(False)
        if self._reset_btn:
            self._reset_btn.setEnabled(True)

    def reset_clicked(self) -> None:
        """
        Handle reset button click.

        Unlocks part movement, resets parts to initial positions,
        and updates button states.
        """
        # Unlock part movement
        self._lock_part_movement(False)

        self.request_reset.emit()

        # Reset parts to original positions
        skeleton_cache = self._get_skeleton_cache()
        if skeleton_cache:
            self._position_parts_at_anchor()
            self._on_skeleton_updated(skeleton_cache.copy())
            logging.info("SimulationController: Skeleton and parts reset to cached initial state.")
        else:
            logging.warning("SimulationController: No cached initial skeleton data for reset.")

        if self._play_btn:
            self._play_btn.setEnabled(True)
        if self._stop_btn:
            self._stop_btn.setEnabled(False)
        if self._reset_btn:
            self._reset_btn.setEnabled(False)

        self.update_button_states(None, None)

        if self._editor_scene:
            self._editor_scene.update()

    # --- State Management ---

    @pyqtSlot(str)
    def on_state_changed(self, state_string: str) -> None:
        """
        Handle animation state change from IK manager.

        Updates button enabled states based on new state.

        Args:
            state_string: New state ("playing", "stopped", "reset")
        """
        logging.info(f"SimulationController: State changed to: {state_string}")

        is_playing = False
        can_play = False
        can_stop = False
        can_reset = False

        has_items = self._has_editor_items()

        if state_string == "playing":
            is_playing = True
            can_play = False
            can_stop = True
            can_reset = False
        elif state_string == "stopped":
            is_playing = False
            can_play = has_items
            can_stop = False
            can_reset = has_items
        elif state_string == "reset":
            is_playing = False
            can_play = has_items
            can_stop = False
            can_reset = has_items
        else:
            logging.warning(f"SimulationController: Unknown state string: {state_string}")
            is_playing = False
            can_play = has_items
            can_stop = False
            can_reset = has_items

        # Update button states
        if self._play_btn:
            self._play_btn.setEnabled(can_play and not is_playing)
            self._play_btn.setChecked(is_playing)
        if self._stop_btn:
            self._stop_btn.setEnabled(can_stop and is_playing)
        if self._reset_btn:
            self._reset_btn.setEnabled(can_reset and not is_playing)

        self._current_state = state_string
        self._ik_log_counter.clear()

    def update_button_states(
        self,
        _selected_part_name: str | None,
        _has_motion_path_fn: Callable[[str], bool] | None,
    ) -> None:
        """
        Update all button enabled states based on current state.

        Args:
            _selected_part_name: Currently selected part name (unused, for future use)
            _has_motion_path_fn: Function to check if part has motion path (unused, for future use)
        """
        has_any_path = self._has_any_path()

        # Animation section
        if self._play_btn:
            self._play_btn.setEnabled(has_any_path)
        if self._stop_btn:
            self._stop_btn.setEnabled(has_any_path and self._current_state == "playing")
        if self._reset_btn:
            self._reset_btn.setEnabled(has_any_path)

        # Update animation status label
        if self._status_label:
            if has_any_path:
                path_count = self._get_path_count()
                self._status_label.setText(f"{path_count} motion path(s) defined")
            else:
                self._status_label.setText("No motion paths defined")

        # Update part list styles
        self._update_part_list_styles()

    # --- Part Movement Locking ---

    def _lock_part_movement(self, lock: bool) -> None:
        """
        Lock or unlock part movement during animation.

        Args:
            lock: True to lock, False to unlock
        """
        if not self._editor_view:
            return

        if lock:
            self._editor_view.setInteractive(False)
            self._editor_view.setDragMode(self._editor_view.DragMode.NoDrag)
            self._editor_view.viewport().setCursor(Qt.CursorShape.ForbiddenCursor)
            logging.info("SimulationController: Part movement LOCKED")
        else:
            self._editor_view.setInteractive(True)
            self._editor_view.setDragMode(self._editor_view.DragMode.NoDrag)
            self._editor_view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            logging.info("SimulationController: Part movement UNLOCKED")
