# MM-3.2 — Foundry Interaction Facade

Date: 2025-10-19  
Scope: Integration of Mechanism Foundry UI with catalog service (now default).

## Deliverables
- `EnhancedMacanismTab` loads mechanisms from `MechanismCatalogService` by default (`src/automataii/ui/tabs/mechanism_foundry/enhanced_macanism_tab.py`).
- States stored (`mechanism_type_combo`, parameters group, educational content) respect catalog metadata while legacy defaults remain only for controller init failures.
- Parameter sliders now come from controller `ParameterSpec` definitions, so the UI no longer hard-codes min/max ranges; slider-crank is provided via a synthesized fallback item until it exists in the catalog.
- Added lazy `catalog_service` init with telemetry-ready search support (leveraging MM-3.1 service).

## Summary
- Mechanism selection dropdown and parameter controls are populated from the application-layer catalog on every launch.
- Educational panel reflects catalog descriptions/tags for the active entry without needing environment flags.
- Fallback paths keep existing static UI available if the catalog fails to initialise.
- Automation hook available via `uv run automataii --scenario blueprint-export`, which emits SVG + manifest + metrics artifacts using controller defaults and structured telemetry.
- Metrics aggregator script (`scripts/collect_scenario_metrics.py`) summarises scenario runs for dashboard ingestion.

## Next Steps
1. Wire scenario telemetry (span + metrics file) to feed MM-4 dashboards.
2. Extend the Foundry controller to handle parameter sliders, animation updates, and mechanism instantiation in upcoming sub-milestones.
3. Add unit tests around the adapter once the new interaction controller is fleshed out (current UI-heavy change is exercised manually).
