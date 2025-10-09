# MM-3.3 — Blueprint Composition Pipeline

Date: 2025-10-19  
Scope: Application-layer composer wrapping the legacy blueprint optimizer.

## Deliverables
- `automataii/application/blueprint/composer.py`: `BlueprintComposer` + `BlueprintCompositionResult` providing a thin facade over `BlueprintLayoutOptimizer` and SVG generation (with telemetry).
- Feature-flag integration in `BlueprintExportManager` (`AUTOMATAII_BLUEPRINT_COMPOSER`) so new composer can be exercised without breaking existing flows (`src/automataii/core/blueprint_manager.py`).
- Unit tests: `tests/test_blueprint_composer.py` for composer behaviour.

## Summary
- Composer isolates layout/SVG composition so blueprint exports no longer instantiate optimizer directly.
- Returning result metadata (dimensions/item count) prepares for logging/telemetry downstream.
- Feature flag keeps legacy path untouched until full migration is validated.

## Next Steps
1. Migrate `gui/blueprint/exporter.py` to use the composer behind the flag.
2. Extend composer to emit telemetry events per layout item once scenario tests exist.
3. After confidence, remove legacy branch and consolidate blueprint pipeline around the new composer.
