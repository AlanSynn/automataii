"""
STL Export Dialog for exporting mechanism bases to 3D printable files.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QGroupBox, QFileDialog, QMessageBox, QRadioButton,
    QButtonGroup, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from pathlib import Path
from typing import Optional, Tuple

from automataii.modules.automata_base.enums.base_types import MaterialType
from automataii.utils.export_mechanism_base import MechanismBaseExporter


class STLExportDialog(QDialog):
    """Dialog for configuring and exporting STL files for mechanism bases."""
    
    exported = pyqtSignal(Path)  # Emitted when STL is successfully exported
    
    def __init__(self, mechanism_bounds: Tuple[float, float, float, float], 
                 parent=None):
        """
        Initialize STL export dialog.
        
        Args:
            mechanism_bounds: (min_x, min_y, max_x, max_y) of mechanism
            parent: Parent widget
        """
        super().__init__(parent)
        self.mechanism_bounds = mechanism_bounds
        self.exporter = MechanismBaseExporter(mechanism_bounds)
        
        self.setWindowTitle("Export Base for 3D Printing")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self._setup_ui()
        self._update_preview()
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout()
        
        # Base type selection
        type_group = QGroupBox("Base Type")
        type_layout = QVBoxLayout()
        
        self.type_group = QButtonGroup()
        self.type_flat = QRadioButton("Flat Base - Simple flat platform")
        self.type_box_open = QRadioButton("Open Box - Box with no top")
        self.type_box_closed = QRadioButton("Enclosed Box - Fully enclosed")
        self.type_pedestal = QRadioButton("Display Pedestal - Raised platform")
        self.type_wall = QRadioButton("Wall Mount - With brackets")
        
        self.type_flat.setChecked(True)
        
        self.type_group.addButton(self.type_flat, 0)
        self.type_group.addButton(self.type_box_open, 1)
        self.type_group.addButton(self.type_box_closed, 2)
        self.type_group.addButton(self.type_pedestal, 3)
        self.type_group.addButton(self.type_wall, 4)
        
        for button in [self.type_flat, self.type_box_open, self.type_box_closed,
                      self.type_pedestal, self.type_wall]:
            type_layout.addWidget(button)
            button.toggled.connect(self._update_preview)
        
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # Material selection
        material_group = QGroupBox("Material Settings")
        material_layout = QVBoxLayout()
        
        # Material type
        mat_layout = QHBoxLayout()
        mat_layout.addWidget(QLabel("Material:"))
        self.material_combo = QComboBox()
        self.material_combo.addItems([
            "Aluminum", "Steel", "Wood", "Plywood", "MDF",
            "Acrylic", "3D Printed (PLA)", "3D Printed (Resin)"
        ])
        self.material_combo.currentTextChanged.connect(self._update_preview)
        mat_layout.addWidget(self.material_combo)
        material_layout.addLayout(mat_layout)
        
        # Thickness
        thick_layout = QHBoxLayout()
        thick_layout.addWidget(QLabel("Material Thickness:"))
        self.thickness_spin = QDoubleSpinBox()
        self.thickness_spin.setRange(1.0, 50.0)
        self.thickness_spin.setValue(10.0)
        self.thickness_spin.setSuffix(" mm")
        self.thickness_spin.valueChanged.connect(self._update_preview)
        thick_layout.addWidget(self.thickness_spin)
        material_layout.addLayout(thick_layout)
        
        material_group.setLayout(material_layout)
        layout.addWidget(material_group)
        
        # Dimension settings
        dim_group = QGroupBox("Dimensions")
        dim_layout = QVBoxLayout()
        
        # Margin
        margin_layout = QHBoxLayout()
        margin_layout.addWidget(QLabel("Margin around mechanism:"))
        self.margin_spin = QDoubleSpinBox()
        self.margin_spin.setRange(5.0, 100.0)
        self.margin_spin.setValue(20.0)
        self.margin_spin.setSuffix(" mm")
        self.margin_spin.valueChanged.connect(self._recalculate_dimensions)
        margin_layout.addWidget(self.margin_spin)
        dim_layout.addLayout(margin_layout)
        
        # Height (for box/pedestal)
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Height:"))
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(10.0, 500.0)
        self.height_spin.setValue(50.0)
        self.height_spin.setSuffix(" mm")
        self.height_spin.valueChanged.connect(self._update_preview)
        height_layout.addWidget(self.height_spin)
        self.height_label = height_layout.itemAt(0).widget()
        dim_layout.addLayout(height_layout)
        
        dim_group.setLayout(dim_layout)
        layout.addWidget(dim_group)
        
        # Preview info
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        preview_layout.addWidget(self.preview_text)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Export options
        export_group = QGroupBox("Export Options")
        export_layout = QVBoxLayout()
        
        self.binary_check = QCheckBox("Export as binary STL (smaller file size)")
        self.binary_check.setChecked(True)
        export_layout.addWidget(self.binary_check)
        
        self.add_info_check = QCheckBox("Add info text file with specifications")
        self.add_info_check.setChecked(True)
        export_layout.addWidget(self.add_info_check)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("Export STL...")
        self.export_btn.clicked.connect(self._export)
        
        self.export_all_btn = QPushButton("Export All Variants...")
        self.export_all_btn.clicked.connect(self._export_all)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.export_all_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _recalculate_dimensions(self):
        """Recalculate base dimensions when margin changes."""
        self.exporter = MechanismBaseExporter(
            self.mechanism_bounds,
            margin=self.margin_spin.value()
        )
        self._update_preview()
    
    def _update_preview(self):
        """Update the preview text with current settings."""
        base_type = ["flat", "box_open", "box_closed", "pedestal", "wall"][
            self.type_group.checkedId()
        ]
        
        # Update height visibility
        show_height = base_type in ["box_open", "box_closed", "pedestal"]
        self.height_label.setVisible(show_height)
        self.height_spin.setVisible(show_height)
        
        # Generate preview text
        preview = f"Base Type: {self.type_group.checkedButton().text()}\n"
        preview += f"Material: {self.material_combo.currentText()}\n"
        preview += f"Base Dimensions: {self.exporter.width:.1f} x {self.exporter.height:.1f} mm\n"
        
        if show_height:
            preview += f"Height: {self.height_spin.value():.1f} mm\n"
        
        preview += f"Material Thickness: {self.thickness_spin.value():.1f} mm\n"
        
        # Estimate material volume
        if base_type == "flat":
            volume = self.exporter.width * self.exporter.height * self.thickness_spin.value()
        elif base_type in ["box_open", "box_closed"]:
            # Approximate volume of walls
            wall_area = 2 * (self.exporter.width + self.exporter.height) * self.height_spin.value()
            bottom_area = self.exporter.width * self.exporter.height
            if base_type == "box_closed":
                bottom_area *= 2  # Top and bottom
            volume = (wall_area + bottom_area) * self.thickness_spin.value()
        elif base_type == "pedestal":
            # Approximate as truncated pyramid
            base_area = self.exporter.width * self.exporter.height
            top_area = base_area * 0.49  # 70% linear = 49% area
            avg_area = (base_area + top_area) / 2
            volume = avg_area * self.height_spin.value()
        else:  # wall mount
            volume = self.exporter.width * self.exporter.height * self.thickness_spin.value()
            # Add bracket volume estimate
            bracket_volume = 4 * (self.exporter.width * 0.15) ** 2 * 30 * self.thickness_spin.value()
            volume += bracket_volume
        
        preview += f"\nEstimated Volume: {volume/1000:.1f} cm³\n"
        
        # Weight estimate based on material
        density_map = {
            "Aluminum": 2.7,  # g/cm³
            "Steel": 7.85,
            "Wood": 0.7,
            "Plywood": 0.68,
            "MDF": 0.75,
            "Acrylic": 1.19,
            "3D Printed (PLA)": 1.24,
            "3D Printed (Resin)": 1.3
        }
        
        material = self.material_combo.currentText()
        if material in density_map:
            weight = (volume / 1000) * density_map[material]
            preview += f"Estimated Weight: {weight:.1f} g\n"
        
        self.preview_text.setPlainText(preview)
    
    def _get_material_type(self) -> MaterialType:
        """Convert combo box selection to MaterialType enum."""
        material_map = {
            "Aluminum": MaterialType.ALUMINUM,
            "Steel": MaterialType.STEEL,
            "Wood": MaterialType.WOOD,
            "Plywood": MaterialType.PLYWOOD,
            "MDF": MaterialType.MDF,
            "Acrylic": MaterialType.ACRYLIC,
            "3D Printed (PLA)": MaterialType.PLASTIC_3D_PRINTED,
            "3D Printed (Resin)": MaterialType.RESIN_3D_PRINTED
        }
        return material_map.get(self.material_combo.currentText(), MaterialType.ALUMINUM)
    
    def _export(self):
        """Export single STL file."""
        base_type = ["flat", "box_open", "box_closed", "pedestal", "wall"][
            self.type_group.checkedId()
        ]
        
        # Get filename
        suggested_name = f"mechanism_base_{base_type}.stl"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export STL File", suggested_name,
            "STL Files (*.stl);;All Files (*.*)"
        )
        
        if not filename:
            return
        
        filepath = Path(filename)
        
        try:
            # Create configuration based on type
            if base_type == "flat":
                config = self.exporter.create_flat_base(
                    thickness=self.thickness_spin.value(),
                    material=self._get_material_type()
                )
            elif base_type == "box_open":
                config = self.exporter.create_box_base(
                    wall_height=self.height_spin.value(),
                    wall_thickness=self.thickness_spin.value(),
                    open_top=True
                )
            elif base_type == "box_closed":
                config = self.exporter.create_box_base(
                    wall_height=self.height_spin.value(),
                    wall_thickness=self.thickness_spin.value(),
                    open_top=False
                )
            elif base_type == "pedestal":
                config = self.exporter.create_display_base(
                    pedestal_height=self.height_spin.value()
                )
            else:  # wall
                config = self.exporter.create_wall_mount()
            
            # Export STL
            from automataii.utils.stl_exporter import STLExporter
            exporter = STLExporter(config)
            exporter.export(filepath, binary=self.binary_check.isChecked())
            
            # Export info file if requested
            if self.add_info_check.isChecked():
                info_path = filepath.with_suffix('.txt')
                with open(info_path, 'w') as f:
                    f.write(f"Mechanism Base STL Export\n")
                    f.write(f"========================\n\n")
                    f.write(self.preview_text.toPlainText())
                    f.write(f"\nSTL Statistics:\n")
                    stats = exporter.get_statistics()
                    f.write(f"- Triangles: {stats['triangle_count']}\n")
                    f.write(f"- Surface Area: {stats['surface_area']:.2f} mm²\n")
                    f.write(f"- Bounding Box: {stats['bounding_box']['dimensions']}\n")
            
            QMessageBox.information(
                self, "Export Successful",
                f"STL file exported successfully to:\n{filepath}"
            )
            
            self.exported.emit(filepath)
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(
                self, "Export Failed",
                f"Failed to export STL file:\n{str(e)}"
            )
    
    def _export_all(self):
        """Export all base variants."""
        # Get directory
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory"
        )
        
        if not directory:
            return
        
        output_dir = Path(directory)
        
        try:
            # Export all variants
            files = self.exporter.export_all_variants(
                output_dir,
                prefix="mechanism_base"
            )
            
            # Create summary file
            summary_path = output_dir / "base_variants_summary.txt"
            with open(summary_path, 'w') as f:
                f.write("Mechanism Base Variants\n")
                f.write("=====================\n\n")
                f.write(f"Material: {self.material_combo.currentText()}\n")
                f.write(f"Thickness: {self.thickness_spin.value():.1f} mm\n\n")
                
                for file_info in files:
                    f.write(f"\n{file_info['variant'].upper()}:\n")
                    f.write(f"  File: {file_info['file'].name}\n")
                    f.write(f"  Triangles: {file_info['triangles']}\n")
                    f.write(f"  Dimensions: {file_info['dimensions']}\n")
            
            QMessageBox.information(
                self, "Export Successful",
                f"Exported {len(files)} base variants to:\n{output_dir}"
            )
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(
                self, "Export Failed",
                f"Failed to export STL files:\n{str(e)}"
            )