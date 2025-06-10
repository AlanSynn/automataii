"""Control panels for mechanism generation."""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QComboBox, QListWidget, QDoubleSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from automataii.gui.dialogs.recommendation.constants import (
    MECHANISM_TYPE_USER_DISPLAY_4_BAR,
    MECHANISM_TYPE_USER_DISPLAY_3_BAR,
    MECHANISM_TYPE_USER_DISPLAY_CAM,
)


class PartSelectionPanel(QGroupBox):
    """Panel for selecting character parts."""

    part_selected = pyqtSignal(str)  # part_name

    def __init__(self, parent=None):
        super().__init__("1 Part Selection", parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.parts_list = QListWidget()
        self.parts_list.setToolTip("Select a part to generate a mechanism for its motion")
        self.parts_list.currentItemChanged.connect(self._on_selection_changed)

        layout.addWidget(self.parts_list)

    def _on_selection_changed(self, current, previous):
        if current:
            part_name = current.data(Qt.ItemDataRole.UserRole)
            if part_name:
                self.part_selected.emit(part_name)

    def update_parts(self, parts_with_paths: list):
        """Update the parts list."""
        self.parts_list.clear()
        for part_name, has_path in parts_with_paths:
            text = f"{part_name} (path defined)" if has_path else part_name
            item = self.parts_list.addItem(text)
            self.parts_list.item(self.parts_list.count() - 1).setData(
                Qt.ItemDataRole.UserRole, part_name
            )

    def update_parts_list(self, part_names: list):
        """Update the parts list with part names."""
        self.parts_list.clear()
        for part_name in part_names:
            item = self.parts_list.addItem(part_name)
            self.parts_list.item(self.parts_list.count() - 1).setData(
                Qt.ItemDataRole.UserRole, part_name
            )
    
    def clear(self):
        """Clear the parts list."""
        self.parts_list.clear()


class MechanismTypePanel(QWidget):
    """Panel for mechanism type selection and parameters."""

    mechanism_type_changed = pyqtSignal(str)
    select_cam_center = pyqtSignal()
    select_pivot_a_3bar = pyqtSignal()
    select_pivot_a_4bar = pyqtSignal()
    select_pivot_d_4bar = pyqtSignal()
    select_driver_center = pyqtSignal()
    select_driven_center = pyqtSignal()
    gear_ratio_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Type selection
        type_layout = QFormLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            MECHANISM_TYPE_USER_DISPLAY_CAM,
            MECHANISM_TYPE_USER_DISPLAY_3_BAR,
            MECHANISM_TYPE_USER_DISPLAY_4_BAR,
        ])
        self.type_combo.setToolTip("Select the type of mechanism to generate")
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addRow("Type:", self.type_combo)
        layout.addLayout(type_layout)

        # Parameter panels
        self.params_layout = QVBoxLayout()
        layout.addLayout(self.params_layout)

        # Create all parameter groups
        self._create_cam_params()
        self._create_3bar_params()
        self._create_4bar_params()
        self._create_gear_params()

        # Show initial params
        self._on_type_changed(self.type_combo.currentText())

    def _create_cam_params(self):
        self.cam_group = QGroupBox("Cam Settings")
        layout = QVBoxLayout(self.cam_group)

        self.cam_center_btn = QPushButton("Select Cam Center")
        self.cam_center_btn.setToolTip("Click on the view to set the cam rotation center")
        self.cam_center_btn.clicked.connect(self.select_cam_center.emit)
        layout.addWidget(self.cam_center_btn)

        self.params_layout.addWidget(self.cam_group)

    def _create_3bar_params(self):
        self.three_bar_group = QGroupBox("3-Bar Linkage Settings")
        layout = QVBoxLayout(self.three_bar_group)

        self.pivot_a_3bar_btn = QPushButton("Select Fixed Pivot A")
        self.pivot_a_3bar_btn.setToolTip("Click on the view to set the fixed pivot point")
        self.pivot_a_3bar_btn.clicked.connect(self.select_pivot_a_3bar.emit)
        layout.addWidget(self.pivot_a_3bar_btn)

        self.params_layout.addWidget(self.three_bar_group)

    def _create_4bar_params(self):
        self.four_bar_group = QGroupBox("4-Bar Linkage Settings")
        layout = QVBoxLayout(self.four_bar_group)

        self.pivot_a_4bar_btn = QPushButton("Select Fixed Pivot A")
        self.pivot_a_4bar_btn.setToolTip("Click on the view to set the first fixed pivot")
        self.pivot_a_4bar_btn.clicked.connect(self.select_pivot_a_4bar.emit)
        layout.addWidget(self.pivot_a_4bar_btn)

        self.pivot_d_4bar_btn = QPushButton("Select Fixed Pivot D")
        self.pivot_d_4bar_btn.setToolTip("Click on the view to set the second fixed pivot")
        self.pivot_d_4bar_btn.clicked.connect(self.select_pivot_d_4bar.emit)
        layout.addWidget(self.pivot_d_4bar_btn)

        self.params_layout.addWidget(self.four_bar_group)

    def _create_gear_params(self):
        self.gear_group = QGroupBox("Gear Settings")
        layout = QFormLayout(self.gear_group)

        button_layout = QHBoxLayout()
        self.driver_center_btn = QPushButton("Driver Center")
        self.driver_center_btn.setToolTip("Click to set driver gear center")
        self.driver_center_btn.clicked.connect(self.select_driver_center.emit)

        self.driven_center_btn = QPushButton("Driven Center")
        self.driven_center_btn.setToolTip("Click to set driven gear center")
        self.driven_center_btn.clicked.connect(self.select_driven_center.emit)

        button_layout.addWidget(self.driver_center_btn)
        button_layout.addWidget(self.driven_center_btn)
        layout.addRow("Select Centers:", button_layout)

        self.gear_ratio_spin = QDoubleSpinBox()
        self.gear_ratio_spin.setRange(0.01, 100.0)
        self.gear_ratio_spin.setSingleStep(0.1)
        self.gear_ratio_spin.setValue(1.0)
        self.gear_ratio_spin.setToolTip("Set gear ratio (Driven Radius / Driver Radius)")
        self.gear_ratio_spin.valueChanged.connect(self.gear_ratio_changed.emit)
        layout.addRow("Gear Ratio:", self.gear_ratio_spin)

        self.params_layout.addWidget(self.gear_group)

    def _on_type_changed(self, mechanism_type: str):
        """Handle mechanism type change."""
        # Hide all groups
        self.cam_group.hide()
        self.three_bar_group.hide()
        self.four_bar_group.hide()
        self.gear_group.hide()

        # Show relevant group
        if mechanism_type == MECHANISM_TYPE_USER_DISPLAY_CAM:
            self.cam_group.show()
        elif mechanism_type == MECHANISM_TYPE_USER_DISPLAY_3_BAR:
            self.three_bar_group.show()
        elif mechanism_type == MECHANISM_TYPE_USER_DISPLAY_4_BAR:
            self.four_bar_group.show()

        self.mechanism_type_changed.emit(mechanism_type)

    def get_current_type(self) -> str:
        """Get currently selected mechanism type."""
        return self.type_combo.currentText()

    def set_mechanism_type(self, type_name: str):
        """Set the mechanism type programmatically."""
        index = self.type_combo.findText(type_name)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)


class SimulationControlPanel(QGroupBox):
    """Panel for simulation controls."""

    play_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    reset_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("5 Simulation Controls", parent)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setCheckable(True)
        self.play_btn.setToolTip("Play mechanism simulation")
        self.play_btn.clicked.connect(self.play_clicked.emit)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setToolTip("Stop mechanism simulation")
        self.stop_btn.clicked.connect(self.stop_clicked.emit)

        self.reset_btn = QPushButton("↺ Reset")
        self.reset_btn.setToolTip("Reset mechanism to initial state")
        self.reset_btn.clicked.connect(self.reset_clicked.emit)

        layout.addWidget(self.play_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.reset_btn)

    def update_button_states(self, is_playing: bool, has_mechanisms: bool):
        """Update button enabled states."""
        self.play_btn.setEnabled(has_mechanisms and not is_playing)
        self.play_btn.setChecked(is_playing)
        self.stop_btn.setEnabled(is_playing)
        self.reset_btn.setEnabled(has_mechanisms and not is_playing)


class MechanismListPanel(QGroupBox):
    """Panel for listing generated mechanisms."""

    mechanism_selected = pyqtSignal(int)  # index
    show_requested = pyqtSignal(int)
    hide_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__("6 Generated Mechanisms", parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.mechanisms_list = QListWidget()
        self.mechanisms_list.setToolTip("List of generated mechanisms")
        self.mechanisms_list.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self.mechanisms_list)

        # Control buttons
        button_layout = QHBoxLayout()

        self.show_btn = QPushButton("Show")
        self.show_btn.clicked.connect(self._on_show_clicked)
        self.show_btn.setEnabled(False)

        self.hide_btn = QPushButton("Hide")
        self.hide_btn.clicked.connect(self._on_hide_clicked)
        self.hide_btn.setEnabled(False)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.delete_btn.setEnabled(False)

        button_layout.addWidget(self.show_btn)
        button_layout.addWidget(self.hide_btn)
        button_layout.addWidget(self.delete_btn)
        layout.addLayout(button_layout)

    def _on_selection_changed(self, current_row: int):
        has_selection = current_row >= 0
        self.show_btn.setEnabled(has_selection)
        self.hide_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

        if has_selection:
            self.mechanism_selected.emit(current_row)

    def _on_show_clicked(self):
        row = self.mechanisms_list.currentRow()
        if row >= 0:
            self.show_requested.emit(row)

    def _on_hide_clicked(self):
        row = self.mechanisms_list.currentRow()
        if row >= 0:
            self.hide_requested.emit(row)

    def _on_delete_clicked(self):
        row = self.mechanisms_list.currentRow()
        if row >= 0:
            self.delete_requested.emit(row)

    def add_mechanism(self, mechanism_type: str, part_name: str):
        """Add a mechanism to the list."""
        item_text = f"{mechanism_type} - {part_name}"
        self.mechanisms_list.addItem(item_text)

    def remove_mechanism(self, index: int):
        """Remove a mechanism from the list."""
        if 0 <= index < self.mechanisms_list.count():
            self.mechanisms_list.takeItem(index)

    def clear(self):
        """Clear the mechanism list."""
        self.mechanisms_list.clear()