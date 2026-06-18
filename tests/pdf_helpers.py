from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest
from PyQt6.QtCore import QByteArray, QRectF, QSize, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

_PDF_TEST_APP: QApplication | None = None
MM_PER_POINT = 25.4 / 72.0


def ensure_qapp() -> None:
    global _PDF_TEST_APP
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    _PDF_TEST_APP = app if isinstance(app, QApplication) else QApplication([])


def render_pdf_page(path: Path, page: int = 0, size: QSize | None = None) -> QImage:
    ensure_qapp()
    qt_pdf = pytest.importorskip("PyQt6.QtPdf")
    document = qt_pdf.QPdfDocument(None)
    document.load(str(path))
    assert document.pageCount() > page
    rendered_size = size or document.pagePointSize(page).toSize()
    image = document.render(page, rendered_size)
    assert not image.isNull(), (path, page)
    return cast(QImage, image)


def _svg_source_to_bytes(source: str | Path) -> bytes:
    return source.read_bytes() if isinstance(source, Path) else source.encode("utf-8")


def render_svg_like_pdf_page(
    source: str | Path,
    size: QSize,
    *,
    margin_points: float = 0.0,
) -> QImage:
    ensure_qapp()
    renderer = QSvgRenderer(QByteArray(_svg_source_to_bytes(source)))
    assert renderer.isValid()
    view_box = renderer.viewBoxF()
    if view_box.isEmpty():
        default_size = renderer.defaultSize()
        svg_width = float(default_size.width()) or 1.0
        svg_height = float(default_size.height()) or 1.0
    else:
        svg_width = float(view_box.width()) or 1.0
        svg_height = float(view_box.height()) or 1.0
    image = QImage(size, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    margin = max(0.0, margin_points)
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


def nonwhite_bbox(image: QImage, *, stride: int = 1) -> tuple[tuple[int, int, int, int], int]:
    min_x = image.width()
    min_y = image.height()
    max_x = -1
    max_y = -1
    count = 0
    for y in range(0, image.height(), stride):
        for x in range(0, image.width(), stride):
            color = image.pixelColor(x, y)
            if color.alpha() and not (
                color.red() > 245 and color.green() > 245 and color.blue() > 245
            ):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                count += 1
    assert max_x >= min_x and max_y >= min_y
    return (min_x, min_y, max_x, max_y), count


def assert_pdf_has_printable_pages(
    pdf_path: Path,
    *,
    expected_pages: int | None = None,
    render_size: QSize | None = None,
) -> None:
    ensure_qapp()
    qt_pdf = pytest.importorskip("PyQt6.QtPdf")
    document = qt_pdf.QPdfDocument(None)
    document.load(str(pdf_path))
    if expected_pages is not None:
        assert document.pageCount() == expected_pages
    else:
        assert document.pageCount() > 0
    size = render_size or QSize(320, 454)
    for page in range(document.pageCount()):
        image = document.render(page, size)
        assert not image.isNull(), (pdf_path, page)
        _, nonwhite = nonwhite_bbox(image, stride=2)
        assert nonwhite > 40, (pdf_path, page)


def pdf_page_sizes_mm(pdf_path: Path) -> list[tuple[float, float]]:
    ensure_qapp()
    qt_pdf = pytest.importorskip("PyQt6.QtPdf")
    document = qt_pdf.QPdfDocument(None)
    document.load(str(pdf_path))
    assert document.pageCount() > 0
    sizes: list[tuple[float, float]] = []
    for page in range(document.pageCount()):
        page_size = document.pagePointSize(page)
        sizes.append(
            (float(page_size.width()) * MM_PER_POINT, float(page_size.height()) * MM_PER_POINT)
        )
    return sizes


def assert_pdf_pages_fit_standard_print_sheet(
    pdf_path: Path,
    *,
    expected_pages: int | None = None,
    max_short_mm: float = 220.0,
    max_long_mm: float = 300.0,
) -> None:
    sizes = pdf_page_sizes_mm(pdf_path)
    if expected_pages is not None:
        assert len(sizes) == expected_pages
    for width_mm, height_mm in sizes:
        assert min(width_mm, height_mm) <= max_short_mm
        assert max(width_mm, height_mm) <= max_long_mm


def assert_pdf_page_uses_area(
    pdf_path: Path,
    *,
    page: int = 0,
    min_width_ratio: float = 0.55,
    min_height_ratio: float = 0.55,
) -> None:
    image = render_pdf_page(pdf_path, page=page, size=QSize(640, 900))
    bbox, _count = nonwhite_bbox(image, stride=2)
    content_width = bbox[2] - bbox[0] + 1
    content_height = bbox[3] - bbox[1] + 1
    assert content_width / image.width() >= min_width_ratio, (pdf_path, page, bbox, image.size())
    assert content_height / image.height() >= min_height_ratio, (
        pdf_path,
        page,
        bbox,
        image.size(),
    )


def assert_pdf_page_matches_svg_bbox(
    pdf_path: Path,
    svg_source: str | Path,
    *,
    page: int = 0,
    margin_points: float = 0.0,
    tolerance_px: int = 24,
) -> None:
    pdf_image = render_pdf_page(pdf_path, page=page)
    svg_image = render_svg_like_pdf_page(svg_source, pdf_image.size(), margin_points=margin_points)
    pdf_bbox, pdf_count = nonwhite_bbox(pdf_image, stride=2)
    svg_bbox, svg_count = nonwhite_bbox(svg_image, stride=2)
    assert all(
        abs(actual - expected) <= tolerance_px
        for actual, expected in zip(pdf_bbox, svg_bbox, strict=True)
    ), (pdf_path, page, pdf_bbox, svg_bbox)
    assert 0.65 <= pdf_count / svg_count <= 1.35, (pdf_path, page, pdf_count, svg_count)
