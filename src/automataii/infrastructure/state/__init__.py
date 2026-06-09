"""
State Management Module.

Redux-like state management with immutable updates, middleware support,
and time-travel debugging capabilities.
"""

from automataii.infrastructure.state.base import (
    Action,
    ActionTypes,
    Reducer,
    State,
    create_action,
    reset_action,
)
from automataii.infrastructure.state.middleware import (
    LoggingMiddleware,
    Middleware,
    PersistenceMiddleware,
)
from automataii.infrastructure.state.selectors import (
    Selector,
    SelectorRegistry,
    create_selector,
    get_global_registry,
    memoize,
)
from automataii.infrastructure.state.store import (
    StateStore,
    get_global_store,
    set_global_store,
)

__all__ = [
    # Store
    "StateStore",
    "get_global_store",
    "set_global_store",
    # Base
    "Action",
    "Reducer",
    "State",
    "ActionTypes",
    "create_action",
    "reset_action",
    # Middleware
    "Middleware",
    "LoggingMiddleware",
    "PersistenceMiddleware",
    # Selectors
    "Selector",
    "SelectorRegistry",
    "create_selector",
    "memoize",
    "get_global_registry",
]
