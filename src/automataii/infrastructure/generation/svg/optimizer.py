#!/usr/bin/env python3
"""
Blueprint Layout Optimizer for Professional Manufacturing Blueprints
Implements intelligent layout, scale normalization, and mechanism support

Author: Legendary CS Research Collective
Inspired by: Knuth's TeX Layout + Catmull's Graphics + Sutherland's Systems

Note: Domain logic has been extracted to:
- automataii.domain.generation.layout (ScaleNormalizer, SmartLayoutManager, LayoutItem)
- automataii.domain.generation.contour (ManufacturingContour)
"""

import logging
from collections.abc import Callable
from typing import Any

# Import from domain modules
from automataii.domain.generation.layout import (
    LayoutItem,
    ScaledBounds,
    ScaleNormalizer,
    SmartLayoutManager,
)

# SVG generators
from automataii.infrastructure.generation.svg.generators import (
    CamSVGGenerator,
    GearSVGGenerator,
    LinkageSVGGenerator,
)
from automataii.shared.physical_kit import finite_float, normalize_mechanism_type

# Note: ScaleNormalizer and SmartLayoutManager have been moved to
# automataii.domain.generation.layout and are imported above.
# LayoutItem and ScaledBounds are also imported from the domain module.


class EnhancedMechanismProcessor:
    """
    Enhanced mechanism processor supporting all mechanism types
    Inspired by Ivan Sutherland's comprehensive CAD systems
    """

    def __init__(self, scale_normalizer: ScaleNormalizer):
        self.scale_normalizer = scale_normalizer
        self.logger = logging.getLogger(__name__)

        # Initialize extracted SVG generators (delegation pattern)
        self._linkage_generator = LinkageSVGGenerator()
        self._gear_generator = GearSVGGenerator()
        self._cam_generator = CamSVGGenerator()

        # Standard mechanism sizes in real-world units (mm)
        self.standard_mechanism_sizes = {
            "gear": {"width": 60, "height": 60},
            "gear_train": {"width": 90, "height": 70},
            "gear_linkage": {"width": 150, "height": 90},
            "linkage": {"width": 100, "height": 30},
            "four_bar": {"width": 120, "height": 70},
            "4_bar_linkage": {"width": 120, "height": 70},
            "5_bar_linkage": {"width": 160, "height": 90},
            "6_bar_linkage": {"width": 190, "height": 100},
            "cam": {"width": 80, "height": 80},
            "cam_follower": {"width": 120, "height": 90},
            "pulley": {"width": 50, "height": 50},
            "belt": {"width": 120, "height": 20},
            "spring": {"width": 40, "height": 80},
            "damper": {"width": 30, "height": 60},
        }

    def process_mechanism(
        self, mech_id: str, mech_data: dict[str, Any], unit_system: str = "metric"
    ) -> LayoutItem | None:
        """
        Process a mechanism into a layout item with proper scaling

        Args:
            mech_id: Mechanism identifier
            mech_data: Mechanism data dictionary
            unit_system: "metric" for mm, "imperial" for inches

        Returns:
            LayoutItem for the mechanism or None if processing fails
        """
        try:
            mechanism_type = mech_data.get(
                "type", "unknown"
            )  # Fixed: GUI uses 'type' not 'mechanism_type'
            normalized_type = self._normalize_for_blueprint(mechanism_type)

            self.logger.info(f"[MECHANISM] Processing {mech_id}: type={mechanism_type}")
            self.logger.info(f"[MECHANISM]   Keys in mech_data: {list(mech_data.keys())}")

            # Enhanced mechanism processing with scale data
            if "total_scale_factor" in mech_data and "real_world_params" in mech_data:
                # Use the real-world parameters and scale data from the screen
                real_world_params = mech_data["real_world_params"]
                scale_factor = mech_data["total_scale_factor"]

                self.logger.info(
                    f"[MECHANISM] Processing {mech_id} with screen-calculated scale: {scale_factor:.3f}"
                )

                # Calculate actual mechanism dimensions from real parameters
                actual_width, actual_height = self._calculate_mechanism_dimensions_from_params(
                    self._merged_dimension_params(mech_data, real_world_params), normalized_type
                )

                self.logger.info(
                    f"[MECHANISM] Calculated dimensions for {mech_id}: "
                    f"{actual_width:.1f}x{actual_height:.1f}mm (scale: {scale_factor:.3f})"
                )
            else:
                # Fallback to standard sizes
                self.logger.warning(
                    f"[MECHANISM] No screen scale data for {mech_id}, using standard sizes"
                )
                if "real_world_params" not in mech_data:
                    self.logger.warning("[MECHANISM]   Missing: real_world_params")
                if "total_scale_factor" not in mech_data:
                    self.logger.warning("[MECHANISM]   Missing: total_scale_factor")

                standard_size = self.standard_mechanism_sizes.get(
                    normalized_type,
                    {"width": 60, "height": 60},  # Default size
                )

                # Apply any custom scaling from mechanism data
                scale = mech_data.get("scale", 1.0)
                actual_width = standard_size["width"] * scale
                actual_height = standard_size["height"] * scale

                self.logger.info(
                    f"[MECHANISM] Using standard dimensions for {mech_id}: "
                    f"{actual_width:.1f}x{actual_height:.1f}mm (from standard: {standard_size})"
                )

            # Create scaled bounds
            bounds = ScaledBounds(
                x=0,  # Will be positioned by layout manager
                y=0,
                width=actual_width,
                height=actual_height,
            )

            self.logger.info(
                f"[MECHANISM] Final bounds for {mech_id}: {bounds.width:.1f}x{bounds.height:.1f}mm"
            )

            # Generate mechanism SVG content with enhanced scaling information and unit system
            svg_content = self._generate_mechanism_svg(mech_id, mech_data, bounds, unit_system)

            # Log first 200 chars of SVG for debugging
            self.logger.info(
                f"[MECHANISM] Generated SVG for {mech_id} (first 200 chars): {svg_content[:200] if svg_content else 'EMPTY'}"
            )

            # Create layout item
            layout_item = LayoutItem(
                name=mech_id,
                bounds=bounds,
                svg_content=svg_content,
                item_type="mechanism",
                priority=2,  # Mechanisms get medium priority
            )

            self.logger.info(
                f"[MECHANISM] Successfully processed {mech_id}: {actual_width:.1f}x{actual_height:.1f}mm"
            )
            return layout_item

        except Exception as e:
            self.logger.error(f"[MECHANISM] Error processing mechanism {mech_id}: {e}")
            import traceback

            self.logger.error(f"[MECHANISM] Traceback: {traceback.format_exc()}")
            return None

    @staticmethod
    def _normalize_for_blueprint(mechanism_type: object) -> str:
        normalized = str(normalize_mechanism_type(mechanism_type))
        blueprint_aliases: dict[str, str] = {
            "four_bar": "4_bar_linkage",
            "cam_follower": "cam",
            "gear_train": "gear",
        }
        return blueprint_aliases.get(normalized, normalized)

    @staticmethod
    def _svg_or_none(value: object) -> str | None:
        return value if isinstance(value, str) else None

    @staticmethod
    def _merged_dimension_params(
        mech_data: dict[str, Any], real_world_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Prefer fabrication-snapped params when present, keep scaled mm aliases."""
        merged = dict(real_world_params)
        params = mech_data.get("params", {})
        if isinstance(params, dict):
            for key, value in params.items():
                merged.setdefault(key, value)
        return merged

    def _calc_4bar_dimensions(self, params: dict[str, Any]) -> tuple[float, float]:
        """Calculate dimensions for 4-bar linkage."""
        l1 = finite_float(params.get("l1_mm", params.get("l1", params.get("L1"))), 50.0)
        l2 = finite_float(params.get("l2_mm", params.get("l2", params.get("L2"))), 30.0)
        l3 = finite_float(params.get("l3_mm", params.get("l3", params.get("L3"))), 40.0)
        l4 = finite_float(params.get("l4_mm", params.get("l4", params.get("L4"))), 35.0)
        max_width = l1 + max(l2, l3, l4) * 1.2
        max_height = max(l2, l3, l4) * 1.5
        return max_width, max_height

    def _calc_multibar_dimensions(self, params: dict[str, Any]) -> tuple[float, float]:
        lengths = [
            finite_float(params.get(f"l{i}_mm", params.get(f"l{i}", params.get(f"L{i}"))), 0.0)
            for i in range(1, 7)
        ]
        positive = [length for length in lengths if length > 0.0]
        if not positive:
            return 160.0, 90.0
        return sum(positive[:4]) * 0.75, max(positive) * 1.8

    def _calc_cam_dimensions(self, params: dict[str, Any]) -> tuple[float, float]:
        """Calculate dimensions for cam mechanism."""
        base_radius = finite_float(
            params.get("base_radius_mm", params.get("base_radius", params.get("cam_radius"))),
            25.0,
        )
        eccentricity = finite_float(
            params.get("eccentricity_mm", params.get("eccentricity", params.get("cam_offset"))),
            5.0,
        )
        width = (base_radius + eccentricity) * 2.5
        height = (base_radius + eccentricity) * 2.2
        return width, height

    def _calc_gear_dimensions(self, params: dict[str, Any]) -> tuple[float, float]:
        """Calculate dimensions for gear mechanisms."""
        radii = (
            finite_float(
                params.get("r1_mm", params.get("r1", params.get("gear1_radius"))),
                0.0,
            ),
            finite_float(
                params.get("r2_mm", params.get("r2", params.get("gear2_radius"))),
                0.0,
            ),
            finite_float(
                params.get("r_sun_mm", params.get("r_sun", params.get("sun_radius"))),
                0.0,
            ),
            finite_float(
                params.get("r_planet_mm", params.get("r_planet", params.get("planet_radius"))),
                0.0,
            ),
        )
        max_radius = max(radii) or 30.0
        return max_radius * 3.0, max_radius * 2.2

    def _calc_gear_linkage_dimensions(self, params: dict[str, Any]) -> tuple[float, float]:
        gear_width, gear_height = self._calc_gear_dimensions(params)
        arm = finite_float(params.get("linkage_arm_length", params.get("arm_length")), 80.0)
        return gear_width + arm, max(gear_height, arm * 0.8)

    def _calc_default_dimensions(self, params: dict[str, Any]) -> tuple[float, float]:
        """Calculate default dimensions for unknown mechanism types."""
        scale_factor = params.get("scale_factor_used", 1.0)
        return 60.0 * scale_factor, 60.0 * scale_factor

    def _calculate_mechanism_dimensions_from_params(
        self, real_world_params: dict[str, Any], mechanism_type: str
    ) -> tuple[float, float]:
        """
        Calculate mechanism bounding box dimensions from real-world parameters.

        Args:
            real_world_params: Real-world mechanism parameters in millimeters
            mechanism_type: Type of mechanism

        Returns:
            Tuple of (width_mm, height_mm)
        """
        # Strategy dictionary for dimension calculations
        dimension_strategies: dict[str, Callable[[dict[str, Any]], tuple[float, float]]] = {
            "4_bar_linkage": self._calc_4bar_dimensions,
            "5_bar_linkage": self._calc_multibar_dimensions,
            "6_bar_linkage": self._calc_multibar_dimensions,
            "cam": self._calc_cam_dimensions,
            "gear": self._calc_gear_dimensions,
            "gear_linkage": self._calc_gear_linkage_dimensions,
            "planetary_gear": self._calc_gear_dimensions,
        }

        try:
            calc_fn = dimension_strategies.get(mechanism_type, self._calc_default_dimensions)
            return calc_fn(real_world_params)
        except Exception as e:
            self.logger.warning(f"Error calculating mechanism dimensions: {e}")
            return 80.0, 60.0

    def _delegate_to_generator(
        self,
        mech_id: str,
        mech_data: dict[str, Any],
        bounds: ScaledBounds,
        mechanism_type: str,
    ) -> str | None:
        """Delegate SVG generation to extracted generator modules.

        Args:
            mech_id: Mechanism identifier
            mech_data: Mechanism data dictionary
            bounds: Scaled bounds for the mechanism
            mechanism_type: Type of mechanism

        Returns:
            SVG string or None if generation fails/not applicable
        """
        # Convert bounds to generator-compatible format
        # ScaledBounds is a single type from domain.generation.layout
        from automataii.domain.generation.layout import ScaledBounds as GenBounds

        CamBounds = GearBounds = LinkageBounds = GenBounds

        try:
            if mechanism_type == "4_bar_linkage" and isinstance(mech_data.get("key_points"), dict):
                gen_bounds = LinkageBounds(
                    x=bounds.x, y=bounds.y, width=bounds.width, height=bounds.height
                )
                result: object = self._linkage_generator.generate_4bar_svg(
                    mech_data,
                    gen_bounds,
                    fallback_generator=lambda mid, mt, b: self._generate_standard_mechanism_svg(
                        mid, mt, bounds
                    ),
                )
                return self._svg_or_none(result)

            elif mechanism_type in ["5_bar_linkage", "6_bar_linkage"] and isinstance(
                mech_data.get("key_points"), dict
            ):
                gen_bounds = LinkageBounds(
                    x=bounds.x, y=bounds.y, width=bounds.width, height=bounds.height
                )
                result = self._linkage_generator.generate_multibar_svg(mech_data, gen_bounds)
                return self._svg_or_none(result)

            elif mechanism_type in {"gear", "gear_linkage"}:
                gen_bounds = GearBounds(
                    x=bounds.x, y=bounds.y, width=bounds.width, height=bounds.height
                )
                result = self._gear_generator.generate_gear_mesh_svg(
                    mech_data, gen_bounds, mm_params_func=self._mm_params
                )
                gear_svg = self._svg_or_none(result)
                if gear_svg and mechanism_type == "gear_linkage":
                    return gear_svg + self._generate_gear_linkage_arm_svg(mech_data, bounds)
                return gear_svg

            elif mechanism_type == "planetary_gear":
                gen_bounds = GearBounds(
                    x=bounds.x, y=bounds.y, width=bounds.width, height=bounds.height
                )
                result = self._gear_generator.generate_planetary_gear_svg(
                    mech_data, gen_bounds, mm_params_func=self._mm_params
                )
                return self._svg_or_none(result)

            elif mechanism_type == "cam":
                gen_bounds = CamBounds(
                    x=bounds.x, y=bounds.y, width=bounds.width, height=bounds.height
                )
                result = self._cam_generator.generate_cam_svg(
                    mech_data, gen_bounds, mm_params_func=self._mm_params
                )
                return self._svg_or_none(result)

        except Exception as e:
            self.logger.warning(f"Generator delegation failed for {mechanism_type}: {e}")

        return None

    def _generate_mechanism_svg(
        self,
        mech_id: str,
        mech_data: dict[str, Any],
        bounds: ScaledBounds,
        unit_system: str = "metric",
    ) -> str:
        """Generate SVG content for mechanism with enhanced support for all types.

        Delegates to extracted SVG generators for cleaner separation of concerns.
        """
        raw_mechanism_type = mech_data.get("type", "unknown")
        mechanism_type = self._normalize_for_blueprint(raw_mechanism_type)

        # Delegate to extracted generators based on mechanism type
        base_svg = self._delegate_to_generator(mech_id, mech_data, bounds, mechanism_type)

        if not base_svg:
            # Fallback to standard representation
            base_svg = self._generate_standard_mechanism_svg(mech_id, mechanism_type, bounds)

        # Calculate text bounds to prevent overlapping
        text_height = 60  # Reserve space for labels
        total_bounds_height = bounds.height + text_height

        # Generate real-world parameter annotations with unit system support
        param_annotations = self._generate_parameter_annotations(mech_data, bounds, unit_system)

        # Calculate mechanism name for display
        mechanism_name = mech_data.get("part_name", mech_id)

        # Enhanced visual patterns and gradients for better texture appearance
        mechanism_patterns = self._generate_mechanism_patterns(mech_id, mechanism_type, bounds)

        # Wrap in positioned group with anti-overlap labeling and scale information
        positioned_svg = f'''
        <g class="mechanism-{mechanism_type}" data-id="{mech_id}">
            <title>{mech_id} ({mechanism_type}) - Screen-Scaled Blueprint</title>

            <!-- Enhanced visual patterns for texture-like appearance -->
            <defs>
                {mechanism_patterns}
            </defs>

            <!-- Mechanism background for visibility with text space -->
            <rect x="-5" y="-5" width="{bounds.width + 10:.1f}" height="{total_bounds_height + 10:.1f}"
                  fill="#f9f9f9" stroke="#ddd" stroke-width="0.5" rx="3"/>

            <!-- Mechanism content with enhanced visuals -->
            <g transform="translate(5,5)">
                {base_svg}
            </g>

            <!-- Mechanism type and name label at bottom -->
            <text x="{bounds.width / 2:.1f}" y="{bounds.height + 25:.1f}"
                  class="mechanism-label" text-anchor="middle" font-size="12" font-weight="bold" fill="#222">
                {mechanism_name}
            </text>

            <text x="{bounds.width / 2:.1f}" y="{bounds.height + 40:.1f}"
                  class="mechanism-type" text-anchor="middle" font-size="10" fill="#666">
                {mechanism_type.replace("_", " ").title()}
            </text>

            <!-- Real-world parameter annotations (positioned to avoid overlap) -->
            {param_annotations}
        </g>
        '''

        return positioned_svg

    def _generate_mechanism_patterns(
        self, mech_id: str, mechanism_type: str, bounds: ScaledBounds
    ) -> str:
        """Generate enhanced visual patterns and textures for mechanisms to improve blueprint appearance"""
        patterns = []

        try:
            # Create unique pattern IDs for this mechanism
            pattern_id = f"pattern-{mech_id}-{mechanism_type}"
            gradient_id = f"gradient-{mech_id}-{mechanism_type}"

            # Mechanism-specific patterns for enhanced visual appearance
            if mechanism_type == "gear":
                # Gear tooth pattern with gradient
                patterns.append(f'''
                <pattern id="{pattern_id}" patternUnits="userSpaceOnUse" width="8" height="8">
                    <rect width="8" height="8" fill="#f0f0f0"/>
                    <circle cx="4" cy="4" r="1.5" fill="#333" opacity="0.3"/>
                </pattern>
                <linearGradient id="{gradient_id}" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#e8e8e8;stop-opacity:1" />
                    <stop offset="50%" style="stop-color:#d0d0d0;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#c0c0c0;stop-opacity:1" />
                </linearGradient>''')

            elif mechanism_type == "4_bar_linkage":
                # Linkage pattern with metallic appearance
                patterns.append(f'''
                <pattern id="{pattern_id}" patternUnits="userSpaceOnUse" width="12" height="4">
                    <rect width="12" height="4" fill="#e5e5e5"/>
                    <line x1="0" y1="2" x2="12" y2="2" stroke="#999" stroke-width="0.5"/>
                </pattern>
                <linearGradient id="{gradient_id}" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#f5f5f5;stop-opacity:1" />
                    <stop offset="50%" style="stop-color:#ddd;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#bbb;stop-opacity:1" />
                </linearGradient>''')

            elif mechanism_type == "cam":
                # Cam surface pattern with texture
                patterns.append(f'''
                <pattern id="{pattern_id}" patternUnits="userSpaceOnUse" width="6" height="6">
                    <rect width="6" height="6" fill="#f8f8f8"/>
                    <path d="M0,3 Q3,0 6,3 Q3,6 0,3" fill="none" stroke="#ccc" stroke-width="0.5"/>
                </pattern>
                <radialGradient id="{gradient_id}" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" style="stop-color:#f0f0f0;stop-opacity:1" />
                    <stop offset="70%" style="stop-color:#e0e0e0;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#d0d0d0;stop-opacity:1" />
                </radialGradient>''')

            else:
                # Generic mechanism pattern
                patterns.append(f'''
                <pattern id="{pattern_id}" patternUnits="userSpaceOnUse" width="10" height="10">
                    <rect width="10" height="10" fill="#f5f5f5"/>
                    <rect x="2" y="2" width="6" height="6" fill="none" stroke="#ddd" stroke-width="0.5"/>
                </pattern>
                <linearGradient id="{gradient_id}" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#f0f0f0;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#e0e0e0;stop-opacity:1" />
                </linearGradient>''')

        except Exception as e:
            self.logger.warning(f"Failed to generate patterns for {mechanism_type}: {e}")
            return ""

        return "\n".join(patterns)

    # NOTE: _generate_4bar_from_keypoints_svg removed - delegated to LinkageSVGGenerator
    # NOTE: _generate_multibar_from_keypoints_svg removed - delegated to LinkageSVGGenerator

    def _generate_gear_linkage_arm_svg(
        self, mech_data: dict[str, Any], bounds: ScaledBounds
    ) -> str:
        """Render the cuttable linkage arm required by the gear-linkage recipe."""
        arm_mm = self._mm_params(mech_data, ["arm_length_mm"]).get("arm_length_mm", 80.0)
        visual_length = min(max(arm_mm, 35.0), max(35.0, bounds.width - 30.0))
        thickness = 10.0
        hole_radius = 2.0
        start_x = 15.0
        center_y = max(28.0, min(bounds.height - 18.0, bounds.height * 0.82))
        end_x = start_x + visual_length
        slot_spacing = 20.0
        intermediate_holes = []
        hole_x = start_x + slot_spacing
        while hole_x < end_x - slot_spacing * 0.5:
            intermediate_holes.append(
                f'<circle cx="{hole_x:.1f}" cy="{center_y:.1f}" r="{hole_radius:.1f}" '
                'fill="white" stroke="#4b5563" stroke-width="0.8"/>'
            )
            hole_x += slot_spacing

        return f'''
        <g class="gear-linkage-arm" data-part-kind="gear-linkage-arm">
            <title>Gear linkage arm - cuttable linkage part</title>
            <rect x="{start_x:.1f}" y="{center_y - thickness / 2:.1f}"
                  width="{visual_length:.1f}" height="{thickness:.1f}"
                  rx="{thickness / 2:.1f}" fill="#fef3c7" stroke="#92400e" stroke-width="1.2"/>
            <circle cx="{start_x:.1f}" cy="{center_y:.1f}" r="{hole_radius:.1f}"
                    fill="white" stroke="#4b5563" stroke-width="0.8"/>
            <circle cx="{end_x:.1f}" cy="{center_y:.1f}" r="{hole_radius:.1f}"
                    fill="white" stroke="#4b5563" stroke-width="0.8"/>
            {"".join(intermediate_holes)}
            <text x="{(start_x + end_x) / 2:.1f}" y="{center_y + 14.0:.1f}"
                  font-size="7" text-anchor="middle" fill="#92400e">
                  Linkage arm: {arm_mm:.1f}mm, 4mm holes
            </text>
        </g>
        '''

    def _mm_params(self, mech_data: dict[str, Any], names: list[str]) -> dict[str, float]:
        """Helper to fetch parameter values in mm from real_world_params or by scaling params."""
        mm = {}
        rwp = mech_data.get("real_world_params", {})
        if rwp:
            for n in names:
                if n in rwp:
                    mm[n] = float(rwp[n])
        if not mm:
            factor = float(mech_data.get("total_scale_factor", 1.0))
            params = mech_data.get("params", {})
            aliases = {
                "r1_mm": ("r1", "gear1_radius"),
                "r2_mm": ("r2", "gear2_radius"),
                "r_sun_mm": ("r_sun", "sun_radius"),
                "r_planet_mm": ("r_planet", "planet_radius"),
                "base_radius_mm": ("base_radius", "cam_radius"),
                "eccentricity_mm": ("eccentricity", "cam_offset"),
                "arm_length_mm": ("arm_length", "linkage_arm_length"),
            }
            for n in names:
                for base in aliases.get(n, (n.replace("_mm", ""),)):
                    if base in params:
                        mm[n] = float(params[base]) * factor
                        break
        return mm

    # NOTE: _generate_gears_from_params_svg removed - delegated to GearSVGGenerator
    # NOTE: _generate_detailed_gear removed - delegated to GearSVGGenerator
    # NOTE: _generate_planetary_gear_from_params_svg removed - delegated to GearSVGGenerator
    # NOTE: _generate_cam_from_params_svg removed - delegated to CamSVGGenerator

    def _generate_parameter_annotations(
        self, mech_data: dict[str, Any], bounds: ScaledBounds, unit_system: str = "metric"
    ) -> str:
        """
        Generate parameter annotations for real-world mechanism dimensions.

        Args:
            mech_data: Mechanism data with real_world_params
            bounds: Mechanism bounds for positioning
            unit_system: "metric" for mm, "imperial" for inches

        Returns:
            SVG string with parameter annotations
        """
        annotations = []

        try:
            real_world_params = mech_data.get("real_world_params", {})
            mechanism_type = self._normalize_for_blueprint(mech_data.get("type", "unknown"))

            # Also try to get parametric editing results if available
            params = mech_data.get("params", {})
            total_scale_factor = mech_data.get("total_scale_factor", 1.0)

            if not real_world_params and params and total_scale_factor:
                # Calculate real-world params from current params if not already calculated
                real_world_params = self._calculate_real_world_params_from_params(
                    params, total_scale_factor, mechanism_type
                )

            if not real_world_params:
                return ""

            # Unit conversion function
            def format_dimension(value_mm: float) -> str:
                if unit_system == "imperial":
                    inches = value_mm / 25.4
                    if inches < 1.0:
                        return f"{inches * 1000:.0f} mil"  # thousandths of inch
                    elif inches < 12.0:
                        return f'{inches:.2f}"'
                    else:
                        feet = inches / 12.0
                        return f"{feet:.2f}'"
                else:
                    return f"{value_mm:.1f}mm"

            # Position annotations to the right of the mechanism, with a light panel
            annotation_x = bounds.width + 15
            annotation_y_start = 20
            line_height = 14  # Increased for better readability

            # Calculate panel height based on mechanism type
            param_count = self._get_param_count_for_mechanism(mechanism_type, real_world_params)
            panel_height = max(110, 40 + (param_count * line_height) + 30)

            annotations.append('<g class="parameter-annotations">')
            annotations.append(
                f'<rect x="{annotation_x - 6}" y="{annotation_y_start - 16}" '
                f'width="180" height="{panel_height}" fill="#ffffff" stroke="#e5e5e5" '
                f'stroke-width="0.5" rx="3"/>'
            )

            unit_label = "Imperial" if unit_system == "imperial" else "Metric"
            annotations.append(
                f'<text x="{annotation_x}" y="{annotation_y_start}" '
                f'class="parameter-header" font-size="9" font-weight="bold" fill="#333">'
                f"Real-World Dimensions ({unit_label}):</text>"
            )

            y_offset = annotation_y_start + line_height + 2

            # Add mechanism-specific parameter annotations with enhanced display
            if mechanism_type == "4_bar_linkage":
                link_params = ["l1_mm", "l2_mm", "l3_mm", "l4_mm"]
                link_names = ["Ground Link", "Crank", "Coupler", "Rocker"]

                for i, param in enumerate(link_params):
                    if param in real_world_params:
                        value = real_world_params[param]
                        formatted_value = format_dimension(value)
                        link_name = link_names[i]

                        annotations.append(
                            f'<text x="{annotation_x}" y="{y_offset}" '
                            f'class="parameter-text" font-size="8" fill="#222">'
                            f"{link_name}: {formatted_value}</text>"
                        )
                        y_offset += line_height

                # Add coupler point if available
                if (
                    "coupler_point_x_mm" in real_world_params
                    and "coupler_point_y_mm" in real_world_params
                ):
                    cp_x = format_dimension(real_world_params["coupler_point_x_mm"])
                    cp_y = format_dimension(real_world_params["coupler_point_y_mm"])
                    annotations.append(
                        f'<text x="{annotation_x}" y="{y_offset}" '
                        f'class="parameter-text" font-size="7" fill="#666">'
                        f"Coupler Point: ({cp_x}, {cp_y})</text>"
                    )
                    y_offset += line_height

            elif mechanism_type == "cam":
                cam_params = ["base_radius_mm", "eccentricity_mm"]
                cam_names = ["Base Radius", "Eccentricity"]

                for i, param in enumerate(cam_params):
                    if param in real_world_params:
                        value = real_world_params[param]
                        formatted_value = format_dimension(value)
                        param_name = cam_names[i]

                        annotations.append(
                            f'<text x="{annotation_x}" y="{y_offset}" '
                            f'class="parameter-text" font-size="8" fill="#222">'
                            f"{param_name}: {formatted_value}</text>"
                        )
                        y_offset += line_height

                # Add calculated values
                if "base_radius_mm" in real_world_params and "eccentricity_mm" in real_world_params:
                    max_radius = (
                        real_world_params["base_radius_mm"] + real_world_params["eccentricity_mm"]
                    )
                    min_radius = (
                        real_world_params["base_radius_mm"] - real_world_params["eccentricity_mm"]
                    )

                    annotations.append(
                        f'<text x="{annotation_x}" y="{y_offset}" '
                        f'class="parameter-text" font-size="7" fill="#666">'
                        f"Max Radius: {format_dimension(max_radius)}</text>"
                    )
                    y_offset += line_height

                    annotations.append(
                        f'<text x="{annotation_x}" y="{y_offset}" '
                        f'class="parameter-text" font-size="7" fill="#666">'
                        f"Min Radius: {format_dimension(min_radius)}</text>"
                    )
                    y_offset += line_height

            elif mechanism_type in ["gear", "gear_linkage", "planetary_gear"]:
                gear_params = [
                    "r1_mm",
                    "r2_mm",
                    "r_sun_mm",
                    "r_planet_mm",
                    "arm_length_mm",
                    "distance_mm",
                ]
                gear_names = [
                    "Gear 1 Radius",
                    "Gear 2 Radius",
                    "Sun Radius",
                    "Planet Radius",
                    "Arm Length",
                    "Center Distance",
                ]

                for i, param in enumerate(gear_params):
                    if param in real_world_params:
                        value = real_world_params[param]
                        formatted_value = format_dimension(value)
                        param_name = gear_names[i]

                        annotations.append(
                            f'<text x="{annotation_x}" y="{y_offset}" '
                            f'class="parameter-text" font-size="8" fill="#222">'
                            f"{param_name}: {formatted_value}</text>"
                        )
                        y_offset += line_height

                # Add gear ratio if applicable
                if (
                    mechanism_type in {"gear", "gear_linkage"}
                    and "r1_mm" in real_world_params
                    and "r2_mm" in real_world_params
                ):
                    r1 = real_world_params["r1_mm"]
                    r2 = real_world_params["r2_mm"]
                    if r1 > 0:
                        ratio = r2 / r1
                        annotations.append(
                            f'<text x="{annotation_x}" y="{y_offset}" '
                            f'class="parameter-text" font-size="7" fill="#666">'
                            f"Gear Ratio: {ratio:.2f}:1</text>"
                        )
                        y_offset += line_height

            # Add scale factor information
            if "scale_factor_used" in real_world_params:
                scale_factor = real_world_params["scale_factor_used"]
                annotations.append(
                    f'<text x="{annotation_x}" y="{y_offset + 8}" '
                    f'class="scale-info" font-size="6" fill="#666" font-style="italic">'
                    f"Scale Factor: {scale_factor:.3f} mm/px</text>"
                )

            # Add unit system note
            annotations.append(
                f'<text x="{annotation_x}" y="{annotation_y_start + panel_height - 8}" '
                f'class="unit-info" font-size="6" fill="#888" font-style="italic">'
                f"Units: {unit_label}</text>"
            )

            annotations.append("</g>")

        except Exception as e:
            self.logger.warning(f"Error generating parameter annotations: {e}")
            # Return empty string if annotation generation fails
            return ""

        return "\n".join(annotations)

    def _get_param_count_for_mechanism(
        self, mechanism_type: str, real_world_params: dict[str, Any]
    ) -> int:
        """Count the number of parameters that will be displayed for a mechanism type."""
        mechanism_type = self._normalize_for_blueprint(mechanism_type)
        if mechanism_type == "4_bar_linkage":
            count = 4  # l1, l2, l3, l4
            if "coupler_point_x_mm" in real_world_params:
                count += 1
            return count
        elif mechanism_type == "cam":
            count = 2  # base_radius, eccentricity
            if "base_radius_mm" in real_world_params and "eccentricity_mm" in real_world_params:
                count += 2  # max_radius, min_radius
            return count
        elif mechanism_type in ["gear", "gear_linkage", "planetary_gear"]:
            count = len(
                [
                    p
                    for p in [
                        "r1_mm",
                        "r2_mm",
                        "r_sun_mm",
                        "r_planet_mm",
                        "arm_length_mm",
                        "distance_mm",
                    ]
                    if p in real_world_params
                ]
            )
            if (
                mechanism_type in {"gear", "gear_linkage"}
                and "r1_mm" in real_world_params
                and "r2_mm" in real_world_params
            ):
                count += 1  # gear ratio
            return count
        return 3  # default

    def _calculate_real_world_params_from_params(
        self, params: dict[str, Any], scale_factor: float, mech_type: str
    ) -> dict[str, Any]:
        """Calculate real-world parameters from current mechanism params and scale factor."""
        real_world_params = {}
        mech_type = self._normalize_for_blueprint(mech_type)

        try:
            if mech_type == "4_bar_linkage":
                for param_name in ["l1", "l2", "l3", "l4"]:
                    if param_name in params:
                        real_world_params[f"{param_name}_mm"] = params[param_name] * scale_factor
                for param_name in ["coupler_point_x", "coupler_point_y"]:
                    if param_name in params:
                        real_world_params[f"{param_name}_mm"] = params[param_name] * scale_factor

            elif mech_type == "cam":
                for param_name in ["base_radius", "eccentricity"]:
                    if param_name in params:
                        real_world_params[f"{param_name}_mm"] = params[param_name] * scale_factor

            elif mech_type in ["gear", "gear_linkage", "planetary_gear"]:
                for param_name in [
                    "r1",
                    "r2",
                    "gear1_radius",
                    "gear2_radius",
                    "r_sun",
                    "r_planet",
                    "sun_radius",
                    "planet_radius",
                    "arm_length",
                    "linkage_arm_length",
                    "distance",
                    "tracking_radius",
                ]:
                    if param_name in params:
                        real_world_params[f"{param_name}_mm"] = params[param_name] * scale_factor

            real_world_params["scale_factor_used"] = scale_factor
            real_world_params["mechanism_type"] = mech_type

        except Exception as e:
            self.logger.warning(f"Error calculating real-world params for {mech_type}: {e}")
            real_world_params = {"scale_factor_used": scale_factor, "mechanism_type": mech_type}

        return real_world_params

    def _generate_standard_mechanism_svg(
        self, mech_id: str, mechanism_type: str, bounds: ScaledBounds
    ) -> str:
        """Generate standard mechanism representation"""

        # Different shapes for different mechanism types
        if mechanism_type == "gear":
            # Gear with teeth
            return self._generate_gear_svg(bounds)
        elif mechanism_type == "4_bar_linkage":  # Fixed: GUI creates '4_bar_linkage' not 'linkage'
            # Link bar
            return self._generate_linkage_svg(bounds)
        elif mechanism_type == "cam":
            # Cam profile
            return self._generate_cam_svg(bounds)
        elif mechanism_type == "pulley":
            # Circular pulley
            return self._generate_pulley_svg(bounds)
        elif mechanism_type == "belt":
            # Belt path
            return self._generate_belt_svg(bounds)
        elif mechanism_type == "spring":
            # Spring coils
            return self._generate_spring_svg(bounds)
        elif mechanism_type == "damper":
            # Damper cylinder
            return self._generate_damper_svg(bounds)
        else:
            # Generic mechanism box
            return self._generate_generic_mechanism_svg(mech_id, mechanism_type, bounds)

    def _generate_gear_svg(self, bounds: ScaledBounds) -> str:
        """Generate enhanced standard gear representation with manufacturing details"""
        cx, cy = bounds.width / 2, bounds.height / 2
        radius = min(bounds.width, bounds.height) / 2 - 5

        hub_radius = radius * 0.4
        shaft_radius = radius * 0.15
        keyway_width = shaft_radius * 0.4

        # Enhanced gear with manufacturing features
        return f'''
        <!-- Gear gradients for metallic appearance -->
        <defs>
            <radialGradient id="standard-gear-gradient" cx="50%" cy="50%" r="50%">
                <stop offset="0%" style="stop-color:#f8f9fa;stop-opacity:1"/>
                <stop offset="60%" style="stop-color:#e9ecef;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#ced4da;stop-opacity:1"/>
            </radialGradient>
        </defs>

        <!-- Main gear body -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}"
                fill="url(#standard-gear-gradient)" stroke="#495057" stroke-width="2.0"/>

        <!-- Gear teeth representation (improved) -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius + 2:.1f}"
                fill="none" stroke="#495057" stroke-width="1.2" stroke-dasharray="2,1"/>

        <!-- Hub -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{hub_radius:.1f}"
                fill="url(#standard-gear-gradient)" stroke="#343a40" stroke-width="1.5"/>

        <!-- Center shaft hole -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{shaft_radius:.1f}"
                fill="#fff" stroke="#343a40" stroke-width="1"/>

        <!-- Keyway -->
        <rect x="{cx - keyway_width / 2:.1f}" y="{cy - shaft_radius:.1f}"
              width="{keyway_width:.1f}" height="{shaft_radius * 0.6:.1f}" fill="#6c757d"/>

        <!-- Manufacturing specifications -->
        <text x="{cx:.1f}" y="{cy + radius + 15:.1f}" class="manufacturing-note"
              font-size="7" text-anchor="middle" fill="#495057">
              Standard Gear | Steel | 6mm Shaft
        </text>
        '''

    def _generate_linkage_svg(self, bounds: ScaledBounds) -> str:
        """Generate enhanced linkage representation with metallic appearance"""
        link_height = 12
        y_center = bounds.height / 2

        # Enhanced linkage with gradient and pattern
        return f'''
        <!-- Main linkage bar with gradient -->
        <rect x="5" y="{y_center - link_height / 2:.1f}" width="{bounds.width - 10:.1f}" height="{link_height}"
              fill="url(#gradient-4_bar_linkage)" stroke="#34495e" stroke-width="1.5" rx="2"/>

        <!-- Pattern overlay for texture -->
        <rect x="5" y="{y_center - link_height / 2:.1f}" width="{bounds.width - 10:.1f}" height="{link_height}"
              fill="url(#pattern-4_bar_linkage)" opacity="0.3" rx="2"/>

        <!-- Left joint with enhanced detail -->
        <circle cx="10" cy="{y_center:.1f}" r="5"
                fill="url(#gradient-4_bar_linkage)" stroke="#2c3e50" stroke-width="1.2"/>
        <circle cx="10" cy="{y_center:.1f}" r="2"
                fill="#fff" stroke="#555" stroke-width="0.5"/>

        <!-- Right joint with enhanced detail -->
        <circle cx="{bounds.width - 10:.1f}" cy="{y_center:.1f}" r="5"
                fill="url(#gradient-4_bar_linkage)" stroke="#2c3e50" stroke-width="1.2"/>
        <circle cx="{bounds.width - 10:.1f}" cy="{y_center:.1f}" r="2"
                fill="#fff" stroke="#555" stroke-width="0.5"/>

        <!-- Center reinforcement -->
        <rect x="{bounds.width / 2 - 10:.1f}" y="{y_center - 2:.1f}" width="20" height="4"
              fill="none" stroke="#7f8c8d" stroke-width="0.8" stroke-dasharray="2,2"/>
        '''

    def _generate_cam_svg(self, bounds: ScaledBounds) -> str:
        """Generate enhanced standard cam representation with follower details"""
        cx, cy = bounds.width / 2, bounds.height / 2
        rx, ry = bounds.width / 2 - 5, bounds.height / 2 - 5

        # Enhanced cam with follower system
        return f'''
        <!-- Cam gradients -->
        <defs>
            <radialGradient id="standard-cam-gradient" cx="50%" cy="50%" r="50%">
                <stop offset="0%" style="stop-color:#f1f3f4;stop-opacity:1"/>
                <stop offset="70%" style="stop-color:#e8eaed;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#dadce0;stop-opacity:1"/>
            </radialGradient>
            <linearGradient id="standard-follower-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#4285f4;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#1a73e8;stop-opacity:1"/>
            </linearGradient>
        </defs>

        <!-- Main cam body -->
        <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}"
                 fill="url(#standard-cam-gradient)" stroke="#5f6368" stroke-width="2.0"/>

        <!-- Cam center shaft -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="4"
                fill="#202124" stroke="#5f6368" stroke-width="1"/>
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="2"
                fill="#fff" stroke="#202124" stroke-width="0.8"/>

        <!-- Follower above cam -->
        <rect x="{cx - 6:.1f}" y="{cy - ry - 20:.1f}" width="12" height="8"
              fill="url(#standard-follower-gradient)" stroke="#1a73e8" stroke-width="1" rx="1"/>

        <!-- Follower rod -->
        <line x1="{cx:.1f}" y1="{cy - ry - 16:.1f}" x2="{cx:.1f}" y2="{cy - ry:.1f}"
              stroke="#4285f4" stroke-width="2"/>

        <!-- Follower contact point -->
        <circle cx="{cx:.1f}" cy="{cy - ry:.1f}" r="2"
                fill="#ea4335" stroke="#d33b2c" stroke-width="1"/>

        <!-- Guide rails -->
        <line x1="{cx - 10:.1f}" y1="{cy - ry - 25:.1f}" x2="{cx - 10:.1f}" y2="{cy - ry + 5:.1f}"
              stroke="#5f6368" stroke-width="2"/>
        <line x1="{cx + 10:.1f}" y1="{cy - ry - 25:.1f}" x2="{cx + 10:.1f}" y2="{cy - ry + 5:.1f}"
              stroke="#5f6368" stroke-width="2"/>

        <!-- Manufacturing specifications -->
        <text x="{cx:.1f}" y="{cy + ry + 15:.1f}" class="manufacturing-note"
              font-size="7" text-anchor="middle" fill="#5f6368">
              Cam Profile | Steel | Follower System
        </text>
        '''

    def _generate_pulley_svg(self, bounds: ScaledBounds) -> str:
        """Generate enhanced pulley representation with belt groove and mounting"""
        cx, cy = bounds.width / 2, bounds.height / 2
        radius = min(bounds.width, bounds.height) / 2 - 3

        groove_width = radius * 0.2
        hub_radius = radius * 0.5

        return f'''
        <!-- Pulley gradients -->
        <defs>
            <radialGradient id="pulley-gradient" cx="50%" cy="50%" r="50%">
                <stop offset="0%" style="stop-color:#fff3e0;stop-opacity:1"/>
                <stop offset="50%" style="stop-color:#ffcc02;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#ff8f00;stop-opacity:1"/>
            </radialGradient>
        </defs>

        <!-- Main pulley body -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}"
                fill="url(#pulley-gradient)" stroke="#ef6c00" stroke-width="2.0"/>

        <!-- Belt groove (V-shaped profile) -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius - groove_width:.1f}"
                fill="none" stroke="#d84315" stroke-width="2"/>
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius - groove_width / 2:.1f}"
                fill="none" stroke="#bf360c" stroke-width="1" stroke-dasharray="2,2"/>

        <!-- Hub -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{hub_radius:.1f}"
                fill="url(#pulley-gradient)" stroke="#d84315" stroke-width="1.5"/>

        <!-- Center mounting -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{hub_radius * 0.3:.1f}"
                fill="#fff" stroke="#bf360c" stroke-width="1"/>

        <!-- Mounting bolts -->
        <circle cx="{cx - hub_radius * 0.6:.1f}" cy="{cy:.1f}" r="1.5"
                fill="#424242" stroke="#212121" stroke-width="0.5"/>
        <circle cx="{cx + hub_radius * 0.6:.1f}" cy="{cy:.1f}" r="1.5"
                fill="#424242" stroke="#212121" stroke-width="0.5"/>
        <circle cx="{cx:.1f}" cy="{cy - hub_radius * 0.6:.1f}" r="1.5"
                fill="#424242" stroke="#212121" stroke-width="0.5"/>
        <circle cx="{cx:.1f}" cy="{cy + hub_radius * 0.6:.1f}" r="1.5"
                fill="#424242" stroke="#212121" stroke-width="0.5"/>

        <!-- Manufacturing specifications -->
        <text x="{cx:.1f}" y="{cy + radius + 15:.1f}" class="manufacturing-note"
              font-size="7" text-anchor="middle" fill="#ef6c00">
              V-Belt Pulley | Aluminum | 4-Bolt Mount
        </text>
        '''

    def _generate_belt_svg(self, bounds: ScaledBounds) -> str:
        """Generate standard belt representation"""
        return f'''
        <rect x="5" y="{bounds.height / 2 - 3:.1f}" width="{bounds.width - 10:.1f}" height="6"
              fill="none" stroke="black" stroke-width="1" stroke-dasharray="5,3"/>
        '''

    def _generate_spring_svg(self, bounds: ScaledBounds) -> str:
        """Generate standard spring representation"""
        coils = []
        cx = bounds.width / 2
        coil_height = bounds.height / 8

        for i in range(6):
            y = 10 + i * coil_height
            coils.append(
                f'<ellipse cx="{cx:.1f}" cy="{y:.1f}" rx="8" ry="{coil_height / 2:.1f}" '
                f'fill="none" stroke="black" stroke-width="1"/>'
            )

        return "\n".join(coils)

    def _generate_damper_svg(self, bounds: ScaledBounds) -> str:
        """Generate standard damper representation"""
        cx = bounds.width / 2

        return f'''
        <rect x="{cx - 8:.1f}" y="10" width="16" height="{bounds.height - 20:.1f}"
              fill="none" stroke="black" stroke-width="1.5"/>
        <line x1="{cx:.1f}" y1="5" x2="{cx:.1f}" y2="15" stroke="black" stroke-width="2"/>
        <line x1="{cx:.1f}" y1="{bounds.height - 15:.1f}" x2="{cx:.1f}" y2="{bounds.height - 5:.1f}"
              stroke="black" stroke-width="2"/>
        '''

    def _generate_generic_mechanism_svg(
        self, mech_id: str, mechanism_type: str, bounds: ScaledBounds
    ) -> str:
        """Generate generic mechanism placeholder"""
        return f'''
        <rect x="2" y="2" width="{bounds.width - 4:.1f}" height="{bounds.height - 4:.1f}"
              fill="#f8f8f8" stroke="black" stroke-width="1" stroke-dasharray="3,3"/>
        <text x="{bounds.width / 2:.1f}" y="{bounds.height / 2 - 5:.1f}"
              class="mechanism-label" text-anchor="middle" font-size="10">
              {mechanism_type.upper()}
        </text>
        <text x="{bounds.width / 2:.1f}" y="{bounds.height / 2 + 8:.1f}"
              class="mechanism-label" text-anchor="middle" font-size="8">
              (Custom)
        </text>
        '''


class BlueprintLayoutOptimizer:
    """
    Complete blueprint layout optimizer
    Combines scale normalization, smart layout, and mechanism processing
    """

    def __init__(self, target_character_height_mm: float = 300.0):
        self.target_character_height_mm = target_character_height_mm
        self.scale_normalizer = ScaleNormalizer(target_character_height_mm)
        self.layout_manager = SmartLayoutManager()
        self.mechanism_processor = EnhancedMechanismProcessor(self.scale_normalizer)
        self.logger = logging.getLogger(__name__)

    def optimize_blueprint_layout(
        self, part_items: list[Any], mechanism_layers: dict[str, Any], unit_system: str = "metric"
    ) -> tuple[list[LayoutItem], float, float]:
        """
        Optimize layout of parts and mechanisms for blueprint generation

        Args:
            part_items: List of character part items
            mechanism_layers: Dictionary of mechanism data
            unit_system: "metric" for mm, "imperial" for inches

        Returns:
            Tuple of (layout_items, total_width_mm, total_height_mm)
        """

        layout_items: list[LayoutItem] = []

        # Process character parts first
        if part_items:
            self.logger.info(f"Processing {len(part_items)} character parts...")
            try:
                # Use the _process_character_parts method to actually process the parts
                part_layout_items = self._process_character_parts(part_items)
                layout_items.extend(part_layout_items)
                self.logger.info(f"Successfully processed {len(part_layout_items)} parts")
            except Exception as e:
                self.logger.error(f"Failed to process parts: {e}")
                import traceback

                self.logger.error(f"Traceback: {traceback.format_exc()}")

        # Process mechanisms with enhanced scaling
        if mechanism_layers:
            self.logger.info(
                f"Processing {len(mechanism_layers)} mechanisms with unit system: {unit_system}..."
            )
            for mech_id, mech_data in mechanism_layers.items():
                try:
                    layout_item = self.mechanism_processor.process_mechanism(
                        mech_id, mech_data, unit_system
                    )
                    if layout_item:
                        layout_items.append(layout_item)
                        self.logger.debug(f"Added mechanism layout item: {mech_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to process mechanism {mech_id}: {e}")

        # Optimize layout positioning
        if layout_items:
            self.logger.info(f"Optimizing layout for {len(layout_items)} items...")
            optimized_items, total_width, total_height = self.layout_manager.optimize_layout(
                layout_items, target_page_width_mm=800, target_page_height_mm=600
            )
            return optimized_items, total_width, total_height
        else:
            self.logger.warning("No layout items to optimize")
            return [], 0.0, 0.0

    def _process_character_parts(self, part_items: list[Any]) -> list[LayoutItem]:
        """Process character parts with TOTAL CHARACTER HEIGHT scaling (not individual parts)"""
        from automataii.infrastructure.generation.processors import PNGBlueprintProcessor

        layout_items = []

        # CRITICAL FIX: Calculate scale based on TOTAL CHARACTER HEIGHT, not individual parts
        total_character_height = 0
        total_character_width = 0
        all_contours = []

        # First pass: collect all contours and calculate total character bounds
        for item in part_items:
            try:
                # Validate item before processing
                if not item or not hasattr(item, "part_info"):
                    self.logger.warning(f"Skipping invalid part item: {item}")
                    continue

                processor = PNGBlueprintProcessor()
                contour = processor.process_part_png(item)
                if contour:
                    all_contours.append((item, contour))
            except Exception as e:
                self.logger.error(f"Error processing part item: {e}")
                import traceback

                self.logger.error(f"Traceback: {traceback.format_exc()}")
                continue

        if all_contours:
            # Calculate total character bounding box
            all_bounds = [contour.bounding_rect for _, contour in all_contours]
            min_x = min(x for x, y, w, h in all_bounds)
            max_x = max(x + w for x, y, w, h in all_bounds)
            min_y = min(y for x, y, w, h in all_bounds)
            max_y = max(y + h for x, y, w, h in all_bounds)

            total_character_height = max_y - min_y
            total_character_width = max_x - min_x

            self.logger.info(
                f"[CHARACTER] Total character dimensions: {total_character_width}x{total_character_height} pixels"
            )
            self.logger.info(
                f"[CHARACTER] Target: {self.scale_normalizer.target_height_mm}mm character height"
            )

            # Scale factor based on TOTAL CHARACTER HEIGHT
            scale_factor = self.scale_normalizer.calculate_scale_factor(total_character_height)

            # Calculate actual character dimensions after scaling
            actual_character_height = total_character_height * scale_factor
            actual_character_width = total_character_width * scale_factor

            self.logger.info(f"[CHARACTER] Scale factor: {scale_factor:.3f} mm/pixel")
            self.logger.info(
                f"[CHARACTER] Final character: {actual_character_width:.1f}x{actual_character_height:.1f}mm"
            )
        else:
            scale_factor = 0.36  # Default scale
            self.logger.warning("[CHARACTER] No contours found, using default scale")

        # Second pass: process each part with the unified character scale
        for item, contour in all_contours:
            # Normalize contour scale using the TOTAL CHARACTER scale
            scaled_contour = self.scale_normalizer.normalize_contour(contour, scale_factor)

            # Get part name
            part_name = getattr(item.part_info, "name", "Unknown Part")

            # Create scaled bounds
            x, y, w, h = scaled_contour.bounding_rect
            bounds = ScaledBounds(
                x=0, y=0, width=w, height=h
            )  # Position will be set by layout manager

            # Generate scaled SVG content
            svg_content = self._generate_scaled_part_svg(scaled_contour, part_name, bounds)

            # Create layout item
            layout_item = LayoutItem(
                name=part_name,
                bounds=bounds,
                svg_content=svg_content,
                item_type="part",
                priority=3,  # Parts get highest priority for placement
            )

            layout_items.append(layout_item)

            # Enhanced logging showing part size relative to character
            part_height_percent = (
                (h / actual_character_height) * 100 if actual_character_height > 0 else 0
            )
            self.logger.info(
                f"[CHARACTER] Part '{part_name}': {w:.1f}×{h:.1f}mm ({part_height_percent:.1f}% of character height)"
            )

        return layout_items

    def _generate_scaled_part_svg(
        self, scaled_contour: Any, part_name: str, bounds: ScaledBounds
    ) -> str:
        """Generate SVG content for scaled part with texture image clipped to contour."""

        # Offset the path so top-left of bounding rect is at (0,0)
        try:
            from automataii.domain.generation.contour import AdvancedContourExtractor

            extractor = AdvancedContourExtractor()
            x, y, w, h = scaled_contour.bounding_rect
            offset_path = extractor._apply_offset_to_path(
                scaled_contour.svg_path, -float(x), -float(y)
            )
        except Exception:
            # Fallback to original path and zeroed rect if bounding data missing
            offset_path = scaled_contour.svg_path
            x, y, w, h = 0.0, 0.0, bounds.width, bounds.height

        # Prepare image data URI if available
        image_href = None
        try:
            if hasattr(scaled_contour, "source_image_path") and scaled_contour.source_image_path:
                import base64

                with open(scaled_contour.source_image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                    # Infer mime type simply by extension
                    ext = str(scaled_contour.source_image_path).lower()
                    mime = (
                        "image/png"
                        if ext.endswith(".png")
                        else "image/jpeg"
                        if ext.endswith((".jpg", ".jpeg"))
                        else "image/*"
                    )
                    image_href = f"data:{mime};base64,{b64}"
        except Exception:
            image_href = None

        # Unique clipPath id - store for later defs collection
        import uuid as _uuid

        clip_id = f"clip-{_uuid.uuid4().hex[:8]}"

        # Store clip path definition for collection by parent
        clip_def = f'<clipPath id="{clip_id}"><path d="{offset_path}" /></clipPath>'
        escaped_clip_def = clip_def.replace('"', "&quot;")

        # Build SVG group with image and outline (no nested defs)
        parts = []
        parts.append(
            f'<g class="scaled-part" data-name="{part_name}" data-clip-def="{escaped_clip_def}">'
        )

        # Embedded texture image clipped to contour
        if image_href:
            # Use both href and xlink:href for maximum compatibility
            parts.append(
                f'  <image href="{image_href}" xlink:href="{image_href}" x="0" y="0" '
                f'width="{w:.1f}" height="{h:.1f}" preserveAspectRatio="none" clip-path="url(#{clip_id})" />'
            )
            try:
                self.logger.debug(
                    f"[BLUEPRINT] Embedded texture for part '{part_name}' from {getattr(scaled_contour, 'source_image_path', 'unknown')}"
                )
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)
        else:
            try:
                self.logger.warning(
                    f"[BLUEPRINT] No texture found for part '{part_name}' (no image href)"
                )
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

        # Outline and cutting path on top
        parts.append(f'  <path d="{offset_path}" class="part-outline"/>')
        parts.append(f'  <path d="{offset_path}" class="cutting-path"/>')

        # Part label
        parts.append(
            f'  <text x="{w / 2:.1f}" y="-8" class="part-label" text-anchor="middle">{part_name}</text>'
        )

        # Dimensions and manufacturing notes
        parts.append('  <g class="dimensions">')
        parts.append(
            f'    <line x1="0" y1="{h + 12:.1f}" x2="{w:.1f}" y2="{h + 12:.1f}" class="dimension-line"/>'
        )
        parts.append(
            f'    <text x="{w / 2:.1f}" y="{h + 22:.1f}" class="dimension-text" text-anchor="middle">{w:.0f}mm</text>'
        )
        parts.append(f'    <line x1="-12" y1="0" x2="-12" y2="{h:.1f}" class="dimension-line"/>')
        parts.append(
            f'    <text x="-15" y="{h / 2:.1f}" class="dimension-text" text-anchor="middle" '
            f'transform="rotate(-90, -15, {h / 2:.1f})">{h:.0f}mm</text>'
        )
        parts.append("  </g>")
        parts.append(
            f'  <text x="0" y="{h + 40:.1f}" class="manufacturing-note" font-size="6">Scaled Area: {scaled_contour.area:.0f}mm² | Perimeter: {scaled_contour.perimeter:.0f}mm</text>'
        )
        parts.append("</g>")

        return "\n".join(parts)
