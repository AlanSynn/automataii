from __future__ import annotations

from pathlib import Path

from automataii.presentation.qt.mechanisms.four_bar import serializer as serializer_module
from automataii.presentation.qt.mechanisms.four_bar.serializer import FourBarSerializer


def _blueprint():
    return FourBarSerializer().serialize(
        {
            "parameters": {
                "anchor1": [0.0, 0.0],
                "anchor2": [80.0, 0.0],
                "l1": 80.0,
                "l2": 40.0,
                "l3": 80.0,
                "l4": 40.0,
            }
        }
    )


def test_fourbar_serializer_pdf_uses_shared_renderer(monkeypatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_render(svg_source: str, output_path: Path) -> bool:
        seen["svg"] = svg_source
        seen["path"] = output_path
        output_path.write_text("%PDF-1.4\n%%EOF\n", encoding="utf-8")
        return True

    monkeypatch.setattr(serializer_module, "render_svg_to_pdf", fake_render)

    target = tmp_path / "four-bar.pdf"
    assert FourBarSerializer().export_to_pdf(_blueprint(), str(target)) is True

    assert target.read_text(encoding="utf-8") == "%PDF-1.4\n%%EOF\n"
    assert "Four-Bar Linkage Blueprint" in str(seen["svg"])
    assert Path(seen["path"]).name == ".four-bar.tmp.pdf"
    assert not (tmp_path / ".four-bar.tmp.pdf").exists()


def test_fourbar_serializer_pdf_removes_partial_output_on_renderer_failure(
    monkeypatch, tmp_path: Path
) -> None:
    target = tmp_path / "four-bar.pdf"
    target.write_text("stale", encoding="utf-8")

    def fake_render(_svg_source: str, output_path: Path) -> bool:
        output_path.write_text("partial", encoding="utf-8")
        return False

    monkeypatch.setattr(serializer_module, "render_svg_to_pdf", fake_render)

    assert FourBarSerializer().export_to_pdf(_blueprint(), str(target)) is False
    assert not target.exists()
    assert not (tmp_path / ".four-bar.tmp.pdf").exists()


def test_fourbar_serializer_rejects_renderer_success_with_non_pdf_output(
    monkeypatch, tmp_path: Path
) -> None:
    target = tmp_path / "four-bar.pdf"

    def fake_render(_svg_source: str, output_path: Path) -> bool:
        output_path.write_text("not a pdf", encoding="utf-8")
        return True

    monkeypatch.setattr(serializer_module, "render_svg_to_pdf", fake_render)

    assert FourBarSerializer().export_to_pdf(_blueprint(), str(target)) is False
    assert not target.exists()
    assert not (tmp_path / ".four-bar.tmp.pdf").exists()
