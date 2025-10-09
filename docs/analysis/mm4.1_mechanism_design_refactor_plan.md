# MM-4.1 — MechanismDesignTab Refactor Plan

**Author:** Mechanism Foundry Refactor Squad  
**Date:** 2025-10-20  
**Target Areas:** `src/automataii/gui/tabs/mechanism_design_tab.py` (~4,648 LOC) and companion God classes  

---

## 1. Problem / Goal

MechanismDesignTab remains a monolithic God widget that fuses UI wiring, mechanism orchestration, animation playback, skeleton/IK coordination, parametric editing, and blueprint export. This size and responsibility mix blocks further refactors, forces brittle slot/callback logic, and prevents automated scenario testing.

**Quantitative targets**
| Metric | Current | Target |
|--------|---------|--------|
| LOC | ~4,648 | ≤ 1,200 (UI adapter only) |
| Public methods | 120+ | ≤ 25, with thin delegates |
| Cyclomatic “hotspots” (>30) | 17 | ≤ 3 |
| Time-to-render preview | Baseline TBD | −20% via async redraw |

**Qualitative goals**
- Isolate application logic behind existing `MechanismDesignController`.
- Introduce explicit state stores for animation, layers, and selection.
- Unify telemetry and scenario automation hooks.
- Enable unit tests for controller/view-model without Qt.

---

## 2. Current State (In-Scope Snapshot)

**Responsibilities inside the tab**
1. **State management:** Maintains dictionaries (`path_data`, `mechanism_layers`, `parts_data`, `mechanism_instances`, …).
2. **Service orchestration:** Calls `MechanismService`, `SkeletonService`, IK manager, and BodyPartsExtractor directly.
3. **UI composition:** Manages QGraphicsScene items, QWidgets, toolbar states, animation timers.
4. **Parametric editing:** Still owns handle creation, rotation updates, drag feedback, despite a separate `ParametricEditingManager`.
5. **Animation loop:** Steps mechanism output, updates visuals, traces motion paths.
6. **Blueprint export:** Delegates to `BlueprintExporter` but drives UI state and validation.

**Key dependencies**
- PyQt6 widgets, graphics primitives.
- `MechanismService`, `SkeletonService`, IK manager hooks.
- `MechanismVisualsFactory`, `EditorView`, `MechanismDesignUI` (layout helper).
- `ParametricEditingManager`, `BlueprintExporter`.
- Application layer controller (`application/mechanism_design/controller.py`) exists but unused by the tab.

**Pain points**
- **High coupling:** Direct mutation of services makes testing impossible; no single source of truth for mechanism state.
- **Long slot chains:** UI signal handlers (>200) blend control and rendering, causing bugs when features toggle.
- **Redundant calculations:** Mechanism output recomputed in multiple pathways (`_calculate_mechanism_output*`).
- **Telemetry gaps:** Only sporadic logging; no visibility into recommendation/apply flows or animation performance in UI.
- **Scenario blocker:** Automation cannot drive tab without instantiating full PyQt window; no headless adapter.

---

## 3. Target Architecture

![Architecture Sketch](../../diagrams/mechanism_design_refactor.png) *(to be produced in MM-4.2)*

### Layers & Modules
1. **Application / Domain (existing & extended)**
   - `MechanismDesignController`: source of truth for paths, layers, selections.
   - **New** `MechanismAnimationService`: simulates mechanism outputs, caches traces.
   - **New** `MechanismLayerAdapter`: translates controller layers → visualization DTOs.

2. **Presentation (new view-models)**
   - `MechanismDesignViewModel` (Qt-free dataclass) mirroring UI needs (active part, enabled buttons, traces, animation state).
   - `MechanismDesignPresenter` bridging controller events → view-model updates; surfaces telemetry events.

3. **UI Adapters**
   - Reduced `MechanismDesignTab` focusing on:
     - Wiring signals to presenter.
     - Applying view-model deltas to Qt widgets/scene.
     - Owning scene objects lifecycle via helper classes (`MechanismSceneAdapter`, `ParametricHandlesAdapter`).
   - `MechanismAnimationPlayer` (wrapper around `QTimer`) to move animation logic out of the tab.

4. **Services/Factories**
   - `MechanismVisualsFactory` remains but receives pure data rather than direct tab state.
   - Parametric editing flows consume updates from presenter rather than tab-level global dicts.

### Data Flow (happy path)
1. Editor tab posts new paths → presenter → controller `update_paths`.
2. Controller emits state snapshot → presenter diff → view-model update.
3. Animation commands flip `MechanismAnimationService`, which invokes `MechanismVisualsAdapter` with computed positions.
4. Blueprint export triggered via presenter, using `MechanismDesignController.state` to build `BlueprintComposer` requests (no direct tab->manager coupling).

### Observability
| Span | Trigger | Fields |
|------|---------|--------|
| `application.mechanism_design.update_paths` | Controller | part_count |
| `ui.mechanism_design.apply_recommendation` | Presenter -> controller | mechanism_type, layer_id |
| `ui.mechanism_design.animation_tick` | Animation player | active_layers, frame_time |
| `ui.mechanism_design.parametric_update` | Parametric adapter | mechanism_id, handles |

---

## 4. Module Boundaries & Interfaces

| Module | Responsibility | Key Interfaces |
|--------|----------------|----------------|
| `MechanismDesignController` (existing) | Paths, layers, selection state | `update_paths`, `request_recommendations`, `apply_recommendation`, `add_listener` |
| `MechanismAnimationService` | Produce positions/traces using generation service | `simulate(layer_id, time)`, `precompute_trace(layer_id)` |
| `MechanismDesignPresenter` | Glue between controller, services, UI | `bind(tab)`, `handle_event(event)`, `current_view_model` |
| `MechanismDesignViewModel` | Immutable UI snapshot | dataclass with `parts`, `layers`, `buttons`, `animation` |
| `MechanismSceneAdapter` | Apply view-model diffs to QGraphics items | `apply(view_model)` |
| `ParametricHandlesAdapter` | Manage handles independent from tab | `sync_from_layer(layer)` |

All PyQt interactions limited to adapters; business logic runs in pure Python, enabling unit tests.

---

## 5. Dependencies & Assumptions

- `MechanismService` exposes deterministic APIs for layer build & simulation (verify contract during refactor).
- `MechanismDesignState` (existing dataclasses) sufficiently expressive; may extend with new flags (e.g., `animation_ready`, `errors`).
- `MechanismVisualsFactory` can accept DTO inputs; otherwise wrap it with adapter.
- IK integration currently in tab; we will stub a `MechanismIKCoordinator` to own signal wiring (Phase 2).

---

## 6. Test Strategy

| Level | Focus | Tooling |
|-------|-------|---------|
| Unit | Presenter diffing, animation service, view-model -> adapter mapping | `pytest` pure tests (no Qt) |
| Integration | Qt tab smoke with presenter stub | `pytest-qt` or custom harness |
| Scenario | Extend automation pack to include mechanism recommendation replay once UI is decoupled | existing CLI harness |
| Regression | Capture baseline `parts_info.json`/trace metrics before/after refactor | scenario metrics JSON |

Success: ability to assert controller state transitions without launching QApplication.

---

## 7. Observability Plan

- Add spans defined above.
- Include per-run metrics in automation scenario (frame count, average frame time).
- Hook presenter to telemetry logger for recommendation/application events with mechanism IDs.

---

## 8. Performance / Resource Constraints

- Mechanism animation tick must stay under 16ms (60 FPS) for 3 active layers.
- Memory budget: avoid storing entire QGraphics item list in Python dict; use adapters to keep references lightweight.
- Avoid blocking Qt event loop during recommendation generation—offsload to worker where possible (Phase 3).

---

## 9. Risks / Mitigations

| Risk | Mitigation |
|------|------------|
| UI regressions due to presenter mismatch | Build view-model snapshots + golden tests using freeze JSON |
| Animation flicker while migrating visuals | Introduce feature flag `AUTOMATAII_MECH_CONTROLLER` to toggle new flow per session |
| Parametric handles reliance on tab globals | Extract adapter first; keep legacy path behind flag until parity tests pass |
| IK syncing dependencies | Provide temporary shim that delegates to old callbacks while wiring the new presenter |

---

## 10. Rollout / Rollback Plan

1. Introduce presenter + adapters behind `AUTOMATAII_MECH_CONTROLLER`.
2. Migrate path updates, recommendations, and layer creation flows.
3. Flip flag in QA builds; collect telemetry/metrics for 1 week.
4. Remove legacy code paths after parity validation.

Rollback: disable flag to revert to current tab behavior (legacy branches untouched until MM-4.2 completion).

---

## 11. Definition of Done

- MechanismDesignTab reduced to UI adapter (≤1,200 LOC) with no business logic.
- Presenter + services unit-tested (≥80% coverage).
- Automation scenario updated to cover blueprint and image + future mechanism flows (tracked in telemetry).
- Telemetry dashboards reflect recommendation/apply success counts.
- Documentation (PRD, ADR, observability notes) updated post-refactor.

---

## 12. Next Milestones

| Phase | Scope | Deliverables |
|-------|-------|--------------|
| MM-4.1a | Presenter + view-model skeleton; wire path updates | Presenter module, tests, tab behind flag |
| MM-4.1b | Layer/animation extraction + MechanismAnimationService | Animation service, Qt adapter, telemetry spans |
| MM-4.1c | Parametric + blueprint wiring to presenter | Handles adapter, blueprint adapter, scenario updates |
| MM-4.2 | Automation & observability hardening | Scenario harness, dashboards, docs |

---
