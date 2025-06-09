"""
Complete usage example for the Automataii automata base system.

This example demonstrates the full workflow from configuration to export,
showing integration with various base types and mechanism systems.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any

# Automata base imports
from automataii.modules.automata_base import (
    BaseType, MaterialType, MountingType, AssemblyMethod,
    BaseConfiguration, Dimensions2D, Dimensions3D, Unit,
    MountingPoint, Point2D, get_base_specification, list_specifications
)
from automataii.modules.automata_base.utils import (
    validate_base_configuration, base_to_svg, base_to_dxf
)

# Generator imports
from automataii.generators import (
    BaseGenerator, GeneratorConfig, AxisGenerator,
    BodyCavityGenerator, StructuredGenerator
)

# Integration imports
from automataii.integration import MechanismAdapter, ExportManager

# Generation imports for mechanisms
from automataii.generation import LinkageMechanism, CamMechanism, GearMechanism


def example_complete_workflow():
    """Demonstrate complete workflow from configuration to export."""
    print("=== COMPLETE WORKFLOW EXAMPLE ===\n")
    
    # Step 1: Create base configuration
    print("1. Creating base configuration...")
    base_config = create_custom_base()
    print(f"   ✓ Created base: {base_config.name}")
    print(f"   ✓ Type: {base_config.base_type.value}")
    print(f"   ✓ Dimensions: {base_config.dimensions.width}x{base_config.dimensions.height} mm")
    
    # Step 2: Generate base structure
    print("\n2. Generating base structure...")
    generator_config = GeneratorConfig(
        scale=1.0,
        material_thickness=6.0,
        tolerance=0.2,
        units="mm"
    )
    
    # Use appropriate generator based on base type
    if base_config.base_type == BaseType.BOX_ENCLOSED:
        generator = StructuredGenerator(generator_config)
    else:
        generator = AxisGenerator(generator_config)
    
    base_data = generator.generate()
    mounting_points = generator.calculate_mounting_points()
    print(f"   ✓ Generated {len(mounting_points)} mounting points")
    
    # Step 3: Create mechanisms
    print("\n3. Creating mechanisms...")
    mechanisms = create_sample_mechanisms()
    print(f"   ✓ Created {len(mechanisms)} mechanisms")
    
    # Step 4: Adapt mechanisms to base
    print("\n4. Adapting mechanisms to base...")
    adapter = MechanismAdapter()
    
    for i, mechanism in enumerate(mechanisms):
        placement = adapter.add_mechanism(mechanism, base_config.base_type.value)
        print(f"   ✓ Placed {mechanism.__class__.__name__} at position {placement.base_position}")
    
    # Step 5: Export to various formats
    print("\n5. Exporting to various formats...")
    export_manager = ExportManager()
    
    # Export base as SVG
    svg_content = base_to_svg(
        base_config,
        show_mounting_points=True,
        show_dimensions=True,
        scale=2.0
    )
    
    output_dir = Path("example_output")
    output_dir.mkdir(exist_ok=True)
    
    # Save SVG
    svg_path = output_dir / "automata_base.svg"
    with open(svg_path, "w") as f:
        f.write(svg_content)
    print(f"   ✓ Exported base to {svg_path}")
    
    # Export assembly info
    assembly_info = {
        "base": base_config.__dict__,
        "mechanisms": [m.__dict__ for m in mechanisms if hasattr(m, "__dict__")],
        "mounting_points": [mp.__dict__ for mp in mounting_points],
        "placements": {k: v.__dict__ for k, v in adapter.placements.items()}
    }
    
    json_path = output_dir / "assembly_info.json"
    with open(json_path, "w") as f:
        json.dump(assembly_info, f, indent=2, default=str)
    print(f"   ✓ Exported assembly info to {json_path}")
    
    print("\n✅ Workflow completed successfully!")
    return base_config, mechanisms, adapter


def create_custom_base() -> BaseConfiguration:
    """Create a custom base configuration."""
    base = BaseConfiguration(
        name="Interactive Automata Display Base",
        base_type=BaseType.BOX_ENCLOSED,
        dimensions=Dimensions3D(
            width=400,
            height=300,
            depth=350,
            unit=Unit.MM
        ),
        primary_material=MaterialType.WOOD,
        secondary_materials=[MaterialType.ACRYLIC],
        mounting_type=MountingType.FREESTANDING,
        assembly_method=AssemblyMethod.SCREWS,
        material_thickness=12.0,
        weight=3.5,
        max_load=15.0,
        color="Natural Oak",
        finish="Satin Varnish"
    )
    
    # Add strategic mounting points
    # Center point for main mechanism
    base.add_mounting_point(MountingPoint(
        position=Point2D(200, 150),
        hole_diameter=8.0,
        thread_type="M8",
        countersink=True,
        countersink_diameter=16.0
    ))
    
    # Corner support points
    corner_offsets = [(50, 50), (350, 50), (350, 250), (50, 250)]
    for x, y in corner_offsets:
        base.add_mounting_point(MountingPoint(
            position=Point2D(x, y),
            hole_diameter=6.0,
            thread_type="M6"
        ))
    
    # Additional mechanism mounting points
    mechanism_points = [(150, 100), (250, 100), (200, 200)]
    for x, y in mechanism_points:
        base.add_mounting_point(MountingPoint(
            position=Point2D(x, y),
            hole_diameter=5.0,
            thread_type="M5"
        ))
    
    return base


def create_sample_mechanisms() -> List[Any]:
    """Create sample mechanisms for the automata."""
    mechanisms = []
    
    # Create a four-bar linkage
    linkage = LinkageMechanism(
        id="linkage_1",
        name="Primary Motion Linkage",
        crank_length=50,
        coupler_length=80,
        follower_length=60,
        ground_length=100,
        crank_pivot=(0, 0),
        ground_pivot=(100, 0)
    )
    mechanisms.append(linkage)
    
    # Create a cam mechanism
    cam = CamMechanism(
        id="cam_1",
        name="Wave Motion Cam",
        cam_radius=40,
        follower_type="roller",
        center_position=(150, 150)
    )
    mechanisms.append(cam)
    
    # Create a gear train
    gear = GearMechanism(
        id="gear_1",
        name="Speed Reduction Gear",
        driver_teeth=20,
        driven_teeth=60,
        module=2.0,
        center_distance=80
    )
    mechanisms.append(gear)
    
    return mechanisms


def example_different_base_types():
    """Demonstrate working with different base types."""
    print("\n=== DIFFERENT BASE TYPES EXAMPLE ===\n")
    
    base_types_config = {
        BaseType.FLAT_RECTANGULAR: {
            "dimensions": Dimensions2D(300, 200, Unit.MM),
            "thickness": 10.0,
            "description": "Simple flat base for table-top display"
        },
        BaseType.BOX_OPEN: {
            "dimensions": Dimensions3D(250, 180, 200, Unit.MM),
            "thickness": 8.0,
            "description": "Open box for accessible mechanisms"
        },
        BaseType.PEDESTAL: {
            "dimensions": Dimensions3D(150, 150, 300, Unit.MM),
            "thickness": 15.0,
            "description": "Tall pedestal for elevated display"
        },
        BaseType.WALL_MOUNTED: {
            "dimensions": Dimensions2D(200, 300, Unit.MM),
            "thickness": 12.0,
            "description": "Wall-mounted for vertical display"
        }
    }
    
    created_bases = []
    
    for base_type, config in base_types_config.items():
        print(f"Creating {base_type.value} base:")
        print(f"  Description: {config['description']}")
        
        base = BaseConfiguration(
            name=f"{base_type.value.replace('_', ' ').title()} Base",
            base_type=base_type,
            dimensions=config['dimensions'],
            primary_material=MaterialType.MDF,
            material_thickness=config['thickness'],
            mounting_type=(MountingType.WALL if base_type == BaseType.WALL_MOUNTED 
                          else MountingType.FREESTANDING)
        )
        
        # Validate
        issues = validate_base_configuration(base)
        status = "✓ Valid" if not issues else f"✗ Issues: {issues}"
        print(f"  Status: {status}")
        
        created_bases.append(base)
    
    return created_bases


def example_ui_interaction():
    """Demonstrate UI interaction patterns."""
    print("\n=== UI INTERACTION EXAMPLE ===\n")
    
    # Simulate user selections
    user_preferences = {
        "base_type": BaseType.BOX_ENCLOSED,
        "material": MaterialType.WOOD,
        "size": "medium",
        "mechanisms": ["linkage", "cam"],
        "theme": "natural"
    }
    
    print("User preferences:")
    for key, value in user_preferences.items():
        print(f"  {key}: {value}")
    
    # Get appropriate base specification
    spec = get_base_specification("display_box")
    
    # Create base from user preferences
    base = spec.create_base(
        size_name=user_preferences["size"],
        material=user_preferences["material"]
    )
    
    print(f"\nCreated base: {base.name}")
    print(f"Material: {base.primary_material.value}")
    print(f"Dimensions: {base.dimensions}")
    
    return base


def example_export_functionality():
    """Demonstrate various export options."""
    print("\n=== EXPORT FUNCTIONALITY EXAMPLE ===\n")
    
    # Create a simple base
    base = BaseConfiguration(
        name="Export Example Base",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(200, 150, Unit.MM),
        primary_material=MaterialType.ACRYLIC,
        material_thickness=5.0
    )
    
    # Add some mounting points
    for x in [50, 150]:
        for y in [50, 100]:
            base.add_mounting_point(MountingPoint(
                position=Point2D(x, y),
                hole_diameter=4.0
            ))
    
    output_dir = Path("example_output")
    output_dir.mkdir(exist_ok=True)
    
    # Export to SVG with different options
    svg_simple = base_to_svg(base, show_mounting_points=False)
    svg_detailed = base_to_svg(
        base,
        show_mounting_points=True,
        show_dimensions=True,
        scale=2.0
    )
    
    # Save files
    with open(output_dir / "base_simple.svg", "w") as f:
        f.write(svg_simple)
    print("✓ Exported simple SVG")
    
    with open(output_dir / "base_detailed.svg", "w") as f:
        f.write(svg_detailed)
    print("✓ Exported detailed SVG")
    
    # Export to DXF (if available)
    try:
        dxf_content = base_to_dxf(base)
        with open(output_dir / "base.dxf", "w") as f:
            f.write(dxf_content)
        print("✓ Exported DXF")
    except:
        print("✗ DXF export not available")
    
    # Export configuration as JSON
    config_data = {
        "name": base.name,
        "type": base.base_type.value,
        "dimensions": {
            "width": base.dimensions.width,
            "height": base.dimensions.height,
            "unit": base.dimensions.unit.value
        },
        "material": base.primary_material.value,
        "mounting_points": [
            {"x": mp.position.x, "y": mp.position.y, "diameter": mp.hole_diameter}
            for mp in base.mounting_points
        ]
    }
    
    with open(output_dir / "base_config.json", "w") as f:
        json.dump(config_data, f, indent=2)
    print("✓ Exported configuration JSON")
    
    return output_dir


def cleanup_example_files():
    """Clean up generated example files."""
    output_dir = Path("example_output")
    if output_dir.exists():
        for file in output_dir.iterdir():
            file.unlink()
        output_dir.rmdir()
        print("\n✓ Cleaned up example files")


if __name__ == "__main__":
    print("AUTOMATAII AUTOMATA BASE SYSTEM - COMPLETE EXAMPLE")
    print("=" * 50)
    
    try:
        # Run all examples
        example_complete_workflow()
        example_different_base_types()
        example_ui_interaction()
        example_export_functionality()
        
        print("\n" + "=" * 50)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Optional: cleanup generated files
        # cleanup_example_files()
        pass