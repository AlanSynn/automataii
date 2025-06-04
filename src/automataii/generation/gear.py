"""Module for generating gear mechanisms."""
import logging
import math
from typing import Optional, Dict, Any
from PyQt6.QtCore import QPointF, QLineF
from PyQt6.QtGui import QPainterPath

from .base_mechanism import BaseMechanism

# Placeholder for more sophisticated data structures
# from ...core.models import Gear, etc.

class Gear(BaseMechanism):
    """
    Generates gear mechanism data.
    """
    def __init__(self, name: str = "Gear Mechanism"):
        super().__init__(name, mechanism_type="Gear")

    def generate(
        self,
        center_pos: QPointF = QPointF(0,0), # Center of the first gear, or midpoint between gears
        r1: float = 30.0,
        r2: float = 20.0,
        num_teeth1: Optional[int] = None,
        num_teeth2: Optional[int] = None,
        gear_distance_offset: float = 0, # Additional distance between gear centers beyond r1+r2
        angle_deg1: float = 0 # Initial angle of gear1 (for drawing teeth)
    ) -> Optional[Dict[str, Any]]:
        """
        Generates data for a pair of simple spur gears.

        Args:
            center_pos: QPointF, reference position. If only one gear, its center.
                          If two, can be gear1's center or a reference for placing both.
            r1: Radius of the first gear.
            r2: Radius of the second gear. If 0 or None, only one gear is generated.
            num_teeth1: Number of teeth for gear 1. If None, estimated from radius.
            num_teeth2: Number of teeth for gear 2. If None, estimated from radius.
            gear_distance_offset: Additional distance to add between gear centers (r1+r2 + offset).
            angle_deg1: Initial rotation angle for gear 1 (affects tooth phase).

        Returns:
            A dictionary containing gear data, or None if inputs are invalid.
            Structure includes a list of gear dictionaries, each with center, radius, teeth, etc.
        """
        if r1 <= 0:
            return None

        gears_data_list = []

        # Estimate number of teeth if not provided (e.g., 1 tooth per 5-10 units of circumference)
        # Module (m) = Diameter / NumTeeth. Or NumTeeth = Pi * Diameter / (Pi * m)
        # Let's assume a default module or tooth size for estimation.
        # Pitch = Pi * Module. Roughly, tooth width ~ Pitch / 2.
        # Let tooth width be ~5-10 units. So, Circumference / (tooth_width * 2) = NumTeeth
        default_tooth_pitch_approx = 15 # Approximate pitch (circumferential distance per tooth)

        if num_teeth1 is None:
            num_teeth1 = max(3, int( (2 * math.pi * r1) / default_tooth_pitch_approx ))

        gear1_center = center_pos
        gear1_data = {
            "center": [gear1_center.x(), gear1_center.y()],
            "radius": r1,
            "num_teeth": num_teeth1,
            "tooth_height": r1 * 0.2, # Example, can be calculated from module later
            "angle_deg": angle_deg1,
            "name": "Gear 1"
        }
        gears_data_list.append(gear1_data)

        if r2 > 0: # Generate a second gear
            if num_teeth2 is None:
                num_teeth2 = max(3, int( (2 * math.pi * r2) / default_tooth_pitch_approx ))

            # Position second gear relative to the first
            # Assume they are meshing externally, typically along x-axis for default placement
            total_radius_sum = r1 + r2
            gear2_center_x = gear1_center.x() + total_radius_sum + gear_distance_offset
            gear2_center_y = gear1_center.y() # Align centers vertically for simple pair

            # Angle of gear2: if meshing, teeth should align.
            # If gear1 rotates by theta, gear2 rotates by -theta * (r1/r2) or -theta * (N1/N2)
            # For initial alignment, consider the phase. If gear1 has tooth at top (0 deg),
            # gear2 should have a valley or tooth appropriately. This is complex for exact mesh visuals.
            # For now, a simple angle offset might be enough for visuals.
            # If N1 teeth on G1, N2 on G2. Angle per tooth G1 = 360/N1. G2 = 360/N2.
            # Offset angle for G2 so teeth mesh: (360 / N1) / 2 for G1, then adjust G2.
            # Or simply angle_deg2 = -angle_deg1 * (r1/r2) or a fixed offset for visual.
            angle_deg2 = -angle_deg1 * (num_teeth1 / num_teeth2) + (180 / num_teeth2) # Initial phase offset

            gear2_data = {
                "center": [gear2_center_x, gear2_center_y],
                "radius": r2,
                "num_teeth": num_teeth2,
                "tooth_height": r2 * 0.2,
                "angle_deg": angle_deg2,
                "name": "Gear 2"
            }
            gears_data_list.append(gear2_data)

        return {
            "type": "gears",
            "name": "Generated Gear Pair" if r2 > 0 else "Generated Single Gear",
            "gears": gears_data_list,
            "thickness": min(r1, r2 if r2 > 0 else r1) * 0.3 # Example thickness based on smaller gear
        }

if __name__ == '__main__':
    print("--- Testing Gear Generation ---")
    gear_generator = Gear()
    print(f"Gear Generator Description: {gear_generator.get_description()}")

    # Test single gear
    single_gear = gear_generator.generate(center_pos=QPointF(0,0), r1=50, r2=0)
    if single_gear:
        print("\nSingle Gear Data:")
        for key, value in single_gear.items():
            if key == "gears":
                print(f"  {key}:")
                for i, g_data in enumerate(value):
                    print(f"    Gear {i+1}: {g_data}")
            else:
                print(f"  {key}: {value}")
    else:
        print("Failed to generate single gear.")

    # Test gear pair
    gear_pair_data = gear_generator.generate(
        center_pos=QPointF(-50, 50), r1=40, r2=25, num_teeth1=20, num_teeth2=12, angle_deg1=15
    )
    if gear_pair_data:
        print("\nGear Pair Data:")
        for key, value in gear_pair_data.items():
            if key == "gears":
                print(f"  {key}:")
                for i, g_data in enumerate(value):
                    print(f"    Gear {i+1}: {g_data}")
            else:
                print(f"  {key}: {value}")
    else:
        print("Failed to generate gear pair.")

    # Test with default teeth numbers
    gear_pair_default_teeth = gear_generator.generate(r1=60, r2=30)
    if gear_pair_default_teeth:
        print("\nGear Pair (Default Teeth) Data:")
        g1_info = gear_pair_default_teeth["gears"][0]
        g2_info = gear_pair_default_teeth["gears"][1]
        print(f"  Gear 1: Radius={g1_info['radius']}, Teeth={g1_info['num_teeth']}")
        print(f"  Gear 2: Radius={g2_info['radius']}, Teeth={g2_info['num_teeth']}")
    else:
        print("Failed to generate gear pair with default teeth.")
