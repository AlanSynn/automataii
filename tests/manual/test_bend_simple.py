#!/usr/bin/env python
"""Simple test to check bend direction issue."""

import logging

from PyQt6.QtCore import QPointF

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def test_joint_id_mapping():
    """Test joint ID mapping logic."""

    print("\n" + "=" * 60)
    print("JOINT ID MAPPING TEST")
    print("=" * 60)

    # Simulate joint_map
    joint_map = {
        "hip": "hip_0",
        "left_shoulder": "left_shoulder_7",
        "left_elbow": "left_elbow_8",
        "left_hand": "left_hand_9",
    }

    # Simulate sim_joints_config
    sim_joints_config = {
        "hip_0": {"position": QPointF(100, 200)},
        "left_shoulder_7": {"position": QPointF(80, 150)},
        "left_elbow_8": {"position": QPointF(60, 170)},
        "left_hand_9": {"position": QPointF(40, 190)},
    }

    # Simulate _get_standardized_joint_id function
    def _get_standardized_joint_id(abstract_name):
        if abstract_name in joint_map:
            return joint_map[abstract_name]
        if abstract_name in sim_joints_config:
            return abstract_name
        return None

    # Test cases
    test_cases = [
        ("left_elbow", "left_elbow_8"),
        ("left_shoulder", "left_shoulder_7"),
        ("left_elbow_8", "left_elbow_8"),  # Already standardized
        ("nonexistent", None),
    ]

    print("\n1. Testing _get_standardized_joint_id:")
    for abstract_name, expected in test_cases:
        result = _get_standardized_joint_id(abstract_name)
        status = "✓" if result == expected else "✗"
        print(f"   {status} '{abstract_name}' -> '{result}' (expected: '{expected}')")

    print("\n2. Testing bend_direction storage:")
    sim_joint_bend_directions = {}

    # Store with standardized ID (as done when user clicks)
    sim_joint_bend_directions["left_elbow_8"] = -1.0
    print("   Stored: 'left_elbow_8' = -1.0")

    # Look up with abstract name (as done in initialize_ik_solver)
    abstract_name = "left_elbow"
    std_id = _get_standardized_joint_id(abstract_name)
    print(f"   Lookup: '{abstract_name}' -> standardized ID: '{std_id}'")

    if std_id in sim_joint_bend_directions:
        bend_dir = sim_joint_bend_directions[std_id]
        print(f"   ✓ Found bend_direction: {bend_dir}")
    else:
        print(f"   ✗ bend_direction not found for '{std_id}'")

    print("\n3. Testing two-way storage:")
    sim_joint_bend_directions.clear()

    # Store with both keys (as should be done in initialize_ik_solver)
    abstract_name = "left_elbow"
    std_id = _get_standardized_joint_id(abstract_name)
    bend_dir = -1.0

    sim_joint_bend_directions[abstract_name] = bend_dir
    sim_joint_bend_directions[std_id] = bend_dir
    print(f"   Stored with both keys: '{abstract_name}' = {bend_dir}, '{std_id}' = {bend_dir}")

    # Test lookup with both keys
    for key in [abstract_name, std_id, "left_elbow", "left_elbow_8"]:
        if key in sim_joint_bend_directions:
            print(f"   ✓ Found with key '{key}': {sim_joint_bend_directions[key]}")
        else:
            print(f"   ✗ Not found with key '{key}'")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_joint_id_mapping()
