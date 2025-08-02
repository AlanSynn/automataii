"""
Parametric Control Revolution - Real-time parameter manipulation with live preview

This module provides revolutionary parametric controls that eliminate the traditional
"adjust-and-apply" workflow. Every parameter change is immediately reflected in the
mechanism visualization with smooth animations and constraint validation.

Features:
- Zero-latency parameter updates with live preview
- Context-sensitive parameter panels that appear on selection
- Parameter constraint visualization with valid ranges
- Parameter lock system for systematic exploration
- Smooth animations between parameter states
- Undo/redo system for parameter changes
"""

import math
import time
from typing import Optional, Dict, List, Tuple, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QFrame, QScrollArea, QToolTip, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal,
    QParallelAnimationGroup, QSequentialAnimationGroup, QRectF
)
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QLinearGradient, QFont,
    QPainterPath, QFontMetrics
)


class ParameterType(Enum):
    """Different types of mechanism parameters"""
    LENGTH = "length"           # Link lengths, distances
    ANGLE = "angle"            # Angles in degrees or radians  
    SPEED = "speed"            # Rotational or linear speeds
    FORCE = "force"            # Applied forces
    MASS = "mass"              # Component masses
    STIFFNESS = "stiffness"    # Spring constants
    DAMPING = "damping"        # Damping coefficients
    COUNT = "count"            # Discrete counts (teeth, etc.)


@dataclass
class ParameterConstraint:
    """Constraint definition for a parameter"""
    min_value: float
    max_value: float
    step_size: float = 0.1
    preferred_range: Tuple[float, float] = None  # Visual emphasis range
    invalid_ranges: List[Tuple[float, float]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # Other parameter names
    
    def __post_init__(self):
        if self.preferred_range is None:
            self.preferred_range = (self.min_value, self.max_value)


@dataclass
class ParameterState:
    """Current state of a parameter including history"""
    name: str
    value: float
    parameter_type: ParameterType
    constraint: ParameterConstraint
    locked: bool = False
    history: List[float] = field(default_factory=list)
    last_change_time: float = field(default_factory=time.time)
    
    def add_to_history(self, value: float):
        """Add value to history with timestamp"""
        self.history.append(value)
        self.last_change_time = time.time()
        
        # Keep history limited to reasonable size
        if len(self.history) > 100:
            self.history = self.history[-50:]  # Keep last 50 changes


class RealTimeSlider(QSlider):
    """
    Enhanced slider with real-time updates and visual constraint feedback.
    
    Features:
    - Live value updates with no apply button needed
    - Visual indication of preferred and invalid ranges
    - Smooth animations between values
    - Context-sensitive tooltips with units and constraints
    """
    
    # Signal emitted on every value change (real-time)
    realTimeValueChanged = pyqtSignal(float)
    
    def __init__(self, parameter_state: ParameterState, parent: Optional[QWidget] = None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        
        self.parameter_state = parameter_state
        self.constraint = parameter_state.constraint
        
        # Setup slider range and precision
        self._setup_slider_range()
        
        # Visual styling
        self.setStyleSheet(self._get_slider_stylesheet())
        
        # Real-time updates
        self.valueChanged.connect(self._on_value_changed)
        
        # Animation for smooth value changes
        self.value_animation = QPropertyAnimation(self, b"value")
        self.value_animation.setDuration(150)
        self.value_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Tooltip system
        self.setMouseTracking(True)
        
    def _setup_slider_range(self):
        """Setup slider range and precision based on parameter constraints"""
        constraint = self.constraint
        
        # Convert to integer range for slider (maintaining precision)
        self.precision_multiplier = int(1.0 / constraint.step_size)
        
        self.setMinimum(int(constraint.min_value * self.precision_multiplier))
        self.setMaximum(int(constraint.max_value * self.precision_multiplier))
        self.setValue(int(self.parameter_state.value * self.precision_multiplier))
        
        # Visual feedback for preferred range
        self.preferred_start = int(constraint.preferred_range[0] * self.precision_multiplier)
        self.preferred_end = int(constraint.preferred_range[1] * self.precision_multiplier)
        
    def _on_value_changed(self, slider_value: int):
        """Handle slider value changes with real-time updates"""
        # Convert back to actual parameter value
        actual_value = slider_value / self.precision_multiplier
        
        # Update parameter state
        self.parameter_state.value = actual_value
        self.parameter_state.add_to_history(actual_value)
        
        # Emit real-time signal
        self.realTimeValueChanged.emit(actual_value)
        
    def set_value_animated(self, value: float):
        """Set slider value with smooth animation"""
        target_slider_value = int(value * self.precision_multiplier)
        
        self.value_animation.setStartValue(self.value())
        self.value_animation.setEndValue(target_slider_value)
        self.value_animation.start()
        
    def _get_slider_stylesheet(self) -> str:
        """Get enhanced stylesheet with constraint visualization"""
        return \"\"\"\n            QSlider::groove:horizontal {\n                border: 1px solid #999;\n                height: 8px;\n                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,\n                    stop:0 #f0f0f0, stop:1 #d0d0d0);\n                margin: 2px 0;\n                border-radius: 4px;\n            }\n            \n            QSlider::handle:horizontal {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,\n                    stop:0 #0d6efd, stop:1 #0b5ed7);\n                border: 1px solid #0a58ca;\n                width: 18px;\n                margin: -2px 0;\n                border-radius: 9px;\n            }\n            \n            QSlider::handle:horizontal:hover {\n                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,\n                    stop:0 #3d8bfd, stop:1 #2c7be5);\n                transform: scale(1.1);\n            }\n            \n            QSlider::sub-page:horizontal {\n                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,\n                    stop:0 #4dabf7, stop:1 #339af0);\n                border: 1px solid #228be6;\n                height: 8px;\n                border-radius: 4px;\n            }\n        \"\"\"\n        \n    def paintEvent(self, event):\n        \"\"\"Custom paint to show constraint visualization\"\"\"\n        super().paintEvent(event)\n        \n        painter = QPainter(self)\n        painter.setRenderHint(QPainter.RenderHint.Antialiasing)\n        \n        # Draw preferred range indicator\n        self._draw_preferred_range(painter)\n        \n        # Draw invalid ranges\n        self._draw_invalid_ranges(painter)\n        \n        # Draw current value tooltip\n        if self.underMouse():\n            self._draw_value_tooltip(painter)\n            \n    def _draw_preferred_range(self, painter: QPainter):\n        \"\"\"Draw visual indicator for preferred parameter range\"\"\"\n        groove_rect = self._get_groove_rect()\n        \n        # Calculate preferred range position\n        total_range = self.maximum() - self.minimum()\n        pref_start_ratio = (self.preferred_start - self.minimum()) / total_range\n        pref_end_ratio = (self.preferred_end - self.minimum()) / total_range\n        \n        pref_start_x = groove_rect.left() + pref_start_ratio * groove_rect.width()\n        pref_end_x = groove_rect.left() + pref_end_ratio * groove_rect.width()\n        \n        # Draw preferred range highlight\n        pref_rect = QRectF(pref_start_x, groove_rect.top() - 2, \n                          pref_end_x - pref_start_x, groove_rect.height() + 4)\n        \n        painter.setBrush(QBrush(QColor(100, 255, 100, 50)))\n        painter.setPen(Qt.PenStyle.NoPen)\n        painter.drawRoundedRect(pref_rect, 2, 2)\n        \n    def _draw_invalid_ranges(self, painter: QPainter):\n        \"\"\"Draw visual indicators for invalid parameter ranges\"\"\"\n        groove_rect = self._get_groove_rect()\n        total_range = self.maximum() - self.minimum()\n        \n        for invalid_start, invalid_end in self.constraint.invalid_ranges:\n            # Convert to slider coordinates\n            start_slider = int(invalid_start * self.precision_multiplier)\n            end_slider = int(invalid_end * self.precision_multiplier)\n            \n            start_ratio = (start_slider - self.minimum()) / total_range\n            end_ratio = (end_slider - self.minimum()) / total_range\n            \n            start_x = groove_rect.left() + start_ratio * groove_rect.width()\n            end_x = groove_rect.left() + end_ratio * groove_rect.width()\n            \n            # Draw invalid range warning\n            invalid_rect = QRectF(start_x, groove_rect.top() - 2,\n                                end_x - start_x, groove_rect.height() + 4)\n            \n            painter.setBrush(QBrush(QColor(255, 100, 100, 80)))\n            painter.setPen(QPen(QColor(255, 0, 0), 1, Qt.PenStyle.DashLine))\n            painter.drawRoundedRect(invalid_rect, 2, 2)\n            \n    def _draw_value_tooltip(self, painter: QPainter):\n        \"\"\"Draw current value tooltip near cursor\"\"\"\n        current_value = self.value() / self.precision_multiplier\n        \n        # Format value based on parameter type\n        if self.parameter_state.parameter_type == ParameterType.ANGLE:\n            text = f\"{current_value:.1f}°\"\n        elif self.parameter_state.parameter_type == ParameterType.LENGTH:\n            text = f\"{current_value:.2f} mm\"\n        elif self.parameter_state.parameter_type == ParameterType.SPEED:\n            text = f\"{current_value:.1f} RPM\"\n        else:\n            text = f\"{current_value:.3f}\"\n            \n        # Draw tooltip background\n        font = QFont(\"Arial\", 10)\n        painter.setFont(font)\n        metrics = QFontMetrics(font)\n        text_rect = metrics.boundingRect(text)\n        \n        tooltip_rect = text_rect.adjusted(-4, -2, 4, 2)\n        tooltip_rect.moveCenter(self.rect().center())\n        tooltip_rect.moveTop(self.rect().top() - 25)\n        \n        painter.setBrush(QBrush(QColor(50, 50, 50, 200)))\n        painter.setPen(Qt.PenStyle.NoPen)\n        painter.drawRoundedRect(tooltip_rect, 3, 3)\n        \n        # Draw tooltip text\n        painter.setPen(QPen(QColor(255, 255, 255)))\n        painter.drawText(tooltip_rect, Qt.AlignmentFlag.AlignCenter, text)\n        \n    def _get_groove_rect(self) -> QRectF:\n        \"\"\"Get the groove rectangle for drawing overlays\"\"\"\n        # Approximate groove rectangle (would need proper calculation)\n        return QRectF(10, self.height()//2 - 4, self.width() - 20, 8)\n\n\nclass ParametricControlPanel(QScrollArea):\n    \"\"\"\n    Revolutionary parametric control panel with context-sensitive controls.\n    \n    Features:\n    - Parameters organized by functional groups\n    - Real-time updates with live mechanism preview\n    - Parameter locking system for systematic exploration\n    - Undo/redo functionality\n    - Export/import parameter configurations\n    - Constraint violation detection and warnings\n    \"\"\"\n    \n    # Signals\n    parameterChanged = pyqtSignal(str, float)  # parameter_name, new_value\n    parameterLocked = pyqtSignal(str, bool)    # parameter_name, locked_state\n    constraintViolated = pyqtSignal(str, str)  # parameter_name, violation_message\n    configurationChanged = pyqtSignal(dict)    # all_parameters\n    \n    def __init__(self, parent: Optional[QWidget] = None):\n        super().__init__(parent)\n        \n        # Parameter management\n        self.parameters: Dict[str, ParameterState] = {}\n        self.parameter_groups: Dict[str, List[str]] = {}\n        self.locked_parameters: set = set()\n        \n        # Undo/redo system\n        self.parameter_history: List[Dict[str, float]] = []\n        self.history_index = -1\n        \n        # UI components\n        self.parameter_widgets: Dict[str, RealTimeSlider] = {}\n        self.group_widgets: Dict[str, QGroupBox] = {}\n        \n        self.setup_ui()\n        \n    def setup_ui(self):\n        \"\"\"Setup the parametric control panel UI\"\"\"\n        self.setWidgetResizable(True)\n        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)\n        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)\n        \n        # Main container\n        self.container = QWidget()\n        self.layout = QVBoxLayout(self.container)\n        self.layout.setContentsMargins(12, 12, 12, 12)\n        self.layout.setSpacing(16)\n        \n        # Title and controls\n        self._create_header()\n        \n        # Parameter groups will be added dynamically\n        self.layout.addStretch()\n        \n        self.setWidget(self.container)\n        \n        # Styling\n        self.setStyleSheet(\"\"\"\n            QScrollArea {\n                border: none;\n                background-color: #f8f9fa;\n            }\n            QGroupBox {\n                font-size: 14px;\n                font-weight: bold;\n                color: #495057;\n                border: 2px solid #dee2e6;\n                border-radius: 8px;\n                margin-top: 12px;\n                padding-top: 12px;\n                background-color: white;\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 12px;\n                padding: 0 8px 0 8px;\n                background-color: white;\n            }\n        \"\"\")\n        \n    def _create_header(self):\n        \"\"\"Create header with global controls\"\"\"\n        header_frame = QFrame()\n        header_layout = QHBoxLayout(header_frame)\n        header_layout.setContentsMargins(0, 0, 0, 0)\n        \n        # Title\n        title = QLabel(\"⚙️ Parameter Controls\")\n        title.setStyleSheet(\"\"\"\n            QLabel {\n                font-size: 18px;\n                font-weight: bold;\n                color: #0d6efd;\n                padding: 8px;\n            }\n        \"\"\")\n        header_layout.addWidget(title)\n        \n        header_layout.addStretch()\n        \n        # Global control buttons\n        self.reset_button = QPushButton(\"🔄 Reset All\")\n        self.lock_all_button = QPushButton(\"🔒 Lock All\")\n        self.undo_button = QPushButton(\"↶ Undo\")\n        self.redo_button = QPushButton(\"↷ Redo\")\n        \n        for btn in [self.reset_button, self.lock_all_button, self.undo_button, self.redo_button]:\n            btn.setStyleSheet(\"\"\"\n                QPushButton {\n                    background-color: #e9ecef;\n                    border: 1px solid #adb5bd;\n                    border-radius: 4px;\n                    padding: 6px 12px;\n                    font-weight: 500;\n                }\n                QPushButton:hover {\n                    background-color: #f8f9fa;\n                    border-color: #6c757d;\n                }\n                QPushButton:pressed {\n                    background-color: #e9ecef;\n                }\n            \"\"\")\n            header_layout.addWidget(btn)\n            \n        # Connect signals\n        self.reset_button.clicked.connect(self.reset_all_parameters)\n        self.lock_all_button.clicked.connect(self.toggle_lock_all)\n        self.undo_button.clicked.connect(self.undo_parameter_change)\n        self.redo_button.clicked.connect(self.redo_parameter_change)\n        \n        self.layout.addWidget(header_frame)\n        \n    def add_parameter_group(self, group_name: str, parameters: List[ParameterState]):\n        \"\"\"Add a group of related parameters\"\"\"\n        # Create group box\n        group_box = QGroupBox(group_name)\n        group_layout = QVBoxLayout(group_box)\n        group_layout.setContentsMargins(16, 20, 16, 16)\n        group_layout.setSpacing(12)\n        \n        # Add parameters to group\n        for param in parameters:\n            self._add_parameter_to_group(param, group_layout)\n            \n        # Store group\n        self.group_widgets[group_name] = group_box\n        self.parameter_groups[group_name] = [p.name for p in parameters]\n        \n        # Add to layout (before stretch)\n        self.layout.insertWidget(self.layout.count() - 1, group_box)\n        \n    def _add_parameter_to_group(self, param: ParameterState, group_layout: QVBoxLayout):\n        \"\"\"Add a single parameter control to a group\"\"\"\n        # Store parameter\n        self.parameters[param.name] = param\n        \n        # Create parameter row\n        param_frame = QFrame()\n        param_layout = QHBoxLayout(param_frame)\n        param_layout.setContentsMargins(0, 0, 0, 0)\n        param_layout.setSpacing(12)\n        \n        # Parameter label with lock button\n        label_frame = QFrame()\n        label_layout = QHBoxLayout(label_frame)\n        label_layout.setContentsMargins(0, 0, 0, 0)\n        label_layout.setSpacing(4)\n        \n        label = QLabel(param.name)\n        label.setMinimumWidth(120)\n        label.setStyleSheet(\"\"\"\n            QLabel {\n                font-weight: 500;\n                color: #495057;\n            }\n        \"\"\")\n        \n        lock_button = QPushButton(\"🔓\")\n        lock_button.setFixedSize(24, 24)\n        lock_button.setCheckable(True)\n        lock_button.setStyleSheet(\"\"\"\n            QPushButton {\n                border: 1px solid #adb5bd;\n                border-radius: 12px;\n                background-color: #f8f9fa;\n                font-size: 12px;\n            }\n            QPushButton:checked {\n                background-color: #ffc107;\n                border-color: #ffb300;\n            }\n        \"\"\")\n        lock_button.toggled.connect(lambda checked: self._toggle_parameter_lock(param.name, checked))\n        \n        label_layout.addWidget(label)\n        label_layout.addWidget(lock_button)\n        label_layout.addStretch()\n        \n        # Real-time slider\n        slider = RealTimeSlider(param)\n        slider.realTimeValueChanged.connect(lambda value: self._on_parameter_changed(param.name, value))\n        \n        # Value spinbox for precise input\n        spinbox = QDoubleSpinBox()\n        spinbox.setRange(param.constraint.min_value, param.constraint.max_value)\n        spinbox.setSingleStep(param.constraint.step_size)\n        spinbox.setDecimals(3)\n        spinbox.setValue(param.value)\n        spinbox.setFixedWidth(80)\n        spinbox.valueChanged.connect(lambda value: self._on_spinbox_changed(param.name, value))\n        \n        # Connect slider and spinbox\n        slider.realTimeValueChanged.connect(lambda value: spinbox.setValue(value))\n        \n        # Store widgets\n        self.parameter_widgets[param.name] = slider\n        \n        # Add to layout\n        param_layout.addWidget(label_frame, 0)\n        param_layout.addWidget(slider, 1)\n        param_layout.addWidget(spinbox, 0)\n        \n        group_layout.addWidget(param_frame)\n        \n    def _on_parameter_changed(self, param_name: str, value: float):\n        \"\"\"Handle parameter change with constraint validation\"\"\"\n        if param_name in self.locked_parameters:\n            return  # Parameter is locked\n            \n        param = self.parameters[param_name]\n        \n        # Validate constraints\n        violation = self._validate_parameter_constraints(param_name, value)\n        if violation:\n            self.constraintViolated.emit(param_name, violation)\n            return\n            \n        # Update parameter state\n        old_value = param.value\n        param.value = value\n        param.add_to_history(value)\n        \n        # Add to undo history\n        self._add_to_history({param_name: old_value})\n        \n        # Emit signals\n        self.parameterChanged.emit(param_name, value)\n        self._emit_configuration_changed()\n        \n    def _on_spinbox_changed(self, param_name: str, value: float):\n        \"\"\"Handle spinbox value change\"\"\"\n        slider = self.parameter_widgets.get(param_name)\n        if slider:\n            slider.set_value_animated(value)\n            \n    def _toggle_parameter_lock(self, param_name: str, locked: bool):\n        \"\"\"Toggle parameter lock state\"\"\"\n        if locked:\n            self.locked_parameters.add(param_name)\n        else:\n            self.locked_parameters.discard(param_name)\n            \n        # Update UI state\n        slider = self.parameter_widgets.get(param_name)\n        if slider:\n            slider.setEnabled(not locked)\n            \n        self.parameterLocked.emit(param_name, locked)\n        \n    def _validate_parameter_constraints(self, param_name: str, value: float) -> Optional[str]:\n        \"\"\"Validate parameter against constraints\"\"\"\n        param = self.parameters[param_name]\n        constraint = param.constraint\n        \n        # Range check\n        if value < constraint.min_value or value > constraint.max_value:\n            return f\"Value {value} is outside valid range [{constraint.min_value}, {constraint.max_value}]\"\n            \n        # Invalid ranges check\n        for invalid_start, invalid_end in constraint.invalid_ranges:\n            if invalid_start <= value <= invalid_end:\n                return f\"Value {value} is in invalid range [{invalid_start}, {invalid_end}]\"\n                \n        # Dependency constraints\n        for dep_param_name in constraint.dependencies:\n            dep_param = self.parameters.get(dep_param_name)\n            if dep_param:\n                # Custom constraint logic would go here\n                pass\n                \n        return None\n        \n    def _add_to_history(self, change: Dict[str, float]):\n        \"\"\"Add parameter change to undo history\"\"\"\n        # Remove any future history if we're not at the end\n        if self.history_index < len(self.parameter_history) - 1:\n            self.parameter_history = self.parameter_history[:self.history_index + 1]\n            \n        self.parameter_history.append(change)\n        self.history_index = len(self.parameter_history) - 1\n        \n        # Limit history size\n        if len(self.parameter_history) > 50:\n            self.parameter_history = self.parameter_history[-25:]\n            self.history_index = len(self.parameter_history) - 1\n            \n        # Update button states\n        self.undo_button.setEnabled(self.history_index >= 0)\n        self.redo_button.setEnabled(self.history_index < len(self.parameter_history) - 1)\n        \n    def _emit_configuration_changed(self):\n        \"\"\"Emit signal with current parameter configuration\"\"\"\n        config = {name: param.value for name, param in self.parameters.items()}\n        self.configurationChanged.emit(config)\n        \n    def reset_all_parameters(self):\n        \"\"\"Reset all parameters to their default values\"\"\"\n        changes = {}\n        \n        for param_name, param in self.parameters.items():\n            if param_name not in self.locked_parameters:\n                # Reset to middle of preferred range\n                default_value = sum(param.constraint.preferred_range) / 2\n                changes[param_name] = param.value\n                param.value = default_value\n                \n                # Update UI\n                slider = self.parameter_widgets.get(param_name)\n                if slider:\n                    slider.set_value_animated(default_value)\n                    \n        if changes:\n            self._add_to_history(changes)\n            self._emit_configuration_changed()\n            \n    def toggle_lock_all(self):\n        \"\"\"Toggle lock state for all parameters\"\"\"\n        if len(self.locked_parameters) == len(self.parameters):\n            # Unlock all\n            for param_name in list(self.locked_parameters):\n                self._toggle_parameter_lock(param_name, False)\n            self.lock_all_button.setText(\"🔒 Lock All\")\n        else:\n            # Lock all\n            for param_name in self.parameters:\n                if param_name not in self.locked_parameters:\n                    self._toggle_parameter_lock(param_name, True)\n            self.lock_all_button.setText(\"🔓 Unlock All\")\n            \n    def undo_parameter_change(self):\n        \"\"\"Undo the last parameter change\"\"\"\n        if self.history_index >= 0:\n            change = self.parameter_history[self.history_index]\n            \n            # Restore previous values\n            for param_name, old_value in change.items():\n                param = self.parameters[param_name]\n                param.value = old_value\n                \n                # Update UI\n                slider = self.parameter_widgets.get(param_name)\n                if slider:\n                    slider.set_value_animated(old_value)\n                    \n            self.history_index -= 1\n            self.undo_button.setEnabled(self.history_index >= 0)\n            self.redo_button.setEnabled(True)\n            \n            self._emit_configuration_changed()\n            \n    def redo_parameter_change(self):\n        \"\"\"Redo the next parameter change\"\"\"\n        if self.history_index < len(self.parameter_history) - 1:\n            self.history_index += 1\n            change = self.parameter_history[self.history_index]\n            \n            # Apply changes (this is the new value, not the old one)\n            # We'd need to store both old and new values for proper redo\n            # For now, this is a placeholder\n            \n            self.undo_button.setEnabled(True)\n            self.redo_button.setEnabled(self.history_index < len(self.parameter_history) - 1)\n            \n    def export_configuration(self) -> Dict[str, Any]:\n        \"\"\"Export current parameter configuration\"\"\"\n        return {\n            'parameters': {name: param.value for name, param in self.parameters.items()},\n            'locked': list(self.locked_parameters),\n            'timestamp': time.time()\n        }\n        \n    def import_configuration(self, config: Dict[str, Any]):\n        \"\"\"Import parameter configuration\"\"\"\n        if 'parameters' not in config:\n            return\n            \n        changes = {}\n        \n        for param_name, value in config['parameters'].items():\n            if param_name in self.parameters:\n                param = self.parameters[param_name]\n                changes[param_name] = param.value\n                param.value = value\n                \n                # Update UI\n                slider = self.parameter_widgets.get(param_name)\n                if slider:\n                    slider.set_value_animated(value)\n                    \n        # Restore lock states\n        if 'locked' in config:\n            for param_name in self.parameters:\n                should_be_locked = param_name in config['locked']\n                is_locked = param_name in self.locked_parameters\n                \n                if should_be_locked != is_locked:\n                    self._toggle_parameter_lock(param_name, should_be_locked)\n                    \n        if changes:\n            self._add_to_history(changes)\n            self._emit_configuration_changed()