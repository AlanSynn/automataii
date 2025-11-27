"""
SVG Generators Package.

Extracted from EnhancedMechanismProcessor (blueprint_optimizer.py).
Contains focused SVG generation modules for different mechanism types.

Extracted Modules:
- LinkageSVGGenerator: 4-bar and multi-bar linkage SVG generation
- GearSVGGenerator: Gear and planetary gear SVG generation
- CamSVGGenerator: Cam mechanism SVG generation
"""
from automataii.generation.svg_generators.linkage_svg import LinkageSVGGenerator
from automataii.generation.svg_generators.gear_svg import GearSVGGenerator
from automataii.generation.svg_generators.cam_svg import CamSVGGenerator

__all__ = [
    "LinkageSVGGenerator",
    "GearSVGGenerator",
    "CamSVGGenerator",
]
