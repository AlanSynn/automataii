# MM-2.1 — Editor View State Store

Date: 2025-10-19  
Scope: Introduce a pure state container for `EditorView` workflows.

## Deliverables
- `automataii/application/editor/state.py`: immutable `EditorViewState` dataclass + `EditorViewStateStore` observer container.
- Public package entry (`automataii/application/editor/__init__.py`) exporting the state utilities.
- Unit coverage in `tests/test_editor_view_state_store.py`.

## State Model Highlights
- Tracks interaction mode, selected part, drawing state, path points, zoom/pan, animation flags, hover info, and cached raw/corrected paths.
- Supports immutable updates (`with_mode`, `start_path`, `with_paths`, etc.) to prepare for controller-driven workflows.
- Store implements listener registration to push deltas to the PyQt layer without direct coupling.

## Next Steps
- Wire the store into `EditorView` behind a feature flag and migrate path/zoom handling.
- Extend state to capture skeleton overlay flags, gestures, and trace data as refactor progresses.
- Integrate telemetry by emitting spans when store transitions occur (e.g., path complete, zoom change).
