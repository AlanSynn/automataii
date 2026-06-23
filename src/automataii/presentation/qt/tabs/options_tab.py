from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from automataii.shared.physical_kit import (
    DEFAULT_GRID_CELL_CM,
    GRID_PITCH_CHOICES,
    PhysicalKitContext,
    grid_cell_cm_for_pitch_choice,
    nearest_pitch_choice,
    physical_context_from_settings,
    physical_kit_preset_summary,
)

DEFAULT_AUTOSAVE_INTERVAL_SECONDS = 60
MIN_AUTOSAVE_INTERVAL_SECONDS = 10
MAX_AUTOSAVE_INTERVAL_SECONDS = 3600


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
    physicsSnapModeChanged = pyqtSignal(str)  # NEW: Physics snap intensity changes
    gridSystemEnabledChanged = pyqtSignal(bool)
    gridCellSizeChanged = pyqtSignal(float)
    gridPitchChoiceChanged = pyqtSignal(str)
    physicalContextChanged = pyqtSignal(object)
    blueprintExportFormatChanged = pyqtSignal(str)
    autosaveSettingsChanged = pyqtSignal(bool, int)

    def __init__(
        self,
        initial_anim_duration: float = 2.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._initial_anim_duration = initial_anim_duration
        self._scroll_area: QScrollArea | None = None
        self._content_widget: QWidget | None = None
        self._grid_pitch_syncing = False
        self._init_ui()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root_layout.addWidget(self._scroll_area)

        self._content_widget = QWidget(self._scroll_area)
        self._content_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._scroll_area.setWidget(self._content_widget)

        layout = QVBoxLayout(self._content_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        # --- Appearance Settings ---
        appearance_group = QGroupBox("Appearance")
        appearance_layout = self._create_group_form_layout(appearance_group)

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
        self.toolbar_toggle_check.setToolTip("Show or hide the main application toolbar.")
        appearance_layout.addRow(self.toolbar_toggle_check)

        # New Checkbox for Part Properties
        self.part_props_toggle_check = QCheckBox("Show Part Properties Panel")
        self.part_props_toggle_check.setChecked(False)  # Hidden by default
        self.part_props_toggle_check.toggled.connect(self.partPropertiesVisibilityChanged.emit)
        self.part_props_toggle_check.toggled.connect(
            lambda val: self.setting_changed.emit("part_properties_visibility", val)
        )
        self.part_props_toggle_check.setToolTip(
            "Show or hide the 'Selected Part Properties' panel in the Editor tab."
        )
        appearance_layout.addRow(self.part_props_toggle_check)

        self._add_group(layout, appearance_group)

        # --- Simulation Settings ---
        simulation_group = QGroupBox("Simulation")
        simulation_layout = self._create_group_form_layout(simulation_group)

        self.anim_duration_spin = QDoubleSpinBox()
        self.anim_duration_spin.setRange(0.1, 60.0)  # Min 0.1s, Max 60s
        self.anim_duration_spin.setSingleStep(0.1)
        self.anim_duration_spin.setValue(self._initial_anim_duration)  # Use initial value
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

        self._add_group(layout, simulation_group)

        # --- Performance Settings ---
        performance_group = QGroupBox("Performance")
        perf_layout = self._create_group_form_layout(performance_group)

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
        self.perf_help_label.setWordWrap(True)
        self.perf_help_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.perf_help_label.setStyleSheet("color: #666; font-size: 10px;")
        perf_layout.addRow(self.perf_help_label)

        # Physics Snap Mode selector (Fast / Balanced / High)
        self.physics_snap_combo = QComboBox()
        self.physics_snap_combo.addItems(["Fast", "Balanced", "High"])  # Snap intensity
        self.physics_snap_combo.setCurrentText("Balanced")
        self.physics_snap_combo.currentTextChanged.connect(self._on_physics_snap_mode_changed)
        self.physics_snap_combo.currentTextChanged.connect(
            lambda val: self.setting_changed.emit("physics_snap_mode", val)
        )
        self.physics_snap_combo.setToolTip(
            "Set guard strength for soft physics snaps (4-bar, gears, cam)."
        )
        perf_layout.addRow("Physics Snap Mode:", self.physics_snap_combo)

        self._add_group(layout, performance_group)

        # --- Debug Settings ---
        debug_group = QGroupBox("Debugging")
        debug_layout = self._create_group_form_layout(debug_group)

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

        self._add_group(layout, debug_group)

        # --- Workflow Settings ---
        workflow_group = QGroupBox("Workflow Customization")
        workflow_layout = self._create_group_form_layout(workflow_group)

        self.adv_proc_toggle_check = QCheckBox("Show Detailed Processing Steps")
        self.adv_proc_toggle_check.setChecked(False)  # Hidden by default
        self.adv_proc_toggle_check.toggled.connect(self.advancedProcessingVisibilityChanged.emit)
        self.adv_proc_toggle_check.toggled.connect(
            lambda val: self.setting_changed.emit("detailed_processing_visibility", val)
        )
        self.adv_proc_toggle_check.setToolTip(
            "Show or hide the detailed step-by-step processing controls in the Character Selection tab."
        )
        workflow_layout.addRow(self.adv_proc_toggle_check)

        self.autosave_enabled_check = QCheckBox("Enable Autosave")
        self.autosave_enabled_check.setChecked(True)
        self.autosave_enabled_check.setToolTip(
            "Keep a lightweight recovery snapshot when the project has changed."
        )

        self.autosave_interval_spin = QSpinBox()
        self.autosave_interval_spin.setRange(
            MIN_AUTOSAVE_INTERVAL_SECONDS,
            MAX_AUTOSAVE_INTERVAL_SECONDS,
        )
        self.autosave_interval_spin.setSingleStep(10)
        self.autosave_interval_spin.setSuffix(" s")
        self.autosave_interval_spin.setValue(DEFAULT_AUTOSAVE_INTERVAL_SECONDS)
        self.autosave_interval_spin.setToolTip(
            "Minimum time between autosaves. Unchanged projects are skipped."
        )

        self.autosave_enabled_check.toggled.connect(self._on_autosave_settings_changed)
        self.autosave_interval_spin.valueChanged.connect(self._on_autosave_settings_changed)
        workflow_layout.addRow(self.autosave_enabled_check)
        workflow_layout.addRow("Autosave Interval:", self.autosave_interval_spin)

        self._add_group(layout, workflow_group)

        # --- Fabrication / Blueprint Settings ---
        fabrication_group = QGroupBox("Fabrication / Blueprint Export")
        fabrication_layout = self._create_group_form_layout(fabrication_group)

        self.blueprint_export_format_combo = QComboBox()
        self.blueprint_export_format_combo.addItem("PDF (default)", "pdf")
        self.blueprint_export_format_combo.addItem("SVG", "svg")
        self.blueprint_export_format_combo.setCurrentIndex(0)
        self.blueprint_export_format_combo.currentIndexChanged.connect(
            self._on_blueprint_export_format_changed
        )
        self.blueprint_export_format_combo.setToolTip(
            "Choose the file type for current-design cut sheets. Assembly guides remain PDF-first when available."
        )
        fabrication_layout.addRow("Cut-sheet File Type:", self.blueprint_export_format_combo)

        self._add_group(layout, fabrication_group)

        # --- Fabrication preset / display settings ---
        unit_settings_group = QGroupBox("Fabrication Presets & Display Units")
        unit_settings_layout = self._create_group_form_layout(unit_settings_group)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["cm", "inch", "px"])  # Standard units
        self.unit_combo.setCurrentText("cm")  # Default to cm
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)
        self.unit_combo.setToolTip("Select the unit system for grid display in editor views.")
        unit_settings_layout.addRow("Grid Unit System:", self.unit_combo)

        self.grid_system_check = QCheckBox("Fabrication-ready preset mode")
        self.grid_system_check.setChecked(True)
        self.grid_system_check.toggled.connect(self._on_grid_system_toggled)
        self.grid_system_check.setToolTip(
            "Default on: snap mechanisms to the physical board kit so blueprint exports "
            "can produce LEGO-style assembly guides. Turn off only for Custom / "
            "Simulation-only exploration."
        )
        unit_settings_layout.addRow(self.grid_system_check)

        self.fabrication_mode_help_label = QLabel()
        self.fabrication_mode_help_label.setWordWrap(True)
        self.fabrication_mode_help_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.fabrication_mode_help_label.setStyleSheet("color: #666; font-size: 10px;")
        unit_settings_layout.addRow(self.fabrication_mode_help_label)

        self.grid_pitch_combo = QComboBox()
        for choice in GRID_PITCH_CHOICES:
            self.grid_pitch_combo.addItem(choice.label, choice.key)
        default_pitch = nearest_pitch_choice(DEFAULT_GRID_CELL_CM)
        default_index = self.grid_pitch_combo.findData(default_pitch.key)
        if default_index >= 0:
            self.grid_pitch_combo.setCurrentIndex(default_index)
        self.grid_pitch_combo.currentIndexChanged.connect(self._on_grid_pitch_choice_changed)
        self.grid_pitch_combo.setToolTip(
            "Choose a physical pegboard pitch. The default board pitch is 20.0 mm (2.0 cm)."
        )
        unit_settings_layout.addRow("Physical Board Pitch:", self.grid_pitch_combo)

        self.grid_cell_size_spin = QDoubleSpinBox()
        self.grid_cell_size_spin.setRange(0.5, 20.0)
        self.grid_cell_size_spin.setSingleStep(0.01)
        self.grid_cell_size_spin.setDecimals(2)
        self.grid_cell_size_spin.setSuffix(" cm")
        self.grid_cell_size_spin.setValue(DEFAULT_GRID_CELL_CM)
        self.grid_cell_size_spin.setReadOnly(True)
        self.grid_cell_size_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.grid_cell_size_spin.valueChanged.connect(self._on_grid_cell_size_changed)
        self.grid_cell_size_spin.setToolTip(
            "Read-only pitch display. Choose one of the supported physical board presets above."
        )
        unit_settings_layout.addRow("Grid Cell Size:", self.grid_cell_size_spin)
        self._update_fabrication_mode_help(True)

        self._add_group(layout, unit_settings_group)

        layout.addStretch()  # Push all groups to the top

    @staticmethod
    def _create_group_form_layout(group: QGroupBox) -> QFormLayout:
        layout = QFormLayout(group)
        layout.setSpacing(8)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        return layout

    @staticmethod
    def _add_group(parent_layout: QVBoxLayout, group: QGroupBox) -> None:
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        parent_layout.addWidget(group)

    def _on_unit_changed(self, unit_text: str) -> None:
        """Emits signals when the unit system selection changes."""
        self.unitChanged.emit(unit_text)
        self.setting_changed.emit("unit_system", unit_text)  # Also emit through generic signal

    def _on_grid_system_toggled(self, enabled: bool) -> None:
        self.grid_pitch_combo.setEnabled(enabled)
        self.grid_cell_size_spin.setEnabled(enabled)
        self._update_fabrication_mode_help(enabled)
        self.gridSystemEnabledChanged.emit(enabled)
        self.setting_changed.emit("fabrication_ready_preset_mode", enabled)
        self.physicalContextChanged.emit(self._current_physical_context())

    def _update_fabrication_mode_help(self, enabled: bool) -> None:
        if enabled:
            text = (
                "Preset / Fabrication-ready: mechanisms snap to the selected physical board "
                f"pitch and kit parts ({physical_kit_preset_summary()}); assembly-guide PDFs "
                "can be generated when the physical contract has no warnings."
            )
        else:
            text = (
                "Custom / Simulation-only: freeform exploration is preserved, but board "
                "assembly-guide PDFs are gated until the design is converted back to kit presets."
            )
        self.fabrication_mode_help_label.setText(text)

    def _on_grid_cell_size_changed(self, value: float) -> None:
        if self._grid_pitch_syncing:
            return
        choice = nearest_pitch_choice(float(value))
        self._set_pitch_choice(choice.key, emit=True)

    def _on_grid_pitch_choice_changed(self, index: int) -> None:
        key = self.grid_pitch_combo.itemData(index)
        self._set_pitch_choice(key, emit=True)

    def _set_pitch_choice(self, key: object, *, emit: bool) -> None:
        choice = next(
            (candidate for candidate in GRID_PITCH_CHOICES if candidate.key == key),
            None,
        )
        if choice is None:
            return

        self._grid_pitch_syncing = True
        previous_combo = self.grid_pitch_combo.blockSignals(True)
        previous_spin = self.grid_cell_size_spin.blockSignals(True)
        try:
            index = self.grid_pitch_combo.findData(choice.key)
            if index >= 0:
                self.grid_pitch_combo.setCurrentIndex(index)
            self.grid_cell_size_spin.setValue(choice.pitch_cm)
        finally:
            self.grid_cell_size_spin.blockSignals(previous_spin)
            self.grid_pitch_combo.blockSignals(previous_combo)
            self._grid_pitch_syncing = False

        if emit:
            self.physicalContextChanged.emit(self._current_physical_context())

    def _current_physical_context(self) -> PhysicalKitContext:
        return physical_context_from_settings(
            self.grid_system_check.isChecked(),
            self.grid_cell_size_spin.value(),
            self.grid_pitch_combo.currentData(),
        )

    def _sync_grid_pitch_combo(self, value_cm: float) -> None:
        choice = nearest_pitch_choice(value_cm)
        self._set_pitch_choice(choice.key, emit=False)

    def _on_timing_profile_changed(self, text: str) -> None:
        # Normalize to code-friendly names
        mapping = {
            "Linear": "linear",
            "Ease-In": "ease_in",
            "Ease-Out": "ease_out",
            "Ease-In-Out": "ease_in_out",
        }
        self.timingProfileChanged.emit(mapping.get(text, "linear"))

    def _on_performance_preset_changed(self, preset_text: str) -> None:
        # Normalize to code-friendly names if needed; emit raw for now
        self.performancePresetChanged.emit(preset_text)

    def _on_physics_snap_mode_changed(self, text: str) -> None:
        # Emit normalized lowercase string (fast | balanced | high)
        mode = str(text).strip().lower()
        if mode not in ("fast", "balanced", "high"):
            # Fallback to balanced
            mode = "balanced"
        self.physicsSnapModeChanged.emit(mode)

    def _on_blueprint_export_format_changed(self, _index: int) -> None:
        fmt = str(self.blueprint_export_format_combo.currentData() or "pdf").strip().lower()
        if fmt not in {"pdf", "svg"}:
            fmt = "pdf"
        self.blueprintExportFormatChanged.emit(fmt)
        self.setting_changed.emit("blueprint_export_format", fmt)

    def _on_autosave_settings_changed(self, *_args: object) -> None:
        enabled = self.autosave_enabled_check.isChecked()
        interval_seconds = int(self.autosave_interval_spin.value())
        self.autosave_interval_spin.setEnabled(enabled)
        self.autosaveSettingsChanged.emit(enabled, interval_seconds)
        self.setting_changed.emit(
            "autosave_settings",
            {"enabled": enabled, "interval_seconds": interval_seconds},
        )

    def set_autosave_settings_input(self, enabled: bool, interval_seconds: object) -> None:
        previous_check = self.autosave_enabled_check.blockSignals(True)
        previous_spin = self.autosave_interval_spin.blockSignals(True)
        try:
            self.autosave_enabled_check.setChecked(bool(enabled))
            if isinstance(interval_seconds, int | str) and not isinstance(
                interval_seconds,
                bool,
            ):
                try:
                    interval = int(interval_seconds)
                except ValueError:
                    interval = DEFAULT_AUTOSAVE_INTERVAL_SECONDS
            else:
                interval = DEFAULT_AUTOSAVE_INTERVAL_SECONDS
            interval = min(
                MAX_AUTOSAVE_INTERVAL_SECONDS,
                max(MIN_AUTOSAVE_INTERVAL_SECONDS, interval),
            )
            self.autosave_interval_spin.setValue(interval)
            self.autosave_interval_spin.setEnabled(bool(enabled))
        finally:
            self.autosave_interval_spin.blockSignals(previous_spin)
            self.autosave_enabled_check.blockSignals(previous_check)

    def set_blueprint_export_format_input(self, fmt: str) -> None:
        normalized = str(fmt).strip().lower()
        if normalized not in {"pdf", "svg"}:
            normalized = "pdf"
        index = self.blueprint_export_format_combo.findData(normalized)
        if index >= 0:
            self.blueprint_export_format_combo.setCurrentIndex(index)

    def set_debug_mode(self, enabled: bool) -> None:
        """Sets the 'Enable Debug Visuals' checkbox state."""
        self.debug_mode_check.setChecked(enabled)

    def set_animation_duration_input(self, duration_seconds: float) -> None:
        """Sets the value of the animation duration spin box."""
        self.anim_duration_spin.setValue(duration_seconds)

    def set_physics_snap_mode_input(self, mode: str) -> None:
        """Sets the Physics Snap Mode combo selection from external code."""
        mapping = {
            "fast": "Fast",
            "balanced": "Balanced",
            "high": "High",
        }
        label = mapping.get(str(mode).strip().lower(), "Balanced")
        self.physics_snap_combo.setCurrentText(label)

    def set_grid_system_input(
        self,
        enabled: bool,
        cell_size_cm: float,
        pitch_choice_key: str | None = None,
    ) -> None:
        previous_check = self.grid_system_check.blockSignals(True)
        try:
            self.grid_system_check.setChecked(bool(enabled))
        finally:
            self.grid_system_check.blockSignals(previous_check)
        key = pitch_choice_key or nearest_pitch_choice(float(cell_size_cm)).key
        cell_cm = grid_cell_cm_for_pitch_choice(key, cell_size_cm)
        self._set_pitch_choice(key, emit=False)
        previous = self.grid_cell_size_spin.blockSignals(True)
        self.grid_cell_size_spin.setValue(cell_cm)
        self.grid_cell_size_spin.blockSignals(previous)
        self.grid_pitch_combo.setEnabled(bool(enabled))
        self.grid_cell_size_spin.setEnabled(bool(enabled))
        self._update_fabrication_mode_help(bool(enabled))
