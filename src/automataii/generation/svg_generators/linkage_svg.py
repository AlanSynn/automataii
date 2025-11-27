"""
Linkage SVG Generator - 4-bar and multi-bar linkage SVG generation.

Extracted from EnhancedMechanismProcessor (blueprint_optimizer.py).
Handles manufacturing-ready SVG generation for linkage mechanisms.

Design Pattern: Generator (focused SVG generation)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScaledBounds:
    """Bounds for SVG generation."""

    x: float
    y: float
    width: float
    height: float


class LinkageSVGGenerator:
    """
    Generates manufacturing-ready SVG for linkage mechanisms.

    Responsibilities:
    - Generate 4-bar linkage SVG with thickness, holes, manufacturing details
    - Generate multi-bar (5/6-bar) linkage SVG
    - Create manufacturing specification panels

    Time Complexity: O(n) where n = number of links
    """

    # Manufacturing specifications
    LINK_THICKNESS_MM = 6.0
    HOLE_DIAMETER_MM = 5.0
    PIN_DIAMETER_MM = 4.0
    JOINT_DIAMETER_MM = 8.0

    # Link colors
    COLOR_GROUND = "#2c3e50"
    COLOR_CRANK = "#e74c3c"
    COLOR_COUPLER = "#27ae60"
    COLOR_ROCKER = "#2980b9"

    def generate_4bar_svg(
        self,
        mech_data: dict[str, Any],
        bounds: ScaledBounds,
        fallback_generator: Any | None = None,
    ) -> str:
        """
        Generate detailed 4-bar linkage with manufacturing details.

        Args:
            mech_data: Mechanism data with key_points
            bounds: SVG bounds for scaling
            fallback_generator: Optional fallback for standard SVG

        Returns:
            SVG string for the 4-bar linkage
        """
        kp = mech_data.get("key_points", {})
        factor = float(mech_data.get("total_scale_factor", 1.0))

        required = ["ground_pivot_1", "ground_pivot_2", "crank_end", "rocker_end"]
        if not all(name in kp for name in required):
            if fallback_generator:
                return fallback_generator(
                    mech_data.get("id", "mech"), "4_bar_linkage", bounds
                )
            return ""

        # Extract key points
        def to_mm(name: str) -> tuple[float, float]:
            x, y = kp[name]
            return float(x) * factor, float(y) * factor

        O1 = to_mm("ground_pivot_1")
        O2 = to_mm("ground_pivot_2")
        A = to_mm("crank_end")
        B = to_mm("rocker_end")

        # Calculate bounds
        xs = [O1[0], O2[0], A[0], B[0]]
        ys = [O1[1], O2[1], A[1], B[1]]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max_x - min_x
        height = max_y - min_y

        # Scale to fit bounds
        margin = 8.0
        avail_w = max(10.0, bounds.width - 2 * margin)
        avail_h = max(10.0, bounds.height - 2 * margin)
        scale = min(
            1.0,
            avail_w / width if width > 0 else 1.0,
            avail_h / height if height > 0 else 1.0,
        )

        def pack(pt: tuple[float, float]) -> tuple[float, float]:
            px = (pt[0] - min_x) * scale + margin
            py = (pt[1] - min_y) * scale + margin
            return px, py

        O1p = pack(O1)
        O2p = pack(O2)
        Ap = pack(A)
        Bp = pack(B)

        # Scaled manufacturing parameters
        link_thickness = self.LINK_THICKNESS_MM * scale
        hole_radius = (self.HOLE_DIAMETER_MM / 2) * scale
        joint_radius = (self.JOINT_DIAMETER_MM / 2) * scale

        # Calculate link lengths
        def dist_mm(p_mm: tuple[float, float], q_mm: tuple[float, float]) -> float:
            dx = p_mm[0] - q_mm[0]
            dy = p_mm[1] - q_mm[1]
            return math.hypot(dx, dy)

        L1_ground = dist_mm(O1, O2)
        L2_crank = dist_mm(O1, A)
        L3_coupler = dist_mm(A, B)
        L4_rocker = dist_mm(B, O2)

        # Build SVG parts
        parts = [self._generate_gradients()]

        # Generate links
        parts.append(
            self._manufacturing_link(
                O1p, O2p, self.COLOR_GROUND, "Ground", L1_ground, link_thickness, hole_radius
            )
        )
        parts.append(
            self._manufacturing_link(
                O1p, Ap, self.COLOR_CRANK, "Crank", L2_crank, link_thickness, hole_radius
            )
        )
        parts.append(
            self._manufacturing_link(
                Ap, Bp, self.COLOR_COUPLER, "Coupler", L3_coupler, link_thickness, hole_radius
            )
        )
        parts.append(
            self._manufacturing_link(
                Bp, O2p, self.COLOR_ROCKER, "Rocker", L4_rocker, link_thickness, hole_radius
            )
        )

        # Add pivot points
        parts.append(self._generate_pivot(O1p, joint_radius, "Ground Pivot 1"))
        parts.append(self._generate_pivot(O2p, joint_radius, "Ground Pivot 2"))
        parts.append(self._generate_moving_joint(Ap, joint_radius))
        parts.append(self._generate_moving_joint(Bp, joint_radius))

        # Add manufacturing specs panel
        parts.append(self._generate_spec_panel(bounds))

        return "".join(parts)

    def generate_multibar_svg(
        self, mech_data: dict[str, Any], bounds: ScaledBounds
    ) -> str:
        """
        Generate N-bar (5/6-bar) linkage SVG.

        Args:
            mech_data: Mechanism data with key_points
            bounds: SVG bounds for scaling

        Returns:
            SVG string for multi-bar linkage
        """
        kp = mech_data.get("key_points", {})
        factor = float(mech_data.get("total_scale_factor", 1.0))

        names_order = [
            "ground_pivot_1",
            "joint_3",
            "joint_4",
            "joint_5",
            "ground_pivot_2",
        ]
        pts_mm = []
        for name in names_order:
            if name in kp:
                x, y = kp[name]
                pts_mm.append((float(x) * factor, float(y) * factor, name))

        if len(pts_mm) < 3:
            return ""

        # Calculate bounds
        xs = [p[0] for p in pts_mm]
        ys = [p[1] for p in pts_mm]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max(10.0, max_x - min_x)
        height = max(10.0, max_y - min_y)

        margin = 8.0
        avail_w = max(10.0, bounds.width - 2 * margin)
        avail_h = max(10.0, bounds.height - 2 * margin)
        scale = min(1.0, avail_w / width, avail_h / height)

        def pack_xy(x: float, y: float) -> tuple[float, float]:
            return (x - min_x) * scale + margin, (y - min_y) * scale + margin

        colors = ["#e74c3c", "#27ae60", "#2980b9", "#8e44ad"]
        parts = []

        # Draw segments
        for i in range(len(pts_mm) - 1):
            (x1, y1, _), (x2, y2, _) = pts_mm[i], pts_mm[i + 1]
            px1, py1 = pack_xy(x1, y1)
            px2, py2 = pack_xy(x2, y2)
            color = colors[i % len(colors)]
            parts.append(
                f'<line x1="{px1:.1f}" y1="{py1:.1f}" x2="{px2:.1f}" y2="{py2:.1f}" '
                f'stroke="{color}" stroke-width="2"/>'
            )

        # Draw joints and labels
        for x, y, name in pts_mm:
            px, py = pack_xy(x, y)
            parts.append(
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" '
                f'fill="none" stroke="#333" stroke-width="1.2"/>'
            )
            parts.append(
                f'<text x="{px:.1f}" y="{py - 7:.1f}" '
                f'class="mechanism-label" font-size="7" text-anchor="middle">{name}</text>'
            )

        return "<g>" + "".join(parts) + "</g>"

    def _manufacturing_link(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        color: str,
        name: str,
        length_mm: float,
        thickness: float,
        hole_radius: float,
    ) -> str:
        """Generate manufacturing-ready link with thickness and holes."""
        x1, y1 = p1
        x2, y2 = p2

        dx = x2 - x1
        dy = y2 - y1
        angle = math.atan2(dy, dx)
        half_thick = thickness / 2
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Corner points
        p1_tl = (x1 + half_thick * sin_a, y1 - half_thick * cos_a)
        p1_bl = (x1 - half_thick * sin_a, y1 + half_thick * cos_a)
        p2_br = (x2 - half_thick * sin_a, y2 + half_thick * cos_a)
        p2_tr = (x2 + half_thick * sin_a, y2 - half_thick * cos_a)

        return f"""
        <!-- {name} link body -->
        <path d="M{p1_tl[0]:.1f},{p1_tl[1]:.1f}
                 L{p2_tr[0]:.1f},{p2_tr[1]:.1f}
                 A{half_thick:.1f},{half_thick:.1f} 0 0,1 {p2_br[0]:.1f},{p2_br[1]:.1f}
                 L{p1_bl[0]:.1f},{p1_bl[1]:.1f}
                 A{half_thick:.1f},{half_thick:.1f} 0 0,1 {p1_tl[0]:.1f},{p1_tl[1]:.1f} Z"
              fill="url(#gradient-{name})" stroke="{color}" stroke-width="1.5"/>

        <!-- End holes -->
        <circle cx="{x1:.1f}" cy="{y1:.1f}" r="{hole_radius:.1f}"
                fill="#fff" stroke="{color}" stroke-width="1"/>
        <circle cx="{x2:.1f}" cy="{y2:.1f}" r="{hole_radius:.1f}"
                fill="#fff" stroke="{color}" stroke-width="1"/>

        <!-- Dimension label -->
        <text x="{(x1+x2)/2:.1f}" y="{(y1+y2)/2 - 18:.1f}"
              class="dimension-text" font-size="7" text-anchor="middle" fill="{color}">
              {name} {length_mm:.1f}mm
        </text>
        """

    def _generate_gradients(self) -> str:
        """Generate SVG gradients for link appearance."""
        return """
        <defs>
            <linearGradient id="gradient-Ground" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#34495e;stop-opacity:1"/>
                <stop offset="50%" style="stop-color:#2c3e50;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#1a252f;stop-opacity:1"/>
            </linearGradient>
            <linearGradient id="gradient-Crank" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#ec7063;stop-opacity:1"/>
                <stop offset="50%" style="stop-color:#e74c3c;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#c0392b;stop-opacity:1"/>
            </linearGradient>
            <linearGradient id="gradient-Coupler" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#58d68d;stop-opacity:1"/>
                <stop offset="50%" style="stop-color:#27ae60;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#1e8449;stop-opacity:1"/>
            </linearGradient>
            <linearGradient id="gradient-Rocker" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#5dade2;stop-opacity:1"/>
                <stop offset="50%" style="stop-color:#2980b9;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#1f618d;stop-opacity:1"/>
            </linearGradient>
        </defs>
        """

    def _generate_pivot(
        self, pos: tuple[float, float], radius: float, label: str
    ) -> str:
        """Generate ground pivot with mounting base."""
        x, y = pos
        return f"""
        <circle cx="{x:.1f}" cy="{y:.1f}" r="{radius * 1.5:.1f}"
                fill="#34495e" stroke="#2c3e50" stroke-width="2"/>
        <circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}"
                fill="none" stroke="#fff" stroke-width="1"/>
        <text x="{x:.1f}" y="{y + 25:.1f}" class="manufacturing-note"
              font-size="6" text-anchor="middle" fill="#333">{label}</text>
        """

    def _generate_moving_joint(
        self, pos: tuple[float, float], radius: float
    ) -> str:
        """Generate moving joint marker."""
        x, y = pos
        return f"""
        <circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}"
                fill="#f39c12" stroke="#e67e22" stroke-width="1.5"/>
        """

    def _generate_spec_panel(self, bounds: ScaledBounds) -> str:
        """Generate manufacturing specifications panel."""
        return f"""
        <g class="manufacturing-specs">
            <rect x="{bounds.width - 150}" y="10" width="140" height="120"
                  fill="#f8f9fa" stroke="#dee2e6" stroke-width="1" rx="3"/>
            <text x="{bounds.width - 145}" y="25" font-size="8" font-weight="bold">
                Manufacturing Specifications
            </text>
            <text x="{bounds.width - 145}" y="40" font-size="7">
                Material: 6mm Steel Bar
            </text>
            <text x="{bounds.width - 145}" y="52" font-size="7">
                Hole Diameter: 5mm (for 4mm pins)
            </text>
            <text x="{bounds.width - 145}" y="64" font-size="7">
                Pin Diameter: 4mm Steel
            </text>
            <text x="{bounds.width - 145}" y="76" font-size="7">
                Ground Mount: 8mm holes
            </text>
            <text x="{bounds.width - 145}" y="88" font-size="7">
                Tolerance: ±0.1mm
            </text>
            <text x="{bounds.width - 145}" y="105" font-size="7" font-weight="bold">
                Assembly Order:
            </text>
            <text x="{bounds.width - 145}" y="117" font-size="6">
                1. Ground → 2. Crank → 3. Coupler → 4. Rocker
            </text>
        </g>
        """
