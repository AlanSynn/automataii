from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from automataii.utils.paths import get_project_root


@dataclass(frozen=True)
class MechanismParameter:
    key: str
    name: str
    type: str
    default: float | int | str
    min: float | int | None = None
    max: float | int | None = None
    unit: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class MechanismEntry:
    key: str
    name: str
    description: str
    mech_type: str
    class_name: str
    tags: Sequence[str]
    complexity: str
    parameters: Mapping[str, MechanismParameter]
    preview_size: Sequence[int] | None = None
    animation_duration: int | None = None


@dataclass(frozen=True)
class MechanismCategory:
    key: str
    name: str
    description: str
    icon: str | None
    mechanisms: Mapping[str, MechanismEntry]


@dataclass(frozen=True)
class MechanismCatalog:
    version: str
    categories: Mapping[str, MechanismCategory]


def load_catalog(catalog_path: Path | None = None) -> MechanismCatalog:
    if catalog_path is None:
        project_root = get_project_root()
        catalog_path = project_root / "resources" / "data" / "mechanism_catalog.json"
    with catalog_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    version = raw.get("version", "0.0.0")
    categories_data = raw.get("categories", {})
    categories: dict[str, MechanismCategory] = {}
    for cat_key, cat_val in categories_data.items():
        mechanisms: dict[str, MechanismEntry] = {}
        for mech_key, mech_val in cat_val.get("mechanisms", {}).items():
            params_cfg = mech_val.get("parameters", {})
            params = {
                key: MechanismParameter(
                    key=key,
                    name=p.get("name", key),
                    type=p.get("type", "float"),
                    default=p.get("default"),
                    min=p.get("min"),
                    max=p.get("max"),
                    unit=p.get("unit"),
                    description=p.get("description"),
                )
                for key, p in params_cfg.items()
            }
            mechanisms[mech_key] = MechanismEntry(
                key=mech_key,
                name=mech_val.get("name", mech_key),
                description=mech_val.get("description", ""),
                mech_type=mech_val.get("type", mech_key),
                class_name=mech_val.get("class", ""),
                tags=tuple(mech_val.get("tags", [])),
                complexity=mech_val.get("complexity", "unknown"),
                parameters=params,
                preview_size=tuple(mech_val.get("preview_size", [])) or None,
                animation_duration=mech_val.get("animation_duration"),
            )
        categories[cat_key] = MechanismCategory(
            key=cat_key,
            name=cat_val.get("name", cat_key),
            description=cat_val.get("description", ""),
            icon=cat_val.get("icon"),
            mechanisms=mechanisms,
        )

    return MechanismCatalog(version=version, categories=categories)
