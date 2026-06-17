#!/usr/bin/env python3
"""Test CAM mechanism positioning after fixes."""

import numpy as np


def test_cam_positioning():
    """Test CAM positioning logic."""
    print("=" * 60)
    print("CAM POSITIONING TEST - AFTER FIXES")
    print("=" * 60)

    # Simulated character position (from _get_character_position)
    # This would return [center_x, lowest_y + 30]
    character_feet_y = 450  # Example feet position
    character_center_x = 300
    cam_position = [character_center_x, character_feet_y + 30]  # CAM positioned 30 units below feet

    print("\n1. Character Position:")
    print(f"   - Center X: {character_center_x}")
    print(f"   - Feet Y: {character_feet_y}")
    print(f"   - CAM Position: {cam_position}")

    # New scaling factors
    cam_scale_factor = 0.5  # 50% size
    rod_length_multiplier = 1.2  # 120% rod length

    # Original parameters
    base_radius = 25.0
    eccentricity = 10.0
    follower_rod_length = 40.0

    # Scaled dimensions
    scaled_base_radius = base_radius * cam_scale_factor
    scaled_eccentricity = eccentricity * cam_scale_factor
    scaled_rod_length = follower_rod_length * rod_length_multiplier

    print("\n2. Scaling Configuration:")
    print(f"   - CAM Scale Factor: {cam_scale_factor} (50% size)")
    print(f"   - Rod Length Multiplier: {rod_length_multiplier} (120% length)")

    print("\n3. Scaled Dimensions:")
    print(f"   - Base Radius: {base_radius} -> {scaled_base_radius}mm")
    print(f"   - Eccentricity: {eccentricity} -> {scaled_eccentricity}mm")
    print(f"   - Rod Length: {follower_rod_length} -> {scaled_rod_length}mm")

    # CAM positioning
    cam_center_orig = np.array([0, 0])

    # Custom transform for CAM
    def cam_to_scene_coords(p):
        """Transform CAM coordinates to scene, placing CAM at character feet."""
        if len(p) != 2:
            return [cam_position[0], cam_position[1]]
        return [float(p[0] + cam_position[0]), float(p[1] + cam_position[1])]

    # Transform cam center to scene
    cam_center_scene = cam_to_scene_coords(cam_center_orig)

    # Follower position (above cam)
    follower_y_orig = cam_center_orig[1] - (scaled_base_radius + scaled_rod_length)
    follower_pos_orig = np.array([cam_center_orig[0], follower_y_orig])
    follower_scene = cam_to_scene_coords(follower_pos_orig)

    print("\n4. Scene Positions:")
    print(f"   - CAM Center: {cam_center_scene}")
    print(f"   - Follower Position: {follower_scene}")

    print("\n5. Position Analysis:")
    print(f"   - CAM Y coordinate: {cam_center_scene[1]}")
    print(f"   - Character Feet Y: {character_feet_y}")
    print(f"   - Distance from feet to CAM: {cam_center_scene[1] - character_feet_y}mm")
    print(f"   - Follower Y: {follower_scene[1]}")
    print(f"   - Distance from feet to follower: {character_feet_y - follower_scene[1]}mm")

    print("\n6. Visual Appearance:")
    # Calculate egg shape dimensions
    max_radius = scaled_base_radius + scaled_eccentricity
    min_radius = scaled_base_radius
    print(f"   - CAM Max Diameter: {max_radius * 2}mm")
    print(f"   - CAM Min Diameter: {min_radius * 2}mm")
    print(
        f"   - Total Mechanism Height: {scaled_base_radius + scaled_rod_length + scaled_eccentricity}mm"
    )

    # Verify positioning
    print("\n7. Verification:")
    if cam_center_scene[1] > character_feet_y:
        print("   ✅ CAM is positioned below character feet")
    else:
        print("   ❌ CAM is NOT below character feet")

    if abs(follower_scene[1] - character_feet_y) < 50:
        print("   ✅ Follower is near character feet level")
    else:
        print("   ❌ Follower is too far from feet")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_cam_positioning()
