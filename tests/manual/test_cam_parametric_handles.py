#!/usr/bin/env python3
"""Test CAM parametric handles functionality."""

def test_cam_handles():
    """Test the three CAM handles and their functions."""
    print("="*60)
    print("CAM PARAMETRIC HANDLES TEST")
    print("="*60)

    print("\n🔧 HANDLE CONFIGURATION:")
    print("-" * 40)

    print("\n1. CENTER HANDLE (Blue) - 🔵")
    print("   - Location: CAM center")
    print("   - Function: Move entire CAM mechanism")
    print("   - Behavior: Drags CAM + follower + rod together")
    print("   - Updates: cam_position coordinates")

    print("\n2. ROD HANDLE (Orange) - 🟠")
    print("   - Location: Follower position (top of rod)")
    print("   - Function: Adjust rod length")
    print("   - Behavior: Changes follower distance from CAM")
    print("   - Updates: follower_rod_length parameter")

    print("\n3. SHAPE HANDLE (Green) - 🟢")
    print("   - Location: CAM edge (rightmost point)")
    print("   - Function: Adjust CAM size and shape")
    print("   - Behavior: Changes base radius and eccentricity")
    print("   - Updates: base_radius and eccentricity parameters")

    print("\n" + "="*60)
    print("HANDLE CALCULATIONS:")
    print("-" * 40)

    # Test parameters
    base_radius = 25.0
    eccentricity = 10.0
    rod_length = 40.0
    cam_scale_factor = 1.5
    rod_length_multiplier = 0.8

    # Scaled values
    scaled_base_radius = base_radius * cam_scale_factor
    scaled_eccentricity = eccentricity * cam_scale_factor
    scaled_rod_length = rod_length * rod_length_multiplier

    print("\nBase Parameters:")
    print(f"  - Base Radius: {base_radius}mm")
    print(f"  - Eccentricity: {eccentricity}mm")
    print(f"  - Rod Length: {rod_length}mm")

    print("\nScaled Values:")
    print(f"  - Scaled Base Radius: {scaled_base_radius}mm")
    print(f"  - Scaled Eccentricity: {scaled_eccentricity}mm")
    print(f"  - Scaled Rod Length: {scaled_rod_length}mm")

    # Handle positions
    cam_center = [0, 0]
    rod_handle_y = -(scaled_base_radius + scaled_rod_length)
    shape_handle_x = scaled_base_radius + scaled_eccentricity

    print("\nHandle Positions (relative to CAM center):")
    print(f"  1. Center Handle: ({cam_center[0]}, {cam_center[1]})")
    print(f"  2. Rod Handle: (0, {rod_handle_y:.1f})")
    print(f"  3. Shape Handle: ({shape_handle_x:.1f}, 0)")

    print("\n" + "="*60)
    print("DRAG BEHAVIORS:")
    print("-" * 40)

    print("\n1. DRAGGING CENTER HANDLE:")
    print("   - New position: (300, 500) -> (350, 520)")
    print("   - Effect: All components move by (+50, +20)")
    print("   - CAM center: (350, 520)")
    print(f"   - Follower: (350, {520 + rod_handle_y:.1f})")
    print(f"   - Shape handle: ({350 + shape_handle_x:.1f}, 520)")

    print("\n2. DRAGGING ROD HANDLE:")
    print(f"   - Original: (0, {rod_handle_y:.1f})")
    print("   - Drag up by 20 units")
    new_rod_y = rod_handle_y - 20
    new_rod_length = abs(new_rod_y) - scaled_base_radius
    new_unscaled_rod = new_rod_length / rod_length_multiplier
    print(f"   - New position: (0, {new_rod_y:.1f})")
    print(f"   - New scaled rod length: {new_rod_length:.1f}mm")
    print(f"   - New unscaled rod length: {new_unscaled_rod:.1f}mm")
    print("   - Effect: Follower moves closer/farther from CAM")

    print("\n3. DRAGGING SHAPE HANDLE:")
    print(f"   - Original: ({shape_handle_x:.1f}, 0)")
    print("   - Drag outward by 15 units")
    new_shape_x = shape_handle_x + 15
    new_max_radius = new_shape_x / cam_scale_factor
    new_base = new_max_radius * 0.77
    new_ecc = new_max_radius * 0.23
    print(f"   - New position: ({new_shape_x:.1f}, 0)")
    print(f"   - New max radius (unscaled): {new_max_radius:.1f}mm")
    print(f"   - New base radius: {new_base:.1f}mm")
    print(f"   - New eccentricity: {new_ecc:.1f}mm")
    print("   - Effect: CAM becomes larger/smaller")

    print("\n" + "="*60)
    print("HANDLE VISUAL DESIGN:")
    print("-" * 40)
    print("  🔵 Blue Handle: #2196f3 (Material Blue)")
    print("  🟠 Orange Handle: #ff9800 (Material Orange)")
    print("  🟢 Green Handle: #4caf50 (Material Green)")
    print("\nTooltips:")
    print("  - Center: 'Drag to move entire CAM mechanism'")
    print("  - Rod: 'Drag to adjust rod length'")
    print("  - Shape: 'Drag to adjust CAM size and shape'")

    print("\n" + "="*60)

if __name__ == "__main__":
    test_cam_handles()
