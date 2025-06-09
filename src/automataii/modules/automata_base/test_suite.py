#!/usr/bin/env python3
"""
Comprehensive test suite for automata_base module.

This test suite verifies that all components of the automata_base module
work correctly with the fixed import system.
"""

import sys
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def test_enums():
    """Test all enum types."""
    print("\n🔧 Testing Enums...")
    from enums.base_types import (
        BaseType, MountingType, MaterialType, 
        AssemblyMethod, ConnectionType
    )
    
    # Test BaseType
    assert BaseType.FLAT_RECTANGULAR.value == "flat_rectangular"
    assert BaseType.FLAT_RECTANGULAR.description == "Flat rectangular base plate"
    print("  ✓ BaseType enum working")
    
    # Test MaterialType
    assert MaterialType.WOOD in MaterialType.get_organic_materials()
    assert MaterialType.ALUMINUM in MaterialType.get_metal_materials()
    print("  ✓ MaterialType enum working")
    
    # Test MountingType
    compatible = MountingType.get_compatible_bases(MountingType.SURFACE)
    assert BaseType.FLAT_RECTANGULAR in compatible
    print("  ✓ MountingType enum working")
    
    return True

def test_dimensions():
    """Test dimension models."""
    print("\n📐 Testing Dimensions...")
    from models.dimensions import (
        Dimensions2D, Dimensions3D, Unit, Point2D, Point3D,
        MountingPoint, BoundingBox
    )
    
    # Test 2D dimensions
    dim2d = Dimensions2D(width=100, height=50, unit=Unit.MM)
    assert dim2d.area == 5000
    assert dim2d.diagonal == (100**2 + 50**2)**0.5
    print("  ✓ Dimensions2D working")
    
    # Test 3D dimensions
    dim3d = Dimensions3D(width=100, height=50, depth=30, unit=Unit.MM)
    assert dim3d.volume == 150000
    dim2d_converted = dim3d.to_2d(exclude_axis="depth")
    assert dim2d_converted.width == 100 and dim2d_converted.height == 50
    print("  ✓ Dimensions3D working")
    
    # Test points
    p2d = Point2D(10, 20)
    p3d = Point3D(10, 20, 30)
    assert p2d.distance_to(Point2D(0, 0)) == (10**2 + 20**2)**0.5
    print("  ✓ Point classes working")
    
    # Test mounting point
    mp = MountingPoint(
        position=p2d,
        hole_diameter=4.0,
        thread_type="M4"
    )
    assert mp.hole_diameter == 4.0
    print("  ✓ MountingPoint working")
    
    return True

def test_base_configuration():
    """Test base configuration."""
    print("\n⚙️ Testing Base Configuration...")
    from models.base_config import BaseConfiguration
    from models.dimensions import Dimensions2D, Unit
    from enums.base_types import BaseType, MaterialType, MountingType, AssemblyMethod
    
    # Create a configuration
    config = BaseConfiguration(
        name="Test Base",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(width=200, height=150, unit=Unit.MM),
        primary_material=MaterialType.WOOD,
        mounting_type=MountingType.SURFACE,
        assembly_method=AssemblyMethod.SCREWS,
        material_thickness=15.0
    )
    
    assert config.name == "Test Base"
    assert config.is_3d == False
    assert config.footprint.width == 200
    print("  ✓ BaseConfiguration creation working")
    
    # Test scaling
    scaled = config.scale(0.5)
    assert scaled.dimensions.width == 100
    assert scaled.material_thickness == 7.5
    print("  ✓ Configuration scaling working")
    
    # Test to_dict
    config_dict = config.to_dict()
    assert config_dict["name"] == "Test Base"
    assert config_dict["dimensions"]["width"] == 200
    print("  ✓ Configuration serialization working")
    
    return True

def test_assembly_info():
    """Test assembly information."""
    print("\n🔩 Testing Assembly Info...")
    from models.assembly_info import (
        AssemblyInfo, Component, ComponentType,
        ConnectionInfo, AssemblyStep
    )
    from enums.base_types import ConnectionType
    
    # Create assembly info
    assembly = AssemblyInfo()
    
    # Add components
    base_plate = Component(
        id="bp1",
        name="Base Plate",
        type=ComponentType.BASE_PLATE,
        quantity=1
    )
    assembly.add_component(base_plate)
    
    side_wall = Component(
        id="sw1",
        name="Side Wall",
        type=ComponentType.SIDE_WALL,
        quantity=4
    )
    assembly.add_component(side_wall)
    
    assert len(assembly.components) == 2
    print("  ✓ Component management working")
    
    # Add assembly step
    step = AssemblyStep(
        step_number=1,
        description="Attach side walls to base plate",
        components=["bp1", "sw1"],
        estimated_time=10,
        difficulty=2
    )
    assembly.add_step(step)
    
    assert len(assembly.assembly_steps) == 1
    assert assembly.total_assembly_time == 10
    print("  ✓ Assembly steps working")
    
    # Test BOM
    bom = assembly.get_bill_of_materials()
    assert len(bom) == 2
    print("  ✓ Bill of materials working")
    
    return True

def test_specifications():
    """Test base specifications."""
    print("\n📋 Testing Specifications...")
    from config.base_specs import get_base_specification, list_specifications
    
    # List available specs
    specs = list_specifications()
    assert "simple_flat" in specs
    assert "display_box" in specs
    print(f"  ✓ Found {len(specs)} specifications")
    
    # Create base from spec
    spec = get_base_specification("simple_flat")
    base = spec.create_base("medium")
    
    assert base.dimensions.width == 200
    assert base.dimensions.height == 150
    assert base.material_thickness == 15
    assert len(base.mounting_points) == 4  # Four corners
    print("  ✓ Base creation from specification working")
    
    # Test different spec
    wall_spec = get_base_specification("wall_mount")
    wall_base = wall_spec.create_base("small")
    assert wall_base.base_type.value == "wall_mounted"
    print("  ✓ Multiple specifications working")
    
    return True

def test_validators():
    """Test validators."""
    print("\n✔️ Testing Validators...")
    from utils.validators import (
        validate_base_configuration,
        validate_dimensions_for_base_type
    )
    from models.base_config import BaseConfiguration
    from models.dimensions import Dimensions2D, Unit
    from enums.base_types import BaseType, MaterialType, MountingType, AssemblyMethod
    
    # Create valid configuration
    config = BaseConfiguration(
        name="Valid Base",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(width=100, height=100, unit=Unit.MM),
        primary_material=MaterialType.WOOD,
        mounting_type=MountingType.SURFACE,
        assembly_method=AssemblyMethod.SCREWS,
        material_thickness=10.0
    )
    
    issues = validate_base_configuration(config)
    assert len(issues) == 0
    print("  ✓ Valid configuration passes validation")
    
    # Create invalid configuration
    bad_config = BaseConfiguration(
        name="Invalid Base",
        base_type=BaseType.FLAT_RECTANGULAR,
        dimensions=Dimensions2D(width=-100, height=100, unit=Unit.MM),
        primary_material=MaterialType.WOOD,
        mounting_type=MountingType.SURFACE,
        assembly_method=AssemblyMethod.SCREWS
    )
    
    issues = validate_base_configuration(bad_config)
    assert len(issues) > 0
    assert any("positive" in issue for issue in issues)
    print("  ✓ Invalid configuration detected")
    
    # Test dimension validation
    dim_issues = validate_dimensions_for_base_type(
        BaseType.FLAT_CIRCULAR,
        {"width": 100, "height": 50}
    )
    assert len(dim_issues) > 0  # Should complain about non-equal dimensions
    print("  ✓ Dimension validation working")
    
    return True

def test_converters():
    """Test converters."""
    print("\n🔄 Testing Converters...")
    from utils.converters import base_to_svg, base_to_dxf
    from config.base_specs import get_base_specification
    
    # Create a base
    spec = get_base_specification("simple_flat")
    base = spec.create_base("small")
    
    # Test SVG conversion
    svg = base_to_svg(base, show_mounting_points=True, show_dimensions=True)
    assert "<svg" in svg
    assert 'class="base-outline"' in svg
    assert 'class="mounting-point"' in svg
    print("  ✓ SVG conversion working")
    
    # Test DXF conversion
    dxf_commands = base_to_dxf(base)
    assert "ENTITIES" in dxf_commands
    assert "LWPOLYLINE" in dxf_commands
    assert "EOF" in dxf_commands
    print("  ✓ DXF conversion working")
    
    return True

def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("🧪 AUTOMATA BASE MODULE TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Enums", test_enums),
        ("Dimensions", test_dimensions),
        ("Base Configuration", test_base_configuration),
        ("Assembly Info", test_assembly_info),
        ("Specifications", test_specifications),
        ("Validators", test_validators),
        ("Converters", test_converters),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"  ❌ {test_name} failed")
        except Exception as e:
            failed += 1
            print(f"  ❌ {test_name} failed with error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"📊 RESULTS: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ All tests passed! The automata_base module is working correctly.")
        print("\n📝 Usage examples:")
        print("  # Import the module components")
        print("  from enums.base_types import BaseType, MaterialType")
        print("  from models.base_config import BaseConfiguration")
        print("  from models.dimensions import Dimensions2D, Unit")
        print("  ")
        print("  # Create a base configuration")
        print("  config = BaseConfiguration(")
        print("      name='My Base',")
        print("      base_type=BaseType.FLAT_RECTANGULAR,")
        print("      dimensions=Dimensions2D(width=200, height=150, unit=Unit.MM),")
        print("      primary_material=MaterialType.WOOD,")
        print("      material_thickness=15.0")
        print("  )")
        print("  ")
        print("  # Or use a predefined specification")
        print("  from config.base_specs import get_base_specification")
        print("  spec = get_base_specification('display_box')")
        print("  base = spec.create_base('medium')")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    print("=" * 60)
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)