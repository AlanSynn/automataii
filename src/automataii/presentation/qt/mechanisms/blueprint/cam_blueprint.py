"""
CAM-specific blueprint generator with profile curves.
Creates detailed manufacturing drawings for cam mechanisms.
"""

import math
from typing import Any, SupportsFloat, SupportsIndex, cast

from .generator import BlueprintGenerator

_NumericPayload = str | bytes | bytearray | SupportsFloat | SupportsIndex


def _finite_float(value: object, default: float) -> float:
    try:
        result = float(cast(_NumericPayload, value))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _positive_finite_float(value: object, default: float) -> float:
    result = _finite_float(value, default)
    return result if result > 0.0 else default


def _non_negative_finite_float(value: object, default: float) -> float:
    result = _finite_float(value, default)
    return result if result >= 0.0 else default


class CamBlueprintGenerator(BlueprintGenerator):
    """
    Blueprint generator for cam mechanisms.

    Generates:
    - Detailed cam profile (egg shape or custom)
    - Follower assembly with rod
    - Displacement diagram
    - Velocity/acceleration curves
    - Surface finish requirements
    """

    def __init__(self):
        """Initialize cam blueprint generator."""
        super().__init__("cam")

    def _generate_front_view(self, mechanism_data: dict[str, Any]):
        """Generate front view showing cam profile and follower."""
        params = mechanism_data.get("params", {})
        viewport = self.views[0]

        # Cam parameters
        center_x = viewport.x + viewport.width / 2
        center_y = viewport.y + viewport.height / 2 + 20
        base_radius = _positive_finite_float(params.get("base_radius"), 30.0)
        eccentricity = _non_negative_finite_float(params.get("eccentricity"), 15.0)
        params.get("rotation_angle", 0)

        # Generate cam profile
        profile_points = self._generate_cam_profile(center_x, center_y, base_radius, eccentricity)

        # Follower parameters
        rod_length = _positive_finite_float(params.get("follower_rod_length"), 60.0)
        rod_diameter = _positive_finite_float(params.get("rod_diameter"), 10.0)
        follower_type = params.get("follower_type", "flat")  # flat, roller, knife

        cam_svg = f'''
        <g id="front-view-cam">
            <!-- Cam Profile -->
            {self._draw_cam_profile(profile_points, center_x, center_y, base_radius)}

            <!-- Cam Shaft -->
            <circle cx="{center_x}" cy="{center_y}" r="5"
                    stroke="black" stroke-width="0.5" fill="white"/>
            <circle cx="{center_x}" cy="{center_y}" r="2.5"
                    stroke="black" stroke-width="0.5" fill="black"/>

            <!-- Keyway -->
            <rect x="{center_x - 2}" y="{center_y - 5}"
                  width="4" height="5"
                  stroke="black" stroke-width="0.5" fill="white"/>

            <!-- Follower Assembly -->
            {
            self._draw_follower_assembly(
                center_x,
                center_y - base_radius - eccentricity,
                rod_length,
                rod_diameter,
                follower_type,
            )
        }

            <!-- Motion Path (dashed) -->
            <line x1="{center_x}" y1="{center_y - base_radius + eccentricity}"
                  x2="{center_x}" y2="{center_y - base_radius - eccentricity - rod_length - 20}"
                  stroke="blue" stroke-width="0.25" stroke-dasharray="3,2"/>

            <!-- Center lines -->
            <g stroke="gray" stroke-width="0.25" stroke-dasharray="5,5">
                <line x1="{viewport.x + 10}" y1="{center_y}"
                      x2="{viewport.x + viewport.width - 10}" y2="{center_y}"/>
                <line x1="{center_x}" y1="{viewport.y + 10}"
                      x2="{center_x}" y2="{viewport.y + viewport.height - 10}"/>
            </g>

            <!-- Profile points for manufacturing -->
            {self._add_profile_points(profile_points)}
        </g>
        '''

        self.svg_elements.append(cam_svg)

        # Add dimensions
        self._add_cam_dimensions(center_x, center_y, base_radius, eccentricity, rod_length)

    def _generate_cam_profile(
        self, cx: float, cy: float, base_r: float, ecc: float
    ) -> list[tuple[float, float]]:
        """Generate egg-shaped cam profile points."""
        points = []
        num_points = 360  # One point per degree for precision

        for i in range(num_points):
            angle = i * math.pi / 180

            # Egg shape formula: varying radius
            # Maximum radius at bottom (270°), minimum at top (90°)
            radius_variation = _non_negative_finite_float(ecc, 15.0) * math.cos(angle)
            radius = max(1e-6, _positive_finite_float(base_r, 30.0) + radius_variation)

            x = cx + radius * math.cos(angle - math.pi / 2)  # Rotate 90° for proper orientation
            y = cy + radius * math.sin(angle - math.pi / 2)

            points.append((x, y))

        return points

    def _draw_cam_profile(
        self, points: list[tuple[float, float]], cx: float, cy: float, base_radius: float
    ) -> str:
        """Draw cam profile with smooth curve."""
        # Create path from points
        path_data = f"M {points[0][0]:.2f},{points[0][1]:.2f}"

        # Use cubic bezier for smooth curve
        for i in range(1, len(points), 3):
            if i + 2 < len(points):
                # Control points for smooth curve
                cp1 = points[i]
                cp2 = points[i + 1]
                end = points[i + 2]
                path_data += f" C {cp1[0]:.2f},{cp1[1]:.2f} {cp2[0]:.2f},{cp2[1]:.2f} {end[0]:.2f},{end[1]:.2f}"

        path_data += " Z"  # Close path

        base_circle_radius = max(0.0, abs(float(base_radius)))
        return f'''
            <path d="{path_data}"
                  stroke="black" stroke-width="0.7" fill="none"/>

            <!-- Base circle reference (dashed) -->
            <circle cx="{cx}" cy="{cy}" r="{base_circle_radius}"
                    stroke="green" stroke-width="0.25" stroke-dasharray="2,2" fill="none"/>
        '''

    def _draw_follower_assembly(
        self, x: float, y: float, rod_length: float, rod_diameter: float, follower_type: str
    ) -> str:
        """Draw follower with rod and guide."""
        follower_svg = f'''
        <g id="follower-assembly">
            <!-- Guide Housing -->
            <rect x="{x - 15}" y="{y - rod_length - 30}"
                  width="30" height="{rod_length + 20}"
                  stroke="black" stroke-width="0.5" fill="none"/>

            <!-- Guide Bore -->
            <rect x="{x - rod_diameter / 2 - 1}" y="{y - rod_length - 25}"
                  width="{rod_diameter + 2}" height="{rod_length + 15}"
                  stroke="black" stroke-width="0.5" fill="white"/>

            <!-- Follower Rod -->
            <rect x="{x - rod_diameter / 2}" y="{y - rod_length}"
                  width="{rod_diameter}" height="{rod_length}"
                  stroke="black" stroke-width="0.7" fill="none"/>

            <!-- Cross-hatching for rod -->
            <g stroke="black" stroke-width="0.25">
        '''

        # Add cross-hatching pattern
        for i in range(5, int(rod_length), 5):
            follower_svg += f'''
                <line x1="{x - rod_diameter / 2}" y1="{y - i}"
                      x2="{x + rod_diameter / 2}" y2="{y - i - 3}"/>
            '''

        # Add follower tip based on type
        if follower_type == "flat":
            follower_svg += f'''
            </g>
            <!-- Flat Follower -->
            <rect x="{x - rod_diameter / 2 - 2}" y="{y - 3}"
                  width="{rod_diameter + 4}" height="6"
                  stroke="black" stroke-width="0.7" fill="gray"/>
            '''
        elif follower_type == "roller":
            follower_svg += f'''
            </g>
            <!-- Roller Follower -->
            <circle cx="{x}" cy="{y}" r="{rod_diameter / 2 + 2}"
                    stroke="black" stroke-width="0.7" fill="white"/>
            <circle cx="{x}" cy="{y}" r="2"
                    stroke="black" stroke-width="0.5" fill="black"/>
            '''
        else:  # knife edge
            follower_svg += f"""
            </g>
            <!-- Knife Edge Follower -->
            <path d="M {x - rod_diameter / 2},{y} L {x},{y + 5} L {x + rod_diameter / 2},{y} Z"
                  stroke="black" stroke-width="0.7" fill="gray"/>
            """

        # Spring representation
        follower_svg += """
            <!-- Return Spring -->
            <g stroke="black" stroke-width="0.5" fill="none">
        """

        spring_top = y - rod_length - 20
        for i in range(8):
            y_pos = spring_top + i * 3
            if i % 2 == 0:
                follower_svg += f"""
                <path d="M {x - 8},{y_pos} Q {x},{y_pos + 1.5} {x + 8},{y_pos + 3}"/>
                """

        follower_svg += """
            </g>
        </g>
        """

        return follower_svg

    def _add_profile_points(self, points: list[tuple[float, float]]) -> str:
        """Add manufacturing reference points on profile."""
        # Show key points every 30 degrees
        point_markers = ""
        for i in range(0, 360, 30):
            if i < len(points):
                x, y = points[i]
                point_markers += f'''
                    <circle cx="{x}" cy="{y}" r="1" fill="red"/>
                    <text x="{x + 3}" y="{y - 2}" font-size="5" font-family="Arial">
                        {i}°
                    </text>
                '''

        return f'<g id="profile-points">{point_markers}</g>'

    def _generate_side_view(self, mechanism_data: dict[str, Any]):
        """Generate side view showing cam thickness."""
        params = mechanism_data.get("params", {})
        viewport = self.views[2]

        cam_thickness = params.get("thickness", 15)
        shaft_diameter = params.get("shaft_diameter", 10)
        hub_diameter = params.get("hub_diameter", 20)

        side_view_svg = f'''
        <g id="side-view-cam">
            <!-- Cam body -->
            <rect x="{viewport.x + 40}" y="{viewport.y + 30}"
                  width="{cam_thickness}" height="60"
                  stroke="black" stroke-width="0.5" fill="none"/>

            <!-- Hub -->
            <rect x="{viewport.x + 40 - 5}" y="{viewport.y + 50}"
                  width="{cam_thickness + 10}" height="{hub_diameter}"
                  stroke="black" stroke-width="0.5" fill="none"/>

            <!-- Shaft hole -->
            <rect x="{viewport.x + 42}" y="{viewport.y + 55}"
                  width="{cam_thickness - 4}" height="{shaft_diameter}"
                  stroke="black" stroke-width="0.5" fill="white"/>

            <!-- Surface finish indication -->
            <g stroke="black" stroke-width="0.25">
                <line x1="{viewport.x + 40}" y1="{viewport.y + 30}"
                      x2="{viewport.x + 38}" y2="{viewport.y + 28}"/>
                <line x1="{viewport.x + 38}" y1="{viewport.y + 28}"
                      x2="{viewport.x + 38}" y2="{viewport.y + 25}"/>
                <text x="{viewport.x + 35}" y="{viewport.y + 23}"
                      font-size="5" font-family="Arial">Ra 0.8</text>
            </g>
        </g>
        '''

        self.svg_elements.append(side_view_svg)

    def _generate_isometric_view(self, mechanism_data: dict[str, Any]):
        """Generate displacement diagram."""
        viewport = self.views[3]

        # Generate displacement curve
        displacement_svg = f'''
        <g id="displacement-diagram">
            <text x="{viewport.x + 5}" y="{viewport.y + 15}"
                  font-size="7" font-family="Arial" font-weight="bold">
                DISPLACEMENT DIAGRAM
            </text>

            <!-- Axes -->
            <line x1="{viewport.x + 20}" y1="{viewport.y + 80}"
                  x2="{viewport.x + 180}" y2="{viewport.y + 80}"
                  stroke="black" stroke-width="0.5"/>
            <line x1="{viewport.x + 20}" y1="{viewport.y + 20}"
                  x2="{viewport.x + 20}" y2="{viewport.y + 80}"
                  stroke="black" stroke-width="0.5"/>

            <!-- Grid -->
            <g stroke="gray" stroke-width="0.25" stroke-dasharray="1,1">
        '''

        # Add grid lines
        for i in range(1, 7):
            x = viewport.x + 20 + i * 25
            displacement_svg += f'''
                <line x1="{x}" y1="{viewport.y + 20}" x2="{x}" y2="{viewport.y + 80}"/>
            '''

        for i in range(1, 4):
            y = viewport.y + 20 + i * 20
            displacement_svg += f'''
                <line x1="{viewport.x + 20}" y1="{y}" x2="{viewport.x + 180}" y2="{y}"/>
            '''

        displacement_svg += """
            </g>

            <!-- Displacement curve -->
            <path d="M 230,80 Q 255,60 280,40 T 330,40 Q 355,60 380,80"
                  stroke="blue" stroke-width="1" fill="none"/>

            <!-- Labels -->
            <text x="250" y="95" font-size="6" font-family="Arial">90°</text>
            <text x="300" y="95" font-size="6" font-family="Arial">180°</text>
            <text x="350" y="95" font-size="6" font-family="Arial">270°</text>

            <text x="210" y="45" font-size="6" font-family="Arial">15mm</text>
            <text x="210" y="65" font-size="6" font-family="Arial">7.5mm</text>

            <text x="290" y="100" font-size="6" font-family="Arial">CAM ANGLE</text>
            <text x="205" y="50" font-size="6" font-family="Arial"
                  transform="rotate(-90 205 50)">LIFT</text>
        </g>
        """

        self.svg_elements.append(displacement_svg)

    def _add_cam_dimensions(
        self, cx: float, cy: float, base_r: float, ecc: float, rod_length: float
    ):
        """Add cam-specific dimensions."""
        # Base radius
        self.dimensions.append(self.create_radius_dimension(cx, cy, base_r, 45))

        # Maximum radius
        self.dimensions.append(self.create_radius_dimension(cx, cy, base_r + ecc, 225))

        # Eccentricity
        self.dimensions.append(
            self.create_dimension_line(
                cx + base_r + 5, cy, cx + base_r + ecc + 5, cy, f"e={ecc}±0.05", 8
            )
        )

        # Rod length
        self.dimensions.append(
            self.create_dimension_line(
                cx + 20,
                cy - base_r - ecc,
                cx + 20,
                cy - base_r - ecc - rod_length,
                f"{rod_length}±0.1",
                10,
            )
        )

    def _add_tolerances(self, mechanism_data: dict[str, Any]):
        """Add cam-specific tolerances."""
        super()._add_tolerances(mechanism_data)

        cam_tolerances = """
        <g id="cam-tolerances" font-size="6" font-family="Arial">
            <text x="140" y="260">CAM SPECIFICATIONS:</text>
            <text x="140" y="266">PROFILE TOLERANCE: ±0.02mm</text>
            <text x="140" y="272">SURFACE FINISH: Ra 0.8μm</text>
            <text x="240" y="260">FOLLOWER CLEARANCE: 0.02-0.05mm</text>
            <text x="240" y="266">HARDNESS: HRC 58-62</text>
            <text x="240" y="272">LUBRICATION: ISO VG 32</text>
        </g>
        """

        self.svg_elements.append(cam_tolerances)

    def _add_part_list(self, mechanism_data: dict[str, Any]):
        """Add cam-specific part list."""
        parts = [
            {"name": "CAM DISC", "quantity": 1, "material": "TOOL STEEL"},
            {"name": "FOLLOWER ROD", "quantity": 1, "material": "HARDENED STEEL"},
            {"name": "GUIDE BUSHING", "quantity": 2, "material": "BRONZE"},
            {"name": "RETURN SPRING", "quantity": 1, "material": "SPRING STEEL"},
            {"name": "SHAFT KEY", "quantity": 1, "material": "STEEL"},
        ]

        mechanism_data["parts"] = parts
        super()._add_part_list(mechanism_data)
