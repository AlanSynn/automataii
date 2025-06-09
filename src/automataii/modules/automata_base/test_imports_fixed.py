#!/usr/bin/env python3
"""Test script to verify all imports work correctly in the automata_base module."""

import sys
import os
import traceback
from pathlib import Path

# Get current directory
current_dir = Path(__file__).parent
print(f"Current directory: {current_dir}")
print("=" * 80)

def test_standalone_imports():
    """Test imports when module is used standalone."""
    print("Testing STANDALONE imports (relative imports)...")
    errors = []
    
    # Add current directory to path so relative imports work
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    # Test 1: Import main module components
    print("\nTest 1: Importing main module components...")
    try:
        from enums.base_types import BaseType, MountingType, MaterialType
        from models.dimensions import Dimensions2D, Unit
        from models.base_config import BaseConfiguration
        print("✓ Direct module imports successful")
    except Exception as e:
        errors.append(f"Failed direct imports: {e}")
        traceback.print_exc()
    
    # Test 2: Import from __init__.py
    print("\nTest 2: Importing from package __init__.py...")
    try:
        # Remove from sys.modules to force reimport
        if 'automata_base' in sys.modules:
            del sys.modules['automata_base']
        
        import automata_base
        print(f"✓ Package imported, version: {automata_base.__version__}")
        
        # Test creating a configuration
        config = automata_base.BaseConfiguration(
            name="Test Base",
            base_type=automata_base.BaseType.FLAT_RECTANGULAR,
            dimensions=automata_base.Dimensions2D(width=100, height=100, unit=automata_base.Unit.MM),
            primary_material=automata_base.MaterialType.WOOD,
            mounting_type=automata_base.MountingType.SURFACE,
            assembly_method=automata_base.AssemblyMethod.SCREWS,
            material_thickness=12.0
        )
        print(f"✓ Created configuration: {config.name}")
    except Exception as e:
        errors.append(f"Failed package import: {e}")
        traceback.print_exc()
    
    return errors

def test_integrated_imports():
    """Test imports when module is part of automataii package."""
    print("\nTesting INTEGRATED imports (absolute imports)...")
    errors = []
    
    # Add src directory to path
    src_dir = current_dir.parent.parent.parent  # Go up to src/
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    print(f"Added to path: {src_dir}")
    
    # Test importing as part of automataii
    print("\nTest 3: Importing as part of automataii package...")
    try:
        from automataii.modules.automata_base import (
            BaseType, MountingType, MaterialType,
            BaseConfiguration, Dimensions2D, Unit
        )
        print("✓ Integrated imports successful")
        
        # Test creating a configuration
        config = BaseConfiguration(
            name="Integrated Test",
            base_type=BaseType.BOX_ENCLOSED,
            dimensions=Dimensions2D(width=200, height=150, unit=Unit.MM),
            primary_material=MaterialType.ACRYLIC,
            mounting_type=MountingType.SURFACE,
            material_thickness=6.0
        )
        print(f"✓ Created integrated configuration: {config.name}")
    except Exception as e:
        errors.append(f"Failed integrated import: {e}")
        traceback.print_exc()
    
    return errors

def test_functionality():
    """Test actual functionality of the module."""
    print("\nTesting MODULE FUNCTIONALITY...")
    errors = []
    
    try:
        # Import what we need
        if 'automata_base' in sys.modules:
            ab = sys.modules['automata_base']
        else:
            import automata_base as ab
        
        # Test 1: Base specifications
        print("\nTest 4: Using base specifications...")
        spec = ab.get_base_specification("simple_flat")
        base = spec.create_base("small")
        print(f"✓ Created base from spec: {base.name}")
        print(f"  - Dimensions: {base.dimensions.width}x{base.dimensions.height}mm")
        print(f"  - Material: {base.primary_material.value}")
        
        # Test 2: Validators
        print("\nTest 5: Using validators...")
        from utils.validators import validate_base_configuration
        issues = validate_base_configuration(base)
        if issues:
            print(f"✗ Validation issues: {issues}")
            errors.append(f"Validation failed: {issues}")
        else:
            print("✓ Configuration validated successfully")
        
        # Test 3: Converters
        print("\nTest 6: Using converters...")
        from utils.converters import base_to_svg
        svg = base_to_svg(base, show_mounting_points=True)
        print(f"✓ Generated SVG ({len(svg)} characters)")
        
        # Test 4: Assembly info
        print("\nTest 7: Creating assembly info...")
        from models.assembly_info import AssemblyInfo, Component, ComponentType
        assembly = AssemblyInfo()
        component = Component(
            id="base_plate_1",
            name="Base Plate",
            type=ComponentType.BASE_PLATE,
            quantity=1
        )
        assembly.add_component(component)
        print(f"✓ Created assembly with {len(assembly.components)} component(s)")
        
    except Exception as e:
        errors.append(f"Functionality test failed: {e}")
        traceback.print_exc()
    
    return errors

def main():
    """Run all tests."""
    all_errors = []
    
    # Test standalone imports first
    errors = test_standalone_imports()
    all_errors.extend(errors)
    
    # Test integrated imports
    errors = test_integrated_imports()
    all_errors.extend(errors)
    
    # Test functionality
    errors = test_functionality()
    all_errors.extend(errors)
    
    # Summary
    print("\n" + "=" * 80)
    if all_errors:
        print(f"❌ Tests completed with {len(all_errors)} errors:")
        for error in all_errors:
            print(f"  - {error}")
        return False
    else:
        print("✅ All tests passed successfully!")
        print("\nThe automata_base module can be used:")
        print("1. As a standalone module with relative imports")
        print("2. As part of the automataii package with absolute imports")
        print("\nExample usage:")
        print("  # Standalone")
        print("  import automata_base")
        print("  config = automata_base.BaseConfiguration(...)")
        print("\n  # Integrated")
        print("  from automataii.modules.automata_base import BaseConfiguration")
        print("  config = BaseConfiguration(...)")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)