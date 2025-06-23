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
            
            # Get standard size for mechanism type
            standard_size = self.standard_mechanism_sizes.get(
                mechanism_type, 
                {'width': 60, 'height': 60}  # Default size
            )
            
            # Apply any custom scaling from mechanism data
            scale = mech_data.get('scale', 1.0)
            actual_width = standard_size['width'] * scale
            actual_height = standard_size['height'] * scale
            
            # Create scaled bounds
            bounds = ScaledBounds(
                x=0,  # Will be positioned by layout manager
                y=0,
                width=actual_width,
                height=actual_height
            )
            
            # Generate mechanism SVG content
            svg_content = self._generate_mechanism_svg(mech_id, mech_data, bounds)
            
            # Create layout item
            layout_item = LayoutItem(
                name=mech_id,
                bounds=bounds,
                svg_content=svg_content,
                item_type='mechanism',
                priority=2  # Mechanisms get medium priority
            )
            
            self.logger.debug(f"Processed mechanism {mech_id}: {actual_width:.1f}x{actual_height:.1f}mm")
            return layout_item
            
        except Exception as e:
            self.logger.error(f"Error processing mechanism {mech_id}: {e}")
            return None
    
    def _generate_mechanism_svg(self, mech_id: str, mech_data: Dict[str, Any], bounds: ScaledBounds) -> str:
        """Generate SVG content for mechanism with enhanced support for all types"""
        
        mechanism_type = mech_data.get('type', 'unknown')  # Fixed: GUI uses 'type' not 'mechanism_type'
        
        # Always use standard mechanism generation for consistency and reliability
        # This ensures all mechanism types are properly supported
        base_svg = self._generate_standard_mechanism_svg(mech_id, mechanism_type, bounds)
        
        # Try to enhance with specific generator if available
        try:
            if mechanism_type == 'gear':
                from automataii.generation.gear import GearGenerator
                generator = GearGenerator()
                enhanced_svg = generator.generate_svg(mech_data)
                # Combine standard with enhanced if enhanced is valid
                if enhanced_svg and len(enhanced_svg.strip()) > 10:
                    base_svg = enhanced_svg
                    self.logger.debug(f"Enhanced {mechanism_type} with specific generator")
            elif mechanism_type == '4_bar_linkage':  # Fixed: GUI creates '4_bar_linkage' not 'linkage'
                from automataii.generation.linkage import LinkageGenerator
                generator = LinkageGenerator()
                enhanced_svg = generator.generate_svg(mech_data)
                if enhanced_svg and len(enhanced_svg.strip()) > 10:
                    base_svg = enhanced_svg
                    self.logger.debug(f"Enhanced {mechanism_type} with specific generator")
            elif mechanism_type == 'cam':
                from automataii.generation.cam import CamGenerator
                generator = CamGenerator()
                enhanced_svg = generator.generate_svg(mech_data)
                if enhanced_svg and len(enhanced_svg.strip()) > 10:
                    base_svg = enhanced_svg
            elif mechanism_type == 'planetary_gear':
                # Handle planetary gear as a special type of gear
                from automataii.generation.gear import GearGenerator
                generator = GearGenerator()
                enhanced_svg = generator.generate_svg(mech_data)
                if enhanced_svg and len(enhanced_svg.strip()) > 10:
                    base_svg = enhanced_svg
                    self.logger.debug(f"Enhanced {mechanism_type} with specific generator")
        except Exception as e:
            self.logger.warning(f"Generator enhancement failed for {mechanism_type}: {e}, using standard")
        
        # Calculate text bounds to prevent overlapping
        text_height = 60  # Reserve space for labels
        total_bounds_height = bounds.height + text_height
        
        # Wrap in positioned group with anti-overlap labeling
        positioned_svg = f'''
        <g class="mechanism-{mechanism_type}" data-id="{mech_id}">
            <title>{mech_id} ({mechanism_type})</title>
            
            <!-- Mechanism background for visibility with text space -->
            <rect x="-5" y="-5" width="{bounds.width + 10:.1f}" height="{total_bounds_height + 10:.1f}" 
                  fill="#f9f9f9" stroke="#ddd" stroke-width="0.5" rx="3"/>
            
            <!-- Mechanism content -->
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
                
                <!-- Mechanism ID for assembly reference -->
                <text x="{bounds.width/2:.1f}" y="{bounds.height + 56:.1f}" 
                      class="dimension-text" text-anchor="middle" font-size="7" fill="#666">
                    ID: {mech_id}
                </text>
            </g>
        </g>
        '''
        
        return positioned_svg
    
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
        """Generate standard gear representation"""
        cx, cy = bounds.width/2, bounds.height/2
        radius = min(bounds.width, bounds.height) / 2 - 5
        
        return f'''
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" 
                fill="none" stroke="black" stroke-width="1.5"/>
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius/3:.1f}" 
                fill="none" stroke="black" stroke-width="1"/>
        <!-- Gear teeth representation -->
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius+2:.1f}" 
                fill="none" stroke="black" stroke-width="0.5" stroke-dasharray="3,2"/>
        '''
    
    def _generate_linkage_svg(self, bounds: ScaledBounds) -> str:
        """Generate standard linkage representation"""
        return f'''
        <rect x="5" y="{bounds.height/2-5:.1f}" width="{bounds.width-10:.1f}" height="10" 
              fill="none" stroke="black" stroke-width="1.5"/>
        <circle cx="10" cy="{bounds.height/2:.1f}" r="4" 
                fill="none" stroke="black" stroke-width="1"/>
        <circle cx="{bounds.width-10:.1f}" cy="{bounds.height/2:.1f}" r="4" 
                fill="none" stroke="black" stroke-width="1"/>
        '''
    
    def _generate_cam_svg(self, bounds: ScaledBounds) -> str:
        """Generate standard cam representation"""
        cx, cy = bounds.width/2, bounds.height/2
        
        return f'''
        <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{bounds.width/2-5:.1f}" ry="{bounds.height/2-5:.1f}" 
                 fill="none" stroke="black" stroke-width="1.5"/>
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" 
                fill="black"/>
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
        """Generate SVG content for scaled part"""
        
        return f'''
        <g class="scaled-part" data-name="{part_name}">
            <!-- Scaled part outline -->
            <path d="{scaled_contour.svg_path}" class="part-outline"/>
            
            <!-- Manufacturing cutting path -->
            <path d="{scaled_contour.svg_path}" class="cutting-path"/>
            
            <!-- Part label -->
            <text x="{bounds.width/2:.1f}" y="-8" 
                  class="part-label" text-anchor="middle">{part_name}</text>
            
            <!-- Dimensions -->
            <g class="dimensions">
                <!-- Width dimension -->
                <line x1="0" y1="{bounds.height + 12:.1f}" 
                      x2="{bounds.width:.1f}" y2="{bounds.height + 12:.1f}" 
                      class="dimension-line"/>
                <text x="{bounds.width/2:.1f}" y="{bounds.height + 22:.1f}" 
                      class="dimension-text" text-anchor="middle">{bounds.width:.0f}mm</text>
                
                <!-- Height dimension -->
                <line x1="-12" y1="0" x2="-12" y2="{bounds.height:.1f}" 
                      class="dimension-line"/>
                <text x="-15" y="{bounds.height/2:.1f}" 
                      class="dimension-text" text-anchor="middle" 
                      transform="rotate(-90, -15, {bounds.height/2:.1f})">
                      {bounds.height:.0f}mm</text>
            </g>
            
            <!-- Manufacturing notes -->
            <text x="0" y="{bounds.height + 40:.1f}" 
                  class="manufacturing-note" font-size="6">
                  Scaled Area: {scaled_contour.area:.0f}mm² | Perimeter: {scaled_contour.perimeter:.0f}mm
            </text>
        </g>
        '''