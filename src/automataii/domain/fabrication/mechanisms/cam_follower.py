"""
Cam-follower mechanism implementation.
Basic cam mechanism with follower for precise motion control.
"""

import math
from typing import Dict, Any, Tuple
from .base_mechanism import BaseMechanism, MechanismPoint


class CamFollower(BaseMechanism):
    """
    Cam-follower mechanism implementation.
    
    A rotating cam drives a follower that moves up and down,
    creating precise motion profiles for timing applications.
    """
    
    def __init__(self, mechanism_id: str = "simple_cam", parameters: Dict[str, Any] = None):
        # Default parameters
        default_params = {
            "cam_radius": 30.0,     # Base cam radius
            "lobe_height": 20.0,    # Height of cam lobe
            "num_lobes": 1,         # Number of lobes
            "speed": 1.2            # Rotation speed
        }
        
        if parameters:
            default_params.update(parameters)
        
        # Mechanism-specific state
        self.cam_angle = 0.0
        self.center_x = 100.0
        self.center_y = 100.0
        
        super().__init__(mechanism_id, default_params)
    
    def _initialize_geometry(self):
        """Initialize the cam-follower geometry."""
        self.clear_geometry()
        
        # Get parameters
        cam_radius = self.get_parameter("cam_radius", 30.0)
        lobe_height = self.get_parameter("lobe_height", 20.0)
        
        # Fixed cam center
        self.cam_center = self.add_point(
            self.center_x, 
            self.center_y, 
            fixed=True
        )
        
        # Follower guide (fixed)
        self.follower_guide = self.add_point(
            self.center_x + cam_radius + lobe_height + 20,
            self.center_y - 50,
            fixed=True
        )
        
        # Moving follower
        self.follower = self.add_point(
            self.center_x + cam_radius + lobe_height + 20,
            self.center_y,
            fixed=False
        )
        
        # Cam circumference point (for visualization)
        self.cam_point = self.add_point(
            self.center_x + cam_radius,
            self.center_y,
            fixed=False
        )
        
        # Links
        self.cam_link = self.add_link(self.cam_center, self.cam_point, cam_radius)
        self.follower_link = self.add_link(self.follower_guide, self.follower)
        
        # Update initial positions
        self._update_positions(0.0)
    
    def _update_positions(self, time: float):
        """Update mechanism positions for animation."""
        # Calculate cam angle
        speed = self.get_parameter("speed", 1.2)
        self.cam_angle = time * speed * 2.0
        
        # Get parameters
        cam_radius = self.get_parameter("cam_radius", 30.0)
        lobe_height = self.get_parameter("lobe_height", 20.0)
        num_lobes = int(self.get_parameter("num_lobes", 1))
        
        try:
            # Update cam point position (rotates around center)
            self.cam_point.x = self.cam_center.x + cam_radius * math.cos(self.cam_angle)
            self.cam_point.y = self.cam_center.y + cam_radius * math.sin(self.cam_angle)
            
            # Calculate cam profile - sinusoidal lobe pattern
            lobe_angle = self.cam_angle * num_lobes
            lobe_factor = (1 + math.cos(lobe_angle)) / 2  # 0 to 1
            current_cam_radius = cam_radius + lobe_height * lobe_factor
            
            # Follower follows the cam profile
            # Simplified: follower moves vertically based on cam profile
            self.follower.y = self.center_y + (current_cam_radius - cam_radius) - lobe_height/2
            
        except (ValueError, ZeroDivisionError):
            pass
    
    def render(self, painter, scale: float = 1.0):
        """Custom render method for cam-follower mechanism."""
        painter.save()
        painter.scale(scale, scale)
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        
        # Get parameters
        cam_radius = self.get_parameter("cam_radius", 30.0)
        lobe_height = self.get_parameter("lobe_height", 20.0)
        num_lobes = int(self.get_parameter("num_lobes", 1))
        
        # Draw cam with profile
        self._draw_cam_profile(painter, self.cam_center, cam_radius, lobe_height, num_lobes)
        
        # Draw follower mechanism
        self._draw_follower_mechanism(painter)
        
        # Draw base mechanism
        self._draw_enhanced_joints(painter)
        
        painter.restore()
    
    def _draw_cam_profile(self, painter, center, base_radius, lobe_height, num_lobes):
        """Draw cam with actual profile."""
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPolygonF
        import math
        
        cam_color = QColor(120, 80, 60)  # Bronze color
        painter.setPen(QPen(cam_color.darker(), 2))
        painter.setBrush(QBrush(cam_color))
        
        # Create cam profile
        num_points = 60
        cam_outline = []
        
        for i in range(num_points):
            angle = i * 2 * math.pi / num_points
            
            # Calculate cam radius at this angle
            lobe_angle = angle * num_lobes
            lobe_factor = (1 + math.cos(lobe_angle)) / 2  # 0 to 1
            current_radius = base_radius + lobe_height * lobe_factor
            
            x = center.x + current_radius * math.cos(angle)
            y = center.y + current_radius * math.sin(angle)
            cam_outline.append(QPointF(x, y))
        
        # Draw cam profile
        cam_polygon = QPolygonF(cam_outline)
        painter.drawPolygon(cam_polygon)
        
        # Draw cam center hub
        hub_radius = base_radius * 0.3
        painter.setBrush(QBrush(cam_color.darker()))
        painter.drawEllipse(
            int(center.x - hub_radius), int(center.y - hub_radius),
            int(hub_radius * 2), int(hub_radius * 2)
        )
        
        # Draw rotation indicator
        painter.setPen(QPen(QColor(200, 200, 200), 2))
        indicator_len = hub_radius * 0.8
        painter.drawLine(
            int(center.x), int(center.y),
            int(center.x + indicator_len * math.cos(self.cam_angle)),
            int(center.y + indicator_len * math.sin(self.cam_angle))
        )
    
    def _draw_follower_mechanism(self, painter):
        """Draw the follower mechanism."""
        # Follower rod
        rod_color = QColor(100, 100, 100)
        painter.setPen(QPen(rod_color.darker(), 6))
        painter.drawLine(
            int(self.follower_guide.x), int(self.follower_guide.y),
            int(self.follower.x), int(self.follower.y)
        )
        
        # Follower head (roller)
        roller_radius = 8
        roller_color = QColor(150, 150, 150)
        painter.setPen(QPen(roller_color.darker(), 2))
        painter.setBrush(QBrush(roller_color))
        painter.drawEllipse(
            int(self.follower.x - roller_radius), int(self.follower.y - roller_radius),
            roller_radius * 2, roller_radius * 2
        )
        
        # Guide mechanism
        guide_color = QColor(80, 80, 80)
        painter.setPen(QPen(guide_color, 4))
        guide_width = 12
        painter.drawRect(
            int(self.follower_guide.x - guide_width/2), int(self.follower_guide.y - 10),
            guide_width, 20
        )
    
    def _draw_enhanced_joints(self, painter):
        """Draw joints with mechanical details."""
        # Use the enhanced joint drawing from base class
        super()._draw_enhanced_joints(painter)
    
    def get_parameter_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about cam-follower parameters."""
        return {
            "cam_radius": {
                "name": "Base Cam Radius",
                "type": "float",
                "min": 15.0,
                "max": 60.0,
                "unit": "mm",
                "description": "Base radius of the cam"
            },
            "lobe_height": {
                "name": "Lobe Height",
                "type": "float",
                "min": 5.0,
                "max": 40.0,
                "unit": "mm",
                "description": "Height of the cam lobes"
            },
            "num_lobes": {
                "name": "Number of Lobes",
                "type": "int",
                "min": 1,
                "max": 4,
                "unit": "",
                "description": "Number of lobes on the cam"
            },
            "speed": {
                "name": "Rotation Speed",
                "type": "float",
                "min": 0.2,
                "max": 4.0,
                "unit": "x",
                "description": "Cam rotation speed multiplier"
            }
        }
    
    def _on_parameter_changed(self, name: str, value: Any):
        """Handle parameter changes."""
        super()._on_parameter_changed(name, value)
        
        if name == "speed":
            self.set_animation_speed(value)
    
    def get_mechanism_type(self) -> str:
        """Get the mechanism type identifier."""
        return "cam_follower"
    
    def get_description(self) -> str:
        """Get a description of this mechanism."""
        return ("Cam-follower mechanism for precise motion control. "
                "The rotating cam creates specific motion profiles for the follower, "
                "commonly used in engines and automation systems.")