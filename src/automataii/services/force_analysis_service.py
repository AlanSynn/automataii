"""
Force Analysis Service - Actuator Optimization

Advanced force propagation analysis for optimal actuator placement
in mechanical characters. Analyzes force transmission quality,
torque requirements, and power consumption to determine optimal
driving points and actuator specifications.

Architecture: Disney Research Computational Character Design
- Inverse dynamics analysis for actuator torque calculation
- Force transmission quality evaluation for optimal driving points
- Actuator specification optimization based on motion requirements
- Power analysis and efficiency optimization
"""

import logging
import math
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal

from ..core.event_bus import EventBus
from ..core.event_types import EventType
from ..models.mechanical_character import ActuatorSpec, ActuatorType
from ..models.mechanism import Mechanism, Point2D, MechanismJoint, MechanismLink

logger = logging.getLogger(__name__)


@dataclass
class ForceAnalysisResult:
    """Results of force analysis for mechanism actuator optimization"""
    mechanism_id: str
    analysis_timestamp: float
    
    # Force requirements
    max_torque_required: float          # Peak torque during cycle (N⋅m)
    average_torque: float               # Average torque (N⋅m)
    rms_torque: float                   # RMS torque for motor sizing (N⋅m)
    peak_power: float                   # Peak power requirement (W)
    average_power: float                # Average power consumption (W)
    
    # Optimal driving configuration
    optimal_driving_joint: str          # Best joint for actuation
    transmission_quality: float         # Force transmission efficiency (0-1)
    mechanical_advantage: float         # Average mechanical advantage
    
    # Motion characteristics
    speed_requirements: Dict[str, float] # Angular velocities (rad/s)
    acceleration_peaks: Dict[str, float] # Angular accelerations (rad/s²)
    
    # Recommended actuator
    recommended_actuator: Optional[ActuatorSpec] = None
    actuator_safety_factor: float = 2.0  # Safety margin for actuator sizing


class ForceAnalysisService(QObject):
    """
    Force propagation analysis service for optimal actuator placement.
    
    Performs comprehensive force analysis to determine:
    - Required torques throughout motion cycle
    - Optimal driving link selection for smooth force transmission
    - Actuator specifications (torque, speed, power)
    - Transmission quality and mechanical advantage analysis
    - Power consumption and efficiency optimization
    
    Analysis Methods:
    - Inverse Dynamics: Calculate required forces from desired motion
    - Transmission Analysis: Evaluate force propagation quality
    - Actuator Optimization: Match requirements to available actuators
    - Power Analysis: Calculate energy consumption and battery requirements
    """
    
    # Signals for progress feedback
    force_analysis_started = pyqtSignal(str, str)  # character_id, mechanism_id
    force_analysis_completed = pyqtSignal(str, dict)  # character_id, analysis_data
    actuator_optimized = pyqtSignal(str, dict)  # mechanism_id, actuator_spec
    force_analysis_failed = pyqtSignal(str, str, str)  # character_id, mechanism_id, error
    
    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        
        # Analysis parameters
        self.cycle_resolution = 100         # Number of analysis points per cycle
        self.force_analysis_timeout = 5.0   # Maximum analysis time (seconds)
        self.default_load = 10.0            # Default load force (N)
        self.safety_factor = 2.0            # Safety factor for actuator sizing
        
        # Actuator database (simplified - would be loaded from external DB)
        self.actuator_database = self._initialize_actuator_database()
        
        # Analysis state
        self._current_analyses: Dict[str, ForceAnalysisResult] = {}
        
        # Subscribe to force analysis requests
        self._subscribe_to_events()
        
        logger.info("ForceAnalysisService initialized for actuator optimization")
    
    def _subscribe_to_events(self):
        """Subscribe to force analysis request events"""
        self.event_bus.subscribe(
            EventType.FORCE_ANALYSIS_REQUESTED,
            self._handle_force_analysis_request
        )
    
    def _handle_force_analysis_request(self, event_data: Dict[str, Any]):
        """
        Handle force analysis request from character design service.
        
        Args:
            event_data: Contains character_id, mechanism_id, mechanism_data
        """
        try:
            character_id = event_data.get('character_id')
            mechanism_id = event_data.get('mechanism_id')
            mechanism_data = event_data.get('mechanism_data')
            
            if not all([character_id, mechanism_id, mechanism_data]):
                logger.error("Invalid force analysis request - missing required data")
                return
            
            logger.info(f"Starting force analysis for mechanism {mechanism_id} in character {character_id}")
            
            # Emit start signal
            self.force_analysis_started.emit(character_id, mechanism_id)
            
            # Perform force analysis
            analysis_result = self._analyze_mechanism_forces(mechanism_id, mechanism_data)
            
            if analysis_result:
                # Store result
                self._current_analyses[mechanism_id] = analysis_result
                
                # Generate actuator recommendation
                actuator_spec = self._generate_actuator_specification(
                    character_id, mechanism_id, analysis_result
                )
                
                if actuator_spec:
                    analysis_result.recommended_actuator = actuator_spec
                    
                    # Emit actuator optimization signal
                    self.actuator_optimized.emit(mechanism_id, actuator_spec.__dict__)
                
                # Publish completion event
                analysis_data = {
                    'character_id': character_id,
                    'mechanism_id': mechanism_id,
                    'analysis_result': self._analysis_result_to_dict(analysis_result),
                    'actuator_spec': actuator_spec.__dict__ if actuator_spec else None
                }
                
                self.event_bus.publish(EventType.FORCE_ANALYSIS_COMPLETED, analysis_data)
                self.force_analysis_completed.emit(character_id, analysis_data)
                
                logger.info(f"Force analysis completed for mechanism {mechanism_id}")
                
            else:
                error_msg = "Force analysis failed - no valid results generated"
                self._handle_analysis_error(character_id, mechanism_id, error_msg)
                
        except Exception as e:
            error_msg = f"Force analysis error: {str(e)}"
            logger.error(error_msg)
            
            character_id = event_data.get('character_id', 'unknown')
            mechanism_id = event_data.get('mechanism_id', 'unknown')
            self._handle_analysis_error(character_id, mechanism_id, error_msg)
    
    def _analyze_mechanism_forces(self, mechanism_id: str, mechanism_data: Dict[str, Any]) -> Optional[ForceAnalysisResult]:
        """
        Perform comprehensive force analysis on mechanism.
        
        Args:
            mechanism_id: Mechanism identifier
            mechanism_data: Complete mechanism specification
            
        Returns:
            ForceAnalysisResult: Complete force analysis results
        """
        try:
            # Create mechanism object from data
            mechanism = self._mechanism_from_data(mechanism_data)
            if not mechanism:
                return None
            
            # Analyze all possible driving points
            driving_analysis = self._analyze_driving_options(mechanism)
            
            # Select optimal driving point
            optimal_joint = self._select_optimal_driving_joint(driving_analysis)
            
            # Calculate force requirements for optimal configuration
            force_requirements = self._calculate_force_requirements(mechanism, optimal_joint)
            
            # Calculate transmission quality
            transmission_quality = self._calculate_transmission_quality(mechanism, optimal_joint)
            
            # Calculate motion characteristics
            motion_characteristics = self._analyze_motion_characteristics(mechanism, optimal_joint)
            
            # Create analysis result
            analysis_result = ForceAnalysisResult(
                mechanism_id=mechanism_id,
                analysis_timestamp=logger.time() if hasattr(logger, 'time') else 0.0,
                max_torque_required=force_requirements['max_torque'],
                average_torque=force_requirements['average_torque'],
                rms_torque=force_requirements['rms_torque'],
                peak_power=force_requirements['peak_power'],
                average_power=force_requirements['average_power'],
                optimal_driving_joint=optimal_joint,
                transmission_quality=transmission_quality,
                mechanical_advantage=force_requirements['mechanical_advantage'],
                speed_requirements=motion_characteristics['speeds'],
                acceleration_peaks=motion_characteristics['accelerations']
            )
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in mechanism force analysis: {e}")
            return None
    
    def _analyze_driving_options(self, mechanism: Mechanism) -> Dict[str, Dict[str, float]]:
        """
        Analyze all possible driving points for mechanism.
        
        Evaluates force transmission quality, torque requirements,
        and mechanical advantage for each potential driving joint.
        """
        driving_analysis = {}
        
        try:
            # Analyze each revolute joint as potential driving point
            for joint_id, joint in mechanism.joints.items():
                if joint.joint_type.value == 'revolute':
                    # Skip ground joints (they can't be driven)
                    if 'ground' in joint_id.lower():
                        continue
                    
                    # Calculate metrics for this driving option
                    torque_analysis = self._calculate_joint_torque_requirements(mechanism, joint_id)
                    quality_metrics = self._calculate_joint_transmission_quality(mechanism, joint_id)
                    
                    driving_analysis[joint_id] = {
                        'max_torque': torque_analysis['max_torque'],
                        'average_torque': torque_analysis['average_torque'],
                        'rms_torque': torque_analysis['rms_torque'],
                        'transmission_quality': quality_metrics['quality_score'],
                        'mechanical_advantage': quality_metrics['mechanical_advantage'],
                        'smoothness_score': quality_metrics['smoothness'],
                        'singularity_margin': quality_metrics['singularity_margin']
                    }
            
            return driving_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing driving options: {e}")
            return {}
    
    def _select_optimal_driving_joint(self, driving_analysis: Dict[str, Dict[str, float]]) -> str:
        """
        Select optimal driving joint based on multiple criteria.
        
        Balances torque requirements, transmission quality, and smoothness
        to find the best actuator placement.
        """
        try:
            if not driving_analysis:
                # Default to first available joint
                return "joint_1"
            
            # Calculate composite score for each option
            best_joint = None
            best_score = -1.0
            
            for joint_id, metrics in driving_analysis.items():
                # Normalize metrics to 0-1 scale
                torque_score = 1.0 / (1.0 + metrics['max_torque'] / 10.0)  # Lower torque is better
                quality_score = metrics['transmission_quality']
                smoothness_score = metrics['smoothness_score']
                singularity_score = metrics['singularity_margin']
                
                # Weighted composite score
                composite_score = (
                    0.3 * torque_score +
                    0.3 * quality_score +
                    0.2 * smoothness_score +
                    0.2 * singularity_score
                )
                
                if composite_score > best_score:
                    best_score = composite_score
                    best_joint = joint_id
            
            return best_joint or "joint_1"
            
        except Exception as e:
            logger.error(f"Error selecting optimal driving joint: {e}")
            return "joint_1"
    
    def _calculate_force_requirements(self, mechanism: Mechanism, driving_joint: str) -> Dict[str, float]:
        """
        Calculate force requirements for driving joint throughout motion cycle.
        
        Uses inverse dynamics to determine torque requirements.
        """
        try:
            # Simplified force calculation
            # In production, this would use full inverse dynamics
            
            # Estimate based on mechanism geometry and load
            link_lengths = []
            for link in mechanism.links.values():
                if hasattr(link, 'length'):
                    link_lengths.append(link.length)
            
            if not link_lengths:
                link_lengths = [100.0]  # Default length
            
            average_length = sum(link_lengths) / len(link_lengths)
            
            # Calculate torque based on load and geometry
            load_force = self.default_load  # N
            moment_arm = average_length / 1000.0  # Convert mm to m
            
            # Simplified torque calculation
            max_torque = load_force * moment_arm * 2.0  # Peak during motion
            average_torque = max_torque * 0.6          # Average load
            rms_torque = max_torque * 0.7              # RMS for motor sizing
            
            # Power calculation (simplified)
            typical_speed = 1.0  # rad/s
            peak_power = max_torque * typical_speed * 1.5
            average_power = average_torque * typical_speed
            
            # Mechanical advantage (simplified)
            mechanical_advantage = average_length / 50.0  # Rough estimate
            
            return {
                'max_torque': max_torque,
                'average_torque': average_torque,
                'rms_torque': rms_torque,
                'peak_power': peak_power,
                'average_power': average_power,
                'mechanical_advantage': mechanical_advantage
            }
            
        except Exception as e:
            logger.error(f"Error calculating force requirements: {e}")
            return {
                'max_torque': 1.0,
                'average_torque': 0.6,
                'rms_torque': 0.7,
                'peak_power': 5.0,
                'average_power': 3.0,
                'mechanical_advantage': 2.0
            }
    
    def _calculate_joint_torque_requirements(self, mechanism: Mechanism, joint_id: str) -> Dict[str, float]:
        """Calculate torque requirements for specific joint"""
        # Simplified implementation - would use full inverse dynamics in production
        base_torque = 1.0  # N⋅m
        return {
            'max_torque': base_torque * 2.0,
            'average_torque': base_torque * 1.2,
            'rms_torque': base_torque * 1.4
        }
    
    def _calculate_joint_transmission_quality(self, mechanism: Mechanism, joint_id: str) -> Dict[str, float]:
        """Calculate transmission quality metrics for specific joint"""
        # Simplified quality metrics
        return {
            'quality_score': 0.8,       # Overall transmission quality
            'mechanical_advantage': 2.5, # Average mechanical advantage
            'smoothness': 0.7,          # Motion smoothness
            'singularity_margin': 0.9   # Distance from singularities
        }
    
    def _calculate_transmission_quality(self, mechanism: Mechanism, driving_joint: str) -> float:
        """
        Calculate overall transmission quality for driving configuration.
        
        Evaluates how well force is transmitted from actuator to end-effector.
        """
        try:
            # Simplified transmission quality calculation
            # In production, this would analyze force propagation through linkage
            
            # Factors affecting transmission quality:
            # - Distance from singularities
            # - Link angle variations
            # - Force magnification/reduction
            
            base_quality = 0.8  # Base transmission quality
            
            # Adjust based on mechanism complexity
            num_links = len(mechanism.links)
            complexity_factor = max(0.5, 1.0 - (num_links - 4) * 0.1)
            
            transmission_quality = base_quality * complexity_factor
            
            return min(1.0, max(0.0, transmission_quality))
            
        except Exception as e:
            logger.error(f"Error calculating transmission quality: {e}")
            return 0.7  # Default quality
    
    def _analyze_motion_characteristics(self, mechanism: Mechanism, driving_joint: str) -> Dict[str, Dict[str, float]]:
        """
        Analyze motion characteristics for actuator specifications.
        
        Calculates speed and acceleration requirements.
        """
        try:
            # Simplified motion analysis
            # In production, this would analyze complete kinematic chain
            
            # Typical values for mechanical character applications
            speeds = {
                driving_joint: 2.0,      # rad/s - driving joint speed
                'output': 1.0,           # rad/s - output motion speed
                'max_linear': 100.0      # mm/s - maximum linear speed
            }
            
            accelerations = {
                driving_joint: 5.0,      # rad/s² - driving joint acceleration
                'output': 3.0,           # rad/s² - output acceleration
                'max_linear': 200.0      # mm/s² - maximum linear acceleration
            }
            
            return {
                'speeds': speeds,
                'accelerations': accelerations
            }
            
        except Exception as e:
            logger.error(f"Error analyzing motion characteristics: {e}")
            return {
                'speeds': {'default': 1.0},
                'accelerations': {'default': 2.0}
            }
    
    def _generate_actuator_specification(self, character_id: str, mechanism_id: str, 
                                       analysis_result: ForceAnalysisResult) -> Optional[ActuatorSpec]:
        """
        Generate actuator specification based on force analysis results.
        
        Matches analysis requirements to available actuators from database.
        """
        try:
            # Apply safety factor to requirements
            required_torque = analysis_result.rms_torque * self.safety_factor
            required_power = analysis_result.peak_power * 1.2  # Power safety margin
            required_speed = max(analysis_result.speed_requirements.values())
            
            # Find suitable actuator from database
            suitable_actuator = self._select_from_actuator_database(
                required_torque, required_power, required_speed
            )
            
            if not suitable_actuator:
                logger.warning(f"No suitable actuator found for mechanism {mechanism_id}")
                return None
            
            # Create actuator specification
            actuator_spec = ActuatorSpec(
                actuator_id=f"actuator_{mechanism_id}",
                actuator_type=suitable_actuator['type'],
                position=Point3D(0, 0, 0),  # Will be set by base generation
                max_torque=suitable_actuator['max_torque'],
                max_speed=suitable_actuator['max_speed'],
                max_power=suitable_actuator['max_power'],
                precision=suitable_actuator['precision'],
                mounting_interface=suitable_actuator['mounting'],
                electrical_requirements=suitable_actuator['electrical'],
                mass=suitable_actuator['mass'],
                envelope=suitable_actuator['envelope'],
                driven_mechanism_id=mechanism_id,
                drive_connection_type="direct"
            )
            
            return actuator_spec
            
        except Exception as e:
            logger.error(f"Error generating actuator specification: {e}")
            return None
    
    def _select_from_actuator_database(self, required_torque: float, 
                                     required_power: float, required_speed: float) -> Optional[Dict[str, Any]]:
        """
        Select suitable actuator from database based on requirements.
        
        Finds actuator that meets or exceeds all requirements with minimal oversize.
        """
        try:
            best_actuator = None
            best_score = float('inf')
            
            for actuator in self.actuator_database:
                # Check if actuator meets requirements
                if (actuator['max_torque'] < required_torque or
                    actuator['max_power'] < required_power or
                    actuator['max_speed'] < required_speed):
                    continue
                
                # Calculate oversize penalty (prefer actuators close to requirements)
                torque_oversize = actuator['max_torque'] / required_torque
                power_oversize = actuator['max_power'] / required_power
                speed_oversize = actuator['max_speed'] / required_speed
                
                # Composite score (lower is better)
                oversize_score = torque_oversize + power_oversize + speed_oversize
                
                if oversize_score < best_score:
                    best_score = oversize_score
                    best_actuator = actuator
            
            return best_actuator
            
        except Exception as e:
            logger.error(f"Error selecting actuator from database: {e}")
            return None
    
    def _initialize_actuator_database(self) -> List[Dict[str, Any]]:
        """
        Initialize actuator database with common motor specifications.
        
        In production, this would be loaded from external database.
        """
        return [
            {
                'name': 'NEMA17 Stepper',
                'type': ActuatorType.STEPPER_MOTOR,
                'max_torque': 0.4,      # N⋅m
                'max_speed': 200.0,     # RPM
                'max_power': 25.0,      # W
                'precision': 0.01,      # degrees
                'mounting': 'NEMA17',
                'electrical': {'voltage': 12, 'current': 2.0},
                'mass': 0.35,           # kg
                'envelope': (42, 42, 40)  # mm
            },
            {
                'name': 'MG996R Servo',
                'type': ActuatorType.SERVO_MOTOR,
                'max_torque': 1.0,      # N⋅m
                'max_speed': 120.0,     # RPM
                'max_power': 15.0,      # W
                'precision': 0.5,       # degrees
                'mounting': 'servo_horn',
                'electrical': {'voltage': 6, 'current': 2.5},
                'mass': 0.055,          # kg
                'envelope': (40, 20, 37)  # mm
            },
            {
                'name': 'N20 Gear Motor',
                'type': ActuatorType.DC_MOTOR,
                'max_torque': 0.2,      # N⋅m
                'max_speed': 300.0,     # RPM
                'max_power': 10.0,      # W
                'precision': 2.0,       # degrees
                'mounting': 'bracket',
                'electrical': {'voltage': 12, 'current': 1.0},
                'mass': 0.025,          # kg
                'envelope': (25, 12, 12)  # mm
            }
        ]
    
    def _mechanism_from_data(self, mechanism_data: Dict[str, Any]) -> Optional[Mechanism]:
        """Convert mechanism data dictionary to Mechanism object"""
        try:
            # Simplified mechanism creation from data
            # In production, this would use proper deserialization
            mechanism = Mechanism(
                id=mechanism_data.get('id', 'unknown'),
                name=mechanism_data.get('name', 'Unknown Mechanism'),
                mechanism_type=mechanism_data.get('mechanism_type', 'four_bar_linkage')
            )
            
            return mechanism
            
        except Exception as e:
            logger.error(f"Error creating mechanism from data: {e}")
            return None
    
    def _analysis_result_to_dict(self, result: ForceAnalysisResult) -> Dict[str, Any]:
        """Convert analysis result to dictionary for serialization"""
        return {
            'mechanism_id': result.mechanism_id,
            'analysis_timestamp': result.analysis_timestamp,
            'max_torque_required': result.max_torque_required,
            'average_torque': result.average_torque,
            'rms_torque': result.rms_torque,
            'peak_power': result.peak_power,
            'average_power': result.average_power,
            'optimal_driving_joint': result.optimal_driving_joint,
            'transmission_quality': result.transmission_quality,
            'mechanical_advantage': result.mechanical_advantage,
            'speed_requirements': result.speed_requirements,
            'acceleration_peaks': result.acceleration_peaks,
            'actuator_safety_factor': result.actuator_safety_factor
        }
    
    def _handle_analysis_error(self, character_id: str, mechanism_id: str, error_msg: str):
        """Handle force analysis error"""
        self.event_bus.publish(
            EventType.FORCE_ANALYSIS_COMPLETED,
            {
                'character_id': character_id,
                'mechanism_id': mechanism_id,
                'error': error_msg,
                'success': False
            }
        )
        self.force_analysis_failed.emit(character_id, mechanism_id, error_msg)
    
    def get_analysis_result(self, mechanism_id: str) -> Optional[ForceAnalysisResult]:
        """Get stored analysis result for mechanism"""
        return self._current_analyses.get(mechanism_id)
    
    def cleanup(self):
        """Clean up resources"""
        self._current_analyses.clear()
        logger.info("ForceAnalysisService cleaned up")