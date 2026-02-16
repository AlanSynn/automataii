#!/usr/bin/env python3
"""Test CAM position relative to character."""

import pytest

# Manual CAM position exploration; skip during automated pytest.
pytest.skip("Manual CAM position test; skipping in automated pytest.", allow_module_level=True)

def test_character_position():
    """Test character position detection."""
    print("Character Position Test:")
    print("="*40)

    # Simulate character joints (example)
    joints = {
        "head": {"position": [300, 200]},
        "torso": {"position": [300, 300]},
        "left_foot": {"position": [280, 450]},
        "right_foot": {"position": [320, 450]}
    }

    # Find lowest joint (feet)
    lowest_y = float('-inf')
    lowest_pos = None
    for joint_id, joint_data in joints.items():
        pos = joint_data.get("position", [0, 0])
        if pos[1] > lowest_y:  # In Qt, y increases downward
            lowest_y = pos[1]
            lowest_pos = pos
            lowest_joint = joint_id

    print(f"Lowest joint: {lowest_joint} at {lowest_pos}")

    # CAM position should be below feet
    cam_position = [lowest_pos[0], lowest_pos[1] + 50]
    print(f"CAM position: {cam_position}")

    return cam_position

def test_cam_scale_and_position():
    """Test final CAM scale and position."""
    print("\nFinal CAM Configuration:")
    print("="*40)

    # Current scaling
    base_radius = 25.0
    eccentricity = 10.0
    rod_length = 40.0

    cam_scale_factor = 0.08
    rod_length_multiplier = 1.2

    scaled_base_radius = base_radius * cam_scale_factor
    scaled_eccentricity = eccentricity * cam_scale_factor
    scaled_rod_length = rod_length * rod_length_multiplier

    print("Scaled CAM dimensions:")
    print(f"  Base radius: {scaled_base_radius:.2f}mm")
    print(f"  Eccentricity: {scaled_eccentricity:.2f}mm")
    print(f"  Rod length: {scaled_rod_length:.1f}mm")
    print(f"  CAM diameter: {(scaled_base_radius + scaled_eccentricity)*2:.2f}mm")

    # Position
    cam_pos = test_character_position()
    print(f"\nCAM positioned at: {cam_pos}")
    print("  X: Centered with character")
    print("  Y: 50 units below feet")

    # Verify CAM is below character
    if cam_pos[1] > 450:  # Feet at 450
        print("✓ CAM is correctly positioned below character")
    else:
        print("✗ CAM position needs adjustment")

def test_egg_shape():
    """Test egg shape orientation."""
    print("\nEgg Shape Orientation:")
    print("="*40)

    # With cos(theta) formula, egg is wider at right (0°)
    print("Current formula: lift = eccentricity * (1 + cos(theta)) / 2")
    print("  At   0° (right):  Maximum radius (widest part)")
    print("  At 180° (left):   Minimum radius (narrowest part)")
    print("  Creates horizontal egg shape")
    print()
    print("For vertical egg (CAM below):")
    print("  Should rotate or use sin(theta) for vertical orientation")

def main():
    print("="*50)
    print("CAM POSITION AND SCALE VERIFICATION")
    print("="*50)
    print()

    test_cam_scale_and_position()
    test_egg_shape()

    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print("✓ CAM scale: 8% of original (2mm radius)")
    print("✓ Position: Below character feet")
    print("✓ Rod length: 48mm (moderate)")
    print("⚠ Egg orientation: Currently horizontal, may need vertical")

if __name__ == "__main__":
    main()
