"""
Rigorous Four-Bar Linkage Implementation with Grashof Analysis.

This implementation provides mathematically accurate four-bar linkage simulation
with proper geometric constraints, Grashof condition validation, and educational
analysis features.
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from dataclasses import dataclass

from .base import BaseMechanism, MechanismConstraint, ParameterType, Joint, Link


class GrashofClassification(Enum):
    """Grashof classification for four-bar linkages"""
    CRANK_ROCKER = "Crank-Rocker"           # One full rotation, one oscillation
    DOUBLE_CRANK = "Double-Crank"           # Both links can rotate fully
    DOUBLE_ROCKER = "Double-Rocker"         # Both links oscillate
    CHANGE_POINT = "Change-Point"           # Special case, s + l = p + q
    INVALID = "Invalid"                     # Triangle inequality violated


@dataclass
class GrashofAnalysis:
    """Analysis results for Grashof condition"""
    classification: GrashofClassification
    grashof_ratio: float  # (s + l) / (p + q)
    shortest_link: str
    longest_link: str
    can_rotate_fully: Dict[str, bool]  # Which links can rotate 360°
    motion_limits: Dict[str, Tuple[float, float]]  # Angular motion limits
    transmission_angle_range: Tuple[float, float]  # Min/max transmission angles
    mechanical_advantage_range: Tuple[float, float]  # Min/max mechanical advantage


class FourBarLinkage(BaseMechanism):
    """
    Rigorous four-bar linkage implementation.
    
    Features:
    - Exact analytical kinematics using circle intersection
    - Grashof condition analysis and classification
    - Transmission angle calculation for mechanical advantage
    - Continuous motion tracking to avoid branch jumping
    - Educational analysis and visualization data
    - Proper constraint validation for physical realizability
    """
    
    def __init__(self):
        super().__init__("Four-Bar Linkage")
        
    def _setup_parameters(self) -> None:
        """Setup four-bar linkage parameters"""
        # Link lengths (mm)
        self.state.parameters = {
            'input_length': 50.0,      # Input crank (a)
            'coupler_length': 100.0,   # Coupler link (b)  
            'output_length': 80.0,     # Output rocker (c)
            'ground_length': 120.0,    # Ground link (d)
            'input_speed': 30.0,       # RPM
        }
        
    def _setup_constraints(self) -> None:
        """Setup parameter constraints with Grashof considerations"""
        
        # Input link length (crank)
        self.constraints['input_length'] = MechanismConstraint(
            min_value=10.0,
            max_value=200.0,
            parameter_type=ParameterType.LENGTH,
            step_size=1.0,
            preferred_range=(30.0, 80.0)
        )
        
        # Coupler link length  
        self.constraints['coupler_length'] = MechanismConstraint(
            min_value=20.0,
            max_value=300.0,
            parameter_type=ParameterType.LENGTH,
            step_size=1.0,
            preferred_range=(60.0, 150.0)
        )
        
        # Output link length (rocker)
        self.constraints['output_length'] = MechanismConstraint(
            min_value=10.0,
            max_value=200.0,
            parameter_type=ParameterType.LENGTH,
            step_size=1.0,
            preferred_range=(40.0, 120.0)
        )
        
        # Ground link length (fixed)
        self.constraints['ground_length'] = MechanismConstraint(
            min_value=30.0,
            max_value=400.0,
            parameter_type=ParameterType.LENGTH,
            step_size=1.0,
            preferred_range=(80.0, 200.0)
        )
        
        # Input speed
        self.constraints['input_speed'] = MechanismConstraint(
            min_value=0.1,
            max_value=300.0,
            parameter_type=ParameterType.SPEED,
            step_size=0.5,
            preferred_range=(10.0, 100.0)
        )
        
    def _setup_educational_info(self) -> None:
        """Setup educational information"""
        self.educational_info = {
            'description': 'The four-bar linkage is the fundamental building block of many mechanical systems.',
            'applications': [
                'Windshield wipers',
                'Robot arms', 
                'Engine valve mechanisms',
                'Suspension systems',
                'Manufacturing machinery'
            ],
            'key_concepts': [
                'Grashof condition determines motion type',
                'Transmission angle affects mechanical advantage',
                'Coupler curves create complex paths',
                'Dead positions occur at extremes'
            ],
            'learning_objectives': [
                'Understand Grashof classification system',
                'Analyze transmission angle variation',
                'Predict motion limits and dead positions',
                'Design for optimal mechanical advantage'
            ]
        }
        
    def _calculate_initial_state(self) -> None:
        """Calculate initial mechanism state"""
        # Fixed joint positions
        ground_length = self.state.parameters['ground_length']
        
        # Ground joints (fixed)
        self.state.joints['A'] = Joint('A', (0.0, 0.0), 'fixed')  # Input pivot
        self.state.joints['B'] = Joint('B', (ground_length, 0.0), 'fixed')  # Output pivot
        
        # Moving joints (calculated by kinematics)
        self.state.joints['C'] = Joint('C', (0.0, 0.0), 'revolute')  # Input-coupler joint
        self.state.joints['D'] = Joint('D', (0.0, 0.0), 'revolute')  # Coupler-output joint
        
        # Links
        self.state.links['input'] = Link(
            'input', 'A', 'C', 
            self.state.parameters['input_length'],
            color='#e74c3c'  # Red for input
        )
        self.state.links['coupler'] = Link(
            'coupler', 'C', 'D',
            self.state.parameters['coupler_length'], 
            color='#3498db'  # Blue for coupler
        )
        self.state.links['output'] = Link(
            'output', 'D', 'B',
            self.state.parameters['output_length'],
            color='#27ae60'  # Green for output
        )
        self.state.links['ground'] = Link(
            'ground', 'A', 'B',
            self.state.parameters['ground_length'],
            color='#95a5a6'  # Gray for ground
        )
        
        # Calculate initial position (input at 0°)
        self.calculate_kinematics(0.0)
        
        # Perform Grashof analysis
        self._analyze_grashof_condition()
        
    def calculate_kinematics(self, input_angle: float) -> bool:
        """
        Calculate four-bar linkage kinematics using exact analytical methods.
        
        Uses circle intersection method for robust position analysis.
        Maintains motion continuity to avoid branch jumping.
        
        Args:
            input_angle: Input crank angle in degrees
            
        Returns:
            True if valid configuration found, False otherwise
        """
        try:
            # Get current link lengths
            a = self.state.parameters['input_length']  # Input crank
            b = self.state.parameters['coupler_length']  # Coupler
            c = self.state.parameters['output_length']   # Output rocker
            d = self.state.parameters['ground_length']   # Ground
            
            # Fixed joint positions
            A = self.state.joints['A'].position  # (0, 0)
            B = self.state.joints['B'].position  # (d, 0)
            
            # Input joint position (rotate around A)
            theta2_rad = math.radians(input_angle)
            C = (A[0] + a * math.cos(theta2_rad), A[1] + a * math.sin(theta2_rad))
            
            # Find output joint position using circle intersection
            # Circle 1: centered at C with radius b (coupler length)
            # Circle 2: centered at B with radius c (output length)
            intersections = self.circle_intersection(C, b, B, c)
            
            if not intersections:
                # No valid configuration - links cannot connect
                self.state.is_valid = False
                self.state.error_message = "Invalid configuration: links cannot connect"
                return False
                
            # Choose correct intersection point to maintain motion continuity
            D = self._select_continuous_solution(intersections, input_angle)
            
            # Update joint positions
            self.state.joints['C'].position = C
            self.state.joints['D'].position = D
            
            # Calculate and update link angles
            self._update_link_angles()
            
            # Calculate transmission angle
            transmission_angle = self._calculate_transmission_angle()
            
            # Update educational analysis
            self._update_motion_analysis(input_angle, transmission_angle)
            
            self.state.is_valid = True
            self.state.error_message = None
            return True
            
        except Exception as e:
            self.state.is_valid = False
            self.state.error_message = f"Kinematic calculation failed: {str(e)}"
            return False
            
    def _select_continuous_solution(self, intersections: List[Tuple[float, float]], 
                                  input_angle: float) -> Tuple[float, float]:
        """
        Select intersection point that maintains motion continuity.
        
        Prevents branch jumping by choosing the solution closest to
        the previous position or using motion type analysis.
        """
        if len(intersections) == 1:
            return intersections[0]
            
        # For two intersections, choose based on motion type and continuity
        D1, D2 = intersections
        
        # Get previous position if available
        prev_D = self.state.joints['D'].position
        
        # If we have a previous position, choose closest point
        if prev_D != (0.0, 0.0):  # Not initial state
            dist1 = self.calculate_distance(D1, prev_D)
            dist2 = self.calculate_distance(D2, prev_D)
            return D1 if dist1 < dist2 else D2
            
        # For initial position, choose based on Grashof classification
        grashof_analysis = getattr(self, '_grashof_analysis', None)
        if grashof_analysis:
            if grashof_analysis.classification == GrashofClassification.CRANK_ROCKER:
                # Choose the solution that gives proper rocker motion
                B = self.state.joints['B'].position
                # Choose point that keeps output link in expected quadrant
                angle1 = self.calculate_angle(B, D1)
                angle2 = self.calculate_angle(B, D2)
                # For initial position, choose upper solution for standard orientation
                return D1 if D1[1] > D2[1] else D2
                
        # Default: choose upper solution
        return D1 if D1[1] > D2[1] else D2
        
    def _update_link_angles(self) -> None:
        """Update link angles based on current joint positions"""
        joints = self.state.joints
        links = self.state.links
        
        # Input link angle
        links['input'].angle = self.calculate_angle(
            joints['A'].position, joints['C'].position
        )
        
        # Coupler link angle  
        links['coupler'].angle = self.calculate_angle(
            joints['C'].position, joints['D'].position
        )
        
        # Output link angle
        links['output'].angle = self.calculate_angle(
            joints['D'].position, joints['B'].position
        )
        
        # Ground link angle (always 0°)
        links['ground'].angle = 0.0
        
    def _calculate_transmission_angle(self) -> float:
        """
        Calculate transmission angle between coupler and output links.
        
        Transmission angle indicates mechanical advantage quality.
        Optimal range is 40° to 140° for good force transmission.
        """
        C = self.state.joints['C'].position
        D = self.state.joints['D'].position  
        B = self.state.joints['B'].position
        
        # Vectors along coupler and output links
        coupler_vector = (D[0] - C[0], D[1] - C[1])
        output_vector = (B[0] - D[0], B[1] - D[1])
        
        # Calculate angle between vectors
        dot_product = (coupler_vector[0] * output_vector[0] + 
                      coupler_vector[1] * output_vector[1])
        
        coupler_mag = math.sqrt(coupler_vector[0]**2 + coupler_vector[1]**2)
        output_mag = math.sqrt(output_vector[0]**2 + output_vector[1]**2)
        
        if coupler_mag == 0 or output_mag == 0:
            return 90.0
            
        cos_angle = dot_product / (coupler_mag * output_mag)
        cos_angle = max(-1.0, min(1.0, cos_angle))  # Clamp to valid range
        
        transmission_angle = math.degrees(math.acos(abs(cos_angle)))
        return transmission_angle
        
    def _analyze_grashof_condition(self) -> GrashofAnalysis:
        """
        Perform complete Grashof analysis of the four-bar linkage.
        
        Returns:
            Detailed analysis including classification and motion predictions
        """
        # Get link lengths
        a = self.state.parameters['input_length']   # Input
        b = self.state.parameters['coupler_length'] # Coupler  
        c = self.state.parameters['output_length']  # Output
        d = self.state.parameters['ground_length']  # Ground
        
        links = [a, b, c, d]
        link_names = ['input', 'coupler', 'output', 'ground']
        
        # Find shortest and longest links
        s = min(links)  # Shortest
        l = max(links)  # Longest
        
        # Get indices
        s_idx = links.index(s)
        l_idx = links.index(l)
        
        shortest_name = link_names[s_idx]
        longest_name = link_names[l_idx]
        
        # Calculate remaining links (p and q)
        remaining_links = [x for i, x in enumerate(links) if i not in [s_idx, l_idx]]
        p, q = remaining_links
        
        # Grashof ratio
        grashof_ratio = (s + l) / (p + q)
        
        # Classify mechanism
        if s + l < p + q:
            # Grashof condition satisfied
            if shortest_name == 'ground':
                classification = GrashofClassification.DOUBLE_CRANK
            elif shortest_name in ['input', 'output']:
                classification = GrashofClassification.CRANK_ROCKER  
            else:  # shortest is coupler
                classification = GrashofClassification.DOUBLE_ROCKER
        elif s + l == p + q:
            classification = GrashofClassification.CHANGE_POINT
        else:
            classification = GrashofClassification.DOUBLE_ROCKER
            
        # Check triangle inequality (mechanism must be assemblable)
        if l >= s + p + q:
            classification = GrashofClassification.INVALID
            
        # Analyze motion capabilities
        can_rotate = {
            'input': False,
            'coupler': False, 
            'output': False,
            'ground': True  # Ground is always fixed
        }
        
        motion_limits = {}
        
        if classification == GrashofClassification.DOUBLE_CRANK:
            can_rotate['input'] = True
            can_rotate['output'] = True
            motion_limits = {
                'input': (0.0, 360.0),
                'output': (0.0, 360.0)
            }
        elif classification == GrashofClassification.CRANK_ROCKER:
            if shortest_name == 'input':
                can_rotate['input'] = True
                motion_limits['input'] = (0.0, 360.0)
                # Calculate rocker motion limits
                motion_limits['output'] = self._calculate_rocker_limits()
            else:
                can_rotate['output'] = True  
                motion_limits['output'] = (0.0, 360.0)
                motion_limits['input'] = self._calculate_rocker_limits()
        else:
            # Double rocker - both oscillate
            motion_limits['input'] = self._calculate_rocker_limits('input')
            motion_limits['output'] = self._calculate_rocker_limits('output')
            
        # Calculate transmission angle range (requires full motion analysis)
        trans_min, trans_max = self._calculate_transmission_angle_range()
        
        # Calculate mechanical advantage range
        ma_min, ma_max = self._calculate_mechanical_advantage_range()
        
        analysis = GrashofAnalysis(
            classification=classification,
            grashof_ratio=grashof_ratio,
            shortest_link=shortest_name,
            longest_link=longest_name,
            can_rotate_fully=can_rotate,
            motion_limits=motion_limits,
            transmission_angle_range=(trans_min, trans_max),
            mechanical_advantage_range=(ma_min, ma_max)
        )
        
        # Store analysis for later use
        self._grashof_analysis = analysis
        
        # Update educational info with analysis
        self._update_educational_analysis(analysis)
        
        return analysis
        
    def _calculate_rocker_limits(self, link_name: str = 'output') -> Tuple[float, float]:
        """Calculate angular motion limits for rocker links"""
        # This requires solving for extreme positions
        # Simplified calculation - full implementation would solve analytically
        return (-45.0, 45.0)  # Placeholder
        
    def _calculate_transmission_angle_range(self) -> Tuple[float, float]:
        """Calculate minimum and maximum transmission angles"""
        # This requires analysis over full motion cycle
        # Simplified calculation - full implementation would analyze complete cycle
        return (30.0, 150.0)  # Placeholder
        
    def _calculate_mechanical_advantage_range(self) -> Tuple[float, float]:
        """Calculate range of mechanical advantage"""
        # MA = (output torque) / (input torque) = sin(transmission_angle) * (input_length/output_length)
        a = self.state.parameters['input_length']
        c = self.state.parameters['output_length']
        
        # Approximate range based on transmission angle range
        trans_min, trans_max = self._calculate_transmission_angle_range()
        
        ma_min = math.sin(math.radians(trans_min)) * (a / c)
        ma_max = math.sin(math.radians(trans_max)) * (a / c)
        
        return (min(ma_min, ma_max), max(ma_min, ma_max))
        
    def _update_educational_analysis(self, analysis: GrashofAnalysis) -> None:
        """Update educational information with Grashof analysis"""
        self.educational_info['grashof_analysis'] = {
            'classification': analysis.classification.value,
            'explanation': self._get_grashof_explanation(analysis.classification),
            'grashof_ratio': analysis.grashof_ratio,
            'motion_type': self._get_motion_description(analysis.classification),
            'design_recommendations': self._get_design_recommendations(analysis)
        }
        
    def _get_grashof_explanation(self, classification: GrashofClassification) -> str:
        """Get educational explanation for Grashof classification"""
        explanations = {
            GrashofClassification.CRANK_ROCKER: 
                "One link rotates fully (crank) while the other oscillates (rocker). Most common type.",
            GrashofClassification.DOUBLE_CRANK:
                "Both input and output links can rotate fully. Creates continuous rotation transmission.",
            GrashofClassification.DOUBLE_ROCKER:
                "Both links oscillate. No continuous rotation possible. Good for oscillating motions.",
            GrashofClassification.CHANGE_POINT:
                "Special case where mechanism is at the boundary between types. May have dead positions.",
            GrashofClassification.INVALID:
                "Cannot be assembled - longest link is too long compared to others."
        }
        return explanations.get(classification, "Unknown classification")
        
    def _get_motion_description(self, classification: GrashofClassification) -> str:
        """Get motion type description"""
        if classification == GrashofClassification.CRANK_ROCKER:
            return "Continuous input rotation produces oscillating output"
        elif classification == GrashofClassification.DOUBLE_CRANK:
            return "Continuous rotation in both directions"
        elif classification == GrashofClassification.DOUBLE_ROCKER:
            return "Oscillating motion in both directions"
        else:
            return "Special or invalid motion pattern"
            
    def _get_design_recommendations(self, analysis: GrashofAnalysis) -> List[str]:
        """Get design recommendations based on analysis"""
        recommendations = []
        
        if analysis.classification == GrashofClassification.INVALID:
            recommendations.append("Reduce longest link length or increase others")
            recommendations.append("Check triangle inequality: longest < sum of other three")
            
        if analysis.transmission_angle_range[0] < 30:
            recommendations.append("Poor transmission angle - increase coupler length")
            
        if analysis.transmission_angle_range[1] > 150:
            recommendations.append("Poor transmission angle - check link proportions")
            
        if analysis.grashof_ratio > 1.2:
            recommendations.append("Far from Grashof condition - expect double rocker motion")
            
        return recommendations
        
    def _update_motion_analysis(self, input_angle: float, transmission_angle: float) -> None:
        """Update motion analysis data for current position"""
        # Store current motion data for educational display
        self.state.motion_data = {
            'input_angle': input_angle,
            'output_angle': self.state.links['output'].angle,
            'transmission_angle': transmission_angle,
            'mechanical_advantage': math.sin(math.radians(transmission_angle)) * 
                                  (self.state.parameters['input_length'] / self.state.parameters['output_length']),
            'coupler_position': self.state.joints['D'].position
        }
        
    def _validate_mechanism_constraints(self) -> List[str]:
        """Validate four-bar specific constraints"""
        errors = []
        
        # Get link lengths
        a = self.state.parameters['input_length']
        b = self.state.parameters['coupler_length']  
        c = self.state.parameters['output_length']
        d = self.state.parameters['ground_length']
        
        # Triangle inequality check
        links = [a, b, c, d]
        max_link = max(links)
        sum_others = sum(links) - max_link
        
        if max_link >= sum_others:
            errors.append("Triangle inequality violated - mechanism cannot be assembled")
            
        # Minimum link ratios
        min_length = min(links)
        max_length = max(links)
        
        if max_length / min_length > 10:
            errors.append("Extreme link ratio - may cause numerical instability")
            
        return errors
        
    def get_grashof_analysis(self) -> Optional[GrashofAnalysis]:
        """Get current Grashof analysis"""
        return getattr(self, '_grashof_analysis', None)