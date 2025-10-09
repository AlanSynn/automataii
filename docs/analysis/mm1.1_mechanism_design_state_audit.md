# MM-1.1 — MechanismDesignTab State Audit

Date: 2025-10-19  
Owner: Refactor squad  
Scope: `src/automataii/gui/tabs/mechanism_design_tab.py`

## Summary
- File size: 4,648 LOC.
- `MechanismDesignTab` maintains **85 mutable attributes** on `self`, merging UI widget references, mechanism state, parametric editing flags, animation controls, and cached data.
- Mixing of concerns:
  - UI widgets (`play_btn`, `mechanism_layers_list`, etc.)
  - Domain state (`mechanism_layers`, `mechanism_instances`, `mechanism_params`)
  - Visualization caches (`mechanism_path_items`, `mechanism_trace_points`)
  - Parametric editing integration (`parametric_manager`, `parametric_edit_mode`)
  - Telemetry / debugging (`debug_items`, `show_debug`)
- Tight coupling to:
  - `MechanismDesignTabLayout`, `MechanismDesignTabSignals`, `MechanismDesignUI` (UI scaffolding modules).
  - Services: `MechanismService`, `SkeletonService`, `BlueprintExporter`.
  - External controllers: `parametric_manager`, `parametric_editor`, `mechanism_view`.
  - Persistence / utility modules: `resolve_path`, JSON fixtures, recommendation dialog.
- Core workflows intertwined in single class: path ingestion, recommendation, mechanism generation, animation playback, parametric editing, blueprint export coordination.

## Attribute Buckets
| Category | Attributes (subset) | Notes |
|----------|--------------------|-------|
| UI widgets | `play_btn`, `stop_btn`, `reset_btn`, `mechanism_layers_list`, `zoom_in_btn`, `recommendation_btn`, `parametric_edit_btn`, `blueprint_btn`, `center_character_btn`, etc. | Should move behind a view adapter or `ui_widgets` accessor. |
| State toggles | `parametric_mode_enabled`, `edit_mode`, `show_debug`, `animating_mechanisms`, `_tab_active`, `_scene_recently_cleared`, `_updating_handles_programmatically` | Candidate for a view-model / state store. |
| Domain data | `path_data`, `mechanism_layers`, `mechanism_params`, `mechanism_instances`, `part_enabled_state`, `generated_paths`, `selected_mechanism_id`, `selected_part_name` | Should live in application services. |
| Visualization caches | `mechanism_path_items`, `mechanism_trace_items`, `mechanism_trace_points`, `skeleton_joint_items`, `skeleton_bone_items`, `_preview_items` | Separate renderer/visual adaptor required. |
| Parametric integration | `parametric_manager`, `parametric_editor`, `interactive_handles`, `mechanism_service` | Should be orchestrated via controller. |
| Animation control | `animation_timer`, `animation_time`, `animation_speed`, `trace_max_points`, `trace_update_stride`, `_trace_frame_tick` | Move into animation controller/service. |
| Recommendation support | `recommendation_dialog`, `generated_paths`, `_initial_skeleton_data_cache`, `_last_target_pos_by_joint` | Suggest dedicated recommendation coordinator. |

## Signal / Dependency Map
- Receives editor paths via `MainWindow.editor_tab.path_data_changed => set_path_data_from_editor`.
- Emits requests: `request_generate_mechanism`, `request_generate_blueprint`.
- Consumes services: `MechanismService`, `SkeletonService`, `BlueprintExporter`, `MechanismRecommendationDialog`.
- Depends on global path `automataii/kinematics/generated_mechanism_paths.json`.
- Interacts with `IKManager` (through main window) for animation updates.

## Identified Modules for Extraction
1. **MechanismDesignController** — orchestrate recommendation, mechanism generation, layer CRUD, enabling/disabling parts.
2. **MechanismStateStore / ViewModel** — encapsulate attributes such as `path_data`, `mechanism_layers`, `part_enabled_state`, `animation` flags.
3. **VisualizationAdapter** (existing) — needs clear contract for `mechanism_path_items`, traces, skeleton overlays.
4. **RecommendationCoordinator** — encapsulate dialog setup, path conversion, JSON lookup, leaving the widget to just call `controller.recommend`.
5. **AnimationController** — manage timers, trace updates, and preview state.
6. **ParametricEditingGateway** — mediates between tab and `ParametricEditingManager`.

## Risks / Observations
- Mechanism recommendation relies on JSON fixtures loaded at runtime; error handling currently prints to stdout—needs structured logging/error surfacing.
- `set_path_data_from_editor` includes UI resets, part enable toggling, scene clearing; should be decomposed into pure state updates + UI reactions.
- Many attributes updated without centralized validation, leading to hidden coupling (e.g., `mechanism_layers_list` and `mechanism_layers`).
- Animation pacing uses raw timers and counters; migrating to service may require refactoring cross-dependencies with IK manager.

## Next Steps (MM‑1.2 prerequisites)
1. Define `MechanismDesignViewModel` dataclass capturing state buckets above.
2. Draft controller API:
   - `controller.update_paths(part_paths)`
   - `controller.enable_part(name, enabled)`
   - `controller.generate_mechanism(part_name)`
   - `controller.recommend(part_name)`
3. Identify required signals/callbacks to emit from controller (e.g., `on_state_changed`, `on_preview_ready`, `on_error`).
4. Plan migration strategy: keep existing widget methods but delegate logic to controller; use feature flag for gradual adoption.
