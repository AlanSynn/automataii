"""Application-layer export/copy service for board assembly guides."""

from __future__ import annotations

import json
import math
import shutil
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from html import escape as html_escape
from pathlib import Path

from automataii.application.mechanism_foundry.mechanism_types import (
    canonical_mechanism_type,
)
from automataii.infrastructure.generation.pdf.svg_pdf import render_svgs_to_pdf
from automataii.shared.fabrication_assembly import ASSEMBLY_SCHEMA_VERSION, manifest_part_index
from automataii.shared.physical_kit import (
    DEFAULT_GRID_CELL_CM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    allowed_linkage_lengths_mm,
    finite_float,
    gear_pair_from_params,
    gear_teeth_from_params,
    grid_cell_cm_from_params,
    grid_step_mm,
    nearest_cam_preset,
    physical_profile_from_params,
    snap_physical_params,
)
from automataii.utils.paths import resolve_path


@dataclass(frozen=True, slots=True)
class FabricationGuideSummary:
    key: str
    title: str
    mechanism_type: str
    guide_svg: str
    step_count: int
    app_mechanism_type: str
    app_highlight_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FabricationGuideExportResult:
    output_dir: Path
    package_dir: Path
    copied_files: tuple[Path, ...]
    recipe_keys: tuple[str, ...]
    pdf_files: tuple[Path, ...] = ()
    fallback_files: tuple[Path, ...] = ()
    contract_warnings: tuple[str, ...] = ()


def _normalize_part_ids(raw_value: object) -> tuple[str, ...]:
    if isinstance(raw_value, str) or not isinstance(raw_value, Iterable):
        return ()
    seen: list[str] = []
    for item in raw_value:
        if not isinstance(item, str):
            continue
        part_id = item.strip()
        if part_id and part_id not in seen:
            seen.append(part_id)
    return tuple(seen)


def _active_part_ids_with_source(
    layer_data: Mapping[str, object],
) -> tuple[tuple[str, ...], str | None]:
    for key in ("active_part_ids", "app_highlight_ids", "fabrication_part_ids", "part_ids"):
        extracted = _normalize_part_ids(layer_data.get(key))
        if extracted:
            return extracted, key

    raw_fabrication = layer_data.get("fabrication")
    if isinstance(raw_fabrication, Mapping):
        extracted = _normalize_part_ids(raw_fabrication.get("active_part_ids"))
        if extracted:
            return extracted, "fabrication.active_part_ids"
    return (), None


@dataclass(frozen=True, slots=True)
class FabricationLayerSelection:
    """Typed compatibility contract for app-layer fabrication recipe selection."""

    mechanism_type: str
    active_part_ids: tuple[str, ...] = ()
    active_part_ids_source: str | None = None

    @classmethod
    def from_layer_data(cls, layer_data: Mapping[str, object]) -> FabricationLayerSelection:
        raw_type = layer_data.get("type") or layer_data.get("mechanism_type")
        raw_type = raw_type or layer_data.get("source_type") or ""
        active_part_ids, source = _active_part_ids_with_source(layer_data)
        return cls(
            mechanism_type=str(canonical_mechanism_type(raw_type)),
            active_part_ids=active_part_ids,
            active_part_ids_source=source,
        )


def active_part_ids_from_layer(layer_data: Mapping[str, object]) -> tuple[str, ...]:
    """Extract active fabrication part IDs from a mechanism-layer payload."""
    return FabricationLayerSelection.from_layer_data(layer_data).active_part_ids


class FabricationAssemblyGuideExporter:
    """Copy generated board-assembly guides without entering legacy blueprint export flow."""

    def __init__(self, fabrication_root: str | Path = "fabrication") -> None:
        root = Path(fabrication_root)
        self.fabrication_root = root if root.is_absolute() else resolve_path(root)

    @property
    def assembly_dir(self) -> Path:
        return self.fabrication_root / "assembly"

    @property
    def recipes_path(self) -> Path:
        return self.assembly_dir / "recipes.json"

    @property
    def manifest_path(self) -> Path:
        return self.fabrication_root / "manifest.json"

    def _resolve_assembly_asset(self, rel_path: str | Path) -> Path:
        """Resolve a generated assembly asset without allowing path traversal."""
        relative = Path(rel_path)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"Unsafe assembly guide path: {rel_path}")
        if relative.parts[0] != "assembly":
            relative = Path("assembly") / relative
        try:
            root = self.fabrication_root.resolve()
            source = (self.fabrication_root / relative).resolve()
            source.relative_to(root)
        except (OSError, ValueError) as exc:
            raise ValueError(f"Unsafe assembly guide path: {rel_path}") from exc
        return source

    def _resolve_fabrication_asset(self, rel_path: str | Path) -> Path:
        relative = Path(rel_path)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"Unsafe fabrication asset path: {rel_path}")
        try:
            root = self.fabrication_root.resolve()
            source = (self.fabrication_root / relative).resolve()
            source.relative_to(root)
        except (OSError, ValueError) as exc:
            raise ValueError(f"Unsafe fabrication asset path: {rel_path}") from exc
        return source

    def load_package(self) -> Mapping[str, object]:
        data = json.loads(self.recipes_path.read_text(encoding="utf-8"))
        if not isinstance(data, Mapping):
            raise ValueError("Assembly recipes.json must contain an object")
        if data.get("schema_version") != ASSEMBLY_SCHEMA_VERSION:
            raise ValueError("Unsupported assembly recipes schema")
        return data

    def load_manifest(self) -> Mapping[str, object]:
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, Mapping):
            raise ValueError("Fabrication manifest.json must contain an object")
        return data

    def list_guides(self) -> tuple[FabricationGuideSummary, ...]:
        package = self.load_package()
        raw_recipes = package.get("recipes", ())
        if not isinstance(raw_recipes, Sequence) or isinstance(raw_recipes, str):
            return ()
        summaries: list[FabricationGuideSummary] = []
        for raw_recipe in raw_recipes:
            if not isinstance(raw_recipe, Mapping):
                continue
            guide_svg = str(raw_recipe.get("guide_svg", ""))
            if not guide_svg:
                continue
            guide_source = self._resolve_assembly_asset(guide_svg)
            if not guide_source.is_file():
                continue
            steps = raw_recipe.get("steps", ())
            step_count = len(steps) if isinstance(steps, Sequence) else 0
            app_mapping = raw_recipe.get("app_mapping", {})
            app_mechanism_type = ""
            app_highlight_ids: tuple[str, ...] = ()
            if isinstance(app_mapping, Mapping):
                app_mechanism_type = canonical_mechanism_type(
                    app_mapping.get("mechanism_type", raw_recipe.get("mechanism_type", ""))
                )
                raw_highlights = app_mapping.get("highlight_ids", ())
                if isinstance(raw_highlights, Sequence) and not isinstance(raw_highlights, str):
                    app_highlight_ids = tuple(
                        str(part) for part in raw_highlights if isinstance(part, str)
                    )
            summaries.append(
                FabricationGuideSummary(
                    key=str(raw_recipe.get("key", "")),
                    title=str(raw_recipe.get("title", "")),
                    mechanism_type=canonical_mechanism_type(raw_recipe.get("mechanism_type", "")),
                    guide_svg=guide_svg,
                    step_count=step_count,
                    app_mechanism_type=app_mechanism_type,
                    app_highlight_ids=app_highlight_ids,
                )
            )
        return tuple(summary for summary in summaries if summary.key and summary.guide_svg)

    def find_guides_for_mechanism(
        self,
        mechanism_type: object,
    ) -> tuple[FabricationGuideSummary, ...]:
        """Return board guides that can represent an app/export mechanism type."""
        canonical = canonical_mechanism_type(mechanism_type)
        if not canonical:
            return ()
        return tuple(
            summary
            for summary in self.list_guides()
            if summary.mechanism_type == canonical or summary.app_mechanism_type == canonical
        )

    def resolve_app_state_to_guide(
        self,
        mechanism_type: object,
        *,
        active_part_ids: Iterable[str] | None = None,
    ) -> FabricationGuideSummary | None:
        """Map an app-level mechanism selection back to the closest board guide."""
        candidates = self.find_guides_for_mechanism(mechanism_type)
        if not candidates:
            return None
        requested_parts = set(active_part_ids or ())
        if not requested_parts:
            return candidates[0]
        exact_matches = [
            candidate
            for candidate in candidates
            if requested_parts <= set(candidate.app_highlight_ids)
        ]
        if exact_matches:
            return exact_matches[0]
        return max(
            candidates,
            key=lambda candidate: len(requested_parts & set(candidate.app_highlight_ids)),
        )

    def _selected_package(
        self,
        *,
        included_keys: set[str],
    ) -> Mapping[str, object]:
        package = dict(self.load_package())
        raw_recipes = package.get("recipes", ())
        if not isinstance(raw_recipes, Sequence) or isinstance(raw_recipes, str):
            package["recipes"] = []
            return package
        package["recipes"] = [
            recipe
            for recipe in raw_recipes
            if isinstance(recipe, Mapping) and str(recipe.get("key", "")) in included_keys
        ]
        return package

    @staticmethod
    def _recipe_part_ids(raw_recipe: object) -> tuple[str, ...]:
        if not isinstance(raw_recipe, Mapping):
            return ()
        seen: dict[str, None] = {}
        raw_parts = raw_recipe.get("parts", ())
        if isinstance(raw_parts, Sequence) and not isinstance(raw_parts, str):
            for raw_part in raw_parts:
                if isinstance(raw_part, Mapping) and isinstance(raw_part.get("part"), str):
                    seen[str(raw_part["part"])] = None
        raw_steps = raw_recipe.get("steps", ())
        if isinstance(raw_steps, Sequence) and not isinstance(raw_steps, str):
            for raw_step in raw_steps:
                if not isinstance(raw_step, Mapping):
                    continue
                step_parts = raw_step.get("parts", ())
                if isinstance(step_parts, Sequence) and not isinstance(step_parts, str):
                    for raw_part in step_parts:
                        if isinstance(raw_part, Mapping) and isinstance(raw_part.get("part"), str):
                            seen[str(raw_part["part"])] = None
                stack = raw_step.get("stack", ())
                if isinstance(stack, Sequence) and not isinstance(stack, str):
                    for raw_layer in stack:
                        if isinstance(raw_layer, Mapping) and isinstance(
                            raw_layer.get("part"), str
                        ):
                            seen[str(raw_layer["part"])] = None
        return tuple(seen)

    @staticmethod
    def _positive_count(value: object, default: int = 1) -> int:
        parsed = int(round(finite_float(value, float(default))))
        return max(1, parsed)

    @classmethod
    def _recipe_part_counts(cls, raw_recipe: object) -> dict[str, int]:
        """Return fabricated part quantities for one recipe.

        The top-level recipe ``parts`` list is the authoritative bill of
        materials.  Step/stack references are still scanned so a guide cannot
        silently omit a physical part that appears only in an instruction card.
        """
        if not isinstance(raw_recipe, Mapping):
            return {}
        counts: dict[str, int] = {}
        raw_parts = raw_recipe.get("parts", ())
        if isinstance(raw_parts, Sequence) and not isinstance(raw_parts, str):
            for raw_part in raw_parts:
                if isinstance(raw_part, Mapping) and isinstance(raw_part.get("part"), str):
                    counts[str(raw_part["part"])] = cls._positive_count(raw_part.get("count"))
        for part_id in cls._recipe_part_ids(raw_recipe):
            counts.setdefault(part_id, 1)
        return counts

    @classmethod
    def _package_part_counts(cls, package: Mapping[str, object]) -> dict[str, int]:
        raw_recipes = package.get("recipes", ())
        if not isinstance(raw_recipes, Sequence) or isinstance(raw_recipes, str):
            return {}
        totals: dict[str, int] = {}
        for raw_recipe in raw_recipes:
            for part_id, count in cls._recipe_part_counts(raw_recipe).items():
                totals[part_id] = totals.get(part_id, 0) + count
        return totals

    @staticmethod
    def _step_fastener_sites(raw_step: Mapping[str, object]) -> set[str]:
        if str(raw_step.get("action", "")) == "test-motion":
            return set()
        raw_stack = raw_step.get("stack", ())
        if not isinstance(raw_stack, Sequence) or isinstance(raw_stack, str):
            return set()
        has_fastener = any(
            isinstance(layer, Mapping) and layer.get("role") == "paper-fastener"
            for layer in raw_stack
        )
        if not has_fastener:
            return set()
        raw_coords = raw_step.get("coords", ())
        raw_roles = raw_step.get("coord_roles", ())
        if not (
            isinstance(raw_coords, Sequence)
            and not isinstance(raw_coords, str)
            and isinstance(raw_roles, Sequence)
            and not isinstance(raw_roles, str)
        ):
            return {"fastener:unplaced"}

        sites: set[str] = set()
        for coord, role in zip(raw_coords, raw_roles, strict=False):
            coord_text = str(coord)
            role_text = str(role)
            if role_text == "board":
                sites.add(f"board:{coord_text}")
            elif role_text:
                sites.add(f"moving:{role_text}:{coord_text}")
        return sites or {"fastener:unplaced"}

    @classmethod
    def _package_hardware_counts(cls, package: Mapping[str, object]) -> dict[str, int]:
        raw_recipes = package.get("recipes", ())
        if not isinstance(raw_recipes, Sequence) or isinstance(raw_recipes, str):
            return {"paper-fastener": 0}
        fastener_sites: set[str] = set()
        for raw_recipe in raw_recipes:
            if not isinstance(raw_recipe, Mapping):
                continue
            raw_steps = raw_recipe.get("steps", ())
            if not isinstance(raw_steps, Sequence) or isinstance(raw_steps, str):
                continue
            for raw_step in raw_steps:
                if isinstance(raw_step, Mapping):
                    fastener_sites.update(cls._step_fastener_sites(raw_step))
        return {"paper-fastener": len(fastener_sites)}

    @staticmethod
    def _part_label(part_id: str) -> str:
        _category, _sep, key = part_id.partition(":")
        if key.startswith("g") and key[1:].isdigit():
            return f"G{key[1:]}"
        if key.startswith("linkage-"):
            return key.replace("linkage-", "L").replace("-cell", "")
        if key.startswith("s") and key[1:].isdigit():
            return f"S{key[1:]}"
        return key.replace("-", " ").title()

    @staticmethod
    def _part_color(part_id: str) -> str:
        category, _sep, _key = part_id.partition(":")
        return {
            "gears": "#fbbf24",
            "linkages": "#60a5fa",
            "cams": "#f472b6",
            "followers": "#34d399",
            "brackets": "#a78bfa",
            "spacers": "#94a3b8",
        }.get(category, "#e5e7eb")

    def _recipe_part_sources(self, package: Mapping[str, object]) -> tuple[Path, ...]:
        manifest = self.load_manifest()
        index = manifest_part_index(manifest)
        seen: dict[str, Path] = {}
        for part_id in self._package_part_counts(package):
            item = index.get(part_id)
            if not isinstance(item, Mapping):
                continue
            raw_path = item.get("path")
            if not isinstance(raw_path, str) or not raw_path:
                continue
            source = self._resolve_fabrication_asset(raw_path)
            if source.is_file():
                seen.setdefault(part_id, source)
        return tuple(seen.values())

    def _quantity_part_sources(self, package: Mapping[str, object]) -> tuple[Path, ...]:
        """Return template sources expanded to the actual cut quantity."""
        manifest = self.load_manifest()
        index = manifest_part_index(manifest)
        expanded: list[Path] = []
        for part_id, count in self._package_part_counts(package).items():
            item = index.get(part_id)
            if not isinstance(item, Mapping):
                continue
            raw_path = item.get("path")
            if not isinstance(raw_path, str) or not raw_path:
                continue
            source = self._resolve_fabrication_asset(raw_path)
            if source.is_file():
                expanded.extend(source for _ in range(count))
        return tuple(expanded)

    def _source_path_for_part(self, part_id: str) -> str:
        item = manifest_part_index(self.load_manifest()).get(part_id)
        if not isinstance(item, Mapping):
            return ""
        raw_path = item.get("path")
        return str(raw_path) if isinstance(raw_path, str) else ""

    def _selected_parts_checklist_svg(self, package: Mapping[str, object]) -> str:
        raw_recipes = package.get("recipes", ())
        recipes = (
            [recipe for recipe in raw_recipes if isinstance(recipe, Mapping)]
            if isinstance(raw_recipes, Sequence) and not isinstance(raw_recipes, str)
            else []
        )
        part_counts = self._package_part_counts(package)
        hardware_counts = self._package_hardware_counts(package)

        row_count = max(1, len(part_counts) + len(hardware_counts))
        height = max(190, 102 + row_count * 13)
        part_rows: list[str] = []
        for index, (part_id, count) in enumerate(part_counts.items(), start=1):
            y = 92 + (index - 1) * 13
            color = self._part_color(part_id)
            label = self._part_label(part_id)
            part_rows.append(
                f'<rect x="18" y="{y - 8}" width="238" height="10" rx="2" '
                f'fill="{html_escape(color)}" fill-opacity="0.18" '
                f'stroke="{html_escape(color)}" stroke-width="0.5"/>'
                f'<circle cx="25" cy="{y - 3}" r="3" fill="{html_escape(color)}"/>'
                f'<text x="34" y="{y - 2}" class="item">{index}. {html_escape(label)}</text>'
                f'<text x="130" y="{y - 2}" class="small">{html_escape(part_id)}</text>'
                f'<text x="242" y="{y - 2}" class="item" text-anchor="end">x{count}</text>'
            )
        start = len(part_counts) + 1
        for offset, (hardware_id, count) in enumerate(hardware_counts.items()):
            y = 92 + (start + offset - 1) * 13
            part_rows.append(
                f'<rect x="18" y="{y - 8}" width="238" height="10" rx="2" '
                'fill="#fee2e2" stroke="#ef4444" stroke-width="0.5"/>'
                f'<circle cx="25" cy="{y - 3}" r="3" fill="#ef4444"/>'
                f'<text x="34" y="{y - 2}" class="item">{start + offset}. '
                f"{html_escape(hardware_id.replace('-', ' ').title())}</text>"
                f'<text x="130" y="{y - 2}" class="small">hardware — buy, do not cut</text>'
                f'<text x="242" y="{y - 2}" class="item" text-anchor="end">x{count}</text>'
            )
        recipe_text = ", ".join(str(recipe.get("title", "Guide")) for recipe in recipes) or "Guide"
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="280mm" height="{height}mm"
     viewBox="0 0 280 {height}">
  <title>MotionSmith selected fabrication checklist</title>
  <desc>LEGO-style cover page for selected board assembly recipes and needed parts only.</desc>
  <defs>
    <style>
      .title {{ font-family: Arial, Helvetica, sans-serif; font-size: 9px; font-weight: bold; fill: #111827; }}
      .heading {{ font-family: Arial, Helvetica, sans-serif; font-size: 5px; font-weight: bold; fill: #111827; }}
      .body {{ font-family: Arial, Helvetica, sans-serif; font-size: 4px; fill: #374151; }}
      .item {{ font-family: Arial, Helvetica, sans-serif; font-size: 3.7px; font-weight: bold; fill: #111827; }}
      .small {{ font-family: Arial, Helvetica, sans-serif; font-size: 3px; fill: #4b5563; }}
    </style>
  </defs>
  <rect x="8" y="8" width="264" height="{height - 16}" rx="6" fill="#ffffff" stroke="#111827" stroke-width="0.8"/>
  <text x="18" y="24" class="title">MotionSmith Board Assembly PDF</text>
  <text x="18" y="36" class="heading">Selected build(s)</text>
  <text x="18" y="44" class="body">{html_escape(recipe_text)}</text>
  <text x="18" y="58" class="heading">Use it like a LEGO guide book</text>
  <text x="18" y="67" class="body">1. Print/cut current-design-cut-sheets.pdf and kit-parts-to-cut.pdf.</text>
  <text x="18" y="75" class="body">2. Open one card at a time; only the newly-added part is highlighted.</text>
  <text x="18" y="83" class="body">3. Follow every fastener/spacer stack before moving to the next card.</text>
  <text x="18" y="96" class="heading">Needed parts and hardware only</text>
  {"".join(part_rows)}
  <text x="18" y="{height - 28}" class="heading">Hardware</text>
  <text x="18" y="{height - 19}" class="body">Paper fasteners up to 2 inch; spacers are cut parts and appear above with quantities.</text>
</svg>
'''

    def _kit_parts_cover_svg(self, package: Mapping[str, object]) -> str:
        part_counts = self._package_part_counts(package)
        row_count = max(1, len(part_counts))
        height = max(160, 72 + row_count * 14)
        rows: list[str] = []
        for index, (part_id, count) in enumerate(part_counts.items(), start=1):
            y = 62 + (index - 1) * 14
            color = self._part_color(part_id)
            rows.append(
                f'<rect x="16" y="{y - 9}" width="248" height="11" rx="2" '
                f'fill="{html_escape(color)}" fill-opacity="0.16" '
                f'stroke="{html_escape(color)}" stroke-width="0.5"/>'
                f'<text x="24" y="{y - 2}" class="item">{index}. '
                f"{html_escape(self._part_label(part_id))}</text>"
                f'<text x="112" y="{y - 2}" class="small">{html_escape(part_id)}</text>'
                f'<text x="254" y="{y - 2}" class="item" text-anchor="end">cut x{count}</text>'
            )
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="280mm" height="{height}mm"
     viewBox="0 0 280 {height}">
  <title>MotionSmith kit parts to cut</title>
  <desc>Quantity-aware cover page for fabricated parts required by the selected assembly guide.</desc>
  <defs>
    <style>
      .title {{ font-family: Arial, Helvetica, sans-serif; font-size: 9px; font-weight: bold; fill: #111827; }}
      .body {{ font-family: Arial, Helvetica, sans-serif; font-size: 4px; fill: #374151; }}
      .item {{ font-family: Arial, Helvetica, sans-serif; font-size: 3.7px; font-weight: bold; fill: #111827; }}
      .small {{ font-family: Arial, Helvetica, sans-serif; font-size: 3px; fill: #4b5563; }}
    </style>
  </defs>
  <rect x="8" y="8" width="264" height="{height - 16}" rx="6" fill="#ffffff" stroke="#111827" stroke-width="0.8"/>
  <text x="18" y="25" class="title">Kit Parts To Cut — quantity-aware</text>
  <text x="18" y="40" class="body">Only the fabrication templates needed by the selected board recipe(s) are included.</text>
  <text x="18" y="49" class="body">The following pages repeat templates by count; paper fasteners are hardware and are not cut.</text>
  {"".join(rows)}
</svg>
'''

    @staticmethod
    def _layer_params(layer_data: Mapping[str, object]) -> Mapping[str, object]:
        for key in ("params", "parameters", "mechanism_params"):
            raw = layer_data.get(key)
            if isinstance(raw, Mapping):
                return raw
        return layer_data

    @staticmethod
    def _layer_mechanism_type(layer_data: Mapping[str, object]) -> str:
        raw_type = layer_data.get("type") or layer_data.get("mechanism_type")
        raw_type = raw_type or layer_data.get("source_type") or ""
        return str(canonical_mechanism_type(raw_type))

    @staticmethod
    def _linkage_part_id_for_length(length_mm: object, grid_cell_cm: object) -> str:
        pitch_mm = grid_step_mm(grid_cell_cm)
        allowed = allowed_linkage_lengths_mm(grid_cell_cm)
        length = min(
            allowed,
            key=lambda choice: (abs(choice - finite_float(length_mm, choice)), choice),
        )
        cells = max(1, int(round(length / pitch_mm)))
        return f"linkages:linkage-{cells}-cell"

    @staticmethod
    def _part_id_for_gear_teeth(teeth: int) -> str:
        return f"gears:g{int(teeth)}"

    def _expected_part_ids_for_layer(
        self,
        mechanism_type: str,
        params: Mapping[str, object],
    ) -> tuple[str, ...]:
        """Infer the fabricated kit parts implied by current app parameters."""
        profile = physical_profile_from_params(params)
        grid_cell_cm = grid_cell_cm_from_params(params, DEFAULT_GRID_CELL_CM)
        snapped = snap_physical_params(
            mechanism_type,
            params,
            grid_cell_cm,
            profile=profile,
        )
        expected: list[str] = []

        def add(part_id: str) -> None:
            if part_id not in expected:
                expected.append(part_id)

        if mechanism_type == "gear_train":
            teeth1, _r1, teeth2, _r2 = gear_pair_from_params(snapped, profile=profile)
            add(self._part_id_for_gear_teeth(teeth1))
            add(self._part_id_for_gear_teeth(teeth2))
        elif mechanism_type == "gear_linkage":
            teeth1, _r1, teeth2, _r2 = gear_pair_from_params(snapped, profile=profile)
            add(self._part_id_for_gear_teeth(teeth1))
            add(self._part_id_for_gear_teeth(teeth2))
            add(
                self._linkage_part_id_for_length(
                    snapped.get("linkage_arm_length", grid_step_mm(grid_cell_cm) * 4.0),
                    grid_cell_cm,
                )
            )
        elif mechanism_type == "planetary_gear":
            sun_teeth = gear_teeth_from_params(
                snapped,
                ("sun_teeth",),
                ("r_sun", "sun_radius"),
                12,
                profile=profile,
            )
            planet_teeth = gear_teeth_from_params(
                snapped,
                ("planet_teeth",),
                ("r_planet", "planet_radius"),
                14,
                profile=profile,
            )
            add(f"ring_gears:ring-g{sun_teeth}-g{planet_teeth}")
            add(self._part_id_for_gear_teeth(sun_teeth))
            add(self._part_id_for_gear_teeth(planet_teeth))
            add(
                self._linkage_part_id_for_length(
                    snapped.get("carrier_arm_length", snapped.get("arm_length", 40.0)),
                    grid_cell_cm,
                )
            )
        elif mechanism_type == "cam_follower":
            cam_preset = nearest_cam_preset(snapped, grid_cell_cm, profile=profile)
            add(f"cams:{cam_preset.key}")
            add("followers:f3-round")
        elif mechanism_type == "four_bar":
            for key_group in (
                ("input_link", "l2", "L2"),
                ("coupler_link", "l3", "L3"),
                ("output_link", "l4", "L4"),
            ):
                raw_length = next((snapped[key] for key in key_group if key in snapped), None)
                if raw_length is not None:
                    add(self._linkage_part_id_for_length(raw_length, grid_cell_cm))
        elif mechanism_type == "slider_crank":
            for key_group in (("crank_length", "l2", "L2"), ("rod_length", "l3", "L3")):
                raw_length = next((snapped[key] for key in key_group if key in snapped), None)
                if raw_length is not None:
                    add(self._linkage_part_id_for_length(raw_length, grid_cell_cm))
            add("brackets:2-hole-straight")
            add("brackets:3-hole-straight")
        return tuple(expected)

    @staticmethod
    def _snapped_parameter_warnings(
        mechanism_type: str,
        params: Mapping[str, object],
    ) -> tuple[str, ...]:
        profile = physical_profile_from_params(params)
        grid_cell_cm = grid_cell_cm_from_params(params, DEFAULT_GRID_CELL_CM)
        snapped = snap_physical_params(
            mechanism_type,
            params,
            grid_cell_cm,
            profile=profile,
        )
        warnings: list[str] = []
        if params.get("grid_system_enabled") is False:
            warnings.append("physical grid is disabled; exported board recipe may not match")
        for key, raw_value in params.items():
            if key not in snapped or isinstance(raw_value, bool):
                continue
            snapped_value = snapped[key]
            if isinstance(raw_value, int | float) and isinstance(snapped_value, int | float):
                if math.isfinite(float(raw_value)) and not math.isclose(
                    float(raw_value),
                    float(snapped_value),
                    rel_tol=1e-6,
                    abs_tol=1e-6,
                ):
                    warnings.append(f"{key}={raw_value} snaps to kit value {snapped_value}")
            elif raw_value != snapped_value:
                warnings.append(f"{key}={raw_value!r} snaps to kit value {snapped_value!r}")
        return tuple(warnings)

    def build_app_physical_contract(
        self,
        mechanism_layers: Mapping[str, object],
        *,
        recipe_keys: Iterable[str] | None = None,
    ) -> Mapping[str, object]:
        """Build an app-to-fabrication consistency report for export packages."""
        selected_keys = set(recipe_keys or ())
        package = (
            self._selected_package(included_keys=selected_keys)
            if selected_keys
            else self.load_package()
        )
        raw_recipes = package.get("recipes", ())
        recipe_entries = (
            raw_recipes
            if isinstance(raw_recipes, Sequence) and not isinstance(raw_recipes, str)
            else ()
        )
        recipes = {
            str(recipe.get("key")): recipe
            for recipe in recipe_entries
            if isinstance(recipe, Mapping)
        }
        manifest = self.load_manifest()
        manifest_index = manifest_part_index(manifest)
        manifest_pitch = finite_float(
            manifest.get("grid_pitch_mm"),
            DEFAULT_PHYSICAL_KIT_PROFILE.default_pitch_mm,
        )
        manifest_hole = finite_float(
            manifest.get("hole_diameter_mm"),
            DEFAULT_PHYSICAL_KIT_PROFILE.hole_diameter_mm,
        )
        layer_reports: list[dict[str, object]] = []
        warnings: list[str] = []

        for layer_id, raw_layer in mechanism_layers.items():
            if not isinstance(raw_layer, Mapping):
                continue
            selection = FabricationLayerSelection.from_layer_data(raw_layer)
            mechanism_type = selection.mechanism_type
            params = self._layer_params(raw_layer)
            summary = self.resolve_app_state_to_guide(
                mechanism_type,
                active_part_ids=selection.active_part_ids,
            )
            recipe = recipes.get(summary.key) if summary is not None else None
            expected_parts = self._expected_part_ids_for_layer(mechanism_type, params)
            recipe_counts = self._recipe_part_counts(recipe) if recipe is not None else {}
            recipe_parts = tuple(recipe_counts)
            layer_warnings = list(self._snapped_parameter_warnings(mechanism_type, params))
            grid_cell_cm = grid_cell_cm_from_params(params, DEFAULT_GRID_CELL_CM)
            grid_pitch_mm = grid_step_mm(grid_cell_cm)
            if not math.isclose(grid_pitch_mm, manifest_pitch, abs_tol=1e-6):
                layer_warnings.append(
                    f"grid pitch {grid_pitch_mm:g}mm does not match fabrication templates {manifest_pitch:g}mm"
                )
            hole = finite_float(params.get("hole_diameter_mm"), manifest_hole)
            if not math.isclose(hole, manifest_hole, abs_tol=1e-6):
                layer_warnings.append(
                    f"hole diameter {hole:g}mm does not match fabrication templates {manifest_hole:g}mm"
                )
            if recipe is None:
                layer_warnings.append(f"no board assembly recipe for {mechanism_type}")
            missing_template_parts = tuple(
                part for part in expected_parts if part not in manifest_index
            )
            missing_recipe_parts = tuple(
                part for part in expected_parts if part not in recipe_counts
            )
            if missing_template_parts:
                layer_warnings.append(
                    "no fabrication template for expected part(s): "
                    + ", ".join(missing_template_parts)
                )
            if missing_recipe_parts:
                layer_warnings.append(
                    "selected assembly guide does not include expected app part(s): "
                    + ", ".join(missing_recipe_parts)
                )
            warnings.extend(f"{layer_id}: {warning}" for warning in layer_warnings)
            layer_reports.append(
                {
                    "layer_id": str(layer_id),
                    "mechanism_type": mechanism_type,
                    "recipe_key": summary.key if summary is not None else None,
                    "recipe_title": summary.title if summary is not None else None,
                    "active_part_ids_from_app": list(selection.active_part_ids),
                    "active_part_ids_source": selection.active_part_ids_source,
                    "expected_part_ids_from_app": list(expected_parts),
                    "recipe_part_ids": list(recipe_parts),
                    "status": "warning" if layer_warnings else "matched",
                    "warnings": layer_warnings,
                }
            )

        return {
            "schema_version": "automataii.fabrication.physical_contract.v1",
            "status": "warning" if warnings else "matched",
            "warnings": warnings,
            "board": {
                "rows": manifest.get("board_rows"),
                "columns": manifest.get("board_columns"),
                "grid_pitch_mm": manifest_pitch,
                "hole_diameter_mm": manifest_hole,
            },
            "layers": layer_reports,
            "selected_recipe_keys": sorted(selected_keys),
            "contract": (
                "Simulation parameters, app visualization metadata, assembly guide recipes, "
                "and fabricated part templates must refer to the same physical kit parts."
            ),
        }

    def _physical_contract_svg(self, contract: Mapping[str, object]) -> str:
        raw_warnings = contract.get("warnings", ())
        warnings = (
            [str(item) for item in raw_warnings if isinstance(item, str)]
            if isinstance(raw_warnings, Sequence) and not isinstance(raw_warnings, str)
            else []
        )
        status = str(contract.get("status", "matched"))
        raw_layers = contract.get("layers", ())
        layer_count = (
            len(raw_layers)
            if isinstance(raw_layers, Sequence) and not isinstance(raw_layers, str)
            else 0
        )
        shown = warnings[:8]
        row_count = max(1, len(shown))
        height = max(150, 88 + row_count * 12)
        status_color = "#16a34a" if status == "matched" else "#dc2626"
        rows: list[str] = []
        if shown:
            for index, warning in enumerate(shown, start=1):
                y = 76 + (index - 1) * 12
                rows.append(
                    f'<text x="24" y="{y}" class="warning">{index}. {html_escape(warning)}</text>'
                )
        else:
            rows.append(
                '<text x="24" y="76" class="body">All exported mechanism layers match the selected physical kit recipes.</text>'
            )
        more = ""
        if len(warnings) > len(shown):
            more = f'<text x="24" y="{height - 18}" class="body">See physical-contract.json for {len(warnings) - len(shown)} more warning(s).</text>'
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="280mm" height="{height}mm"
     viewBox="0 0 280 {height}">
  <title>MotionSmith physical contract check</title>
  <desc>Checks whether app simulation/visualization parameters match fabrication templates.</desc>
  <defs>
    <style>
      .title {{ font-family: Arial, Helvetica, sans-serif; font-size: 9px; font-weight: bold; fill: #111827; }}
      .body {{ font-family: Arial, Helvetica, sans-serif; font-size: 4px; fill: #374151; }}
      .status {{ font-family: Arial, Helvetica, sans-serif; font-size: 5px; font-weight: bold; fill: {status_color}; }}
      .warning {{ font-family: Arial, Helvetica, sans-serif; font-size: 3.4px; fill: #7f1d1d; }}
    </style>
  </defs>
  <rect x="8" y="8" width="264" height="{height - 16}" rx="6" fill="#ffffff" stroke="{status_color}" stroke-width="0.9"/>
  <text x="18" y="25" class="title">Physical Contract Check</text>
  <text x="18" y="40" class="status">Status: {html_escape(status.upper())}</text>
  <text x="18" y="52" class="body">Checked {layer_count} mechanism layer(s): simulation parameters, visualization metadata, board recipe, and cut templates.</text>
  <text x="18" y="63" class="body">Warnings mean the PDF remains useful, but the current simulation is not guaranteed to match the produced parts.</text>
  {"".join(rows)}
  {more}
</svg>
'''

    def _render_pdf_or_copy_fallback(
        self,
        *,
        svg_sources: Sequence[str | Path],
        pdf_path: Path,
        fallback_dir: Path,
    ) -> tuple[Path, ...]:
        temp_pdf_path = pdf_path.with_name(f".{pdf_path.stem}.tmp{pdf_path.suffix}")
        if temp_pdf_path.is_file():
            temp_pdf_path.unlink()
        if render_svgs_to_pdf(tuple(svg_sources), temp_pdf_path):
            temp_pdf_path.replace(pdf_path)
            return (pdf_path,)
        if temp_pdf_path.is_file():
            temp_pdf_path.unlink()
        if pdf_path.is_file():
            pdf_path.unlink()
        copied: list[Path] = []
        fallback_dir.mkdir(parents=True, exist_ok=True)
        for index, source in enumerate(svg_sources, start=1):
            if isinstance(source, Path) and source.is_file():
                target = fallback_dir / f"{index:02d}-{source.name}"
                shutil.copy2(source, target)
                copied.append(target)
            elif isinstance(source, str):
                target = fallback_dir / f"{index:02d}-checklist.svg"
                target.write_text(source, encoding="utf-8")
                copied.append(target)
        return tuple(copied)

    @staticmethod
    def _remove_legacy_export_artifacts(package_dir: Path) -> None:
        for svg_path in package_dir.glob("*.svg"):
            if svg_path.is_file():
                svg_path.unlink()
        for filename in (
            "index.html",
            "board-15x15.svg",
            "parts-overview.svg",
            "assembly-guide.pdf",
            "assembly-guide.svg",
            "needed-part-blueprints.svg",
            "needed-part-blueprints.pdf",
            "kit-parts-to-cut.svg",
            "kit-parts-to-cut.pdf",
            "physical-contract.json",
        ):
            path = package_dir / filename
            if path.is_file():
                path.unlink()
        parts_dir = package_dir / "parts"
        if parts_dir.is_dir():
            shutil.rmtree(parts_dir)
        fallback_dir = package_dir / "svg-fallback"
        if fallback_dir.is_dir():
            shutil.rmtree(fallback_dir)

    def _export_readme(self, summaries: Sequence[FabricationGuideSummary]) -> str:
        guide_lines = "\n".join(
            f"- `{summary.key}` — {summary.title} ({summary.step_count} steps)"
            for summary in summaries
        )
        return f"""# Automataii exported board assembly guides

This folder is a self-contained `assembly/` package exported from Automataii.

## How to use

1. Export **Make Parts / Cut Sheets** first when you need to fabricate character or mechanism
   components.
2. Open `assembly-guide.pdf` to identify board coordinates and follow the LEGO-style step cards.
3. Open `kit-parts-to-cut.pdf` for only the fabricated kit parts used by these guides.
4. Follow one step card at a time: place the fastener at the called-out hole, then add spacers
   and parts in the exact `Stack` row order before running the check.
5. Keep paper fasteners loose enough for rotation or sliding before flattening the tabs.

## Character attachment

- Cut character body components from the current character blueprint/cut sheet. There is no
  separate Example Character fabrication template.
- Use paper fasteners for pivot/drive holes and keep spacers between moving character parts,
  linkage layers, and the board or bracket.
- Align character drive holes to the mechanism output shown in the guide; the cut sheet makes
  parts, while this guide decides board holes and per-step stack order.

## Included guides

{guide_lines}

## Data contract

- `recipes.json` lists exactly the guide SVGs included in this export.
- `physical-contract.json` records whether current app simulation/visualization parameters match
  the selected fabrication recipe parts.
- `assembly-guide.pdf` contains the board map, physical contract check, selected-parts checklist,
  and step-card guides.
- `kit-parts-to-cut.pdf` contains only the printable kit templates used by the selected guides,
  repeated by required quantity.
- If PDF rendering is unavailable, `svg-fallback/` contains the same source guide/template SVGs.
"""

    def export_guides(
        self,
        output_dir: str | Path,
        *,
        recipe_keys: Iterable[str] | None = None,
        app_contract: Mapping[str, object] | None = None,
    ) -> FabricationGuideExportResult:
        selected = set(recipe_keys or ())
        summaries = self.list_guides()
        if selected:
            summaries = tuple(summary for summary in summaries if summary.key in selected)
        if not summaries:
            raise ValueError("No matching board assembly guides to export")

        destination = Path(output_dir)
        package_dir = destination / "assembly"
        package_dir.mkdir(parents=True, exist_ok=True)
        self._remove_legacy_export_artifacts(package_dir)
        copied: list[Path] = []
        pdf_files: list[Path] = []
        fallback_files: list[Path] = []
        package = self._selected_package(included_keys={summary.key for summary in summaries})
        recipes_target = package_dir / "recipes.json"
        recipes_target.write_text(
            json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        copied.append(recipes_target)
        contract = app_contract
        contract_warnings: tuple[str, ...] = ()
        if contract is not None:
            contract_target = package_dir / "physical-contract.json"
            contract_target.write_text(
                json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            copied.append(contract_target)
            raw_warnings = contract.get("warnings", ())
            if isinstance(raw_warnings, Sequence) and not isinstance(raw_warnings, str):
                contract_warnings = tuple(str(item) for item in raw_warnings)
        readme_target = package_dir / "README.md"
        readme_target.write_text(self._export_readme(summaries), encoding="utf-8")
        copied.append(readme_target)

        board_source = self._resolve_assembly_asset("board-15x15.svg")
        guide_sources: list[str | Path] = [
            self._selected_parts_checklist_svg(package),
            board_source,
        ]
        if contract is not None:
            guide_sources.insert(1, self._physical_contract_svg(contract))
        for summary in summaries:
            source = self._resolve_assembly_asset(summary.guide_svg)
            guide_sources.append(source)
        guide_outputs = self._render_pdf_or_copy_fallback(
            svg_sources=guide_sources,
            pdf_path=package_dir / "assembly-guide.pdf",
            fallback_dir=package_dir / "svg-fallback" / "assembly",
        )
        copied.extend(guide_outputs)
        pdf_files.extend(path for path in guide_outputs if path.suffix.lower() == ".pdf")
        fallback_files.extend(path for path in guide_outputs if path.suffix.lower() != ".pdf")

        part_sources = self._quantity_part_sources(package)
        if part_sources:
            part_outputs = self._render_pdf_or_copy_fallback(
                svg_sources=(self._kit_parts_cover_svg(package), *part_sources),
                pdf_path=package_dir / "kit-parts-to-cut.pdf",
                fallback_dir=package_dir / "svg-fallback" / "parts",
            )
            copied.extend(part_outputs)
            pdf_files.extend(path for path in part_outputs if path.suffix.lower() == ".pdf")
            fallback_files.extend(path for path in part_outputs if path.suffix.lower() != ".pdf")
        return FabricationGuideExportResult(
            output_dir=destination,
            package_dir=package_dir,
            copied_files=tuple(copied),
            recipe_keys=tuple(summary.key for summary in summaries),
            pdf_files=tuple(pdf_files),
            fallback_files=tuple(fallback_files),
            contract_warnings=contract_warnings,
        )

    def export_contract_report(
        self,
        output_dir: str | Path,
        contract: Mapping[str, object],
    ) -> Path:
        """Write the physical contract without creating assembly guide PDFs.

        Custom / Simulation-only designs still need an auditable explanation of
        why board assembly output was gated. Keeping this helper in the
        fabrication application layer avoids UI code hand-writing the contract
        path or JSON formatting.
        """
        package_dir = Path(output_dir) / "assembly"
        package_dir.mkdir(parents=True, exist_ok=True)
        self._remove_legacy_export_artifacts(package_dir)
        for stale_metadata in ("recipes.json", "README.md"):
            stale_path = package_dir / stale_metadata
            if stale_path.is_file():
                stale_path.unlink()
        contract_target = package_dir / "physical-contract.json"
        contract_target.write_text(
            json.dumps(contract, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return contract_target

    def clear_exported_package(self, output_dir: str | Path) -> Path:
        """Remove stale assembly outputs when no board guide can be generated."""
        package_dir = Path(output_dir) / "assembly"
        package_dir.mkdir(parents=True, exist_ok=True)
        self._remove_legacy_export_artifacts(package_dir)
        for stale_metadata in ("recipes.json", "README.md"):
            stale_path = package_dir / stale_metadata
            if stale_path.is_file():
                stale_path.unlink()
        return package_dir
