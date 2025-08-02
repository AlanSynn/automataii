"""
Parameter Controls Component - Interactive parameter manipulation widgets

Provides sophisticated parameter control widgets for mechanism experimentation:
- Sliders with real-time feedback
- Spinboxes for precise numeric input
- Parameter grouping and organization
- Value constraints and validation
- Change event handling
"""

from typing import Optional, Dict, List, Callable, Any, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QSlider, QSpinBox, QDoubleSpinBox, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont


class ParameterSlider(QWidget):
    """Combined slider and spinbox parameter control"""
    
    valueChanged = pyqtSignal(float)  # New value
    
    def __init__(self, 
                 name: str,
                 min_value: float,
                 max_value: float,
                 initial_value: float,
                 step: float = 1.0,
                 unit: str = "",
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.name = name
        self.min_value = min_value
        self.max_value = max_value
        self.step = step
        self.unit = unit
        self.is_updating = False
        
        self.setup_ui()
        self.set_value(initial_value)
        
    def setup_ui(self):
        """Setup the parameter control UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # Parameter name and value display
        header_layout = QHBoxLayout()
        
        name_label = QLabel(self.name)
        name_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 500;
                color: #495057;
            }
        """)
        
        self.value_label = QLabel()
        self.value_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #0d6efd;
                font-weight: bold;
                min-width: 50px;
            }
        """)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(self.value_label)
        
        # Control widgets layout
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        
        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #ced4da;
                height: 6px;
                background: #f8f9fa;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0d6efd;
                border: 1px solid #0d6efd;
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -6px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #0b5ed7;
                border-color: #0b5ed7;
            }
            QSlider::sub-page:horizontal {
                background: #0d6efd;
                border-radius: 3px;
            }
        """)
        
        # Convert float range to integer range for slider
        self.slider_scale = 1000  # Scale factor for precision
        self.slider.setMinimum(int(self.min_value * self.slider_scale))
        self.slider.setMaximum(int(self.max_value * self.slider_scale))
        
        # Spinbox (use QDoubleSpinBox for float values)
        if self.step < 1.0 or self.min_value != int(self.min_value) or self.max_value != int(self.max_value):
            self.spinbox = QDoubleSpinBox()
            self.spinbox.setDecimals(2 if self.step >= 0.01 else 3)
            self.spinbox.setSingleStep(self.step)
            self.spinbox.setMinimum(self.min_value)
            self.spinbox.setMaximum(self.max_value)
        else:
            self.spinbox = QSpinBox()
            self.spinbox.setSingleStep(int(self.step))
            self.spinbox.setMinimum(int(self.min_value))
            self.spinbox.setMaximum(int(self.max_value))
        self.spinbox.setStyleSheet("""
            QSpinBox, QDoubleSpinBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                background-color: white;
                min-width: 60px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #0d6efd;
                outline: none;
            }
        """)
        
        controls_layout.addWidget(self.slider, 1)
        controls_layout.addWidget(self.spinbox)
        
        layout.addLayout(header_layout)
        layout.addLayout(controls_layout)
        
        # Connect signals
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.spinbox.valueChanged.connect(self.on_spinbox_changed)
        
    def set_value(self, value: float):
        """Set the parameter value"""
        if self.is_updating:
            return
            
        self.is_updating = True
        
        # Constrain value to valid range
        value = max(self.min_value, min(self.max_value, value))
        
        # Update slider
        slider_value = int(value * self.slider_scale)
        self.slider.setValue(slider_value)
        
        # Update spinbox
        if isinstance(self.spinbox, QSpinBox):
            self.spinbox.setValue(int(value))
        else:
            self.spinbox.setValue(value)
        
        # Update value display
        if self.unit:
            self.value_label.setText(f"{value:.2f} {self.unit}")
        else:
            self.value_label.setText(f"{value:.2f}")
            
        self.is_updating = False
        
    def get_value(self) -> float:
        """Get the current parameter value"""
        return float(self.spinbox.value())
        
    def on_slider_changed(self, slider_value: int):
        """Handle slider value changes"""
        if self.is_updating:
            return
            
        value = slider_value / self.slider_scale
        self.set_value(value)
        self.valueChanged.emit(value)
        
    def on_spinbox_changed(self, value):
        """Handle spinbox value changes"""
        if self.is_updating:
            return
            
        float_value = float(value)
        self.set_value(float_value)
        self.valueChanged.emit(float_value)


class ParameterGroup(QGroupBox):
    """Group of related parameters"""
    
    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(title, parent)
        self.parameters = {}
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the parameter group UI"""
        self.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #495057;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: white;
            }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 16, 12, 12)
        self.layout.setSpacing(8)
        
    def add_parameter(self, 
                     name: str,
                     min_value: float,
                     max_value: float,
                     initial_value: float,
                     step: float = 1.0,
                     unit: str = "",
                     callback: Optional[Callable[[float], None]] = None) -> ParameterSlider:
        """Add a parameter to the group"""
        param = ParameterSlider(name, min_value, max_value, initial_value, step, unit)
        
        if callback:
            param.valueChanged.connect(callback)
            
        self.parameters[name] = param
        self.layout.addWidget(param)
        
        return param
        
    def get_parameter_value(self, name: str) -> Optional[float]:
        """Get value of a specific parameter"""
        param = self.parameters.get(name)
        return param.get_value() if param else None
        
    def set_parameter_value(self, name: str, value: float):
        """Set value of a specific parameter"""
        param = self.parameters.get(name)
        if param:
            param.set_value(value)
            
    def get_all_values(self) -> Dict[str, float]:
        """Get all parameter values as a dictionary"""
        return {name: param.get_value() for name, param in self.parameters.items()}


class ParameterControls(QWidget):
    """
    Main parameter controls widget providing organized parameter manipulation.
    
    Features:
    - Grouped parameter organization
    - Real-time value updates
    - Slider and spinbox combination
    - Value constraints and validation
    - Batch parameter updates
    - Preset management
    """
    
    parametersChanged = pyqtSignal(dict)  # All parameter values
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.groups = {}
        self.parameter_name_mapping = {}  # Maps display names to original names
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.emit_parameters_changed)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the parameter controls UI"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(12)
        
        # Add stretch at the end to push groups to top
        self.layout.addStretch()
        
    def add_group(self, title: str) -> ParameterGroup:
        """Add a parameter group"""
        group = ParameterGroup(title)
        self.groups[title] = group
        
        # Insert before the stretch
        self.layout.insertWidget(self.layout.count() - 1, group)
        
        return group
        
    def add_parameter(self,
                     group_title: str,
                     param_name: str,
                     min_value: float,
                     max_value: float,
                     initial_value: float,
                     step: float = 1.0,
                     unit: str = "") -> ParameterSlider:
        """Add a parameter to a specific group"""
        # Create group if it doesn't exist
        if group_title not in self.groups:
            self.add_group(group_title)
            
        group = self.groups[group_title]
        param = group.add_parameter(
            param_name, min_value, max_value, initial_value, step, unit,
            callback=self.on_parameter_changed
        )
        
        return param
        
    def on_parameter_changed(self, value: float):
        """Handle individual parameter changes with debouncing"""
        # Use timer to debounce rapid changes
        self.update_timer.start(50)  # 50ms delay
        
    def emit_parameters_changed(self):
        """Emit the parametersChanged signal with all current values"""
        all_values = {}
        for group_title, group in self.groups.items():
            group_values = group.get_all_values()
            # Map display names back to original parameter names for mechanism service compatibility
            for display_name, value in group_values.items():
                original_name = self.parameter_name_mapping.get(display_name, display_name)
                all_values[original_name] = value
                
        self.parametersChanged.emit(all_values)
        
    def get_parameter_value(self, group_title: str, param_name: str) -> Optional[float]:
        """Get value of a specific parameter"""
        group = self.groups.get(group_title)
        return group.get_parameter_value(param_name) if group else None
        
    def set_parameter_value(self, group_title: str, param_name: str, value: float):
        """Set value of a specific parameter"""
        group = self.groups.get(group_title)
        if group:
            group.set_parameter_value(param_name, value)
            
    def get_all_values(self) -> Dict[str, float]:
        """Get all parameter values"""
        all_values = {}
        for group_title, group in self.groups.items():
            group_values = group.get_all_values()
            for param_name, value in group_values.items():
                all_values[f"{group_title}.{param_name}"] = value
        return all_values
        
    def set_mechanism_parameters(self, mechanism_data: Dict):
        """Configure parameters based on mechanism type"""
        # Clear existing parameters
        for group in self.groups.values():
            group.setParent(None)
        self.groups.clear()
        
        mechanism_name = mechanism_data.get('name', '').lower()
        
        if 'four-bar' in mechanism_name or 'linkage' in mechanism_name:
            self.setup_linkage_parameters()
        elif 'gear' in mechanism_name:
            self.setup_gear_parameters()
        elif 'cam' in mechanism_name:
            self.setup_cam_parameters()
        elif 'spring' in mechanism_name:
            self.setup_spring_parameters()
        else:
            self.setup_generic_parameters()
            
    def setup_linkage_parameters(self):
        """Setup parameters for linkage mechanisms"""
        # Link lengths
        self.add_parameter("Link Lengths", "Link 1 (Ground)", 80, 120, 100, 1, "mm")
        self.add_parameter("Link Lengths", "Link 2 (Input)", 40, 80, 60, 1, "mm")
        self.add_parameter("Link Lengths", "Link 3 (Coupler)", 60, 100, 80, 1, "mm")
        self.add_parameter("Link Lengths", "Link 4 (Output)", 50, 90, 70, 1, "mm")
        
        # Motion parameters
        self.add_parameter("Motion", "Input Speed", 10, 120, 60, 5, "rpm")
        self.add_parameter("Motion", "Input Angle", 0, 360, 0, 1, "°")
        
        # Analysis options
        self.add_parameter("Analysis", "Coupler Point X", -20, 20, 0, 1, "mm")
        self.add_parameter("Analysis", "Coupler Point Y", -20, 20, 0, 1, "mm")
        
    def setup_gear_parameters(self):
        """Setup parameters for gear mechanisms"""
        # Gear specifications
        self.add_parameter("Gear 1", "Teeth Count", 12, 60, 24, 1, "teeth")
        self.add_parameter("Gear 1", "Module", 1, 5, 2, 0.5, "mm")
        
        self.add_parameter("Gear 2", "Teeth Count", 12, 60, 36, 1, "teeth")
        self.add_parameter("Gear 2", "Module", 1, 5, 2, 0.5, "mm")
        
        # Motion parameters
        self.add_parameter("Motion", "Input Speed", 10, 300, 100, 10, "rpm")
        
    def setup_cam_parameters(self):
        """Setup parameters for cam mechanisms"""
        # Cam geometry
        self.add_parameter("Cam Profile", "Base Radius", 20, 50, 30, 1, "mm")
        self.add_parameter("Cam Profile", "Lift Height", 5, 25, 15, 1, "mm")
        self.add_parameter("Cam Profile", "Rise Angle", 60, 180, 120, 5, "°")
        self.add_parameter("Cam Profile", "Dwell Angle", 30, 120, 60, 5, "°")
        
        # Motion parameters
        self.add_parameter("Motion", "Cam Speed", 10, 180, 60, 5, "rpm")
        
    def setup_spring_parameters(self):
        """Setup parameters for spring mechanisms"""
        # Spring properties
        self.add_parameter("Spring", "Spring Constant", 10, 100, 50, 5, "N/mm")
        self.add_parameter("Spring", "Free Length", 50, 150, 100, 5, "mm")
        self.add_parameter("Spring", "Wire Diameter", 1, 5, 2, 0.1, "mm")
        
        # Loading
        self.add_parameter("Loading", "Applied Force", 0, 500, 100, 10, "N")
        self.add_parameter("Loading", "Displacement", 0, 50, 10, 1, "mm")
        
    def setup_generic_parameters(self):
        """Setup generic parameters for unknown mechanisms"""
        # Basic motion parameters
        self.add_parameter("Motion", "Speed", 10, 200, 60, 5, "rpm")
        self.add_parameter("Motion", "Amplitude", 10, 100, 50, 5, "mm")
        
        # Geometry
        self.add_parameter("Geometry", "Scale Factor", 0.5, 2.0, 1.0, 0.1, "×")
        
    def configure_for_mechanism(self, param_info: Dict[str, Dict[str, Any]]):
        """Configure parameters based on mechanism parameter info from MechanismService"""
        # Clear existing parameters
        for group in self.groups.values():
            group.setParent(None)
        self.groups.clear()
        self.parameter_name_mapping.clear()
        
        if not param_info:
            return
            
        # Group parameters by type or use a default group
        main_group = self.add_group("Parameters")
        
        for param_name, info in param_info.items():
            # Extract parameter info
            current_value = info.get('current_value', 0.0)
            min_value = info.get('min_value', 0.0)
            max_value = info.get('max_value', 100.0)
            step_size = info.get('step_size', 1.0)
            param_type = info.get('parameter_type', 'dimensionless')
            
            # Determine unit based on parameter type
            unit = ""
            if param_type == "length":
                unit = "mm"
            elif param_type == "angle":
                unit = "°"
            elif param_type == "speed":
                unit = "rpm"
            elif param_type == "force":
                unit = "N"
                
            # Create display name and store mapping
            display_name = param_name.replace('_', ' ').title()
            self.parameter_name_mapping[display_name] = param_name
                
            # Add parameter to main group
            main_group.add_parameter(
                display_name,
                min_value,
                max_value,
                current_value,
                step_size,
                unit,
                callback=self.on_parameter_changed
            )
            
    def update_parameter_value(self, param_name: str, value: float):
        """Update a specific parameter value (for interactive updates)"""
        # Look for the parameter in all groups
        for group in self.groups.values():
            # Check if parameter exists in this group (with formatted name)
            formatted_name = param_name.replace('_', ' ').title()
            if formatted_name in group.parameters:
                group.set_parameter_value(formatted_name, value)
                return
                
        # If not found with formatted name, try original name
        for group in self.groups.values():
            if param_name in group.parameters:
                group.set_parameter_value(param_name, value)
                return