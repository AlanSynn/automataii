# Blueprint Export Manager - Singleton Pattern Implementation
# Author: Automataii Contributors

import logging
import math
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape as escape_xml
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QWidget

from automataii.application.blueprint import (
    BlueprintComposer,
    BlueprintCompositionResult,
    BlueprintLayoutCompositionResult,
)
from automataii.infrastructure.generation.mechanism.cam import CamGenerator
from automataii.infrastructure.generation.mechanism.gear import GearGenerator
from automataii.infrastructure.generation.mechanism.linkage import LinkageGenerator
from automataii.infrastructure.generation.pdf.svg_pdf import (
    is_valid_pdf_file,
    render_svg_to_pdf,
    render_svgs_to_pdf,
)
from automataii.infrastructure.generation.svg.blueprint import _flatten_embedded_svg
from automataii.shared.physical_kit import (
    DEFAULT_DISPLAY_UNIT_SYSTEM,
    FABRICATION_HOLE_DIAMETER_INCH_LABEL,
    format_length_for_user,
)

CUT_SHEET_PAGE_SIZE_MM = (215.9, 279.4)
CUT_SHEET_MARGIN_MM = 10.0
CUT_SHEET_CONTENT_X_MM = CUT_SHEET_MARGIN_MM + 7.0
CUT_SHEET_CONTENT_Y_MM = 54.0
CUT_SHEET_CONTENT_W_MM = CUT_SHEET_PAGE_SIZE_MM[0] - (CUT_SHEET_MARGIN_MM * 2) - 14.0
CUT_SHEET_CONTENT_H_MM = 172.0
_CUT_SHEET_PAGE_GAP_MM = 8.0
CUT_SHEET_TILE_OVERLAP_MM = 5.0
_SVG_WRAPPER_RE = re.compile(
    r"^\s*(?:<\?xml[^>]*>\s*)?<svg\b(?P<attrs>[^>]*)>(?P<body>.*)</svg>\s*$",
    re.IGNORECASE | re.DOTALL,
)

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
        unit_system: str = DEFAULT_DISPLAY_UNIT_SYSTEM,
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
            unit_system: "imperial" for inches, "metric" for millimeters

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
                # Generate fixed-size printable cut-sheet pages. The previous
                # path emitted one oversized preview SVG and depended on PDF
                # fit-scaling, which made text/parts unreadable or clipped.
                svg_pages = self._generate_printable_cut_sheet_pages(
                    part_items, mechanism_layers or {}, snapshot_png_bytes, unit_system
                )

                if not svg_pages:
                    raise ValueError("Generated SVG content is empty")

                # Save printable pages
                ext = os.path.splitext(file_path)[1].lower()
                actual_path = file_path
                fallback_used = False
                if ext == ".pdf":
                    success = self._save_pdf_pages(svg_pages, file_path)
                    if not success:
                        fallback_svg = os.path.splitext(file_path)[0] + ".svg"
                        self.logger.warning(
                            "PDF export unavailable; writing SVG fallback to %s", fallback_svg
                        )
                        success = self._save_svg_pages(svg_pages, fallback_svg)
                        actual_path = fallback_svg
                        fallback_used = success
                else:
                    success = self._save_svg_pages(svg_pages, file_path)

                if success:
                    self.logger.info("Make-parts cut sheet saved to %s", actual_path)
                    if fallback_used:
                        self.export_completed.emit(
                            True,
                            f"PDF rendering unavailable; SVG fallback saved to {actual_path}",
                        )
                    else:
                        self.export_completed.emit(
                            True,
                            f"Make Parts / Cut Sheets exported successfully:\n{actual_path}",
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
        unit_system: str = DEFAULT_DISPLAY_UNIT_SYSTEM,
        output_format: str = "pdf",
    ) -> BlueprintExportResult:
        """Export blueprint content directly to a caller-chosen path with artifact details.

        This is used by the package-style fabrication export so the caller can
        report the actual cut-sheet artifact. PDF is requested by default, but
        a successful SVG fallback is a valid degraded result.
        """
        try:
            svg_pages = self._generate_printable_cut_sheet_pages(
                part_items, mechanism_layers or {}, snapshot_png_bytes, unit_system
            )
            if not svg_pages:
                raise ValueError("Generated SVG content is empty")

            destination = Path(file_path)
            fmt = str(output_format).strip().lower()
            ext = destination.suffix.lower()
            requested_format = "svg" if fmt == "svg" or ext == ".svg" else "pdf"
            if requested_format == "svg":
                svg_destination = destination.with_suffix(".svg")
                if self._save_svg_pages(svg_pages, str(svg_destination)):
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
            success = self._save_pdf_pages(svg_pages, str(pdf_destination))
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
            if self._save_svg_pages(svg_pages, str(fallback_svg)):
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
        unit_system: str = DEFAULT_DISPLAY_UNIT_SYSTEM,
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
            downloads = Path.home() / "Downloads"
            default_dir = downloads if downloads.is_dir() else Path.home()
            default_path = str(default_dir / default_name)
            filters = (
                "PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)"
                if fmt == "pdf"
                else "SVG Files (*.svg);;PDF Files (*.pdf);;All Files (*)"
            )
            file_path, _ = QFileDialog.getSaveFileName(
                parent_widget,
                "Export Make Parts / Cut Sheets",
                default_path,
                filters,
            )
            return file_path if file_path else None
        except Exception as e:
            self.logger.error(f"File dialog error: {e}")
            return None

    @staticmethod
    def _page_style() -> str:
        return """<style>
      .sheet-bg { fill:#ffffff; }
      .page-border { fill:none; stroke:#111827; stroke-width:0.8; }
      .title { font-family:Arial, Helvetica, sans-serif; font-size:8px; font-weight:700; fill:#111827; }
      .subtitle { font-family:Arial, Helvetica, sans-serif; font-size:4.2px; fill:#374151; }
      .body { font-family:Arial, Helvetica, sans-serif; font-size:3.8px; fill:#374151; }
      .body-strong { font-family:Arial, Helvetica, sans-serif; font-size:4px; font-weight:700; fill:#111827; }
      .tiny { font-family:Arial, Helvetica, sans-serif; font-size:3px; fill:#64748b; }
      .callout { fill:#eff6ff; stroke:#60a5fa; stroke-width:0.55; rx:4; }
      .warning { fill:#fff7ed; stroke:#fb923c; stroke-width:0.6; rx:4; }
      .calibration { fill:none; stroke:#111827; stroke-width:0.65; }
      .calibration-grid { stroke:#cbd5e1; stroke-width:0.25; }
      .part-outline { fill:none; stroke:#111827; stroke-width:0.7; }
      .cutting-path { stroke:#dc2626; stroke-width:0.45; stroke-dasharray:1.5 1.2; fill:none; }
      .pivot-drill-hole { fill:none; stroke:#2563eb; stroke-width:0.55; }
      .drill-hole-label { font-family:Arial, Helvetica, sans-serif; font-size:2.8px; fill:#1d4ed8; }
      .part-label { font-family:Arial, Helvetica, sans-serif; font-size:4.0px; font-weight:700; fill:#111827; }
      .dimension-line { stroke:#64748b; stroke-width:0.35; stroke-dasharray:1.4 1.0; }
      .dimension-text { font-family:Arial, Helvetica, sans-serif; font-size:3.1px; fill:#334155; }
      .manufacturing-note { font-family:Arial, Helvetica, sans-serif; font-size:3px; fill:#475569; }
    </style>"""

    @staticmethod
    def _svg_body(svg_content: str) -> str:
        match = _SVG_WRAPPER_RE.match(svg_content)
        return match.group("body") if match else svg_content

    @staticmethod
    def _clip_defs_from_item_svg(svg_content: object) -> tuple[str, ...]:
        content = str(svg_content or "")
        if "data-clip-def=" not in content:
            return ()
        import html

        start = content.find('data-clip-def="') + len('data-clip-def="')
        end = content.find('"', start)
        if start <= len('data-clip-def="') - 1 or end <= start:
            return ()
        return (html.unescape(content[start:end]),)

    @staticmethod
    def _clean_item_svg(svg_content: object) -> str:
        content = str(svg_content or "")
        if "data-clip-def=" in content:
            start = content.find(' data-clip-def="')
            if start >= 0:
                end = content.find('"', start + len(' data-clip-def="')) + 1
                if end > start:
                    content = content[:start] + content[end:]
        return str(_flatten_embedded_svg(content))

    @staticmethod
    def _item_dimensions(item: object) -> tuple[float, float]:
        bounds = getattr(item, "bounds", None)
        width = BlueprintComposer._positive_finite_float(getattr(bounds, "width", 0.0), 1.0)
        height = BlueprintComposer._positive_finite_float(getattr(bounds, "height", 0.0), 1.0)
        return width, height

    @staticmethod
    def _item_label(item: object, fallback: str) -> str:
        for attr_name in ("name", "label", "part_name"):
            value = getattr(item, attr_name, None)
            if value:
                return str(value)
        return fallback

    @staticmethod
    def _part_tile_grid(item: object) -> tuple[int, int]:
        item_width, item_height = BlueprintExportManager._item_dimensions(item)
        stride_w = max(1.0, CUT_SHEET_CONTENT_W_MM - CUT_SHEET_TILE_OVERLAP_MM)
        stride_h = max(1.0, CUT_SHEET_CONTENT_H_MM - CUT_SHEET_TILE_OVERLAP_MM)
        cols = 1 if item_width <= CUT_SHEET_CONTENT_W_MM else math.ceil(
            (item_width - CUT_SHEET_TILE_OVERLAP_MM) / stride_w
        )
        rows = 1 if item_height <= CUT_SHEET_CONTENT_H_MM else math.ceil(
            (item_height - CUT_SHEET_TILE_OVERLAP_MM) / stride_h
        )
        return max(1, cols), max(1, rows)

    @staticmethod
    def _tile_registration_marks_svg(
        *,
        content_x: float,
        content_y: float,
        content_w: float,
        content_h: float,
        tile_col: int,
        tile_row: int,
        tile_cols: int,
        tile_rows: int,
    ) -> str:
        if tile_cols <= 1 and tile_rows <= 1:
            return ""
        right = content_x + content_w
        bottom = content_y + content_h
        marks = [
            '<g data-tile-registration="true" stroke="#111827" stroke-width="0.35" fill="none">',
            f'<line x1="{content_x - 3:.1f}" y1="{content_y:.1f}" x2="{content_x + 3:.1f}" y2="{content_y:.1f}"/>',
            f'<line x1="{content_x:.1f}" y1="{content_y - 3:.1f}" x2="{content_x:.1f}" y2="{content_y + 3:.1f}"/>',
            f'<line x1="{right - 3:.1f}" y1="{content_y:.1f}" x2="{right + 3:.1f}" y2="{content_y:.1f}"/>',
            f'<line x1="{right:.1f}" y1="{content_y - 3:.1f}" x2="{right:.1f}" y2="{content_y + 3:.1f}"/>',
            f'<line x1="{content_x - 3:.1f}" y1="{bottom:.1f}" x2="{content_x + 3:.1f}" y2="{bottom:.1f}"/>',
            f'<line x1="{content_x:.1f}" y1="{bottom - 3:.1f}" x2="{content_x:.1f}" y2="{bottom + 3:.1f}"/>',
            f'<line x1="{right - 3:.1f}" y1="{bottom:.1f}" x2="{right + 3:.1f}" y2="{bottom:.1f}"/>',
            f'<line x1="{right:.1f}" y1="{bottom - 3:.1f}" x2="{right:.1f}" y2="{bottom + 3:.1f}"/>',
            '</g>',
        ]
        return "\n  ".join(marks)

    def _compose_layout_result(
        self,
        part_items: list[Any],
        mechanism_layers: dict[str, Any],
        *,
        unit_system: str,
    ) -> BlueprintLayoutCompositionResult | None:
        compose_layout = getattr(self._composer, "compose_layout_items", None)
        if not callable(compose_layout):
            return None
        return compose_layout(part_items, mechanism_layers, unit_system=unit_system)

    def _cut_sheet_cover_page_svg(
        self,
        *,
        part_count: int,
        mechanism_count: int,
        total_pages: int,
        notice_lines: Sequence[str] = (),
    ) -> str:
        width, height = CUT_SHEET_PAGE_SIZE_MM
        margin = CUT_SHEET_MARGIN_MM
        calibration_x = 142.0
        calibration_y = 166.0
        calibration_size = 50.8
        grid_lines: list[str] = []
        for offset in (12.7, 25.4, 38.1):
            grid_lines.append(
                f'<line x1="{calibration_x + offset}" y1="{calibration_y}" '
                f'x2="{calibration_x + offset}" y2="{calibration_y + calibration_size}" '
                'class="calibration-grid"/>'
            )
            grid_lines.append(
                f'<line x1="{calibration_x}" y1="{calibration_y + offset}" '
                f'x2="{calibration_x + calibration_size}" y2="{calibration_y + offset}" '
                'class="calibration-grid"/>'
            )
        middle_section = (
            '<rect x="18" y="134" width="103" height="96" class="warning"/>'
            '<text x="26" y="149" class="body-strong">What is included</text>'
            f'<text x="26" y="164" class="body">Character body components: {part_count}</text>'
            f'<text x="26" y="178" class="body">Mechanisms in current design: {mechanism_count}</text>'
            f'<text x="26" y="192" class="body">Cut-sheet pages: {total_pages}</text>'
            '<text x="26" y="210" class="body">Fasteners/spacers are assigned in the</text>'
            '<text x="26" y="222" class="body">assembly guide, not duplicated here.</text>'
        )
        if notice_lines:
            rows = []
            for index, line in enumerate(tuple(notice_lines)[:4]):
                rows.append(
                    f'<text x="26" y="{164 + index * 12}" class="body">'
                    f"{escape_xml(str(line))}</text>"
                )
            middle_section = (
                '<rect x="18" y="134" width="103" height="96" class="warning"/>'
                '<text x="26" y="149" class="body-strong">Export notice</text>'
                f'{"".join(rows)}'
            )
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm"
     viewBox="0 0 {width} {height}" data-layout-kind="current-design-cut-sheet-cover">
  <title>Current design cut sheets cover</title>
  <defs>{self._page_style()}</defs>
  <rect width="{width}" height="{height}" class="sheet-bg"/>
  <rect x="{margin}" y="{margin}" width="{width - margin * 2}" height="{height - margin * 2}" class="page-border"/>
  <text x="18" y="25" class="title">Current Design Cut Sheets</text>
  <text x="18" y="34" class="subtitle">Character body component cut sheets + mechanism package handoff</text>
  <rect x="18" y="48" width="180" height="72" class="callout"/>
  <text x="26" y="62" class="body-strong">Print contract</text>
  <text x="26" y="75" class="body">1. Print this file at 100% / actual size. Do not fit-to-page.</text>
  <text x="26" y="88" class="body">2. Cut only the character body pages in this file.</text>
  <text x="26" y="101" class="body">3. Print assembly/kit-parts-to-cut.pdf for fabricated mechanism parts.</text>
  <text x="26" y="114" class="body">4. Follow assembly/assembly-guide.pdf one step card at a time.</text>
  {middle_section}
  <rect x="{calibration_x}" y="{calibration_y}" width="{calibration_size}" height="{calibration_size}" class="calibration"/>
  {''.join(grid_lines)}
  <text x="{calibration_x}" y="{calibration_y - 7}" class="body-strong">2 in calibration square</text>
  <text x="{calibration_x}" y="{calibration_y + calibration_size + 10}" class="tiny">If not 2 in, turn off printer scaling.</text>
  <text x="18" y="{height - 18}" class="tiny">MotionSmith fabrication export · current design cut sheets · page 1 of {total_pages}</text>
</svg>
'''

    def _part_cut_sheet_page_svg(
        self,
        item: object,
        *,
        page_index: int,
        total_pages: int,
        tile_col: int = 0,
        tile_row: int = 0,
        tile_cols: int = 1,
        tile_rows: int = 1,
    ) -> str:
        width, height = CUT_SHEET_PAGE_SIZE_MM
        margin = CUT_SHEET_MARGIN_MM
        item_width, item_height = self._item_dimensions(item)
        label = self._item_label(item, f"Part {page_index - 1}")
        content_x = CUT_SHEET_CONTENT_X_MM
        content_y = CUT_SHEET_CONTENT_Y_MM
        content_w = CUT_SHEET_CONTENT_W_MM
        content_h = CUT_SHEET_CONTENT_H_MM
        is_tiled = tile_cols > 1 or tile_rows > 1
        tile_stride_w = max(1.0, content_w - CUT_SHEET_TILE_OVERLAP_MM)
        tile_stride_h = max(1.0, content_h - CUT_SHEET_TILE_OVERLAP_MM)
        tile_x = tile_col * tile_stride_w
        tile_y = tile_row * tile_stride_h
        if is_tiled:
            part_x = content_x - tile_x
            part_y = content_y - tile_y
        else:
            part_x = content_x + (content_w - item_width) / 2.0
            part_y = content_y + (content_h - item_height) / 2.0
        clean_svg = self._clean_item_svg(getattr(item, "svg_content", ""))
        clip_defs = "\n    ".join(self._clip_defs_from_item_svg(getattr(item, "svg_content", "")))
        tile_index = tile_row * tile_cols + tile_col + 1
        tile_count = tile_cols * tile_rows
        scale_note = "Actual size"
        if is_tiled:
            scale_note = f"Actual size tile {tile_index}/{tile_count}"
        overlap_text = format_length_for_user(
            CUT_SHEET_TILE_OVERLAP_MM,
            include_board_spaces=False,
        )
        tile_note = (
            f"Tile row {tile_row + 1}/{tile_rows}, column {tile_col + 1}/{tile_cols}. "
            f"Print at 100%; align {overlap_text} overlaps and registration marks."
            if is_tiled
            else "Print at 100% / actual size. Do not fit-to-page."
        )
        width_text = format_length_for_user(item_width, include_board_spaces=False)
        height_text = format_length_for_user(item_height, include_board_spaces=False)
        registration_marks = self._tile_registration_marks_svg(
            content_x=content_x,
            content_y=content_y,
            content_w=content_w,
            content_h=content_h,
            tile_col=tile_col,
            tile_row=tile_row,
            tile_cols=tile_cols,
            tile_rows=tile_rows,
        )
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{width}mm" height="{height}mm" viewBox="0 0 {width} {height}"
     data-layout-kind="current-design-part-cut-sheet" data-part-name="{escape_xml(label, quote=True)}"
     data-tile-overlap-mm="{CUT_SHEET_TILE_OVERLAP_MM:.1f}">
  <title>{escape_xml(label)} cut sheet</title>
  <defs>{self._page_style()}
    {clip_defs}
  </defs>
  <rect width="{width}" height="{height}" class="sheet-bg"/>
  <rect x="{content_x}" y="{content_y}" width="{content_w}" height="{content_h}" fill="#ffffff" stroke="none"/>
  <g transform="translate({part_x:.2f},{part_y:.2f}) scale(1.000000)">
    {clean_svg}
  </g>
  <rect x="-1000" y="-1000" width="{width + 2000}" height="{content_y + 999.4}" fill="#ffffff"/>
  <rect x="-1000" y="{content_y - 2}" width="{content_x + 999.4}" height="{content_h + 4}" fill="#ffffff"/>
  <rect x="{content_x + content_w + 0.6}" y="{content_y - 2}" width="1000" height="{content_h + 4}" fill="#ffffff"/>
  <rect x="-1000" y="{content_y + content_h + 0.6}" width="{width + 2000}" height="1000" fill="#ffffff"/>
  <rect x="{margin}" y="{margin}" width="{width - margin * 2}" height="{height - margin * 2}" class="page-border"/>
  <text x="18" y="25" class="title">{escape_xml(label)}</text>
  <text x="18" y="34" class="subtitle">Cut red dashed outline. Drill blue {FABRICATION_HOLE_DIAMETER_INCH_LABEL} pivot holes when shown.</text>
  <text x="{width - 18}" y="25" class="body" text-anchor="end">Page {page_index} of {total_pages}</text>
  <rect x="{content_x}" y="{content_y}" width="{content_w}" height="{content_h}" fill="none" stroke="#cbd5e1" stroke-width="0.45"/>
  {registration_marks}
  <rect x="18" y="238" width="180" height="20" class="callout"/>
  <text x="26" y="250" class="body-strong">{escape_xml(scale_note)}</text>
  <text x="88" y="250" class="body">Part size: {width_text} × {height_text} · holes: {FABRICATION_HOLE_DIAMETER_INCH_LABEL}</text>
  <text x="26" y="256" class="tiny">{escape_xml(tile_note)}</text>
  <text x="18" y="{height - 18}" class="tiny">Mechanism board placement lives in assembly/assembly-guide.pdf · page {page_index} of {total_pages}</text>
</svg>
'''

    def _generate_printable_cut_sheet_pages(
        self,
        part_items: list[Any],
        mechanism_layers: dict[str, Any],
        snapshot_png_bytes: bytes | None = None,
        unit_system: str = DEFAULT_DISPLAY_UNIT_SYSTEM,
    ) -> tuple[str, ...]:
        """Generate fixed-size pages for the current-design cut-sheet package.

        This is intentionally separate from the large overview blueprint. The
        PDF-first package must print cleanly on Letter pages, keep character
        geometry at actual size when possible, and delegate standard mechanism
        parts/board placement to the matching kit PDFs and assembly guide.
        """
        try:
            layout_result = self._compose_layout_result(
                part_items, mechanism_layers, unit_system=unit_system
            )
        except Exception as exc:
            self.logger.exception("Printable cut-sheet layout failed")
            raise RuntimeError("Printable cut-sheet layout failed") from exc
        if layout_result is None:
            raise RuntimeError("Printable cut-sheet layout data is unavailable")

        layout_items = tuple(layout_result.layout_items)
        part_layout_items = tuple(
            item for item in layout_items if getattr(item, "item_type", None) == "part"
        )
        mechanism_count = len(
            tuple(item for item in layout_items if getattr(item, "item_type", None) == "mechanism")
        )
        tile_counts = tuple(
            (item, *self._part_tile_grid(item))
            for item in part_layout_items
        )
        total_pages = 1 + sum(cols * rows for _item, cols, rows in tile_counts)
        pages = [
            self._cut_sheet_cover_page_svg(
                part_count=len(part_layout_items),
                mechanism_count=mechanism_count,
                total_pages=total_pages,
            )
        ]
        page_index = 2
        for item, cols, rows in tile_counts:
            for tile_row in range(rows):
                for tile_col in range(cols):
                    pages.append(
                        self._part_cut_sheet_page_svg(
                            item,
                            page_index=page_index,
                            total_pages=total_pages,
                            tile_col=tile_col,
                            tile_row=tile_row,
                            tile_cols=cols,
                            tile_rows=rows,
                        )
                    )
                    page_index += 1
        return tuple(pages)

    @staticmethod
    def _combine_svg_pages(svg_pages: Sequence[str]) -> str:
        width, height = CUT_SHEET_PAGE_SIZE_MM
        total_height = (height * len(svg_pages)) + (
            _CUT_SHEET_PAGE_GAP_MM * max(0, len(svg_pages) - 1)
        )
        nested: list[str] = []
        for index, page in enumerate(svg_pages):
            body = BlueprintExportManager._svg_body(page)
            y = index * (height + _CUT_SHEET_PAGE_GAP_MM)
            nested.append(
                f'<svg x="0" y="{y:.1f}" width="{width}mm" height="{height}mm" '
                f'viewBox="0 0 {width} {height}">{body}</svg>'
            )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{width}mm" height="{total_height:.1f}mm" '
            f'viewBox="0 0 {width} {total_height:.1f}">'
            f'{"".join(nested)}</svg>\n'
        )

    def _save_svg_pages(self, svg_pages: Sequence[str], file_path: str) -> bool:
        if not svg_pages:
            return False
        svg_content = svg_pages[0] if len(svg_pages) == 1 else self._combine_svg_pages(svg_pages)
        return self._save_svg_file(svg_content, file_path)

    def _save_pdf_pages(self, svg_pages: Sequence[str], file_path: str) -> bool:
        """Render printable SVG pages to PDF atomically."""
        if not svg_pages:
            return False
        if len(svg_pages) == 1:
            # Preserve the older single-page render path for direct callers and
            # tests that monkeypatch render_svg_to_pdf.
            return self._save_pdf_file(svg_pages[0], file_path)
        destination = Path(file_path)
        temp_destination = destination.with_name(
            f".{destination.stem}.tmp{destination.suffix or '.pdf'}"
        )
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if temp_destination.is_file():
                temp_destination.unlink()
            if render_svgs_to_pdf(
                tuple(svg_pages),
                temp_destination,
                page_size_mm=CUT_SHEET_PAGE_SIZE_MM,
                scale_mode="actual-size",
            ) and is_valid_pdf_file(temp_destination):
                temp_destination.replace(destination)
                return True
            if temp_destination.is_file():
                temp_destination.unlink()
            if destination.is_file():
                destination.unlink()
            return False
        except Exception as e:
            self.logger.error("Failed to save PDF pages: %s", e)
            for stale_path in (temp_destination, destination):
                try:
                    if stale_path.is_file():
                        stale_path.unlink()
                except OSError:
                    self.logger.debug("Could not remove stale PDF path %s", stale_path)
            return False

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
            if render_svg_to_pdf(svg_content, temp_destination) and is_valid_pdf_file(
                temp_destination
            ):
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

    def compose_layout_items(
        self,
        part_items: list[Any],
        mechanism_layers: dict[str, Any],
        *,
        unit_system: str = DEFAULT_DISPLAY_UNIT_SYSTEM,
    ) -> BlueprintLayoutCompositionResult:
        """Expose normalized cut-sheet items for fixed-page exporters."""
        return self._composer.compose_layout_items(
            part_items,
            mechanism_layers,
            unit_system=unit_system,
        )

    def compose_single_page(
        self,
        part_items: list[Any],
        mechanism_layers: dict[str, Any],
        *,
        snapshot_png_bytes: bytes | None = None,
        unit_system: str = DEFAULT_DISPLAY_UNIT_SYSTEM,
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
        unit_system: str = DEFAULT_DISPLAY_UNIT_SYSTEM,
    ) -> str:
        """
        Generate single large page blueprint SVG with all parts and mechanisms.

        Args:
            part_items: List of part items to include
            mechanism_layers: Dictionary of mechanism data
            snapshot_png_bytes: Optional snapshot image data
            unit_system: "imperial" for inches, "metric" for millimeters

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
