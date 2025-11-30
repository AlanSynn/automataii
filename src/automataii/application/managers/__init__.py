"""
Application Layer Managers.

Orchestrators that coordinate between domain logic and infrastructure.
These managers use Qt signals for the Observer pattern.

Managers:
- SkeletonManager: Skeleton data lifecycle and transformations
- MechanismManager: Mechanism generation and coordination
- ProjectDataManager: Project data orchestration
- BlueprintExportManager: Blueprint export coordination

Usage:
    from automataii.application.managers import SkeletonManager
"""

from automataii.application.managers.blueprint_manager import BlueprintExportManager
from automataii.application.managers.mechanism_manager import MechanismManager
from automataii.application.managers.project_data_manager import ProjectDataManager
from automataii.application.managers.skeleton_manager import SkeletonManager

__all__ = [
    "SkeletonManager",
    "MechanismManager",
    "ProjectDataManager",
    "BlueprintExportManager",
]
