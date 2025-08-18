#!/usr/bin/env python3
"""
Multi-Page Blueprint System for Complete Manufacturing Documentation
Ensures all parts and mechanisms are fully visible across multiple pages

Author: Legendary CS Research Collective
Inspired by: Knuth's multi-page algorithms + professional CAD systems
"""

import html
import logging
import re
from dataclasses import dataclass

from automataii.generation.blueprint_optimizer import LayoutItem, ScaledBounds


@dataclass
class BlueprintPage:
    """Represents a single blueprint page"""
    page_number: int
    title: str
    items: list[LayoutItem]
    width_mm: float
    height_mm: float
    content_type: str  # 'parts', 'mechanisms', 'assembly', 'specifications'

class MultiPageBlueprintManager:
    """
    Manages multi-page blueprint generation for complete documentation
    Ensures nothing gets cut off and all content is properly organized
    """

    def __init__(self, page_width_mm: float = 600.0, page_height_mm: float = 800.0):
        """
        Initialize multi-page manager
        
        Args:
            page_width_mm: Standard page width (600mm for readability)
            page_height_mm: Standard page height (800mm ≈ A4 length but wider)
        """
        self.page_width_mm = page_width_mm
        self.page_height_mm = page_height_mm
        self.title_height_mm = 60.0
        self.specs_height_mm = 100.0
        self.content_height_mm = page_height_mm - self.title_height_mm - self.specs_height_mm - 40  # margins
        self.logger = logging.getLogger(__name__)

    def create_multi_page_blueprint(self, layout_items: list[LayoutItem]) -> list[BlueprintPage]:
        """
        Create multi-page blueprint ensuring all content is visible
        
        Args:
            layout_items: List of optimally placed layout items
            
        Returns:
            List of BlueprintPage objects
        """
        if not layout_items:
            return [self._create_empty_page()]

        self.logger.info(f"Creating multi-page blueprint for {len(layout_items)} items")

        # Separate items by type for better organization
        parts = [item for item in layout_items if item.item_type == 'part']
        mechanisms = [item for item in layout_items if item.item_type == 'mechanism']

        pages = []

        # Create parts pages
        if parts:
            parts_pages = self._create_parts_pages(parts)
            pages.extend(parts_pages)

        # Create mechanism pages
        if mechanisms:
            mechanism_pages = self._create_mechanism_pages(mechanisms)
            pages.extend(mechanism_pages)

        # Create assembly overview page
        if parts or mechanisms:
            assembly_page = self._create_assembly_overview_page(parts, mechanisms)
            pages.append(assembly_page)

        # Create specifications page
        specs_page = self._create_specifications_page(len(parts), len(mechanisms))
        pages.append(specs_page)

        self.logger.info(f"Generated {len(pages)} blueprint pages")
        return pages

    def _create_parts_pages(self, parts: list[LayoutItem]) -> list[BlueprintPage]:
        """Create dedicated pages for character parts"""
        pages = []

        # Group parts that fit on each page
        current_page_items = []
        current_y = 15.0  # Start padding
        page_number = 1

        for part in parts:
            # Check if part fits on current page
            required_height = part.bounds.height + 60  # Extra space for dimensions and labels

            if current_y + required_height <= self.content_height_mm:
                # Fits on current page
                current_page_items.append(part)
                current_y += required_height + 20  # Spacing between parts
            else:
                # Create page with current items
                if current_page_items:
                    page = BlueprintPage(
                        page_number=page_number,
                        title=f"Character Parts - Page {page_number}",
                        items=current_page_items.copy(),
                        width_mm=self.page_width_mm,
                        height_mm=self.page_height_mm,
                        content_type='parts'
                    )
                    pages.append(page)
                    page_number += 1

                # Start new page with current part
                current_page_items = [part]
                current_y = 15.0 + required_height + 20

        # Add remaining items to final page
        if current_page_items:
            page = BlueprintPage(
                page_number=page_number,
                title=f"Character Parts - Page {page_number}",
                items=current_page_items,
                width_mm=self.page_width_mm,
                height_mm=self.page_height_mm,
                content_type='parts'
            )
            pages.append(page)

        return pages

    def _create_mechanism_pages(self, mechanisms: list[LayoutItem]) -> list[BlueprintPage]:
        """Create dedicated pages for mechanisms"""
        pages = []

        # Group mechanisms by type for better organization
        mechanism_groups = self._group_mechanisms_by_type(mechanisms)

        page_number = 1
        for mech_type, mech_list in mechanism_groups.items():
            if not mech_list:
                continue

            # Create pages for this mechanism type
            type_pages = self._create_mechanism_type_pages(mech_type, mech_list, page_number)
            pages.extend(type_pages)
            page_number += len(type_pages)

        return pages

    def _group_mechanisms_by_type(self, mechanisms: list[LayoutItem]) -> dict[str, list[LayoutItem]]:
        """Group mechanisms by their type for better organization"""
        groups = {
            'gears': [],
            'linkages': [],
            'cams': [],
            'pulleys': [],
            'belts': [],
            'springs': [],
            'dampers': [],
            'custom': []
        }

        for mech in mechanisms:
            # Extract mechanism type from SVG content or name
            mech_name = mech.name.lower()

            if 'gear' in mech_name:
                groups['gears'].append(mech)
            elif 'linkage' in mech_name or 'link' in mech_name:
                groups['linkages'].append(mech)
            elif 'cam' in mech_name:
                groups['cams'].append(mech)
            elif 'pulley' in mech_name:
                groups['pulleys'].append(mech)
            elif 'belt' in mech_name:
                groups['belts'].append(mech)
            elif 'spring' in mech_name:
                groups['springs'].append(mech)
            elif 'damper' in mech_name:
                groups['dampers'].append(mech)
            else:
                groups['custom'].append(mech)

        # Remove empty groups
        return {k: v for k, v in groups.items() if v}

    def _create_mechanism_type_pages(self, mech_type: str, mechanisms: list[LayoutItem], start_page: int) -> list[BlueprintPage]:
        """Create pages for a specific mechanism type"""
        pages = []

        # Calculate how many mechanisms fit per page
        mechanisms_per_row = 3  # 3 mechanisms per row for readability
        mechanism_height = 120  # Standard height including labels
        rows_per_page = int(self.content_height_mm / mechanism_height)
        mechanisms_per_page = mechanisms_per_row * rows_per_page

        page_number = start_page

        for i in range(0, len(mechanisms), mechanisms_per_page):
            page_mechanisms = mechanisms[i:i + mechanisms_per_page]

            # Redistribute mechanisms on this page for optimal layout
            redistributed_mechanisms = self._redistribute_mechanisms_on_page(
                page_mechanisms, mechanisms_per_row
            )

            page = BlueprintPage(
                page_number=page_number,
                title=f"{mech_type.title()} Mechanisms - Page {page_number}",
                items=redistributed_mechanisms,
                width_mm=self.page_width_mm,
                height_mm=self.page_height_mm,
                content_type='mechanisms'
            )
            pages.append(page)
            page_number += 1

        return pages

    def _redistribute_mechanisms_on_page(self, mechanisms: list[LayoutItem], per_row: int) -> list[LayoutItem]:
        """Redistribute mechanisms evenly on a page"""
        mechanism_width = (self.page_width_mm - 60) / per_row  # Account for margins
        mechanism_height = 120

        redistributed = []

        for i, mech in enumerate(mechanisms):
            row = i // per_row
            col = i % per_row

            # Calculate new position
            new_x = 30 + col * mechanism_width  # Start margin + column spacing
            new_y = 20 + row * mechanism_height  # Top margin + row spacing

            # Update mechanism bounds
            new_bounds = ScaledBounds(
                x=new_x,
                y=new_y,
                width=min(mech.bounds.width, mechanism_width - 20),  # Leave some spacing
                height=min(mech.bounds.height, mechanism_height - 20)
            )

            # Create new layout item with updated position
            new_mech = LayoutItem(
                name=mech.name,
                bounds=new_bounds,
                svg_content=mech.svg_content,
                item_type=mech.item_type,
                priority=mech.priority
            )

            redistributed.append(new_mech)

        return redistributed

    def _create_assembly_overview_page(self, parts: list[LayoutItem], mechanisms: list[LayoutItem]) -> BlueprintPage:
        """Create assembly overview page showing how parts and mechanisms connect"""

        # Create simplified overview items
        overview_items = []

        # Add simplified part representations
        parts_overview = self._create_parts_overview(parts)
        overview_items.extend(parts_overview)

        # Add mechanism connection diagrams
        mechanism_overview = self._create_mechanism_overview(mechanisms)
        overview_items.extend(mechanism_overview)

        return BlueprintPage(
            page_number=999,  # Will be renumbered
            title="Assembly Overview & Connection Diagram",
            items=overview_items,
            width_mm=self.page_width_mm,
            height_mm=self.page_height_mm,
            content_type='assembly'
        )

    def _create_parts_overview(self, parts: list[LayoutItem]) -> list[LayoutItem]:
        """Create simplified overview of all parts"""
        overview_items = []

        # Create a grid layout for part thumbnails
        thumbnails_per_row = 4
        thumbnail_size = 80

        for i, part in enumerate(parts):
            row = i // thumbnails_per_row
            col = i % thumbnails_per_row

            x = 50 + col * (thumbnail_size + 20)
            y = 50 + row * (thumbnail_size + 30)

            # Create simplified part representation
            simplified_svg = f'''
            <g class="part-overview">
                <rect x="0" y="0" width="{thumbnail_size}" height="{thumbnail_size}" 
                      fill="#f0f0f0" stroke="black" stroke-width="1"/>
                <text x="{thumbnail_size/2}" y="{thumbnail_size/2}" 
                      class="part-label" text-anchor="middle" font-size="8">
                      {part.name}
                </text>
                <text x="{thumbnail_size/2}" y="{thumbnail_size + 15}" 
                      class="dimension-text" text-anchor="middle" font-size="6">
                      {part.bounds.width:.0f}×{part.bounds.height:.0f}mm
                </text>
            </g>
            '''

            overview_item = LayoutItem(
                name=f"{part.name}_overview",
                bounds=ScaledBounds(x=x, y=y, width=thumbnail_size, height=thumbnail_size+20),
                svg_content=simplified_svg,
                item_type='part_overview',
                priority=1
            )
            overview_items.append(overview_item)

        return overview_items

    def _create_mechanism_overview(self, mechanisms: list[LayoutItem]) -> list[LayoutItem]:
        """Create mechanism connection overview"""
        overview_items = []

        # Group mechanisms and show connections
        connection_y = 300  # Below parts overview

        connection_svg = '''
        <g class="mechanism-connections">
            <text x="50" y="20" class="section-title">Mechanism Connections</text>
            <text x="50" y="40" class="manufacturing-note" font-size="10">
                Assembly sequence and mechanical connections between components
            </text>
            
            <!-- Connection diagram -->
            <g transform="translate(50,60)">
        '''

        # Add connection lines and labels for different mechanism types
        y_offset = 0
        for i, mech in enumerate(mechanisms):
            connection_svg += f'''
                <circle cx="20" cy="{y_offset + 10}" r="8" fill="#e0e0e0" stroke="black"/>
                <text x="35" y="{y_offset + 15}" class="mechanism-label" font-size="8">
                    {mech.name} - {mech.bounds.width:.0f}×{mech.bounds.height:.0f}mm
                </text>
            '''
            y_offset += 25

        connection_svg += '''
            </g>
        </g>
        '''

        connection_item = LayoutItem(
            name="mechanism_connections",
            bounds=ScaledBounds(x=0, y=connection_y, width=500, height=200),
            svg_content=connection_svg,
            item_type='connection_diagram',
            priority=1
        )
        overview_items.append(connection_item)

        return overview_items

    def _create_specifications_page(self, num_parts: int, num_mechanisms: int) -> BlueprintPage:
        """Create comprehensive specifications page"""

        specs_svg = f'''
        <g class="specifications-page">
            <text x="50" y="50" class="section-title" font-size="18">
                Manufacturing Specifications & Bill of Materials
            </text>
            
            <!-- Parts Summary -->
            <g transform="translate(50,100)">
                <text x="0" y="0" class="section-title" font-size="14">Character Parts ({num_parts} total)</text>
                <text x="0" y="20" class="manufacturing-note">
                    • Material: 3mm Plywood or Acrylic sheet
                </text>
                <text x="0" y="35" class="manufacturing-note">
                    • Cutting Method: Laser cutter or CNC router
                </text>
                <text x="0" y="50" class="manufacturing-note">
                    • Tolerance: ±0.1mm for precision fit
                </text>
                <text x="0" y="65" class="manufacturing-note">
                    • Surface Finish: Sand all edges smooth
                </text>
            </g>
            
            <!-- Mechanisms Summary -->
            <g transform="translate(50,200)">
                <text x="0" y="0" class="section-title" font-size="14">Mechanisms ({num_mechanisms} total)</text>
                <text x="0" y="20" class="manufacturing-note">
                    • Hardware: Standard metric fasteners (M3, M4 bolts)
                </text>
                <text x="0" y="35" class="manufacturing-note">
                    • Bearings: 608ZZ ball bearings for rotating parts
                </text>
                <text x="0" y="50" class="manufacturing-note">
                    • Springs: Custom wound to specification
                </text>
                <text x="0" y="65" class="manufacturing-note">
                    • Assembly: Follow connection diagram on previous page
                </text>
            </g>
            
            <!-- Tools Required -->
            <g transform="translate(50,300)">
                <text x="0" y="0" class="section-title" font-size="14">Required Tools</text>
                <text x="0" y="20" class="manufacturing-note">
                    • Laser cutter or CNC router for cutting parts
                </text>
                <text x="0" y="35" class="manufacturing-note">
                    • Drill press with metric drill bits
                </text>
                <text x="0" y="50" class="manufacturing-note">
                    • Metric hex keys and screwdrivers
                </text>
                <text x="0" y="65" class="manufacturing-note">
                    • Digital calipers for quality control
                </text>
            </g>
            
            <!-- Quality Control -->
            <g transform="translate(50,400)">
                <text x="0" y="0" class="section-title" font-size="14">Quality Control</text>
                <text x="0" y="20" class="manufacturing-note">
                    • Test fit all parts before final assembly
                </text>
                <text x="0" y="35" class="manufacturing-note">
                    • Check mechanism operation without binding
                </text>
                <text x="0" y="50" class="manufacturing-note">
                    • Verify all fasteners are properly tightened
                </text>
                <text x="0" y="65" class="manufacturing-note">
                    • Document any deviations from specification
                </text>
            </g>
            
            <!-- Footer -->
            <g transform="translate(50,550)">
                <rect x="0" y="0" width="500" height="80" fill="#f8f8f8" stroke="black"/>
                <text x="250" y="25" class="section-title" text-anchor="middle" font-size="12">
                    Automataii Manufacturing Blueprint System
                </text>
                <text x="250" y="45" class="manufacturing-note" text-anchor="middle">
                    Scale: 30cm character height standard | Generated: Professional CAD quality
                </text>
                <text x="250" y="60" class="manufacturing-note" text-anchor="middle">
                    For technical support: Automataii Platform v2.0
                </text>
            </g>
        </g>
        '''

        specs_item = LayoutItem(
            name="specifications",
            bounds=ScaledBounds(x=0, y=0, width=600, height=700),
            svg_content=specs_svg,
            item_type='specifications',
            priority=1
        )

        return BlueprintPage(
            page_number=999,  # Will be renumbered
            title="Manufacturing Specifications",
            items=[specs_item],
            width_mm=self.page_width_mm,
            height_mm=self.page_height_mm,
            content_type='specifications'
        )

    def _create_empty_page(self) -> BlueprintPage:
        """Create empty page when no content is available"""
        empty_svg = '''
        <text x="300" y="400" class="section-title" text-anchor="middle" font-size="16">
            No Content Available
        </text>
        <text x="300" y="430" class="manufacturing-note" text-anchor="middle">
            Please provide character parts or mechanisms to generate blueprint
        </text>
        '''

        empty_item = LayoutItem(
            name="empty",
            bounds=ScaledBounds(x=0, y=0, width=600, height=800),
            svg_content=empty_svg,
            item_type='empty',
            priority=1
        )

        return BlueprintPage(
            page_number=1,
            title="Empty Blueprint",
            items=[empty_item],
            width_mm=self.page_width_mm,
            height_mm=self.page_height_mm,
            content_type='empty'
        )

    def renumber_pages(self, pages: list[BlueprintPage]) -> list[BlueprintPage]:
        """Renumber pages sequentially"""
        for i, page in enumerate(pages, 1):
            page.page_number = i
        return pages


class MultiPageSVGGenerator:
    """
    Generates multiple SVG files for complete blueprint documentation
    Each page is a separate SVG file for easy printing and viewing
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _escape_xml_text(self, text: str) -> str:
        """Properly escape text for XML/SVG"""
        # First do HTML escaping for basic entities
        text = html.escape(text, quote=False)
        # Fix any remaining unescaped ampersands
        text = re.sub(r'&(?!(amp|lt|gt|quot|apos);)', '&amp;', text)
        return text

    def generate_page_svgs(self, pages: list[BlueprintPage]) -> dict[str, str]:
        """
        Generate individual SVG files for each page
        
        Args:
            pages: List of BlueprintPage objects
            
        Returns:
            Dictionary mapping filename to SVG content
        """
        svg_files = {}

        for page in pages:
            filename = f"blueprint_page_{page.page_number:02d}_{page.content_type}.svg"
            svg_content = self._generate_page_svg(page)
            svg_files[filename] = svg_content

            self.logger.info(f"Generated page {page.page_number}: {filename}")

        # Generate index page
        index_svg = self._generate_index_page(pages)
        svg_files["blueprint_index.svg"] = index_svg

        return svg_files

    def _generate_page_svg(self, page: BlueprintPage) -> str:
        """Generate SVG content for a single page"""

        # Generate title block
        title_block = f'''
        <g id="title-block">
            <rect x="10" y="10" width="{page.width_mm - 20}" height="50" 
                  fill="#f8f8f8" stroke="black" stroke-width="2"/>
            <text x="20" y="30" class="section-title" font-size="16">
                {self._escape_xml_text(page.title)}
            </text>
            <text x="20" y="45" class="manufacturing-note" font-size="10">
                Page {page.page_number} | Scale: 30cm character standard | Professional manufacturing quality
            </text>
            <text x="{page.width_mm - 20}" y="30" class="manufacturing-note" font-size="8" text-anchor="end">
                Automataii Platform v2.0
            </text>
            <text x="{page.width_mm - 20}" y="45" class="manufacturing-note" font-size="8" text-anchor="end">
                {self._get_timestamp()}
            </text>
        </g>
        '''

        # Generate content
        content_svg = '<g id="page-content" transform="translate(0,70)">'

        for item in page.items:
            # Remove any XML declaration from embedded content
            clean_content = item.svg_content
            if clean_content.startswith('<?xml'):
                # Remove XML declaration if present
                xml_end = clean_content.find('?>')
                if xml_end != -1:
                    clean_content = clean_content[xml_end + 2:].strip()

            # Remove outer SVG tags if present (just keep inner content)
            if '<svg' in clean_content and '</svg>' in clean_content:
                svg_start = clean_content.find('<svg')
                svg_content_start = clean_content.find('>', svg_start) + 1
                svg_end = clean_content.rfind('</svg>')
                if svg_start != -1 and svg_end != -1:
                    clean_content = clean_content[svg_content_start:svg_end]

            item_svg = f'''
            <g transform="translate({item.bounds.x},{item.bounds.y})">
                {clean_content}
            </g>
            '''
            content_svg += item_svg

        content_svg += '</g>'

        # Generate page footer
        footer_y = page.height_mm - 30
        footer_svg = f'''
        <g id="page-footer">
            <line x1="10" y1="{footer_y}" x2="{page.width_mm - 10}" y2="{footer_y}" 
                  stroke="black" stroke-width="1"/>
            <text x="20" y="{footer_y + 15}" class="manufacturing-note" font-size="8">
                Manufacturing Blueprint | Page {page.page_number} | {page.content_type.title()}
            </text>
            <text x="{page.width_mm - 20}" y="{footer_y + 15}" class="manufacturing-note" 
                  font-size="8" text-anchor="end">
                Automataii Manufacturing System
            </text>
        </g>
        '''

        # Combine all elements
        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{page.width_mm}" height="{page.height_mm}" 
     xmlns="http://www.w3.org/2000/svg" version="1.1">
  <defs>
    <style>
      .blueprint-text {{ font-family: Arial, sans-serif; }}
      .section-title {{ font-size: 14px; font-weight: bold; }}
      .part-outline {{ fill: none; stroke: black; stroke-width: 1.5; }}
      .part-label {{ font-family: Arial, sans-serif; font-size: 10px; font-weight: bold; }}
      .mechanism-label {{ font-family: Arial, sans-serif; font-size: 8px; font-weight: bold; }}
      .dimension-line {{ stroke: #666; stroke-width: 0.5; stroke-dasharray: 2,2; }}
      .dimension-text {{ font-family: Arial, sans-serif; font-size: 8px; fill: #333; }}
      .cutting-path {{ stroke: red; stroke-width: 0.25; stroke-dasharray: 1,1; fill: none; }}
      .manufacturing-note {{ font-family: Arial, sans-serif; font-size: 7px; fill: #555; }}
      .gear-mechanism {{ }}
      .linkage-mechanism {{ }}
      .cam-mechanism {{ }}
      .pulley-mechanism {{ }}
      .belt-mechanism {{ }}
      .spring-mechanism {{ }}
      .damper-mechanism {{ }}
    </style>
  </defs>
  
  <!-- Page Border -->
  <rect x="5" y="5" width="{page.width_mm - 10}" height="{page.height_mm - 10}" 
        fill="none" stroke="black" stroke-width="2"/>
  
  {title_block}
  {content_svg}
  {footer_svg}
</svg>'''

        return svg_content

    def _generate_index_page(self, pages: list[BlueprintPage]) -> str:
        """Generate index page listing all pages"""

        index_content = '''
        <g id="index-content">
            <text x="300" y="100" class="section-title" font-size="20" text-anchor="middle">
                Blueprint Documentation Index
            </text>
            <text x="300" y="130" class="manufacturing-note" font-size="12" text-anchor="middle">
                Complete manufacturing documentation for Automataii character system
            </text>
        '''

        y_offset = 180
        for page in pages:
            index_content += f'''
            <g transform="translate(50,{y_offset})">
                <rect x="0" y="0" width="500" height="30" fill="#f0f0f0" stroke="black"/>
                <text x="10" y="20" class="section-title" font-size="12">
                    Page {page.page_number}: {page.title}
                </text>
                <text x="490" y="20" class="manufacturing-note" font-size="10" text-anchor="end">
                    {page.content_type} ({len(page.items)} items)
                </text>
            </g>
            '''
            y_offset += 35

        index_content += '</g>'

        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="600" height="800" xmlns="http://www.w3.org/2000/svg" version="1.1">
  <defs>
    <style>
      .section-title {{ font-size: 14px; font-weight: bold; font-family: Arial, sans-serif; }}
      .manufacturing-note {{ font-size: 10px; font-family: Arial, sans-serif; fill: #555; }}
    </style>
  </defs>
  
  <rect x="5" y="5" width="590" height="790" fill="none" stroke="black" stroke-width="2"/>
  {index_content}
</svg>'''

        return svg_content

    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
