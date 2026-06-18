from __future__ import annotations

from pathlib import Path

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
