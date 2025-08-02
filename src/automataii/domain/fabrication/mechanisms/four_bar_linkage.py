"""
Four-bar linkage mechanism implementation.
Classic mechanism for converting rotary to oscillating motion.
"""

import math
from typing import Dict, Any, Tuple
from .base_mechanism import BaseMechanism, MechanismPoint


class FourBarLinkage(BaseMechanism):
    """
    Four-bar linkage mechanism implementation.
    
    Consists of four links connected in a loop:
    - Fixed base link
    - Input crank (rotates continuously)
    - Connecting rod (coupler)
    - Output rocker (oscillates)
    """
    
    def __init__(self, mechanism_id: str = "four_bar", parameters: Dict[str, Any] = None):
        # Default parameters
        default_params = {
            "link1_length": 50.0,    # Crank length
            "link2_length": 80.0,    # Coupler length
            "link3_length": 60.0,    # Rocker length
            "base_length": 100.0,    # Base length
            "speed": 1.0             # Animation speed multiplier
        }
        
        if parameters:
            default_params.update(parameters)
        
        # Mechanism-specific state
        self.crank_angle = 0.0
        self.center_x = 150.0  # Center the mechanism
        self.center_y = 100.0
        
        super().__init__(mechanism_id, default_params)
    
    def _initialize_geometry(self):
        """Initialize the four-bar linkage geometry."""
        self.clear_geometry()
        
        # Get parameters
        link1_len = self.get_parameter("link1_length", 50.0)
        link2_len = self.get_parameter("link2_length", 80.0)
        link3_len = self.get_parameter("link3_length", 60.0)
        base_len = self.get_parameter("base_length", 100.0)
        
        # Fixed points (base link)
        self.fixed_pivot_a = self.add_point(
            self.center_x - base_len / 2, 
            self.center_y, 
            fixed=True
        )
        self.fixed_pivot_b = self.add_point(
            self.center_x + base_len / 2, 
            self.center_y, 
            fixed=True
        )
        
        # Moving points (initially positioned)
        self.crank_end = self.add_point(
            self.fixed_pivot_a.x + link1_len,
            self.fixed_pivot_a.y,
            fixed=False
        )
        self.rocker_end = self.add_point(
            self.fixed_pivot_b.x - link3_len,
            self.fixed_pivot_b.y,
            fixed=False
        )
        
        # Add links with proper length constraints
        self.crank_link = self.add_link(self.fixed_pivot_a, self.crank_end, link1_len)
        self.coupler_link = self.add_link(self.crank_end, self.rocker_end, link2_len)
        self.rocker_link = self.add_link(self.rocker_end, self.fixed_pivot_b, link3_len)
        self.base_link = self.add_link(self.fixed_pivot_a, self.fixed_pivot_b, base_len)
        
        # Update initial positions
        self._update_positions(0.0)
    
    def _update_positions(self, time: float):
        """Update mechanism positions for animation with proper kinematics."""
        # Calculate crank angle based on time and speed
        speed = self.get_parameter("speed", 1.0)
        self.crank_angle = time * speed * 2.0  # 2 radians per second at 1x speed
        
        # Get link lengths
        link1_len = self.get_parameter("link1_length", 50.0)  # Crank
        link2_len = self.get_parameter("link2_length", 80.0)  # Coupler
        link3_len = self.get_parameter("link3_length", 60.0)  # Rocker
        base_len = self.get_parameter("base_length", 100.0)   # Ground
        
        # Calculate crank end position (input link rotation)
        self.crank_end.x = self.fixed_pivot_a.x + link1_len * math.cos(self.crank_angle)
        self.crank_end.y = self.fixed_pivot_a.y + link1_len * math.sin(self.crank_angle)
        
        # Calculate rocker end position using law of cosines
        # This is the complex part of four-bar linkage kinematics
        try:
            # Distance between crank end and fixed pivot B
            dx = self.fixed_pivot_b.x - self.crank_end.x
            dy = self.fixed_pivot_b.y - self.crank_end.y
            d = math.sqrt(dx * dx + dy * dy)
            
            # Check if mechanism can close (triangle inequality)
            if d <= link2_len + link3_len and abs(link2_len - link3_len) <= d:
                # Use law of cosines to find rocker angle
                cos_beta = (link3_len * link3_len + d * d - link2_len * link2_len) / (2 * link3_len * d)
                cos_beta = max(-1.0, min(1.0, cos_beta))  # Clamp to valid range
                beta = math.acos(cos_beta)
                
                # Angle from fixed pivot B to crank end
                alpha = math.atan2(-dy, -dx)  # Angle from B to crank end
                
                # Calculate two possible rocker angles
                rocker_angle1 = alpha + beta
                rocker_angle2 = alpha - beta
                
                # Choose the solution that gives smooth continuous motion
                # Use the angle that keeps the mechanism in the same configuration
                if not hasattr(self, 'prev_rocker_angle'):
                    self.prev_rocker_angle = rocker_angle1
                
                # Choose the angle closest to previous angle for continuity
                diff1 = abs(rocker_angle1 - self.prev_rocker_angle)
                diff2 = abs(rocker_angle2 - self.prev_rocker_angle)
                
                # Handle angle wrapping
                if diff1 > math.pi:
                    diff1 = 2 * math.pi - diff1
                if diff2 > math.pi:
                    diff2 = 2 * math.pi - diff2
                
                rocker_angle = rocker_angle1 if diff1 <= diff2 else rocker_angle2
                self.prev_rocker_angle = rocker_angle
                
                # Update rocker end position
                self.rocker_end.x = self.fixed_pivot_b.x + link3_len * math.cos(rocker_angle)
                self.rocker_end.y = self.fixed_pivot_b.y + link3_len * math.sin(rocker_angle)
            
        except (ValueError, ZeroDivisionError):
            # If calculation fails, keep current position
            pass
    
    def render(self, painter, scale: float = 1.0):
        """Custom render method for realistic four-bar linkage visualization."""
        painter.save()
        painter.scale(scale, scale)
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        
        # Draw mechanism with physics simulation appearance
        self._draw_physics_simulation_style(painter)
        
        painter.restore()
    
    def _draw_physics_simulation_style(self, painter):
        """Draw four-bar linkage with physics simulation appearance."""
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QRadialGradient, QLinearGradient
        import math
        
        # Get link lengths for force calculations
        link1_len = self.get_parameter("link1_length", 50.0)
        link2_len = self.get_parameter("link2_length", 80.0)  
        link3_len = self.get_parameter("link3_length", 60.0)
        
        # Draw links with realistic appearance
        self._draw_realistic_link(painter, self.fixed_pivot_a, self.crank_end, 
                                 QColor(70, 130, 180), "CRANK", True)  # Steel blue for driving link
        self._draw_realistic_link(painter, self.crank_end, self.rocker_end,
                                 QColor(105, 105, 105), "COUPLER", False)  # Gray for coupler
        self._draw_realistic_link(painter, self.rocker_end, self.fixed_pivot_b,
                                 QColor(178, 34, 34), "ROCKER", False)  # Red for output link
        self._draw_realistic_link(painter, self.fixed_pivot_a, self.fixed_pivot_b,
                                 QColor(85, 85, 85), "BASE", False)  # Dark gray for base
        
        # Draw joints with realistic bearings
        self._draw_physics_joint(painter, self.fixed_pivot_a, True, "A")
        self._draw_physics_joint(painter, self.fixed_pivot_b, True, "B") 
        self._draw_physics_joint(painter, self.crank_end, False, "P")
        self._draw_physics_joint(painter, self.rocker_end, False, "Q")
        
        # Add force vectors and motion indicators
        self._draw_force_vectors(painter)
        self._draw_motion_indicators(painter)
        
        # Add dimension annotations
        self._draw_dimension_annotations(painter)
    
    def _draw_realistic_link(self, painter, point1, point2, color, label, is_driving=False):
        """Draw a realistic mechanical link with 3D appearance."""
        dx = point2.x - point1.x
        dy = point2.y - point1.y
        length = math.sqrt(dx*dx + dy*dy)
        
        if length < 0.1:
            return
            
        angle = math.atan2(dy, dx)
        
        # Link dimensions
        width = 12 if is_driving else 8
        half_width = width / 2
        
        # Create gradient for 3D effect
        gradient = QLinearGradient(0, -half_width, 0, half_width)
        gradient.setColorAt(0, color.lighter(140))
        gradient.setColorAt(0.3, color)
        gradient.setColorAt(0.7, color.darker(120))
        gradient.setColorAt(1, color.darker(150))
        
        painter.save()
        painter.translate(point1.x, point1.y)
        painter.rotate(math.degrees(angle))
        
        # Draw main link body
        painter.setPen(QPen(color.darker(160), 1))
        painter.setBrush(QBrush(gradient))
        
        from PyQt6.QtCore import QRectF
        link_rect = QRectF(0, -half_width, length, width)
        painter.drawRoundedRect(link_rect, 3, 3)
        
        # Add surface details
        if is_driving:
            # Add drive pattern for input link
            painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
            for i in range(int(length/8)):
                x = i * 8 + 4
                painter.drawLine(x, -half_width+2, x, half_width-2)
        
        # Add link label
        if length > 30:  # Only show label if link is long enough
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
            painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            text_rect = QRectF(length/4, -half_width, length/2, width)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)
        
        painter.restore()
    
    def _draw_physics_joint(self, painter, point, is_fixed, label):
        """Draw a joint with physics simulation appearance."""
        if is_fixed:
            # Fixed joint with ground connection
            bearing_radius = 15
            
            # Outer bearing ring
            gradient = QRadialGradient(point.x, point.y, bearing_radius)
            gradient.setColorAt(0, QColor(180, 180, 180))
            gradient.setColorAt(0.7, QColor(120, 120, 120))
            gradient.setColorAt(1, QColor(80, 80, 80))
            
            painter.setPen(QPen(QColor(60, 60, 60), 2))
            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(int(point.x - bearing_radius), int(point.y - bearing_radius),
                              bearing_radius * 2, bearing_radius * 2)
            
            # Inner bearing
            inner_radius = 8
            painter.setBrush(QBrush(QColor(40, 40, 40)))
            painter.drawEllipse(int(point.x - inner_radius), int(point.y - inner_radius),
                              inner_radius * 2, inner_radius * 2)
            
            # Ground symbol with hatching
            self._draw_ground_connection(painter, point, bearing_radius)
            
        else:
            # Moving joint
            bearing_radius = 12
            
            # Bearing visualization
            gradient = QRadialGradient(point.x, point.y, bearing_radius)
            gradient.setColorAt(0, QColor(200, 200, 200))
            gradient.setColorAt(0.5, QColor(150, 150, 150))
            gradient.setColorAt(1, QColor(100, 100, 100))
            
            painter.setPen(QPen(QColor(80, 80, 80), 2))
            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(int(point.x - bearing_radius), int(point.y - bearing_radius),
                              bearing_radius * 2, bearing_radius * 2)
            
            # Center pin
            pin_radius = 4
            painter.setBrush(QBrush(QColor(50, 50, 50)))
            painter.drawEllipse(int(point.x - pin_radius), int(point.y - pin_radius),
                              pin_radius * 2, pin_radius * 2)
        
        # Joint label
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.drawText(int(point.x + 20), int(point.y - 15), label)
    
    def _draw_ground_connection(self, painter, point, bearing_radius):
        """Draw ground connection with hatching pattern."""
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPolygonF
        
        # Ground plate
        plate_width = 40
        plate_height = 8
        plate_y = point.y + bearing_radius + 8
        
        painter.setPen(QPen(QColor(60, 60, 60), 2))
        painter.setBrush(QBrush(QColor(100, 100, 100)))
        
        plate_rect = QRectF(point.x - plate_width/2, plate_y, plate_width, plate_height)
        painter.drawRect(plate_rect)
        
        # Hatching pattern
        painter.setPen(QPen(QColor(40, 40, 40), 1))
        for i in range(8):
            x = point.x - plate_width/2 + i * (plate_width/7)
            painter.drawLine(int(x), int(plate_y + plate_height),
                           int(x - 6), int(plate_y + plate_height + 8))
    
    def _draw_force_vectors(self, painter):
        """Draw force vectors showing force transmission."""
        # Input torque on crank
        painter.setPen(QPen(QColor(255, 100, 100), 3))
        torque_radius = 25
        
        # Draw curved arrow for input torque
        start_angle = self.crank_angle - 0.3
        end_angle = self.crank_angle + 0.3
        
        painter.drawArc(
            int(self.fixed_pivot_a.x - torque_radius), int(self.fixed_pivot_a.y - torque_radius),
            torque_radius * 2, torque_radius * 2,
            int(start_angle * 180 / math.pi * 16), int(0.6 * 180 / math.pi * 16)
        )
        
        # Arrow head for torque
        arrow_x = self.fixed_pivot_a.x + torque_radius * math.cos(end_angle)
        arrow_y = self.fixed_pivot_a.y + torque_radius * math.sin(end_angle)
        self._draw_arrow_head(painter, arrow_x, arrow_y, end_angle + math.pi/2, QColor(255, 100, 100))
        
        # Output force on rocker
        output_force_len = 30
        rocker_angle = math.atan2(self.rocker_end.y - self.fixed_pivot_b.y, 
                                 self.rocker_end.x - self.fixed_pivot_b.x)
        force_angle = rocker_angle + math.pi/2
        
        painter.setPen(QPen(QColor(100, 255, 100), 3))
        force_end_x = self.rocker_end.x + output_force_len * math.cos(force_angle)
        force_end_y = self.rocker_end.y + output_force_len * math.sin(force_angle)
        
        painter.drawLine(int(self.rocker_end.x), int(self.rocker_end.y),
                        int(force_end_x), int(force_end_y))
        self._draw_arrow_head(painter, force_end_x, force_end_y, force_angle, QColor(100, 255, 100))
    
    def _draw_motion_indicators(self, painter):
        """Draw motion direction indicators."""
        # Crank rotation indicator
        painter.setPen(QPen(QColor(255, 200, 0), 2))
        
        # Rotation direction arrow
        rot_radius = 35
        rot_angle = self.crank_angle + math.pi/4
        
        start_x = self.fixed_pivot_a.x + rot_radius * math.cos(rot_angle - 0.2)
        start_y = self.fixed_pivot_a.y + rot_radius * math.sin(rot_angle - 0.2)
        end_x = self.fixed_pivot_a.x + rot_radius * math.cos(rot_angle + 0.2)
        end_y = self.fixed_pivot_a.y + rot_radius * math.sin(rot_angle + 0.2)
        
        painter.drawLine(int(start_x), int(start_y), int(end_x), int(end_y))
        self._draw_arrow_head(painter, end_x, end_y, rot_angle + 0.2 + math.pi/2, QColor(255, 200, 0))
        
        # Speed indicator text
        speed = self.get_parameter("speed", 1.0)
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(int(self.fixed_pivot_a.x - 30), int(self.fixed_pivot_a.y - 50), 
                        f"ω = {speed:.1f} rad/s")
    
    def _draw_arrow_head(self, painter, x, y, angle, color):
        """Draw an arrow head at the specified position and angle."""
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPolygonF
        
        arrow_size = 8
        painter.setBrush(QBrush(color))
        
        # Arrow head points
        p1 = QPointF(x, y)
        p2 = QPointF(x - arrow_size * math.cos(angle - 0.5), 
                     y - arrow_size * math.sin(angle - 0.5))
        p3 = QPointF(x - arrow_size * math.cos(angle + 0.5),
                     y - arrow_size * math.sin(angle + 0.5))
        
        arrow = QPolygonF([p1, p2, p3])
        painter.drawPolygon(arrow)
    
    def _draw_dimension_annotations(self, painter):
        """Draw dimension annotations for educational purposes."""
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.setFont(QFont("Arial", 8))
        
        # Link length annotations
        link1_len = self.get_parameter("link1_length", 50.0)
        link2_len = self.get_parameter("link2_length", 80.0)
        link3_len = self.get_parameter("link3_length", 60.0)
        
        # Crank length
        mid_x = (self.fixed_pivot_a.x + self.crank_end.x) / 2
        mid_y = (self.fixed_pivot_a.y + self.crank_end.y) / 2
        painter.drawText(int(mid_x - 15), int(mid_y - 10), f"L1={link1_len:.0f}")
        
        # Coupler length  
        mid_x = (self.crank_end.x + self.rocker_end.x) / 2
        mid_y = (self.crank_end.y + self.rocker_end.y) / 2
        painter.drawText(int(mid_x - 15), int(mid_y - 10), f"L2={link2_len:.0f}")
        
        # Rocker length
        mid_x = (self.rocker_end.x + self.fixed_pivot_b.x) / 2
        mid_y = (self.rocker_end.y + self.fixed_pivot_b.y) / 2
        painter.drawText(int(mid_x - 15), int(mid_y - 10), f"L3={link3_len:.0f}")
    
    def get_parameter_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about four-bar linkage parameters."""
        return {
            "link1_length": {
                "name": "Crank Length",
                "type": "float",
                "min": 20.0,
                "max": 100.0,
                "unit": "mm",
                "description": "Length of the input crank"
            },
            "link2_length": {
                "name": "Coupler Length",
                "type": "float",
                "min": 30.0,
                "max": 150.0,
                "unit": "mm",
                "description": "Length of the connecting rod"
            },
            "link3_length": {
                "name": "Rocker Length",
                "type": "float",
                "min": 25.0,
                "max": 120.0,
                "unit": "mm",
                "description": "Length of the output rocker"
            },
            "base_length": {
                "name": "Base Length",
                "type": "float",
                "min": 50.0,
                "max": 200.0,
                "unit": "mm",
                "description": "Distance between fixed pivots"
            },
            "speed": {
                "name": "Animation Speed",
                "type": "float",
                "min": 0.1,
                "max": 5.0,
                "unit": "x",
                "description": "Speed multiplier for animation"
            }
        }
    
    def _on_parameter_changed(self, name: str, value: Any):
        """Handle parameter changes specific to four-bar linkage."""
        super()._on_parameter_changed(name, value)
        
        # Update animation speed immediately
        if name == "speed":
            self.set_animation_speed(value)
    
    def get_mechanism_type(self) -> str:
        """Get the mechanism type identifier."""
        return "four_bar_linkage"
    
    def get_description(self) -> str:
        """Get a description of this mechanism."""
        return ("Four-bar linkage mechanism for converting rotary input motion "
                "to oscillating output motion. Widely used in mechanical systems.")
    
    def is_valid_configuration(self) -> bool:
        """Check if the current parameter configuration is valid."""
        link1 = self.get_parameter("link1_length", 50.0)
        link2 = self.get_parameter("link2_length", 80.0)
        link3 = self.get_parameter("link3_length", 60.0)
        base = self.get_parameter("base_length", 100.0)
        
        # Check Grashof's condition for a working four-bar linkage
        links = sorted([link1, link2, link3, base])
        shortest = links[0]
        longest = links[3]
        sum_others = sum(links[1:3])
        
        # For a crank-rocker mechanism, Grashof condition must be satisfied
        return shortest + longest <= sum_others
    
    def get_motion_type(self) -> str:
        """Get the type of motion this linkage produces."""
        if not self.is_valid_configuration():
            return "Invalid configuration"
        
        link1 = self.get_parameter("link1_length", 50.0)
        link2 = self.get_parameter("link2_length", 80.0)
        link3 = self.get_parameter("link3_length", 60.0)
        base = self.get_parameter("base_length", 100.0)
        
        # Classify motion type based on Grashof's theorem
        if link1 == min(link1, link2, link3, base):
            return "Crank-Rocker (Input: full rotation, Output: oscillation)"
        elif link3 == min(link1, link2, link3, base):
            return "Rocker-Crank (Input: oscillation, Output: full rotation)"
        else:
            return "Double-Rocker (Both links oscillate)"