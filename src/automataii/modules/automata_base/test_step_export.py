"""
Test script for STEP export functionality.

This script demonstrates how to create and export different base types as STEP files
for professional CAD integration.
"""

from pathlib import Path
from automataii.modules.automata_base.enums.base_types import (
    BaseType, MaterialType, MountingType
)
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import (
    Dimensions2D, Dimensions3D, MountingPoint, Point2D, Unit
)
from automataii.modules.automata_base.utils.step_exporter import (
    STEPExporter, create_step_from_config
)


def create_test_bases():
    """Create test base configurations."""
    bases = []
    
    # Flat rectangular base
    config1 = BaseConfiguration(
        name="FlatRectangularBase",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(width=200, height=150, unit=Unit.MM),
        primary_material=MaterialType.ALUMINUM,
        material_thickness=10.0,
        mounting_type=MountingType.SURFACE
    )
    
    # Add mounting holes
    config1.add_mounting_point(MountingPoint(
        position=Point2D(20, 20),
        hole_diameter=5,
        thread_type="M5"
    ))
    config1.add_mounting_point(MountingPoint(
        position=Point2D(180, 20),
        hole_diameter=5,
        thread_type="M5"
    ))
    config1.add_mounting_point(MountingPoint(
        position=Point2D(180, 130),
        hole_diameter=5,
        thread_type="M5"
    ))
    config1.add_mounting_point(MountingPoint(
        position=Point2D(20, 130),
        hole_diameter=5,
        thread_type="M5"
    ))
    
    bases.append(("rectangular", config1))
    
    # Circular base
    config2 = BaseConfiguration(
        name="CircularBase",
        base_type=BaseType.FLAT_CIRCULAR,
        dimensions=Dimensions2D(width=150, height=150, unit=Unit.MM),
        primary_material=MaterialType.ACRYLIC,
        material_thickness=8.0,
        mounting_type=MountingType.SURFACE
    )
    
    # Add center hole
    config2.add_mounting_point(MountingPoint(
        position=Point2D(75, 75),
        hole_diameter=10,
        thread_type="M8"
    ))
    
    # Add radial holes
    import math
    radius = 50
    for i in range(4):
        angle = i * math.pi / 2
        x = 75 + radius * math.cos(angle)
        y = 75 + radius * math.sin(angle)
        config2.add_mounting_point(MountingPoint(
            position=Point2D(x, y),
            hole_diameter=5,
            thread_type="M5"
        ))
    
    bases.append(("circular", config2))
    
    return bases


def main():
    """Test STEP export functionality."""
    output_dir = Path("step_output")
    output_dir.mkdir(exist_ok=True)
    
    bases = create_test_bases()
    
    for name, config in bases:
        print(f"\nExporting {name} base to STEP...")
        
        # Create exporter
        exporter = STEPExporter(config)
        
        # Export STEP file
        step_path = output_dir / f"{name}_base.step"
        exporter.export(step_path)
        
        print(f"  Exported to: {step_path}")
        
        # Also test convenience function
        step_path2 = output_dir / f"{name}_base_v2.step"
        create_step_from_config(config, step_path2)
        print(f"  Also exported via convenience function to: {step_path2}")
    
    print(f"\n✅ STEP export test completed!")
    print(f"Files saved to: {output_dir.absolute()}")
    
    # Show sample of STEP file content
    print("\nSample STEP file content:")
    sample_file = output_dir / "rectangular_base.step"
    if sample_file.exists():
        with open(sample_file, 'r') as f:
            lines = f.readlines()
            print("First 20 lines:")
            for line in lines[:20]:
                print(f"  {line.rstrip()}")
            print("  ...")


if __name__ == "__main__":
    main()