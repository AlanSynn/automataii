# Mechanism Interface
# Lines: ~150
# Public API: MechanismInterface, MechanismParameters, SimulationData
# Deps In: All mechanism implementations
# Deps Out: abc, dataclasses, typing, numpy
# Coupling: Low (pure interface)
# Cohesion: Feature (mechanism abstraction)
# Owner: Alan Synn
# Last Updated: 2025-01-20

"""
Base interface for all mechanism types.
Defines the contract that all mechanisms must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


@dataclass
class MechanismParameters:
    """Container for mechanism parameters."""
    mechanism_type: str
    mechanism_id: str
    part_name: str
    params: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'type': self.mechanism_type,
            'id': self.mechanism_id,
            'part_name': self.part_name,
            'params': self.params,
            'metadata': self.metadata or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MechanismParameters':
        """Create from dictionary."""
        return cls(
            mechanism_type=data['type'],
            mechanism_id=data['id'],
            part_name=data['part_name'],
            params=data['params'],
            metadata=data.get('metadata')
        )


@dataclass
class SimulationData:
    """Container for simulation results."""
    frames: int
    time_steps: np.ndarray
    joint_positions: Dict[str, np.ndarray]  # joint_name -> positions array
    link_orientations: Optional[Dict[str, np.ndarray]] = None
    output_path: Optional[np.ndarray] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def get_frame(self, frame_index: int) -> Dict[str, Any]:
        """Get data for a specific frame."""
        frame_data = {
            'time': self.time_steps[frame_index],
            'joints': {}
        }
        
        for joint_name, positions in self.joint_positions.items():
            if len(positions) > frame_index:
                frame_data['joints'][joint_name] = positions[frame_index]
        
        if self.link_orientations:
            frame_data['orientations'] = {}
            for link_name, orientations in self.link_orientations.items():
                if len(orientations) > frame_index:
                    frame_data['orientations'][link_name] = orientations[frame_index]
        
        if self.output_path is not None and len(self.output_path) > frame_index:
            frame_data['output'] = self.output_path[frame_index]
            
        return frame_data


class MechanismInterface(ABC):
    """
    Abstract base class for all mechanism implementations.
    
    This interface ensures all mechanisms provide consistent
    functionality for simulation, validation, and serialization.
    """
    
    @abstractmethod
    def __init__(self, parameters: MechanismParameters):
        """
        Initialize mechanism with parameters.
        
        Args:
            parameters: Mechanism configuration
        """
        pass
    
    @abstractmethod
    def validate_parameters(self) -> Tuple[bool, Optional[str]]:
        """
        Validate current mechanism parameters.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def simulate(self, num_frames: int = 100) -> SimulationData:
        """
        Run mechanism simulation.
        
        Args:
            num_frames: Number of simulation frames
            
        Returns:
            Simulation results
        """
        pass
    
    @abstractmethod
    def update_parameters(self, param_changes: Dict[str, Any]) -> None:
        """
        Update mechanism parameters.
        
        Args:
            param_changes: Dictionary of parameter updates
        """
        pass
    
    @abstractmethod
    def get_key_points(self) -> Dict[str, Tuple[float, float]]:
        """
        Get key points for visualization.
        
        Returns:
            Dictionary of point_name -> (x, y) coordinates
        """
        pass
    
    @abstractmethod
    def get_constraints(self) -> Dict[str, Any]:
        """
        Get mechanism constraints for validation.
        
        Returns:
            Dictionary of constraint definitions
        """
        pass
    
    @abstractmethod
    def calculate_output_motion(self, input_angle: float) -> Dict[str, Any]:
        """
        Calculate output motion for given input.
        
        Args:
            input_angle: Input angle in radians
            
        Returns:
            Output motion data
        """
        pass
    
    @property
    @abstractmethod
    def mechanism_type(self) -> str:
        """Get mechanism type identifier."""
        pass
    
    @property
    @abstractmethod
    def degrees_of_freedom(self) -> int:
        """Get mechanism degrees of freedom."""
        pass