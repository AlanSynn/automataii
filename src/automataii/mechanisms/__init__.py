"""
Mechanisms - Modular mechanism domain logic and rendering

This package provides reusable, testable mechanism implementations extracted from the UI layer.
Each mechanism type implements the Mechanism protocol for domain logic and uses MechanismRenderer
for visualization.

Architecture:
- core/: Protocol definitions and state models
- catalog/: Mechanism registry and metadata
- linkages/: Four-bar, slider-crank mechanisms
- cams/: Cam-follower mechanisms
- gears/: Gear train mechanisms
- utils/: Shared geometry, safety, and force utilities

Public API:
    from automataii.mechanisms import get_mechanism, list_mechanism_types

    mechanism = get_mechanism("four_bar")
    state = mechanism.compute_state(parameters, input_angle)
"""

from automataii.mechanisms.catalog.registry import (
    MechanismRegistry,
    get_mechanism,
    list_mechanism_types,
)
from automataii.mechanisms.core.protocols import (
    Mechanism,
    MechanismRenderer,
)
from automataii.mechanisms.core.state import (
    ForceVector,
    MechanismState,
    SafetyStatus,
)

__all__ = [
    "Mechanism",
    "MechanismRenderer",
    "MechanismState",
    "ForceVector",
    "SafetyStatus",
    "MechanismRegistry",
    "get_mechanism",
    "list_mechanism_types",
]
