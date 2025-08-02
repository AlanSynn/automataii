"""
Base mechanism class with rigorous mathematical constraints.

Provides the foundation for all mechanism implementations with proper
constraint validation, parameter management, and kinematic calculations.
"""

import math
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ParameterType(Enum):
    """Types of mechanism parameters"""
    LENGTH = "length"           # Linear dimensions (mm)
    ANGLE = "angle"             # Angular dimensions (degrees)
    SPEED = "speed"             # Rotational speed (RPM)
    FORCE = "force"             # Applied forces (N)
    DIMENSIONLESS = "dimensionless"  # Ratios, coefficients


@dataclass
class MechanismConstraint:
    """Constraint for mechanism parameters with validation"""
    min_value: float
    max_value: float
    parameter_type: ParameterType
    step_size: float = 0.1
    preferred_range: Tuple[float, float] = field(default_factory=lambda: (0.0, 100.0))
    invalid_ranges: List[Tuple[float, float]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    def validate(self, value: float) -> Tuple[bool, Optional[str]]:
        """Validate parameter value against constraints"""
        if not self.min_value <= value <= self.max_value:
            return False, f"Value {value} outside range [{self.min_value}, {self.max_value}]"
            
        # Check invalid ranges
        for invalid_start, invalid_end in self.invalid_ranges:
            if invalid_start <= value <= invalid_end:
                return False, f"Value {value} in invalid range [{invalid_start}, {invalid_end}]"
                
        return True, None
        
    def clamp(self, value: float) -> float:
        """Clamp value to valid range"""
        return max(self.min_value, min(self.max_value, value))


@dataclass 
class Joint:
    """Represents a mechanical joint with position and constraints"""
    name: str
    position: Tuple[float, float]  # (x, y) in mm
    joint_type: str = "revolute"   # revolute, prismatic, fixed
    angle: float = 0.0             # Current angle in degrees
    constraints: Optional[MechanismConstraint] = None
    
    def distance_to(self, other: 'Joint') -> float:
        """Calculate distance to another joint"""
        dx = other.position[0] - self.position[0]
        dy = other.position[1] - self.position[1]
        return math.sqrt(dx*dx + dy*dy)


@dataclass
class Link:
    """Represents a rigid link between joints"""
    name: str
    joint_a: str  # Joint name
    joint_b: str  # Joint name
    length: float  # Length in mm
    angle: float = 0.0  # Current angle in degrees
    thickness: float = 5.0  # Visual thickness
    color: str = "#2980b9"  # Display color
    
    def get_angle_from_joints(self, joint_a_pos: Tuple[float, float], 
                             joint_b_pos: Tuple[float, float]) -> float:
        """Calculate link angle from joint positions"""
        dx = joint_b_pos[0] - joint_a_pos[0]
        dy = joint_b_pos[1] - joint_a_pos[1]
        return math.degrees(math.atan2(dy, dx))


@dataclass
class MechanismState:
    """Current state of the mechanism"""
    joints: Dict[str, Joint] = field(default_factory=dict)
    links: Dict[str, Link] = field(default_factory=dict)
    parameters: Dict[str, float] = field(default_factory=dict)
    time: float = 0.0
    angular_velocity: float = 0.0  # Input speed in RPM
    is_valid: bool = True
    error_message: Optional[str] = None
    
    def copy(self) -> 'MechanismState':
        """Create deep copy of mechanism state"""
        import copy
        return copy.deepcopy(self)


class BaseMechanism(ABC):
    """
    Abstract base class for all mechanisms.
    
    Provides common functionality for parameter management, constraint validation,
    and kinematic calculations while enforcing mathematical rigor.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.state = MechanismState()
        self.constraints: Dict[str, MechanismConstraint] = {}
        self.educational_info: Dict[str, Any] = {}
        
        # Animation state
        self.animation_time = 0.0
        self.animation_speed = 1.0  # Speed multiplier
        self.is_animating = False
        
        # Setup mechanism-specific parameters
        self._setup_parameters()
        self._setup_constraints()
        self._setup_educational_info()
        
        # Calculate initial state
        self._calculate_initial_state()
        
    @abstractmethod
    def _setup_parameters(self) -> None:
        """Setup mechanism-specific parameters"""
        pass
        
    @abstractmethod
    def _setup_constraints(self) -> None:
        """Setup parameter constraints"""
        pass
        
    @abstractmethod
    def _setup_educational_info(self) -> None:
        """Setup educational information"""
        pass
        
    @abstractmethod
    def _calculate_initial_state(self) -> None:
        """Calculate initial mechanism state"""
        pass
        
    @abstractmethod
    def calculate_kinematics(self, input_angle: float) -> bool:
        """
        Calculate mechanism kinematics for given input angle.
        
        Args:
            input_angle: Input angle in degrees
            
        Returns:
            True if calculation successful, False if invalid configuration
        """
        pass
        
    def set_parameter(self, name: str, value: float) -> bool:
        """
        Set parameter value with constraint validation.
        
        Args:
            name: Parameter name
            value: New parameter value
            
        Returns:
            True if parameter set successfully, False if invalid
        """
        if name not in self.constraints:
            logger.warning(f"Unknown parameter: {name}")
            return False
            
        constraint = self.constraints[name]
        is_valid, error_msg = constraint.validate(value)
        
        if not is_valid:
            logger.warning(f"Parameter validation failed for {name}: {error_msg}")
            self.state.is_valid = False
            self.state.error_message = error_msg
            return False
            
        # Update parameter
        old_value = self.state.parameters.get(name, 0.0)
        self.state.parameters[name] = value
        
        # Recalculate mechanism state
        success = self._recalculate_state()
        
        if not success:
            # Restore old value if calculation failed
            self.state.parameters[name] = old_value
            self._recalculate_state()
            return False
            
        return True
        
    def get_parameter(self, name: str) -> Optional[float]:
        """Get current parameter value"""
        return self.state.parameters.get(name)
        
    def get_parameter_info(self, name: str) -> Optional[MechanismConstraint]:
        """Get parameter constraint information"""
        return self.constraints.get(name)
        
    def get_all_parameters(self) -> Dict[str, float]:
        """Get all current parameter values"""
        return self.state.parameters.copy()
        
    def validate_configuration(self) -> Tuple[bool, List[str]]:
        """
        Validate entire mechanism configuration.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Validate all parameters
        for name, value in self.state.parameters.items():
            if name in self.constraints:
                is_valid, error_msg = self.constraints[name].validate(value)
                if not is_valid:
                    errors.append(f"{name}: {error_msg}")
                    
        # Check mechanism-specific constraints
        mechanism_errors = self._validate_mechanism_constraints()
        errors.extend(mechanism_errors)
        
        is_valid = len(errors) == 0
        return is_valid, errors
        
    def update_animation(self, delta_time: float) -> None:
        """
        Update animation state.
        
        Args:
            delta_time: Time step in seconds
        """
        if not self.is_animating:
            return
            
        # Update animation time
        self.animation_time += delta_time * self.animation_speed
        
        # Calculate input angle based on angular velocity
        if self.state.angular_velocity != 0:
            # Convert RPM to degrees per second
            degrees_per_second = self.state.angular_velocity * 6.0  # 360°/60s
            input_angle = self.animation_time * degrees_per_second
            
            # Update mechanism kinematics
            self.calculate_kinematics(input_angle % 360)
            
    def start_animation(self, speed_rpm: float = 30.0) -> None:
        """Start mechanism animation"""
        self.state.angular_velocity = speed_rpm
        self.is_animating = True
        
    def stop_animation(self) -> None:
        """Stop mechanism animation"""
        self.is_animating = False
        
    def reset_animation(self) -> None:
        """Reset animation to initial state"""
        self.animation_time = 0.0
        self.calculate_kinematics(0.0)
        
    def get_joint_position(self, joint_name: str) -> Optional[Tuple[float, float]]:
        """Get current position of a joint"""
        joint = self.state.joints.get(joint_name)
        return joint.position if joint else None
        
    def get_link_info(self, link_name: str) -> Optional[Link]:
        """Get link information"""
        return self.state.links.get(link_name)
        
    def get_educational_content(self) -> Dict[str, Any]:
        """Get educational information about this mechanism"""
        return self.educational_info.copy()
        
    def _recalculate_state(self) -> bool:
        """Recalculate mechanism state after parameter change"""
        try:
            # Update mechanism geometry
            self._update_geometry()
            
            # Recalculate current kinematics
            return self.calculate_kinematics(self.animation_time * self.state.angular_velocity * 6.0)
            
        except Exception as e:
            logger.error(f"Error recalculating mechanism state: {e}")
            self.state.is_valid = False
            self.state.error_message = str(e)
            return False
            
    def _update_geometry(self) -> None:
        """Update mechanism geometry based on current parameters"""
        # Update link lengths from parameters
        for link_name, link in self.state.links.items():
            param_name = f"{link_name}_length"
            if param_name in self.state.parameters:
                link.length = self.state.parameters[param_name]
                
    @abstractmethod
    def _validate_mechanism_constraints(self) -> List[str]:
        """Validate mechanism-specific constraints"""
        pass
        
    # Utility methods for common kinematic calculations
    @staticmethod
    def calculate_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Calculate distance between two points"""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        return math.sqrt(dx*dx + dy*dy)
        
    @staticmethod
    def calculate_angle(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Calculate angle from p1 to p2 in degrees"""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        return math.degrees(math.atan2(dy, dx))
        
    @staticmethod
    def rotate_point(point: Tuple[float, float], center: Tuple[float, float], angle_deg: float) -> Tuple[float, float]:
        """Rotate point around center by angle (degrees)"""
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        # Translate to origin
        x = point[0] - center[0]
        y = point[1] - center[1]
        
        # Rotate
        x_rot = x * cos_a - y * sin_a
        y_rot = x * sin_a + y * cos_a
        
        # Translate back
        return (x_rot + center[0], y_rot + center[1])
        
    @staticmethod
    def circle_intersection(center1: Tuple[float, float], radius1: float,
                          center2: Tuple[float, float], radius2: float) -> List[Tuple[float, float]]:
        """
        Find intersection points of two circles.
        
        Returns:
            List of intersection points (0, 1, or 2 points)
        """
        x1, y1 = center1
        x2, y2 = center2
        
        # Distance between centers
        d = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        # Check if circles intersect
        if d > radius1 + radius2 or d < abs(radius1 - radius2) or d == 0:
            return []
            
        # Calculate intersection points
        a = (radius1**2 - radius2**2 + d**2) / (2 * d)
        h = math.sqrt(radius1**2 - a**2)
        
        # Point along line between centers
        px = x1 + a * (x2 - x1) / d
        py = y1 + a * (y2 - y1) / d
        
        if h == 0:
            # Single intersection point
            return [(px, py)]
        else:
            # Two intersection points
            offset_x = h * (y2 - y1) / d
            offset_y = h * (x2 - x1) / d
            
            return [
                (px + offset_x, py - offset_y),
                (px - offset_x, py + offset_y)
            ]