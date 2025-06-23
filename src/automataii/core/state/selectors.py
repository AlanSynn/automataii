"""
State selectors for efficient state queries and memoization.
"""

import hashlib
import pickle
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from .base import State

T = TypeVar('T')
R = TypeVar('R')


class Selector(Generic[T, R]):
    """
    Selector for extracting and computing derived state.
    
    Provides memoization and dependency tracking for efficient
    state access patterns.
    """

    def __init__(
        self,
        selector_func: Callable[[State[T]], R],
        dependencies: list | None = None,
        memoize: bool = True
    ):
        self.selector_func = selector_func
        self.dependencies = dependencies or []
        self.memoize = memoize
        self._cache: dict[str, tuple[Any, R]] = {}
        self._name = selector_func.__name__ if hasattr(selector_func, '__name__') else 'anonymous'

    def __call__(self, state: State[T]) -> R:
        """Execute selector on state."""
        if not self.memoize:
            return self.selector_func(state)

        # Create cache key from state
        cache_key = self._create_cache_key(state)

        # Check cache
        if cache_key in self._cache:
            cached_state, cached_result = self._cache[cache_key]
            if self._states_equal(state.data, cached_state):
                return cached_result

        # Compute result
        result = self.selector_func(state)

        # Store in cache
        self._cache[cache_key] = (state.data, result)

        # Limit cache size
        if len(self._cache) > 100:
            # Remove oldest entries
            oldest_keys = list(self._cache.keys())[:50]
            for key in oldest_keys:
                del self._cache[key]

        return result

    def _create_cache_key(self, state: State[T]) -> str:
        """Create cache key from state."""
        try:
            # Try to create a hash of the relevant state parts
            if self.dependencies:
                # Hash only dependencies
                dep_data = {}
                for dep in self.dependencies:
                    if hasattr(state.data, dep):
                        dep_data[dep] = getattr(state.data, dep)
                    elif isinstance(state.data, dict) and dep in state.data:
                        dep_data[dep] = state.data[dep]

                state_bytes = pickle.dumps(dep_data, protocol=pickle.HIGHEST_PROTOCOL)
            else:
                # Hash entire state
                state_bytes = pickle.dumps(state.data, protocol=pickle.HIGHEST_PROTOCOL)

            return hashlib.md5(state_bytes).hexdigest()

        except (pickle.PicklingError, TypeError):
            # Fallback to string representation
            return str(hash(str(state.data)))

    def _states_equal(self, state1: Any, state2: Any) -> bool:
        """Check if two states are equal."""
        try:
            return state1 == state2
        except:
            return str(state1) == str(state2)

    def clear_cache(self) -> None:
        """Clear selector cache."""
        self._cache.clear()

    def __repr__(self) -> str:
        return f"Selector({self._name}, deps={self.dependencies}, memoized={self.memoize})"


def create_selector(
    *input_selectors: Selector,
    dependencies: list | None = None
) -> Callable[[Callable], Selector]:
    """
    Create a memoized selector that depends on other selectors.
    
    Args:
        *input_selectors: Input selectors to depend on
        dependencies: Additional state dependencies
        
    Returns:
        Decorator that creates a selector
    """
    def decorator(result_func: Callable) -> Selector:
        def combined_selector(state: State) -> Any:
            # Get results from input selectors
            input_results = [selector(state) for selector in input_selectors]

            # Call result function with input results
            return result_func(*input_results)

        return Selector(
            combined_selector,
            dependencies=dependencies,
            memoize=True
        )

    return decorator


def memoize(
    dependencies: list | None = None,
    cache_size: int = 100
) -> Callable[[Callable], Selector]:
    """
    Decorator to create a memoized selector.
    
    Args:
        dependencies: State fields to track for cache invalidation
        cache_size: Maximum cache size
        
    Returns:
        Decorator that creates a memoized selector
    """
    def decorator(func: Callable) -> Selector:
        selector = Selector(func, dependencies=dependencies, memoize=True)

        # Override cache size
        original_call = selector.__call__

        def cached_call(state: State) -> Any:
            result = original_call(state)

            # Trim cache if needed
            if len(selector._cache) > cache_size:
                # Keep only the most recent entries
                recent_keys = list(selector._cache.keys())[-cache_size//2:]
                new_cache = {k: selector._cache[k] for k in recent_keys}
                selector._cache = new_cache

            return result

        selector.__call__ = cached_call
        return selector

    return decorator


class SelectorRegistry:
    """
    Registry for managing selectors and their dependencies.
    """

    def __init__(self):
        self._selectors: dict[str, Selector] = {}
        self._dependencies: dict[str, set] = {}

    def register(self, name: str, selector: Selector) -> None:
        """Register a selector."""
        self._selectors[name] = selector
        self._dependencies[name] = set(selector.dependencies)

    def get(self, name: str) -> Selector | None:
        """Get selector by name."""
        return self._selectors.get(name)

    def invalidate(self, changed_fields: set) -> None:
        """Invalidate selectors that depend on changed fields."""
        for name, deps in self._dependencies.items():
            if deps.intersection(changed_fields):
                selector = self._selectors.get(name)
                if selector:
                    selector.clear_cache()

    def clear_all(self) -> None:
        """Clear all selector caches."""
        for selector in self._selectors.values():
            selector.clear_cache()

    def list_selectors(self) -> list[str]:
        """List all registered selector names."""
        return list(self._selectors.keys())


# Global selector registry
_global_registry: SelectorRegistry | None = None


def get_global_selector_registry() -> SelectorRegistry:
    """Get global selector registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = SelectorRegistry()
    return _global_registry


# Example selectors for common patterns
@memoize(dependencies=['user'])
def get_current_user(state: State) -> dict[str, Any] | None:
    """Get current user from state."""
    if hasattr(state.data, 'user'):
        return state.data.user
    elif isinstance(state.data, dict):
        return state.data.get('user')
    return None


@memoize(dependencies=['ui', 'theme'])
def get_theme_settings(state: State) -> dict[str, Any]:
    """Get theme settings from state."""
    default_theme = {'mode': 'light', 'primary_color': '#007acc'}

    if hasattr(state.data, 'ui') and hasattr(state.data.ui, 'theme'):
        return {**default_theme, **state.data.ui.theme}
    elif isinstance(state.data, dict):
        ui_data = state.data.get('ui', {})
        theme_data = ui_data.get('theme', {})
        return {**default_theme, **theme_data}

    return default_theme


@create_selector(get_current_user, get_theme_settings)
def get_user_theme_preferences(user: dict | None, theme: dict) -> dict[str, Any]:
    """Get user's theme preferences combined with current theme."""
    if user and 'preferences' in user and 'theme' in user['preferences']:
        user_theme = user['preferences']['theme']
        return {**theme, **user_theme}
    return theme
