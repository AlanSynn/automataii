import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QDoubleSpinBox, QLabel, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal

class OptionsTab(QWidget):
    """Widget for the Options tab, containing application settings."""
    # Signals to notify the main window of changes
    animationDurationChanged = pyqtSignal(float)
    themeChanged = pyqtSignal(str)
    debugModeChanged = pyqtSignal(bool)

    def __init__(self, initial_anim_duration=5.0, parent=None):
        super().__init__(parent)
        self._init_ui(initial_anim_duration)
        self._connect_signals()
        logging.debug("OptionsTab initialized.")

    def _init_ui(self, initial_anim_duration):
        """Creates the widgets and layout for the Options tab."""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(15)

        # --- General Settings ---
        general_group = QGroupBox("General")
        general_layout = QFormLayout(general_group)

        # Theme Selection
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setToolTip("Change the application's color theme.")
        general_layout.addRow("Theme:", self.theme_combo)

        # Debug Mode Checkbox
        self.debug_mode_check = QCheckBox("Enable Debug Visualization")
        self.debug_mode_check.setToolTip("Show bounding boxes and coordinate info in Image Processing tab.")
        general_layout.addRow(self.debug_mode_check)

        layout.addWidget(general_group)

        # --- Simulation Settings ---
        sim_group = QGroupBox("Simulation")
        sim_layout = QFormLayout(sim_group)

        self.anim_duration_spin = QDoubleSpinBox()
        self.anim_duration_spin.setRange(0.1, 60.0)
        self.anim_duration_spin.setSingleStep(0.1)
        self.anim_duration_spin.setSuffix(" s")
        self.anim_duration_spin.setValue(initial_anim_duration)
        self.anim_duration_spin.setToolTip("Set the duration of one simulation loop.")
        sim_layout.addRow("Animation Duration:", self.anim_duration_spin)
        layout.addWidget(sim_group)

        # --- Appearance Settings ---
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)

        # Re-add Theme ComboBox
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setToolTip("Select the application theme.")
        appearance_layout.addRow("Theme:", self.theme_combo)

        # Placeholder for other appearance options
        font_label = QLabel("(Font options placeholder)")
        appearance_layout.addRow(font_label)

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
        self.anim_duration_spin.valueChanged.connect(self.animationDurationChanged)
        self.theme_combo.currentTextChanged.connect(self.themeChanged)
        self.debug_mode_check.stateChanged.connect(self.on_debug_mode_changed)

    # --- Public Methods (Getters/Setters) ---
    def get_animation_duration(self) -> float:
        """Returns the current value of the animation duration spinbox."""
        return self.anim_duration_spin.value()

    def set_animation_duration(self, duration: float):
        """Sets the value of the animation duration spinbox."""
        self.anim_duration_spin.blockSignals(True)
        self.anim_duration_spin.setValue(duration)
        self.anim_duration_spin.blockSignals(False)

    def get_selected_theme(self) -> str:
        """Returns the currently selected theme name."""
        return self.theme_combo.currentText()

    def set_theme(self, theme_name: str):
        """Sets the selected theme in the combo box without emitting the signal."""
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentText(theme_name)
        self.theme_combo.blockSignals(False)

    def on_debug_mode_changed(self, state):
        """Internal slot to handle checkbox state change and emit signal."""
        is_checked = (state == Qt.CheckState.Checked.value)
        self.debugModeChanged.emit(is_checked)
