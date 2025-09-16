"""
Automataii Core Module

The foundational architecture providing:
- Event-driven communication (EventBus, Event types)
- State management with Redux patterns (StateStore, Actions, Reducers)
- Project file format and management (ProjectManager, AtiiProject) 
- Dependency injection (Container, Injectable)
- Serialization and data persistence
- Manager classes for domain logic

This core provides services to GUI, processing, and other modules.
GUI components should use these services via dependency injection.
"""

# Event system
# Dependency injection
from .container import Container, Injectable, get_global_container, inject
from .events import Event, EventBus, get_global_event_bus
from .events.base import (
    ApplicationStarted,
    ComponentActivated,
    ComponentDeactivated,
    ProjectLoaded,
    ProjectSaved,
)
from .mechanism_manager import MechanismManager

# Models and data structures
from .models import PartInfo
from .models_pydantic import ProjectMetadata
from .models_skeleton import StandardizedJointModel, StandardizedSkeletonModel

# Project management
from .project import AtiiProject, ProjectManager, get_global_project_manager
from .project.file_integration import FileIntegration
from .project.serialization import ProjectSerializer
from .project_data_manager import ProjectDataManager

# Domain managers (business logic)
from .skeleton_manager import SkeletonManager

# State management
from .state import Action, Reducer, StateStore, get_global_store
from .state.base import State
from .state.middleware import Middleware

__all__ = [
    # Event system
    'EventBus', 'Event', 'get_global_event_bus',
    'ProjectLoaded', 'ProjectSaved', 'ApplicationStarted',
    'ComponentActivated', 'ComponentDeactivated',

    # State management
    'StateStore', 'Action', 'Reducer', 'get_global_store',
    'State', 'Middleware',

    # Project management
    'ProjectManager', 'AtiiProject', 'get_global_project_manager',
    'FileIntegration', 'ProjectSerializer',

    # Dependency injection
    'Container', 'Injectable', 'inject', 'get_global_container',

    # Domain managers
    'SkeletonManager', 'MechanismManager', 'ProjectDataManager',

    # Models and data
    'PartInfo', 'SkeletonData', 'JointData', 'ProjectMetadata'
]
