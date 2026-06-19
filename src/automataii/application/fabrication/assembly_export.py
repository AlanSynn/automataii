"""Application-layer export/copy service for board assembly guides."""

from __future__ import annotations

import json
import math
import re
import shutil
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from html import escape as html_escape
from pathlib import Path
from xml.etree import ElementTree as ET

from automataii.application.mechanism_foundry.mechanism_types import (
    canonical_mechanism_type,
)
from automataii.infrastructure.generation.pdf.svg_pdf import (
    PageScaleMode,
    is_valid_pdf_file,
    render_svgs_to_pdf,
)
from automataii.shared.fabrication_assembly import (
    ASSEMBLY_SCHEMA_VERSION,
    BOARD_COLUMNS,
    BOARD_ROWS,
    AssemblyValidationError,
    BoardCoord,
    board_coord_to_centered_mm,
    board_coord_to_svg_xy,
    manifest_part_index,
)
from automataii.shared.physical_kit import (
    DEFAULT_GRID_CELL_CM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    allowed_linkage_lengths_mm,
    finite_float,
    format_length_for_user,
    gear_pair_from_params,
    gear_teeth_from_params,
    grid_cell_cm_from_params,
    grid_step_mm,
    nearest_cam_preset,
    physical_profile_from_params,
    snap_physical_params,
)
from automataii.utils.paths import resolve_path

PRINT_PAGE_SIZE_MM = (215.9, 279.4)
ASSEMBLY_PAGE_SIZE_MM = (279.4, 215.9)
PRINT_MARGIN_POINTS = 18.0
_SVG_TITLE_RE = re.compile(r"<title>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
_SVG_DATA_ATTR_RE = re.compile(r'data-(?P<key>[a-z0-9_-]+)="(?P<value>[^"]*)"', re.IGNORECASE)
_SVG_BODY_RE = re.compile(r"<svg\b[^>]*>(?P<body>.*)</svg>\s*$", re.IGNORECASE | re.DOTALL)
_SVG_DEFS_RE = re.compile(r"<defs\b[^>]*>.*?</defs>", re.IGNORECASE | re.DOTALL)


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


@dataclass(frozen=True, slots=True)
class KitPartCutInstance:
    part_id: str
    source: Path
    copy_index: int
    width_mm: float
    height_mm: float
    view_box: tuple[float, float, float, float]
    body_svg: str


@dataclass(frozen=True, slots=True)
class PlacedKitPartCutInstance:
    instance: KitPartCutInstance
    x_mm: float
    y_mm: float


@dataclass(slots=True)
class KitPartCutRow:
    y_mm: float
    height_mm: float
    next_x_mm: float


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


def _compact_svg_text(value: object, *, max_chars: int, suffix: str = "… see JSON") -> str:
    """Escape a single SVG text line without letting dynamic content clip the page."""

    text = " ".join(str(value or "").split())
    if len(text) > max_chars:
        room = max(1, max_chars - len(suffix) - 1)
        text = f"{text[:room].rstrip(' ,.;:')} {suffix}"
    return html_escape(text)


def _fmt_mm(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


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
        required_part_ids: Iterable[str] | None = None,
    ) -> FabricationGuideSummary | None:
        """Map an app-level mechanism selection back to the closest board guide."""
        candidates = self.find_guides_for_mechanism(mechanism_type)
        if not candidates:
            return None
        requested_parts = set(active_part_ids or ()) | set(required_part_ids or ())
        if not requested_parts:
            return candidates[0]
        exact_matches = [
            candidate
            for candidate in candidates
            if requested_parts <= set(candidate.app_highlight_ids)
        ]
        if exact_matches:
            return exact_matches[0]
        # Do not silently downgrade an app-selected physical part to a different
        # board guide.  A near recipe is still shown in the physical contract as
        # a warning, but assembly PDFs must be selected-parts-only.
        return None

    def expected_part_ids_for_layer(
        self,
        mechanism_type: str,
        params: Mapping[str, object],
    ) -> tuple[str, ...]:
        """Infer app-selected fabrication part IDs for recipe matching."""
        return self._expected_part_ids_for_layer(mechanism_type, params)

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

    @staticmethod
    def _svg_length_mm(value: object) -> float | None:
        if not isinstance(value, str):
            return None
        match = re.match(r"\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-z%]*)", value)
        if match is None:
            return None
        try:
            number = float(match.group(1))
        except ValueError:
            return None
        if not math.isfinite(number) or number <= 0.0:
            return None
        unit = match.group(2).lower()
        if unit in {"", "mm"}:
            return number
        if unit == "cm":
            return number * 10.0
        if unit == "in":
            return number * 25.4
        if unit == "pt":
            return number * 25.4 / 72.0
        if unit == "px":
            return number * 25.4 / 96.0
        return None

    @staticmethod
    def _svg_view_box(root: ET.Element) -> tuple[float, float, float, float] | None:
        raw_view_box = root.attrib.get("viewBox")
        if not raw_view_box:
            return None
        try:
            values = tuple(float(value) for value in re.split(r"[,\s]+", raw_view_box.strip()) if value)
        except ValueError:
            return None
        if len(values) != 4:
            return None
        min_x, min_y, width, height = values
        if not all(math.isfinite(value) for value in values) or width <= 0.0 or height <= 0.0:
            return None
        return min_x, min_y, width, height

    def _kit_part_cut_instance(
        self,
        *,
        part_id: str,
        source: Path,
        copy_index: int,
    ) -> KitPartCutInstance | None:
        try:
            svg_text = source.read_text(encoding="utf-8")
            root = ET.fromstring(svg_text)
        except (OSError, ET.ParseError):
            return None

        view_box = self._svg_view_box(root)
        if view_box is None:
            return None
        _min_x, _min_y, view_width, view_height = view_box
        width_mm = self._svg_length_mm(root.attrib.get("width")) or view_width
        height_mm = self._svg_length_mm(root.attrib.get("height")) or view_height
        if width_mm <= 0.0 or height_mm <= 0.0:
            return None

        body_match = _SVG_BODY_RE.search(svg_text)
        if body_match is None:
            return None
        body_svg = _SVG_DEFS_RE.sub("", body_match.group("body")).strip()
        if not body_svg:
            return None
        return KitPartCutInstance(
            part_id=part_id,
            source=source,
            copy_index=copy_index,
            width_mm=width_mm,
            height_mm=height_mm,
            view_box=view_box,
            body_svg=body_svg,
        )

    def _quantity_part_instances(self, package: Mapping[str, object]) -> tuple[KitPartCutInstance, ...]:
        """Return cut-part templates expanded by quantity with reusable SVG geometry."""
        manifest = self.load_manifest()
        index = manifest_part_index(manifest)
        expanded: list[KitPartCutInstance] = []
        for part_id, count in self._package_part_counts(package).items():
            item = index.get(part_id)
            if not isinstance(item, Mapping):
                continue
            raw_path = item.get("path")
            if not isinstance(raw_path, str) or not raw_path:
                continue
            source = self._resolve_fabrication_asset(raw_path)
            if not source.is_file():
                continue
            for copy_index in range(1, count + 1):
                instance = self._kit_part_cut_instance(
                    part_id=part_id,
                    source=source,
                    copy_index=copy_index,
                )
                if instance is not None:
                    expanded.append(instance)
        return tuple(expanded)

    def _packed_kit_parts_cut_sheet_svgs(self, package: Mapping[str, object]) -> tuple[str, ...]:
        """Pack all required cut-part copies into actual-size Letter cut-sheet SVG pages."""
        instances = sorted(
            self._quantity_part_instances(package),
            key=lambda item: (-item.height_mm, -item.width_mm, item.part_id, item.copy_index),
        )
        if not instances:
            return ()

        page_width, page_height = PRINT_PAGE_SIZE_MM
        margin = 8.0
        header_height = 18.0
        gap = 4.0
        usable_width = page_width - 2.0 * margin
        max_x = page_width - margin
        max_y = page_height - margin

        pages: list[list[PlacedKitPartCutInstance]] = []
        rows_by_page: list[list[KitPartCutRow]] = []

        for instance in instances:
            part_width = instance.width_mm
            part_height = instance.height_mm
            placed = False
            for page_index, rows in enumerate(rows_by_page):
                for row in rows:
                    if (
                        part_height <= row.height_mm + 0.001
                        and row.next_x_mm + part_width <= max_x + 0.001
                    ):
                        pages[page_index].append(
                            PlacedKitPartCutInstance(
                                instance=instance,
                                x_mm=row.next_x_mm,
                                y_mm=row.y_mm,
                            )
                        )
                        row.next_x_mm += part_width + gap
                        placed = True
                        break
                if placed:
                    break

                next_y = (
                    margin + header_height
                    if not rows
                    else max(row.y_mm + row.height_mm for row in rows) + gap
                )
                if part_width <= usable_width + 0.001 and next_y + part_height <= max_y + 0.001:
                    rows.append(
                        KitPartCutRow(
                            y_mm=next_y,
                            height_mm=part_height,
                            next_x_mm=margin + part_width + gap,
                        )
                    )
                    pages[page_index].append(
                        PlacedKitPartCutInstance(instance=instance, x_mm=margin, y_mm=next_y)
                    )
                    placed = True
                    break

            if placed:
                continue

            rows_by_page.append(
                [
                    KitPartCutRow(
                        y_mm=margin + header_height,
                        height_mm=part_height,
                        next_x_mm=margin + part_width + gap,
                    )
                ]
            )
            pages.append(
                [
                    PlacedKitPartCutInstance(
                        instance=instance,
                        x_mm=margin,
                        y_mm=margin + header_height,
                    )
                ]
            )

        return tuple(
            self._kit_parts_cut_sheet_page_svg(placed, page_index=index, page_count=len(pages))
            for index, placed in enumerate(pages, start=1)
        )

    def _kit_parts_cut_sheet_page_svg(
        self,
        placed_parts: Sequence[PlacedKitPartCutInstance],
        *,
        page_index: int,
        page_count: int,
    ) -> str:
        width, height = PRINT_PAGE_SIZE_MM
        count = len(placed_parts)
        groups: list[str] = []
        for placed in placed_parts:
            instance = placed.instance
            min_x, min_y, view_width, view_height = instance.view_box
            scale_x = instance.width_mm / view_width
            scale_y = instance.height_mm / view_height
            part_label = self._part_label(instance.part_id)
            groups.append(
                f'<g class="packed-kit-part" data-part-id="{html_escape(instance.part_id)}" '
                f'data-source-path="{html_escape(instance.source.name)}" '
                f'data-copy-index="{instance.copy_index}" '
                f'transform="translate({_fmt_mm(placed.x_mm)} {_fmt_mm(placed.y_mm)}) '
                f'scale({_fmt_mm(scale_x)} {_fmt_mm(scale_y)}) '
                f'translate({_fmt_mm(-min_x)} {_fmt_mm(-min_y)})">'
                f"{instance.body_svg}</g>"
                f'<rect x="{_fmt_mm(placed.x_mm)}" y="{_fmt_mm(placed.y_mm)}" '
                f'width="{_fmt_mm(instance.width_mm)}" height="{_fmt_mm(instance.height_mm)}" '
                f'rx="1.4" class="pack-boundary"/>'
                f'<text x="{_fmt_mm(placed.x_mm)}" y="{_fmt_mm(max(4.0, placed.y_mm - 1.4))}" '
                f'class="pack-label">{html_escape(part_label)} #{instance.copy_index}</text>'
            )
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm"
     viewBox="0 0 {width} {height}" data-layout-kind="kit-parts-compact-cut-sheet"
     data-actual-size="true" data-packed-part-count="{count}">
  <title>MotionSmith kit parts compact cut sheet page {page_index}</title>
  <desc>Actual-size Letter cut sheet packing multiple required kit parts onto one page.</desc>
  <defs>
    <style>
      .cut {{ fill: #ffffff; stroke: #ed1c24; stroke-width: 0.35; vector-effect: non-scaling-stroke; }}
      .drill {{ fill: none; stroke: #0071bc; stroke-width: 0.28; vector-effect: non-scaling-stroke; }}
      .score {{ fill: none; stroke: #777777; stroke-width: 0.22; stroke-dasharray: 1.2 1.2; vector-effect: non-scaling-stroke; }}
      .label {{ font-family: Arial, Helvetica, sans-serif; font-size: 3px; fill: #333333; }}
      .tiny {{ font-family: Arial, Helvetica, sans-serif; font-size: 2.4px; fill: #333333; }}
      .small {{ font-family: Arial, Helvetica, sans-serif; font-size: 2.7px; fill: #333333; }}
      .pack-label {{ font-family: Arial, Helvetica, sans-serif; font-size: 2.8px; font-weight: bold; fill: #111827; }}
      .pack-boundary {{ fill: none; stroke: #d1d5db; stroke-width: 0.18; stroke-dasharray: 1.6 1.6; }}
    </style>
  </defs>
  <rect x="4" y="4" width="{width - 8}" height="{height - 8}" rx="3" fill="#ffffff" stroke="#d1d5db" stroke-width="0.35"/>
  <text x="8" y="11" class="pack-label">Kit Parts To Cut — compact actual-size page {page_index}/{page_count}</text>
  <text x="8" y="16" class="tiny">Print at 100%. Parts below are packed by quantity; paper fasteners are hardware, not cut parts.</text>
  {"".join(groups)}
</svg>
'''

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
        width, height = ASSEMBLY_PAGE_SIZE_MM
        entries: list[tuple[str, str, str, str, str]] = []
        for index, (part_id, count) in enumerate(part_counts.items(), start=1):
            entries.append(
                (
                    str(index),
                    self._part_label(part_id),
                    part_id,
                    f"x{count}",
                    self._part_color(part_id),
                )
            )
        start = len(entries) + 1
        for offset, (hardware_id, count) in enumerate(hardware_counts.items()):
            entries.append(
                (
                    str(start + offset),
                    hardware_id.replace("-", " ").title(),
                    "hardware — buy, do not cut",
                    f"x{count}",
                    "#ef4444",
                )
            )
        shown_entries = entries[:14]
        hidden_count = max(0, len(entries) - len(shown_entries))
        part_rows: list[str] = []
        for row_index, (index_text, label, detail, count_text, color) in enumerate(shown_entries):
            col = 0 if row_index < 7 else 1
            row = row_index if col == 0 else row_index - 7
            x = 18 + col * 128
            y = 106 + row * 13
            part_rows.append(
                f'<rect x="{x}" y="{y - 8}" width="112" height="10" rx="2" '
                f'fill="{html_escape(color)}" fill-opacity="0.18" '
                f'stroke="{html_escape(color)}" stroke-width="0.5"/>'
                f'<circle cx="{x + 7}" cy="{y - 3}" r="3" fill="{html_escape(color)}"/>'
                f'<text x="{x + 14}" y="{y - 4}" class="item">{index_text}. '
                f'{_compact_svg_text(label, max_chars=25, suffix="…")}</text>'
                f'<text x="{x + 14}" y="{y + 0.7}" class="small">'
                f'{_compact_svg_text(detail, max_chars=38, suffix="…")}</text>'
                f'<text x="{x + 107}" y="{y - 2}" class="item" text-anchor="end">'
                f"{html_escape(count_text)}</text>"
            )
        more = ""
        if hidden_count:
            more = (
                f'<text x="18" y="196" class="body">See recipes.json for '
                f"{hidden_count} more item(s).</text>"
            )
        recipe_text = ", ".join(str(recipe.get("title", "Guide")) for recipe in recipes) or "Guide"
        recipe_text = _compact_svg_text(recipe_text, max_chars=112, suffix="… see recipes.json")
        board_pitch = format_length_for_user(
            grid_step_mm(DEFAULT_GRID_CELL_CM),
            include_board_spaces=False,
        )
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm"
     viewBox="0 0 {width} {height}">
  <title>MotionSmith selected fabrication checklist</title>
  <desc>LEGO-style cover page for selected board assembly recipes and needed parts only.</desc>
  <defs>
    <style>
      .title {{ font-family: Arial, Helvetica, sans-serif; font-size: 9px; font-weight: bold; fill: #111827; }}
      .heading {{ font-family: Arial, Helvetica, sans-serif; font-size: 5px; font-weight: bold; fill: #111827; }}
      .body {{ font-family: Arial, Helvetica, sans-serif; font-size: 4px; fill: #374151; }}
      .item {{ font-family: Arial, Helvetica, sans-serif; font-size: 3.55px; font-weight: bold; fill: #111827; }}
      .small {{ font-family: Arial, Helvetica, sans-serif; font-size: 2.75px; fill: #4b5563; }}
    </style>
  </defs>
  <rect x="8" y="8" width="{width - 16}" height="{height - 16}" rx="6" fill="#ffffff" stroke="#111827" stroke-width="0.8"/>
  <text x="18" y="24" class="title">MotionSmith Board Assembly PDF</text>
  <text x="18" y="36" class="heading">Selected build(s)</text>
  <text x="18" y="44" class="body">{recipe_text}</text>
  <text x="18" y="58" class="heading">Use it like a LEGO guide book</text>
  <text x="18" y="67" class="body">1. Print/cut the current-design cut sheet and kit-parts-to-cut.pdf.</text>
  <text x="18" y="75" class="body">2. Open one card at a time; only the newly-added part is highlighted.</text>
  <text x="18" y="83" class="body">3. Follow every fastener/spacer stack before moving to the next card.</text>
  <text x="18" y="91" class="body">Board scale: 1 board space = {board_pitch}; coordinates use the 15×15 hole grid.</text>
  <text x="18" y="101" class="heading">Needed parts and hardware only</text>
  {"".join(part_rows)}
  {more}
  <text x="18" y="{height - 18}" class="heading">Hardware</text>
  <text x="18" y="{height - 9}" class="body">Paper fasteners up to 2 in; spacers are cut parts and appear above with quantities.</text>
</svg>
'''

    def _kit_parts_cover_svg(self, package: Mapping[str, object]) -> str:
        part_counts = self._package_part_counts(package)
        width, height = PRINT_PAGE_SIZE_MM
        rows: list[str] = []
        max_rows = 15
        for index, (part_id, count) in enumerate(tuple(part_counts.items())[:max_rows], start=1):
            y = 62 + (index - 1) * 13.5
            color = self._part_color(part_id)
            rows.append(
                f'<rect x="16" y="{y - 9}" width="184" height="10.8" rx="2" '
                f'fill="{html_escape(color)}" fill-opacity="0.16" '
                f'stroke="{html_escape(color)}" stroke-width="0.5"/>'
                f'<text x="24" y="{y - 4}" class="item">{index}. '
                f"{html_escape(self._part_label(part_id))}</text>"
                f'<text x="24" y="{y + 0.8}" class="small">'
                f'{_compact_svg_text(part_id, max_chars=46, suffix="…")}</text>'
                f'<text x="194" y="{y - 2}" class="item" text-anchor="end">cut x{count}</text>'
            )
        if len(part_counts) > max_rows:
            rows.append(
                f'<text x="24" y="{62 + max_rows * 13.5}" class="body">'
                f"See recipes.json for {len(part_counts) - max_rows} more part type(s).</text>"
            )
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm"
     viewBox="0 0 {width} {height}">
  <title>MotionSmith kit parts to cut</title>
  <desc>Quantity-aware cover page for fabricated parts required by the selected assembly guide.</desc>
  <defs>
    <style>
      .title {{ font-family: Arial, Helvetica, sans-serif; font-size: 8px; font-weight: bold; fill: #111827; }}
      .body {{ font-family: Arial, Helvetica, sans-serif; font-size: 3.7px; fill: #374151; }}
      .item {{ font-family: Arial, Helvetica, sans-serif; font-size: 3.45px; font-weight: bold; fill: #111827; }}
      .small {{ font-family: Arial, Helvetica, sans-serif; font-size: 2.7px; fill: #4b5563; }}
    </style>
  </defs>
  <rect x="8" y="8" width="{width - 16}" height="{height - 16}" rx="6" fill="#ffffff" stroke="#111827" stroke-width="0.8"/>
  <text x="18" y="25" class="title">Kit Parts To Cut — compact quantity-aware</text>
  <text x="18" y="40" class="body">Only templates needed by the selected board recipe(s) are included.</text>
  <text x="18" y="49" class="body">Following pages pack as many actual-size parts as possible onto Letter sheets.</text>
  <text x="18" y="57" class="body">Paper fasteners are hardware; spacers/brackets/linkages/gears/cams/followers are cut parts.</text>
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

    @staticmethod
    def _follower_part_id_for_params(params: Mapping[str, object]) -> str:
        raw_key = params.get("follower_preset_key") or params.get("follower_key")
        if isinstance(raw_key, str):
            key = raw_key.strip()
            if key.startswith("followers:"):
                return key
            if key in {"f3-round", "f4-roller", "f5-flat", "f6-linkage-output"}:
                return f"followers:{key}"

        raw_type = str(params.get("follower_type", "")).strip().lower().replace("-", "_")
        aliases = {
            "": "followers:f3-round",
            "round": "followers:f3-round",
            "round_nose": "followers:f3-round",
            "knife": "followers:f3-round",
            "knife_edge": "followers:f3-round",
            "roller": "followers:f4-roller",
            "roller_pin": "followers:f4-roller",
            "flat": "followers:f5-flat",
            "flat_shoe": "followers:f5-flat",
            "linkage": "followers:f6-linkage-output",
            "linkage_output": "followers:f6-linkage-output",
        }
        return aliases.get(raw_type, "followers:f3-round")

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
            add(self._follower_part_id_for_params(params))
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
    def _snapped_parameter_adjustments(
        mechanism_type: str,
        params: Mapping[str, object],
    ) -> tuple[str, ...]:
        """Describe values that will be normalized to the nearest kit preset.

        These are intentionally informational rather than blocking warnings:
        exporting a board guide should use the same snap rules as the Design and
        Foundry tabs, not strand the user with a cut sheet and a JSON file.
        """
        profile = physical_profile_from_params(params)
        grid_cell_cm = grid_cell_cm_from_params(params, DEFAULT_GRID_CELL_CM)
        snapped = snap_physical_params(
            mechanism_type,
            params,
            grid_cell_cm,
            profile=profile,
        )
        adjustments: list[str] = []
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
                    adjustments.append(f"{key}={raw_value} snaps to kit value {snapped_value}")
            elif raw_value != snapped_value:
                adjustments.append(f"{key}={raw_value!r} snaps to kit value {snapped_value!r}")
        return tuple(adjustments)

    @staticmethod
    def _snapped_parameter_warnings(params: Mapping[str, object]) -> tuple[str, ...]:
        """Return only hard physical-contract blockers.

        Snap-to-preset differences are no longer blockers because export now
        normalizes a fabrication package to the nearest supported kit values.
        """
        warnings: list[str] = []
        if params.get("grid_system_enabled") is False:
            warnings.append("physical grid is disabled; exported board recipe may not match")
        return tuple(warnings)

    @classmethod
    def _recipe_board_placements(
        cls,
        recipe: Mapping[str, object] | None,
        pitch_mm: float,
    ) -> tuple[dict[str, object], ...]:
        """Expose exact recipe coordinates in the same frame as the app scene.

        Assembly/PDF pages draw in a top-left SVG frame, while Foundry and
        Design previews use a center-origin scene frame.  The contract records
        both the semantic board label and the center-origin millimeter point so
        exported packages can be audited 1:1 against what the user saw.
        """

        if recipe is None:
            return ()
        raw_steps = recipe.get("steps", ())
        if not isinstance(raw_steps, Sequence) or isinstance(raw_steps, str):
            return ()

        placements: list[dict[str, object]] = []
        for raw_step in raw_steps:
            if not isinstance(raw_step, Mapping):
                continue
            points: list[dict[str, object]] = []
            roles = cls._sequence_strings(raw_step.get("coord_roles", ()))
            for index, coord_text in enumerate(cls._sequence_strings(raw_step.get("coords", ()))):
                try:
                    coord = BoardCoord.from_label(coord_text)
                    board_x, board_y = coord.board_space_xy(origin="center")
                    mm_x, mm_y = board_coord_to_centered_mm(coord.label, pitch_mm)
                except AssemblyValidationError:
                    continue
                role = roles[index] if index < len(roles) else ""
                points.append(
                    {
                        "coord": coord.label,
                        "role": role,
                        "board_space_xy": [round(board_x, 3), round(board_y, 3)],
                        "centered_mm": [round(mm_x, 3), round(mm_y, 3)],
                    }
                )
            if not points:
                continue
            placements.append(
                {
                    "step": raw_step.get("n"),
                    "action": raw_step.get("action"),
                    "title": raw_step.get("title"),
                    "points": points,
                }
            )
        return tuple(placements)

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
            expected_parts = self._expected_part_ids_for_layer(mechanism_type, params)
            summary = self.resolve_app_state_to_guide(
                mechanism_type,
                active_part_ids=selection.active_part_ids,
                required_part_ids=expected_parts,
            )
            recipe = recipes.get(summary.key) if summary is not None else None
            recipe_counts = self._recipe_part_counts(recipe) if recipe is not None else {}
            recipe_parts = tuple(recipe_counts)
            recipe_board_placements = self._recipe_board_placements(recipe, manifest_pitch)
            snapped_adjustments = list(self._snapped_parameter_adjustments(mechanism_type, params))
            layer_warnings = list(self._snapped_parameter_warnings(params))
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
            active_parts = tuple(selection.active_part_ids)
            unknown_active_parts = tuple(
                part for part in active_parts if part not in manifest_index
            )
            active_parts_missing_recipe = tuple(
                part for part in active_parts if part not in recipe_counts
            )
            missing_template_parts = tuple(
                part for part in expected_parts if part not in manifest_index
            )
            missing_recipe_parts = tuple(
                part for part in expected_parts if part not in recipe_counts
            )
            if unknown_active_parts:
                layer_warnings.append(
                    "no fabrication template for active app-selected part(s): "
                    + ", ".join(unknown_active_parts)
                )
            if active_parts_missing_recipe:
                active_prefix = (
                    "no board assembly recipe contains active app-selected part(s): "
                    if recipe is None
                    else "selected assembly guide does not include active app-selected part(s): "
                )
                layer_warnings.append(active_prefix + ", ".join(active_parts_missing_recipe))
            if missing_template_parts:
                layer_warnings.append(
                    "no fabrication template for expected part(s): "
                    + ", ".join(missing_template_parts)
                )
            if missing_recipe_parts:
                recipe_prefix = (
                    "no board assembly recipe contains expected app part(s): "
                    if recipe is None
                    else "selected assembly guide does not include expected app part(s): "
                )
                layer_warnings.append(recipe_prefix + ", ".join(missing_recipe_parts))
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
                    "recipe_board_placements": list(recipe_board_placements),
                    "active_part_ids_missing_from_recipe": list(active_parts_missing_recipe),
                    "snapped_parameter_adjustments": snapped_adjustments,
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
                "scene_origin": "H8",
                "scene_coordinate_frame": "+x right, +y down, one board space equals grid_pitch_mm",
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
        width = ASSEMBLY_PAGE_SIZE_MM[0]
        status_color = "#16a34a" if status == "matched" else "#dc2626"
        rows: list[str] = []
        if shown:
            for index, warning in enumerate(shown, start=1):
                y = 76 + (index - 1) * 12
                warning_text = _compact_svg_text(
                    warning,
                    max_chars=118,
                    suffix="… see physical-contract.json",
                )
                rows.append(f'<text x="24" y="{y}" class="warning">{index}. {warning_text}</text>')
        else:
            rows.append(
                '<text x="24" y="76" class="body">All exported mechanism layers match the selected physical kit recipes.</text>'
            )
        more = ""
        if len(warnings) > len(shown):
            more = f'<text x="24" y="{height - 18}" class="body">See physical-contract.json for {len(warnings) - len(shown)} more warning(s).</text>'
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm"
     viewBox="0 0 {width} {height}">
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
  <rect x="8" y="8" width="{width - 16}" height="{height - 16}" rx="6" fill="#ffffff" stroke="{status_color}" stroke-width="0.9"/>
  <text x="18" y="25" class="title">Physical Contract Check</text>
  <text x="18" y="40" class="status">Status: {html_escape(status.upper())}</text>
  <text x="18" y="52" class="body">Checked {layer_count} mechanism layer(s): simulation parameters, visualization metadata, board recipe, and cut templates.</text>
  <text x="18" y="63" class="body">Warnings mean the PDF remains useful, but the current simulation is not guaranteed to match the produced parts.</text>
  {"".join(rows)}
  {more}
</svg>
'''

    @staticmethod
    def _wrapped_lines(text: object, *, max_chars: int, max_lines: int = 3) -> tuple[str, ...]:
        words = " ".join(str(text or "").split()).split()
        if not words:
            return ("",)
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
        if current and len(lines) < max_lines:
            lines.append(current)
        if len(lines) == max_lines and words:
            original = " ".join(words)
            if len(" ".join(lines)) < len(original):
                lines[-1] = lines[-1].rstrip(" .,;") + "…"
        return tuple(lines or ("",))

    @staticmethod
    def _text_lines(
        *,
        x: float,
        y: float,
        lines: Sequence[str],
        class_name: str,
        line_height: float,
        anchor: str = "start",
    ) -> str:
        font_sizes = {
            "instruction": 4.6,
            "body": 3.25,
            "body-strong": 3.55,
            "tiny": 3.0,
            "footer": 3.0,
        }
        font_size = font_sizes.get(class_name, 3.25)
        return "".join(
            f'<text x="{x:.1f}" y="{y + index * line_height:.1f}" '
            f'class="{html_escape(class_name)}" text-anchor="{html_escape(anchor)}" '
            f'font-family="Arial, Helvetica, sans-serif" font-size="{font_size:.2f}">'
            f"{html_escape(line)}</text>"
            for index, line in enumerate(lines)
        )

    @staticmethod
    def _coord_to_xy(label: object, *, x: float, y: float, size: float) -> tuple[float, float] | None:
        try:
            point = board_coord_to_svg_xy(str(label), x=x, y=y, size=size)
            return (float(point[0]), float(point[1]))
        except AssemblyValidationError:
            return None

    @staticmethod
    def _sequence_strings(value: object) -> tuple[str, ...]:
        if isinstance(value, Sequence) and not isinstance(value, str):
            return tuple(str(item) for item in value)
        return ()

    @classmethod
    def _step_coords(cls, step: Mapping[str, object]) -> tuple[str, ...]:
        return cls._sequence_strings(step.get("coords", ()))

    @classmethod
    def _step_coord_roles(cls, step: Mapping[str, object]) -> tuple[str, ...]:
        return cls._sequence_strings(step.get("coord_roles", ()))

    @classmethod
    def _step_board_coords(cls, step: Mapping[str, object]) -> tuple[str, ...]:
        coords = cls._step_coords(step)
        roles = cls._step_coord_roles(step)
        return tuple(coord for coord, role in zip(coords, roles, strict=False) if role == "board")

    @classmethod
    def _step_reference_coords(cls, step: Mapping[str, object]) -> tuple[str, ...]:
        coords = cls._step_coords(step)
        roles = cls._step_coord_roles(step)
        return tuple(coord for coord, role in zip(coords, roles, strict=False) if role != "board")

    @staticmethod
    def _step_part_ids(step: Mapping[str, object]) -> tuple[str, ...]:
        parts = step.get("parts", ())
        if not isinstance(parts, Sequence) or isinstance(parts, str):
            return ()
        found: list[str] = []
        for raw_part in parts:
            part_id = raw_part.get("part") if isinstance(raw_part, Mapping) else raw_part
            if isinstance(part_id, str) and part_id and part_id not in found:
                found.append(part_id)
        return tuple(found)

    @staticmethod
    def _step_stack_layers(step: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
        stack = step.get("stack", ())
        if not isinstance(stack, Sequence) or isinstance(stack, str):
            return ()
        return tuple(layer for layer in stack if isinstance(layer, Mapping))

    @staticmethod
    def _step_ghost_parts(step: Mapping[str, object]) -> tuple[str, ...]:
        state = step.get("visual_state", {})
        if not isinstance(state, Mapping):
            return ()
        ghosts = state.get("ghost_parts", ())
        if not isinstance(ghosts, Sequence) or isinstance(ghosts, str):
            return ()
        return tuple(str(part) for part in ghosts)

    def _stack_label(self, layer: Mapping[str, object]) -> str:
        role = str(layer.get("role", ""))
        label = str(layer.get("label", role))
        if role == "paper-fastener":
            return "Paper fastener"
        if role == "fastener-tabs":
            return "Tabs loose"
        if role in {"spacer", "top-spacer"}:
            part = str(layer.get("part", ""))
            return self._part_label(part) if part else label.replace(" spacer", "")
        if role == "moving-part":
            part = str(layer.get("part", ""))
            return self._part_label(part) if part else label
        if role == "board":
            return label.replace("Board hole ", "Board ")
        if role.startswith("repeat"):
            return label.replace("Repeat this stack", "Repeat")
        return label

    def _board_grid_svg(
        self,
        *,
        x: float,
        y: float,
        size: float,
        active: Sequence[str] = (),
        references: Sequence[str] = (),
        show_all_labels: bool = True,
    ) -> str:
        pitch = size / 14.0
        active_set = {coord.upper() for coord in active}
        ref_set = {coord.upper() for coord in references}
        parts = [
            f'<rect x="{x - 6:.1f}" y="{y - 6:.1f}" width="{size + 12:.1f}" height="{size + 12:.1f}" class="board-frame"/>'
        ]
        if show_all_labels:
            for col in BOARD_COLUMNS:
                cx = x + (col - 1) * pitch
                parts.append(
                    f'<text x="{cx:.1f}" y="{y - 9:.1f}" class="board-label" '
                    f'text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
                    f'font-size="2.35">{col}</text>'
                )
            for index, row in enumerate(BOARD_ROWS):
                cy = y + index * pitch + 1.3
                parts.append(
                    f'<text x="{x - 10:.1f}" y="{cy:.1f}" class="board-label" '
                    f'text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
                    f'font-size="2.35">{row}</text>'
                )
        for row in BOARD_ROWS:
            for col in BOARD_COLUMNS:
                label = f"{row}{col}"
                xy = self._coord_to_xy(label, x=x, y=y, size=size)
                if xy is None:
                    continue
                cx, cy = xy
                class_name = "board-hole"
                if label in active_set:
                    class_name = "board-hole active-hole"
                elif label in ref_set:
                    class_name = "board-hole reference-hole"
                parts.append(
                    f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="1.25" class="{class_name}" data-board-coord="{label}"/>'
                )
        for label in tuple(active_set) + tuple(ref_set):
            xy = self._coord_to_xy(label, x=x, y=y, size=size)
            if xy is None:
                continue
            cx, cy = xy
            bubble_y = cy - 5.2 if cy > y + size * 0.18 else cy + 9.0
            parts.append(
                f'<rect x="{cx - 6:.1f}" y="{bubble_y - 5.2:.1f}" width="12" height="6.2" rx="2.4" class="coord-bubble"/>'
                f'<text x="{cx:.1f}" y="{bubble_y - 1.0:.1f}" class="coord-bubble-text" '
                f'text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
                f'font-size="2.40">{html_escape(label)}</text>'
            )
        return "".join(parts)


    @staticmethod
    def _part_category(part_id: str) -> str:
        category, _sep, _key = part_id.partition(":")
        return category

    @staticmethod
    def _mini_gear_teeth(part_id: str) -> int:
        _category, _sep, key = part_id.partition(":")
        if key.startswith("g") and key[1:].isdigit():
            return int(key[1:])
        return 12

    @staticmethod
    def _mini_gear_path(cx: float, cy: float, radius: float, teeth: int) -> str:
        points: list[tuple[float, float]] = []
        safe_teeth = max(6, min(int(teeth), 32))
        root = max(1.0, radius * 0.80)
        for tooth in range(safe_teeth):
            base = 2.0 * math.pi * tooth / safe_teeth
            for fraction, point_radius in ((0.08, root), (0.28, radius), (0.56, radius), (0.82, root)):
                theta = base + 2.0 * math.pi * fraction / safe_teeth
                points.append(
                    (cx + point_radius * math.cos(theta), cy + point_radius * math.sin(theta))
                )
        if not points:
            return ""
        commands = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
        commands.extend(f"L {x:.1f} {y:.1f}" for x, y in points[1:])
        commands.append("Z")
        return " ".join(commands)

    @staticmethod
    def _placement_state_class(state: str) -> str:
        return "placed-part-new" if state == "new" else "placed-part-ghost"

    @staticmethod
    def _data_attrs(**values: object) -> str:
        attrs: list[str] = []
        for key, value in values.items():
            if value is None:
                continue
            attrs.append(f'data-{key.replace("_", "-")}="{html_escape(str(value))}"')
        return " ".join(attrs)

    def _placement_points(
        self,
        coords: Sequence[str],
        *,
        x: float,
        y: float,
        size: float,
    ) -> tuple[tuple[str, float, float], ...]:
        points: list[tuple[str, float, float]] = []
        for coord in coords:
            xy = self._coord_to_xy(coord, x=x, y=y, size=size)
            if xy is None:
                continue
            points.append((coord, xy[0], xy[1]))
        return tuple(points)

    def _draw_visual_part(
        self,
        part_id: str,
        points: Sequence[tuple[str, float, float]],
        *,
        state: str,
        step_n: int,
        part_index: int,
        coord_roles: Sequence[str] = (),
    ) -> str:
        if not points:
            return ""
        category = self._part_category(part_id)
        color = self._part_color(part_id)
        state_class = self._placement_state_class(state)
        coord_labels = ",".join(point[0] for point in points)
        role_labels = ",".join(coord_roles)
        attrs = self._data_attrs(
            step=step_n,
            part_key=part_id,
            placement_state=state,
            board_coord=coord_labels,
            coordinate_role=role_labels,
            part_index=part_index,
        )

        def point_at(index: int = 0) -> tuple[float, float]:
            _label, px, py = points[min(index, len(points) - 1)]
            return px, py

        if category == "ring_gears" and len(points) >= 2:
            cx = sum(point[1] for point in points) / len(points)
            cy = sum(point[2] for point in points) / len(points)
            radius = max(10.0, max(math.hypot(cx - point[1], cy - point[2]) for point in points))
            mount_holes = "".join(
                f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="1.4" class="placed-part-hole {state_class}" {attrs}/>'
                for _label, hx, hy in points
            )
            return (
                f'<g class="placed-part visual-ring-gear {state_class}" {attrs}>'
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius + 5.0:.1f}" '
                f'fill="{html_escape(color)}" fill-opacity="0.20" stroke="#92400e" stroke-width="2.0"/>'
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{max(4.0, radius * 0.58):.1f}" '
                f'fill="#ffffff" fill-opacity="0.70" stroke="#92400e" stroke-width="1.0"/>'
                f'{mount_holes}'
                f'</g>'
            )

        if category == "gears":
            px, py = point_at(max(0, part_index - 1))
            teeth = self._mini_gear_teeth(part_id)
            radius = max(6.2, min(11.5, teeth * 0.55))
            hole_ring = "".join(
                f'<circle cx="{px + radius * 0.50 * math.cos(2 * math.pi * i / 4):.1f}" '
                f'cy="{py + radius * 0.50 * math.sin(2 * math.pi * i / 4):.1f}" r="1.0" '
                f'class="placed-part-hole gear-handle-hole {state_class}" {attrs}/>'
                for i in range(4)
            )
            return (
                f'<g class="placed-part visual-gear {state_class}" {attrs}>'
                f'<path d="{self._mini_gear_path(px, py, radius, teeth)}" fill="{html_escape(color)}" '
                f'fill-opacity="0.58" stroke="#78350f" stroke-width="1.1" stroke-linejoin="round"/>'
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.1" fill="#ffffff" stroke="#78350f" stroke-width="0.9"/>'
                f'{hole_ring}'
                f'</g>'
            )

        if category in {"linkages", "brackets", "followers"} and len(points) >= 2:
            first = points[0]
            last = points[-1]
            x1, y1 = first[1], first[2]
            x2, y2 = last[1], last[2]
            width = 6.2 if category == "linkages" else 7.2
            holes = "".join(
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="1.7" class="placed-part-hole {category}-hole {state_class}" {attrs}/>'
                for _label, px, py in (first, last)
            )
            return (
                f'<g class="placed-part visual-bar {category} {state_class}" {attrs}>'
                f'<path d="M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}" fill="none" '
                f'stroke="{html_escape(color)}" stroke-opacity="0.78" stroke-width="{width:.1f}" stroke-linecap="round"/>'
                f'<path d="M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}" fill="none" '
                f'stroke="#1f2937" stroke-opacity="0.35" stroke-width="0.8" stroke-linecap="round"/>'
                f'{holes}'
                f'</g>'
            )

        if category == "cams":
            px, py = point_at(max(0, part_index - 1))
            return (
                f'<path class="placed-part visual-cam {state_class}" {attrs} '
                f'd="M {px - 9:.1f} {py:.1f} C {px - 7:.1f} {py - 10:.1f} {px + 7:.1f} {py - 8:.1f} {px + 10:.1f} {py - 1:.1f} '
                f'C {px + 9:.1f} {py + 8:.1f} {px - 4:.1f} {py + 11:.1f} {px - 9:.1f} {py:.1f} Z" '
                f'fill="{html_escape(color)}" fill-opacity="0.55" stroke="#831843" stroke-width="1.0"/>'
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.0" class="placed-part-hole {state_class}" {attrs}/>'
            )

        if category == "spacers":
            px, py = point_at()
            return (
                f'<g class="placed-part visual-spacer {state_class}" {attrs}>'
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.0" fill="{html_escape(color)}" fill-opacity="0.34" stroke="#475569" stroke-width="0.8"/>'
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="1.7" fill="#ffffff" stroke="#475569" stroke-width="0.55"/>'
                f'</g>'
            )

        if part_id.startswith("hardware:"):
            px, py = point_at()
            return (
                f'<g class="placed-part visual-fastener {state_class}" {attrs}>'
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.6" fill="#fb923c" fill-opacity="0.42" stroke="#9a3412" stroke-width="1.0"/>'
                f'<path d="M {px - 5:.1f} {py:.1f} L {px + 5:.1f} {py:.1f} M {px:.1f} {py - 5:.1f} L {px:.1f} {py + 5:.1f}" '
                f'stroke="#9a3412" stroke-width="0.9" stroke-linecap="round"/>'
                f'</g>'
            )

        px, py = point_at(max(0, part_index - 1))
        return (
            f'<circle class="placed-part visual-generic {state_class}" {attrs} '
            f'cx="{px:.1f}" cy="{py:.1f}" r="5.2" fill="{html_escape(color)}" '
            f'fill-opacity="0.45" stroke="#334155" stroke-width="0.8"/>'
        )

    def _step_visual_part_ids(self, step: Mapping[str, object]) -> tuple[str, ...]:
        part_ids = self._step_part_ids(step)
        if part_ids:
            return part_ids
        if any(layer.get("role") == "paper-fastener" for layer in self._step_stack_layers(step)):
            return ("hardware:paper-fastener",)
        return ()

    def _placement_overlay_svg(
        self,
        steps: Sequence[Mapping[str, object]],
        *,
        x: float,
        y: float,
        size: float,
        state: str,
        current_step_n: int,
    ) -> str:
        rendered: list[str] = []
        seen: set[tuple[str, tuple[str, ...], str]] = set()
        for step in steps:
            coords = self._step_coords(step)
            points = self._placement_points(coords, x=x, y=y, size=size)
            if not points:
                continue
            roles = self._step_coord_roles(step)
            for part_index, part_id in enumerate(self._step_visual_part_ids(step), start=1):
                key = (part_id, tuple(label for label, _px, _py in points), state)
                if key in seen:
                    continue
                seen.add(key)
                rendered.append(
                    self._draw_visual_part(
                        part_id,
                        points,
                        state=state,
                        step_n=current_step_n,
                        part_index=part_index,
                        coord_roles=roles,
                    )
                )
        return "".join(rendered)

    def _placement_callout_svg(
        self,
        *,
        coords: Sequence[str],
        x: float,
        y: float,
        size: float,
        from_x: float,
        from_y: float,
        step_n: int,
    ) -> str:
        points = self._placement_points(coords, x=x, y=y, size=size)
        if not points:
            return ""
        _label, target_x, target_y = points[0]
        return (
            f'<path class="placement-callout-line" data-step="{step_n}" '
            f'd="M {from_x:.1f} {from_y:.1f} C {(from_x + target_x) / 2:.1f} {from_y:.1f} '
            f'{(from_x + target_x) / 2:.1f} {target_y:.1f} {target_x:.1f} {target_y:.1f}"/>'
            f'<circle class="placement-target-halo" data-step="{step_n}" cx="{target_x:.1f}" cy="{target_y:.1f}" r="7.2"/>'
        )

    def _assembly_board_legend_svg(self) -> str:
        width, height = ASSEMBLY_PAGE_SIZE_MM
        board_size = 156.0
        board_x = 18.0
        board_y = 36.0
        board_pitch = format_length_for_user(
            grid_step_mm(DEFAULT_GRID_CELL_CM),
            include_board_spaces=False,
        )
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="0 0 {width} {height}">
  <title>MotionSmith 15x15 board coordinate legend</title>
  <defs>{self._assembly_page_style()}</defs>
  <rect x="8" y="8" width="{width - 16}" height="{height - 16}" rx="5" class="page-border"/>
  <text x="18" y="23" class="page-title">15×15 board coordinate map</text>
  <text x="190" y="43" class="body-strong">Use row letters A–O and column numbers 1–15.</text>
  <text x="190" y="57" class="body">Each guide step highlights the exact board holes or reference link holes to use.</text>
  <text x="190" y="74" class="body">1 board space = {board_pitch}; the board has 15 holes across and 15 holes down.</text>
  <text x="190" y="91" class="body">Keep paper fasteners loose until the motion check passes.</text>
  <g id="board-legend">{self._board_grid_svg(x=board_x, y=board_y, size=board_size)}</g>
</svg>
'''

    @staticmethod
    def _assembly_page_style() -> str:
        return '''<style>
      .page-border { fill:#ffffff; stroke:#111827; stroke-width:0.8; }
      .page-title { font-family:Arial, Helvetica, sans-serif; font-size:7px; font-weight:700; fill:#111827; }
      .step-badge { fill:#2563eb; stroke:#1e40af; stroke-width:0.8; }
      .step-badge-text { font-family:Arial, Helvetica, sans-serif; font-size:8px; font-weight:700; fill:#ffffff; }
      .step-title { font-family:Arial, Helvetica, sans-serif; font-size:7px; font-weight:700; fill:#111827; }
      .instruction { font-family:Arial, Helvetica, sans-serif; font-size:4.6px; fill:#374151; }
      .section-label { font-family:Arial, Helvetica, sans-serif; font-size:4px; font-weight:700; fill:#111827; }
      .body { font-family:Arial, Helvetica, sans-serif; font-size:3.25px; fill:#374151; }
      .body-strong { font-family:Arial, Helvetica, sans-serif; font-size:3.55px; font-weight:700; fill:#111827; }
      .tiny { font-family:Arial, Helvetica, sans-serif; font-size:3.1px; fill:#4b5563; }
      .column-box { fill:#f8fafc; stroke:#cbd5e1; stroke-width:0.45; }
      .part-card { stroke-width:0.65; rx:3; fill-opacity:0.22; }
      .part-card-text { font-family:Arial, Helvetica, sans-serif; font-size:3.9px; font-weight:700; fill:#111827; }
      .board-frame { fill:#ffffff; stroke:#94a3b8; stroke-width:0.7; stroke-dasharray:2 2; }
      .board-label { font-family:Arial, Helvetica, sans-serif; font-size:2.35px; fill:#475569; }
      .board-hole { fill:#ffffff; stroke:#60a5fa; stroke-width:0.55; }
      .active-hole { fill:#fef3c7; stroke:#f97316; stroke-width:1.2; }
      .reference-hole { fill:#eff6ff; stroke:#2563eb; stroke-width:1.0; stroke-dasharray:1.8 1.2; }
      .placed-part-ghost { opacity:0.28; filter:none; }
      .placed-part-new { opacity:0.98; }
      .placed-part-hole { fill:#ffffff; stroke:#1f2937; stroke-width:0.55; }
      .placement-callout-line { fill:none; stroke:#f97316; stroke-width:1.0; stroke-linecap:round; stroke-dasharray:3 1.8; }
      .placement-target-halo { fill:#fed7aa; fill-opacity:0.25; stroke:#f97316; stroke-width:1.0; }
      .coord-bubble { fill:#111827; stroke:#111827; stroke-width:0.2; }
      .coord-bubble-text { font-family:Arial, Helvetica, sans-serif; font-size:2.7px; font-weight:700; fill:#ffffff; }
      .stack-layer { fill:#ffffff; stroke:#64748b; stroke-width:0.55; stroke-dasharray:2 1.2; }
      .stack-text { font-family:Arial, Helvetica, sans-serif; font-size:3.15px; fill:#111827; }
      .check-box { fill:#fff7ed; stroke:#fb923c; stroke-width:0.5; }
      .footer { font-family:Arial, Helvetica, sans-serif; font-size:3px; fill:#64748b; }
    </style>'''

    def _assembly_step_page_svg(
        self,
        recipe: Mapping[str, object],
        step: Mapping[str, object],
        *,
        previous_steps: Sequence[Mapping[str, object]] = (),
        page_index: int,
        page_count: int,
    ) -> str:
        width, height = ASSEMBLY_PAGE_SIZE_MM
        step_n = int(finite_float(step.get("n"), float(page_index)))
        title = str(step.get("title", f"Step {step_n}"))
        instruction_lines = self._wrapped_lines(step.get("instruction", ""), max_chars=78, max_lines=2)
        check_lines = self._wrapped_lines(step.get("check", ""), max_chars=18, max_lines=4)
        part_ids = self._step_part_ids(step)
        stack_layers = self._step_stack_layers(step)
        board_coords = self._step_board_coords(step)
        reference_coords = self._step_reference_coords(step)
        all_coords = self._step_coords(step)
        ghost_parts = self._step_ghost_parts(step)
        recipe_title = str(recipe.get("title", "Assembly"))
        recipe_key = str(recipe.get("key", "recipe"))

        left_x, left_w = 12.0, 58.0
        board_x, board_w = 76.0, 132.0
        right_x, right_w = 214.0, 53.0
        body_y, body_h = 38.0, 142.0
        board_size = 126.0
        board_origin_x = board_x + (board_w - board_size) / 2.0
        board_origin_y = body_y + 12.0
        previous_placement_svg = self._placement_overlay_svg(
            previous_steps,
            x=board_origin_x,
            y=board_origin_y,
            size=board_size,
            state="ghost",
            current_step_n=step_n,
        )
        current_placement_svg = self._placement_overlay_svg(
            (step,),
            x=board_origin_x,
            y=board_origin_y,
            size=board_size,
            state="new",
            current_step_n=step_n,
        )
        placement_callout_svg = self._placement_callout_svg(
            coords=all_coords,
            x=board_origin_x,
            y=board_origin_y,
            size=board_size,
            from_x=left_x + left_w - 2.0,
            from_y=body_y + 31.0,
            step_n=step_n,
        )

        part_cards: list[str] = []
        shown_parts = list(part_ids)
        if not shown_parts and any(layer.get("role") == "paper-fastener" for layer in stack_layers):
            shown_parts = ["hardware:paper-fastener"]
        if not shown_parts:
            shown_parts = ["instruction:check-only"]
        for index, part_id in enumerate(shown_parts[:7]):
            y = body_y + 24.0 + index * 14.2
            color = "#ef4444" if part_id.startswith("hardware:") else self._part_color(part_id)
            label = "Paper fastener" if part_id.startswith("hardware:") else self._part_label(part_id)
            if part_id.startswith("instruction:"):
                color = "#94a3b8"
                label = "No new cut part"
            part_cards.append(
                f'<rect x="{left_x + 3:.1f}" y="{y - 7:.1f}" width="{left_w - 8:.1f}" height="11" '
                f'class="part-card" fill="{html_escape(color)}" stroke="{html_escape(color)}"/>'
                f'<circle cx="{left_x + 9:.1f}" cy="{y - 1.5:.1f}" r="2.7" fill="{html_escape(color)}"/>'
                f'<text x="{left_x + 15:.1f}" y="{y:.1f}" class="part-card-text">{html_escape(label)}</text>'
            )

        stack_rows: list[str] = []
        for index, layer in enumerate(stack_layers[:9]):
            y = body_y + 17.0 + index * 10.5
            stack_rows.append(
                f'<rect x="{right_x + 2:.1f}" y="{y - 6:.1f}" width="20" height="5.8" class="stack-layer"/>'
                f'<text x="{right_x + 25:.1f}" y="{y - 1.4:.1f}" class="stack-text" '
                f'font-family="Arial, Helvetica, sans-serif" font-size="3.15">'
                f"{html_escape(self._stack_label(layer))}</text>"
            )
        coord_text = ", ".join(all_coords) if all_coords else "See board"
        ghost_text = ", ".join(self._part_label(part) for part in ghost_parts[:4]) or "previous parts ghosted"
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="0 0 {width} {height}"
     data-recipe-key="{html_escape(recipe_key)}" data-step="{step_n}" data-layout-kind="assembly-step-page">
  <title>{html_escape(recipe_title)} — step {step_n}</title>
  <defs>{self._assembly_page_style()}</defs>
  <rect x="8" y="8" width="{width - 16}" height="{height - 16}" rx="5" class="page-border"/>
  <circle cx="22" cy="23" r="10" class="step-badge"/>
  <text x="22" y="26" class="step-badge-text" text-anchor="middle">{step_n}</text>
  <text x="38" y="21" class="step-title">{html_escape(title)}</text>
  <text x="38" y="30" class="body-strong">{html_escape(recipe_title)}</text>
  {self._text_lines(x=100, y=22, lines=instruction_lines, class_name="instruction", line_height=5.6)}
  <rect x="{left_x}" y="{body_y}" width="{left_w}" height="{body_h}" rx="4" class="column-box"/>
  <rect x="{board_x}" y="{body_y}" width="{board_w}" height="{body_h}" rx="4" class="column-box"/>
  <rect x="{right_x}" y="{body_y}" width="{right_w}" height="{body_h}" rx="4" class="column-box"/>
  <text x="{left_x + 4}" y="{body_y + 8}" class="section-label">Add now</text>
  {''.join(part_cards)}
  <text x="{left_x + 4}" y="{body_y + body_h - 20}" class="tiny">Fasteners are hardware.</text>
  <text x="{left_x + 4}" y="{body_y + body_h - 13}" class="tiny">Cut parts are in kit-parts PDF.</text>
  <text x="{board_x + 4}" y="{body_y + 8}" class="section-label">Board placement: {html_escape(coord_text)}</text>
  <g id="board-step-{step_n}">{self._board_grid_svg(x=board_origin_x, y=board_origin_y, size=board_size, active=board_coords, references=reference_coords)}</g>
  <g id="layer-previous-step-ghost-step-{step_n}" data-step="{step_n}">{previous_placement_svg}</g>
  <g id="layer-new-part-placement-step-{step_n}" data-step="{step_n}">{current_placement_svg}{placement_callout_svg}</g>
  <text x="{board_x + 4}" y="{body_y + body_h - 11}" class="tiny">Context: {html_escape(ghost_text)}</text>
  <text x="{right_x + 4}" y="{body_y + 8}" class="section-label">Fastener stack</text>
  {''.join(stack_rows)}
  <rect x="{right_x + 2}" y="{body_y + body_h - 39}" width="{right_w - 4}" height="31" rx="3" class="check-box"/>
  <text x="{right_x + 5}" y="{body_y + body_h - 30}" class="section-label">Check</text>
  {self._text_lines(x=right_x + 5, y=body_y + body_h - 22, lines=check_lines, class_name="body", line_height=4.2)}
  <text x="12" y="{height - 13}" class="footer">Keep paper-fastener tabs loose until the final motion check passes.</text>
  <text x="{width - 12}" y="{height - 13}" class="footer" text-anchor="end">{html_escape(recipe_key)} · page {page_index} of {page_count}</text>
</svg>
'''

    def _assembly_step_page_svgs(
        self,
        package: Mapping[str, object],
        *,
        front_matter_pages: int = 2,
    ) -> tuple[str, ...]:
        raw_recipes = package.get("recipes", ())
        recipes = (
            [recipe for recipe in raw_recipes if isinstance(recipe, Mapping)]
            if isinstance(raw_recipes, Sequence) and not isinstance(raw_recipes, str)
            else []
        )
        total_steps = 0
        for recipe in recipes:
            raw_steps = recipe.get("steps", ())
            if isinstance(raw_steps, Sequence) and not isinstance(raw_steps, str):
                total_steps += len([step for step in raw_steps if isinstance(step, Mapping)])
        page_count = front_matter_pages + total_steps
        pages: list[str] = []
        page_index = front_matter_pages + 1
        for recipe in recipes:
            raw_steps = recipe.get("steps", ())
            steps = (
                [step for step in raw_steps if isinstance(step, Mapping)]
                if isinstance(raw_steps, Sequence) and not isinstance(raw_steps, str)
                else []
            )
            for step in steps:
                prior_steps = tuple(
                    earlier_step
                    for earlier_step in steps
                    if isinstance(earlier_step.get("n"), int)
                    and isinstance(step.get("n"), int)
                    and int(earlier_step["n"]) < int(step["n"])
                )
                pages.append(
                    self._assembly_step_page_svg(
                        recipe,
                        step,
                        previous_steps=prior_steps,
                        page_index=page_index,
                        page_count=page_count,
                    )
                )
                page_index += 1
        return tuple(pages)

    @staticmethod
    def _inline_svg_fallback_name(index: int, source: str) -> str:
        data_attrs = {
            match.group("key").lower(): match.group("value")
            for match in _SVG_DATA_ATTR_RE.finditer(source[:4096])
        }
        layout_kind = data_attrs.get("layout-kind", "")
        recipe_key = data_attrs.get("recipe-key", "recipe")
        step = data_attrs.get("step", "")
        if layout_kind == "kit-parts-compact-cut-sheet":
            return f"{index:02d}-kit-parts-cut-sheet.svg"
        if layout_kind == "assembly-step-page" and step:
            return f"{index:02d}-step-{step}-{recipe_key}.svg"

        title_match = _SVG_TITLE_RE.search(source[:4096])
        title = " ".join(title_match.group("title").lower().split()) if title_match else ""
        if "selected fabrication checklist" in title:
            return f"{index:02d}-checklist.svg"
        if "coordinate legend" in title or "15x15 board" in title:
            return f"{index:02d}-board-15x15.svg"
        if "physical contract" in title:
            return f"{index:02d}-physical-contract.svg"
        if "kit parts" in title:
            return f"{index:02d}-kit-parts-checklist.svg"
        return f"{index:02d}-page.svg"

    def _render_pdf_or_copy_fallback(
        self,
        *,
        svg_sources: Sequence[str | Path],
        pdf_path: Path,
        fallback_dir: Path,
        page_size_mm: tuple[float, float] | None = None,
        scale_mode: str = "fit",
        margin_points: float | None = None,
    ) -> tuple[Path, ...]:
        temp_pdf_path = pdf_path.with_name(f".{pdf_path.stem}.tmp{pdf_path.suffix}")
        if temp_pdf_path.is_file():
            temp_pdf_path.unlink()
        pdf_scale_mode: PageScaleMode = "actual-size" if scale_mode == "actual-size" else "fit"
        effective_margin = (
            PRINT_MARGIN_POINTS if page_size_mm and margin_points is None else float(margin_points or 0.0)
        )
        if render_svgs_to_pdf(
            tuple(svg_sources),
            temp_pdf_path,
            margin_points=effective_margin,
            page_size_mm=page_size_mm,
            scale_mode=pdf_scale_mode,
        ) and is_valid_pdf_file(temp_pdf_path):
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
                target = fallback_dir / self._inline_svg_fallback_name(index, source)
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

1. Print/cut the current-design cut sheet generated beside this folder for character and
   mechanism components.
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

        guide_sources: list[str | Path] = [
            self._selected_parts_checklist_svg(package),
            self._assembly_board_legend_svg(),
        ]
        if contract is not None:
            guide_sources.insert(1, self._physical_contract_svg(contract))
        guide_sources.extend(
            self._assembly_step_page_svgs(package, front_matter_pages=len(guide_sources))
        )
        guide_outputs = self._render_pdf_or_copy_fallback(
            svg_sources=guide_sources,
            pdf_path=package_dir / "assembly-guide.pdf",
            fallback_dir=package_dir / "svg-fallback" / "assembly",
            page_size_mm=ASSEMBLY_PAGE_SIZE_MM,
        )
        copied.extend(guide_outputs)
        pdf_files.extend(path for path in guide_outputs if path.suffix.lower() == ".pdf")
        fallback_files.extend(path for path in guide_outputs if path.suffix.lower() != ".pdf")

        packed_part_pages = self._packed_kit_parts_cut_sheet_svgs(package)
        part_sources: tuple[str | Path, ...] = packed_part_pages or self._quantity_part_sources(package)
        if part_sources:
            part_outputs = self._render_pdf_or_copy_fallback(
                svg_sources=(self._kit_parts_cover_svg(package), *part_sources),
                pdf_path=package_dir / "kit-parts-to-cut.pdf",
                fallback_dir=package_dir / "svg-fallback" / "parts",
                page_size_mm=PRINT_PAGE_SIZE_MM,
                scale_mode="actual-size",
                margin_points=0.0,
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
