"""
Mechanism Data Generators.

These generators produce mechanism data dictionaries that can be
rendered by SVG generators or used for simulation.

Note: These have Qt dependencies for geometry calculations.
"""

from automataii.infrastructure.generation.mechanism.base import BaseMechanism
from automataii.infrastructure.generation.mechanism.cam import Cam
from automataii.infrastructure.generation.mechanism.gear import Gear
from automataii.infrastructure.generation.mechanism.linkage import Linkage

__all__ = [
    "BaseMechanism",
    "Cam",
    "Gear",
    "Linkage",
]
