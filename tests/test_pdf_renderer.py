from __future__ import annotations

from pathlib import Path

import pytest
from pdf_helpers import ensure_qapp, nonwhite_bbox, pdf_page_sizes_mm, render_pdf_page
from PyQt6.QtCore import QByteArray, QRectF, QSize, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

from automataii.infrastructure.generation.pdf import svg_pdf
from automataii.infrastructure.generation.pdf.svg_pdf import render_svg_to_pdf, render_svgs_to_pdf

VALID_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60">
  <rect x="5" y="5" width="90" height="50" fill="white" stroke="black"/>
  <text x="10" y="30">PDF smoke</text>
</svg>
"""

PARITY_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="360mm" height="240mm" viewBox="0 0 360 240">
  <rect x="0" y="0" width="360" height="240" fill="white"/>
  <rect x="8" y="8" width="344" height="224" fill="none" stroke="black" stroke-width="4"/>
  <rect x="18" y="18" width="42" height="42" fill="#ef4444"/>
  <rect x="300" y="18" width="42" height="42" fill="#22c55e"/>
  <rect x="18" y="180" width="42" height="42" fill="#3b82f6"/>
  <rect x="300" y="180" width="42" height="42" fill="#f59e0b"/>
  <circle cx="180" cy="120" r="38" fill="none" stroke="#111827" stroke-width="5"/>
  <path d="M80 120 L145 85 L215 155 L280 120" fill="none" stroke="#7c3aed" stroke-width="6"/>
  <text x="180" y="210" font-size="24" text-anchor="middle" font-family="Arial">LEGO-style PDF parity</text>
</svg>
"""


def _svg_size(renderer: QSvgRenderer) -> tuple[float, float]:
    view_box = renderer.viewBoxF()
    if not view_box.isEmpty():
        return float(view_box.width()) or 1.0, float(view_box.height()) or 1.0
    default_size = renderer.defaultSize()
    return float(default_size.width()) or 1.0, float(default_size.height()) or 1.0


def _render_svg_like_pdf(svg: str, size: QSize) -> QImage:
    ensure_qapp()
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    assert renderer.isValid()
    svg_width, svg_height = _svg_size(renderer)
    image = QImage(size, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    margin = 0.0
    usable_width = max(1.0, float(size.width()) - 2.0 * margin)
    usable_height = max(1.0, float(size.height()) - 2.0 * margin)
    scale = min(usable_width / svg_width, usable_height / svg_height)
    target_width = max(1.0, svg_width * scale)
    target_height = max(1.0, svg_height * scale)
    target = QRectF(
        margin + (usable_width - target_width) / 2.0,
        margin + (usable_height - target_height) / 2.0,
        target_width,
        target_height,
    )
    painter = QPainter(image)
    renderer.render(painter, target)
    painter.end()
    return image


def _has_color(image: QImage, expected: tuple[int, int, int], *, tolerance: int = 32) -> bool:
    red, green, blue = expected
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if (
                abs(color.red() - red) <= tolerance
                and abs(color.green() - green) <= tolerance
                and abs(color.blue() - blue) <= tolerance
            ):
                return True
    return False


def test_render_svg_to_pdf_writes_valid_pdf(tmp_path: Path) -> None:
    target = tmp_path / "smoke.pdf"

    assert render_svg_to_pdf(VALID_SVG, target) is True

    assert target.read_bytes().startswith(b"%PDF-")
    assert target.stat().st_size > 100


def test_render_svg_to_pdf_visually_matches_svg_fit(tmp_path: Path) -> None:
    target = tmp_path / "parity.pdf"

    assert render_svg_to_pdf(PARITY_SVG, target) is True

    pdf_image = render_pdf_page(target)
    svg_image = _render_svg_like_pdf(PARITY_SVG, pdf_image.size())
    pdf_bbox, pdf_count = nonwhite_bbox(pdf_image)
    svg_bbox, svg_count = nonwhite_bbox(svg_image)

    for sentinel in ((239, 68, 68), (34, 197, 94), (59, 130, 246), (245, 158, 11)):
        assert _has_color(svg_image, sentinel), sentinel
        assert _has_color(pdf_image, sentinel), sentinel
    assert all(
        abs(actual - expected) <= 16 for actual, expected in zip(pdf_bbox, svg_bbox, strict=True)
    )
    assert 0.75 <= pdf_count / svg_count <= 1.25
    assert pdf_bbox[0] > 1
    assert pdf_bbox[1] > 1
    assert pdf_bbox[2] < pdf_image.width() - 2
    assert pdf_bbox[3] < pdf_image.height() - 2


def test_render_svg_to_pdf_preserves_source_physical_page_size(tmp_path: Path) -> None:
    target = tmp_path / "gear.pdf"

    assert render_svg_to_pdf(Path("fabrication/gears/gear-8t.svg"), target) is True

    ensure_qapp()
    qt_pdf = pytest.importorskip("PyQt6.QtPdf")
    document = qt_pdf.QPdfDocument(None)
    document.load(str(target))
    page_size = document.pagePointSize(0)
    assert page_size.width() == pytest.approx(39.0 * 72.0 / 25.4, abs=1.0)
    assert page_size.height() == pytest.approx(49.0 * 72.0 / 25.4, abs=1.0)


def test_render_svg_to_pdf_can_fit_guides_on_standard_print_pages(tmp_path: Path) -> None:
    target = tmp_path / "guide.pdf"

    assert render_svg_to_pdf(PARITY_SVG, target, page_size_mm=(210.0, 297.0)) is True

    width_mm, height_mm = pdf_page_sizes_mm(target)[0]
    assert width_mm == pytest.approx(210.0, abs=1.0)
    assert height_mm == pytest.approx(297.0, abs=1.0)
    image = render_pdf_page(target)
    for sentinel in ((239, 68, 68), (34, 197, 94), (59, 130, 246), (245, 158, 11)):
        assert _has_color(image, sentinel), sentinel


def test_render_svg_to_pdf_fit_mode_does_not_clip_large_svg_to_top_left(
    tmp_path: Path,
) -> None:
    target = tmp_path / "large-corners.pdf"
    large_svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="900mm" height="620mm" viewBox="0 0 900 620">
  <rect x="0" y="0" width="900" height="620" fill="white"/>
  <rect x="0" y="0" width="70" height="70" fill="#ef4444"/>
  <rect x="830" y="0" width="70" height="70" fill="#22c55e"/>
  <rect x="0" y="550" width="70" height="70" fill="#3b82f6"/>
  <rect x="830" y="550" width="70" height="70" fill="#f59e0b"/>
  <rect x="12" y="12" width="876" height="596" fill="none" stroke="#111827" stroke-width="12"/>
</svg>
"""

    assert render_svg_to_pdf(large_svg, target, page_size_mm=(215.9, 279.4)) is True

    image = render_pdf_page(target, size=QSize(768, 994))
    for sentinel in ((239, 68, 68), (34, 197, 94), (59, 130, 246), (245, 158, 11)):
        assert _has_color(image, sentinel), sentinel
    bbox, _count = nonwhite_bbox(image)
    assert bbox[0] > 1
    assert bbox[1] > image.height() * 0.20
    assert bbox[2] < image.width() - 2
    assert bbox[3] < image.height() * 0.80


def test_render_svg_to_pdf_can_center_actual_size_parts_on_print_pages(tmp_path: Path) -> None:
    target = tmp_path / "small-part.pdf"
    small_svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 20 10">
  <rect x="1" y="1" width="18" height="8" fill="#111827"/>
</svg>
"""

    assert (
        render_svg_to_pdf(small_svg, target, page_size_mm=(210.0, 297.0), scale_mode="actual-size")
        is True
    )

    width_mm, height_mm = pdf_page_sizes_mm(target)[0]
    assert width_mm == pytest.approx(210.0, abs=1.0)
    assert height_mm == pytest.approx(297.0, abs=1.0)
    image = render_pdf_page(target)
    bbox, _count = nonwhite_bbox(image)
    assert bbox[0] > image.width() * 0.40
    assert bbox[1] > image.height() * 0.45
    assert (bbox[2] - bbox[0]) / image.width() < 0.15
    assert (bbox[3] - bbox[1]) / image.height() < 0.15


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

        def setPageSize(self, page_size) -> None:
            seen["page_size"] = page_size

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
    assert 0.0 <= target_rect.x() < 600.0
    assert 0.0 <= target_rect.y() < 800.0
    assert 0.0 < target_rect.width() <= 600.0
    assert 0.0 < target_rect.height() <= 800.0
    assert target_rect.right() <= 600.0
    assert target_rect.bottom() <= 800.0
