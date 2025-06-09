#!/usr/bin/env python3
"""
Integration Example for Automata Base System with Automataii

This example shows how to integrate the automata_base module into
the main Automataii application's Mechanism Design tab.
"""

from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QGroupBox, QRadioButton, QButtonGroup, QLabel
)
from PyQt6.QtCore import pyqtSignal, Qt

# Import from the automata_base module
from automata_base import (
    BaseType,
    BaseConfiguration,
    StructuredGenerator,
    BodyCavityGenerator,
    MechanismAdapter,
    ExportManager,
    BaseSelectionWidget,
    BasePreviewWidget,
    UI_AVAILABLE
)


class AutomataBaseIntegration(QWidget):
    """
    Example integration widget for Mechanism Design tab.
    This would be added to the existing tab to provide base selection.
    """
    
    base_configured = pyqtSignal(dict)  # Emitted when base is configured
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mechanisms = []  # List of current mechanisms
        self.base_config = None
        self.adapted_design = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Base Type Selection
        type_group = QGroupBox("Automata Base Type")
        type_layout = QVBoxLayout(type_group)
        
        self.type_button_group = QButtonGroup()
        
        # Structured Base Option
        structured_layout = QHBoxLayout()
        self.structured_radio = QRadioButton("Structured Base")
        self.structured_radio.setChecked(True)
        structured_desc = QLabel("Traditional base with housing for mechanisms")
        structured_desc.setStyleSheet("color: gray; font-size: 10px;")
        structured_layout.addWidget(self.structured_radio)
        structured_layout.addWidget(structured_desc)
        structured_layout.addStretch()
        type_layout.addLayout(structured_layout)
        
        # Body-Mounted Option
        body_layout = QHBoxLayout()
        self.body_radio = QRadioButton("Body-Mounted")
        body_desc = QLabel("Mechanisms integrated into character body")
        body_desc.setStyleSheet("color: gray; font-size: 10px;")
        body_layout.addWidget(self.body_radio)
        body_layout.addWidget(body_desc)
        body_layout.addStretch()
        type_layout.addLayout(body_layout)
        
        self.type_button_group.addButton(self.structured_radio, 0)
        self.type_button_group.addButton(self.body_radio, 1)
        
        layout.addWidget(type_group)
        
        # Configuration Widget
        if UI_AVAILABLE:
            self.config_widget = BaseSelectionWidget()
            self.config_widget.configuration_changed.connect(self.on_config_changed)
            layout.addWidget(self.config_widget)
            
            # Preview Widget
            self.preview_widget = BasePreviewWidget()
            self.preview_widget.setMinimumHeight(300)
            layout.addWidget(self.preview_widget)
        else:
            layout.addWidget(QLabel("UI components not available"))
        
        # Action Buttons
        button_layout = QHBoxLayout()
        
        self.generate_button = QPushButton("Generate Base")
        self.generate_button.clicked.connect(self.generate_base)
        button_layout.addWidget(self.generate_button)
        
        self.export_button = QPushButton("Export Design")
        self.export_button.clicked.connect(self.export_design)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        self.type_button_group.buttonClicked.connect(self.on_type_changed)
        
    def on_type_changed(self):
        """Handle base type change."""
        is_structured = self.structured_radio.isChecked()
        
        if UI_AVAILABLE:
            # Update configuration widget based on type
            if is_structured:
                self.config_widget.set_base_type('rectangular')
            else:
                # For body-mounted, we might show different options
                pass
                
    def on_config_changed(self, config: Dict[str, Any]):
        """Handle configuration change."""
        self.base_config = BaseConfiguration(**config)
        
        # Update preview if available
        if UI_AVAILABLE and self.base_config:
            # Update preview with new configuration
            pass
            
    def set_mechanisms(self, mechanisms: list):
        """Set the current mechanisms from the main application."""
        self.current_mechanisms = mechanisms
        
        # Update preview with mechanisms
        if UI_AVAILABLE and hasattr(self, 'preview_widget'):
            preview_mechs = []
            for i, mech in enumerate(mechanisms):
                preview_mechs.append({
                    'id': f'mech_{i}',
                    'type': mech.get('type', 'unknown'),
                    'bounds': {'width': 50, 'height': 50}
                })
            self.preview_widget.set_mechanisms(preview_mechs)
            
    def generate_base(self):
        """Generate the base based on current configuration."""
        if not self.base_config:
            return
            
        try:
            if self.structured_radio.isChecked():
                # Generate structured base
                generator = StructuredGenerator(self.base_config)
                base_data = generator.generate()
                
                # Adapt mechanisms to base
                adapter = MechanismAdapter(base_data)
                for mech in self.current_mechanisms:
                    adapter.add_mechanism(mech, f"mech_{self.current_mechanisms.index(mech)}")
                    
                self.adapted_design = adapter.adapt()
                
            else:
                # Generate body-mounted design
                generator = BodyCavityGenerator(self.base_config)
                cavity_data = generator.generate()
                
                # Different adaptation for body-mounted
                # This would integrate with the character body data
                self.adapted_design = cavity_data
                
            # Enable export
            self.export_button.setEnabled(True)
            
            # Emit signal for main application
            self.base_configured.emit({
                'type': 'structured' if self.structured_radio.isChecked() else 'body_mounted',
                'config': self.base_config.__dict__,
                'adapted_design': self.adapted_design
            })
            
            # Update preview
            if UI_AVAILABLE:
                self.preview_widget.set_adapted_design(self.adapted_design)
                
        except Exception as e:
            print(f"Error generating base: {e}")
            
    def export_design(self):
        """Export the adapted design."""
        if not self.adapted_design:
            return
            
        # Use ExportManager to handle exports
        exporter = ExportManager(self.adapted_design)
        
        # In real implementation, would show file dialog
        # For now, just export to multiple formats
        output_dir = "./exports"
        
        # Export all formats
        exporter.export_svg(f"{output_dir}/base_design.svg")
        exporter.export_dxf(f"{output_dir}/base_design.dxf")
        exporter.export_json(f"{output_dir}/base_design.json")
        
        print(f"Design exported to {output_dir}")
        

def integrate_with_mechanism_tab(mechanism_tab):
    """
    Function to integrate the base system with existing Mechanism Design tab.
    
    Args:
        mechanism_tab: The existing mechanism design tab widget
    """
    # Add base configuration section
    base_section = AutomataBaseIntegration()
    
    # Insert into mechanism tab layout
    # This would be customized based on actual tab structure
    if hasattr(mechanism_tab, 'layout'):
        mechanism_tab.layout().addWidget(base_section)
        
    # Connect to mechanism updates
    if hasattr(mechanism_tab, 'mechanisms_updated'):
        mechanism_tab.mechanisms_updated.connect(base_section.set_mechanisms)
        
    # Connect base configuration back to main app
    def on_base_configured(base_data):
        # Update mechanism tab with base information
        if hasattr(mechanism_tab, 'set_base_configuration'):
            mechanism_tab.set_base_configuration(base_data)
            
    base_section.base_configured.connect(on_base_configured)
    
    return base_section


if __name__ == "__main__":
    # Example standalone test
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Create integration widget
    widget = AutomataBaseIntegration()
    
    # Add some test mechanisms
    test_mechanisms = [
        {'type': 'fourbar', 'parameters': {}},
        {'type': 'cam', 'parameters': {}},
        {'type': 'gear', 'parameters': {}}
    ]
    widget.set_mechanisms(test_mechanisms)
    
    widget.show()
    sys.exit(app.exec())