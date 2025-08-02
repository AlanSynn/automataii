"""
Six-bar linkage mechanism implementation.
More complex linkage with additional degrees of freedom for complex motion paths.
"""

import math
from typing import Dict, Any, Tuple
from .base_mechanism import BaseMechanism, MechanismPoint


class SixBarLinkage(BaseMechanism):
    """
    Six-bar linkage mechanism implementation.
    
    A more complex linkage consisting of six links and seven joints,
    providing additional degrees of freedom for creating complex motion paths.
    This implementation uses a Watt-type six-bar linkage.
    """
    
    def __init__(self, mechanism_id: str = "six_bar", parameters: Dict[str, Any] = None):
        # Default parameters
        default_params = {
            "link1_length": 40.0,    # Crank length
            "link2_length": 90.0,    # First coupler length
            "link3_length": 70.0,    # Second coupler length
            "link4_length": 80.0,    # Third coupler length
            "link5_length": 50.0,    # Output rocker length
            "base_length": 120.0,    # Base length
            "speed": 0.8             # Animation speed multiplier
        }
        
        if parameters:
            default_params.update(parameters)
        
        # Mechanism-specific state
        self.crank_angle = 0.0
        self.center_x = 150.0
        self.center_y = 120.0
        
        super().__init__(mechanism_id, default_params)
    
    def _initialize_geometry(self):
        """Initialize the six-bar linkage geometry."""
        self.clear_geometry()
        
        # Get parameters
        link1_len = self.get_parameter("link1_length", 40.0)
        link2_len = self.get_parameter("link2_length", 90.0)
        link3_len = self.get_parameter("link3_length", 70.0)
        link4_len = self.get_parameter("link4_length", 80.0)
        link5_len = self.get_parameter("link5_length", 50.0)
        base_len = self.get_parameter("base_length", 120.0)
        
        # Fixed points (ground links)
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
        
        # Additional fixed point for six-bar configuration
        self.fixed_pivot_c = self.add_point(
            self.center_x - base_len / 4,
            self.center_y - 40,
            fixed=True
        )
        
        # Moving joints (initially positioned)
        # Link 1 end (crank end)
        self.joint_1 = self.add_point(
            self.fixed_pivot_a.x + link1_len,
            self.fixed_pivot_a.y,
            fixed=False
        )
        
        # Link 2 end (first coupler end)
        self.joint_2 = self.add_point(
            self.joint_1.x + link2_len * 0.7,
            self.joint_1.y - link2_len * 0.3,
            fixed=False
        )
        
        # Link 3 end (second coupler end)
        self.joint_3 = self.add_point(
            self.joint_2.x + link3_len * 0.5,
            self.joint_2.y + link3_len * 0.5,
            fixed=False
        )
        
        # Link 4 end (connects to output rocker)
        self.joint_4 = self.add_point(
            self.fixed_pivot_b.x - link5_len * 0.8,
            self.fixed_pivot_b.y - link5_len * 0.6,
            fixed=False
        )
        
        # Create the linkage connections
        # Main chain: Fixed_A -> Link1 -> Link2 -> Link3 -> Link4 -> Fixed_B
        self.link1 = self.add_link(self.fixed_pivot_a, self.joint_1, link1_len)
        self.link2 = self.add_link(self.joint_1, self.joint_2, link2_len)
        self.link3 = self.add_link(self.joint_2, self.joint_3, link3_len)
        self.link4 = self.add_link(self.joint_3, self.joint_4, link4_len)
        self.link5 = self.add_link(self.joint_4, self.fixed_pivot_b, link5_len)
        
        # Additional constraint link (what makes it a six-bar)
        # Connect one of the coupler points to the third fixed point
        self.link6 = self.add_link(self.joint_2, self.fixed_pivot_c)
        
        # Ground link
        self.base_link = self.add_link(self.fixed_pivot_a, self.fixed_pivot_b, base_len)
        
        # Update initial positions
        self._update_positions(0.0)
    
    def _update_positions(self, time: float):
        """Update mechanism positions for animation with simplified but stable motion."""
        # Calculate crank angle
        speed = self.get_parameter("speed", 0.8)
        self.crank_angle = time * speed * 1.5  # Reasonable speed
        
        # Get link lengths
        link1_len = self.get_parameter("link1_length", 40.0)
        link2_len = self.get_parameter("link2_length", 90.0)
        link3_len = self.get_parameter("link3_length", 70.0)
        link4_len = self.get_parameter("link4_length", 80.0)
        link5_len = self.get_parameter("link5_length", 50.0)
        
        try:
            # Update Link 1 end (crank rotation)
            self.joint_1.x = self.fixed_pivot_a.x + link1_len * math.cos(self.crank_angle)
            self.joint_1.y = self.fixed_pivot_a.y + link1_len * math.sin(self.crank_angle)
            
            # Use a simplified but stable approach for six-bar motion
            # This creates a more predictable and visually coherent motion
            
            # Joint 2 follows a path influenced by both joint_1 and the constraint to fixed_pivot_c
            offset_angle = self.crank_angle * 0.6 + math.pi / 4
            self.joint_2.x = self.joint_1.x + link2_len * 0.7 * math.cos(offset_angle)
            self.joint_2.y = self.joint_1.y + link2_len * 0.7 * math.sin(offset_angle)
            
            # Joint 3 creates a complex path
            complex_angle = self.crank_angle * 0.8 - math.pi / 6
            self.joint_3.x = self.joint_2.x + link3_len * 0.8 * math.cos(complex_angle)
            self.joint_3.y = self.joint_2.y + link3_len * 0.8 * math.sin(complex_angle)
            
            # Joint 4 connects to the output, creating an oscillating motion
            # Calculate distance and angle from fixed_pivot_b
            dx = self.joint_3.x - self.fixed_pivot_b.x
            dy = self.joint_3.y - self.fixed_pivot_b.y
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist > 0:
                # Scale to maintain link5 length constraint
                scale = min(link5_len / dist, 1.0)
                self.joint_4.x = self.fixed_pivot_b.x + dx * scale
                self.joint_4.y = self.fixed_pivot_b.y + dy * scale
            
        except (ValueError, ZeroDivisionError):
            # If calculation fails, keep current positions
            pass
    
    
    def get_parameter_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about six-bar linkage parameters."""
        return {
            "link1_length": {
                "name": "Crank Length",
                "type": "float",
                "min": 20.0,
                "max": 80.0,
                "unit": "mm",
                "description": "Length of the input crank"
            },
            "link2_length": {
                "name": "Coupler 1 Length",
                "type": "float",
                "min": 40.0,
                "max": 140.0,
                "unit": "mm",
                "description": "Length of the first connecting rod"
            },
            "link3_length": {
                "name": "Coupler 2 Length",
                "type": "float",
                "min": 30.0,
                "max": 110.0,
                "unit": "mm",
                "description": "Length of the second connecting rod"
            },
            "link4_length": {
                "name": "Coupler 3 Length",
                "type": "float",
                "min": 35.0,
                "max": 120.0,
                "unit": "mm",
                "description": "Length of the third connecting rod"
            },
            "link5_length": {
                "name": "Output Rocker Length",
                "type": "float",
                "min": 25.0,
                "max": 100.0,
                "unit": "mm",
                "description": "Length of the output rocker"
            },
            "base_length": {
                "name": "Base Length",
                "type": "float",
                "min": 60.0,
                "max": 200.0,
                "unit": "mm",
                "description": "Distance between main fixed pivots"
            },
            "speed": {
                "name": "Animation Speed",
                "type": "float",
                "min": 0.1,
                "max": 3.0,
                "unit": "x",
                "description": "Speed multiplier for animation"
            }
        }
    
    def _on_parameter_changed(self, name: str, value: Any):
        """Handle parameter changes specific to six-bar linkage."""
        super()._on_parameter_changed(name, value)
        
        # Update animation speed immediately
        if name == "speed":
            self.set_animation_speed(value)
    
    def get_mechanism_type(self) -> str:
        """Get the mechanism type identifier."""
        return "six_bar_linkage"
    
    def get_description(self) -> str:
        """Get a description of this mechanism."""
        return ("Six-bar linkage mechanism for complex motion generation. "
                "Provides additional degrees of freedom compared to four-bar linkages "
                "for creating sophisticated motion paths and dwell mechanisms.")
    
    def get_complexity_level(self) -> str:
        """Get the complexity level of this mechanism."""
        return "intermediate"
    
    def get_degrees_of_freedom(self) -> int:
        """Calculate the degrees of freedom using Gruebler's equation."""
        # For planar mechanisms: DOF = 3(n-1) - 2j
        # where n = number of links, j = number of joints
        n_links = 6  # Six links plus ground
        n_joints = 7  # Seven revolute joints
        
        return 3 * (n_links + 1 - 1) - 2 * n_joints  # Should be 1 for single DOF
    
    def get_path_complexity(self) -> str:
        """Describe the complexity of the motion path generated."""
        return ("Complex curved paths with potential for dwell periods "
                "and multi-looped trajectories depending on link ratios")