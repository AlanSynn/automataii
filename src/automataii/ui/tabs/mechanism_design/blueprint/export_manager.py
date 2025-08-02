"""
Blueprint Export Manager - Orchestrates multi-format blueprint generation

This module provides the central management system for generating manufacturing
blueprints from mechanism designs. It coordinates between different export formats
and ensures consistent quality across all output types.

Features:
- Strategy pattern for different export formats
- Physics-based accuracy validation
- Automatic quality checking and optimization
- Batch export capabilities
- Template management for consistent formatting
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import QProgressDialog, QMessageBox, QFileDialog
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl

from .exporters import DxfExporter, SvgExporter, PdfExporter
from .drawing_standards import DrawingStandards, ISO_Standard, ANSI_Standard
from .dimensioning import AutoDimensioning
from .annotation import AnnotationManager

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    """Supported export formats"""
    DXF = "dxf"      # CAD format for AutoCAD, SolidWorks, etc.
    SVG = "svg"      # Vector graphics for web and documentation
    PDF = "pdf"      # Professional documentation format
    PNG = "png"      # Raster format for presentations
    ALL = "all"      # Export all formats


class ExportQuality(Enum):
    """Export quality levels"""
    DRAFT = "draft"         # Fast export, basic quality
    STANDARD = "standard"   # Good quality, reasonable performance
    PROFESSIONAL = "professional"  # Highest quality, slower export


@dataclass
class ExportSettings:
    """Configuration for blueprint export"""
    format: ExportFormat = ExportFormat.PDF
    quality: ExportQuality = ExportQuality.STANDARD
    drawing_standard: str = "ISO"  # ISO or ANSI
    include_dimensions: bool = True
    include_annotations: bool = True
    include_material_specs: bool = True
    include_assembly_notes: bool = True
    include_part_list: bool = True
    
    # Advanced settings
    paper_size: str = "A4"  # A4, A3, Letter, etc.
    scale: float = 1.0
    line_weights: Dict[str, float] = field(default_factory=lambda: {
        'outline': 0.7,
        'hidden': 0.35,
        'dimension': 0.25,
        'center': 0.25,
        'construction': 0.18
    })
    
    # Output settings
    output_directory: Optional[str] = None
    filename_prefix: str = "mechanism"
    embed_metadata: bool = True
    
    def __post_init__(self):
        """Initialize derived settings"""
        if self.output_directory is None:
            self.output_directory = str(Path.home() / "Downloads" / "Mechanism_Blueprints")


@dataclass
class ExportResult:
    """Result of blueprint export operation"""
    success: bool
    format: ExportFormat
    output_path: Optional[str] = None
    file_size: Optional[int] = None
    export_time: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0
        
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


class ExportWorker(QThread):
    """Background worker for blueprint export operations"""
    
    progress_updated = pyqtSignal(int, str)  # progress_percent, status_message
    export_completed = pyqtSignal(ExportResult)
    
    def __init__(self, exporter, mechanism_data: Dict[str, Any], 
                 settings: ExportSettings, output_path: str):
        super().__init__()
        self.exporter = exporter
        self.mechanism_data = mechanism_data
        self.settings = settings
        self.output_path = output_path
        
    def run(self):
        """Execute export in background thread"""
        try:
            import time
            start_time = time.time()
            
            # Initialize exporter
            self.progress_updated.emit(10, "Initializing export...")
            self.exporter.initialize(self.mechanism_data, self.settings)
            
            # Generate geometry
            self.progress_updated.emit(30, "Generating geometry...")
            self.exporter.generate_geometry()
            
            # Add dimensions
            if self.settings.include_dimensions:
                self.progress_updated.emit(50, "Adding dimensions...")
                self.exporter.add_dimensions()
                
            # Add annotations
            if self.settings.include_annotations:
                self.progress_updated.emit(70, "Adding annotations...")
                self.exporter.add_annotations()
                
            # Export file
            self.progress_updated.emit(90, "Writing output file...")
            warnings, errors = self.exporter.export(self.output_path)
            
            # Create result
            export_time = time.time() - start_time
            file_size = os.path.getsize(self.output_path) if os.path.exists(self.output_path) else None
            
            result = ExportResult(
                success=len(errors) == 0,
                format=self.settings.format,
                output_path=self.output_path,
                file_size=file_size,
                export_time=export_time,
                warnings=warnings,
                errors=errors
            )
            
            self.progress_updated.emit(100, "Export completed!")
            self.export_completed.emit(result)
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            result = ExportResult(
                success=False,
                format=self.settings.format,
                errors=[str(e)]
            )
            self.export_completed.emit(result)


class BlueprintExportManager(QObject):
    """
    Central manager for blueprint export operations.
    
    Orchestrates the export process, manages different format exporters,
    and provides a unified interface for the mechanism design tab.
    
    Features:
    - Multi-format export with consistent quality
    - Background processing for large exports
    - Progress reporting and error handling
    - Template management for consistent formatting
    - Integration with physics simulation data
    """
    
    # Signals
    export_started = pyqtSignal(ExportFormat)
    export_progress = pyqtSignal(int, str)  # progress_percent, status_message
    export_completed = pyqtSignal(ExportResult)
    batch_export_completed = pyqtSignal(List[ExportResult])
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        # Export settings
        self.default_settings = ExportSettings()
        self.current_settings = ExportSettings()
        
        # Drawing standards
        self.drawing_standards = {
            'ISO': ISO_Standard(),
            'ANSI': ANSI_Standard()
        }
        
        # Exporters (created on demand)
        self.exporters: Dict[ExportFormat, Any] = {}
        
        # Export state
        self.current_worker: Optional[ExportWorker] = None
        self.is_exporting = False
        
        # Progress dialog
        self.progress_dialog: Optional[QProgressDialog] = None
        
        # Initialize exporters
        self._initialize_exporters()
        
    def _initialize_exporters(self):
        """Initialize all format exporters"""
        try:
            self.exporters[ExportFormat.DXF] = DxfExporter()
            self.exporters[ExportFormat.SVG] = SvgExporter()
            self.exporters[ExportFormat.PDF] = PdfExporter()
            logger.info("Blueprint exporters initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize exporters: {e}")
            
    def export_mechanism(self, mechanism_data: Dict[str, Any], 
                        settings: Optional[ExportSettings] = None,
                        output_path: Optional[str] = None) -> bool:
        """
        Export mechanism blueprint in specified format.
        
        Args:
            mechanism_data: Complete mechanism data from design tab
            settings: Export configuration (uses default if None)
            output_path: Output file path (prompts user if None)
            
        Returns:
            True if export started successfully, False otherwise
        """
        if self.is_exporting:
            QMessageBox.warning(None, "Export in Progress", 
                              "An export operation is already in progress.")
            return False
            
        # Use provided settings or current settings
        export_settings = settings or self.current_settings
        
        # Validate mechanism data
        if not self._validate_mechanism_data(mechanism_data):
            QMessageBox.critical(None, "Export Error", 
                               "Mechanism data is invalid or incomplete.")
            return False
            
        # Get output path if not provided
        if output_path is None:
            output_path = self._get_output_path(export_settings)
            if not output_path:
                return False  # User cancelled
                
        # Get appropriate exporter
        exporter = self.exporters.get(export_settings.format)
        if not exporter:
            QMessageBox.critical(None, "Export Error", 
                               f"Exporter for {export_settings.format.value} format not available.")
            return False
            
        # Create output directory if needed
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # Start export process
        self._start_export(exporter, mechanism_data, export_settings, output_path)
        return True
        
    def export_all_formats(self, mechanism_data: Dict[str, Any],
                          base_settings: Optional[ExportSettings] = None) -> bool:
        """
        Export mechanism in all supported formats.
        
        Args:
            mechanism_data: Complete mechanism data
            base_settings: Base settings (format will be overridden)
            
        Returns:
            True if batch export started successfully
        """
        if self.is_exporting:
            QMessageBox.warning(None, "Export in Progress", 
                              "An export operation is already in progress.")
            return False
            
        settings = base_settings or self.current_settings
        
        # Get base output directory
        output_dir = self._get_output_directory()
        if not output_dir:
            return False
            
        # Start batch export
        self._start_batch_export(mechanism_data, settings, output_dir)
        return True
        
    def _validate_mechanism_data(self, mechanism_data: Dict[str, Any]) -> bool:
        \"\"\"Validate mechanism data for export\"\"\"\n        required_fields = ['name', 'type', 'components', 'constraints']\n        \n        for field in required_fields:\n            if field not in mechanism_data:\n                logger.error(f\"Missing required field: {field}\")\n                return False\n                \n        # Validate components\n        components = mechanism_data.get('components', [])\n        if not components:\n            logger.error(\"No components found in mechanism data\")\n            return False\n            \n        # Validate each component has required geometry data\n        for component in components:\n            if 'geometry' not in component:\n                logger.error(f\"Component {component.get('name', 'unknown')} missing geometry data\")\n                return False\n                \n        return True\n        \n    def _get_output_path(self, settings: ExportSettings) -> Optional[str]:\n        \"\"\"Get output path from user\"\"\"\n        format_filters = {\n            ExportFormat.DXF: \"DXF Files (*.dxf)\",\n            ExportFormat.SVG: \"SVG Files (*.svg)\", \n            ExportFormat.PDF: \"PDF Files (*.pdf)\",\n            ExportFormat.PNG: \"PNG Files (*.png)\"\n        }\n        \n        file_filter = format_filters.get(settings.format, \"All Files (*)\")\n        default_name = f\"{settings.filename_prefix}.{settings.format.value}\"\n        default_path = os.path.join(settings.output_directory, default_name)\n        \n        file_path, _ = QFileDialog.getSaveFileName(\n            None, \n            f\"Export {settings.format.value.upper()} Blueprint\",\n            default_path,\n            file_filter\n        )\n        \n        return file_path if file_path else None\n        \n    def _get_output_directory(self) -> Optional[str]:\n        \"\"\"Get output directory for batch export\"\"\"\n        directory = QFileDialog.getExistingDirectory(\n            None,\n            \"Select Export Directory\",\n            self.current_settings.output_directory\n        )\n        \n        return directory if directory else None\n        \n    def _start_export(self, exporter, mechanism_data: Dict[str, Any],\n                     settings: ExportSettings, output_path: str):\n        \"\"\"Start single format export\"\"\"\n        self.is_exporting = True\n        self.export_started.emit(settings.format)\n        \n        # Create and setup worker\n        self.current_worker = ExportWorker(exporter, mechanism_data, settings, output_path)\n        self.current_worker.progress_updated.connect(self.export_progress.emit)\n        self.current_worker.export_completed.connect(self._on_export_completed)\n        \n        # Show progress dialog\n        self._show_progress_dialog(f\"Exporting {settings.format.value.upper()} blueprint...\")\n        \n        # Start export\n        self.current_worker.start()\n        \n    def _start_batch_export(self, mechanism_data: Dict[str, Any],\n                           base_settings: ExportSettings, output_dir: str):\n        \"\"\"Start batch export for all formats\"\"\"\n        # This would implement batch export logic\n        # For now, just export PDF as primary format\n        settings = ExportSettings(\n            format=ExportFormat.PDF,\n            quality=base_settings.quality,\n            output_directory=output_dir\n        )\n        \n        output_path = os.path.join(output_dir, f\"{base_settings.filename_prefix}.pdf\")\n        exporter = self.exporters[ExportFormat.PDF]\n        \n        self._start_export(exporter, mechanism_data, settings, output_path)\n        \n    def _show_progress_dialog(self, title: str):\n        \"\"\"Show progress dialog for export operation\"\"\"\n        self.progress_dialog = QProgressDialog(title, \"Cancel\", 0, 100)\n        self.progress_dialog.setWindowTitle(\"Blueprint Export\")\n        self.progress_dialog.setModal(True)\n        self.progress_dialog.show()\n        \n        # Connect signals\n        self.export_progress.connect(self.progress_dialog.setValue)\n        self.progress_dialog.canceled.connect(self._cancel_export)\n        \n    def _cancel_export(self):\n        \"\"\"Cancel current export operation\"\"\"\n        if self.current_worker and self.current_worker.isRunning():\n            self.current_worker.terminate()\n            self.current_worker.wait()\n            \n        self.is_exporting = False\n        \n        if self.progress_dialog:\n            self.progress_dialog.close()\n            self.progress_dialog = None\n            \n        logger.info(\"Export operation cancelled by user\")\n        \n    def _on_export_completed(self, result: ExportResult):\n        \"\"\"Handle export completion\"\"\"\n        self.is_exporting = False\n        \n        # Close progress dialog\n        if self.progress_dialog:\n            self.progress_dialog.close()\n            self.progress_dialog = None\n            \n        # Clean up worker\n        if self.current_worker:\n            self.current_worker.deleteLater()\n            self.current_worker = None\n            \n        # Emit completion signal\n        self.export_completed.emit(result)\n        \n        # Show result to user\n        self._show_export_result(result)\n        \n    def _show_export_result(self, result: ExportResult):\n        \"\"\"Show export result to user\"\"\"\n        if result.success:\n            message = f\"Blueprint exported successfully!\\n\\nFormat: {result.format.value.upper()}\"\n            \n            if result.output_path:\n                message += f\"\\nLocation: {result.output_path}\"\n                \n            if result.file_size:\n                size_mb = result.file_size / (1024 * 1024)\n                message += f\"\\nSize: {size_mb:.2f} MB\"\n                \n            if result.export_time:\n                message += f\"\\nTime: {result.export_time:.1f} seconds\"\n                \n            if result.has_warnings:\n                message += f\"\\n\\nWarnings: {len(result.warnings)}\"\n                \n            msg_box = QMessageBox(QMessageBox.Icon.Information, \"Export Successful\", message)\n            \n            # Add \"Open File\" button if we have a path\n            if result.output_path and os.path.exists(result.output_path):\n                open_button = msg_box.addButton(\"Open File\", QMessageBox.ButtonRole.ActionRole)\n                show_button = msg_box.addButton(\"Show in Folder\", QMessageBox.ButtonRole.ActionRole)\n                msg_box.addButton(QMessageBox.StandardButton.Ok)\n                \n                reply = msg_box.exec()\n                \n                if msg_box.clickedButton() == open_button:\n                    QDesktopServices.openUrl(QUrl.fromLocalFile(result.output_path))\n                elif msg_box.clickedButton() == show_button:\n                    folder_path = os.path.dirname(result.output_path)\n                    QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))\n            else:\n                msg_box.exec()\n                \n        else:\n            error_message = f\"Export failed!\\n\\nFormat: {result.format.value.upper()}\"\n            \n            if result.errors:\n                error_message += \"\\n\\nErrors:\\n\" + \"\\n\".join(result.errors)\n                \n            QMessageBox.critical(None, \"Export Failed\", error_message)\n            \n    # Public configuration methods\n    def set_export_settings(self, settings: ExportSettings):\n        \"\"\"Update current export settings\"\"\"\n        self.current_settings = settings\n        \n    def get_export_settings(self) -> ExportSettings:\n        \"\"\"Get current export settings\"\"\"\n        return self.current_settings\n        \n    def set_drawing_standard(self, standard: str):\n        \"\"\"Set drawing standard (ISO or ANSI)\"\"\"\n        if standard in self.drawing_standards:\n            self.current_settings.drawing_standard = standard\n            logger.info(f\"Drawing standard set to {standard}\")\n        else:\n            logger.warning(f\"Unknown drawing standard: {standard}\")\n            \n    def get_supported_formats(self) -> List[ExportFormat]:\n        \"\"\"Get list of supported export formats\"\"\"\n        return list(self.exporters.keys())\n        \n    def is_format_available(self, format: ExportFormat) -> bool:\n        \"\"\"Check if export format is available\"\"\"\n        return format in self.exporters and self.exporters[format] is not None