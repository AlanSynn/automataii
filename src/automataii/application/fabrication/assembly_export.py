"""Application-layer export/copy service for board assembly guides."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from automataii.application.mechanism_foundry.mechanism_types import (
    VISIBLE_FOUNDRY_MECHANISM_TYPES,
    canonical_mechanism_type,
)
from automataii.shared.fabrication_assembly import ASSEMBLY_SCHEMA_VERSION
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

    def load_package(self) -> Mapping[str, object]:
        data = json.loads(self.recipes_path.read_text(encoding="utf-8"))
        if not isinstance(data, Mapping):
            raise ValueError("Assembly recipes.json must contain an object")
        if data.get("schema_version") != ASSEMBLY_SCHEMA_VERSION:
            raise ValueError("Unsupported assembly recipes schema")
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
        """Return board guides that can represent an app/foundry mechanism type."""
        canonical = canonical_mechanism_type(mechanism_type)
        if canonical not in VISIBLE_FOUNDRY_MECHANISM_TYPES:
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

    def _export_readme(self, summaries: Sequence[FabricationGuideSummary]) -> str:
        guide_lines = "\n".join(
            f"- `{summary.key}` — {summary.title} ({summary.step_count} steps)"
            for summary in summaries
        )
        return f"""# Automataii exported board assembly guides

This folder is a self-contained `assembly/` package exported from Automataii.

## How to use

1. Open `board-15x15.svg` to identify board coordinates.
2. Pick one guide SVG listed below.
3. Follow one step card at a time: place the fastener, add spacers, add the part, then run the check.
4. Keep paper fasteners loose enough for rotation or sliding before flattening the tabs.

## Included guides

{guide_lines}

## Data contract

- `recipes.json` lists exactly the guide SVGs included in this export.
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
        board_source = self._resolve_assembly_asset("board-15x15.svg")
        board_target = package_dir / "board-15x15.svg"
        shutil.copy2(board_source, board_target)
        copied.append(board_target)
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
