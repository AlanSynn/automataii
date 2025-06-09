"""Interface for Project Manager to enable dependency injection."""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
from pathlib import Path


class ProjectManagerInterface(ABC):
    """Interface for Project Data Manager.
    
    This interface defines the contract for project data management,
    enabling dependency injection and easier testing.
    """
    
    @abstractmethod
    def create_new_project(self, project_name: str) -> bool:
        """Create a new project.
        
        Args:
            project_name: Name of the project
            
        Returns:
            True if created successfully
        """
        pass
    
    @abstractmethod
    def open_project(self, project_path: Path) -> bool:
        """Open an existing project.
        
        Args:
            project_path: Path to the project file
            
        Returns:
            True if opened successfully
        """
        pass
    
    @abstractmethod
    def save_project(self, project_path: Optional[Path] = None) -> bool:
        """Save the current project.
        
        Args:
            project_path: Optional path to save to
            
        Returns:
            True if saved successfully
        """
        pass
    
    @abstractmethod
    def close_project(self) -> None:
        """Close the current project."""
        pass
    
    @property
    @abstractmethod
    def is_project_open(self) -> bool:
        """Check if a project is currently open."""
        pass
    
    @property
    @abstractmethod
    def current_project_path(self) -> Optional[Path]:
        """Get the current project file path."""
        pass
    
    @abstractmethod
    def get_project_data(self) -> Dict[str, Any]:
        """Get all project data.
        
        Returns:
            Dictionary containing all project data
        """
        pass
    
    @abstractmethod
    def update_project_data(self, data: Dict[str, Any]) -> None:
        """Update project data.
        
        Args:
            data: Dictionary of data to update
        """
        pass
    
    @abstractmethod
    def get_current_parts_data(self) -> Optional[Dict[str, Any]]:
        """Get current parts data.
        
        Returns:
            Dictionary of parts data or None
        """
        pass
    
    @abstractmethod
    def set_current_parts_data(self, parts_data: Dict[str, Any]) -> None:
        """Set current parts data.
        
        Args:
            parts_data: Dictionary of parts data
        """
        pass
    
    @abstractmethod
    def get_skeleton_data(self) -> Optional[Dict[str, Any]]:
        """Get skeleton data.
        
        Returns:
            Dictionary of skeleton data or None
        """
        pass
    
    @abstractmethod
    def set_skeleton_data(self, skeleton_data: Dict[str, Any]) -> None:
        """Set skeleton data.
        
        Args:
            skeleton_data: Dictionary of skeleton data
        """
        pass
    
    @abstractmethod
    def get_motion_paths(self) -> Dict[str, Any]:
        """Get motion paths data.
        
        Returns:
            Dictionary of motion paths
        """
        pass
    
    @abstractmethod
    def set_motion_paths(self, motion_paths: Dict[str, Any]) -> None:
        """Set motion paths data.
        
        Args:
            motion_paths: Dictionary of motion paths
        """
        pass
    
    @abstractmethod
    def get_mechanisms(self) -> List[Dict[str, Any]]:
        """Get all mechanisms data.
        
        Returns:
            List of mechanism dictionaries
        """
        pass
    
    @abstractmethod
    def add_mechanism(self, mechanism_data: Dict[str, Any]) -> str:
        """Add a new mechanism.
        
        Args:
            mechanism_data: Mechanism data dictionary
            
        Returns:
            Mechanism ID
        """
        pass
    
    @abstractmethod
    def remove_mechanism(self, mechanism_id: str) -> bool:
        """Remove a mechanism.
        
        Args:
            mechanism_id: ID of the mechanism to remove
            
        Returns:
            True if removed successfully
        """
        pass
    
    @abstractmethod
    def get_project_metadata(self) -> Dict[str, Any]:
        """Get project metadata.
        
        Returns:
            Dictionary of metadata
        """
        pass