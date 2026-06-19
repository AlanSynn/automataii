from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pdf_helpers import (
    assert_pdf_has_printable_pages,
    assert_pdf_page_matches_svg_bbox,
    assert_pdf_page_uses_area,
    assert_pdf_pages_fit_standard_print_sheet,
    pdf_page_sizes_mm,
)
from PyQt6.QtWidgets import QApplication

from automataii.application.blueprint import (
    BlueprintCompositionResult,
    BlueprintLayoutCompositionResult,
)
from automataii.application.managers import BlueprintExportManager, BlueprintExportResult
from automataii.domain.generation.layout import LayoutItem, ScaledBounds

_APP: QApplication | None = None


@pytest.fixture(scope="session", autouse=True)
def qapp() -> QApplication:
    """Keep a QApplication alive for BlueprintExportManager's QObject signals."""
    global _APP
    _APP = QApplication.instance() or QApplication(sys.argv)
    return _APP


@pytest.fixture
def fresh_manager():
    # Reset the singleton so tests do not leak state.
    BlueprintExportManager._instance = None  # type: ignore[attr-defined]
    manager = BlueprintExportManager.get_instance()
    yield manager
    BlueprintExportManager._instance = None  # type: ignore[attr-defined]


class EmptyLayoutComposer:
    def compose_layout_items(self, *_args, **_kwargs):
        return BlueprintLayoutCompositionResult(
            layout_items=(),
            width_mm=215.9,
            height_mm=279.4,
            item_count=0,
        )


def test_direct_construction_returns_initialized_singleton(qapp: QApplication) -> None:
    """Direct construction should keep singleton semantics without caching a half-init QObject."""
    BlueprintExportManager._instance = None  # type: ignore[attr-defined]
    try:
        first = BlueprintExportManager()
        second = BlueprintExportManager()

        assert first is second
        assert first._initialized is True  # type: ignore[attr-defined]
        assert hasattr(first, "gear_generator")
        assert hasattr(first, "_composer")
    finally:
        BlueprintExportManager._instance = None  # type: ignore[attr-defined]


def test_generate_single_page_delegates_to_composer(fresh_manager):
    captured = {}

    class StubComposer:
        def compose_single_page(
            self,
            part_items,
            mechanism_layers,
            *,
            unit_system="metric",
            snapshot_png_bytes=None,
        ):
            captured["part_items"] = part_items
            captured["mechanism_layers"] = mechanism_layers
            captured["unit_system"] = unit_system
            captured["snapshot_png_bytes"] = snapshot_png_bytes
            return BlueprintCompositionResult(
                svg="<svg/>",
                width_mm=123.4,
                height_mm=567.8,
                item_count=42,
            )

    fresh_manager._composer = StubComposer()  # type: ignore[attr-defined]

    result = fresh_manager.compose_single_page(
        part_items=["alpha"],
        mechanism_layers={"mech": {"type": "demo"}},
        snapshot_png_bytes=b"png-bytes",
        unit_system="imperial",
    )

    assert isinstance(result, BlueprintCompositionResult)
    assert result.svg == "<svg/>"
    assert result.width_mm == 123.4
    assert result.height_mm == 567.8
    assert result.item_count == 42

    svg = fresh_manager._generate_single_large_page_blueprint(  # type: ignore[attr-defined]
        part_items=["alpha"],
        mechanism_layers={"mech": {"type": "demo"}},
        snapshot_png_bytes=b"png-bytes",
        unit_system="imperial",
    )

    assert svg == "<svg/>"
    assert captured["part_items"] == ["alpha"]
    assert captured["mechanism_layers"] == {"mech": {"type": "demo"}}
    assert captured["unit_system"] == "imperial"
    assert captured["snapshot_png_bytes"] == b"png-bytes"


def test_save_dialog_defaults_to_pdf_and_allows_svg(fresh_manager, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    captured: list[tuple[str, str]] = []

    def fake_get_save_file_name(_parent, _title, default_name, filters):
        captured.append((default_name, filters))
        return (default_name, filters)

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_get_save_file_name)

    pdf_path = Path(fresh_manager._get_save_file_path(None))  # type: ignore[attr-defined,arg-type]
    svg_path = Path(
        fresh_manager._get_save_file_path(None, output_format="svg")  # type: ignore[attr-defined,arg-type]
    )

    assert pdf_path.name == "current-design-cut-sheets.pdf"
    assert svg_path.name == "current-design-cut-sheets.svg"

    assert captured[0] == (
        str(Path.home() / "Downloads" / "current-design-cut-sheets.pdf")
        if (Path.home() / "Downloads").is_dir()
        else str(Path.home() / "current-design-cut-sheets.pdf"),
        "PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)",
    )
    assert captured[1] == (
        str(Path.home() / "Downloads" / "current-design-cut-sheets.svg")
        if (Path.home() / "Downloads").is_dir()
        else str(Path.home() / "current-design-cut-sheets.svg"),
        "SVG Files (*.svg);;PDF Files (*.pdf);;All Files (*)",
    )


def test_dialog_export_reports_actual_svg_fallback_when_pdf_render_fails(
    fresh_manager,
    monkeypatch,
    tmp_path,
) -> None:
    import automataii.application.managers.blueprint_manager as blueprint_manager

    def fake_render(_svg_content: str, output_path: Path) -> bool:
        output_path.write_text("partial pdf", encoding="utf-8")
        return False

    messages: list[tuple[bool, str]] = []
    fresh_manager._composer = EmptyLayoutComposer()  # type: ignore[attr-defined]
    monkeypatch.setattr(blueprint_manager, "render_svg_to_pdf", fake_render)
    monkeypatch.setattr(
        fresh_manager,
        "_get_save_file_path",
        lambda *_args, **_kwargs: str(tmp_path / "current-design-cut-sheets.pdf"),
    )
    fresh_manager.export_completed.connect(lambda ok, message: messages.append((ok, message)))

    assert fresh_manager.export_blueprint(part_items=[], mechanism_layers={}, output_format="pdf")
    assert messages[-1][0] is True
    assert "PDF rendering unavailable" in messages[-1][1]
    assert "current-design-cut-sheets.svg" in messages[-1][1]
    assert (tmp_path / "current-design-cut-sheets.svg").is_file()
    assert not (tmp_path / "current-design-cut-sheets.pdf").exists()


def test_save_pdf_file_removes_partial_and_stale_pdf_when_renderer_fails(
    fresh_manager,
    monkeypatch,
    tmp_path,
) -> None:
    import automataii.application.managers.blueprint_manager as blueprint_manager

    target = tmp_path / "current-design-cut-sheets.pdf"
    target.write_text("stale pdf", encoding="utf-8")

    def fake_render(_svg_content: str, output_path: Path) -> bool:
        output_path.write_text("partial pdf", encoding="utf-8")
        return False

    monkeypatch.setattr(blueprint_manager, "render_svg_to_pdf", fake_render)

    assert fresh_manager._save_pdf_file("<svg />", str(target)) is False  # type: ignore[attr-defined]
    assert not target.exists()
    assert not (tmp_path / ".current-design-cut-sheets.tmp.pdf").exists()


def test_save_pdf_file_rejects_renderer_success_with_non_pdf_output(
    fresh_manager,
    monkeypatch,
    tmp_path,
) -> None:
    import automataii.application.managers.blueprint_manager as blueprint_manager

    target = tmp_path / "current-design-cut-sheets.pdf"

    def fake_render(_svg_content: str, output_path: Path) -> bool:
        output_path.write_text("not a pdf", encoding="utf-8")
        return True

    monkeypatch.setattr(blueprint_manager, "render_svg_to_pdf", fake_render)

    assert fresh_manager._save_pdf_file("<svg />", str(target)) is False  # type: ignore[attr-defined]
    assert not target.exists()
    assert not (tmp_path / ".current-design-cut-sheets.tmp.pdf").exists()


def test_export_blueprint_to_path_returns_svg_fallback_when_pdf_render_fails(
    fresh_manager,
    monkeypatch,
    tmp_path,
) -> None:
    import automataii.application.managers.blueprint_manager as blueprint_manager

    def fake_render(_svg_content: str, output_path: Path) -> bool:
        output_path.write_text("partial pdf", encoding="utf-8")
        return False

    fresh_manager._composer = EmptyLayoutComposer()  # type: ignore[attr-defined]
    monkeypatch.setattr(blueprint_manager, "render_svg_to_pdf", fake_render)
    target = tmp_path / "current-design-cut-sheets.pdf"

    result = fresh_manager.export_blueprint_to_path_result(
        part_items=[],
        mechanism_layers={},
        file_path=target,
        output_format="pdf",
    )

    assert isinstance(result, BlueprintExportResult)
    assert result.success is True
    assert result.requested_format == "pdf"
    assert result.actual_format == "svg"
    assert result.path == tmp_path / "current-design-cut-sheets.svg"
    assert result.fallback_path == tmp_path / "current-design-cut-sheets.svg"
    assert not target.exists()
    assert result.path.is_file()


def test_export_blueprint_to_path_reports_pdf_success(
    fresh_manager,
    monkeypatch,
    tmp_path,
) -> None:
    import automataii.application.managers.blueprint_manager as blueprint_manager

    def fake_render(_svg_content: str, output_path: Path) -> bool:
        output_path.write_text("%PDF-1.4\n%%EOF\n", encoding="utf-8")
        return True

    fresh_manager._composer = EmptyLayoutComposer()  # type: ignore[attr-defined]
    monkeypatch.setattr(blueprint_manager, "render_svg_to_pdf", fake_render)
    target = tmp_path / "current-design-cut-sheets.pdf"

    result = fresh_manager.export_blueprint_to_path_result(
        part_items=[],
        mechanism_layers={},
        file_path=target,
        output_format="pdf",
    )

    assert result.success is True
    assert result.requested_format == "pdf"
    assert result.actual_format == "pdf"
    assert result.path == target
    assert result.fallback_path is None
    assert result.error is None
    assert target.is_file()


def test_export_blueprint_to_path_uses_fixed_letter_printable_pages(
    fresh_manager,
    tmp_path,
) -> None:
    class StubComposer:
        def compose_layout_items(self, *_args, **_kwargs):
            part = LayoutItem(
                name="Head",
                bounds=ScaledBounds(0, 0, 60, 42),
                svg_content=(
                    '<g class="scaled-part" data-name="Head">'
                    '<rect x="0" y="0" width="60" height="42" class="part-outline"/>'
                    '<path d="M0 0 H60 V42 H0 Z" class="cutting-path"/>'
                    '<circle cx="30" cy="21" r="2" class="pivot-drill-hole" '
                    'data-hole-diameter-mm="4"/>'
                    "</g>"
                ),
                item_type="part",
            )
            mechanism = LayoutItem(
                name="Four bar",
                bounds=ScaledBounds(0, 0, 80, 50),
                svg_content='<g><rect width="80" height="50"/></g>',
                item_type="mechanism",
            )
            return BlueprintLayoutCompositionResult(
                layout_items=(part, mechanism),
                width_mm=215.9,
                height_mm=279.4,
                item_count=2,
            )

    fresh_manager._composer = StubComposer()  # type: ignore[attr-defined]
    target = tmp_path / "current-design-cut-sheets.pdf"

    result = fresh_manager.export_blueprint_to_path_result(
        part_items=[],
        mechanism_layers={"four_bar": {"type": "four_bar"}},
        file_path=target,
        output_format="pdf",
    )

    assert result.success is True
    assert result.actual_format == "pdf"
    assert_pdf_has_printable_pages(target, expected_pages=2)
    assert_pdf_pages_fit_standard_print_sheet(target, expected_pages=2)
    sizes = pdf_page_sizes_mm(target)
    assert all(214.0 <= width <= 218.0 for width, _height in sizes)
    assert all(277.0 <= height <= 282.0 for _width, height in sizes)
    assert_pdf_page_uses_area(target, page=0, min_width_ratio=0.65, min_height_ratio=0.55)
    assert_pdf_page_uses_area(target, page=1, min_width_ratio=0.65, min_height_ratio=0.55)


def test_current_design_pdf_pages_match_their_fixed_size_svg_sources(
    fresh_manager,
    tmp_path,
) -> None:
    class StubComposer:
        def compose_layout_items(self, *_args, **_kwargs):
            part = LayoutItem(
                name="Body",
                bounds=ScaledBounds(0, 0, 72, 96),
                svg_content=(
                    '<g class="scaled-part" data-name="Body">'
                    '<rect x="0" y="0" width="72" height="96" class="part-outline"/>'
                    '<path d="M0 0 H72 V96 H0 Z" class="cutting-path"/>'
                    '<circle cx="36" cy="48" r="2" class="pivot-drill-hole" '
                    'data-hole-diameter-mm="4"/>'
                    "</g>"
                ),
                item_type="part",
            )
            return BlueprintLayoutCompositionResult(
                layout_items=(part,),
                width_mm=215.9,
                height_mm=279.4,
                item_count=1,
            )

    fresh_manager._composer = StubComposer()  # type: ignore[attr-defined]
    target = tmp_path / "current-design-cut-sheets.pdf"
    svg_pages = fresh_manager._generate_printable_cut_sheet_pages(  # type: ignore[attr-defined]
        part_items=[],
        mechanism_layers={},
    )

    result = fresh_manager.export_blueprint_to_path_result(
        part_items=[],
        mechanism_layers={},
        file_path=target,
        output_format="pdf",
    )

    assert result.success is True
    assert_pdf_page_matches_svg_bbox(target, svg_pages[0], page=0, tolerance_px=28)
    assert_pdf_page_matches_svg_bbox(target, svg_pages[1], page=1, tolerance_px=28)


def test_current_design_part_cut_sheets_never_upscale_small_parts(
    fresh_manager,
) -> None:
    class StubComposer:
        def compose_layout_items(self, *_args, **_kwargs):
            small_part = LayoutItem(
                name="Small handle",
                bounds=ScaledBounds(0, 0, 20, 10),
                svg_content='<g><rect x="0" y="0" width="20" height="10" class="part-outline"/></g>',
                item_type="part",
            )
            large_part = LayoutItem(
                name="Oversize panel",
                bounds=ScaledBounds(0, 0, 260, 220),
                svg_content='<g><rect x="0" y="0" width="260" height="220" class="part-outline"/></g>',
                item_type="part",
            )
            return BlueprintLayoutCompositionResult(
                layout_items=(small_part, large_part),
                width_mm=215.9,
                height_mm=279.4,
                item_count=2,
            )

    fresh_manager._composer = StubComposer()  # type: ignore[attr-defined]

    pages = fresh_manager._generate_printable_cut_sheet_pages(  # type: ignore[attr-defined]
        part_items=[],
        mechanism_layers={},
    )
    _cover, small_page, *large_pages = pages

    assert "Actual size" in small_page
    assert "scale(1.000000)" in small_page
    assert len(large_pages) == 4
    assert all("Actual size tile" in page for page in large_pages)
    assert all("scale(1.000000)" in page for page in large_pages)
    assert all("Scaled " not in page for page in large_pages)


def test_current_design_oversized_parts_tile_across_actual_size_pages(
    fresh_manager,
    tmp_path,
) -> None:
    class StubComposer:
        def compose_layout_items(self, *_args, **_kwargs):
            oversized = LayoutItem(
                name="Full body panel",
                bounds=ScaledBounds(0, 0, 260, 220),
                svg_content=(
                    '<g class="scaled-part" data-name="Full body panel">'
                    '<rect x="0" y="0" width="260" height="220" class="part-outline"/>'
                    '<path d="M0 0 H260 V220 H0 Z" class="cutting-path"/>'
                    '<circle cx="130" cy="110" r="2" class="pivot-drill-hole" '
                    'data-hole-diameter-mm="4"/>'
                    "</g>"
                ),
                item_type="part",
            )
            return BlueprintLayoutCompositionResult(
                layout_items=(oversized,),
                width_mm=215.9,
                height_mm=279.4,
                item_count=1,
            )

    fresh_manager._composer = StubComposer()  # type: ignore[attr-defined]
    target = tmp_path / "current-design-cut-sheets.pdf"

    result = fresh_manager.export_blueprint_to_path_result(
        part_items=[],
        mechanism_layers={},
        file_path=target,
        output_format="pdf",
    )

    assert result.success is True
    assert_pdf_has_printable_pages(target, expected_pages=5)
    assert_pdf_pages_fit_standard_print_sheet(target, expected_pages=5)
    svg_pages = fresh_manager._generate_printable_cut_sheet_pages(  # type: ignore[attr-defined]
        part_items=[],
        mechanism_layers={},
    )
    assert len(svg_pages) == 5
    assert all("Actual size tile" in page for page in svg_pages[1:])
    assert all('data-tile-overlap-mm="5.0"' in page for page in svg_pages[1:])
    assert all('data-tile-registration="true"' in page for page in svg_pages[1:])
    assert all("align 0.2 in overlaps and registration marks" in page for page in svg_pages[1:])
    assert all("Scaled " not in page for page in svg_pages)


def test_current_design_layout_failure_does_not_emit_fake_success_cut_sheet(
    fresh_manager,
    monkeypatch,
    tmp_path,
) -> None:
    import automataii.application.managers.blueprint_manager as blueprint_manager

    class FailingLayoutComposer:
        def compose_layout_items(self, *_args, **_kwargs):
            raise RuntimeError("layout optimizer exploded")

        def compose_single_page(self, *_args, **_kwargs):
            raise AssertionError("legacy oversized single-page SVG must not be used for PDF")

    rendered_sources: list[str] = []

    def fake_render(svg_content: str, output_path: Path) -> bool:
        rendered_sources.append(svg_content)
        output_path.write_text("%PDF-1.4\n%%EOF\n", encoding="utf-8")
        return True

    fresh_manager._composer = FailingLayoutComposer()  # type: ignore[attr-defined]
    monkeypatch.setattr(blueprint_manager, "render_svg_to_pdf", fake_render)
    target = tmp_path / "current-design-cut-sheets.pdf"

    result = fresh_manager.export_blueprint_to_path_result(
        part_items=[],
        mechanism_layers={"custom": {"type": "custom"}},
        file_path=target,
        output_format="pdf",
    )

    assert result.success is False
    assert result.path is None
    assert result.actual_format is None
    assert "Printable cut-sheet layout failed" in str(result.error)
    assert rendered_sources == []
    assert not target.exists()


def test_export_blueprint_to_path_reports_svg_success(fresh_manager, tmp_path) -> None:
    fresh_manager._composer = EmptyLayoutComposer()  # type: ignore[attr-defined]
    target = tmp_path / "current-design-cut-sheets.svg"

    result = fresh_manager.export_blueprint_to_path_result(
        part_items=[],
        mechanism_layers={},
        file_path=target,
        output_format="svg",
    )

    assert result.success is True
    assert result.requested_format == "svg"
    assert result.actual_format == "svg"
    assert result.path == target
    assert result.fallback_path is None
    assert target.is_file()


def test_export_blueprint_to_path_preserves_legacy_bool_contract(fresh_manager, tmp_path) -> None:
    fresh_manager._composer = EmptyLayoutComposer()  # type: ignore[attr-defined]
    target = tmp_path / "current-design-cut-sheets.svg"

    result = fresh_manager.export_blueprint_to_path(
        part_items=[],
        mechanism_layers={},
        file_path=target,
        output_format="svg",
    )

    assert result is True
    assert target.is_file()


def test_export_blueprint_to_path_reports_total_failure(
    fresh_manager,
    monkeypatch,
    tmp_path,
) -> None:
    class StubComposer:
        def compose_layout_items(self, *_args, **_kwargs):
            return BlueprintLayoutCompositionResult(
                layout_items=(),
                width_mm=215.9,
                height_mm=279.4,
                item_count=0,
            )

    fresh_manager._composer = StubComposer()  # type: ignore[attr-defined]
    monkeypatch.setattr(fresh_manager, "_save_pdf_pages", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(fresh_manager, "_save_svg_pages", lambda *_args, **_kwargs: False)
    target = tmp_path / "current-design-cut-sheets.pdf"

    result = fresh_manager.export_blueprint_to_path_result(
        part_items=[],
        mechanism_layers={},
        file_path=target,
        output_format="pdf",
    )

    assert result.success is False
    assert result.requested_format == "pdf"
    assert result.actual_format is None
    assert result.path is None
    assert result.error
    assert not target.exists()
