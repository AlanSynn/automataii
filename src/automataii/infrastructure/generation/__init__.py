"""
Generation Infrastructure.

Provides mechanism data generation and SVG rendering capabilities.

Submodules:
- mechanism/: Mechanism data generators (cam, gear, linkage)
- svg/: SVG rendering and blueprint composition
- processors/: Image processing for blueprint generation
"""

# Import mechanism generators
from automataii.infrastructure.generation.mechanism import (
    BaseMechanism,
    Cam,
    Gear,
    Linkage,
)

# Import SVG generators
from automataii.infrastructure.generation.svg import (
    CamSVGGenerator,
    GearSVGGenerator,
    LinkageSVGGenerator,
)

# Import blueprint functions
from automataii.infrastructure.generation.svg.blueprint import (
    generate_single_large_blueprint,
    generate_detailed_part_content,
    get_timestamp,
)

# Import processors
from automataii.infrastructure.generation.processors import (
    PNGBlueprintProcessor,
)

__all__ = [
    # Mechanism generators
    "BaseMechanism",
    "Cam",
    "Gear",
    "Linkage",
    # SVG generators
    "CamSVGGenerator",
    "GearSVGGenerator",
    "LinkageSVGGenerator",
    # Blueprint functions
    "generate_single_large_blueprint",
    "generate_detailed_part_content",
    "get_timestamp",
    # Processors
    "PNGBlueprintProcessor",
]
