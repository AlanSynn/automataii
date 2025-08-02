"""
Core Event Definitions for Automataii Application

Defines all events used throughout the application for decoupled communication.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

from .base import Event


@dataclass(frozen=True)
class MotionPathEvent(Event):
    """Base class for motion path related events."""
    part_name: str = ""


@dataclass(frozen=True)
class MotionPathStartedEvent(MotionPathEvent):
    """Emitted when user starts drawing a motion path."""
    target_item: Any = None


@dataclass(frozen=True)
class MotionPathPointAddedEvent(MotionPathEvent):
    """Emitted when a point is added to the motion path."""
    point: QPointF = None
    point_index: int = 0


@dataclass(frozen=True)
class MotionPathCompletedEvent(MotionPathEvent):
    """Emitted when motion path drawing is completed."""
    path_points: List[QPointF] = None
    path_data: QPainterPath = None


@dataclass(frozen=True)
class MotionPathCancelledEvent(MotionPathEvent):
    """Emitted when motion path drawing is cancelled."""
    pass


@dataclass(frozen=True)
class MotionPathClearedEvent(MotionPathEvent):
    """Emitted when motion path is cleared for a part."""
    pass


@dataclass(frozen=True)
class AnimationEvent(Event):
    """Base class for animation related events."""
    pass


@dataclass(frozen=True)
class AnimationStartedEvent(AnimationEvent):
    """Emitted when animation starts."""
    duration_ms: int = 5000


@dataclass(frozen=True)
class AnimationStoppedEvent(AnimationEvent):
    """Emitted when animation stops."""
    pass


@dataclass(frozen=True)
class AnimationResetEvent(AnimationEvent):
    """Emitted when animation is reset."""
    pass


@dataclass(frozen=True)
class AnimationTickEvent(AnimationEvent):
    """Emitted on each animation frame."""
    progress: float = 0.0  # 0.0 to 1.0
    timestamp: float = 0.0


@dataclass(frozen=True)
class PoseUpdatedEvent(Event):
    """Emitted when skeleton pose is updated from IK solving."""
    ik_results: Dict[str, Any] = None
    targets: Dict[str, QPointF] = None


@dataclass(frozen=True)
class MechanismEvent(Event):
    """Base class for mechanism related events."""
    mechanism_id: str = ""


@dataclass(frozen=True)
class MechanismRecommendationRequestedEvent(MechanismEvent):
    """Emitted when user requests mechanism recommendations."""
    part_name: str = ""
    target_path: QPainterPath = None
    mechanism_id: str = ""  # Will be generated


@dataclass(frozen=True)
class MechanismSelectedEvent(MechanismEvent):
    """Emitted when user selects a mechanism from recommendations."""
    mechanism_data: Dict[str, Any] = None
    part_name: str = ""


@dataclass(frozen=True)
class MechanismAddedEvent(MechanismEvent):
    """Emitted when a mechanism is added to the system."""
    layer_data: Dict[str, Any] = None
    part_name: str = ""


@dataclass(frozen=True)
class MechanismRemovedEvent(MechanismEvent):
    """Emitted when a mechanism is removed."""
    part_name: str = ""


@dataclass(frozen=True)
class MechanismParameterChangedEvent(MechanismEvent):
    """Emitted when mechanism parameters are changed."""
    parameter_name: str = ""
    old_value: Any = None
    new_value: Any = None


@dataclass(frozen=True)
class SkeletonEvent(Event):
    """Base class for skeleton related events."""
    pass


@dataclass(frozen=True)
class SkeletonLoadedEvent(SkeletonEvent):
    """Emitted when skeleton data is loaded."""
    skeleton_data: Dict[str, Any] = None
    source_format: str = ""


@dataclass(frozen=True)
class SkeletonUpdatedEvent(SkeletonEvent):
    """Emitted when skeleton data is updated."""
    skeleton_data: Dict[str, Any] = None


@dataclass(frozen=True)
class ProjectEvent(Event):
    """Base class for project related events."""
    pass


@dataclass(frozen=True)
class ProjectLoadedEvent(ProjectEvent):
    """Emitted when project is loaded."""
    project_path: str = ""
    parts_data: Dict[str, Any] = None
    skeleton_data: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ProjectSavedEvent(ProjectEvent):
    """Emitted when project is saved."""
    project_path: str = ""


@dataclass(frozen=True)
class ProjectClearedEvent(ProjectEvent):
    """Emitted when project is cleared."""
    pass


@dataclass(frozen=True)
class ProjectCreated(ProjectEvent):
    """Emitted when a new project is created."""
    aggregate_id: str = ""
    project_name: str = ""
    template_used: str = "default"


@dataclass(frozen=True)
class ProjectClosed(ProjectEvent):
    """Emitted when a project is closed."""
    aggregate_id: str = ""
    project_name: str = ""


@dataclass(frozen=True)
class ProjectModified(ProjectEvent):
    """Emitted when project data is modified."""
    aggregate_id: str = ""
    modification_type: str = "content"
    details: Dict[str, Any] = None


@dataclass(frozen=True)
class AutoSaveTriggered(ProjectEvent):
    """Emitted when auto-save is triggered."""
    aggregate_id: str = ""
    backup_path: Optional[str] = None


@dataclass(frozen=True)
class UIEvent(Event):
    """Base class for UI related events."""
    pass


@dataclass(frozen=True)
class TabActivatedEvent(UIEvent):
    """Emitted when a tab is activated."""
    tab_name: str = ""
    tab_index: int = 0


@dataclass(frozen=True)
class TabDeactivatedEvent(UIEvent):
    """Emitted when a tab is deactivated."""
    tab_name: str = ""
    tab_index: int = 0


@dataclass(frozen=True)
class ModeChangedEvent(UIEvent):
    """Emitted when interaction mode changes."""
    old_mode: str = ""
    new_mode: str = ""
    context: str = ""  # e.g. "editor", "mechanism_design"


@dataclass(frozen=True)
class ErrorEvent(Event):
    """Emitted when errors occur."""
    error_message: str = ""
    error_type: str = ""
    source_component: str = ""
    exception: Optional[Exception] = None


@dataclass(frozen=True)
class WarningEvent(Event):
    """Emitted for warning messages."""
    warning_message: str = ""
    source_component: str = ""


@dataclass(frozen=True)
class InfoEvent(Event):
    """Emitted for informational messages."""
    info_message: str = ""
    source_component: str = ""