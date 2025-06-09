#!/usr/bin/env python3
"""
Basic functionality test for Automataii
Tests imports, core models, and basic operations
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🧪 Testing Automataii Basic Functionality\n")

# Test 1: Core imports
print("1. Testing core imports...")
try:
    from automataii.core.models.skeleton import StandardizedSkeletonModel, StandardizedJointModel
    from automataii.generation.base_mechanism import BaseMechanism, MechanismType
    from automataii.utils.config import AppConfig
    print("   ✅ Core imports successful")
except ImportError as e:
    print(f"   ❌ Import error: {e}")
    sys.exit(1)

# Test 2: Model creation
print("\n2. Testing model creation...")
try:
    # Create a joint
    joint = StandardizedJointModel(
        id="test_joint",
        name="Test Joint",
        position=(100.0, 200.0)
    )
    print(f"   ✅ Created StandardizedJointModel: {joint.name}")
    
    # Create a skeleton
    skeleton = StandardizedSkeletonModel()
    skeleton.joints[joint.id] = joint
    skeleton.root_joint_ids.append(joint.id)
    print(f"   ✅ Created StandardizedSkeletonModel with {len(skeleton.joints)} joints")
    
    # Test mechanism types
    print(f"   ✅ Available mechanism types: {[t.value for t in MechanismType]}")
except Exception as e:
    print(f"   ❌ Model creation error: {e}")

# Test 3: Configuration
print("\n3. Testing configuration...")
try:
    # AppConfig is a class with class attributes
    print(f"   ✅ App config loaded")
    print(f"   - App name: {AppConfig.APP_NAME}")
    print(f"   - Debug mode: {AppConfig.debug}")
    
    # Create instance for session_dir
    config = AppConfig()
    print(f"   - Session dir: {config.session_dir}")
    print(f"   - Session dir exists: {config.session_dir.exists()}")
except Exception as e:
    print(f"   ❌ Configuration error: {e}")

# Test 4: File operations
print("\n4. Testing file operations...")
try:
    from automataii.utils.paths import get_session_temp_dir, get_app_temp_dir
    
    temp_dir = get_session_temp_dir()
    app_temp_dir = get_app_temp_dir()
    
    print(f"   ✅ Session temp directory: {temp_dir}")
    print(f"   ✅ App temp directory: {app_temp_dir}")
    print(f"   - Session temp dir exists: {temp_dir.exists()}")
    print(f"   - App temp dir exists: {app_temp_dir.exists()}")
except Exception as e:
    print(f"   ❌ File operations error: {e}")

# Test 5: Mechanism generation base
print("\n5. Testing mechanism generation...")
try:
    from automataii.generation.linkage import Linkage
    from automataii.generation.gear import Gear
    
    # Check if we can instantiate
    linkage = Linkage()
    print(f"   ✅ Created Linkage: {linkage.mechanism_type}")
    
    gear = Gear()
    print(f"   ✅ Created Gear: {gear.mechanism_type}")
except Exception as e:
    print(f"   ❌ Mechanism generation error: {e}")

# Test 6: Animation components
print("\n6. Testing animation components...")
try:
    from automataii.processing.animation.skeleton_animator import SkeletonAnimator
    print("   ✅ Animation components imported successfully")
except Exception as e:
    print(f"   ❌ Animation components error: {e}")

# Test 7: GUI components (without creating windows)
print("\n7. Testing GUI component imports...")
try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    print("   ✅ PyQt6 available")
    
    from automataii.gui.widgets.canvas import DrawingCanvas
    from automataii.gui.graphics_items.skeleton_item import SkeletonGraphicsItem
    print("   ✅ GUI components can be imported")
except Exception as e:
    print(f"   ⚠️  GUI components warning: {e}")
    print("   (This may be normal if running without display)")

# Test 8: Test data validation
print("\n8. Testing data validation...")
try:
    from automataii.modules.automata_base.utils.validators import validate_base_configuration
    from automataii.modules.automata_base.models.base_config import BaseConfiguration
    from automataii.modules.automata_base.models.dimensions import Dimensions3D
    from automataii.modules.automata_base.enums.base_types import BaseType, MaterialType
    
    # Create a test configuration
    test_config = BaseConfiguration(
        name="Test Base",
        base_type=BaseType.BOX_ENCLOSED,
        dimensions=Dimensions3D(width=100, height=100, depth=50),
        primary_material=MaterialType.WOOD,
        material_thickness=5.0
    )
    
    issues = validate_base_configuration(test_config)
    if not issues:
        print("   ✅ Validation passed for test configuration")
    else:
        print(f"   ❌ Validation issues: {issues}")
except Exception as e:
    print(f"   ❌ Validation error: {e}")

# Test 9: Export formats
print("\n9. Testing export format availability...")
try:
    import json
    import xml.etree.ElementTree as ET
    print("   ✅ JSON export available")
    print("   ✅ XML export available")
    
    # Check for SVG support
    try:
        import svgwrite
        print("   ✅ SVG export available")
    except ImportError:
        print("   ⚠️  SVG export not available (svgwrite not installed)")
except Exception as e:
    print(f"   ❌ Export format error: {e}")

# Summary
print("\n" + "="*50)
print("🎯 Basic functionality test completed!")
print("="*50)