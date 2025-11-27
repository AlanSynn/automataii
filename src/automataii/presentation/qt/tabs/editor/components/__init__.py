"""
EditorTab extracted components.

This package contains modules extracted from the EditorTab god class
using the LLM-native refactoring approach.

Extracted Modules:
- PathQueryService: Pure query functions for motion path state
- ViewControls: Zoom, pan, reset operations
- SimulationController: Play/stop/reset animation control
- MotionPathManager: Path drawing, smoothing, and manipulation
- SkeletonIKHandler: Skeleton updates, IK, and joint management
- PartsDataManager: Parts list and data management
"""
from automataii.presentation.qt.tabs.editor.components.motion_path_manager import (
    MotionPathManager,
)
from automataii.presentation.qt.tabs.editor.components.parts_data_manager import (
    PartsDataManager,
)
from automataii.presentation.qt.tabs.editor.components.path_query_service import (
    PathQueryService,
)
from automataii.presentation.qt.tabs.editor.components.simulation_controller import (
    SimulationController,
)
from automataii.presentation.qt.tabs.editor.components.skeleton_ik_handler import (
    SkeletonIKHandler,
)
from automataii.presentation.qt.tabs.editor.components.view_controls import ViewControls

__all__ = [
    "MotionPathManager",
    "PartsDataManager",
    "PathQueryService",
    "SimulationController",
    "SkeletonIKHandler",
    "ViewControls",
]
