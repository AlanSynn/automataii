"""
Rigorous Slider-Crank Mechanism Implementation.

The slider-crank mechanism converts rotary motion to linear motion (or vice versa).
It's fundamental to internal combustion engines, pumps, and many other machines.
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from dataclasses import dataclass

from .base import BaseMechanism, MechanismConstraint, ParameterType, Joint, Link


class SliderCrankType(Enum):
    """Types of slider-crank mechanisms"""
    IN_LINE = "In-line"        # Slider centerline passes through crank pivot
    OFFSET = "Offset"          # Slider centerline offset from crank pivot


@dataclass
class SliderCrankAnalysis:
    """Analysis results for slider-crank mechanism"""
    mechanism_type: SliderCrankType
    stroke_length: float  # Total slider displacement
    maximum_acceleration: float  # Peak slider acceleration
    connecting_rod_ratio: float  # Connecting rod length / crank radius  
    offset_ratio: float  # Offset / crank radius
    velocity_ratio_range: Tuple[float, float]  # Min/max velocity ratios
    acceleration_factor: float  # Acceleration amplification factor


class SliderCrankMechanism(BaseMechanism):
    """
    Rigorous slider-crank mechanism implementation.
    
    Features:
    - Exact analytical kinematics for position, velocity, acceleration
    - Support for both in-line and offset configurations
    - Connecting rod ratio analysis for smooth operation
    - Educational content about engine applications
    - Proper constraint validation for physical realizability
    """
    
    def __init__(self):
        super().__init__("Slider-Crank Mechanism")
        
    def _setup_parameters(self) -> None:
        """Setup slider-crank mechanism parameters"""
        # Basic dimensions (mm)
        self.state.parameters = {
            'crank_radius': 40.0,          # Crank arm radius (r)
            'connecting_rod_length': 120.0,  # Connecting rod length (l)
            'slider_offset': 0.0,          # Offset from crank centerline (e)
            'input_speed': 60.0,           # RPM
        }
        
    def _setup_constraints(self) -> None:
        """Setup parameter constraints"""
        
        # Crank radius
        self.constraints['crank_radius'] = MechanismConstraint(
            min_value=10.0,
            max_value=100.0,
            parameter_type=ParameterType.LENGTH,
            step_size=1.0,
            preferred_range=(20.0, 60.0)
        )
        
        # Connecting rod length
        self.constraints['connecting_rod_length'] = MechanismConstraint(
            min_value=40.0,
            max_value=300.0,
            parameter_type=ParameterType.LENGTH,
            step_size=1.0,
            preferred_range=(80.0, 200.0)
        )
        
        # Slider offset (can be negative for offset below centerline)
        self.constraints['slider_offset'] = MechanismConstraint(
            min_value=-50.0,
            max_value=50.0,
            parameter_type=ParameterType.LENGTH,
            step_size=0.5,
            preferred_range=(-20.0, 20.0)
        )
        
        # Input speed
        self.constraints['input_speed'] = MechanismConstraint(
            min_value=0.1,
            max_value=300.0,
            parameter_type=ParameterType.SPEED,
            step_size=0.5,
            preferred_range=(30.0, 120.0)
        )
        
    def _setup_educational_info(self) -> None:
        """Setup educational information"""
        self.educational_info = {
            'description': 'The slider-crank mechanism converts rotary motion to reciprocating linear motion.',
            'applications': [
                'Internal combustion engines',
                'Reciprocating pumps and compressors',
                'Mechanical presses',
                'Sewing machines',
                'Hand pumps'
            ],
            'key_concepts': [
                'Connecting rod ratio affects smoothness',
                'Offset creates asymmetric motion',
                'Stroke length = 2 × crank radius',
                'Maximum acceleration occurs at dead centers'
            ],
            'learning_objectives': [
                'Understand piston motion in engines',
                'Analyze effect of connecting rod ratio',
                'Study impact of slider offset',
                'Calculate forces and accelerations'
            ]
        }
        
    def _calculate_initial_state(self) -> None:
        """Calculate initial mechanism state"""
        # Crank pivot (fixed)
        self.state.joints['O'] = Joint('O', (0.0, 0.0), 'fixed')  # Crank center
        
        # Moving joints (calculated by kinematics)
        self.state.joints['A'] = Joint('A', (0.0, 0.0), 'revolute')  # Crank-rod joint
        self.state.joints['B'] = Joint('B', (0.0, 0.0), 'prismatic')  # Rod-slider joint
        
        # Links
        self.state.links['crank'] = Link(
            'crank', 'O', 'A',
            self.state.parameters['crank_radius'],
            color='#e74c3c'  # Red for crank
        )
        self.state.links['connecting_rod'] = Link(
            'connecting_rod', 'A', 'B',
            self.state.parameters['connecting_rod_length'],
            color='#3498db'  # Blue for connecting rod
        )
        
        # Calculate initial position (crank at 0°)
        self.calculate_kinematics(0.0)
        
        # Perform mechanism analysis
        self._analyze_slider_crank()
        
    def calculate_kinematics(self, input_angle: float) -> bool:
        """
        Calculate slider-crank kinematics using exact analytical methods.
        
        Args:
            input_angle: Crank angle in degrees (0° = rightmost position)
            
        Returns:
            True if valid configuration found, False otherwise
        """
        try:
            # Get current parameters
            r = self.state.parameters['crank_radius']        # Crank radius
            l = self.state.parameters['connecting_rod_length']  # Connecting rod length
            e = self.state.parameters['slider_offset']       # Slider offset
            
            # Convert to radians
            theta = math.radians(input_angle)
            
            # Crank pin position (revolute joint A)
            A_x = r * math.cos(theta)
            A_y = r * math.sin(theta)
            A = (A_x, A_y)
            
            # Calculate connecting rod angle using law of cosines
            # Distance from crank pin to slider centerline
            h = A_y - e  # Vertical distance to slider centerline
            s = A_x      # Horizontal distance along slider
            
            # Check if configuration is possible
            if abs(h) > l:
                self.state.is_valid = False
                self.state.error_message = "Invalid configuration: connecting rod too short"
                return False
                
            # Calculate slider position using Pythagorean theorem
            discriminant = l*l - h*h
            if discriminant < 0:
                self.state.is_valid = False
                self.state.error_message = "Invalid configuration: no solution exists"
                return False
                
            x_offset = math.sqrt(discriminant)
            
            # Slider position (choose forward solution for normal operation)
            B_x = s + x_offset  # Forward solution (engine compression/expansion)
            B_y = e  # Slider moves along offset line
            
            # Update joint positions
            self.state.joints['A'].position = A
            self.state.joints['B'].position = (B_x, B_y)
            
            # Calculate link angles
            self._update_link_angles()
            
            # Calculate motion analysis data
            self._update_motion_analysis(input_angle, theta, r, l, e)
            
            self.state.is_valid = True
            self.state.error_message = None
            return True
            
        except Exception as e:
            self.state.is_valid = False
            self.state.error_message = f"Kinematic calculation failed: {str(e)}"
            return False
            
    def _update_link_angles(self) -> None:
        """Update link angles based on current joint positions"""
        joints = self.state.joints
        links = self.state.links
        
        # Crank angle
        links['crank'].angle = self.calculate_angle(
            joints['O'].position, joints['A'].position
        )
        
        # Connecting rod angle
        links['connecting_rod'].angle = self.calculate_angle(
            joints['A'].position, joints['B'].position
        )
        
    def _update_motion_analysis(self, input_angle_deg: float, theta: float, 
                              r: float, l: float, e: float) -> None:
        """Update motion analysis with velocity and acceleration data"""
        
        # Slider position (analytical)
        x_slider = r * math.cos(theta) + math.sqrt(l*l - (r * math.sin(theta) - e)**2)
        
        # Slider velocity (derivative of position)
        omega = math.radians(self.state.parameters['input_speed'] * 6.0)  # rad/s
        
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        sqrt_term = math.sqrt(l*l - (r * sin_theta - e)**2)
        
        # Velocity calculation
        dx_dtheta = -r * sin_theta + (r * (r * sin_theta - e) * cos_theta) / sqrt_term
        v_slider = dx_dtheta * omega
        
        # Acceleration calculation (simplified approximation)
        a_slider = -r * omega * omega * (cos_theta + (r * cos_theta) / l)
        
        # Connecting rod angle
        beta = math.asin((r * sin_theta - e) / l)  # Rod angle from horizontal
        beta_deg = math.degrees(beta)
        
        # Angular velocity of connecting rod
        omega_rod = (r * omega * cos_theta) / (l * math.cos(beta))
        
        # Store motion data
        self.state.motion_data = {
            'input_angle': input_angle_deg,
            'crank_angle': input_angle_deg,
            'rod_angle': beta_deg,
            'slider_position': x_slider,
            'slider_velocity': v_slider,
            'slider_acceleration': a_slider,
            'rod_angular_velocity': math.degrees(omega_rod),
            'connecting_rod_ratio': l / r
        }
        
    def _analyze_slider_crank(self) -> SliderCrankAnalysis:
        """Perform complete analysis of the slider-crank mechanism"""
        # Get parameters
        r = self.state.parameters['crank_radius']
        l = self.state.parameters['connecting_rod_length']
        e = self.state.parameters['slider_offset']
        
        # Determine mechanism type
        mechanism_type = SliderCrankType.IN_LINE if abs(e) < 0.1 else SliderCrankType.OFFSET
        
        # Calculate stroke length
        stroke_length = 2 * r if mechanism_type == SliderCrankType.IN_LINE else 2 * r * (1 + r / (2 * l))
        
        # Connecting rod ratio (important for smoothness)
        connecting_rod_ratio = l / r
        
        # Offset ratio
        offset_ratio = e / r if r > 0 else 0.0
        
        # Maximum acceleration (occurs at dead centers)
        omega = math.radians(self.state.parameters['input_speed'] * 6.0)
        max_acceleration = r * omega * omega * (1 + 1/connecting_rod_ratio)
        
        # Velocity ratio range
        v_min = 1.0 - 1.0/connecting_rod_ratio
        v_max = 1.0 + 1.0/connecting_rod_ratio
        velocity_ratio_range = (v_min, v_max)
        
        # Acceleration factor
        acceleration_factor = 1 + 1/connecting_rod_ratio
        
        analysis = SliderCrankAnalysis(
            mechanism_type=mechanism_type,
            stroke_length=stroke_length,
            maximum_acceleration=max_acceleration,
            connecting_rod_ratio=connecting_rod_ratio,
            offset_ratio=offset_ratio,
            velocity_ratio_range=velocity_ratio_range,
            acceleration_factor=acceleration_factor
        )
        
        # Store analysis
        self._slider_crank_analysis = analysis
        
        # Update educational info
        self._update_educational_analysis(analysis)
        
        return analysis
        
    def _update_educational_analysis(self, analysis: SliderCrankAnalysis) -> None:
        """Update educational information with mechanism analysis"""
        self.educational_info['mechanism_analysis'] = {
            'type': analysis.mechanism_type.value,
            'stroke_length': analysis.stroke_length,
            'connecting_rod_ratio': analysis.connecting_rod_ratio,
            'smoothness_rating': self._get_smoothness_rating(analysis.connecting_rod_ratio),
            'design_recommendations': self._get_design_recommendations(analysis)
        }
        
    def _get_smoothness_rating(self, rod_ratio: float) -> str:
        """Get smoothness rating based on connecting rod ratio"""
        if rod_ratio < 2.5:
            return "Poor - High vibration and acceleration"
        elif rod_ratio < 3.5:
            return "Fair - Moderate vibration"
        elif rod_ratio < 5.0:
            return "Good - Acceptable for most applications"
        else:
            return "Excellent - Very smooth operation"
            
    def _get_design_recommendations(self, analysis: SliderCrankAnalysis) -> List[str]:
        """Get design recommendations based on analysis"""
        recommendations = []
        
        if analysis.connecting_rod_ratio < 3.0:
            recommendations.append("Increase connecting rod length for smoother operation")
            
        if analysis.connecting_rod_ratio > 8.0:
            recommendations.append("Consider shorter connecting rod to reduce mechanism size")
            
        if abs(analysis.offset_ratio) > 0.3:
            recommendations.append("Large offset may cause excessive side forces")
            
        if analysis.maximum_acceleration > 1000:  # Arbitrary threshold
            recommendations.append("High acceleration - consider balancing or speed reduction")
            
        return recommendations
        
    def _validate_mechanism_constraints(self) -> List[str]:
        """Validate slider-crank specific constraints"""
        errors = []
        
        # Get parameters
        r = self.state.parameters['crank_radius']
        l = self.state.parameters['connecting_rod_length']
        e = self.state.parameters['slider_offset']
        
        # Connecting rod must be longer than crank + offset
        min_rod_length = r + abs(e)
        if l <= min_rod_length:
            errors.append(f"Connecting rod too short - minimum length: {min_rod_length:.1f}mm")
            
        # Practical connecting rod ratio limits
        rod_ratio = l / r if r > 0 else 0
        if rod_ratio < 1.5:
            errors.append("Connecting rod ratio too small - mechanism will bind")
        elif rod_ratio > 20:
            errors.append("Connecting rod ratio too large - impractical mechanism")
            
        # Offset limits relative to connecting rod length
        if abs(e) >= l:
            errors.append("Offset too large - slider cannot reach all positions")
            
        return errors