import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QLineEdit, QLabel, QComboBox, QCheckBox, QHBoxLayout, QButtonGroup
)
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtCore import Qt, pyqtSignal

class OptionsTab(QWidget):
    """Widget for the Options tab, containing application settings."""
    # Signals to notify the main window of changes
    animationDurationChanged = pyqtSignal(float)
    themeChanged = pyqtSignal(str)
    debugModeChanged = pyqtSignal(bool)
    toolbarVisibilityChanged = pyqtSignal(bool)
    partPropertiesVisibilityChanged = pyqtSignal(bool) # New signal

    def __init__(self, initial_anim_duration=0.5, parent=None):
        super().__init__(parent)
        self._init_ui(initial_anim_duration)
        self._connect_signals()
        logging.debug("OptionsTab initialized.")

    def _init_ui(self, initial_anim_duration):
        """Creates the widgets and layout for the Options tab."""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(15)

        # --- Simulation Settings ---
        sim_group = QGroupBox("Simulation")
        sim_layout = QVBoxLayout(sim_group)
        sim_layout.setSpacing(10)

        # Animation Duration (Using QLineEdit)
        anim_duration_layout = QHBoxLayout()
        anim_label = QLabel("Animation Duration:")
        self.anim_duration_edit = QLineEdit()
        self.anim_duration_edit.setValidator(QDoubleValidator(0.01, 60.0, 2)) # Allow 0.01 to 60.0 with 2 decimals
        self.anim_duration_edit.setText(str(initial_anim_duration))
        self.anim_duration_edit.setToolTip("Enter the duration (in seconds) of one simulation loop.")
        self.anim_duration_edit.setMaximumWidth(80) # Limit width
        unit_label = QLabel(" s")
        anim_duration_layout.addWidget(anim_label)
        anim_duration_layout.addWidget(self.anim_duration_edit)
        anim_duration_layout.addWidget(unit_label)
        anim_duration_layout.addStretch()
        sim_layout.addLayout(anim_duration_layout)

        layout.addWidget(sim_group)

        # --- Appearance Settings ---
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)

        # Theme Selection (Checkboxes behaving like radio buttons)
        theme_layout = QHBoxLayout()
        self.theme_light_check = QCheckBox("Light")
        self.theme_dark_check = QCheckBox("Dark")
        self.theme_group = QButtonGroup(self) # Button group for exclusivity
        self.theme_group.addButton(self.theme_light_check)
        self.theme_group.addButton(self.theme_dark_check)
        self.theme_group.setExclusive(True) # Only one can be checked
        theme_layout.addWidget(self.theme_light_check)
        theme_layout.addWidget(self.theme_dark_check)
        theme_layout.addStretch()
        appearance_layout.addRow("Theme:", theme_layout)

        # Set initial theme state
        self.set_theme("Light") # Default to light

        # Debug Mode Checkbox
        self.debug_mode_check = QCheckBox("Enable Debug Visualization")
        self.debug_mode_check.setToolTip("Show bounding boxes and coordinate info in Image Processing tab.")
        appearance_layout.addRow(self.debug_mode_check)

        # Toolbar Visibility Checkbox
        self.show_toolbar_check = QCheckBox("Show Toolbar")
        self.show_toolbar_check.setToolTip("Toggle visibility of the main toolbar.")
        self.show_toolbar_check.setChecked(False)
        appearance_layout.addRow(self.show_toolbar_check)

        # Part Properties Visibility Checkbox
        self.show_part_properties_check = QCheckBox("Show Part Properties")
        self.show_part_properties_check.setToolTip("Toggle visibility of the Selected Part Properties panel.")
        self.show_part_properties_check.setChecked(False) # Hidden by default
        appearance_layout.addRow(self.show_part_properties_check)

        layout.addWidget(appearance_group)

        # --- Paths/Defaults Settings ---
        paths_group = QGroupBox("Default Paths")
        paths_layout = QVBoxLayout(paths_group)
        paths_label = QLabel("(Default path settings placeholder)")
        paths_layout.addWidget(paths_label)
        layout.addWidget(paths_group)

        layout.addStretch()

    def _connect_signals(self):
        """Connects internal widget signals to the class's public signals."""
        # Connect animation duration line edit (editingFinished is better than textChanged)
        self.anim_duration_edit.editingFinished.connect(self._emit_anim_duration)
        # Connect theme checkboxes
        self.theme_light_check.toggled.connect(self._on_theme_toggled)
        self.theme_dark_check.toggled.connect(self._on_theme_toggled)
        self.debug_mode_check.stateChanged.connect(self.on_debug_mode_changed)
        self.show_toolbar_check.stateChanged.connect(self.on_toolbar_visibility_changed)
        self.show_part_properties_check.stateChanged.connect(self.on_part_properties_visibility_changed) # Connect new checkbox

    def _emit_anim_duration(self):
        """Emits the animation duration when editing is finished."""
        try:
            value = float(self.anim_duration_edit.text())
            self.animationDurationChanged.emit(value)
            logging.debug(f"Animation duration emitted: {value}")
        except ValueError:
            logging.warning(f"Invalid animation duration input: {self.anim_duration_edit.text()}")
            # Optionally reset to previous valid value

    def _on_theme_toggled(self, checked):
        """Handles toggling of theme checkboxes and emits the themeChanged signal."""
        if not checked:
            return # Only react when a box is checked

        if self.theme_light_check.isChecked():
            self.themeChanged.emit("Light")
        elif self.theme_dark_check.isChecked():
            self.themeChanged.emit("Dark")

    # --- Public Methods (Getters/Setters) ---
    def get_animation_duration(self) -> float:
        """Returns the current valid value of the animation duration edit."""
        try:
            return float(self.anim_duration_edit.text())
        except ValueError:
            return 0.1 # Return default or last known good value

    def set_animation_duration(self, duration: float):
        """Sets the text of the animation duration edit."""
        self.anim_duration_edit.blockSignals(True)
        self.anim_duration_edit.setText(f"{duration:.2f}") # Format to 2 decimal places
        self.anim_duration_edit.blockSignals(False)

    def get_selected_theme(self) -> str:
        """Returns the currently selected theme name based on checkboxes."""
        if self.theme_light_check.isChecked():
            return "Light"
        elif self.theme_dark_check.isChecked():
            return "Dark"
        else:
            return "Light" # Default

    def set_theme(self, theme_name: str):
        """Sets the selected theme checkbox without emitting the signal."""
        self.theme_light_check.blockSignals(True)
        self.theme_dark_check.blockSignals(True)
        if theme_name == "Dark":
            self.theme_dark_check.setChecked(True)
        else:
            self.theme_light_check.setChecked(True)
        self.theme_light_check.blockSignals(False)
        self.theme_dark_check.blockSignals(False)

    def on_debug_mode_changed(self, state):
        """Internal slot to handle checkbox state change and emit signal."""
        is_checked = (state == Qt.CheckState.Checked.value)
        self.debugModeChanged.emit(is_checked)

    def on_toolbar_visibility_changed(self, state):
        """Internal slot for toolbar visibility checkbox change."""
        is_checked = (state == Qt.CheckState.Checked.value)
        self.toolbarVisibilityChanged.emit(is_checked)

    def on_part_properties_visibility_changed(self, state):
        """Internal slot for part properties visibility checkbox change."""
        is_checked = (state == Qt.CheckState.Checked.value)
        self.partPropertiesVisibilityChanged.emit(is_checked)
