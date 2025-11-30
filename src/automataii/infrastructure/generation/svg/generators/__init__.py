"""
SVG Generators Package.

Contains focused SVG generation modules for different mechanism types.

Modules:
- cam: Cam mechanism SVG generation
- gear: Gear and planetary gear SVG generation
- linkage: 4-bar and multi-bar linkage SVG generation
- shared: Common SVG utilities
"""

from automataii.infrastructure.generation.svg.generators.cam import CamSVGGenerator
from automataii.infrastructure.generation.svg.generators.gear import GearSVGGenerator
from automataii.infrastructure.generation.svg.generators.linkage import (
    LinkageSVGGenerator,
)

__all__ = [
    "CamSVGGenerator",
    "GearSVGGenerator",
    "LinkageSVGGenerator",
]
