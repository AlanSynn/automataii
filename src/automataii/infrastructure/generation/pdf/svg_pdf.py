"""Render generated SVG documents into PDF files using Qt backends.

The project already depends on PyQt6, so this module intentionally avoids adding
another PDF/SVG dependency. It is used by both cut-sheet exports and LEGO-style
fabrication assembly packages.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QByteArray, QRectF
from PyQt6.QtGui import QGuiApplication, QPainter, QPdfWriter
from PyQt6.QtWidgets import QApplication

LOGGER = logging.getLogger(__name__)
SvgSource = str | bytes | Path
_PDF_APP: QApplication | None = None


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


def _margin_to_device_units(margin_points: float, resolution: int) -> float:
    """Convert PDF point margins to the device units used by ``QPdfWriter``.

    ``QPdfWriter.width()``/``height()`` are reported in the writer's current
    resolution units, not typographic points. Treating 20 pt as 20 device units
    at 300 DPI left almost no real margin and made clipping harder to spot.
    """
    try:
        points = float(margin_points)
    except (TypeError, ValueError):
        points = 20.0
    try:
        dpi = float(resolution)
    except (TypeError, ValueError):
        dpi = 300.0
    return max(0.0, points) * max(1.0, dpi) / 72.0


def render_svgs_to_pdf(
    svg_sources: Sequence[SvgSource],
    output_path: str | Path,
    *,
    margin_points: float = 20.0,
    resolution: int = 300,
) -> bool:
    """Render one or more SVG sources into a single PDF document.

    Each SVG is scaled to fit one PDF page while preserving aspect ratio. The
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
        renderers: list[tuple[Any, float, float]] = []
        for index, source in enumerate(svg_sources):
            renderer = QSvgRenderer(QByteArray(_source_to_bytes(source)))
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
            renderers.append((renderer, svg_width, svg_height))

        destination.parent.mkdir(parents=True, exist_ok=True)
        writer = QPdfWriter(str(destination))
        writer.setResolution(resolution)
        painter = QPainter(writer)
        if not painter.isActive():
            LOGGER.error("Could not activate PDF painter for %s", destination)
            _unlink_quietly(destination)
            return False
        page_start_failed = False
        try:
            for index, (renderer, svg_width, svg_height) in enumerate(renderers):
                if index > 0 and not _start_new_pdf_page(writer, destination, index + 1):
                    page_start_failed = True
                    break

                page_width = float(writer.width())
                page_height = float(writer.height())
                margin_units = _margin_to_device_units(margin_points, resolution)
                usable_width = max(1.0, page_width - 2.0 * margin_units)
                usable_height = max(1.0, page_height - 2.0 * margin_units)
                scale = min(usable_width / svg_width, usable_height / svg_height)
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


def render_svg_to_pdf(svg_source: SvgSource, output_path: str | Path) -> bool:
    """Render a single SVG source into one PDF file."""
    return render_svgs_to_pdf((svg_source,), output_path)
