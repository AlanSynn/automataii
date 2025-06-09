#!/usr/bin/env python3
"""Standalone test script for enhanced DXF export functionality."""

import os
from datetime import datetime
from typing import Optional, List, Dict, Union

# Import the classes we need directly
from dataclasses import dataclass, field
from enum import Enum


# Recreate minimal necessary enums and classes for testing
class LengthUnit(str, Enum):
    MILLIMETERS = "mm"
    CENTIMETERS = "cm"
    METERS = "m"
    INCHES = "in"
    FEET = "ft"


class BaseType(str, Enum):
    FLAT_RECTANGULAR = "flat_rectangular"
    FLAT_CIRCULAR = "flat_circular"
    BOX_ENCLOSED = "box_enclosed"
    BOX_OPEN = "box_open"
    PEDESTAL = "pedestal"
    WALL_MOUNTED = "wall_mounted"
    MODULAR = "modular"
    CUSTOM = "custom"


class MaterialType(str, Enum):
    WOOD = "wood"
    MDF = "mdf"
    PLYWOOD = "plywood"
    ACRYLIC = "acrylic"
    ALUMINUM = "aluminum"
    STEEL = "steel"
    PLASTIC_3D_PRINTED = "plastic_3d_printed"
    RESIN_3D_PRINTED = "resin_3d_printed"
    CARDBOARD = "cardboard"
    COMPOSITE = "composite"


class AssemblyMethod(str, Enum):
    SCREWS = "screws"
    GLUE = "glue"
    SNAP_FIT = "snap_fit"
    WELDING = "welding"
    MAGNETS = "magnets"
    INTERLOCKING = "interlocking"
    MIXED = "mixed"


@dataclass
class Point2D:
    x: float
    y: float


@dataclass
class Point3D:
    x: float
    y: float
    z: float


@dataclass
class MountingPoint:
    position: Point2D
    hole_diameter: float
    countersink: bool = False
    countersink_diameter: Optional[float] = None
    countersink_angle: Optional[float] = 82.0


@dataclass
class Dimensions2D:
    width: float
    height: float
    unit: LengthUnit = LengthUnit.MILLIMETERS


@dataclass
class Dimensions3D:
    width: float
    height: float
    depth: float
    unit: LengthUnit = LengthUnit.MILLIMETERS


@dataclass
class BaseConfiguration:
    name: str
    base_type: BaseType
    dimensions: Union[Dimensions2D, Dimensions3D]
    primary_material: MaterialType
    material_thickness: Optional[float] = None
    mounting_points: List[MountingPoint] = field(default_factory=list)
    assembly_method: Optional[AssemblyMethod] = None
    weight: Optional[float] = None
    max_load: Optional[float] = None
    
    @property
    def is_3d(self) -> bool:
        return isinstance(self.dimensions, Dimensions3D)
    
    @property
    def footprint(self) -> Dimensions2D:
        if isinstance(self.dimensions, Dimensions2D):
            return self.dimensions
        return Dimensions2D(
            width=self.dimensions.width,
            height=self.dimensions.height,
            unit=self.dimensions.unit
        )


def test_simple_dxf():
    """Test simple DXF generation to verify the enhanced functionality."""
    print("Testing Enhanced DXF Export")
    print("=" * 60)
    
    # Import the enhanced base_to_dxf function
    try:
        from utils.converters import base_to_dxf
        print("✓ Successfully imported base_to_dxf function")
    except ImportError as e:
        print(f"✗ Failed to import: {e}")
        return
    
    # Create a simple test configuration
    config = BaseConfiguration(
        name="Test Base Plate",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(
            width=200.0,
            height=150.0,
            unit=LengthUnit.MILLIMETERS
        ),
        primary_material=MaterialType.ACRYLIC,
        material_thickness=6.0,
        mounting_points=[
            MountingPoint(
                position=Point2D(x=20.0, y=20.0),
                hole_diameter=4.0,
                countersink=False
            ),
            MountingPoint(
                position=Point2D(x=180.0, y=20.0),
                hole_diameter=4.0,
                countersink=False
            ),
        ],
        assembly_method=AssemblyMethod.SCREWS,
        weight=0.5,
        max_load=10.0
    )
    
    print(f"\nTest Configuration:")
    print(f"  Name: {config.name}")
    print(f"  Type: {config.base_type.value}")
    print(f"  Material: {config.primary_material.value}")
    print(f"  Dimensions: {config.footprint.width} x {config.footprint.height} mm")
    
    # Test different export modes
    export_modes = ["laser", "manufacturing", "documentation"]
    
    for mode in export_modes:
        print(f"\nTesting {mode} mode...")
        try:
            dxf_content = base_to_dxf(
                config=config,
                scale=1.0,
                export_mode=mode,
                include_dimensions=(mode != "laser"),
                include_annotations=(mode == "documentation"),
                units="MILLIMETERS"
            )
            
            # Save to file
            filename = f"test_{mode}.dxf"
            with open(filename, 'w') as f:
                f.write(dxf_content)
            
            file_size = os.path.getsize(filename)
            print(f"  ✓ Generated {filename} ({file_size:,} bytes)")
            
            # Check that file contains expected DXF sections
            expected_sections = ["HEADER", "TABLES", "BLOCKS", "ENTITIES"]
            found_sections = []
            with open(filename, 'r') as f:
                content = f.read()
                for section in expected_sections:
                    if f"SECTION\n  2\n{section}" in content or f"SECTION\r\n  2\r\n{section}" in content:
                        found_sections.append(section)
            
            print(f"  ✓ Found DXF sections: {', '.join(found_sections)}")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Test complete! Check the generated DXF files.")


if __name__ == "__main__":
    test_simple_dxf()