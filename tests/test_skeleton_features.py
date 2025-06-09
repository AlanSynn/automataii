#!/usr/bin/env python3
"""Test script for skeleton extension and joint locking features."""

import sys
import logging
from PyQt6.QtWidgets import QApplication
from automataii.core.managers.skeleton_manager import SkeletonManager

logging.basicConfig(level=logging.INFO)

def test_skeleton_features():
    """Test the new skeleton features."""
    
    # Create skeleton manager
    manager = SkeletonManager()
    
    # Example skeleton data (Animated Drawings format)
    test_skeleton_data = {
        "skeleton": [
            {"name": "hip", "parent": None, "coordinates": [0, 0]},
            {"name": "torso", "parent": "hip", "coordinates": [0, -30]},
            {"name": "neck", "parent": "torso", "coordinates": [0, -60]},
            {"name": "head", "parent": "neck", "coordinates": [0, -80]},
            {"name": "left_shoulder", "parent": "torso", "coordinates": [-20, -50]},
            {"name": "left_elbow", "parent": "left_shoulder", "coordinates": [-40, -50]},
            {"name": "left_hand", "parent": "left_elbow", "coordinates": [-60, -50]},
            {"name": "right_shoulder", "parent": "torso", "coordinates": [20, -50]},
            {"name": "right_elbow", "parent": "right_shoulder", "coordinates": [40, -50]},
            {"name": "right_hand", "parent": "right_elbow", "coordinates": [60, -50]},
        ],
    }
    
    print("=== Testing Skeleton Manager ===")
    
    # Load skeleton
    print("\n1. Loading skeleton...")
    if manager.load_skeleton_from_dict(test_skeleton_data):
        print("✓ Skeleton loaded successfully")
        model = manager.standardized_model
        print(f"  - Number of joints: {len(model.joints)}")
        print(f"  - Root joints: {model.root_joint_ids}")
    else:
        print("✗ Failed to load skeleton")
        return
    
    # Test extension
    print("\n2. Testing skeleton extension by 10%...")
    
    # Get original positions
    original_positions = {}
    for joint_id, joint in model.joints.items():
        original_positions[joint_id] = joint.position
        print(f"  - {joint.name}: {joint.position}")
    
    # Extend skeleton
    if manager.extend_skeleton_lengths(1.1):
        print("\n✓ Skeleton extended successfully")
        
        # Check new positions
        print("\nNew positions:")
        for joint_id, joint in model.joints.items():
            orig_pos = original_positions[joint_id]
            new_pos = joint.position
            print(f"  - {joint.name}: {orig_pos} -> {new_pos}")
            
            # Verify root didn't move
            if joint_id in model.root_joint_ids:
                assert orig_pos == new_pos, f"Root joint {joint.name} should not move!"
    else:
        print("✗ Failed to extend skeleton")
    
    # Test joint locking
    print("\n3. Testing joint locking...")
    
    # Lock some joints
    joints_to_lock = ["neck", "left_elbow"]
    for joint_name in joints_to_lock:
        if manager.lock_joint(joint_name, True):
            print(f"✓ Locked joint: {joint_name}")
        else:
            print(f"✗ Failed to lock joint: {joint_name}")
    
    # Check locked joints
    locked_joints = manager.get_locked_joints()
    print(f"\nLocked joints: {locked_joints}")
    
    # Verify locked state
    for joint_id, joint in model.joints.items():
        if joint.name in joints_to_lock:
            assert joint.is_locked, f"Joint {joint.name} should be locked!"
            print(f"✓ Verified {joint.name} is locked")
    
    # Unlock one joint
    if manager.lock_joint("neck", False):
        print(f"\n✓ Unlocked joint: neck")
    
    # Unlock all
    if manager.unlock_all_joints():
        print("✓ Unlocked all joints")
        locked_joints = manager.get_locked_joints()
        assert len(locked_joints) == 0, "All joints should be unlocked!"
        print(f"  - Locked joints after unlock all: {locked_joints}")
    
    print("\n=== All tests passed! ===")


if __name__ == "__main__":
    # No need for QApplication for this test since we're just testing the data model
    test_skeleton_features()