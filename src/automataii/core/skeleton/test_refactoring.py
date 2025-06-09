"""
Test file to verify the refactored skeleton module works correctly.
"""

import logging
from ..skeleton import SkeletonManager

def test_skeleton_manager():
    """Test basic functionality of the refactored SkeletonManager."""
    logging.basicConfig(level=logging.INFO)
    
    # Create manager
    manager = SkeletonManager()
    
    # Test data - Animated Drawings format
    ad_skeleton_data = {
        "skeleton": [
            {"name": "hip", "parent": None, "coordinates": [0, 0]},
            {"name": "neck", "parent": "hip", "coordinates": [0, 50]},
            {"name": "head", "parent": "neck", "coordinates": [0, 70]},
            {"name": "left_shoulder", "parent": "neck", "coordinates": [-20, 50]},
            {"name": "left_elbow", "parent": "left_shoulder", "coordinates": [-40, 50]},
        ],
        "limb_meta": {
            "head_limb": 20.0,
            "left_upper_arm_limb": 25.0,
        },
    }
    
    print("\n--- Testing Skeleton Loading ---")
    if manager.load_skeleton_from_dict(ad_skeleton_data):
        print("✓ Successfully loaded skeleton")
        
        # Test joint access
        hip = manager.get_joint_by_name("hip")
        if hip:
            print(f"✓ Found hip joint at position: {hip.position}")
        
        # Test hierarchy
        children = manager.get_child_joints("hip")
        print(f"✓ Hip has {len(children)} children")
        
        # Test operations
        if manager.extend_skeleton_lengths(1.1):
            print("✓ Extended skeleton lengths by 10%")
        
        if manager.lock_joint("head", True):
            print("✓ Locked head joint")
        
        locked_joints = manager.get_locked_joints()
        print(f"✓ Locked joints: {locked_joints}")
        
        # Test serialization
        skeleton_dict = manager.get_skeleton_as_dict()
        print(f"✓ Exported skeleton with {len(skeleton_dict['joints'])} joints")
        
        # Test simplified export
        simplified = manager.export_simplified()
        print(f"✓ Simplified export has {len(simplified['joints'])} joints and {len(simplified['connections'])} connections")
        
        return True
    else:
        print("✗ Failed to load skeleton")
        return False


if __name__ == "__main__":
    test_skeleton_manager()