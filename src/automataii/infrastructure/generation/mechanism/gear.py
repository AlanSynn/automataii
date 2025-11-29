"""Module for generating gear mechanisms."""

import logging
import math
from typing import Any

from PyQt6.QtCore import QPointF

from automataii.infrastructure.generation.mechanism.base import BaseMechanism

logger = logging.getLogger(__name__)

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
        center_pos: QPointF = QPointF(
            0, 0
        ),  # Center of the first gear, or midpoint between gears
        r1: float = 30.0,
        r2: float = 20.0,
        num_teeth1: int | None = None,
        num_teeth2: int | None = None,
        gear_distance_offset: float = 0,  # Additional distance between gear centers beyond r1+r2
        angle_deg1: float = 0,  # Initial angle of gear1 (for drawing teeth)
    ) -> dict[str, Any] | None:
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
        default_tooth_pitch_approx = (
            15  # Approximate pitch (circumferential distance per tooth)
        )

        if num_teeth1 is None:
            num_teeth1 = max(3, int((2 * math.pi * r1) / default_tooth_pitch_approx))

        gear1_center = center_pos
        gear1_data = {
            "center": [gear1_center.x(), gear1_center.y()],
            "radius": r1,
            "num_teeth": num_teeth1,
            "tooth_height": r1 * 0.2,  # Example, can be calculated from module later
            "angle_deg": angle_deg1,
            "name": "Gear 1",
        }
        gears_data_list.append(gear1_data)

        if r2 > 0:  # Generate a second gear
            if num_teeth2 is None:
                num_teeth2 = max(
                    3, int((2 * math.pi * r2) / default_tooth_pitch_approx)
                )

            # Position second gear relative to the first
            # Assume they are meshing externally, typically along x-axis for default placement
            total_radius_sum = r1 + r2
            gear2_center_x = gear1_center.x() + total_radius_sum + gear_distance_offset
            gear2_center_y = (
                gear1_center.y()
            )  # Align centers vertically for simple pair

            # Angle of gear2: if meshing, teeth should align.
            # If gear1 rotates by theta, gear2 rotates by -theta * (r1/r2) or -theta * (N1/N2)
            # For initial alignment, consider the phase. If gear1 has tooth at top (0 deg),
            # gear2 should have a valley or tooth appropriately. This is complex for exact mesh visuals.
            # For now, a simple angle offset might be enough for visuals.
            # If N1 teeth on G1, N2 on G2. Angle per tooth G1 = 360/N1. G2 = 360/N2.
            # Offset angle for G2 so teeth mesh: (360 / N1) / 2 for G1, then adjust G2.
            # Or simply angle_deg2 = -angle_deg1 * (r1/r2) or a fixed offset for visual.
            angle_deg2 = -angle_deg1 * (num_teeth1 / num_teeth2) + (
                180 / num_teeth2
            )  # Initial phase offset

            gear2_data = {
                "center": [gear2_center_x, gear2_center_y],
                "radius": r2,
                "num_teeth": num_teeth2,
                "tooth_height": r2 * 0.2,
                "angle_deg": angle_deg2,
                "name": "Gear 2",
            }
            gears_data_list.append(gear2_data)

        return {
            "type": "gears",
            "name": "Generated Gear Pair" if r2 > 0 else "Generated Single Gear",
            "gears": gears_data_list,
            "thickness": min(r1, r2 if r2 > 0 else r1)
            * 0.3,  # Example thickness based on smaller gear
        }


if __name__ == "__main__":
    print("--- Testing Gear Generation ---")
    gear_generator = Gear()
    print(f"Gear Generator Description: {gear_generator.get_description()}")

    # Test single gear
    single_gear = gear_generator.generate(center_pos=QPointF(0, 0), r1=50, r2=0)
    if single_gear:
        print("\nSingle Gear Data:")
        for key, value in single_gear.items():
            if key == "gears":
                print(f"  {key}:")
                for i, g_data in enumerate(value):
                    print(f"    Gear {i + 1}: {g_data}")
            else:
                print(f"  {key}: {value}")
    else:
        print("Failed to generate single gear.")

    # Test gear pair
    gear_pair_data = gear_generator.generate(
        center_pos=QPointF(-50, 50),
        r1=40,
        r2=25,
        num_teeth1=20,
        num_teeth2=12,
        angle_deg1=15,
    )
    if gear_pair_data:
        print("\nGear Pair Data:")
        for key, value in gear_pair_data.items():
            if key == "gears":
                print(f"  {key}:")
                for i, g_data in enumerate(value):
                    print(f"    Gear {i + 1}: {g_data}")
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


class GearGenerator:
    """Generator for gear mechanism SVG blueprints."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def generate_svg(self, gear_data: dict[str, Any]) -> str:
        """
        Generate SVG representation of gear mechanism for blueprints.

        Args:
            gear_data: Dictionary containing gear mechanism data

        Returns:
            str: SVG content for the gear mechanism
        """
        try:
            # Extract gear parameters with defaults
            center = gear_data.get('center', [0, 0])
            radius = gear_data.get('radius', 30.0)
            num_teeth = gear_data.get('num_teeth', 12)
            tooth_height = gear_data.get('tooth_height', radius * 0.2)
            angle_deg = gear_data.get('angle_deg', 0)
            gear_name = gear_data.get('name', 'Gear')

            # Generate gear teeth path
            teeth_path = self._generate_gear_teeth_path(
                center[0], center[1], radius, num_teeth, tooth_height, angle_deg
            )

            # Calculate additional technical parameters
            module = (radius * 2) / num_teeth  # Gear module
            outer_radius = radius + tooth_height
            root_radius = radius - tooth_height * 0.3
            bore_radius = radius * 0.15  # Shaft hole

            # Create comprehensive technical drawing
            svg_content = f'''
            <g class="gear-mechanism">
                <!-- Title and part number -->
                <text x="{center[0]}" y="{center[1] - outer_radius - 30}"
                      font-family="Arial" font-size="12" font-weight="bold" text-anchor="middle">{gear_name}</text>
                <text x="{center[0]}" y="{center[1] - outer_radius - 15}"
                      font-family="Arial" font-size="8" text-anchor="middle">Part No: GEAR-{num_teeth}T-M{module:.1f}</text>

                <!-- Root circle (cutting guideline) -->
                <circle cx="{center[0]}" cy="{center[1]}" r="{root_radius}"
                        fill="none" stroke="#888" stroke-width="0.5" stroke-dasharray="2,2"/>

                <!-- Pitch circle (reference) -->
                <circle cx="{center[0]}" cy="{center[1]}" r="{radius}"
                        fill="none" stroke="blue" stroke-width="0.5" stroke-dasharray="3,3"/>

                <!-- Gear teeth (cutting outline) -->
                <path d="{teeth_path}" fill="none" stroke="red" stroke-width="2"/>

                <!-- Center bore hole -->
                <circle cx="{center[0]}" cy="{center[1]}" r="{bore_radius}"
                        fill="none" stroke="black" stroke-width="1.5"/>

                <!-- Keyway (if applicable) -->
                <rect x="{center[0] - bore_radius * 0.3}" y="{center[1] - bore_radius}"
                      width="{bore_radius * 0.6}" height="{bore_radius * 2}"
                      fill="none" stroke="black" stroke-width="1"/>

                <!-- Manufacturing notes with anti-overlap positioning -->
                <g class="manufacturing-notes">
                    <rect x="{center[0] + outer_radius + 15}" y="{center[1] - 50}"
                          width="160" height="85" fill="white" stroke="#ddd" stroke-width="0.5" rx="2"/>
                    <text x="{center[0] + outer_radius + 20}" y="{center[1] - 35}"
                          font-family="Arial" font-size="8" font-weight="bold">Manufacturing Specs:</text>
                    <text x="{center[0] + outer_radius + 25}" y="{center[1] - 20}"
                          font-family="Arial" font-size="7">• Material: 3mm Plywood/Acrylic</text>
                    <text x="{center[0] + outer_radius + 25}" y="{center[1] - 8}"
                          font-family="Arial" font-size="7">• Cut on Red Lines</text>
                    <text x="{center[0] + outer_radius + 25}" y="{center[1] + 4}"
                          font-family="Arial" font-size="7">• Tolerance: ±0.1mm</text>
                    <text x="{center[0] + outer_radius + 25}" y="{center[1] + 16}"
                          font-family="Arial" font-size="7">• Module: {module:.2f}mm</text>
                    <text x="{center[0] + outer_radius + 25}" y="{center[1] + 28}"
                          font-family="Arial" font-size="7">• Pressure Angle: 20°</text>
                </g>

                <!-- Dimension lines and measurements -->
                <g class="dimensions">
                    <!-- Overall diameter -->
                    <line x1="{center[0] - outer_radius - 15}" y1="{center[1]}"
                          x2="{center[0] + outer_radius + 15}" y2="{center[1]}"
                          stroke="#666" stroke-width="0.5"/>
                    <line x1="{center[0] - outer_radius - 15}" y1="{center[1] - 5}"
                          x2="{center[0] - outer_radius - 15}" y2="{center[1] + 5}"
                          stroke="#666" stroke-width="0.5"/>
                    <line x1="{center[0] + outer_radius + 15}" y1="{center[1] - 5}"
                          x2="{center[0] + outer_radius + 15}" y2="{center[1] + 5}"
                          stroke="#666" stroke-width="0.5"/>
                    <text x="{center[0]}" y="{center[1] + outer_radius + 35}"
                          font-family="Arial" font-size="9" text-anchor="middle" font-weight="bold">
                          Ø{outer_radius * 2:.1f}mm OD ({num_teeth} teeth)
                    </text>

                    <!-- Pitch diameter -->
                    <text x="{center[0]}" y="{center[1] + outer_radius + 50}"
                          font-family="Arial" font-size="8" text-anchor="middle">
                          Ø{radius * 2:.1f}mm PCD (Pitch Circle)
                    </text>

                    <!-- Bore diameter -->
                    <line x1="{center[0] - bore_radius}" y1="{center[1] - outer_radius - 5}"
                          x2="{center[0] + bore_radius}" y2="{center[1] - outer_radius - 5}"
                          stroke="#666" stroke-width="0.5"/>
                    <text x="{center[0]}" y="{center[1] - outer_radius - 10}"
                          font-family="Arial" font-size="8" text-anchor="middle">
                          Ø{bore_radius * 2:.1f}mm BORE
                    </text>
                </g>

                <!-- Assembly reference marks -->
                <g class="assembly-marks">
                    <circle cx="{center[0]}" cy="{center[1] - radius}" r="1" fill="green"/>
                    <text x="{center[0] + 5}" y="{center[1] - radius + 3}"
                          font-family="Arial" font-size="6">TDC</text>
                </g>
            </g>
            '''

            return svg_content.strip()

        except Exception as e:
            self.logger.error(f"Failed to generate gear SVG: {e}")
            return '<text x="0" y="0" font-family="Arial" font-size="10">Error: Failed to generate gear</text>'

    def _generate_gear_teeth_path(self, cx: float, cy: float, radius: float,
                                 num_teeth: int, tooth_height: float, angle_deg: float) -> str:
        """Generate SVG path for gear teeth."""
        if num_teeth < 3:
            return ""  # Not enough teeth to draw

        angle_per_tooth = 360.0 / num_teeth
        outer_radius = radius + tooth_height

        path_data = ""

        for i in range(num_teeth):
            # Calculate angles for this tooth
            base_angle = angle_deg + i * angle_per_tooth
            tooth_start = math.radians(base_angle - angle_per_tooth * 0.4)
            tooth_mid1 = math.radians(base_angle - angle_per_tooth * 0.1)
            tooth_mid2 = math.radians(base_angle + angle_per_tooth * 0.1)
            tooth_end = math.radians(base_angle + angle_per_tooth * 0.4)

            # Points on inner circle (gear base)
            x1 = cx + radius * math.cos(tooth_start)
            y1 = cy + radius * math.sin(tooth_start)
            x4 = cx + radius * math.cos(tooth_end)
            y4 = cy + radius * math.sin(tooth_end)

            # Points on outer circle (tooth tips)
            x2 = cx + outer_radius * math.cos(tooth_mid1)
            y2 = cy + outer_radius * math.sin(tooth_mid1)
            x3 = cx + outer_radius * math.cos(tooth_mid2)
            y3 = cy + outer_radius * math.sin(tooth_mid2)

            if i == 0:
                path_data += f"M {x1:.2f} {y1:.2f} "
            else:
                path_data += f"L {x1:.2f} {y1:.2f} "

            # Draw tooth profile
            path_data += f"L {x2:.2f} {y2:.2f} L {x3:.2f} {y3:.2f} L {x4:.2f} {y4:.2f} "

        path_data += "Z"  # Close the path
        return path_data
