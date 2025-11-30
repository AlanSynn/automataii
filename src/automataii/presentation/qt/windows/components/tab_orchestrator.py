"""
Tab Orchestrator - Tab lifecycle management and camera state sharing.

Extracted from AutomataDesigner (main_window.py) to handle tab switching,
camera state persistence, and tab activation/deactivation lifecycle.

Design Pattern: Orchestrator (coordinates tab lifecycle events)
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QTabWidget, QWidget

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QStatusBar


class TabOrchestrator(QObject):
    """
    Orchestrates tab lifecycle and camera state sharing.

    Responsibilities:
    - Handle tab switch events
    - Manage camera state sharing between tabs
    - Coordinate tab activation/deactivation
    - Apply initial zoom on first tab visit

    Extracted from AutomataDesigner to reduce god class complexity.
    """

    def __init__(
        self,
        tab_widget: QTabWidget,
        parent: QObject | None = None,
    ) -> None:
        """
        Initialize tab orchestrator.

        Args:
            tab_widget: The main QTabWidget to orchestrate
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._tab_widget = tab_widget
        self._previous_tab_index: int = 0
        self._shared_camera_state: dict[str, Any] | None = None

        # Tabs that share camera state
        self._shared_view_tabs: list[QWidget] = []

        # Callbacks for external state access
        self._get_status_bar: Callable[[], QStatusBar | None] = lambda: None
        self._get_skeleton_manager: Callable[[], Any] = lambda: None
        self._on_tab_activated: Callable[[QWidget, int], None] = lambda t, i: None

        # Connect to tab widget
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

    def configure_callbacks(
        self,
        get_status_bar: Callable[[], QStatusBar | None],
        get_skeleton_manager: Callable[[], Any],
        on_tab_activated: Callable[[QWidget, int], None] | None = None,
    ) -> None:
        """Configure callback functions for external state access."""
        self._get_status_bar = get_status_bar
        self._get_skeleton_manager = get_skeleton_manager
        if on_tab_activated:
            self._on_tab_activated = on_tab_activated

    def set_shared_view_tabs(self, tabs: list[QWidget]) -> None:
        """Set the list of tabs that share camera state."""
        self._shared_view_tabs = tabs

    @property
    def shared_camera_state(self) -> dict[str, Any] | None:
        """Get the shared camera state."""
        return self._shared_camera_state

    @shared_camera_state.setter
    def shared_camera_state(self, value: dict[str, Any] | None) -> None:
        """Set the shared camera state."""
        self._shared_camera_state = value

    @property
    def previous_tab_index(self) -> int:
        """Get the previous tab index."""
        return self._previous_tab_index

    def _on_tab_changed(self, index: int) -> None:
        """
        Handle tab change events.

        Manages camera state sharing, tab lifecycle, and initial zoom.

        Args:
            index: New tab index
        """
        current_tab = self._tab_widget.widget(index)
        previous_tab = self._tab_widget.widget(self._previous_tab_index)

        # Call deactivate_tab on the previous tab
        if previous_tab and hasattr(previous_tab, "deactivate_tab"):
            previous_tab.deactivate_tab()

        # Handle camera state sharing
        camera_state_applied = self._handle_camera_state_transition(
            previous_tab, current_tab
        )

        # Update status bar
        self._update_status_bar(current_tab, index)

        # Apply initial zoom if needed
        if not camera_state_applied:
            self._apply_initial_zoom_if_needed(current_tab)

        # Call activate_tab on the current tab
        if current_tab and hasattr(current_tab, "activate_tab"):
            current_tab.activate_tab()
            self._sync_skeleton_data_if_needed(current_tab)

        # Notify external handler
        self._on_tab_activated(current_tab, index)

        # Remember current index for next tab change
        self._previous_tab_index = index

    def _handle_camera_state_transition(
        self, previous_tab: QWidget | None, current_tab: QWidget | None
    ) -> bool:
        """
        Handle camera state save/restore during tab transition.

        Returns:
            True if camera state was applied, False otherwise
        """
        # Save camera state if leaving a shared-view tab
        if previous_tab in self._shared_view_tabs:
            self._save_camera_state(previous_tab)

        # Apply camera state if entering a shared-view tab
        if current_tab in self._shared_view_tabs:
            return self._apply_camera_state(current_tab)

        return False

    def _save_camera_state(self, tab: QWidget) -> None:
        """Save camera state from a tab."""
        view = getattr(tab, "editor_view", None) or getattr(tab, "mechanism_view", None)
        if not view:
            return

        try:
            _ = view.scene()  # Check if view is still valid
            camera_state = view.get_camera_state()
            self._shared_camera_state = camera_state
            tab._last_camera_state = camera_state  # Tab-specific backup
            logging.info(f"Saved camera state from {tab.__class__.__name__}")
        except RuntimeError as e:
            logging.error(f"View was deleted, cannot save camera state: {e}")

    def _apply_camera_state(self, tab: QWidget) -> bool:
        """
        Apply camera state to a tab.

        Returns:
            True if camera state was applied
        """
        view = getattr(tab, "editor_view", None) or getattr(tab, "mechanism_view", None)
        if not view:
            return False

        try:
            _ = view.scene()  # Check if view is still valid

            if self._shared_camera_state:
                view.set_camera_state(self._shared_camera_state)
                logging.info(f"Applied shared camera state to {tab.__class__.__name__}")
                return True
            elif hasattr(tab, "_last_camera_state") and tab._last_camera_state:
                view.set_camera_state(tab._last_camera_state)
                logging.info(f"Applied tab-specific camera state to {tab.__class__.__name__}")
                return True
            else:
                logging.debug(f"No camera state available for {tab.__class__.__name__}")
                return False

        except RuntimeError as e:
            logging.error(f"View was deleted, cannot apply camera state: {e}")
            self._shared_camera_state = None
            return False

    def _update_status_bar(self, tab: QWidget | None, index: int) -> None:
        """Update status bar with current tab info."""
        status_bar = self._get_status_bar()
        if not status_bar:
            return

        if tab and hasattr(tab, "tab_name"):
            status_bar.showMessage(f"{tab.tab_name} tab active")
        else:
            status_bar.showMessage(f"Tab {index + 1} active")

    def _apply_initial_zoom_if_needed(self, tab: QWidget | None) -> None:
        """Apply initial zoom on first tab visit."""
        if not tab:
            return

        tab_needs_initial_zoom = False

        # Check editor_view
        if hasattr(tab, "editor_view") and tab.editor_view:
            if not hasattr(tab, "_view_initialized"):
                tab_needs_initial_zoom = True
                tab._view_initialized = True
        # Check mechanism_view
        elif hasattr(tab, "mechanism_view") and tab.mechanism_view:
            if not hasattr(tab, "_view_initialized"):
                tab_needs_initial_zoom = True
                tab._view_initialized = True
        # Image processing tab always zooms
        elif hasattr(tab, "image_proc_view"):
            tab_needs_initial_zoom = True

        if tab_needs_initial_zoom:
            self._do_zoom_to_fit(tab)
        else:
            logging.debug(f"Preserving camera for: {getattr(tab, 'tab_name', 'Unknown')}")

    def _do_zoom_to_fit(self, tab: QWidget) -> None:
        """Execute zoom to fit on appropriate view."""
        tab_name = getattr(tab, "tab_name", "Unknown")
        logging.debug(f"Applying initial zoom for tab: {tab_name}")

        if hasattr(tab, "editor_view") and tab.editor_view:
            tab.editor_view.zoom_to_fit()
        elif hasattr(tab, "mechanism_view") and tab.mechanism_view:
            tab.mechanism_view.zoom_to_fit()
        elif hasattr(tab, "image_proc_view"):
            view = tab.image_proc_view
            if hasattr(view, "zoom_to_fit"):
                view.zoom_to_fit()
            elif hasattr(view, "fit_in_view"):
                view.fit_in_view()

    def _sync_skeleton_data_if_needed(self, tab: QWidget) -> None:
        """Sync skeleton data for mechanism design tab."""
        skeleton_manager = self._get_skeleton_manager()
        if not skeleton_manager:
            return

        # Check if this is the mechanism design tab that needs skeleton sync
        if not hasattr(tab, "cache_initial_skeleton"):
            return

        if hasattr(tab, "_initial_skeleton_data_cache") and tab._initial_skeleton_data_cache:
            return  # Already has data

        if hasattr(skeleton_manager, "get_current_skeleton_data"):
            current_skeleton = skeleton_manager.get_current_skeleton_data()
            if current_skeleton:
                tab.cache_initial_skeleton(current_skeleton)
                logging.info(f"{tab.__class__.__name__}: Synchronized skeleton data")
