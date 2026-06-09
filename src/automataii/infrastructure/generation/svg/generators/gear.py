"""
Gear SVG Generator - Gear and planetary gear SVG generation.

Extracted from EnhancedMechanismProcessor (blueprint_optimizer.py).
Handles manufacturing-ready SVG generation for gear mechanisms.

Design Pattern: Generator (focused SVG generation)
"""

from __future__ import annotations

import math
from typing import Any

from automataii.domain.generation.layout import ScaledBounds


class GearSVGGenerator:
    """
    Generates manufacturing-ready SVG for gear mechanisms.

    Responsibilities:
    - Generate two-gear mesh SVG with manufacturing specifications
    - Generate planetary gear system SVG
    - Generate detailed gear with teeth, hub, keyway

    Time Complexity: O(t) where t = number of teeth
    """

    # Manufacturing specifications
    MODULE_MM = 2.0  # Standard gear module
    HUB_RATIO = 0.4  # Hub diameter = 40% of gear diameter
    SHAFT_DIAMETER_MM = 6.0
    MIN_TEETH = 8

    def generate_gear_mesh_svg(
        self,
        mech_data: dict[str, Any],
        bounds: ScaledBounds,
        mm_params_func: Any | None = None,
    ) -> str:
        """
        Generate two-gear mesh with manufacturing specifications.

        Args:
            mech_data: Mechanism data with radii and key_points
            bounds: SVG bounds for scaling
            mm_params_func: Optional function to get mm parameters

        Returns:
            SVG string for gear mesh
        """
        # Get gear radii
        if mm_params_func:
            mm = mm_params_func(mech_data, ["r1_mm", "r2_mm"])
        else:
            mm = self._get_mm_params(mech_data, ["r1_mm", "r2_mm"])

        r1 = mm.get("r1_mm", 30.0)
        r2 = mm.get("r2_mm", 20.0)

        # Get centers from key_points or calculate
        kp = mech_data.get("key_points", {})
        factor = float(mech_data.get("total_scale_factor", 1.0))

        if "gear1_center" in kp and "gear2_center" in kp:
            x1, y1 = kp["gear1_center"]
            x2, y2 = kp["gear2_center"]
            c1 = (float(x1) * factor, float(y1) * factor)
            c2 = (float(x2) * factor, float(y2) * factor)
        else:
            c1 = (0.0, 0.0)
            c2 = (r1 + r2, 0.0)

        # Calculate bounds
        xs = [c1[0] - r1, c1[0] + r1, c2[0] - r2, c2[0] + r2]
        ys = [c1[1] - r1, c1[1] + r1, c2[1] - r2, c2[1] + r2]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max(10.0, max_x - min_x)
        height = max(10.0, max_y - min_y)

        margin = 8.0
        avail_w = max(10.0, bounds.width - 2 * margin)
        avail_h = max(10.0, bounds.height - 2 * margin)
        scale = min(1.0, avail_w / width, avail_h / height)

        def pack(pt: tuple[float, float]) -> tuple[float, float]:
            return (pt[0] - min_x) * scale + margin, (pt[1] - min_y) * scale + margin

        c1p = pack(c1)
        c2p = pack(c2)
        r1p = r1 * scale
        r2p = r2 * scale

        # Calculate teeth
        teeth1 = max(int(2 * r1 / self.MODULE_MM), self.MIN_TEETH)
        teeth2 = max(int(2 * r2 / self.MODULE_MM), self.MIN_TEETH)

        parts = [self._generate_gradients()]

        # Generate gears
        parts.append(
            self._generate_detailed_gear(c1p, r1p, teeth1, "gear-gradient-1", "Gear 1", r1, scale)
        )
        parts.append(
            self._generate_detailed_gear(c2p, r2p, teeth2, "gear-gradient-2", "Gear 2", r2, scale)
        )

        # Center distance line
        parts.append(f"""
        <line x1="{c1p[0]:.1f}" y1="{c1p[1]:.1f}" x2="{c2p[0]:.1f}" y2="{c2p[1]:.1f}"
              stroke="#666" stroke-width="0.8" stroke-dasharray="3,3"/>
        <text x="{(c1p[0] + c2p[0]) / 2:.1f}" y="{(c1p[1] + c2p[1]) / 2 - 8:.1f}"
              font-size="7" text-anchor="middle" fill="#666">
              Center: {r1 + r2:.1f}mm
        </text>
        """)

        # Gear ratio and specs panel
        gear_ratio = r1 / r2 if r2 > 0 else 1.0
        parts.append(self._generate_spec_panel(bounds, r1, r2, teeth1, teeth2, gear_ratio))

        return "".join(parts)

    def generate_planetary_gear_svg(
        self,
        mech_data: dict[str, Any],
        bounds: ScaledBounds,
        mm_params_func: Any | None = None,
    ) -> str:
        """
        Generate planetary gear system SVG.

        Args:
            mech_data: Mechanism data with sun/planet radii
            bounds: SVG bounds for scaling
            mm_params_func: Optional function to get mm parameters

        Returns:
            SVG string for planetary gear system
        """
        if mm_params_func:
            mm = mm_params_func(mech_data, ["r_sun_mm", "r_planet_mm"])
        else:
            mm = self._get_mm_params(mech_data, ["r_sun_mm", "r_planet_mm"])

        rs = mm.get("r_sun_mm", 20.0)
        rp = mm.get("r_planet_mm", 12.0)
        rr = rs + 2 * rp  # Ring gear radius
        num_planets = 3

        kp = mech_data.get("key_points", {})
        factor = float(mech_data.get("total_scale_factor", 1.0))

        if "sun_center" in kp:
            sx, sy = kp["sun_center"]
            center = (float(sx) * factor, float(sy) * factor)
        else:
            center = (rr, rr)

        # Calculate bounds
        outer_r = rr + 10
        min_x, max_x = center[0] - outer_r, center[0] + outer_r
        min_y, max_y = center[1] - outer_r, center[1] + outer_r
        width = max(10.0, max_x - min_x)
        height = max(10.0, max_y - min_y)

        margin = 8.0
        avail_w = max(10.0, bounds.width - 2 * margin)
        avail_h = max(10.0, bounds.height - 2 * margin)
        scale = min(1.0, avail_w / width, avail_h / height)

        def pack(pt: tuple[float, float]) -> tuple[float, float]:
            return (pt[0] - min_x) * scale + margin, (pt[1] - min_y) * scale + margin

        cp = pack(center)
        rsp = rs * scale
        rpp = rp * scale
        rrp = rr * scale

        parts = [self._generate_planetary_gradients()]

        # Ring gear (outer)
        parts.append(f"""
        <circle cx="{cp[0]:.1f}" cy="{cp[1]:.1f}" r="{rrp:.1f}"
                fill="none" stroke="#34495e" stroke-width="3"/>
        <circle cx="{cp[0]:.1f}" cy="{cp[1]:.1f}" r="{rrp + 5:.1f}"
                fill="none" stroke="#7f8c8d" stroke-width="1" stroke-dasharray="2,2"/>
        """)

        # Sun gear (center)
        sun_teeth = max(int(2 * rs / self.MODULE_MM), self.MIN_TEETH)
        parts.append(
            self._generate_detailed_gear(cp, rsp, sun_teeth, "sun-gradient", "Sun", rs, scale)
        )

        # Planet gears
        planet_orbit_r = rs + rp
        planet_teeth = max(int(2 * rp / self.MODULE_MM), self.MIN_TEETH)

        for i in range(num_planets):
            angle = (2 * math.pi * i) / num_planets
            px = cp[0] + planet_orbit_r * scale * math.cos(angle)
            py = cp[1] + planet_orbit_r * scale * math.sin(angle)
            parts.append(
                self._generate_detailed_gear(
                    (px, py), rpp, planet_teeth, "planet-gradient", f"P{i + 1}", rp, scale
                )
            )

        # Carrier arm
        parts.append(f"""
        <circle cx="{cp[0]:.1f}" cy="{cp[1]:.1f}" r="{planet_orbit_r * scale:.1f}"
                fill="none" stroke="#e74c3c" stroke-width="1" stroke-dasharray="5,3"/>
        """)

        return "".join(parts)

    def _generate_detailed_gear(
        self,
        center: tuple[float, float],
        radius: float,
        teeth: int,
        gradient_id: str,
        gear_name: str,
        actual_radius_mm: float,
        scale: float,
    ) -> str:
        """Generate detailed gear with teeth, hub, and keyway."""
        cx, cy = center
        hub_radius = radius * self.HUB_RATIO
        shaft_radius = (self.SHAFT_DIAMETER_MM / 2) * scale
        tooth_height = max(2.0 * scale, 1.0)
        keyway_width = max(2.0 * scale, 1.0)

        parts = []

        # Main gear body
        parts.append(f"""
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}"
                fill="url(#{gradient_id})" stroke="#34495e" stroke-width="1.5"/>
        """)

        # Simplified teeth
        tooth_count = max(teeth, 8)
        for i in range(tooth_count):
            angle = (2 * math.pi * i) / tooth_count
            tooth_x = cx + (radius + tooth_height / 2) * math.cos(angle)
            tooth_y = cy + (radius + tooth_height / 2) * math.sin(angle)
            parts.append(f"""
            <circle cx="{tooth_x:.1f}" cy="{tooth_y:.1f}" r="{tooth_height / 3:.1f}"
                    fill="#bdc3c7" stroke="#95a5a6" stroke-width="0.5"/>
            """)

        # Hub
        parts.append(f"""
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{hub_radius:.1f}"
                fill="url(#{gradient_id})" stroke="#2c3e50" stroke-width="1.2"/>
        """)

        # Mounting holes
        for i in range(4):
            hole_angle = (2 * math.pi * i) / 4
            hole_radius = hub_radius * 0.7
            hole_x = cx + hole_radius * math.cos(hole_angle)
            hole_y = cy + hole_radius * math.sin(hole_angle)
            parts.append(f"""
            <circle cx="{hole_x:.1f}" cy="{hole_y:.1f}" r="{shaft_radius * 0.6:.1f}"
                    fill="#fff" stroke="#7f8c8d" stroke-width="0.8"/>
            """)

        # Center shaft hole
        parts.append(f"""
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{shaft_radius:.1f}"
                fill="#fff" stroke="#2c3e50" stroke-width="1"/>
        """)

        # Keyway
        parts.append(f"""
        <rect x="{cx - keyway_width / 2:.1f}" y="{cy - shaft_radius:.1f}"
              width="{keyway_width:.1f}" height="{shaft_radius * 0.6:.1f}" fill="#7f8c8d"/>
        """)

        # Label
        parts.append(f"""
        <text x="{cx:.1f}" y="{cy - radius - 10:.1f}"
              font-size="8" text-anchor="middle" font-weight="bold">{gear_name}</text>
        <text x="{cx:.1f}" y="{cy - radius - 2:.1f}"
              font-size="6" text-anchor="middle" fill="#666">
              ⌀{actual_radius_mm * 2:.1f}mm ({teeth}T)
        </text>
        """)

        return "".join(parts)

    def _generate_gradients(self) -> str:
        """Generate gear gradients."""
        return """
        <defs>
            <linearGradient id="gear-gradient-1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#e8f4f8"/>
                <stop offset="50%" style="stop-color:#d1e9f0"/>
                <stop offset="100%" style="stop-color:#a0c4d1"/>
            </linearGradient>
            <linearGradient id="gear-gradient-2" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#f5f0e8"/>
                <stop offset="50%" style="stop-color:#ede4d1"/>
                <stop offset="100%" style="stop-color:#d4c8a0"/>
            </linearGradient>
        </defs>
        """

    def _generate_planetary_gradients(self) -> str:
        """Generate planetary gear gradients."""
        return """
        <defs>
            <linearGradient id="sun-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#f9e79f"/>
                <stop offset="50%" style="stop-color:#f4d03f"/>
                <stop offset="100%" style="stop-color:#d4ac0d"/>
            </linearGradient>
            <linearGradient id="planet-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#aed6f1"/>
                <stop offset="50%" style="stop-color:#5dade2"/>
                <stop offset="100%" style="stop-color:#2980b9"/>
            </linearGradient>
        </defs>
        """

    def _generate_spec_panel(
        self,
        bounds: ScaledBounds,
        r1: float,
        r2: float,
        teeth1: int,
        teeth2: int,
        gear_ratio: float,
    ) -> str:
        """Generate gear specifications panel."""
        return f"""
        <g class="gear-manufacturing-specs">
            <rect x="{bounds.width - 160}" y="10" width="150" height="140"
                  fill="#f8f9fa" stroke="#dee2e6" stroke-width="1" rx="3"/>
            <text x="{bounds.width - 155}" y="25" font-size="8" font-weight="bold">
                Gear Specifications
            </text>
            <text x="{bounds.width - 155}" y="40" font-size="7" font-weight="bold" fill="#2c3e50">
                Gear 1 (Drive):
            </text>
            <text x="{bounds.width - 155}" y="52" font-size="6">
                • Diameter: {2 * r1:.1f}mm ({teeth1} teeth)
            </text>
            <text x="{bounds.width - 155}" y="62" font-size="6">
                • Module: {self.MODULE_MM:.1f}mm
            </text>
            <text x="{bounds.width - 155}" y="87" font-size="7" font-weight="bold" fill="#8e44ad">
                Gear 2 (Driven):
            </text>
            <text x="{bounds.width - 155}" y="99" font-size="6">
                • Diameter: {2 * r2:.1f}mm ({teeth2} teeth)
            </text>
            <text x="{bounds.width - 155}" y="109" font-size="6">
                • Module: {self.MODULE_MM:.1f}mm
            </text>
            <text x="{bounds.width - 155}" y="130" font-size="7" font-weight="bold" fill="#e74c3c">
                Ratio: {gear_ratio:.2f}:1
            </text>
        </g>
        """

    def _get_mm_params(self, mech_data: dict[str, Any], names: list[str]) -> dict[str, float]:
        """Get parameters in mm."""
        mm = {}
        rwp = mech_data.get("real_world_params", {})
        if rwp:
            for n in names:
                if n in rwp:
                    mm[n] = float(rwp[n])
        return mm
