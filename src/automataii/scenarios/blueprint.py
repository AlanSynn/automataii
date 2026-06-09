from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from automataii.application.blueprint import BlueprintComposer
from automataii.application.mechanism_foundry import (
    MechanismFoundryController,
    MechanismItem,
)
from automataii.domain.generation.layout import ScaledBounds
from automataii.infrastructure.generation.svg.blueprint import generate_single_large_blueprint

# ---------------------------------------------------------------------------
# Scenario-specific optimizer & layout helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioLayoutItem:
    """Minimal layout item matching the generator contract."""

    name: str
    bounds: ScaledBounds
    svg_content: str
    item_type: str
    priority: int = 1


class ScenarioOptimizer:
    """Deterministic optimizer returning a small mechanism + part layout."""

    @staticmethod
    def _positive_dimension(value: object, default: float) -> float:
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) and number > 0.0 else default

    @staticmethod
    def _safe_text(value: object, default: str) -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text or default

    @staticmethod
    def _format_param(key: object, value: object) -> str:
        key_text = ScenarioOptimizer._safe_text(key, "param")
        if (
            isinstance(value, int | float)
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        ):
            value_text = f"{float(value):g}"
        else:
            value_text = ScenarioOptimizer._safe_text(value, "n/a")
        return f"{key_text}={value_text}"

    def optimize_blueprint_layout(
        self,
        part_items: Iterable[dict[str, Any]],
        mechanism_layers: dict[str, Any],
        unit_system: str,
    ) -> tuple[list[ScenarioLayoutItem], float, float]:
        layout_items: list[ScenarioLayoutItem] = []
        x_offset = 0.0

        for index, part in enumerate(part_items):
            if not isinstance(part, dict):
                continue
            width = self._positive_dimension(part.get("width_mm"), 160.0)
            height = self._positive_dimension(part.get("height_mm"), 90.0)
            name = self._safe_text(part.get("name"), f"Part {index + 1}")
            bounds = ScaledBounds(x_offset, 0.0, width, height)
            svg = _svg_panel(
                width,
                height,
                title=name,
                body=f"Area: {width * height:.0f} mm²",
            )
            layout_items.append(
                ScenarioLayoutItem(
                    name=name,
                    bounds=bounds,
                    svg_content=svg,
                    item_type="part",
                    priority=1,
                )
            )
            x_offset += width + 40.0

        mech_y = 160.0
        mechanism_layers = mechanism_layers if isinstance(mechanism_layers, dict) else {}
        for mech_id, mech_data in mechanism_layers.items():
            if not isinstance(mech_data, dict):
                mech_data = {}
            bounds = ScaledBounds(0.0, mech_y, 260.0, 180.0)
            params = mech_data.get("params", {})
            params_items = list(params.items())[:4] if isinstance(params, dict) else []
            params_summary = ", ".join(
                self._format_param(key, value) for key, value in params_items
            )
            mech_name = self._safe_text(mech_data.get("display_name"), str(mech_id))
            svg = _svg_panel(
                bounds.width,
                bounds.height,
                title=mech_name,
                body=f"Type: {self._safe_text(mech_data.get('type'), 'unknown')}\n{params_summary}",
                fill="#f9fbff",
            )
            layout_items.append(
                ScenarioLayoutItem(
                    name=self._safe_text(mech_id, "mechanism"),
                    bounds=bounds,
                    svg_content=svg,
                    item_type="mechanism",
                    priority=2,
                )
            )
            mech_y += bounds.height + 40.0

        if not layout_items:
            return [], 400.0, 300.0

        total_width = max(item.bounds.x + item.bounds.width for item in layout_items) + 60.0
        total_height = max(item.bounds.y + item.bounds.height for item in layout_items) + 80.0
        return layout_items, total_width, total_height


# ---------------------------------------------------------------------------
# Public scenario runner
# ---------------------------------------------------------------------------


def run_blueprint_export_scenario(output_dir: Path, unit_system: str = "metric") -> Path:
    """Generate a sample blueprint using controller defaults."""
    controller = MechanismFoundryController()
    items = list(controller.list_mechanisms())
    target = _pick_mechanism(items, preferred_type="four_bar")

    controller.select_mechanism(target.category_key, target.mechanism_key)
    config = controller.get_configuration(target.mechanism_type)
    if config is None:
        raise RuntimeError(f"No configuration available for {target.mechanism_type}")

    mechanism_params = controller.initial_parameters(target.mechanism_type)
    mechanism_layers = {
        target.mechanism_key: {
            "type": target.mechanism_type,
            "display_name": target.display_name,
            "params": mechanism_params,
        }
    }

    part_items = [
        {"name": "Upper Arm Panel", "width_mm": 180.0, "height_mm": 90.0},
        {"name": "Lower Arm Panel", "width_mm": 160.0, "height_mm": 80.0},
        {"name": "Connector Plate", "width_mm": 120.0, "height_mm": 60.0},
    ]

    composer = BlueprintComposer(
        optimizer=ScenarioOptimizer(), svg_generator=generate_single_large_blueprint
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    logger = logging.getLogger("automataii.scenario.blueprint")
    start_time = time.perf_counter()

    from automataii.infrastructure.telemetry import telemetry_span

    with telemetry_span(
        "scenario.blueprint_export",
        unit_system=unit_system,
        mechanism_type=target.mechanism_type,
        mechanism_key=target.mechanism_key,
    ) as span:
        result = composer.compose_single_page(
            part_items,
            mechanism_layers,
            unit_system=unit_system,
            snapshot_png_bytes=None,
        )
        span.set(item_count=result.item_count, width_mm=result.width_mm, height_mm=result.height_mm)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 3)
    logger.info(
        "scenario_complete blueprint-export item_count=%s duration_ms=%s output_dir=%s",
        result.item_count,
        duration_ms,
        output_dir,
    )

    svg_path = output_dir / "foundry_blueprint.svg"
    svg_path.write_text(result.svg, encoding="utf-8")

    manifest_path = output_dir / "foundry_blueprint_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at": timestamp,
                "unit_system": unit_system,
                "layout": {
                    "width_mm": result.width_mm,
                    "height_mm": result.height_mm,
                    "item_count": result.item_count,
                },
                "mechanism": {
                    "mechanism_type": target.mechanism_type,
                    "display_name": target.display_name,
                    "parameter_keys": list(mechanism_params.keys()),
                },
                "automation": {
                    "controller_mechanisms": len(items),
                    "parameter_specs": [spec.key for spec in config.parameter_specs],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    metrics_path = output_dir / "foundry_blueprint_metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "duration_ms": duration_ms,
                "unit_system": unit_system,
                "mechanism_type": target.mechanism_type,
                "artifact_svg": str(svg_path),
                "manifest": str(manifest_path),
                "timestamp": timestamp,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return svg_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pick_mechanism(items: Iterable[MechanismItem], preferred_type: str) -> MechanismItem:
    for item in items:
        if item.mechanism_type == preferred_type:
            return item
    try:
        return next(iter(items))
    except StopIteration as exc:
        raise RuntimeError("No mechanisms available in controller") from exc


def _svg_panel(width: float, height: float, *, title: str, body: str, fill: str = "#ffffff") -> str:
    width = ScenarioOptimizer._positive_dimension(width, 160.0)
    height = ScenarioOptimizer._positive_dimension(height, 90.0)
    title = _escape_svg_text(str(title))
    body = _escape_svg_text(str(body))
    fill = _escape_svg_text(str(fill))
    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="8" '
        f'ry="8" fill="{fill}" stroke="#2a2a2a" stroke-width="2"/>'
        f'<text x="16" y="32" font-size="18" font-family="Arial" font-weight="bold">{title}</text>'
        f'<text x="16" y="56" font-size="12" font-family="Arial">{body}</text>'
        "</svg>"
    )


def _escape_svg_text(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "&#10;")
    )


if __name__ == "__main__":
    artifacts_dir = Path(__file__).resolve().parent / "_artifacts"
    svg_output = run_blueprint_export_scenario(artifacts_dir)
    print(f"Blueprint scenario completed: {svg_output}")
