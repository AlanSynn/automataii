# Mechanism Design Tab Migration Plan

## 1. Current Assessment
- `src/automataii/gui/tabs/mechanism_design_tab.py`
  - **Size**: 4,648 LOC, single class `MechanismDesignTab` with 90+ methods (largest: `_update_mechanism_visuals_for_animation` 468 LOC, `_calculate_mechanism_output` 187 LOC, `_get_anchor_positions_for_mechanism` 179 LOC, `_generate_mechanism_from_candidate` 153 LOC).
  - **Responsibilities**: UI wiring, animation orchestration, mechanism IK integration, preview rendering, parametric editing handles, blueprint export, caching, logging.
  - **Couplings**: Direct imports from generation, core, kinematics, and GUI rendering; manual state management, implicit dependencies on global services, shared mutable state.
  - **Testability**: No automated coverage; methods mutate UI widgets directly; heavy reliance on real-time timers/RNG, difficult to run headless.

## 2. Goals
- Reduce tab implementation to ≤600 LOC with no method >80 LOC.
- Separate concerns into testable modules (view-models, controllers, services, render adapters).
- Enable deterministic automation via scenario harness (headless rendering, state assertions).
- Preserve feature parity while achieving 30% latency reduction for mechanism preview/animation workflows.

## 3. Target Architecture
- **View-Model Layer (`ui.view_models.mechanism_design`)**
  - State reducers for mechanism selection, animation progress, parametric mode, blueprint export state.
  - Emits intents/events consumed by GUI adapter; no direct widget access.
- **Interaction Controllers**
  - `MechanismAnimationController`: schedules animations, integrates with IK Manager via async service calls.
  - `ParametricEditingController`: manages handles, anchor updates, and parametric mode toggling.
  - `MechanismBlueprintController`: handles recommendation selection, blueprint export, performance presets.
- **Domain/Application Services**
  - `MechanismVisualService`: generates geometry layers, handles caching, provides scene transform functions.
  - `MechanismSimulationService`: wraps `_calculate_mechanism_output` logic, uses dependency-inverted math/IK ports.
- **Render Adapter (`ui.renderers.mechanism`)**
  - Responsible for translating visual DTOs into Qt scene nodes; supports headless renderer for automation.
- **State & Event Infrastructure**
  - Integrate with project-wide event bus, command/query handlers, and snapshot capture API defined in main PRD.

## 4. Migration Strategy & Milestones

### Milestone A — Baseline & Guardrails (Week 0–1)
- Capture existing behavior via manual scripts, start scenario DSL recording for top 5 flows (load mechanism, preview animation, apply recommendation, toggle parametric mode, export blueprint).
- Instrument current class with lightweight telemetry (timers, counters) and freeze initial metrics.
- Deliverables: Baseline report, scenario recordings, diff of critical method responsibilities, ADR draft for mechanism tab refactor.

### Milestone B — View-Model & Event Bus Extraction (Week 1–3)
- Introduce view-model module mirroring current state; route widget callbacks through intents → reducers.
- Implement state snapshot/restore for deterministic tests; replace direct widget mutations where feasible.
- Deliverables: `ui.view_models.mechanism_design` package, unit tests for reducers, feature flag to enable new view-model path for non-destructive sync.

### Milestone C — Service Decomposition (Week 3–6)
- Extract animation, simulation, and visual generation logic into domain/application services with dependency-inverted ports.
- Refactor heavy methods (`_calculate_mechanism_output`, `_update_mechanism_visuals_for_animation`, `_get_anchor_positions_for_mechanism`) into service classes with focused responsibilities.
- Deliverables: `services/mechanism_animation_service.py`, `services/mechanism_visual_service.py`, `generation/mechanism_simulation_service.py`, integration tests with stubbed adapters.

### Milestone D — Rendering Adapter & Headless Harness Integration (Week 6–8)
- Build renderer adapter translating DTOs to Qt (and headless) artifacts. Replace direct scene manipulation with adapter interface.
- Connect to automated harness (scenario runner) for headless validation; generate golden snapshots for migrated workflows.
- Deliverables: `ui/renderers/mechanism_renderer.py`, headless compatibility tests, CI job executing scenarios for mechanism tab.

### Milestone E — Parametric & Blueprint Modules (Week 8–10)
- Extract parametric editing logic into dedicated controller + DTOs; isolate blueprint recommendation/export flow.
- Add property-based tests for geometry calculations and blueprint validation.
- Deliverables: Parametric controller module, blueprint service module, coverage ≥80% for new components, documentation updates.

### Milestone F — Legacy Class Decommission (Week 10–12)
- Replace `MechanismDesignTab` with thin adapter wiring view-model → renderer; remove legacy methods.
- Clean up feature flags, update dependency wiring, finalize observability dashboards, complete rollout/rollback rehearsal.
- Deliverables: Simplified tab adapter (<400 LOC), green automated suite, updated docs, release checklist.

## 5. Testing & Observability Alignment
- Reuse scenario DSL + headless renderer from global PRD for regression coverage.
- Ensure each controller/service exposes structured logs + metrics, tagged by `mechanism_id`, `scenario_id`.
- Establish dedicated dashboards for animation latency, frame diff scores, parametric handle actions per minute.

## 6. Risks & Mitigations
- **Hidden Couplings**: Legacy methods might mutate shared state. → Introduce strangler façade with facade API shim; run dual-mode until metrics stable.
- **Animation Timing Drift**: Deterministic clock may diverge from real-time UI expectations. → Provide time abstraction and acceptance tests verifying sync.
- **Scenario Coverage Gaps**: New flows may lack automation scripts. → Mandate scenario authoring with each module extraction; update baseline after review.

## 7. Next Steps
1. Review and approve this migration plan alongside the main Modular UI PRD.
2. Kick off Milestone A tasks—baseline capture and telemetry instrumentation.
3. Prepare ADR-004 documenting view-model/event-bus adoption for mechanism tab before code changes.

