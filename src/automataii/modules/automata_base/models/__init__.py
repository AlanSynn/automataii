"""Models for automata base system."""

from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import (
    Dimensions2D,
    Dimensions3D,
    BoundingBox,
    MountingPoint,
)
from automataii.modules.automata_base.models.assembly_info import AssemblyInfo, ConnectionInfo

__all__ = [
    "BaseConfiguration",
    "Dimensions2D",
    "Dimensions3D",
    "BoundingBox",
    "MountingPoint",
    "AssemblyInfo",
    "ConnectionInfo",
]