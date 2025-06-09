"""
Dimension input widget for automata base designer.
"""

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QSpinBox, QComboBox, QGroupBox, QGridLayout,
        QPushButton, QCheckBox
    )
    from PyQt6.QtCore import pyqtSignal, Qt
except ImportError:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QSpinBox, QComboBox, QGroupBox, QGridLayout,
        QPushButton, QCheckBox
    )
    from PyQt5.QtCore import pyqtSignal, Qt

from automataii.modules.automata_base.models.dimensions import Unit, Dimensions2D, Dimensions3D
from automataii.modules.automata_base.enums.base_types import BaseType


class DimensionInputWidget(QWidget):
    """Widget for inputting base dimensions."""
    
    # Signals
    dimensions_changed = pyqtSignal(object)  # Dimensions2D or Dimensions3D
    unit_changed = pyqtSignal(Unit)
    
    def __init__(self, parent=None):
        """Initialize the dimension input widget."""
        super().__init__(parent)
        self.is_3d = False
        self.maintain_aspect_ratio = False
        self.aspect_ratio = 1.0
        self.current_unit = Unit.MM
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Dimensions")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Dimension inputs
        dim_group = QGroupBox("Base Dimensions")
        dim_layout = QGridLayout()
        
        # Width
        dim_layout.addWidget(QLabel("Width:"), 0, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(10, 10000)
        self.width_spin.setValue(200)
        self.width_spin.setSingleStep(10)
        dim_layout.addWidget(self.width_spin, 0, 1)
        
        # Height/Length
        self.height_label = QLabel("Height:")
        dim_layout.addWidget(self.height_label, 1, 0)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(10, 10000)
        self.height_spin.setValue(150)
        self.height_spin.setSingleStep(10)
        dim_layout.addWidget(self.height_spin, 1, 1)
        
        # Depth (for 3D)
        self.depth_label = QLabel("Depth:")
        dim_layout.addWidget(self.depth_label, 2, 0)
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(10, 10000)
        self.depth_spin.setValue(100)
        self.depth_spin.setSingleStep(10)
        dim_layout.addWidget(self.depth_spin, 2, 1)
        
        # Initially hide depth
        self.depth_label.setVisible(False)
        self.depth_spin.setVisible(False)
        
        # Unit selection
        dim_layout.addWidget(QLabel("Unit:"), 3, 0)
        self.unit_combo = QComboBox()
        for unit in Unit:
            self.unit_combo.addItem(unit.value, unit)
        self.unit_combo.setCurrentIndex(0)  # Default to MM
        dim_layout.addWidget(self.unit_combo, 3, 1)
        
        dim_group.setLayout(dim_layout)
        layout.addWidget(dim_group)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        
        # Maintain aspect ratio
        self.aspect_check = QCheckBox("Maintain aspect ratio")
        self.aspect_check.stateChanged.connect(self._on_aspect_changed)
        options_layout.addWidget(self.aspect_check)
        
        # Common sizes
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Common sizes:"))
        
        self.size_combo = QComboBox()
        self.size_combo.addItem("Custom", None)
        self.size_combo.addItem("Small (100x75)", (100, 75))
        self.size_combo.addItem("Medium (200x150)", (200, 150))
        self.size_combo.addItem("Large (300x200)", (300, 200))
        self.size_combo.addItem("X-Large (400x300)", (400, 300))
        self.size_combo.addItem("Square Small (100x100)", (100, 100))
        self.size_combo.addItem("Square Medium (200x200)", (200, 200))
        self.size_combo.addItem("Square Large (300x300)", (300, 300))
        self.size_combo.currentIndexChanged.connect(self._on_size_selected)
        
        size_layout.addWidget(self.size_combo)
        options_layout.addLayout(size_layout)
        
        # Convert units button
        self.convert_btn = QPushButton("Convert Units")
        self.convert_btn.clicked.connect(self._convert_units)
        options_layout.addWidget(self.convert_btn)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Info display
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("padding: 10px; background-color: #f0f0f0;")
        layout.addWidget(self.info_label)
        
        # Connect signals
        self.width_spin.valueChanged.connect(self._on_dimension_changed)
        self.height_spin.valueChanged.connect(self._on_dimension_changed)
        self.depth_spin.valueChanged.connect(self._on_dimension_changed)
        self.unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        
        # Initial update
        self._update_info()
        
        layout.addStretch()
    
    def set_base_type(self, base_type: BaseType):
        """Update widget based on base type."""
        # Determine if 3D dimensions are needed
        self.is_3d = base_type in [
            BaseType.BOX_OPEN,
            BaseType.BOX_ENCLOSED,
            BaseType.PEDESTAL
        ]
        
        # Update labels based on type
        if base_type == BaseType.FLAT_CIRCULAR:
            self.height_label.setText("Diameter:")
            self.width_spin.setEnabled(True)
            self.height_spin.setEnabled(False)  # Will mirror width
        else:
            self.height_label.setText("Height:" if not self.is_3d else "Length:")
            self.width_spin.setEnabled(True)
            self.height_spin.setEnabled(True)
        
        # Show/hide depth
        self.depth_label.setVisible(self.is_3d)
        self.depth_spin.setVisible(self.is_3d)
        
        # Update common sizes based on type
        self._update_common_sizes(base_type)
    
    def _on_dimension_changed(self):
        """Handle dimension value change."""
        # Maintain aspect ratio if enabled
        if self.maintain_aspect_ratio:
            sender = self.sender()
            if sender == self.width_spin:
                new_height = int(self.width_spin.value() / self.aspect_ratio)
                self.height_spin.blockSignals(True)
                self.height_spin.setValue(new_height)
                self.height_spin.blockSignals(False)
            elif sender == self.height_spin:
                new_width = int(self.height_spin.value() * self.aspect_ratio)
                self.width_spin.blockSignals(True)
                self.width_spin.setValue(new_width)
                self.width_spin.blockSignals(False)
        
        # Emit signal
        dimensions = self.get_dimensions()
        self.dimensions_changed.emit(dimensions)
        self._update_info()
    
    def _on_unit_changed(self, index):
        """Handle unit selection change."""
        unit = self.unit_combo.itemData(index)
        if unit:
            self.current_unit = unit
            self.unit_changed.emit(unit)
            self._update_info()
    
    def _on_aspect_changed(self, state):
        """Handle aspect ratio checkbox change."""
        self.maintain_aspect_ratio = state == Qt.CheckState.Checked.value if hasattr(Qt.CheckState, 'Checked') else state == 2
        
        if self.maintain_aspect_ratio:
            # Calculate current aspect ratio
            self.aspect_ratio = self.width_spin.value() / self.height_spin.value()
    
    def _on_size_selected(self, index):
        """Handle common size selection."""
        size_data = self.size_combo.itemData(index)
        if size_data:
            width, height = size_data
            self.width_spin.setValue(width)
            self.height_spin.setValue(height)
            
            # Also set depth for 3D
            if self.is_3d:
                self.depth_spin.setValue(int(height * 0.8))  # Default depth
    
    def _update_common_sizes(self, base_type: BaseType):
        """Update common sizes based on base type."""
        self.size_combo.clear()
        self.size_combo.addItem("Custom", None)
        
        if base_type == BaseType.FLAT_CIRCULAR:
            # Circular sizes (diameter)
            self.size_combo.addItem("Small (⌀100mm)", (100, 100))
            self.size_combo.addItem("Medium (⌀150mm)", (150, 150))
            self.size_combo.addItem("Large (⌀200mm)", (200, 200))
            self.size_combo.addItem("X-Large (⌀300mm)", (300, 300))
        elif base_type in [BaseType.BOX_OPEN, BaseType.BOX_ENCLOSED]:
            # Box sizes
            self.size_combo.addItem("Small Box (150x100x80)", (150, 100))
            self.size_combo.addItem("Medium Box (250x150x100)", (250, 150))
            self.size_combo.addItem("Large Box (350x200x150)", (350, 200))
            self.size_combo.addItem("Storage Box (400x300x200)", (400, 300))
        elif base_type == BaseType.PEDESTAL:
            # Pedestal sizes
            self.size_combo.addItem("Small Pedestal (100x100)", (100, 100))
            self.size_combo.addItem("Medium Pedestal (150x150)", (150, 150))
            self.size_combo.addItem("Large Pedestal (200x200)", (200, 200))
        else:
            # Default rectangular sizes
            self.size_combo.addItem("Small (100x75)", (100, 75))
            self.size_combo.addItem("Medium (200x150)", (200, 150))
            self.size_combo.addItem("Large (300x200)", (300, 200))
            self.size_combo.addItem("X-Large (400x300)", (400, 300))
    
    def _convert_units(self):
        """Convert current dimensions to different unit."""
        # Get current dimensions
        current_dims = self.get_dimensions()
        
        # Cycle through units
        current_index = self.unit_combo.currentIndex()
        new_index = (current_index + 1) % self.unit_combo.count()
        new_unit = self.unit_combo.itemData(new_index)
        
        # Convert dimensions
        converted_dims = current_dims.to_unit(new_unit)
        
        # Update spinboxes
        self.width_spin.setValue(int(converted_dims.width))
        self.height_spin.setValue(int(converted_dims.height))
        if self.is_3d:
            self.depth_spin.setValue(int(converted_dims.depth))
        
        # Update unit combo
        self.unit_combo.setCurrentIndex(new_index)
    
    def _update_info(self):
        """Update information display."""
        dims = self.get_dimensions()
        
        info_text = "<b>Dimensions Summary</b><br>"
        
        if isinstance(dims, Dimensions2D):
            info_text += f"Area: {dims.area:,.0f} {dims.unit.value}²<br>"
            info_text += f"Perimeter: {dims.perimeter:,.0f} {dims.unit.value}<br>"
            info_text += f"Diagonal: {dims.diagonal:,.1f} {dims.unit.value}"
        else:
            info_text += f"Volume: {dims.volume:,.0f} {dims.unit.value}³<br>"
            info_text += f"Surface Area: {dims.surface_area:,.0f} {dims.unit.value}²<br>"
            info_text += f"Diagonal: {dims.diagonal:,.1f} {dims.unit.value}"
        
        self.info_label.setText(info_text)
    
    def get_dimensions(self):
        """Get current dimensions as Dimensions2D or Dimensions3D object."""
        width = self.width_spin.value()
        height = self.height_spin.value()
        unit = self.current_unit
        
        if self.is_3d:
            depth = self.depth_spin.value()
            return Dimensions3D(width=width, height=height, depth=depth, unit=unit)
        else:
            return Dimensions2D(width=width, height=height, unit=unit)
    
    def set_dimensions(self, dimensions):
        """Set dimensions from Dimensions2D or Dimensions3D object."""
        self.width_spin.setValue(int(dimensions.width))
        self.height_spin.setValue(int(dimensions.height))
        
        if isinstance(dimensions, Dimensions3D):
            self.is_3d = True
            self.depth_label.setVisible(True)
            self.depth_spin.setVisible(True)
            self.depth_spin.setValue(int(dimensions.depth))
        
        # Set unit
        for i in range(self.unit_combo.count()):
            if self.unit_combo.itemData(i) == dimensions.unit:
                self.unit_combo.setCurrentIndex(i)
                break