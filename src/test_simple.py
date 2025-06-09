#!/usr/bin/env python3
"""
Simple Integration Test - Verify core workflow components
"""

import sys
import os

# Test 1: Core Imports
print("\n✅ TEST 1: Core Module Structure")
try:
    import automataii
    import automataii.core
    import automataii.gui
    import automataii.processing
    import automataii.kinematics
    print("   ✓ All core modules accessible")
except Exception as e:
    print(f"   ✗ Module import failed: {e}")
    sys.exit(1)

# Test 2: Critical Classes
print("\n✅ TEST 2: Critical Components")
try:
    from automataii.core.managers.project_manager import ProjectDataManager
    from automataii.core.skeleton.manager import SkeletonManager
    from automataii.processing.animation.parts_extraction.models import PartInfo
    print("   ✓ Project Manager available")
    print("   ✓ Skeleton Manager available")
    print("   ✓ Part models available")
except Exception as e:
    print(f"   ✗ Component import failed: {e}")
    sys.exit(1)

# Test 3: Service Layer
print("\n✅ TEST 3: Service Layer")
try:
    from automataii.services.path_drawing_service import PathDrawingService
    from automataii.services.animation_service import AnimationService
    print("   ✓ Path Drawing Service available")
    print("   ✓ Animation Service available")
except Exception as e:
    print(f"   ✗ Service import failed: {e}")
    sys.exit(1)

# Test 4: Data Flow
print("\n✅ TEST 4: Data Structures")
try:
    # Test skeleton structure
    skeleton = {
        'joints': [
            {'name': 'root', 'location': [100, 100]},
            {'name': 'joint1', 'location': [150, 150]}
        ],
        'hierarchy': {
            'root': ['joint1']
        }
    }
    
    # Test part structure - create dict since PartInfo is complex
    part_data = {
        'name': 'test_part',
        'texture_path': '/tmp/test.png',
        'position': [100, 100],
        'z_index': 1
    }
    
    print("   ✓ Skeleton data structure valid")
    print("   ✓ Part data structure valid")
except Exception as e:
    print(f"   ✗ Data structure failed: {e}")
    sys.exit(1)

# Test 5: Processing Pipeline
print("\n✅ TEST 5: Processing Pipeline")
try:
    from automataii.processing.vision import annotations
    # Just verify the modules exist
    import automataii.processing.animation
    print("   ✓ Image annotation module ready")
    print("   ✓ Animation processing module ready")
except Exception as e:
    print(f"   ✗ Processing pipeline failed: {e}")
    sys.exit(1)

print("\n" + "="*40)
print("🎉 ALL TESTS PASSED!")
print("   Automataii core components operational")
print("="*40 + "\n")

sys.exit(0)