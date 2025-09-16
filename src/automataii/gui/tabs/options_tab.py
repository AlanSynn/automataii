from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class OptionsTab(QWidget):
    """Tab for application options and settings."""

    themeChanged = pyqtSignal(str)
    animationDurationChanged = pyqtSignal(float)
    timingProfileChanged = pyqtSignal(str)
    toolbarVisibilityChanged = pyqtSignal(bool)
    partPropertiesVisibilityChanged = pyqtSignal(bool)  # New signal
    debugModeChanged = pyqtSignal(bool)  # Signal for debug mode
    setting_changed = pyqtSignal(str, object)  # Generic signal for any setting change
    advancedProcessingVisibilityChanged = pyqtSignal(
        bool
    )  # For detailed processing steps visibility
    unitChanged = pyqtSignal(str)  # NEW: Signal for unit changes
    performancePresetChanged = pyqtSignal(str)  # NEW: Performance preset changes

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

        # Timing profile selector (Linear / Ease-In / Ease-Out / Ease-In-Out)
        self.timing_combo = QComboBox()
        self.timing_combo.addItems(["Linear", "Ease-In", "Ease-Out", "Ease-In-Out"])
        self.timing_combo.setCurrentText("Linear")
        self.timing_combo.currentTextChanged.connect(self._on_timing_profile_changed)
        self.timing_combo.currentTextChanged.connect(
            lambda val: self.setting_changed.emit("timing_profile", val)
        )
        self.timing_combo.setToolTip(
            "Select the timing curve used to map animation progress (pacing)."
        )
        simulation_layout.addRow("Timing Profile:", self.timing_combo)

        layout.addWidget(simulation_group)

        # --- Performance Settings ---
        performance_group = QGroupBox("Performance")
        perf_layout = QFormLayout(performance_group)
        perf_layout.setSpacing(10)

        self.perf_preset_combo = QComboBox()
        self.perf_preset_combo.addItems(["Fast", "Balanced", "High"])  # Presets
        self.perf_preset_combo.setCurrentText("Balanced")
        self.perf_preset_combo.currentTextChanged.connect(self._on_performance_preset_changed)
        self.perf_preset_combo.currentTextChanged.connect(
            lambda val: self.setting_changed.emit("performance_preset", val)
        )
        self.perf_preset_combo.setToolTip(
            "Choose a performance preset for mechanism simulation (Fast/Balanced/High)."
        )
        perf_layout.addRow("Preset:", self.perf_preset_combo)

        self.perf_help_label = QLabel(
            "Fast: smoother FPS, simpler visuals\n"
            "Balanced: default settings\n"
            "High: finer visuals, more updates"
        )
        self.perf_help_label.setStyleSheet("color: #666; font-size: 10px;")
        perf_layout.addRow(self.perf_help_label)

        layout.addWidget(performance_group)

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

    def _on_timing_profile_changed(self, text: str):
        # Normalize to code-friendly names
        mapping = {
            "Linear": "linear",
            "Ease-In": "ease_in",
            "Ease-Out": "ease_out",
            "Ease-In-Out": "ease_in_out",
        }
        self.timingProfileChanged.emit(mapping.get(text, "linear"))

    def _on_performance_preset_changed(self, preset_text: str):
        # Normalize to code-friendly names if needed; emit raw for now
        self.performancePresetChanged.emit(preset_text)





    def set_debug_mode(self, enabled: bool):
        """Sets the 'Enable Debug Visuals' checkbox state."""
        self.debug_mode_check.setChecked(enabled)

    def set_animation_duration_input(self, duration_seconds: float):
        """Sets the value of the animation duration spin box."""
        self.anim_duration_spin.setValue(duration_seconds)
