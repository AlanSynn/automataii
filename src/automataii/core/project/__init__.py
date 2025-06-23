"""
Project Management Module

Handles .atii project files, serialization, and project lifecycle management.
"""

from .file_integration import FileIntegration
from .project_format import AtiiProject
from .project_manager import ProjectManager
from .serialization import ProjectSerializer, SerializationFormat

# Global project manager instance
_global_project_manager = None

def get_global_project_manager() -> ProjectManager:
    """Get the global project manager instance."""
    global _global_project_manager
    if _global_project_manager is None:
        _global_project_manager = ProjectManager()
    return _global_project_manager

def set_global_project_manager(manager: ProjectManager) -> None:
    """Set the global project manager instance."""
    global _global_project_manager
    _global_project_manager = manager

__all__ = [
    'ProjectManager',
    'AtiiProject',
    'ProjectSerializer', 'SerializationFormat',
    'FileIntegration',
    'get_global_project_manager', 'set_global_project_manager'
]
