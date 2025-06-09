"""
Automata Base System Module

A modular system for defining and configuring mechanical automata bases,
including mounting types, dimensions, and assembly methods.
"""

from automataii.modules.automata_base.version import __version__

# Import core enums
from automataii.modules.automata_base.enums.base_types import (
    BaseType,
    MountingType,
    MaterialType,
    AssemblyMethod,
    ConnectionType,
)

# Import core models
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import (
    Dimensions2D,
    Dimensions3D,
    BoundingBox,
    MountingPoint,
)
from automataii.modules.automata_base.models.assembly_info import AssemblyInfo, ConnectionInfo

# Import configuration
from automataii.modules.automata_base.config.base_specs import BaseSpecification, get_base_specification

# Generators not yet implemented
BaseGenerator = None
StructuredGenerator = None
BodyCavityGenerator = None
AxisGenerator = None

# Integration not yet implemented
MechanismAdapter = None
ConnectionPoint = None
ExportManager = None

# UI components not yet implemented
UI_AVAILABLE = False
BaseSelectionWidget = None
BasePreviewWidget = None

__all__ = [
    # Version
    "__version__",
    # Enums
    "BaseType",
    "MountingType",
    "MaterialType",
    "AssemblyMethod",
    "ConnectionType",
    # Models
    "BaseConfiguration",
    "Dimensions2D",
    "Dimensions3D",
    "BoundingBox",
    "MountingPoint",
    "AssemblyInfo",
    "ConnectionInfo",
    # Configuration
    "BaseSpecification",
    "get_base_specification",
    # Generators
    "BaseGenerator",
    "StructuredGenerator",
    "BodyCavityGenerator",
    "AxisGenerator",
    # Integration
    "MechanismAdapter",
    "ConnectionPoint",
    "ExportManager",
    # UI flag
    "UI_AVAILABLE",
]

# Add UI components to __all__ if available
if UI_AVAILABLE:
    __all__.extend(["BaseSelectionWidget", "BasePreviewWidget"])