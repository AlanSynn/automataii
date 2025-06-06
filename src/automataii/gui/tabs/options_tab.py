from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QDoubleSpinBox,
    QCheckBox,
)
from PyQt6.QtCore import pyqtSignal, Qt


class OptionsTab(QWidget):
    """Tab for application options and settings."""

    themeChanged = pyqtSignal(str)
    animationDurationChanged = pyqtSignal(float)
    toolbarVisibilityChanged = pyqtSignal(bool)
    partPropertiesVisibilityChanged = pyqtSignal(bool)  # New signal
    debugModeChanged = pyqtSignal(bool)  # Signal for debug mode
    setting_changed = pyqtSignal(str, object)  # Generic signal for any setting change
    advancedProcessingVisibilityChanged = pyqtSignal(
        bool
    )  # For detailed processing steps visibility
    unitChanged = pyqtSignal(str)  # NEW: Signal for unit changes

    def __init__(self, initial_anim_duration: float = 2.0, parent=None):
        super().__init__(parent)
        self._initial_anim_duration = initial_anim_duration
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            15, 15, 15, 15
        )  # Add more padding around the tab content
        layout.setSpacing(20)  # Increase spacing between groups

        # --- Appearance Settings ---
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)
        appearance_layout.setSpacing(10)  # Spacing within the form

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.currentTextChanged.connect(self.themeChanged.emit)
        self.theme_combo.currentTextChanged.connect(
            lambda val: self.setting_changed.emit("theme", val)
        )
        self.theme_combo.setToolTip("Select the application color theme.")
        appearance_layout.addRow("Theme:", self.theme_combo)

        self.toolbar_toggle_check = QCheckBox("Show Toolbar")
        self.toolbar_toggle_check.setChecked(False)  # Toolbar hidden by default
        self.toolbar_toggle_check.toggled.connect(self.toolbarVisibilityChanged.emit)
        self.toolbar_toggle_check.toggled.connect(
            lambda val: self.setting_changed.emit("toolbar_visibility", val)
        )
        self.toolbar_toggle_check.setToolTip(
            "Show or hide the main application toolbar."
        )
        appearance_layout.addRow(self.toolbar_toggle_check)

        # New Checkbox for Part Properties
        self.part_props_toggle_check = QCheckBox("Show Part Properties Panel")
        self.part_props_toggle_check.setChecked(False)  # Hidden by default
        self.part_props_toggle_check.toggled.connect(
            self.partPropertiesVisibilityChanged.emit
        )
        self.part_props_toggle_check.toggled.connect(
            lambda val: self.setting_changed.emit("part_properties_visibility", val)
        )
        self.part_props_toggle_check.setToolTip(
            "Show or hide the 'Selected Part Properties' panel in the Editor tab."
        )
        appearance_layout.addRow(self.part_props_toggle_check)

        layout.addWidget(appearance_group)

        # --- Simulation Settings ---
        simulation_group = QGroupBox("Simulation")
        simulation_layout = QFormLayout(simulation_group)
        simulation_layout.setSpacing(10)

        self.anim_duration_spin = QDoubleSpinBox()
        self.anim_duration_spin.setRange(0.1, 60.0)  # Min 0.1s, Max 60s
        self.anim_duration_spin.setSingleStep(0.1)
        self.anim_duration_spin.setValue(
            self._initial_anim_duration
        )  # Use initial value
        self.anim_duration_spin.valueChanged.connect(self.animationDurationChanged.emit)
        self.anim_duration_spin.valueChanged.connect(
            lambda val: self.setting_changed.emit("animation_duration", val)
        )
        self.anim_duration_spin.setToolTip(
            "Set the duration for one loop of the simulation animation (in seconds)."
        )
        simulation_layout.addRow("Animation Duration (s):", self.anim_duration_spin)

        layout.addWidget(simulation_group)

        # --- Debug Settings ---
        debug_group = QGroupBox("Debugging")
        debug_layout = QFormLayout(debug_group)
        debug_layout.setSpacing(10)

        self.debug_mode_check = QCheckBox("Enable Debug Visuals")
        self.debug_mode_check.setChecked(False)  # Debug mode off by default
        self.debug_mode_check.toggled.connect(self.debugModeChanged.emit)
        self.debug_mode_check.toggled.connect(
            lambda val: self.setting_changed.emit("debug_mode", val)
        )
        self.debug_mode_check.setToolTip(
            "Enable/disable debug visualizations in the image processing view."
        )
        debug_layout.addRow(self.debug_mode_check)

        layout.addWidget(debug_group)

        # --- Workflow Settings ---
        workflow_group = QGroupBox("Workflow Customization")
        workflow_layout = QFormLayout(workflow_group)
        workflow_layout.setSpacing(10)

        self.adv_proc_toggle_check = QCheckBox("Show Detailed Processing Steps")
        self.adv_proc_toggle_check.setChecked(False)  # Hidden by default
        self.adv_proc_toggle_check.toggled.connect(
            self.advancedProcessingVisibilityChanged.emit
        )
        self.adv_proc_toggle_check.toggled.connect(
            lambda val: self.setting_changed.emit("detailed_processing_visibility", val)
        )
        self.adv_proc_toggle_check.setToolTip(
            "Show or hide the detailed step-by-step processing controls in the Character Selection tab."
        )
        workflow_layout.addRow(self.adv_proc_toggle_check)

        layout.addWidget(workflow_group)

        # --- Display Unit Settings ---
        unit_settings_group = QGroupBox("Grid & Display Units")
        unit_settings_layout = QFormLayout(unit_settings_group)
        unit_settings_layout.setSpacing(10)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["cm", "inch", "px"])  # Standard units
        self.unit_combo.setCurrentText("cm")  # Default to cm
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)
        self.unit_combo.setToolTip(
            "Select the unit system for grid display in editor views."
        )
        unit_settings_layout.addRow("Grid Unit System:", self.unit_combo)

        layout.addWidget(unit_settings_group)

        layout.addStretch()  # Push all groups to the top

    def _on_unit_changed(self, unit_text: str):
        """Emits signals when the unit system selection changes."""
        self.unitChanged.emit(unit_text)
        self.setting_changed.emit(
            "unit_system", unit_text
        )  # Also emit through generic signal

    def set_theme(self, theme_name: str):
        """Sets the theme combo box to the given theme name."""
        self.theme_combo.setCurrentText(theme_name)

    def get_animation_duration(self) -> float:
        """Returns the current animation duration."""
        return self.anim_duration_spin.value()

    def set_toolbar_visibility(self, visible: bool):
        """Sets the 'Show Toolbar' checkbox state."""
        self.toolbar_toggle_check.setChecked(visible)

    def set_part_properties_visibility(self, visible: bool):
        """Sets the 'Show Part Properties Panel' checkbox state."""
        self.part_props_toggle_check.setChecked(visible)

    def set_debug_mode(self, enabled: bool):
        """Sets the 'Enable Debug Visuals' checkbox state."""
        self.debug_mode_check.setChecked(enabled)

    def set_animation_duration_input(self, duration_seconds: float):
        """Sets the value of the animation duration spin box."""
        self.anim_duration_spin.setValue(duration_seconds)
