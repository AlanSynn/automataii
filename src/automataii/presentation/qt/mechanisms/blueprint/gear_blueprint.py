"""
Gear-specific blueprint generator with tooth profiles.
Creates detailed manufacturing drawings for gear mechanisms.
"""

import math
from typing import Any

from .generator import BlueprintGenerator


class GearBlueprintGenerator(BlueprintGenerator):
    """
    Blueprint generator for gear mechanisms.

    Generates:
    - Detailed tooth profiles (involute)
    - Pitch circles
    - Module and pressure angle
    - Center distance
    - Backlash specifications
    """

    def __init__(self):
        """Initialize gear blueprint generator."""
        super().__init__("gear")

    def _generate_front_view(self, mechanism_data: dict[str, Any]):
        """Generate front view showing complete gear pair."""
        params = mechanism_data.get('params', {})
        viewport = self.views[0]  # Front view viewport

        # Gear parameters
        r1 = params.get('gear1_radius', 30)
        r2 = params.get('gear2_radius', 50)
        center1 = (viewport.x + 50, viewport.y + viewport.height/2)
        center2 = (center1[0] + r1 + r2 + 2, center1[1])  # Proper meshing distance

        # Calculate tooth parameters
        module = params.get('module', 2)  # Module (tooth size)
        n1 = int(2 * r1 / module)  # Number of teeth
        n2 = int(2 * r2 / module)
        pressure_angle = params.get('pressure_angle', 20)  # degrees

        gear_svg = f'''
        <g id="front-view-gears" transform="translate(0,0)">
            <!-- Gear 1 (Driver) -->
            {self._generate_gear_with_teeth(center1[0], center1[1], r1, n1, module, pressure_angle, "gear1")}

            <!-- Gear 2 (Driven) -->
            {self._generate_gear_with_teeth(center2[0], center2[1], r2, n2, module, pressure_angle, "gear2")}

            <!-- Center marks -->
            <g stroke="black" stroke-width="0.35">
                <line x1="{center1[0]-5}" y1="{center1[1]}" x2="{center1[0]+5}" y2="{center1[1]}"/>
                <line x1="{center1[0]}" y1="{center1[1]-5}" x2="{center1[0]}" y2="{center1[1]+5}"/>
                <line x1="{center2[0]-5}" y1="{center2[1]}" x2="{center2[0]+5}" y2="{center2[1]}"/>
                <line x1="{center2[0]}" y1="{center2[1]-5}" x2="{center2[0]}" y2="{center2[1]+5}"/>
            </g>

            <!-- Pitch circles (dashed) -->
            <circle cx="{center1[0]}" cy="{center1[1]}" r="{r1}"
                    stroke="blue" stroke-width="0.25" stroke-dasharray="2,2" fill="none"/>
            <circle cx="{center2[0]}" cy="{center2[1]}" r="{r2}"
                    stroke="blue" stroke-width="0.25" stroke-dasharray="2,2" fill="none"/>

            <!-- Annotations -->
            <g font-size="6" font-family="Arial">
                <text x="{center1[0]}" y="{center1[1] + r1 + 15}" text-anchor="middle">
                    GEAR 1 (DRIVER)
                </text>
                <text x="{center1[0]}" y="{center1[1] + r1 + 21}" text-anchor="middle">
                    {n1} TEETH
                </text>

                <text x="{center2[0]}" y="{center2[1] + r2 + 15}" text-anchor="middle">
                    GEAR 2 (DRIVEN)
                </text>
                <text x="{center2[0]}" y="{center2[1] + r2 + 21}" text-anchor="middle">
                    {n2} TEETH
                </text>
            </g>
        </g>
        '''

        self.svg_elements.append(gear_svg)

        # Add dimensions
        self._add_gear_dimensions(center1, center2, r1, r2)

    def _generate_gear_with_teeth(self, cx: float, cy: float, r: float,
                                 n_teeth: int, module: float,
                                 pressure_angle: float, gear_id: str) -> str:
        """Generate detailed gear with involute tooth profile."""

        # Calculate tooth geometry
        pitch_radius = r
        base_radius = r * math.cos(math.radians(pressure_angle))
        addendum = module  # Tooth height above pitch circle
        dedendum = 1.25 * module  # Tooth depth below pitch circle
        outer_radius = pitch_radius + addendum
        root_radius = pitch_radius - dedendum
        tooth_thickness = math.pi * module / 2  # Thickness at pitch circle

        gear_path = f'<g id="{gear_id}">\n'

        # Generate each tooth
        for i in range(n_teeth):
            angle = i * 2 * math.pi / n_teeth

            # Generate involute curve for tooth profile
            tooth_svg = self._generate_tooth_profile(
                cx, cy, base_radius, pitch_radius,
                outer_radius, root_radius, angle, tooth_thickness
            )
            gear_path += tooth_svg

        # Add hub
        hub_radius = root_radius * 0.3
        gear_path += f'''
            <!-- Hub -->
            <circle cx="{cx}" cy="{cy}" r="{hub_radius}"
                    stroke="black" stroke-width="0.5" fill="white"/>

            <!-- Keyway -->
            <rect x="{cx - 3}" y="{cy - hub_radius}"
                  width="6" height="{hub_radius}"
                  stroke="black" stroke-width="0.5" fill="white"/>
        '''

        gear_path += '</g>\n'

        return gear_path

    def _generate_tooth_profile(self, cx: float, cy: float, base_r: float,
                               pitch_r: float, outer_r: float, root_r: float,
                               angle: float, thickness: float) -> str:
        """Generate single tooth with involute profile."""

        # Simplified tooth profile (for clarity in manufacturing)
        # In production, use precise involute calculations

        # Angular width of tooth at pitch circle
        tooth_angle = thickness / pitch_r

        # Points for tooth profile
        points = []

        # Root circle points
        root_angle1 = angle - tooth_angle * 0.7
        root_angle2 = angle + tooth_angle * 0.7
        points.append((
            cx + root_r * math.cos(root_angle1),
            cy + root_r * math.sin(root_angle1)
        ))

        # Pitch circle points (involute starts here)
        pitch_angle1 = angle - tooth_angle / 2
        pitch_angle2 = angle + tooth_angle / 2
        points.append((
            cx + pitch_r * math.cos(pitch_angle1),
            cy + pitch_r * math.sin(pitch_angle1)
        ))

        # Outer circle points (tooth tip)
        tip_angle1 = angle - tooth_angle * 0.3
        tip_angle2 = angle + tooth_angle * 0.3
        points.append((
            cx + outer_r * math.cos(tip_angle1),
            cy + outer_r * math.sin(tip_angle1)
        ))
        points.append((
            cx + outer_r * math.cos(tip_angle2),
            cy + outer_r * math.sin(tip_angle2)
        ))

        # Other side of tooth
        points.append((
            cx + pitch_r * math.cos(pitch_angle2),
            cy + pitch_r * math.sin(pitch_angle2)
        ))
        points.append((
            cx + root_r * math.cos(root_angle2),
            cy + root_r * math.sin(root_angle2)
        ))

        # Create path
        path_data = f"M {points[0][0]:.2f},{points[0][1]:.2f}"
        for point in points[1:]:
            path_data += f" L {point[0]:.2f},{point[1]:.2f}"

        # Arc for root fillet
        path_data += f" A {root_r:.2f},{root_r:.2f} 0 0 0 {points[0][0]:.2f},{points[0][1]:.2f}"

        return f'''
            <path d="{path_data}"
                  stroke="black" stroke-width="0.5" fill="none"/>
        '''

    def _generate_top_view(self, mechanism_data: dict[str, Any]):
        """Generate top view showing gear thickness."""
        params = mechanism_data.get('params', {})
        viewport = self.views[1]  # Top view viewport

        gear_thickness = params.get('thickness', 10)
        params.get('shaft_diameter', 10)

        top_view_svg = f'''
        <g id="top-view-gear">
            <!-- Gear body (side view) -->
            <rect x="{viewport.x + 30}" y="{viewport.y + 40}"
                  width="100" height="{gear_thickness}"
                  stroke="black" stroke-width="0.5" fill="none"/>

            <!-- Shaft -->
            <rect x="{viewport.x + 70}" y="{viewport.y + 40 - 5}"
                  width="20" height="{gear_thickness + 10}"
                  stroke="black" stroke-width="0.5" fill="none"/>

            <!-- Keyway -->
            <rect x="{viewport.x + 77}" y="{viewport.y + 40}"
                  width="6" height="{gear_thickness}"
                  stroke="black" stroke-width="0.5" fill="white"/>

            <!-- Hidden lines for teeth (dashed) -->
            <line x1="{viewport.x + 30}" y1="{viewport.y + 42}"
                  x2="{viewport.x + 130}" y2="{viewport.y + 42}"
                  stroke="black" stroke-width="0.25" stroke-dasharray="2,1"/>
            <line x1="{viewport.x + 30}" y1="{viewport.y + 48}"
                  x2="{viewport.x + 130}" y2="{viewport.y + 48}"
                  stroke="black" stroke-width="0.25" stroke-dasharray="2,1"/>
        </g>
        '''

        self.svg_elements.append(top_view_svg)

        # Add thickness dimension
        self.dimensions.append(
            self.create_dimension_line(
                viewport.x + 30, viewport.y + 40,
                viewport.x + 30, viewport.y + 40 + gear_thickness,
                f"{gear_thickness}±0.1", -15
            )
        )

    def _add_gear_dimensions(self, center1: tuple[float, float],
                            center2: tuple[float, float],
                            r1: float, r2: float):
        """Add detailed dimensions for gears."""

        # Pitch diameter dimensions
        self.dimensions.append(
            self.create_radius_dimension(center1[0], center1[1], r1, 135)
        )
        self.dimensions.append(
            self.create_radius_dimension(center2[0], center2[1], r2, 45)
        )

        # Center distance
        self.dimensions.append(
            self.create_dimension_line(
                center1[0], center1[1] + r1 + 25,
                center2[0], center2[1] + r2 + 25,
                f"{r1 + r2 + 2:.1f}±0.05", 10
            )
        )

    def _add_tolerances(self, mechanism_data: dict[str, Any]):
        """Add gear-specific tolerances."""
        super()._add_tolerances(mechanism_data)

        gear_tolerances = f'''
        <g id="gear-tolerances" font-size="6" font-family="Arial">
            <text x="140" y="280">GEAR SPECIFICATIONS:</text>
            <text x="140" y="286">MODULE: {mechanism_data.get('params', {}).get('module', 2)}mm</text>
            <text x="140" y="292">PRESSURE ANGLE: {mechanism_data.get('params', {}).get('pressure_angle', 20)}°</text>
            <text x="220" y="280">BACKLASH: 0.05-0.10mm</text>
            <text x="220" y="286">SURFACE FINISH: Ra 1.6</text>
            <text x="220" y="292">MATERIAL: {mechanism_data.get('material', 'STEEL')} HRC 58-62</text>
        </g>
        '''

        self.svg_elements.append(gear_tolerances)

    def _add_part_list(self, mechanism_data: dict[str, Any]):
        """Add gear-specific part list."""
        parts = [
            {'name': 'DRIVER GEAR', 'quantity': 1, 'material': 'STEEL'},
            {'name': 'DRIVEN GEAR', 'quantity': 1, 'material': 'STEEL'},
            {'name': 'SHAFT KEY 6x6x25', 'quantity': 2, 'material': 'STEEL'},
            {'name': 'RETAINING RING', 'quantity': 4, 'material': 'SPRING STL'}
        ]

        mechanism_data['parts'] = parts
        super()._add_part_list(mechanism_data)

    def _add_assembly_notes(self, mechanism_data: dict[str, Any]):
        """Add gear-specific assembly notes."""
        notes = [
            'Ensure proper backlash (0.05-0.10mm) during assembly',
            'Apply gear oil before operation',
            'Check alignment of shafts (parallel within 0.02mm)',
            'Verify smooth rotation without binding',
            'Break-in period: 100 hours at 50% load'
        ]

        mechanism_data['assembly_notes'] = notes
        super()._add_assembly_notes(mechanism_data)
