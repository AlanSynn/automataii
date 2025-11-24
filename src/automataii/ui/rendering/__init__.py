"""Visual rendering protocols and services for mechanism graphics.

This module provides Strategy Pattern-based visual rendering for different
mechanism types, enabling extensibility and testability.
"""

from .protocol import MechanismVisualRendererProtocol, RenderConfig
from .factory import (
    MechanismVisualRendererFactory,
    RendererNotFoundError,
    get_global_factory,
    register_renderer,
)

__all__ = [
    "MechanismVisualRendererProtocol",
    "RenderConfig",
    "MechanismVisualRendererFactory",
    "RendererNotFoundError",
    "get_global_factory",
    "register_renderer",
]
