"""Factory for mechanism visual renderers using Registry Pattern.

This module implements the Strategy + Registry Pattern for extensible
mechanism type support without violating the Open/Closed Principle.
"""

from __future__ import annotations

from typing import Any, Callable, Type

from PyQt6.QtWidgets import QGraphicsItem

from .protocol import (
    MechanismVisualRendererProtocol,
    RenderConfig,
)

__all__ = ["MechanismVisualRendererFactory", "RendererNotFoundError"]


class RendererNotFoundError(Exception):
    """Raised when no renderer is registered for mechanism type."""

    def __init__(self, mechanism_type: str) -> None:
        super().__init__(f"No renderer registered for mechanism type: '{mechanism_type}'")
        self.mechanism_type = mechanism_type


class MechanismVisualRendererFactory:
    """Factory for creating mechanism visual renderers using Registry Pattern.

    This factory maintains a registry mapping mechanism type strings to
    renderer classes. New mechanism types can be added without modifying
    existing code (Open/Closed Principle).

    Example:
        >>> factory = MechanismVisualRendererFactory()
        >>> factory.register("4_bar_linkage", FourBarVisualRenderer)
        >>> renderer = factory.create("4_bar_linkage", config)
        >>> items = renderer.render(graphics_data, config)

    Thread-safety: Registry is not thread-safe. Register during initialization.
    """

    def __init__(self) -> None:
        """Initialize empty renderer registry."""
        self._registry: dict[str, Type[MechanismVisualRendererProtocol]] = {}

    def register(
        self,
        mechanism_type: str,
        renderer_class: Type[MechanismVisualRendererProtocol],
    ) -> None:
        """Register a renderer class for a mechanism type.

        Args:
            mechanism_type: Unique identifier for mechanism type
                (e.g., "4_bar_linkage", "cam", "gear")
            renderer_class: Class implementing MechanismVisualRendererProtocol

        Raises:
            ValueError: If mechanism_type already registered
        """
        if mechanism_type in self._registry:
            raise ValueError(f"Renderer already registered for type: '{mechanism_type}'")
        self._registry[mechanism_type] = renderer_class

    def create(
        self,
        mechanism_type: str,
        *args: Any,
        **kwargs: Any,
    ) -> MechanismVisualRendererProtocol:
        """Create a renderer instance for the given mechanism type.

        Args:
            mechanism_type: Type identifier (must be registered)
            *args: Positional arguments for renderer constructor
            **kwargs: Keyword arguments for renderer constructor

        Returns:
            Renderer instance ready to use

        Raises:
            RendererNotFoundError: If mechanism_type not in registry
        """
        renderer_class = self._registry.get(mechanism_type)
        if renderer_class is None:
            raise RendererNotFoundError(mechanism_type)
        return renderer_class(*args, **kwargs)

    def render(
        self,
        mechanism_type: str,
        graphics_data: dict[str, Any],
        config: RenderConfig,
        *args: Any,
        **kwargs: Any,
    ) -> list[QGraphicsItem]:
        """Convenience method: create renderer and render immediately.

        This method is useful when renderer instances don't need to be reused.

        Args:
            mechanism_type: Type identifier (must be registered)
            graphics_data: Mechanism-specific graphics data
            config: Rendering configuration
            *args: Additional arguments for renderer constructor
            **kwargs: Additional keyword arguments for renderer constructor

        Returns:
            List of QGraphicsItem objects

        Raises:
            RendererNotFoundError: If mechanism_type not in registry
            ValueError: If graphics_data is malformed

        Example:
            >>> items = factory.render(
            ...     "4_bar_linkage",
            ...     graphics_data,
            ...     RenderConfig(show_pivots=True),
            ...     visuals_factory=visuals_factory
            ... )
        """
        renderer = self.create(mechanism_type, *args, **kwargs)
        return renderer.render(graphics_data, config)

    def is_registered(self, mechanism_type: str) -> bool:
        """Check if a renderer is registered for mechanism type.

        Args:
            mechanism_type: Type identifier to check

        Returns:
            True if registered, False otherwise
        """
        return mechanism_type in self._registry

    def get_registered_types(self) -> list[str]:
        """Get list of all registered mechanism types.

        Returns:
            Sorted list of mechanism type identifiers
        """
        return sorted(self._registry.keys())


# Global singleton factory instance
_GLOBAL_FACTORY: MechanismVisualRendererFactory | None = None


def get_global_factory() -> MechanismVisualRendererFactory:
    """Get or create the global factory singleton.

    Returns:
        Global MechanismVisualRendererFactory instance
    """
    global _GLOBAL_FACTORY
    if _GLOBAL_FACTORY is None:
        _GLOBAL_FACTORY = MechanismVisualRendererFactory()
    return _GLOBAL_FACTORY


def register_renderer(
    mechanism_type: str,
) -> Callable[[Type[MechanismVisualRendererProtocol]], Type[MechanismVisualRendererProtocol]]:
    """Decorator for registering renderer classes with global factory.

    Example:
        >>> @register_renderer("4_bar_linkage")
        ... class FourBarVisualRenderer:
        ...     def render(self, graphics_data, config):
        ...         ...

    Args:
        mechanism_type: Unique identifier for mechanism type

    Returns:
        Decorator function
    """

    def decorator(
        renderer_class: Type[MechanismVisualRendererProtocol],
    ) -> Type[MechanismVisualRendererProtocol]:
        get_global_factory().register(mechanism_type, renderer_class)
        return renderer_class

    return decorator
