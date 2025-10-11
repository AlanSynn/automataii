from __future__ import annotations

from automataii.application.mechanism_foundry import MechanismCatalogService, load_catalog


def test_catalog_summary():
    service = MechanismCatalogService(load_catalog())
    summary = service.get_summary()
    assert summary.version
    assert len(summary.categories) > 0


def test_search_by_tag():
    service = MechanismCatalogService(load_catalog())
    results = service.search(tag="basic")
    assert all("basic" in entry.tags for entry in results)


def test_get_mechanism():
    service = MechanismCatalogService(load_catalog())
    category_key = next(iter(service.catalog.categories.keys()))
    mech_key = next(iter(service.catalog.categories[category_key].mechanisms.keys()))
    entry = service.get_mechanism(category_key, mech_key)
    assert entry is not None
