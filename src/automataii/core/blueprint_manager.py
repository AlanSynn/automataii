# Blueprint Export Manager - Singleton Pattern Implementation
# Author: Alan Synn · alan@alansynn.com

import logging
import os
from typing import Dict, List, Optional, Any
from PyQt6.QtWidgets import QFileDialog, QWidget, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPainterPath

from automataii.generation.blueprint import generate_blueprint_svg, generate_detailed_part_content
from automataii.generation.gear import GearGenerator
from automataii.generation.linkage import LinkageGenerator
from automataii.generation.cam import CamGenerator
from automataii.generation.mechanism_debug import MechanismDebugRenderer
from automataii.generation.blueprint_optimizer import BlueprintLayoutOptimizer
from automataii.generation.multi_page_blueprint import MultiPageBlueprintManager, MultiPageSVGGenerator


class BlueprintExportManager(QObject):
    """
    Singleton manager for blueprint export functionality.

    Coordinates the export of character parts and mechanism components
    to SVG blueprints suitable for fabrication.

    Features:
    - Singleton pattern for centralized management
    - SVG export with file save dialog
    - Support for character parts, gears, linkages, and cams
    - Comprehensive layout with specifications
    """

    # Singleton instance
    _instance: Optional['BlueprintExportManager'] = None

    # Signals
    export_started = pyqtSignal()
    export_completed = pyqtSignal(bool, str)  # success, message

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._initialized = True

        # Multi-page state management
        self._current_blueprint_pages = []
        self._current_page_index = 0
        self._last_export_base_path = ""

        # Initialize mechanism generators (Factory Pattern)
        self.gear_generator = GearGenerator()
        self.linkage_generator = LinkageGenerator()
        self.cam_generator = CamGenerator()

        self.logger.debug("BlueprintExportManager singleton initialized")

    @classmethod
    def get_instance(cls) -> 'BlueprintExportManager':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def export_blueprint(
        self,
        part_items: List[Any],
        mechanism_layers: Optional[Dict[str, Any]] = None,
        parent_widget: Optional[QWidget] = None,
        single_large_page: bool = True,
        snapshot_png_bytes: Optional[bytes] = None,
        unit_system: str = "metric",
    ) -> bool:
        """
        Export blueprint with character parts and mechanisms.

        Args:
            part_items: List of CharacterPartItem objects
            mechanism_layers: Dictionary of mechanism layer data
            parent_widget: Parent widget for dialogs
            single_large_page: Whether to create a single large page or multi-page
            snapshot_png_bytes: Optional snapshot data
            unit_system: "metric" for mm, "imperial" for inches

        Returns:
            bool: True if export successful, False otherwise
        """
        try:
            self.export_started.emit()

            # Get save file path for single large page
            file_path = self._get_save_file_path(parent_widget)
            if not file_path:
                self.logger.debug("Export cancelled by user")
                return False

            # Store base path for multi-page exports
            self._last_export_base_path = file_path

            # Create single large page blueprint
            if single_large_page:
                # Generate single large page with all content
                svg_content = self._generate_single_large_page_blueprint(
                    part_items, mechanism_layers or {}, snapshot_png_bytes, unit_system
                )

                if not svg_content:
                    raise ValueError("Generated SVG content is empty")

                # Save single large page
                success = self._save_svg_file(svg_content, file_path)

                if success:
                    unit_label = "Imperial" if unit_system == "imperial" else "Metric"
                    self.logger.info(f"Large-format blueprint ({unit_label}) saved to {file_path}")
                    self.export_completed.emit(True, f"Blueprint exported successfully ({unit_label} units)")
                else:
                    self.logger.error("Failed to save SVG file")
                    self.export_completed.emit(False, "Failed to save SVG file")

            return success

        except Exception as e:
            self.logger.error(f"Blueprint export failed: {e}")
            self.export_completed.emit(False, f"Export failed: {str(e)}")
            return False

    def _get_save_file_path(self, parent_widget: Optional[QWidget]) -> Optional[str]:
        """Get save file path from user using file dialog."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                parent_widget,
                "Export Blueprint",
                "blueprint.svg",
                "SVG Files (*.svg);;All Files (*)"
            )
            return file_path if file_path else None
        except Exception as e:
            self.logger.error(f"File dialog error: {e}")
            return None

    def _get_save_directory_path(self, parent_widget: Optional[QWidget]) -> Optional[str]:
        """Get save directory path from user using directory dialog."""
        try:
            directory_path = QFileDialog.getExistingDirectory(
                parent_widget,
                "Select Directory for Blueprint Export",
                "",
                QFileDialog.Option.ShowDirsOnly
            )
            return directory_path if directory_path else None
        except Exception as e:
            self.logger.error(f"Directory dialog error: {e}")
            return None

    def _save_svg_file(self, svg_content: str, file_path: str) -> bool:
        """Save SVG content to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(svg_content)

            return True
        except Exception as e:
            self.logger.error(f"Failed to save SVG file: {e}")
            return False

    def generate_gear_svg(self, gear_data: Dict[str, Any]) -> str:
        """Generate SVG for gear mechanism."""
        return self.gear_generator.generate_svg(gear_data)

    def generate_linkage_svg(self, linkage_data: Dict[str, Any]) -> str:
        """Generate SVG for linkage mechanism."""
        return self.linkage_generator.generate_svg(linkage_data)

    def generate_cam_svg(self, cam_data: Dict[str, Any]) -> str:
        """Generate SVG for cam mechanism."""
        return self.cam_generator.generate_svg(cam_data)

    def _generate_single_large_page_blueprint(
        self, part_items: List[Any], mechanism_layers: Dict[str, Any], snapshot_png_bytes: Optional[bytes] = None, unit_system: str = "metric"
    ) -> str:
        """
        Generate single large page blueprint SVG with all parts and mechanisms.
        
        Args:
            part_items: List of part items to include
            mechanism_layers: Dictionary of mechanism data
            snapshot_png_bytes: Optional snapshot image data
            unit_system: "metric" for mm, "imperial" for inches
            
        Returns:
            SVG string for the complete blueprint
        """
        try:
            from automataii.generation.blueprint_optimizer import BlueprintLayoutOptimizer
            from automataii.generation.blueprint import generate_single_large_blueprint

            # Optimize layout with enhanced mechanism processing
            optimizer = BlueprintLayoutOptimizer(target_character_height_mm=300.0)
            layout_items, total_width_mm, total_height_mm = optimizer.optimize_blueprint_layout(
                part_items, mechanism_layers, unit_system
            )

            if not layout_items:
                self.logger.warning("No layout items generated - creating minimal blueprint")
                return '<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg"><text x="50" y="150">No items to export</text></svg>'

            # Convert snapshot to data URI if provided
            snapshot_data_uri = None
            if snapshot_png_bytes:
                import base64
                snapshot_data_uri = f"data:image/png;base64,{base64.b64encode(snapshot_png_bytes).decode()}"

            # Generate blueprint with proper scaling and unit system
            unit_label = "Imperial" if unit_system == "imperial" else "Metric"
            svg_content = generate_single_large_blueprint(
                layout_items,
                max(total_width_mm, 800),  # Minimum width
                max(total_height_mm, 600),  # Minimum height  
                title=f"Character Manufacturing Blueprint ({unit_label})",
                scale_info=f"Character Height: 300mm | Units: {unit_label}",
                snapshot_data_uri=snapshot_data_uri,
                unit_system=unit_system,
            )

            self.logger.info(f"Generated blueprint: {len(layout_items)} items, {total_width_mm:.0f}x{total_height_mm:.0f}mm, units: {unit_system}")
            return svg_content

        except Exception as e:
            self.logger.error(f"Error generating single large page blueprint: {e}")
            return ""

    def export_next_page(self, parent_widget: Optional[QWidget] = None) -> bool:
        """
        Export the next page in the multi-page blueprint sequence.

        Args:
            parent_widget: Parent widget for dialogs

        Returns:
            bool: True if next page exported successfully, False if no more pages
        """
        if not hasattr(self, '_current_blueprint_pages') or not self._current_blueprint_pages:
            self.logger.warning("No multi-page blueprint in progress")
            return False

        # Move to next page
        self._current_page_index += 1

        if self._current_page_index >= len(self._current_blueprint_pages):
            self.logger.info("All pages exported. Multi-page blueprint complete.")
            self.export_completed.emit(True, "All blueprint pages exported successfully!")
            # Reset state
            self._current_blueprint_pages = []
            self._current_page_index = 0
            return False

        try:
            # Generate current page SVG
            svg_generator = MultiPageSVGGenerator()
            current_page = self._current_blueprint_pages[self._current_page_index]
            page_svg = svg_generator._generate_page_svg(current_page)

            # Add navigation info
            total_pages = len(self._current_blueprint_pages)
            current_num = self._current_page_index + 1
            navigation_info = f'''<!-- Multi-Page Blueprint: Page {current_num} of {total_pages} -->
<!-- Current: {current_page.title} -->
<!-- Progress: {current_num}/{total_pages} pages -->
'''

            svg_content = navigation_info + page_svg

            # Determine file path for this page
            if self._last_export_base_path:
                base_path = self._last_export_base_path.replace('.svg', '')
                page_file_path = f"{base_path}_page_{current_num:02d}_{current_page.content_type}.svg"
            else:
                # Use default naming if no previous path
                page_file_path = f"blueprint_page_{current_num:02d}_{current_page.content_type}.svg"

            # Save page
            success = self._save_svg_file(svg_content, page_file_path)

            if success:
                remaining_pages = total_pages - current_num
                self.logger.info(f"Exported page {current_num} of {total_pages}: {current_page.title}")
                if remaining_pages > 0:
                    self.export_completed.emit(True, f"Page {current_num} of {total_pages} saved. {remaining_pages} pages remaining.")
                else:
                    self.export_completed.emit(True, f"Final page {current_num} of {total_pages} saved. Blueprint complete!")
                return True
            else:
                self.logger.error(f"Failed to save page {current_num}")
                self.export_completed.emit(False, f"Failed to save page {current_num}")
                return False

        except Exception as e:
            self.logger.error(f"Error exporting next page: {e}")
            self.export_completed.emit(False, f"Error exporting next page: {str(e)}")
            return False

    def get_blueprint_progress(self) -> Dict[str, Any]:
        """
        Get current progress information for multi-page blueprint.

        Returns:
            Dictionary with progress information
        """
        if not hasattr(self, '_current_blueprint_pages') or not self._current_blueprint_pages:
            return {
                'has_pages': False,
                'current_page': 0,
                'total_pages': 0,
                'progress_text': 'No multi-page blueprint active'
            }

        current_page = self._current_page_index + 1
        total_pages = len(self._current_blueprint_pages)

        return {
            'has_pages': True,
            'current_page': current_page,
            'total_pages': total_pages,
            'progress_text': f"Page {current_page} of {total_pages}",
            'current_page_title': self._current_blueprint_pages[self._current_page_index].title if self._current_page_index < total_pages else "Complete",
            'remaining_pages': total_pages - current_page
        }


class OptimizedBlueprintBuilder:
    """
    Optimized Blueprint Builder with professional layout and scaling
    Uses the new BlueprintLayoutOptimizer for intelligent placement
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def build_optimized_blueprint(self, layout_items: List[Any], total_width_mm: float, total_height_mm: float) -> str:
        """
        Build optimized blueprint with proper layout and scaling

        Args:
            layout_items: List of optimally placed layout items
            total_width_mm: Total blueprint width in millimeters
            total_height_mm: Total blueprint height in millimeters

        Returns:
            Complete SVG blueprint string
        """
        # Add title block space
        title_height = 60
        content_y_offset = title_height + 20

        # Calculate final dimensions
        final_width = max(600, total_width_mm + 40)  # Minimum width with margins
        final_height = total_height_mm + content_y_offset + 40  # Add title and bottom margin

        # Generate title block
        title_block = self._generate_title_block(final_width)

        # Generate optimized content
        content_svg = self._generate_optimized_content(layout_items, content_y_offset)

        # Generate specifications section
        specs_svg = self._generate_specifications_section(final_width, final_height - 100)

        # Combine all sections
        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{final_width:.1f}" height="{final_height:.1f}"
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
      .debug-overlay {{ opacity: 0.7; }}
    </style>
  </defs>

  <!-- Blueprint Border -->
  <rect x="5" y="5" width="{final_width-10:.1f}" height="{final_height-10:.1f}"
        fill="none" stroke="black" stroke-width="2"/>

  <!-- Title Block -->
  {title_block}

  <!-- Optimized Content -->
  {content_svg}

  <!-- Specifications -->
  {specs_svg}
</svg>'''

        # Validate SVG
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(svg_content)
            self.logger.info(f"Generated optimized blueprint: {len(svg_content)} characters, {final_width:.0f}×{final_height:.0f}mm")
        except ET.ParseError as e:
            self.logger.error(f"Generated SVG is not well-formed: {e}")
            return self._generate_error_svg(str(e))

        return svg_content

    def _generate_title_block(self, width: float) -> str:
        """Generate professional title block"""
        return f'''
        <g id="title-block">
            <rect x="10" y="10" width="{width-20:.1f}" height="50"
                  fill="#f8f8f8" stroke="black" stroke-width="2"/>
            <text x="20" y="30" class="section-title" font-size="16">
                Automataii Manufacturing Blueprint - Optimized Layout
            </text>
            <text x="20" y="45" class="manufacturing-note" font-size="10">
                Scale: Normalized to 30cm character height | Professional spacing | All mechanisms supported
            </text>
            <text x="{width-20:.1f}" y="30" class="manufacturing-note" font-size="8" text-anchor="end">
                Generated: {self._get_timestamp()}
            </text>
            <text x="{width-20:.1f}" y="45" class="manufacturing-note" font-size="8" text-anchor="end">
                Automataii Platform v2.0
            </text>
        </g>
        '''

    def _generate_optimized_content(self, layout_items: List[Any], y_offset: float) -> str:
        """Generate optimized content with proper positioning"""
        if not layout_items:
            return '<text x="50" y="100" class="manufacturing-note">No items to display</text>'

        content_groups = []

        # Group items by type for better organization
        parts = [item for item in layout_items if item.item_type == 'part']
        mechanisms = [item for item in layout_items if item.item_type == 'mechanism']

        # Add parts section
        if parts:
            parts_svg = f'''
            <g id="parts-section" transform="translate(0,{y_offset})">
                <text x="20" y="0" class="section-title">Character Parts (30cm Scale)</text>
                <text x="20" y="15" class="manufacturing-note">
                    {len(parts)} parts | Cut RED lines | Material: 3mm Plywood/Acrylic
                </text>
                <g transform="translate(0,25)">
            '''

            for item in parts:
                item_svg = f'''
                    <g transform="translate({item.bounds.x:.1f},{item.bounds.y:.1f})">
                        {item.svg_content}
                    </g>
                '''
                parts_svg += item_svg

            parts_svg += '''    </g>
            </g>'''
            content_groups.append(parts_svg)

        # Add mechanisms section
        if mechanisms:
            # Calculate mechanisms section Y position
            max_part_y = max((item.bounds.y + item.bounds.height for item in parts), default=0)
            mechanisms_y = max_part_y + 50  # Space between sections

            mechanisms_svg = f'''
            <g id="mechanisms-section" transform="translate(0,{y_offset + mechanisms_y})">
                <text x="20" y="0" class="section-title">Mechanisms ({len(mechanisms)} total)</text>
                <text x="20" y="15" class="manufacturing-note">
                    All mechanism types supported | Standard sizes | Assembly ready
                </text>
                <g transform="translate(0,25)">
            '''

            for item in mechanisms:
                item_svg = f'''
                    <g transform="translate({item.bounds.x:.1f},{item.bounds.y - mechanisms_y:.1f})">
                        {item.svg_content}
                    </g>
                '''
                mechanisms_svg += item_svg

            mechanisms_svg += '''    </g>
            </g>'''
            content_groups.append(mechanisms_svg)

        return '\n'.join(content_groups)

    def _generate_specifications_section(self, width: float, y_pos: float) -> str:
        """Generate specifications section"""
        return f'''
        <g id="specifications" transform="translate(0,{y_pos})">
            <rect x="10" y="0" width="{width-20:.1f}" height="80"
                  fill="#f0f0f0" stroke="black" stroke-width="1"/>
            <text x="20" y="20" class="section-title">Manufacturing Specifications</text>
            <text x="20" y="35" class="manufacturing-note">
                • Scale: Character normalized to 30cm height • Units: Millimeters • Tolerance: ±0.1mm
            </text>
            <text x="20" y="48" class="manufacturing-note">
                • Material: 3mm Plywood or Acrylic • Cut Method: Laser/CNC • Assembly: Mechanical fasteners
            </text>
            <text x="20" y="61" class="manufacturing-note">
                • Layout: Optimized non-overlapping • Mechanisms: Standard industrial sizes • Quality: Production ready
            </text>
        </g>
        '''

    def _get_timestamp(self) -> str:
        """Get current timestamp for title block"""
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    def _generate_error_svg(self, error_msg: str) -> str:
        """Generate error SVG when optimization fails"""
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="600" height="400" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="10" width="580" height="380" fill="none" stroke="red" stroke-width="2"/>
  <text x="300" y="100" font-family="Arial" font-size="16" text-anchor="middle" fill="red">
    Blueprint Optimization Error
  </text>
  <text x="300" y="130" font-family="Arial" font-size="12" text-anchor="middle">
    {error_msg[:100]}{'...' if len(error_msg) > 100 else ''}
  </text>
  <text x="300" y="200" font-family="Arial" font-size="10" text-anchor="middle">
    Please check input data and try again
  </text>
</svg>'''


class BlueprintBuilder:
    """
    Builder pattern for constructing complex blueprint layouts.

    Builds comprehensive SVG blueprints with multiple sections:
    - Title block
    - Character parts section
    - Mechanisms section (gears, linkages, cams)
    - Specifications section
    - Fabrication notes section
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sections: List[str] = []
        self.total_width = 0
        self.total_height = 0
        self.current_y = 50  # Start with title block space
        self.padding = 20
        self.section_spacing = 40

    def add_title_block(self) -> 'BlueprintBuilder':
        """Add title block to blueprint."""
        title_svg = f'''
        <g id="title-block">
            <rect x="10" y="10" width="300" height="80" fill="none" stroke="black" stroke-width="2"/>
            <text x="20" y="35" font-family="Arial" font-size="16" font-weight="bold">Automataii Blueprint</text>
            <text x="20" y="55" font-family="Arial" font-size="12">Character Parts & Mechanisms</text>
            <text x="20" y="75" font-family="Arial" font-size="10">Generated with Automataii Platform</text>
        </g>
        '''
        self.sections.append(title_svg)
        self.current_y += 100
        return self

    def add_character_parts_section(self, part_items: List[Any]) -> 'BlueprintBuilder':
        """Add character parts section to blueprint."""
        if not part_items:
            return self

        self.logger.debug(f"Adding {len(part_items)} character parts to blueprint")

        # Generate detailed parts content (no SVG wrapper)
        parts_content = generate_detailed_part_content(part_items, self.padding)

        if parts_content:
            # Wrap in section group with title
            section_svg = f'''
            <g id="character-parts" transform="translate(0,{self.current_y})">
                <text x="20" y="0" font-family="Arial" font-size="14" font-weight="bold">Character Parts - Manufacturing Blueprint</text>
                <text x="20" y="15" font-family="Arial" font-size="10">Cut RED lines | Drill holes as marked | Material: 3mm Plywood/Acrylic</text>
                <g transform="translate(0,30)">
                    {parts_content}
                </g>
            </g>
            '''
            self.sections.append(section_svg)
            self.current_y += 400  # More space for detailed parts

        return self

    def add_mechanisms_section(self, mechanism_layers: Dict[str, Any], export_manager: BlueprintExportManager) -> 'BlueprintBuilder':
        """Add mechanisms section to blueprint with debug validation."""
        if not mechanism_layers:
            self.logger.warning("No mechanism layers provided to blueprint")
            return self

        self.logger.info(f"Adding {len(mechanism_layers)} mechanisms to blueprint with debug validation")

        # Initialize debug renderer
        debug_renderer = MechanismDebugRenderer()

        # Debug mechanism data before processing
        debug_reports = debug_renderer.debug_mechanism_transforms(mechanism_layers)

        # Log debug summary
        debug_summary = debug_renderer.generate_debug_report()
        self.logger.debug(f"Mechanism debug report:\n{debug_summary}")

        # Check for critical issues
        problematic_mechanisms = debug_renderer.get_problematic_mechanisms()
        if problematic_mechanisms:
            self.logger.warning(f"Found {len(problematic_mechanisms)} mechanisms with issues")
            for prob_mech in problematic_mechanisms:
                self.logger.warning(f"Mechanism {prob_mech.mechanism_id}: {len(prob_mech.errors)} errors")

        # Start mechanisms section
        section_svg = f'''
        <g id="mechanisms" transform="translate(0,{self.current_y})">
            <text x="20" y="0" font-family="Arial" font-size="14" font-weight="bold">Mechanisms ({len(mechanism_layers)} total)</text>
            <text x="20" y="15" font-family="Arial" font-size="10">Debug: {len(problematic_mechanisms)} issues found</text>
        '''

        mech_y = 40  # Start below title and debug info
        successful_mechanisms = 0

        for mech_id, layer_data in mechanism_layers.items():
            try:
                mechanism_type = layer_data.get('mechanism_type', 'unknown')
                self.logger.debug(f"Processing mechanism {mech_id} of type {mechanism_type}")

                # Generate mechanism-specific SVG with error handling
                mech_svg = ""
                if mechanism_type == 'gear':
                    mech_svg = export_manager.generate_gear_svg(layer_data)
                elif mechanism_type == 'linkage':
                    mech_svg = export_manager.generate_linkage_svg(layer_data)
                elif mechanism_type == 'cam':
                    mech_svg = export_manager.generate_cam_svg(layer_data)
                else:
                    self.logger.warning(f"Unknown mechanism type: {mechanism_type}")
                    mech_svg = self._generate_placeholder_mechanism_svg(mech_id, mechanism_type, mech_y)

                # Validate generated SVG
                if not mech_svg or not mech_svg.strip():
                    self.logger.warning(f"Empty SVG generated for mechanism {mech_id}")
                    mech_svg = self._generate_error_mechanism_svg(mech_id, "Empty SVG generated", mech_y)
                else:
                    # Add debug visualization if needed
                    debug_info = next((d for d in debug_reports if d.mechanism_id == mech_id), None)
                    if debug_info and debug_info.bounding_box:
                        mech_svg = debug_renderer.render_mechanism_bounds(mech_svg, debug_info)
                        successful_mechanisms += 1
                        self.logger.debug(f"Successfully processed mechanism {mech_id}")
                    else:
                        self.logger.warning(f"No bounding box calculated for mechanism {mech_id}")

                # Add mechanism to section with proper positioning
                position = layer_data.get('position', [0, 0])
                x_offset = float(position[0]) if len(position) > 0 else 0
                y_offset = float(position[1]) if len(position) > 1 else 0

                # Apply reasonable position constraints
                x_offset = max(-200, min(600, x_offset))  # Constrain to reasonable bounds
                y_offset = max(0, min(200, y_offset))

                section_svg += f'''
            <g id="mechanism-{mech_id}" transform="translate({x_offset},{mech_y + y_offset})">
                <!-- Mechanism: {mech_id} ({mechanism_type}) -->
                {mech_svg}
            </g>
                '''

                mech_y += 200  # More space between mechanisms for debug info

            except Exception as e:
                self.logger.error(f"Error processing mechanism {mech_id}: {e}")
                error_svg = self._generate_error_mechanism_svg(mech_id, str(e), mech_y)
                section_svg += f'<g transform="translate(0,{mech_y})">{error_svg}</g>'
                mech_y += 100

        # Add summary information
        section_svg += f'''
            <text x="20" y="{mech_y + 20}" font-family="Arial" font-size="10" fill="green">
                Successfully processed: {successful_mechanisms}/{len(mechanism_layers)} mechanisms
            </text>
        '''

        section_svg += '</g>'
        self.sections.append(section_svg)
        self.current_y += mech_y + 60  # Account for summary text

        self.logger.info(f"Mechanisms section completed: {successful_mechanisms}/{len(mechanism_layers)} successful")
        return self

    def _generate_placeholder_mechanism_svg(self, mech_id: str, mechanism_type: str, y_pos: float) -> str:
        """Generate placeholder SVG for unknown mechanism types"""
        return f'''
        <g class="placeholder-mechanism">
            <rect x="0" y="0" width="150" height="80" fill="#f0f0f0" stroke="#ccc" stroke-width="1"/>
            <text x="75" y="25" font-family="Arial" font-size="12" text-anchor="middle" fill="#666">
                {mech_id}
            </text>
            <text x="75" y="45" font-family="Arial" font-size="10" text-anchor="middle" fill="#999">
                Unknown Type: {mechanism_type}
            </text>
            <text x="75" y="65" font-family="Arial" font-size="8" text-anchor="middle" fill="#999">
                Placeholder
            </text>
        </g>
        '''

    def _generate_error_mechanism_svg(self, mech_id: str, error_msg: str, y_pos: float) -> str:
        """Generate error SVG for failed mechanisms"""
        return f'''
        <g class="error-mechanism">
            <rect x="0" y="0" width="200" height="100" fill="#ffe6e6" stroke="red" stroke-width="1"/>
            <text x="100" y="20" font-family="Arial" font-size="12" text-anchor="middle" fill="red">
                ERROR: {mech_id}
            </text>
            <text x="100" y="40" font-family="Arial" font-size="8" text-anchor="middle" fill="#666">
                {error_msg[:50]}{'...' if len(error_msg) > 50 else ''}
            </text>
            <text x="100" y="60" font-family="Arial" font-size="8" text-anchor="middle" fill="#666">
                Check mechanism data
            </text>
            <text x="100" y="80" font-family="Arial" font-size="8" text-anchor="middle" fill="#666">
                and generator implementation
            </text>
        </g>
        '''

    def add_specifications_section(self) -> 'BlueprintBuilder':
        """Add specifications section to blueprint."""
        specs_svg = f'''
        <g id="specifications" transform="translate(0,{self.current_y})">
            <text x="20" y="0" font-family="Arial" font-size="14" font-weight="bold">Specifications</text>
            <text x="20" y="25" font-family="Arial" font-size="10">Scale: 1:1 (unless otherwise noted)</text>
            <text x="20" y="40" font-family="Arial" font-size="10">Units: Millimeters</text>
            <text x="20" y="55" font-family="Arial" font-size="10">Material: 3mm Plywood or Acrylic</text>
            <text x="20" y="70" font-family="Arial" font-size="10">Tolerance: ±0.1mm</text>
        </g>
        '''
        self.sections.append(specs_svg)
        self.current_y += 90
        return self

    def add_fabrication_notes_section(self) -> 'BlueprintBuilder':
        """Add fabrication notes section to blueprint."""
        notes_svg = f'''
        <g id="fabrication-notes" transform="translate(0,{self.current_y})">
            <text x="20" y="0" font-family="Arial" font-size="14" font-weight="bold">Fabrication Notes</text>
            <text x="20" y="25" font-family="Arial" font-size="10">1. Cut parts using laser cutter or CNC router</text>
            <text x="20" y="40" font-family="Arial" font-size="10">2. Sand all edges smooth</text>
            <text x="20" y="55" font-family="Arial" font-size="10">3. Test fit before final assembly</text>
            <text x="20" y="70" font-family="Arial" font-size="10">4. Use appropriate fasteners for mechanism joints</text>
        </g>
        '''
        self.sections.append(notes_svg)
        self.current_y += 90
        return self

    def _escape_xml_text(self, text: str) -> str:
        """Escape special XML characters in text content."""
        if not isinstance(text, str):
            text = str(text)

        # Replace XML special characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')

        return text

    def build(self) -> str:
        """Build final SVG blueprint."""
        if not self.sections:
            self.logger.warning("No sections added to blueprint")
            return ""

        # Add title block if not already added
        if not any('title-block' in section for section in self.sections):
            self.add_title_block()

        # Calculate final dimensions
        self.total_width = 800  # Fixed width for standard blueprint
        self.total_height = self.current_y + self.padding

        # Clean and combine all sections
        cleaned_sections = []
        for section in self.sections:
            # Comprehensive cleanup of potential XML issues
            cleaned_section = section

            # Fix common XML entity issues
            cleaned_section = cleaned_section.replace('& ', '&amp; ')
            cleaned_section = cleaned_section.replace(' & ', ' &amp; ')

            # Fix any unescaped ampersands not part of entities
            import re
            # Replace & that are not part of valid XML entities
            cleaned_section = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', cleaned_section)

            cleaned_sections.append(cleaned_section)

        # Combine all sections
        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{self.total_width}" height="{self.total_height}"
     xmlns="http://www.w3.org/2000/svg" version="1.1">
  <defs>
    <style>
      .blueprint-text {{ font-family: Arial, sans-serif; }}
      .section-title {{ font-size: 14px; font-weight: bold; }}
      .spec-text {{ font-size: 10px; }}
      .part-outline {{ fill: none; stroke: black; stroke-width: 1.5; }}
      .part-label {{ font-family: Arial, sans-serif; font-size: 10px; font-weight: bold; }}
      .dimension-line {{ stroke: #666; stroke-width: 0.5; stroke-dasharray: 2,2; }}
      .dimension-text {{ font-family: Arial, sans-serif; font-size: 8px; fill: #333; }}
      .cut-line {{ stroke: red; stroke-width: 0.5; stroke-dasharray: 1,1; }}
      .gear-mechanism {{ }}
      .linkage-mechanism {{ }}
      .cam-mechanism {{ }}
      .placeholder-mechanism {{ }}
      .error-mechanism {{ }}
      .debug-overlay {{ opacity: 0.7; }}
      .manufacturing-notes {{ font-size: 7px; }}
    </style>
  </defs>

  <!-- Blueprint Border -->
  <rect x="5" y="5" width="{self.total_width-10}" height="{self.total_height-10}"
        fill="none" stroke="black" stroke-width="2"/>

  <!-- Blueprint Content -->
  {chr(10).join(cleaned_sections)}
</svg>'''

        # Validate the SVG is well-formed XML
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(svg_content)
            self.logger.info(f"Generated valid blueprint SVG: {len(svg_content)} characters")
        except ET.ParseError as e:
            self.logger.error(f"Generated SVG is not well-formed XML: {e}")
            # Return a detailed fallback SVG with debug information
            svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="600" height="400" xmlns="http://www.w3.org/2000/svg" version="1.1">
  <rect x="10" y="10" width="580" height="380" fill="none" stroke="black" stroke-width="2"/>
  <text x="300" y="50" font-family="Arial" font-size="16" text-anchor="middle">Automataii Blueprint</text>
  <text x="300" y="80" font-family="Arial" font-size="12" text-anchor="middle" fill="red">XML Parse Error - Blueprint Generation Failed</text>
  <text x="300" y="120" font-family="Arial" font-size="10" text-anchor="middle">Error: {self._escape_xml_text(str(e))}</text>
  <text x="300" y="150" font-family="Arial" font-size="10" text-anchor="middle">Sections generated: {len(self.sections)}</text>
  <text x="300" y="180" font-family="Arial" font-size="10" text-anchor="middle">Total content length: {len(svg_content)} characters</text>
  <text x="300" y="220" font-family="Arial" font-size="9" text-anchor="middle">This is likely due to special characters in mechanism data.</text>
  <text x="300" y="240" font-family="Arial" font-size="9" text-anchor="middle">Check mechanism definitions and part names for XML-incompatible characters.</text>
</svg>'''

        return svg_content