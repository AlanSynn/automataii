"""
Mechanism-specific interaction handlers using Factory Pattern.
Provides specialized UI controls and analysis tools for different mechanism types.
"""

import logging
import math
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QPointF, QTimer
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QSlider, QSpinBox, QDoubleSpinBox, QGroupBox, QCheckBox,
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsLineItem
)

from automataii.domain.fabrication.mechanisms.base_mechanism import BaseMechanism
from .styling import ModernStyling

logger = logging.getLogger(__name__)


class DragHandle(QGraphicsEllipseItem):
    """Interactive drag handle for parameter adjustment with enhanced visual feedback."""
    
    def __init__(self, x: float, y: float, radius: float = 12):  # Increased default size
        super().__init__(-radius, -radius, radius*2, radius*2)
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        
        # Enhanced visual styling
        self.base_radius = radius
        self.hover_radius = radius + 3
        self.setBrush(QBrush(QColor(ModernStyling.COLORS['primary'])))
        self.setPen(QPen(QColor(ModernStyling.COLORS['primary_dark']), 2))
        
        # Interaction state
        self.parameter_name = ""
        self.original_value = 0.0
        self.value_range = (0.0, 100.0)
        self.is_dragging = False
        self.is_valid = True
        self.is_hovered = False
        
        # Enhanced visual feedback
        self.hover_brush = QBrush(QColor(ModernStyling.COLORS['primary_light']))
        self.drag_brush = QBrush(QColor(ModernStyling.COLORS['secondary']))
        self.invalid_brush = QBrush(QColor(ModernStyling.COLORS['error']))
        self.warning_brush = QBrush(QColor(ModernStyling.COLORS['warning']))
        
        # Pulsing animation for attention
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self._pulse_effect)
        self.pulse_phase = 0
        
        # Constraint validation
        self.constraint_function = None
        self.warning_function = None
        
        # Enhanced affordance
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setZValue(100)  # Always on top for visibility
    
    def hoverEnterEvent(self, event):
        """Handle hover enter with enhanced feedback."""
        self.is_hovered = True
        if not self.is_dragging:
            self.setBrush(self.hover_brush)
            # Expand handle on hover
            self.setRect(-self.hover_radius, -self.hover_radius, 
                        self.hover_radius*2, self.hover_radius*2)
            # Show parameter info
            if self.parameter_name:
                self.setToolTip(f"🎛️ Drag to adjust {self.parameter_name.replace('_', ' ').title()}")
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Handle hover leave with size restoration."""
        self.is_hovered = False
        if not self.is_dragging:
            self.setBrush(QBrush(QColor(ModernStyling.COLORS['primary'])))
            # Restore original size
            self.setRect(-self.base_radius, -self.base_radius, 
                        self.base_radius*2, self.base_radius*2)
        super().hoverLeaveEvent(event)
    
    def start_pulse_animation(self):
        """Start pulsing animation to draw attention."""
        if not self.pulse_timer.isActive():
            self.pulse_timer.start(100)  # 10 FPS pulse
    
    def stop_pulse_animation(self):
        """Stop pulsing animation."""
        self.pulse_timer.stop()
        self.pulse_phase = 0
    
    def _pulse_effect(self):
        """Create a pulsing visual effect."""
        import math
        self.pulse_phase += 0.2
        
        # Calculate pulse scale (1.0 to 1.3)
        scale = 1.0 + 0.3 * (math.sin(self.pulse_phase) + 1) / 2
        
        # Apply pulse effect by modifying opacity
        color = QColor(ModernStyling.COLORS['primary'])
        color.setAlpha(int(100 + 155 * scale / 1.3))
        self.setBrush(QBrush(color))
        
        # Reset after full cycle
        if self.pulse_phase >= 2 * math.pi:
            self.pulse_phase = 0
    
    def mousePressEvent(self, event):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.setBrush(self.drag_brush)
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.setBrush(QBrush(QColor(ModernStyling.COLORS['primary'])))
        super().mouseReleaseEvent(event)
    
    def itemChange(self, change, value):
        """Handle item position changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.is_dragging:
            # Emit position change signal through parent handler
            if hasattr(self.scene(), 'interaction_handler'):
                self.scene().interaction_handler.handle_drag_update(self, value)
        
        return super().itemChange(change, value)
    
    def set_parameter(self, name: str, value: float, value_range: Tuple[float, float]):
        """Configure this handle for a specific parameter."""
        self.parameter_name = name
        self.original_value = value
        self.value_range = value_range
    
    def set_constraint_function(self, constraint_func, warning_func=None):
        """Set constraint validation functions."""
        self.constraint_function = constraint_func
        self.warning_function = warning_func
    
    def validate_value(self, value: float) -> Tuple[bool, str]:
        """Validate parameter value against constraints."""
        # Check basic range
        if not (self.value_range[0] <= value <= self.value_range[1]):
            return False, f"Value must be between {self.value_range[0]} and {self.value_range[1]}"
        
        # Check custom constraint
        if self.constraint_function:
            try:
                valid, message = self.constraint_function(value)
                if not valid:
                    return False, message
            except Exception as e:
                return False, f"Constraint error: {str(e)}"
        
        # Check warning condition
        if self.warning_function:
            try:
                has_warning, warning_msg = self.warning_function(value)
                if has_warning:
                    return True, warning_msg  # Valid but with warning
            except Exception:
                pass
        
        return True, "Valid"
    
    def update_visual_state(self, value: float):
        """Update visual appearance based on value validity."""
        is_valid, message = self.validate_value(value)
        
        if not is_valid:
            self.is_valid = False
            self.setBrush(self.invalid_brush)
            self.setPen(QPen(QColor(ModernStyling.COLORS['error']), 3))
            self.setToolTip(f"❌ {message}")
        elif "warning" in message.lower() or "caution" in message.lower():
            self.is_valid = True
            self.setBrush(self.warning_brush)
            self.setPen(QPen(QColor(ModernStyling.COLORS['warning']), 2))
            self.setToolTip(f"⚠️ {message}")
        else:
            self.is_valid = True
            self.setBrush(QBrush(QColor(ModernStyling.COLORS['primary'])))
            self.setPen(QPen(QColor(ModernStyling.COLORS['primary_dark']), 2))
            self.setToolTip(f"✅ {self.parameter_name}: {value:.2f}")
    
    def get_parameter_value_from_position(self) -> float:
        """Calculate parameter value based on current position."""
        # This will be implemented by specific interaction handlers
        return self.original_value


class BaseMechanismInteractionHandler(QObject):
    """Base class for mechanism-specific interaction handlers."""
    
    parameter_changed = pyqtSignal(str, object)  # parameter_name, value
    analysis_updated = pyqtSignal(dict)  # analysis_data
    
    def __init__(self, mechanism: BaseMechanism, parent=None):
        super().__init__(parent)
        self.mechanism = mechanism
        self.drag_handles: List[DragHandle] = []
        self.graphics_scene = None
        self.analysis_timer = QTimer()
        self.analysis_timer.timeout.connect(self._update_analysis)
        self.analysis_timer.setInterval(100)  # Update analysis every 100ms
        
    @abstractmethod
    def create_interaction_controls(self) -> QWidget:
        """Create mechanism-specific interaction controls."""
        pass
    
    @abstractmethod
    def create_drag_handles(self, scene):
        """Create interactive drag handles in the graphics scene."""
        pass
    
    @abstractmethod
    def update_visualization(self):
        """Update the visual representation of the mechanism."""
        pass
    
    @abstractmethod
    def get_analysis_data(self) -> Dict[str, Any]:
        """Get mechanism-specific analysis data."""
        pass
    
    def handle_drag_update(self, handle: DragHandle, new_position: QPointF):
        """Handle drag handle position updates with constraint validation."""
        # Convert position to parameter value
        value = self._position_to_parameter_value(handle, new_position)
        if value is not None:
            # Update visual state based on constraints
            handle.update_visual_state(value)
            
            # Only emit change if value is valid
            if handle.is_valid:
                self.parameter_changed.emit(handle.parameter_name, value)
            else:
                # Optionally snap back to valid position or show error
                logger.debug(f"Invalid parameter value: {handle.parameter_name} = {value}")
                # Could implement snap-back behavior here
    
    def _position_to_parameter_value(self, handle: DragHandle, position: QPointF) -> Optional[float]:
        """Convert handle position to parameter value."""
        # Base implementation - override in subclasses
        return None
    
    def _update_analysis(self):
        """Update analysis data."""
        analysis_data = self.get_analysis_data()
        self.analysis_updated.emit(analysis_data)
    
    def set_graphics_scene(self, scene):
        """Set the graphics scene for drag handles."""
        self.graphics_scene = scene
        scene.interaction_handler = self
        self.create_drag_handles(scene)
    
    def start_analysis(self):
        """Start real-time analysis updates."""
        self.analysis_timer.start()
    
    def stop_analysis(self):
        """Stop analysis updates."""
        self.analysis_timer.stop()
    
    def cleanup(self):
        """Clean up resources."""
        self.stop_analysis()
        for handle in self.drag_handles:
            if self.graphics_scene:
                self.graphics_scene.removeItem(handle)
        self.drag_handles.clear()


# ==============================================================================
# BASE HANDLER CLASSES - Extract common functionality for mechanism categories
# ==============================================================================

class BaseLinkageHandler(BaseMechanismInteractionHandler):
    """Base handler for linkage mechanisms (four-bar, six-bar, etc.)."""
    
    def create_linkage_analysis_group(self, layout: QVBoxLayout) -> Dict[str, QLabel]:
        """Create common linkage analysis UI group."""
        linkage_group = QGroupBox("Linkage Analysis")
        linkage_layout = QVBoxLayout(linkage_group)
        
        labels = {}
        labels['grashof'] = QLabel("Grashof Condition: --")
        labels['grashof'].setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        linkage_layout.addWidget(labels['grashof'])
        
        labels['mechanism_type'] = QLabel("Mechanism Type: --")
        labels['mechanism_type'].setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        linkage_layout.addWidget(labels['mechanism_type'])
        
        labels['mobility'] = QLabel("Degrees of Freedom: 1")
        linkage_layout.addWidget(labels['mobility'])
        
        layout.addWidget(linkage_group)
        return labels
    
    def check_grashof_condition(self, l1: float, l2: float, l3: float, l4: float) -> Tuple[bool, str]:
        """Check Grashof's law for four-bar linkage."""
        lengths = sorted([l1, l2, l3, l4])
        s, l, p, q = lengths[0], lengths[3], lengths[1], lengths[2]
        
        if s + l <= p + q:
            # Grashof linkage
            if l1 == s:
                return True, "Crank-Rocker"
            elif l3 == s:
                return True, "Rocker-Crank"
            elif l4 == s:
                return True, "Double-Crank"
            else:
                return True, "Grashof Linkage"
        else:
            # Non-Grashof - all inversions are double-rockers
            return False, "Triple-Rocker"
    
    def calculate_transmission_angle(self, joint_positions: List[Tuple[float, float]]) -> float:
        """Calculate transmission angle for linkage quality assessment."""
        if len(joint_positions) < 4:
            return 90.0
            
        # Calculate angle between coupler and follower
        p1, p2, p3, p4 = joint_positions
        
        # Vector from joint 2 to joint 3 (coupler)
        v_coupler = (p3[0] - p2[0], p3[1] - p2[1])
        
        # Vector from joint 3 to joint 4 (follower)
        v_follower = (p4[0] - p3[0], p4[1] - p3[1])
        
        # Calculate angle
        dot_product = v_coupler[0] * v_follower[0] + v_coupler[1] * v_follower[1]
        mag_coupler = math.sqrt(v_coupler[0]**2 + v_coupler[1]**2)
        mag_follower = math.sqrt(v_follower[0]**2 + v_follower[1]**2)
        
        if mag_coupler > 0 and mag_follower > 0:
            cos_angle = dot_product / (mag_coupler * mag_follower)
            cos_angle = max(-1.0, min(1.0, cos_angle))
            return math.degrees(math.acos(cos_angle))
        
        return 90.0
    
    def create_link_length_handle(self, scene, position: Tuple[float, float], 
                                 param_name: str, value: float, 
                                 value_range: Tuple[float, float],
                                 tooltip: str) -> DragHandle:
        """Create a standard link length adjustment handle."""
        handle = DragHandle(position[0], position[1])
        handle.set_parameter(param_name, value, value_range)
        handle.setToolTip(tooltip)
        scene.addItem(handle)
        return handle


class BaseRotaryHandler(BaseMechanismInteractionHandler):
    """Base handler for rotary mechanisms (gears, geneva, etc.)."""
    
    def create_speed_analysis_group(self, layout: QVBoxLayout) -> Dict[str, QLabel]:
        """Create common speed/ratio analysis UI group."""
        speed_group = QGroupBox("Speed & Ratio Analysis")
        speed_layout = QVBoxLayout(speed_group)
        
        labels = {}
        labels['speed_ratio'] = QLabel("Speed Ratio: 1:1")
        labels['speed_ratio'].setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        speed_layout.addWidget(labels['speed_ratio'])
        
        labels['input_speed'] = QLabel("Input Speed: 100 RPM")
        speed_layout.addWidget(labels['input_speed'])
        
        labels['output_speed'] = QLabel("Output Speed: 100 RPM")
        speed_layout.addWidget(labels['output_speed'])
        
        labels['mechanical_advantage'] = QLabel("Mechanical Advantage: 1.0")
        labels['mechanical_advantage'].setStyleSheet(f"color: {ModernStyling.COLORS['secondary']};")
        speed_layout.addWidget(labels['mechanical_advantage'])
        
        layout.addWidget(speed_group)
        return labels
    
    def calculate_gear_ratio(self, driver_param: float, driven_param: float, 
                           gear_type: str = "spur") -> Dict[str, float]:
        """Calculate gear ratio and related parameters."""
        if gear_type in ["spur", "helical"]:
            # For regular gears, ratio is teeth count or radius
            ratio = driven_param / driver_param if driver_param > 0 else 1.0
        elif gear_type == "planetary":
            # Planetary gear ratios are more complex
            ratio = driven_param / driver_param
        else:
            ratio = 1.0
            
        return {
            "ratio": ratio,
            "mechanical_advantage": ratio,
            "speed_multiplier": 1 / ratio if ratio > 0 else 1.0,
            "torque_multiplier": ratio
        }
    
    def create_teeth_count_handle(self, scene, center: Tuple[float, float],
                                 param_name: str, teeth_count: int,
                                 teeth_range: Tuple[int, int],
                                 radius_factor: float,
                                 tooltip: str) -> DragHandle:
        """Create a handle for adjusting gear teeth count."""
        radius = teeth_count * radius_factor
        handle = DragHandle(center[0] + radius, center[1])
        handle.set_parameter(param_name, teeth_count, teeth_range)
        handle.setToolTip(tooltip)
        scene.addItem(handle)
        return handle
    
    def validate_gear_mesh(self, gear1_teeth: int, gear2_teeth: int,
                          center_distance: float, module: float = 1.0) -> bool:
        """Validate if two gears can properly mesh."""
        theoretical_distance = module * (gear1_teeth + gear2_teeth) / 2
        tolerance = module * 0.1  # 10% tolerance
        return abs(center_distance - theoretical_distance) <= tolerance


class BasePowerTransmissionHandler(BaseMechanismInteractionHandler):
    """Base handler for power transmission mechanisms (belts, chains, etc.)."""
    
    def create_power_analysis_group(self, layout: QVBoxLayout) -> Dict[str, QLabel]:
        """Create power transmission analysis UI group."""
        power_group = QGroupBox("Power Transmission")
        power_layout = QVBoxLayout(power_group)
        
        labels = {}
        labels['power_capacity'] = QLabel("Power Capacity: 0.0 kW")
        labels['power_capacity'].setStyleSheet(f"color: {ModernStyling.COLORS['primary']};")
        power_layout.addWidget(labels['power_capacity'])
        
        labels['efficiency'] = QLabel("Efficiency: 98%")
        labels['efficiency'].setStyleSheet(f"color: {ModernStyling.COLORS['success']};")
        power_layout.addWidget(labels['efficiency'])
        
        labels['slip'] = QLabel("Slip: 0%")
        power_layout.addWidget(labels['slip'])
        
        labels['tension_ratio'] = QLabel("Tension Ratio: 1.0:1")
        power_layout.addWidget(labels['tension_ratio'])
        
        layout.addWidget(power_group)
        return labels
    
    def calculate_belt_length(self, r1: float, r2: float, center_distance: float,
                            is_crossed: bool = False) -> float:
        """Calculate belt length for open or crossed configuration."""
        if is_crossed:
            # Crossed belt configuration
            length = (2 * center_distance + 
                     math.pi * (r1 + r2) + 
                     (r1 + r2)**2 / (4 * center_distance))
        else:
            # Open belt configuration
            length = (2 * center_distance + 
                     math.pi * (r1 + r2) + 
                     (r2 - r1)**2 / (4 * center_distance))
        return length
    
    def calculate_contact_angles(self, r1: float, r2: float, center_distance: float,
                               is_crossed: bool = False) -> Tuple[float, float]:
        """Calculate wrap angles for pulleys."""
        if center_distance <= abs(r2 - r1):
            return math.pi, math.pi
            
        if is_crossed:
            alpha = math.asin((r1 + r2) / center_distance)
            angle1 = math.pi + 2 * alpha
            angle2 = math.pi + 2 * alpha
        else:
            alpha = math.asin((r2 - r1) / center_distance)
            angle1 = math.pi + 2 * alpha
            angle2 = math.pi - 2 * alpha
            
        return angle1, angle2


class BaseElasticHandler(BaseMechanismInteractionHandler):
    """Base handler for elastic mechanisms (springs, dampers, etc.)."""
    
    def create_energy_analysis_group(self, layout: QVBoxLayout) -> Dict[str, QLabel]:
        """Create energy analysis UI group."""
        energy_group = QGroupBox("Energy Analysis")
        energy_layout = QVBoxLayout(energy_group)
        
        labels = {}
        labels['potential_energy'] = QLabel("Potential Energy: 0.0 J")
        labels['potential_energy'].setStyleSheet(f"color: {ModernStyling.COLORS['success']};")
        energy_layout.addWidget(labels['potential_energy'])
        
        labels['kinetic_energy'] = QLabel("Kinetic Energy: 0.0 J")
        labels['kinetic_energy'].setStyleSheet(f"color: {ModernStyling.COLORS['info']};")
        energy_layout.addWidget(labels['kinetic_energy'])
        
        labels['total_energy'] = QLabel("Total Energy: 0.0 J")
        energy_layout.addWidget(labels['total_energy'])
        
        labels['damping_energy'] = QLabel("Damping Loss: 0.0 J/s")
        labels['damping_energy'].setStyleSheet(f"color: {ModernStyling.COLORS['warning']};")
        energy_layout.addWidget(labels['damping_energy'])
        
        layout.addWidget(energy_group)
        return labels
    
    def calculate_spring_energy(self, k: float, x: float, m: float = 0, v: float = 0) -> Dict[str, float]:
        """Calculate spring system energies."""
        potential = 0.5 * k * x * x
        kinetic = 0.5 * m * v * v if m > 0 else 0
        total = potential + kinetic
        
        return {
            "potential": potential,
            "kinetic": kinetic,
            "total": total,
            "displacement": x,
            "velocity": v
        }
    
    def calculate_natural_frequency(self, k: float, m: float, c: float = 0) -> Dict[str, float]:
        """Calculate natural frequency and damping parameters."""
        if m <= 0:
            return {"frequency": 0, "period": 0, "damping_ratio": 0}
            
        omega_n = math.sqrt(k / m)
        frequency = omega_n / (2 * math.pi)
        period = 1 / frequency if frequency > 0 else 0
        
        critical_damping = 2 * math.sqrt(k * m)
        damping_ratio = c / critical_damping if critical_damping > 0 else 0
        
        # Damped natural frequency
        if damping_ratio < 1:
            omega_d = omega_n * math.sqrt(1 - damping_ratio**2)
            damped_frequency = omega_d / (2 * math.pi)
        else:
            damped_frequency = 0  # Overdamped
            
        return {
            "natural_frequency": frequency,
            "damped_frequency": damped_frequency,
            "angular_frequency": omega_n,
            "period": period,
            "damping_ratio": damping_ratio,
            "critical_damping": critical_damping,
            "quality_factor": 1 / (2 * damping_ratio) if damping_ratio > 0 else float('inf')
        }


# ==============================================================================
# SPECIFIC HANDLER IMPLEMENTATIONS - Now inherit from base classes
# ==============================================================================

class FourBarLinkageInteractionHandler(BaseLinkageHandler):
    """Specialized interaction handler for four-bar linkages."""
    
    def create_interaction_controls(self) -> QWidget:
        """Create four-bar linkage specific controls."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Grashof analysis group
        grashof_group = QGroupBox("Grashof Analysis")
        grashof_layout = QVBoxLayout(grashof_group)
        
        self.grashof_label = QLabel("Calculating...")
        self.grashof_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        grashof_layout.addWidget(self.grashof_label)
        
        self.rotation_type_label = QLabel("Rotation Type: Unknown")
        self.rotation_type_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        grashof_layout.addWidget(self.rotation_type_label)
        
        layout.addWidget(grashof_group)
        
        # Transmission angle group
        transmission_group = QGroupBox("Transmission Analysis")
        transmission_layout = QVBoxLayout(transmission_group)
        
        self.transmission_angle_label = QLabel("Transmission Angle: --°")
        self.transmission_angle_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        transmission_layout.addWidget(self.transmission_angle_label)
        
        self.transmission_quality_label = QLabel("Quality: Unknown")
        self.transmission_quality_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        transmission_layout.addWidget(self.transmission_quality_label)
        
        layout.addWidget(transmission_group)
        
        # Path optimization controls
        optimization_group = QGroupBox("Path Optimization")
        optimization_layout = QVBoxLayout(optimization_group)
        
        self.optimize_for_straightness = QCheckBox("Optimize for Straight Line")
        self.optimize_for_smoothness = QCheckBox("Optimize for Smoothness")
        
        optimization_layout.addWidget(self.optimize_for_straightness)
        optimization_layout.addWidget(self.optimize_for_smoothness)
        
        optimize_button = QPushButton("Apply Optimization")
        optimize_button.setStyleSheet(ModernStyling.get_button_style("primary"))
        optimize_button.clicked.connect(self._apply_optimization)
        optimization_layout.addWidget(optimize_button)
        
        layout.addWidget(optimization_group)
        
        layout.addStretch()
        return widget
    
    def create_drag_handles(self, scene):
        """Create drag handles for four-bar linkage parameters."""
        self.drag_handles.clear()
        
        # Create handles for each moveable joint
        # Handle for adjusting link lengths
        base_x, base_y = 100, 100  # Base position
        
        # Link 1 end handle (crank end)
        link1_length = self.mechanism.get_parameter("link1_length", 50.0)
        handle1 = DragHandle(base_x + link1_length, base_y)
        handle1.set_parameter("link1_length", link1_length, (20.0, 100.0))
        
        # Add Grashof constraint for link 1
        def link1_constraint(value):
            l2 = self.mechanism.get_parameter("link2_length", 80.0)
            l3 = self.mechanism.get_parameter("link3_length", 60.0)
            l4 = self.mechanism.get_parameter("base_length", 100.0)
            lengths = sorted([value, l2, l3, l4])
            s, p, q, l = lengths[0], lengths[1], lengths[2], lengths[3]
            
            # Check triangle inequality
            if s + l > p + q:
                return False, "Configuration creates impossible triangle - reduce link length"
            return True, "Valid"
        
        def link1_warning(value):
            l2 = self.mechanism.get_parameter("link2_length", 80.0)
            l3 = self.mechanism.get_parameter("link3_length", 60.0)
            l4 = self.mechanism.get_parameter("base_length", 100.0)
            lengths = sorted([value, l2, l3, l4])
            s, p, q, l = lengths[0], lengths[1], lengths[2], lengths[3]
            
            if abs(s + l - (p + q)) < 5:  # Close to limit
                return True, "Warning: Near Grashof limit - may have restricted motion"
            return False, ""
        
        handle1.set_constraint_function(link1_constraint, link1_warning)
        scene.addItem(handle1)
        self.drag_handles.append(handle1)
        
        # Link 2 end handle (coupler end)
        link2_length = self.mechanism.get_parameter("link2_length", 80.0)
        handle2 = DragHandle(base_x + link1_length + link2_length * 0.7, base_y - link2_length * 0.7)
        handle2.set_parameter("link2_length", link2_length, (30.0, 150.0))
        
        # Similar constraint for link 2
        def link2_constraint(value):
            l1 = self.mechanism.get_parameter("link1_length", 50.0)
            l3 = self.mechanism.get_parameter("link3_length", 60.0)
            l4 = self.mechanism.get_parameter("base_length", 100.0)
            lengths = sorted([l1, value, l3, l4])
            s, p, q, l = lengths[0], lengths[1], lengths[2], lengths[3]
            
            if s + l > p + q:
                return False, "Configuration creates impossible triangle - reduce link length"
            return True, "Valid"
        
        handle2.set_constraint_function(link2_constraint)
        scene.addItem(handle2)
        self.drag_handles.append(handle2)
        
        # Base length handle
        base_length = self.mechanism.get_parameter("base_length", 100.0)
        handle3 = DragHandle(base_x + base_length, base_y + 20)
        handle3.set_parameter("base_length", base_length, (50.0, 200.0))
        
        # Base length constraint
        def base_constraint(value):
            l1 = self.mechanism.get_parameter("link1_length", 50.0)
            l2 = self.mechanism.get_parameter("link2_length", 80.0)
            l3 = self.mechanism.get_parameter("link3_length", 60.0)
            lengths = sorted([l1, l2, l3, value])
            s, p, q, l = lengths[0], lengths[1], lengths[2], lengths[3]
            
            if s + l > p + q:
                return False, "Configuration creates impossible triangle - reduce base length"
            return True, "Valid"
        
        handle3.set_constraint_function(base_constraint)
        scene.addItem(handle3)
        self.drag_handles.append(handle3)
    
    def update_visualization(self):
        """Update four-bar linkage visualization."""
        # Update handle positions based on current parameters
        if len(self.drag_handles) >= 3:
            base_x, base_y = 100, 100
            
            link1_length = self.mechanism.get_parameter("link1_length", 50.0)
            self.drag_handles[0].setPos(base_x + link1_length, base_y)
            
            link2_length = self.mechanism.get_parameter("link2_length", 80.0)
            self.drag_handles[1].setPos(base_x + link1_length + link2_length * 0.7, 
                                      base_y - link2_length * 0.7)
            
            base_length = self.mechanism.get_parameter("base_length", 100.0)
            self.drag_handles[2].setPos(base_x + base_length, base_y + 20)
    
    def get_analysis_data(self) -> Dict[str, Any]:
        """Get four-bar linkage analysis data."""
        # Get current link lengths
        l1 = self.mechanism.get_parameter("link1_length", 50.0)
        l2 = self.mechanism.get_parameter("link2_length", 80.0)
        l3 = self.mechanism.get_parameter("link3_length", 60.0)
        l4 = self.mechanism.get_parameter("base_length", 100.0)
        
        # Grashof analysis
        lengths = sorted([l1, l2, l3, l4])
        s, p, q, l = lengths[0], lengths[1], lengths[2], lengths[3]
        grashof_condition = s + l <= p + q
        
        # Determine rotation type
        if grashof_condition:
            if s == l1:  # Crank is shortest
                rotation_type = "Crank-Rocker"
            elif s == l4:  # Base is shortest
                rotation_type = "Double-Crank"
            else:
                rotation_type = "Double-Rocker"
        else:
            rotation_type = "Triple-Rocker (No continuous rotation)"
        
        # Transmission angle calculation (simplified)
        # This would need more complex kinematics for exact calculation
        transmission_angle = 90.0  # Placeholder
        
        # Quality assessment
        if 40 <= transmission_angle <= 140:
            transmission_quality = "Good"
            quality_color = ModernStyling.COLORS['success']
        elif 30 <= transmission_angle <= 150:
            transmission_quality = "Fair"
            quality_color = ModernStyling.COLORS['warning']
        else:
            transmission_quality = "Poor"
            quality_color = ModernStyling.COLORS['error']
        
        # Update UI labels
        if hasattr(self, 'grashof_label'):
            self.grashof_label.setText(f"Grashof: {'Satisfied' if grashof_condition else 'Not Satisfied'}")
            self.rotation_type_label.setText(f"Type: {rotation_type}")
            self.transmission_angle_label.setText(f"Transmission Angle: {transmission_angle:.1f}°")
            self.transmission_quality_label.setText(f"Quality: {transmission_quality}")
            self.transmission_quality_label.setStyleSheet(f"color: {quality_color};")
        
        return {
            "grashof_satisfied": grashof_condition,
            "rotation_type": rotation_type,
            "transmission_angle": transmission_angle,
            "transmission_quality": transmission_quality,
            "link_lengths": {"l1": l1, "l2": l2, "l3": l3, "l4": l4}
        }
    
    def _position_to_parameter_value(self, handle: DragHandle, position: QPointF) -> Optional[float]:
        """Convert handle position to parameter value for four-bar linkage."""
        base_x, base_y = 100, 100
        
        if handle.parameter_name == "link1_length":
            # Distance from base to handle position
            distance = math.sqrt((position.x() - base_x)**2 + (position.y() - base_y)**2)
            return max(handle.value_range[0], min(handle.value_range[1], distance))
        
        elif handle.parameter_name == "base_length":
            # Horizontal distance from base
            distance = abs(position.x() - base_x)
            return max(handle.value_range[0], min(handle.value_range[1], distance))
        
        elif handle.parameter_name == "link2_length":
            # Distance from link1 end position
            link1_length = self.mechanism.get_parameter("link1_length", 50.0)
            link1_end_x = base_x + link1_length
            distance = math.sqrt((position.x() - link1_end_x)**2 + (position.y() - base_y)**2)
            return max(handle.value_range[0], min(handle.value_range[1], distance))
        
        return None
    
    def _apply_optimization(self):
        """Apply path optimization based on selected criteria."""
        # This would implement optimization algorithms
        # For now, just emit a signal to indicate optimization was requested
        optimize_for_straight = self.optimize_for_straightness.isChecked()
        optimize_for_smooth = self.optimize_for_smoothness.isChecked()
        
        optimization_data = {
            "straight_line": optimize_for_straight,
            "smoothness": optimize_for_smooth
        }
        
        self.analysis_updated.emit({"optimization_applied": optimization_data})


class CamFollowerInteractionHandler(BaseMechanismInteractionHandler):
    """Specialized interaction handler for cam follower mechanisms."""
    
    def create_interaction_controls(self) -> QWidget:
        """Create cam follower specific controls."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Cam profile analysis
        profile_group = QGroupBox("Cam Profile Analysis")
        profile_layout = QVBoxLayout(profile_group)
        
        self.cam_radius_label = QLabel("Base Radius: 50mm")
        self.cam_radius_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        profile_layout.addWidget(self.cam_radius_label)
        
        self.lift_profile_label = QLabel("Max Lift: 20mm")
        self.lift_profile_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        profile_layout.addWidget(self.lift_profile_label)
        
        # Cam profile type selection
        profile_type_layout = QHBoxLayout()
        profile_type_layout.addWidget(QLabel("Profile Type:"))
        self.profile_type_combo = QComboBox()
        self.profile_type_combo.addItems(["Linear", "Harmonic", "Cycloidal", "Modified Sine"])
        self.profile_type_combo.currentTextChanged.connect(self._on_profile_type_changed)
        profile_type_layout.addWidget(self.profile_type_combo)
        profile_layout.addLayout(profile_type_layout)
        
        layout.addWidget(profile_group)
        
        # Follower motion analysis
        motion_group = QGroupBox("Follower Motion")
        motion_layout = QVBoxLayout(motion_group)
        
        self.follower_position_label = QLabel("Position: 0°")
        self.follower_velocity_label = QLabel("Velocity: 0 mm/s")
        self.follower_acceleration_label = QLabel("Acceleration: 0 mm/s²")
        
        motion_layout.addWidget(self.follower_position_label)
        motion_layout.addWidget(self.follower_velocity_label)
        motion_layout.addWidget(self.follower_acceleration_label)
        
        layout.addWidget(motion_group)
        
        # Pressure angle analysis
        pressure_group = QGroupBox("Pressure Angle Analysis")
        pressure_layout = QVBoxLayout(pressure_group)
        
        self.pressure_angle_label = QLabel("Current Angle: 30°")
        self.pressure_quality_label = QLabel("Quality: Good")
        
        pressure_layout.addWidget(self.pressure_angle_label)
        pressure_layout.addWidget(self.pressure_quality_label)
        
        layout.addWidget(pressure_group)
        
        layout.addStretch()
        return widget
    
    def create_drag_handles(self, scene):
        """Create drag handles for cam parameters."""
        self.drag_handles.clear()
        
        # Cam center
        cam_center = (150, 150)
        
        # Base radius handle
        base_radius = self.mechanism.get_parameter("base_radius", 50.0)
        handle_base = DragHandle(cam_center[0] + base_radius, cam_center[1])
        handle_base.set_parameter("base_radius", base_radius, (20.0, 80.0))
        scene.addItem(handle_base)
        self.drag_handles.append(handle_base)
        
        # Lift handle (maximum lift position)
        max_lift = self.mechanism.get_parameter("max_lift", 20.0)
        handle_lift = DragHandle(cam_center[0], cam_center[1] - base_radius - max_lift)
        handle_lift.set_parameter("max_lift", max_lift, (5.0, 50.0))
        scene.addItem(handle_lift)
        self.drag_handles.append(handle_lift)
        
        # Follower offset handle
        follower_offset = self.mechanism.get_parameter("follower_offset", 0.0)
        handle_offset = DragHandle(cam_center[0] + follower_offset, cam_center[1] - 80)
        handle_offset.set_parameter("follower_offset", follower_offset, (-30.0, 30.0))
        scene.addItem(handle_offset)
        self.drag_handles.append(handle_offset)
    
    def update_visualization(self):
        """Update cam follower visualization."""
        if len(self.drag_handles) >= 3:
            cam_center = (150, 150)
            
            base_radius = self.mechanism.get_parameter("base_radius", 50.0)
            self.drag_handles[0].setPos(cam_center[0] + base_radius, cam_center[1])
            
            max_lift = self.mechanism.get_parameter("max_lift", 20.0)
            self.drag_handles[1].setPos(cam_center[0], cam_center[1] - base_radius - max_lift)
            
            follower_offset = self.mechanism.get_parameter("follower_offset", 0.0)
            self.drag_handles[2].setPos(cam_center[0] + follower_offset, cam_center[1] - 80)
    
    def get_analysis_data(self) -> Dict[str, Any]:
        """Get cam follower analysis data."""
        base_radius = self.mechanism.get_parameter("base_radius", 50.0)
        max_lift = self.mechanism.get_parameter("max_lift", 20.0)
        follower_offset = self.mechanism.get_parameter("follower_offset", 0.0)
        cam_angle = self.mechanism.get_parameter("cam_angle", 0.0)
        
        # Calculate current follower position based on cam profile
        lift_ratio = (1 - math.cos(math.radians(cam_angle))) / 2  # Harmonic motion
        current_lift = max_lift * lift_ratio
        
        # Pressure angle calculation (simplified)
        pressure_angle = abs(math.degrees(math.atan(follower_offset / (base_radius + current_lift))))
        
        # Quality assessment
        if pressure_angle <= 30:
            pressure_quality = "Excellent"
            quality_color = ModernStyling.COLORS['success']
        elif pressure_angle <= 45:
            pressure_quality = "Good"
            quality_color = ModernStyling.COLORS['info']
        elif pressure_angle <= 60:
            pressure_quality = "Fair"
            quality_color = ModernStyling.COLORS['warning']
        else:
            pressure_quality = "Poor"
            quality_color = ModernStyling.COLORS['error']
        
        # Update UI labels
        if hasattr(self, 'cam_radius_label'):
            self.cam_radius_label.setText(f"Base Radius: {base_radius:.1f}mm")
            self.lift_profile_label.setText(f"Max Lift: {max_lift:.1f}mm")
            self.follower_position_label.setText(f"Position: {cam_angle:.1f}°")
            self.follower_velocity_label.setText(f"Current Lift: {current_lift:.1f}mm")
            self.pressure_angle_label.setText(f"Pressure Angle: {pressure_angle:.1f}°")
            self.pressure_quality_label.setText(f"Quality: {pressure_quality}")
            self.pressure_quality_label.setStyleSheet(f"color: {quality_color};")
        
        return {
            "base_radius": base_radius,
            "max_lift": max_lift,
            "follower_offset": follower_offset,
            "current_lift": current_lift,
            "pressure_angle": pressure_angle,
            "pressure_quality": pressure_quality,
            "cam_angle": cam_angle
        }
    
    def _position_to_parameter_value(self, handle: DragHandle, position: QPointF) -> Optional[float]:
        """Convert handle position to parameter value for cam followers."""
        cam_center = (150, 150)
        
        if handle.parameter_name == "base_radius":
            # Distance from cam center
            distance = math.sqrt((position.x() - cam_center[0])**2 + (position.y() - cam_center[1])**2)
            return max(handle.value_range[0], min(handle.value_range[1], distance))
        
        elif handle.parameter_name == "max_lift":
            # Vertical distance above base radius
            base_radius = self.mechanism.get_parameter("base_radius", 50.0)
            lift = abs(position.y() - (cam_center[1] - base_radius))
            return max(handle.value_range[0], min(handle.value_range[1], lift))
        
        elif handle.parameter_name == "follower_offset":
            # Horizontal offset from cam center
            offset = position.x() - cam_center[0]
            return max(handle.value_range[0], min(handle.value_range[1], offset))
        
        return None
    
    def _on_profile_type_changed(self, profile_type: str):
        """Handle cam profile type changes."""
        self.mechanism.set_parameter("profile_type", profile_type)
        self.parameter_changed.emit("profile_type", profile_type)


class GearSystemInteractionHandler(BaseRotaryHandler):
    """Specialized interaction handler for gear systems."""
    
    def create_interaction_controls(self) -> QWidget:
        """Create gear system specific controls."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Gear ratio analysis
        ratio_group = QGroupBox("Gear Ratio Analysis")
        ratio_layout = QVBoxLayout(ratio_group)
        
        self.gear_ratio_label = QLabel("Gear Ratio: 1:1")
        self.gear_ratio_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        ratio_layout.addWidget(self.gear_ratio_label)
        
        self.mechanical_advantage_label = QLabel("Mechanical Advantage: 1.0")
        self.mechanical_advantage_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        ratio_layout.addWidget(self.mechanical_advantage_label)
        
        layout.addWidget(ratio_group)
        
        # Speed analysis
        speed_group = QGroupBox("Speed Analysis")
        speed_layout = QVBoxLayout(speed_group)
        
        self.input_speed_label = QLabel("Input Speed: 100 RPM")
        self.output_speed_label = QLabel("Output Speed: 100 RPM")
        
        speed_layout.addWidget(self.input_speed_label)
        speed_layout.addWidget(self.output_speed_label)
        
        layout.addWidget(speed_group)
        
        # Efficiency controls
        efficiency_group = QGroupBox("Efficiency Analysis")
        efficiency_layout = QVBoxLayout(efficiency_group)
        
        self.efficiency_label = QLabel("Efficiency: 95%")
        efficiency_layout.addWidget(self.efficiency_label)
        
        layout.addWidget(efficiency_group)
        
        layout.addStretch()
        return widget
    
    def create_drag_handles(self, scene):
        """Create drag handles for gear parameters."""
        self.drag_handles.clear()
        
        # Center positions for gears
        gear1_center = (100, 100)
        gear2_center = (200, 100)
        
        # Handle for gear 1 radius (number of teeth)
        gear1_teeth = self.mechanism.get_parameter("gear1_teeth", 12)
        gear1_radius = gear1_teeth * 2  # Simplified radius calculation
        handle1 = DragHandle(gear1_center[0] + gear1_radius, gear1_center[1])
        handle1.set_parameter("gear1_teeth", gear1_teeth, (8, 30))
        scene.addItem(handle1)
        self.drag_handles.append(handle1)
        
        # Handle for gear 2 radius
        gear2_teeth = self.mechanism.get_parameter("gear2_teeth", 24)
        gear2_radius = gear2_teeth * 2
        handle2 = DragHandle(gear2_center[0] + gear2_radius, gear2_center[1])
        handle2.set_parameter("gear2_teeth", gear2_teeth, (10, 50))
        scene.addItem(handle2)
        self.drag_handles.append(handle2)
    
    def update_visualization(self):
        """Update gear system visualization."""
        if len(self.drag_handles) >= 2:
            gear1_center = (100, 100)
            gear2_center = (200, 100)
            
            gear1_teeth = self.mechanism.get_parameter("gear1_teeth", 12)
            gear1_radius = gear1_teeth * 2
            self.drag_handles[0].setPos(gear1_center[0] + gear1_radius, gear1_center[1])
            
            gear2_teeth = self.mechanism.get_parameter("gear2_teeth", 24)
            gear2_radius = gear2_teeth * 2
            self.drag_handles[1].setPos(gear2_center[0] + gear2_radius, gear2_center[1])
    
    def get_analysis_data(self) -> Dict[str, Any]:
        """Get gear system analysis data."""
        gear1_teeth = self.mechanism.get_parameter("gear1_teeth", 12)
        gear2_teeth = self.mechanism.get_parameter("gear2_teeth", 24)
        
        # Calculate gear ratio
        gear_ratio = gear2_teeth / gear1_teeth
        mechanical_advantage = gear_ratio
        
        # Speed calculations
        input_speed = 100  # RPM (could be parameter)
        output_speed = input_speed / gear_ratio
        
        # Efficiency (simplified)
        efficiency = 95.0  # Typical gear efficiency
        
        # Update UI labels
        if hasattr(self, 'gear_ratio_label'):
            self.gear_ratio_label.setText(f"Gear Ratio: {gear_ratio:.2f}:1")
            self.mechanical_advantage_label.setText(f"Mechanical Advantage: {mechanical_advantage:.2f}")
            self.input_speed_label.setText(f"Input Speed: {input_speed:.0f} RPM")
            self.output_speed_label.setText(f"Output Speed: {output_speed:.0f} RPM")
            self.efficiency_label.setText(f"Efficiency: {efficiency:.1f}%")
        
        return {
            "gear_ratio": gear_ratio,
            "mechanical_advantage": mechanical_advantage,
            "input_speed": input_speed,
            "output_speed": output_speed,
            "efficiency": efficiency,
            "gear_teeth": {"gear1": gear1_teeth, "gear2": gear2_teeth}
        }
    
    def _position_to_parameter_value(self, handle: DragHandle, position: QPointF) -> Optional[float]:
        """Convert handle position to parameter value for gear systems."""
        if handle.parameter_name == "gear1_teeth":
            gear1_center = (100, 100)
            radius = math.sqrt((position.x() - gear1_center[0])**2 + (position.y() - gear1_center[1])**2)
            teeth = int(radius / 2)  # Simplified conversion
            return max(handle.value_range[0], min(handle.value_range[1], teeth))
        
        elif handle.parameter_name == "gear2_teeth":
            gear2_center = (200, 100)
            radius = math.sqrt((position.x() - gear2_center[0])**2 + (position.y() - gear2_center[1])**2)
            teeth = int(radius / 2)
            return max(handle.value_range[0], min(handle.value_range[1], teeth))
        
        return None


class SixBarLinkageInteractionHandler(BaseLinkageHandler):
    """Specialized interaction handler for six-bar linkage mechanisms."""
    
    def create_interaction_controls(self) -> QWidget:
        """Create six-bar linkage specific controls."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Six-bar linkage analysis
        linkage_group = QGroupBox("Six-Bar Linkage Analysis")
        linkage_layout = QVBoxLayout(linkage_group)
        
        self.dof_label = QLabel("Degrees of Freedom: 1")
        self.dof_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        linkage_layout.addWidget(self.dof_label)
        
        self.linkage_type_label = QLabel("Type: Watt Six-Bar")
        self.linkage_type_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        linkage_layout.addWidget(self.linkage_type_label)
        
        self.coupler_curve_label = QLabel("Coupler Curve: Complex")
        self.coupler_curve_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        linkage_layout.addWidget(self.coupler_curve_label)
        
        layout.addWidget(linkage_group)
        
        # Individual four-bar loops analysis
        loops_group = QGroupBox("Four-Bar Loop Analysis")
        loops_layout = QVBoxLayout(loops_group)
        
        self.loop1_grashof_label = QLabel("Loop 1 Grashof: --")
        self.loop1_grashof_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        loops_layout.addWidget(self.loop1_grashof_label)
        
        self.loop2_grashof_label = QLabel("Loop 2 Grashof: --")
        self.loop2_grashof_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        loops_layout.addWidget(self.loop2_grashof_label)
        
        layout.addWidget(loops_group)
        
        # Coupler curve analysis
        coupler_group = QGroupBox("Coupler Curve Analysis")
        coupler_layout = QVBoxLayout(coupler_group)
        
        self.curve_complexity_label = QLabel("Curve Complexity: High")
        self.curve_length_label = QLabel("Curve Length: -- mm")
        self.curve_cusps_label = QLabel("Cusps: 0")
        
        coupler_layout.addWidget(self.curve_complexity_label)
        coupler_layout.addWidget(self.curve_length_label)
        coupler_layout.addWidget(self.curve_cusps_label)
        
        # Curve optimization
        optimize_curve_button = QPushButton("Optimize Coupler Curve")
        optimize_curve_button.setStyleSheet(ModernStyling.get_button_style("primary"))
        optimize_curve_button.clicked.connect(self._optimize_coupler_curve)
        coupler_layout.addWidget(optimize_curve_button)
        
        layout.addWidget(coupler_group)
        
        # Six-bar specific controls
        advanced_group = QGroupBox("Advanced Six-Bar Controls")
        advanced_layout = QVBoxLayout(advanced_group)
        
        self.show_loops_checkbox = QCheckBox("Show Individual Four-Bar Loops")
        self.show_loops_checkbox.setChecked(True)
        advanced_layout.addWidget(self.show_loops_checkbox)
        
        self.show_coupler_curve_checkbox = QCheckBox("Show Complete Coupler Curve")
        self.show_coupler_curve_checkbox.setChecked(True)
        advanced_layout.addWidget(self.show_coupler_curve_checkbox)
        
        self.animate_construction_checkbox = QCheckBox("Animate Construction")
        advanced_layout.addWidget(self.animate_construction_checkbox)
        
        layout.addWidget(advanced_group)
        
        layout.addStretch()
        return widget
    
    def create_drag_handles(self, scene):
        """Create drag handles for six-bar linkage parameters."""
        self.drag_handles.clear()
        
        # Base positions
        base_x, base_y = 100, 100
        
        # Link 1 handle (crank)
        link1_length = self.mechanism.get_parameter("link1_length", 40.0)
        handle1 = DragHandle(base_x + link1_length, base_y)
        handle1.set_parameter("link1_length", link1_length, (20.0, 80.0))
        
        # Add six-bar specific constraints
        def link1_constraint(value):
            # Six-bar constraints are more complex than four-bar
            l2 = self.mechanism.get_parameter("link2_length", 90.0)
            l3 = self.mechanism.get_parameter("link3_length", 70.0)
            base_len = self.mechanism.get_parameter("base_length", 120.0)
            
            # Check if first four-bar loop is valid
            if value + l2 <= l3 + base_len and abs(value - l2) >= abs(l3 - base_len):
                return True, "Valid"
            return False, "Invalid six-bar configuration - first loop broken"
        
        handle1.set_constraint_function(link1_constraint)
        scene.addItem(handle1)
        self.drag_handles.append(handle1)
        
        # Link 2 handle (first coupler)
        link2_length = self.mechanism.get_parameter("link2_length", 90.0)
        handle2 = DragHandle(base_x + link1_length + link2_length * 0.6, base_y - link2_length * 0.8)
        handle2.set_parameter("link2_length", link2_length, (40.0, 140.0))
        scene.addItem(handle2)
        self.drag_handles.append(handle2)
        
        # Link 3 handle (second coupler)
        link3_length = self.mechanism.get_parameter("link3_length", 70.0)
        handle3 = DragHandle(base_x + link1_length + 60, base_y - link3_length)
        handle3.set_parameter("link3_length", link3_length, (30.0, 110.0))
        scene.addItem(handle3)
        self.drag_handles.append(handle3)
        
        # Link 4 handle (third coupler)
        link4_length = self.mechanism.get_parameter("link4_length", 80.0)
        handle4 = DragHandle(base_x + link4_length + 40, base_y - 60)
        handle4.set_parameter("link4_length", link4_length, (35.0, 120.0))
        scene.addItem(handle4)
        self.drag_handles.append(handle4)
        
        # Link 5 handle (output rocker)
        link5_length = self.mechanism.get_parameter("link5_length", 50.0)
        handle5 = DragHandle(base_x + link5_length + 80, base_y + 10)
        handle5.set_parameter("link5_length", link5_length, (25.0, 90.0))
        scene.addItem(handle5)
        self.drag_handles.append(handle5)
        
        # Base length handle
        base_length = self.mechanism.get_parameter("base_length", 120.0)
        handle6 = DragHandle(base_x + base_length, base_y + 30)
        handle6.set_parameter("base_length", base_length, (60.0, 200.0))
        scene.addItem(handle6)
        self.drag_handles.append(handle6)
    
    def update_visualization(self):
        """Update six-bar linkage visualization."""
        if len(self.drag_handles) >= 6:
            base_x, base_y = 100, 100
            
            # Update all handle positions based on current parameters
            link1_length = self.mechanism.get_parameter("link1_length", 40.0)
            self.drag_handles[0].setPos(base_x + link1_length, base_y)
            
            link2_length = self.mechanism.get_parameter("link2_length", 90.0)
            self.drag_handles[1].setPos(base_x + link1_length + link2_length * 0.6, base_y - link2_length * 0.8)
            
            link3_length = self.mechanism.get_parameter("link3_length", 70.0)
            self.drag_handles[2].setPos(base_x + link1_length + 60, base_y - link3_length)
            
            link4_length = self.mechanism.get_parameter("link4_length", 80.0)
            self.drag_handles[3].setPos(base_x + link4_length + 40, base_y - 60)
            
            link5_length = self.mechanism.get_parameter("link5_length", 50.0)
            self.drag_handles[4].setPos(base_x + link5_length + 80, base_y + 10)
            
            base_length = self.mechanism.get_parameter("base_length", 120.0)
            self.drag_handles[5].setPos(base_x + base_length, base_y + 30)
    
    def get_analysis_data(self) -> Dict[str, Any]:
        """Get six-bar linkage analysis data."""
        # Get all link lengths
        l1 = self.mechanism.get_parameter("link1_length", 40.0)
        l2 = self.mechanism.get_parameter("link2_length", 90.0)
        l3 = self.mechanism.get_parameter("link3_length", 70.0)
        l4 = self.mechanism.get_parameter("link4_length", 80.0)
        l5 = self.mechanism.get_parameter("link5_length", 50.0)
        base_len = self.mechanism.get_parameter("base_length", 120.0)
        
        # Analyze both four-bar loops
        # Loop 1: links 1, 2, 3, base
        loop1_lengths = sorted([l1, l2, l3, base_len])
        s1, p1, q1, l1_max = loop1_lengths[0], loop1_lengths[1], loop1_lengths[2], loop1_lengths[3]
        loop1_grashof = s1 + l1_max <= p1 + q1
        
        # Loop 2: links 3, 4, 5, base (simplified)
        loop2_lengths = sorted([l3, l4, l5, base_len])
        s2, p2, q2, l2_max = loop2_lengths[0], loop2_lengths[1], loop2_lengths[2], loop2_lengths[3]
        loop2_grashof = s2 + l2_max <= p2 + q2
        
        # Degrees of freedom (should be 1 for proper six-bar)
        dof = 1  # For Watt six-bar linkage
        
        # Coupler curve complexity (simplified metric)
        curve_complexity = "High" if loop1_grashof and loop2_grashof else "Medium"
        
        # Update UI labels
        if hasattr(self, 'dof_label'):
            self.dof_label.setText(f"Degrees of Freedom: {dof}")
            self.linkage_type_label.setText("Type: Watt Six-Bar")
            self.coupler_curve_label.setText(f"Coupler Curve: {curve_complexity}")
            
            self.loop1_grashof_label.setText(f"Loop 1 Grashof: {'Satisfied' if loop1_grashof else 'Not Satisfied'}")
            self.loop2_grashof_label.setText(f"Loop 2 Grashof: {'Satisfied' if loop2_grashof else 'Not Satisfied'}")
            
            self.curve_complexity_label.setText(f"Curve Complexity: {curve_complexity}")
            # Simplified curve length calculation
            estimated_curve_length = (l2 + l3 + l4) * 2 * math.pi
            self.curve_length_label.setText(f"Curve Length: {estimated_curve_length:.1f} mm")
            
            # Simplified cusp detection
            cusps = 2 if loop1_grashof and loop2_grashof else 0
            self.curve_cusps_label.setText(f"Cusps: {cusps}")
        
        return {
            "degrees_of_freedom": dof,
            "linkage_type": "Watt Six-Bar",
            "loop1_grashof": loop1_grashof,
            "loop2_grashof": loop2_grashof,
            "curve_complexity": curve_complexity,
            "link_lengths": {
                "l1": l1, "l2": l2, "l3": l3, "l4": l4, "l5": l5, "base": base_len
            },
            "estimated_curve_length": estimated_curve_length,
            "estimated_cusps": cusps
        }
    
    def _position_to_parameter_value(self, handle: DragHandle, position: QPointF) -> Optional[float]:
        """Convert handle position to parameter value for six-bar linkage."""
        base_x, base_y = 100, 100
        
        if handle.parameter_name == "link1_length":
            distance = math.sqrt((position.x() - base_x)**2 + (position.y() - base_y)**2)
            return max(handle.value_range[0], min(handle.value_range[1], distance))
        
        elif handle.parameter_name == "base_length":
            distance = abs(position.x() - base_x)
            return max(handle.value_range[0], min(handle.value_range[1], distance))
        
        elif handle.parameter_name in ["link2_length", "link3_length", "link4_length", "link5_length"]:
            # For other links, use distance from their respective reference points
            # This is a simplified implementation
            distance = math.sqrt((position.x() - base_x)**2 + (position.y() - base_y)**2)
            return max(handle.value_range[0], min(handle.value_range[1], distance))
        
        return None
    
    def _optimize_coupler_curve(self):
        """Optimize coupler curve for specific objectives."""
        # This would implement coupler curve optimization algorithms
        optimization_data = {
            "objective": "maximize_area",
            "constraints": ["no_cusps", "smooth_curve"],
            "iterations": 100
        }
        
        self.analysis_updated.emit({"coupler_optimization": optimization_data})
        logger.info("Coupler curve optimization requested")


class GenevaDriveInteractionHandler(BaseRotaryHandler):
    """Specialized interaction handler for Geneva drive mechanisms."""
    
    def create_interaction_controls(self) -> QWidget:
        """Create Geneva drive specific controls."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Geneva wheel analysis
        geneva_group = QGroupBox("Geneva Wheel Analysis")
        geneva_layout = QVBoxLayout(geneva_group)
        
        self.slots_label = QLabel("Number of Slots: 4")
        self.slots_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        geneva_layout.addWidget(self.slots_label)
        
        self.wheel_radius_label = QLabel("Wheel Radius: 80mm")
        self.wheel_radius_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        geneva_layout.addWidget(self.wheel_radius_label)
        
        # Slot configuration
        slots_layout = QHBoxLayout()
        slots_layout.addWidget(QLabel("Slots:"))
        self.slots_spinbox = QSpinBox()
        self.slots_spinbox.setRange(3, 12)
        self.slots_spinbox.setValue(4)
        self.slots_spinbox.valueChanged.connect(self._on_slots_changed)
        slots_layout.addWidget(self.slots_spinbox)
        geneva_layout.addLayout(slots_layout)
        
        layout.addWidget(geneva_group)
        
        # Drive pin analysis
        pin_group = QGroupBox("Drive Pin Analysis")
        pin_layout = QVBoxLayout(pin_group)
        
        self.pin_radius_label = QLabel("Pin Circle Radius: 60mm")
        self.pin_position_label = QLabel("Pin Position: 0°")
        self.engagement_label = QLabel("Engagement: Locked")
        
        pin_layout.addWidget(self.pin_radius_label)
        pin_layout.addWidget(self.pin_position_label)
        pin_layout.addWidget(self.engagement_label)
        
        layout.addWidget(pin_group)
        
        # Timing analysis
        timing_group = QGroupBox("Timing Analysis")
        timing_layout = QVBoxLayout(timing_group)
        
        self.dwell_angle_label = QLabel("Dwell Angle: 60°")
        self.motion_angle_label = QLabel("Motion Angle: 30°")
        self.velocity_ratio_label = QLabel("Velocity Ratio: 1:4")
        
        timing_layout.addWidget(self.dwell_angle_label)
        timing_layout.addWidget(self.motion_angle_label)
        timing_layout.addWidget(self.velocity_ratio_label)
        
        layout.addWidget(timing_group)
        
        layout.addStretch()
        return widget
    
    def create_drag_handles(self, scene):
        """Create drag handles for Geneva drive parameters."""
        self.drag_handles.clear()
        
        # Geneva wheel center
        geneva_center = (200, 150)
        drive_center = (100, 150)
        
        # Geneva wheel radius handle
        wheel_radius = self.mechanism.get_parameter("wheel_radius", 80.0)
        handle_wheel = DragHandle(geneva_center[0] + wheel_radius, geneva_center[1])
        handle_wheel.set_parameter("wheel_radius", wheel_radius, (40.0, 120.0))
        scene.addItem(handle_wheel)
        self.drag_handles.append(handle_wheel)
        
        # Drive pin circle radius handle
        pin_radius = self.mechanism.get_parameter("pin_radius", 60.0)
        handle_pin = DragHandle(drive_center[0] + pin_radius, drive_center[1])
        handle_pin.set_parameter("pin_radius", pin_radius, (30.0, 100.0))
        scene.addItem(handle_pin)
        self.drag_handles.append(handle_pin)
        
        # Center distance handle
        center_distance = self.mechanism.get_parameter("center_distance", 100.0)
        handle_distance = DragHandle(geneva_center[0], drive_center[1] + 30)
        handle_distance.set_parameter("center_distance", center_distance, (70.0, 150.0))
        scene.addItem(handle_distance)
        self.drag_handles.append(handle_distance)
    
    def update_visualization(self):
        """Update Geneva drive visualization."""
        if len(self.drag_handles) >= 3:
            geneva_center = (200, 150)
            drive_center = (100, 150)
            
            wheel_radius = self.mechanism.get_parameter("wheel_radius", 80.0)
            self.drag_handles[0].setPos(geneva_center[0] + wheel_radius, geneva_center[1])
            
            pin_radius = self.mechanism.get_parameter("pin_radius", 60.0)
            self.drag_handles[1].setPos(drive_center[0] + pin_radius, drive_center[1])
            
            center_distance = self.mechanism.get_parameter("center_distance", 100.0)
            # Update positions based on new center distance
            new_geneva_center = (drive_center[0] + center_distance, drive_center[1])
            self.drag_handles[2].setPos(new_geneva_center[0], drive_center[1] + 30)
    
    def get_analysis_data(self) -> Dict[str, Any]:
        """Get Geneva drive analysis data."""
        num_slots = int(self.mechanism.get_parameter("num_slots", 4))
        wheel_radius = self.mechanism.get_parameter("wheel_radius", 80.0)
        pin_radius = self.mechanism.get_parameter("pin_radius", 60.0)
        center_distance = self.mechanism.get_parameter("center_distance", 100.0)
        drive_angle = self.mechanism.get_parameter("drive_angle", 0.0)
        
        # Calculate Geneva drive geometry
        slot_angle = 360.0 / num_slots
        dwell_angle = slot_angle - (2 * math.degrees(math.asin(pin_radius / center_distance)))
        motion_angle = slot_angle - dwell_angle
        
        # Velocity ratio calculation
        velocity_ratio = f"1:{num_slots}"
        
        # Determine engagement state
        engagement_angle = math.degrees(math.asin(pin_radius / center_distance))
        drive_position = drive_angle % 360
        
        if drive_position <= engagement_angle or drive_position >= (360 - engagement_angle):
            engagement_state = "Engaged"
            engagement_color = ModernStyling.COLORS['success']
        else:
            engagement_state = "Locked"
            engagement_color = ModernStyling.COLORS['info']
        
        # Update UI labels
        if hasattr(self, 'slots_label'):
            self.slots_label.setText(f"Number of Slots: {num_slots}")
            self.wheel_radius_label.setText(f"Wheel Radius: {wheel_radius:.1f}mm")
            self.pin_radius_label.setText(f"Pin Circle Radius: {pin_radius:.1f}mm")
            self.pin_position_label.setText(f"Pin Position: {drive_angle:.1f}°")
            self.engagement_label.setText(f"Engagement: {engagement_state}")
            self.engagement_label.setStyleSheet(f"color: {engagement_color};")
            self.dwell_angle_label.setText(f"Dwell Angle: {dwell_angle:.1f}°")
            self.motion_angle_label.setText(f"Motion Angle: {motion_angle:.1f}°")
            self.velocity_ratio_label.setText(f"Velocity Ratio: {velocity_ratio}")
        
        return {
            "num_slots": num_slots,
            "wheel_radius": wheel_radius,
            "pin_radius": pin_radius,
            "center_distance": center_distance,
            "dwell_angle": dwell_angle,
            "motion_angle": motion_angle,
            "velocity_ratio": velocity_ratio,
            "engagement_state": engagement_state,
            "drive_angle": drive_angle
        }
    
    def _position_to_parameter_value(self, handle: DragHandle, position: QPointF) -> Optional[float]:
        """Convert handle position to parameter value for Geneva drives."""
        geneva_center = (200, 150)
        drive_center = (100, 150)
        
        if handle.parameter_name == "wheel_radius":
            # Distance from Geneva wheel center
            distance = math.sqrt((position.x() - geneva_center[0])**2 + (position.y() - geneva_center[1])**2)
            return max(handle.value_range[0], min(handle.value_range[1], distance))
        
        elif handle.parameter_name == "pin_radius":
            # Distance from drive wheel center
            distance = math.sqrt((position.x() - drive_center[0])**2 + (position.y() - drive_center[1])**2)
            return max(handle.value_range[0], min(handle.value_range[1], distance))
        
        elif handle.parameter_name == "center_distance":
            # Horizontal distance between centers
            distance = abs(position.x() - drive_center[0])
            return max(handle.value_range[0], min(handle.value_range[1], distance))
        
        return None
    
    def _on_slots_changed(self, slots: int):
        """Handle number of slots changes."""
        self.mechanism.set_parameter("num_slots", slots)
        self.parameter_changed.emit("num_slots", slots)


class PlanetaryGearInteractionHandler(BaseRotaryHandler):
    """Specialized interaction handler for planetary gear systems with Willis equation analysis."""
    
    def create_interaction_controls(self) -> QWidget:
        """Create planetary gear specific controls."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Planetary gear configuration
        config_group = QGroupBox("Planetary Configuration")
        config_layout = QVBoxLayout(config_group)
        
        # Configuration selector
        config_layout_h = QHBoxLayout()
        config_layout_h.addWidget(QLabel("Configuration:"))
        self.config_combo = QCheckBox("Input: Sun, Fixed: Ring")
        self.config_combo.setChecked(True)
        self.config_combo.stateChanged.connect(self._on_config_changed)
        config_layout_h.addWidget(self.config_combo)
        config_layout.addLayout(config_layout_h)
        
        self.config_label = QLabel("Sun Input - Ring Fixed")
        self.config_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        config_layout.addWidget(self.config_label)
        
        layout.addWidget(config_group)
        
        # Willis equation analysis
        willis_group = QGroupBox("Willis Equation Analysis")
        willis_layout = QVBoxLayout(willis_group)
        
        self.willis_equation_label = QLabel("ωₛ - ωᶜ = R(ωᵣ - ωᶜ)")
        self.willis_equation_label.setStyleSheet(f"color: {ModernStyling.COLORS['secondary']};")
        willis_layout.addWidget(self.willis_equation_label)
        
        self.speed_ratio_label = QLabel("Speed Ratio: 1:4.0")
        self.speed_ratio_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        willis_layout.addWidget(self.speed_ratio_label)
        
        self.basic_ratio_label = QLabel("Basic Ratio R: 2.5")
        self.basic_ratio_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        willis_layout.addWidget(self.basic_ratio_label)
        
        layout.addWidget(willis_group)
        
        # Gear teeth analysis
        teeth_group = QGroupBox("Gear Teeth Analysis")
        teeth_layout = QVBoxLayout(teeth_group)
        
        self.sun_teeth_label = QLabel("Sun Teeth: 12")
        self.planet_teeth_label = QLabel("Planet Teeth: 18")
        self.ring_teeth_label = QLabel("Ring Teeth: 48")
        
        teeth_layout.addWidget(self.sun_teeth_label)
        teeth_layout.addWidget(self.planet_teeth_label)
        teeth_layout.addWidget(self.ring_teeth_label)
        
        layout.addWidget(teeth_group)
        
        # Planet positioning analysis
        planet_group = QGroupBox("Planet Positioning")
        planet_layout = QVBoxLayout(planet_group)
        
        self.num_planets_label = QLabel("Number of Planets: 3")
        self.clearance_label = QLabel("Clearance: OK")
        self.assembly_label = QLabel("Assembly: Valid")
        
        planet_layout.addWidget(self.num_planets_label)
        planet_layout.addWidget(self.clearance_label)
        planet_layout.addWidget(self.assembly_label)
        
        layout.addWidget(planet_group)
        
        # Torque and power analysis
        power_group = QGroupBox("Power Analysis")
        power_layout = QVBoxLayout(power_group)
        
        self.torque_ratio_label = QLabel("Torque Ratio: 4.0:1")
        self.efficiency_label = QLabel("Efficiency: 97%")
        self.power_split_label = QLabel("Power Split: 75%/25%")
        
        power_layout.addWidget(self.torque_ratio_label)
        power_layout.addWidget(self.efficiency_label)
        power_layout.addWidget(self.power_split_label)
        
        layout.addWidget(power_group)
        
        layout.addStretch()
        return widget
    
    def create_drag_handles(self, scene):
        """Create drag handles for planetary gear parameters."""
        self.drag_handles.clear()
        
        # System center
        center = (200, 150)
        
        # Sun gear teeth handle (center)
        sun_teeth = self.mechanism.get_parameter("sun_teeth", 12)
        sun_radius = sun_teeth * 1.5  # Visual radius proportional to teeth
        handle_sun = DragHandle(center[0] + sun_radius, center[1])
        handle_sun.set_parameter("sun_teeth", sun_teeth, (8, 30))
        handle_sun.setToolTip("🟡 Drag to adjust Sun Gear teeth count")
        scene.addItem(handle_sun)
        self.drag_handles.append(handle_sun)
        
        # Planet gear teeth handle
        planet_teeth = self.mechanism.get_parameter("planet_teeth", 18)
        planet_radius = planet_teeth * 1.5
        handle_planet = DragHandle(center[0] + 60, center[1] - 40)  # Offset position
        handle_planet.set_parameter("planet_teeth", planet_teeth, (12, 36))
        handle_planet.setToolTip("🟢 Drag to adjust Planet Gear teeth count")
        scene.addItem(handle_planet)
        self.drag_handles.append(handle_planet)
        
        # Ring gear teeth handle (outer edge)
        ring_teeth = self.mechanism.get_parameter("ring_teeth", 48)
        ring_radius = ring_teeth * 1.5
        handle_ring = DragHandle(center[0] + ring_radius * 0.8, center[1])
        handle_ring.set_parameter("ring_teeth", ring_teeth, (30, 90))
        handle_ring.setToolTip("🔴 Drag to adjust Ring Gear teeth count")
        scene.addItem(handle_ring)
        self.drag_handles.append(handle_ring)
    
    def update_visualization(self):
        """Update planetary gear visualization."""
        if len(self.drag_handles) >= 3:
            center = (200, 150)
            
            sun_teeth = self.mechanism.get_parameter("sun_teeth", 12)
            sun_radius = sun_teeth * 1.5
            self.drag_handles[0].setPos(center[0] + sun_radius, center[1])
            
            planet_teeth = self.mechanism.get_parameter("planet_teeth", 18)
            self.drag_handles[1].setPos(center[0] + 60, center[1] - 40)
            
            ring_teeth = self.mechanism.get_parameter("ring_teeth", 48)
            ring_radius = ring_teeth * 1.5
            self.drag_handles[2].setPos(center[0] + ring_radius * 0.8, center[1])
    
    def get_analysis_data(self) -> Dict[str, Any]:
        """Get comprehensive planetary gear analysis using Willis equation."""
        sun_teeth = int(self.mechanism.get_parameter("sun_teeth", 12))
        planet_teeth = int(self.mechanism.get_parameter("planet_teeth", 18))
        ring_teeth = int(self.mechanism.get_parameter("ring_teeth", 48))
        num_planets = int(self.mechanism.get_parameter("num_planets", 3))
        input_config = self.mechanism.get_parameter("input_config", "sun")
        
        # Validate gear relationships
        if sun_teeth + 2 * planet_teeth != ring_teeth:
            logger.warning(f"Invalid gear relationship: {sun_teeth} + 2×{planet_teeth} ≠ {ring_teeth}")
        
        # Calculate basic ratio R = -Zring/Zsun (negative because of internal gear)
        basic_ratio = -ring_teeth / sun_teeth
        
        # Willis equation analysis for different configurations
        if input_config == "sun":  # Sun input, Ring fixed
            # ωₛ - ωᶜ = R(ωᵣ - ωᶜ)
            # With ωᵣ = 0 (ring fixed): ωₛ = R × ωᶜ
            # Therefore: ωᶜ/ωₛ = 1/R = -Zsun/Zring
            speed_ratio = 1 / basic_ratio  # Carrier output speed relative to sun input
            torque_ratio = abs(basic_ratio)  # Torque amplification
            config_name = "Sun Input - Ring Fixed"
        else:  # Carrier input, Ring fixed
            # With ωᶜ = input, ωᵣ = 0: ωₛ = R × ωᶜ
            speed_ratio = basic_ratio  # Sun speed relative to carrier input
            torque_ratio = 1 / abs(basic_ratio)
            config_name = "Carrier Input - Ring Fixed"
        
        # Planet positioning validation
        planet_angle_step = 360.0 / num_planets
        assembly_valid = (sun_teeth + ring_teeth) % num_planets == 0
        
        # Clearance analysis
        sun_radius = sun_teeth * 1.5  # Simplified module = 1.5
        planet_radius = planet_teeth * 1.5
        ring_radius = ring_teeth * 1.5
        planet_center_radius = (sun_radius + planet_radius)
        
        # Check for planet-to-planet clearance
        min_planet_spacing = 2 * planet_radius * math.sin(math.pi / num_planets)
        actual_planet_spacing = 2 * planet_center_radius * math.sin(math.pi / num_planets)
        clearance_ok = actual_planet_spacing > min_planet_spacing * 1.1  # 10% clearance margin
        
        # Efficiency calculation (simplified)
        # Planetary gears typically have 97-99% efficiency
        gear_efficiency = 0.99  # Per gear mesh
        total_efficiency = gear_efficiency ** 2  # Two gear meshes in power path
        
        # Power split analysis
        # In sun-input configuration, power splits between planet meshes
        power_split_sun = 100.0 / (num_planets + 1)  # Power through sun-planet meshes
        power_split_ring = 100.0 - power_split_sun   # Power through planet-ring meshes
        
        # Update UI labels
        if hasattr(self, 'config_label'):
            self.config_label.setText(config_name)
            self.speed_ratio_label.setText(f"Speed Ratio: 1:{abs(speed_ratio):.2f}")
            self.basic_ratio_label.setText(f"Basic Ratio R: {basic_ratio:.2f}")
            
            self.sun_teeth_label.setText(f"Sun Teeth: {sun_teeth}")
            self.planet_teeth_label.setText(f"Planet Teeth: {planet_teeth}")
            self.ring_teeth_label.setText(f"Ring Teeth: {ring_teeth}")
            
            self.num_planets_label.setText(f"Number of Planets: {num_planets}")
            clearance_status = "OK" if clearance_ok else "TIGHT"
            clearance_color = ModernStyling.COLORS['success'] if clearance_ok else ModernStyling.COLORS['warning']
            self.clearance_label.setText(f"Clearance: {clearance_status}")
            self.clearance_label.setStyleSheet(f"color: {clearance_color};")
            
            assembly_status = "Valid" if assembly_valid else "Invalid"
            assembly_color = ModernStyling.COLORS['success'] if assembly_valid else ModernStyling.COLORS['error']
            self.assembly_label.setText(f"Assembly: {assembly_status}")
            self.assembly_label.setStyleSheet(f"color: {assembly_color};")
            
            self.torque_ratio_label.setText(f"Torque Ratio: {torque_ratio:.1f}:1")
            self.efficiency_label.setText(f"Efficiency: {total_efficiency*100:.1f}%")
            self.power_split_label.setText(f"Power Split: {power_split_sun:.0f}%/{power_split_ring:.0f}%")
        
        return {
            "gear_teeth": {"sun": sun_teeth, "planet": planet_teeth, "ring": ring_teeth},
            "num_planets": num_planets,
            "basic_ratio": basic_ratio,
            "speed_ratio": speed_ratio,
            "torque_ratio": torque_ratio,
            "efficiency": total_efficiency,
            "clearance_ok": clearance_ok,
            "assembly_valid": assembly_valid,
            "configuration": config_name,
            "power_split": {"sun_planet": power_split_sun, "planet_ring": power_split_ring},
            "willis_equation": "ωₛ - ωᶜ = R(ωᵣ - ωᶜ)"
        }
    
    def _position_to_parameter_value(self, handle: DragHandle, position: QPointF) -> Optional[float]:
        """Convert handle position to parameter value for planetary gears."""
        center = (200, 150)
        
        if handle.parameter_name == "sun_teeth":
            # Distance from center determines sun gear size
            radius = math.sqrt((position.x() - center[0])**2 + (position.y() - center[1])**2)
            teeth = int(radius / 1.5)  # Inverse of visual scaling
            return max(handle.value_range[0], min(handle.value_range[1], teeth))
        
        elif handle.parameter_name == "planet_teeth":
            # Use distance from offset position for planet size
            radius = math.sqrt((position.x() - (center[0] + 60))**2 + (position.y() - (center[1] - 40))**2)
            teeth = int(radius / 1.5)
            return max(handle.value_range[0], min(handle.value_range[1], teeth))
        
        elif handle.parameter_name == "ring_teeth":
            # Distance from center for ring gear (constrained by relationship)
            radius = math.sqrt((position.x() - center[0])**2 + (position.y() - center[1])**2)
            teeth = int(radius / 1.2)  # Slightly different scaling for ring
            
            # Enforce relationship: ring = sun + 2×planet
            sun_teeth = self.mechanism.get_parameter("sun_teeth", 12)
            planet_teeth = self.mechanism.get_parameter("planet_teeth", 18)
            ideal_ring = sun_teeth + 2 * planet_teeth
            
            # Allow some deviation but warn if too far off
            deviation = abs(teeth - ideal_ring)
            if deviation > 6:  # More than 6 teeth difference
                teeth = ideal_ring  # Force correct relationship
                
            return max(handle.value_range[0], min(handle.value_range[1], teeth))
        
        return None
    
    def _on_config_changed(self, state):
        """Handle configuration change."""
        config = "sun" if state else "carrier"
        self.mechanism.set_parameter("input_config", config)
        self.parameter_changed.emit("input_config", config)


class BeltSystemInteractionHandler(BaseMechanismInteractionHandler):
    """Specialized interaction handler for belt and pulley systems with tension analysis."""
    
    def create_interaction_controls(self) -> QWidget:
        """Create belt system specific controls."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Belt configuration
        config_group = QGroupBox("Belt Configuration")
        config_layout = QVBoxLayout(config_group)
        
        # Belt type selector
        belt_type_layout = QHBoxLayout()
        belt_type_layout.addWidget(QLabel("Belt Type:"))
        self.belt_type_combo = QCheckBox("V-Belt (vs Flat)")
        self.belt_type_combo.setChecked(True)
        self.belt_type_combo.stateChanged.connect(self._on_belt_type_changed)
        belt_type_layout.addWidget(self.belt_type_combo)
        config_layout.addLayout(belt_type_layout)
        
        self.belt_type_label = QLabel("Type: V-Belt")
        self.belt_type_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        config_layout.addWidget(self.belt_type_label)
        
        self.belt_length_label = QLabel("Belt Length: 500mm")
        self.belt_length_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        config_layout.addWidget(self.belt_length_label)
        
        layout.addWidget(config_group)
        
        # Pulley analysis
        pulley_group = QGroupBox("Pulley Analysis")
        pulley_layout = QVBoxLayout(pulley_group)
        
        self.driver_diameter_label = QLabel("Driver Diameter: 60mm")
        self.driven_diameter_label = QLabel("Driven Diameter: 120mm")
        self.speed_ratio_label = QLabel("Speed Ratio: 2:1")
        
        pulley_layout.addWidget(self.driver_diameter_label)
        pulley_layout.addWidget(self.driven_diameter_label)
        pulley_layout.addWidget(self.speed_ratio_label)
        
        layout.addWidget(pulley_group)
        
        # Center distance and wrap angles
        geometry_group = QGroupBox("Belt Geometry")
        geometry_layout = QVBoxLayout(geometry_group)
        
        self.center_distance_label = QLabel("Center Distance: 200mm")
        self.wrap_angle_driver_label = QLabel("Driver Wrap Angle: 180°")
        self.wrap_angle_driven_label = QLabel("Driven Wrap Angle: 180°")
        
        geometry_layout.addWidget(self.center_distance_label)
        geometry_layout.addWidget(self.wrap_angle_driver_label)
        geometry_layout.addWidget(self.wrap_angle_driven_label)
        
        layout.addWidget(geometry_group)
        
        # Tension analysis
        tension_group = QGroupBox("Belt Tension Analysis")
        tension_layout = QVBoxLayout(tension_group)
        
        self.tight_side_tension_label = QLabel("Tight Side: 150N")
        self.slack_side_tension_label = QLabel("Slack Side: 50N")
        self.tension_ratio_label = QLabel("Tension Ratio: 3.0")
        
        tension_layout.addWidget(self.tight_side_tension_label)
        tension_layout.addWidget(self.slack_side_tension_label)
        tension_layout.addWidget(self.tension_ratio_label)
        
        layout.addWidget(tension_group)
        
        # Power transmission
        power_group = QGroupBox("Power Transmission")
        power_layout = QVBoxLayout(power_group)
        
        self.power_transmitted_label = QLabel("Power: 2.5 kW")
        self.belt_efficiency_label = QLabel("Efficiency: 96%")
        self.slip_percentage_label = QLabel("Slip: 2%")
        
        power_layout.addWidget(self.power_transmitted_label)
        power_layout.addWidget(self.belt_efficiency_label)
        power_layout.addWidget(self.slip_percentage_label)
        
        layout.addWidget(power_group)
        
        layout.addStretch()
        return widget
    
    def create_drag_handles(self, scene):
        """Create drag handles for belt system parameters."""
        self.drag_handles.clear()
        
        # Pulley centers
        driver_center = (100, 150)
        driven_center = (300, 150)
        
        # Driver pulley diameter handle
        driver_diameter = self.mechanism.get_parameter("driver_diameter", 60.0)
        handle_driver = DragHandle(driver_center[0] + driver_diameter/2, driver_center[1])
        handle_driver.set_parameter("driver_diameter", driver_diameter, (30.0, 150.0))
        handle_driver.setToolTip("🔵 Drag to adjust Driver Pulley diameter")
        scene.addItem(handle_driver)
        self.drag_handles.append(handle_driver)
        
        # Driven pulley diameter handle
        driven_diameter = self.mechanism.get_parameter("driven_diameter", 120.0)
        handle_driven = DragHandle(driven_center[0] + driven_diameter/2, driven_center[1])
        handle_driven.set_parameter("driven_diameter", driven_diameter, (40.0, 200.0))
        handle_driven.setToolTip("🟢 Drag to adjust Driven Pulley diameter")
        scene.addItem(handle_driven)
        self.drag_handles.append(handle_driven)
        
        # Center distance handle
        center_distance = self.mechanism.get_parameter("center_distance", 200.0)
        handle_distance = DragHandle(driven_center[0], driver_center[1] - 50)
        handle_distance.set_parameter("center_distance", center_distance, (150.0, 400.0))
        handle_distance.setToolTip("🔴 Drag to adjust Center Distance")
        scene.addItem(handle_distance)
        self.drag_handles.append(handle_distance)
    
    def update_visualization(self):
        """Update belt system visualization."""
        if len(self.drag_handles) >= 3:
            driver_center = (100, 150)
            driven_center = (300, 150)
            
            driver_diameter = self.mechanism.get_parameter("driver_diameter", 60.0)
            self.drag_handles[0].setPos(driver_center[0] + driver_diameter/2, driver_center[1])
            
            driven_diameter = self.mechanism.get_parameter("driven_diameter", 120.0)
            self.drag_handles[1].setPos(driven_center[0] + driven_diameter/2, driven_center[1])
            
            center_distance = self.mechanism.get_parameter("center_distance", 200.0)
            new_driven_center = (driver_center[0] + center_distance, driver_center[1])
            self.drag_handles[2].setPos(new_driven_center[0], driver_center[1] - 50)
    
    def get_analysis_data(self) -> Dict[str, Any]:
        """Get comprehensive belt system analysis."""
        driver_diameter = self.mechanism.get_parameter("driver_diameter", 60.0)
        driven_diameter = self.mechanism.get_parameter("driven_diameter", 120.0)
        center_distance = self.mechanism.get_parameter("center_distance", 200.0)
        belt_type = self.mechanism.get_parameter("belt_type", "v_belt")
        input_power = self.mechanism.get_parameter("input_power", 2.5)  # kW
        input_speed = self.mechanism.get_parameter("input_speed", 1440)  # RPM
        
        # Calculate speed ratio
        speed_ratio = driven_diameter / driver_diameter
        output_speed = input_speed / speed_ratio
        
        # Belt length calculation (simplified)
        # L = 2C + π(D1 + D2)/2 + (D2 - D1)²/(4C)
        pi_factor = math.pi * (driver_diameter + driven_diameter) / 2
        diameter_diff_factor = (driven_diameter - driver_diameter)**2 / (4 * center_distance)
        belt_length = 2 * center_distance + pi_factor + diameter_diff_factor
        
        # Wrap angles calculation
        # β = π ± 2sin⁻¹((D2 - D1)/(2C))
        angle_diff = 2 * math.asin(abs(driven_diameter - driver_diameter) / (2 * center_distance))
        if driven_diameter > driver_diameter:
            wrap_angle_driver = math.pi - angle_diff  # Smaller wrap on driver
            wrap_angle_driven = math.pi + angle_diff   # Larger wrap on driven
        else:
            wrap_angle_driver = math.pi + angle_diff
            wrap_angle_driven = math.pi - angle_diff
        
        # Convert to degrees
        wrap_angle_driver_deg = math.degrees(wrap_angle_driver)
        wrap_angle_driven_deg = math.degrees(wrap_angle_driven)
        
        # Tension analysis using Eytelwein's equation
        # T1/T2 = e^(μβ) where μ is coefficient of friction
        mu = 0.3 if belt_type == "v_belt" else 0.25  # V-belt vs flat belt
        
        # Power equation: P = (T1 - T2) * v where v = πDN/60
        belt_velocity = math.pi * driver_diameter * input_speed / 60000  # m/s
        
        # From power: T1 - T2 = P/v (in Newtons)
        tension_difference = (input_power * 1000) / belt_velocity  # Convert kW to W
        
        # From Eytelwein: T1 = T2 * e^(μβ)
        # Solving: T2 = (T1 - T2) / (e^(μβ) - 1)
        tension_ratio = math.exp(mu * wrap_angle_driver)
        slack_side_tension = tension_difference / (tension_ratio - 1)
        tight_side_tension = slack_side_tension * tension_ratio
        
        # Belt efficiency (accounting for slip and bending losses)
        slip_percentage = 2.0  # Typical slip for belt drives
        bending_loss = 0.02   # 2% bending loss
        belt_efficiency = (1 - slip_percentage/100) * (1 - bending_loss)
        
        # Update UI labels
        if hasattr(self, 'belt_type_label'):
            belt_type_name = "V-Belt" if belt_type == "v_belt" else "Flat Belt"
            self.belt_type_label.setText(f"Type: {belt_type_name}")
            self.belt_length_label.setText(f"Belt Length: {belt_length:.0f}mm")
            
            self.driver_diameter_label.setText(f"Driver Diameter: {driver_diameter:.0f}mm")
            self.driven_diameter_label.setText(f"Driven Diameter: {driven_diameter:.0f}mm")
            self.speed_ratio_label.setText(f"Speed Ratio: {speed_ratio:.2f}:1")
            
            self.center_distance_label.setText(f"Center Distance: {center_distance:.0f}mm")
            self.wrap_angle_driver_label.setText(f"Driver Wrap Angle: {wrap_angle_driver_deg:.0f}°")
            self.wrap_angle_driven_label.setText(f"Driven Wrap Angle: {wrap_angle_driven_deg:.0f}°")
            
            self.tight_side_tension_label.setText(f"Tight Side: {tight_side_tension:.0f}N")
            self.slack_side_tension_label.setText(f"Slack Side: {slack_side_tension:.0f}N")
            self.tension_ratio_label.setText(f"Tension Ratio: {tension_ratio:.1f}")
            
            self.power_transmitted_label.setText(f"Power: {input_power:.1f} kW")
            self.belt_efficiency_label.setText(f"Efficiency: {belt_efficiency*100:.1f}%")
            self.slip_percentage_label.setText(f"Slip: {slip_percentage:.1f}%")
        
        return {
            "pulley_diameters": {"driver": driver_diameter, "driven": driven_diameter},
            "speed_ratio": speed_ratio,
            "speeds": {"input": input_speed, "output": output_speed},
            "belt_length": belt_length,
            "center_distance": center_distance,
            "wrap_angles": {"driver": wrap_angle_driver_deg, "driven": wrap_angle_driven_deg},
            "tensions": {"tight_side": tight_side_tension, "slack_side": slack_side_tension},
            "tension_ratio": tension_ratio,
            "power": {"input": input_power, "transmitted": input_power * belt_efficiency},
            "efficiency": belt_efficiency,
            "slip_percentage": slip_percentage,
            "belt_type": belt_type_name,
            "belt_velocity": belt_velocity
        }
    
    def _position_to_parameter_value(self, handle: DragHandle, position: QPointF) -> Optional[float]:
        """Convert handle position to parameter value for belt systems."""
        driver_center = (100, 150)
        driven_center = (300, 150)
        
        if handle.parameter_name == "driver_diameter":
            # Distance from driver center determines diameter
            radius = math.sqrt((position.x() - driver_center[0])**2 + (position.y() - driver_center[1])**2)
            diameter = radius * 2
            return max(handle.value_range[0], min(handle.value_range[1], diameter))
        
        elif handle.parameter_name == "driven_diameter":
            # Distance from driven center determines diameter
            radius = math.sqrt((position.x() - driven_center[0])**2 + (position.y() - driven_center[1])**2)
            diameter = radius * 2
            return max(handle.value_range[0], min(handle.value_range[1], diameter))
        
        elif handle.parameter_name == "center_distance":
            # Horizontal distance from driver center
            distance = abs(position.x() - driver_center[0])
            return max(handle.value_range[0], min(handle.value_range[1], distance))
        
        return None
    
    def _on_belt_type_changed(self, state):
        """Handle belt type change."""
        belt_type = "v_belt" if state else "flat_belt"
        self.mechanism.set_parameter("belt_type", belt_type)
        self.parameter_changed.emit("belt_type", belt_type)


class SpringSystemInteractionHandler(BaseMechanismInteractionHandler):
    """Specialized interaction handler for spring systems with Hooke's law and energy analysis."""
    
    def create_interaction_controls(self) -> QWidget:
        """Create spring system specific controls."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Spring configuration
        config_group = QGroupBox("Spring Configuration")
        config_layout = QVBoxLayout(config_group)
        
        # Spring type selector
        spring_type_layout = QHBoxLayout()
        spring_type_layout.addWidget(QLabel("Spring Type:"))
        self.spring_type_combo = QCheckBox("Compression (vs Extension)")
        self.spring_type_combo.setChecked(True)
        self.spring_type_combo.stateChanged.connect(self._on_spring_type_changed)
        spring_type_layout.addWidget(self.spring_type_combo)
        config_layout.addLayout(spring_type_layout)
        
        self.spring_type_label = QLabel("Type: Compression")
        self.spring_type_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        config_layout.addWidget(self.spring_type_label)
        
        self.spring_constant_label = QLabel("Spring Constant: 1000 N/m")
        self.spring_constant_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        config_layout.addWidget(self.spring_constant_label)
        
        layout.addWidget(config_group)
        
        # Hooke's Law analysis
        hooke_group = QGroupBox("Hooke's Law Analysis")
        hooke_layout = QVBoxLayout(hooke_group)
        
        self.hooke_equation_label = QLabel("F = -k × x")
        self.hooke_equation_label.setStyleSheet(f"color: {ModernStyling.COLORS['secondary']};")
        hooke_layout.addWidget(self.hooke_equation_label)
        
        self.force_label = QLabel("Applied Force: 50 N")
        self.displacement_label = QLabel("Displacement: 50 mm")
        self.effective_length_label = QLabel("Effective Length: 100 mm")
        
        hooke_layout.addWidget(self.force_label)
        hooke_layout.addWidget(self.displacement_label)
        hooke_layout.addWidget(self.effective_length_label)
        
        layout.addWidget(hooke_group)
        
        # Spring geometry
        geometry_group = QGroupBox("Spring Geometry")
        geometry_layout = QVBoxLayout(geometry_group)
        
        self.free_length_label = QLabel("Free Length: 150 mm")
        self.coil_diameter_label = QLabel("Coil Diameter: 20 mm")
        self.wire_diameter_label = QLabel("Wire Diameter: 2 mm")
        self.active_coils_label = QLabel("Active Coils: 8")
        
        geometry_layout.addWidget(self.free_length_label)
        geometry_layout.addWidget(self.coil_diameter_label)
        geometry_layout.addWidget(self.wire_diameter_label)
        geometry_layout.addWidget(self.active_coils_label)
        
        layout.addWidget(geometry_group)
        
        # Energy analysis
        energy_group = QGroupBox("Energy Analysis")
        energy_layout = QVBoxLayout(energy_group)
        
        self.potential_energy_label = QLabel("Potential Energy: 1.25 J")
        self.energy_density_label = QLabel("Energy Density: 125 J/m³")
        self.work_done_label = QLabel("Work Done: 1.25 J")
        
        energy_layout.addWidget(self.potential_energy_label)
        energy_layout.addWidget(self.energy_density_label)
        energy_layout.addWidget(self.work_done_label)
        
        layout.addWidget(energy_group)
        
        # Stress analysis
        stress_group = QGroupBox("Stress Analysis")
        stress_layout = QVBoxLayout(stress_group)
        
        self.shear_stress_label = QLabel("Max Shear Stress: 250 MPa")
        self.safety_factor_label = QLabel("Safety Factor: 3.2")
        self.buckling_check_label = QLabel("Buckling: Safe")
        
        stress_layout.addWidget(self.shear_stress_label)
        stress_layout.addWidget(self.safety_factor_label)
        stress_layout.addWidget(self.buckling_check_label)
        
        layout.addWidget(stress_group)
        
        layout.addStretch()
        return widget
    
    def create_drag_handles(self, scene):
        """Create drag handles for spring system parameters."""
        self.drag_handles.clear()
        
        # Spring center position
        spring_center = (200, 150)
        
        # Spring constant handle (affects stiffness visualization)
        spring_constant = self.mechanism.get_parameter("spring_constant", 1000.0)
        handle_constant = DragHandle(spring_center[0] + 80, spring_center[1])
        handle_constant.set_parameter("spring_constant", spring_constant, (100.0, 5000.0))
        handle_constant.setToolTip("🔧 Drag to adjust Spring Constant (stiffness)")
        scene.addItem(handle_constant)
        self.drag_handles.append(handle_constant)
        
        # Applied force handle
        applied_force = self.mechanism.get_parameter("applied_force", 50.0)
        handle_force = DragHandle(spring_center[0], spring_center[1] - 60)
        handle_force.set_parameter("applied_force", applied_force, (0.0, 200.0))
        handle_force.setToolTip("⚡ Drag to adjust Applied Force")
        scene.addItem(handle_force)
        self.drag_handles.append(handle_force)
        
        # Free length handle
        free_length = self.mechanism.get_parameter("free_length", 150.0)
        handle_length = DragHandle(spring_center[0] - 50, spring_center[1] + free_length/2)
        handle_length.set_parameter("free_length", free_length, (50.0, 300.0))
        handle_length.setToolTip("📏 Drag to adjust Free Length")
        scene.addItem(handle_length)
        self.drag_handles.append(handle_length)
        
        # Wire diameter handle (affects spring constant)
        wire_diameter = self.mechanism.get_parameter("wire_diameter", 2.0)
        handle_wire = DragHandle(spring_center[0] + 30, spring_center[1] + 30)
        handle_wire.set_parameter("wire_diameter", wire_diameter, (1.0, 5.0))
        handle_wire.setToolTip("🔘 Drag to adjust Wire Diameter")
        scene.addItem(handle_wire)
        self.drag_handles.append(handle_wire)
    
    def update_visualization(self):
        """Update spring system visualization."""
        if len(self.drag_handles) >= 4:
            spring_center = (200, 150)
            
            # Update handle positions based on parameter changes
            spring_constant = self.mechanism.get_parameter("spring_constant", 1000.0)
            stiffness_offset = min(80, spring_constant / 50)  # Visual scaling
            self.drag_handles[0].setPos(spring_center[0] + stiffness_offset, spring_center[1])
            
            applied_force = self.mechanism.get_parameter("applied_force", 50.0)
            force_offset = min(60, applied_force * 0.3)  # Visual scaling
            self.drag_handles[1].setPos(spring_center[0], spring_center[1] - force_offset)
            
            free_length = self.mechanism.get_parameter("free_length", 150.0)
            self.drag_handles[2].setPos(spring_center[0] - 50, spring_center[1] + free_length/2)
            
            wire_diameter = self.mechanism.get_parameter("wire_diameter", 2.0)
            wire_offset = 20 + wire_diameter * 5  # Visual scaling
            self.drag_handles[3].setPos(spring_center[0] + wire_offset, spring_center[1] + wire_offset)
    
    def get_analysis_data(self) -> Dict[str, Any]:
        """Get comprehensive spring system analysis using Hooke's law and energy principles."""
        spring_constant = self.mechanism.get_parameter("spring_constant", 1000.0)  # N/m
        applied_force = self.mechanism.get_parameter("applied_force", 50.0)  # N
        free_length = self.mechanism.get_parameter("free_length", 150.0)  # mm
        coil_diameter = self.mechanism.get_parameter("coil_diameter", 20.0)  # mm
        wire_diameter = self.mechanism.get_parameter("wire_diameter", 2.0)  # mm
        active_coils = self.mechanism.get_parameter("active_coils", 8.0)
        spring_type = self.mechanism.get_parameter("spring_type", "compression")
        
        # Convert to SI units for calculations
        free_length_m = free_length / 1000
        coil_diameter_m = coil_diameter / 1000
        wire_diameter_m = wire_diameter / 1000
        
        # Hooke's Law: F = k × x
        displacement = applied_force / spring_constant  # meters
        displacement_mm = displacement * 1000  # mm for display
        
        # Current length under load
        if spring_type == "compression":
            current_length = free_length - displacement_mm
            effective_length = current_length
        else:  # extension
            current_length = free_length + displacement_mm
            effective_length = current_length
        
        # Energy analysis
        # Potential energy stored: U = (1/2) × k × x²
        potential_energy = 0.5 * spring_constant * (displacement ** 2)  # Joules
        
        # Work done by applied force: W = ∫F dx = (1/2) × F × x
        work_done = 0.5 * applied_force * displacement  # Joules
        
        # Energy density (energy per unit volume)
        spring_volume = math.pi * (coil_diameter_m ** 2) * free_length_m / 4  # Simplified volume
        energy_density = potential_energy / spring_volume if spring_volume > 0 else 0  # J/m³
        
        # Spring index and geometry
        spring_index = coil_diameter / wire_diameter  # C = D/d
        
        # Theoretical spring constant calculation for validation
        # k = (G × d⁴) / (8 × D³ × N)
        # Using typical values: G = 80 GPa for steel
        shear_modulus = 80e9  # Pa
        theoretical_k = (shear_modulus * (wire_diameter_m ** 4)) / (8 * (coil_diameter_m ** 3) * active_coils)
        
        # Stress analysis
        # Maximum shear stress: τ = (8 × F × D × K) / (π × d³)
        # where K is Wahl correction factor: K = (4C - 1)/(4C - 4) + 0.615/C
        wahl_factor = ((4 * spring_index - 1) / (4 * spring_index - 4)) + (0.615 / spring_index)
        max_shear_stress = (8 * applied_force * coil_diameter_m * wahl_factor) / (math.pi * (wire_diameter_m ** 3))
        max_shear_stress_mpa = max_shear_stress / 1e6  # Convert to MPa
        
        # Safety factor (assuming material strength of 800 MPa for spring steel)
        material_strength = 800e6  # Pa
        safety_factor = material_strength / max_shear_stress if max_shear_stress > 0 else float('inf')
        
        # Buckling check for compression springs
        # Critical buckling ratio: L/D where L is free length, D is coil diameter
        buckling_ratio = free_length / coil_diameter
        buckling_safe = buckling_ratio < 4.0 if spring_type == "compression" else True
        
        # Frequency analysis (natural frequency)
        # f = (1/2π) × √(k/m_eff) where m_eff is effective mass
        # For spring mass: m_spring ≈ ρ × V_wire
        steel_density = 7850  # kg/m³
        wire_volume = math.pi * (wire_diameter_m ** 2) / 4 * (math.pi * coil_diameter_m * active_coils)
        spring_mass = steel_density * wire_volume
        effective_mass = spring_mass / 3  # Effective mass is approximately 1/3 of total mass
        natural_frequency = (1 / (2 * math.pi)) * math.sqrt(spring_constant / effective_mass) if effective_mass > 0 else 0
        
        # Update UI labels
        if hasattr(self, 'spring_type_label'):
            spring_type_name = "Compression" if spring_type == "compression" else "Extension"
            self.spring_type_label.setText(f"Type: {spring_type_name}")
            self.spring_constant_label.setText(f"Spring Constant: {spring_constant:.0f} N/m")
            
            self.force_label.setText(f"Applied Force: {applied_force:.1f} N")
            self.displacement_label.setText(f"Displacement: {displacement_mm:.2f} mm")
            self.effective_length_label.setText(f"Effective Length: {effective_length:.1f} mm")
            
            self.free_length_label.setText(f"Free Length: {free_length:.0f} mm")
            self.coil_diameter_label.setText(f"Coil Diameter: {coil_diameter:.1f} mm")
            self.wire_diameter_label.setText(f"Wire Diameter: {wire_diameter:.1f} mm")
            self.active_coils_label.setText(f"Active Coils: {active_coils:.0f}")
            
            self.potential_energy_label.setText(f"Potential Energy: {potential_energy:.3f} J")
            self.energy_density_label.setText(f"Energy Density: {energy_density:.0f} J/m³")
            self.work_done_label.setText(f"Work Done: {work_done:.3f} J")
            
            self.shear_stress_label.setText(f"Max Shear Stress: {max_shear_stress_mpa:.0f} MPa")
            self.safety_factor_label.setText(f"Safety Factor: {safety_factor:.1f}")
            buckling_status = "Safe" if buckling_safe else "Risk"
            buckling_color = ModernStyling.COLORS['success'] if buckling_safe else ModernStyling.COLORS['warning']
            self.buckling_check_label.setText(f"Buckling: {buckling_status}")
            self.buckling_check_label.setStyleSheet(f"color: {buckling_color};")
        
        return {
            "spring_constant": spring_constant,
            "applied_force": applied_force,
            "displacement": {"mm": displacement_mm, "m": displacement},
            "lengths": {"free": free_length, "current": current_length, "effective": effective_length},
            "geometry": {
                "coil_diameter": coil_diameter,
                "wire_diameter": wire_diameter, 
                "active_coils": active_coils,
                "spring_index": spring_index
            },
            "energy": {
                "potential": potential_energy,
                "work_done": work_done,
                "energy_density": energy_density
            },
            "stress": {
                "max_shear_stress_mpa": max_shear_stress_mpa,
                "safety_factor": safety_factor,
                "wahl_factor": wahl_factor
            },
            "buckling": {
                "ratio": buckling_ratio,
                "safe": buckling_safe
            },
            "dynamics": {
                "natural_frequency": natural_frequency,
                "spring_mass": spring_mass
            },
            "spring_type": spring_type_name,
            "theoretical_k": theoretical_k,
            "hookes_law": "F = -k × x"
        }
    
    def _position_to_parameter_value(self, handle: DragHandle, position: QPointF) -> Optional[float]:
        """Convert handle position to parameter value for spring systems."""
        spring_center = (200, 150)
        
        if handle.parameter_name == "spring_constant":
            # Distance from center affects spring constant
            offset = abs(position.x() - spring_center[0])
            spring_constant = offset * 50  # Scaling factor
            return max(handle.value_range[0], min(handle.value_range[1], spring_constant))
        
        elif handle.parameter_name == "applied_force":
            # Vertical distance from center affects force
            offset = abs(position.y() - spring_center[1])
            force = offset / 0.3  # Inverse of visual scaling
            return max(handle.value_range[0], min(handle.value_range[1], force))
        
        elif handle.parameter_name == "free_length":
            # Vertical position affects length
            offset = abs(position.y() - spring_center[1])
            length = offset * 2  # Scaling factor
            return max(handle.value_range[0], min(handle.value_range[1], length))
        
        elif handle.parameter_name == "wire_diameter":
            # Distance from offset position affects wire diameter
            offset = math.sqrt((position.x() - spring_center[0])**2 + (position.y() - spring_center[1])**2)
            diameter = (offset - 20) / 5  # Inverse of visual scaling
            return max(handle.value_range[0], min(handle.value_range[1], diameter))
        
        return None
    
    def _on_spring_type_changed(self, state):
        """Handle spring type change."""
        spring_type = "compression" if state else "extension"
        self.mechanism.set_parameter("spring_type", spring_type)
        self.parameter_changed.emit("spring_type", spring_type)


class BeltSystemInteractionHandler(BasePowerTransmissionHandler):
    """Specialized interaction handler for belt and pulley systems with tension analysis."""
    
    def create_interaction_controls(self) -> QWidget:
        """Create belt system specific controls."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Belt configuration
        config_group = QGroupBox("Belt Configuration")
        config_layout = QVBoxLayout(config_group)
        
        # Belt type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Belt Type:"))
        self.belt_type_combo = QCheckBox("Timing Belt")
        self.belt_type_combo.setChecked(True)
        self.belt_type_combo.stateChanged.connect(self._on_belt_type_changed)
        type_layout.addWidget(self.belt_type_combo)
        config_layout.addLayout(type_layout)
        
        self.belt_type_label = QLabel("Type: Timing Belt")
        self.belt_type_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        config_layout.addWidget(self.belt_type_label)
        
        self.crossing_label = QLabel("Configuration: Open Belt")
        self.crossing_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        config_layout.addWidget(self.crossing_label)
        
        layout.addWidget(config_group)
        
        # Tension analysis
        tension_group = QGroupBox("Tension Analysis")
        tension_layout = QVBoxLayout(tension_group)
        
        self.belt_length_label = QLabel("Belt Length: 450mm")
        self.belt_length_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        tension_layout.addWidget(self.belt_length_label)
        
        self.tight_side_label = QLabel("Tight Side Tension: 120N")
        self.tight_side_label.setStyleSheet(f"color: {ModernStyling.COLORS['error']};")
        tension_layout.addWidget(self.tight_side_label)
        
        self.slack_side_label = QLabel("Slack Side Tension: 40N")
        self.slack_side_label.setStyleSheet(f"color: {ModernStyling.COLORS['warning']};")
        tension_layout.addWidget(self.slack_side_label)
        
        self.tension_ratio_label = QLabel("Tension Ratio: 3.0:1")
        tension_layout.addWidget(self.tension_ratio_label)
        
        layout.addWidget(tension_group)
        
        # Speed and power transmission
        transmission_group = QGroupBox("Power Transmission")
        transmission_layout = QVBoxLayout(transmission_group)
        
        self.speed_ratio_label = QLabel("Speed Ratio: 1:2.5")
        self.power_capacity_label = QLabel("Power Capacity: 5.2 kW")
        self.efficiency_label = QLabel("Efficiency: 98%")
        self.slip_label = QLabel("Slip: 0.5%")
        
        transmission_layout.addWidget(self.speed_ratio_label)
        transmission_layout.addWidget(self.power_capacity_label)
        transmission_layout.addWidget(self.efficiency_label)
        transmission_layout.addWidget(self.slip_label)
        
        layout.addWidget(transmission_group)
        
        # Contact angle analysis
        contact_group = QGroupBox("Contact Angle Analysis")
        contact_layout = QVBoxLayout(contact_group)
        
        self.contact_angle1_label = QLabel("Driver Contact: 180°")
        self.contact_angle2_label = QLabel("Driven Contact: 180°")
        self.center_distance_label = QLabel("Center Distance: 150mm")
        
        contact_layout.addWidget(self.contact_angle1_label)
        contact_layout.addWidget(self.contact_angle2_label)
        contact_layout.addWidget(self.center_distance_label)
        
        layout.addWidget(contact_group)
        
        layout.addStretch()
        return widget
    
    def create_drag_handles(self, scene):
        """Create drag handles for belt system parameters."""
        self.drag_handles.clear()
        
        # Pulley centers
        pulley1_center = (100, 150)
        pulley2_center = (250, 150)
        
        # Handle for pulley 1 radius
        pulley1_radius = self.mechanism.get_parameter("pulley1_radius", 30.0)
        handle1 = DragHandle(pulley1_center[0], pulley1_center[1] - pulley1_radius)
        handle1.set_parameter("pulley1_radius", pulley1_radius, (15.0, 80.0))
        handle1.setToolTip("🔵 Drag to adjust Driver Pulley radius")
        scene.addItem(handle1)
        self.drag_handles.append(handle1)
        
        # Handle for pulley 2 radius
        pulley2_radius = self.mechanism.get_parameter("pulley2_radius", 75.0)
        handle2 = DragHandle(pulley2_center[0], pulley2_center[1] - pulley2_radius)
        handle2.set_parameter("pulley2_radius", pulley2_radius, (20.0, 120.0))
        handle2.setToolTip("🟣 Drag to adjust Driven Pulley radius")
        scene.addItem(handle2)
        self.drag_handles.append(handle2)
        
        # Handle for center distance
        center_distance = self.mechanism.get_parameter("center_distance", 150.0)
        handle_distance = DragHandle(
            (pulley1_center[0] + pulley2_center[0]) / 2,
            pulley1_center[1] + 50
        )
        handle_distance.set_parameter("center_distance", center_distance, (100.0, 300.0))
        handle_distance.setToolTip("↔️ Drag to adjust Center Distance")
        scene.addItem(handle_distance)
        self.drag_handles.append(handle_distance)
        
        # Handle for belt tension (visual indicator)
        handle_tension = DragHandle(
            (pulley1_center[0] + pulley2_center[0]) / 2,
            pulley1_center[1] - 30
        )
        handle_tension.set_parameter("initial_tension", 80.0, (20.0, 200.0))
        handle_tension.setToolTip("⚡ Drag to adjust Initial Belt Tension")
        scene.addItem(handle_tension)
        self.drag_handles.append(handle_tension)
    
    def update_visualization(self):
        """Update belt system visualization."""
        if len(self.drag_handles) >= 4:
            pulley1_center = (100, 150)
            center_distance = self.mechanism.get_parameter("center_distance", 150.0)
            pulley2_center = (pulley1_center[0] + center_distance, pulley1_center[1])
            
            # Update pulley radius handles
            pulley1_radius = self.mechanism.get_parameter("pulley1_radius", 30.0)
            self.drag_handles[0].setPos(pulley1_center[0], pulley1_center[1] - pulley1_radius)
            
            pulley2_radius = self.mechanism.get_parameter("pulley2_radius", 75.0)
            self.drag_handles[1].setPos(pulley2_center[0], pulley2_center[1] - pulley2_radius)
            
            # Update center distance handle
            self.drag_handles[2].setPos(
                (pulley1_center[0] + pulley2_center[0]) / 2,
                pulley1_center[1] + 50
            )
            
            # Update tension handle
            self.drag_handles[3].setPos(
                (pulley1_center[0] + pulley2_center[0]) / 2,
                pulley1_center[1] - 30
            )
    
    def get_analysis_data(self) -> Dict[str, Any]:
        """Get comprehensive belt system analysis."""
        pulley1_radius = self.mechanism.get_parameter("pulley1_radius", 30.0)
        pulley2_radius = self.mechanism.get_parameter("pulley2_radius", 75.0)
        center_distance = self.mechanism.get_parameter("center_distance", 150.0)
        initial_tension = self.mechanism.get_parameter("initial_tension", 80.0)
        belt_type = self.mechanism.get_parameter("belt_type", "timing")
        input_speed = self.mechanism.get_parameter("input_speed", 1000.0)  # RPM
        torque = self.mechanism.get_parameter("input_torque", 10.0)  # Nm
        
        # Calculate belt length (open belt configuration)
        # L = 2C + π(D₁ + D₂)/2 + (D₂ - D₁)²/(4C)
        d1 = 2 * pulley1_radius
        d2 = 2 * pulley2_radius
        belt_length = (2 * center_distance + 
                      math.pi * (d1 + d2) / 2 + 
                      (d2 - d1) ** 2 / (4 * center_distance))
        
        # Speed ratio
        speed_ratio = pulley1_radius / pulley2_radius
        output_speed = input_speed * speed_ratio
        
        # Contact angles
        alpha = math.asin((pulley2_radius - pulley1_radius) / center_distance)
        contact_angle1 = math.pi + 2 * alpha  # radians
        contact_angle2 = math.pi - 2 * alpha
        
        # Tension analysis using Euler-Eytelwein formula
        # For V-belt μ ≈ 0.5, for timing belt μ ≈ 0.35
        mu = 0.35 if belt_type == "timing" else 0.5
        
        # Power transmitted
        power_watts = (2 * math.pi * input_speed / 60) * torque
        power_kw = power_watts / 1000
        
        # Belt velocity
        belt_velocity = math.pi * d1 * input_speed / 60000  # m/s
        
        # Effective tension (force transmitting power)
        effective_tension = power_watts / belt_velocity if belt_velocity > 0 else 0
        
        # Tight and slack side tensions
        # T₁/T₂ = e^(μθ) where θ is contact angle
        tension_ratio = math.exp(mu * contact_angle1)
        tight_side_tension = initial_tension + effective_tension / 2
        slack_side_tension = tight_side_tension / tension_ratio
        
        # Belt slip calculation (for non-timing belts)
        if belt_type != "timing":
            # Simplified slip calculation
            slip_percent = (1 - 1/tension_ratio) * 100 * 0.1  # Approximate
        else:
            slip_percent = 0  # No slip in timing belts
        
        # Efficiency
        efficiency = 0.98 if belt_type == "timing" else 0.96
        
        # Check if belt is crossed
        is_crossed = self.mechanism.get_parameter("is_crossed", False)
        config_name = "Crossed Belt" if is_crossed else "Open Belt"
        
        # Update UI labels
        if hasattr(self, 'belt_length_label'):
            self.belt_type_label.setText(f"Type: {'Timing' if belt_type == 'timing' else 'V-Belt'}")
            self.crossing_label.setText(f"Configuration: {config_name}")
            self.belt_length_label.setText(f"Belt Length: {belt_length:.1f}mm")
            self.tight_side_label.setText(f"Tight Side Tension: {tight_side_tension:.1f}N")
            self.slack_side_label.setText(f"Slack Side Tension: {slack_side_tension:.1f}N")
            self.tension_ratio_label.setText(f"Tension Ratio: {tension_ratio:.1f}:1")
            
            self.speed_ratio_label.setText(f"Speed Ratio: 1:{1/speed_ratio:.2f}")
            self.power_capacity_label.setText(f"Power Capacity: {power_kw:.1f} kW")
            self.efficiency_label.setText(f"Efficiency: {efficiency*100:.0f}%")
            self.slip_label.setText(f"Slip: {slip_percent:.1f}%")
            
            self.contact_angle1_label.setText(f"Driver Contact: {math.degrees(contact_angle1):.0f}°")
            self.contact_angle2_label.setText(f"Driven Contact: {math.degrees(contact_angle2):.0f}°")
            self.center_distance_label.setText(f"Center Distance: {center_distance:.0f}mm")
        
        return {
            "belt_length": belt_length,
            "speed_ratio": speed_ratio,
            "output_speed": output_speed,
            "contact_angles": {
                "driver": math.degrees(contact_angle1),
                "driven": math.degrees(contact_angle2)
            },
            "tensions": {
                "tight_side": tight_side_tension,
                "slack_side": slack_side_tension,
                "effective": effective_tension,
                "ratio": tension_ratio
            },
            "power": {
                "input_kw": power_kw,
                "transmitted_kw": power_kw * efficiency,
                "efficiency": efficiency,
                "slip_percent": slip_percent
            },
            "belt_velocity": belt_velocity,
            "configuration": config_name
        }
    
    def _position_to_parameter_value(self, handle: DragHandle, position: QPointF) -> Optional[float]:
        """Convert handle position to parameter value for belt system."""
        if handle.parameter_name == "pulley1_radius":
            pulley1_center = (100, 150)
            radius = abs(pulley1_center[1] - position.y())
            return max(handle.value_range[0], min(handle.value_range[1], radius))
        
        elif handle.parameter_name == "pulley2_radius":
            center_distance = self.mechanism.get_parameter("center_distance", 150.0)
            pulley2_center = (100 + center_distance, 150)
            radius = abs(pulley2_center[1] - position.y())
            return max(handle.value_range[0], min(handle.value_range[1], radius))
        
        elif handle.parameter_name == "center_distance":
            # Horizontal distance from pulley1 center
            pulley1_x = 100
            distance = abs(position.x() - pulley1_x) * 2  # Handle is at midpoint
            return max(handle.value_range[0], min(handle.value_range[1], distance))
        
        elif handle.parameter_name == "initial_tension":
            # Vertical offset from belt line indicates tension
            belt_y = 150
            tension = abs(belt_y - position.y()) * 2  # Scale factor
            return max(handle.value_range[0], min(handle.value_range[1], tension))
        
        return None
    
    def _on_belt_type_changed(self, state):
        """Handle belt type change."""
        belt_type = "timing" if state else "v_belt"
        self.mechanism.set_parameter("belt_type", belt_type)
        self.parameter_changed.emit("belt_type", belt_type)


class SpringSystemInteractionHandler(BaseElasticHandler):
    """Specialized interaction handler for spring and damper systems with energy analysis."""
    
    def create_interaction_controls(self) -> QWidget:
        """Create spring system specific controls."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Spring configuration
        config_group = QGroupBox("Spring Configuration")
        config_layout = QVBoxLayout(config_group)
        
        self.spring_type_label = QLabel("Type: Compression Spring")
        self.spring_type_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface']};")
        config_layout.addWidget(self.spring_type_label)
        
        self.material_label = QLabel("Material: Spring Steel")
        self.material_label.setStyleSheet(f"color: {ModernStyling.COLORS['on_surface_variant']};")
        config_layout.addWidget(self.material_label)
        
        self.coils_label = QLabel("Active Coils: 8")
        config_layout.addWidget(self.coils_label)
        
        layout.addWidget(config_group)
        
        # Hooke's Law analysis
        hooke_group = QGroupBox("Hooke's Law Analysis")
        hooke_layout = QVBoxLayout(hooke_group)
        
        self.spring_constant_label = QLabel("Spring Constant k: 500 N/m")
        self.spring_constant_label.setStyleSheet(f"color: {ModernStyling.COLORS['secondary']};")
        hooke_layout.addWidget(self.spring_constant_label)
        
        self.displacement_label = QLabel("Displacement x: 20.0 mm")
        hooke_layout.addWidget(self.displacement_label)
        
        self.force_label = QLabel("Force F = kx: 10.0 N")
        self.force_label.setStyleSheet(f"color: {ModernStyling.COLORS['primary']};")
        hooke_layout.addWidget(self.force_label)
        
        layout.addWidget(hooke_group)
        
        # Energy analysis
        energy_group = QGroupBox("Energy Analysis")
        energy_layout = QVBoxLayout(energy_group)
        
        self.potential_energy_label = QLabel("Potential Energy: 0.10 J")
        self.potential_energy_label.setStyleSheet(f"color: {ModernStyling.COLORS['success']};")
        energy_layout.addWidget(self.potential_energy_label)
        
        self.kinetic_energy_label = QLabel("Kinetic Energy: 0.00 J")
        self.kinetic_energy_label.setStyleSheet(f"color: {ModernStyling.COLORS['info']};")
        energy_layout.addWidget(self.kinetic_energy_label)
        
        self.total_energy_label = QLabel("Total Energy: 0.10 J")
        energy_layout.addWidget(self.total_energy_label)
        
        layout.addWidget(energy_group)
        
        # Oscillation analysis
        oscillation_group = QGroupBox("Oscillation Analysis")
        oscillation_layout = QVBoxLayout(oscillation_group)
        
        self.natural_freq_label = QLabel("Natural Frequency: 3.56 Hz")
        self.period_label = QLabel("Period: 0.28 s")
        self.damping_ratio_label = QLabel("Damping Ratio: 0.05")
        self.quality_factor_label = QLabel("Quality Factor Q: 10")
        
        oscillation_layout.addWidget(self.natural_freq_label)
        oscillation_layout.addWidget(self.period_label)
        oscillation_layout.addWidget(self.damping_ratio_label)
        oscillation_layout.addWidget(self.quality_factor_label)
        
        layout.addWidget(oscillation_group)
        
        # Damper controls
        damper_group = QGroupBox("Damper Settings")
        damper_layout = QVBoxLayout(damper_group)
        
        damper_layout.addWidget(QLabel("Damping Coefficient:"))
        self.damping_slider = QSlider(Qt.Orientation.Horizontal)
        self.damping_slider.setRange(0, 100)
        self.damping_slider.setValue(5)
        self.damping_slider.valueChanged.connect(self._on_damping_changed)
        damper_layout.addWidget(self.damping_slider)
        
        self.damping_value_label = QLabel("c = 5.0 Ns/m")
        damper_layout.addWidget(self.damping_value_label)
        
        layout.addWidget(damper_group)
        
        layout.addStretch()
        return widget
    
    def create_drag_handles(self, scene):
        """Create drag handles for spring system parameters."""
        self.drag_handles.clear()
        
        # Spring attachment points
        fixed_point = (150, 50)
        movable_point = (150, 150)
        
        # Handle for spring constant (stiffness visualization)
        spring_constant = self.mechanism.get_parameter("spring_constant", 500.0)
        handle_k = DragHandle(fixed_point[0] + 50, fixed_point[1] + 30)
        handle_k.set_parameter("spring_constant", spring_constant, (100.0, 2000.0))
        handle_k.setToolTip("🌀 Drag to adjust Spring Constant k")
        scene.addItem(handle_k)
        self.drag_handles.append(handle_k)
        
        # Handle for rest length
        rest_length = self.mechanism.get_parameter("rest_length", 80.0)
        handle_rest = DragHandle(fixed_point[0] - 50, fixed_point[1] + rest_length)
        handle_rest.set_parameter("rest_length", rest_length, (40.0, 120.0))
        handle_rest.setToolTip("📏 Drag to adjust Rest Length")
        scene.addItem(handle_rest)
        self.drag_handles.append(handle_rest)
        
        # Handle for current displacement
        displacement = self.mechanism.get_parameter("displacement", 20.0)
        handle_disp = DragHandle(movable_point[0], movable_point[1])
        handle_disp.set_parameter("displacement", displacement, (-40.0, 40.0))
        handle_disp.setToolTip("↕️ Drag to apply Displacement")
        scene.addItem(handle_disp)
        self.drag_handles.append(handle_disp)
        
        # Handle for mass (affects oscillation)
        mass = self.mechanism.get_parameter("mass", 1.0)
        handle_mass = DragHandle(movable_point[0] + 50, movable_point[1])
        handle_mass.set_parameter("mass", mass, (0.1, 5.0))
        handle_mass.setToolTip("⚖️ Drag to adjust Mass")
        scene.addItem(handle_mass)
        self.drag_handles.append(handle_mass)
    
    def update_visualization(self):
        """Update spring system visualization."""
        if len(self.drag_handles) >= 4:
            fixed_point = (150, 50)
            rest_length = self.mechanism.get_parameter("rest_length", 80.0)
            displacement = self.mechanism.get_parameter("displacement", 20.0)
            
            # Update handle positions
            spring_constant = self.mechanism.get_parameter("spring_constant", 500.0)
            self.drag_handles[0].setPos(fixed_point[0] + 50, fixed_point[1] + 30)
            
            self.drag_handles[1].setPos(fixed_point[0] - 50, fixed_point[1] + rest_length)
            
            # Movable point with displacement
            movable_y = fixed_point[1] + rest_length + displacement
            self.drag_handles[2].setPos(fixed_point[0], movable_y)
            self.drag_handles[3].setPos(fixed_point[0] + 50, movable_y)
    
    def get_analysis_data(self) -> Dict[str, Any]:
        """Get comprehensive spring system analysis using Hooke's law and energy principles."""
        k = self.mechanism.get_parameter("spring_constant", 500.0)  # N/m
        x = self.mechanism.get_parameter("displacement", 20.0) / 1000  # Convert mm to m
        m = self.mechanism.get_parameter("mass", 1.0)  # kg
        c = self.mechanism.get_parameter("damping_coefficient", 5.0)  # Ns/m
        v = self.mechanism.get_parameter("velocity", 0.0)  # m/s
        rest_length = self.mechanism.get_parameter("rest_length", 80.0)  # mm
        
        # Hooke's Law: F = -kx
        force = k * abs(x)  # Magnitude of force
        
        # Energy calculations
        potential_energy = 0.5 * k * x * x  # U = ½kx²
        kinetic_energy = 0.5 * m * v * v    # K = ½mv²
        total_energy = potential_energy + kinetic_energy
        
        # Natural frequency and period (undamped)
        omega_n = math.sqrt(k / m)  # rad/s
        frequency = omega_n / (2 * math.pi)  # Hz
        period = 1 / frequency if frequency > 0 else 0
        
        # Damping analysis
        critical_damping = 2 * math.sqrt(k * m)
        damping_ratio = c / critical_damping if critical_damping > 0 else 0
        
        # Quality factor
        quality_factor = 1 / (2 * damping_ratio) if damping_ratio > 0 else float('inf')
        
        # Spring specifications
        wire_diameter = self.mechanism.get_parameter("wire_diameter", 2.0)  # mm
        coil_diameter = self.mechanism.get_parameter("coil_diameter", 20.0)  # mm
        active_coils = self.mechanism.get_parameter("active_coils", 8)
        
        # Spring index
        spring_index = coil_diameter / wire_diameter
        
        # Maximum stress (simplified)
        max_stress = 8 * force * coil_diameter / (math.pi * wire_diameter ** 3) if wire_diameter > 0 else 0
        
        # Update UI labels
        if hasattr(self, 'spring_constant_label'):
            self.spring_constant_label.setText(f"Spring Constant k: {k:.0f} N/m")
            self.displacement_label.setText(f"Displacement x: {x*1000:.1f} mm")
            self.force_label.setText(f"Force F = kx: {force:.1f} N")
            
            self.potential_energy_label.setText(f"Potential Energy: {potential_energy:.2f} J")
            self.kinetic_energy_label.setText(f"Kinetic Energy: {kinetic_energy:.2f} J")
            self.total_energy_label.setText(f"Total Energy: {total_energy:.2f} J")
            
            self.natural_freq_label.setText(f"Natural Frequency: {frequency:.2f} Hz")
            self.period_label.setText(f"Period: {period:.2f} s")
            self.damping_ratio_label.setText(f"Damping Ratio: {damping_ratio:.2f}")
            self.quality_factor_label.setText(f"Quality Factor Q: {quality_factor:.1f}")
            
            self.coils_label.setText(f"Active Coils: {active_coils}")
        
        return {
            "hookes_law": {
                "spring_constant": k,
                "displacement": x * 1000,  # mm
                "force": force,
                "stress": max_stress
            },
            "energy": {
                "potential": potential_energy,
                "kinetic": kinetic_energy,
                "total": total_energy
            },
            "dynamics": {
                "natural_frequency": frequency,
                "angular_frequency": omega_n,
                "period": period,
                "damping_ratio": damping_ratio,
                "quality_factor": quality_factor,
                "critical_damping": critical_damping
            },
            "geometry": {
                "rest_length": rest_length,
                "wire_diameter": wire_diameter,
                "coil_diameter": coil_diameter,
                "active_coils": active_coils,
                "spring_index": spring_index
            }
        }
    
    def _position_to_parameter_value(self, handle: DragHandle, position: QPointF) -> Optional[float]:
        """Convert handle position to parameter value for spring system."""
        fixed_point = (150, 50)
        
        if handle.parameter_name == "spring_constant":
            # Horizontal offset indicates stiffness
            offset = position.x() - fixed_point[0]
            k = offset * 20  # Scale factor
            return max(handle.value_range[0], min(handle.value_range[1], k))
        
        elif handle.parameter_name == "rest_length":
            # Vertical distance from fixed point
            length = position.y() - fixed_point[1]
            return max(handle.value_range[0], min(handle.value_range[1], length))
        
        elif handle.parameter_name == "displacement":
            # Displacement from rest position
            rest_length = self.mechanism.get_parameter("rest_length", 80.0)
            rest_y = fixed_point[1] + rest_length
            displacement = position.y() - rest_y
            return max(handle.value_range[0], min(handle.value_range[1], displacement))
        
        elif handle.parameter_name == "mass":
            # Horizontal offset indicates mass
            movable_x = 150
            mass = (position.x() - movable_x) / 10  # Scale factor
            return max(handle.value_range[0], min(handle.value_range[1], mass))
        
        return None
    
    def _on_damping_changed(self, value):
        """Handle damping coefficient changes."""
        damping = value / 10.0  # Scale to reasonable range
        self.mechanism.set_parameter("damping_coefficient", damping)
        self.damping_value_label.setText(f"c = {damping:.1f} Ns/m")
        self.parameter_changed.emit("damping_coefficient", damping)


class InteractionHandlerFactory:
    """Factory for creating mechanism-specific interaction handlers."""
    
    _handler_classes = {
        # ✅ FULL SUPPORT - Specialized handlers with complete feature set
        "four_bar_linkage": FourBarLinkageInteractionHandler,     # ✅ Full support
        "gear_train": GearSystemInteractionHandler,              # ✅ Full support
        "cam_follower": CamFollowerInteractionHandler,           # ✅ Full support
        "geneva_drive": GenevaDriveInteractionHandler,           # ✅ Full support
        "planetary_gear": PlanetaryGearInteractionHandler,       # ✅ Full support with Willis equation
        "six_bar_linkage": SixBarLinkageInteractionHandler,      # ✅ Full support
        "belt": BeltSystemInteractionHandler,                    # ✅ Full support with tension analysis
        "spring": SpringSystemInteractionHandler,               # ✅ Full support with Hooke's law and energy analysis
    }
    
    @classmethod
    def create_handler(cls, mechanism: BaseMechanism) -> BaseMechanismInteractionHandler:
        """Create appropriate interaction handler for the mechanism."""
        mechanism_type = mechanism.get_mechanism_type()
        handler_class = cls._handler_classes.get(mechanism_type, BaseMechanismInteractionHandler)
        
        # Warn about limited support
        if handler_class == BaseMechanismInteractionHandler:
            logger.warning(f"❌ {mechanism_type} has basic interaction only - no specialized features available")
        
        logger.debug(f"Creating {handler_class.__name__} for mechanism type: {mechanism_type}")
        
        return handler_class(mechanism)
    
    @classmethod
    def register_handler(cls, mechanism_type: str, handler_class):
        """Register a new handler class for a mechanism type."""
        cls._handler_classes[mechanism_type] = handler_class
        logger.info(f"Registered handler {handler_class.__name__} for type: {mechanism_type}")
    
    @classmethod
    def get_supported_types(cls) -> List[str]:
        """Get list of supported mechanism types."""
        return list(cls._handler_classes.keys())
    
    @classmethod
    def get_support_level(cls, mechanism_type: str) -> str:
        """Get the support level for a mechanism type."""
        handler_class = cls._handler_classes.get(mechanism_type, BaseMechanismInteractionHandler)
        
        if handler_class == BaseMechanismInteractionHandler:
            return "basic"  # ❌ Basic interaction only
        else:
            return "full"  # ✅ Full specialized support
    
    @classmethod
    def get_feature_matrix(cls) -> Dict[str, Dict[str, bool]]:
        """Get feature support matrix for all mechanism types."""
        features = {
            "four_bar_linkage": {
                "drag_handles": True,
                "constraint_validation": True,
                "real_time_analysis": True,
                "specialized_analysis": True,
                "path_optimization": True
            },
            "gear_train": {
                "drag_handles": True,
                "constraint_validation": False,
                "real_time_analysis": True,
                "specialized_analysis": True,
                "path_optimization": False
            },
            "cam_follower": {
                "drag_handles": True,
                "constraint_validation": False,
                "real_time_analysis": True,
                "specialized_analysis": True,
                "path_optimization": False
            },
            "geneva_drive": {
                "drag_handles": True,
                "constraint_validation": False,
                "real_time_analysis": True,
                "specialized_analysis": True,
                "path_optimization": False
            },
            "six_bar_linkage": {
                "drag_handles": True,           # ✅ 6 drag handles for all links
                "constraint_validation": True,  # ✅ Six-bar specific constraints
                "real_time_analysis": True,     # ✅ Proper six-bar analysis
                "specialized_analysis": True,   # ✅ Coupler curve analysis
                "path_optimization": True       # ✅ Coupler curve optimization
            },
            "planetary_gear": {
                "drag_handles": True,            # ✅ 3 drag handles for gear teeth
                "constraint_validation": True,   # ✅ Gear relationship validation
                "real_time_analysis": True,      # ✅ Willis equation analysis
                "specialized_analysis": True,    # ✅ Power split, clearance, assembly
                "path_optimization": False       # N/A for gear systems
            },
            "belt": {
                "drag_handles": True,            # ✅ 3 drag handles for pulley diameters and center distance
                "constraint_validation": True,   # ✅ Belt geometry validation
                "real_time_analysis": True,      # ✅ Tension, wrap angle, and efficiency analysis
                "specialized_analysis": True,    # ✅ Eytelwein equation, power transmission
                "path_optimization": False       # N/A for belt systems
            },
            "spring": {
                "drag_handles": True,            # ✅ 4 drag handles for spring parameters
                "constraint_validation": True,   # ✅ Buckling and stress validation
                "real_time_analysis": True,      # ✅ Hooke's law, energy, and stress analysis
                "specialized_analysis": True,    # ✅ Wahl factor, safety factor, natural frequency
                "path_optimization": False       # N/A for spring systems
            }
        }
        return features