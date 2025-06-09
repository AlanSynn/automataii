"""Example usage of the automata_base module."""

from automata_base import (
    BaseType,
    MaterialType,
    MountingType,
    AssemblyMethod,
    BaseConfiguration,
    Dimensions2D,
    Dimensions3D,
    Unit,
    MountingPoint,
    Point2D,
    get_base_specification,
    list_specifications,
)
from automata_base.utils import validate_base_configuration, base_to_svg


def example_predefined_base():
    """Example using predefined specifications."""
    print("=== Predefined Base Example ===")
    
    # List available specifications
    print("Available specifications:", list_specifications())
    
    # Get a specification
    spec = get_base_specification("simple_flat")
    print(f"\nSpecification: {spec.name}")
    print(f"Description: {spec.description}")
    print(f"Available sizes: {list(spec.standard_sizes.keys())}")
    
    # Create a base from specification
    base = spec.create_base(
        size_name="medium",
        material=MaterialType.WOOD,
        color="Natural Oak",
        finish="Satin"
    )
    
    print(f"\nCreated base: {base.name}")
    print(f"Dimensions: {base.dimensions.width} x {base.dimensions.height} mm")
    print(f"Material: {base.primary_material.value}")
    print(f"Mounting points: {len(base.mounting_points)}")
    
    # Validate
    issues = validate_base_configuration(base)
    print(f"Validation issues: {issues if issues else 'None'}")
    
    return base


def example_custom_base():
    """Example creating a custom base."""
    print("\n=== Custom Base Example ===")
    
    # Create a custom 3D box base
    base = BaseConfiguration(
        name="Custom Display Box",
        base_type=BaseType.BOX_ENCLOSED,
        dimensions=Dimensions3D(
            width=300,
            height=200,
            depth=250,
            unit=Unit.MM
        ),
        primary_material=MaterialType.WOOD,
        secondary_materials=[MaterialType.ACRYLIC],  # For front panel
        mounting_type=MountingType.FREESTANDING,
        assembly_method=AssemblyMethod.SCREWS,
        weight=2.5,  # kg
        max_load=10.0,  # kg
        color="Walnut",
        finish="Matte Varnish"
    )
    
    # Add custom mounting points for internal mechanism
    base.add_mounting_point(MountingPoint(
        position=Point2D(150, 100),  # Center
        hole_diameter=6.0,
        thread_type="M6",
        countersink=True,
        countersink_diameter=12.0
    ))
    
    # Add corner mounting points
    for x in [50, 250]:
        for y in [50, 150]:
            base.add_mounting_point(MountingPoint(
                position=Point2D(x, y),
                hole_diameter=4.0,
                thread_type="M4"
            ))
    
    print(f"Created base: {base.name}")
    print(f"Type: {base.base_type.value}")
    print(f"Dimensions: {base.dimensions.width} x {base.dimensions.height} x {base.dimensions.depth} mm")
    print(f"Volume: {base.dimensions.volume / 1000000:.2f} liters")
    print(f"Mounting points: {len(base.mounting_points)}")
    
    # Validate
    issues = validate_base_configuration(base)
    print(f"Validation issues: {issues if issues else 'None'}")
    
    return base


def example_export():
    """Example exporting base to different formats."""
    print("\n=== Export Example ===")
    
    # Create a simple base
    spec = get_base_specification("simple_flat")
    base = spec.create_base("small")
    
    # Export to SVG
    svg = base_to_svg(
        base,
        scale=2.0,  # 2x scale
        show_mounting_points=True,
        show_dimensions=True
    )
    
    print(f"SVG export length: {len(svg)} characters")
    print("SVG preview (first 200 chars):")
    print(svg[:200] + "...")
    
    # Save to file
    with open("base_example.svg", "w") as f:
        f.write(svg)
    print("\nSaved to base_example.svg")


def example_material_properties():
    """Example working with material properties."""
    print("\n=== Material Properties Example ===")
    
    materials = [
        MaterialType.WOOD,
        MaterialType.ALUMINUM,
        MaterialType.PLASTIC_3D_PRINTED,
        MaterialType.CARDBOARD
    ]
    
    for material in materials:
        props = MaterialType.get_properties(material)
        print(f"\n{material.value}:")
        print(f"  Density: {props['density']} kg/m³")
        print(f"  Strength: {props['strength']}")
        print(f"  Cost: {props['cost']}")
        print(f"  Workability: {props['workability']}")


def example_scaling():
    """Example scaling a base configuration."""
    print("\n=== Scaling Example ===")
    
    # Create original base
    original = BaseConfiguration(
        name="Original Base",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(100, 80, Unit.MM),
        primary_material=MaterialType.MDF,
        material_thickness=10.0,
        weight=0.5
    )
    
    # Add a mounting point
    original.add_mounting_point(MountingPoint(
        position=Point2D(50, 40),
        hole_diameter=4.0
    ))
    
    print(f"Original: {original.dimensions.width} x {original.dimensions.height} mm")
    print(f"Original weight: {original.weight} kg")
    
    # Scale up by 1.5x
    scaled = original.scale(1.5)
    
    print(f"\nScaled: {scaled.dimensions.width} x {scaled.dimensions.height} mm")
    print(f"Scaled weight: {scaled.weight} kg")
    print(f"Mounting point moved to: ({scaled.mounting_points[0].position.x}, "
          f"{scaled.mounting_points[0].position.y})")


if __name__ == "__main__":
    # Run examples
    example_predefined_base()
    example_custom_base()
    example_export()
    example_material_properties()
    example_scaling()
    
    print("\n=== Examples completed! ===")
    
    # Cleanup
    import os
    if os.path.exists("base_example.svg"):
        os.remove("base_example.svg")
        print("Cleaned up generated files.")