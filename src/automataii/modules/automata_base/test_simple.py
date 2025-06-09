#!/usr/bin/env python3
"""Simple test to verify imports work correctly."""

import sys
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

print(f"Testing from: {current_dir}")
print("=" * 80)

# Test 1: Direct imports
print("\nTest 1: Direct module imports...")
try:
    from enums.base_types import BaseType, MaterialType, MountingType, AssemblyMethod
    from models.dimensions import Dimensions2D, Unit
    from models.base_config import BaseConfiguration
    print("✓ Direct imports successful")
except Exception as e:
    print(f"✗ Direct imports failed: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Package import
print("\nTest 2: Package import...")
try:
    import automata_base
    print(f"✓ Package import successful, version: {automata_base.__version__}")
except Exception as e:
    print(f"✗ Package import failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Create a configuration
print("\nTest 3: Creating a configuration...")
try:
    config = BaseConfiguration(
        name="Test Base",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(width=100, height=100, unit=Unit.MM),
        primary_material=MaterialType.WOOD,
        mounting_type=MountingType.SURFACE,
        assembly_method=AssemblyMethod.SCREWS,
        material_thickness=12.0
    )
    print(f"✓ Created configuration: {config.name}")
    print(f"  - Type: {config.base_type.value}")
    print(f"  - Dimensions: {config.dimensions.width}x{config.dimensions.height} {config.dimensions.unit.value}")
    print(f"  - Material: {config.primary_material.value}")
except Exception as e:
    print(f"✗ Failed to create configuration: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Use validators
print("\nTest 4: Using validators...")
try:
    from utils.validators import validate_base_configuration
    issues = validate_base_configuration(config)
    if issues:
        print(f"✗ Validation issues: {issues}")
    else:
        print("✓ Configuration validated successfully")
except Exception as e:
    print(f"✗ Failed to use validators: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Use converters
print("\nTest 5: Using converters...")
try:
    from utils.converters import base_to_svg
    svg = base_to_svg(config, show_mounting_points=False)
    print(f"✓ Generated SVG ({len(svg)} characters)")
    print(f"  Preview: {svg[:100]}...")
except Exception as e:
    print(f"✗ Failed to use converters: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Use specifications
print("\nTest 6: Using base specifications...")
try:
    from config.base_specs import get_base_specification
    spec = get_base_specification("simple_flat")
    base = spec.create_base("small")
    print(f"✓ Created base from specification: {base.name}")
    print(f"  - Dimensions: {base.dimensions.width}x{base.dimensions.height} {base.dimensions.unit.value}")
    print(f"  - Material thickness: {base.material_thickness}mm")
except Exception as e:
    print(f"✗ Failed to use specifications: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("✅ Testing complete!")