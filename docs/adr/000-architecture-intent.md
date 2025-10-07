# ADR-000: Modular UI & Automation Architecture Intent

- **Status**: Accepted (2025-10-19)
- **Context**: Automataii’s monolithic UI modules, legacy tooling, and manual QA loops block scalable feature work and automated validation. We need a refactor plan (see `docs/prd/modular_ui_automation_refactor_prd.md`) to introduce layered architecture, deterministic view-models, and automated UI regression testing.
- **Decision**:
  - Proceed with the milestone plan defined in the PRD, starting with Milestone 0 baselining and dead-code reduction.
  - Establish telemetry primitives (`telemetry_span`) to capture latency/health for all high-priority workflows; integrate into refactor deliverables.
  - Maintain backward-compatible GUI behaviour during the strangler migration via feature flags and façade adapters.
  - Treat the new test harness and observability stack as first-class deliverables (Definition of Done requires automated scenarios + dashboards).
- **Consequences**:
  - Initial engineering investment shifts to plumbing (instrumentation, harness, workflow inventory) before functional rewrites.
  - Existing manual workflows gain traceability metrics, enabling quantitative regression detection.
  - Teams must follow the modular layering guidelines; new modules require telemetry + tests at creation time.
  - Legacy modules slated for deletion remain in maintenance mode only; any new feature work must target the new architecture once delivered.
