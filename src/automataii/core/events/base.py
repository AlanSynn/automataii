"""
Base event system components.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

EventType = TypeVar('EventType', bound='Event')


@dataclass(frozen=True)
class Event:
    """
    Base event class with immutable data and metadata.
    All events should inherit from this class.
    """

    # Event metadata (automatically filled)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    source: str | None = field(default=None)

    # Event data (to be defined by subclasses)

    def __post_init__(self):
        """Validate event data after initialization."""
        self.validate()

    def validate(self) -> None:
        """Override in subclasses to add validation logic."""
        pass


class EventHandler(ABC, Generic[EventType]):
    """
    Abstract base class for event handlers.
    Provides type safety and consistent interface.
    """

    @abstractmethod
    def handle(self, event: EventType) -> None:
        """Handle the given event."""
        pass

    @property
    @abstractmethod
    def event_type(self) -> type[EventType]:
        """Return the event type this handler processes."""
        pass

    @property
    def priority(self) -> int:
        """Return handler priority (higher = processed first)."""
        return 0

    @property
    def is_async(self) -> bool:
        """Return True if this handler should be called asynchronously."""
        return False


@dataclass(frozen=True)
class DomainEvent(Event):
    """Base class for domain-specific events."""

    aggregate_id: str = ""
    aggregate_type: str = ""
    version: int = 1


@dataclass(frozen=True)
class SystemEvent(Event):
    """Base class for system-level events."""

    component: str = ""
    level: str = "info"  # debug, info, warning, error, critical


@dataclass(frozen=True)
class UIEvent(Event):
    """Base class for UI-related events."""

    widget_id: str | None = None
    action: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


# Common event types
@dataclass(frozen=True)
class ApplicationStarted(SystemEvent):
    """Fired when the application starts."""
    component: str = "application"
    startup_time: float = 0.0


@dataclass(frozen=True)
class ApplicationShutdown(SystemEvent):
    """Fired when the application shuts down."""
    component: str = "application"
    clean_shutdown: bool = True


@dataclass(frozen=True)
class ProjectLoaded(DomainEvent):
    """Fired when a project is loaded."""
    aggregate_type: str = "project"
    project_path: str = ""
    project_name: str = ""


@dataclass(frozen=True)
class ProjectSaved(DomainEvent):
    """Fired when a project is saved."""
    aggregate_type: str = "project"
    project_path: str = ""
    save_time: float = 0.0


@dataclass(frozen=True)
class ProjectCreated(DomainEvent):
    """Fired when a project is created."""
    aggregate_type: str = "project"
    project_name: str = ""
    template_used: str = ""


@dataclass(frozen=True)
class ProjectClosed(DomainEvent):
    """Fired when a project is closed."""
    aggregate_type: str = "project"
    project_name: str = ""


@dataclass(frozen=True)
class ProjectModified(DomainEvent):
    """Fired when a project is modified."""
    aggregate_type: str = "project"
    modification_type: str = ""


@dataclass(frozen=True)
class AutoSaveTriggered(DomainEvent):
    """Fired when auto-save is triggered."""
    aggregate_type: str = "project"
    backup_path: str | None = None


@dataclass(frozen=True)
class ComponentActivated(UIEvent):
    """Fired when a UI component is activated."""
    component_id: str = ""
    component_type: str = ""


@dataclass(frozen=True)
class ComponentDeactivated(UIEvent):
    """Fired when a UI component is deactivated."""
    component_id: str = ""
    component_type: str = ""


@dataclass(frozen=True)
class ImageSelectedEvent(UIEvent):
    """Fired when an image is selected."""
    image_path: str = ""
    widget_id: str | None = "landing_tab"
    action: str | None = "image_selected"


@dataclass(frozen=True)
class ProjectLoadedEvent(DomainEvent):
    """Fired when a project is loaded (alias for ProjectLoaded)."""
    aggregate_type: str = "project"
    project_path: str = ""
    project_name: str = ""
