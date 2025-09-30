# Blueprint Generator
# Lines: ~400
# Public API: BlueprintGenerator
# Deps In: mechanism serializers
# Deps Out: math, numpy
# Coupling: Low
# Cohesion: Feature (blueprint generation)
# Owner: Alan Synn
# Last Updated: 2025-01-20

"""
Advanced blueprint generator for manufacturing documentation.
Creates detailed technical drawings with dimensions, tolerances, and assembly instructions.
"""

import math
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ViewPort:
    """Viewport configuration for drawings."""
    x: float
    y: float
    width: float
    height: float
    scale: float = 1.0
    label: str = ""


class BlueprintGenerator:
    """
    Base blueprint generator for all mechanism types.
    
    Generates manufacturing-ready technical drawings with:
    - Multiple views (front, side, top, isometric)
    - Detailed dimensions
    - Tolerances and fits
    - Part breakdown
    - Assembly instructions
    - Bill of materials
    """
    
    def __init__(self, mechanism_type: str):
        """Initialize blueprint generator."""
        self.mechanism_type = mechanism_type
        self.views: List[ViewPort] = []
        self.svg_elements: List[str] = []
        self.dimensions: List[str] = []
        self.annotations: List[str] = []
        self.title_block: Dict[str, str] = {}
        
    def generate_blueprint(self, mechanism_data: Dict[str, Any]) -> str:
        """
        Generate complete blueprint SVG.
        
        Args:
            mechanism_data: Complete mechanism configuration
            
        Returns:
            SVG string for manufacturing documentation
        """
        # Setup drawing layout
        self._setup_layout()
        
        # Add title block
        self._add_title_block(mechanism_data)
        
        # Generate views
        self._generate_front_view(mechanism_data)
        self._generate_top_view(mechanism_data)
        self._generate_side_view(mechanism_data)
        self._generate_isometric_view(mechanism_data)
        
        # Add dimensions
        self._add_dimensions(mechanism_data)
        
        # Add tolerances
        self._add_tolerances(mechanism_data)
        
        # Add part list
        self._add_part_list(mechanism_data)
        
        # Add assembly notes
        self._add_assembly_notes(mechanism_data)
        
        # Combine all elements
        return self._combine_svg_elements()
    
    def _setup_layout(self):
        """Setup standard drawing layout with viewports."""
        # A3 landscape layout (420mm x 297mm)
        drawing_width = 420
        drawing_height = 297
        margin = 10
        
        # Define viewports for different views
        self.views = [
            ViewPort(
                x=margin,
                y=margin,
                width=(drawing_width - 3*margin) / 2,
                height=(drawing_height - 3*margin) / 2,
                label="FRONT VIEW"
            ),
            ViewPort(
                x=(drawing_width + margin) / 2,
                y=margin,
                width=(drawing_width - 3*margin) / 2,
                height=(drawing_height - 3*margin) / 2,
                label="TOP VIEW"
            ),
            ViewPort(
                x=margin,
                y=(drawing_height + margin) / 2,
                width=(drawing_width - 3*margin) / 2,
                height=(drawing_height - 3*margin) / 2,
                label="SIDE VIEW"
            ),
            ViewPort(
                x=(drawing_width + margin) / 2,
                y=(drawing_height + margin) / 2,
                width=(drawing_width - 3*margin) / 2,
                height=(drawing_height - 3*margin) / 2,
                label="ISOMETRIC VIEW"
            )
        ]
    
    def _add_title_block(self, mechanism_data: Dict[str, Any]):
        """Add standard title block with drawing information."""
        title_block_svg = f'''
        <!-- Title Block -->
        <g id="title-block">
            <rect x="300" y="250" width="110" height="40" 
                  stroke="black" stroke-width="0.5" fill="none"/>
            <line x1="300" y1="260" x2="410" y2="260" stroke="black" stroke-width="0.5"/>
            <line x1="300" y1="270" x2="410" y2="270" stroke="black" stroke-width="0.5"/>
            <line x1="300" y1="280" x2="410" y2="280" stroke="black" stroke-width="0.5"/>
            <line x1="355" y1="250" x2="355" y2="290" stroke="black" stroke-width="0.5"/>
            
            <text x="302" y="258" font-size="8" font-family="Arial">TITLE:</text>
            <text x="357" y="258" font-size="8" font-family="Arial" font-weight="bold">
                {mechanism_data.get('type', 'MECHANISM').upper()}
            </text>
            
            <text x="302" y="268" font-size="8" font-family="Arial">PART NO:</text>
            <text x="357" y="268" font-size="8" font-family="Arial">
                {mechanism_data.get('id', 'M-001')[:10]}
            </text>
            
            <text x="302" y="278" font-size="8" font-family="Arial">MATERIAL:</text>
            <text x="357" y="278" font-size="8" font-family="Arial">
                {mechanism_data.get('material', 'STEEL')}
            </text>
            
            <text x="302" y="288" font-size="8" font-family="Arial">SCALE:</text>
            <text x="357" y="288" font-size="8" font-family="Arial">1:1</text>
        </g>
        '''
        self.svg_elements.append(title_block_svg)
    
    def _generate_front_view(self, mechanism_data: Dict[str, Any]):
        """Generate front view of mechanism."""
        # Override in specific implementations
        pass
    
    def _generate_top_view(self, mechanism_data: Dict[str, Any]):
        """Generate top view of mechanism."""
        # Override in specific implementations
        pass
    
    def _generate_side_view(self, mechanism_data: Dict[str, Any]):
        """Generate side view of mechanism."""
        # Override in specific implementations
        pass
    
    def _generate_isometric_view(self, mechanism_data: Dict[str, Any]):
        """Generate isometric view of mechanism."""
        # Override in specific implementations
        pass
    
    def _add_dimensions(self, mechanism_data: Dict[str, Any]):
        """Add dimension lines and values."""
        dimensions_svg = '''
        <!-- Dimensions -->
        <g id="dimensions" stroke="black" stroke-width="0.35" fill="none">
        '''
        
        for dimension in self.dimensions:
            dimensions_svg += dimension
        
        dimensions_svg += '</g>'
        self.svg_elements.append(dimensions_svg)
    
    def _add_tolerances(self, mechanism_data: Dict[str, Any]):
        """Add tolerance specifications."""
        tolerances = mechanism_data.get('tolerances', {})
        
        tolerance_svg = '''
        <!-- Tolerances -->
        <g id="tolerances" font-size="6" font-family="Arial">
            <text x="10" y="280">UNLESS OTHERWISE SPECIFIED:</text>
            <text x="10" y="286">DIMENSIONS ARE IN MILLIMETERS</text>
            <text x="10" y="292">TOLERANCES: ±0.1mm</text>
        </g>
        '''
        self.svg_elements.append(tolerance_svg)
    
    def _add_part_list(self, mechanism_data: Dict[str, Any]):
        """Add bill of materials / part list."""
        parts = mechanism_data.get('parts', [])
        
        part_list_svg = '''
        <!-- Part List -->
        <g id="part-list" font-size="7" font-family="Arial">
            <rect x="10" y="200" width="120" height="40" 
                  stroke="black" stroke-width="0.5" fill="none"/>
            <line x1="10" y1="208" x2="130" y2="208" stroke="black" stroke-width="0.5"/>
            <line x1="30" y1="200" x2="30" y2="240" stroke="black" stroke-width="0.5"/>
            <line x1="90" y1="200" x2="90" y2="240" stroke="black" stroke-width="0.5"/>
            <line x1="110" y1="200" x2="110" y2="240" stroke="black" stroke-width="0.5"/>
            
            <text x="12" y="206" font-weight="bold">NO.</text>
            <text x="32" y="206" font-weight="bold">DESCRIPTION</text>
            <text x="92" y="206" font-weight="bold">QTY</text>
            <text x="112" y="206" font-weight="bold">MAT.</text>
        '''
        
        # Add parts (example)
        y_offset = 214
        for i, part in enumerate(parts[:5], 1):  # Limit to 5 parts for space
            part_list_svg += f'''
            <text x="12" y="{y_offset}">{i}</text>
            <text x="32" y="{y_offset}">{part.get('name', 'Part')[:20]}</text>
            <text x="92" y="{y_offset}">{part.get('quantity', 1)}</text>
            <text x="112" y="{y_offset}">{part.get('material', 'STL')[:5]}</text>
            '''
            y_offset += 6
        
        part_list_svg += '</g>'
        self.svg_elements.append(part_list_svg)
    
    def _add_assembly_notes(self, mechanism_data: Dict[str, Any]):
        """Add assembly instructions and notes."""
        notes = mechanism_data.get('assembly_notes', [])
        
        notes_svg = '''
        <!-- Assembly Notes -->
        <g id="notes" font-size="6" font-family="Arial">
            <text x="140" y="210" font-weight="bold">ASSEMBLY NOTES:</text>
        '''
        
        y_offset = 216
        for i, note in enumerate(notes[:5], 1):
            notes_svg += f'<text x="140" y="{y_offset}">{i}. {note[:50]}</text>'
            y_offset += 6
        
        notes_svg += '</g>'
        self.svg_elements.append(notes_svg)
    
    def _combine_svg_elements(self) -> str:
        """Combine all SVG elements into final blueprint."""
        svg = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" 
     width="420mm" height="297mm" 
     viewBox="0 0 420 297">
    
    <!-- Drawing Border -->
    <rect x="5" y="5" width="410" height="287" 
          stroke="black" stroke-width="1" fill="none"/>
    <rect x="7" y="7" width="406" height="283" 
          stroke="black" stroke-width="0.5" fill="none"/>
    
    <!-- Viewport Borders -->
    <g id="viewports" stroke="black" stroke-width="0.5" fill="none">
'''
        
        for view in self.views:
            svg += f'''
        <rect x="{view.x}" y="{view.y}" 
              width="{view.width}" height="{view.height}"/>
        <text x="{view.x + 2}" y="{view.y + 10}" 
              font-size="8" font-family="Arial" font-weight="bold">
            {view.label}
        </text>
'''
        
        svg += '    </g>\n\n'
        
        # Add all generated elements
        for element in self.svg_elements:
            svg += element + '\n'
        
        svg += '</svg>'
        
        return svg
    
    def create_dimension_line(self, x1: float, y1: float, x2: float, y2: float, 
                            value: str, offset: float = 10) -> str:
        """Create a dimension line with arrows and text."""
        # Calculate midpoint
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        
        # Calculate perpendicular offset
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy)
        
        if length > 0:
            perp_x = -dy / length * offset
            perp_y = dx / length * offset
        else:
            perp_x = 0
            perp_y = offset
        
        # Offset points
        ox1 = x1 + perp_x
        oy1 = y1 + perp_y
        ox2 = x2 + perp_x
        oy2 = y2 + perp_y
        
        return f'''
        <g class="dimension">
            <!-- Extension lines -->
            <line x1="{x1}" y1="{y1}" x2="{ox1}" y2="{oy1}" 
                  stroke-dasharray="2,2"/>
            <line x1="{x2}" y1="{y2}" x2="{ox2}" y2="{oy2}" 
                  stroke-dasharray="2,2"/>
            
            <!-- Dimension line -->
            <line x1="{ox1}" y1="{oy1}" x2="{ox2}" y2="{oy2}"/>
            
            <!-- Arrows -->
            <polygon points="{ox1-2},{oy1} {ox1+2},{oy1-1} {ox1+2},{oy1+1}" 
                     fill="black"/>
            <polygon points="{ox2+2},{oy2} {ox2-2},{oy2-1} {ox2-2},{oy2+1}" 
                     fill="black"/>
            
            <!-- Value -->
            <text x="{mid_x + perp_x}" y="{mid_y + perp_y - 2}" 
                  font-size="7" text-anchor="middle" font-family="Arial">
                {value}
            </text>
        </g>
        '''
    
    def create_radius_dimension(self, cx: float, cy: float, r: float, 
                               angle: float = 45) -> str:
        """Create radius dimension with leader line."""
        # Calculate point on circle
        rad = math.radians(angle)
        px = cx + r * math.cos(rad)
        py = cy + r * math.sin(rad)
        
        # Leader line endpoint
        lx = px + 20 * math.cos(rad)
        ly = py + 20 * math.sin(rad)
        
        return f'''
        <g class="radius-dimension">
            <!-- Leader line -->
            <line x1="{cx}" y1="{cy}" x2="{px}" y2="{py}"/>
            <line x1="{px}" y1="{py}" x2="{lx}" y2="{ly}"/>
            
            <!-- Arrow -->
            <polygon points="{px-2},{py} {px+2},{py-1} {px+2},{py+1}" 
                     fill="black"/>
            
            <!-- Value -->
            <text x="{lx + 2}" y="{ly}" font-size="7" font-family="Arial">
                R{r:.1f}
            </text>
        </g>
        '''
    
    def create_angle_dimension(self, cx: float, cy: float, r: float,
                              start_angle: float, end_angle: float) -> str:
        """Create angle dimension arc."""
        # Calculate arc path
        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)
        
        x1 = cx + r * math.cos(start_rad)
        y1 = cy + r * math.sin(start_rad)
        x2 = cx + r * math.cos(end_rad)
        y2 = cy + r * math.sin(end_rad)
        
        angle_value = abs(end_angle - start_angle)
        large_arc = 1 if angle_value > 180 else 0
        
        return f'''
        <g class="angle-dimension">
            <!-- Arc -->
            <path d="M {x1} {y1} A {r} {r} 0 {large_arc} 1 {x2} {y2}"
                  stroke="black" stroke-width="0.35" fill="none"/>
            
            <!-- Value -->
            <text x="{cx}" y="{cy - r - 5}" font-size="7" 
                  text-anchor="middle" font-family="Arial">
                {angle_value:.0f}°
            </text>
        </g>
        '''