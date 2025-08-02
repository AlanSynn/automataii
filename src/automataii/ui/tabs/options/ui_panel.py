# src/automataii/ui/tabs/options/ui_panel.py

import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class OptionsUIPanel(QWidget):
    """
    Pure UI component for the Options tab.
    Contains all widgets and layout but no business logic.
    """

    # Signals for user interactions
    theme_changed = pyqtSignal(str)
    animation_duration_changed = pyqtSignal(float)
    toolbar_visibility_changed = pyqtSignal(bool)
    part_properties_visibility_changed = pyqtSignal(bool)
    debug_mode_changed = pyqtSignal(bool)
    advanced_processing_visibility_changed = pyqtSignal(bool)
    unit_system_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Create and layout all UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)

        # Appearance Settings
        appearance_group = self._create_appearance_group()
        layout.addWidget(appearance_group)

        # Simulation Settings
        simulation_group = self._create_simulation_group()
        layout.addWidget(simulation_group)

        # Debug Settings
        debug_group = self._create_debug_group()
        layout.addWidget(debug_group)

        # Workflow Settings
        workflow_group = self._create_workflow_group()
        layout.addWidget(workflow_group)

        # Unit Settings
        unit_group = self._create_unit_group()
        layout.addWidget(unit_group)

        # Push all groups to the top
        layout.addStretch()

    def _create_appearance_group(self) -> QGroupBox:
        """Create the appearance settings group."""
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)
        appearance_layout.setSpacing(10)

        # Theme selection
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setToolTip("Select the application color theme.")
        appearance_layout.addRow("Theme:", self.theme_combo)

        # Toolbar visibility
        self.toolbar_toggle_check = QCheckBox("Show Toolbar")
        self.toolbar_toggle_check.setChecked(False)
        self.toolbar_toggle_check.setToolTip("Show or hide the main application toolbar.")
        appearance_layout.addRow(self.toolbar_toggle_check)

        # Part properties visibility
        self.part_props_toggle_check = QCheckBox("Show Part Properties Panel")
        self.part_props_toggle_check.setChecked(False)
        self.part_props_toggle_check.setToolTip(
            "Show or hide the 'Selected Part Properties' panel in the Editor tab."
        )
        appearance_layout.addRow(self.part_props_toggle_check)

        return appearance_group

    def _create_simulation_group(self) -> QGroupBox:
        """Create the simulation settings group."""
        simulation_group = QGroupBox("Simulation")
        simulation_layout = QFormLayout(simulation_group)
        simulation_layout.setSpacing(10)

        # Animation duration
        self.anim_duration_spin = QDoubleSpinBox()
        self.anim_duration_spin.setRange(0.1, 60.0)
        self.anim_duration_spin.setSingleStep(0.1)
        self.anim_duration_spin.setValue(2.0)
        self.anim_duration_spin.setToolTip(
            "Set the duration for one loop of the simulation animation (in seconds)."
        )
        simulation_layout.addRow("Animation Duration (s):", self.anim_duration_spin)

        return simulation_group

    def _create_debug_group(self) -> QGroupBox:
        """Create the debug settings group."""
        debug_group = QGroupBox("Debugging")
        debug_layout = QFormLayout(debug_group)
        debug_layout.setSpacing(10)

        # Debug mode
        self.debug_mode_check = QCheckBox("Enable Debug Visuals")
        self.debug_mode_check.setChecked(False)
        self.debug_mode_check.setToolTip(
            "Enable/disable debug visualizations in the image processing view."
        )
        debug_layout.addRow(self.debug_mode_check)

        return debug_group

    def _create_workflow_group(self) -> QGroupBox:
        """Create the workflow settings group."""
        workflow_group = QGroupBox("Workflow Customization")
        workflow_layout = QFormLayout(workflow_group)
        workflow_layout.setSpacing(10)

        # Advanced processing visibility
        self.adv_proc_toggle_check = QCheckBox("Show Detailed Processing Steps")
        self.adv_proc_toggle_check.setChecked(False)
        self.adv_proc_toggle_check.setToolTip(
            "Show or hide the detailed step-by-step processing controls in the Character Selection tab."
        )
        workflow_layout.addRow(self.adv_proc_toggle_check)

        return workflow_group

    def _create_unit_group(self) -> QGroupBox:
        """Create the unit settings group."""
        unit_group = QGroupBox("Grid & Display Units")
        unit_layout = QFormLayout(unit_group)
        unit_layout.setSpacing(10)

        # Unit system
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["cm", "inch", "px"])
        self.unit_combo.setCurrentText("cm")
        self.unit_combo.setToolTip("Select the unit system for grid display in editor views.")
        unit_layout.addRow("Grid Unit System:", self.unit_combo)

        return unit_group

    def _connect_signals(self) -> None:
        """Connect internal widget signals to our public signals."""
        self.theme_combo.currentTextChanged.connect(self.theme_changed.emit)
        self.anim_duration_spin.valueChanged.connect(self.animation_duration_changed.emit)
        self.toolbar_toggle_check.toggled.connect(self.toolbar_visibility_changed.emit)
        self.part_props_toggle_check.toggled.connect(self.part_properties_visibility_changed.emit)
        self.debug_mode_check.toggled.connect(self.debug_mode_changed.emit)
        self.adv_proc_toggle_check.toggled.connect(self.advanced_processing_visibility_changed.emit)
        self.unit_combo.currentTextChanged.connect(self.unit_system_changed.emit)

    def update_ui_from_state(self, state_manager) -> None:
        """Update UI elements based on state changes."""
        # Block signals during update to prevent loops
        self.theme_combo.blockSignals(True)
        self.anim_duration_spin.blockSignals(True)
        self.toolbar_toggle_check.blockSignals(True)
        self.part_props_toggle_check.blockSignals(True)
        self.debug_mode_check.blockSignals(True)
        self.adv_proc_toggle_check.blockSignals(True)
        self.unit_combo.blockSignals(True)

        try:
            # Update widget values from state
            self.theme_combo.setCurrentText(state_manager.theme)
            self.anim_duration_spin.setValue(state_manager.animation_duration)
            self.toolbar_toggle_check.setChecked(state_manager.toolbar_visible)
            self.part_props_toggle_check.setChecked(state_manager.part_properties_visible)
            self.debug_mode_check.setChecked(state_manager.debug_mode)
            self.adv_proc_toggle_check.setChecked(state_manager.advanced_processing_visible)
            self.unit_combo.setCurrentText(state_manager.unit_system)

            logger.debug("UI updated from state successfully")

        finally:
            # Re-enable signals
            self.theme_combo.blockSignals(False)
            self.anim_duration_spin.blockSignals(False)
            self.toolbar_toggle_check.blockSignals(False)
            self.part_props_toggle_check.blockSignals(False)
            self.debug_mode_check.blockSignals(False)
            self.adv_proc_toggle_check.blockSignals(False)
            self.unit_combo.blockSignals(False)

    def get_theme(self) -> str:
        """Get the current theme selection."""
        return self.theme_combo.currentText()

    def get_animation_duration(self) -> float:
        """Get the current animation duration."""
        return self.anim_duration_spin.value()

    def get_toolbar_visibility(self) -> bool:
        """Get the current toolbar visibility state."""
        return self.toolbar_toggle_check.isChecked()

    def get_part_properties_visibility(self) -> bool:
        """Get the current part properties visibility state."""
        return self.part_props_toggle_check.isChecked()

    def get_debug_mode(self) -> bool:
        """Get the current debug mode state."""
        return self.debug_mode_check.isChecked()

    def get_advanced_processing_visibility(self) -> bool:
        """Get the current advanced processing visibility state."""
        return self.adv_proc_toggle_check.isChecked()

    def get_unit_system(self) -> str:
        """Get the current unit system."""
        return self.unit_combo.currentText()

    def set_theme(self, theme: str) -> None:
        """Set the theme programmatically."""
        self.theme_combo.setCurrentText(theme)

    def set_animation_duration(self, duration: float) -> None:
        """Set the animation duration programmatically."""
        self.anim_duration_spin.setValue(duration)

    def set_toolbar_visibility(self, visible: bool) -> None:
        """Set the toolbar visibility programmatically."""
        self.toolbar_toggle_check.setChecked(visible)

    def set_part_properties_visibility(self, visible: bool) -> None:
        """Set the part properties visibility programmatically."""
        self.part_props_toggle_check.setChecked(visible)

    def set_debug_mode(self, enabled: bool) -> None:
        """Set the debug mode programmatically."""
        self.debug_mode_check.setChecked(enabled)

    def set_advanced_processing_visibility(self, visible: bool) -> None:
        """Set the advanced processing visibility programmatically."""
        self.adv_proc_toggle_check.setChecked(visible)

    def set_unit_system(self, unit: str) -> None:
        """Set the unit system programmatically."""
        self.unit_combo.setCurrentText(unit)
