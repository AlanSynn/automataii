"""Service for handling mechanism generation and management."""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid

from PyQt6.QtCore import QObject, pyqtSignal, QPointF
from PyQt6.QtGui import QPainterPath


class MechanismType(Enum):
    """Types of mechanisms available."""
    CAM_FOLLOWER = "cam_follower"
    THREE_BAR_LINKAGE = "3bar_linkage"
    FOUR_BAR_LINKAGE = "4bar_linkage"
    GEAR_PAIR = "gear_pair"


@dataclass
class MechanismParameters:
    """Base class for mechanism parameters."""
    mechanism_type: MechanismType
    target_part: str
    motion_path: QPainterPath


@dataclass
class CamParameters(MechanismParameters):
    """Parameters specific to cam mechanisms."""
    cam_center: QPointF
    follower_type: str = "roller"
    cam_radius: float = 50.0
    
    def __post_init__(self):
        self.mechanism_type = MechanismType.CAM_FOLLOWER


@dataclass
class ThreeBarParameters(MechanismParameters):
    """Parameters for 3-bar linkage."""
    pivot_a: QPointF
    link_lengths: Tuple[float, float] = (100.0, 100.0)
    
    def __post_init__(self):
        self.mechanism_type = MechanismType.THREE_BAR_LINKAGE


@dataclass
class FourBarParameters(MechanismParameters):
    """Parameters for 4-bar linkage."""
    pivot_a: QPointF
    pivot_d: QPointF
    link_lengths: Tuple[float, float, float, float] = (50.0, 100.0, 80.0, 120.0)
    
    def __post_init__(self):
        self.mechanism_type = MechanismType.FOUR_BAR_LINKAGE


@dataclass
class GearParameters(MechanismParameters):
    """Parameters for gear mechanisms."""
    driver_center: QPointF
    driven_center: QPointF
    gear_ratio: float = 1.0
    module: float = 2.0
    
    def __post_init__(self):
        self.mechanism_type = MechanismType.GEAR_PAIR


@dataclass
class Mechanism:
    """Represents a generated mechanism."""
    id: str
    type: MechanismType
    parameters: MechanismParameters
    visual_elements: List[Any] = field(default_factory=list)
    is_visible: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class MechanismService(QObject):
    """Service for managing mechanism generation and lifecycle.
    
    This service extracts mechanism-related logic from MainWindow,
    providing a clean interface for mechanism operations.
    """
    
    # Signals
    mechanism_generated = pyqtSignal(str, Mechanism)  # mechanism_id, mechanism
    mechanism_updated = pyqtSignal(str)  # mechanism_id
    mechanism_deleted = pyqtSignal(str)  # mechanism_id
    generation_failed = pyqtSignal(str, str)  # mechanism_type, error_message
    
    def __init__(self):
        super().__init__()
        self._mechanisms: Dict[str, Mechanism] = {}
        self._generation_strategies: Dict[MechanismType, Any] = {}
        
        logging.info("MechanismService initialized")
    
    def generate_mechanism(self, parameters: MechanismParameters) -> Optional[str]:
        """Generate a new mechanism based on parameters.
        
        Args:
            parameters: Mechanism parameters
            
        Returns:
            Mechanism ID if successful, None otherwise
        """
        # Validate parameters
        validation_result = self._validate_parameters(parameters)
        if not validation_result[0]:
            self.generation_failed.emit(
                parameters.mechanism_type.value,
                validation_result[1]
            )
            return None
        
        # Generate unique ID
        mechanism_id = str(uuid.uuid4())
        
        try:
            # Create mechanism instance
            mechanism = Mechanism(
                id=mechanism_id,
                type=parameters.mechanism_type,
                parameters=parameters
            )
            
            # Generate visual elements using appropriate strategy
            visual_elements = self._generate_visual_elements(parameters)
            mechanism.visual_elements = visual_elements
            
            # Add metadata
            mechanism.metadata = {
                'created_at': logging.Formatter.formatTime(logging.LogRecord(
                    'MechanismService', logging.INFO, '', 1, '', (), None
                )),
                'target_part': parameters.target_part,
                'path_length': parameters.motion_path.length() if parameters.motion_path else 0
            }
            
            # Store mechanism
            self._mechanisms[mechanism_id] = mechanism
            
            # Emit success signal
            self.mechanism_generated.emit(mechanism_id, mechanism)
            
            logging.info(
                f"MechanismService: Generated {parameters.mechanism_type.value} "
                f"mechanism with ID {mechanism_id}"
            )
            return mechanism_id
            
        except Exception as e:
            logging.error(f"MechanismService: Generation failed - {str(e)}")
            self.generation_failed.emit(parameters.mechanism_type.value, str(e))
            return None
    
    def get_mechanism(self, mechanism_id: str) -> Optional[Mechanism]:
        """Get mechanism by ID.
        
        Args:
            mechanism_id: Mechanism ID
            
        Returns:
            Mechanism instance or None
        """
        return self._mechanisms.get(mechanism_id)
    
    def get_all_mechanisms(self) -> Dict[str, Mechanism]:
        """Get all mechanisms.
        
        Returns:
            Dictionary of all mechanisms
        """
        return self._mechanisms.copy()
    
    def update_mechanism(self, mechanism_id: str, updates: Dict[str, Any]) -> bool:
        """Update mechanism properties.
        
        Args:
            mechanism_id: Mechanism ID
            updates: Dictionary of updates
            
        Returns:
            True if updated successfully
        """
        mechanism = self._mechanisms.get(mechanism_id)
        if not mechanism:
            logging.warning(f"MechanismService: Mechanism {mechanism_id} not found")
            return False
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(mechanism, key):
                setattr(mechanism, key, value)
            elif key in mechanism.metadata:
                mechanism.metadata[key] = value
        
        self.mechanism_updated.emit(mechanism_id)
        logging.info(f"MechanismService: Updated mechanism {mechanism_id}")
        return True
    
    def delete_mechanism(self, mechanism_id: str) -> bool:
        """Delete a mechanism.
        
        Args:
            mechanism_id: Mechanism ID
            
        Returns:
            True if deleted successfully
        """
        if mechanism_id not in self._mechanisms:
            logging.warning(f"MechanismService: Mechanism {mechanism_id} not found")
            return False
        
        del self._mechanisms[mechanism_id]
        self.mechanism_deleted.emit(mechanism_id)
        
        logging.info(f"MechanismService: Deleted mechanism {mechanism_id}")
        return True
    
    def show_mechanism(self, mechanism_id: str) -> bool:
        """Show a mechanism.
        
        Args:
            mechanism_id: Mechanism ID
            
        Returns:
            True if shown successfully
        """
        return self.update_mechanism(mechanism_id, {'is_visible': True})
    
    def hide_mechanism(self, mechanism_id: str) -> bool:
        """Hide a mechanism.
        
        Args:
            mechanism_id: Mechanism ID
            
        Returns:
            True if hidden successfully
        """
        return self.update_mechanism(mechanism_id, {'is_visible': False})
    
    def get_mechanisms_for_part(self, part_name: str) -> List[Mechanism]:
        """Get all mechanisms associated with a part.
        
        Args:
            part_name: Name of the part
            
        Returns:
            List of mechanisms for the part
        """
        mechanisms = []
        for mechanism in self._mechanisms.values():
            if mechanism.parameters.target_part == part_name:
                mechanisms.append(mechanism)
        return mechanisms
    
    def clear_all(self) -> None:
        """Clear all mechanisms."""
        mechanism_ids = list(self._mechanisms.keys())
        for mechanism_id in mechanism_ids:
            self.delete_mechanism(mechanism_id)
        
        logging.info("MechanismService: Cleared all mechanisms")
    
    def validate_mechanism_feasibility(self, parameters: MechanismParameters) -> Tuple[bool, str]:
        """Validate if a mechanism is feasible to generate.
        
        Args:
            parameters: Mechanism parameters
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        return self._validate_parameters(parameters)
    
    def _validate_parameters(self, parameters: MechanismParameters) -> Tuple[bool, str]:
        """Validate mechanism parameters.
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check common requirements
        if not parameters.target_part:
            return False, "No target part specified"
        
        if not parameters.motion_path or parameters.motion_path.isEmpty():
            return False, "No motion path defined"
        
        # Type-specific validation
        if isinstance(parameters, CamParameters):
            if not parameters.cam_center:
                return False, "Cam center point not specified"
                
        elif isinstance(parameters, ThreeBarParameters):
            if not parameters.pivot_a:
                return False, "Pivot point A not specified"
                
        elif isinstance(parameters, FourBarParameters):
            if not parameters.pivot_a or not parameters.pivot_d:
                return False, "Both pivot points must be specified"
            
            # Check Grashof condition (simplified)
            lengths = parameters.link_lengths
            if min(lengths) + max(lengths) > sum(lengths) - min(lengths) - max(lengths):
                logging.warning("MechanismService: Four-bar may not satisfy Grashof condition")
                
        elif isinstance(parameters, GearParameters):
            if not parameters.driver_center or not parameters.driven_center:
                return False, "Both gear centers must be specified"
            
            if parameters.gear_ratio <= 0:
                return False, "Invalid gear ratio"
        
        return True, ""
    
    def _generate_visual_elements(self, parameters: MechanismParameters) -> List[Any]:
        """Generate visual elements for a mechanism.
        
        Args:
            parameters: Mechanism parameters
            
        Returns:
            List of visual elements
        """
        # This is a placeholder - actual implementation would create
        # QGraphicsItems or similar visual representations
        visual_elements = []
        
        if isinstance(parameters, CamParameters):
            # Generate cam profile, follower, etc.
            visual_elements.append(f"Cam profile for {parameters.target_part}")
            
        elif isinstance(parameters, ThreeBarParameters):
            # Generate links, joints, etc.
            visual_elements.append(f"3-bar linkage for {parameters.target_part}")
            
        elif isinstance(parameters, FourBarParameters):
            # Generate 4-bar linkage elements
            visual_elements.append(f"4-bar linkage for {parameters.target_part}")
            
        elif isinstance(parameters, GearParameters):
            # Generate gear teeth, centers, etc.
            visual_elements.append(f"Gear pair for {parameters.target_part}")
        
        return visual_elements
    
    def export_mechanism(self, mechanism_id: str) -> Optional[Dict[str, Any]]:
        """Export mechanism data for serialization.
        
        Args:
            mechanism_id: Mechanism ID
            
        Returns:
            Serializable dictionary or None
        """
        mechanism = self._mechanisms.get(mechanism_id)
        if not mechanism:
            return None
        
        # Convert to serializable format
        export_data = {
            'id': mechanism.id,
            'type': mechanism.type.value,
            'parameters': self._serialize_parameters(mechanism.parameters),
            'metadata': mechanism.metadata.copy()
        }
        
        return export_data
    
    def _serialize_parameters(self, parameters: MechanismParameters) -> Dict[str, Any]:
        """Serialize mechanism parameters.
        
        Args:
            parameters: Parameters to serialize
            
        Returns:
            Serializable dictionary
        """
        base_data = {
            'target_part': parameters.target_part,
            'mechanism_type': parameters.mechanism_type.value
        }
        
        if isinstance(parameters, CamParameters):
            base_data.update({
                'cam_center': {'x': parameters.cam_center.x(), 'y': parameters.cam_center.y()},
                'follower_type': parameters.follower_type,
                'cam_radius': parameters.cam_radius
            })
        # Add other parameter types as needed
        
        return base_data