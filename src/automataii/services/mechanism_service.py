"""
Mechanism Service - Event-driven bridge between domain models and UI.

Manages mechanism state, parameter validation, and provides clean separation
between mathematical models and user interface concerns.
"""

import math
from typing import Dict, Any, Optional, Type
from PyQt6.QtCore import QObject, pyqtSignal

from ..domain.mechanisms import (
    BaseMechanism, FourBarLinkage, SliderCrankMechanism, GearTrain, 
    CamFollowerMechanism, SpringSystem
)
from ..core.event_bus import EventBus
from ..core.types import Event


class ParameterChangedEvent(Event):
    """Event emitted when mechanism parameter changes."""
    def __init__(self, parameter_name: str, value: float, mechanism_id: str):
        super().__init__()
        self.parameter_name = parameter_name
        self.value = value
        self.mechanism_id = mechanism_id


class MechanismUpdatedEvent(Event):
    """Event emitted when mechanism state is updated."""
    def __init__(self, state_data: Dict[str, Any], mechanism_id: str):
        super().__init__()
        self.state_data = state_data
        self.mechanism_id = mechanism_id


class MechanismValidationEvent(Event):
    """Event emitted when mechanism validation changes."""
    def __init__(self, is_valid: bool, errors: list, mechanism_id: str):
        super().__init__()
        self.is_valid = is_valid
        self.errors = errors
        self.mechanism_id = mechanism_id


class MechanismService(QObject):
    """
    Service layer for managing mechanism instances and their interactions.
    
    Responsibilities:
    - Create and manage mechanism instances
    - Handle parameter changes from UI
    - Validate constraints and publish validation events
    - Provide clean API for mechanism state access
    - Manage animation and simulation timing
    """
    
    # Qt Signals for direct UI communication
    mechanismUpdated = pyqtSignal(dict, str)  # state_data, mechanism_id
    parameterValidated = pyqtSignal(str, bool, str)  # param_name, is_valid, error_msg
    constraintsValidated = pyqtSignal(bool, list)  # is_valid, error_list
    
    # Registry of available mechanism types
    MECHANISM_TYPES: Dict[str, Type[BaseMechanism]] = {
        'four_bar_linkage': FourBarLinkage,
        'slider_crank': SliderCrankMechanism,
        'gear_train': GearTrain,
        'cam_follower': CamFollowerMechanism,
        'spring_system': SpringSystem
    }
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        Initialize mechanism service.
        
        Args:
            event_bus: Optional event bus for system-wide communication
        """
        super().__init__()
        self.event_bus = event_bus
        
        # Active mechanisms
        self._mechanisms: Dict[str, BaseMechanism] = {}
        self._active_mechanism_id: Optional[str] = None
        
        # Animation state
        self._current_input_angle = 0.0
        self._animation_speed = 2.0  # Multiplier for animation speed (increased for better visibility)
        
        # Connect to event bus if provided
        if self.event_bus:
            self.event_bus.subscribe(ParameterChangedEvent, self._handle_parameter_changed)
    
    def create_mechanism(
        self, 
        mechanism_type: str, 
        mechanism_id: str, 
        parameters: Optional[Dict[str, float]] = None
    ) -> bool:
        """
        Create a new mechanism instance.
        
        Args:
            mechanism_type: Type identifier (e.g., 'four_bar_linkage')
            mechanism_id: Unique identifier for this instance
            parameters: Initial parameters
            
        Returns:
            True if mechanism was created successfully
        """
        if mechanism_type not in self.MECHANISM_TYPES:
            print(f"Unknown mechanism type: {mechanism_type}")
            return False
        
        try:
            mechanism_class = self.MECHANISM_TYPES[mechanism_type]
            mechanism = mechanism_class()  # New rigorous mechanisms don't take parameters in constructor
            
            # Set initial parameters if provided
            if parameters:
                for param_name, value in parameters.items():
                    mechanism.set_parameter(param_name, value)
            
            # Validate initial configuration
            is_valid, errors = mechanism.validate_configuration()
            if not is_valid:
                print(f"Warning: Initial configuration for {mechanism_id} is invalid: {errors}")
            
            self._mechanisms[mechanism_id] = mechanism
            
            # Set as active if no active mechanism
            if self._active_mechanism_id is None:
                self._active_mechanism_id = mechanism_id
            
            # Emit initial state
            self._emit_mechanism_updated(mechanism_id)
            
            return True
            
        except Exception as e:
            print(f"Failed to create mechanism {mechanism_id}: {e}")
            return False
    
    def set_active_mechanism(self, mechanism_id: str) -> bool:
        """
        Set the active mechanism for interaction.
        
        Args:
            mechanism_id: ID of mechanism to activate
            
        Returns:
            True if mechanism exists and was activated
        """
        if mechanism_id not in self._mechanisms:
            return False
        
        self._active_mechanism_id = mechanism_id
        self._emit_mechanism_updated(mechanism_id)
        return True
    
    def get_active_mechanism(self) -> Optional[BaseMechanism]:
        """Get the currently active mechanism."""
        if self._active_mechanism_id:
            return self._mechanisms.get(self._active_mechanism_id)
        return None
    
    def update_parameter(self, parameter_name: str, value: float, mechanism_id: Optional[str] = None) -> bool:
        """
        Update a mechanism parameter with validation.
        
        Args:
            parameter_name: Name of parameter to update
            value: New parameter value
            mechanism_id: Mechanism to update (uses active if None)
            
        Returns:
            True if parameter was updated successfully
        """
        target_id = mechanism_id or self._active_mechanism_id
        if not target_id or target_id not in self._mechanisms:
            return False
        
        mechanism = self._mechanisms[target_id]
        
        try:
            # Validate and set parameter
            success = mechanism.set_parameter(parameter_name, value)
            
            if not success:
                self.parameterValidated.emit(parameter_name, False, "Parameter validation failed")
                return False
            
            # Validate overall constraints
            is_valid, errors = mechanism.validate_configuration()
            
            # Emit validation events
            self.parameterValidated.emit(parameter_name, True, "")
            self.constraintsValidated.emit(is_valid, errors)
            
            # Emit parameter change event to event bus
            if self.event_bus:
                event = ParameterChangedEvent(parameter_name, value, target_id)
                self.event_bus.publish(event)
            
            # Update mechanism state and emit (use degrees for angle)
            mechanism.calculate_kinematics(math.degrees(self._current_input_angle))
            self._emit_mechanism_updated(target_id)
            
            return True
            
        except Exception as e:
            # Parameter validation failed
            self.parameterValidated.emit(parameter_name, False, str(e))
            return False
    
    def update_input_angle(self, angle: float, mechanism_id: Optional[str] = None) -> None:
        """
        Update the input angle for mechanism animation.
        
        Args:
            angle: Input angle in radians
            mechanism_id: Mechanism to update (uses active if None)
        """
        target_id = mechanism_id or self._active_mechanism_id
        if not target_id or target_id not in self._mechanisms:
            return
        
        self._current_input_angle = angle
        mechanism = self._mechanisms[target_id]
        
        try:
            # Convert radians to degrees for new mechanism API
            angle_degrees = math.degrees(angle) if angle < 10 else angle  # Assume degrees if > 10
            mechanism.calculate_kinematics(angle_degrees)
            self._emit_mechanism_updated(target_id)
        except Exception as e:
            print(f"Failed to update mechanism {target_id}: {e}")
    
    def get_mechanism_state(self, mechanism_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get current state data for a mechanism.
        
        Args:
            mechanism_id: Mechanism ID (uses active if None)
            
        Returns:
            State data dictionary or None if mechanism not found
        """
        target_id = mechanism_id or self._active_mechanism_id
        if not target_id or target_id not in self._mechanisms:
            return None
        
        mechanism = self._mechanisms[target_id]
        # Build state data from mechanism's internal state with UI-compatible format
        joints_data = {}
        for name, joint in mechanism.state.joints.items():
            joints_data[name] = {
                'x': joint.position[0],
                'y': joint.position[1],
                'angle': joint.angle,
                'fixed': joint.joint_type == 'fixed'
            }
            
        return {
            'joints': joints_data,
            'links': {name: {
                'length': link.length, 
                'angle': link.angle, 
                'color': link.color,
                'joint_a': link.joint_a,
                'joint_b': link.joint_b
            } for name, link in mechanism.state.links.items()},
            'parameters': mechanism.state.parameters.copy(),
            'is_valid': mechanism.state.is_valid,
            'error_message': mechanism.state.error_message,
            'motion_data': getattr(mechanism.state, 'motion_data', {})
        }
    
    def get_parameter_info(self, mechanism_id: Optional[str] = None) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Get parameter information for UI generation.
        
        Args:
            mechanism_id: Mechanism ID (uses active if None)
            
        Returns:
            Parameter info dictionary or None if mechanism not found
        """
        target_id = mechanism_id or self._active_mechanism_id
        if not target_id or target_id not in self._mechanisms:
            return None
        
        mechanism = self._mechanisms[target_id]
        # Build parameter info from mechanism constraints and current values
        param_info = {}
        for param_name, constraint in mechanism.constraints.items():
            param_info[param_name] = {
                'current_value': mechanism.get_parameter(param_name),
                'min_value': constraint.min_value,
                'max_value': constraint.max_value,
                'step_size': constraint.step_size,
                'parameter_type': constraint.parameter_type.value,
                'preferred_range': constraint.preferred_range
            }
        return param_info
    
    def validate_mechanism(self, mechanism_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform comprehensive validation of mechanism.
        
        Args:
            mechanism_id: Mechanism ID (uses active if None)
            
        Returns:
            Validation results dictionary
        """
        target_id = mechanism_id or self._active_mechanism_id
        if not target_id or target_id not in self._mechanisms:
            return {'valid': False, 'errors': ['Mechanism not found']}
        
        mechanism = self._mechanisms[target_id]
        
        # Use the new validation API
        is_valid, error_list = mechanism.validate_configuration()
        
        results = {
            'valid': is_valid,
            'errors': error_list,
            'warnings': []
        }
        
        # Add educational analysis if available
        educational_info = mechanism.get_educational_content()
        if educational_info and not mechanism.state.is_valid:
            results['warnings'].append('Mechanism configuration may not be optimal')
        
        return results
    
    def get_available_mechanisms(self) -> Dict[str, str]:
        """
        Get list of available mechanism types.
        
        Returns:
            Dictionary mapping type IDs to display names
        """
        return {
            'four_bar_linkage': 'Four-Bar Linkage',
            'slider_crank': 'Slider-Crank Mechanism',
            'gear_train': 'Gear Train',
            'cam_follower': 'Cam-Follower',
            'spring_system': 'Spring System'
        }
    
    def set_animation_speed(self, speed_multiplier: float) -> None:
        """
        Set animation speed multiplier.
        
        Args:
            speed_multiplier: Speed multiplier (1.0 = normal speed)
        """
        self._animation_speed = max(0.1, min(10.0, speed_multiplier))
    
    def get_animation_speed(self) -> float:
        """Get current animation speed multiplier."""
        return self._animation_speed
    
    def remove_mechanism(self, mechanism_id: str) -> bool:
        """
        Remove a mechanism instance.
        
        Args:
            mechanism_id: ID of mechanism to remove
            
        Returns:
            True if mechanism was removed successfully
        """
        if mechanism_id not in self._mechanisms:
            return False
        
        del self._mechanisms[mechanism_id]
        
        # Update active mechanism if needed
        if self._active_mechanism_id == mechanism_id:
            if self._mechanisms:
                self._active_mechanism_id = next(iter(self._mechanisms.keys()))
            else:
                self._active_mechanism_id = None
        
        return True
    
    def get_educational_analysis(self, mechanism_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get educational analysis for a mechanism.
        
        Args:
            mechanism_id: Mechanism ID (uses active if None)
            
        Returns:
            Educational analysis data or None if not available
        """
        target_id = mechanism_id or self._active_mechanism_id
        if not target_id or target_id not in self._mechanisms:
            return None
        
        mechanism = self._mechanisms[target_id]
        
        # All new mechanisms have educational content
        educational_info = mechanism.get_educational_content()
        
        # Add current state information
        educational_info['current_state'] = {
            'mechanism_name': mechanism.name,
            'parameter_count': len(mechanism.state.parameters),
            'is_valid': mechanism.state.is_valid,
            'current_angle': self._current_input_angle,
            'motion_data': getattr(mechanism.state, 'motion_data', {})
        }
        
        return educational_info
    
    def _emit_mechanism_updated(self, mechanism_id: str) -> None:
        """Emit mechanism updated signals."""
        mechanism = self._mechanisms.get(mechanism_id)
        if not mechanism:
            return
        
        # Build state data using the same format as get_mechanism_state
        joints_data = {}
        for name, joint in mechanism.state.joints.items():
            joints_data[name] = {
                'x': joint.position[0],
                'y': joint.position[1],
                'angle': joint.angle,
                'fixed': joint.joint_type == 'fixed'
            }
            
        state_data = {
            'joints': joints_data,
            'links': {name: {
                'length': link.length, 
                'angle': link.angle, 
                'color': link.color,
                'joint_a': link.joint_a,
                'joint_b': link.joint_b
            } for name, link in mechanism.state.links.items()},
            'parameters': mechanism.state.parameters.copy(),
            'is_valid': mechanism.state.is_valid,
            'error_message': mechanism.state.error_message,
            'motion_data': getattr(mechanism.state, 'motion_data', {})
        }
        
        # Emit Qt signal for direct UI updates
        self.mechanismUpdated.emit(state_data, mechanism_id)
        
        # Emit event bus event for system-wide communication
        if self.event_bus:
            event = MechanismUpdatedEvent(state_data, mechanism_id)
            self.event_bus.publish(event)
    
    def _handle_parameter_changed(self, event: ParameterChangedEvent) -> None:
        """Handle parameter changed events from event bus."""
        self.update_parameter(event.parameter_name, event.value, event.mechanism_id)