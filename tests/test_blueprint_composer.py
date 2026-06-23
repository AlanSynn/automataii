from __future__ import annotations

from dataclasses import dataclass

from automataii.application.blueprint import BlueprintComposer, BlueprintCompositionResult
from automataii.domain.generation.layout import LayoutItem, ScaledBounds
from automataii.infrastructure.generation.svg.blueprint import generate_single_large_blueprint
from automataii.shared.physical_kit import LETTER_PAGE_HEIGHT_MM


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


def test_default_composer_targets_letter_page_character_height() -> None:
    composer = BlueprintComposer()

    assert composer._optimizer.scale_normalizer.target_height_mm == LETTER_PAGE_HEIGHT_MM


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
    assert 'width="400mm"' in result.svg
    assert 'viewBox="0 0 400 300"' in result.svg


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

    assert seen["title"] == "Make Parts / Cut Sheets"
    assert "Cut/drill only" in seen["scale_info"]
    assert "assembly-guide.pdf shows 15x15 board placement" in seen["scale_info"]


def test_single_page_blueprint_flattens_embedded_item_svgs_for_pdf_renderer() -> None:
    part = LayoutItem(
        name="Body",
        bounds=ScaledBounds(0, 0, 100, 50),
        svg_content=(
            '<svg width="100" height="50" viewBox="0 0 100 50" '
            'xmlns="http://www.w3.org/2000/svg"><rect width="100" height="50"/></svg>'
        ),
        item_type="part",
    )
    mechanism = LayoutItem(
        name="Mechanism",
        bounds=ScaledBounds(0, 0, 120, 80),
        svg_content=(
            '<svg width="120" height="80" viewBox="0 0 120 80" '
            'xmlns="http://www.w3.org/2000/svg"><circle cx="40" cy="40" r="20"/></svg>'
        ),
        item_type="mechanism",
    )

    svg = generate_single_large_blueprint(
        [part, mechanism],
        400,
        300,
        title="Make Parts / Cut Sheets",
        scale_info="Cut/drill only",
    )

    assert svg.count("<svg") == 1
    assert "<g><rect" in svg
    assert "<g><circle" in svg
