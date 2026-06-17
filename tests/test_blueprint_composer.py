from __future__ import annotations

from dataclasses import dataclass

from automataii.application.blueprint import BlueprintComposer, BlueprintCompositionResult


@dataclass
class DummyLayoutItem:
    bounds: any
    svg_content: str
    name: str = "item"
    item_type: str = "part"
    priority: int = 1


class DummyOptimizer:
    def __init__(self, layout_items=None):
        if layout_items is None:
            self.layout_items = [DummyLayoutItem(bounds=None, svg_content="<svg/>")]
        else:
            self.layout_items = layout_items

    def optimize_blueprint_layout(self, part_items, mechanism_layers, unit_system):
        return self.layout_items, 900.0, 700.0


def dummy_generator(layout_items, width, height, title, scale_info, snapshot_data_uri, unit_system):
    return f"<svg width='{width}' height='{height}'>{len(layout_items)}</svg>"


def test_compose_single_page_with_layout():
    composer = BlueprintComposer(optimizer=DummyOptimizer(), svg_generator=dummy_generator)
    result = composer.compose_single_page([], {})
    assert isinstance(result, BlueprintCompositionResult)
    assert "width='900.0'" in result.svg
    assert result.item_count == 1


def test_compose_single_page_empty_layout():
    composer = BlueprintComposer(
        optimizer=DummyOptimizer(layout_items=[]), svg_generator=dummy_generator
    )
    result = composer.compose_single_page([], {})
    assert result.item_count == 0
    assert "No items to export" in result.svg or "svg" in result.svg


def test_compose_single_page_names_cut_sheet_handoff():
    seen: dict[str, str] = {}

    def capturing_generator(
        layout_items, width, height, title, scale_info, snapshot_data_uri, unit_system
    ):
        seen["title"] = title
        seen["scale_info"] = scale_info
        return f"<svg width='{width}' height='{height}'>{len(layout_items)}</svg>"

    composer = BlueprintComposer(optimizer=DummyOptimizer(), svg_generator=capturing_generator)

    composer.compose_single_page([], {})

    assert seen["title"] == "Make Parts / Cut Sheets (Metric)"
    assert "Cut/drill only" in seen["scale_info"]
    assert "Board Assembly Guide has 15x15 coordinates" in seen["scale_info"]
