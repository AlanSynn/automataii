# God-Class Refactor PRD (UI-Preserving)

## 1. Problem / Goal
- **Problem**: Core Automataii workflows sit atop “god classes” (4–5k LOC widgets such as `MechanismDesignTab`, `EnhancedMacanismTab`, `EditorView`, `BlueprintOptimizer`, `IKManager`). The entangled state-handling, business logic, and rendering code prevent safe changes, block automated testing, and slow boot/runtime.
- **Goal**: Factor these monoliths into composable application/domain services while keeping the existing PyQt UI surfaces visually and behaviorally identical. Preserve widget public APIs/signals so the UI layout and interactions remain unchanged.
- **Targets**:
  - Reduce each refactored class to ≤800 LOC, ≤20 methods, cyclomatic complexity < 200.
  - Extract ≥90 % of non-render logic into new application/domain modules with explicit interfaces.
  - Preserve UI parity: zero observable delta in UX (verified via scenario checks + telemetry).
  - Improve cold-start time by 20 % via lazy loading of refactored services.

## 2. Scope
- **In Scope**:
  - Refactoring logic inside the following hotspot files:  
    `gui/tabs/mechanism_design_tab.py`, `ui/tabs/mechanism_foundry/enhanced_macanism_tab.py`, `gui/views/editor_view.py`, `gui/tabs/editor_tab.py`, `generation/blueprint_optimizer.py`, `core/skeleton_manager.py`, `kinematics/ik_manager.py`, `gui/main_window.py`, `gui/dialogs/recommendation_dialog.py`.
  - Introducing application-layer coordinators, view-models, and state stores that sit behind the existing widgets.
  - Adding telemetry/test harness hooks to validate non-regression on UI workflows.
  - Dependency inversion to isolate PyQt from domain logic; new modules live under `automataii/application` and `automataii/domain`.
- **Out of Scope**:
  - Changing Qt widget hierarchies, layouts, or styling.
  - Replacing PyQt with another GUI toolkit.
  - Shipping new end-user features; parity only.
  - Large-scale data/model schema changes (beyond necessary DTO definitions).

## 3. Success Metrics & Validation
- Structural:
  - LOC and complexity targets met for each refactored UI class.
  - Introduce ≥6 new composable services with hardened APIs (e.g., `MechanismRecommendationService`, `BlueprintComposer`, `PathDefinitionService`).
- Quality:
  - Automated scenario diff suite confirms no change in UI state for top 10 workflows.
  - Telemetry spans (latency, success/failure) attached to refactored services show ≤5 % regression vs. baseline.
- Performance:
  - Mechanism recommendation and blueprint export median latency reduced by 25 %.
  - App startup (when run with `uv run automataii --editing`) improved by ≥20 %.

## 3.1 Current Progress (MM-3 complete, MM-4 in flight)
- MM-3.1/3.2/3.3 delivered: Foundry catalog/service/controller stack and the feature-flagged blueprint composer with passing unit coverage (`src/automataii/application/mechanism_foundry/*`, `src/automataii/application/blueprint/composer.py`).
- Blueprint export flow now defaults to `BlueprintComposer` end-to-end. `core/blueprint_manager.py` delegates through `compose_single_page`, and `gui/blueprint/exporter.py` writes composer output directly for both dialog and direct-file paths.
- Regression tests guard the composer delegation (`tests/test_blueprint_composer.py`, `tests/test_blueprint_manager.py`); broader `pytest` suite still needs to run locally because sandbox cache permission errors persist.
- Mechanism Foundry parameter UI now consumes controller `ParameterSpec` metadata; the slider-crank option is provided via a synthesized fallback entry until it lands in the catalog.
- Introduced the first automation scenario (`automataii.scenarios.blueprint`) to exercise blueprint export via controllers/composer, emitting SVG, manifest, and metrics with telemetry spans; runnable via `uv run automataii --scenario blueprint-export`.
- Added `scripts/collect_scenario_metrics.py` to aggregate scenario runs for downstream dashboards.
- Added `scripts/verify_onnx_models.py` to sanity-check ONNX assets ahead of the image-processing automation work.
- Stood up the image-processing automation scenario (`automataii.scenarios.image_processing`) with ONNX inference, parts extraction, telemetry, and manifest/metrics outputs via `uv run automataii --scenario image-processing`.
- MM-4.1 progressing: blueprint shims removed; next items are Foundry slider cleanup and flipping feature flags once telemetry validates usage.
- MM-4.2 (Scenario Automation Pack) queued; automation will target image-processing and blueprint-export UI paths using the new controllers/composer.
- Outstanding blocker: ONNX detector/pose weights still fail protobuf parsing; validate models before enabling automated image scenarios.

## 4. Architecture Overview
- **UI Layer (unchanged)**: Existing PyQt widgets remain entry points. New facades/adapters wrap refactored logic and expose the same methods/signals.
- **Presentation Layer (new)**:
  - `application/viewmodels/*`: pure-Python state objects mirroring widget data; updated via commands/events.
  - `application/controllers/*`: orchestrate interactions, convert widget signals into domain commands.
- **Domain Layer (expanded)**:
  - `domain/mechanisms`: recommendation algorithms, parametric data, validation rules.
  - `domain/blueprints`: layout optimization, SVG generation, metadata assembly.
  - `domain/kinematics`: IK solvers, skeleton state transitions (extracted from `ik_manager` / `skeleton_manager`).
- **Infrastructure/Adapters**:
  - `infrastructure/rendering`: wrappers for current visualization code.
  - `infrastructure/persistence`: file IO, config serialization.
- **Telemetry**:
  - `core.telemetry.telemetry_span` drives structured logs for each command.

## 5. Public API & Compatibility Strategy
- Maintain widget method signatures (e.g., `MechanismDesignTab.toggle_parametric_mode`, `ImageProcessingTab.process_image`) by delegating to new controllers.
- Introduce application-level APIs for use by controllers:
  - `MechanismDesignController.recommend(mechanism_id)` returning DTOs.
  - `BlueprintExportController.export(command)`, `ImageProcessingPipeline.process(request)`.
- Domain objects expressed as dataclasses or pydantic models with clear versioning; UI converts to/from legacy structures.
- Provide compatibility shim modules (e.g., `gui/tabs/mechanism_design/legacy_bridge.py`) for features not yet migrated.

## 6. Dependencies
- **Internal**:
  - New application layer depends on domain services via interfaces; UI depends on application layer only.
  - State store uses `core.state` primitives (subject to refactor to match new API).
- **External**:
  - PyQt6 remains primary GUI dependency.
  - ONNX / numpy / scipy usage remains unchanged; adapters encapsulate data conversions.
- **Dependency Injection**:
  - Enhance `core.container.Container` to register new services; provide `ApplicationContext` builder for tests.

## 7. Test & Observability Strategy
- **Unit Tests**: For controllers and domain services, using pytest to cover success/error paths.
- **Integration Tests**: Harness existing GUI scenario scripts (headless) to validate behavior. For now, run in analysis mode without altering UI.
- **Telemetry & Metrics**:
  - add spans such as `application.mechanism.recommend`, `application.blueprint.compose`, `application.path.define`.
  - Emit metadata (workflow id, asset size, mechanism count) for dashboards.
- **Regression Scripts**:
  - Manual to start (record flows), then convert to automation once harness matures.
  - Visual diff snapshots optional, but UI unchanged so minimal scope.

## 8. Execution Constraints
- Must retain identical UI. All refactors occur behind adapters; only internal logic moves.
- Avoid long-lived branches: incremental branch per workflow to reduce risk.
- Compatibility mode should ship with feature flags toggled via environment.

## 9. Risks & Mitigations
- **Hidden Coupling**: UI classes directly mutate deep state. → Introduce baseline test capturing object graphs; add shim that logs suspicious attribute access.
- **Performance Regressions**: Additional abstraction overhead. → Use telemetry to detect; freeze budgets before releasing.
- **Team Ramp**: New module structure may confuse devs. → Document controllers/services in ADRs; provide examples.
- **Partial Migration**: risk leaving mixed patterns. → Adopt “strangler” approach with milestone sign-offs; no partial merges without full controller coverage for targeted workflow.

## 10. Milestones & Deliverables
### M0 — Baseline & Plan (complete)
- Workflow inventory (docs/prd/milestone0_workflow_inventory.md).
- Telemetry scaffold & instrumentation for key workflows.
- ADR-000 capturing architecture intent.

### M1 — Controller & State Store Foundations (Weeks 1–3)
- Create `application/controllers`, `application/viewmodels`; wire Mechanism Design tab commands.
- Extract skeleton/motion-path logic into `domain` services.
- Deliverables: controller tests, updated telemetry spans, shim bridging old UI to new controllers.

### M2 — Mechanism Design Refactor (Weeks 3–6)
- Split `MechanismDesignTab` into view adapter + application services.
- Extract mechanism recommendation, parametric editing orchestration.
- Validate via scenario + telemetry; update doc strings / developer guide.

### M3 — Editor & IK Services (Weeks 6–8)
- Refactor `EditorTab`, `EditorView`, `IKManager` into distinct services (path editing, kinematics, selection).
- Add property-based tests for IK/dynamics.
- Ensure UI interacts with view-model updates only.

### M4 — Mechanism Foundry & Blueprint Workflow (Weeks 8–10)
- Rework `EnhancedMacanismTab`, `BlueprintOptimizer`, blueprint export pipeline using new services.
- Guarantee export/regression via telemetry and scenario tests.

### M5 — Consolidation & Cleanup (Weeks 10–12)
- Remove legacy helpers, freeze interfaces, refresh documentation.
- CI gating via scenario suite + telemetry dashboards.
- Produce final ADR capturing new module layout.

## Micro-Milestone Breakdown
| ID | Focus | Scope | Deliverables |
|----|-------|-------|--------------|
| MM-0.1 | Telemetry Hardening | Verify spans on image processing & blueprint flows, add quick dashboards | Dashboard link, alert thresholds, span docs |
| MM-0.2 | Baseline Snapshots | Capture current UI state & perf metrics for top 10 workflows | Scenario recordings, metrics report |
| MM-1.1 | Mechanism Design State Audit | Map all mutable attributes & signal paths in `MechanismDesignTab` | State diagram, property inventory, test gap list |
| MM-1.2 | Mechanism Design Controllers | Introduce `MechanismDesignController` + view-model, wire export/recommend calls via adapter | Controller module, unit tests, shim engaged behind flag |
| MM-1.3 | Parametric Editing Extraction | Move parametric editing logic into dedicated service modules | `ParametricEditingService`, tests, updated wiring |
| MM-2.1 | Editor View State Store | Implement shared state store for selection/path editing | State store module + reducer tests |
| MM-2.2 | IK Service Abstraction | Extract IK operations into `domain/kinematics` service | IK service class, property-based tests, controller integration |
| MM-2.3 | Editor Widget Facade | Replace direct scene manipulation with service calls behind adapter | Facade layer, telemetry spans (`application.editor.*`) |
| MM-3.1 | Mechanism Foundry Catalog Service | Create service for catalog data, remove inline definitions | Catalog service, snapshot tests |
| MM-3.2 | Foundry Interaction Controller | Move controls/physics updates into controller; UI binds signals only | Controller, tests, instrumentation |
| MM-3.3 | Blueprint Composition Pipeline | Break out `BlueprintOptimizer` into composer + layout service | Composer module, regression SVG tests |
| MM-4.1 | Legacy Shim Cleanup | Remove unused legacy helpers replaced by services | Composer-default blueprint flow (done), Foundry slider legacy paths removed, documentation update |
| MM-4.2 | Scenario Automation Pack | Add automated scripts for recomposed workflows (image processing, recommendation, export) | Scenario files, CI job |
| MM-4.3 | Final Review & Hand-off | ADR updates, architecture diagrams, knowledge share session | Updated ADRs, diagrams, retro notes |

## 11. Rollout & Rollback Plan
- Feature flag each refactored workflow (`MECHANISM_REFACTOR_ENABLED`, etc.).
- Dual-run new controllers alongside legacy logic until metrics stable; tap telemetry to monitor.
- Rollback uses preserved legacy modules invoked when feature flags off.
- Provide migration guide for devs referencing old functions.

## 12. Definition of Done
- UI functionality unchanged (verified via manual + automated checks).
- Targeted god class reduced to ≤800 LOC with delegated logic; legacy methods remain thin wrappers.
- Telemetry spans cover success/failure paths; dashboards updated.
- Unit/integration tests green with ≥80 % coverage for new modules.
- Documentation (PRD, ADR updates, developer guide) reflects new architecture.
