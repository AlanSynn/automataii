from __future__ import annotations

import sys

import pytest
from PyQt6.QtWidgets import QApplication

from automataii.application.blueprint import BlueprintCompositionResult
from automataii.application.managers import BlueprintExportManager

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

    assert fresh_manager._get_save_file_path(None) == "blueprint.pdf"  # type: ignore[attr-defined]
    assert fresh_manager._get_save_file_path(None, output_format="svg") == "blueprint.svg"  # type: ignore[attr-defined]

    assert captured[0] == (
        "blueprint.pdf",
        "PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)",
    )
    assert captured[1] == (
        "blueprint.svg",
        "SVG Files (*.svg);;PDF Files (*.pdf);;All Files (*)",
    )
