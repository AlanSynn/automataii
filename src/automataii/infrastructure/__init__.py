"""
Infrastructure Layer.

Contains adapters for external concerns:
- generation/: SVG and mechanism generation (uses Qt for geometry)
- events/: Event bus for decoupled communication
- state/: Redux-like state management
- container/: Dependency injection
- telemetry/: Observability and tracing

This layer provides concrete implementations of ports defined in the domain.
"""

from automataii.infrastructure import (
    container,
    events,
    generation,
    state,
    telemetry,
)

__all__ = [
    "generation",
    "events",
    "state",
    "container",
    "telemetry",
]
