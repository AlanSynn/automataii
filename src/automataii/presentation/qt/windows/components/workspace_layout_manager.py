"""
Workspace layout manager for dock/tab customization and persistence.

Responsibilities:
- Enable tab reordering for the main QTabWidget
- Persist and restore workspace geometry/state/tab order
"""

from __future__ import annotations

from collections.abc import Iterable

from PyQt6.QtCore import QByteArray, QObject, QSettings
from PyQt6.QtWidgets import (
    QMainWindow,
    QTabWidget,
)


class WorkspaceLayoutManager(QObject):
    """Coordinates workspace layout customization and persistence."""

    _STATE_VERSION = 1

    def __init__(
        self,
        main_window: QMainWindow,
        tab_widget: QTabWidget,
        settings: QSettings | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._tab_widget = tab_widget
        self._settings = settings or QSettings("MotionSmith", "WorkspaceLayout")
        self._restoring_tabs = False
        self._default_tab_order: list[str] = []

    @property
    def navigator_dock(self) -> None:
        return None

    def initialize(self) -> None:
        """Enable tab reordering and restore saved layout."""
        if not self._default_tab_order:
            self._default_tab_order = self.get_current_tab_order()

        self._tab_widget.setMovable(True)
        tab_bar = self._tab_widget.tabBar()
        if tab_bar is not None:
            tab_bar.setMovable(True)
            tab_bar.tabMoved.connect(self._on_tab_moved)
        self._tab_widget.currentChanged.connect(self._on_current_tab_changed)

        self._main_window.setDockNestingEnabled(True)
        self._main_window.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )

        self.restore_workspace_layout()

    def get_current_tab_order(self) -> list[str]:
        """Return tab IDs in visual order."""
        ids: list[str] = []
        for index in range(self._tab_widget.count()):
            tab_id = self._tab_id_for_index(index)
            if tab_id:
                ids.append(tab_id)
        return ids

    def save_workspace_layout(self) -> None:
        """Persist geometry, dock state, tab order, and current tab."""
        self._save_tab_order()
        self._save_current_tab_id()
        self._settings.setValue("workspace/geometry", self._main_window.saveGeometry())
        self._settings.setValue("workspace/state", self._main_window.saveState(self._STATE_VERSION))
        self._settings.sync()

    def restore_workspace_layout(self) -> None:
        """Restore tab order first, then geometry and dock state."""
        self._restore_tab_order()

        saved_geometry = self._settings.value("workspace/geometry")
        if isinstance(saved_geometry, QByteArray):
            self._main_window.restoreGeometry(saved_geometry)

        saved_state = self._settings.value("workspace/state")
        if isinstance(saved_state, QByteArray):
            self._main_window.restoreState(saved_state, self._STATE_VERSION)

        current_tab_id = self._settings.value("workspace/current_tab_id")
        if isinstance(current_tab_id, str):
            index = self._find_tab_index_by_id(current_tab_id)
            if index >= 0:
                self._tab_widget.setCurrentIndex(index)

    def reset_workspace_layout(self) -> None:
        """Reset workspace persistence and restore default tab order."""
        self._settings.remove("workspace")
        self._restore_default_tab_order()

    def refresh_navigator_items(self) -> None:
        """Compatibility no-op; the visible navigator UI has been removed."""
        return

    def _tab_id_for_index(self, index: int) -> str | None:
        if index < 0 or index >= self._tab_widget.count():
            return None
        tab = self._tab_widget.widget(index)
        if tab is None:
            return None
        object_name = tab.objectName()
        if object_name:
            return object_name
        return f"tab_{index}"

    def _find_tab_index_by_id(self, tab_id: str) -> int:
        for index in range(self._tab_widget.count()):
            if self._tab_id_for_index(index) == tab_id:
                return index
        return -1

    def _coerce_string_list(self, value: object) -> list[str]:
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, Iterable):
            items: list[str] = []
            for item in value:
                if isinstance(item, str) and item:
                    items.append(item)
            return items
        return []

    def _save_tab_order(self) -> None:
        self._settings.setValue("workspace/tab_order", self.get_current_tab_order())

    def _save_current_tab_id(self) -> None:
        current_tab_id = self._tab_id_for_index(self._tab_widget.currentIndex())
        if current_tab_id:
            self._settings.setValue("workspace/current_tab_id", current_tab_id)

    def _restore_tab_order(self) -> None:
        raw = self._settings.value("workspace/tab_order", [])
        stored_order = self._coerce_string_list(raw)
        if not stored_order:
            return

        self._restoring_tabs = True
        try:
            for target_index, tab_id in enumerate(stored_order):
                current_index = self._find_tab_index_by_id(tab_id)
                if current_index < 0 or current_index == target_index:
                    continue
                tab_bar = self._tab_widget.tabBar()
                if tab_bar is None:
                    return
                tab_bar.moveTab(current_index, target_index)
        finally:
            self._restoring_tabs = False

    def _restore_default_tab_order(self) -> None:
        if not self._default_tab_order:
            return

        self._restoring_tabs = True
        try:
            for target_index, tab_id in enumerate(self._default_tab_order):
                current_index = self._find_tab_index_by_id(tab_id)
                if current_index < 0 or current_index == target_index:
                    continue
                tab_bar = self._tab_widget.tabBar()
                if tab_bar is None:
                    return
                tab_bar.moveTab(current_index, target_index)
        finally:
            self._restoring_tabs = False

    def _on_tab_moved(self, _from_index: int, _to_index: int) -> None:
        if self._restoring_tabs:
            return
        self._save_tab_order()

    def _on_current_tab_changed(self, index: int) -> None:
        self._save_current_tab_id()
