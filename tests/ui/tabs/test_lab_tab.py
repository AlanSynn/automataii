import inspect

from PyQt6.QtWidgets import QApplication

from automataii.presentation.qt.tabs.lab import LabTab

_APP = None


def _qapp():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_lab_tab_instantiates_offscreen():
    _qapp()
    tab = LabTab()
    assert tab.objectName() == "tab_lab"
    tab.deleteLater()


def test_lab_tab_contains_required_panels():
    _qapp()
    tab = LabTab()
    assert tab.kit_catalog_panel is not None
    assert tab.episode_builder_panel is not None
    assert tab.trace_duel_panel is not None
    assert tab.motion_autopsy_panel is not None
    assert tab.facilitator_log_panel is not None
    tab.deleteLater()


def test_main_window_registers_user_facing_lab_tab():
    from automataii.presentation.qt import main_window

    source = inspect.getsource(main_window.AutomataDesigner._init_ui)
    assert "LabTab" in source
    assert "tab_lab" in source
    assert '"Lab"' in source
    assert "MS4N Lab" not in source
