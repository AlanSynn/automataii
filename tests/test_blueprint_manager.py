from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from automataii.application.blueprint import BlueprintCompositionResult
from automataii.application.managers import BlueprintExportManager, BlueprintExportResult

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

    class StubComposer:
        def compose_single_page(self, *_args, **_kwargs):
            return BlueprintCompositionResult(
                svg="<svg/>",
                width_mm=10.0,
                height_mm=10.0,
                item_count=0,
            )

    def fake_render(_svg_content: str, output_path: Path) -> bool:
        output_path.write_text("partial pdf", encoding="utf-8")
        return False

    messages: list[tuple[bool, str]] = []
    fresh_manager._composer = StubComposer()  # type: ignore[attr-defined]
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

    class StubComposer:
        def compose_single_page(self, *_args, **_kwargs):
            return BlueprintCompositionResult(
                svg="<svg/>",
                width_mm=10.0,
                height_mm=10.0,
                item_count=0,
            )

    def fake_render(_svg_content: str, output_path: Path) -> bool:
        output_path.write_text("partial pdf", encoding="utf-8")
        return False

    fresh_manager._composer = StubComposer()  # type: ignore[attr-defined]
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

    class StubComposer:
        def compose_single_page(self, *_args, **_kwargs):
            return BlueprintCompositionResult(
                svg="<svg/>",
                width_mm=10.0,
                height_mm=10.0,
                item_count=0,
            )

    def fake_render(_svg_content: str, output_path: Path) -> bool:
        output_path.write_text("%PDF-1.4\n%%EOF\n", encoding="utf-8")
        return True

    fresh_manager._composer = StubComposer()  # type: ignore[attr-defined]
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


def test_export_blueprint_to_path_reports_svg_success(fresh_manager, tmp_path) -> None:
    class StubComposer:
        def compose_single_page(self, *_args, **_kwargs):
            return BlueprintCompositionResult(
                svg="<svg/>",
                width_mm=10.0,
                height_mm=10.0,
                item_count=0,
            )

    fresh_manager._composer = StubComposer()  # type: ignore[attr-defined]
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
    class StubComposer:
        def compose_single_page(self, *_args, **_kwargs):
            return BlueprintCompositionResult(
                svg="<svg/>",
                width_mm=10.0,
                height_mm=10.0,
                item_count=0,
            )

    fresh_manager._composer = StubComposer()  # type: ignore[attr-defined]
    target = tmp_path / "current-design-cut-sheets.svg"

    result = fresh_manager.export_blueprint_to_path(
        part_items=[],
        mechanism_layers={},
        file_path=target,
        output_format="svg",
    )

    assert result is True
    assert target.is_file()


def test_export_blueprint_to_path_reports_total_failure(fresh_manager, tmp_path) -> None:
    class EmptyComposer:
        def compose_single_page(self, *_args, **_kwargs):
            return BlueprintCompositionResult(
                svg="",
                width_mm=10.0,
                height_mm=10.0,
                item_count=0,
            )

    fresh_manager._composer = EmptyComposer()  # type: ignore[attr-defined]
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
