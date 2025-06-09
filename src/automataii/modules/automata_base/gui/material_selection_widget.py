"""
Material selection widget for automata base designer.
"""

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
        QComboBox, QGroupBox, QSpinBox, QDoubleSpinBox,
        QTableWidget, QTableWidgetItem, QHeaderView
    )
    from PyQt6.QtCore import pyqtSignal, Qt
except ImportError:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QComboBox, QGroupBox, QSpinBox, QDoubleSpinBox,
        QTableWidget, QTableWidgetItem, QHeaderView
    )
    from PyQt5.QtCore import pyqtSignal, Qt

from automataii.modules.automata_base.enums.base_types import MaterialType
from automataii.modules.automata_base.utils.cost_calculator import CostCalculator, MaterialCost


class MaterialSelectionWidget(QWidget):
    """Widget for selecting materials and thickness."""
    
    # Signals
    material_changed = pyqtSignal(MaterialType)
    thickness_changed = pyqtSignal(float)
    
    def __init__(self, parent=None):
        """Initialize the material selection widget."""
        super().__init__(parent)
        self.cost_calculator = CostCalculator()
        self.current_material = None
        self.current_thickness = 10.0
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Material Selection")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Material selection
        material_group = QGroupBox("Primary Material")
        material_layout = QVBoxLayout()
        
        # Material type combo
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Material Type:"))
        
        self.material_combo = QComboBox()
        
        # Group materials by category
        materials = [
            ("--- Organic Materials ---", None),
            ("Wood", MaterialType.WOOD),
            ("Plywood", MaterialType.PLYWOOD),
            ("MDF", MaterialType.MDF),
            ("Cardboard", MaterialType.CARDBOARD),
            ("--- Metals ---", None),
            ("Aluminum", MaterialType.ALUMINUM),
            ("Steel", MaterialType.STEEL),
            ("--- Plastics ---", None),
            ("Acrylic", MaterialType.ACRYLIC),
            ("3D Printed (PLA)", MaterialType.PLASTIC_3D_PRINTED),
            ("3D Printed (Resin)", MaterialType.RESIN_3D_PRINTED),
        ]
        
        for label, material in materials:
            if material is None:
                # Separator
                self.material_combo.addItem(label)
                item_index = self.material_combo.count() - 1
                self.material_combo.model().item(item_index).setEnabled(False)
            else:
                self.material_combo.addItem(label, material)
        
        # Set default to wood
        for i in range(self.material_combo.count()):
            if self.material_combo.itemData(i) == MaterialType.WOOD:
                self.material_combo.setCurrentIndex(i)
                break
        
        type_layout.addWidget(self.material_combo)
        material_layout.addLayout(type_layout)
        
        # Thickness input
        thickness_layout = QHBoxLayout()
        thickness_layout.addWidget(QLabel("Material Thickness:"))
        
        self.thickness_spin = QDoubleSpinBox()
        self.thickness_spin.setRange(0.5, 100.0)
        self.thickness_spin.setValue(10.0)
        self.thickness_spin.setSingleStep(0.5)
        self.thickness_spin.setSuffix(" mm")
        thickness_layout.addWidget(self.thickness_spin)
        
        material_layout.addLayout(thickness_layout)
        
        # Material properties display
        self.properties_table = QTableWidget()
        self.properties_table.setColumnCount(2)
        self.properties_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.properties_table.horizontalHeader().setStretchLastSection(True)
        self.properties_table.verticalHeader().setVisible(False)
        self.properties_table.setMaximumHeight(150)
        
        material_layout.addWidget(QLabel("Material Properties:"))
        material_layout.addWidget(self.properties_table)
        
        material_group.setLayout(material_layout)
        layout.addWidget(material_group)
        
        # Cost estimation
        cost_group = QGroupBox("Cost Estimation")
        cost_layout = QVBoxLayout()
        
        self.cost_label = QLabel("Select material and dimensions to see cost estimate")
        self.cost_label.setWordWrap(True)
        self.cost_label.setStyleSheet("padding: 10px; background-color: #f0f0f0;")
        cost_layout.addWidget(self.cost_label)
        
        cost_group.setLayout(cost_layout)
        layout.addWidget(cost_group)
        
        # Connect signals
        self.material_combo.currentIndexChanged.connect(self._on_material_changed)
        self.thickness_spin.valueChanged.connect(self._on_thickness_changed)
        
        # Trigger initial update
        self._on_material_changed(self.material_combo.currentIndex())
        
        layout.addStretch()
    
    def _on_material_changed(self, index):
        """Handle material selection change."""
        material = self.material_combo.itemData(index)
        
        if material is not None:
            self.current_material = material
            self.material_changed.emit(material)
            self._update_properties_display()
            self._update_thickness_range()
    
    def _on_thickness_changed(self, value):
        """Handle thickness change."""
        self.current_thickness = value
        self.thickness_changed.emit(value)
    
    def _update_properties_display(self):
        """Update the material properties display."""
        if not self.current_material:
            return
        
        # Get material properties
        properties = MaterialType.get_properties(self.current_material)
        
        # Clear table
        self.properties_table.setRowCount(0)
        
        # Add properties
        property_items = [
            ("Category", properties.get("category", "N/A")),
            ("Workability", properties.get("workability", "N/A")),
            ("Durability", properties.get("durability", "N/A")),
            ("Cost Level", properties.get("cost", "N/A")),
            ("Weight", properties.get("weight", "N/A")),
        ]
        
        # Add density if available
        if self.current_material in self.cost_calculator.prices:
            cost_info = self.cost_calculator.prices[self.current_material]
            if cost_info.density:
                property_items.append(("Density", f"{cost_info.density} kg/m³"))
        
        for prop, value in property_items:
            row = self.properties_table.rowCount()
            self.properties_table.insertRow(row)
            self.properties_table.setItem(row, 0, QTableWidgetItem(prop))
            self.properties_table.setItem(row, 1, QTableWidgetItem(str(value)))
        
        # Resize to content
        self.properties_table.resizeRowsToContents()
    
    def _update_thickness_range(self):
        """Update thickness range based on material."""
        if not self.current_material:
            return
        
        # Set reasonable thickness ranges for different materials
        thickness_ranges = {
            MaterialType.CARDBOARD: (1.0, 10.0, 3.0),
            MaterialType.ACRYLIC: (2.0, 20.0, 5.0),
            MaterialType.ALUMINUM: (1.0, 50.0, 3.0),
            MaterialType.STEEL: (1.0, 50.0, 5.0),
            MaterialType.WOOD: (5.0, 100.0, 15.0),
            MaterialType.PLYWOOD: (3.0, 50.0, 12.0),
            MaterialType.MDF: (3.0, 50.0, 10.0),
            MaterialType.PLASTIC_3D_PRINTED: (2.0, 50.0, 10.0),
            MaterialType.RESIN_3D_PRINTED: (2.0, 30.0, 5.0),
        }
        
        if self.current_material in thickness_ranges:
            min_t, max_t, default_t = thickness_ranges[self.current_material]
            self.thickness_spin.setRange(min_t, max_t)
            self.thickness_spin.setValue(default_t)
    
    def update_cost_estimate(self, base_config):
        """Update cost estimate based on current configuration."""
        if not base_config or not self.current_material:
            return
        
        try:
            # Calculate cost
            costs = self.cost_calculator.calculate_material_cost(base_config)
            
            # Format cost display
            cost_text = f"<b>Material Cost Estimate</b><br>"
            cost_text += f"Material: ${costs['material_cost']:.2f}<br>"
            
            if costs['fastener_cost'] > 0:
                cost_text += f"Fasteners: ${costs['fastener_cost']:.2f}<br>"
            
            if costs['finish_cost'] > 0:
                cost_text += f"Finish: ${costs['finish_cost']:.2f}<br>"
            
            cost_text += f"<br><b>Total: ${costs['subtotal']:.2f}</b><br>"
            cost_text += f"<small>({costs['price_per_unit']} {costs['price_unit']})</small>"
            
            self.cost_label.setText(cost_text)
            
        except Exception as e:
            self.cost_label.setText(f"Cost calculation error: {str(e)}")
    
    def get_selected_material(self) -> MaterialType:
        """Get currently selected material."""
        return self.current_material
    
    def get_thickness(self) -> float:
        """Get current thickness value."""
        return self.current_thickness
    
    def set_material(self, material: MaterialType):
        """Set the material selection."""
        for i in range(self.material_combo.count()):
            if self.material_combo.itemData(i) == material:
                self.material_combo.setCurrentIndex(i)
                break
    
    def set_thickness(self, thickness: float):
        """Set the thickness value."""
        self.thickness_spin.setValue(thickness)