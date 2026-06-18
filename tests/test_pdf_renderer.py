from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QRectF

from automataii.infrastructure.generation.pdf import svg_pdf
from automataii.infrastructure.generation.pdf.svg_pdf import render_svg_to_pdf, render_svgs_to_pdf

VALID_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60">
  <rect x="5" y="5" width="90" height="50" fill="white" stroke="black"/>
  <text x="10" y="30">PDF smoke</text>
</svg>
"""


def test_render_svg_to_pdf_writes_valid_pdf(tmp_path: Path) -> None:
    target = tmp_path / "smoke.pdf"

    assert render_svg_to_pdf(VALID_SVG, target) is True

    assert target.read_bytes().startswith(b"%PDF-")
    assert target.stat().st_size > 100


def test_render_svgs_to_pdf_rejects_invalid_page_without_partial_output(tmp_path: Path) -> None:
    target = tmp_path / "multi.pdf"

    assert render_svgs_to_pdf((VALID_SVG, "<svg><g>"), target) is False

    assert not target.exists()


def test_render_svgs_to_pdf_returns_false_when_no_sources(tmp_path: Path) -> None:
    target = tmp_path / "empty.pdf"
    target.write_text("stale", encoding="utf-8")

    assert render_svgs_to_pdf((), target) is False

    assert not target.exists()


def test_render_svgs_to_pdf_rejects_failed_second_page(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "multi.pdf"

    def fail_second_page(_writer, _destination, page_number: int) -> bool:
        return page_number != 2

    monkeypatch.setattr(svg_pdf, "_start_new_pdf_page", fail_second_page)

    assert render_svgs_to_pdf((VALID_SVG, VALID_SVG), target) is False

    assert not target.exists()


def test_render_svgs_to_pdf_uses_explicit_fit_target(monkeypatch, tmp_path: Path) -> None:
    """Large SVGs must be fitted to the PDF page, not clipped at the top-left."""

    target = tmp_path / "fitted.pdf"
    seen: dict[str, object] = {}

    class FakeViewBox:
        def isEmpty(self) -> bool:
            return False

        def width(self) -> float:
            return 1200.0

        def height(self) -> float:
            return 900.0

    class FakeRenderer:
        def __init__(self, _data) -> None:
            pass

        def isValid(self) -> bool:
            return True

        def viewBoxF(self) -> FakeViewBox:
            return FakeViewBox()

        def render(self, _painter, target_rect=None) -> None:
            seen["target_rect"] = target_rect

    class FakeWriter:
        def __init__(self, destination: str) -> None:
            self.destination = destination
            seen["destination"] = destination

        def setResolution(self, resolution: int) -> None:
            seen["resolution"] = resolution

        def width(self) -> int:
            return 600

        def height(self) -> int:
            return 800

        def newPage(self) -> bool:
            return True

    class FakePainter:
        def __init__(self, _writer: FakeWriter) -> None:
            pass

        def isActive(self) -> bool:
            return True

        def save(self) -> None:
            pass

        def restore(self) -> None:
            pass

        def end(self) -> None:
            pass

    import PyQt6.QtSvg as qt_svg

    monkeypatch.setattr(svg_pdf, "_ensure_gui_application", lambda: None)
    monkeypatch.setattr(svg_pdf, "QPdfWriter", FakeWriter)
    monkeypatch.setattr(svg_pdf, "QPainter", FakePainter)
    monkeypatch.setattr(svg_pdf, "is_valid_pdf_file", lambda _path: True)
    monkeypatch.setattr(qt_svg, "QSvgRenderer", FakeRenderer)

    assert render_svg_to_pdf(VALID_SVG, target) is True

    target_rect = seen["target_rect"]
    assert isinstance(target_rect, QRectF)
    assert 0.0 < target_rect.x() < 600.0
    assert 0.0 < target_rect.y() < 800.0
    assert 0.0 < target_rect.width() <= 600.0
    assert 0.0 < target_rect.height() <= 800.0
    assert target_rect.right() <= 600.0
    assert target_rect.bottom() <= 800.0
