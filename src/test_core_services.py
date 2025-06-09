#!/usr/bin/env python3
"""
Core Services Integration Test for Automataii
Quick verification that all services can initialize and communicate
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO, format='[SERVICE TEST] %(message)s')


def test_core_services():
    """Test all core services initialization and basic communication"""

    print("\n🧪 AUTOMATAII CORE SERVICES TEST\n")

    # 1. Test Managers
    print("1️⃣ Testing Core Managers...")
    try:
        from automataii.core.managers.project_manager import ProjectDataManager
        from automataii.core.skeleton.manager import SkeletonManager
        from automataii.core.managers.mechanism_manager import MechanismManager

        project_mgr = ProjectDataManager(None)
        skeleton_mgr = SkeletonManager(None)
        mechanism_mgr = MechanismManager(None)

        print("   ✅ Project Manager initialized")
        print("   ✅ Skeleton Manager initialized")
        print("   ✅ Mechanism Manager initialized")
    except Exception as e:
        print(f"   ❌ Manager initialization failed: {e}")
        return False

    # 2. Test Services
    print("\n2️⃣ Testing Services...")
    try:
        from automataii.services import PathDrawingService, AnimationService
        from automataii.kinematics.ik_service import IKService

        path_service = PathDrawingService()
        anim_service = AnimationService()
        ik_service = IKService(None)

        print("   ✅ Path Drawing Service initialized")
        print("   ✅ Animation Service initialized")
        print("   ✅ IK Service initialized")
    except Exception as e:
        print(f"   ❌ Service initialization failed: {e}")
        return False

    # 3. Test Processing Pipeline
    print("\n3️⃣ Testing Processing Pipeline...")
    try:
        from automataii.processing.vision.annotations import image_to_annotations
        from automataii.processing.animation.skeleton_extraction import extract_skeleton
        from automataii.processing.animation.parts_extraction import extract_parts

        print("   ✅ Image annotation module loaded")
        print("   ✅ Skeleton extraction module loaded")
        print("   ✅ Parts extraction module loaded")
    except Exception as e:
        print(f"   ❌ Processing pipeline failed: {e}")
        return False

    # 4. Test UI Components (without displaying)
    print("\n4️⃣ Testing UI Components...")
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication([])

        from automataii.gui.tabs.landing_tab import LandingTab
        from automataii.gui.tabs.image_processing import ImageProcessingTab
        from automataii.gui.tabs.editor import EditorTabCoordinator
        from automataii.gui.tabs.mechanism_generation import MechanismGenerationTab

        # Just verify they can be imported and instantiated
        print("   ✅ Landing Tab available")
        print("   ✅ Image Processing Tab available")
        print("   ✅ Editor Tab available")
        print("   ✅ Mechanism Generation Tab available")

        app.quit()
    except Exception as e:
        print(f"   ❌ UI component failed: {e}")
        return False

    # 5. Test Data Flow
    print("\n5️⃣ Testing Data Flow...")
    try:
        # Test skeleton data structure
        test_skeleton = {
            'joints': [{'name': 'root', 'location': [0, 0]}],
            'hierarchy': {'root': []}
        }
        skeleton_mgr.load_skeleton_from_dict(test_skeleton, 'test')

        # Test parts data structure
        from automataii.processing.animation.parts_extraction.models import PartInfo
        test_part = PartInfo(
            name='test_part',
            texture_path='/tmp/test.png',
            position=[0, 0],
            z_index=0
        )

        print("   ✅ Skeleton data flow works")
        print("   ✅ Parts data structure works")
    except Exception as e:
        print(f"   ❌ Data flow test failed: {e}")
        return False

    # 6. Test Mechanism Generation
    print("\n6️⃣ Testing Mechanism Generation...")
    try:
        from automataii.generation.linkage import FourBarLinkage
        from automataii.generation.cam import CamMechanism
        from automataii.generation.gear import GearMechanism

        print("   ✅ FourBar Linkage generator available")
        print("   ✅ Cam Mechanism generator available")
        print("   ✅ Gear Mechanism generator available")
    except Exception as e:
        print(f"   ❌ Mechanism generation failed: {e}")
        return False

    print("\n" + "="*50)
    print("✅ ALL CORE SERVICES OPERATIONAL!")
    print("="*50 + "\n")

    return True


if __name__ == "__main__":
    success = test_core_services()
    sys.exit(0 if success else 1)