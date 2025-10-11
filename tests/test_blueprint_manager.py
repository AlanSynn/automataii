from __future__ import annotations

import pytest

from automataii.application.blueprint import BlueprintCompositionResult
from automataii.core.blueprint_manager import BlueprintExportManager


@pytest.fixture
def fresh_manager():
    # Reset the singleton so tests do not leak state.
    BlueprintExportManager._instance = None  # type: ignore[attr-defined]
    manager = BlueprintExportManager.get_instance()
    yield manager
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
