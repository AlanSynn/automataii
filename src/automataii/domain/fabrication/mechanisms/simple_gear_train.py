"""
Simple gear train mechanism implementation.
Two meshing gears for speed and torque conversion.
"""

import math
from typing import Dict, Any, Tuple
from .base_mechanism import BaseMechanism, MechanismPoint


class SimpleGearTrain(BaseMechanism):
    """
    Simple gear train mechanism implementation.
    
    Two meshing gears with different numbers of teeth for
    speed reduction or multiplication and torque conversion.
    """
    
    def __init__(self, mechanism_id: str = "simple_gear_train", parameters: Dict[str, Any] = None):
        # Default parameters
        default_params = {
            "gear1_teeth": 12,      # Driver gear teeth
            "gear2_teeth": 24,      # Driven gear teeth  
            "module": 2.0,          # Gear module (tooth size)
            "speed": 1.0            # Input speed
        }
        
        if parameters:
            default_params.update(parameters)
        
        # Mechanism-specific state
        self.gear1_angle = 0.0
        self.gear2_angle = 0.0
        self.center_x = 120.0
        self.center_y = 100.0
        
        super().__init__(mechanism_id, default_params)
    
    def _initialize_geometry(self):
        """Initialize the gear train geometry."""
        self.clear_geometry()
        
        # Get parameters
        teeth1 = int(self.get_parameter("gear1_teeth", 12))
        teeth2 = int(self.get_parameter("gear2_teeth", 24))
        module = self.get_parameter("module", 2.0)
        
        # Calculate gear radii (pitch radius = module * teeth / 2)
        radius1 = module * teeth1 / 2
        radius2 = module * teeth2 / 2
        center_distance = radius1 + radius2
        
        # Gear centers (fixed)
        self.gear1_center = self.add_point(
            self.center_x - center_distance/2,
            self.center_y,
            fixed=True
        )
        
        self.gear2_center = self.add_point(
            self.center_x + center_distance/2,
            self.center_y,
            fixed=True
        )
        
        # Gear pitch circle points (for visualization)
        self.gear1_point = self.add_point(
            self.gear1_center.x + radius1,
            self.gear1_center.y,
            fixed=False
        )
        
        self.gear2_point = self.add_point(
            self.gear2_center.x + radius2,
            self.gear2_center.y,
            fixed=False
        )
        
        # Store gear info for custom rendering
        self.gear1_radius = radius1
        self.gear2_radius = radius2
        
        # Links (represent the gears) - these won't be drawn with default renderer
        self.gear1_link = self.add_link(self.gear1_center, self.gear1_point, radius1)
        self.gear2_link = self.add_link(self.gear2_center, self.gear2_point, radius2)
        
        # Update initial positions
        self._update_positions(0.0)
    
    def _update_positions(self, time: float):
        """Update mechanism positions for animation."""
        # Calculate gear angles
        speed = self.get_parameter("speed", 1.0)
        teeth1 = int(self.get_parameter("gear1_teeth", 12))
        teeth2 = int(self.get_parameter("gear2_teeth", 24))
        module = self.get_parameter("module", 2.0)
        
        # Calculate gear ratios
        gear_ratio = teeth2 / teeth1  # gear2 rotates slower
        
        try:
            # Update gear1 angle (driver)
            self.gear1_angle = time * speed * 2.0
            
            # Update gear2 angle (driven, opposite direction)
            self.gear2_angle = -self.gear1_angle / gear_ratio
            
            # Calculate gear radii
            radius1 = module * teeth1 / 2
            radius2 = module * teeth2 / 2
            
            # Update gear pitch points
            self.gear1_point.x = self.gear1_center.x + radius1 * math.cos(self.gear1_angle)
            self.gear1_point.y = self.gear1_center.y + radius1 * math.sin(self.gear1_angle)
            
            self.gear2_point.x = self.gear2_center.x + radius2 * math.cos(self.gear2_angle)
            self.gear2_point.y = self.gear2_center.y + radius2 * math.sin(self.gear2_angle)
            
        except (ValueError, ZeroDivisionError):
            pass
    
    def render(self, painter, scale: float = 1.0):
        """Custom render method for gears with teeth."""
        painter.save()
        painter.scale(scale, scale)
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        
        # Get parameters
        teeth1 = int(self.get_parameter("gear1_teeth", 12))
        teeth2 = int(self.get_parameter("gear2_teeth", 24))
        module = self.get_parameter("module", 2.0)
        
        # Draw gears with teeth
        self._draw_gear_with_teeth(painter, self.gear1_center, self.gear1_radius, 
                                  teeth1, self.gear1_angle, QColor(100, 100, 150))
        self._draw_gear_with_teeth(painter, self.gear2_center, self.gear2_radius, 
                                  teeth2, self.gear2_angle, QColor(150, 100, 100))
        
        # Draw center hubs
        self._draw_gear_hub(painter, self.gear1_center, self.gear1_radius * 0.3)
        self._draw_gear_hub(painter, self.gear2_center, self.gear2_radius * 0.3)
        
        painter.restore()
    
    def _draw_gear_with_teeth(self, painter, center, radius, num_teeth, angle, color):
        """Draw a gear with proper teeth."""
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPolygonF
        import math
        
        # Gear body
        painter.setPen(QPen(color.darker(), 2))
        painter.setBrush(QBrush(color))
        
        # Create gear outline with teeth
        tooth_height = radius * 0.15
        outer_radius = radius + tooth_height
        inner_radius = radius - tooth_height * 0.3
        
        # Calculate tooth angles
        tooth_angle = 2 * math.pi / num_teeth
        
        gear_outline = []
        
        for i in range(num_teeth):
            base_angle = i * tooth_angle + angle
            
            # Tooth root (inner)
            angle1 = base_angle - tooth_angle * 0.4
            angle2 = base_angle - tooth_angle * 0.1
            angle3 = base_angle + tooth_angle * 0.1  
            angle4 = base_angle + tooth_angle * 0.4
            
            # Add tooth profile points
            gear_outline.extend([
                QPointF(center.x + inner_radius * math.cos(angle1),
                       center.y + inner_radius * math.sin(angle1)),
                QPointF(center.x + outer_radius * math.cos(angle2),
                       center.y + outer_radius * math.sin(angle2)),
                QPointF(center.x + outer_radius * math.cos(angle3),
                       center.y + outer_radius * math.sin(angle3)),
                QPointF(center.x + inner_radius * math.cos(angle4),
                       center.y + inner_radius * math.sin(angle4))
            ])
        
        # Draw the gear
        gear_polygon = QPolygonF(gear_outline)
        painter.drawPolygon(gear_polygon)
        
        # Add inner circle for strength
        painter.setBrush(QBrush(color.darker()))
        inner_circle_radius = radius * 0.7
        painter.drawEllipse(
            int(center.x - inner_circle_radius), int(center.y - inner_circle_radius),
            int(inner_circle_radius * 2), int(inner_circle_radius * 2)
        )
    
    def _draw_gear_hub(self, painter, center, radius):
        """Draw gear center hub."""
        hub_color = QColor(80, 80, 80)
        painter.setPen(QPen(hub_color.darker(), 2))
        painter.setBrush(QBrush(hub_color))
        
        # Outer hub
        painter.drawEllipse(
            int(center.x - radius), int(center.y - radius),
            int(radius * 2), int(radius * 2)
        )
        
        # Inner hub with key slot
        inner_radius = radius * 0.4
        painter.setBrush(QBrush(hub_color.darker()))
        painter.drawEllipse(
            int(center.x - inner_radius), int(center.y - inner_radius),
            int(inner_radius * 2), int(inner_radius * 2)
        )
        
        # Key slot
        painter.setPen(QPen(QColor(40, 40, 40), 2))
        slot_length = radius * 0.6
        painter.drawLine(
            int(center.x - slot_length/2), int(center.y),
            int(center.x + slot_length/2), int(center.y)
        )
    
    def get_parameter_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about gear train parameters."""
        return {
            "gear1_teeth": {
                "name": "Driver Gear Teeth",
                "type": "int",
                "min": 8,
                "max": 30,
                "unit": "teeth",
                "description": "Number of teeth on the driver gear"
            },
            "gear2_teeth": {
                "name": "Driven Gear Teeth",
                "type": "int", 
                "min": 10,
                "max": 50,
                "unit": "teeth",
                "description": "Number of teeth on the driven gear"
            },
            "module": {
                "name": "Module",
                "type": "float",
                "min": 1.0,
                "max": 4.0,
                "unit": "mm",
                "description": "Gear module (pitch diameter / teeth)"
            },
            "speed": {
                "name": "Input Speed",
                "type": "float",
                "min": 0.1,
                "max": 3.0,
                "unit": "x",
                "description": "Input shaft speed multiplier"
            }
        }
    
    def _on_parameter_changed(self, name: str, value: Any):
        """Handle parameter changes."""
        super()._on_parameter_changed(name, value)
        
        if name == "speed":
            self.set_animation_speed(value)
    
    def get_mechanism_type(self) -> str:
        """Get the mechanism type identifier."""
        return "gear_train"
    
    def get_description(self) -> str:
        """Get a description of this mechanism."""
        return ("Simple gear train for speed and torque conversion. "
                "Two meshing gears with different tooth counts provide "
                "mechanical advantage and direction change.")