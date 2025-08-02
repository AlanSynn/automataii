"""
Parameter Converter Singleton
Eliminates fragmented parameter conversion logic across the codebase.

This singleton serves as the single source of truth for all parameter conversions
between UI values, internal representations, and physical parameters.

Author: ULTRATHINK Architecture Implementation
Based on: PAPER_IMPL.md unified architecture design
"""

import threading
from typing import Dict, Any, Tuple, Optional
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger(__name__)


class MechanismType(str, Enum):
    """Unified mechanism type enumeration."""
    FOUR_BAR = "4_bar_linkage"
    CAM = "cam"
    GEAR = "gear"
    PLANETARY_GEAR = "planetary_gear"
    BELT = "belt"
    SPRING = "spring"
    
    @classmethod
    def from_ui_string(cls, ui_string: str) -> Optional['MechanismType']:
        """Convert UI display strings to mechanism type."""
        ui_mapping = {
            "4-Bar Linkage": cls.FOUR_BAR,
            "4_bar_linkage": cls.FOUR_BAR,
            "4-bar Coupler": cls.FOUR_BAR,
            "Cam & Follower": cls.CAM,
            "cam": cls.CAM,
            "Cam-Follower": cls.CAM,
            "Cam Follower": cls.CAM,
            "Gears (Simple Pair)": cls.GEAR,
            "gear": cls.GEAR,
            "Simple Gear": cls.GEAR,
            "Gear Contact": cls.GEAR,
            "Planetary Gear": cls.PLANETARY_GEAR,
            "planetary_gear": cls.PLANETARY_GEAR,
            "Belt": cls.BELT,
            "belt": cls.BELT,
            "belt_pulley": cls.BELT,
            "Belt System": cls.BELT,
            "Pulley System": cls.BELT,
            "Spring": cls.SPRING,
            "spring": cls.SPRING,
            "spring_damper": cls.SPRING,
            "Spring System": cls.SPRING,
            "Damper System": cls.SPRING,
        }
        return ui_mapping.get(ui_string)


class ParameterConverter:
    """
    Thread-safe singleton for parameter conversion.
    
    Handles conversions between:
    - Normalized UI values (0-1)
    - Physical parameters (real-world units)
    - Internal simulation parameters
    - UI display parameters
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ParameterConverter, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        logger.info("Initializing ParameterConverter singleton")
        
        # Parameter range definitions for each mechanism type
        self._parameter_ranges = {
            MechanismType.FOUR_BAR: {
                'l1': (10.0, 200.0),  # mm
                'l2': (10.0, 200.0),  # mm
                'l3': (10.0, 200.0),  # mm
                'l4': (10.0, 200.0),  # mm
                'p_x': (-100.0, 100.0),  # mm
                'p_y': (-100.0, 100.0),  # mm
                'theta0': (0.0, 360.0),  # degrees
                'omega': (0.1, 5.0),  # rad/s
            },
            MechanismType.CAM: {
                'base_radius': (10.0, 100.0),  # mm
                'rise': (5.0, 80.0),  # mm
                'offset': (-50.0, 50.0),  # mm
                'cam_center_x': (-100.0, 100.0),  # mm
                'cam_center_y': (-100.0, 100.0),  # mm
                'motion_law': (0, 2),  # discrete: 0=harmonic, 1=cycloidal, 2=polynomial
                'dwell_start': (0.0, 180.0),  # degrees
                'dwell_end': (0.0, 180.0),  # degrees
            },
            MechanismType.BELT: {
                'r1': (10.0, 100.0),  # mm
                'r2': (10.0, 100.0),  # mm
                'center1_x': (-200.0, 200.0),  # mm
                'center1_y': (-200.0, 200.0),  # mm
                'center2_x': (-200.0, 200.0),  # mm
                'center2_y': (-200.0, 200.0),  # mm
                'omega1': (0.1, 10.0),  # rad/s
                'slip_coeff': (0.0, 0.3),  # dimensionless
            },
            MechanismType.SPRING: {
                'k': (10.0, 2000.0),  # N/m
                'c': (0.0, 100.0),  # N·s/m
                'm': (0.1, 10.0),  # kg
                'x1': (-100.0, 100.0),  # mm
                'y1': (-100.0, 100.0),  # mm
                'x2': (-100.0, 100.0),  # mm
                'y2': (-100.0, 100.0),  # mm
                'rest_length': (20.0, 300.0),  # mm
                'initial_velocity': (-50.0, 50.0),  # mm/s
                'external_force': (-100.0, 100.0),  # N
            },
            MechanismType.GEAR: {
                'r1': (10.0, 100.0),  # mm
                'r2': (10.0, 100.0),  # mm
                'center1_x': (-200.0, 200.0),  # mm
                'center1_y': (-200.0, 200.0),  # mm
                'center2_x': (-200.0, 200.0),  # mm
                'center2_y': (-200.0, 200.0),  # mm
                'omega': (0.1, 10.0),  # rad/s
            },
            MechanismType.PLANETARY_GEAR: {
                'r_sun': (10.0, 80.0),  # mm
                'r_planet': (10.0, 60.0),  # mm
                'r_ring': (30.0, 200.0),  # mm
                'num_planets': (2, 6),  # count
                'omega_sun': (0.1, 10.0),  # rad/s
                'omega_carrier': (0.0, 5.0),  # rad/s
            },
        }
    
    @classmethod
    def get_instance(cls) -> 'ParameterConverter':
        """Public access point for the singleton instance."""
        return cls()
    
    def to_physical(self, normalized_value: float, param_name: str, mechanism_type: MechanismType) -> float:
        """
        Convert normalized UI value (0-1) to physical parameter.
        
        Args:
            normalized_value: Value between 0 and 1 from UI slider
            param_name: Name of the parameter (e.g., 'l1', 'base_radius')
            mechanism_type: Type of mechanism
            
        Returns:
            Physical parameter value in appropriate units
        """
        if mechanism_type not in self._parameter_ranges:
            logger.warning(f"Unknown mechanism type: {mechanism_type}")
            return normalized_value
        
        param_ranges = self._parameter_ranges[mechanism_type]
        if param_name not in param_ranges:
            logger.warning(f"Unknown parameter {param_name} for mechanism {mechanism_type}")
            return normalized_value
        
        min_val, max_val = param_ranges[param_name]
        
        # Handle discrete parameters (like motion_law)
        if param_name in ['motion_law', 'num_planets'] and isinstance(min_val, int):
            # Map to discrete integer values
            num_options = max_val - min_val + 1
            discrete_value = int(normalized_value * (num_options - 1))
            return min_val + discrete_value
        
        # Linear interpolation for continuous parameters
        return min_val + normalized_value * (max_val - min_val)
    
    def to_normalized(self, physical_value: float, param_name: str, mechanism_type: MechanismType) -> float:
        """
        Convert physical parameter to normalized UI value (0-1).
        
        Args:
            physical_value: Physical parameter value
            param_name: Name of the parameter
            mechanism_type: Type of mechanism
            
        Returns:
            Normalized value between 0 and 1
        """
        if mechanism_type not in self._parameter_ranges:
            logger.warning(f"Unknown mechanism type: {mechanism_type}")
            return 0.5
        
        param_ranges = self._parameter_ranges[mechanism_type]
        if param_name not in param_ranges:
            logger.warning(f"Unknown parameter {param_name} for mechanism {mechanism_type}")
            return 0.5
        
        min_val, max_val = param_ranges[param_name]
        
        # Handle discrete parameters
        if param_name in ['motion_law', 'num_planets'] and isinstance(min_val, int):
            num_options = max_val - min_val + 1
            discrete_index = int(physical_value) - min_val
            return discrete_index / (num_options - 1)
        
        # Prevent division by zero
        if max_val - min_val == 0:
            return 0.0
        
        # Clamp to valid range
        clamped_value = max(min_val, min(max_val, physical_value))
        return (clamped_value - min_val) / (max_val - min_val)
    
    def ui_params_to_simulator(self, ui_params: Dict[str, Any], mechanism_type: MechanismType) -> np.ndarray:
        """
        Convert UI parameter dictionary to simulator parameter array.
        
        Args:
            ui_params: Dictionary of UI parameters
            mechanism_type: Type of mechanism
            
        Returns:
            Numpy array of parameters for simulator
        """
        if mechanism_type == MechanismType.FOUR_BAR:
            return np.array([
                ui_params.get('l1', 100.0),
                ui_params.get('l2', 40.0),
                ui_params.get('l3', 120.0),
                ui_params.get('l4', 80.0),
                ui_params.get('p_x', 60.0),
                ui_params.get('p_y', 0.0),
                ui_params.get('theta0', 0.0),
                ui_params.get('omega', 1.0),
            ])
        
        elif mechanism_type == MechanismType.CAM:
            return np.array([
                ui_params.get('base_radius', 30.0),
                ui_params.get('rise', 20.0),
                ui_params.get('offset', 0.0),
                ui_params.get('cam_center_x', 0.0),
                ui_params.get('cam_center_y', 0.0),
                ui_params.get('motion_law', 0),
                ui_params.get('dwell_start', 0.0),
                ui_params.get('dwell_end', 0.0),
            ])
        
        elif mechanism_type == MechanismType.BELT:
            return np.array([
                ui_params.get('r1', 40.0),
                ui_params.get('r2', 40.0),
                ui_params.get('center1_x', 0.0),
                ui_params.get('center1_y', 0.0),
                ui_params.get('center2_x', 120.0),
                ui_params.get('center2_y', 0.0),
                ui_params.get('omega1', 1.0),
                ui_params.get('slip_coeff', 0.05),
            ])
        
        elif mechanism_type == MechanismType.SPRING:
            return np.array([
                ui_params.get('k', 100.0),
                ui_params.get('c', 5.0),
                ui_params.get('m', 1.0),
                ui_params.get('x1', 0.0),
                ui_params.get('y1', 0.0),
                ui_params.get('x2', 0.0),
                ui_params.get('y2', 100.0),
                ui_params.get('rest_length', 80.0),
                ui_params.get('initial_velocity', 0.0),
                ui_params.get('external_force', 0.0),
            ])
        
        elif mechanism_type == MechanismType.GEAR:
            return np.array([
                ui_params.get('r1', 30.0),
                ui_params.get('r2', 50.0),
                ui_params.get('center1_x', 0.0),
                ui_params.get('center1_y', 0.0),
                ui_params.get('center2_x', 80.0),
                ui_params.get('center2_y', 0.0),
                ui_params.get('omega', 1.0),
            ])
        
        elif mechanism_type == MechanismType.PLANETARY_GEAR:
            return np.array([
                ui_params.get('r_sun', 20.0),
                ui_params.get('r_planet', 30.0),
                ui_params.get('r_ring', 80.0),
                ui_params.get('num_planets', 3),
                ui_params.get('omega_sun', 1.0),
                ui_params.get('omega_carrier', 0.0),
            ])
        
        else:
            logger.error(f"Unknown mechanism type: {mechanism_type}")
            return np.array([])
    
    def simulator_results_to_ui(self, sim_results: Dict[str, Any], mechanism_type: MechanismType) -> Dict[str, Any]:
        """
        Convert simulator results to UI-friendly format.
        
        Args:
            sim_results: Raw simulator output
            mechanism_type: Type of mechanism
            
        Returns:
            UI-formatted results dictionary
        """
        ui_results = {
            'mechanism_type': mechanism_type.value,
            'success': sim_results.get('success', False),
            'error': sim_results.get('error'),
        }
        
        # Add mechanism-specific UI formatting
        if mechanism_type == MechanismType.FOUR_BAR:
            if 'coupler_path' in sim_results:
                ui_results['path_coordinates'] = sim_results['coupler_path']
            if 'joint_positions' in sim_results:
                ui_results['pivots'] = {
                    'A': sim_results['joint_positions'].get('p1_positions', [[0, 0]])[0],
                    'B': sim_results['joint_positions'].get('p2_positions', [[0, 0]])[0],
                    'C': sim_results['joint_positions'].get('p3_positions', [[0, 0]])[0],
                    'D': sim_results['joint_positions'].get('p4_positions', [[0, 0]])[0],
                }
        
        elif mechanism_type == MechanismType.CAM:
            if 'follower_path' in sim_results:
                ui_results['path_coordinates'] = sim_results['follower_path']
            if 'cam_profile' in sim_results:
                ui_results['cam_profile'] = sim_results['cam_profile']
        
        elif mechanism_type == MechanismType.BELT:
            if 'belt_path' in sim_results:
                ui_results['belt_path'] = sim_results['belt_path']
            if 'pulley_positions' in sim_results:
                ui_results['pulleys'] = sim_results['pulley_positions']
        
        elif mechanism_type == MechanismType.SPRING:
            if 'mass_path' in sim_results:
                ui_results['path_coordinates'] = sim_results['mass_path']
            if 'spring_states' in sim_results:
                ui_results['spring_compression'] = sim_results['spring_states']
        
        return ui_results
    
    def get_parameter_info(self, param_name: str, mechanism_type: MechanismType) -> Dict[str, Any]:
        """
        Get comprehensive information about a parameter.
        
        Args:
            param_name: Name of the parameter
            mechanism_type: Type of mechanism
            
        Returns:
            Dictionary with parameter metadata
        """
        if mechanism_type not in self._parameter_ranges:
            return {}
        
        param_ranges = self._parameter_ranges.get(mechanism_type, {})
        if param_name not in param_ranges:
            return {}
        
        min_val, max_val = param_ranges[param_name]
        
        # Parameter metadata
        param_info = {
            'name': param_name,
            'min': min_val,
            'max': max_val,
            'type': 'discrete' if param_name in ['motion_law', 'num_planets'] else 'continuous',
        }
        
        # Add human-readable labels and units
        labels = {
            'l1': ('Link 1 Length', 'mm'),
            'l2': ('Link 2 Length', 'mm'),
            'l3': ('Link 3 Length', 'mm'),
            'l4': ('Link 4 Length', 'mm'),
            'p_x': ('Coupler Point X', 'mm'),
            'p_y': ('Coupler Point Y', 'mm'),
            'theta0': ('Initial Angle', '°'),
            'omega': ('Angular Velocity', 'rad/s'),
            'base_radius': ('Base Radius', 'mm'),
            'rise': ('Maximum Rise', 'mm'),
            'offset': ('Follower Offset', 'mm'),
            'motion_law': ('Motion Profile', ''),
            'k': ('Spring Constant', 'N/m'),
            'c': ('Damping Coefficient', 'N·s/m'),
            'm': ('Mass', 'kg'),
            'rest_length': ('Rest Length', 'mm'),
            'r1': ('Radius 1', 'mm'),
            'r2': ('Radius 2', 'mm'),
            'slip_coeff': ('Slip Coefficient', ''),
            'r_sun': ('Sun Gear Radius', 'mm'),
            'r_planet': ('Planet Gear Radius', 'mm'),
            'r_ring': ('Ring Gear Radius', 'mm'),
            'num_planets': ('Number of Planets', ''),
        }
        
        if param_name in labels:
            param_info['label'], param_info['unit'] = labels[param_name]
        else:
            param_info['label'] = param_name.replace('_', ' ').title()
            param_info['unit'] = ''
        
        return param_info
    
    def validate_parameters(self, params: Dict[str, Any], mechanism_type: MechanismType) -> Tuple[bool, Optional[str]]:
        """
        Validate mechanism parameters.
        
        Args:
            params: Parameter dictionary to validate
            mechanism_type: Type of mechanism
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if mechanism_type not in self._parameter_ranges:
            return False, f"Unknown mechanism type: {mechanism_type}"
        
        param_ranges = self._parameter_ranges[mechanism_type]
        
        # Check required parameters
        for param_name, (min_val, max_val) in param_ranges.items():
            if param_name not in params:
                continue  # Skip optional parameters
            
            value = params[param_name]
            
            # Type check
            if param_name in ['motion_law', 'num_planets']:
                if not isinstance(value, (int, np.integer)):
                    return False, f"{param_name} must be an integer"
            else:
                if not isinstance(value, (int, float, np.number)):
                    return False, f"{param_name} must be a number"
            
            # Range check
            if value < min_val or value > max_val:
                return False, f"{param_name} must be between {min_val} and {max_val}"
        
        # Mechanism-specific validation
        if mechanism_type == MechanismType.FOUR_BAR:
            # Grashof condition check
            lengths = [params.get(f'l{i}', 0) for i in range(1, 5)]
            if any(l <= 0 for l in lengths):
                return False, "All link lengths must be positive"
            
            # Check if mechanism can be assembled
            sorted_lengths = sorted(lengths)
            s, p, q, l = sorted_lengths
            if s + l > p + q + 0.1:  # Small tolerance for numerical errors
                return False, "Mechanism cannot be assembled (Grashof condition violated)"
        
        elif mechanism_type == MechanismType.PLANETARY_GEAR:
            r_sun = params.get('r_sun', 0)
            r_planet = params.get('r_planet', 0)
            r_ring = params.get('r_ring', 0)
            
            # Ring gear must contain sun and planets
            if r_ring <= r_sun + 2 * r_planet:
                return False, "Ring gear too small to contain sun and planet gears"
        
        return True, None