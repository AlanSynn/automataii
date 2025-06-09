"""
Test script for STL export functionality.

This script demonstrates how to create and export different base types as STL files.
"""

from pathlib import Path
from automataii.modules.automata_base.enums.base_types import (
    BaseType, MaterialType, MountingType, AssemblyMethod
)
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import (
    Dimensions2D, Dimensions3D, MountingPoint, Point2D, Point3D, Unit
)
from automataii.utils.stl_exporter import STLExporter, create_stl_from_config


def create_flat_rectangular_base():
    """Create a flat rectangular base with mounting holes."""
    config = BaseConfiguration(
        name="FlatRectangularBase",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(width=200, height=150, unit=Unit.MM),
        primary_material=MaterialType.ALUMINUM,
        material_thickness=10.0,
        mounting_type=MountingType.SURFACE,
        assembly_method=AssemblyMethod.SCREWS
    )
    
    # Add mounting holes at corners
    hole_offset = 10
    hole_diameter = 5
    
    config.add_mounting_point(MountingPoint(
        position=Point2D(hole_offset, hole_offset),
        hole_diameter=hole_diameter,
        thread_type="M5"
    ))
    config.add_mounting_point(MountingPoint(
        position=Point2D(200 - hole_offset, hole_offset),
        hole_diameter=hole_diameter,
        thread_type="M5"
    ))
    config.add_mounting_point(MountingPoint(
        position=Point2D(200 - hole_offset, 150 - hole_offset),
        hole_diameter=hole_diameter,
        thread_type="M5"
    ))
    config.add_mounting_point(MountingPoint(
        position=Point2D(hole_offset, 150 - hole_offset),
        hole_diameter=hole_diameter,
        thread_type="M5"
    ))
    
    return config


def create_circular_base():
    """Create a circular base."""
    config = BaseConfiguration(
        name="CircularBase",
        base_type=BaseType.FLAT_CIRCULAR,
        dimensions=Dimensions2D(width=150, height=150, unit=Unit.MM),
        primary_material=MaterialType.ACRYLIC,
        material_thickness=8.0,
        mounting_type=MountingType.SURFACE
    )
    
    # Add center mounting hole
    config.add_mounting_point(MountingPoint(
        position=Point2D(75, 75),
        hole_diameter=10,
        thread_type="M8"
    ))
    
    # Add radial mounting holes
    import math
    radius = 60
    for i in range(4):
        angle = i * math.pi / 2
        x = 75 + radius * math.cos(angle)
        y = 75 + radius * math.sin(angle)
        config.add_mounting_point(MountingPoint(
            position=Point2D(x, y),
            hole_diameter=5,
            thread_type="M5"
        ))
    
    return config


def create_box_base():
    """Create an enclosed box base."""
    config = BaseConfiguration(
        name="BoxBase",
        base_type=BaseType.BOX_ENCLOSED,
        dimensions=Dimensions3D(width=250, height=80, depth=200, unit=Unit.MM),
        primary_material=MaterialType.PLYWOOD,
        material_thickness=6.0,
        mounting_type=MountingType.FREESTANDING
    )
    
    return config


def create_pedestal_base():
    """Create a pedestal base."""
    config = BaseConfiguration(
        name="PedestalBase",
        base_type=BaseType.PEDESTAL,
        dimensions=Dimensions3D(width=120, height=150, depth=120, unit=Unit.MM),
        primary_material=MaterialType.WOOD,
        material_thickness=15.0,
        mounting_type=MountingType.FREESTANDING
    )
    
    return config


def create_wall_mounted_base():
    """Create a wall-mounted base."""
    config = BaseConfiguration(
        name="WallMountedBase",
        base_type=BaseType.WALL_MOUNTED,
        dimensions=Dimensions2D(width=300, height=200, unit=Unit.MM),
        primary_material=MaterialType.STEEL,
        material_thickness=5.0,
        mounting_type=MountingType.WALL
    )
    
    # Add wall mounting holes
    config.add_mounting_point(MountingPoint(
        position=Point2D(50, 180),
        hole_diameter=8,
        countersink=True,
        countersink_diameter=16
    ))
    config.add_mounting_point(MountingPoint(
        position=Point2D(250, 180),
        hole_diameter=8,
        countersink=True,
        countersink_diameter=16
    ))
    config.add_mounting_point(MountingPoint(
        position=Point2D(50, 20),
        hole_diameter=8,
        countersink=True,
        countersink_diameter=16
    ))
    config.add_mounting_point(MountingPoint(
        position=Point2D(250, 20),
        hole_diameter=8,
        countersink=True,
        countersink_diameter=16
    ))
    
    return config


def main():
    """Generate STL files for different base types."""
    output_dir = Path("stl_output")
    output_dir.mkdir(exist_ok=True)
    
    # Test configurations
    configs = [
        ("flat_rectangular", create_flat_rectangular_base()),
        ("circular", create_circular_base()),
        ("box_enclosed", create_box_base()),
        ("pedestal", create_pedestal_base()),
        ("wall_mounted", create_wall_mounted_base()),
    ]
    
    for name, config in configs:
        print(f"\nGenerating {name} base...")
        
        # Create exporter
        exporter = STLExporter(config)
        
        # Generate geometry
        triangles = exporter.generate_geometry()
        print(f"  Generated {len(triangles)} triangles")
        
        # Get statistics
        stats = exporter.get_statistics()
        print(f"  Bounding box: {stats['bounding_box']['dimensions']}")
        print(f"  Surface area: {stats['surface_area']:.2f} mm²")
        
        # Export as binary STL
        binary_path = output_dir / f"{name}_binary.stl"
        exporter.export_binary(binary_path)
        print(f"  Exported binary STL: {binary_path}")
        
        # Export as ASCII STL
        ascii_path = output_dir / f"{name}_ascii.stl"
        exporter.export_ascii(ascii_path)
        print(f"  Exported ASCII STL: {ascii_path}")
    
    print("\n✅ All STL files generated successfully!")
    print(f"Files saved to: {output_dir.absolute()}")


if __name__ == "__main__":
    main()