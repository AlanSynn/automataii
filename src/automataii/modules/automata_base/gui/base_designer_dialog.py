"""
Main base designer dialog for automata base module.
"""

try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
        QTabWidget, QDialogButtonBox, QMessageBox,
        QFileDialog, QMenu, QInputDialog
    )
    from PyQt6.QtCore import Qt, pyqtSignal
except ImportError:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
        QTabWidget, QDialogButtonBox, QMessageBox,
        QFileDialog, QMenu, QInputDialog
    )
    from PyQt5.QtCore import Qt, pyqtSignal

from pathlib import Path

from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import MountingPoint, Point2D
from automataii.modules.automata_base.enums.base_types import MountingType, AssemblyMethod
from automataii.modules.automata_base.gui.base_selection_widget import BaseSelectionWidget
from automataii.modules.automata_base.gui.base_preview_widget import BasePreviewWidget
from automataii.modules.automata_base.gui.material_selection_widget import MaterialSelectionWidget
from automataii.modules.automata_base.gui.dimension_input_widget import DimensionInputWidget
from automataii.modules.automata_base.utils.validators import validate_base_configuration
from automataii.modules.automata_base.utils.converters import base_to_svg, base_to_dxf
from automataii.modules.automata_base.config.base_specs import get_base_specification


class BaseDesignerDialog(QDialog):
    """Main dialog for designing automata bases."""
    
    # Signals
    base_created = pyqtSignal(BaseConfiguration)
    
    def __init__(self, parent=None):
        """Initialize the base designer dialog."""
        super().__init__(parent)
        self.current_config = None
        self.setup_ui()
        self.setWindowTitle("Automata Base Designer")
        self.resize(1000, 700)
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Main content area
        content_layout = QHBoxLayout()
        
        # Left side - Input controls
        left_panel = QTabWidget()
        left_panel.setMaximumWidth(400)
        
        # Base selection tab
        self.base_selection = BaseSelectionWidget()
        left_panel.addTab(self.base_selection, "Base Type")
        
        # Dimensions tab
        self.dimension_input = DimensionInputWidget()
        left_panel.addTab(self.dimension_input, "Dimensions")
        
        # Material tab
        self.material_selection = MaterialSelectionWidget()
        left_panel.addTab(self.material_selection, "Material")
        
        content_layout.addWidget(left_panel)
        
        # Right side - Preview
        preview_layout = QVBoxLayout()
        
        # Preview controls
        preview_controls = QHBoxLayout()
        
        # View options
        self.show_dims_btn = QPushButton("Show Dimensions")
        self.show_dims_btn.setCheckable(True)
        self.show_dims_btn.setChecked(True)
        preview_controls.addWidget(self.show_dims_btn)
        
        self.show_mounts_btn = QPushButton("Show Mounting Points")
        self.show_mounts_btn.setCheckable(True)
        self.show_mounts_btn.setChecked(True)
        preview_controls.addWidget(self.show_mounts_btn)
        
        self.show_grid_btn = QPushButton("Show Grid")
        self.show_grid_btn.setCheckable(True)
        self.show_grid_btn.setChecked(True)
        preview_controls.addWidget(self.show_grid_btn)
        
        preview_controls.addStretch()
        
        # Export button with menu
        self.export_btn = QPushButton("Export...")
        export_menu = QMenu(self)
        export_menu.addAction("Export as SVG", self.export_svg)
        export_menu.addAction("Export as DXF", self.export_dxf)
        export_menu.addAction("Export as STL", self.export_stl)
        export_menu.addAction("Export as STEP", self.export_step)
        export_menu.addSeparator()
        export_menu.addAction("Generate PDF Instructions", self.export_pdf)
        self.export_btn.setMenu(export_menu)
        preview_controls.addWidget(self.export_btn)
        
        preview_layout.addLayout(preview_controls)
        
        # Preview widget
        self.preview = BasePreviewWidget()
        preview_layout.addWidget(self.preview, 1)
        
        content_layout.addLayout(preview_layout, 1)
        layout.addLayout(content_layout)
        
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        # Add custom buttons
        self.validate_btn = QPushButton("Validate")
        self.validate_btn.clicked.connect(self.validate_configuration)
        buttons.addButton(self.validate_btn, QDialogButtonBox.ButtonRole.ActionRole)
        
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self.reset_configuration)
        buttons.addButton(self.reset_btn, QDialogButtonBox.ButtonRole.ResetRole)
        
        layout.addWidget(buttons)
        
        # Connect signals
        self.base_selection.base_type_changed.connect(self.on_base_type_changed)
        self.base_selection.specification_changed.connect(self.on_specification_changed)
        self.dimension_input.dimensions_changed.connect(self.on_dimensions_changed)
        self.material_selection.material_changed.connect(self.on_material_changed)
        self.material_selection.thickness_changed.connect(self.on_thickness_changed)
        
        self.show_dims_btn.toggled.connect(self.preview.set_show_dimensions)
        self.show_mounts_btn.toggled.connect(self.preview.set_show_mounting_points)
        self.show_grid_btn.toggled.connect(self.preview.set_show_grid)
        
        # Initialize with default
        self.create_default_configuration()
    
    def create_default_configuration(self):
        """Create a default configuration."""
        from automataii.modules.automata_base.enums.base_types import BaseType, MaterialType
        
        self.current_config = BaseConfiguration(
            name="New Base",
            base_type=BaseType.FLAT_RECTANGULAR,
            dimensions=self.dimension_input.get_dimensions(),
            primary_material=MaterialType.WOOD,
            material_thickness=10.0,
            mounting_type=MountingType.SURFACE,
            assembly_method=AssemblyMethod.SCREWS
        )
        
        # Add default mounting points
        self.add_default_mounting_points()
        
        # Update preview
        self.update_preview()
    
    def add_default_mounting_points(self):
        """Add default mounting points based on base type."""
        if not self.current_config:
            return
        
        dims = self.current_config.dimensions
        margin = 10  # mm from edge
        
        if self.current_config.base_type == BaseType.FLAT_RECTANGULAR:
            # Add corner mounting points
            points = [
                (margin, margin),
                (dims.width - margin, margin),
                (dims.width - margin, dims.height - margin),
                (margin, dims.height - margin)
            ]
            
            for x, y in points:
                mp = MountingPoint(
                    position=Point2D(x, y),
                    hole_diameter=5.0,
                    thread_type="M5"
                )
                self.current_config.add_mounting_point(mp)
        
        elif self.current_config.base_type == BaseType.FLAT_CIRCULAR:
            # Add radial mounting points
            center_x = dims.width / 2
            center_y = dims.height / 2
            radius = min(dims.width, dims.height) / 2 - margin * 2
            
            import math
            for i in range(4):
                angle = i * math.pi / 2
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                
                mp = MountingPoint(
                    position=Point2D(x, y),
                    hole_diameter=5.0,
                    thread_type="M5"
                )
                self.current_config.add_mounting_point(mp)
    
    def on_base_type_changed(self, base_type):
        """Handle base type change."""
        if self.current_config:
            self.current_config.base_type = base_type
            self.dimension_input.set_base_type(base_type)
            
            # Clear and re-add mounting points
            self.current_config.mounting_points.clear()
            self.add_default_mounting_points()
            
            self.update_preview()
    
    def on_specification_changed(self, spec_name):
        """Handle specification selection."""
        if spec_name:
            spec = get_base_specification(spec_name)
            # Create base from specification
            self.current_config = spec.create_base("medium")  # Default to medium size
            
            # Update UI components
            self.dimension_input.set_dimensions(self.current_config.dimensions)
            self.material_selection.set_material(self.current_config.primary_material)
            self.material_selection.set_thickness(self.current_config.material_thickness)
            
            self.update_preview()
    
    def on_dimensions_changed(self, dimensions):
        """Handle dimension change."""
        if self.current_config:
            self.current_config.dimensions = dimensions
            
            # Update mounting points if needed
            self.current_config.mounting_points.clear()
            self.add_default_mounting_points()
            
            self.update_preview()
            self.update_cost_estimate()
    
    def on_material_changed(self, material):
        """Handle material change."""
        if self.current_config:
            self.current_config.primary_material = material
            self.update_preview()
            self.update_cost_estimate()
    
    def on_thickness_changed(self, thickness):
        """Handle thickness change."""
        if self.current_config:
            self.current_config.material_thickness = thickness
            self.update_preview()
            self.update_cost_estimate()
    
    def update_preview(self):
        """Update the preview widget."""
        if self.current_config:
            self.preview.set_base_configuration(self.current_config)
    
    def update_cost_estimate(self):
        """Update cost estimate in material widget."""
        if self.current_config:
            self.material_selection.update_cost_estimate(self.current_config)
    
    def validate_configuration(self):
        """Validate the current configuration."""
        if not self.current_config:
            return
        
        issues = validate_base_configuration(self.current_config)
        
        if issues:
            # Show validation errors
            error_text = "Configuration validation failed:\n\n"
            for issue in issues:
                error_text += f"• {issue}\n"
            
            QMessageBox.warning(self, "Validation Failed", error_text)
        else:
            QMessageBox.information(self, "Validation Passed", 
                                  "Configuration is valid!")
    
    def reset_configuration(self):
        """Reset to default configuration."""
        reply = QMessageBox.question(
            self, "Reset Configuration",
            "Are you sure you want to reset to default configuration?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.create_default_configuration()
            # Reset UI
            self.base_selection.set_base_type(self.current_config.base_type)
            self.dimension_input.set_dimensions(self.current_config.dimensions)
            self.material_selection.set_material(self.current_config.primary_material)
            self.material_selection.set_thickness(self.current_config.material_thickness)
    
    def export_svg(self):
        """Export as SVG."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export SVG", "", "SVG Files (*.svg)"
        )
        if filename:
            svg_content = base_to_svg(self.current_config, mode="technical")
            with open(filename, 'w') as f:
                f.write(svg_content)
            QMessageBox.information(self, "Export Complete", 
                                  f"SVG exported to {filename}")
    
    def export_dxf(self):
        """Export as DXF."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export DXF", "", "DXF Files (*.dxf)"
        )
        if filename:
            dxf_content = base_to_dxf(self.current_config)
            with open(filename, 'w') as f:
                f.write(dxf_content)
            QMessageBox.information(self, "Export Complete",
                                  f"DXF exported to {filename}")
    
    def export_stl(self):
        """Export as STL."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export STL", "", "STL Files (*.stl)"
        )
        if filename:
            try:
                from automataii.modules.automata_base.utils.stl_exporter import STLExporter
                exporter = STLExporter(self.current_config)
                exporter.export(filename)
                QMessageBox.information(self, "Export Complete",
                                      f"STL exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", str(e))
    
    def export_step(self):
        """Export as STEP."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export STEP", "", "STEP Files (*.step *.stp)"
        )
        if filename:
            try:
                from automataii.modules.automata_base.utils.step_exporter import STEPExporter
                exporter = STEPExporter(self.current_config)
                exporter.export(filename)
                QMessageBox.information(self, "Export Complete",
                                      f"STEP exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", str(e))
    
    def export_pdf(self):
        """Generate PDF instructions."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", "", "PDF Files (*.pdf)"
        )
        if filename:
            try:
                from automataii.modules.automata_base.utils.pdf_generator import PDFGenerator
                generator = PDFGenerator(self.current_config)
                generator.generate(Path(filename))
                QMessageBox.information(self, "Export Complete",
                                      f"PDF instructions generated at {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", str(e))
    
    def accept(self):
        """Accept the dialog."""
        # Validate before accepting
        issues = validate_base_configuration(self.current_config)
        if issues:
            reply = QMessageBox.question(
                self, "Configuration Issues",
                "The configuration has validation issues. Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Set a proper name
        name, ok = QInputDialog.getText(
            self, "Base Name", "Enter a name for this base:",
            text=self.current_config.name
        )
        if ok and name:
            self.current_config.name = name
        
        # Emit signal
        self.base_created.emit(self.current_config)
        super().accept()
    
    def get_configuration(self) -> BaseConfiguration:
        """Get the current base configuration."""
        return self.current_config