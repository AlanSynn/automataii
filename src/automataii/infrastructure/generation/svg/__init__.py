"""
SVG Generation Infrastructure.

Provides SVG rendering for blueprints and mechanism visualization.

Submodules:
- blueprint: Full blueprint SVG composition
- optimizer: Blueprint optimization and layout
- generators/: Individual mechanism SVG generators
"""

from automataii.infrastructure.generation.svg.generators import (
    CamSVGGenerator,
    GearSVGGenerator,
    LinkageSVGGenerator,
)

__all__ = [
    "CamSVGGenerator",
    "GearSVGGenerator",
    "LinkageSVGGenerator",
]
