"""
Generators module for automata base system components.

This module provides generators for creating various components of the automata system:
- Base structures (box, pedestal)
- Body-mounted cavities
- Axis systems
- Mechanism adaptations
"""

from .base_generator import BaseGenerator, GeneratorConfig
from .structured_generator import StructuredGenerator, BoxBase, PedestalBase
from .body_cavity_generator import BodyCavityGenerator, CavityConfig
from .axis_generator import AxisGenerator, AxisConfig

__all__ = [
    'BaseGenerator',
    'GeneratorConfig',
    'StructuredGenerator',
    'BoxBase',
    'PedestalBase',
    'BodyCavityGenerator',
    'CavityConfig',
    'AxisGenerator',
    'AxisConfig',
]