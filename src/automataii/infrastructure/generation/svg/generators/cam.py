"""
Cam SVG Generator - Cam mechanism SVG generation.

Extracted from EnhancedMechanismProcessor (blueprint_optimizer.py).
Handles manufacturing-ready SVG generation for cam mechanisms.

Design Pattern: Generator (focused SVG generation)
"""

from __future__ import annotations

import math
from typing import Any, SupportsFloat, SupportsIndex, cast

from automataii.domain.generation.layout import ScaledBounds

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


class CamSVGGenerator:
    """
    Generates manufacturing-ready SVG for cam mechanisms.

    Responsibilities:
    - Generate cam profile SVG with follower
    - Generate cam manufacturing specifications
    - Calculate cam profile points

    Time Complexity: O(p) where p = number of profile points
    """

    # Manufacturing specifications
    CAM_COLOR = "#3498db"
    FOLLOWER_COLOR = "#e74c3c"
    PROFILE_POINTS = 72  # Default number of profile points

    def generate_cam_svg(
        self,
        mech_data: dict[str, Any],
        bounds: ScaledBounds,
        mm_params_func: Any | None = None,
    ) -> str:
        """
        Generate cam mechanism SVG with follower.

        Args:
            mech_data: Mechanism data with cam profile parameters
            bounds: SVG bounds for scaling
            mm_params_func: Optional function to get mm parameters

        Returns:
            SVG string for cam mechanism
        """
        if mm_params_func:
            mm = mm_params_func(
                mech_data,
                ["base_radius_mm", "lift_mm", "eccentricity_mm", "follower_radius_mm"],
            )
        else:
            mm = self._get_mm_params(
                mech_data,
                ["base_radius_mm", "lift_mm", "eccentricity_mm", "follower_radius_mm"],
            )

        base_r = _positive_finite_float(mm.get("base_radius_mm"), 30.0)
        lift = _non_negative_finite_float(
            mm.get("lift_mm", mm.get("eccentricity_mm")),
            15.0,
        )
        follower_r = _positive_finite_float(mm.get("follower_radius_mm"), 8.0)

        # Get center from key_points or default
        kp = mech_data.get("key_points", {})
        factor = float(mech_data.get("total_scale_factor", 1.0))

        if "cam_center" in kp:
            cx, cy = kp["cam_center"]
            center = (
                _finite_float(cx, base_r + lift + 20) * factor,
                _finite_float(cy, base_r + lift + 20) * factor,
            )
        else:
            center = (base_r + lift + 20, base_r + lift + 20)

        # Calculate bounds
        outer_r = base_r + lift + follower_r + 20
        min_x = center[0] - outer_r
        max_x = center[0] + outer_r
        min_y = center[1] - outer_r
        max_y = center[1] + outer_r
        width = max(10.0, max_x - min_x)
        height = max(10.0, max_y - min_y)

        margin = 8.0
        avail_w = max(10.0, bounds.width - 2 * margin)
        avail_h = max(10.0, bounds.height - 2 * margin)
        scale = min(1.0, avail_w / width, avail_h / height)

        def pack(pt: tuple[float, float]) -> tuple[float, float]:
            return (pt[0] - min_x) * scale + margin, (pt[1] - min_y) * scale + margin

        cp = pack(center)
        base_rp = base_r * scale
        lift_p = lift * scale
        follower_rp = follower_r * scale

        parts = [self._generate_gradients()]

        # Generate cam profile
        profile_points = self._calculate_cam_profile(cp, base_rp, lift_p, self.PROFILE_POINTS)
        parts.append(self._draw_cam_profile(profile_points))

        # Center shaft
        shaft_radius = max(4.0 * scale, 2.0)
        parts.append(f"""
        <circle cx="{cp[0]:.1f}" cy="{cp[1]:.1f}" r="{shaft_radius:.1f}"
                fill="#fff" stroke="#2c3e50" stroke-width="1.5"/>
        <circle cx="{cp[0]:.1f}" cy="{cp[1]:.1f}" r="{shaft_radius * 0.3:.1f}"
                fill="#2c3e50"/>
        """)

        # Follower at top position
        follower_y = cp[1] - base_rp - lift_p / 2
        parts.append(f"""
        <!-- Follower -->
        <circle cx="{cp[0]:.1f}" cy="{follower_y:.1f}" r="{follower_rp:.1f}"
                fill="url(#follower-gradient)" stroke="{self.FOLLOWER_COLOR}" stroke-width="1.5"/>
        <line x1="{cp[0]:.1f}" y1="{follower_y + follower_rp:.1f}"
              x2="{cp[0]:.1f}" y2="{follower_y + follower_rp + 30:.1f}"
              stroke="#666" stroke-width="2"/>
        """)

        # Dimensions
        parts.append(f"""
        <!-- Base radius dimension -->
        <line x1="{cp[0]:.1f}" y1="{cp[1]:.1f}"
              x2="{cp[0] + base_rp:.1f}" y2="{cp[1]:.1f}"
              stroke="#666" stroke-width="0.5" stroke-dasharray="2,2"/>
        <text x="{cp[0] + base_rp / 2:.1f}" y="{cp[1] + 12:.1f}"
              font-size="7" text-anchor="middle" fill="#666">
              Base R: {base_r:.1f}mm
        </text>

        <!-- Lift dimension -->
        <line x1="{cp[0] + base_rp + 15:.1f}" y1="{cp[1] - base_rp:.1f}"
              x2="{cp[0] + base_rp + 15:.1f}" y2="{cp[1] - base_rp - lift_p:.1f}"
              stroke="#e74c3c" stroke-width="0.8"/>
        <text x="{cp[0] + base_rp + 25:.1f}" y="{cp[1] - base_rp - lift_p / 2:.1f}"
              font-size="7" text-anchor="start" fill="#e74c3c">
              Lift: {lift:.1f}mm
        </text>
        """)

        # Specifications panel
        parts.append(self._generate_spec_panel(bounds, base_r, lift, follower_r))

        return "".join(parts)

    def _calculate_cam_profile(
        self,
        center: tuple[float, float],
        base_radius: float,
        lift: float,
        num_points: int,
    ) -> list[tuple[float, float]]:
        """
        Calculate cam profile points.

        Uses a simple harmonic motion profile.

        Args:
            center: Center point of cam
            base_radius: Base circle radius
            lift: Maximum lift
            num_points: Number of profile points

        Returns:
            List of (x, y) profile points
        """
        cx, cy = center
        points = []

        for i in range(num_points):
            angle = (2 * math.pi * i) / num_points

            # Harmonic motion: rise during 0-180°, dwell during 180-360°
            if angle < math.pi:
                # Rise phase (harmonic)
                displacement = (lift / 2) * (1 - math.cos(angle))
            else:
                # Fall phase (harmonic)
                displacement = (lift / 2) * (1 + math.cos(angle - math.pi))

            r = max(1e-6, base_radius + displacement)
            x = cx + r * math.cos(angle - math.pi / 2)  # Start from top
            y = cy + r * math.sin(angle - math.pi / 2)
            points.append((x, y))

        return points

    def _draw_cam_profile(self, points: list[tuple[float, float]]) -> str:
        """Draw cam profile as filled polygon."""
        if not points:
            return ""

        path_data = f"M{points[0][0]:.1f},{points[0][1]:.1f}"
        for x, y in points[1:]:
            path_data += f" L{x:.1f},{y:.1f}"
        path_data += " Z"

        return f"""
        <path d="{path_data}"
              fill="url(#cam-gradient)" stroke="{self.CAM_COLOR}" stroke-width="2"/>
        """

    def _generate_gradients(self) -> str:
        """Generate cam and follower gradients."""
        return """
        <defs>
            <linearGradient id="cam-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#aed6f1"/>
                <stop offset="50%" style="stop-color:#5dade2"/>
                <stop offset="100%" style="stop-color:#2980b9"/>
            </linearGradient>
            <linearGradient id="follower-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#f5b7b1"/>
                <stop offset="50%" style="stop-color:#e74c3c"/>
                <stop offset="100%" style="stop-color:#c0392b"/>
            </linearGradient>
        </defs>
        """

    def _generate_spec_panel(
        self,
        bounds: ScaledBounds,
        base_r: float,
        lift: float,
        follower_r: float,
    ) -> str:
        """Generate cam specifications panel."""
        return f"""
        <g class="cam-manufacturing-specs">
            <rect x="{bounds.width - 160}" y="10" width="150" height="120"
                  fill="#f8f9fa" stroke="#dee2e6" stroke-width="1" rx="3"/>
            <text x="{bounds.width - 155}" y="25" font-size="8" font-weight="bold">
                Cam Specifications
            </text>
            <text x="{bounds.width - 155}" y="42" font-size="7">
                Base Circle Radius: {base_r:.1f}mm
            </text>
            <text x="{bounds.width - 155}" y="55" font-size="7">
                Maximum Lift: {lift:.1f}mm
            </text>
            <text x="{bounds.width - 155}" y="68" font-size="7">
                Follower Radius: {follower_r:.1f}mm
            </text>
            <text x="{bounds.width - 155}" y="85" font-size="7" font-weight="bold">
                Motion Profile:
            </text>
            <text x="{bounds.width - 155}" y="98" font-size="6">
                Simple Harmonic Motion
            </text>
            <text x="{bounds.width - 155}" y="108" font-size="6">
                Rise: 0-180° | Fall: 180-360°
            </text>
            <text x="{bounds.width - 155}" y="120" font-size="6">
                Material: Steel/Aluminum
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
                    mm[n] = _finite_float(rwp[n], math.nan)
        return mm
