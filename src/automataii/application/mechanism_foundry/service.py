from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

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


class MechanismCatalogService:
    """Provides read access to the mechanism catalog."""

    def __init__(self, catalog: MechanismCatalog | None = None) -> None:
        self._catalog = catalog or load_catalog()

    @property
    def catalog(self) -> MechanismCatalog:
        return self._catalog

    def get_summary(self) -> CatalogSummary:
        return CatalogSummary(
            version=self._catalog.version,
            categories=tuple(self._catalog.categories.keys()),
        )

    def list_categories(self) -> Iterable[MechanismCategory]:
        return self._catalog.categories.values()

    def get_category(self, key: str) -> MechanismCategory | None:
        return self._catalog.categories.get(key)

    def search(self, tag: str | None = None, complexity: str | None = None) -> list[MechanismEntry]:
        results: list[MechanismEntry] = []
        with telemetry_span("application.foundry.catalog_search", tag=tag, complexity=complexity):
            for category in self._catalog.categories.values():
                for entry in category.mechanisms.values():
                    if tag and tag not in entry.tags:
                        continue
                    if complexity and entry.complexity != complexity:
                        continue
                    results.append(entry)
        return results

    def get_mechanism(self, category_key: str, mechanism_key: str) -> MechanismEntry | None:
        category = self._catalog.categories.get(category_key)
        if not category:
            return None
        return category.mechanisms.get(mechanism_key)
