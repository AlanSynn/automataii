# MM-1.3 — Parametric Editing Extraction

Date: 2025-10-19  
Scope: Move mechanism parameter normalisation logic into application-layer service.

## Deliverables
- `automataii/application/mechanism_design/parametric_service.py`: pure math/service layer (`ParametricParameterService`, `ParametricContext`).
- `ParametricEditingManager` updated to delegate parameter preparation to new service.
- Unit tests for service (`tests/test_parametric_service.py`).

## Highlights
- Cam, 4-bar, gear, and planetary parameter derivations are now toolkit-agnostic and reusable.
- `ParametricEditingManager` retains UI responsibilities; legacy helper methods now guard against accidental use (raise runtime errors) while controller integration migrates.
- Service uses telemetry-compatible pure logic; bridging can be leveraged by automated tests without PyQt.

## Next Steps
1. Replace remaining runtime guards by removing legacy methods once UI fully migrated.
2. Implement concrete generation service/adapter to feed controller outputs into manager.
3. Expand tests to cover regeneration routines (MM-2.x) once controllers orchestrate state.
