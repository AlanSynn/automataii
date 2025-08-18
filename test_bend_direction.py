#!/usr/bin/env python
"""Test script to verify bend direction changes are working"""

import sys
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF
from automataii.core.skeleton_manager import SkeletonManager
from automataii.kinematics.ik_manager import IKManager
import logging

logging.basicConfig(level=logging.DEBUG)

def test_bend_direction():
    app = QApplication(sys.argv)
    
    # Create managers
    skeleton_manager = SkeletonManager()
    ik_manager = IKManager(main_window_ref=None)  # Pass None for testing
    ik_manager.skeleton_manager = skeleton_manager
    
    # Create a simple skeleton
    skeleton_data = {
        "joints": {
            "root_0": {"position": [400, 400]},
            "left_shoulder_7": {"position": [500, 300]},
            "left_elbow_8": {"position": [580, 350], "bend_direction": 1.0},
            "left_hand_9": {"position": [660, 400]},
        },
        "bones": [
            {"parent": "root_0", "child": "left_shoulder_7"},
            {"parent": "left_shoulder_7", "child": "left_elbow_8"},
            {"parent": "left_elbow_8", "child": "left_hand_9"},
        ]
    }
    
    # Update skeleton  
    skeleton_manager.load_skeleton_from_dict(skeleton_data, source_format="standard")
    
    # Test IK with default bend direction
    print("\n=== Testing with bend_direction = 1.0 ===")
    ik_manager.on_skeleton_data_updated_from_manager(skeleton_data)
    ik_manager.initialize_ik_solver()
    
    # Simulate a target position
    target = QPointF(650, 250)
    result = ik_manager._solve_two_bone_ik(
        QPointF(500, 300),  # shoulder
        target,
        80,  # upper arm length
        80,  # lower arm length
        "left_shoulder_7"
    )
    if result:
        print(f"Elbow position: {result[0].x():.1f}, {result[0].y():.1f}")
        print(f"Hand position: {result[1].x():.1f}, {result[1].y():.1f}")
    
    # Change bend direction
    print("\n=== Changing bend_direction to -1.0 ===")
    skeleton_data["joints"]["left_elbow_8"]["bend_direction"] = -1.0
    skeleton_manager.load_skeleton_from_dict(skeleton_data, source_format="standard")
    ik_manager.on_skeleton_data_updated_from_manager(skeleton_data)
    
    # Test again with inverted bend direction
    result = ik_manager._solve_two_bone_ik(
        QPointF(500, 300),  # shoulder
        target,
        80,  # upper arm length
        80,  # lower arm length
        "left_shoulder_7"
    )
    if result:
        print(f"Elbow position: {result[0].x():.1f}, {result[0].y():.1f}")
        print(f"Hand position: {result[1].x():.1f}, {result[1].y():.1f}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_bend_direction()