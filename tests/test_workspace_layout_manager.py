from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from automataii.presentation.qt.windows.components.workspace_layout_manager import (
    WorkspaceLayoutManager,
)


def _create_window_with_tabs() -> tuple[QMainWindow, QTabWidget]:
    window = QMainWindow()
    central = QWidget()
    layout = QVBoxLayout(central)
    tabs = QTabWidget()
    tabs.setObjectName("mainTabWidget")
    layout.addWidget(tabs)
    window.setCentralWidget(central)

    entries = [
        ("tab_welcome", "Welcome"),
        ("tab_character_selection", "Character"),
        ("tab_mechanism_design", "Mechanism Design"),
    ]
    for tab_id, label in entries:
        tab = QWidget()
        tab.setObjectName(tab_id)
        tabs.addTab(tab, label)

    return window, tabs


def _settings_for_test(tmp_path: Path, name: str) -> QSettings:
    settings_path = tmp_path / f"{name}.ini"
    return QSettings(str(settings_path), QSettings.Format.IniFormat)


def test_workspace_manager_persists_and_restores_tab_order(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])

    settings = _settings_for_test(tmp_path, "layout_restore")

    window_1, tabs_1 = _create_window_with_tabs()
    manager_1 = WorkspaceLayoutManager(window_1, tabs_1, settings=settings)
    manager_1.initialize()
    tabs_1.tabBar().moveTab(0, 2)
    manager_1.save_workspace_layout()
    saved_order = manager_1.get_current_tab_order()

    window_2, tabs_2 = _create_window_with_tabs()
    manager_2 = WorkspaceLayoutManager(window_2, tabs_2, settings=settings)
    manager_2.initialize()

    assert manager_2.get_current_tab_order() == saved_order
    assert app is not None


def test_workflow_navigator_item_switches_tab(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])

    settings = _settings_for_test(tmp_path, "navigator_switch")
    window, tabs = _create_window_with_tabs()
    manager = WorkspaceLayoutManager(window, tabs, settings=settings)
    manager.initialize()
    manager.refresh_navigator_items()

    dock = manager.navigator_dock
    assert dock is not None
    list_widget = dock.widget()
    assert list_widget is not None
    assert list_widget.count() >= 2

    target_item = list_widget.item(1)
    target_tab_id = target_item.data(Qt.ItemDataRole.UserRole)
    list_widget.itemActivated.emit(target_item)

    current_tab = tabs.currentWidget()
    assert current_tab is not None
    assert current_tab.objectName() == target_tab_id
    assert app is not None
