# MM-3.1 — Mechanism Foundry Catalog Service

Date: 2025-10-19  
Scope: Introduce a reusable catalog loader/service for the Foundry tab.

## Deliverables
- `automataii/application/mechanism_foundry/catalog.py`: dataclasses (`MechanismCatalog`, `MechanismCategory`, `MechanismEntry`, `MechanismParameter`) + `load_catalog` helper parsing `mechanism_catalog.json`.
- `automataii/application/mechanism_foundry/service.py`: `MechanismCatalogService` with summary, search, and item lookup APIs (telemetry instrumented via `application.foundry.catalog_search`).
- Unit coverage (`tests/test_mechanism_catalog_service.py`).

## Impact
- Catalog access is now decoupled from the Foundry UI; future controllers can consume the service without touching JSON directly.
- Telemetry hooks prepare the ground for usage analytics when the new Foundry controllers land.

## Next Steps
1. Consume `MechanismCatalogService` from `EnhancedMacanismTab` behind a feature flag.
2. Extend service APIs for parameter presets / defaults once interaction controllers are in place.
3. Tie search/filter UI to the service so the tab can respond to queries without duplicating logic.
