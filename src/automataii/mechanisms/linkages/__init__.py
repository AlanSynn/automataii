"""Unified linkage mechanisms with modular strategy and validation.

Public API for linkage mechanisms (4-bar, 5-bar, 6-bar) with:
- Strategy pattern for type-specific kinematics
- Validator pattern for type-specific safety checks
- Unified interface via UnifiedLinkageMechanism

Example:
    from automataii.mechanisms.linkages import UnifiedLinkageMechanism

    params = {
        "bar_count": 4,
        "ground_link": 100.0,
        "input_link": 40.0,
        "coupler_link": 120.0,
        "output_link": 130.0,
    }

    linkage = UnifiedLinkageMechanism(params)
    state = linkage.compute_state(params, input_angle=45.0)
"""

from automataii.mechanisms.linkages.compute import UnifiedLinkageMechanism
from automataii.mechanisms.linkages.config import LinkageConfig, LinkageType, LinkRole
from automataii.mechanisms.linkages.strategies.base import LinkageStrategy
from automataii.mechanisms.linkages.strategies.fourbar import FourBarStrategy
from automataii.mechanisms.linkages.strategies.fivebar import FiveBarStrategy
from automataii.mechanisms.linkages.strategies.sixbar import SixBarStrategy
from automataii.mechanisms.linkages.validators.base import LinkageValidator
from automataii.mechanisms.linkages.validators.fourbar import FourBarValidator
from automataii.mechanisms.linkages.validators.fivebar import FiveBarValidator
from automataii.mechanisms.linkages.validators.sixbar import SixBarValidator

__all__ = [
    # Main entry point
    "UnifiedLinkageMechanism",
    # Configuration
    "LinkageConfig",
    "LinkageType",
    "LinkRole",
    # Strategies
    "LinkageStrategy",
    "FourBarStrategy",
    "FiveBarStrategy",
    "SixBarStrategy",
    # Validators
    "LinkageValidator",
    "FourBarValidator",
    "FiveBarValidator",
    "SixBarValidator",
]
