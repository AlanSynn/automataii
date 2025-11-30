"""
SVG Generation Module.

Presentation layer facade for SVG blueprint generation.
Re-exports from infrastructure/generation for convenience.
"""

# Re-export from infrastructure
from automataii.infrastructure.generation.svg.generators import (
    CamSVGGenerator,
    GearSVGGenerator,
    LinkageSVGGenerator,
)

# Import domain types
from automataii.domain.generation.layout import ScaledBounds

__all__ = [
    # SVG Generators
    "LinkageSVGGenerator",
    "GearSVGGenerator",
    "CamSVGGenerator",
    # Types
    "ScaledBounds",
]
