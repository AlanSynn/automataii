"""
Planetary Gear Blueprint Generator Module

This module provides the PlanetaryGearBlueprintGenerator class for generating
detailed manufacturing blueprints for planetary gear mechanisms.

Classes:
    PlanetaryGearBlueprintGenerator: Generates planetary gear system blueprints
"""

import math
from typing import Any, SupportsFloat, SupportsIndex, cast

from .generator import BlueprintGenerator

__all__ = ["PlanetaryGearBlueprintGenerator"]


def _finite_float(value: object, default: float) -> float:
    try:
        result = float(cast(str | bytes | bytearray | SupportsFloat | SupportsIndex, value))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def _planet_count(params: dict[str, Any]) -> int:
    raw_value = params.get("planet_count", params.get("num_planets", 1))
    return min(max(int(round(_finite_float(raw_value, 1.0))), 1), 4)


class PlanetaryGearBlueprintGenerator(BlueprintGenerator):
    """
    Blueprint generator for planetary gear mechanisms.

    Generates detailed manufacturing documentation for planetary gear systems
    including sun gear, planet gears, ring gear, and carrier assembly.
    """

    def __init__(self) -> None:
        """Initialize planetary gear blueprint generator."""
        super().__init__("planetary_gear")

    def _generate_front_view(self, mechanism_data: dict[str, Any]) -> None:
        """Generate front view of planetary gear system."""
        viewport = self.viewports["front"]
        params = mechanism_data.get("params", {})

        # Extract parameters
        r_sun = params.get("r_sun", 30) * viewport.scale
        r_planet = params.get("r_planet", 20) * viewport.scale
        r_carrier = params.get("r_carrier", r_sun + r_planet) * viewport.scale
        num_planets = _planet_count(params)
        module = params.get("module", 2)
        pressure_angle = params.get("pressure_angle", 20)

        cx = viewport.x + viewport.width / 2
        cy = viewport.y + viewport.height / 2

        # Calculate ring gear radius
        r_ring = r_sun + 2 * r_planet

        # Ring gear (outer)
        self._add_gear_teeth(
            cx, cy, r_ring, int(r_ring / module), module, pressure_angle, internal=True
        )

        # Sun gear (center)
        self._add_gear_teeth(
            cx, cy, r_sun, int(r_sun / module), module, pressure_angle, internal=False
        )

        # Planet gears
        for i in range(num_planets):
            angle = 2 * math.pi * i / num_planets
            px = cx + r_carrier * math.cos(angle)
            py = cy + r_carrier * math.sin(angle)

            self._add_gear_teeth(
                px, py, r_planet, int(r_planet / module), module, pressure_angle, internal=False
            )

            # Planet carrier arm
            self.svg_elements.append(f'''
                <line x1="{cx}" y1="{cy}" x2="{px}" y2="{py}"
                      stroke="black" stroke-width="2" opacity="0.5"/>
            ''')

            # Planet bearing
            self.svg_elements.append(f'''
                <circle cx="{px}" cy="{py}" r="3"
                        fill="none" stroke="black" stroke-width="1"/>
            ''')

        # Sun gear center bore
        bore_radius = r_sun * 0.2
        self.svg_elements.append(f'''
            <circle cx="{cx}" cy="{cy}" r="{bore_radius}"
                    fill="none" stroke="black" stroke-width="1.5"/>
        ''')

        # Keyway on sun gear
        self.svg_elements.append(f'''
            <rect x="{cx - bore_radius * 0.3}" y="{cy - bore_radius}"
                  width="{bore_radius * 0.6}" height="{bore_radius * 2}"
                  fill="none" stroke="black" stroke-width="1"/>
        ''')

        # Carrier center hub
        hub_radius = r_sun * 0.4
        self.svg_elements.append(f'''
            <circle cx="{cx}" cy="{cy}" r="{hub_radius}"
                    fill="none" stroke="black" stroke-width="1"
                    stroke-dasharray="3,2" opacity="0.7"/>
        ''')

        # View label
        self.svg_elements.append(f'''
            <text x="{cx}" y="{viewport.y + 20}"
                  font-family="Arial" font-size="12" font-weight="bold"
                  text-anchor="middle">FRONT VIEW</text>
        ''')

    def _generate_top_view(self, mechanism_data: dict[str, Any]) -> None:
        """Generate top view showing thickness and stack arrangement."""
        viewport = self.viewports["top"]
        params = mechanism_data.get("params", {})

        cx = viewport.x + viewport.width / 2
        cy = viewport.y + viewport.height / 2

        # Component thicknesses
        gear_thickness = params.get("gear_thickness", 10) * viewport.scale
        carrier_thickness = params.get("carrier_thickness", 8) * viewport.scale
        total_width = gear_thickness * 3 + carrier_thickness * 2  # Stacked arrangement

        # Draw stacked components
        y_offset = cy - total_width / 2

        # Ring gear layer
        self.svg_elements.append(f'''
            <rect x="{viewport.x + 20}" y="{y_offset}"
                  width="{viewport.width - 40}" height="{gear_thickness}"
                  fill="none" stroke="black" stroke-width="1.5"/>
            <text x="{viewport.x + 25}" y="{y_offset + gear_thickness / 2 + 3}"
                  font-family="Arial" font-size="10">Ring Gear</text>
        ''')
        y_offset += gear_thickness

        # Carrier plate 1
        self.svg_elements.append(f'''
            <rect x="{viewport.x + 30}" y="{y_offset}"
                  width="{viewport.width - 60}" height="{carrier_thickness}"
                  fill="none" stroke="black" stroke-width="1"/>
            <text x="{viewport.x + 35}" y="{y_offset + carrier_thickness / 2 + 3}"
                  font-family="Arial" font-size="10">Carrier Top</text>
        ''')
        y_offset += carrier_thickness

        # Gears layer (sun + planets)
        self.svg_elements.append(f'''
            <rect x="{viewport.x + 20}" y="{y_offset}"
                  width="{viewport.width - 40}" height="{gear_thickness}"
                  fill="none" stroke="black" stroke-width="1.5"/>
            <text x="{viewport.x + 25}" y="{y_offset + gear_thickness / 2 + 3}"
                  font-family="Arial" font-size="10">Sun & Planets</text>
        ''')
        y_offset += gear_thickness

        # Carrier plate 2
        self.svg_elements.append(f'''
            <rect x="{viewport.x + 30}" y="{y_offset}"
                  width="{viewport.width - 60}" height="{carrier_thickness}"
                  fill="none" stroke="black" stroke-width="1"/>
            <text x="{viewport.x + 35}" y="{y_offset + carrier_thickness / 2 + 3}"
                  font-family="Arial" font-size="10">Carrier Bottom</text>
        ''')

        # View label
        self.svg_elements.append(f'''
            <text x="{cx}" y="{viewport.y + 20}"
                  font-family="Arial" font-size="12" font-weight="bold"
                  text-anchor="middle">TOP VIEW - ASSEMBLY STACK</text>
        ''')

    def _generate_side_view(self, mechanism_data: dict[str, Any]) -> None:
        """Generate side view showing shaft arrangements."""
        viewport = self.viewports["side"]
        params = mechanism_data.get("params", {})

        cx = viewport.x + viewport.width / 2
        cy = viewport.y + viewport.height / 2

        # Extract dimensions
        r_sun = params.get("r_sun", 30) * viewport.scale
        r_planet = params.get("r_planet", 20) * viewport.scale
        params.get("r_carrier", r_sun + r_planet) * viewport.scale
        shaft_length = params.get("shaft_length", 50) * viewport.scale

        # Draw side profile
        # Main housing
        housing_width = (r_sun + 2 * r_planet) * 2.2
        housing_height = shaft_length

        self.svg_elements.append(f'''
            <rect x="{cx - housing_width / 2}" y="{cy - housing_height / 2}"
                  width="{housing_width}" height="{housing_height}"
                  fill="none" stroke="black" stroke-width="2" rx="5"/>
        ''')

        # Input shaft (sun gear)
        self.svg_elements.append(f'''
            <line x1="{cx}" y1="{cy - housing_height / 2 - 20}"
                  x2="{cx}" y2="{cy - housing_height / 2}"
                  stroke="black" stroke-width="3"/>
            <text x="{cx + 10}" y="{cy - housing_height / 2 - 10}"
                  font-family="Arial" font-size="10">Input</text>
        ''')

        # Output shaft (carrier)
        self.svg_elements.append(f'''
            <line x1="{cx}" y1="{cy + housing_height / 2}"
                  x2="{cx}" y2="{cy + housing_height / 2 + 20}"
                  stroke="black" stroke-width="4"/>
            <text x="{cx + 10}" y="{cy + housing_height / 2 + 15}"
                  font-family="Arial" font-size="10">Output</text>
        ''')

        # Bearings
        bearing_positions = [cy - housing_height / 2 + 10, cy + housing_height / 2 - 10]

        for y_pos in bearing_positions:
            self.svg_elements.append(f'''
                <rect x="{cx - 15}" y="{y_pos - 5}"
                      width="30" height="10"
                      fill="none" stroke="black" stroke-width="1"/>
                <text x="{cx - 40}" y="{y_pos + 3}"
                      font-family="Arial" font-size="8">Bearing</text>
            ''')

        # View label
        self.svg_elements.append(f'''
            <text x="{cx}" y="{viewport.y + 20}"
                  font-family="Arial" font-size="12" font-weight="bold"
                  text-anchor="middle">SIDE VIEW - SHAFT ARRANGEMENT</text>
        ''')

    def _generate_isometric_view(self, mechanism_data: dict[str, Any]) -> None:
        """Generate exploded isometric view."""
        viewport = self.viewports["isometric"]
        mechanism_data.get("params", {})

        cx = viewport.x + viewport.width / 2
        viewport.y + viewport.height / 2

        # Isometric transformation angles
        math.radians(30)
        math.radians(-30)

        # Component spacing for explosion
        explosion_offset = 30

        components = [
            "Ring Gear",
            "Planet Carrier Top",
            "Planet Gears (3x)",
            "Sun Gear",
            "Planet Carrier Bottom",
            "Output Shaft",
        ]

        y_pos = viewport.y + 40

        for i, component in enumerate(components):
            # Draw simplified isometric component
            x = cx + (i - len(components) / 2) * 20
            y = y_pos + i * explosion_offset

            # Component box
            self.svg_elements.append(f"""
                <g transform="translate({x}, {y}) skewY(-30) scale(1, 0.5)">
                    <rect x="-30" y="-10" width="60" height="20"
                          fill="none" stroke="black" stroke-width="1.5"/>
                </g>
            """)

            # Component label
            self.svg_elements.append(f'''
                <text x="{x + 40}" y="{y}"
                      font-family="Arial" font-size="9">{component}</text>
            ''')

            # Assembly arrow
            if i < len(components) - 1:
                self.svg_elements.append(f'''
                    <line x1="{x}" y1="{y + 10}"
                          x2="{x}" y2="{y + explosion_offset - 10}"
                          stroke="blue" stroke-width="1"
                          marker-end="url(#arrowhead)"
                          stroke-dasharray="2,2"/>
                ''')

        # Arrow marker definition
        self.svg_elements.append("""
            <defs>
                <marker id="arrowhead" markerWidth="10" markerHeight="7"
                        refX="9" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill="blue"/>
                </marker>
            </defs>
        """)

        # View label
        self.svg_elements.append(f'''
            <text x="{cx}" y="{viewport.y + 20}"
                  font-family="Arial" font-size="12" font-weight="bold"
                  text-anchor="middle">EXPLODED VIEW</text>
        ''')

    def _add_gear_teeth(
        self,
        cx: float,
        cy: float,
        radius: float,
        num_teeth: int,
        module: float,
        pressure_angle: float,
        internal: bool = False,
    ) -> None:
        """
        Add gear teeth to the blueprint.

        Args:
            cx, cy: Center coordinates
            radius: Pitch radius
            num_teeth: Number of teeth
            module: Gear module
            pressure_angle: Pressure angle in degrees
            internal: True for internal gear (ring gear)
        """
        if num_teeth < 3:
            return

        tooth_angle = 2 * math.pi / num_teeth
        addendum = module
        dedendum = 1.25 * module

        if internal:
            # Internal gear (ring)
            outer_radius = radius - addendum
            inner_radius = radius + dedendum
        else:
            # External gear
            outer_radius = radius + addendum
            inner_radius = radius - dedendum

        # Generate involute profile approximation
        path_data = []

        for i in range(num_teeth):
            base_angle = i * tooth_angle

            # Simplified tooth profile (trapezoid approximation)
            tooth_width = tooth_angle * 0.4

            if internal:
                # Internal tooth points
                angles = [
                    base_angle - tooth_width,
                    base_angle - tooth_width * 0.5,
                    base_angle + tooth_width * 0.5,
                    base_angle + tooth_width,
                ]

                points = []
                points.append(
                    (
                        cx + inner_radius * math.cos(angles[0]),
                        cy + inner_radius * math.sin(angles[0]),
                    )
                )
                points.append(
                    (
                        cx + outer_radius * math.cos(angles[1]),
                        cy + outer_radius * math.sin(angles[1]),
                    )
                )
                points.append(
                    (
                        cx + outer_radius * math.cos(angles[2]),
                        cy + outer_radius * math.sin(angles[2]),
                    )
                )
                points.append(
                    (
                        cx + inner_radius * math.cos(angles[3]),
                        cy + inner_radius * math.sin(angles[3]),
                    )
                )
            else:
                # External tooth points
                angles = [
                    base_angle - tooth_width,
                    base_angle - tooth_width * 0.3,
                    base_angle + tooth_width * 0.3,
                    base_angle + tooth_width,
                ]

                points = []
                points.append(
                    (
                        cx + inner_radius * math.cos(angles[0]),
                        cy + inner_radius * math.sin(angles[0]),
                    )
                )
                points.append(
                    (
                        cx + outer_radius * math.cos(angles[1]),
                        cy + outer_radius * math.sin(angles[1]),
                    )
                )
                points.append(
                    (
                        cx + outer_radius * math.cos(angles[2]),
                        cy + outer_radius * math.sin(angles[2]),
                    )
                )
                points.append(
                    (
                        cx + inner_radius * math.cos(angles[3]),
                        cy + inner_radius * math.sin(angles[3]),
                    )
                )

            if i == 0:
                path_data.append(f"M {points[0][0]:.2f} {points[0][1]:.2f}")
            else:
                path_data.append(f"L {points[0][0]:.2f} {points[0][1]:.2f}")

            for point in points[1:]:
                path_data.append(f"L {point[0]:.2f} {point[1]:.2f}")

        path_data.append("Z")

        # Add gear outline
        self.svg_elements.append(f'''
            <path d="{" ".join(path_data)}"
                  fill="none" stroke="black" stroke-width="1.5"/>
        ''')

        # Add pitch circle (reference)
        self.svg_elements.append(f'''
            <circle cx="{cx}" cy="{cy}" r="{radius}"
                    fill="none" stroke="blue" stroke-width="0.5"
                    stroke-dasharray="3,3" opacity="0.5"/>
        ''')

    def _add_dimensions(self, mechanism_data: dict[str, Any]) -> None:
        """Add dimensional annotations."""
        params = mechanism_data.get("params", {})
        viewport = self.viewports["front"]

        cx = viewport.x + viewport.width / 2
        cy = viewport.y + viewport.height / 2

        r_sun = params.get("r_sun", 30) * viewport.scale
        r_planet = params.get("r_planet", 20) * viewport.scale
        r_ring = r_sun + 2 * r_planet

        # Sun gear diameter
        self._add_dimension_line(
            cx - r_sun,
            cy + r_ring + 30,
            cx + r_sun,
            cy + r_ring + 30,
            f"Ø{r_sun * 2 / viewport.scale:.1f}",
            offset=10,
        )

        # Ring gear diameter
        self._add_dimension_line(
            cx - r_ring,
            cy + r_ring + 50,
            cx + r_ring,
            cy + r_ring + 50,
            f"Ø{r_ring * 2 / viewport.scale:.1f}",
            offset=10,
        )

        # Planet gear diameter (on one planet)
        angle = 0  # First planet at 0 degrees
        px = cx + (r_sun + r_planet) * math.cos(angle)
        py = cy + (r_sun + r_planet) * math.sin(angle)

        self._add_dimension_line(
            px - r_planet,
            py - r_ring - 30,
            px + r_planet,
            py - r_ring - 30,
            f"Ø{r_planet * 2 / viewport.scale:.1f}",
            offset=10,
        )

    def _add_tolerances(self, mechanism_data: dict[str, Any]) -> None:
        """Add tolerance specifications."""
        tolerance_text = [
            "TOLERANCES (Unless Otherwise Specified):",
            "• Linear dimensions: ±0.1mm",
            "• Angular dimensions: ±0.5°",
            "• Gear tooth profile: DIN 3960 Quality 8",
            "• Center distance: ±0.05mm",
            "• Bore diameter: H7",
            "• Shaft diameter: g6",
            "• Surface finish: Ra 1.6μm (gear teeth)",
            "• Surface finish: Ra 3.2μm (other surfaces)",
        ]

        y_offset = 50
        for line in tolerance_text:
            self.svg_elements.append(f'''
                <text x="50" y="{y_offset}"
                      font-family="Arial" font-size="9">{line}</text>
            ''')
            y_offset += 12

    def _add_part_list(self, mechanism_data: dict[str, Any]) -> None:
        """Add bill of materials."""
        params = mechanism_data.get("params", {})
        num_planets = _planet_count(params)

        parts = [
            {
                "no": "1",
                "name": "Sun Gear",
                "qty": "1",
                "material": "Steel",
                "spec": f"Module {params.get('module', 2)}",
            },
            {
                "no": "2",
                "name": "Planet Gear",
                "qty": str(num_planets),
                "material": "Steel",
                "spec": f"Module {params.get('module', 2)}",
            },
            {
                "no": "3",
                "name": "Ring Gear",
                "qty": "1",
                "material": "Steel",
                "spec": f"Internal, Module {params.get('module', 2)}",
            },
            {
                "no": "4",
                "name": "Planet Carrier",
                "qty": "1",
                "material": "Aluminum",
                "spec": "6061-T6",
            },
            {
                "no": "5",
                "name": "Planet Pin",
                "qty": str(num_planets),
                "material": "Steel",
                "spec": "Ø8mm x 30mm",
            },
            {
                "no": "6",
                "name": "Bearing",
                "qty": str(num_planets * 2 + 2),
                "material": "-",
                "spec": "608ZZ",
            },
            {"no": "7", "name": "Input Shaft", "qty": "1", "material": "Steel", "spec": "Ø10mm"},
            {"no": "8", "name": "Output Shaft", "qty": "1", "material": "Steel", "spec": "Ø12mm"},
        ]

        # Table header
        table_x = self.drawing_width - 400
        table_y = 200

        self.svg_elements.append(f'''
            <g class="part-list">
                <rect x="{table_x}" y="{table_y}" width="380" height="25"
                      fill="#e0e0e0" stroke="black" stroke-width="1"/>
                <text x="{table_x + 10}" y="{table_y + 17}"
                      font-family="Arial" font-size="11" font-weight="bold">PARTS LIST</text>
            </g>
        ''')

        # Column headers
        headers = [
            {"text": "No.", "x": table_x + 10, "width": 30},
            {"text": "Part Name", "x": table_x + 50, "width": 120},
            {"text": "Qty", "x": table_x + 180, "width": 40},
            {"text": "Material", "x": table_x + 230, "width": 80},
            {"text": "Specification", "x": table_x + 320, "width": 60},
        ]

        table_y += 25
        self.svg_elements.append(f'''
            <rect x="{table_x}" y="{table_y}" width="380" height="20"
                  fill="#f0f0f0" stroke="black" stroke-width="1"/>
        ''')

        for header in headers:
            self.svg_elements.append(f'''
                <text x="{header["x"]}" y="{table_y + 14}"
                      font-family="Arial" font-size="10" font-weight="bold">{header["text"]}</text>
            ''')

        # Part rows
        table_y += 20
        for part in parts:
            self.svg_elements.append(f'''
                <rect x="{table_x}" y="{table_y}" width="380" height="18"
                      fill="white" stroke="black" stroke-width="0.5"/>
                <text x="{table_x + 10}" y="{table_y + 13}"
                      font-family="Arial" font-size="10">{part["no"]}</text>
                <text x="{table_x + 50}" y="{table_y + 13}"
                      font-family="Arial" font-size="10">{part["name"]}</text>
                <text x="{table_x + 180}" y="{table_y + 13}"
                      font-family="Arial" font-size="10">{part["qty"]}</text>
                <text x="{table_x + 230}" y="{table_y + 13}"
                      font-family="Arial" font-size="10">{part["material"]}</text>
                <text x="{table_x + 320}" y="{table_y + 13}"
                      font-family="Arial" font-size="10">{part["spec"]}</text>
            ''')
            table_y += 18

    def _add_assembly_notes(self, mechanism_data: dict[str, Any]) -> None:
        """Add assembly instructions."""
        params = mechanism_data.get("params", {})
        gear_ratio = self._calculate_gear_ratio(params)

        notes = [
            "ASSEMBLY NOTES:",
            f"1. Gear Ratio: {gear_ratio:.2f}:1 (Reduction)",
            "2. Press-fit bearings into carrier and housing before assembly",
            "3. Ensure proper backlash: 0.05-0.10mm between gear teeth",
            "4. Apply grease to all gear teeth before final assembly",
            "5. Check smooth rotation before tightening carrier bolts",
            "6. Input torque limit: Based on sun gear tooth strength",
            "7. Operating temperature: -20°C to +80°C",
            "",
            "LUBRICATION:",
            "• Gear teeth: EP gear oil ISO VG 220",
            "• Bearings: Lithium grease NLGI 2",
            "",
            "MAINTENANCE:",
            "• Check oil level every 500 hours",
            "• Replace bearings every 10,000 hours",
            "• Inspect gear teeth for wear annually",
        ]

        notes_x = self.drawing_width - 400
        notes_y = 500

        for note in notes:
            font_weight = "bold" if note.endswith(":") else "normal"
            self.svg_elements.append(f'''
                <text x="{notes_x}" y="{notes_y}"
                      font-family="Arial" font-size="9"
                      font-weight="{font_weight}">{note}</text>
            ''')
            notes_y += 14

    def _calculate_gear_ratio(self, params: dict[str, Any]) -> float:
        """
        Calculate the gear ratio of the planetary system.

        Formula: GR = 1 + (Ring teeth / Sun teeth)
        for fixed ring, carrier output configuration
        """
        r_sun = params.get("r_sun", 30)
        r_ring = params.get("r_ring", r_sun + 2 * params.get("r_planet", 20))

        # Approximate tooth count from radius (assuming same module)
        sun_teeth = r_sun
        ring_teeth = r_ring

        # Planetary gear ratio (carrier output, ring fixed)
        gear_ratio = 1 + (ring_teeth / sun_teeth)

        return float(gear_ratio)
