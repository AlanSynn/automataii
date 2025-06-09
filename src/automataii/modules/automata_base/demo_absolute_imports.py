#!/usr/bin/env python3
"""
Demonstration of automata_base module with absolute imports.

This script shows how to properly import and use the automata_base module
from within the automataii project structure.
"""

import sys
from pathlib import Path

# Add src directory to Python path if needed
src_dir = Path(__file__).parent.parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Import everything using absolute imports
from automataii.modules.automata_base import (
    BaseType,
    MountingType,
    MaterialType,
    AssemblyMethod,
    BaseConfiguration,
    Dimensions2D,
    Dimensions3D,
    MountingPoint,
)
from automataii.modules.automata_base.models.dimensions import Point2D
from automataii.modules.automata_base.utils import validate_base_configuration, base_to_svg
from automataii.modules.automata_base.config import get_base_specification


def main():
    print("Automata Base Module Demo")
    print("=" * 60)
    
    # Create a simple rectangular base
    print("\n1. Creating a flat rectangular base...")
    base = BaseConfiguration(
        name="Desktop Automata Base",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(width=200, height=150),
        primary_material=MaterialType.WOOD,
        material_thickness=12.0,
        mounting_type=MountingType.SURFACE,
        color="#8B4513",  # Saddle brown
        finish="Matte varnish"
    )
    
    # Add mounting points
    base.add_mounting_point(MountingPoint(
        position=Point2D(50, 50),
        hole_diameter=5.0,
        hole_depth=8.0,
        countersink=True,
        countersink_diameter=10.0
    ))
    base.add_mounting_point(MountingPoint(
        position=Point2D(150, 50),
        hole_diameter=5.0,
        hole_depth=8.0,
        countersink=True,
        countersink_diameter=10.0
    ))
    
    print(f"✓ Created: {base.name}")
    print(f"  Type: {base.base_type.value}")
    print(f"  Dimensions: {base.dimensions.width}x{base.dimensions.height} {base.dimensions.unit.value}")
    print(f"  Material: {base.primary_material.value} ({base.material_thickness}mm thick)")
    print(f"  Mounting points: {len(base.mounting_points)}")
    
    # Validate the configuration
    print("\n2. Validating configuration...")
    issues = validate_base_configuration(base)
    if issues:
        print(f"✗ Validation issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✓ Configuration is valid")
    
    # Get a preset specification
    print("\n3. Loading preset specification...")
    try:
        preset = get_base_specification("standard_flat")
        if preset:
            print(f"✓ Loaded preset: {preset.name}")
            print(f"  Description: {preset.description}")
            print(f"  Recommended for loads up to: {preset.max_load_kg} kg")
    except ValueError:
        print("  Note: No presets available in this version")
    
    # Generate SVG
    print("\n4. Generating SVG representation...")
    svg = base_to_svg(base, show_mounting_points=True, show_dimensions=True)
    svg_file = Path("base_demo.svg")
    svg_file.write_text(svg)
    print(f"✓ SVG saved to: {svg_file.absolute()}")
    
    # Create a 3D base
    print("\n5. Creating a 3D box base...")
    box_base = BaseConfiguration(
        name="Enclosed Box Base",
        base_type=BaseType.BOX_ENCLOSED,
        dimensions=Dimensions3D(width=300, height=100, depth=200),
        primary_material=MaterialType.MDF,
        material_thickness=15.0,
        mounting_type=MountingType.SURFACE,
        weight=2.5,
        max_load=10.0
    )
    
    print(f"✓ Created: {box_base.name}")
    print(f"  Type: {box_base.base_type.value}")
    print(f"  3D Dimensions: {box_base.dimensions.width}x{box_base.dimensions.height}x{box_base.dimensions.depth} {box_base.dimensions.unit.value}")
    print(f"  Volume: {box_base.dimensions.volume:.0f} {box_base.dimensions.unit.value}³")
    print(f"  Weight: {box_base.weight} kg")
    print(f"  Max load: {box_base.max_load} kg")
    
    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    

if __name__ == "__main__":
    main()