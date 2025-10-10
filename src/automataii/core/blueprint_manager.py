# Blueprint Export Manager - Singleton Pattern Implementation
# Author: Alan Synn · alan@alansynn.com

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QWidget

from automataii.generation.blueprint import generate_detailed_part_content
from automataii.generation.cam import CamGenerator
from automataii.generation.gear import GearGenerator
from automataii.generation.linkage import LinkageGenerator
from automataii.generation.mechanism_debug import MechanismDebugRenderer
# Multi-page blueprint generation (future feature)
# from automataii.generation.multi_page_blueprint import (
#     MultiPageSVGGenerator,
# )


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
        part_items: list[Any],
        mechanism_layers: dict[str, Any] | None = None,
        parent_widget: QWidget | None = None,
        single_large_page: bool = True,
        snapshot_png_bytes: bytes | None = None,
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
                ext = os.path.splitext(file_path)[1].lower()
                if ext == ".pdf":
                    success = self._save_pdf_file(svg_content, file_path)
                    if not success:
                        fallback_svg = os.path.splitext(file_path)[0] + ".svg"
                        self.logger.warning("PDF export unavailable; writing SVG fallback to %s", fallback_svg)
                        success = self._save_svg_file(svg_content, fallback_svg)
                else:
                    success = self._save_svg_file(svg_content, file_path)

                if success:
                    unit_label = "Imperial" if unit_system == "imperial" else "Metric"
                    self.logger.info(f"Large-format blueprint ({unit_label}) saved to {file_path}")
                    self.export_completed.emit(True, f"Blueprint exported successfully ({unit_label} units)")
                else:
                    self.logger.error("Failed to save blueprint file")
                    self.export_completed.emit(False, "Failed to save blueprint file")

            return success

        except Exception as e:
            self.logger.error(f"Blueprint export failed: {e}")
            self.export_completed.emit(False, f"Export failed: {str(e)}")
            return False

    def _get_save_file_path(self, parent_widget: QWidget | None) -> str | None:
        """Get save file path from user using file dialog."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                parent_widget,
                "Export Blueprint",
                "blueprint.svg",
                "SVG Files (*.svg);;PDF Files (*.pdf);;All Files (*)"
            )
            return file_path if file_path else None
        except Exception as e:
            self.logger.error(f"File dialog error: {e}")
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

    
    def _save_pdf_file(self, svg_content: str, file_path: str) -> bool:
        """Render SVG content into a single-page PDF using Qt backends.

        Returns False if QtSvg is unavailable or rendering fails.
        """
        try:
            from PyQt6.QtGui import QPdfWriter, QPainter
            try:
                from PyQt6.QtSvg import QSvgRenderer
            except Exception as e:
                self.logger.warning(f"QtSvg not available for PDF export: {e}")
                return False

            from PyQt6.QtCore import QByteArray
            data = QByteArray(bytes(svg_content, 'utf-8'))
            renderer = QSvgRenderer(data)
            if not renderer.isValid():
                self.logger.error("SVG renderer failed to load content for PDF export")
                return False

            writer = QPdfWriter(file_path)
            writer.setResolution(300)
            painter = QPainter(writer)

            view_box = renderer.viewBoxF()
            if view_box.isEmpty():
                sz = renderer.defaultSize()
                vw = float(sz.width()) or 1.0
                vh = float(sz.height()) or 1.0
            else:
                vw = float(view_box.width()) or 1.0
                vh = float(view_box.height()) or 1.0

            page_w = float(writer.width())
            page_h = float(writer.height())
            margin = 20.0
            scale_x = (page_w - 2 * margin) / vw
            scale_y = (page_h - 2 * margin) / vh
            scale = min(scale_x, scale_y)

            painter.translate(margin, margin)
            painter.scale(scale, scale)
            renderer.render(painter)
            painter.end()
            return True
        except Exception as e:
            self.logger.error(f"Failed to save PDF file: {e}")
            return False

    def generate_gear_svg(self, gear_data: dict[str, Any]) -> str:
        """Generate SVG for gear mechanism."""
        return self.gear_generator.generate_svg(gear_data)

    def generate_linkage_svg(self, linkage_data: dict[str, Any]) -> str:
        """Generate SVG for linkage mechanism."""
        return self.linkage_generator.generate_svg(linkage_data)

    def generate_cam_svg(self, cam_data: dict[str, Any]) -> str:
        """Generate SVG for cam mechanism."""
        return self.cam_generator.generate_svg(cam_data)

    def _generate_single_large_page_blueprint(
        self,
        part_items: List[Any],
        mechanism_layers: Dict[str, Any],
        snapshot_png_bytes: Optional[bytes] = None,
        unit_system: str = "metric",
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
            from automataii.generation.blueprint import generate_single_large_blueprint
            from automataii.generation.blueprint_optimizer import BlueprintLayoutOptimizer

            self.logger.info(
                "Starting blueprint generation with %s parts and %s mechanisms",
                len(part_items),
                len(mechanism_layers),
            )

            # Log mechanism details
            for mech_id, mech_data in mechanism_layers.items():
                self.logger.info(
                    "Mechanism %s: type=%s, has_params=%s, has_scale=%s",
                    mech_id,
                    mech_data.get("type", "unknown"),
                    bool(mech_data.get("params")),
                    bool(mech_data.get("total_scale_factor")),
                )

            # Optimize layout with enhanced mechanism processing
            optimizer = BlueprintLayoutOptimizer(target_character_height_mm=300.0)
            layout_items, total_width_mm, total_height_mm = optimizer.optimize_blueprint_layout(
                part_items, mechanism_layers, unit_system
            )

            self.logger.info(
                "Layout optimization complete: %s items, %.1fx%.1fmm",
                len(layout_items),
                total_width_mm,
                total_height_mm,
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

            self.logger.info(
                "Generated blueprint: %s items, %.0fx%.0fmm, units: %s",
                len(layout_items),
                total_width_mm,
                total_height_mm,
                unit_system,
            )
            return svg_content

        except Exception as e:
            self.logger.error("Error generating single large page blueprint: %s", e)
            import traceback

            self.logger.error("Traceback: %s", traceback.format_exc())
            return ""



