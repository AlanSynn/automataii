from __future__ import annotations

import base64
import logging
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from automataii.infrastructure.generation.svg.blueprint import generate_single_large_blueprint
from automataii.infrastructure.generation.svg.optimizer import BlueprintLayoutOptimizer
from automataii.infrastructure.telemetry import telemetry_span
from automataii.shared.physical_kit import DEFAULT_DISPLAY_UNIT_SYSTEM, normalize_unit_system


@dataclass(frozen=True)
class BlueprintCompositionResult:
    svg: str
    width_mm: float
    height_mm: float
    item_count: int


@dataclass(frozen=True)
class BlueprintLayoutCompositionResult:
    layout_items: tuple[Any, ...]
    width_mm: float
    height_mm: float
    item_count: int


class BlueprintComposer:
    """Facade around the legacy blueprint optimizer and SVG generator."""

    def __init__(
        self,
        optimizer: BlueprintLayoutOptimizer | None = None,
        svg_generator: Callable[..., str] = generate_single_large_blueprint,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self._optimizer = optimizer or BlueprintLayoutOptimizer(target_character_height_mm=300.0)
        self._svg_generator = svg_generator

    @staticmethod
    def _positive_finite_float(value: object, default: float) -> float:
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) and number > 0.0 else default

    def compose_layout_items(
        self,
        part_items: Sequence[Any],
        mechanism_layers: dict[str, Any],
        *,
        unit_system: str = DEFAULT_DISPLAY_UNIT_SYSTEM,
    ) -> BlueprintLayoutCompositionResult:
        """Return normalized physical layout items without choosing a document surface.

        The legacy composer used the optimizer output only to build one large
        on-screen SVG. Printable PDF packages need the same physical items, but
        placed onto fixed Letter pages. This method exposes that SSOT so PDF and
        SVG cut-sheet emitters do not have to parse the large preview SVG.
        """
        part_items_seq = tuple(part_items) if part_items is not None else ()
        mechanism_layers = mechanism_layers if isinstance(mechanism_layers, dict) else {}
        unit_system = normalize_unit_system(unit_system)
        layout_items, width_mm, height_mm = self._optimizer.optimize_blueprint_layout(
            part_items_seq, mechanism_layers, unit_system
        )
        layout_items_tuple = tuple(layout_items or ())
        width_mm = self._positive_finite_float(width_mm, 800.0)
        height_mm = self._positive_finite_float(height_mm, 600.0)
        return BlueprintLayoutCompositionResult(
            layout_items=layout_items_tuple,
            width_mm=width_mm,
            height_mm=height_mm,
            item_count=len(layout_items_tuple),
        )

    def compose_single_page(
        self,
        part_items: Sequence[Any],
        mechanism_layers: dict[str, Any],
        *,
        unit_system: str = DEFAULT_DISPLAY_UNIT_SYSTEM,
        snapshot_png_bytes: bytes | None = None,
    ) -> BlueprintCompositionResult:
        part_items_seq = tuple(part_items) if part_items is not None else ()
        mechanism_layers = mechanism_layers if isinstance(mechanism_layers, dict) else {}
        unit_system = normalize_unit_system(unit_system)

        with telemetry_span(
            "application.blueprint.compose_single_page",
            part_count=len(part_items_seq),
            mechanism_count=len(mechanism_layers),
            unit_system=unit_system,
        ) as span:
            layout_result = self.compose_layout_items(
                part_items_seq, mechanism_layers, unit_system=unit_system
            )
            layout_items = list(layout_result.layout_items)
            width_mm = layout_result.width_mm
            height_mm = layout_result.height_mm
            if not layout_items:
                svg = (
                    '<svg width="400mm" height="300mm" viewBox="0 0 400 300" '
                    'xmlns="http://www.w3.org/2000/svg">'
                    "<title>Make Parts / Cut Sheets</title>"
                    "<text x='50' y='150'>No items to export</text></svg>"
                )
                span.set(status="empty")
                return BlueprintCompositionResult(svg, 400.0, 300.0, 0)

            snapshot_data_uri = None
            if isinstance(snapshot_png_bytes, bytes | bytearray) and snapshot_png_bytes:
                snapshot_data_uri = (
                    f"data:image/png;base64,{base64.b64encode(bytes(snapshot_png_bytes)).decode()}"
                )

            svg = self._svg_generator(
                layout_items,
                max(width_mm, 800),
                max(height_mm, 600),
                title="Make Parts / Cut Sheets",
                scale_info=("Cut/drill only; assembly-guide.pdf shows 15x15 board placement"),
                snapshot_data_uri=snapshot_data_uri,
                unit_system=unit_system,
            )
            span.set(status="success", width_mm=width_mm, height_mm=height_mm)
            return BlueprintCompositionResult(svg, width_mm, height_mm, len(layout_items))
