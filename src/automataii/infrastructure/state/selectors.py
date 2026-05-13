"""
State selectors for efficient state queries and memoization.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import Any, Generic, TypeVar

from automataii.infrastructure.state.base import State

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
        memoize: bool = True,
        max_cache_size: int = 100,
    ):
        self.selector_func = selector_func
        self.dependencies = dependencies or []
        self.memoize = memoize
        self.max_cache_size = max(1, int(max_cache_size))
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
            _cached_state, cached_result = self._cache[cache_key]
            return cached_result

        # Compute result
        result = self.selector_func(state)

        # Store in cache
        self._cache[cache_key] = (self._cache_data(state), result)

        self._trim_cache()

        return result

    def _trim_cache(self) -> None:
        """Trim cache using insertion order when it exceeds the configured size."""
        if len(self._cache) <= self.max_cache_size:
            return

        overflow = len(self._cache) - self.max_cache_size
        oldest_keys = list(self._cache.keys())[:overflow]
        for key in oldest_keys:
            del self._cache[key]

    def _create_cache_key(self, state: State[T]) -> str:
        """Create cache key from state using JSON serialization (secure alternative to pickle).

        Security Note:
            Uses JSON instead of pickle to prevent arbitrary code execution.
            Uses SHA256 instead of MD5 to prevent hash collision attacks.
        """
        cache_data = self._cache_data(state)
        try:
            state_json = self._serialize_to_json(cache_data)

            # Use SHA256 instead of MD5 (collision-resistant)
            return hashlib.sha256(state_json.encode('utf-8')).hexdigest()

        except (ValueError, TypeError, AttributeError):
            # Fallback to string representation
            return hashlib.sha256(repr(cache_data).encode('utf-8')).hexdigest()

    def _cache_data(self, state: State[T]) -> Any:
        """Return the exact state subset that participates in memoization."""
        if not self.dependencies:
            return state.data

        dep_data = {}
        for dep in self.dependencies:
            if hasattr(state.data, dep):
                dep_data[dep] = getattr(state.data, dep)
            elif isinstance(state.data, dict) and dep in state.data:
                dep_data[dep] = state.data[dep]
        return dep_data

    def _serialize_to_json(self, data: Any) -> str:
        """Serialize data to JSON string for hashing.

        Handles dataclasses, dicts, and other common types safely.
        """
        def json_default(obj: Any) -> Any:
            """Custom JSON encoder for non-serializable types."""
            if is_dataclass(obj) and not isinstance(obj, type):
                return asdict(obj)
            if hasattr(obj, '__dict__'):
                return obj.__dict__
            if hasattr(obj, 'tolist'):  # numpy arrays
                return obj.tolist()
            # Fallback to string representation
            return repr(obj)

        return json.dumps(data, default=json_default, sort_keys=True, ensure_ascii=False)

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
        return Selector(func, dependencies=dependencies, memoize=True, max_cache_size=cache_size)

    return decorator


class SelectorRegistry:
    """
    Registry for managing selectors and their dependencies.
    """

    def __init__(self) -> None:
        self._selectors: dict[str, Selector] = {}
        self._dependencies: dict[str, set] = {}

    def get(self, name: str) -> Selector | None:
        """Get selector by name."""
        return self._selectors.get(name)

    def register(self, name: str, selector: Selector) -> None:
        """Register a selector."""
        self._selectors[name] = selector


# Global selector registry
_global_registry: SelectorRegistry | None = None


def get_global_registry() -> SelectorRegistry:
    """Get the global selector registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = SelectorRegistry()
    return _global_registry
