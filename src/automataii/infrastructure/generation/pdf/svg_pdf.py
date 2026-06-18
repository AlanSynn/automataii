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

from PyQt6.QtCore import QByteArray
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
        return False

    try:
        from PyQt6.QtSvg import QSvgRenderer
    except Exception as exc:  # pragma: no cover - environment dependent
        LOGGER.warning("QtSvg not available for PDF export: %s", exc)
        return False

    destination = Path(output_path)
    try:
        _ensure_gui_application()
        destination.parent.mkdir(parents=True, exist_ok=True)
        writer = QPdfWriter(str(destination))
        writer.setResolution(resolution)
        painter = QPainter(writer)
        if not painter.isActive():
            LOGGER.error("Could not activate PDF painter for %s", destination)
            return False
        try:
            for index, source in enumerate(svg_sources):
                if index > 0:
                    writer.newPage()
                renderer = QSvgRenderer(QByteArray(_source_to_bytes(source)))
                if not renderer.isValid():
                    LOGGER.error(
                        "SVG renderer failed to load page %s for %s", index + 1, destination
                    )
                    return False

                view_box = renderer.viewBoxF()
                if view_box.isEmpty():
                    size = renderer.defaultSize()
                    svg_width = float(size.width()) or 1.0
                    svg_height = float(size.height()) or 1.0
                else:
                    svg_width = float(view_box.width()) or 1.0
                    svg_height = float(view_box.height()) or 1.0

                page_width = float(writer.width())
                page_height = float(writer.height())
                usable_width = max(1.0, page_width - 2.0 * margin_points)
                usable_height = max(1.0, page_height - 2.0 * margin_points)
                scale = min(usable_width / svg_width, usable_height / svg_height)
                x_offset = margin_points + (usable_width - svg_width * scale) / 2.0
                y_offset = margin_points + (usable_height - svg_height * scale) / 2.0

                painter.save()
                painter.translate(x_offset, y_offset)
                painter.scale(scale, scale)
                renderer.render(painter)
                painter.restore()
        finally:
            painter.end()
        return True
    except Exception as exc:
        LOGGER.error("Failed to render SVG PDF %s: %s", destination, exc)
        return False


def render_svg_to_pdf(svg_source: SvgSource, output_path: str | Path) -> bool:
    """Render a single SVG source into one PDF file."""
    return render_svgs_to_pdf((svg_source,), output_path)
