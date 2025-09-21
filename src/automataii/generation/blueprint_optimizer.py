#!/usr/bin/env python3
"""
Blueprint Layout Optimizer for Professional Manufacturing Blueprints
Implements intelligent layout, scale normalization, and mechanism support

Author: Legendary CS Research Collective
Inspired by: Knuth's TeX Layout + Catmull's Graphics + Sutherland's Systems
"""

import logging
import math
from dataclasses import dataclass
from typing import Any

from automataii.generation.contour_extractor import ManufacturingContour


@dataclass
class ScaledBounds:
    """Represents scaled bounding box in real-world units (mm)"""
    x: float
    y: float
    width: float
    height: float

    def area(self) -> float:
        return self.width * self.height

    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    def overlaps_with(self, other: 'ScaledBounds', margin: float = 5.0) -> bool:
        """Check if this bounds overlaps with another (with margin)"""
        return not (
            self.x + self.width + margin <= other.x or
            other.x + other.width + margin <= self.x or
            self.y + self.height + margin <= other.y or
            other.y + other.height + margin <= self.y
        )

@dataclass
class LayoutItem:
    """Represents an item to be laid out in the blueprint"""
    name: str
    bounds: ScaledBounds
    svg_content: str
    item_type: str  # 'part', 'mechanism', 'annotation'
    priority: int = 1  # Higher priority items get better placement


class ScaleNormalizer:
    """
    Normalizes character parts to standard 30cm height
    Inspired by Edwin Catmull's computer graphics scaling principles
    """

    def __init__(self, target_character_height_mm: float = 300.0):
        """
        Initialize scale normalizer

        Args:
            target_character_height_mm: Target character height in millimeters (default: 30cm)
        """
        self.target_height_mm = target_character_height_mm
        self.logger = logging.getLogger(__name__)

    def calculate_scale_factor(self, original_height_pixels: float) -> float:
        """
        Calculate scale factor to convert pixels to target real-world size

        Args:
            original_height_pixels: Original character height in pixels

        Returns:
            Scale factor (mm per pixel)
        """
        if original_height_pixels <= 0:
            self.logger.warning("Invalid original height, using default scale")
            return 0.36  # Default: ~0.36mm per pixel for reasonable sizing

        scale_factor = self.target_height_mm / original_height_pixels
        self.logger.info(f"Calculated scale factor: {scale_factor:.3f} mm/pixel (target: {self.target_height_mm}mm)")
        return scale_factor

    def normalize_contour(self, contour: ManufacturingContour, scale_factor: float) -> ManufacturingContour:
        """Normalize a manufacturing contour to real-world scale"""

        # Scale the bounding rect
        x, y, w, h = contour.bounding_rect
        new_x = x * scale_factor
        new_y = y * scale_factor
        new_w = w * scale_factor
        new_h = h * scale_factor

        # Scale the SVG path
        scaled_svg_path = self._scale_svg_path(contour.svg_path, scale_factor)

        # Create new contour with scaled properties
        # Note: We create a mock contour since we can't easily scale the numpy arrays
        scaled_contour = ManufacturingContour(
            contour=contour.contour,  # Keep original for reference
            simplified_contour=contour.simplified_contour,  # Keep original
            svg_path=scaled_svg_path
        )

        # Update scaled properties
        scaled_contour.area = contour.area * (scale_factor ** 2)
        scaled_contour.perimeter = contour.perimeter * scale_factor
        scaled_contour.bounding_rect = (int(new_x), int(new_y), int(new_w), int(new_h))

        # Preserve source image path for texture embedding if available
        try:
            if hasattr(contour, 'source_image_path'):
                scaled_contour.source_image_path = contour.source_image_path
        except Exception:
            pass

        return scaled_contour

    def _scale_svg_path(self, svg_path: str, scale_factor: float) -> str:
        """Scale coordinates in SVG path data"""
        import re

        def scale_coords(match):
            command = match.group(1)
            x = float(match.group(2)) * scale_factor
            y = float(match.group(3)) * scale_factor
            return f"{command} {x:.2f} {y:.2f}"

        # Scale coordinate patterns
        pattern = r'([ML]) ([\d\.-]+) ([\d\.-]+)'
        scaled_path = re.sub(pattern, scale_coords, svg_path)

        return scaled_path



class SmartLayoutManager:
    """
    Intelligent layout manager for non-overlapping blueprint placement
    Inspired by Don Knuth's TeX layout algorithms
    """

    def __init__(self, page_width_mm: float = 600.0, padding_mm: float = 15.0):
        """
        Initialize layout manager

        Args:
            page_width_mm: Target page width (Letter: ~216mm, A4: ~210mm, but we use wider for readability)
            padding_mm: Minimum padding between items
        """
        self.page_width_mm = page_width_mm
        self.padding_mm = padding_mm
        self.logger = logging.getLogger(__name__)

    def calculate_optimal_layout(self, items: list[LayoutItem]) -> list[LayoutItem]:
        """
        Calculate optimal non-overlapping layout for all items

        Args:
            items: List of items to lay out

        Returns:
            List of items with updated positions
        """
        if not items:
            return items

        # Sort items by priority and size (larger, higher priority first)
        sorted_items = sorted(items, key=lambda item: (
            -item.priority,
            -item.bounds.area()
        ))

        # Place items using modified bin packing algorithm
        placed_items = []
        current_y = self.padding_mm
        row_height = 0
        current_x = self.padding_mm

        for item in sorted_items:
            # Check if item fits in current row
            if current_x + item.bounds.width <= self.page_width_mm - self.padding_mm:
                # Place in current row
                new_bounds = ScaledBounds(
                    x=current_x,
                    y=current_y,
                    width=item.bounds.width,
                    height=item.bounds.height
                )

                # Check for overlaps with already placed items
                if not self._has_overlaps(new_bounds, placed_items):
                    item.bounds = new_bounds
                    placed_items.append(item)

                    current_x += item.bounds.width + self.padding_mm
                    row_height = max(row_height, item.bounds.height)
                    continue

            # Move to next row
            current_y += row_height + self.padding_mm
            current_x = self.padding_mm
            row_height = item.bounds.height

            # Place item at start of new row
            item.bounds = ScaledBounds(
                x=current_x,
                y=current_y,
                width=item.bounds.width,
                height=item.bounds.height
            )
            placed_items.append(item)

            current_x += item.bounds.width + self.padding_mm

        self.logger.info(f"Successfully laid out {len(placed_items)} items")
        return placed_items

    def _has_overlaps(self, bounds: ScaledBounds, placed_items: list[LayoutItem]) -> bool:
        """Check if bounds overlap with any placed items"""
        for item in placed_items:
            if bounds.overlaps_with(item.bounds, self.padding_mm):
                return True
        return False

    def calculate_total_dimensions(self, items: list[LayoutItem]) -> tuple[float, float]:
        """Calculate total blueprint dimensions from placed items"""
        if not items:
            return (self.page_width_mm, 400.0)  # Default size

        max_x = max(item.bounds.x + item.bounds.width for item in items)
        max_y = max(item.bounds.y + item.bounds.height for item in items)

        total_width = max_x + self.padding_mm
        total_height = max_y + self.padding_mm

        return (total_width, total_height)

    def optimize_layout(self, items: list[LayoutItem], target_page_width_mm: float, target_page_height_mm: float) -> tuple[list[LayoutItem], float, float]:
        """
        Optimize layout of items and return positioned items with total dimensions
        
        Args:
            items: List of items to lay out
            target_page_width_mm: Target page width in mm
            target_page_height_mm: Target page height in mm
            
        Returns:
            Tuple of (positioned_items, total_width_mm, total_height_mm)
        """
        # Update page width if different from default
        self.page_width_mm = target_page_width_mm

        # Calculate optimal layout
        positioned_items = self.calculate_optimal_layout(items)

        # Calculate total dimensions
        total_width, total_height = self.calculate_total_dimensions(positioned_items)

        # Ensure minimum dimensions
        total_width = max(total_width, target_page_width_mm)
        total_height = max(total_height, target_page_height_mm)

        return positioned_items, total_width, total_height


class EnhancedMechanismProcessor:
    """
    Enhanced mechanism processor supporting all mechanism types
    Inspired by Ivan Sutherland's comprehensive CAD systems
    """

    def __init__(self, scale_normalizer: ScaleNormalizer):
        self.scale_normalizer = scale_normalizer
        self.logger = logging.getLogger(__name__)

        # Standard mechanism sizes in real-world units (mm)
        self.standard_mechanism_sizes = {
            'gear': {'width': 60, 'height': 60},
            'linkage': {'width': 100, 'height': 30},
            'cam': {'width': 80, 'height': 80},
            'pulley': {'width': 50, 'height': 50},
            'belt': {'width': 120, 'height': 20},
            'spring': {'width': 40, 'height': 80},
            'damper': {'width': 30, 'height': 60}
        }

    def process_mechanism(self, mech_id: str, mech_data: dict[str, Any], unit_system: str = "metric") -> LayoutItem | None:
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
            mechanism_type = mech_data.get('type', 'unknown')  # Fixed: GUI uses 'type' not 'mechanism_type'
            
            self.logger.info(f"[MECHANISM] Processing {mech_id}: type={mechanism_type}")
            self.logger.info(f"[MECHANISM]   Keys in mech_data: {list(mech_data.keys())}")

            # Enhanced mechanism processing with scale data
            if 'total_scale_factor' in mech_data and 'real_world_params' in mech_data:
                # Use the real-world parameters and scale data from the screen
                real_world_params = mech_data['real_world_params']
                scale_factor = mech_data['total_scale_factor']

                self.logger.info(f"[MECHANISM] Processing {mech_id} with screen-calculated scale: {scale_factor:.3f}")

                # Calculate actual mechanism dimensions from real parameters
                actual_width, actual_height = self._calculate_mechanism_dimensions_from_params(
                    real_world_params, mechanism_type
                )

                self.logger.info(f"[MECHANISM] Calculated dimensions for {mech_id}: "
                               f"{actual_width:.1f}x{actual_height:.1f}mm (scale: {scale_factor:.3f})")
            else:
                # Fallback to standard sizes
                self.logger.warning(f"[MECHANISM] No screen scale data for {mech_id}, using standard sizes")
                if 'real_world_params' not in mech_data:
                    self.logger.warning("[MECHANISM]   Missing: real_world_params")
                if 'total_scale_factor' not in mech_data:
                    self.logger.warning("[MECHANISM]   Missing: total_scale_factor")

                standard_size = self.standard_mechanism_sizes.get(
                    mechanism_type,
                    {'width': 60, 'height': 60}  # Default size
                )

                # Apply any custom scaling from mechanism data
                scale = mech_data.get('scale', 1.0)
                actual_width = standard_size['width'] * scale
                actual_height = standard_size['height'] * scale

                self.logger.info(f"[MECHANISM] Using standard dimensions for {mech_id}: "
                                f"{actual_width:.1f}x{actual_height:.1f}mm (from standard: {standard_size})")

            # Create scaled bounds
            bounds = ScaledBounds(
                x=0,  # Will be positioned by layout manager
                y=0,
                width=actual_width,
                height=actual_height
            )

            self.logger.info(f"[MECHANISM] Final bounds for {mech_id}: {bounds.width:.1f}x{bounds.height:.1f}mm")

            # Generate mechanism SVG content with enhanced scaling information and unit system
            svg_content = self._generate_mechanism_svg(mech_id, mech_data, bounds, unit_system)
            
            # Log first 200 chars of SVG for debugging
            self.logger.info(f"[MECHANISM] Generated SVG for {mech_id} (first 200 chars): {svg_content[:200] if svg_content else 'EMPTY'}")

            # Create layout item
            layout_item = LayoutItem(
                name=mech_id,
                bounds=bounds,
                svg_content=svg_content,
                item_type='mechanism',
                priority=2  # Mechanisms get medium priority
            )

            self.logger.info(f"[MECHANISM] Successfully processed {mech_id}: {actual_width:.1f}x{actual_height:.1f}mm")
            return layout_item

        except Exception as e:
            self.logger.error(f"[MECHANISM] Error processing mechanism {mech_id}: {e}")
            import traceback
            self.logger.error(f"[MECHANISM] Traceback: {traceback.format_exc()}")
            return None

    def _calculate_mechanism_dimensions_from_params(self, real_world_params: dict[str, Any], mechanism_type: str) -> tuple[float, float]:
        """
        Calculate mechanism bounding box dimensions from real-world parameters.

        Args:
            real_world_params: Real-world mechanism parameters in millimeters
            mechanism_type: Type of mechanism

        Returns:
            Tuple of (width_mm, height_mm)
        """
        try:
            if mechanism_type == "4_bar_linkage":
                # For 4-bar linkage, use the maximum link lengths to estimate bounds
                l1 = real_world_params.get('l1_mm', 50.0)
                l2 = real_world_params.get('l2_mm', 30.0)
                l3 = real_world_params.get('l3_mm', 40.0)
                l4 = real_world_params.get('l4_mm', 35.0)

                # Estimate bounding box as maximum reach of the linkage
                max_width = l1 + max(l2, l3, l4) * 1.2  # Add some padding
                max_height = max(l2, l3, l4) * 1.5  # Allow for vertical movement

                return max_width, max_height

            elif mechanism_type == "cam":
                # For cam, use base radius and eccentricity
                base_radius = real_world_params.get('base_radius_mm', 25.0)
                eccentricity = real_world_params.get('eccentricity_mm', 5.0)

                # Cam bounding box includes rotation and follower movement
                width = (base_radius + eccentricity) * 2.5  # Include follower space
                height = (base_radius + eccentricity) * 2.2  # Vertical movement space

                return width, height

            elif mechanism_type in ["gear", "planetary_gear"]:
                # For gears, use the larger of the gear radii
                max_radius = 0
                for param_name in ['r1_mm', 'r2_mm', 'r_sun_mm', 'r_planet_mm']:
                    if param_name in real_world_params:
                        max_radius = max(max_radius, real_world_params[param_name])

                if max_radius == 0:
                    max_radius = 30.0  # Default

                # Add space for gear mesh and rotation
                width = max_radius * 3.0  # Allow for two gears side by side
                height = max_radius * 2.2  # Vertical clearance

                return width, height

            else:
                # Default dimensions for unknown mechanism types
                scale_factor = real_world_params.get('scale_factor_used', 1.0)
                return 60.0 * scale_factor, 60.0 * scale_factor

        except Exception as e:
            self.logger.warning(f"Error calculating mechanism dimensions: {e}")
            # Return reasonable defaults
            return 80.0, 60.0

    def _generate_mechanism_svg(self, mech_id: str, mech_data: dict[str, Any], bounds: ScaledBounds, unit_system: str = "metric") -> str:
        """Generate SVG content for mechanism with enhanced support for all types"""

        mechanism_type = mech_data.get('type', 'unknown')  # Fixed: GUI uses 'type' not 'mechanism_type'

        # Prefer readable drawings; if 4-bar and key_points exist, render actual linkage cloned from screen.
        base_svg = None
        if mechanism_type == '4_bar_linkage' and isinstance(mech_data.get('key_points'), dict):
            try:
                base_svg = self._generate_4bar_from_keypoints_svg(mech_data, bounds)
            except Exception:
                base_svg = None
        elif mechanism_type in ['5_bar_linkage', '6_bar_linkage'] and isinstance(mech_data.get('key_points'), dict):
            try:
                base_svg = self._generate_multibar_from_keypoints_svg(mech_data, bounds)
            except Exception:
                base_svg = None
        elif mechanism_type == 'gear':
            try:
                base_svg = self._generate_gears_from_params_svg(mech_data, bounds)
            except Exception:
                base_svg = None
        elif mechanism_type == 'planetary_gear':
            try:
                base_svg = self._generate_planetary_gear_from_params_svg(mech_data, bounds)
            except Exception:
                base_svg = None
        elif mechanism_type == 'cam':
            try:
                base_svg = self._generate_cam_from_params_svg(mech_data, bounds)
            except Exception:
                base_svg = None
        if not base_svg:
            # Fallback to standard representation
            base_svg = self._generate_standard_mechanism_svg(mech_id, mechanism_type, bounds)

        # Optionally enable detailed generators for extremely rich visuals.
        # Keep disabled so our key_points-based clone isn't overridden.
        use_detailed_generators = False
        if use_detailed_generators:
            try:
                if mechanism_type == 'gear':
                    from automataii.generation.gear import GearGenerator
                    generator = GearGenerator()
                    enhanced_svg = generator.generate_svg(mech_data)
                    if enhanced_svg and len(enhanced_svg.strip()) > 10:
                        base_svg = enhanced_svg
                elif mechanism_type == '4_bar_linkage':
                    from automataii.generation.linkage import LinkageGenerator
                    generator = LinkageGenerator()
                    enhanced_svg = generator.generate_svg(mech_data)
                    if enhanced_svg and len(enhanced_svg.strip()) > 10:
                        base_svg = enhanced_svg
                elif mechanism_type == 'cam':
                    from automataii.generation.cam import CamGenerator
                    generator = CamGenerator()
                    enhanced_svg = generator.generate_svg(mech_data)
                    if enhanced_svg and len(enhanced_svg.strip()) > 10:
                        base_svg = enhanced_svg
                elif mechanism_type == 'planetary_gear':
                    from automataii.generation.gear import GearGenerator
                    generator = GearGenerator()
                    enhanced_svg = generator.generate_svg(mech_data)
                    if enhanced_svg and len(enhanced_svg.strip()) > 10:
                        base_svg = enhanced_svg
            except Exception as e:
                self.logger.warning(f"Generator enhancement failed for {mechanism_type}: {e}, using standard")

        # Calculate text bounds to prevent overlapping
        text_height = 60  # Reserve space for labels
        total_bounds_height = bounds.height + text_height

        # Generate real-world parameter annotations with unit system support
        param_annotations = self._generate_parameter_annotations(mech_data, bounds, unit_system)

        # Calculate mechanism name for display
        mechanism_name = mech_data.get('part_name', mech_id)

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
            <text x="{bounds.width/2:.1f}" y="{bounds.height + 25:.1f}"
                  class="mechanism-label" text-anchor="middle" font-size="12" font-weight="bold" fill="#222">
                {mechanism_name}
            </text>

            <text x="{bounds.width/2:.1f}" y="{bounds.height + 40:.1f}"
                  class="mechanism-type" text-anchor="middle" font-size="10" fill="#666">
                {mechanism_type.replace('_', ' ').title()}
            </text>

            <!-- Real-world parameter annotations (positioned to avoid overlap) -->
            {param_annotations}
        </g>
        '''

        return positioned_svg

    def _generate_mechanism_patterns(self, mech_id: str, mechanism_type: str, bounds: ScaledBounds) -> str:
        """Generate enhanced visual patterns and textures for mechanisms to improve blueprint appearance"""
        patterns = []

        try:
            # Create unique pattern IDs for this mechanism
            pattern_id = f"pattern-{mech_id}-{mechanism_type}"
            gradient_id = f"gradient-{mech_id}-{mechanism_type}"

            # Mechanism-specific patterns for enhanced visual appearance
            if mechanism_type == 'gear':
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

            elif mechanism_type == '4_bar_linkage':
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

            elif mechanism_type == 'cam':
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

        return '\n'.join(patterns)

    def _generate_4bar_from_keypoints_svg(self, mech_data: dict[str, Any], bounds: ScaledBounds) -> str:
        """Generate detailed 4-bar linkage with proper thickness, holes, and manufacturing details."""
        kp = mech_data.get('key_points', {})
        factor = float(mech_data.get('total_scale_factor', 1.0))

        required = ["ground_pivot_1", "ground_pivot_2", "crank_end", "rocker_end"]
        if not all(name in kp for name in required):
            return self._generate_standard_mechanism_svg(mech_data.get('id', 'mech'), '4_bar_linkage', bounds)

        def to_mm(name: str) -> tuple[float, float]:
            x, y = kp[name]
            return float(x) * factor, float(y) * factor

        O1 = to_mm("ground_pivot_1")
        O2 = to_mm("ground_pivot_2")
        A = to_mm("crank_end")
        B = to_mm("rocker_end")

        xs = [O1[0], O2[0], A[0], B[0]]
        ys = [O1[1], O2[1], A[1], B[1]]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max_x - min_x
        height = max_y - min_y

        # Margin inside bounds
        margin = 8.0
        avail_w = max(10.0, bounds.width - 2 * margin)
        avail_h = max(10.0, bounds.height - 2 * margin)

        # Uniform scale to fit drawing if oversized
        scale = min(1.0, avail_w / width if width > 0 else 1.0, avail_h / height if height > 0 else 1.0)

        def pack(pt: tuple[float, float]) -> tuple[float, float]:
            px = (pt[0] - min_x) * scale + margin
            py = (pt[1] - min_y) * scale + margin
            return px, py

        O1p = pack(O1)
        O2p = pack(O2)
        Ap = pack(A)
        Bp = pack(B)

        # Enhanced colors and manufacturing parameters
        color_ground = "#2c3e50"
        color_crank = "#e74c3c"    # red
        color_coupler = "#27ae60"  # green
        color_rocker = "#2980b9"   # blue

        # Manufacturing specifications
        link_thickness = 6.0 * scale  # 6mm thick bars
        hole_radius = 2.5 * scale    # 5mm diameter holes
        joint_radius = 4.0 * scale   # 8mm diameter pins

        def manufacturing_link(x1, y1, x2, y2, color, name, length_mm):
            """Generate a manufacturing-ready link with thickness and holes"""
            import math

            # Calculate link angle and dimensions
            dx = x2 - x1
            dy = y2 - y1
            angle = math.atan2(dy, dx)
            length_scaled = math.sqrt(dx*dx + dy*dy)

            # Link outline (rectangular with rounded ends)
            half_thick = link_thickness / 2
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)

            # Corner points of the rectangular link
            p1 = (x1 + half_thick * sin_a, y1 - half_thick * cos_a)  # top-left
            p2 = (x1 - half_thick * sin_a, y1 + half_thick * cos_a)  # bottom-left
            p3 = (x2 - half_thick * sin_a, y2 + half_thick * cos_a)  # bottom-right
            p4 = (x2 + half_thick * sin_a, y2 - half_thick * cos_a)  # top-right

            # Generate link as rounded rectangle
            link_path = f'''
            <!-- {name} link body with thickness -->
            <path d="M{p1[0]:.1f},{p1[1]:.1f} 
                     L{p4[0]:.1f},{p4[1]:.1f}
                     A{half_thick:.1f},{half_thick:.1f} 0 0,1 {p3[0]:.1f},{p3[1]:.1f}
                     L{p2[0]:.1f},{p2[1]:.1f}
                     A{half_thick:.1f},{half_thick:.1f} 0 0,1 {p1[0]:.1f},{p1[1]:.1f} Z"
                  fill="url(#gradient-{name})" stroke="{color}" stroke-width="1.5"/>
            
            <!-- End holes for pins -->
            <circle cx="{x1:.1f}" cy="{y1:.1f}" r="{hole_radius:.1f}" 
                    fill="#fff" stroke="{color}" stroke-width="1"/>
            <circle cx="{x2:.1f}" cy="{y2:.1f}" r="{hole_radius:.1f}" 
                    fill="#fff" stroke="{color}" stroke-width="1"/>
                    
            <!-- Dimension line above link -->
            <line x1="{x1:.1f}" y1="{y1 - 15:.1f}" x2="{x2:.1f}" y2="{y2 - 15:.1f}" 
                  stroke="#666" stroke-width="0.5" stroke-dasharray="2,2"/>
            <text x="{(x1+x2)/2:.1f}" y="{(y1+y2)/2 - 18:.1f}" 
                  class="dimension-text" font-size="7" text-anchor="middle" fill="{color}">
                  {name} {length_mm:.1f}mm
            </text>
            
            <!-- Material specification -->
            <text x="{(x1+x2)/2:.1f}" y="{(y1+y2)/2 + half_thick + 12:.1f}" 
                  class="manufacturing-note" font-size="6" text-anchor="middle" fill="#666">
                  6mm steel bar
            </text>
            '''
            return link_path

        # Generate gradients for manufacturing appearance
        gradients = '''
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
        '''

        # Dimension calculations using real mm (unscaled by fit)
        def dist_mm(p_mm: tuple[float, float], q_mm: tuple[float, float]) -> float:
            dx = p_mm[0] - q_mm[0]
            dy = p_mm[1] - q_mm[1]
            return math.hypot(dx, dy)

        L1_ground = dist_mm(O1, O2)  # Ground link
        L2_crank = dist_mm(O1, A)   # Crank
        L3_coupler = dist_mm(A, B)  # Coupler
        L4_rocker = dist_mm(B, O2)  # Rocker

        # Build comprehensive manufacturing SVG
        parts = [gradients]

        # Generate manufacturing-ready links
        parts.append(manufacturing_link(O1p[0], O1p[1], O2p[0], O2p[1], color_ground, "Ground", L1_ground))
        parts.append(manufacturing_link(O1p[0], O1p[1], Ap[0], Ap[1], color_crank, "Crank", L2_crank))
        parts.append(manufacturing_link(Ap[0], Ap[1], Bp[0], Bp[1], color_coupler, "Coupler", L3_coupler))
        parts.append(manufacturing_link(Bp[0], Bp[1], O2p[0], O2p[1], color_rocker, "Rocker", L4_rocker))

        # Enhanced pivot points with mounting details
        parts.extend([
            f'''<!-- Ground pivot 1 with mounting base -->
            <circle cx="{O1p[0]:.1f}" cy="{O1p[1]:.1f}" r="{joint_radius * 1.5:.1f}" 
                    fill="#34495e" stroke="#2c3e50" stroke-width="2"/>
            <circle cx="{O1p[0]:.1f}" cy="{O1p[1]:.1f}" r="{joint_radius:.1f}" 
                    fill="none" stroke="#fff" stroke-width="1"/>
            <text x="{O1p[0]:.1f}" y="{O1p[1] + 25:.1f}" class="manufacturing-note" 
                  font-size="6" text-anchor="middle" fill="#333">Ground Pivot 1</text>''',

            f'''<!-- Ground pivot 2 with mounting base -->
            <circle cx="{O2p[0]:.1f}" cy="{O2p[1]:.1f}" r="{joint_radius * 1.5:.1f}" 
                    fill="#34495e" stroke="#2c3e50" stroke-width="2"/>
            <circle cx="{O2p[0]:.1f}" cy="{O2p[1]:.1f}" r="{joint_radius:.1f}" 
                    fill="none" stroke="#fff" stroke-width="1"/>
            <text x="{O2p[0]:.1f}" y="{O2p[1] + 25:.1f}" class="manufacturing-note" 
                  font-size="6" text-anchor="middle" fill="#333">Ground Pivot 2</text>''',

            f'''<!-- Moving joints -->
            <circle cx="{Ap[0]:.1f}" cy="{Ap[1]:.1f}" r="{joint_radius:.1f}" 
                    fill="#f39c12" stroke="#e67e22" stroke-width="1.5"/>
            <circle cx="{Bp[0]:.1f}" cy="{Bp[1]:.1f}" r="{joint_radius:.1f}" 
                    fill="#f39c12" stroke="#e67e22" stroke-width="1.5"/>'''
        ])

        # Manufacturing specifications panel
        spec_panel = f'''
        <g class="manufacturing-specs">
            <rect x="{bounds.width - 150}" y="10" width="140" height="120" 
                  fill="#f8f9fa" stroke="#dee2e6" stroke-width="1" rx="3"/>
            <text x="{bounds.width - 145}" y="25" class="manufacturing-note" font-size="8" font-weight="bold">
                Manufacturing Specifications
            </text>
            <text x="{bounds.width - 145}" y="40" class="manufacturing-note" font-size="7">
                Material: 6mm Steel Bar
            </text>
            <text x="{bounds.width - 145}" y="52" class="manufacturing-note" font-size="7">
                Hole Diameter: 5mm (for 4mm pins)
            </text>
            <text x="{bounds.width - 145}" y="64" class="manufacturing-note" font-size="7">
                Pin Diameter: 4mm Steel
            </text>
            <text x="{bounds.width - 145}" y="76" class="manufacturing-note" font-size="7">
                Ground Mount: 8mm holes
            </text>
            <text x="{bounds.width - 145}" y="88" class="manufacturing-note" font-size="7">
                Tolerance: ±0.1mm
            </text>
            <text x="{bounds.width - 145}" y="105" class="manufacturing-note" font-size="7" font-weight="bold">
                Assembly Order:
            </text>
            <text x="{bounds.width - 145}" y="117" class="manufacturing-note" font-size="6">
                1. Ground → 2. Crank → 3. Coupler → 4. Rocker
            </text>
        </g>
        '''

        parts.append(spec_panel)

        return ''.join(parts)

    def _generate_multibar_from_keypoints_svg(self, mech_data: dict[str, Any], bounds: ScaledBounds) -> str:
        """Generic N-bar (5/6-bar) linkage from key_points with readable bars and joints."""
        kp = mech_data.get('key_points', {})
        factor = float(mech_data.get('total_scale_factor', 1.0))

        # Collect joints if present
        names_order = [
            'ground_pivot_1', 'joint_3', 'joint_4', 'joint_5', 'ground_pivot_2'
        ]
        pts_mm = []
        for name in names_order:
            if name in kp:
                x, y = kp[name]
                pts_mm.append((float(x) * factor, float(y) * factor, name))

        if len(pts_mm) < 3:
            return ''

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

        def pack_xy(x, y):
            return (x - min_x) * scale + margin, (y - min_y) * scale + margin

        # Colors per link segment for readability
        colors = ['#e74c3c', '#27ae60', '#2980b9', '#8e44ad']

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
        for (x, y, name) in pts_mm:
            px, py = pack_xy(x, y)
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="none" stroke="#333" stroke-width="1.2"/>')
            parts.append(f'<text x="{px:.1f}" y="{py-7:.1f}" class="mechanism-label" font-size="7" text-anchor="middle">{name}</text>')

        return '<g>' + ''.join(parts) + '</g>'

    def _mm_params(self, mech_data: dict[str, Any], names: list[str]) -> dict[str, float]:
        """Helper to fetch parameter values in mm from real_world_params or by scaling params."""
        mm = {}
        rwp = mech_data.get('real_world_params', {})
        if rwp:
            for n in names:
                if n in rwp:
                    mm[n] = float(rwp[n])
        if not mm:
            factor = float(mech_data.get('total_scale_factor', 1.0))
            params = mech_data.get('params', {})
            for n in names:
                base = n.replace('_mm', '')
                if base in params:
                    mm[n] = float(params[base]) * factor
        return mm

    def _generate_gears_from_params_svg(self, mech_data: dict[str, Any], bounds: ScaledBounds) -> str:
        """Enhanced two-gear mesh with manufacturing specifications, tooth details, and mounting holes."""
        mm = self._mm_params(mech_data, ['r1_mm', 'r2_mm'])
        r1 = mm.get('r1_mm', 30.0)
        r2 = mm.get('r2_mm', 20.0)

        # Centers from key_points if available, else place side-by-side at distance r1+r2
        kp = mech_data.get('key_points', {})
        factor = float(mech_data.get('total_scale_factor', 1.0))
        if 'gear1_center' in kp and 'gear2_center' in kp:
            x1, y1 = kp['gear1_center']
            x2, y2 = kp['gear2_center']
            c1 = (float(x1) * factor, float(y1) * factor)
            c2 = (float(x2) * factor, float(y2) * factor)
        else:
            c1 = (0.0, 0.0)
            c2 = (r1 + r2, 0.0)

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

        def pack(pt):
            return (pt[0] - min_x) * scale + margin, (pt[1] - min_y) * scale + margin

        c1p = pack(c1)
        c2p = pack(c2)
        r1p = r1 * scale
        r2p = r2 * scale

        # Manufacturing specifications for gears
        hub_ratio = 0.4  # Hub diameter = 40% of gear diameter
        keyway_width = max(2.0 * scale, 1.0)  # Minimum 2mm keyway
        shaft_diameter = max(6.0 * scale, 2.0)  # Minimum 6mm shaft
        tooth_height = max(2.0 * scale, 1.0)  # Tooth height
        mounting_holes = 4  # Number of mounting holes

        # Calculate gear specifications
        module = 2.0  # Standard gear module in mm
        teeth1 = max(int(2 * r1 / module), 8)  # Minimum 8 teeth
        teeth2 = max(int(2 * r2 / module), 8)  # Minimum 8 teeth
        pitch_diameter1 = teeth1 * module
        pitch_diameter2 = teeth2 * module

        parts = []

        # Generate enhanced gradients for metallic appearance
        parts.append('''
        <defs>
            <linearGradient id="gear-gradient-1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#e8f4f8;stop-opacity:1"/>
                <stop offset="30%" style="stop-color:#d1e9f0;stop-opacity:1"/>
                <stop offset="70%" style="stop-color:#b8dce8;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#a0c4d1;stop-opacity:1"/>
            </linearGradient>
            <linearGradient id="gear-gradient-2" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#f5f0e8;stop-opacity:1"/>
                <stop offset="30%" style="stop-color:#ede4d1;stop-opacity:1"/>
                <stop offset="70%" style="stop-color:#e3d7b8;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#d4c8a0;stop-opacity:1"/>
            </linearGradient>
            <pattern id="gear-teeth-pattern" patternUnits="userSpaceOnUse" width="4" height="4">
                <rect width="4" height="4" fill="#f0f0f0"/>
                <circle cx="2" cy="2" r="0.5" fill="#999"/>
            </pattern>
        </defs>
        ''')

        # Generate detailed gear 1
        gear1_svg = self._generate_detailed_gear(
            c1p, r1p, teeth1, pitch_diameter1, hub_ratio, keyway_width,
            shaft_diameter, tooth_height, mounting_holes, "gear-gradient-1", "Gear 1", r1
        )
        parts.append(gear1_svg)

        # Generate detailed gear 2
        gear2_svg = self._generate_detailed_gear(
            c2p, r2p, teeth2, pitch_diameter2, hub_ratio, keyway_width,
            shaft_diameter, tooth_height, mounting_holes, "gear-gradient-2", "Gear 2", r2
        )
        parts.append(gear2_svg)

        # Mesh line and center distance
        parts.append(f'''
        <!-- Center distance line -->
        <line x1="{c1p[0]:.1f}" y1="{c1p[1]:.1f}" x2="{c2p[0]:.1f}" y2="{c2p[1]:.1f}" 
              stroke="#666" stroke-width="0.8" stroke-dasharray="3,3"/>
        <text x="{(c1p[0] + c2p[0])/2:.1f}" y="{(c1p[1] + c2p[1])/2 - 8:.1f}" 
              class="dimension-text" font-size="7" text-anchor="middle" fill="#666">
              Center: {r1 + r2:.1f}mm
        </text>
        ''')

        # Gear ratio calculation and display
        gear_ratio = r1 / r2 if r2 > 0 else 1.0

        # Manufacturing specifications panel
        spec_panel = f'''
        <g class="gear-manufacturing-specs">
            <rect x="{bounds.width - 160}" y="10" width="150" height="140" 
                  fill="#f8f9fa" stroke="#dee2e6" stroke-width="1" rx="3"/>
            <text x="{bounds.width - 155}" y="25" class="manufacturing-note" font-size="8" font-weight="bold">
                Gear Manufacturing Specifications
            </text>
            
            <!-- Gear 1 specs -->
            <text x="{bounds.width - 155}" y="40" class="manufacturing-note" font-size="7" font-weight="bold" fill="#2c3e50">
                Gear 1 (Drive):
            </text>
            <text x="{bounds.width - 155}" y="52" class="manufacturing-note" font-size="6">
                • Diameter: {2*r1:.1f}mm ({teeth1} teeth)
            </text>
            <text x="{bounds.width - 155}" y="62" class="manufacturing-note" font-size="6">
                • Module: {module:.1f}mm | Shaft: 6mm
            </text>
            <text x="{bounds.width - 155}" y="72" class="manufacturing-note" font-size="6">
                • Material: Steel/Aluminum
            </text>
            
            <!-- Gear 2 specs -->
            <text x="{bounds.width - 155}" y="87" class="manufacturing-note" font-size="7" font-weight="bold" fill="#8e44ad">
                Gear 2 (Driven):
            </text>
            <text x="{bounds.width - 155}" y="99" class="manufacturing-note" font-size="6">
                • Diameter: {2*r2:.1f}mm ({teeth2} teeth)
            </text>
            <text x="{bounds.width - 155}" y="109" class="manufacturing-note" font-size="6">
                • Module: {module:.1f}mm | Shaft: 6mm
            </text>
            <text x="{bounds.width - 155}" y="119" class="manufacturing-note" font-size="6">
                • Material: Steel/Aluminum
            </text>
            
            <!-- System specs -->
            <text x="{bounds.width - 155}" y="134" class="manufacturing-note" font-size="7" font-weight="bold" fill="#e74c3c">
                System: Ratio {gear_ratio:.2f}:1
            </text>
            <text x="{bounds.width - 155}" y="146" class="manufacturing-note" font-size="6">
                Center Distance: {r1 + r2:.1f}mm
            </text>
        </g>
        '''

        parts.append(spec_panel)

        return ''.join(parts)

    def _generate_detailed_gear(self, center, radius, teeth, pitch_diameter, hub_ratio,
                               keyway_width, shaft_diameter, tooth_height, mounting_holes,
                               gradient_id, gear_name, actual_radius_mm):
        """Generate a detailed gear with teeth, hub, keyway, and mounting holes"""

        cx, cy = center
        hub_radius = radius * hub_ratio
        shaft_radius = shaft_diameter / 2

        parts = []

        # Main gear body with realistic tooth outline
        tooth_radius = radius + tooth_height
        parts.append(f'''
        <!-- {gear_name} main body -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" 
                fill="url(#{gradient_id})" stroke="#34495e" stroke-width="1.5"/>
        ''')

        # Generate simplified tooth representation
        tooth_count = max(teeth, 8)
        for i in range(tooth_count):
            angle = (2 * math.pi * i) / tooth_count
            tooth_x = cx + (radius + tooth_height/2) * math.cos(angle)
            tooth_y = cy + (radius + tooth_height/2) * math.sin(angle)

            parts.append(f'''
            <circle cx="{tooth_x:.1f}" cy="{tooth_y:.1f}" r="{tooth_height/3:.1f}" 
                    fill="#bdc3c7" stroke="#95a5a6" stroke-width="0.5"/>
            ''')

        # Hub with mounting holes
        parts.append(f'''
        <!-- {gear_name} hub -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{hub_radius:.1f}" 
                fill="url(#{gradient_id})" stroke="#2c3e50" stroke-width="1.2"/>
        ''')

        # Generate mounting holes around the hub
        for i in range(mounting_holes):
            hole_angle = (2 * math.pi * i) / mounting_holes
            hole_radius = hub_radius * 0.7  # 70% of hub radius
            hole_x = cx + hole_radius * math.cos(hole_angle)
            hole_y = cy + hole_radius * math.sin(hole_angle)

            parts.append(f'''
            <circle cx="{hole_x:.1f}" cy="{hole_y:.1f}" r="{shaft_radius*0.6:.1f}" 
                    fill="#fff" stroke="#7f8c8d" stroke-width="0.8"/>
            ''')

        # Center shaft hole
        parts.append(f'''
        <!-- {gear_name} center shaft hole -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{shaft_radius:.1f}" 
                fill="#fff" stroke="#2c3e50" stroke-width="1"/>
        ''')

        # Keyway slot
        parts.append(f'''
        <!-- {gear_name} keyway -->
        <rect x="{cx - keyway_width/2:.1f}" y="{cy - shaft_radius:.1f}" 
              width="{keyway_width:.1f}" height="{shaft_radius*0.6:.1f}" 
              fill="#7f8c8d"/>
        ''')

        # Gear label with specifications
        parts.append(f'''
        <text x="{cx:.1f}" y="{cy - radius - 15:.1f}" 
              class="mechanism-label" font-size="8" text-anchor="middle" font-weight="bold">
              {gear_name}
        </text>
        <text x="{cx:.1f}" y="{cy - radius - 5:.1f}" 
              class="dimension-text" font-size="6" text-anchor="middle" fill="#666">
              ⌀{actual_radius_mm*2:.1f}mm ({teeth}T)
        </text>
        ''')

        return ''.join(parts)

    def _generate_planetary_gear_from_params_svg(self, mech_data: dict[str, Any], bounds: ScaledBounds) -> str:
        """Enhanced planetary gear system with sun, planets, ring gear, and carrier arm details."""
        mm = self._mm_params(mech_data, ['r_sun_mm', 'r_planet_mm'])
        rs = mm.get('r_sun_mm', 20.0)
        rp = mm.get('r_planet_mm', 12.0)

        # Calculate ring gear radius (sun + 2*planet)
        rr = rs + 2 * rp

        # Number of planet gears (typically 3 or 4)
        num_planets = 3

        kp = mech_data.get('key_points', {})
        factor = float(mech_data.get('total_scale_factor', 1.0))
        if 'sun_center' in kp:
            sx, sy = kp['sun_center']
            cs = (float(sx) * factor, float(sy) * factor)
        else:
            cs = (0.0, 0.0)

        # Calculate system bounds including ring gear
        xs = [cs[0] - rr, cs[0] + rr]
        ys = [cs[1] - rr, cs[1] + rr]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max(10.0, max_x - min_x)
        height = max(10.0, max_y - min_y)

        margin = 8.0
        avail_w = max(10.0, bounds.width - 2 * margin)
        avail_h = max(10.0, bounds.height - 2 * margin)
        scale = min(1.0, avail_w / width, avail_h / height)

        def pack(pt):
            return (pt[0] - min_x) * scale + margin, (pt[1] - min_y) * scale + margin

        csp = pack(cs)
        rsp = rs * scale
        rpp = rp * scale
        rrp = rr * scale

        # Planet center distance (sun radius + planet radius)
        planet_orbit_radius = (rs + rp) * scale

        parts = []

        # Enhanced gradients for planetary gear system
        parts.append('''
        <defs>
            <radialGradient id="sun-gradient" cx="50%" cy="50%" r="50%">
                <stop offset="0%" style="stop-color:#ffeaa7;stop-opacity:1"/>
                <stop offset="50%" style="stop-color:#fdcb6e;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#e17055;stop-opacity:1"/>
            </radialGradient>
            <radialGradient id="planet-gradient" cx="50%" cy="50%" r="50%">
                <stop offset="0%" style="stop-color:#74b9ff;stop-opacity:1"/>
                <stop offset="50%" style="stop-color:#0984e3;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#2d3436;stop-opacity:1"/>
            </radialGradient>
            <linearGradient id="ring-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#636e72;stop-opacity:1"/>
                <stop offset="50%" style="stop-color:#2d3436;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#636e72;stop-opacity:1"/>
            </linearGradient>
            <linearGradient id="carrier-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#00b894;stop-opacity:1"/>
                <stop offset="50%" style="stop-color:#00a085;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#2d3436;stop-opacity:1"/>
            </linearGradient>
            <pattern id="gear-teeth" patternUnits="userSpaceOnUse" width="2" height="2">
                <rect width="2" height="2" fill="#f1f2f6"/>
                <circle cx="1" cy="1" r="0.3" fill="#bbb"/>
            </pattern>
        </defs>
        ''')

        # Ring gear (outer stationary gear)
        ring_thickness = 8 * scale
        parts.append(f'''
        <!-- Ring gear (outer) -->
        <circle cx="{csp[0]:.1f}" cy="{csp[1]:.1f}" r="{rrp:.1f}" 
                fill="none" stroke="url(#ring-gradient)" stroke-width="{ring_thickness:.1f}"/>
        <!-- Ring gear teeth (internal) -->
        <circle cx="{csp[0]:.1f}" cy="{csp[1]:.1f}" r="{rrp - ring_thickness/2:.1f}" 
                fill="none" stroke="#7f8c8d" stroke-width="1" stroke-dasharray="2,1"/>
        ''')

        # Carrier arms connecting planets
        planet_positions = []
        for i in range(num_planets):
            angle = (2 * math.pi * i) / num_planets
            px = csp[0] + planet_orbit_radius * math.cos(angle)
            py = csp[1] + planet_orbit_radius * math.sin(angle)
            planet_positions.append((px, py))

            # Carrier arm from sun to planet
            parts.append(f'''
            <!-- Carrier arm {i+1} -->
            <line x1="{csp[0]:.1f}" y1="{csp[1]:.1f}" x2="{px:.1f}" y2="{py:.1f}" 
                  stroke="url(#carrier-gradient)" stroke-width="4"/>
            <!-- Arm reinforcement -->
            <circle cx="{(csp[0] + px)/2:.1f}" cy="{(csp[1] + py)/2:.1f}" r="2" 
                    fill="url(#carrier-gradient)" stroke="#00a085"/>
            ''')

        # Planet gears with detailed features
        for i, (px, py) in enumerate(planet_positions):
            parts.append(f'''
            <!-- Planet gear {i+1} body -->
            <circle cx="{px:.1f}" cy="{py:.1f}" r="{rpp:.1f}" 
                    fill="url(#planet-gradient)" stroke="#0984e3" stroke-width="1.5"/>
            <!-- Planet gear teeth -->
            <circle cx="{px:.1f}" cy="{py:.1f}" r="{rpp + 1:.1f}" 
                    fill="none" stroke="#74b9ff" stroke-width="0.8" stroke-dasharray="1.5,0.5"/>
            <!-- Planet hub -->
            <circle cx="{px:.1f}" cy="{py:.1f}" r="{rpp*0.4:.1f}" 
                    fill="url(#planet-gradient)" stroke="#2d3436" stroke-width="1"/>
            <!-- Planet bearing -->
            <circle cx="{px:.1f}" cy="{py:.1f}" r="{rpp*0.2:.1f}" 
                    fill="#fff" stroke="#2d3436" stroke-width="0.8"/>
            ''')

        # Sun gear (central drive)
        parts.append(f'''
        <!-- Sun gear body -->
        <circle cx="{csp[0]:.1f}" cy="{csp[1]:.1f}" r="{rsp:.1f}" 
                fill="url(#sun-gradient)" stroke="#e17055" stroke-width="1.8"/>
        <!-- Sun gear teeth -->
        <circle cx="{csp[0]:.1f}" cy="{csp[1]:.1f}" r="{rsp + 1:.1f}" 
                fill="none" stroke="#d63031" stroke-width="0.8" stroke-dasharray="1.5,0.5"/>
        <!-- Sun hub -->
        <circle cx="{csp[0]:.1f}" cy="{csp[1]:.1f}" r="{rsp*0.5:.1f}" 
                fill="url(#sun-gradient)" stroke="#2d3436" stroke-width="1.2"/>
        <!-- Sun shaft -->
        <circle cx="{csp[0]:.1f}" cy="{csp[1]:.1f}" r="{rsp*0.25:.1f}" 
                fill="#fff" stroke="#2d3436" stroke-width="1"/>
        <!-- Keyway in sun shaft -->
        <rect x="{csp[0] - rsp*0.1:.1f}" y="{csp[1] - rsp*0.25:.1f}" 
              width="{rsp*0.2:.1f}" height="{rsp*0.15:.1f}" fill="#7f8c8d"/>
        ''')

        # Direction indicators and mesh points
        parts.append(f'''
        <!-- Rotation direction indicators -->
        <!-- Sun rotation -->
        <path d="M{csp[0] + rsp*0.7:.1f},{csp[1]:.1f} 
                 A{rsp*0.7:.1f},{rsp*0.7:.1f} 0 0,1 {csp[0]:.1f},{csp[1] - rsp*0.7:.1f}" 
              fill="none" stroke="#e74c3c" stroke-width="1.5" marker-end="url(#planetary-arrow)"/>
        
        <defs>
            <marker id="planetary-arrow" markerWidth="6" markerHeight="4" 
                    refX="5" refY="2" orient="auto" markerUnits="strokeWidth">
                <polygon points="0 0, 6 2, 0 4" fill="#e74c3c"/>
            </marker>
        </defs>
        
        <!-- Carrier rotation (slower) -->
        <path d="M{csp[0] + planet_orbit_radius*0.8:.1f},{csp[1]:.1f} 
                 A{planet_orbit_radius*0.8:.1f},{planet_orbit_radius*0.8:.1f} 0 0,0 {csp[0]:.1f},{csp[1] - planet_orbit_radius*0.8:.1f}" 
              fill="none" stroke="#00b894" stroke-width="1.5" stroke-dasharray="3,2" marker-end="url(#carrier-arrow)"/>
        
        <defs>
            <marker id="carrier-arrow" markerWidth="6" markerHeight="4" 
                    refX="5" refY="2" orient="auto" markerUnits="strokeWidth">
                <polygon points="0 0, 6 2, 0 4" fill="#00b894"/>
            </marker>
        </defs>
        ''')

        # Calculate gear ratios
        sun_teeth = max(int(2 * rs / 2), 12)  # Module 2mm
        planet_teeth = max(int(2 * rp / 2), 8)
        ring_teeth = sun_teeth + 2 * planet_teeth

        # Planetary ratio calculation: (Ring + Sun) / Sun when ring is fixed
        planetary_ratio = (ring_teeth + sun_teeth) / sun_teeth if sun_teeth > 0 else 1.0

        # Manufacturing specifications panel
        spec_panel = f'''
        <g class="planetary-manufacturing-specs">
            <rect x="{bounds.width - 170}" y="10" width="160" height="160" 
                  fill="#f8f9fa" stroke="#dee2e6" stroke-width="1" rx="3"/>
            <text x="{bounds.width - 165}" y="25" class="manufacturing-note" font-size="8" font-weight="bold">
                Planetary Gear Manufacturing
            </text>
            
            <!-- Sun gear specs -->
            <text x="{bounds.width - 165}" y="40" class="manufacturing-note" font-size="7" font-weight="bold" fill="#e17055">
                Sun Gear (Input):
            </text>
            <text x="{bounds.width - 165}" y="52" class="manufacturing-note" font-size="6">
                • Diameter: {rs*2:.1f}mm ({sun_teeth}T)
            </text>
            <text x="{bounds.width - 165}" y="62" class="manufacturing-note" font-size="6">
                • Material: Hardened steel
            </text>
            
            <!-- Planet gear specs -->
            <text x="{bounds.width - 165}" y="77" class="manufacturing-note" font-size="7" font-weight="bold" fill="#0984e3">
                Planet Gears ({num_planets}x):
            </text>
            <text x="{bounds.width - 165}" y="89" class="manufacturing-note" font-size="6">
                • Diameter: {rp*2:.1f}mm ({planet_teeth}T)
            </text>
            <text x="{bounds.width - 165}" y="99" class="manufacturing-note" font-size="6">
                • Orbit: {rs + rp:.1f}mm radius
            </text>
            <text x="{bounds.width - 165}" y="109" class="manufacturing-note" font-size="6">
                • Bearings: Needle roller
            </text>
            
            <!-- Ring gear specs -->
            <text x="{bounds.width - 165}" y="124" class="manufacturing-note" font-size="7" font-weight="bold" fill="#636e72">
                Ring Gear (Fixed):
            </text>
            <text x="{bounds.width - 165}" y="136" class="manufacturing-note" font-size="6">
                • Inner Diameter: {rr*2:.1f}mm ({ring_teeth}T)
            </text>
            <text x="{bounds.width - 165}" y="146" class="manufacturing-note" font-size="6">
                • Material: Cast iron housing
            </text>
            
            <!-- System performance -->
            <text x="{bounds.width - 165}" y="161" class="manufacturing-note" font-size="7" font-weight="bold" fill="#00b894">
                Ratio: {planetary_ratio:.1f}:1 Reduction
            </text>
        </g>
        '''

        parts.append(spec_panel)

        # Component labels
        parts.append(f'''
        <text x="{csp[0]:.1f}" y="{csp[1] - rsp - 10:.1f}" 
              class="mechanism-label" font-size="8" text-anchor="middle" font-weight="bold" fill="#e17055">
              Sun Gear (Drive)
        </text>
        <text x="{csp[0]:.1f}" y="{csp[1] + rrp + 15:.1f}" 
              class="mechanism-label" font-size="7" text-anchor="middle" fill="#636e72">
              Ring Gear (Fixed Housing)
        </text>
        <text x="{planet_positions[0][0] + 15:.1f}" y="{planet_positions[0][1]:.1f}" 
              class="mechanism-label" font-size="7" text-anchor="left" fill="#0984e3">
              Planet
        </text>
        <text x="{csp[0] + planet_orbit_radius*0.7:.1f}" y="{csp[1] + planet_orbit_radius*0.7 + 10:.1f}" 
              class="mechanism-label" font-size="7" text-anchor="middle" fill="#00b894">
              Carrier (Output)
        </text>
        ''')

        return ''.join(parts)

    def _generate_cam_from_params_svg(self, mech_data: dict[str, Any], bounds: ScaledBounds) -> str:
        """Enhanced cam mechanism with detailed follower, guide rails, and manufacturing specifications."""
        mm = self._mm_params(mech_data, ['base_radius_mm', 'eccentricity_mm'])
        r = mm.get('base_radius_mm', 25.0)
        e = mm.get('eccentricity_mm', 5.0)
        rod_len = float(mech_data.get('params', {}).get('follower_rod_length', 40.0)) * float(mech_data.get('total_scale_factor', 1.0))

        kp = mech_data.get('key_points', {})
        factor = float(mech_data.get('total_scale_factor', 1.0))
        if 'cam_center' in kp:
            cx, cy = kp['cam_center']
            center = (float(cx) * factor, float(cy) * factor)
        else:
            center = (r + 10.0, r + 10.0)

        # Calculate cam profile bounds
        min_x = center[0] - (r + e)
        max_x = center[0] + (r + e)
        min_y = center[1] - r
        max_y = center[1] + r
        width = max(10.0, max_x - min_x)
        height = max(10.0, max_y - min_y)

        margin = 8.0
        avail_w = max(10.0, bounds.width - 2 * margin)
        avail_h = max(10.0, bounds.height - 2 * margin)
        scale = min(1.0, avail_w / width, avail_h / height)

        def pack_xy(x, y):
            return (x - min_x) * scale + margin, (y - min_y) * scale + margin

        cxp, cyp = pack_xy(*center)
        rxp = (r + e) * scale
        ryp = r * scale
        base_r_scaled = r * scale

        # Manufacturing specifications
        shaft_diameter = max(8.0 * scale, 3.0)  # 8mm cam shaft
        follower_width = max(12.0 * scale, 4.0)  # 12mm follower width
        guide_width = max(16.0 * scale, 5.0)    # 16mm guide rail width
        bearing_diameter = max(6.0 * scale, 2.0)  # 6mm follower bearing

        parts = []

        # Enhanced gradients and patterns for cam mechanism
        parts.append('''
        <defs>
            <radialGradient id="cam-gradient" cx="50%" cy="50%" r="50%">
                <stop offset="0%" style="stop-color:#f8f9fa;stop-opacity:1"/>
                <stop offset="40%" style="stop-color:#e9ecef;stop-opacity:1"/>
                <stop offset="80%" style="stop-color:#dee2e6;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#ced4da;stop-opacity:1"/>
            </radialGradient>
            <linearGradient id="follower-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#74b9ff;stop-opacity:1"/>
                <stop offset="50%" style="stop-color:#0984e3;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#2d3436;stop-opacity:1"/>
            </linearGradient>
            <linearGradient id="guide-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#636e72;stop-opacity:1"/>
                <stop offset="50%" style="stop-color:#2d3436;stop-opacity:1"/>
                <stop offset="100%" style="stop-color:#636e72;stop-opacity:1"/>
            </linearGradient>
            <pattern id="cam-surface" patternUnits="userSpaceOnUse" width="3" height="3">
                <rect width="3" height="3" fill="#f1f2f6"/>
                <circle cx="1.5" cy="1.5" r="0.5" fill="#ddd"/>
            </pattern>
        </defs>
        ''')

        # Main cam body with enhanced egg-shaped profile
        cam_points = []
        num_points = 36  # More points for smoother curve

        for i in range(num_points + 1):
            angle = (2 * math.pi * i) / num_points
            # Create egg-shaped profile with eccentricity
            radius_at_angle = r + e * math.cos(2 * angle)  # Egg shape
            x = cxp + radius_at_angle * scale * math.cos(angle)
            y = cyp + radius_at_angle * scale * math.sin(angle)
            cam_points.append(f"{x:.1f},{y:.1f}")

        cam_path = "M " + " L ".join(cam_points) + " Z"

        parts.append(f'''
        <!-- Enhanced cam body with egg profile -->
        <path d="{cam_path}" fill="url(#cam-gradient)" stroke="#2c3e50" stroke-width="1.8"/>
        <path d="{cam_path}" fill="url(#cam-surface)" opacity="0.3"/>
        ''')

        # Cam center shaft with keyway
        keyway_width = shaft_diameter * 0.25
        parts.append(f'''
        <!-- Cam center shaft -->
        <circle cx="{cxp:.1f}" cy="{cyp:.1f}" r="{shaft_diameter/2:.1f}" 
                fill="url(#guide-gradient)" stroke="#2c3e50" stroke-width="1.2"/>
        <!-- Keyway in shaft -->
        <rect x="{cxp - keyway_width/2:.1f}" y="{cyp - shaft_diameter/2:.1f}" 
              width="{keyway_width:.1f}" height="{shaft_diameter*0.4:.1f}" fill="#34495e"/>
        ''')

        # Enhanced follower system with guide rails
        follower_y_top = cyp - (base_r_scaled + rod_len)
        follower_y_contact = cyp - base_r_scaled - e * scale  # Contact point on cam

        # Guide rails (vertical supports)
        guide_left = cxp - guide_width/2
        guide_right = cxp + guide_width/2

        parts.append(f'''
        <!-- Left guide rail -->
        <rect x="{guide_left - 3:.1f}" y="{follower_y_top - 10:.1f}" 
              width="6" height="{cyp - follower_y_top + base_r_scaled + 20:.1f}" 
              fill="url(#guide-gradient)" stroke="#2c3436" stroke-width="1"/>
        <!-- Right guide rail -->
        <rect x="{guide_right - 3:.1f}" y="{follower_y_top - 10:.1f}" 
              width="6" height="{cyp - follower_y_top + base_r_scaled + 20:.1f}" 
              fill="url(#guide-gradient)" stroke="#2c3436" stroke-width="1"/>
        ''')

        # Follower assembly with detailed components
        parts.append(f'''
        <!-- Follower rod -->
        <rect x="{cxp - 2:.1f}" y="{follower_y_contact:.1f}" 
              width="4" height="{follower_y_top - follower_y_contact:.1f}" 
              fill="url(#follower-gradient)" stroke="#0984e3" stroke-width="1"/>
        
        <!-- Follower contact bearing -->
        <circle cx="{cxp:.1f}" cy="{follower_y_contact:.1f}" r="{bearing_diameter/2:.1f}" 
                fill="#e17055" stroke="#d63031" stroke-width="1"/>
        
        <!-- Follower block (top) -->
        <rect x="{cxp - follower_width/2:.1f}" y="{follower_y_top - 6:.1f}" 
              width="{follower_width:.1f}" height="12" 
              fill="url(#follower-gradient)" stroke="#0984e3" stroke-width="1.2" rx="2"/>
        
        <!-- Follower attachment point -->
        <circle cx="{cxp:.1f}" cy="{follower_y_top:.1f}" r="3" 
                fill="#fff" stroke="#2d3436" stroke-width="1"/>
        ''')

        # Motion path indication
        max_lift = e * scale
        parts.append(f'''
        <!-- Motion path indicator -->
        <line x1="{cxp - 15:.1f}" y1="{follower_y_contact:.1f}" 
              x2="{cxp - 15:.1f}" y2="{follower_y_contact - max_lift:.1f}" 
              stroke="#e74c3c" stroke-width="2" stroke-dasharray="4,2"/>
        <text x="{cxp - 18:.1f}" y="{(follower_y_contact + follower_y_contact - max_lift)/2:.1f}" 
              class="dimension-text" font-size="6" text-anchor="middle" fill="#e74c3c" 
              transform="rotate(-90, {cxp - 18:.1f}, {(follower_y_contact + follower_y_contact - max_lift)/2:.1f})">
              Lift: {e:.1f}mm
        </text>
        ''')

        # Direction of rotation arrow
        arrow_radius = base_r_scaled + 10
        parts.append(f'''
        <!-- Rotation direction -->
        <path d="M{cxp + arrow_radius:.1f},{cyp:.1f} 
                 A{arrow_radius:.1f},{arrow_radius:.1f} 0 0,1 {cxp:.1f},{cyp - arrow_radius:.1f}" 
              fill="none" stroke="#e74c3c" stroke-width="2" marker-end="url(#cam-arrowhead)"/>
        
        <defs>
            <marker id="cam-arrowhead" markerWidth="8" markerHeight="6" 
                    refX="7" refY="3" orient="auto" markerUnits="strokeWidth">
                <polygon points="0 0, 8 3, 0 6" fill="#e74c3c"/>
            </marker>
        </defs>
        ''')

        # Manufacturing specifications panel
        lift_angle = math.degrees(math.acos((r - e) / (r + e))) if r + e > 0 else 0

        spec_panel = f'''
        <g class="cam-manufacturing-specs">
            <rect x="{bounds.width - 160}" y="10" width="150" height="130" 
                  fill="#f8f9fa" stroke="#dee2e6" stroke-width="1" rx="3"/>
            <text x="{bounds.width - 155}" y="25" class="manufacturing-note" font-size="8" font-weight="bold">
                Cam Manufacturing Specifications
            </text>
            
            <!-- Cam specs -->
            <text x="{bounds.width - 155}" y="40" class="manufacturing-note" font-size="7" font-weight="bold" fill="#2c3e50">
                Cam Profile:
            </text>
            <text x="{bounds.width - 155}" y="52" class="manufacturing-note" font-size="6">
                • Base Radius: {r:.1f}mm
            </text>
            <text x="{bounds.width - 155}" y="62" class="manufacturing-note" font-size="6">
                • Eccentricity: {e:.1f}mm (Lift)
            </text>
            <text x="{bounds.width - 155}" y="72" class="manufacturing-note" font-size="6">
                • Shaft: 8mm steel with keyway
            </text>
            
            <!-- Follower specs -->
            <text x="{bounds.width - 155}" y="87" class="manufacturing-note" font-size="7" font-weight="bold" fill="#0984e3">
                Follower System:
            </text>
            <text x="{bounds.width - 155}" y="99" class="manufacturing-note" font-size="6">
                • Rod: 4mm steel, {rod_len:.0f}mm length
            </text>
            <text x="{bounds.width - 155}" y="109" class="manufacturing-note" font-size="6">
                • Bearing: 6mm roller bearing
            </text>
            <text x="{bounds.width - 155}" y="119" class="manufacturing-note" font-size="6">
                • Guides: Hardened steel rails
            </text>
            
            <!-- Performance -->
            <text x="{bounds.width - 155}" y="134" class="manufacturing-note" font-size="7" font-weight="bold" fill="#e74c3c">
                Performance: {e:.1f}mm lift
            </text>
        </g>
        '''

        parts.append(spec_panel)

        # Component labels
        parts.append(f'''
        <text x="{cxp:.1f}" y="{cyp - base_r_scaled - 25:.1f}" 
              class="mechanism-label" font-size="8" text-anchor="middle" font-weight="bold">
              Cam Profile (Egg-shaped)
        </text>
        <text x="{cxp + 25:.1f}" y="{follower_y_top - 5:.1f}" 
              class="mechanism-label" font-size="7" text-anchor="left" fill="#0984e3">
              Follower Assembly
        </text>
        ''')

        return ''.join(parts)

    def _generate_parameter_annotations(self, mech_data: dict[str, Any], bounds: ScaledBounds, unit_system: str = "metric") -> str:
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
            real_world_params = mech_data.get('real_world_params', {})
            mechanism_type = mech_data.get('type', 'unknown')

            # Also try to get parametric editing results if available
            params = mech_data.get('params', {})
            total_scale_factor = mech_data.get('total_scale_factor', 1.0)

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
                        return f"{inches:.2f}\""
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
            annotations.append(f'<rect x="{annotation_x - 6}" y="{annotation_y_start - 16}" '
                               f'width="180" height="{panel_height}" fill="#ffffff" stroke="#e5e5e5" '
                               f'stroke-width="0.5" rx="3"/>')

            unit_label = "Imperial" if unit_system == "imperial" else "Metric"
            annotations.append(f'<text x="{annotation_x}\" y="{annotation_y_start}" '
                             f'class="parameter-header" font-size="9" font-weight="bold" fill="#333">'
                             f'Real-World Dimensions ({unit_label}):</text>')

            y_offset = annotation_y_start + line_height + 2

            # Add mechanism-specific parameter annotations with enhanced display
            if mechanism_type == "4_bar_linkage":
                link_params = ['l1_mm', 'l2_mm', 'l3_mm', 'l4_mm']
                link_names = ['Ground Link', 'Crank', 'Coupler', 'Rocker']

                for i, param in enumerate(link_params):
                    if param in real_world_params:
                        value = real_world_params[param]
                        formatted_value = format_dimension(value)
                        link_name = link_names[i]

                        annotations.append(f'<text x="{annotation_x}\" y="{y_offset}" '
                                         f'class="parameter-text" font-size="8" fill="#222">'
                                         f'{link_name}: {formatted_value}</text>')
                        y_offset += line_height

                # Add coupler point if available
                if 'coupler_point_x_mm' in real_world_params and 'coupler_point_y_mm' in real_world_params:
                    cp_x = format_dimension(real_world_params['coupler_point_x_mm'])
                    cp_y = format_dimension(real_world_params['coupler_point_y_mm'])
                    annotations.append(f'<text x="{annotation_x}\" y="{y_offset}" '
                                     f'class="parameter-text" font-size="7" fill="#666">'
                                     f'Coupler Point: ({cp_x}, {cp_y})</text>')
                    y_offset += line_height

            elif mechanism_type == "cam":
                cam_params = ['base_radius_mm', 'eccentricity_mm']
                cam_names = ['Base Radius', 'Eccentricity']

                for i, param in enumerate(cam_params):
                    if param in real_world_params:
                        value = real_world_params[param]
                        formatted_value = format_dimension(value)
                        param_name = cam_names[i]

                        annotations.append(f'<text x="{annotation_x}\" y="{y_offset}" '
                                         f'class="parameter-text" font-size="8" fill="#222">'
                                         f'{param_name}: {formatted_value}</text>')
                        y_offset += line_height

                # Add calculated values
                if 'base_radius_mm' in real_world_params and 'eccentricity_mm' in real_world_params:
                    max_radius = real_world_params['base_radius_mm'] + real_world_params['eccentricity_mm']
                    min_radius = real_world_params['base_radius_mm'] - real_world_params['eccentricity_mm']

                    annotations.append(f'<text x="{annotation_x}\" y="{y_offset}" '
                                     f'class="parameter-text" font-size="7" fill="#666">'
                                     f'Max Radius: {format_dimension(max_radius)}</text>')
                    y_offset += line_height

                    annotations.append(f'<text x="{annotation_x}\" y="{y_offset}" '
                                     f'class="parameter-text" font-size="7" fill="#666">'
                                     f'Min Radius: {format_dimension(min_radius)}</text>')
                    y_offset += line_height

            elif mechanism_type in ["gear", "planetary_gear"]:
                gear_params = ['r1_mm', 'r2_mm', 'r_sun_mm', 'r_planet_mm', 'arm_length_mm', 'distance_mm']
                gear_names = ['Gear 1 Radius', 'Gear 2 Radius', 'Sun Radius', 'Planet Radius', 'Arm Length', 'Center Distance']

                for i, param in enumerate(gear_params):
                    if param in real_world_params:
                        value = real_world_params[param]
                        formatted_value = format_dimension(value)
                        param_name = gear_names[i]

                        annotations.append(f'<text x="{annotation_x}\" y="{y_offset}" '
                                         f'class="parameter-text" font-size="8" fill="#222">'
                                         f'{param_name}: {formatted_value}</text>')
                        y_offset += line_height

                # Add gear ratio if applicable
                if mechanism_type == "gear" and 'r1_mm' in real_world_params and 'r2_mm' in real_world_params:
                    r1 = real_world_params['r1_mm']
                    r2 = real_world_params['r2_mm']
                    if r1 > 0:
                        ratio = r2 / r1
                        annotations.append(f'<text x="{annotation_x}\" y="{y_offset}" '
                                         f'class="parameter-text" font-size="7" fill="#666">'
                                         f'Gear Ratio: {ratio:.2f}:1</text>')
                        y_offset += line_height

            # Add scale factor information
            if 'scale_factor_used' in real_world_params:
                scale_factor = real_world_params['scale_factor_used']
                annotations.append(f'<text x="{annotation_x}\" y="{y_offset + 8}" '
                                 f'class="scale-info" font-size="6" fill="#666" font-style="italic">'
                                 f'Scale Factor: {scale_factor:.3f} mm/px</text>')

            # Add unit system note
            annotations.append(f'<text x="{annotation_x}\" y="{annotation_y_start + panel_height - 8}" '
                             f'class="unit-info" font-size="6" fill="#888" font-style="italic">'
                             f'Units: {unit_label}</text>')

            annotations.append('</g>')

        except Exception as e:
            self.logger.warning(f"Error generating parameter annotations: {e}")
            # Return empty string if annotation generation fails
            return ""

        return '\n'.join(annotations)

    def _get_param_count_for_mechanism(self, mechanism_type: str, real_world_params: dict[str, Any]) -> int:
        """Count the number of parameters that will be displayed for a mechanism type."""
        if mechanism_type == "4_bar_linkage":
            count = 4  # l1, l2, l3, l4
            if 'coupler_point_x_mm' in real_world_params:
                count += 1
            return count
        elif mechanism_type == "cam":
            count = 2  # base_radius, eccentricity
            if 'base_radius_mm' in real_world_params and 'eccentricity_mm' in real_world_params:
                count += 2  # max_radius, min_radius
            return count
        elif mechanism_type in ["gear", "planetary_gear"]:
            count = len([p for p in ['r1_mm', 'r2_mm', 'r_sun_mm', 'r_planet_mm', 'arm_length_mm', 'distance_mm']
                        if p in real_world_params])
            if mechanism_type == "gear" and 'r1_mm' in real_world_params and 'r2_mm' in real_world_params:
                count += 1  # gear ratio
            return count
        return 3  # default

    def _calculate_real_world_params_from_params(self, params: dict[str, Any], scale_factor: float, mech_type: str) -> dict[str, Any]:
        """Calculate real-world parameters from current mechanism params and scale factor."""
        real_world_params = {}

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

            elif mech_type in ["gear", "planetary_gear"]:
                for param_name in ["r1", "r2", "r_sun", "r_planet", "arm_length", "distance", "tracking_radius"]:
                    if param_name in params:
                        real_world_params[f"{param_name}_mm"] = params[param_name] * scale_factor

            real_world_params["scale_factor_used"] = scale_factor
            real_world_params["mechanism_type"] = mech_type

        except Exception as e:
            self.logger.warning(f"Error calculating real-world params for {mech_type}: {e}")
            real_world_params = {"scale_factor_used": scale_factor, "mechanism_type": mech_type}

        return real_world_params

    def _generate_standard_mechanism_svg(self, mech_id: str, mechanism_type: str, bounds: ScaledBounds) -> str:
        """Generate standard mechanism representation"""

        # Different shapes for different mechanism types
        if mechanism_type == 'gear':
            # Gear with teeth
            return self._generate_gear_svg(bounds)
        elif mechanism_type == '4_bar_linkage':  # Fixed: GUI creates '4_bar_linkage' not 'linkage'
            # Link bar
            return self._generate_linkage_svg(bounds)
        elif mechanism_type == 'cam':
            # Cam profile
            return self._generate_cam_svg(bounds)
        elif mechanism_type == 'pulley':
            # Circular pulley
            return self._generate_pulley_svg(bounds)
        elif mechanism_type == 'belt':
            # Belt path
            return self._generate_belt_svg(bounds)
        elif mechanism_type == 'spring':
            # Spring coils
            return self._generate_spring_svg(bounds)
        elif mechanism_type == 'damper':
            # Damper cylinder
            return self._generate_damper_svg(bounds)
        else:
            # Generic mechanism box
            return self._generate_generic_mechanism_svg(mech_id, mechanism_type, bounds)

    def _generate_gear_svg(self, bounds: ScaledBounds) -> str:
        """Generate enhanced standard gear representation with manufacturing details"""
        cx, cy = bounds.width/2, bounds.height/2
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
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius+2:.1f}"
                fill="none" stroke="#495057" stroke-width="1.2" stroke-dasharray="2,1"/>
        
        <!-- Hub -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{hub_radius:.1f}"
                fill="url(#standard-gear-gradient)" stroke="#343a40" stroke-width="1.5"/>
        
        <!-- Center shaft hole -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{shaft_radius:.1f}"
                fill="#fff" stroke="#343a40" stroke-width="1"/>
                
        <!-- Keyway -->
        <rect x="{cx - keyway_width/2:.1f}" y="{cy - shaft_radius:.1f}" 
              width="{keyway_width:.1f}" height="{shaft_radius*0.6:.1f}" fill="#6c757d"/>
        
        <!-- Manufacturing specifications -->
        <text x="{cx:.1f}" y="{cy + radius + 15:.1f}" class="manufacturing-note" 
              font-size="7" text-anchor="middle" fill="#495057">
              Standard Gear | Steel | 6mm Shaft
        </text>
        '''

    def _generate_linkage_svg(self, bounds: ScaledBounds) -> str:
        """Generate enhanced linkage representation with metallic appearance"""
        link_height = 12
        y_center = bounds.height/2

        # Enhanced linkage with gradient and pattern
        return f'''
        <!-- Main linkage bar with gradient -->
        <rect x="5" y="{y_center-link_height/2:.1f}" width="{bounds.width-10:.1f}" height="{link_height}"
              fill="url(#gradient-4_bar_linkage)" stroke="#34495e" stroke-width="1.5" rx="2"/>
        
        <!-- Pattern overlay for texture -->
        <rect x="5" y="{y_center-link_height/2:.1f}" width="{bounds.width-10:.1f}" height="{link_height}"
              fill="url(#pattern-4_bar_linkage)" opacity="0.3" rx="2"/>
        
        <!-- Left joint with enhanced detail -->
        <circle cx="10" cy="{y_center:.1f}" r="5"
                fill="url(#gradient-4_bar_linkage)" stroke="#2c3e50" stroke-width="1.2"/>
        <circle cx="10" cy="{y_center:.1f}" r="2"
                fill="#fff" stroke="#555" stroke-width="0.5"/>
        
        <!-- Right joint with enhanced detail -->
        <circle cx="{bounds.width-10:.1f}" cy="{y_center:.1f}" r="5"
                fill="url(#gradient-4_bar_linkage)" stroke="#2c3e50" stroke-width="1.2"/>
        <circle cx="{bounds.width-10:.1f}" cy="{y_center:.1f}" r="2"
                fill="#fff" stroke="#555" stroke-width="0.5"/>
        
        <!-- Center reinforcement -->
        <rect x="{bounds.width/2-10:.1f}" y="{y_center-2:.1f}" width="20" height="4"
              fill="none" stroke="#7f8c8d" stroke-width="0.8" stroke-dasharray="2,2"/>
        '''

    def _generate_cam_svg(self, bounds: ScaledBounds) -> str:
        """Generate enhanced standard cam representation with follower details"""
        cx, cy = bounds.width/2, bounds.height/2
        rx, ry = bounds.width/2-5, bounds.height/2-5

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
        cx, cy = bounds.width/2, bounds.height/2
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
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius - groove_width/2:.1f}"
                fill="none" stroke="#bf360c" stroke-width="1" stroke-dasharray="2,2"/>
                
        <!-- Hub -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{hub_radius:.1f}"
                fill="url(#pulley-gradient)" stroke="#d84315" stroke-width="1.5"/>
        
        <!-- Center mounting -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{hub_radius*0.3:.1f}"
                fill="#fff" stroke="#bf360c" stroke-width="1"/>
        
        <!-- Mounting bolts -->
        <circle cx="{cx - hub_radius*0.6:.1f}" cy="{cy:.1f}" r="1.5"
                fill="#424242" stroke="#212121" stroke-width="0.5"/>
        <circle cx="{cx + hub_radius*0.6:.1f}" cy="{cy:.1f}" r="1.5"
                fill="#424242" stroke="#212121" stroke-width="0.5"/>
        <circle cx="{cx:.1f}" cy="{cy - hub_radius*0.6:.1f}" r="1.5"
                fill="#424242" stroke="#212121" stroke-width="0.5"/>
        <circle cx="{cx:.1f}" cy="{cy + hub_radius*0.6:.1f}" r="1.5"
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
        <rect x="5" y="{bounds.height/2-3:.1f}" width="{bounds.width-10:.1f}" height="6"
              fill="none" stroke="black" stroke-width="1" stroke-dasharray="5,3"/>
        '''

    def _generate_spring_svg(self, bounds: ScaledBounds) -> str:
        """Generate standard spring representation"""
        coils = []
        cx = bounds.width / 2
        coil_height = bounds.height / 8

        for i in range(6):
            y = 10 + i * coil_height
            coils.append(f'<ellipse cx="{cx:.1f}" cy="{y:.1f}" rx="8" ry="{coil_height/2:.1f}" '
                        f'fill="none" stroke="black" stroke-width="1"/>')

        return '\n'.join(coils)

    def _generate_damper_svg(self, bounds: ScaledBounds) -> str:
        """Generate standard damper representation"""
        cx = bounds.width / 2

        return f'''
        <rect x="{cx-8:.1f}" y="10" width="16" height="{bounds.height-20:.1f}"
              fill="none" stroke="black" stroke-width="1.5"/>
        <line x1="{cx:.1f}" y1="5" x2="{cx:.1f}" y2="15" stroke="black" stroke-width="2"/>
        <line x1="{cx:.1f}" y1="{bounds.height-15:.1f}" x2="{cx:.1f}" y2="{bounds.height-5:.1f}"
              stroke="black" stroke-width="2"/>
        '''

    def _generate_generic_mechanism_svg(self, mech_id: str, mechanism_type: str, bounds: ScaledBounds) -> str:
        """Generate generic mechanism placeholder"""
        return f'''
        <rect x="2" y="2" width="{bounds.width-4:.1f}" height="{bounds.height-4:.1f}"
              fill="#f8f8f8" stroke="black" stroke-width="1" stroke-dasharray="3,3"/>
        <text x="{bounds.width/2:.1f}" y="{bounds.height/2-5:.1f}"
              class="mechanism-label" text-anchor="middle" font-size="10">
              {mechanism_type.upper()}
        </text>
        <text x="{bounds.width/2:.1f}" y="{bounds.height/2+8:.1f}"
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

    def optimize_blueprint_layout(self, part_items: list[Any], mechanism_layers: dict[str, Any], unit_system: str = "metric") -> tuple[list[LayoutItem], float, float]:
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
            self.logger.info(f"Processing {len(mechanism_layers)} mechanisms with unit system: {unit_system}...")
            for mech_id, mech_data in mechanism_layers.items():
                try:
                    layout_item = self.mechanism_processor.process_mechanism(mech_id, mech_data, unit_system)
                    if layout_item:
                        layout_items.append(layout_item)
                        self.logger.debug(f"Added mechanism layout item: {mech_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to process mechanism {mech_id}: {e}")

        # Optimize layout positioning
        if layout_items:
            self.logger.info(f"Optimizing layout for {len(layout_items)} items...")
            optimized_items, total_width, total_height = self.layout_manager.optimize_layout(
                layout_items,
                target_page_width_mm=800,
                target_page_height_mm=600
            )
            return optimized_items, total_width, total_height
        else:
            self.logger.warning("No layout items to optimize")
            return [], 0.0, 0.0

    def _process_character_parts(self, part_items: list[Any]) -> list[LayoutItem]:
        """Process character parts with TOTAL CHARACTER HEIGHT scaling (not individual parts)"""
        from automataii.generation.contour_extractor import PNGBlueprintProcessor

        layout_items = []

        # CRITICAL FIX: Calculate scale based on TOTAL CHARACTER HEIGHT, not individual parts
        total_character_height = 0
        total_character_width = 0
        all_contours = []

        # First pass: collect all contours and calculate total character bounds
        for item in part_items:
            try:
                # Validate item before processing
                if not item or not hasattr(item, 'part_info'):
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

            self.logger.info(f"[CHARACTER] Total character dimensions: {total_character_width}x{total_character_height} pixels")
            self.logger.info(f"[CHARACTER] Target: {self.scale_normalizer.target_height_mm}mm character height")

            # Scale factor based on TOTAL CHARACTER HEIGHT
            scale_factor = self.scale_normalizer.calculate_scale_factor(total_character_height)

            # Calculate actual character dimensions after scaling
            actual_character_height = total_character_height * scale_factor
            actual_character_width = total_character_width * scale_factor

            self.logger.info(f"[CHARACTER] Scale factor: {scale_factor:.3f} mm/pixel")
            self.logger.info(f"[CHARACTER] Final character: {actual_character_width:.1f}x{actual_character_height:.1f}mm")
        else:
            scale_factor = 0.36  # Default scale
            self.logger.warning("[CHARACTER] No contours found, using default scale")

        # Second pass: process each part with the unified character scale
        for item, contour in all_contours:
            # Normalize contour scale using the TOTAL CHARACTER scale
            scaled_contour = self.scale_normalizer.normalize_contour(contour, scale_factor)

            # Get part name
            part_name = getattr(item.part_info, 'name', 'Unknown Part')

            # Create scaled bounds
            x, y, w, h = scaled_contour.bounding_rect
            bounds = ScaledBounds(x=0, y=0, width=w, height=h)  # Position will be set by layout manager

            # Generate scaled SVG content
            svg_content = self._generate_scaled_part_svg(scaled_contour, part_name, bounds)

            # Create layout item
            layout_item = LayoutItem(
                name=part_name,
                bounds=bounds,
                svg_content=svg_content,
                item_type='part',
                priority=3  # Parts get highest priority for placement
            )

            layout_items.append(layout_item)

            # Enhanced logging showing part size relative to character
            part_height_percent = (h / actual_character_height) * 100 if actual_character_height > 0 else 0
            self.logger.info(f"[CHARACTER] Part '{part_name}': {w:.1f}×{h:.1f}mm ({part_height_percent:.1f}% of character height)")

        return layout_items


    def _generate_scaled_part_svg(self, scaled_contour: Any, part_name: str, bounds: ScaledBounds) -> str:
        """Generate SVG content for scaled part with texture image clipped to contour."""

        # Offset the path so top-left of bounding rect is at (0,0)
        try:
            from automataii.generation.contour_extractor import AdvancedContourExtractor
            extractor = AdvancedContourExtractor()
            x, y, w, h = scaled_contour.bounding_rect
            offset_path = extractor._apply_offset_to_path(scaled_contour.svg_path, -float(x), -float(y))
        except Exception:
            # Fallback to original path and zeroed rect if bounding data missing
            offset_path = scaled_contour.svg_path
            x, y, w, h = 0.0, 0.0, bounds.width, bounds.height

        # Prepare image data URI if available
        image_href = None
        try:
            if hasattr(scaled_contour, 'source_image_path') and scaled_contour.source_image_path:
                import base64
                with open(scaled_contour.source_image_path, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode('ascii')
                    # Infer mime type simply by extension
                    ext = str(scaled_contour.source_image_path).lower()
                    mime = 'image/png' if ext.endswith('.png') else 'image/jpeg' if ext.endswith(('.jpg', '.jpeg')) else 'image/*'
                    image_href = f"data:{mime};base64,{b64}"
        except Exception:
            image_href = None

        # Unique clipPath id - store for later defs collection
        import uuid as _uuid
        clip_id = f"clip-{_uuid.uuid4().hex[:8]}"

        # Store clip path definition for collection by parent
        clip_def = f'<clipPath id="{clip_id}"><path d="{offset_path}" /></clipPath>'

        # Build SVG group with image and outline (no nested defs)
        parts = []
        parts.append(f'<g class="scaled-part" data-name="{part_name}" data-clip-def="{clip_def.replace('"', '&quot;')}">')

        # Embedded texture image clipped to contour
        if image_href:
            # Use both href and xlink:href for maximum compatibility
            parts.append(
                f'  <image href="{image_href}" xlink:href="{image_href}" x="0" y="0" '
                f'width="{w:.1f}" height="{h:.1f}" preserveAspectRatio="none" clip-path="url(#{clip_id})" />'
            )
            try:
                self.logger.debug(f"[BLUEPRINT] Embedded texture for part '{part_name}' from {getattr(scaled_contour, 'source_image_path', 'unknown')}")
            except Exception:
                pass
        else:
            try:
                self.logger.warning(f"[BLUEPRINT] No texture found for part '{part_name}' (no image href)")
            except Exception:
                pass

        # Outline and cutting path on top
        parts.append(f'  <path d="{offset_path}" class="part-outline"/>')
        parts.append(f'  <path d="{offset_path}" class="cutting-path"/>')

        # Part label
        parts.append(
            f'  <text x="{w/2:.1f}" y="-8" class="part-label" text-anchor="middle">{part_name}</text>'
        )

        # Dimensions and manufacturing notes
        parts.append('  <g class="dimensions">')
        parts.append(
            f'    <line x1="0" y1="{h + 12:.1f}" x2="{w:.1f}" y2="{h + 12:.1f}" class="dimension-line"/>'
        )
        parts.append(
            f'    <text x="{w/2:.1f}" y="{h + 22:.1f}" class="dimension-text" text-anchor="middle">{w:.0f}mm</text>'
        )
        parts.append(
            f'    <line x1="-12" y1="0" x2="-12" y2="{h:.1f}" class="dimension-line"/>'
        )
        parts.append(
            f'    <text x="-15" y="{h/2:.1f}" class="dimension-text" text-anchor="middle" '
            f'transform="rotate(-90, -15, {h/2:.1f})">{h:.0f}mm</text>'
        )
        parts.append('  </g>')
        parts.append(f'  <text x="0" y="{h + 40:.1f}" class="manufacturing-note" font-size="6">Scaled Area: {scaled_contour.area:.0f}mm² | Perimeter: {scaled_contour.perimeter:.0f}mm</text>')
        parts.append('</g>')

        return '\n'.join(parts)
