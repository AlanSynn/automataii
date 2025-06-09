"""
Standalone PyQt6 demo application for the Automataii automata base system.

This demo showcases the complete workflow from base selection to export,
with interactive UI elements and real-time preview.
"""

import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QTextEdit, QFileDialog, QMessageBox, QTabWidget,
    QListWidget, QSplitter, QCheckBox, QSlider, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QPalette, QColor

# Automata base imports
from automataii.modules.automata_base import (
    BaseType, MaterialType, MountingType, AssemblyMethod,
    BaseConfiguration, Dimensions2D, Dimensions3D, Unit,
    MountingPoint, Point2D, get_base_specification, list_specifications
)
from automataii.modules.automata_base.utils import validate_base_configuration, base_to_svg

# Generator and integration imports
from automataii.generators import GeneratorConfig, StructuredGenerator
from automataii.integration import MechanismAdapter, ExportManager
from automataii.generation import LinkageMechanism, CamMechanism, GearMechanism


@dataclass
class AppState:
    """Application state management."""
    current_base: Optional[BaseConfiguration] = None
    mechanisms: List[Any] = None
    adapter: Optional[MechanismAdapter] = None
    export_manager: Optional[ExportManager] = None
    
    def __post_init__(self):
        if self.mechanisms is None:
            self.mechanisms = []
        if self.adapter is None:
            self.adapter = MechanismAdapter()
        if self.export_manager is None:
            self.export_manager = ExportManager()


class DemoMainWindow(QMainWindow):
    """Main window for the automata base demo application."""
    
    def __init__(self):
        super().__init__()
        self.state = AppState()
        self.init_ui()
        self.apply_theme()
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Automataii Base System Demo")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Main content area with tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_base_tab(), "Base Configuration")
        self.tabs.addTab(self.create_mechanism_tab(), "Mechanisms")
        self.tabs.addTab(self.create_preview_tab(), "Preview")
        self.tabs.addTab(self.create_export_tab(), "Export")
        
        main_layout.addWidget(self.tabs)
        
        # Status bar
        self.status_label = QLabel("Ready")
        self.statusBar().addWidget(self.status_label)
        
    def create_header(self) -> QWidget:
        """Create application header."""
        header = QWidget()
        header.setMaximumHeight(80)
        
        layout = QHBoxLayout(header)
        
        # Title
        title = QLabel("Automataii Base System Demo")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Action buttons
        new_btn = QPushButton("New Project")
        new_btn.clicked.connect(self.new_project)
        layout.addWidget(new_btn)
        
        load_btn = QPushButton("Load Project")
        load_btn.clicked.connect(self.load_project)
        layout.addWidget(load_btn)
        
        save_btn = QPushButton("Save Project")
        save_btn.clicked.connect(self.save_project)
        layout.addWidget(save_btn)
        
        return header
        
    def create_base_tab(self) -> QWidget:
        """Create base configuration tab."""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # Left panel - Configuration
        config_panel = QGroupBox("Base Configuration")
        config_layout = QVBoxLayout(config_panel)
        
        # Base type selection
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Base Type:"))
        self.base_type_combo = QComboBox()
        self.base_type_combo.addItems([
            "Flat Rectangular", "Flat Circular", "Box Enclosed",
            "Box Open", "Pedestal", "Wall Mounted", "Custom"
        ])
        self.base_type_combo.currentTextChanged.connect(self.on_base_type_changed)
        type_layout.addWidget(self.base_type_combo)
        config_layout.addLayout(type_layout)
        
        # Dimensions
        dim_group = QGroupBox("Dimensions")
        dim_layout = QGridLayout(dim_group)
        
        self.width_spin = QSpinBox()
        self.width_spin.setRange(50, 1000)
        self.width_spin.setValue(300)
        self.width_spin.setSuffix(" mm")
        dim_layout.addWidget(QLabel("Width:"), 0, 0)
        dim_layout.addWidget(self.width_spin, 0, 1)
        
        self.height_spin = QSpinBox()
        self.height_spin.setRange(50, 1000)
        self.height_spin.setValue(200)
        self.height_spin.setSuffix(" mm")
        dim_layout.addWidget(QLabel("Height:"), 1, 0)
        dim_layout.addWidget(self.height_spin, 1, 1)
        
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(50, 1000)
        self.depth_spin.setValue(250)
        self.depth_spin.setSuffix(" mm")
        dim_layout.addWidget(QLabel("Depth:"), 2, 0)
        dim_layout.addWidget(self.depth_spin, 2, 1)
        
        config_layout.addWidget(dim_group)
        
        # Material selection
        mat_layout = QHBoxLayout()
        mat_layout.addWidget(QLabel("Material:"))
        self.material_combo = QComboBox()
        self.material_combo.addItems([
            "Wood", "MDF", "Plywood", "Acrylic", "Aluminum",
            "3D Printed", "Cardboard"
        ])
        mat_layout.addWidget(self.material_combo)
        config_layout.addLayout(mat_layout)
        
        # Material thickness
        thick_layout = QHBoxLayout()
        thick_layout.addWidget(QLabel("Thickness:"))
        self.thickness_spin = QDoubleSpinBox()
        self.thickness_spin.setRange(1.0, 50.0)
        self.thickness_spin.setValue(6.0)
        self.thickness_spin.setSuffix(" mm")
        thick_layout.addWidget(self.thickness_spin)
        config_layout.addLayout(thick_layout)
        
        # Create base button
        self.create_base_btn = QPushButton("Create Base")
        self.create_base_btn.clicked.connect(self.create_base)
        config_layout.addWidget(self.create_base_btn)
        
        config_layout.addStretch()
        
        # Right panel - Info and preview
        info_panel = QGroupBox("Base Information")
        info_layout = QVBoxLayout(info_panel)
        
        self.base_info_text = QTextEdit()
        self.base_info_text.setReadOnly(True)
        info_layout.addWidget(self.base_info_text)
        
        # Layout panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(config_panel)
        splitter.addWidget(info_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter)
        
        return tab
        
    def create_mechanism_tab(self) -> QWidget:
        """Create mechanism configuration tab."""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # Left panel - Add mechanisms
        add_panel = QGroupBox("Add Mechanisms")
        add_layout = QVBoxLayout(add_panel)
        
        # Mechanism type selection
        self.mech_type_combo = QComboBox()
        self.mech_type_combo.addItems([
            "Four-Bar Linkage", "Cam Follower", "Gear Train"
        ])
        add_layout.addWidget(QLabel("Mechanism Type:"))
        add_layout.addWidget(self.mech_type_combo)
        
        # Mechanism parameters (simplified)
        params_group = QGroupBox("Parameters")
        self.params_layout = QVBoxLayout(params_group)
        self.update_mechanism_params()
        add_layout.addWidget(params_group)
        
        # Add mechanism button
        add_mech_btn = QPushButton("Add Mechanism")
        add_mech_btn.clicked.connect(self.add_mechanism)
        add_layout.addWidget(add_mech_btn)
        
        add_layout.addStretch()
        
        # Right panel - Mechanism list
        list_panel = QGroupBox("Current Mechanisms")
        list_layout = QVBoxLayout(list_panel)
        
        self.mechanism_list = QListWidget()
        list_layout.addWidget(self.mechanism_list)
        
        # Mechanism controls
        controls_layout = QHBoxLayout()
        
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_mechanism)
        controls_layout.addWidget(remove_btn)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_mechanisms)
        controls_layout.addWidget(clear_btn)
        
        list_layout.addLayout(controls_layout)
        
        # Layout panels
        layout.addWidget(add_panel, 1)
        layout.addWidget(list_panel, 2)
        
        return tab
        
    def create_preview_tab(self) -> QWidget:
        """Create preview tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Preview controls
        controls = QGroupBox("Preview Controls")
        controls_layout = QHBoxLayout(controls)
        
        self.show_dimensions_cb = QCheckBox("Show Dimensions")
        self.show_dimensions_cb.setChecked(True)
        controls_layout.addWidget(self.show_dimensions_cb)
        
        self.show_mounting_cb = QCheckBox("Show Mounting Points")
        self.show_mounting_cb.setChecked(True)
        controls_layout.addWidget(self.show_mounting_cb)
        
        controls_layout.addWidget(QLabel("Scale:"))
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(50, 200)
        self.scale_slider.setValue(100)
        self.scale_label = QLabel("100%")
        self.scale_slider.valueChanged.connect(
            lambda v: self.scale_label.setText(f"{v}%")
        )
        controls_layout.addWidget(self.scale_slider)
        controls_layout.addWidget(self.scale_label)
        
        update_btn = QPushButton("Update Preview")
        update_btn.clicked.connect(self.update_preview)
        controls_layout.addWidget(update_btn)
        
        controls_layout.addStretch()
        layout.addWidget(controls)
        
        # Preview display
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        layout.addWidget(self.preview_text)
        
        return tab
        
    def create_export_tab(self) -> QWidget:
        """Create export tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Export options
        options_group = QGroupBox("Export Options")
        options_layout = QVBoxLayout(options_group)
        
        # Format selection
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Export Format:"))
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["SVG", "DXF", "JSON", "Complete Package"])
        format_layout.addWidget(self.export_format_combo)
        options_layout.addLayout(format_layout)
        
        # Export options checkboxes
        self.include_assembly_cb = QCheckBox("Include Assembly Instructions")
        self.include_assembly_cb.setChecked(True)
        options_layout.addWidget(self.include_assembly_cb)
        
        self.include_bom_cb = QCheckBox("Include Bill of Materials")
        self.include_bom_cb.setChecked(True)
        options_layout.addWidget(self.include_bom_cb)
        
        # Export button
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self.export_project)
        options_layout.addWidget(export_btn)
        
        layout.addWidget(options_group)
        
        # Export log
        log_group = QGroupBox("Export Log")
        log_layout = QVBoxLayout(log_group)
        
        self.export_log = QTextEdit()
        self.export_log.setReadOnly(True)
        log_layout.addWidget(self.export_log)
        
        layout.addWidget(log_group)
        
        return tab
        
    def apply_theme(self):
        """Apply dark theme to the application."""
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.black)
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        
        self.setPalette(dark_palette)
        
    # Event handlers
    def on_base_type_changed(self, base_type: str):
        """Handle base type selection change."""
        # Enable/disable depth based on type
        needs_depth = base_type in ["Box Enclosed", "Box Open", "Pedestal"]
        self.depth_spin.setEnabled(needs_depth)
        
    def create_base(self):
        """Create base configuration from UI inputs."""
        try:
            # Map UI values to enums
            base_type_map = {
                "Flat Rectangular": BaseType.FLAT_RECTANGULAR,
                "Flat Circular": BaseType.FLAT_CIRCULAR,
                "Box Enclosed": BaseType.BOX_ENCLOSED,
                "Box Open": BaseType.BOX_OPEN,
                "Pedestal": BaseType.PEDESTAL,
                "Wall Mounted": BaseType.WALL_MOUNTED,
                "Custom": BaseType.CUSTOM
            }
            
            material_map = {
                "Wood": MaterialType.WOOD,
                "MDF": MaterialType.MDF,
                "Plywood": MaterialType.PLYWOOD,
                "Acrylic": MaterialType.ACRYLIC,
                "Aluminum": MaterialType.ALUMINUM,
                "3D Printed": MaterialType.PLASTIC_3D_PRINTED,
                "Cardboard": MaterialType.CARDBOARD
            }
            
            base_type = base_type_map[self.base_type_combo.currentText()]
            material = material_map[self.material_combo.currentText()]
            
            # Create dimensions based on type
            if base_type in [BaseType.FLAT_RECTANGULAR, BaseType.FLAT_CIRCULAR, BaseType.WALL_MOUNTED]:
                dimensions = Dimensions2D(
                    width=self.width_spin.value(),
                    height=self.height_spin.value(),
                    unit=Unit.MM
                )
            else:
                dimensions = Dimensions3D(
                    width=self.width_spin.value(),
                    height=self.height_spin.value(),
                    depth=self.depth_spin.value(),
                    unit=Unit.MM
                )
            
            # Create base configuration
            self.state.current_base = BaseConfiguration(
                name=f"Demo {base_type.value} Base",
                base_type=base_type,
                dimensions=dimensions,
                primary_material=material,
                material_thickness=self.thickness_spin.value(),
                mounting_type=MountingType.WALL if base_type == BaseType.WALL_MOUNTED else MountingType.FREESTANDING
            )
            
            # Validate
            issues = validate_base_configuration(self.state.current_base)
            
            if issues:
                QMessageBox.warning(self, "Validation Issues", "\n".join(issues))
            else:
                self.update_base_info()
                self.status_label.setText("Base created successfully")
                QMessageBox.information(self, "Success", "Base configuration created!")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create base: {str(e)}")
            
    def update_base_info(self):
        """Update base information display."""
        if not self.state.current_base:
            self.base_info_text.setText("No base configured")
            return
            
        base = self.state.current_base
        info = f"""Base Configuration:
Name: {base.name}
Type: {base.base_type.value}
Dimensions: {base.dimensions}
Material: {base.primary_material.value}
Thickness: {base.material_thickness} mm
Mounting Type: {base.mounting_type.value if base.mounting_type else 'None'}
Assembly Method: {base.assembly_method.value if base.assembly_method else 'None'}

Mounting Points: {len(base.mounting_points)}
Weight: {base.weight if base.weight else 'Not specified'} kg
Max Load: {base.max_load if base.max_load else 'Not specified'} kg
"""
        self.base_info_text.setText(info)
        
    def update_mechanism_params(self):
        """Update mechanism parameter inputs based on selected type."""
        # Clear existing widgets
        while self.params_layout.count():
            widget = self.params_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()
                
        # Add parameters based on mechanism type
        mech_type = self.mech_type_combo.currentText()
        
        if mech_type == "Four-Bar Linkage":
            self.crank_length_spin = QSpinBox()
            self.crank_length_spin.setRange(10, 200)
            self.crank_length_spin.setValue(50)
            self.crank_length_spin.setSuffix(" mm")
            self.params_layout.addWidget(QLabel("Crank Length:"))
            self.params_layout.addWidget(self.crank_length_spin)
            
        elif mech_type == "Cam Follower":
            self.cam_radius_spin = QSpinBox()
            self.cam_radius_spin.setRange(10, 100)
            self.cam_radius_spin.setValue(40)
            self.cam_radius_spin.setSuffix(" mm")
            self.params_layout.addWidget(QLabel("Cam Radius:"))
            self.params_layout.addWidget(self.cam_radius_spin)
            
        elif mech_type == "Gear Train":
            self.driver_teeth_spin = QSpinBox()
            self.driver_teeth_spin.setRange(10, 100)
            self.driver_teeth_spin.setValue(20)
            self.params_layout.addWidget(QLabel("Driver Teeth:"))
            self.params_layout.addWidget(self.driver_teeth_spin)
            
            self.driven_teeth_spin = QSpinBox()
            self.driven_teeth_spin.setRange(10, 100)
            self.driven_teeth_spin.setValue(60)
            self.params_layout.addWidget(QLabel("Driven Teeth:"))
            self.params_layout.addWidget(self.driven_teeth_spin)
            
    def add_mechanism(self):
        """Add mechanism to the project."""
        if not self.state.current_base:
            QMessageBox.warning(self, "No Base", "Please create a base first")
            return
            
        try:
            mech_type = self.mech_type_combo.currentText()
            mech_id = f"mech_{len(self.state.mechanisms) + 1}"
            
            if mech_type == "Four-Bar Linkage":
                mechanism = LinkageMechanism(
                    id=mech_id,
                    name=f"Linkage {len(self.state.mechanisms) + 1}",
                    crank_length=self.crank_length_spin.value()
                )
            elif mech_type == "Cam Follower":
                mechanism = CamMechanism(
                    id=mech_id,
                    name=f"Cam {len(self.state.mechanisms) + 1}",
                    cam_radius=self.cam_radius_spin.value()
                )
            elif mech_type == "Gear Train":
                mechanism = GearMechanism(
                    id=mech_id,
                    name=f"Gear {len(self.state.mechanisms) + 1}",
                    driver_teeth=self.driver_teeth_spin.value(),
                    driven_teeth=self.driven_teeth_spin.value()
                )
            else:
                return
                
            self.state.mechanisms.append(mechanism)
            self.state.adapter.add_mechanism(
                mechanism, 
                self.state.current_base.base_type.value
            )
            
            self.mechanism_list.addItem(f"{mechanism.name} ({mech_type})")
            self.status_label.setText(f"Added {mechanism.name}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add mechanism: {str(e)}")
            
    def remove_mechanism(self):
        """Remove selected mechanism."""
        current_row = self.mechanism_list.currentRow()
        if current_row >= 0:
            self.mechanism_list.takeItem(current_row)
            removed = self.state.mechanisms.pop(current_row)
            del self.state.adapter.placements[removed.id]
            self.status_label.setText(f"Removed {removed.name}")
            
    def clear_mechanisms(self):
        """Clear all mechanisms."""
        self.mechanism_list.clear()
        self.state.mechanisms.clear()
        self.state.adapter.placements.clear()
        self.status_label.setText("Cleared all mechanisms")
        
    def update_preview(self):
        """Update preview display."""
        if not self.state.current_base:
            self.preview_text.setText("No base to preview")
            return
            
        try:
            # Generate SVG preview
            svg_content = base_to_svg(
                self.state.current_base,
                show_mounting_points=self.show_mounting_cb.isChecked(),
                show_dimensions=self.show_dimensions_cb.isChecked(),
                scale=self.scale_slider.value() / 100.0
            )
            
            # Display SVG content (in real app, would render it)
            preview_info = f"""Preview Generated:
Base: {self.state.current_base.name}
Scale: {self.scale_slider.value()}%
Show Dimensions: {self.show_dimensions_cb.isChecked()}
Show Mounting Points: {self.show_mounting_cb.isChecked()}

Mechanisms: {len(self.state.mechanisms)}
{chr(10).join([f"- {m.name}" for m in self.state.mechanisms])}

SVG Size: {len(svg_content)} characters

(In a real application, this would render the SVG visually)
"""
            self.preview_text.setText(preview_info)
            
        except Exception as e:
            self.preview_text.setText(f"Preview failed: {str(e)}")
            
    def export_project(self):
        """Export the project."""
        if not self.state.current_base:
            QMessageBox.warning(self, "No Base", "Please create a base first")
            return
            
        export_format = self.export_format_combo.currentText()
        
        # Get save location
        if export_format == "Complete Package":
            folder = QFileDialog.getExistingDirectory(self, "Select Export Folder")
            if not folder:
                return
        else:
            file_filter = {
                "SVG": "SVG Files (*.svg)",
                "DXF": "DXF Files (*.dxf)",
                "JSON": "JSON Files (*.json)"
            }.get(export_format, "All Files (*)")
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save File", "", file_filter
            )
            if not file_path:
                return
                
        try:
            self.export_log.append(f"\n--- Export Started ({export_format}) ---")
            
            if export_format == "SVG":
                svg_content = base_to_svg(self.state.current_base)
                with open(file_path, 'w') as f:
                    f.write(svg_content)
                self.export_log.append(f"✓ Exported SVG to {file_path}")
                
            elif export_format == "JSON":
                export_data = {
                    "base": self.state.current_base.__dict__,
                    "mechanisms": [m.__dict__ for m in self.state.mechanisms],
                    "placements": {k: v.__dict__ for k, v in self.state.adapter.placements.items()}
                }
                with open(file_path, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                self.export_log.append(f"✓ Exported JSON to {file_path}")
                
            elif export_format == "Complete Package":
                folder_path = Path(folder)
                
                # Export base SVG
                svg_path = folder_path / "base.svg"
                svg_content = base_to_svg(self.state.current_base)
                with open(svg_path, 'w') as f:
                    f.write(svg_content)
                self.export_log.append(f"✓ Exported base SVG")
                
                # Export assembly info
                if self.include_assembly_cb.isChecked():
                    assembly_path = folder_path / "assembly_instructions.txt"
                    with open(assembly_path, 'w') as f:
                        f.write(self.generate_assembly_instructions())
                    self.export_log.append(f"✓ Exported assembly instructions")
                
                # Export BOM
                if self.include_bom_cb.isChecked():
                    bom_path = folder_path / "bill_of_materials.csv"
                    with open(bom_path, 'w') as f:
                        f.write(self.generate_bom())
                    self.export_log.append(f"✓ Exported bill of materials")
                    
                self.export_log.append(f"✓ Complete package exported to {folder}")
                
            self.export_log.append("--- Export Complete ---\n")
            QMessageBox.information(self, "Success", "Export completed successfully!")
            
        except Exception as e:
            self.export_log.append(f"✗ Export failed: {str(e)}")
            QMessageBox.critical(self, "Export Failed", str(e))
            
    def generate_assembly_instructions(self) -> str:
        """Generate assembly instructions text."""
        return f"""ASSEMBLY INSTRUCTIONS
====================

Base Assembly:
1. Cut base material ({self.state.current_base.primary_material.value}) to specified dimensions
2. Drill mounting holes as indicated
3. Sand all edges smooth
4. Apply finish as desired

Mechanism Installation:
{chr(10).join([f"{i+1}. Install {m.name} at designated position" 
               for i, m in enumerate(self.state.mechanisms)])}

Final Assembly:
1. Secure all mechanisms to base
2. Connect drive system
3. Test all movements
4. Make final adjustments
"""
        
    def generate_bom(self) -> str:
        """Generate bill of materials CSV."""
        bom = "Item,Quantity,Material,Dimensions\n"
        bom += f"Base,1,{self.state.current_base.primary_material.value},{self.state.current_base.dimensions}\n"
        bom += f"Mounting Screws,{len(self.state.current_base.mounting_points)},Steel,M4x20\n"
        
        for mech in self.state.mechanisms:
            bom += f"{mech.name},1,Various,Per specification\n"
            
        return bom
        
    def new_project(self):
        """Start a new project."""
        reply = QMessageBox.question(
            self, "New Project", 
            "Are you sure you want to start a new project? Unsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.state = AppState()
            self.base_info_text.clear()
            self.mechanism_list.clear()
            self.preview_text.clear()
            self.export_log.clear()
            self.status_label.setText("New project started")
            
    def load_project(self):
        """Load project from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Project", "", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path) as f:
                    data = json.load(f)
                    
                # Load base configuration
                # (Simplified - in real app would reconstruct objects properly)
                self.status_label.setText(f"Loaded project from {file_path}")
                QMessageBox.information(self, "Success", "Project loaded!")
                
            except Exception as e:
                QMessageBox.critical(self, "Load Failed", str(e))
                
    def save_project(self):
        """Save project to file."""
        if not self.state.current_base:
            QMessageBox.warning(self, "No Project", "Nothing to save")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                export_data = {
                    "base": self.state.current_base.__dict__,
                    "mechanisms": [m.__dict__ for m in self.state.mechanisms],
                    "placements": {k: v.__dict__ for k, v in self.state.adapter.placements.items()}
                }
                
                with open(file_path, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                    
                self.status_label.setText(f"Saved project to {file_path}")
                QMessageBox.information(self, "Success", "Project saved!")
                
            except Exception as e:
                QMessageBox.critical(self, "Save Failed", str(e))


def main():
    """Run the demo application."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show main window
    window = DemoMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()