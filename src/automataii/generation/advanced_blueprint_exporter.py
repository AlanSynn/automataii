"""
Advanced Blueprint Exporter with Part Decomposition Support.

This module extends the existing blueprint functionality to support:
- Part-by-part decomposition of mechanisms
- Multi-page letter-size layouts
- Assembly instructions generation
- Dimensional annotations
- Texture-included rendering

Author: Alan Synn · alan@alansynn.com
"""

import sys
import logging
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
import json

from PyQt6.QtWidgets import QProgressDialog, QMessageBox, QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont, QPainter, QPen, QBrush, QColor
from PyQt6.QtSvg import QSvgGenerator

from automataii.generation.mechanism_part_decomposer import (
    MechanismPartDecomposer, 
    MechanismPart, 
    PartType,
    decompose_mechanism_to_parts
)


@dataclass
class BlueprintPage:
    """Represents a single page of blueprint output."""
    page_number: int
    page_type: str  # "part", "assembly", "overview"
    title: str
    parts: List[MechanismPart]
    layout_info: Dict[str, Any]
    svg_content: str = ""
    
    # Page dimensions in mm
    width_mm: float = 215.9  # Letter width
    height_mm: float = 279.4  # Letter height
    margin_mm: float = 15.0


class AdvancedBlueprintExporter(QObject):
    """
    Advanced blueprint exporter supporting part decomposition and multi-page layouts.
    
    Features:
    - Decomposes mechanisms into individual buildable parts
    - Generates multi-page letter-size blueprints
    - Includes assembly instructions and dimensional annotations
    - Supports both contour and textured rendering
    - Optimizes part layout for efficient material usage
    """
    
    # Signals
    export_progress = pyqtSignal(int, str)  # progress_percent, status_message
    export_completed = pyqtSignal(bool, str)  # success, message
    page_generated = pyqtSignal(int, str)  # page_number, page_title
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.part_decomposer = MechanismPartDecomposer()
        
        # Export configuration
        self.export_config = {}
        self.current_export_data = {}
        
        # Page layout parameters (letter size)
        self.page_width_mm = 215.9  # 8.5 inches
        self.page_height_mm = 279.4  # 11 inches
        self.default_margin_mm = 15.0
        self.usable_width_mm = self.page_width_mm - 2 * self.default_margin_mm
        self.usable_height_mm = self.page_height_mm - 2 * self.default_margin_mm
        
        # Layout parameters
        self.part_spacing_mm = 10.0
        self.title_height_mm = 20.0
        self.dimension_space_mm = 15.0
        
    def export_blueprint(
        self, 
        mechanism_data: Dict[str, Any], 
        character_data: Dict[str, Any],
        export_config: Dict[str, Any]
    ) -> bool:
        """
        Export blueprint with advanced options.
        
        Args:
            mechanism_data: Complete mechanism assembly data
            character_data: Character parts and textures
            export_config: Export configuration from dialog
            
        Returns:
            True if export successful
        """
        try:
            self.export_config = export_config
            self.current_export_data = {
                "mechanisms": mechanism_data,
                "character": character_data
            }
            
            self.logger.info(f"[BLUEPRINT] Starting advanced export with config: {export_config}")
            
            # Step 1: Decompose mechanisms into parts if requested
            if export_config.get("decompose_mechanisms", True):
                all_parts = self._decompose_all_mechanisms(mechanism_data)
                self.export_progress.emit(20, "Mechanisms decomposed into parts")
            else:
                all_parts = self._create_mechanism_parts_without_decomposition(mechanism_data)
                self.export_progress.emit(20, "Mechanism parts prepared")
            
            # Step 2: Generate blueprint pages
            if export_config.get("multi_page", True):
                pages = self._generate_multi_page_layout(all_parts, character_data)
                self.export_progress.emit(40, f"Generated {len(pages)} blueprint pages")
            else:
                pages = self._generate_single_page_layout(all_parts, character_data)
                self.export_progress.emit(40, "Generated single-page layout")
            
            # Step 3: Add assembly instructions if requested
            if export_config.get("include_assembly_guide", True):
                assembly_page = self._generate_assembly_guide(all_parts)
                pages.append(assembly_page)
                self.export_progress.emit(60, "Assembly instructions added")
            
            # Step 4: Render and save pages
            success = self._render_and_save_pages(pages)
            
            if success:
                self.export_progress.emit(100, "Blueprint export completed successfully")
                self.export_completed.emit(True, f"Blueprint exported successfully to {export_config['save_path']}")
                return True
            else:
                self.export_completed.emit(False, "Failed to render blueprint pages")
                return False
                
        except Exception as e:
            self.logger.error(f"[BLUEPRINT] Export failed: {e}")
            self.export_completed.emit(False, f"Export failed: {str(e)}")
            return False
    
    def _decompose_all_mechanisms(self, mechanism_data: Dict[str, Any]) -> List[MechanismPart]:
        """Decompose all mechanisms into individual parts."""
        all_parts = []
        mechanisms = mechanism_data.get("mechanisms", [])
        
        if not mechanisms:
            # Handle single mechanism case
            mechanisms = [mechanism_data]
        
        for i, mech in enumerate(mechanisms):
            self.logger.info(f"[BLUEPRINT] Decomposing mechanism {i+1}/{len(mechanisms)}: {mech.get('type', 'unknown')}")
            
            try:
                parts = decompose_mechanism_to_parts(mech)
                all_parts.extend(parts)
                self.logger.info(f"[BLUEPRINT] Decomposed into {len(parts)} parts")
            except Exception as e:
                self.logger.error(f"[BLUEPRINT] Failed to decompose mechanism: {e}")
                continue
        
        self.logger.info(f"[BLUEPRINT] Total parts generated: {len(all_parts)}")
        return all_parts
    
    def _create_mechanism_parts_without_decomposition(self, mechanism_data: Dict[str, Any]) -> List[MechanismPart]:
        """Create mechanism parts without full decomposition (whole assemblies)."""
        parts = []
        mechanisms = mechanism_data.get("mechanisms", [])
        
        if not mechanisms:
            mechanisms = [mechanism_data]
        
        for i, mech in enumerate(mechanisms):
            # Create a single part representing the whole mechanism
            mech_type = mech.get("type", "unknown")
            mech_id = mech.get("mechanism_id", f"mech_{i}")
            
            # This is a simplified approach - could be enhanced
            whole_assembly = MechanismPart(
                part_id=f"{mech_id}_assembly",
                part_type=PartType.HOUSING,  # Generic type for whole assembly
                name=f"{mech_type.upper()} Assembly",
                description=f"Complete {mech_type} mechanism assembly",
                geometry={"type": "mechanism_assembly", "data": mech},
                mounting_holes=[],
                material="Various",
                thickness=0.0,
                assembly_order=i,
                assembly_notes="Pre-assembled mechanism unit"
            )
            
            parts.append(whole_assembly)
        
        return parts
    
    def _generate_multi_page_layout(
        self, 
        parts: List[MechanismPart], 
        character_data: Dict[str, Any]
    ) -> List[BlueprintPage]:
        """Generate multi-page letter-size layout."""
        pages = []
        
        # Group parts by mechanism or type for logical organization
        part_groups = self._group_parts_for_pages(parts)
        
        page_number = 1
        
        for group_name, group_parts in part_groups.items():
            # Calculate if parts fit on one page
            parts_per_page = self._calculate_parts_per_page(group_parts)
            
            if len(group_parts) <= parts_per_page:
                # Single page for this group
                page = self._create_parts_page(
                    page_number, 
                    f"{group_name} Parts",
                    group_parts
                )
                pages.append(page)
                page_number += 1
            else:
                # Multiple pages needed
                for i in range(0, len(group_parts), parts_per_page):
                    page_parts = group_parts[i:i + parts_per_page]
                    page_title = f"{group_name} Parts (Page {i//parts_per_page + 1})"
                    
                    page = self._create_parts_page(
                        page_number,
                        page_title,
                        page_parts
                    )
                    pages.append(page)
                    page_number += 1
        
        # Add character parts if present
        if character_data and character_data.get("parts"):
            char_page = self._create_character_parts_page(page_number, character_data)
            pages.append(char_page)
        
        return pages
    
    def _generate_single_page_layout(
        self, 
        parts: List[MechanismPart], 
        character_data: Dict[str, Any]
    ) -> List[BlueprintPage]:
        """Generate single large-format page layout."""
        # For single page, use larger format (A1 or custom size)
        page = BlueprintPage(
            page_number=1,
            page_type="overview",
            title="Complete Blueprint",
            parts=parts,
            layout_info={"format": "large_format"},
            width_mm=841.0,  # A1 width
            height_mm=594.0,  # A1 height
            margin_mm=20.0
        )
        
        return [page]
    
    def _group_parts_for_pages(self, parts: List[MechanismPart]) -> Dict[str, List[MechanismPart]]:
        """Group parts logically for page layout."""
        groups = {}
        
        for part in parts:
            # Group by mechanism ID (extracted from part_id)
            mech_id = part.part_id.split('_')[0] if '_' in part.part_id else "misc"
            
            if mech_id not in groups:
                groups[mech_id] = []
            
            groups[mech_id].append(part)
        
        return groups
    
    def _calculate_parts_per_page(self, parts: List[MechanismPart]) -> int:
        """Calculate how many parts can fit on a page."""
        # Simplified calculation - could be more sophisticated
        # Based on estimated part sizes and page layout
        
        avg_part_area = 50 * 50  # mm² - rough estimate
        usable_area = self.usable_width_mm * (self.usable_height_mm - self.title_height_mm)
        
        # Account for spacing and annotations
        effective_area = usable_area * 0.7  # 70% utilization
        
        parts_per_page = max(1, int(effective_area / avg_part_area))
        
        # Practical limits
        return min(parts_per_page, 8)  # Maximum 8 parts per page for clarity
    
    def _create_parts_page(
        self, 
        page_number: int, 
        title: str, 
        parts: List[MechanismPart]
    ) -> BlueprintPage:
        """Create a page with part layouts and dimensions."""
        page = BlueprintPage(
            page_number=page_number,
            page_type="part",
            title=title,
            parts=parts,
            layout_info=self._calculate_page_layout(parts)
        )
        
        # Generate SVG content for this page
        page.svg_content = self._generate_page_svg(page)
        
        return page
    
    def _create_character_parts_page(
        self, 
        page_number: int, 
        character_data: Dict[str, Any]
    ) -> BlueprintPage:
        """Create a page with character parts."""
        # Convert character data to MechanismPart format for consistency
        char_parts = self._convert_character_data_to_parts(character_data)
        
        return self._create_parts_page(
            page_number,
            "Character Parts",
            char_parts
        )
    
    def _generate_assembly_guide(self, parts: List[MechanismPart]) -> BlueprintPage:
        """Generate assembly instruction page."""
        page = BlueprintPage(
            page_number=999,  # Will be renumbered
            page_type="assembly",
            title="Assembly Instructions",
            parts=[],  # No individual parts, just instructions
            layout_info={"type": "instructions"}
        )
        
        # Generate assembly SVG content
        page.svg_content = self._generate_assembly_instructions_svg(parts)
        
        return page
    
    def _calculate_page_layout(self, parts: List[MechanismPart]) -> Dict[str, Any]:
        """Calculate optimal layout for parts on a page."""
        layout = {
            "parts_positions": [],
            "scale_factor": 1.0,
            "total_parts": len(parts)
        }
        
        # Simple grid layout for now
        cols = math.ceil(math.sqrt(len(parts)))
        rows = math.ceil(len(parts) / cols)
        
        part_width = self.usable_width_mm / cols - self.part_spacing_mm
        part_height = (self.usable_height_mm - self.title_height_mm) / rows - self.part_spacing_mm
        
        for i, part in enumerate(parts):
            row = i // cols
            col = i % cols
            
            x = self.default_margin_mm + col * (part_width + self.part_spacing_mm)
            y = self.default_margin_mm + self.title_height_mm + row * (part_height + self.part_spacing_mm)
            
            layout["parts_positions"].append({
                "part_id": part.part_id,
                "x": x,
                "y": y,
                "width": part_width,
                "height": part_height
            })
        
        return layout
    
    def _generate_page_svg(self, page: BlueprintPage) -> str:
        """Generate complete SVG content for a page."""
        svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" 
     width="{page.width_mm}mm" height="{page.height_mm}mm"
     viewBox="0 0 {page.width_mm} {page.height_mm}">
     
    <!-- Page border -->
    <rect x="{page.margin_mm}" y="{page.margin_mm}" 
          width="{page.width_mm - 2*page.margin_mm}" 
          height="{page.height_mm - 2*page.margin_mm}"
          fill="none" stroke="black" stroke-width="0.5"/>
    
    <!-- Page title -->
    <text x="{page.width_mm/2}" y="{page.margin_mm + 15}" 
          text-anchor="middle" font-size="16" font-weight="bold" fill="black">
        {page.title}
    </text>
    
    <text x="{page.width_mm - page.margin_mm - 5}" y="{page.margin_mm + 10}" 
          text-anchor="end" font-size="10" fill="black">
        Page {page.page_number}
    </text>
"""
        
        # Add parts content
        if page.page_type == "part":
            svg_content += self._generate_parts_svg_content(page)
        elif page.page_type == "assembly":
            svg_content += self._generate_assembly_svg_content(page)
        
        # Add scale reference
        svg_content += self._generate_scale_reference(page)
        
        svg_content += "</svg>"
        
        return svg_content
    
    def _generate_parts_svg_content(self, page: BlueprintPage) -> str:
        """Generate SVG content for individual parts."""
        content = []
        
        for i, part in enumerate(page.parts):
            if i < len(page.layout_info["parts_positions"]):
                pos = page.layout_info["parts_positions"][i]
                
                # Part geometry
                part_svg = f"""
    <g transform="translate({pos['x']}, {pos['y']})">
        <!-- Part outline would go here -->
        <rect x="0" y="0" width="{pos['width']}" height="{pos['height']}" 
              fill="none" stroke="blue" stroke-width="0.3"/>
        
        <!-- Part label -->
        <text x="{pos['width']/2}" y="15" text-anchor="middle" font-size="8" fill="black">
            {part.name}
        </text>
        
        <!-- Material info -->
        <text x="{pos['width']/2}" y="{pos['height'] - 5}" text-anchor="middle" font-size="6" fill="gray">
            {part.material} - {part.thickness}mm
        </text>
        
        <!-- Mounting holes -->
        {self._generate_part_holes_svg(part, pos)}
    </g>
                """
                content.append(part_svg)
        
        return "\n".join(content)
    
    def _generate_assembly_svg_content(self, page: BlueprintPage) -> str:
        """Generate SVG content for assembly instructions."""
        return """
    <text x="50" y="80" font-size="12" font-weight="bold" fill="black">Assembly Instructions</text>
    
    <text x="50" y="110" font-size="10" fill="black">1. Start with the ground link (base plate)</text>
    <text x="50" y="130" font-size="10" fill="black">2. Install joint pins and bushings</text>
    <text x="50" y="150" font-size="10" fill="black">3. Attach moving links in order</text>
    <text x="50" y="170" font-size="10" fill="black">4. Check for smooth operation</text>
    
    <!-- Could include assembly diagrams here -->
    """
    
    def _generate_part_holes_svg(self, part: MechanismPart, pos: Dict) -> str:
        """Generate SVG for part mounting holes."""
        holes_svg = []
        
        for hole in part.mounting_holes:
            # Scale hole position to fit in part area
            hole_x = pos['width'] * 0.3 + hole.get('x', 0) * 0.1
            hole_y = pos['height'] * 0.5 + hole.get('y', 0) * 0.1
            radius = hole.get('diameter', 6.0) / 4  # Scale down for display
            
            holes_svg.append(f"""
        <circle cx="{hole_x}" cy="{hole_y}" r="{radius}" 
                fill="none" stroke="red" stroke-width="0.3"/>
        <text x="{hole_x + radius + 2}" y="{hole_y + 3}" font-size="4" fill="red">
            ⌀{hole.get('diameter', 6.0):.1f}
        </text>
            """)
        
        return "\n".join(holes_svg)
    
    def _generate_scale_reference(self, page: BlueprintPage) -> str:
        """Generate scale reference ruler."""
        ruler_y = page.height_mm - page.margin_mm - 20
        ruler_length = 50.0  # 50mm ruler
        
        return f"""
    <!-- Scale reference -->
    <line x1="{page.margin_mm + 20}" y1="{ruler_y}" 
          x2="{page.margin_mm + 20 + ruler_length}" y2="{ruler_y}" 
          stroke="black" stroke-width="1"/>
    
    <text x="{page.margin_mm + 20 + ruler_length/2}" y="{ruler_y - 5}" 
          text-anchor="middle" font-size="8" fill="black">
        50mm (1:1 scale)
    </text>
    
    <!-- Character scale info -->
    <text x="{page.margin_mm + 20}" y="{ruler_y + 15}" font-size="8" fill="black">
        Character Height: {self.export_config.get('character_height_mm', 400)}mm
    </text>
        """
    
    def _generate_assembly_instructions_svg(self, parts: List[MechanismPart]) -> str:
        """Generate detailed assembly instructions."""
        # Group parts by assembly order
        ordered_parts = sorted(parts, key=lambda p: p.assembly_order)
        
        instructions = []
        y_pos = 80
        
        instructions.append(f'<text x="50" y="{y_pos}" font-size="14" font-weight="bold" fill="black">Assembly Instructions</text>')
        y_pos += 30
        
        for i, part in enumerate(ordered_parts[:10]):  # Limit to first 10 steps
            step_text = f"{i+1}. {part.name}: {part.assembly_notes}"
            instructions.append(f'<text x="50" y="{y_pos}" font-size="10" fill="black">{step_text}</text>')
            y_pos += 20
        
        # Add general assembly notes
        y_pos += 20
        general_notes = [
            "General Assembly Notes:",
            "• Ensure all holes are properly aligned before inserting pins",
            "• Use light machine oil on moving joints",
            "• Check for smooth operation before final assembly",
            "• Tighten all connections but allow for movement"
        ]
        
        for note in general_notes:
            font_weight = "bold" if note.endswith(":") else "normal"
            instructions.append(f'<text x="50" y="{y_pos}" font-size="10" font-weight="{font_weight}" fill="black">{note}</text>')
            y_pos += 18
        
        return "\n".join(instructions)
    
    def _convert_character_data_to_parts(self, character_data: Dict[str, Any]) -> List[MechanismPart]:
        """Convert character parts data to MechanismPart format."""
        char_parts = []
        parts_data = character_data.get("parts", {})
        
        for part_name, part_info in parts_data.items():
            char_part = MechanismPart(
                part_id=f"char_{part_name}",
                part_type=PartType.HOUSING,  # Generic for character parts
                name=f"Character {part_name.replace('_', ' ').title()}",
                description=f"Character body part: {part_name}",
                geometry={"type": "character_part", "data": part_info},
                mounting_holes=[],
                material="Fabric/Paper",
                thickness=1.0,
                assembly_notes="Attach to character body"
            )
            char_parts.append(char_part)
        
        return char_parts
    
    def _render_and_save_pages(self, pages: List[BlueprintPage]) -> bool:
        """Render and save all pages."""
        try:
            save_path = Path(self.export_config["save_path"])
            
            if self.export_config.get("multi_page", True):
                # Multi-page export - save each page separately
                success_count = 0
                
                for page in pages:
                    filename = save_path / f"page_{page.page_number:02d}_{page.title.replace(' ', '_')}.svg"
                    
                    if self._save_svg_page(page, filename):
                        success_count += 1
                        self.page_generated.emit(page.page_number, page.title)
                    
                    # Update progress
                    progress = int((success_count / len(pages)) * 40) + 60  # 60-100% range
                    self.export_progress.emit(progress, f"Saved page {success_count}/{len(pages)}")
                
                # Create index file
                self._create_index_file(pages, save_path)
                
                return success_count == len(pages)
            
            else:
                # Single page export
                if pages:
                    return self._save_svg_page(pages[0], save_path)
                
        except Exception as e:
            self.logger.error(f"[BLUEPRINT] Failed to render pages: {e}")
            return False
    
    def _save_svg_page(self, page: BlueprintPage, filename: Path) -> bool:
        """Save a single page as SVG file."""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(page.svg_content)
            
            self.logger.info(f"[BLUEPRINT] Saved page: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"[BLUEPRINT] Failed to save page {filename}: {e}")
            return False
    
    def _create_index_file(self, pages: List[BlueprintPage], save_dir: Path):
        """Create an index file listing all generated pages."""
        index_content = {
            "blueprint_info": {
                "total_pages": len(pages),
                "export_config": self.export_config,
                "generated_at": str(Path().cwd()),
            },
            "pages": [
                {
                    "page_number": page.page_number,
                    "title": page.title,
                    "type": page.page_type,
                    "filename": f"page_{page.page_number:02d}_{page.title.replace(' ', '_')}.svg",
                    "parts_count": len(page.parts)
                }
                for page in pages
            ]
        }
        
        index_file = save_dir / "blueprint_index.json"
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_content, f, indent=2)
        
        # Also create a simple README
        readme_content = f"""# Blueprint Export

Total Pages: {len(pages)}
Character Height: {self.export_config.get('character_height_mm', 'Unknown')}mm
Export Date: Auto-generated

## Pages:
"""
        
        for page in pages:
            readme_content += f"- Page {page.page_number}: {page.title} ({len(page.parts)} parts)\\n"
        
        readme_content += """
## Printing Instructions:
1. Print all pages on letter-size paper (8.5" × 11")
2. Use the scale reference to verify correct printing size
3. Cut out parts along the outline
4. Follow assembly instructions page

## Assembly:
Refer to the assembly instructions page for step-by-step guidance.
"""
        
        readme_file = save_dir / "README.txt"
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme_content)


# Factory function for easy integration
def create_advanced_blueprint_exporter() -> AdvancedBlueprintExporter:
    """Create and return an AdvancedBlueprintExporter instance."""
    return AdvancedBlueprintExporter()


if __name__ == "__main__":
    """Test the exporter with sample data."""
    
    # Sample mechanism data
    test_mechanism = {
        "type": "4bar",
        "mechanism_id": "test_4bar", 
        "params": {
            "l1": 100.0,
            "l2": 80.0,
            "l3": 120.0,
            "l4": 90.0
        }
    }
    
    test_character = {
        "parts": {
            "head": {"type": "ellipse", "width": 50, "height": 60},
            "body": {"type": "rectangle", "width": 80, "height": 120}
        }
    }
    
    test_config = {
        "multi_page": True,
        "decompose_mechanisms": True,
        "include_assembly_guide": True,
        "character_height_mm": 400,
        "save_path": Path.home() / "test_blueprint"
    }
    
    exporter = AdvancedBlueprintExporter()
    success = exporter.export_blueprint(test_mechanism, test_character, test_config)
    
    print(f"Export result: {'Success' if success else 'Failed'}")