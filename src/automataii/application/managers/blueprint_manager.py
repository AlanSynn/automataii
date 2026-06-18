# Blueprint Export Manager - Singleton Pattern Implementation
# Author: Automataii Contributors

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QWidget

from automataii.application.blueprint import BlueprintComposer, BlueprintCompositionResult
from automataii.infrastructure.generation.mechanism.cam import CamGenerator
from automataii.infrastructure.generation.mechanism.gear import GearGenerator
from automataii.infrastructure.generation.mechanism.linkage import LinkageGenerator
from automataii.infrastructure.generation.pdf.svg_pdf import render_svg_to_pdf

# Multi-page blueprint generation (future feature)
# from automataii.generation.multi_page_blueprint import (
#     MultiPageSVGGenerator,
# )


@dataclass(frozen=True, slots=True)
class BlueprintExportResult:
    """Observable result for a package cut-sheet export."""

    success: bool
    requested_format: str
    actual_format: str | None
    path: Path | None
    fallback_path: Path | None = None
    error: str | None = None

    def __bool__(self) -> bool:
        return self.success


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
    _instance: Optional["BlueprintExportManager"] = None
    _initialized: bool = False

    # Signals
    export_started = pyqtSignal()
    export_completed = pyqtSignal(bool, str)  # success, message

    def __new__(cls) -> "BlueprintExportManager":
        if cls._instance is not None:
            return cls._instance
        # Do not cache the PyQt QObject before QObject.__init__ runs. Holding a
        # half-initialized SIP wrapper as the singleton can segfault on macOS.
        instance = super().__new__(cls)
        instance._initialized = False
        return instance

    def __init__(self) -> None:
        if self._initialized:
            return

        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._initialized = True

        # Multi-page state management
        self._current_blueprint_pages: list[str] = []
        self._current_page_index = 0
        self._last_export_base_path = ""

        # Initialize mechanism generators (Factory Pattern)
        self.gear_generator = GearGenerator()
        self.linkage_generator = LinkageGenerator()
        self.cam_generator = CamGenerator()

        # Application-layer blueprint composer replaces legacy optimizer flow.
        self._composer = BlueprintComposer()

        self.logger.debug("BlueprintExportManager singleton initialized")
        type(self)._instance = self

    @classmethod
    def get_instance(cls) -> "BlueprintExportManager":
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
        output_format: str = "pdf",
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
            file_path = self._get_save_file_path(parent_widget, output_format=output_format)
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
                        self.logger.warning(
                            "PDF export unavailable; writing SVG fallback to %s", fallback_svg
                        )
                        success = self._save_svg_file(svg_content, fallback_svg)
                else:
                    success = self._save_svg_file(svg_content, file_path)

                if success:
                    unit_label = "Imperial" if unit_system == "imperial" else "Metric"
                    self.logger.info(f"Large-format blueprint ({unit_label}) saved to {file_path}")
                    self.export_completed.emit(
                        True, f"Blueprint exported successfully ({unit_label} units)"
                    )
                else:
                    self.logger.error("Failed to save blueprint file")
                    self.export_completed.emit(False, "Failed to save blueprint file")

            return success

        except Exception as e:
            self.logger.error(f"Blueprint export failed: {e}")
            self.export_completed.emit(False, f"Export failed: {str(e)}")
            return False

    def export_blueprint_to_path_result(
        self,
        part_items: list[Any],
        mechanism_layers: dict[str, Any] | None,
        file_path: str | Path,
        *,
        snapshot_png_bytes: bytes | None = None,
        unit_system: str = "metric",
        output_format: str = "pdf",
    ) -> BlueprintExportResult:
        """Export blueprint content directly to a caller-chosen path with artifact details.

        This is used by the package-style fabrication export so the caller can
        report the actual cut-sheet artifact. PDF is requested by default, but
        a successful SVG fallback is a valid degraded result.
        """
        try:
            svg_content = self._generate_single_large_page_blueprint(
                part_items, mechanism_layers or {}, snapshot_png_bytes, unit_system
            )
            if not svg_content:
                raise ValueError("Generated SVG content is empty")

            destination = Path(file_path)
            fmt = str(output_format).strip().lower()
            ext = destination.suffix.lower()
            requested_format = "svg" if fmt == "svg" or ext == ".svg" else "pdf"
            if requested_format == "svg":
                svg_destination = destination.with_suffix(".svg")
                if self._save_svg_file(svg_content, str(svg_destination)):
                    self.logger.info("Blueprint package cut sheet saved to %s", svg_destination)
                    return BlueprintExportResult(
                        success=True,
                        requested_format=requested_format,
                        actual_format="svg",
                        path=svg_destination,
                    )
                return BlueprintExportResult(
                    success=False,
                    requested_format=requested_format,
                    actual_format=None,
                    path=None,
                    error=f"Failed to save SVG cut sheet to {svg_destination}",
                )

            pdf_destination = destination.with_suffix(".pdf")
            success = self._save_pdf_file(svg_content, str(pdf_destination))
            if success:
                self.logger.info("Blueprint package cut sheet saved to %s", pdf_destination)
                return BlueprintExportResult(
                    success=True,
                    requested_format=requested_format,
                    actual_format="pdf",
                    path=pdf_destination,
                )
            fallback_svg = destination.with_suffix(".svg")
            self.logger.warning(
                "PDF package cut-sheet export unavailable; writing SVG fallback to %s",
                fallback_svg,
            )
            if self._save_svg_file(svg_content, str(fallback_svg)):
                return BlueprintExportResult(
                    success=True,
                    requested_format=requested_format,
                    actual_format="svg",
                    path=fallback_svg,
                    fallback_path=fallback_svg,
                    error="PDF rendering unavailable; SVG fallback generated",
                )
            return BlueprintExportResult(
                success=False,
                requested_format=requested_format,
                actual_format=None,
                path=None,
                error="Failed to render PDF and failed to save SVG fallback",
            )
        except Exception as e:
            self.logger.error(f"Blueprint export to path failed: {e}")
            return BlueprintExportResult(
                success=False,
                requested_format=str(output_format).strip().lower() or "pdf",
                actual_format=None,
                path=None,
                error=str(e),
            )

    def export_blueprint_to_path(
        self,
        part_items: list[Any],
        mechanism_layers: dict[str, Any] | None,
        file_path: str | Path,
        *,
        snapshot_png_bytes: bytes | None = None,
        unit_system: str = "metric",
        output_format: str = "pdf",
    ) -> bool:
        """Export blueprint content directly to a caller-chosen path.

        Legacy callers only receive success/failure. Package export callers that
        need the actual PDF/SVG artifact should use
        :meth:`export_blueprint_to_path_result`.
        """
        return bool(
            self.export_blueprint_to_path_result(
                part_items=part_items,
                mechanism_layers=mechanism_layers,
                file_path=file_path,
                snapshot_png_bytes=snapshot_png_bytes,
                unit_system=unit_system,
                output_format=output_format,
            )
        )

    def _get_save_file_path(
        self,
        parent_widget: QWidget | None,
        *,
        output_format: str = "pdf",
    ) -> str | None:
        """Get save file path from user using file dialog."""
        try:
            fmt = str(output_format).strip().lower()
            if fmt not in {"pdf", "svg"}:
                fmt = "pdf"
            default_name = (
                "current-design-cut-sheets.pdf" if fmt == "pdf" else "current-design-cut-sheets.svg"
            )
            filters = (
                "PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)"
                if fmt == "pdf"
                else "SVG Files (*.svg);;PDF Files (*.pdf);;All Files (*)"
            )
            file_path, _ = QFileDialog.getSaveFileName(
                parent_widget,
                "Export Make Parts / Cut Sheets",
                default_name,
                filters,
            )
            return file_path if file_path else None
        except Exception as e:
            self.logger.error(f"File dialog error: {e}")
            return None

    def _save_svg_file(self, svg_content: str, file_path: str) -> bool:
        """Save SVG content to file."""
        try:
            # Ensure directory exists
            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(svg_content)

            return True
        except Exception as e:
            self.logger.error(f"Failed to save SVG file: {e}")
            return False

    def _save_pdf_file(self, svg_content: str, file_path: str) -> bool:
        """Render SVG content into a single-page PDF using Qt backends.

        Returns False if QtSvg is unavailable or rendering fails.
        """
        destination = Path(file_path)
        temp_destination = destination.with_name(
            f".{destination.stem}.tmp{destination.suffix or '.pdf'}"
        )
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if temp_destination.is_file():
                temp_destination.unlink()
            if render_svg_to_pdf(svg_content, temp_destination):
                temp_destination.replace(destination)
                return True
            if temp_destination.is_file():
                temp_destination.unlink()
            if destination.is_file():
                destination.unlink()
            return False
        except Exception as e:
            self.logger.error("Failed to save PDF file: %s", e)
            for stale_path in (temp_destination, destination):
                try:
                    if stale_path.is_file():
                        stale_path.unlink()
                except OSError:
                    self.logger.debug("Could not remove stale PDF path %s", stale_path)
            return False

    def generate_gear_svg(self, gear_data: dict[str, Any]) -> str:
        """Generate SVG for gear mechanism."""
        return str(self.gear_generator.generate_svg(gear_data))

    def generate_linkage_svg(self, linkage_data: dict[str, Any]) -> str:
        """Generate SVG for linkage mechanism."""
        return str(self.linkage_generator.generate_svg(linkage_data))

    def generate_cam_svg(self, cam_data: dict[str, Any]) -> str:
        """Generate SVG for cam mechanism."""
        return str(self.cam_generator.generate_svg(cam_data))

    def compose_single_page(
        self,
        part_items: list[Any],
        mechanism_layers: dict[str, Any],
        *,
        snapshot_png_bytes: bytes | None = None,
        unit_system: str = "metric",
    ) -> BlueprintCompositionResult:
        """Compose a single-page blueprint using the shared composer."""
        return self._composer.compose_single_page(
            part_items,
            mechanism_layers,
            unit_system=unit_system,
            snapshot_png_bytes=snapshot_png_bytes,
        )

    def _generate_single_large_page_blueprint(
        self,
        part_items: list[Any],
        mechanism_layers: dict[str, Any],
        snapshot_png_bytes: bytes | None = None,
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
            mechanism_layers = mechanism_layers or {}
            part_count = len(part_items)
            mechanism_count = len(mechanism_layers)

            self.logger.info(
                "Composing blueprint via BlueprintComposer (parts=%s, mechanisms=%s, unit=%s)",
                part_count,
                mechanism_count,
                unit_system,
            )

            result = self.compose_single_page(
                part_items,
                mechanism_layers,
                unit_system=unit_system,
                snapshot_png_bytes=snapshot_png_bytes,
            )

            self.logger.info(
                "Blueprint composed (%s items, %.1fx%.1fmm)",
                result.item_count,
                result.width_mm,
                result.height_mm,
            )
            return str(result.svg)

        except Exception as e:
            self.logger.error("Error generating single large page blueprint: %s", e)
            import traceback

            self.logger.error("Traceback: %s", traceback.format_exc())
            return ""
