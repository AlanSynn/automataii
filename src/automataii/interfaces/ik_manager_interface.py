"""Interface for IK Manager to enable dependency injection."""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from PyQt6.QtCore import pyqtSignal


class IKManagerInterface(ABC):
    """Interface for IK (Inverse Kinematics) Manager.
    
    This interface defines the contract for IK management,
    enabling dependency injection and easier testing.
    """
    
    @property
    @abstractmethod
    def animation_duration(self) -> int:
        """Get animation duration in milliseconds."""
        pass
    
    @property
    @abstractmethod
    def is_animating(self) -> bool:
        """Check if animation is currently playing."""
        pass
    
    @abstractmethod
    def start_animation(self) -> None:
        """Start the animation."""
        pass
    
    @abstractmethod
    def stop_animation(self) -> None:
        """Stop the animation."""
        pass
    
    @abstractmethod
    def reset_animation_state(self) -> None:
        """Reset animation to initial state."""
        pass
    
    @abstractmethod
    def set_animation_duration(self, duration_ms: int) -> None:
        """Set animation duration.
        
        Args:
            duration_ms: Duration in milliseconds
        """
        pass
    
    @abstractmethod
    def update_skeleton_data(self, skeleton_data: Dict[str, Any]) -> None:
        """Update skeleton data for IK calculations.
        
        Args:
            skeleton_data: Dictionary containing skeleton joint information
        """
        pass
    
    @abstractmethod
    def update_motion_paths(self, motion_paths: Dict[str, Any]) -> None:
        """Update motion paths for parts.
        
        Args:
            motion_paths: Dictionary mapping part names to motion paths
        """
        pass
    
    @abstractmethod
    def get_current_joint_positions(self) -> Dict[str, Any]:
        """Get current positions of all joints.
        
        Returns:
            Dictionary mapping joint names to positions
        """
        pass
    
    @abstractmethod
    def set_mechanism_data(self, mechanism_data: Dict[str, Any]) -> None:
        """Set mechanism data for simulation.
        
        Args:
            mechanism_data: Dictionary containing mechanism parameters
        """
        pass
    
    # Signals that implementations should provide
    animation_state_changed: pyqtSignal
    character_visuals_updated: pyqtSignal
    frame_updated: pyqtSignal