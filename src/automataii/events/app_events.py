"""Application-specific events."""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

from .event_bus import Event


@dataclass
class PartSelectedEvent(Event):
    """Event fired when a part is selected."""
    part_name: Optional[str]
    previous_part: Optional[str] = None
    source: str = "unknown"
    
    @property
    def event_type(self) -> str:
        return "part_selected"


@dataclass
class PathDrawingStartedEvent(Event):
    """Event fired when path drawing starts."""
    part_name: str
    start_point: QPointF
    source: str = "editor"
    
    @property
    def event_type(self) -> str:
        return "path_drawing_started"


@dataclass
class PathDrawingCompletedEvent(Event):
    """Event fired when path drawing is completed."""
    part_name: str
    path: QPainterPath
    point_count: int
    source: str = "editor"
    
    @property
    def event_type(self) -> str:
        return "path_drawing_completed"


@dataclass
class AnimationStateChangedEvent(Event):
    """Event fired when animation state changes."""
    state: str  # "playing", "paused", "stopped", "reset"
    previous_state: str
    source: str = "animation_service"
    
    @property
    def event_type(self) -> str:
        return "animation_state_changed"


@dataclass
class MechanismGeneratedEvent(Event):
    """Event fired when a mechanism is generated."""
    mechanism_id: str
    mechanism_type: str
    target_part: str
    parameters: Dict[str, Any]
    source: str = "mechanism_service"
    
    @property
    def event_type(self) -> str:
        return "mechanism_generated"


@dataclass
class ProjectLoadedEvent(Event):
    """Event fired when a project is loaded."""
    project_path: str
    project_data: Dict[str, Any]
    source: str = "project_manager"
    
    @property
    def event_type(self) -> str:
        return "project_loaded"


@dataclass
class ProjectSavedEvent(Event):
    """Event fired when a project is saved."""
    project_path: str
    success: bool
    source: str = "project_manager"
    
    @property
    def event_type(self) -> str:
        return "project_saved"


@dataclass
class SkeletonUpdatedEvent(Event):
    """Event fired when skeleton data is updated."""
    skeleton_data: Dict[str, Any]
    has_skeleton: bool
    source: str = "skeleton_manager"
    
    @property
    def event_type(self) -> str:
        return "skeleton_updated"


@dataclass
class PartsLoadedEvent(Event):
    """Event fired when parts are loaded."""
    parts_data: Dict[str, Any]
    part_count: int
    source: str = "project_manager"
    
    @property
    def event_type(self) -> str:
        return "parts_loaded"


@dataclass
class MotionPathUpdatedEvent(Event):
    """Event fired when a motion path is updated."""
    part_name: str
    has_path: bool
    path_length: Optional[float] = None
    source: str = "path_service"
    
    @property
    def event_type(self) -> str:
        return "motion_path_updated"


@dataclass
class ErrorOccurredEvent(Event):
    """Event fired when an error occurs."""
    error_message: str
    error_type: str  # "warning", "error", "critical"
    source: str
    details: Optional[str] = None
    
    @property
    def event_type(self) -> str:
        return "error_occurred"


@dataclass
class TabSwitchRequestedEvent(Event):
    """Event fired when tab switch is requested."""
    target_tab: str  # "landing", "image_processing", "path_drawing", "mechanism_generation", "options"
    data: Optional[Dict[str, Any]] = None
    source: str = "unknown"
    
    @property
    def event_type(self) -> str:
        return "tab_switch_requested"


@dataclass
class ViewZoomChangedEvent(Event):
    """Event fired when view zoom changes."""
    zoom_factor: float
    view_name: str
    source: str = "view"
    
    @property
    def event_type(self) -> str:
        return "view_zoom_changed"


@dataclass
class SimulationProgressEvent(Event):
    """Event fired to report simulation progress."""
    progress: float  # 0.0 to 1.0
    current_frame: int
    total_frames: int
    source: str = "animation_service"
    
    @property
    def event_type(self) -> str:
        return "simulation_progress"


@dataclass
class MechanismSimulationRequestEvent(Event):
    """Event fired to request mechanism simulation."""
    mechanism_id: str
    action: str  # "play", "pause", "stop", "reset"
    parameters: Optional[Dict[str, Any]] = None
    source: str = "ui"
    
    @property
    def event_type(self) -> str:
        return "mechanism_simulation_request"


@dataclass
class UIStateUpdateEvent(Event):
    """Event fired to update UI state."""
    component: str
    state: Dict[str, Any]
    source: str = "controller"
    
    @property
    def event_type(self) -> str:
        return "ui_state_update"