#!/usr/bin/env python3
"""Test script to verify all absolute imports work correctly."""

import sys
import traceback
from pathlib import Path

# Ensure we're working from the src directory
src_dir = Path(__file__).parent.parent.parent.parent  # Go up to src/
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
    
print(f"Python path includes: {src_dir}")
print(f"Working directory: {Path.cwd()}")

def test_imports():
    """Test importing all major components with absolute imports."""
    
    print("Testing absolute imports for automata_base module...")
    print("=" * 50)
    
    # Test 1: Import from main module
    try:
        from automataii.modules.automata_base import (
            BaseType,
            MountingType,
            MaterialType,
            BaseConfiguration,
            Dimensions2D,
            Dimensions3D,
            __version__
        )
        print("✓ Main module imports successful")
        print(f"  Version: {__version__}")
    except Exception as e:
        print(f"✗ Main module imports failed: {e}")
        traceback.print_exc()
        return False
    
    # Test 2: Import validators
    try:
        from automataii.modules.automata_base.utils.validators import (
            validate_base_configuration,
            ConfigValidator
        )
        print("✓ Validator imports successful")
    except Exception as e:
        print(f"✗ Validator imports failed: {e}")
        traceback.print_exc()
        return False
    
    # Test 3: Import converters
    try:
        from automataii.modules.automata_base.utils.converters import (
            base_to_svg,
            base_to_dxf
        )
        print("✓ Converter imports successful")
    except Exception as e:
        print(f"✗ Converter imports failed: {e}")
        traceback.print_exc()
        return False
    
    # Test 4: Import base specs
    try:
        from automataii.modules.automata_base.config.base_specs import (
            BaseSpecification,
            get_base_specification
        )
        print("✓ Base specs imports successful")
    except Exception as e:
        print(f"✗ Base specs imports failed: {e}")
        traceback.print_exc()
        return False
    
    # Test 5: Create a simple configuration
    try:
        config = BaseConfiguration(
            name="Test Base",
            base_type=BaseType.FLAT_RECTANGULAR,
            dimensions=Dimensions2D(width=100, height=100),
            primary_material=MaterialType.WOOD,
            mounting_type=MountingType.SURFACE,
            material_thickness=10.0  # Added required thickness
        )
        print("✓ BaseConfiguration creation successful")
        print(f"  Created: {config.name} ({config.base_type.value})")
    except Exception as e:
        print(f"✗ BaseConfiguration creation failed: {e}")
        traceback.print_exc()
        return False
    
    # Test 6: Validate configuration
    try:
        issues = validate_base_configuration(config)
        if issues:
            print(f"✗ Validation found issues: {issues}")
        else:
            print("✓ Configuration validation successful")
    except Exception as e:
        print(f"✗ Validation failed: {e}")
        traceback.print_exc()
        return False
    
    # Test 7: Convert to SVG
    try:
        svg = base_to_svg(config)
        print("✓ SVG conversion successful")
        print(f"  SVG length: {len(svg)} characters")
    except Exception as e:
        print(f"✗ SVG conversion failed: {e}")
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 50)
    print("All import tests passed! ✓")
    return True


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)