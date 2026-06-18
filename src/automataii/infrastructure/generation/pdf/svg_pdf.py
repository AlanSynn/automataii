"""Render generated SVG documents into PDF files using Qt backends.

The project already depends on PyQt6, so this module intentionally avoids adding
another PDF/SVG dependency. It is used by both cut-sheet exports and LEGO-style
fabrication assembly packages.
"""

from __future__ import annotations

import logging
import math
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from PyQt6.QtCore import QByteArray, QRectF, QSizeF
from PyQt6.QtGui import QGuiApplication, QPageSize, QPainter, QPdfWriter
from PyQt6.QtWidgets import QApplication

LOGGER = logging.getLogger(__name__)
SvgSource = str | bytes | Path
PageScaleMode = Literal["fit", "actual-size"]
_PDF_APP: QApplication | None = None
_SVG_OPEN_RE = re.compile(rb"<svg\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
_SVG_ATTR_RE = re.compile(rb"([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(['\"])(.*?)\2", re.DOTALL)


def _source_to_bytes(source: SvgSource) -> bytes:
    if isinstance(source, bytes):
        return source
    if isinstance(source, Path):
        return source.read_bytes()
    return source.encode("utf-8")


def _ensure_gui_application() -> None:
    """Create a minimal GUI application when rendering outside the running app.

    Qt's SVG text rendering can abort the process if QFontDatabase is touched
    before a QGuiApplication exists. Tests and CLI exports can call this utility
    without a full PyQt application, so create an offscreen app only in that case.
    """
    global _PDF_APP
    if QGuiApplication.instance() is not None:
        return
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _PDF_APP = QApplication(sys.argv[:1])


def is_valid_pdf_file(path: str | Path) -> bool:
    """Return True only for a complete-enough PDF artifact.

    Qt can report success through a mocked or platform-specific renderer while
    leaving an empty/non-PDF file behind. Callers use this tiny guard before
    promoting a temporary file to the user-visible export path.
    """
    pdf_path = Path(path)
    try:
        if not pdf_path.is_file() or pdf_path.stat().st_size < 12:
            return False
        with pdf_path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                return False
            handle.seek(max(0, pdf_path.stat().st_size - 1024))
            return b"%%EOF" in handle.read()
    except OSError:
        return False


def _unlink_quietly(path: Path) -> None:
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        LOGGER.debug("Could not remove failed PDF artifact %s", path)


def _start_new_pdf_page(writer: QPdfWriter, destination: Path, page_number: int) -> bool:
    """Start a new PDF page and keep the failure visible to callers/tests."""
    if writer.newPage():
        return True
    LOGGER.error("Could not create PDF page %s for %s", page_number, destination)
    return False


def _svg_attrs(source: bytes) -> dict[str, str]:
    match = _SVG_OPEN_RE.search(source[:4096])
    if match is None:
        return {}
    attrs: dict[str, str] = {}
    for attr_match in _SVG_ATTR_RE.finditer(match.group("attrs")):
        key = attr_match.group(1).decode("ascii", errors="ignore")
        value = attr_match.group(3).decode("utf-8", errors="ignore")
        attrs[key] = value
    return attrs


def _svg_length_to_mm(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-z%]*)", value)
    if match is None:
        return None
    try:
        number = float(match.group(1))
    except ValueError:
        return None
    if not math.isfinite(number) or number <= 0.0:
        return None
    unit = match.group(2).lower()
    if unit in {"", "mm"}:
        return number
    if unit == "cm":
        return number * 10.0
    if unit == "in":
        return number * 25.4
    if unit == "pt":
        return number * 25.4 / 72.0
    if unit == "px":
        return number * 25.4 / 96.0
    return None


def _source_page_size_mm(source: bytes, svg_width: float, svg_height: float) -> tuple[float, float]:
    attrs = _svg_attrs(source)
    width_mm = _svg_length_to_mm(attrs.get("width"))
    height_mm = _svg_length_to_mm(attrs.get("height"))
    if width_mm is not None and height_mm is not None:
        return width_mm, height_mm
    # Project-generated blueprint SVGs use user units as millimeters when units
    # are omitted. Preserve that physical contract rather than shrinking to A4.
    return max(1.0, svg_width), max(1.0, svg_height)


def _set_writer_page_size(writer: QPdfWriter, width_mm: float, height_mm: float) -> None:
    writer.setPageSize(
        QPageSize(QSizeF(max(1.0, width_mm), max(1.0, height_mm)), QPageSize.Unit.Millimeter)
    )


def render_svgs_to_pdf(
    svg_sources: Sequence[SvgSource],
    output_path: str | Path,
    *,
    margin_points: float = 0.0,
    resolution: int = 300,
    page_size_mm: tuple[float, float] | None = None,
    scale_mode: PageScaleMode = "fit",
) -> bool:
    """Render one or more SVG sources into a single PDF document.

    By default, each SVG gets a PDF page matching its declared physical size. A
    fixed ``page_size_mm`` can be supplied for print-guide PDFs: ``fit`` scales
    the SVG to the page, while ``actual-size`` keeps small cut parts at 1:1 and
    only shrinks when the source is too large for the printable page. The
    function returns ``False`` when QtSvg is unavailable or a renderer cannot
    load the SVG; callers can choose whether to fall back to SVG output.
    """
    if not svg_sources:
        LOGGER.error("PDF export requested with no SVG sources")
        _unlink_quietly(Path(output_path))
        return False

    try:
        from PyQt6.QtSvg import QSvgRenderer
    except Exception as exc:  # pragma: no cover - environment dependent
        LOGGER.warning("QtSvg not available for PDF export: %s", exc)
        return False

    destination = Path(output_path)
    try:
        _ensure_gui_application()

        # Preflight every page before creating/writing the PDF. Without this,
        # a later bad SVG page can leave a partial PDF that looks successful to
        # downstream package export code.
        renderers: list[tuple[Any, float, float, float, float, float, float]] = []
        for index, source in enumerate(svg_sources):
            source_bytes = _source_to_bytes(source)
            renderer = QSvgRenderer(QByteArray(source_bytes))
            if not renderer.isValid():
                LOGGER.error("SVG renderer failed to load page %s for %s", index + 1, destination)
                _unlink_quietly(destination)
                return False

            view_box = renderer.viewBoxF()
            if view_box.isEmpty():
                size = renderer.defaultSize()
                svg_width = float(size.width()) or 1.0
                svg_height = float(size.height()) or 1.0
            else:
                svg_width = float(view_box.width()) or 1.0
                svg_height = float(view_box.height()) or 1.0
            source_width_mm, source_height_mm = _source_page_size_mm(
                source_bytes, svg_width, svg_height
            )
            page_width_mm, page_height_mm = page_size_mm or (source_width_mm, source_height_mm)
            renderers.append(
                (renderer, svg_width, svg_height, source_width_mm, source_height_mm)
                + (page_width_mm, page_height_mm)
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        writer = QPdfWriter(str(destination))
        writer.setResolution(resolution)
        _set_writer_page_size(writer, renderers[0][5], renderers[0][6])
        painter = QPainter(writer)
        if not painter.isActive():
            LOGGER.error("Could not activate PDF painter for %s", destination)
            _unlink_quietly(destination)
            return False
        page_start_failed = False
        try:
            for index, (
                renderer,
                svg_width,
                svg_height,
                source_width_mm,
                source_height_mm,
                page_width_mm,
                page_height_mm,
            ) in enumerate(renderers):
                if index > 0:
                    _set_writer_page_size(writer, page_width_mm, page_height_mm)
                    if not _start_new_pdf_page(writer, destination, index + 1):
                        page_start_failed = True
                        break

                page_width = float(writer.width())
                page_height = float(writer.height())
                margin_units = max(0.0, float(margin_points)) * float(resolution) / 72.0
                usable_width = max(1.0, page_width - 2.0 * margin_units)
                usable_height = max(1.0, page_height - 2.0 * margin_units)
                fit_scale = min(usable_width / svg_width, usable_height / svg_height)
                scale = fit_scale
                if scale_mode == "actual-size" and page_size_mm is not None:
                    units_per_mm_x = page_width / max(1.0, page_width_mm)
                    units_per_mm_y = page_height / max(1.0, page_height_mm)
                    actual_scale = min(
                        (source_width_mm * units_per_mm_x) / svg_width,
                        (source_height_mm * units_per_mm_y) / svg_height,
                    )
                    scale = min(actual_scale, fit_scale)
                target_width = max(1.0, svg_width * scale)
                target_height = max(1.0, svg_height * scale)
                x_offset = margin_units + (usable_width - target_width) / 2.0
                y_offset = margin_units + (usable_height - target_height) / 2.0
                target_rect = QRectF(x_offset, y_offset, target_width, target_height)

                painter.save()
                # Render into an explicit page target. Relying on painter
                # translate/scale plus QSvgRenderer.render(painter) can leave
                # large fabrication SVGs painted at their natural viewport and
                # clipped to the PDF's top-left corner in some Qt backends.
                renderer.render(painter, target_rect)
                painter.restore()
        finally:
            painter.end()
        if page_start_failed:
            _unlink_quietly(destination)
            return False
        if not is_valid_pdf_file(destination):
            LOGGER.error("PDF renderer did not produce a valid PDF at %s", destination)
            _unlink_quietly(destination)
            return False
        return True
    except Exception as exc:
        LOGGER.error("Failed to render SVG PDF %s: %s", destination, exc)
        _unlink_quietly(destination)
        return False


def render_svg_to_pdf(
    svg_source: SvgSource,
    output_path: str | Path,
    *,
    margin_points: float = 0.0,
    resolution: int = 300,
    page_size_mm: tuple[float, float] | None = None,
    scale_mode: PageScaleMode = "fit",
) -> bool:
    """Render a single SVG source into one PDF file."""
    return render_svgs_to_pdf(
        (svg_source,),
        output_path,
        margin_points=margin_points,
        resolution=resolution,
        page_size_mm=page_size_mm,
        scale_mode=scale_mode,
    )
