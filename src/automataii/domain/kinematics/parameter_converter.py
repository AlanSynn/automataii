"""
DEPRECATED: Parameter conversion utilities for UI-Simulator integration.

This module is maintained for backward compatibility only.
All new code should use automataii.domain.common.ParameterConverter.get_instance().

Provides bidirectional conversion between UI parameter dictionaries and 
simulator parameter arrays, ensuring consistent data flow across the system.
"""

import numpy as np
import logging
from typing import Dict, Any, Tuple, List, Optional
from .mechanism import MechanismType
from automataii.domain.common.parameter_converter import (
    ParameterConverter as UnifiedConverter,
    MechanismType as UnifiedMechanismType
)

logger = logging.getLogger(__name__)


class ParameterConverter:
    """
    DEPRECATED: Legacy parameter converter wrapper.
    
    This class provides backward compatibility for existing code.
    New implementations should use:
    
        from automataii.domain.common.parameter_converter import ParameterConverter
        converter = ParameterConverter.get_instance()
    """
    
    # Legacy type string mappings between layers
    TYPE_MAPPINGS = {
        "4_bar_linkage": MechanismType.FOUR_BAR,
        "4bar": MechanismType.FOUR_BAR,
        "cam": MechanismType.CAM,
        "belt": MechanismType.BELT,
        "spring": MechanismType.SPRING,
        "gear": MechanismType.PARAMETRIC,  # Legacy gear type
        "parametric": MechanismType.PARAMETRIC,
    }
    
    # Reverse mapping
    REVERSE_TYPE_MAPPINGS = {v: k for k, v in TYPE_MAPPINGS.items() if k in ["4_bar_linkage", "cam", "belt", "spring", "parametric"]}
    
    def __init__(self):
        """Initialize with deprecation warning."""
        logger.warning(
            "ParameterConverter instantiation is deprecated. "
            "Use automataii.domain.common.ParameterConverter.get_instance() instead."
        )
        self._unified = UnifiedConverter.get_instance()
    
    @classmethod
    def string_to_mechanism_type(cls, type_string: str) -> MechanismType:
        """Convert string type to legacy MechanismType enum."""
        if type_string not in cls.TYPE_MAPPINGS:
            # Try unified converter
            unified_type = UnifiedMechanismType.from_ui_string(type_string)
            if unified_type:
                # Map back to legacy type
                if unified_type == UnifiedMechanismType.FOUR_BAR:
                    return MechanismType.FOUR_BAR
                elif unified_type == UnifiedMechanismType.CAM:
                    return MechanismType.CAM
                elif unified_type == UnifiedMechanismType.BELT:
                    return MechanismType.BELT
                elif unified_type == UnifiedMechanismType.SPRING:
                    return MechanismType.SPRING
                else:
                    return MechanismType.PARAMETRIC
            
            raise ValueError(f"Unknown mechanism type: {type_string}")
        
        return cls.TYPE_MAPPINGS[type_string]
    
    @classmethod
    def mechanism_type_to_string(cls, mech_type: MechanismType) -> str:
        """Convert legacy MechanismType enum to string."""
        return cls.REVERSE_TYPE_MAPPINGS.get(mech_type, mech_type.value)
    
    @classmethod
    def legacy_to_unified_type(cls, legacy_type: MechanismType) -> UnifiedMechanismType:
        """Convert legacy MechanismType to unified MechanismType."""
        mapping = {
            MechanismType.FOUR_BAR: UnifiedMechanismType.FOUR_BAR,
            MechanismType.CAM: UnifiedMechanismType.CAM,
            MechanismType.BELT: UnifiedMechanismType.BELT,
            MechanismType.SPRING: UnifiedMechanismType.SPRING,
            MechanismType.PARAMETRIC: UnifiedMechanismType.GEAR,  # Default parametric to gear
        }
        return mapping.get(legacy_type, UnifiedMechanismType.GEAR)
    
    @classmethod
    def ui_to_simulator_params(cls, mechanism_type: str, ui_params: dict, key_points: dict = None) -> np.ndarray:
        """
        Convert UI parameters to simulator parameter array.
        
        DEPRECATED: Use UnifiedConverter.ui_params_to_simulator() instead.
        
        Args:
            mechanism_type: Type string from UI layer
            ui_params: UI parameter dictionary
            key_points: Optional key points for position data (legacy)
            
        Returns:
            Parameter array for simulator
        """
        logger.debug(f"Legacy parameter conversion for {mechanism_type}")
        
        # Get unified converter
        unified = UnifiedConverter.get_instance()
        
        # Convert type string to unified type
        unified_type = UnifiedMechanismType.from_ui_string(mechanism_type)
        if not unified_type:
            # Fallback to legacy mapping
            try:
                legacy_type = cls.string_to_mechanism_type(mechanism_type)
                unified_type = cls.legacy_to_unified_type(legacy_type)
            except ValueError:
                logger.error(f"Cannot convert mechanism type: {mechanism_type}")
                return np.array([])
        
        # Handle legacy key_points parameter by merging into ui_params
        merged_params = ui_params.copy()
        if key_points:
            # Legacy key_points integration
            if unified_type == UnifiedMechanismType.FOUR_BAR:
                # Extract pivot positions if available
                if 'ground_pivot_1' in key_points:
                    merged_params.setdefault('pivot1_x', key_points['ground_pivot_1'][0])
                    merged_params.setdefault('pivot1_y', key_points['ground_pivot_1'][1])
                if 'ground_pivot_2' in key_points:
                    merged_params.setdefault('pivot2_x', key_points['ground_pivot_2'][0])
                    merged_params.setdefault('pivot2_y', key_points['ground_pivot_2'][1])
            
            elif unified_type == UnifiedMechanismType.CAM:
                # Extract cam center if available
                if 'cam_center' in key_points:
                    merged_params.setdefault('cam_center_x', key_points['cam_center'][0])
                    merged_params.setdefault('cam_center_y', key_points['cam_center'][1])
        
        return unified.ui_params_to_simulator(merged_params, unified_type)
    
    @classmethod
    def simulator_to_ui_params(cls, mechanism_type: str, sim_results: dict) -> dict:
        """
        Convert simulator results to UI parameters.
        
        DEPRECATED: Use UnifiedConverter.simulator_results_to_ui() instead.
        
        Args:
            mechanism_type: Type string
            sim_results: Simulator results dictionary
            
        Returns:
            UI-formatted parameters
        """
        logger.debug(f"Legacy result conversion for {mechanism_type}")
        
        # Get unified converter
        unified = UnifiedConverter.get_instance()
        
        # Convert type string to unified type
        unified_type = UnifiedMechanismType.from_ui_string(mechanism_type)
        if not unified_type:
            try:
                legacy_type = cls.string_to_mechanism_type(mechanism_type)
                unified_type = cls.legacy_to_unified_type(legacy_type)
            except ValueError:
                logger.error(f"Cannot convert mechanism type: {mechanism_type}")
                return sim_results
        
        return unified.simulator_results_to_ui(sim_results, unified_type)
    
    @classmethod
    def validate_ui_params(cls, mechanism_type: str, ui_params: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate UI parameters.
        
        DEPRECATED: Use UnifiedConverter.validate_parameters() instead.
        
        Args:
            mechanism_type: Type string
            ui_params: Parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        unified = UnifiedConverter.get_instance()
        
        # Convert type string to unified type
        unified_type = UnifiedMechanismType.from_ui_string(mechanism_type)
        if not unified_type:
            try:
                legacy_type = cls.string_to_mechanism_type(mechanism_type)
                unified_type = cls.legacy_to_unified_type(legacy_type)
            except ValueError:
                return False, f"Unknown mechanism type: {mechanism_type}"
        
        return unified.validate_parameters(ui_params, unified_type)
    
    @classmethod
    def get_parameter_ranges(cls, mechanism_type: str) -> Dict[str, Tuple[float, float]]:
        """
        Get parameter ranges for a mechanism type.
        
        DEPRECATED: Use UnifiedConverter.get_parameter_info() instead.
        
        Args:
            mechanism_type: Type string
            
        Returns:
            Dictionary of parameter ranges
        """
        unified = UnifiedConverter.get_instance()
        
        # Convert type string to unified type
        unified_type = UnifiedMechanismType.from_ui_string(mechanism_type)
        if not unified_type:
            return {}
        
        # Get parameter ranges from unified converter
        ranges = {}
        param_ranges = unified._parameter_ranges.get(unified_type, {})
        
        for param_name, (min_val, max_val) in param_ranges.items():
            ranges[param_name] = (min_val, max_val)
        
        return ranges
    
    @classmethod 
    def convert_legacy_params(cls, legacy_params: dict, mechanism_type: str) -> dict:
        """
        Convert legacy parameter format to unified format.
        
        Args:
            legacy_params: Legacy parameter dictionary
            mechanism_type: Mechanism type string
            
        Returns:
            Unified parameter format
        """
        # Handle common legacy parameter names
        unified_params = legacy_params.copy()
        
        # Legacy coupler point format conversion
        if 'coupler_point_x' in legacy_params:
            unified_params['p_x'] = legacy_params['coupler_point_x']
        if 'coupler_point_y' in legacy_params:
            unified_params['p_y'] = legacy_params['coupler_point_y']
        
        # Legacy gear radius conversion
        if 'gear1_radius' in legacy_params:
            unified_params['r1'] = legacy_params['gear1_radius']
        if 'gear2_radius' in legacy_params:
            unified_params['r2'] = legacy_params['gear2_radius']
        
        # Legacy cam parameters
        if 'eccentricity' in legacy_params:
            unified_params['rise'] = legacy_params['eccentricity']
        
        return unified_params


# Backward compatibility functions
def ui_to_simulator_params(mechanism_type: str, ui_params: dict, key_points: dict = None) -> np.ndarray:
    """DEPRECATED: Use UnifiedConverter.get_instance().ui_params_to_simulator() instead."""
    logger.warning("Function ui_to_simulator_params is deprecated. Use UnifiedConverter.get_instance().ui_params_to_simulator()")
    return ParameterConverter.ui_to_simulator_params(mechanism_type, ui_params, key_points)


def simulator_to_ui_params(mechanism_type: str, sim_results: dict) -> dict:
    """DEPRECATED: Use UnifiedConverter.get_instance().simulator_results_to_ui() instead."""
    logger.warning("Function simulator_to_ui_params is deprecated. Use UnifiedConverter.get_instance().simulator_results_to_ui()")
    return ParameterConverter.simulator_to_ui_params(mechanism_type, sim_results)


def validate_ui_params(mechanism_type: str, ui_params: dict) -> Tuple[bool, Optional[str]]:
    """DEPRECATED: Use UnifiedConverter.get_instance().validate_parameters() instead."""
    logger.warning("Function validate_ui_params is deprecated. Use UnifiedConverter.get_instance().validate_parameters()")
    return ParameterConverter.validate_ui_params(mechanism_type, ui_params)