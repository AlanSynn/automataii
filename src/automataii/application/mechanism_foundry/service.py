from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar

from automataii.infrastructure.telemetry import telemetry_span

from .catalog import (
    MechanismCatalog,
    MechanismCategory,
    MechanismEntry,
    load_catalog,
)


@dataclass(frozen=True)
class CatalogSummary:
    version: str
    categories: Sequence[str]


_T = TypeVar("_T")


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _normalized_text(value: object) -> str:
    return _safe_text(value).casefold()


def _lookup_by_normalized_key(mapping: Mapping[str, _T], key: object) -> _T | None:
    exact_key = _safe_text(key)
    if not exact_key:
        return None
    if exact_key in mapping:
        return mapping[exact_key]

    normalized_key = exact_key.casefold()
    for candidate_key, value in mapping.items():
        if _normalized_text(candidate_key) == normalized_key:
            return value
    return None


def _normalized_tags(value: object) -> frozenset[str]:
    values: tuple[object, ...]
    if value is None:
        return frozenset()
    if isinstance(value, str):
        values = (value,)
    else:
        try:
            values = tuple(value)  # type: ignore[arg-type]
        except TypeError:
            values = (value,)
    return frozenset(tag for item in values if (tag := _normalized_text(item)))


class MechanismCatalogService:
    """Provides read access to the mechanism catalog."""

    def __init__(self, catalog: MechanismCatalog | None = None) -> None:
        self._catalog = catalog if catalog is not None else load_catalog()

    @property
    def catalog(self) -> MechanismCatalog:
        return self._catalog

    def _categories(self) -> Mapping[str, MechanismCategory]:
        categories = self._catalog.categories
        return categories if isinstance(categories, Mapping) else {}

    @staticmethod
    def _mechanisms(category: MechanismCategory) -> Mapping[str, MechanismEntry]:
        mechanisms = category.mechanisms
        return mechanisms if isinstance(mechanisms, Mapping) else {}

    def get_summary(self) -> CatalogSummary:
        return CatalogSummary(
            version=_safe_text(self._catalog.version, "0.0.0"),
            categories=tuple(
                sorted(key for raw_key in self._categories() if (key := _safe_text(raw_key)))
            ),
        )

    def list_categories(self) -> Iterable[MechanismCategory]:
        return tuple(
            category
            for category in self._categories().values()
            if isinstance(category, MechanismCategory)
        )

    def get_category(self, key: str) -> MechanismCategory | None:
        category = _lookup_by_normalized_key(self._categories(), key)
        return category if isinstance(category, MechanismCategory) else None

    def search(self, tag: str | None = None, complexity: str | None = None) -> list[MechanismEntry]:
        results: list[MechanismEntry] = []
        tag_filter = _normalized_text(tag)
        complexity_filter = _normalized_text(complexity)
        with telemetry_span(
            "application.foundry.catalog_search",
            tag=tag_filter or None,
            complexity=complexity_filter or None,
        ):
            for category in self.list_categories():
                for entry in self._mechanisms(category).values():
                    if not isinstance(entry, MechanismEntry):
                        continue
                    if tag_filter and tag_filter not in _normalized_tags(entry.tags):
                        continue
                    if (
                        complexity_filter
                        and _normalized_text(entry.complexity) != complexity_filter
                    ):
                        continue
                    results.append(entry)
        return results

    def get_mechanism(self, category_key: str, mechanism_key: str) -> MechanismEntry | None:
        category = self.get_category(category_key)
        if not category:
            return None
        entry = _lookup_by_normalized_key(self._mechanisms(category), mechanism_key)
        return entry if isinstance(entry, MechanismEntry) else None
