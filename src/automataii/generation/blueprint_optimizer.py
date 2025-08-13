#!/usr/bin/env python3
"""
Blueprint Layout Optimizer for Professional Manufacturing Blueprints
Implements intelligent layout, scale normalization, and mechanism support

Author: Legendary CS Research Collective
Inspired by: Knuth's TeX Layout + Catmull's Graphics + Sutherland's Systems
"""

import logging
import math
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
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

    def center(self) -> Tuple[float, float]:
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
                setattr(scaled_contour, 'source_image_path', getattr(contour, 'source_image_path'))
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

    def get_scaled_bounds(self, original_bounds: Tuple[int, int, int, int], scale_factor: float) -> ScaledBounds:
        """Convert pixel bounds to scaled real-world bounds"""
        x, y, w, h = original_bounds
        return ScaledBounds(
            x=x * scale_factor,
            y=y * scale_factor,
            width=w * scale_factor,
            height=h * scale_factor
        )


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

    def calculate_optimal_layout(self, items: List[LayoutItem]) -> List[LayoutItem]:
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

    def _has_overlaps(self, bounds: ScaledBounds, placed_items: List[LayoutItem]) -> bool:
        """Check if bounds overlap with any placed items"""
        for item in placed_items:
            if bounds.overlaps_with(item.bounds, self.padding_mm):
                return True
        return False

    def calculate_total_dimensions(self, items: List[LayoutItem]) -> Tuple[float, float]:
        """Calculate total blueprint dimensions from placed items"""
        if not items:
            return (self.page_width_mm, 400.0)  # Default size

        max_x = max(item.bounds.x + item.bounds.width for item in items)
        max_y = max(item.bounds.y + item.bounds.height for item in items)

        total_width = max_x + self.padding_mm
        total_height = max_y + self.padding_mm

        return (total_width, total_height)


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

    def process_mechanism(self, mech_id: str, mech_data: Dict[str, Any]) -> Optional[LayoutItem]:
        """
        Process a mechanism into a layout item with proper scaling

        Args:
            mech_id: Mechanism identifier
            mech_data: Mechanism data dictionary

        Returns:
            LayoutItem for the mechanism or None if processing fails
        """
        try:
            mechanism_type = mech_data.get('type', 'unknown')  # Fixed: GUI uses 'type' not 'mechanism_type'

            # Enhanced logging for debugging dimension flow
            self.logger.info(f"[MECHANISM] Processing {mech_id} (type: {mechanism_type})")
            self.logger.info(f"[MECHANISM] Input data keys: {list(mech_data.keys())}")
            
            # Log raw parameters
            raw_params = mech_data.get('params', {})
            self.logger.info(f"[MECHANISM] Raw params: {raw_params}")

            # CRITICAL: Use real-world scaling if available from screen calculations
            if 'real_world_params' in mech_data and 'total_scale_factor' in mech_data:
                # Use actual screen-to-blueprint scaling
                real_world_params = mech_data['real_world_params']
                scale_factor = mech_data['total_scale_factor']

                self.logger.info(f"[MECHANISM] Using screen-calculated scaling:")
                self.logger.info(f"[MECHANISM]   Scale factor: {scale_factor:.3f}")
                self.logger.info(f"[MECHANISM]   Real-world params: {real_world_params}")

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
                    self.logger.warning(f"[MECHANISM]   Missing: real_world_params")
                if 'total_scale_factor' not in mech_data:
                    self.logger.warning(f"[MECHANISM]   Missing: total_scale_factor")
                
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

            # Generate mechanism SVG content with enhanced scaling information
            svg_content = self._generate_mechanism_svg(mech_id, mech_data, bounds)

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

    def _calculate_mechanism_dimensions_from_params(self, real_world_params: Dict[str, Any], mechanism_type: str) -> Tuple[float, float]:
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

    def _generate_mechanism_svg(self, mech_id: str, mech_data: Dict[str, Any], bounds: ScaledBounds) -> str:
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

        # Generate real-world parameter annotations
        param_annotations = self._generate_parameter_annotations(mech_data, bounds)

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

            <!-- Non-overlapping text labels with generous spacing -->
            <g class="mechanism-labels">
                <!-- Part name with adequate spacing -->
                <text x="{bounds.width/2:.1f}" y="{bounds.height + 25:.1f}"
                      class="mechanism-label" text-anchor="middle" font-size="10" font-weight="bold">
                    {mechanism_name}
                </text>

                <!-- Mechanism type with clear spacing -->
                <text x="{bounds.width/2:.1f}" y="{bounds.height + 42:.1f}"
                      class="dimension-text" text-anchor="middle" font-size="8">
                    Type: {mechanism_type.replace('_', '-').title()}
                </text>

                <!-- Real-world dimensions from screen scaling -->
                <text x="{bounds.width/2:.1f}" y="{bounds.height + 56:.1f}"
                      class="dimension-text" text-anchor="middle" font-size="7" fill="#666">
                    Size: {bounds.width:.0f}×{bounds.height:.0f}mm (Screen-Scaled)
                </text>

                <!-- Mechanism ID for assembly reference -->
                <text x="{bounds.width/2:.1f}" y="{bounds.height + 70:.1f}"
                      class="dimension-text" text-anchor="middle" font-size="7" fill="#666">
                    ID: {mech_id}
                </text>
            </g>

            <!-- Real-world parameter annotations -->
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

    def _generate_4bar_from_keypoints_svg(self, mech_data: Dict[str, Any], bounds: ScaledBounds) -> str:
        """Clone on-screen 4-bar geometry using key_points for crystal-clear bars and labels."""
        kp = mech_data.get('key_points', {})
        factor = float(mech_data.get('total_scale_factor', 1.0))

        required = ["ground_pivot_1", "ground_pivot_2", "crank_end", "rocker_end"]
        if not all(name in kp for name in required):
            return self._generate_standard_mechanism_svg(mech_data.get('id', 'mech'), '4_bar_linkage', bounds)

        def to_mm(name: str) -> Tuple[float, float]:
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

        # Uniform scale to fit drawing if oversized; do not upscale to preserve readable thickness
        scale = min(1.0, avail_w / width if width > 0 else 1.0, avail_h / height if height > 0 else 1.0)

        def pack(pt: Tuple[float, float]) -> Tuple[float, float]:
            px = (pt[0] - min_x) * scale + margin
            py = (pt[1] - min_y) * scale + margin
            return px, py

        O1p = pack(O1)
        O2p = pack(O2)
        Ap = pack(A)
        Bp = pack(B)

        # Colors for clarity
        color_ground = "black"
        color_crank = "#e74c3c"    # red
        color_coupler = "#27ae60"  # green
        color_rocker = "#2980b9"   # blue

        def line(x1, y1, x2, y2, color, w=1.5):
            return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{w}"/>'

        def circ(x, y, r=3, color="black"):
            return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="none" stroke="{color}" stroke-width="1.2"/>'

        def label(x, y, text, color="#333", dy=-6):
            return f'<text x="{x:.1f}" y="{y+dy:.1f}" class="mechanism-label" font-size="8" fill="{color}" text-anchor="middle">{text}</text>'

        def mid(p, q):
            return (p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0

        # Dimension texts using real mm (unscaled by fit)
        import math
        def dist_mm(p_mm: Tuple[float, float], q_mm: Tuple[float, float]) -> float:
            dx = p_mm[0] - q_mm[0]
            dy = p_mm[1] - q_mm[1]
            return math.hypot(dx, dy)

        L1 = dist_mm(O1, A)
        L2 = dist_mm(A, B)
        L3 = dist_mm(B, O2)
        L4 = dist_mm(O1, O2)

        # Build SVG
        parts = [
            # Links
            line(O1p[0], O1p[1], O2p[0], O2p[1], color_ground, 1.6),
            line(O1p[0], O1p[1], Ap[0], Ap[1], color_crank, 2.0),
            line(Ap[0], Ap[1], Bp[0], Bp[1], color_coupler, 2.0),
            line(O2p[0], O2p[1], Bp[0], Bp[1], color_rocker, 2.0),
            # Joints
            circ(*O1p), circ(*O2p), circ(*Ap), circ(*Bp),
            # Labels
            label(*mid(O1p, Ap), f"Crank (L1 {L1:.1f}mm)", color_crank, dy=-8),
            label(*mid(Ap, Bp), f"Coupler (L2 {L2:.1f}mm)", color_coupler, dy=-8),
            label(*mid(O2p, Bp), f"Rocker (L3 {L3:.1f}mm)", color_rocker, dy=-8),
            label(*mid(O1p, O2p), f"Ground (L4 {L4:.1f}mm)", color_ground, dy=14)
        ]

        # Simple legend on the right side of bounds
        legend_x = bounds.width - 120
        legend_y = 6
        legend = f'''<g class="legend">
            <rect x="{legend_x:.1f}" y="{legend_y:.1f}" width="114" height="64" fill="#ffffff" stroke="#e5e5e5" stroke-width="0.5" rx="3"/>
            <text x="{legend_x+6:.1f}" y="{legend_y+14:.1f}" class="dimension-text" font-size="8">Structure</text>
            <text x="{legend_x+10:.1f}" y="{legend_y+28:.1f}" font-size="8" fill="{color_crank}">Crank</text>
            <text x="{legend_x+10:.1f}" y="{legend_y+40:.1f}" font-size="8" fill="{color_coupler}">Coupler</text>
            <text x="{legend_x+10:.1f}" y="{legend_y+52:.1f}" font-size="8" fill="{color_rocker}">Rocker</text>
        </g>'''

        return '<g>' + ''.join(parts) + legend + '</g>'

    def _generate_multibar_from_keypoints_svg(self, mech_data: Dict[str, Any], bounds: ScaledBounds) -> str:
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

    def _mm_params(self, mech_data: Dict[str, Any], names: list[str]) -> Dict[str, float]:
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

    def _generate_gears_from_params_svg(self, mech_data: Dict[str, Any], bounds: ScaledBounds) -> str:
        """Two-gear mesh from params with clear circles and labels."""
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

        parts = []
        for (cx, cy, r, name, color) in [
            (c1p[0], c1p[1], r1p, 'Gear 1', '#2c3e50'),
            (c2p[0], c2p[1], r2p, 'Gear 2', '#8e44ad'),
        ]:
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="{color}" stroke-width="1.5"/>')
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r/3:.1f}" fill="none" stroke="#444" stroke-width="1"/>')
            parts.append(f'<text x="{cx:.1f}" y="{cy - r - 8:.1f}" class="mechanism-label" font-size="8" text-anchor="middle">{name}</text>')

        # Mesh line for reference
        parts.append(f'<line x1="{c1p[0]:.1f}" y1="{c1p[1]:.1f}" x2="{c2p[0]:.1f}" y2="{c2p[1]:.1f}" stroke="#aaa" stroke-width="0.8" stroke-dasharray="3,3"/>')

        return '<g>' + ''.join(parts) + '</g>'

    def _generate_planetary_gear_from_params_svg(self, mech_data: Dict[str, Any], bounds: ScaledBounds) -> str:
        """Planetary gear (sun + planet) from params with clear circles and labels."""
        mm = self._mm_params(mech_data, ['r_sun_mm', 'r_planet_mm'])
        rs = mm.get('r_sun_mm', 20.0)
        rp = mm.get('r_planet_mm', 12.0)

        kp = mech_data.get('key_points', {})
        factor = float(mech_data.get('total_scale_factor', 1.0))
        if 'sun_center' in kp and 'planet_center' in kp:
            sx, sy = kp['sun_center']
            px, py = kp['planet_center']
            cs = (float(sx) * factor, float(sy) * factor)
            cp = (float(px) * factor, float(py) * factor)
        else:
            cs = (0.0, 0.0)
            cp = (rs + rp, 0.0)

        xs = [cs[0] - rs, cs[0] + rs, cp[0] - rp, cp[0] + rp]
        ys = [cs[1] - rs, cs[1] + rs, cp[1] - rp, cp[1] + rp]
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
        cpp = pack(cp)
        rsp = rs * scale
        rpp = rp * scale

        parts = []
        parts.append(f'<circle cx="{csp[0]:.1f}" cy="{csp[1]:.1f}" r="{rsp:.1f}" fill="none" stroke="#2c3e50" stroke-width="1.5"/>')
        parts.append(f'<circle cx="{cpp[0]:.1f}" cy="{cpp[1]:.1f}" r="{rpp:.1f}" fill="none" stroke="#16a085" stroke-width="1.5"/>')
        parts.append(f'<text x="{csp[0]:.1f}" y="{csp[1] - rsp - 8:.1f}" class="mechanism-label" font-size="8" text-anchor="middle">Sun</text>')
        parts.append(f'<text x="{cpp[0]:.1f}" y="{cpp[1] - rpp - 8:.1f}" class="mechanism-label" font-size="8" text-anchor="middle">Planet</text>')
        parts.append(f'<line x1="{csp[0]:.1f}" y1="{csp[1]:.1f}" x2="{cpp[0]:.1f}" y2="{cpp[1]:.1f}" stroke="#aaa" stroke-width="0.8" stroke-dasharray="3,3"/>')

        return '<g>' + ''.join(parts) + '</g>'

    def _generate_cam_from_params_svg(self, mech_data: Dict[str, Any], bounds: ScaledBounds) -> str:
        """Cam from params with egg-shape and top follower using long rod semantics."""
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

        # Rough egg outline: ellipse approximating eccentric cam (rx=r+e, ry=r)
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

        parts = []
        parts.append(f'<ellipse cx="{cxp:.1f}" cy="{cyp:.1f}" rx="{rxp:.1f}" ry="{ryp:.1f}" fill="none" stroke="#2c3e50" stroke-width="1.5"/>')
        parts.append(f'<circle cx="{cxp:.1f}" cy="{cyp:.1f}" r="{2:.1f}" fill="#2c3e50"/>')
        # Follower above cam (rod can be long). Place guide vertically above center.
        fx = cxp
        fy_top = cyp - (ryp + rod_len)
        parts.append(f'<line x1="{fx:.1f}" y1="{fy_top:.1f}" x2="{fx:.1f}" y2="{cyp - ryp:.1f}" stroke="#aaa" stroke-width="0.8" stroke-dasharray="3,3"/>')
        # Follower block at top
        parts.append(f'<rect x="{fx-6:.1f}" y="{fy_top-4:.1f}" width="12" height="8" fill="#27ae60" stroke="#1e8449" stroke-width="1"/>')
        # Rod line
        parts.append(f'<line x1="{fx:.1f}" y1="{fy_top:.1f}" x2="{fx:.1f}" y2="{cyp - ryp:.1f}" stroke="#27ae60" stroke-width="1" stroke-dasharray="3,2"/>')
        parts.append(f'<text x="{cxp:.1f}" y="{cyp - ryp - 10:.1f}" class="mechanism-label" font-size="8" text-anchor="middle">Cam (Egg)</text>')

        return '<g>' + ''.join(parts) + '</g>'

    def _generate_parameter_annotations(self, mech_data: Dict[str, Any], bounds: ScaledBounds) -> str:
        """
        Generate parameter annotations for real-world mechanism dimensions.

        Args:
            mech_data: Mechanism data with real_world_params
            bounds: Mechanism bounds for positioning

        Returns:
            SVG string with parameter annotations
        """
        annotations = []

        try:
            real_world_params = mech_data.get('real_world_params', {})
            mechanism_type = mech_data.get('type', 'unknown')

            if not real_world_params:
                return ""

            # Position annotations to the right of the mechanism, with a light panel
            annotation_x = bounds.width + 15
            annotation_y_start = 20
            line_height = 12

            annotations.append('<g class="parameter-annotations">')
            annotations.append(f'<rect x="{annotation_x - 6}" y="{annotation_y_start - 14}" '
                               f'width="160" height="110" fill="#ffffff" stroke="#e5e5e5" '
                               f'stroke-width="0.5" rx="3"/>')
            annotations.append(f'<text x="{annotation_x}" y="{annotation_y_start}" '
                             f'class="parameter-header" font-size="8" font-weight="bold" fill="#333">'
                             f'Real-World Dimensions:</text>')

            y_offset = annotation_y_start + line_height

            # Add mechanism-specific parameter annotations
            if mechanism_type == "4_bar_linkage":
                link_params = ['l1_mm', 'l2_mm', 'l3_mm', 'l4_mm']
                for i, param in enumerate(link_params):
                    if param in real_world_params:
                        value = real_world_params[param]
                        link_name = param.replace('_mm', '').upper()
                        annotations.append(f'<text x="{annotation_x}" y="{y_offset}" '
                                         f'class="parameter-text" font-size="7" fill="#222">'
                                         f'{link_name}: {value:.1f}mm</text>')
                        y_offset += line_height

            elif mechanism_type == "cam":
                cam_params = ['base_radius_mm', 'eccentricity_mm']
                for param in cam_params:
                    if param in real_world_params:
                        value = real_world_params[param]
                        param_name = param.replace('_mm', '').replace('_', ' ').title()
                        annotations.append(f'<text x="{annotation_x}" y="{y_offset}" '
                                         f'class="parameter-text" font-size="7" fill="#222">'
                                         f'{param_name}: {value:.1f}mm</text>')
                        y_offset += line_height

            elif mechanism_type in ["gear", "planetary_gear"]:
                gear_params = ['r1_mm', 'r2_mm', 'r_sun_mm', 'r_planet_mm', 'arm_length_mm']
                for param in gear_params:
                    if param in real_world_params:
                        value = real_world_params[param]
                        param_name = param.replace('_mm', '').replace('_', ' ').title()
                        annotations.append(f'<text x="{annotation_x}" y="{y_offset}" '
                                         f'class="parameter-text" font-size="7" fill="#222">'
                                         f'{param_name}: {value:.1f}mm</text>')
                        y_offset += line_height

            # Add scale factor information
            if 'scale_factor_used' in real_world_params:
                scale_factor = real_world_params['scale_factor_used']
                annotations.append(f'<text x="{annotation_x}" y="{y_offset + 5}" '
                                 f'class="scale-info" font-size="6" fill="#666" font-style="italic">'
                                 f'Scale Factor: {scale_factor:.3f}</text>')

            annotations.append('</g>')

        except Exception as e:
            # Return empty string if annotation generation fails
            return ""

        return '\n'.join(annotations)

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
        """Generate enhanced gear representation with patterns and textures"""
        cx, cy = bounds.width/2, bounds.height/2
        radius = min(bounds.width, bounds.height) / 2 - 5
        
        # Enhanced gear with patterns
        return f'''
        <!-- Main gear body with gradient fill -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}"
                fill="url(#gradient-gear)" stroke="#2c3e50" stroke-width="1.5"/>
        
        <!-- Inner hub -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius/3:.1f}"
                fill="url(#pattern-gear)" stroke="#34495e" stroke-width="1"/>
        
        <!-- Gear teeth representation with enhanced detail -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius+2:.1f}"
                fill="none" stroke="#2c3e50" stroke-width="0.8" stroke-dasharray="2,1"/>
        
        <!-- Center hole -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius/8:.1f}"
                fill="#fff" stroke="#555" stroke-width="0.5"/>
        
        <!-- Keyway indicator -->
        <rect x="{cx-1:.1f}" y="{cy-radius/8:.1f}" width="2" height="{radius/4:.1f}"
              fill="#555"/>
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
        """Generate enhanced cam representation with surface texture"""
        cx, cy = bounds.width/2, bounds.height/2
        rx, ry = bounds.width/2-5, bounds.height/2-5
        
        # Enhanced cam with surface patterns
        return f'''
        <!-- Main cam body with radial gradient -->
        <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}"
                 fill="url(#gradient-cam)" stroke="#2c3e50" stroke-width="1.5"/>
        
        <!-- Surface texture pattern -->
        <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}"
                 fill="url(#pattern-cam)" opacity="0.4"/>
        
        <!-- Center shaft -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="4"
                fill="#34495e" stroke="#2c3e50" stroke-width="1"/>
        
        <!-- Center hole -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="2"
                fill="#fff" stroke="#555" stroke-width="0.5"/>
        
        <!-- Cam profile indicators -->
        <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx*0.7:.1f}" ry="{ry*0.7:.1f}"
                 fill="none" stroke="#7f8c8d" stroke-width="0.5" stroke-dasharray="1,1"/>
        
        <!-- Direction of rotation arrow -->
        <path d="M{cx+rx*0.5:.1f},{cy:.1f} Q{cx+rx*0.3:.1f},{cy-10:.1f} {cx:.1f},{cy-10:.1f}"
              fill="none" stroke="#e74c3c" stroke-width="1" marker-end="url(#arrowhead)"/>
        
        <!-- Arrow marker definition -->
        <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" 
                    refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#e74c3c"/>
            </marker>
        </defs>
        '''

    def _generate_pulley_svg(self, bounds: ScaledBounds) -> str:
        """Generate standard pulley representation"""
        cx, cy = bounds.width/2, bounds.height/2
        radius = min(bounds.width, bounds.height) / 2 - 3

        return f'''
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}"
                fill="none" stroke="black" stroke-width="1.5"/>
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius-5:.1f}"
                fill="none" stroke="black" stroke-width="1"/>
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
        self.scale_normalizer = ScaleNormalizer(target_character_height_mm)
        self.layout_manager = SmartLayoutManager()
        self.mechanism_processor = EnhancedMechanismProcessor(self.scale_normalizer)
        self.logger = logging.getLogger(__name__)

    def optimize_blueprint_layout(self, part_items: List[Any], mechanism_data: Dict[str, Any]) -> Tuple[List[LayoutItem], float, float]:
        """
        Optimize complete blueprint layout with proper scaling and spacing

        Args:
            part_items: List of character part items
            mechanism_data: Dictionary of mechanism data

        Returns:
            Tuple of (layout_items, total_width_mm, total_height_mm)
        """
        self.logger.info("Starting blueprint layout optimization...")

        layout_items = []

        # Process character parts with scale normalization
        if part_items:
            part_layout_items = self._process_character_parts(part_items)
            layout_items.extend(part_layout_items)

        # Process mechanisms with enhanced support
        if mechanism_data:
            mechanism_layout_items = self._process_mechanisms(mechanism_data)
            layout_items.extend(mechanism_layout_items)

        # Apply smart layout to prevent overlapping
        optimized_items = self.layout_manager.calculate_optimal_layout(layout_items)

        # Calculate total dimensions
        total_width, total_height = self.layout_manager.calculate_total_dimensions(optimized_items)

        self.logger.info(f"Blueprint optimization complete: {len(optimized_items)} items, "
                        f"{total_width:.0f}×{total_height:.0f}mm")

        return optimized_items, total_width, total_height

    def _process_character_parts(self, part_items: List[Any]) -> List[LayoutItem]:
        """Process character parts with scale normalization"""
        from automataii.generation.contour_extractor import PNGBlueprintProcessor

        layout_items = []

        # Calculate scale factor based on largest character part
        max_height = 0
        for item in part_items:
            processor = PNGBlueprintProcessor()
            contour = processor.process_part_png(item)
            if contour:
                _, _, _, height = contour.bounding_rect
                max_height = max(max_height, height)

        if max_height > 0:
            scale_factor = self.scale_normalizer.calculate_scale_factor(max_height)
        else:
            scale_factor = 0.36  # Default scale

        # Process each part with normalized scale
        for item in part_items:
            processor = PNGBlueprintProcessor()
            contour = processor.process_part_png(item)

            if contour:
                # Normalize contour scale
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
                self.logger.debug(f"Processed part {part_name}: {w:.1f}×{h:.1f}mm")

        return layout_items

    def _process_mechanisms(self, mechanism_data: Dict[str, Any]) -> List[LayoutItem]:
        """Process mechanisms with enhanced support"""
        layout_items = []

        for mech_id, mech_info in mechanism_data.items():
            layout_item = self.mechanism_processor.process_mechanism(mech_id, mech_info)
            if layout_item:
                layout_items.append(layout_item)

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
