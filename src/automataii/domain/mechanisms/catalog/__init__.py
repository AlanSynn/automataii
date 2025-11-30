"""
Mechanism catalog and registry.

This module provides mechanism registration and lookup functionality.
"""

from automataii.domain.mechanisms.catalog.registry import (
    MechanismNotFoundError,
    MechanismRegistry,
)

__all__ = [
    "MechanismNotFoundError",
    "MechanismRegistry",
]
