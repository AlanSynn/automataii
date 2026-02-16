import sys

from PyQt6.QtWidgets import QApplication, QFormLayout, QGroupBox, QScrollArea

from automataii.presentation.qt.tabs.options_tab import OptionsTab


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_options_tab_uses_scroll_area() -> None:
    _ = _get_app()
    tab = OptionsTab()

    scroll_area = tab.findChild(QScrollArea)
    assert scroll_area is not None
    assert scroll_area.widgetResizable()


def test_options_tab_supports_small_window_scrolling() -> None:
    app = _get_app()
    tab = OptionsTab()
    tab.resize(320, 220)
    tab.show()
    app.processEvents()

    scroll_area = tab.findChild(QScrollArea)
    assert scroll_area is not None

    content_height = scroll_area.widget().sizeHint().height()
    viewport_height = scroll_area.viewport().height()

    assert content_height > viewport_height
    assert scroll_area.verticalScrollBar().maximum() > 0


def test_option_group_form_layouts_wrap_long_rows() -> None:
    _ = _get_app()
    tab = OptionsTab()

    groups = tab.findChildren(QGroupBox)
    assert groups

    for group in groups:
        layout = group.layout()
        assert isinstance(layout, QFormLayout)
        assert layout.rowWrapPolicy() == QFormLayout.RowWrapPolicy.WrapLongRows
        assert (
            layout.fieldGrowthPolicy()
            == QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )


def test_grid_system_controls_defaults_and_toggle() -> None:
    _ = _get_app()
    tab = OptionsTab()

    assert tab.grid_system_check.isChecked() is True
    assert tab.grid_cell_size_spin.value() == 2.5
    assert tab.grid_cell_size_spin.isEnabled() is True

    tab.grid_system_check.setChecked(False)
    assert tab.grid_cell_size_spin.isEnabled() is False
