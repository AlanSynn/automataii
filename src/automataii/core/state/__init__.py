"""
State Management Module

Redux-like state management with immutable updates, middleware support,
and time-travel debugging capabilities.
"""

from .store import StateStore
from .base import Action, Reducer, State
from .middleware import Middleware, LoggingMiddleware, PersistenceMiddleware
from .selectors import Selector, create_selector, memoize

# Global store instance
_global_store = None

def get_global_store() -> StateStore:
    """Get the global state store instance."""
    global _global_store
    if _global_store is None:
        # Create default store with minimal state
        from .base import State
        initial_state = {
            'app': {
                'theme': 'light',
                'debug_mode': False
            },
            'project': {
                'current_path': None,
                'is_modified': False
            },
            'ui': {
                'active_tab': 'welcome'
            }
        }
        
        class DefaultReducer(Reducer):
            def reduce(self, state: State, action: Action) -> State:
                # Simple default reducer
                return state
            
            @property
            def action_types(self) -> set[str]:
                """Return set of action types this reducer handles."""
                return set()  # Default reducer handles no specific actions
        
        _global_store = StateStore(
            initial_state=initial_state,
            reducer=DefaultReducer()
        )
    
    return _global_store

def set_global_store(store: StateStore) -> None:
    """Set the global state store instance."""
    global _global_store
    _global_store = store

__all__ = [
    'StateStore',
    'Action', 'Reducer', 'State',
    'Middleware', 'LoggingMiddleware', 'PersistenceMiddleware',
    'Selector', 'create_selector', 'memoize',
    'get_global_store', 'set_global_store'
]