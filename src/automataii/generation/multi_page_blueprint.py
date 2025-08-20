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


class MultiPageSVGGenerator:
    """Generates multi-page blueprint documentation in SVG format"""
    
    def _generate_page_svg(self, page: BlueprintPage) -> str:
        """Generate SVG content for a single blueprint page"""
        
        # Generate title block
        title_block = f'''
        <g id="title-block">
            <rect x="10" y="10" width="{page.width_mm - 20}" height="40" 
                  fill="#f0f0f0" stroke="black" stroke-width="1"/>
            <text x="{page.width_mm / 2}" y="35" class="section-title" 
                  font-size="16" text-anchor="middle">
                {html.escape(page.title)}
            </text>
        </g>
        '''
        
        # Generate content area
        content_svg = '<g id="page-content" transform="translate(0,60)">'
        
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
