from __future__ import annotations

import json
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from automataii.infrastructure.validation.schemas import validate_mechanism_catalog
from automataii.utils.paths import get_project_root

logger = logging.getLogger(__name__)


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


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _safe_text_tuple(value: object) -> tuple[str, ...]:
    values: tuple[object, ...]
    if value is None:
        return ()
    if isinstance(value, str):
        values = (value,)
    else:
        try:
            values = tuple(value)  # type: ignore[arg-type]
        except TypeError:
            values = (value,)
    return tuple(text for item in values if (text := _safe_text(item)))


def _safe_number(value: object) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_scalar(value: object, default: float | int | str = 0.0) -> float | int | str:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | str):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else default
    number = _safe_number(value)
    return number if number is not None else default


def _safe_preview_size(value: object) -> tuple[int, ...] | None:
    if not isinstance(value, list | tuple):
        return None
    sizes: list[int] = []
    for item in value:
        number = _safe_number(item)
        if number is None:
            continue
        size = int(number)
        if size > 0:
            sizes.append(size)
    return tuple(sizes) or None


def _safe_animation_duration(value: object) -> int | None:
    number = _safe_number(value)
    if number is None or number <= 0:
        return None
    return int(number)


def _parse_parameters(raw_params: object) -> dict[str, MechanismParameter]:
    if not isinstance(raw_params, Mapping):
        return {}
    params: dict[str, MechanismParameter] = {}
    for raw_key, raw_param in raw_params.items():
        if not isinstance(raw_param, Mapping):
            continue
        key = _safe_text(raw_key, "parameter")
        default = _safe_scalar(raw_param.get("default", 0.0))
        params[key] = MechanismParameter(
            key=key,
            name=_safe_text(raw_param.get("name"), key),
            type=_safe_text(raw_param.get("type"), "float"),
            default=default,
            min=_safe_number(raw_param.get("min")),
            max=_safe_number(raw_param.get("max")),
            unit=_safe_text(raw_param.get("unit")) or None,
            description=_safe_text(raw_param.get("description")) or None,
        )
    return params


def load_catalog(catalog_path: Path | None = None) -> MechanismCatalog:
    if catalog_path is None:
        project_root = get_project_root()
        catalog_path = project_root / "resources" / "data" / "mechanism_catalog.json"

    try:
        with catalog_path.open("r", encoding="utf-8") as f:
            raw: Any = json.load(f)
    except FileNotFoundError:
        logger.error(f"Mechanism catalog file not found: {catalog_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in mechanism catalog {catalog_path}: {e}")
        raise
    except PermissionError:
        logger.error(f"Permission denied reading catalog: {catalog_path}")
        raise

    # Validate JSON structure using Pydantic schema
    try:
        validated = validate_mechanism_catalog(raw)
        logger.debug(f"Catalog validation passed: version {validated.version}")
    except (ValidationError, TypeError, ValueError, AttributeError) as e:
        logger.warning(f"Catalog validation errors (proceeding with defaults): {e}")
        # Continue with raw data - validation is advisory, not blocking

    if not isinstance(raw, Mapping):
        logger.warning("Mechanism catalog root must be an object; using empty catalog")
        return MechanismCatalog(version="0.0.0", categories={})

    version = _safe_text(raw.get("version"), "0.0.0")
    categories_data = raw.get("categories", {})
    if not isinstance(categories_data, Mapping):
        categories_data = {}
    categories: dict[str, MechanismCategory] = {}
    for cat_key, cat_val in categories_data.items():
        if not isinstance(cat_val, Mapping):
            continue
        category_key = _safe_text(cat_key, "category")
        mechanisms_data = cat_val.get("mechanisms", {})
        if not isinstance(mechanisms_data, Mapping):
            mechanisms_data = {}
        mechanisms: dict[str, MechanismEntry] = {}
        for mech_key, mech_val in mechanisms_data.items():
            if not isinstance(mech_val, Mapping):
                continue
            mechanism_key = _safe_text(mech_key, "mechanism")
            params = _parse_parameters(mech_val.get("parameters", {}))
            mechanisms[mechanism_key] = MechanismEntry(
                key=mechanism_key,
                name=_safe_text(mech_val.get("name"), mechanism_key),
                description=_safe_text(mech_val.get("description")),
                mech_type=_safe_text(mech_val.get("type"), mechanism_key),
                class_name=_safe_text(mech_val.get("class")),
                tags=_safe_text_tuple(mech_val.get("tags", ())),
                complexity=_safe_text(mech_val.get("complexity"), "unknown"),
                parameters=params,
                preview_size=_safe_preview_size(mech_val.get("preview_size")),
                animation_duration=_safe_animation_duration(mech_val.get("animation_duration")),
            )
        categories[category_key] = MechanismCategory(
            key=category_key,
            name=_safe_text(cat_val.get("name"), category_key),
            description=_safe_text(cat_val.get("description")),
            icon=_safe_text(cat_val.get("icon")) or None,
            mechanisms=mechanisms,
        )

    return MechanismCatalog(version=version, categories=categories)
