# Modular UI & Core Refactor PRD

## 1. Problem / Goal
- **Problem**: GUI and application modules have grown into tightly coupled god classes (>4k LOC each), making change cost high, UI behavior hard to test, and runtime latency unpredictable.
- **Business/Research Goal**: Evolve the research-grade automataii app into a modular, scalable system with measurable UX quality. Achieve ≤600 LOC per module, ≤15 public methods per class, dependency depth <3. Reduce GUI workflow latency by 30%, and automate ≥80% of critical UI regression checks.
- **Success Metrics**:
  - Maintain baseline parity: zero regressions in top 10 business-critical workflows.
  - 30% reduction in `ui` command latency (median) vs. current baseline.
  - 25% reduction in cyclomatic complexity for refactored modules.
  - 80% of UI/graphics test cases automated; <3% false positives in visual diffs.
  - Shrink legacy footprint: eliminate 100% of confirmed dead modules and ≥90% of dead classes/functions surfaced by static analysis before architecture migration.

## 2. Scope
- **In-Scope**:
  - Refactor `automataii/gui`, `generation`, `core`, `services` into layered, single-responsibility modules.
  - Introduce deterministic view-models, command/query handlers, and dependency-inversion boundaries.
  - Build automated UI/graphics test harness (headless rendering, scenario scripting, visual diffing).
  - Establish observability for UI and application services (structured logs, metrics, tracing).
- **Out-of-Scope**:
  - Re-training ML models or altering dataset schemas.
  - Shipping net-new end-user features (feature parity only).
  - Rebuilding asset pipelines or art resources beyond testing fixtures.

## 3. Architecture Overview
- **Domain Layer**: Immutable domain models for mechanisms, skeletons, kinematics algorithms. Domain services expose intent-focused contracts and emit domain events.
- **Application Layer**: Command/query handlers orchestrating workflows (e.g., `GenerateBlueprintCommandHandler`, `RefreshMechanismPreviewQuery`). Uses dependency-injected ports for domain operations and infrastructure.
- **Interface Layer**: View-models producing deterministic UI state from domain/application events. GUI, CLI, and batch adapters consume view-model outputs via an event bus.
- **Infrastructure Layer**: Adapters for persistence, ML inference, rendering engines. All bound through factories/registries, swappable per environment.
- **Testing & Observability Harness**: Scenario DSL drives commands, headless renderer produces snapshots, metrics capture render/latency. Simulation clock abstraction allows deterministic animation playback.

## 4. Public API
- **Command API**: Typed commands (`GenerateBlueprintCommand`, `LoadMechanismCommand`) returning status envelopes with correlation IDs and error semantics (`recoverable`, `retryable`, `fatal`).
- **Query API**: Deterministic queries (`GetMechanismStateQuery`, `CaptureFrameQuery`) yielding DTOs; stable versioning with semantic guarantees.
- **Event Bus**: Versioned domain/application events (`MechanismUpdated`, `BlueprintValidated`, `RenderFrameReady`) for UI subscription. Support record/replay hooks for test harness.
- **Plugin Registration**: Registry-based interface for new render drivers, mechanism solvers, analytics sinks. Public contracts documented and versioned.

## 5. Dependencies
- **Internal**: Domain algorithms rely on `core/kinematics`. Application services depend on domain ports and infrastructure abstractions. GUI adapters rely solely on application ports and view-model contracts.
- **External**: Rendering (Qt/OpenGL), data storage, ML inference frameworks. Introduce adapter interfaces so these dependencies can be mocked/replaced in tests.
- **Injection Strategy**: Lightweight service container or functional wiring module that composes dependencies per environment (production, test, headless).

## 6. Test Strategy
- **Unit Tests**: Property-based tests for kinematics/IK; reducer tests for view-model state transitions; command handlers with mocked ports.
- **Integration Tests**: Contract suites per adapter ensuring consistent behavior between application ports and infrastructure implementations.
- **Scenario Tests**: Scripted flows using scenario DSL (JSON/YAML) executed via headless harness; assertions on emitted state, logs, metrics.
- **Visual Regression Tests**: Headless renderer captures frames and depth buffers; perceptual diff compares against golden baselines with configurable thresholds.
- **Performance Benchmarks**: Measure command latency, render time, animation frame pacing under synthetic load; run nightly and on release branches.
- **Coverage Targets**: Domain/application layers ≥85%, view-models ≥80%, scenario suite covering top-priority workflows.

## 7. Observability Plan
- **Structured Logging**: Include `session_id`, `command_id`, `scenario_id`, `mechanism_id`. Emit intent-level events at info, detailed state for debug.
- **Metrics**: Track command latency, render time, frame drop rates, scenario pass/fail counts, diff scores. Publish to dashboard with alerting thresholds.
- **Tracing**: Lightweight spans across command execution, domain service calls, render pipeline. Correlate with scenario runs in CI.
- **Artifact Storage**: Store golden snapshots and diff artifacts versioned alongside fixtures; auto-expire obsolete baselines via retention rules.

## 8. Performance / Resource Constraints
- Median synchronous UI interaction <120 ms; 95th percentile <250 ms.
- Headless harness runs full critical scenario suite in ≤20 minutes in CI.
- Memory ceiling for editors <1.5 GB during automated runs; streaming assets with caching eviction.
- Batch pipelines (blueprint generation) sustain 500 jobs/hour on reference hardware; measured post-refactor.

## 9. Risks / Mitigations
- **Hidden Couplings**: Legacy UI logic reaches into domain internals. → Introduce strangler façade and contract tests before cutting over.
- **Visual Diff Flakiness**: Driver or GPU variance. → Use software renderer fallback, perceptual metrics with tolerance, hash golden assets.
- **Scope Creep**: Refactor exposes feature gaps. → Phase per milestone, maintain backlog triage, enforce DoD gates.
- **Team Ramp-Up**: New architecture patterns. → Provide ADRs, pairing sessions, coding standards.

## 10. Rollout / Rollback Plan
- Feature-flag each migrated workflow (mechanism editor, blueprint optimizer, animation preview). Dual-run legacy and new paths until metrics stable.
- Maintain adapter bridge to redirect commands to legacy modules if new implementation regresses.
- Capture baseline metrics before each milestone; rollback triggered if latency/quality regress >10% and fix not ready within 24h.

## 11. Definition of Done
- Approved design (this PRD) with stakeholder ACK and ADRs for major decisions.
- Refactored modules meet LOC/complexity targets and pass full automated test suite.
- Observability dashboards live; alerting tuned and documented.
- UI harness documented (scenario authoring guide) and integrated into CI/CD.
- Rollout checklist executed, rollback validated, release notes updated.

---

## Milestones & Deliverables

### Milestone 0 — Baseline Capture & Planning (Week 0–1)
- Inventory current module sizes, complexity, dependency graphs; store metrics baseline.
- Catalog top 15 UI workflows and manual test cases with owners and business priority.
- Stand up telemetry scaffolding (basic logging hooks) to measure current latency.
- Run static dead-code sweep (import graph + Vulture) and delete confirmed-unused modules/scripts; capture follow-up queue for intra-module dead methods.
- Deliverables: Baseline report, prioritized workflow list, ADR-000 (architecture intent), metric dashboards initial view.

### Milestone 1 — Domain & Application Layer Refactor (Week 2–4)
- Extract immutable domain models and services (`core`, `generation`) with property tests.
- Implement command/query handler interfaces with dependency-inverted ports.
- Introduce service wiring module (DI container/registry) and update legacy code to consume via façade.
- Continue static-analysis-driven cleanup: prune dead classes/functions within refactored scope before applying new boundaries.
- Deliverables: Refactored domain/application modules meeting LOC/complexity targets, ≥85% coverage, ADR-001 (domain boundaries), passing unit/integration suite.

### Milestone 2 — UI Layer Modularization (Week 4–6)
- Build deterministic view-models per UI workflow; decouple from rendering toolkit.
- Implement event bus/state store with record/replay hooks and simulation clock abstraction.
- Migrate one pilot workflow (e.g., mechanism editor) behind feature flag to validate architecture.
- Deliverables: View-model library, event bus module, feature-flagged pilot workflow, ADR-002 (UI architecture), initial scenario DSL spec.

### Milestone 3 — Automated UI/Graphics Harness (Week 6–8)
- Implement headless rendering adapter (OpenGL software/ANGLE) with frame capture API.
- Develop scenario runner CLI, DSL parser, and snapshot diff pipeline with perceptual thresholds.
- Automate top 5 workflows; integrate metrics emission and CI job (≤20 min runtime).
- Deliverables: Harness toolchain, golden baseline repository, scenario authoring guide, CI job logs, <3% false-positive rate validated.

### Milestone 4 — Full Workflow Migration & Observability (Week 8–10)
- Migrate remaining critical workflows to new architecture; retire legacy dependencies.
- Expand scenario coverage to ≥80% of prioritized workflows, including stress/performance cases.
- Finalize dashboards (latency, diff metrics, frame performance) and alert thresholds.
- Deliverables: Feature parity confirmation, automated suite coverage report, observability dashboards, ADR-003 (observability topology), rollback playbook.

### Milestone 5 — Stabilization & Handoff (Week 10–12)
- Burn-in period with live telemetry monitoring; resolve residual defects.
- Document maintenance playbooks, module ownership, and onboarding materials.
- Final readiness review and post-project retro capturing learnings and future backlog.
- Deliverables: Final DoD checklist, handoff documentation, retro report, backlog of future enhancements.

## Open Questions
- Which rendering backend (Qt off-screen, EGL, software) best balances determinism and performance?
- Do we need cross-platform harness support immediately, or can we stage (macOS first, then Linux/Windows)?
- What is the acceptable storage footprint for snapshot artifacts in CI, and how often can we rotate baselines?

## Next Actions
1. Secure stakeholder approval for this PRD and milestone plan.
2. Launch Milestone 0 tasks: gather baselines, instrument telemetry, schedule ADR reviews.
3. Decide on headless rendering strategy and prototype feasibility before Milestone 2 kickoff.
