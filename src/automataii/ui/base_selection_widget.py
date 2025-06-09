"""Widget for selecting and configuring automata base types."""

from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QRadioButton, QSpinBox, QDoubleSpinBox, QLabel,
    QPushButton, QComboBox, QStackedWidget, QFormLayout
)
from PyQt6.QtCore import pyqtSignal, Qt


class BaseSelectionWidget(QWidget):
    """Widget for selecting and configuring automata base."""
    
    # Signals
    base_changed = pyqtSignal(dict)  # Emitted when base configuration changes
    preview_requested = pyqtSignal(dict)  # Request preview update
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_config = {}
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # Base type selection
        type_group = QGroupBox("Base Type")
        type_layout = QVBoxLayout()
        
        self.type_buttons = {}
        for base_type in ['rectangular', 'cylindrical', 'custom']:
            btn = QRadioButton(base_type.capitalize())
            btn.toggled.connect(lambda checked, t=base_type: self._on_type_changed(t, checked))
            self.type_buttons[base_type] = btn
            type_layout.addWidget(btn)
            
        self.type_buttons['rectangular'].setChecked(True)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # Configuration stack
        self.config_stack = QStackedWidget()
        
        # Rectangular configuration
        rect_widget = QWidget()
        rect_layout = QFormLayout()
        
        self.rect_width = QSpinBox()
        self.rect_width.setRange(50, 500)
        self.rect_width.setValue(200)
        self.rect_width.setSuffix(" mm")
        self.rect_width.valueChanged.connect(self._update_config)
        rect_layout.addRow("Width:", self.rect_width)
        
        self.rect_depth = QSpinBox()
        self.rect_depth.setRange(50, 500)
        self.rect_depth.setValue(150)
        self.rect_depth.setSuffix(" mm")
        self.rect_depth.valueChanged.connect(self._update_config)
        rect_layout.addRow("Depth:", self.rect_depth)
        
        self.rect_height = QSpinBox()
        self.rect_height.setRange(10, 200)
        self.rect_height.setValue(50)
        self.rect_height.setSuffix(" mm")
        self.rect_height.valueChanged.connect(self._update_config)
        rect_layout.addRow("Height:", self.rect_height)
        
        rect_widget.setLayout(rect_layout)
        self.config_stack.addWidget(rect_widget)
        
        # Cylindrical configuration
        cyl_widget = QWidget()
        cyl_layout = QFormLayout()
        
        self.cyl_radius = QSpinBox()
        self.cyl_radius.setRange(50, 300)
        self.cyl_radius.setValue(100)
        self.cyl_radius.setSuffix(" mm")
        self.cyl_radius.valueChanged.connect(self._update_config)
        cyl_layout.addRow("Radius:", self.cyl_radius)
        
        self.cyl_height = QSpinBox()
        self.cyl_height.setRange(10, 200)
        self.cyl_height.setValue(60)
        self.cyl_height.setSuffix(" mm")
        self.cyl_height.valueChanged.connect(self._update_config)
        cyl_layout.addRow("Height:", self.cyl_height)
        
        cyl_widget.setLayout(cyl_layout)
        self.config_stack.addWidget(cyl_widget)
        
        # Custom configuration
        custom_widget = QWidget()
        custom_layout = QFormLayout()
        
        self.custom_file = QLabel("No file selected")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_custom_file)
        
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.custom_file)
        file_layout.addWidget(browse_btn)
        
        custom_layout.addRow("File:", file_layout)
        
        custom_widget.setLayout(custom_layout)
        self.config_stack.addWidget(custom_widget)
        
        layout.addWidget(self.config_stack)
        
        # Material selection
        material_group = QGroupBox("Material")
        material_layout = QFormLayout()
        
        self.material_combo = QComboBox()
        self.material_combo.addItems([
            "Wood - Plywood",
            "Wood - MDF",
            "Acrylic - Clear",
            "Acrylic - Colored",
            "Metal - Aluminum",
            "3D Print - PLA",
            "3D Print - ABS"
        ])
        self.material_combo.currentTextChanged.connect(self._update_config)
        material_layout.addRow("Type:", self.material_combo)
        
        self.thickness_spin = QDoubleSpinBox()
        self.thickness_spin.setRange(1.0, 20.0)
        self.thickness_spin.setValue(6.0)
        self.thickness_spin.setSuffix(" mm")
        self.thickness_spin.setDecimals(1)
        self.thickness_spin.valueChanged.connect(self._update_config)
        material_layout.addRow("Thickness:", self.thickness_spin)
        
        material_group.setLayout(material_layout)
        layout.addWidget(material_group)
        
        # Preview button
        preview_btn = QPushButton("Update Preview")
        preview_btn.clicked.connect(self._request_preview)
        layout.addWidget(preview_btn)
        
        layout.addStretch()
        
        # Initialize configuration
        self._update_config()
        
    def _on_type_changed(self, base_type: str, checked: bool):
        """Handle base type selection change."""
        if not checked:
            return
            
        # Update stack
        if base_type == 'rectangular':
            self.config_stack.setCurrentIndex(0)
        elif base_type == 'cylindrical':
            self.config_stack.setCurrentIndex(1)
        else:  # custom
            self.config_stack.setCurrentIndex(2)
            
        self._update_config()
        
    def _update_config(self):
        """Update current configuration."""
        # Determine selected type
        base_type = None
        for type_name, btn in self.type_buttons.items():
            if btn.isChecked():
                base_type = type_name
                break
                
        if not base_type:
            return
            
        # Build configuration
        config = {
            'type': base_type,
            'material': self.material_combo.currentText(),
            'thickness': self.thickness_spin.value()
        }
        
        if base_type == 'rectangular':
            config.update({
                'width': self.rect_width.value(),
                'depth': self.rect_depth.value(),
                'height': self.rect_height.value()
            })
        elif base_type == 'cylindrical':
            config.update({
                'radius': self.cyl_radius.value(),
                'height': self.cyl_height.value()
            })
        elif base_type == 'custom':
            config.update({
                'file': self.custom_file.text()
            })
            
        self.current_config = config
        self.base_changed.emit(config)
        
    def _browse_custom_file(self):
        """Browse for custom base file."""
        from PyQt6.QtWidgets import QFileDialog
        
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Custom Base File",
            "",
            "3D Models (*.stl *.obj);;All Files (*.*)"
        )
        
        if filename:
            self.custom_file.setText(filename)
            self._update_config()
            
    def _request_preview(self):
        """Request preview update."""
        self.preview_requested.emit(self.current_config)
        
    def get_configuration(self) -> Dict[str, Any]:
        """Get current base configuration."""
        return self.current_config.copy()
        
    def set_configuration(self, config: Dict[str, Any]):
        """Set base configuration."""
        base_type = config.get('type', 'rectangular')
        
        # Set type
        if base_type in self.type_buttons:
            self.type_buttons[base_type].setChecked(True)
            
        # Set parameters
        if base_type == 'rectangular':
            self.rect_width.setValue(config.get('width', 200))
            self.rect_depth.setValue(config.get('depth', 150))
            self.rect_height.setValue(config.get('height', 50))
        elif base_type == 'cylindrical':
            self.cyl_radius.setValue(config.get('radius', 100))
            self.cyl_height.setValue(config.get('height', 60))
        elif base_type == 'custom':
            self.custom_file.setText(config.get('file', 'No file selected'))
            
        # Set material
        material = config.get('material', 'Wood - Plywood')
        index = self.material_combo.findText(material)
        if index >= 0:
            self.material_combo.setCurrentIndex(index)
            
        self.thickness_spin.setValue(config.get('thickness', 6.0))