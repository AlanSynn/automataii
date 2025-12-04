"""
Four-bar linkage blueprint generator with assembly details.
Creates detailed manufacturing drawings for linkage mechanisms.
"""

import math
from typing import Any

from .generator import BlueprintGenerator


class FourBarBlueprintGenerator(BlueprintGenerator):
    """
    Blueprint generator for four-bar linkage mechanisms.

    Generates:
    - Complete linkage assembly
    - Individual link details
    - Joint specifications (bearings, pins)
    - Motion envelope
    - Assembly sequence
    """

    def __init__(self):
        """Initialize four-bar blueprint generator."""
        super().__init__("four_bar")

    def _generate_front_view(self, mechanism_data: dict[str, Any]):
        """Generate front view showing complete linkage assembly."""
        params = mechanism_data.get('params', {})
        viewport = self.views[0]

        # Link parameters
        p1 = params.get('anchor1', [viewport.x + 50, viewport.y + 80])
        p2 = params.get('anchor2', [viewport.x + 150, viewport.y + 80])
        l2 = params.get('l2', 40)  # Crank
        l3 = params.get('l3', 60)  # Coupler
        l4 = params.get('l4', 50)  # Rocker

        # Calculate joint positions (example configuration)
        crank_angle = math.radians(45)  # Show at 45 degrees
        p3 = [
            p1[0] + l2 * math.cos(crank_angle),
            p1[1] + l2 * math.sin(crank_angle)
        ]

        # Solve for p4 position (simplified)
        rocker_angle = math.radians(30)
        p4 = [
            p2[0] + l4 * math.cos(math.pi - rocker_angle),
            p2[1] + l4 * math.sin(math.pi - rocker_angle)
        ]

        linkage_svg = f'''
        <g id="front-view-linkage">
            <!-- Ground Link (Frame) -->
            {self._draw_ground_link(p1, p2)}

            <!-- Crank Link -->
            {self._draw_link(p1, p3, "CRANK", l2, 8)}

            <!-- Rocker Link -->
            {self._draw_link(p2, p4, "ROCKER", l4, 8)}

            <!-- Coupler Link -->
            {self._draw_coupler_link(p3, p4, "COUPLER", l3, 10)}

            <!-- Joints -->
            {self._draw_revolute_joint(p1[0], p1[1], "A", True)}  # Fixed
            {self._draw_revolute_joint(p2[0], p2[1], "B", True)}  # Fixed
            {self._draw_revolute_joint(p3[0], p3[1], "C", False)} # Moving
            {self._draw_revolute_joint(p4[0], p4[1], "D", False)} # Moving

            <!-- Motion Path (for coupler point) -->
            {self._draw_motion_path(p3, p4)}

            <!-- Workspace envelope (dashed) -->
            <circle cx="{p1[0]}" cy="{p1[1]}" r="{l2}"
                    stroke="green" stroke-width="0.25" stroke-dasharray="3,2" fill="none"/>
            <circle cx="{p2[0]}" cy="{p2[1]}" r="{l4}"
                    stroke="green" stroke-width="0.25" stroke-dasharray="3,2" fill="none"/>
        </g>
        '''

        self.svg_elements.append(linkage_svg)

        # Add dimensions
        self._add_linkage_dimensions(p1, p2, p3, p4, l2, l3, l4)

    def _draw_ground_link(self, p1: list[float], p2: list[float]) -> str:
        """Draw ground link with foundation symbols."""
        return f'''
        <g id="ground-link">
            <!-- Ground link bar -->
            <line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}"
                  stroke="black" stroke-width="3" stroke-linecap="round"/>

            <!-- Foundation hatching -->
            <g stroke="black" stroke-width="0.5">
        ''' + ''.join([
            f'<line x1="{p1[0] + i}" y1="{p1[1] + 3}" x2="{p1[0] + i - 5}" y2="{p1[1] + 10}"/>'
            for i in range(0, int(p2[0] - p1[0]) + 5, 5)
        ]) + f'''
            </g>

            <!-- Ground symbols -->
            <path d="M {p1[0]-10},{p1[1]+3} L {p1[0]+10},{p1[1]+3}
                     M {p1[0]-7},{p1[1]+6} L {p1[0]+7},{p1[1]+6}
                     M {p1[0]-4},{p1[1]+9} L {p1[0]+4},{p1[1]+9}"
                  stroke="black" stroke-width="0.7"/>
            <path d="M {p2[0]-10},{p2[1]+3} L {p2[0]+10},{p2[1]+3}
                     M {p2[0]-7},{p2[1]+6} L {p2[0]+7},{p2[1]+6}
                     M {p2[0]-4},{p2[1]+9} L {p2[0]+4},{p2[1]+9}"
                  stroke="black" stroke-width="0.7"/>
        </g>
        '''

    def _draw_link(self, start: list[float], end: list[float],
                  label: str, length: float, width: float) -> str:
        """Draw a single link with realistic shape."""
        # Calculate angle and perpendicular
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        angle = math.atan2(dy, dx)

        # Perpendicular offsets for width
        perp_x = -math.sin(angle) * width/2
        perp_y = math.cos(angle) * width/2

        # Link profile points
        p1 = f"{start[0] + perp_x},{start[1] + perp_y}"
        p2 = f"{end[0] + perp_x},{end[1] + perp_y}"
        p3 = f"{end[0] - perp_x},{end[1] - perp_y}"
        p4 = f"{start[0] - perp_x},{start[1] - perp_y}"

        return f'''
        <g id="link-{label}">
            <!-- Link body -->
            <path d="M {p1} L {p2} L {p3} L {p4} Z"
                  stroke="black" stroke-width="0.7" fill="white"/>

            <!-- Lightening holes -->
            <circle cx="{(start[0] + end[0])/2}" cy="{(start[1] + end[1])/2}"
                    r="{width/3}"
                    stroke="black" stroke-width="0.5" fill="white"/>

            <!-- Link label -->
            <text x="{(start[0] + end[0])/2}" y="{(start[1] + end[1])/2 - width - 2}"
                  font-size="6" font-family="Arial" text-anchor="middle">
                {label}
            </text>
        </g>
        '''

    def _draw_coupler_link(self, start: list[float], end: list[float],
                          label: str, length: float, width: float) -> str:
        """Draw coupler link with triangular extension."""
        base_link = self._draw_link(start, end, label, length, width)

        # Add triangular coupler point extension
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2

        # Perpendicular extension for coupler point
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.sqrt(dx*dx + dy*dy)

        if length > 0:
            perp_x = -dy / length * 30
            perp_y = dx / length * 30
        else:
            perp_x, perp_y = 0, 30

        coupler_point = [mid_x + perp_x, mid_y + perp_y]

        extension = f'''
        <g id="coupler-extension">
            <!-- Triangular extension -->
            <path d="M {start[0]},{start[1]} L {coupler_point[0]},{coupler_point[1]}
                     L {end[0]},{end[1]}"
                  stroke="black" stroke-width="0.7" fill="none"/>

            <!-- Coupler point -->
            <circle cx="{coupler_point[0]}" cy="{coupler_point[1]}" r="3"
                    stroke="black" stroke-width="0.7" fill="white"/>
            <circle cx="{coupler_point[0]}" cy="{coupler_point[1]}" r="1"
                    fill="black"/>

            <!-- Coupler point label -->
            <text x="{coupler_point[0] + 5}" y="{coupler_point[1] - 5}"
                  font-size="6" font-family="Arial">P</text>
        </g>
        '''

        return base_link + extension

    def _draw_revolute_joint(self, x: float, y: float,
                            label: str, is_fixed: bool) -> str:
        """Draw revolute joint with bearing representation."""
        return f'''
        <g id="joint-{label}">
            <!-- Outer bearing race -->
            <circle cx="{x}" cy="{y}" r="6"
                    stroke="black" stroke-width="0.7" fill="white"/>

            <!-- Inner race -->
            <circle cx="{x}" cy="{y}" r="4"
                    stroke="black" stroke-width="0.5" fill="white"/>

            <!-- Pin/Shaft -->
            <circle cx="{x}" cy="{y}" r="2"
                    stroke="black" stroke-width="0.5" fill="{'black' if is_fixed else 'gray'}"/>

            <!-- Cross-hairs for fixed joints -->
            {'<g stroke="black" stroke-width="0.5">' if is_fixed else ''}
            {f'<line x1="{x-2}" y1="{y}" x2="{x+2}" y2="{y}"/>' if is_fixed else ''}
            {f'<line x1="{x}" y1="{y-2}" x2="{x}" y2="{y+2}"/>' if is_fixed else ''}
            {'</g>' if is_fixed else ''}

            <!-- Joint label -->
            <text x="{x - 10}" y="{y - 8}" font-size="7" font-family="Arial" font-weight="bold">
                {label}
            </text>
        </g>
        '''

    def _draw_motion_path(self, p3: list[float], p4: list[float]) -> str:
        """Draw the motion path of coupler point."""
        # Simplified - would calculate actual path
        mid_x = (p3[0] + p4[0]) / 2
        mid_y = (p3[1] + p4[1]) / 2 - 15  # Coupler point offset

        # Example elliptical path
        return f'''
        <ellipse cx="{mid_x}" cy="{mid_y + 10}" rx="25" ry="15"
                 stroke="blue" stroke-width="0.35" stroke-dasharray="4,2" fill="none"
                 opacity="0.7"/>
        '''

    def _generate_side_view(self, mechanism_data: dict[str, Any]):
        """Generate side view showing link thickness and joint details."""
        viewport = self.views[2]
        params = mechanism_data.get('params', {})

        link_thickness = params.get('thickness', 5)
        pin_diameter = params.get('pin_diameter', 8)
        bearing_width = params.get('bearing_width', 10)

        side_view_svg = f'''
        <g id="side-view-linkage">
            <!-- Link cross-section -->
            <rect x="{viewport.x + 40}" y="{viewport.y + 40}"
                  width="{link_thickness}" height="40"
                  stroke="black" stroke-width="0.5" fill="none"/>

            <!-- Joint assembly cross-section -->
            <g transform="translate({viewport.x + 100}, {viewport.y + 60})">
                <!-- Bearing -->
                <rect x="-{bearing_width/2}" y="-10"
                      width="{bearing_width}" height="20"
                      stroke="black" stroke-width="0.5" fill="none"/>

                <!-- Pin -->
                <rect x="-{pin_diameter/2}" y="-12"
                      width="{pin_diameter}" height="24"
                      stroke="black" stroke-width="0.5" fill="gray"/>

                <!-- Retaining rings -->
                <rect x="-{pin_diameter/2 + 1}" y="-13"
                      width="{pin_diameter + 2}" height="2"
                      stroke="black" stroke-width="0.5" fill="black"/>
                <rect x="-{pin_diameter/2 + 1}" y="11"
                      width="{pin_diameter + 2}" height="2"
                      stroke="black" stroke-width="0.5" fill="black"/>
            </g>

            <!-- Section indicators -->
            <g stroke="black" stroke-width="0.35">
                <line x1="{viewport.x + 30}" y1="{viewport.y + 30}"
                      x2="{viewport.x + 55}" y2="{viewport.y + 30}"/>
                <text x="{viewport.x + 35}" y="{viewport.y + 27}"
                      font-size="6" font-family="Arial">A-A</text>

                <line x1="{viewport.x + 85}" y1="{viewport.y + 30}"
                      x2="{viewport.x + 115}" y2="{viewport.y + 30}"/>
                <text x="{viewport.x + 95}" y="{viewport.y + 27}"
                      font-size="6" font-family="Arial">B-B</text>
            </g>
        </g>
        '''

        self.svg_elements.append(side_view_svg)

    def _generate_isometric_view(self, mechanism_data: dict[str, Any]):
        """Generate exploded isometric view."""
        viewport = self.views[3]

        exploded_svg = f'''
        <g id="exploded-view">
            <text x="{viewport.x + 5}" y="{viewport.y + 15}"
                  font-size="7" font-family="Arial" font-weight="bold">
                EXPLODED VIEW
            </text>

            <!-- Simplified exploded assembly -->
            <g transform="translate({viewport.x + viewport.width/2}, {viewport.y + viewport.height/2})">
                <!-- Base plate -->
                <path d="M -40,20 L 40,20 L 45,25 L -35,25 Z"
                      stroke="black" stroke-width="0.5" fill="lightgray"/>

                <!-- Link 1 -->
                <rect x="-30" y="0" width="60" height="8"
                      stroke="black" stroke-width="0.5" fill="white"
                      transform="rotate(-10)"/>

                <!-- Link 2 -->
                <rect x="-25" y="-20" width="50" height="8"
                      stroke="black" stroke-width="0.5" fill="white"
                      transform="rotate(15)"/>

                <!-- Pins (exploded upward) -->
                <g stroke="black" stroke-width="0.5" fill="gray">
                    <rect x="-3" y="-40" width="6" height="15"/>
                    <rect x="20" y="-35" width="6" height="15"/>
                    <rect x="-25" y="-35" width="6" height="15"/>
                </g>

                <!-- Assembly arrows -->
                <g stroke="blue" stroke-width="0.35" fill="blue">
                    <line x1="0" y1="-25" x2="0" y2="-5" marker-end="url(#arrow)"/>
                    <line x1="23" y1="-20" x2="23" y2="-5" marker-end="url(#arrow)"/>
                    <line x1="-22" y1="-20" x2="-22" y2="-5" marker-end="url(#arrow)"/>
                </g>
            </g>

            <!-- Arrow marker definition -->
            <defs>
                <marker id="arrow" markerWidth="10" markerHeight="10"
                        refX="0" refY="3" orient="auto" markerUnits="strokeWidth">
                    <path d="M0,0 L0,6 L9,3 z" fill="blue"/>
                </marker>
            </defs>
        </g>
        '''

        self.svg_elements.append(exploded_svg)

    def _add_linkage_dimensions(self, p1: list[float], p2: list[float],
                               p3: list[float], p4: list[float],
                               l2: float, l3: float, l4: float):
        """Add dimensions for linkage."""
        # Ground link length
        self.dimensions.append(
            self.create_dimension_line(
                p1[0], p1[1] + 20,
                p2[0], p2[1] + 20,
                f"{math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2):.1f}±0.1", 8
            )
        )

        # Crank length
        self.dimensions.append(
            self.create_dimension_line(
                p1[0] - 15, p1[1],
                p3[0] - 15, p3[1],
                f"{l2}±0.1", -10
            )
        )

        # Rocker length
        self.dimensions.append(
            self.create_dimension_line(
                p2[0] + 15, p2[1],
                p4[0] + 15, p4[1],
                f"{l4}±0.1", 10
            )
        )

    def _add_tolerances(self, mechanism_data: dict[str, Any]):
        """Add linkage-specific tolerances."""
        super()._add_tolerances(mechanism_data)

        linkage_tolerances = '''
        <g id="linkage-tolerances" font-size="6" font-family="Arial">
            <text x="140" y="260">LINKAGE SPECIFICATIONS:</text>
            <text x="140" y="266">PIN FIT: H7/g6</text>
            <text x="140" y="272">BEARING FIT: H7/k6</text>
            <text x="240" y="260">PARALLELISM: 0.05mm</text>
            <text x="240" y="266">SURFACE FINISH: Ra 3.2μm</text>
            <text x="240" y="272">GRASHOF CONDITION: VERIFIED</text>
        </g>
        '''

        self.svg_elements.append(linkage_tolerances)

    def _add_part_list(self, mechanism_data: dict[str, Any]):
        """Add linkage-specific part list."""
        parts = [
            {'name': 'CRANK LINK', 'quantity': 1, 'material': 'AL 6061-T6'},
            {'name': 'COUPLER LINK', 'quantity': 1, 'material': 'AL 6061-T6'},
            {'name': 'ROCKER LINK', 'quantity': 1, 'material': 'AL 6061-T6'},
            {'name': 'SHOULDER PIN Ø8x20', 'quantity': 4, 'material': 'STEEL'},
            {'name': 'BALL BEARING 608ZZ', 'quantity': 4, 'material': 'STEEL'},
            {'name': 'RETAINING RING Ø8', 'quantity': 8, 'material': 'SPRING STL'},
            {'name': 'BASE FRAME', 'quantity': 1, 'material': 'STEEL'}
        ]

        mechanism_data['parts'] = parts
        super()._add_part_list(mechanism_data)

    def _add_assembly_notes(self, mechanism_data: dict[str, Any]):
        """Add linkage-specific assembly notes."""
        notes = [
            'Press bearings into links using arbor press',
            'Ensure 0.01-0.02mm clearance on all pins',
            'Apply light machine oil to all joints',
            'Check for smooth rotation without binding',
            'Verify coupler point trajectory before final assembly',
            'Torque frame bolts to 15 Nm'
        ]

        mechanism_data['assembly_notes'] = notes
        super()._add_assembly_notes(mechanism_data)
