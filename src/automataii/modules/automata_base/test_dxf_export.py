#!/usr/bin/env python3
"""Test script for enhanced DXF export functionality."""

import os
import sys
from datetime import datetime

# Add the automata_base module to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.base_config import BaseConfiguration
from models.dimensions import (
    Dimensions2D, Dimensions3D, MountingPoint, Point2D
)
from enums.base_types import (
    BaseType, MaterialType, AssemblyMethod, LengthUnit
)
from utils.converters import base_to_dxf


def create_sample_configurations():
    """Create various sample base configurations for testing."""
    configs = []
    
    # 1. Flat rectangular base for laser cutting
    config1 = BaseConfiguration(
        name="Laser Cut Base Plate",
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
            MountingPoint(
                position=Point2D(x=180.0, y=130.0),
                hole_diameter=4.0,
                countersink=False
            ),
            MountingPoint(
                position=Point2D(x=20.0, y=130.0),
                hole_diameter=4.0,
                countersink=False
            ),
        ],
        assembly_method=AssemblyMethod.SCREWS,
        weight=0.5,
        max_load=10.0
    )
    configs.append(("laser_cut_base", config1))
    
    # 2. Box enclosure for CNC manufacturing
    config2 = BaseConfiguration(
        name="CNC Box Enclosure",
        base_type=BaseType.BOX_ENCLOSED,
        dimensions=Dimensions3D(
            width=300.0,
            height=200.0,
            depth=100.0,
            unit=LengthUnit.MILLIMETERS
        ),
        primary_material=MaterialType.ALUMINUM,
        material_thickness=3.0,
        mounting_points=[
            MountingPoint(
                position=Point2D(x=50.0, y=50.0),
                hole_diameter=6.0,
                countersink=True,
                countersink_diameter=12.0
            ),
            MountingPoint(
                position=Point2D(x=250.0, y=50.0),
                hole_diameter=6.0,
                countersink=True,
                countersink_diameter=12.0
            ),
            MountingPoint(
                position=Point2D(x=250.0, y=150.0),
                hole_diameter=6.0,
                countersink=True,
                countersink_diameter=12.0
            ),
            MountingPoint(
                position=Point2D(x=50.0, y=150.0),
                hole_diameter=6.0,
                countersink=True,
                countersink_diameter=12.0
            ),
        ],
        assembly_method=AssemblyMethod.WELDING,
        weight=2.5,
        max_load=50.0
    )
    configs.append(("cnc_box_enclosure", config2))
    
    # 3. Circular base with complex features
    config3 = BaseConfiguration(
        name="Circular Display Base",
        base_type=BaseType.FLAT_CIRCULAR,
        dimensions=Dimensions2D(
            width=250.0,
            height=250.0,
            unit=LengthUnit.MILLIMETERS
        ),
        primary_material=MaterialType.WOOD,
        material_thickness=18.0,
        mounting_points=[
            # Radial pattern of mounting holes
            MountingPoint(
                position=Point2D(x=125.0, y=75.0),
                hole_diameter=5.0,
                countersink=True,
                countersink_diameter=10.0
            ),
            MountingPoint(
                position=Point2D(x=175.0, y=125.0),
                hole_diameter=5.0,
                countersink=True,
                countersink_diameter=10.0
            ),
            MountingPoint(
                position=Point2D(x=125.0, y=175.0),
                hole_diameter=5.0,
                countersink=True,
                countersink_diameter=10.0
            ),
            MountingPoint(
                position=Point2D(x=75.0, y=125.0),
                hole_diameter=5.0,
                countersink=True,
                countersink_diameter=10.0
            ),
        ],
        assembly_method=AssemblyMethod.GLUE,
        weight=1.8
    )
    configs.append(("circular_display_base", config3))
    
    # 4. Wall mounted bracket
    config4 = BaseConfiguration(
        name="Wall Mount Bracket",
        base_type=BaseType.WALL_MOUNTED,
        dimensions=Dimensions2D(
            width=150.0,
            height=100.0,
            unit=LengthUnit.MILLIMETERS
        ),
        primary_material=MaterialType.STEEL,
        material_thickness=5.0,
        mounting_points=[
            MountingPoint(
                position=Point2D(x=30.0, y=50.0),
                hole_diameter=8.0,
                countersink=False
            ),
            MountingPoint(
                position=Point2D(x=120.0, y=50.0),
                hole_diameter=8.0,
                countersink=False
            ),
        ],
        assembly_method=AssemblyMethod.SCREWS,
        weight=0.8,
        max_load=25.0
    )
    configs.append(("wall_mount_bracket", config4))
    
    # 5. Modular base with connection slots
    config5 = BaseConfiguration(
        name="Modular Base Unit",
        base_type=BaseType.MODULAR,
        dimensions=Dimensions2D(
            width=200.0,
            height=200.0,
            unit=LengthUnit.MILLIMETERS
        ),
        primary_material=MaterialType.PLASTIC_3D_PRINTED,
        material_thickness=4.0,
        mounting_points=[
            MountingPoint(
                position=Point2D(x=50.0, y=50.0),
                hole_diameter=3.0,
                countersink=False
            ),
            MountingPoint(
                position=Point2D(x=150.0, y=50.0),
                hole_diameter=3.0,
                countersink=False
            ),
            MountingPoint(
                position=Point2D(x=150.0, y=150.0),
                hole_diameter=3.0,
                countersink=False
            ),
            MountingPoint(
                position=Point2D(x=50.0, y=150.0),
                hole_diameter=3.0,
                countersink=False
            ),
        ],
        assembly_method=AssemblyMethod.SNAP_FIT,
        weight=0.3,
        max_load=5.0
    )
    configs.append(("modular_base_unit", config5))
    
    return configs


def test_dxf_export():
    """Test DXF export with various configurations and export modes."""
    # Create output directory
    output_dir = "dxf_exports"
    os.makedirs(output_dir, exist_ok=True)
    
    # Get sample configurations
    configs = create_sample_configurations()
    
    # Export modes to test
    export_modes = ["laser", "manufacturing", "documentation"]
    
    print("Generating DXF exports...")
    print("-" * 60)
    
    for name, config in configs:
        print(f"\nProcessing: {config.name}")
        print(f"  Type: {config.base_type.value}")
        print(f"  Material: {config.primary_material.value}")
        print(f"  Dimensions: {config.footprint.width} x {config.footprint.height} {config.footprint.unit.value}")
        
        for mode in export_modes:
            # Set appropriate options for each mode
            include_dims = mode != "laser"
            include_annot = mode == "documentation"
            
            # Generate DXF
            dxf_content = base_to_dxf(
                config=config,
                scale=1.0,
                export_mode=mode,
                include_dimensions=include_dims,
                include_annotations=include_annot,
                units="MILLIMETERS"
            )
            
            # Save to file
            filename = f"{name}_{mode}.dxf"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w') as f:
                f.write(dxf_content)
            
            print(f"  ✓ Exported {mode} mode: {filename}")
            
            # Check file size to ensure content was generated
            file_size = os.path.getsize(filepath)
            print(f"    File size: {file_size:,} bytes")
    
    print("\n" + "-" * 60)
    print(f"✓ All DXF files exported to: {os.path.abspath(output_dir)}")
    print("\nYou can now open these files in:")
    print("  - AutoCAD")
    print("  - DraftSight")
    print("  - LibreCAD")
    print("  - Fusion 360")
    print("  - Any laser cutter software")
    print("  - CNC/CAM software")
    
    # Generate a summary report
    summary_file = os.path.join(output_dir, "export_summary.txt")
    with open(summary_file, 'w') as f:
        f.write("DXF Export Summary\n")
        f.write("=" * 60 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for name, config in configs:
            f.write(f"\n{config.name}\n")
            f.write("-" * 40 + "\n")
            f.write(f"Base Type: {config.base_type.value}\n")
            f.write(f"Material: {config.primary_material.value}\n")
            f.write(f"Dimensions: {config.footprint.width} x {config.footprint.height} {config.footprint.unit.value}\n")
            if config.is_3d:
                f.write(f"Depth: {config.dimensions.depth} {config.dimensions.unit.value}\n")
            f.write(f"Material Thickness: {config.material_thickness} {config.footprint.unit.value}\n")
            f.write(f"Mounting Points: {len(config.mounting_points)}\n")
            f.write(f"Assembly Method: {config.assembly_method.value if config.assembly_method else 'None'}\n")
            if config.weight:
                f.write(f"Weight: {config.weight} kg\n")
            if config.max_load:
                f.write(f"Max Load: {config.max_load} kg\n")
            f.write("\n")
    
    print(f"\n✓ Summary report saved to: {summary_file}")


if __name__ == "__main__":
    test_dxf_export()