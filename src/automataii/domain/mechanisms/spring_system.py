"""
Rigorous Spring System Mechanism Implementation.

Implements accurate spring dynamics, harmonic oscillation analysis, and energy calculations
with educational content about vibration theory and dynamic systems.
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from dataclasses import dataclass

from .base import BaseMechanism, MechanismConstraint, ParameterType, Joint, Link


class SpringType(Enum):
    """Types of spring systems"""
    COMPRESSION = "Compression"      # Spring under compression
    TENSION = "Tension"              # Spring under tension
    TORSIONAL = "Torsional"          # Rotational spring


class DampingType(Enum):
    """Types of damping"""
    NONE = "None"                    # No damping (ideal spring)
    VISCOUS = "Viscous"              # Linear damping (dashpot)
    COULOMB = "Coulomb"              # Friction damping


@dataclass
class SpringAnalysis:
    """Analysis results for spring system"""
    spring_constant: float  # Spring stiffness (N/m)
    natural_frequency: float  # Undamped natural frequency (Hz)
    damped_frequency: float  # Damped natural frequency (Hz)
    damping_ratio: float  # Damping ratio (dimensionless)
    quality_factor: float  # Q factor for oscillation quality
    static_deflection: float  # Static deflection under load (mm)
    maximum_stress: float  # Maximum spring stress (MPa)
    spring_type: SpringType  # Type of spring system
    damping_type: DampingType  # Type of damping


class SpringSystem(BaseMechanism):
    """
    Rigorous spring system mechanism implementation.
    
    Features:
    - Accurate spring dynamics with Hooke's law
    - Harmonic oscillation analysis with damping
    - Energy calculations (kinetic, potential, dissipated)
    - Educational content about vibration theory
    - Support for different spring and damping types
    """
    
    def __init__(self):
        super().__init__("Spring System")
        
    def _setup_parameters(self) -> None:
        """Setup spring system parameters"""
        # Spring and mass parameters
        self.state.parameters = {
            'spring_constant': 200.0,        # Spring stiffness (N/m)
            'natural_length': 150.0,         # Unloaded spring length (mm)
            'mass': 2.0,                     # Attached mass (kg)
            'damping_coefficient': 10.0,     # Damping coefficient (N⋅s/m)
            'applied_force': 20.0,           # Static applied force (N)
            'oscillation_frequency': 1.0,    # Driving frequency (Hz)
            'oscillation_amplitude': 15.0,   # Driving amplitude (mm)
        }
        
    def _setup_constraints(self) -> None:
        """Setup parameter constraints"""
        
        # Spring constant
        self.constraints['spring_constant'] = MechanismConstraint(
            min_value=10.0,
            max_value=2000.0,
            parameter_type=ParameterType.FORCE,  # N/m
            step_size=5.0,
            preferred_range=(50.0, 500.0)
        )
        
        # Natural length
        self.constraints['natural_length'] = MechanismConstraint(
            min_value=50.0,
            max_value=300.0,
            parameter_type=ParameterType.LENGTH,
            step_size=5.0,
            preferred_range=(100.0, 200.0)
        )
        
        # Mass
        self.constraints['mass'] = MechanismConstraint(
            min_value=0.1,
            max_value=10.0,
            parameter_type=ParameterType.FORCE,  # Using force type for mass (kg)
            step_size=0.1,
            preferred_range=(0.5, 5.0)
        )
        
        # Damping coefficient
        self.constraints['damping_coefficient'] = MechanismConstraint(
            min_value=0.0,
            max_value=100.0,
            parameter_type=ParameterType.FORCE,  # N⋅s/m
            step_size=1.0,
            preferred_range=(2.0, 30.0)
        )
        
        # Applied force
        self.constraints['applied_force'] = MechanismConstraint(
            min_value=0.0,
            max_value=200.0,
            parameter_type=ParameterType.FORCE,
            step_size=1.0,
            preferred_range=(10.0, 50.0)
        )
        
        # Oscillation frequency
        self.constraints['oscillation_frequency'] = MechanismConstraint(
            min_value=0.1,
            max_value=10.0,
            parameter_type=ParameterType.SPEED,  # Hz
            step_size=0.1,
            preferred_range=(0.5, 5.0)
        )
        
        # Oscillation amplitude
        self.constraints['oscillation_amplitude'] = MechanismConstraint(
            min_value=0.0,
            max_value=50.0,
            parameter_type=ParameterType.LENGTH,
            step_size=1.0,
            preferred_range=(5.0, 25.0)
        )
        
    def _setup_educational_info(self) -> None:
        """Setup educational information"""
        self.educational_info = {
            'description': 'Spring systems demonstrate fundamental principles of vibration and harmonic motion.',
            'applications': [
                'Vehicle suspension systems',
                'Vibration isolation mounts',
                'Mechanical oscillators',
                'Seismic dampers',
                'Precision balance mechanisms'
            ],
            'key_concepts': [
                'Natural frequency depends on spring stiffness and mass',
                'Damping reduces oscillation amplitude and shifts frequency',
                'Resonance occurs when driving frequency matches natural frequency',
                'Quality factor indicates sharpness of resonance'
            ],
            'learning_objectives': [
                'Understand relationship between stiffness, mass, and frequency',
                'Analyze effects of damping on oscillatory motion',
                'Calculate energy storage and dissipation in springs',
                'Design spring systems for specific dynamic requirements'
            ]
        }
        
    def _calculate_initial_state(self) -> None:
        """Calculate initial mechanism state"""
        # Get parameters
        natural_length = self.state.parameters['natural_length']
        applied_force = self.state.parameters['applied_force']
        spring_constant = self.state.parameters['spring_constant']
        
        # Calculate static equilibrium position
        static_deflection = applied_force / spring_constant if spring_constant > 0 else 0.0
        
        # Fixed spring anchor
        self.state.joints['anchor'] = Joint('anchor', (0.0, 0.0), 'fixed')
        
        # Mass position (positive y is up, spring extends downward)
        equilibrium_y = -(natural_length + static_deflection)
        self.state.joints['mass'] = Joint('mass', (0.0, equilibrium_y), 'prismatic')
        
        # Spring representation as a link
        current_length = natural_length + static_deflection
        self.state.links['spring'] = Link(
            'spring', 'anchor', 'mass',
            current_length,
            color='#2ecc71'  # Green for spring
        )
        
        # Store system state
        self._system_state = {
            'time': 0.0,
            'position': static_deflection,  # Displacement from natural length
            'velocity': 0.0,
            'acceleration': 0.0,
            'static_deflection': static_deflection
        }
        
        # Calculate initial kinematics
        self.calculate_kinematics(0.0)
        
        # Perform spring analysis
        self._analyze_spring_system()
        
    def calculate_kinematics(self, input_angle: float) -> bool:
        """
        Calculate spring system dynamics using harmonic motion equations.
        
        Args:
            input_angle: Time-based angle for oscillation (degrees)
            
        Returns:
            True if calculation successful, False otherwise
        """
        try:
            # Convert angle to time (assuming 1 degree = 1/360 second)
            time = input_angle / 360.0
            
            # Get parameters
            k = self.state.parameters['spring_constant']
            m = self.state.parameters['mass']
            c = self.state.parameters['damping_coefficient']
            F0 = self.state.parameters['applied_force']
            freq = self.state.parameters['oscillation_frequency']
            amp = self.state.parameters['oscillation_amplitude'] / 1000.0  # Convert mm to m
            
            # Calculate natural frequency and damping ratio
            omega_n = math.sqrt(k / m)  # Natural frequency (rad/s)
            zeta = c / (2 * math.sqrt(k * m))  # Damping ratio
            
            # Static deflection
            static_deflection = F0 / k
            
            # Driving frequency
            omega_d = 2 * math.pi * freq  # Driving frequency (rad/s)
            
            # Calculate response (simplified analysis for educational purposes)
            if zeta < 1.0:  # Underdamped
                omega_damped = omega_n * math.sqrt(1 - zeta**2)
                
                # Free vibration component (decaying)
                free_response = amp * math.exp(-zeta * omega_n * time) * math.cos(omega_damped * time)
                
                # Forced response (steady-state)
                frequency_ratio = omega_d / omega_n
                denominator = math.sqrt((1 - frequency_ratio**2)**2 + (2 * zeta * frequency_ratio)**2)
                
                if denominator > 0:
                    forced_amplitude = amp / denominator
                    phase_lag = math.atan2(2 * zeta * frequency_ratio, 1 - frequency_ratio**2)
                    forced_response = forced_amplitude * math.sin(omega_d * time - phase_lag)
                else:
                    forced_response = 0.0
                    
                # Total displacement from equilibrium
                dynamic_displacement = free_response + forced_response
                
            else:  # Overdamped or critically damped
                # Simplified exponential decay
                dynamic_displacement = amp * math.exp(-omega_n * time)
                
            # Total position (static + dynamic)
            total_displacement = static_deflection + dynamic_displacement
            
            # Velocity and acceleration (approximate derivatives)
            dt = 0.001  # Small time step for numerical differentiation
            if time > dt:
                # Use stored previous values for differentiation
                prev_displacement = getattr(self, '_prev_displacement', static_deflection)
                velocity = (dynamic_displacement - (prev_displacement - static_deflection)) / dt
                prev_velocity = getattr(self, '_prev_velocity', 0.0)
                acceleration = (velocity - prev_velocity) / dt
            else:
                velocity = 0.0
                acceleration = 0.0
                
            # Store for next iteration
            self._prev_displacement = total_displacement
            self._prev_velocity = velocity
            
            # Update joint positions
            natural_length = self.state.parameters['natural_length'] / 1000.0  # Convert to m
            mass_y = -(natural_length + total_displacement) * 1000.0  # Convert back to mm
            
            self.state.joints['mass'].position = (0.0, mass_y)
            
            # Update link length
            current_length = (natural_length + total_displacement) * 1000.0  # mm
            self.state.links['spring'].length = current_length
            
            # Update system state
            self._system_state.update({
                'time': time,
                'position': total_displacement * 1000.0,  # mm
                'velocity': velocity * 1000.0,  # mm/s
                'acceleration': acceleration * 1000.0,  # mm/s²
                'static_deflection': static_deflection * 1000.0  # mm
            })
            
            # Calculate motion analysis
            self._update_motion_analysis(time, total_displacement, velocity, acceleration)
            
            self.state.is_valid = True
            self.state.error_message = None
            return True
            
        except Exception as e:
            self.state.is_valid = False
            self.state.error_message = f"Spring calculation failed: {str(e)}"
            return False
            
    def _update_motion_analysis(self, time: float, displacement: float, 
                              velocity: float, acceleration: float) -> None:
        """Update motion analysis with spring dynamics data"""
        
        # Get parameters
        k = self.state.parameters['spring_constant']
        m = self.state.parameters['mass']
        c = self.state.parameters['damping_coefficient']
        
        # Calculate forces
        spring_force = k * displacement  # Hooke's law
        damping_force = c * velocity     # Viscous damping
        inertia_force = m * acceleration # F = ma
        
        # Calculate energies
        kinetic_energy = 0.5 * m * velocity**2
        potential_energy = 0.5 * k * displacement**2
        total_energy = kinetic_energy + potential_energy
        
        # Power dissipation
        power_dissipated = c * velocity**2
        
        # Store motion data
        self.state.motion_data = {
            'time': time,
            'displacement': displacement * 1000.0,  # mm
            'velocity': velocity * 1000.0,  # mm/s
            'acceleration': acceleration * 1000.0,  # mm/s²
            'spring_force': spring_force,  # N
            'damping_force': damping_force,  # N
            'inertia_force': inertia_force,  # N
            'kinetic_energy': kinetic_energy,  # J
            'potential_energy': potential_energy,  # J
            'total_energy': total_energy,  # J
            'power_dissipated': power_dissipated  # W
        }
        
    def _analyze_spring_system(self) -> SpringAnalysis:
        """Perform complete analysis of the spring system"""
        # Get parameters
        k = self.state.parameters['spring_constant']
        m = self.state.parameters['mass']
        c = self.state.parameters['damping_coefficient']
        F0 = self.state.parameters['applied_force']
        
        # Natural frequency (undamped)
        omega_n = math.sqrt(k / m)  # rad/s
        natural_frequency = omega_n / (2 * math.pi)  # Hz
        
        # Damping ratio
        damping_ratio = c / (2 * math.sqrt(k * m))
        
        # Damped frequency
        if damping_ratio < 1.0:
            omega_damped = omega_n * math.sqrt(1 - damping_ratio**2)
            damped_frequency = omega_damped / (2 * math.pi)  # Hz
        else:
            damped_frequency = 0.0  # No oscillation for overdamped
            
        # Quality factor
        quality_factor = 1 / (2 * damping_ratio) if damping_ratio > 0 else float('inf')
        
        # Static deflection
        static_deflection = (F0 / k) * 1000.0  # mm
        
        # Maximum stress (simplified for educational purposes)
        # Assume spring wire stress τ = 8*F*D/(π*d³) where F is force, D is coil diameter, d is wire diameter
        # For educational purposes, use a representative stress
        max_force = F0 + k * (self.state.parameters['oscillation_amplitude'] / 1000.0)
        maximum_stress = max_force * 50  # Simplified stress calculation (MPa)
        
        # Determine spring and damping types
        spring_type = SpringType.COMPRESSION  # Default assumption
        damping_type = DampingType.VISCOUS if c > 0 else DampingType.NONE
        
        analysis = SpringAnalysis(
            spring_constant=k,
            natural_frequency=natural_frequency,
            damped_frequency=damped_frequency,
            damping_ratio=damping_ratio,
            quality_factor=quality_factor,
            static_deflection=static_deflection,
            maximum_stress=maximum_stress,
            spring_type=spring_type,
            damping_type=damping_type
        )
        
        # Store analysis
        self._spring_analysis = analysis
        
        # Update educational info
        self._update_educational_analysis(analysis)
        
        return analysis
        
    def _update_educational_analysis(self, analysis: SpringAnalysis) -> None:
        """Update educational information with spring analysis"""
        self.educational_info['spring_analysis'] = {
            'natural_frequency': f"{analysis.natural_frequency:.2f} Hz",
            'damping_type': analysis.damping_type.value,
            'damping_classification': self._get_damping_classification(analysis.damping_ratio),
            'quality_factor': f"{analysis.quality_factor:.1f}",
            'resonance_sharpness': self._get_resonance_rating(analysis.quality_factor),
            'design_recommendations': self._get_design_recommendations(analysis)
        }
        
    def _get_damping_classification(self, damping_ratio: float) -> str:
        """Get damping classification based on damping ratio"""
        if damping_ratio < 0.1:
            return "Lightly damped - Sharp resonance"
        elif damping_ratio < 0.7:
            return "Underdamped - Oscillatory with decay"
        elif damping_ratio < 1.0:
            return "Moderately damped - Fast settling"
        elif damping_ratio == 1.0:
            return "Critically damped - Optimal response"
        else:
            return "Overdamped - Slow, non-oscillatory"
            
    def _get_resonance_rating(self, quality_factor: float) -> str:
        """Get resonance sharpness rating"""
        if quality_factor < 1:
            return "Very broad resonance"
        elif quality_factor < 5:
            return "Moderate resonance"
        elif quality_factor < 20:
            return "Sharp resonance"
        else:
            return "Very sharp resonance - potential for instability"
            
    def _get_design_recommendations(self, analysis: SpringAnalysis) -> List[str]:
        """Get design recommendations based on analysis"""
        recommendations = []
        
        if analysis.damping_ratio < 0.05:
            recommendations.append("Very low damping - add damper to prevent excessive oscillation")
            
        if analysis.damping_ratio > 2.0:
            recommendations.append("High damping - system may be too sluggish")
            
        if analysis.quality_factor > 50:
            recommendations.append("Very high Q factor - system may be unstable at resonance")
            
        if analysis.maximum_stress > 1000:  # MPa
            recommendations.append("High stress - check spring material and safety factor")
            
        if analysis.natural_frequency < 1.0:
            recommendations.append("Low natural frequency - increase spring stiffness or reduce mass")
            
        return recommendations
        
    def _validate_mechanism_constraints(self) -> List[str]:
        """Validate spring system specific constraints"""
        errors = []
        
        # Get parameters
        k = self.state.parameters['spring_constant']
        m = self.state.parameters['mass']
        c = self.state.parameters['damping_coefficient']
        
        # Basic physical constraints
        if k <= 0:
            errors.append("Spring constant must be positive")
            
        if m <= 0:
            errors.append("Mass must be positive")
            
        if c < 0:
            errors.append("Damping coefficient cannot be negative")
            
        # System stability
        if m > 0 and k > 0:
            damping_ratio = c / (2 * math.sqrt(k * m))
            if damping_ratio > 5.0:
                errors.append("Excessive damping - system may be unresponsive")
                
        # Practical limits
        natural_freq = math.sqrt(k / m) / (2 * math.pi) if m > 0 and k > 0 else 0
        if natural_freq > 100:  # Hz
            errors.append("Very high natural frequency - may cause manufacturing issues")
            
        return errors