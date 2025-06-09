"""Interfaces package for dependency injection and testing."""

from .ik_manager_interface import IKManagerInterface
from .project_manager_interface import ProjectManagerInterface
from .skeleton_manager_interface import SkeletonManagerInterface

__all__ = [
    'IKManagerInterface',
    'ProjectManagerInterface', 
    'SkeletonManagerInterface'
]