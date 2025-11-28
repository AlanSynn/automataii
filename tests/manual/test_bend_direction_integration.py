#!/usr/bin/env python
"""Integration test for bend direction in IK animation."""

import sys
import logging
import pytest
from PyQt6.QtCore import QPointF, QTimer
from PyQt6.QtWidgets import QApplication
from automataii.core.skeleton_manager import SkeletonManager
from automataii.presentation.qt.kinematics import IKManager
from automataii.core.models_skeleton import StandardizedJointModel, StandardizedSkeletonModel
from automataii.core.models import PartInfo

# Skip this manual/integration test in automated runs
pytest.skip("Manual bend direction integration test; skipping in automated pytest.", allow_module_level=True)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class MockMainWindow:
    def __init__(self):
        self.skeleton_manager = SkeletonManager()
        self.editor_tab = None
        
    def statusBar(self):
        class MockStatusBar:
            def showMessage(self, msg, timeout=0):
                logging.info(f"STATUS: {msg}")
        return MockStatusBar()

def create_test_skeleton():
    """Create a test skeleton with specific joint IDs."""
    joints = {
        "hip_0": StandardizedJointModel(
            id="hip_0",
            name="hip",
            position=(100, 200),
            parent_id=None,
        ),
        "left_shoulder_7": StandardizedJointModel(
            id="left_shoulder_7",
            name="left_shoulder",
            position=(80, 150),
            parent_id="hip_0",
        ),
        "left_elbow_8": StandardizedJointModel(
            id="left_elbow_8",
            name="left_elbow",
            position=(60, 170),
            parent_id="left_shoulder_7",
            bend_direction=1.0,  # Default bend direction
        ),
        "left_hand_9": StandardizedJointModel(
            id="left_hand_9",
            name="left_hand",
            position=(40, 190),
            parent_id="left_elbow_8",
        ),
    }
    
    skeleton = StandardizedSkeletonModel(
        joints=joints,
        root_joint_ids=["hip_0"],
        hierarchy={
            "hip_0": ["left_shoulder_7"],
            "left_shoulder_7": ["left_elbow_8"],
            "left_elbow_8": ["left_hand_9"],
        },
        joint_map={
            "hip": "hip_0",
            "left_shoulder": "left_shoulder_7",
            "left_elbow": "left_elbow_8",
            "left_hand": "left_hand_9",
        },
        limb_lengths={
            "left_arm_upper": 30.0,
            "left_arm_lower": 30.0,
        },
        source_format="test",
    )
    
    return skeleton

def test_bend_direction_flow():
    """Test the complete flow of bend direction from user click to animation."""
    
    print("\n" + "="*60)
    print("BEND DIRECTION INTEGRATION TEST")
    print("="*60)
    
    # Create application
    app = QApplication(sys.argv)
    
    # Setup components
    main_window = MockMainWindow()
    skeleton_manager = main_window.skeleton_manager
    ik_manager = IKManager(main_window)
    ik_manager.set_skeleton_manager(skeleton_manager)
    
    # Create test skeleton
    test_skeleton = create_test_skeleton()
    
    print("\n1. Loading skeleton...")
    skeleton_dict = test_skeleton.model_dump()
    skeleton_manager._standardized_skeleton_model = test_skeleton
    skeleton_manager.skeleton_updated.emit(skeleton_dict)
    
    # Set project parts data
    parts_data = {
        "left_arm_upper": PartInfo(
            name="left_arm_upper",
            x=70,
            y=160,
            roi=[0, 0, 30, 30],
            motion_path_data=None,
        ),
        "left_arm_lower": PartInfo(
            name="left_arm_lower",
            x=50,
            y=180,
            roi=[0, 0, 30, 30],
            motion_path_data=[
                QPointF(40, 190),
                QPointF(30, 200),
                QPointF(40, 210),
                QPointF(50, 200),
                QPointF(40, 190),
            ],
        ),
    }
    
    print("\n2. Setting project parts data...")
    ik_manager.set_project_parts_data(parts_data)
    
    # Check initial bend directions
    print("\n3. Initial bend directions:")
    print(f"   sim_joint_bend_directions: {ik_manager.sim_joint_bend_directions}")
    
    # Simulate user clicking on joint to change bend direction
    print("\n4. Simulating user click on left_elbow_8 to change bend direction...")
    skeleton_manager.set_joint_bend_direction("left_elbow_8", -1.0)
    
    # This should trigger skeleton_updated signal
    updated_skeleton = skeleton_manager.get_current_skeleton_data()
    if updated_skeleton:
        print(f"   Skeleton updated with new bend_direction for left_elbow_8: {updated_skeleton['joints']['left_elbow_8'].get('bend_direction')}")
    
    # Check if IK manager received the update
    print("\n5. After user click, bend directions in IK manager:")
    print(f"   sim_joint_bend_directions: {ik_manager.sim_joint_bend_directions}")
    
    # Test animation step
    print("\n6. Testing animation step...")
    ik_manager.start_animation()
    
    def check_animation():
        print("\n7. During animation:")
        print(f"   Current bend directions: {ik_manager.sim_joint_bend_directions}")
        
        # Check if the bend direction is being used in two-bone IK
        if "left_elbow_8" in ik_manager.sim_joint_bend_directions:
            bend_dir = ik_manager.sim_joint_bend_directions["left_elbow_8"]
            print(f"   ✓ Bend direction for left_elbow_8: {bend_dir}")
            if bend_dir == -1.0:
                print("   ✓ User-set bend direction is preserved!")
            else:
                print("   ✗ User-set bend direction was lost!")
        else:
            print("   ✗ left_elbow_8 not found in sim_joint_bend_directions")
        
        if "left_elbow" in ik_manager.sim_joint_bend_directions:
            bend_dir = ik_manager.sim_joint_bend_directions["left_elbow"]
            print(f"   ✓ Bend direction for left_elbow: {bend_dir}")
            if bend_dir == -1.0:
                print("   ✓ Abstract name also has correct bend direction!")
            else:
                print("   ✗ Abstract name has wrong bend direction!")
        
        ik_manager.stop_animation()
        app.quit()
    
    # Run animation for a short time
    QTimer.singleShot(100, check_animation)
    
    # Start event loop
    app.exec()
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    test_bend_direction_flow()
