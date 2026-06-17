#!/usr/bin/env python
"""Test if Pydantic model_dump includes all fields including bend_direction."""

import logging

from automataii.domain.skeleton import StandardizedJointModel, StandardizedSkeletonModel

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def test_model_dump():
    """Test if model_dump includes bend_direction field."""

    print("\n" + "=" * 60)
    print("PYDANTIC MODEL_DUMP TEST")
    print("=" * 60)

    # Create a joint with bend_direction
    joint = StandardizedJointModel(
        id="left_elbow_8",
        name="left_elbow",
        position=(60, 170),
        parent_id="left_shoulder_7",
        bend_direction=-1.0,  # Set to -1.0
    )

    print("\n1. Original joint model:")
    print(f"   bend_direction attribute: {joint.bend_direction}")

    # Dump to dict
    joint_dict = joint.model_dump()

    print("\n2. After model_dump:")
    print(f"   'bend_direction' in dict: {'bend_direction' in joint_dict}")
    print(f"   Value: {joint_dict.get('bend_direction')}")
    print(f"   Full dict: {joint_dict}")

    # Create a skeleton with the joint
    skeleton = StandardizedSkeletonModel(
        joints={"left_elbow_8": joint},
        root_joint_ids=[],
        hierarchy={},
    )

    print("\n3. Skeleton model:")
    print(f"   Joint bend_direction: {skeleton.joints['left_elbow_8'].bend_direction}")

    # Dump skeleton to dict
    skeleton_dict = skeleton.model_dump()

    print("\n4. After skeleton model_dump:")
    joint_from_dict = skeleton_dict.get("joints", {}).get("left_elbow_8", {})
    print(f"   'bend_direction' in joint dict: {'bend_direction' in joint_from_dict}")
    print(f"   Value: {joint_from_dict.get('bend_direction')}")

    # Test modifying bend_direction
    print("\n5. Modifying bend_direction:")
    skeleton.joints["left_elbow_8"].bend_direction = 1.0
    print(f"   New value: {skeleton.joints['left_elbow_8'].bend_direction}")

    skeleton_dict2 = skeleton.model_dump()
    joint_from_dict2 = skeleton_dict2.get("joints", {}).get("left_elbow_8", {})
    print(f"   After model_dump: {joint_from_dict2.get('bend_direction')}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_model_dump()
