"""Application-layer export/copy service for board assembly guides."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from html import escape as html_escape
from pathlib import Path

from automataii.application.mechanism_foundry.mechanism_types import (
    canonical_mechanism_type,
)
from automataii.shared.fabrication_assembly import ASSEMBLY_SCHEMA_VERSION, manifest_part_index
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
    def _recipe_guide_filename(raw_recipe: object) -> str | None:
        if not isinstance(raw_recipe, Mapping):
            return None
        raw_guide = raw_recipe.get("guide_svg")
        if not isinstance(raw_guide, str):
            return None
        guide_path = Path(raw_guide)
        if guide_path.is_absolute() or ".." in guide_path.parts or not guide_path.name:
            return None
        return guide_path.name

    def _existing_exported_guide_filenames(self, package_dir: Path) -> set[str]:
        recipes_path = package_dir / "recipes.json"
        if not recipes_path.is_file():
            return set()
        try:
            data = json.loads(recipes_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return set()
        if not isinstance(data, Mapping):
            return set()
        raw_recipes = data.get("recipes", ())
        if not isinstance(raw_recipes, Sequence) or isinstance(raw_recipes, str):
            return set()
        return {
            filename
            for raw_recipe in raw_recipes
            if (filename := self._recipe_guide_filename(raw_recipe)) is not None
        }

    def _prune_stale_exported_guides(
        self,
        package_dir: Path,
        *,
        selected_filenames: set[str],
    ) -> None:
        for filename in self._existing_exported_guide_filenames(package_dir) - selected_filenames:
            stale_path = package_dir / filename
            if stale_path.is_file():
                stale_path.unlink()

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

    @staticmethod
    def _step_coord_roles(raw_step: Mapping[str, object]) -> tuple[str, ...]:
        coords = raw_step.get("coords", ())
        if not isinstance(coords, Sequence) or isinstance(coords, str):
            return ()
        roles = raw_step.get("coord_roles", ())
        if not isinstance(roles, Sequence) or isinstance(roles, str):
            return tuple("board" for _coord in coords)
        normalized = tuple(str(role) for role in roles)
        if len(normalized) != len(coords):
            return tuple("board" for _coord in coords)
        return normalized

    @classmethod
    def _coord_heading_for_step(cls, raw_step: Mapping[str, object]) -> str:
        roles = set(cls._step_coord_roles(raw_step))
        if roles and roles <= {"board"}:
            return "Board holes"
        if "board" in roles:
            return "Board/ref"
        if "gear_handle_reference" in roles:
            return "Gear/handle ref"
        if "link_end_reference" in roles:
            return "Link-end ref"
        if "link_joint_reference" in roles:
            return "Link-joint ref"
        if "slider_reference" in roles:
            return "Slider ref"
        if "carrier_reference" in roles:
            return "Carrier ref"
        return "Reference"

    def _part_paths_by_id(self) -> dict[str, str]:
        try:
            index = manifest_part_index(self.load_manifest())
        except (OSError, ValueError, json.JSONDecodeError):
            return {}
        paths: dict[str, str] = {}
        for part_id, item in index.items():
            raw_path = item.get("path") if isinstance(item, Mapping) else None
            if isinstance(raw_path, str) and raw_path:
                paths[part_id] = raw_path
        return paths

    def _copy_recipe_parts(
        self,
        *,
        package: Mapping[str, object],
        package_dir: Path,
    ) -> list[Path]:
        manifest = self.load_manifest()
        index = manifest_part_index(manifest)
        copied: list[Path] = []
        raw_recipes = package.get("recipes", ())
        if not isinstance(raw_recipes, Sequence) or isinstance(raw_recipes, str):
            return copied
        seen: dict[str, None] = {}
        for raw_recipe in raw_recipes:
            for part_id in self._recipe_part_ids(raw_recipe):
                seen[part_id] = None
        for part_id in seen:
            item = index.get(part_id)
            if not isinstance(item, Mapping):
                continue
            raw_path = item.get("path")
            if not isinstance(raw_path, str) or not raw_path:
                continue
            source = self._resolve_fabrication_asset(raw_path)
            if not source.is_file():
                continue
            target = package_dir / "parts" / raw_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(target)
        return copied

    def _export_index_html(self, package: Mapping[str, object]) -> str:
        raw_recipes = package.get("recipes", ())
        recipes = (
            [recipe for recipe in raw_recipes if isinstance(recipe, Mapping)]
            if isinstance(raw_recipes, Sequence) and not isinstance(raw_recipes, str)
            else []
        )
        sections: list[str] = []
        part_paths = self._part_paths_by_id()
        for recipe in recipes:
            part_cards = []
            for part_id in self._recipe_part_ids(recipe):
                label = self._part_label(part_id)
                color = self._part_color(part_id)
                href = f"parts/{part_paths[part_id]}" if part_id in part_paths else "#"
                part_cards.append(
                    '<a class="part-card" '
                    f'style="--part-color:{html_escape(color)}" '
                    f'href="{html_escape(href)}">'
                    f"<strong>{html_escape(label)}</strong>"
                    f"<small>{html_escape(part_id)}</small>"
                    "</a>"
                )
            step_rows: list[str] = []
            raw_steps = recipe.get("steps", ())
            if isinstance(raw_steps, Sequence) and not isinstance(raw_steps, str):
                for raw_step in raw_steps:
                    if not isinstance(raw_step, Mapping):
                        continue
                    coords = raw_step.get("coords", ())
                    coord_text = (
                        ", ".join(str(coord) for coord in coords)
                        if isinstance(coords, Sequence) and not isinstance(coords, str)
                        else ""
                    )
                    coord_heading = self._coord_heading_for_step(raw_step)
                    stack = raw_step.get("stack", ())
                    stack_labels: list[str] = []
                    if isinstance(stack, Sequence) and not isinstance(stack, str):
                        for layer in stack:
                            if not isinstance(layer, Mapping):
                                continue
                            label = str(layer.get("label", "")).strip()
                            if label:
                                stack_labels.append(label)
                    stack_text = " → ".join(stack_labels)
                    stack_row = (
                        f'<span class="stack">Stack: {html_escape(stack_text)}</span>'
                        if stack_text
                        else ""
                    )
                    step_rows.append(
                        "<li>"
                        f"<b>{html_escape(str(raw_step.get('n', '')))}. "
                        f"{html_escape(str(raw_step.get('title', '')))}</b>"
                        f"<span>{html_escape(coord_heading)}: {html_escape(coord_text)}</span>"
                        f"<span>{html_escape(str(raw_step.get('instruction', '')))}</span>"
                        f"{stack_row}"
                        "</li>"
                    )
            guide_name = Path(str(recipe.get("guide_svg", ""))).name
            sections.append(
                "<section>"
                f"<h2>{html_escape(str(recipe.get('title', 'Guide')))}</h2>"
                f'<p><a href="{html_escape(guide_name)}">Open printable guide</a></p>'
                "<h3>Parts in this build</h3>"
                f'<div class="parts-grid">{"".join(part_cards)}</div>'
                "<h3>Assembly order</h3>"
                f"<ol>{''.join(step_rows)}</ol>"
                "</section>"
            )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Automataii assembly export</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 24px; color: #111827; }}
    header, section {{ border: 1px solid #d1d5db; border-radius: 14px; padding: 16px; margin-bottom: 18px; }}
    li {{ margin: 10px 0; }}
    li span {{ display: block; margin-top: 4px; }}
    .callout {{ border-color: #f97316; background: #fff7ed; }}
    .stack {{ color: #92400e; font-weight: 600; }}
    .parts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
    .part-card {{ border: 2px solid var(--part-color); border-radius: 12px; padding: 10px; background: #fff; display: grid; gap: 4px; color: inherit; text-decoration: none; }}
    .part-card strong {{ background: var(--part-color); border-radius: 999px; padding: 6px 8px; width: max-content; }}
    @media print {{ body {{ margin: 12mm; }} section {{ break-inside: avoid; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Automataii board assembly</h1>
    <p>
      This is the board-coordinate assembly guide, not the cut sheet. First make the
      character and mechanism parts from <b>Make Parts / Cut Sheets</b>, then use
      board-15x15.svg and the step cards below.
    </p>
  </header>
  <section class="callout">
    <h2>Character attachment rule</h2>
    <p>
      Use the current character body components from the Parts Blueprint/Cut Sheets.
      Do not introduce a separate Example Character template. Attach each moving character
      part to the mechanism output with a paper fastener, keep a spacer between moving layers
      and the board/bracket, and flatten the fastener tabs only after the motion clears.
    </p>
    <p>
      Follow each step's <b>Stack</b> row exactly. Typical moving stack:
      board hole → paper fastener → spacer → character part or linkage →
      spacer → fastener tabs.
    </p>
  </section>
  <p><a href="parts-overview.svg">Open printable part checklist</a></p>
  {"".join(sections)}
</body>
</html>
"""

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
2. Open `board-15x15.svg` to identify board coordinates.
3. Open `index.html` for a LEGO-style visual sequence, part checklist, and stack order.
4. Pick one guide SVG listed below.
5. Follow one step card at a time: place the fastener at the called-out hole, then add spacers
   and parts in the exact `Stack` row order before running the check.
6. Keep paper fasteners loose enough for rotation or sliding before flattening the tabs.

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
- `parts/` contains copied printable templates for the parts used by the selected guides.
- Guide SVGs include board coordinates, stack order, part IDs, and app mechanism metadata.
"""

    def export_guides(
        self,
        output_dir: str | Path,
        *,
        recipe_keys: Iterable[str] | None = None,
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
        parts_dir = package_dir / "parts"
        if parts_dir.is_dir():
            shutil.rmtree(parts_dir)
        copied: list[Path] = []
        selected_filenames = {Path(summary.guide_svg).name for summary in summaries}
        self._prune_stale_exported_guides(package_dir, selected_filenames=selected_filenames)
        package = self._selected_package(included_keys={summary.key for summary in summaries})
        recipes_target = package_dir / "recipes.json"
        recipes_target.write_text(
            json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        copied.append(recipes_target)
        readme_target = package_dir / "README.md"
        readme_target.write_text(self._export_readme(summaries), encoding="utf-8")
        copied.append(readme_target)
        index_target = package_dir / "index.html"
        index_target.write_text(self._export_index_html(package), encoding="utf-8")
        copied.append(index_target)
        board_source = self._resolve_assembly_asset("board-15x15.svg")
        board_target = package_dir / "board-15x15.svg"
        shutil.copy2(board_source, board_target)
        copied.append(board_target)
        overview_source = self._resolve_assembly_asset("parts-overview.svg")
        if overview_source.is_file():
            overview_target = package_dir / "parts-overview.svg"
            shutil.copy2(overview_source, overview_target)
            copied.append(overview_target)
        copied.extend(self._copy_recipe_parts(package=package, package_dir=package_dir))
        for summary in summaries:
            source = self._resolve_assembly_asset(summary.guide_svg)
            filename = source.name
            target = package_dir / filename
            shutil.copy2(source, target)
            copied.append(target)
        return FabricationGuideExportResult(
            output_dir=destination,
            package_dir=package_dir,
            copied_files=tuple(copied),
            recipe_keys=tuple(summary.key for summary in summaries),
        )
