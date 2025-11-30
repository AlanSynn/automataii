"""
Automataii Core Infrastructure Module (Legacy)

DEPRECATION NOTICE:
This module is being phased out. Please use the new architectural layers:

- Infrastructure: automataii.infrastructure (events, state, container, telemetry)
- Application: automataii.application (managers, services)
- Domain: automataii.domain (skeleton, project)
- Presentation: automataii.presentation.qt (models, views)

For new code, import from the appropriate layer:
    from automataii.infrastructure.events import EventBus
    from automataii.application.managers import SkeletonManager
    from automataii.domain.skeleton import StandardizedJointModel
    from automataii.presentation.qt.models import PartInfo
"""

# Re-export from new locations for remaining internal use

# Infrastructure layer
from automataii.infrastructure.container import Container, Injectable, get_global_container, inject
from automataii.infrastructure.events import (
    ApplicationStarted,
    ComponentActivated,
    ComponentDeactivated,
    Event,
    EventBus,
    ProjectLoaded,
    ProjectSaved,
    get_global_event_bus,
)
from automataii.infrastructure.state import (
    Action,
    Middleware,
    Reducer,
    State,
    StateStore,
    get_global_store,
)

# Application layer
from automataii.application.managers import (
    MechanismManager,
    ProjectDataManager,
    SkeletonManager,
)

# Domain layer
from automataii.domain.project import ProjectMetadata
from automataii.domain.skeleton import StandardizedJointModel, StandardizedSkeletonModel

# Presentation layer
from automataii.presentation.qt.models import PartInfo

# Project management (still in core/)
from automataii.core.project import AtiiProject, ProjectManager, get_global_project_manager
from automataii.core.project.file_integration import FileIntegration
from automataii.core.project.serialization import ProjectSerializer

__all__ = [
    # Event system
    "EventBus",
    "Event",
    "get_global_event_bus",
    "ProjectLoaded",
    "ProjectSaved",
    "ApplicationStarted",
    "ComponentActivated",
    "ComponentDeactivated",
    # State management
    "StateStore",
    "Action",
    "Reducer",
    "get_global_store",
    "State",
    "Middleware",
    # Project management
    "ProjectManager",
    "AtiiProject",
    "get_global_project_manager",
    "FileIntegration",
    "ProjectSerializer",
    # Dependency injection
    "Container",
    "Injectable",
    "inject",
    "get_global_container",
    # Managers (Qt-based)
    "SkeletonManager",
    "MechanismManager",
    "ProjectDataManager",
    # Models
    "PartInfo",
    "ProjectMetadata",
    "StandardizedJointModel",
    "StandardizedSkeletonModel",
]
