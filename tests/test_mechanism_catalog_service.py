from __future__ import annotations

from automataii.application.mechanism_foundry import MechanismCatalogService, load_catalog
from automataii.application.mechanism_foundry.catalog import (
    MechanismCatalog,
    MechanismCategory,
    MechanismEntry,
)


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


def test_catalog_service_normalizes_search_and_lookup_filters():
    entry = MechanismEntry(
        key=" Four_Bar ",
        name="Four Bar",
        description="Test linkage",
        mech_type="four_bar",
        class_name="FourBarMechanism",
        tags=(" Basic ", "LINKAGE"),
        complexity=" Beginner ",
        parameters={},
    )
    category = MechanismCategory(
        key=" Linkages ",
        name="Linkages",
        description="",
        icon=None,
        mechanisms={" Four_Bar ": entry},
    )
    service = MechanismCatalogService(
        MechanismCatalog(version=" 1.2.3 ", categories={" Linkages ": category})
    )

    assert service.get_summary().version == "1.2.3"
    assert service.get_summary().categories == ("Linkages",)
    assert service.get_category("linkages") is category
    assert service.get_mechanism("LINKAGES", "four_bar") is entry
    assert service.search(tag="basic", complexity="beginner") == [entry]
    assert service.search(tag="missing") == []
