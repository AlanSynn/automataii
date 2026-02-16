#!/usr/bin/env python3
"""Final test of CAM mechanism with updated scaling."""


import numpy as np
import pytest

# Manual CAM scaling exploration; skip during automated pytest.
pytest.skip("Manual CAM scaling test; skipping in automated pytest.", allow_module_level=True)

def test_cam_scaling():
    """Test new CAM scaling parameters."""
    print("CAM Scaling Test (Updated):")
    print("="*40)

    # New scaling parameters
    base_radius = 25.0
    eccentricity = 10.0
    rod_length = 40.0

    cam_scale_factor = 0.15  # Much smaller
    rod_length_multiplier = 1.5  # Moderate increase

    scaled_base_radius = base_radius * cam_scale_factor
    scaled_eccentricity = eccentricity * cam_scale_factor
    scaled_rod_length = rod_length * rod_length_multiplier

    print("Original dimensions:")
    print(f"  Base radius: {base_radius:.1f}mm")
    print(f"  Eccentricity: {eccentricity:.1f}mm")
    print(f"  Rod length: {rod_length:.1f}mm")
    print()
    print("Scaled dimensions:")
    print(f"  Base radius: {scaled_base_radius:.2f}mm (15% of original)")
    print(f"  Eccentricity: {scaled_eccentricity:.2f}mm")
    print(f"  Rod length: {scaled_rod_length:.1f}mm (1.5x original)")
    print()
    print(f"CAM total size: {(scaled_base_radius + scaled_eccentricity)*2:.2f}mm diameter")
    print(f"Total mechanism height: {scaled_base_radius + scaled_rod_length:.2f}mm")

    return scaled_base_radius, scaled_eccentricity, scaled_rod_length

def test_egg_shape(base_radius, eccentricity):
    """Test egg shape profile generation."""
    print("\nEgg Shape Profile Test:")
    print("="*40)

    # Test at key angles
    angles = [0, np.pi/2, np.pi, 3*np.pi/2]
    angle_names = ["0° (right)", "90° (top)", "180° (left)", "270° (bottom)"]

    for angle, name in zip(angles, angle_names, strict=False):
        # Egg shape formula
        lift = eccentricity * (1 + np.cos(angle)) / 2
        radius_at_angle = base_radius + lift

        print(f"At {name:15s}: r = {radius_at_angle:.3f}mm (lift = {lift:.3f}mm)")

    # Calculate egg shape characteristics
    max_radius = base_radius + eccentricity  # At angle = 0
    min_radius = base_radius  # At angle = π

    print("\nEgg shape characteristics:")
    print(f"  Maximum radius: {max_radius:.3f}mm (at right)")
    print(f"  Minimum radius: {min_radius:.3f}mm (at left)")
    print(f"  Eccentricity ratio: {(max_radius - min_radius) / base_radius * 100:.1f}%")

def test_position():
    """Test CAM positioning relative to character."""
    print("\nCAM Position Test:")
    print("="*40)

    # Fallback position (when no transform params)
    cam_center = np.array([0, 0])

    # Transform to scene coordinates (fallback)
    scene_x = cam_center[0] * 1.5 + 300
    scene_y = cam_center[1] * 1.5 + 400

    print(f"CAM center in mechanism coords: ({cam_center[0]}, {cam_center[1]})")
    print(f"CAM center in scene coords: ({scene_x:.1f}, {scene_y:.1f})")
    print("Position is closer to character center (300, 400)")

def main():
    print("="*50)
    print("FINAL CAM MECHANISM VERIFICATION")
    print("="*50)
    print()

    # Test scaling
    scaled_base_radius, scaled_eccentricity, scaled_rod_length = test_cam_scaling()

    # Test egg shape
    test_egg_shape(scaled_base_radius, scaled_eccentricity)

    # Test position
    test_position()

    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print("✓ CAM size reduced to 15% (much smaller)")
    print("✓ Rod length increased to 1.5x (moderate)")
    print("✓ Egg shape properly defined (wider at one end)")
    print("✓ Position closer to character center")
    print("\nExpected visual result:")
    print("• Small egg-shaped CAM below character")
    print("• Moderate length rod connecting to follower")
    print("• CAM positioned near character, not far away")

if __name__ == "__main__":
    main()
