"""
Workspace layout manager for dock/tab customization and persistence.

Responsibilities:
- Enable tab reordering for the main QTabWidget
- Provide a dockable workflow navigator list
- Persist and restore workspace geometry/state/tab order
"""

from __future__ import annotations

from collections.abc import Iterable

from PyQt6.QtCore import QByteArray, QObject, QSettings, Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QListWidget,
    QListWidgetItem,
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
        self._settings = settings or QSettings("Automataii", "WorkspaceLayout")
        self._restoring_tabs = False
        self._default_tab_order: list[str] = []
        self._navigator_dock: QDockWidget | None = None
        self._navigator_list: QListWidget | None = None

    @property
    def navigator_dock(self) -> QDockWidget | None:
        return self._navigator_dock

    def initialize(self) -> None:
        """Enable tab reordering, install navigator dock, and restore saved layout."""
        if not self._default_tab_order:
            self._default_tab_order = self.get_current_tab_order()

        self._tab_widget.setMovable(True)
        tab_bar = self._tab_widget.tabBar()
        tab_bar.setMovable(True)
        tab_bar.tabMoved.connect(self._on_tab_moved)
        self._tab_widget.currentChanged.connect(self._on_current_tab_changed)

        self._main_window.setDockNestingEnabled(True)
        self._main_window.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )

        self._install_navigator_dock()
        self.restore_workspace_layout()
        self.refresh_navigator_items()

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
        self._settings.setValue(
            "workspace/state", self._main_window.saveState(self._STATE_VERSION)
        )
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
        """Reset workspace persistence and restore default tab order/dock placement."""
        self._settings.remove("workspace")
        self._restore_default_tab_order()
        if self._navigator_dock:
            self._main_window.removeDockWidget(self._navigator_dock)
            self._main_window.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self._navigator_dock
            )
            self._navigator_dock.show()
        self.refresh_navigator_items()

    def refresh_navigator_items(self) -> None:
        """Rebuild navigator dock list from current tab state."""
        if self._navigator_list is None:
            return

        current_tab_id = self._tab_id_for_index(self._tab_widget.currentIndex())
        self._navigator_list.blockSignals(True)
        self._navigator_list.clear()

        for index in range(self._tab_widget.count()):
            tab_id = self._tab_id_for_index(index)
            if not tab_id:
                continue
            item = QListWidgetItem(self._tab_widget.tabText(index))
            item.setData(Qt.ItemDataRole.UserRole, tab_id)
            self._navigator_list.addItem(item)

        self._select_navigator_item_by_tab_id(current_tab_id)
        self._navigator_list.blockSignals(False)

    def _install_navigator_dock(self) -> None:
        if self._navigator_dock is not None:
            return

        dock = QDockWidget("Workflow Navigator", self._main_window)
        dock.setObjectName("workflowNavigatorDock")
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        navigator = QListWidget(dock)
        navigator.itemActivated.connect(self._on_navigator_item_selected)
        navigator.itemClicked.connect(self._on_navigator_item_selected)

        dock.setWidget(navigator)
        self._main_window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self._navigator_dock = dock
        self._navigator_list = navigator

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
                self._tab_widget.tabBar().moveTab(current_index, target_index)
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
                self._tab_widget.tabBar().moveTab(current_index, target_index)
        finally:
            self._restoring_tabs = False

    def _select_navigator_item_by_tab_id(self, tab_id: str | None) -> None:
        if self._navigator_list is None or not tab_id:
            return
        for row in range(self._navigator_list.count()):
            item = self._navigator_list.item(row)
            item_tab_id = item.data(Qt.ItemDataRole.UserRole)
            if item_tab_id == tab_id:
                self._navigator_list.setCurrentRow(row)
                return

    def _on_tab_moved(self, _from_index: int, _to_index: int) -> None:
        if self._restoring_tabs:
            return
        self._save_tab_order()
        self.refresh_navigator_items()

    def _on_current_tab_changed(self, index: int) -> None:
        current_tab_id = self._tab_id_for_index(index)
        self._select_navigator_item_by_tab_id(current_tab_id)
        self._save_current_tab_id()

    def _on_navigator_item_selected(self, item: QListWidgetItem) -> None:
        tab_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(tab_id, str):
            return
        tab_index = self._find_tab_index_by_id(tab_id)
        if tab_index >= 0:
            self._tab_widget.setCurrentIndex(tab_index)
