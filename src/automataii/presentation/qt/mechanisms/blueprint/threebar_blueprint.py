"""
Three-Bar Linkage Blueprint Generator Module

This module provides the ThreeBarBlueprintGenerator class for generating
detailed manufacturing blueprints for three-bar linkage mechanisms.

Classes:
    ThreeBarBlueprintGenerator: Generates three-bar linkage blueprints
"""

import math
from typing import Any

from .generator import BlueprintGenerator

__all__ = ['ThreeBarBlueprintGenerator']


class ThreeBarBlueprintGenerator(BlueprintGenerator):
    """
    Blueprint generator for three-bar linkage mechanisms.

    Generates detailed manufacturing documentation for three-bar linkages
    including crank, coupler, and rocker/slider components.
    """

    def __init__(self):
        """Initialize three-bar blueprint generator."""
        super().__init__("three_bar")

    def _generate_front_view(self, mechanism_data: dict[str, Any]):
        """Generate front view of three-bar linkage."""
        viewport = self.viewports['front']
        params = mechanism_data.get('params', {})

        # Extract parameters
        anchor1 = params.get('anchor1', [100, 300])
        anchor2 = params.get('anchor2', [400, 300])
        l1 = params.get('l1', 80) * viewport.scale  # Crank length
        params.get('l2', 120) * viewport.scale  # Coupler length
        l3 = params.get('l3', 100) * viewport.scale  # Rocker length
        angle = params.get('angle', 0)

        # Scale and position anchors
        ax1 = viewport.x + anchor1[0] * viewport.scale
        ay1 = viewport.y + anchor1[1] * viewport.scale
        ax2 = viewport.x + anchor2[0] * viewport.scale
        ay2 = viewport.y + anchor2[1] * viewport.scale

        # Calculate joint positions
        # Crank endpoint (P1)
        p1x = ax1 + l1 * math.cos(angle)
        p1y = ay1 + l1 * math.sin(angle)

        # Rocker endpoint (P2) - simplified positioning
        # In real implementation, would solve the constraint equations
        p2x = ax2 + l3 * math.cos(angle + math.pi/4)
        p2y = ay2 + l3 * math.sin(angle + math.pi/4)

        # Draw ground anchors
        self._add_ground_anchor(ax1, ay1, "A")
        self._add_ground_anchor(ax2, ay2, "B")

        # Draw links with realistic thickness
        link_thickness = 15

        # Crank (Link 1)
        self._add_link(ax1, ay1, p1x, p1y, link_thickness, "1")

        # Coupler (Link 2)
        self._add_link(p1x, p1y, p2x, p2y, link_thickness, "2")

        # Rocker (Link 3)
        self._add_link(ax2, ay2, p2x, p2y, link_thickness, "3")

        # Draw joints
        self._add_revolute_joint(ax1, ay1, "O1")
        self._add_revolute_joint(p1x, p1y, "A")
        self._add_revolute_joint(p2x, p2y, "B")
        self._add_revolute_joint(ax2, ay2, "O2")

        # Motion envelope (trace path)
        self._add_motion_envelope(ax1, ay1, l1, "Crank Path")

        # View label
        self.svg_elements.append(f'''
            <text x="{viewport.x + viewport.width/2}" y="{viewport.y + 20}"
                  font-family="Arial" font-size="12" font-weight="bold"
                  text-anchor="middle">FRONT VIEW - ASSEMBLY</text>
        ''')

    def _generate_top_view(self, mechanism_data: dict[str, Any]):
        """Generate top view showing link thickness and assembly."""
        viewport = self.viewports['top']
        params = mechanism_data.get('params', {})

        cx = viewport.x + viewport.width / 2
        cy = viewport.y + viewport.height / 2

        # Link thicknesses
        link_thickness = params.get('link_thickness', 8) * viewport.scale
        pin_diameter = params.get('pin_diameter', 10) * viewport.scale

        # Draw stacked links (side view of assembly)
        y_offset = cy - link_thickness * 2

        # Ground base
        self.svg_elements.append(f'''
            <rect x="{viewport.x + 30}" y="{y_offset}"
                  width="{viewport.width - 60}" height="{link_thickness * 0.5}"
                  fill="none" stroke="black" stroke-width="2"/>
            <text x="{viewport.x + 35}" y="{y_offset + link_thickness * 0.3}"
                  font-family="Arial" font-size="10">Ground Frame</text>
        ''')
        y_offset += link_thickness * 0.7

        # Link 3 (Rocker - bottom layer)
        self.svg_elements.append(f'''
            <rect x="{viewport.x + 40}" y="{y_offset}"
                  width="{viewport.width - 80}" height="{link_thickness}"
                  fill="none" stroke="black" stroke-width="1.5"/>
            <text x="{viewport.x + 45}" y="{y_offset + link_thickness/2 + 3}"
                  font-family="Arial" font-size="10">Link 3 (Rocker)</text>
        ''')
        y_offset += link_thickness + 2

        # Link 2 (Coupler - middle layer)
        self.svg_elements.append(f'''
            <rect x="{viewport.x + 50}" y="{y_offset}"
                  width="{viewport.width - 100}" height="{link_thickness}"
                  fill="none" stroke="black" stroke-width="1.5"/>
            <text x="{viewport.x + 55}" y="{y_offset + link_thickness/2 + 3}"
                  font-family="Arial" font-size="10">Link 2 (Coupler)</text>
        ''')
        y_offset += link_thickness + 2

        # Link 1 (Crank - top layer)
        self.svg_elements.append(f'''
            <rect x="{viewport.x + 40}" y="{y_offset}"
                  width="{viewport.width - 80}" height="{link_thickness}"
                  fill="none" stroke="black" stroke-width="1.5"/>
            <text x="{viewport.x + 45}" y="{y_offset + link_thickness/2 + 3}"
                  font-family="Arial" font-size="10">Link 1 (Crank)</text>
        ''')

        # Show pin positions
        pin_x_positions = [
            viewport.x + 80,
            viewport.x + viewport.width - 80,
            cx
        ]

        for px in pin_x_positions:
            self.svg_elements.append(f'''
                <line x1="{px}" y1="{cy - link_thickness * 2.5}"
                      x2="{px}" y2="{cy + link_thickness * 2.5}"
                      stroke="red" stroke-width="1" stroke-dasharray="3,2"/>
                <circle cx="{px}" cy="{cy}" r="{pin_diameter/2}"
                        fill="none" stroke="red" stroke-width="1"/>
            ''')

        # View label
        self.svg_elements.append(f'''
            <text x="{cx}" y="{viewport.y + 20}"
                  font-family="Arial" font-size="12" font-weight="bold"
                  text-anchor="middle">TOP VIEW - LAYER STACK</text>
        ''')

    def _generate_side_view(self, mechanism_data: dict[str, Any]):
        """Generate side view showing joint details."""
        viewport = self.viewports['side']
        params = mechanism_data.get('params', {})

        cx = viewport.x + viewport.width / 2
        cy = viewport.y + viewport.height / 2

        # Joint parameters
        pin_diameter = params.get('pin_diameter', 10) * viewport.scale
        bushing_od = pin_diameter * 1.5
        bushing_length = params.get('link_thickness', 8) * viewport.scale * 3

        # Draw detailed joint assembly
        # Outer housing
        self.svg_elements.append(f'''
            <rect x="{cx - bushing_od}" y="{cy - bushing_length/2}"
                  width="{bushing_od * 2}" height="{bushing_length}"
                  fill="none" stroke="black" stroke-width="2"/>
        ''')

        # Bushing layers
        bushing_positions = [
            cy - bushing_length/2 + bushing_length * 0.2,
            cy,
            cy + bushing_length/2 - bushing_length * 0.2
        ]

        for by in bushing_positions:
            self.svg_elements.append(f'''
                <rect x="{cx - bushing_od * 0.7}" y="{by - 3}"
                      width="{bushing_od * 1.4}" height="6"
                      fill="none" stroke="black" stroke-width="1"/>
            ''')

        # Center pin
        self.svg_elements.append(f'''
            <rect x="{cx - pin_diameter/2}" y="{cy - bushing_length/2 - 10}"
                  width="{pin_diameter}" height="{bushing_length + 20}"
                  fill="none" stroke="black" stroke-width="1.5"/>
        ''')

        # Pin head and nut
        self.svg_elements.append(f'''
            <rect x="{cx - pin_diameter * 0.7}" y="{cy - bushing_length/2 - 15}"
                  width="{pin_diameter * 1.4}" height="5"
                  fill="none" stroke="black" stroke-width="1"/>
            <rect x="{cx - pin_diameter * 0.7}" y="{cy + bushing_length/2 + 10}"
                  width="{pin_diameter * 1.4}" height="5"
                  fill="none" stroke="black" stroke-width="1"/>
        ''')

        # Labels
        self.svg_elements.append(f'''
            <text x="{cx + bushing_od + 10}" y="{cy - bushing_length/2}"
                  font-family="Arial" font-size="9">Link Connection</text>
            <text x="{cx + bushing_od + 10}" y="{cy}"
                  font-family="Arial" font-size="9">Bronze Bushing</text>
            <text x="{cx + bushing_od + 10}" y="{cy + bushing_length/2}"
                  font-family="Arial" font-size="9">Steel Pin</text>
        ''')

        # View label
        self.svg_elements.append(f'''
            <text x="{cx}" y="{viewport.y + 20}"
                  font-family="Arial" font-size="12" font-weight="bold"
                  text-anchor="middle">SIDE VIEW - JOINT DETAIL</text>
        ''')

    def _generate_isometric_view(self, mechanism_data: dict[str, Any]):
        """Generate isometric exploded view."""
        viewport = self.viewports['isometric']
        mechanism_data.get('params', {})

        cx = viewport.x + viewport.width / 2
        viewport.y + viewport.height / 2

        # Component list for explosion
        components = [
            {"name": "Ground Frame", "width": 150, "height": 30},
            {"name": "Link 1 (Crank)", "width": 100, "height": 20},
            {"name": "Link 2 (Coupler)", "width": 120, "height": 20},
            {"name": "Link 3 (Rocker)", "width": 100, "height": 20},
            {"name": "Pin A (Ø10x30)", "width": 10, "height": 30},
            {"name": "Pin B (Ø10x30)", "width": 10, "height": 30},
            {"name": "Bushing (4x)", "width": 15, "height": 10},
            {"name": "Washers (8x)", "width": 12, "height": 2},
            {"name": "Lock Nuts (4x)", "width": 12, "height": 5}
        ]

        y_offset = viewport.y + 40
        explosion_spacing = 25

        for i, comp in enumerate(components):
            y_pos = y_offset + i * explosion_spacing

            # Draw isometric component representation
            transform_str = f"translate({cx}, {y_pos}) skewY(-20) scale(1, 0.6)"

            self.svg_elements.append(f'''
                <g transform="{transform_str}">
                    <rect x="{-comp['width']/2}" y="{-comp['height']/2}"
                          width="{comp['width']}" height="{comp['height']}"
                          fill="none" stroke="black" stroke-width="1.5"/>
                </g>
            ''')

            # Component label
            self.svg_elements.append(f'''
                <text x="{cx + 80}" y="{y_pos + 3}"
                      font-family="Arial" font-size="9">{comp['name']}</text>
            ''')

            # Assembly arrow
            if i < len(components) - 1:
                self.svg_elements.append(f'''
                    <line x1="{cx}" y1="{y_pos + comp['height']/2 + 2}"
                          x2="{cx}" y2="{y_pos + explosion_spacing - 2}"
                          stroke="blue" stroke-width="0.8"
                          stroke-dasharray="2,2"
                          marker-end="url(#assembly-arrow)"/>
                ''')

        # Arrow marker
        self.svg_elements.append('''
            <defs>
                <marker id="assembly-arrow" markerWidth="8" markerHeight="6"
                        refX="7" refY="3" orient="auto">
                    <polygon points="0 0, 8 3, 0 6" fill="blue"/>
                </marker>
            </defs>
        ''')

        # View label
        self.svg_elements.append(f'''
            <text x="{cx}" y="{viewport.y + 20}"
                  font-family="Arial" font-size="12" font-weight="bold"
                  text-anchor="middle">EXPLODED VIEW</text>
        ''')

    def _add_link(self, x1: float, y1: float, x2: float, y2: float,
                  thickness: float, label: str):
        """Add a link with realistic appearance."""
        # Calculate link angle and length
        dx = x2 - x1
        dy = y2 - y1
        math.sqrt(dx*dx + dy*dy)
        math.atan2(dy, dx)

        # Link body with rounded ends
        self.svg_elements.append(f'''
            <g class="link-{label}">
                <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"
                      stroke="black" stroke-width="{thickness}"
                      stroke-linecap="round" opacity="0.3"/>
                <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"
                      stroke="black" stroke-width="2" stroke-linecap="round"/>
                <circle cx="{x1}" cy="{y1}" r="{thickness/2}"
                        fill="white" stroke="black" stroke-width="1.5"/>
                <circle cx="{x2}" cy="{y2}" r="{thickness/2}"
                        fill="white" stroke="black" stroke-width="1.5"/>
                <text x="{(x1+x2)/2}" y="{(y1+y2)/2 - thickness/2 - 5}"
                      font-family="Arial" font-size="10" text-anchor="middle">
                    Link {label}
                </text>
            </g>
        ''')

    def _add_ground_anchor(self, x: float, y: float, label: str):
        """Add ground anchor symbol."""
        self.svg_elements.append(f'''
            <g class="ground-anchor-{label}">
                <path d="M {x-15} {y+5} L {x} {y} L {x+15} {y+5}"
                      fill="none" stroke="black" stroke-width="2"/>
                <line x1="{x-20}" y1="{y+5}" x2="{x+20}" y2="{y+5}"
                      stroke="black" stroke-width="1"/>
                <line x1="{x-15}" y1="{y+10}" x2="{x+15}" y2="{y+10}"
                      stroke="black" stroke-width="1"/>
                <line x1="{x-10}" y1="{y+15}" x2="{x+10}" y2="{y+15}"
                      stroke="black" stroke-width="1"/>
                <text x="{x}" y="{y+30}" font-family="Arial" font-size="10"
                      text-anchor="middle">{label}</text>
            </g>
        ''')

    def _add_revolute_joint(self, x: float, y: float, label: str):
        """Add revolute joint symbol."""
        self.svg_elements.append(f'''
            <g class="joint-{label}">
                <circle cx="{x}" cy="{y}" r="8" fill="white"
                        stroke="black" stroke-width="2"/>
                <circle cx="{x}" cy="{y}" r="3" fill="black"/>
                <text x="{x+12}" y="{y-10}" font-family="Arial" font-size="9">
                    {label}
                </text>
            </g>
        ''')

    def _add_motion_envelope(self, cx: float, cy: float, radius: float, label: str):
        """Add motion envelope circle."""
        self.svg_elements.append(f'''
            <g class="motion-envelope">
                <circle cx="{cx}" cy="{cy}" r="{radius}"
                        fill="none" stroke="green" stroke-width="0.5"
                        stroke-dasharray="5,3" opacity="0.5"/>
                <text x="{cx}" y="{cy - radius - 10}"
                      font-family="Arial" font-size="9" fill="green"
                      text-anchor="middle">{label}</text>
            </g>
        ''')

    def _add_dimensions(self, mechanism_data: dict[str, Any]):
        """Add dimensional annotations."""
        params = mechanism_data.get('params', {})
        viewport = self.viewports['front']

        # Get scaled dimensions
        l1 = params.get('l1', 80)
        l2 = params.get('l2', 120)
        l3 = params.get('l3', 100)
        ground_length = params.get('ground_length', 300)

        # Add dimension lines
        base_y = viewport.y + viewport.height - 50

        # Ground length
        self._add_dimension_line(
            viewport.x + 100, base_y,
            viewport.x + 400, base_y,
            f"{ground_length}mm",
            offset=15
        )

        # Link dimensions (shown separately)
        dim_x = viewport.x + viewport.width - 150
        dim_y = viewport.y + 100

        dimensions = [
            f"L1 (Crank): {l1}mm",
            f"L2 (Coupler): {l2}mm",
            f"L3 (Rocker): {l3}mm"
        ]

        for dim in dimensions:
            self.svg_elements.append(f'''
                <text x="{dim_x}" y="{dim_y}"
                      font-family="Arial" font-size="10">{dim}</text>
            ''')
            dim_y += 20

    def _add_tolerances(self, mechanism_data: dict[str, Any]):
        """Add tolerance specifications."""
        tolerance_text = [
            "TOLERANCES:",
            "• Link lengths: ±0.1mm",
            "• Pin holes: H7/g6 fit",
            "• Angular alignment: ±0.5°",
            "• Surface finish: Ra 3.2μm",
            "• Bushing bore: H7",
            "• Pin diameter: g6",
            "• Parallelism: 0.05mm",
            "• Perpendicularity: 0.05mm"
        ]

        y_offset = 50
        for line in tolerance_text:
            font_weight = "bold" if line == "TOLERANCES:" else "normal"
            self.svg_elements.append(f'''
                <text x="50" y="{y_offset}"
                      font-family="Arial" font-size="9"
                      font-weight="{font_weight}">{line}</text>
            ''')
            y_offset += 12

    def _add_part_list(self, mechanism_data: dict[str, Any]):
        """Add bill of materials."""
        parts = [
            {"no": "1", "name": "Ground Frame", "qty": "1",
             "material": "Steel", "spec": "S235JR"},
            {"no": "2", "name": "Link 1 (Crank)", "qty": "1",
             "material": "Aluminum", "spec": "6061-T6"},
            {"no": "3", "name": "Link 2 (Coupler)", "qty": "1",
             "material": "Aluminum", "spec": "6061-T6"},
            {"no": "4", "name": "Link 3 (Rocker)", "qty": "1",
             "material": "Aluminum", "spec": "6061-T6"},
            {"no": "5", "name": "Joint Pin", "qty": "4",
             "material": "Steel", "spec": "Ø10mm x 30mm"},
            {"no": "6", "name": "Bronze Bushing", "qty": "4",
             "material": "Bronze", "spec": "CuSn8"},
            {"no": "7", "name": "Washer", "qty": "8",
             "material": "Steel", "spec": "M10 DIN 125"},
            {"no": "8", "name": "Lock Nut", "qty": "4",
             "material": "Steel", "spec": "M10 DIN 985"},
            {"no": "9", "name": "Grease Nipple", "qty": "4",
             "material": "Steel", "spec": "M6x1"}
        ]

        # Create parts table
        table_x = self.drawing_width - 400
        table_y = 200

        # Table header
        self.svg_elements.append(f'''
            <g class="part-list">
                <rect x="{table_x}" y="{table_y}" width="380" height="25"
                      fill="#e0e0e0" stroke="black" stroke-width="1"/>
                <text x="{table_x + 10}" y="{table_y + 17}"
                      font-family="Arial" font-size="11" font-weight="bold">
                    PARTS LIST
                </text>
            </g>
        ''')

        # Column headers
        table_y += 25
        self.svg_elements.append(f'''
            <rect x="{table_x}" y="{table_y}" width="380" height="20"
                  fill="#f0f0f0" stroke="black" stroke-width="1"/>
        ''')

        headers = [
            ("No.", table_x + 10),
            ("Part Name", table_x + 50),
            ("Qty", table_x + 180),
            ("Material", table_x + 230),
            ("Specification", table_x + 320)
        ]

        for header, x_pos in headers:
            self.svg_elements.append(f'''
                <text x="{x_pos}" y="{table_y + 14}"
                      font-family="Arial" font-size="10" font-weight="bold">
                    {header}
                </text>
            ''')

        # Part rows
        table_y += 20
        for part in parts:
            self.svg_elements.append(f'''
                <rect x="{table_x}" y="{table_y}" width="380" height="18"
                      fill="white" stroke="black" stroke-width="0.5"/>
            ''')

            values = [
                (part['no'], table_x + 10),
                (part['name'], table_x + 50),
                (part['qty'], table_x + 180),
                (part['material'], table_x + 230),
                (part['spec'], table_x + 320)
            ]

            for value, x_pos in values:
                self.svg_elements.append(f'''
                    <text x="{x_pos}" y="{table_y + 13}"
                          font-family="Arial" font-size="10">{value}</text>
                ''')

            table_y += 18

    def _add_assembly_notes(self, mechanism_data: dict[str, Any]):
        """Add assembly instructions."""
        notes = [
            "ASSEMBLY INSTRUCTIONS:",
            "1. Press-fit bronze bushings into all link holes",
            "2. Align Link 1 (crank) with ground anchor A",
            "3. Insert pin through bushing and secure with washer and lock nut",
            "4. Connect Link 2 (coupler) to Link 1 at joint A",
            "5. Connect Link 3 (rocker) to ground anchor B",
            "6. Join Link 2 and Link 3 at joint B",
            "7. Check free rotation at all joints",
            "8. Apply grease through nipples at each joint",
            "",
            "MAINTENANCE:",
            "• Lubricate joints every 100 hours of operation",
            "• Check pin wear every 500 hours",
            "• Replace bushings if play exceeds 0.2mm",
            "• Use lithium grease NLGI 2 for joints",
            "",
            "OPERATING LIMITS:",
            "• Max speed: 300 RPM",
            "• Max load: 100N at coupler point",
            "• Temperature range: -20°C to +80°C"
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
