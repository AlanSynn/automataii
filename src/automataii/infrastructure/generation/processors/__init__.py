"""
Blueprint Processors.

Provides image processing capabilities for blueprint generation.

Modules:
- png_blueprint: PNG-based contour extraction for manufacturing blueprints
"""

from automataii.infrastructure.generation.processors.png_blueprint import (
    PNGBlueprintProcessor,
)

__all__ = [
    "PNGBlueprintProcessor",
]
