import sys

from PyQt6.QtWidgets import QApplication, QFormLayout, QGroupBox, QScrollArea

from automataii.presentation.qt.physical_context_store import PhysicalKitContextStore
from automataii.presentation.qt.tabs.options_tab import OptionsTab
from automataii.shared.physical_kit import DEFAULT_GRID_CELL_CM


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
        assert layout.fieldGrowthPolicy() == QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow


def test_grid_system_controls_defaults_and_toggle() -> None:
    _ = _get_app()
    tab = OptionsTab()

    assert tab.grid_system_check.text() == "Fabrication-ready preset mode"
    assert "Preset / Fabrication-ready" in tab.fabrication_mode_help_label.text()
    assert tab.grid_system_check.isChecked() is True
    assert tab.grid_cell_size_spin.value() == DEFAULT_GRID_CELL_CM
    assert tab.grid_pitch_combo.currentData() == "2cm"
    assert tab.grid_cell_size_spin.isEnabled() is True
    assert tab.grid_pitch_combo.isEnabled() is True

    tab.grid_pitch_combo.setCurrentIndex(tab.grid_pitch_combo.findData("2_5cm"))
    assert tab.grid_cell_size_spin.value() == 2.5

    tab.grid_system_check.setChecked(False)
    assert tab.grid_cell_size_spin.isEnabled() is False
    assert tab.grid_pitch_combo.isEnabled() is False
    assert "Custom / Simulation-only" in tab.fabrication_mode_help_label.text()


def test_fabrication_preset_option_has_user_facing_copy() -> None:
    _ = _get_app()
    tab = OptionsTab()

    group_titles = {group.title() for group in tab.findChildren(QGroupBox)}
    assert "Fabrication Presets & Display Units" in group_titles
    assert "physical board kit" in tab.grid_system_check.toolTip()
    assert "LEGO-style assembly guides" in tab.grid_system_check.toolTip()


def test_programmatic_fabrication_mode_sync_does_not_emit_stale_context() -> None:
    _ = _get_app()
    tab = OptionsTab()
    seen = []
    tab.physicalContextChanged.connect(seen.append)

    tab.set_grid_system_input(False, 2.5, "2_5cm")

    assert seen == []
    assert tab.grid_system_check.isChecked() is False
    assert tab.grid_cell_size_spin.value() == 2.5
    assert tab.grid_pitch_combo.currentData() == "2_5cm"
    assert "Custom / Simulation-only" in tab.fabrication_mode_help_label.text()


def test_blueprint_export_format_defaults_to_pdf_and_can_switch_to_svg() -> None:
    _ = _get_app()
    tab = OptionsTab()
    seen: list[str] = []
    tab.blueprintExportFormatChanged.connect(seen.append)

    assert tab.blueprint_export_format_combo.currentData() == "pdf"

    tab.blueprint_export_format_combo.setCurrentIndex(
        tab.blueprint_export_format_combo.findData("svg")
    )

    assert seen[-1] == "svg"
    tab.set_blueprint_export_format_input("pdf")
    assert tab.blueprint_export_format_combo.currentData() == "pdf"


def test_grid_cell_display_is_preset_authoritative() -> None:
    _ = _get_app()
    tab = OptionsTab()
    seen = []
    tab.physicalContextChanged.connect(seen.append)

    tab.grid_cell_size_spin.setValue(2.31)

    assert tab.grid_pitch_combo.currentData() == "2_5cm"
    assert tab.grid_cell_size_spin.value() == 2.5
    assert seen[-1].grid_pitch_choice == "2_5cm"
    assert seen[-1].grid_cell_cm == 2.5


def test_options_tab_emits_typed_physical_context() -> None:
    _ = _get_app()
    tab = OptionsTab()
    seen = []
    tab.physicalContextChanged.connect(seen.append)

    tab.grid_pitch_combo.setCurrentIndex(tab.grid_pitch_combo.findData("2_5cm"))

    assert seen
    assert seen[-1].enabled is True
    assert seen[-1].grid_pitch_choice == "2_5cm"
    assert seen[-1].grid_cell_cm == 2.5


def test_physical_context_store_is_single_authoritative_owner() -> None:
    _ = _get_app()
    store = PhysicalKitContextStore()
    seen = []
    store.context_changed.connect(seen.append)

    context = store.update_from_settings(grid_pitch_choice="2_5cm")

    assert store.context is context
    assert context.grid_pitch_choice == "2_5cm"
    assert context.grid_cell_cm == 2.5
    assert seen[-1] is context


def test_main_window_handles_grid_pitch_choice_setting() -> None:
    from automataii.presentation.qt.main_window import AutomataDesigner
    from automataii.shared.physical_kit import physical_context_from_settings

    window = AutomataDesigner.__new__(AutomataDesigner)

    AutomataDesigner._handle_physical_context_change(
        window,
        physical_context_from_settings(True, DEFAULT_GRID_CELL_CM, "2_5cm"),
    )

    assert window._grid_pitch_choice == "2_5cm"
    assert window._physical_context.grid_cell_cm == 2.5
    assert "_grid_pitch_choice" not in window.__dict__
    assert "_grid_cell_size_cm" not in window.__dict__
