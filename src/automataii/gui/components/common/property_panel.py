"""Part properties panel component."""

import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QFormLayout, 
    QDoubleSpinBox, QCheckBox, QLabel
)
from PyQt6.QtCore import pyqtSignal


class PartPropertiesPanel(QGroupBox):
    """Reusable part properties panel.
    
    This component displays and allows editing of part properties
    such as Z-order and fixed state.
    """
    
    # Signals
    z_value_changed = pyqtSignal(str, float)  # part_name, z_value
    fixed_state_changed = pyqtSignal(str, bool)  # part_name, is_fixed
    
    def __init__(self, parent=None):
        super().__init__("Part Properties", parent)
        
        self._current_part: Optional[str] = None
        self._part_info: Optional[Dict[str, Any]] = None
        
        self._init_ui()
        self._connect_signals()
        
        # Start disabled
        self.setEnabled(False)
    
    def _init_ui(self) -> None:
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        
        # Create form layout for properties
        form_layout = QFormLayout()
        form_layout.setSpacing(8)
        
        # Part name label
        self.part_name_label = QLabel("No part selected")
        self.part_name_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow("Part:", self.part_name_label)
        
        # Z-Value spinner
        self.z_value_spin = QDoubleSpinBox()
        self.z_value_spin.setRange(-1000, 1000)
        self.z_value_spin.setSingleStep(0.1)
        self.z_value_spin.setDecimals(1)
        self.z_value_spin.setValue(0)
        self.z_value_spin.setToolTip("Z-order value (higher values appear on top)")
        form_layout.addRow("Z-Order:", self.z_value_spin)
        
        # Fixed checkbox
        self.fixed_check = QCheckBox()
        self.fixed_check.setToolTip("Whether this part is fixed in place")
        form_layout.addRow("Fixed:", self.fixed_check)
        
        # Additional info labels
        self.info_labels = {}
        
        # Add form to main layout
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # Apply styling
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                background-color: white;
            }
            QLabel {
                font-weight: normal;
            }
        """)
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.z_value_spin.valueChanged.connect(self._on_z_value_changed)
        self.fixed_check.stateChanged.connect(self._on_fixed_state_changed)
    
    def load_part(self, part_name: str, part_info: Dict[str, Any]) -> None:
        """Load a part's properties for editing.
        
        Args:
            part_name: Name of the part
            part_info: Part information dictionary
        """
        self._current_part = part_name
        self._part_info = part_info
        
        # Update UI
        self.setEnabled(True)
        
        # Update part name
        display_name = part_name.replace('_', ' ').title()
        self.part_name_label.setText(display_name)
        
        # Block signals while updating values
        self.z_value_spin.blockSignals(True)
        self.fixed_check.blockSignals(True)
        
        # Update values
        z_value = part_info.get('z_value', 0.0)
        if hasattr(part_info, 'z_value'):
            z_value = part_info.z_value
        self.z_value_spin.setValue(z_value)
        
        is_fixed = part_info.get('fixed', False)
        if hasattr(part_info, 'fixed'):
            is_fixed = part_info.fixed
        self.fixed_check.setChecked(is_fixed)
        
        # Re-enable signals
        self.z_value_spin.blockSignals(False)
        self.fixed_check.blockSignals(False)
        
        # Update additional info
        self._update_info_labels(part_info)
        
        logging.debug(f"PartPropertiesPanel: Loaded part '{part_name}'")
    
    def clear_part(self) -> None:
        """Clear the current part."""
        self._current_part = None
        self._part_info = None
        
        # Update UI
        self.setEnabled(False)
        self.part_name_label.setText("No part selected")
        
        # Reset values
        self.z_value_spin.blockSignals(True)
        self.fixed_check.blockSignals(True)
        
        self.z_value_spin.setValue(0)
        self.fixed_check.setChecked(False)
        
        self.z_value_spin.blockSignals(False)
        self.fixed_check.blockSignals(False)
        
        # Clear info labels
        for label in self.info_labels.values():
            label.deleteLater()
        self.info_labels.clear()
        
        logging.debug("PartPropertiesPanel: Cleared part")
    
    def get_current_part(self) -> Optional[str]:
        """Get the current part name.
        
        Returns:
            Current part name or None
        """
        return self._current_part
    
    def get_z_value(self) -> float:
        """Get the current Z-value.
        
        Returns:
            Current Z-value
        """
        return self.z_value_spin.value()
    
    def get_fixed_state(self) -> bool:
        """Get the current fixed state.
        
        Returns:
            Current fixed state
        """
        return self.fixed_check.isChecked()
    
    def update_property(self, property_name: str, value: Any) -> None:
        """Update a specific property value.
        
        Args:
            property_name: Name of the property
            value: New value
        """
        if not self._current_part:
            return
        
        if property_name == 'z_value':
            self.z_value_spin.blockSignals(True)
            self.z_value_spin.setValue(float(value))
            self.z_value_spin.blockSignals(False)
        elif property_name == 'fixed':
            self.fixed_check.blockSignals(True)
            self.fixed_check.setChecked(bool(value))
            self.fixed_check.blockSignals(False)
        
        # Update internal info
        if self._part_info:
            self._part_info[property_name] = value
    
    def _update_info_labels(self, part_info: Dict[str, Any]) -> None:
        """Update additional info labels.
        
        Args:
            part_info: Part information
        """
        # Clear existing labels
        for label in self.info_labels.values():
            label.deleteLater()
        self.info_labels.clear()
        
        # Add labels for additional properties
        layout = self.layout()
        if isinstance(layout, QVBoxLayout) and layout.count() > 0:
            form_layout = layout.itemAt(0).layout()
            if isinstance(form_layout, QFormLayout):
                # Add additional properties
                if 'anchor_joint' in part_info:
                    label = QLabel(str(part_info['anchor_joint']))
                    form_layout.addRow("Anchor:", label)
                    self.info_labels['anchor'] = label
                
                if 'motion_path' in part_info and part_info['motion_path']:
                    label = QLabel("Yes")
                    label.setStyleSheet("color: green;")
                    form_layout.addRow("Has Path:", label)
                    self.info_labels['has_path'] = label
    
    def _on_z_value_changed(self, value: float) -> None:
        """Handle Z-value change.
        
        Args:
            value: New Z-value
        """
        if self._current_part:
            self.z_value_changed.emit(self._current_part, value)
            logging.debug(f"PartPropertiesPanel: Z-value changed to {value} for '{self._current_part}'")
    
    def _on_fixed_state_changed(self, state: int) -> None:
        """Handle fixed state change.
        
        Args:
            state: Check state
        """
        if self._current_part:
            is_fixed = state == 2  # Qt.CheckState.Checked
            self.fixed_state_changed.emit(self._current_part, is_fixed)
            logging.debug(f"PartPropertiesPanel: Fixed state changed to {is_fixed} for '{self._current_part}'")