from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPoint, QSettings
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from automataii.presentation.qt.actions.action_manager import ActionManager
from automataii.presentation.qt.widgets.scrollable_tab_bar import ScrollableTabBar
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
        ("tab_character_selection", "Character"),
        ("tab_path_editor", "Path"),
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


def test_workspace_manager_can_skip_current_tab_restore_on_startup(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])

    settings = _settings_for_test(tmp_path, "skip_current_tab_restore")

    window_1, tabs_1 = _create_window_with_tabs()
    manager_1 = WorkspaceLayoutManager(window_1, tabs_1, settings=settings)
    manager_1.initialize()
    tabs_1.setCurrentIndex(2)
    manager_1.save_workspace_layout()

    window_2, tabs_2 = _create_window_with_tabs()
    manager_2 = WorkspaceLayoutManager(window_2, tabs_2, settings=settings)
    manager_2.initialize(restore_current_tab=False)

    assert tabs_2.currentIndex() == 0
    assert tabs_2.currentWidget().objectName() == "tab_character_selection"

    window_3, tabs_3 = _create_window_with_tabs()
    manager_3 = WorkspaceLayoutManager(window_3, tabs_3, settings=settings)
    manager_3.initialize()

    assert tabs_3.currentWidget().objectName() == "tab_mechanism_design"
    assert app is not None


def test_workspace_manager_does_not_install_navigator_ui(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])

    settings = _settings_for_test(tmp_path, "navigator_removed")
    window, tabs = _create_window_with_tabs()
    manager = WorkspaceLayoutManager(window, tabs, settings=settings)
    manager.initialize()
    manager.refresh_navigator_items()

    assert manager.navigator_dock is None
    assert not window.findChildren(QWidget, "workflowNavigatorDock")
    assert app is not None


def test_scrollable_tab_bar_disables_native_overflow_buttons() -> None:
    app = QApplication.instance() or QApplication([])
    tabs = QTabWidget()
    tab_bar = ScrollableTabBar(tabs)
    tabs.setTabBar(tab_bar)

    assert tabs.usesScrollButtons() is False
    assert tab_bar.usesScrollButtons() is False
    assert app is not None


def test_scrollable_tab_bar_spreads_primary_workflow_tabs_across_width() -> None:
    app = QApplication.instance() or QApplication([])
    tabs = QTabWidget()
    tab_bar = ScrollableTabBar(tabs)
    tabs.setTabBar(tab_bar)
    tab_bar.resize(880, 36)
    for label in (
        "Character Selection",
        "Path Editor",
        "Mechanism Design",
        "Mechanism Foundry",
    ):
        tabs.addTab(QWidget(), label)

    widths = [tab_bar.tabSizeHint(index).width() for index in range(tab_bar.count())]

    assert min(widths) >= ScrollableTabBar.MIN_TAB_WIDTH
    assert sum(widths) >= tab_bar.width() - 20
    assert tab_bar.expanding() is True
    assert app is not None


def test_scrollable_tab_bar_geometry_uses_whole_qtabwidget_width() -> None:
    app = QApplication.instance() or QApplication([])
    tabs = QTabWidget()
    tab_bar = ScrollableTabBar(tabs)
    tabs.setTabBar(tab_bar)
    tabs.setUsesScrollButtons(False)
    for label in (
        "Character Selection",
        "Path Editor",
        "Mechanism Design",
        "Mechanism Foundry",
    ):
        tabs.addTab(QWidget(), label)

    tabs.resize(1320, 320)
    tabs.show()
    app.processEvents()

    try:
        assert tab_bar.sizeHint().width() >= tabs.width() - 4
        assert tab_bar.geometry().width() >= tabs.width() - 24
        assert sum(tab_bar.tabRect(index).width() for index in range(tab_bar.count())) >= (
            tabs.width() - 40
        )
    finally:
        tabs.close()
    assert app is not None


class _FakeWheelEvent:
    def __init__(self, x_delta: int = 0, y_delta: int = 0) -> None:
        self._angle_delta = QPoint(x_delta, y_delta)
        self._pixel_delta = QPoint(0, 0)
        self.accepted = False

    def angleDelta(self) -> QPoint:
        return self._angle_delta

    def pixelDelta(self) -> QPoint:
        return self._pixel_delta

    def accept(self) -> None:
        self.accepted = True


def test_scrollable_tab_bar_wheel_switches_tabs() -> None:
    app = QApplication.instance() or QApplication([])
    tabs = QTabWidget()
    tab_bar = ScrollableTabBar(tabs)
    tabs.setTabBar(tab_bar)
    for _index in range(3):
        tabs.addTab(QWidget(), f"Tab {_index}")

    forward_event = _FakeWheelEvent(y_delta=-120)
    tab_bar.wheelEvent(forward_event)

    assert tabs.currentIndex() == 1
    assert tab_bar.currentIndex() == 1
    assert forward_event.accepted

    backward_event = _FakeWheelEvent(y_delta=120)
    tab_bar.wheelEvent(backward_event)

    assert tabs.currentIndex() == 0
    assert backward_event.accepted
    assert app is not None


def test_menus_do_not_expose_workflow_ui() -> None:
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    action_manager = ActionManager(window)
    action_manager.setup_menus(window.menuBar())

    menu_titles = [action.text().replace("&", "") for action in window.menuBar().actions()]
    assert "Workflow" not in menu_titles

    view_menu = next(
        action.menu() for action in window.menuBar().actions() if action.text() == "&View"
    )
    view_actions = [action.text() for action in view_menu.actions()]
    assert "Show Workflow Navigator" not in view_actions
    assert app is not None


def test_experiment_mode_hides_foundry_and_options_tabs() -> None:
    app = QApplication.instance() or QApplication([])

    from automataii.presentation.qt.main_window import AutomataDesigner

    window = AutomataDesigner(experiment_mode=True)
    try:
        window.reset_workspace_layout()
        tab_titles = [
            window.tab_widget.tabText(index) for index in range(window.tab_widget.count())
        ]

        assert tab_titles == [
            "1. Character Selection",
            "2. Path Editor",
            "3. Mechanism Design",
        ]
        assert window.mechanism_foundry_tab is None
        assert not hasattr(window, "landing_tab")
        assert not hasattr(window, "lab_tab")
    finally:
        window.close()

    assert app is not None
