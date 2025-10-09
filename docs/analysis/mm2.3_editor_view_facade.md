# MM-2.3 — Editor View Facade

Date: 2025-10-19  
Scope: Introduce feature-flagged state mirroring for `EditorView`.

## Deliverables
- `EditorView` optionally instantiates `EditorViewStateStore` when `AUTOMATAII_EDITOR_FACADE` is enabled (`src/automataii/gui/views/editor_view.py`).
- Core interactions (`set_mode`, zoom operations, freehand path drawing/cancellation, panning) now update the store alongside existing UI state.
- Added accessors (`get_state_store`) so controllers can observe state without touching PyQt internals.

## Behaviour
- When the feature flag is off (default) nothing changes.
- When on, state transitions (mode changes, zoom level, path point updates, pan offset, path completion/cancel) are captured immutably for downstream controllers/tests.
- Telemetry-friendly foundation for replacing direct widget coupling in later milestones.

## Next Steps
1. Move path emission (`freehandPathCompleted`) handling into the upcoming editor controller so state updates drive downstream logic.
2. Expand store integration for selection changes, skeleton overlay toggles, and animation playback once controller facade matures.
3. Hook the state store into `EditorTab` for cross-tab coordination after the controller layer lands.
