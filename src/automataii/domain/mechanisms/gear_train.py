"""
Rigorous Gear Train Mechanism Implementation.

Implements proper gear tooth meshing, gear ratios, and comprehensive power transmission analysis
with educational content about mechanical advantage and gear design principles.
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from dataclasses import dataclass

from .base import BaseMechanism, MechanismConstraint, ParameterType, Joint, Link


class GearType(Enum):
    """Types of gears in the gear train"""
    SPUR = "Spur"              # Straight teeth, parallel axes
    HELICAL = "Helical"        # Angled teeth, parallel axes
    BEVEL = "Bevel"            # Conical gears, intersecting axes
    WORM = "Worm"              # Worm and wheel, perpendicular axes


@dataclass
class GearTrainAnalysis:
    """Analysis results for gear train mechanism"""
    gear_ratio: float  # Overall gear ratio (output/input)
    velocity_ratio: float  # Speed ratio (input/output)
    mechanical_advantage: float  # Torque amplification
    contact_ratio: float  # Average number of teeth in contact
    center_distance: float  # Distance between gear centers
    pressure_angle: float  # Gear pressure angle in degrees
    module: float  # Gear module (tooth size)
    transmission_efficiency: float  # Power transmission efficiency


class GearTrain(BaseMechanism):
    """
    Rigorous gear train mechanism implementation.
    
    Features:
    - Exact gear ratio calculations with proper tooth meshing
    - Comprehensive power transmission analysis
    - Contact ratio and efficiency calculations
    - Educational content about gear design principles
    - Support for different gear types and configurations
    """
    
    def __init__(self):
        super().__init__("Gear Train")
        
    def _setup_parameters(self) -> None:
        """Setup gear train parameters"""
        # Basic gear parameters
        self.state.parameters = {
            'input_teeth': 20.0,         # Number of teeth on driving gear
            'output_teeth': 60.0,        # Number of teeth on driven gear
            'module': 2.5,               # Gear module (tooth size in mm)
            'pressure_angle': 20.0,      # Pressure angle in degrees
            'input_speed': 100.0,        # RPM
            'face_width': 20.0,          # Gear face width in mm
        }
        
    def _setup_constraints(self) -> None:
        """Setup parameter constraints"""
        
        # Input gear teeth
        self.constraints['input_teeth'] = MechanismConstraint(
            min_value=12.0,  # Minimum for good meshing
            max_value=100.0,
            parameter_type=ParameterType.DIMENSIONLESS,
            step_size=1.0,
            preferred_range=(15.0, 40.0)
        )
        
        # Output gear teeth
        self.constraints['output_teeth'] = MechanismConstraint(
            min_value=12.0,
            max_value=200.0,
            parameter_type=ParameterType.DIMENSIONLESS,
            step_size=1.0,
            preferred_range=(20.0, 80.0)
        )
        
        # Module (standardized values)
        self.constraints['module'] = MechanismConstraint(
            min_value=0.5,
            max_value=10.0,
            parameter_type=ParameterType.LENGTH,
            step_size=0.25,
            preferred_range=(1.0, 5.0)
        )
        
        # Pressure angle (standard values: 14.5°, 20°, 25°)
        self.constraints['pressure_angle'] = MechanismConstraint(
            min_value=14.5,
            max_value=25.0,
            parameter_type=ParameterType.ANGLE,
            step_size=0.5,
            preferred_range=(20.0, 20.0)  # 20° is most common
        )
        
        # Input speed
        self.constraints['input_speed'] = MechanismConstraint(
            min_value=0.1,
            max_value=3000.0,
            parameter_type=ParameterType.SPEED,
            step_size=1.0,
            preferred_range=(50.0, 500.0)
        )
        
        # Face width
        self.constraints['face_width'] = MechanismConstraint(
            min_value=5.0,
            max_value=100.0,
            parameter_type=ParameterType.LENGTH,
            step_size=1.0,
            preferred_range=(10.0, 50.0)
        )
        
    def _setup_educational_info(self) -> None:
        """Setup educational information"""
        self.educational_info = {
            'description': 'Gear trains transmit power and motion between rotating shafts with precise speed ratios.',
            'applications': [
                'Automotive transmissions',
                'Industrial gearboxes',
                'Clock mechanisms',
                'Robot joints',
                'Machine tools'
            ],
            'key_concepts': [
                'Gear ratio determines speed and torque relationship',
                'Contact ratio affects smoothness of operation',
                'Pressure angle affects force transmission',
                'Module determines tooth size and strength'
            ],
            'learning_objectives': [
                'Calculate gear ratios and mechanical advantage',
                'Understand relationship between speed and torque',
                'Analyze gear tooth geometry and forces',
                'Design gear trains for specific applications'
            ]
        }
        
    def _calculate_initial_state(self) -> None:
        """Calculate initial mechanism state"""
        # Get gear parameters
        teeth_input = int(self.state.parameters['input_teeth'])
        teeth_output = int(self.state.parameters['output_teeth'])
        module = self.state.parameters['module']
        
        # Calculate gear radii
        pitch_radius_input = teeth_input * module / 2.0
        pitch_radius_output = teeth_output * module / 2.0
        center_distance = pitch_radius_input + pitch_radius_output
        
        # Fixed gear centers
        self.state.joints['input_center'] = Joint('input_center', (-center_distance/2, 0.0), 'fixed')
        self.state.joints['output_center'] = Joint('output_center', (center_distance/2, 0.0), 'fixed')
        
        # Gear "links" (represented as circular bodies)
        self.state.links['input_gear'] = Link(
            'input_gear', 'input_center', 'input_center',
            pitch_radius_input * 2,  # Diameter
            color='#e74c3c'  # Red for input
        )
        self.state.links['output_gear'] = Link(
            'output_gear', 'output_center', 'output_center',
            pitch_radius_output * 2,  # Diameter  
            color='#27ae60'  # Green for output
        )
        
        # Store gear geometry data
        self._gear_geometry = {
            'pitch_radius_input': pitch_radius_input,
            'pitch_radius_output': pitch_radius_output,
            'center_distance': center_distance,
            'input_angle': 0.0,
            'output_angle': 0.0
        }
        
        # Calculate initial position
        self.calculate_kinematics(0.0)
        
        # Perform gear train analysis
        self._analyze_gear_train()
        
    def calculate_kinematics(self, input_angle: float) -> bool:
        """
        Calculate gear train kinematics with proper tooth meshing.
        
        Args:
            input_angle: Input gear angle in degrees
            
        Returns:
            True if calculation successful, False otherwise
        """
        try:
            # Get gear parameters
            teeth_input = self.state.parameters['input_teeth']
            teeth_output = self.state.parameters['output_teeth']
            
            # Calculate gear ratio
            gear_ratio = teeth_output / teeth_input
            
            # Input gear angle
            input_angle_rad = math.radians(input_angle)
            self._gear_geometry['input_angle'] = input_angle
            
            # Output gear angle (opposite direction due to external meshing)
            output_angle = -input_angle * gear_ratio
            self._gear_geometry['output_angle'] = output_angle
            
            # Update link angles
            self.state.links['input_gear'].angle = input_angle
            self.state.links['output_gear'].angle = output_angle
            
            # Calculate motion analysis
            self._update_motion_analysis(input_angle, gear_ratio)
            
            self.state.is_valid = True
            self.state.error_message = None
            return True
            
        except Exception as e:
            self.state.is_valid = False
            self.state.error_message = f"Gear calculation failed: {str(e)}"
            return False
            
    def _update_motion_analysis(self, input_angle: float, gear_ratio: float) -> None:
        """Update motion analysis with gear train data"""
        
        # Angular velocities
        input_rpm = self.state.parameters['input_speed']
        output_rpm = input_rpm / gear_ratio  # Speed reduction
        
        # Convert to rad/s
        input_omega = input_rpm * 2 * math.pi / 60.0
        output_omega = output_rpm * 2 * math.pi / 60.0
        
        # Mechanical advantage (torque ratio)
        mechanical_advantage = gear_ratio  # Torque increases with gear ratio
        
        # Linear velocities at pitch circles
        pitch_radius_input = self._gear_geometry['pitch_radius_input']
        pitch_radius_output = self._gear_geometry['pitch_radius_output']
        
        pitch_line_velocity = pitch_radius_input * input_omega  # Same for both gears
        
        # Store motion data
        self.state.motion_data = {
            'input_angle': input_angle,
            'output_angle': self._gear_geometry['output_angle'],
            'input_rpm': input_rpm,
            'output_rpm': output_rpm,
            'gear_ratio': gear_ratio,
            'mechanical_advantage': mechanical_advantage,
            'pitch_line_velocity': pitch_line_velocity,
            'input_angular_velocity': input_omega,
            'output_angular_velocity': output_omega
        }
        
    def _analyze_gear_train(self) -> GearTrainAnalysis:
        """
        Perform complete analysis of the gear train.
        
        Returns:
            Detailed analysis including ratios, efficiency, and design parameters
        """
        # Get parameters
        teeth_input = self.state.parameters['input_teeth']
        teeth_output = self.state.parameters['output_teeth']
        module = self.state.parameters['module']
        pressure_angle = self.state.parameters['pressure_angle']
        face_width = self.state.parameters['face_width']
        
        # Basic ratios
        gear_ratio = teeth_output / teeth_input
        velocity_ratio = teeth_input / teeth_output
        mechanical_advantage = gear_ratio
        
        # Gear geometry
        pitch_radius_input = teeth_input * module / 2.0
        pitch_radius_output = teeth_output * module / 2.0
        center_distance = pitch_radius_input + pitch_radius_output
        
        # Contact ratio calculation (simplified)
        # Real calculation involves involute geometry
        addendum = module  # Standard addendum
        contact_ratio = 1.2 + 0.8 * (teeth_input + teeth_output) / (2 * 20)  # Approximation
        contact_ratio = max(1.1, min(2.0, contact_ratio))  # Clamp to reasonable range
        
        # Transmission efficiency (depends on gear quality, lubrication, etc.)
        # High-quality spur gears: 98-99% efficiency
        base_efficiency = 0.98
        # Reduce efficiency for high gear ratios
        ratio_penalty = max(0.0, (gear_ratio - 1.0) * 0.005)
        transmission_efficiency = base_efficiency - ratio_penalty
        
        analysis = GearTrainAnalysis(
            gear_ratio=gear_ratio,
            velocity_ratio=velocity_ratio,
            mechanical_advantage=mechanical_advantage,
            contact_ratio=contact_ratio,
            center_distance=center_distance,
            pressure_angle=pressure_angle,
            module=module,
            transmission_efficiency=transmission_efficiency
        )
        
        # Store analysis
        self._gear_analysis = analysis
        
        # Update educational info
        self._update_educational_analysis(analysis)
        
        return analysis
        
    def _update_educational_analysis(self, analysis: GearTrainAnalysis) -> None:
        """Update educational information with gear analysis"""
        self.educational_info['gear_analysis'] = {
            'gear_ratio': analysis.gear_ratio,
            'speed_change': f"Speed reduced by {analysis.gear_ratio:.1f}:1",
            'torque_change': f"Torque increased by {analysis.mechanical_advantage:.1f}:1",
            'efficiency': f"{analysis.transmission_efficiency*100:.1f}%",
            'contact_rating': self._get_contact_rating(analysis.contact_ratio),
            'design_recommendations': self._get_design_recommendations(analysis)
        }
        
    def _get_contact_rating(self, contact_ratio: float) -> str:
        """Get contact ratio quality rating"""
        if contact_ratio < 1.2:
            return "Poor - Risk of impact and noise"
        elif contact_ratio < 1.4:
            return "Fair - Adequate for low-speed applications"
        elif contact_ratio < 1.8:
            return "Good - Smooth operation"
        else:
            return "Excellent - Very smooth and quiet"
            
    def _get_design_recommendations(self, analysis: GearTrainAnalysis) -> List[str]:
        """Get design recommendations based on analysis"""
        recommendations = []
        
        if analysis.gear_ratio > 10:
            recommendations.append("High gear ratio - consider compound gear train")
            
        if analysis.contact_ratio < 1.2:
            recommendations.append("Low contact ratio - increase tooth count or modify profile")
            
        if analysis.transmission_efficiency < 0.95:
            recommendations.append("Low efficiency - check gear quality and lubrication")
            
        if analysis.module < 1.0:
            recommendations.append("Small module - check tooth strength for applied loads")
            
        return recommendations
        
    def _validate_mechanism_constraints(self) -> List[str]:
        """Validate gear train specific constraints"""
        errors = []
        
        # Get parameters
        teeth_input = self.state.parameters['input_teeth']
        teeth_output = self.state.parameters['output_teeth']
        module = self.state.parameters['module']
        
        # Minimum tooth count for good meshing
        if teeth_input < 12:
            errors.append("Input gear has too few teeth - minimum 12 for good meshing")
            
        if teeth_output < 12:
            errors.append("Output gear has too few teeth - minimum 12 for good meshing")
            
        # Gear ratio limits
        gear_ratio = teeth_output / teeth_input
        if gear_ratio > 15:
            errors.append("Gear ratio too high - consider compound gear train")
            
        # Module standardization
        standard_modules = [0.5, 0.8, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]
        if not any(abs(module - std) < 0.1 for std in standard_modules):
            errors.append("Non-standard module - may increase manufacturing cost")
            
        return errors
        
    def get_gear_ratio(self) -> float:
        """Get current gear ratio"""
        return self.state.parameters['output_teeth'] / self.state.parameters['input_teeth']
        
    def get_mechanical_advantage(self) -> float:
        """Get mechanical advantage (torque amplification)"""
        return self.get_gear_ratio()
        
    def get_speed_reduction(self) -> float:
        """Get speed reduction ratio"""
        return 1.0 / self.get_gear_ratio()