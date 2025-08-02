"""
Visualization options panel for mechanism dictionary.
Controls visual feedback settings for physics simulation.
"""

import logging
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QCheckBox, 
    QSlider, QLabel, QHBoxLayout, QPushButton
)
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class VisualizationPanel(QWidget):
    """Panel for controlling mechanism visualization options."""
    
    # Signals
    show_forces_changed = pyqtSignal(bool)
    show_velocity_changed = pyqtSignal(bool)
    show_constraints_changed = pyqtSignal(bool)
    show_grid_changed = pyqtSignal(bool)
    show_dimensions_changed = pyqtSignal(bool)
    force_scale_changed = pyqtSignal(float)
    velocity_scale_changed = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("Visualization Options")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Display options group
        display_group = QGroupBox("Display")
        display_layout = QVBoxLayout(display_group)
        
        # Checkboxes for display options
        self.show_forces_cb = QCheckBox("Show Forces")
        self.show_forces_cb.setChecked(True)
        self.show_forces_cb.toggled.connect(self.show_forces_changed)
        display_layout.addWidget(self.show_forces_cb)
        
        self.show_velocity_cb = QCheckBox("Show Velocity Vectors")
        self.show_velocity_cb.setChecked(True)
        self.show_velocity_cb.toggled.connect(self.show_velocity_changed)
        display_layout.addWidget(self.show_velocity_cb)
        
        self.show_constraints_cb = QCheckBox("Show Constraints")
        self.show_constraints_cb.setChecked(True)
        self.show_constraints_cb.toggled.connect(self.show_constraints_changed)
        display_layout.addWidget(self.show_constraints_cb)
        
        self.show_grid_cb = QCheckBox("Show Grid")
        self.show_grid_cb.setChecked(True)
        self.show_grid_cb.toggled.connect(self.show_grid_changed)
        display_layout.addWidget(self.show_grid_cb)
        
        self.show_dimensions_cb = QCheckBox("Show Dimensions")
        self.show_dimensions_cb.setChecked(True)
        self.show_dimensions_cb.toggled.connect(self.show_dimensions_changed)
        display_layout.addWidget(self.show_dimensions_cb)
        
        layout.addWidget(display_group)
        
        # Scale controls group
        scale_group = QGroupBox("Vector Scales")
        scale_layout = QVBoxLayout(scale_group)
        
        # Force scale slider
        force_layout = QHBoxLayout()
        force_layout.addWidget(QLabel("Force:"))
        self.force_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.force_scale_slider.setRange(10, 200)  # 0.1x to 2.0x
        self.force_scale_slider.setValue(50)  # 0.5x default
        self.force_scale_slider.valueChanged.connect(
            lambda v: self.force_scale_changed.emit(v / 100.0)
        )
        force_layout.addWidget(self.force_scale_slider)
        self.force_scale_label = QLabel("0.5x")
        force_layout.addWidget(self.force_scale_label)
        self.force_scale_slider.valueChanged.connect(
            lambda v: self.force_scale_label.setText(f"{v/100:.1f}x")
        )
        scale_layout.addLayout(force_layout)
        
        # Velocity scale slider
        velocity_layout = QHBoxLayout()
        velocity_layout.addWidget(QLabel("Velocity:"))
        self.velocity_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.velocity_scale_slider.setRange(10, 200)  # 0.1x to 2.0x
        self.velocity_scale_slider.setValue(100)  # 1.0x default
        self.velocity_scale_slider.valueChanged.connect(
            lambda v: self.velocity_scale_changed.emit(v / 100.0)
        )
        velocity_layout.addWidget(self.velocity_scale_slider)
        self.velocity_scale_label = QLabel("1.0x")
        velocity_layout.addWidget(self.velocity_scale_label)
        self.velocity_scale_slider.valueChanged.connect(
            lambda v: self.velocity_scale_label.setText(f"{v/100:.1f}x")
        )
        scale_layout.addLayout(velocity_layout)
        
        layout.addWidget(scale_group)
        
        # Analysis button
        self.analysis_btn = QPushButton("Show Detailed Analysis")
        self.analysis_btn.setCheckable(True)
        layout.addWidget(self.analysis_btn)
        
        # Add stretch to push everything to top
        layout.addStretch()
    
    def get_settings(self) -> dict:
        """Get current visualization settings."""
        return {
            'show_forces': self.show_forces_cb.isChecked(),
            'show_velocity': self.show_velocity_cb.isChecked(),
            'show_constraints': self.show_constraints_cb.isChecked(),
            'show_grid': self.show_grid_cb.isChecked(),
            'show_dimensions': self.show_dimensions_cb.isChecked(),
            'force_scale': self.force_scale_slider.value() / 100.0,
            'velocity_scale': self.velocity_scale_slider.value() / 100.0,
        }