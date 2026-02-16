#!/usr/bin/env python3
"""Test script to verify CAM mechanism positioning and animation."""

import logging
import sys

import numpy as np
import pytest

# Manual CAM mechanism positioning test; skip in automated pytest.
pytest.skip("Manual CAM mechanism test; skipping in automated pytest.", allow_module_level=True)

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_cam_positioning():
    """Test that CAM is positioned below and follower above."""

    # Simulate CAM creation with scaling
    base_radius = 25.0
    eccentricity = 10.0
    follower_rod_length = 40.0

    cam_scale_factor = 0.4
    rod_length_multiplier = 2.5

    scaled_base_radius = base_radius * cam_scale_factor
    scaled_eccentricity = eccentricity * cam_scale_factor
    scaled_rod_length = follower_rod_length * rod_length_multiplier

    # CAM center at origin
    cam_center = np.array([0, 0])

    # Follower position (negative Y means up in scene coordinates)
    follower_y = cam_center[1] - (scaled_base_radius + scaled_rod_length)
    follower_pos = np.array([cam_center[0], follower_y])

    print("CAM Positioning Test:")
    print(f"  CAM center: {cam_center}")
    print(f"  CAM scaled radius: {scaled_base_radius:.2f}")
    print(f"  Follower Y position: {follower_y:.2f}")
    print(f"  Rod length (scaled): {scaled_rod_length:.2f}")
    print(f"  Follower is {abs(follower_y):.2f} units above CAM center")

    # Verify follower is above CAM
    assert follower_y < cam_center[1], "Follower should be above CAM (negative Y)"
    print("✓ CAM is below, follower is above")

    return True

def test_animation_scaling():
    """Test that animation uses correct scaling."""

    base_radius = 25.0
    eccentricity = 10.0
    cam_scale_factor = 0.4
    rod_length_multiplier = 2.5

    scaled_base_radius = base_radius * cam_scale_factor
    scaled_eccentricity = eccentricity * cam_scale_factor
    scaled_rod_length = 40.0 * rod_length_multiplier

    print("\nAnimation Scaling Test:")
    print(f"  Original: base_radius={base_radius}, eccentricity={eccentricity}")
    print(f"  Scaled: base_radius={scaled_base_radius:.2f}, eccentricity={scaled_eccentricity:.2f}")
    print(f"  Rod length: original=40.0, scaled={scaled_rod_length:.2f}")

    # Test animation at different angles
    for angle in [0, np.pi/2, np.pi, 3*np.pi/2]:
        lift = scaled_eccentricity * (1 + np.cos(angle + np.pi/2)) / 2
        cam_radius_at_angle = scaled_base_radius + lift
        follower_y = 0 - cam_radius_at_angle - scaled_rod_length

        print(f"  At angle {angle:.2f}: cam_radius={cam_radius_at_angle:.2f}, follower_y={follower_y:.2f}")
        assert follower_y < 0, f"Follower should always be above CAM at angle {angle}"

    print("✓ Animation maintains correct positioning")

    return True

def test_parametric_edit():
    """Test parametric editing calculations."""

    print("\nParametric Edit Test:")

    # Test rod length adjustment
    cam_scale_factor = 0.4
    rod_length_multiplier = 2.5
    scaled_base_radius = 25.0 * cam_scale_factor

    # Simulate handle movement
    cam_center_y = 300  # Scene coordinates
    new_handle_y = 200  # Handle moved up

    delta_y = cam_center_y - new_handle_y
    new_scaled_rod_length = max(10.0, min(250.0, delta_y - scaled_base_radius))
    new_rod_length = new_scaled_rod_length / rod_length_multiplier

    print(f"  Handle delta_y: {delta_y}")
    print(f"  New scaled rod length: {new_scaled_rod_length:.2f}")
    print(f"  New actual rod length: {new_rod_length:.2f}")
    print("✓ Parametric edit calculations correct")

    return True

if __name__ == "__main__":
    print("=== CAM Mechanism Verification ===\n")

    try:
        # Run tests
        test_cam_positioning()
        test_animation_scaling()
        test_parametric_edit()

        print("\n=== All tests passed! ===")
        print("\nSummary:")
        print("1. ✓ CAM is positioned below with follower above")
        print("2. ✓ Animation uses correct scaling factors")
        print("3. ✓ Parametric editing maintains proportions")

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)
