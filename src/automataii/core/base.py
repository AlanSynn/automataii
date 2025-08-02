"""
Base classes for state management and event system.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar


@dataclass(frozen=True)
class Action:
    """
    Base action class for state mutations.
    All actions should be immutable and serializable.
    """

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    # Metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate action after initialization."""
        if not self.type:
            raise ValueError("Action type cannot be empty")


# Event System Classes
@dataclass(frozen=True)
class Event:
    """
    Base event class for the event system.
    All events should be immutable and serializable.
    """
    
    # Metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class ApplicationStarted(Event):
    """Event fired when application starts."""
    startup_time: float = 0.0


@dataclass(frozen=True)
class ComponentActivated(Event):
    """Event fired when a component is activated."""
    component_id: str = ""
    component_type: str = ""
    widget_id: str = ""
    action: str = ""


class EventHandler(ABC):
    """
    Abstract base class for event handlers.
    """
    
    def __init__(self, is_async: bool = False):
        self.is_async = is_async
    
    @abstractmethod
    def handle(self, event: Event) -> None:
        """Handle the event."""
        pass


StateType = TypeVar("StateType")


class State(Generic[StateType]):
    """
    Base state container with immutability guarantees.
    """

    def __init__(self, data: StateType):
        self._data = data
        self._frozen = False

    @property
    def data(self) -> StateType:
        """Get the state data."""
        return self._data

    def freeze(self) -> "State[StateType]":
        """Make this state immutable."""
        self._frozen = True
        return self

    def copy(self, **changes) -> "State[StateType]":
        """Create a copy with optional changes."""
        if hasattr(self._data, "_replace"):
            # NamedTuple or dataclass
            new_data = self._data._replace(**changes)
        elif hasattr(self._data, "copy"):
            # Dict-like
            new_data = self._data.copy()
            new_data.update(changes)
        else:
            # Fallback
            new_data = changes.get("data", self._data)

        return State(new_data)

    def __setattr__(self, name: str, value: Any) -> None:
        if hasattr(self, "_frozen") and self._frozen and name != "_frozen":
            raise AttributeError("Cannot modify frozen state")
        super().__setattr__(name, value)


class Reducer(ABC, Generic[StateType]):
    """
    Abstract base class for state reducers.
    """

    @abstractmethod
    def reduce(self, state: State[StateType], action: Action) -> State[StateType]:
        """
        Apply an action to the state and return new state.

        Args:
            state: Current state
            action: Action to apply

        Returns:
            New state after applying action
        """
        pass

    @property
    @abstractmethod
    def action_types(self) -> set[str]:
        """Return set of action types this reducer handles."""
        pass

    def handles_action(self, action: Action) -> bool:
        """Check if this reducer handles the given action."""
        return action.type in self.action_types


class CombinedReducer(Reducer[dict[str, Any]]):
    """
    Combines multiple reducers into one.
    """

    def __init__(self, reducers: dict[str, Reducer]):
        self.reducers = reducers
        self._action_types = set()
        for reducer in reducers.values():
            self._action_types.update(reducer.action_types)

    def reduce(self, state: State[dict[str, Any]], action: Action) -> State[dict[str, Any]]:
        """Apply action to each sub-reducer."""
        new_state_data = {}

        for key, reducer in self.reducers.items():
            if reducer.handles_action(action):
                sub_state = State(state.data.get(key))
                new_sub_state = reducer.reduce(sub_state, action)
                new_state_data[key] = new_sub_state.data
            else:
                new_state_data[key] = state.data.get(key)

        return State(new_state_data)

    @property
    def action_types(self) -> set[str]:
        return self._action_types


# Common action types
class ActionTypes:
    """Common action type constants."""

    INIT = "@@INIT"
    RESET = "@@RESET"
    UPDATE = "@@UPDATE"

    # Project actions
    PROJECT_LOAD = "PROJECT_LOAD"
    PROJECT_SAVE = "PROJECT_SAVE"
    PROJECT_CLOSE = "PROJECT_CLOSE"

    # UI actions
    UI_THEME_CHANGE = "UI_THEME_CHANGE"
    UI_PANEL_TOGGLE = "UI_PANEL_TOGGLE"
    UI_ZOOM_CHANGE = "UI_ZOOM_CHANGE"

    # Animation actions
    ANIMATION_PLAY = "ANIMATION_PLAY"
    ANIMATION_PAUSE = "ANIMATION_PAUSE"
    ANIMATION_STOP = "ANIMATION_STOP"


# Common actions
def create_action(
    action_type: str, payload: dict[str, Any] = None, meta: dict[str, Any] = None
) -> Action:
    """Helper to create actions."""
    return Action(type=action_type, payload=payload or {}, meta=meta or {})


# Action creators
def init_action() -> Action:
    """Create initialization action."""
    return create_action(ActionTypes.INIT)


def reset_action() -> Action:
    """Create reset action."""
    return create_action(ActionTypes.RESET)


def update_action(path: str, value: Any) -> Action:
    """Create update action."""
    return create_action(ActionTypes.UPDATE, {"path": path, "value": value})
