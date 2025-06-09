#!/usr/bin/env python3
"""Test script to verify all imports work correctly in the automata_base module."""

import sys
import traceback
from pathlib import Path

# Add the parent directories to Python path
current_dir = Path(__file__).parent
src_dir = current_dir.parent.parent.parent  # Go up to src/
sys.path.insert(0, str(src_dir))

print(f"Python path includes: {src_dir}")
print("=" * 80)

def test_imports():
    """Test all imports in the module."""
    errors = []
    
    # Test 1: Import the main module
    print("Test 1: Importing main module...")
    try:
        import automataii.modules.automata_base
        print("✓ Main module imported successfully")
    except Exception as e:
        errors.append(f"Failed to import main module: {e}")
        traceback.print_exc()
    
    # Test 2: Import from __init__.py
    print("\nTest 2: Importing from __init__.py...")
    try:
        from automataii.modules.automata_base import (
            BaseType, MountingType, MaterialType, AssemblyMethod,
            BaseConfiguration, Dimensions2D, Dimensions3D,
            BaseSpecification, get_base_specification
        )
        print("✓ All exports from __init__.py imported successfully")
    except Exception as e:
        errors.append(f"Failed to import from __init__.py: {e}")
        traceback.print_exc()
    
    # Test 3: Import individual modules
    print("\nTest 3: Importing individual modules...")
    modules_to_test = [
        "automataii.modules.automata_base.enums.base_types",
        "automataii.modules.automata_base.models.dimensions",
        "automataii.modules.automata_base.models.base_config",
        "automataii.modules.automata_base.models.assembly_info",
        "automataii.modules.automata_base.config.base_specs",
        "automataii.modules.automata_base.utils.validators",
        "automataii.modules.automata_base.utils.converters",
    ]
    
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✓ {module}")
        except Exception as e:
            errors.append(f"Failed to import {module}: {e}")
            traceback.print_exc()
    
    # Test 4: Create a simple configuration
    print("\nTest 4: Creating a simple configuration...")
    try:
        from automataii.modules.automata_base import (
            BaseConfiguration, BaseType, MaterialType, 
            Dimensions2D, Unit, MountingType, AssemblyMethod
        )
        
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
        errors.append(f"Failed to create configuration: {e}")
        traceback.print_exc()
    
    # Test 5: Use base specification
    print("\nTest 5: Using base specifications...")
    try:
        from automataii.modules.automata_base import get_base_specification
        
        spec = get_base_specification("simple_flat")
        base = spec.create_base("small")
        print(f"✓ Created base from specification: {base.name}")
        print(f"  - Dimensions: {base.dimensions.width}x{base.dimensions.height} {base.dimensions.unit.value}")
        print(f"  - Material thickness: {base.material_thickness}mm")
    except Exception as e:
        errors.append(f"Failed to use base specification: {e}")
        traceback.print_exc()
    
    # Test 6: Use validators
    print("\nTest 6: Using validators...")
    try:
        from automataii.modules.automata_base.utils.validators import validate_base_configuration
        
        issues = validate_base_configuration(config)
        if issues:
            print(f"✗ Validation issues: {issues}")
        else:
            print("✓ Configuration validated successfully")
    except Exception as e:
        errors.append(f"Failed to use validators: {e}")
        traceback.print_exc()
    
    # Test 7: Use converters
    print("\nTest 7: Using converters...")
    try:
        from automataii.modules.automata_base.utils.converters import base_to_svg
        
        svg = base_to_svg(config, show_mounting_points=False)
        print(f"✓ Generated SVG ({len(svg)} characters)")
        print(f"  Preview: {svg[:100]}...")
    except Exception as e:
        errors.append(f"Failed to use converters: {e}")
        traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 80)
    if errors:
        print(f"❌ Tests completed with {len(errors)} errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("✅ All tests passed successfully!")
        return True


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)