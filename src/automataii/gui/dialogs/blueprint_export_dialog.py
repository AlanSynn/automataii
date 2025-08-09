"""
Blueprint Export Dialog with advanced options for part-by-part and single-page export.

Author: Alan Synn · alan@alansynn.com
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, 
    QRadioButton, QCheckBox, QSpinBox, QDoubleSpinBox, QSlider,
    QPushButton, QLabel, QComboBox, QButtonGroup, QTabWidget,
    QWidget, QFileDialog, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QPainter


class BlueprintExportDialog(QDialog):
    """
    Sleek Blueprint Export Dialog with intuitive UX.
    Inspired by the mechanism recommendation dialog design.
    """
    
    export_requested = pyqtSignal(dict)  # Export configuration
    
    def __init__(self, mechanism_data: dict, parent=None):
        super().__init__(parent)
        self.mechanism_data = mechanism_data
        self.export_config = {}
        
        self.setWindowTitle("Blueprint Export")
        self.setModal(True)
        self.setFixedSize(800, 600)
        
        # Apply modern stylesheet
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 10px 0 10px;
                color: #333;
            }
            QRadioButton, QCheckBox {
                font-size: 13px;
                padding: 5px;
            }
            QRadioButton::indicator, QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QPushButton {
                font-size: 13px;
                padding: 8px 20px;
                border-radius: 6px;
                font-weight: 500;
            }
            QLabel {
                font-size: 13px;
                color: #555;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                padding: 6px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 13px;
                background-color: white;
            }
        """)
        
        self.setup_ui()
        self.update_preview()
    
    def setup_ui(self):
        """Setup clean and intuitive UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title Section
        title_widget = self.create_title_section()
        main_layout.addWidget(title_widget)
        
        # Main Content Area (2 columns)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        # Left Column - Export Options
        left_column = QVBoxLayout()
        left_column.setSpacing(15)
        
        # Export Format Card
        format_card = self.create_format_card()
        left_column.addWidget(format_card)
        
        # Scale Settings Card
        scale_card = self.create_scale_card()
        left_column.addWidget(scale_card)
        
        left_column.addStretch()
        
        # Right Column - Preview
        right_column = QVBoxLayout()
        preview_card = self.create_preview_card()
        right_column.addWidget(preview_card)
        
        content_layout.addLayout(left_column, 1)
        content_layout.addLayout(right_column, 1)
        
        main_layout.addLayout(content_layout)
        
        # Bottom Action Bar
        action_bar = self.create_action_bar()
        main_layout.addWidget(action_bar)
    
    def create_title_section(self):
        """Create clean title section."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Icon and title
        title_label = QLabel("🎯 Blueprint Export Configuration")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            padding: 10px;
        """)
        
        # Info label
        info_label = QLabel(f"Export {len(self.mechanism_data.get('mechanisms', []))} mechanisms")
        info_label.setStyleSheet("""
            font-size: 13px;
            color: #7f8c8d;
            padding: 10px;
        """)
        
        layout.addWidget(title_label)
        layout.addStretch()
        layout.addWidget(info_label)
        
        return widget
    
    def create_format_card(self):
        """Create export format selection card."""
        card = QGroupBox("Export Format")
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        
        # Format toggle buttons (styled like recommendation dialog)
        format_widget = QWidget()
        format_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        format_layout = QVBoxLayout(format_widget)
        
        self.single_page_btn = self.create_option_button(
            "📄 Single Page",
            "One large blueprint for plotting",
            False
        )
        
        self.multi_page_btn = self.create_option_button(
            "📚 Multi-Page", 
            "Letter-size pages for printing",
            True
        )
        
        format_layout.addWidget(self.single_page_btn)
        format_layout.addWidget(self.multi_page_btn)
        
        layout.addWidget(format_widget)
        
        # Part options with clean checkboxes
        options_widget = QWidget()
        options_layout = QVBoxLayout(options_widget)
        options_layout.setSpacing(8)
        
        self.decompose_check = self.create_clean_checkbox(
            "🔧 Decompose into parts",
            True
        )
        
        self.assembly_check = self.create_clean_checkbox(
            "📋 Include assembly guide",
            True
        )
        
        self.dimensions_check = self.create_clean_checkbox(
            "📏 Add dimensions",
            True
        )
        
        self.textures_check = self.create_clean_checkbox(
            "🎨 Include textures",
            False
        )
        
        options_layout.addWidget(self.decompose_check)
        options_layout.addWidget(self.assembly_check)
        options_layout.addWidget(self.dimensions_check)
        options_layout.addWidget(self.textures_check)
        
        layout.addWidget(options_widget)
        
        return card
    
    def create_scale_card(self):
        """Create scale settings card."""
        card = QGroupBox("Scale & Size")
        layout = QGridLayout(card)
        layout.setSpacing(12)
        
        # Character height with visual indicator
        layout.addWidget(QLabel("Character Height:"), 0, 0)
        
        height_widget = QWidget()
        height_layout = QHBoxLayout(height_widget)
        height_layout.setContentsMargins(0, 0, 0, 0)
        
        self.character_height = QSpinBox()
        self.character_height.setRange(100, 2000)
        self.character_height.setValue(400)
        self.character_height.setSuffix(" mm")
        self.character_height.setMinimumWidth(100)
        
        # Visual height indicator
        height_indicator = QLabel("👤")
        height_indicator.setStyleSheet("font-size: 24px;")
        
        height_layout.addWidget(self.character_height)
        height_layout.addWidget(height_indicator)
        height_layout.addStretch()
        
        layout.addWidget(height_widget, 0, 1)
        
        # Scale factor with slider
        layout.addWidget(QLabel("Scale Factor:"), 1, 0)
        
        scale_widget = QWidget()
        scale_layout = QHBoxLayout(scale_widget)
        scale_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(50, 200)
        self.scale_slider.setValue(100)
        self.scale_slider.setMinimumWidth(150)
        
        self.scale_label = QLabel("1.0×")
        self.scale_label.setMinimumWidth(40)
        self.scale_label.setStyleSheet("font-weight: bold;")
        
        scale_layout.addWidget(self.scale_slider)
        scale_layout.addWidget(self.scale_label)
        
        layout.addWidget(scale_widget, 1, 1)
        
        # Paper size selector
        layout.addWidget(QLabel("Paper Size:"), 2, 0)
        
        self.paper_combo = QComboBox()
        self.paper_combo.addItems(["Letter (8.5\" × 11\")", "A4 (210 × 297mm)", "A3 (297 × 420mm)"])
        self.paper_combo.setMinimumWidth(180)
        layout.addWidget(self.paper_combo, 2, 1)
        
        # Connect signals
        self.character_height.valueChanged.connect(self.update_preview)
        self.scale_slider.valueChanged.connect(self.on_scale_changed)
        self.paper_combo.currentTextChanged.connect(self.update_preview)
        
        return card
    
    def create_preview_card(self):
        """Create preview card with visual feedback."""
        card = QGroupBox("Preview")
        layout = QVBoxLayout(card)
        
        # Preview area with visual representation
        preview_widget = QWidget()
        preview_widget.setMinimumHeight(250)
        preview_widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 2px dashed #cbd5e0;
                border-radius: 8px;
            }
        """)
        
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Visual preview elements
        self.preview_icon = QLabel("📐")
        self.preview_icon.setStyleSheet("font-size: 48px;")
        self.preview_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.preview_title = QLabel("Multi-Page Export")
        self.preview_title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
            padding: 10px;
        """)
        self.preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.preview_info = QLabel("")
        self.preview_info.setStyleSheet("""
            font-size: 14px;
            color: #34495e;
            padding: 5px;
        """)
        self.preview_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        preview_layout.addWidget(self.preview_icon)
        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.preview_info)
        
        layout.addWidget(preview_widget)
        
        # Statistics cards
        stats_widget = QWidget()
        stats_layout = QHBoxLayout(stats_widget)
        stats_layout.setSpacing(10)
        
        self.pages_stat = self.create_stat_card("📄", "3", "Pages")
        self.parts_stat = self.create_stat_card("🔧", "12", "Parts")
        
        stats_layout.addWidget(self.pages_stat)
        stats_layout.addWidget(self.parts_stat)
        
        layout.addWidget(stats_widget)
        
        return card
    
    def create_stat_card(self, icon, value, label):
        """Create a statistics card widget."""
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #f7fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        value_label = QLabel(value)
        value_label.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #2563eb;
        """)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setObjectName(f"{label}_value")  # For updating
        
        text_label = QLabel(label)
        text_label.setStyleSheet("""
            font-size: 12px;
            color: #64748b;
        """)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(icon_label)
        layout.addWidget(value_label)
        layout.addWidget(text_label)
        
        return card
    
    def create_action_bar(self):
        """Create bottom action bar."""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border-top: 1px solid #e0e0e0;
                padding: 10px;
            }
        """)
        
        layout = QHBoxLayout(widget)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f5;
                color: #495057;
                border: none;
                padding: 10px 24px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
        
        # Export button
        self.export_btn = QPushButton("📤 Export Blueprint")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                padding: 10px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        
        layout.addWidget(self.cancel_btn)
        layout.addStretch()
        layout.addWidget(self.export_btn)
        
        # Connect signals
        self.cancel_btn.clicked.connect(self.reject)
        self.export_btn.clicked.connect(self.start_export)
        
        return widget
    
    def create_option_button(self, text, description, checked=False):
        """Create a styled option button."""
        btn = QRadioButton(text)
        btn.setChecked(checked)
        btn.setStyleSheet("""
            QRadioButton {
                font-size: 14px;
                font-weight: 500;
                padding: 8px;
            }
        """)
        
        # Add description as tooltip
        btn.setToolTip(description)
        
        # Connect signal
        btn.toggled.connect(self.update_preview)
        
        return btn
    
    def create_clean_checkbox(self, text, checked=False):
        """Create a clean styled checkbox."""
        check = QCheckBox(text)
        check.setChecked(checked)
        check.setStyleSheet("""
            QCheckBox {
                font-size: 13px;
                padding: 4px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
        """)
        
        check.toggled.connect(self.update_preview)
        
        return check
    
    def on_scale_changed(self, value):
        """Handle scale slider change."""
        scale = value / 100.0
        self.scale_label.setText(f"{scale:.1f}×")
        self.update_preview()
    
    def update_preview(self):
        """Update the preview display."""
        is_multi = self.multi_page_btn.isChecked()
        decompose = self.decompose_check.isChecked()
        
        # Update preview title
        if is_multi:
            self.preview_icon.setText("📚")
            self.preview_title.setText("Multi-Page Export")
            self.preview_info.setText(f"Letter-size pages\n{self.character_height.value()}mm character")
        else:
            self.preview_icon.setText("📄")
            self.preview_title.setText("Single Page Export")
            self.preview_info.setText(f"Large format blueprint\n{self.character_height.value()}mm character")
        
        # Calculate statistics
        mechanism_count = len(self.mechanism_data.get('mechanisms', []))
        
        if decompose:
            # Estimate parts
            estimated_parts = 0
            for mech in self.mechanism_data.get('mechanisms', []):
                mech_type = mech.get('type', '')
                if mech_type == '4bar':
                    estimated_parts += 6
                elif mech_type == 'gear':
                    estimated_parts += 3
                elif mech_type == 'cam':
                    estimated_parts += 3
                else:
                    estimated_parts += 2
            
            pages = estimated_parts // 4 + (2 if self.assembly_check.isChecked() else 1)
        else:
            estimated_parts = mechanism_count
            pages = 1 if not is_multi else mechanism_count
        
        # Update stat cards
        pages_value = self.pages_stat.findChild(QLabel, "Pages_value")
        if pages_value:
            pages_value.setText(str(pages))
        
        parts_value = self.parts_stat.findChild(QLabel, "Parts_value")
        if parts_value:
            parts_value.setText(str(estimated_parts))
    
    def start_export(self):
        """Start the export process."""
        # Collect configuration
        self.export_config = {
            'multi_page': self.multi_page_btn.isChecked(),
            'decompose_mechanisms': self.decompose_check.isChecked(),
            'include_assembly_guide': self.assembly_check.isChecked(),
            'add_dimensions': self.dimensions_check.isChecked(),
            'include_textures': self.textures_check.isChecked(),
            'character_height_mm': self.character_height.value(),
            'scale_factor': self.scale_slider.value() / 100.0,
            'paper_size': self.paper_combo.currentText(),
        }
        
        # Get save location
        from PyQt6.QtWidgets import QFileDialog
        from pathlib import Path
        
        if self.export_config['multi_page']:
            save_dir = QFileDialog.getExistingDirectory(
                self,
                "Choose Export Directory",
                str(Path.home() / "Documents")
            )
            if not save_dir:
                return
            self.export_config['save_path'] = save_dir
        else:
            save_file, _ = QFileDialog.getSaveFileName(
                self,
                "Save Blueprint As",
                str(Path.home() / "Documents" / "blueprint.svg"),
                "SVG files (*.svg)"
            )
            if not save_file:
                return
            self.export_config['save_path'] = save_file
        
        self.export_requested.emit(self.export_config)
        self.accept()


if __name__ == "__main__":
    """Test the dialog standalone."""
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Sample mechanism data
    test_data = {
        'mechanisms': [
            {'type': '4bar', 'id': 'test1'},
            {'type': 'gear', 'id': 'test2'},
            {'type': 'cam', 'id': 'test3'},
        ]
    }
    
    dialog = BlueprintExportDialog(test_data)
    
    def on_export(config):
        print("Export configuration:")
        for key, value in config.items():
            print(f"  {key}: {value}")
    
    dialog.export_requested.connect(on_export)
    dialog.show()
    
    sys.exit(app.exec())