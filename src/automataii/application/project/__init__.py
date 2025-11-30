"""
Project State Management Module.

Central state store implementing Single Source of Truth (SSOT) pattern.
All tabs subscribe to state changes rather than holding copies.

Architecture: Application Layer (Hexagonal)
Pattern: Observer + Command (for undo/redo) + Repository (for persistence)

Usage:
    from automataii.application.project import (
        ProjectStateManager,
        ProjectState,
        ProjectSerializer,
        PartData,
        SkeletonData,
        PathData,
        MechanismData,
    )

    # Create state manager
    state_manager = ProjectStateManager()

    # Subscribe to changes
    state_manager.parts_changed.connect(my_tab.on_parts_changed)
    state_manager.paths_changed.connect(my_tab.on_paths_changed)

    # Mutate state
    state_manager.load_parts({"head": PartData(...)})
    state_manager.set_path(PathData(part_name="head", points=[...]))

    # Save/Load
    serializer = ProjectSerializer()
    serializer.save(state_manager.state, Path("project.automataii"))
"""

# Core data models
from .models import (
    BoneData,
    JointData,
    MechanismData,
    PartData,
    PathData,
    Point,
    ProjectMetadata,
    ProjectState,
    SkeletonData,
    Transform,
)

# Serialization
from .serializer import (
    AutoSaveManager,
    LoadResult,
    ProjectSerializer,
    SaveResult,
)

# State management
from .state_manager import MutationEntry, ProjectStateManager

__all__ = [
    # Primitive types
    "Point",
    "Transform",
    # Core data models
    "PartData",
    "JointData",
    "BoneData",
    "SkeletonData",
    "PathData",
    "MechanismData",
    "ProjectMetadata",
    "ProjectState",
    # State management
    "ProjectStateManager",
    "MutationEntry",
    # Serialization
    "ProjectSerializer",
    "SaveResult",
    "LoadResult",
    "AutoSaveManager",
]
