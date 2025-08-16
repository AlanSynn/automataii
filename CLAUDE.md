You are a professional and legendary SW Engineer. Following document is a codebook within the team.

**Author** Alan Synn · [alan@alansynn.com](mailto:alan@alansynn.com)

## Objectives

Producing stable, scalable, reusable research/sw code.

## Core Principles

MUST Files exceeding 500 LOC trigger immediate refactoring/modularization.
MUST Modular-first architecture—decompose into single-responsibility components.
MUST Pattern-driven design—Strategy, Factory, Repository patterns for extensibility.
MUST Interface segregation—define minimal, focused contracts between modules.
MUST Dependency inversion—depend on abstractions, not concrete implementations.
MUST Composition over inheritance—build complex behavior through module composition.
MUST Plan-first implementation—obtain architectural approval before coding.
MUST Every module includes isolated tests, metrics, and clear boundaries.
MUST High cohesion and loose coupling as defaults.
MUST Stable interfaces, replaceable implementations. Minimize public API, maximize ability to swap internals.
MUST Every change includes tests, analysis, and observability. Improvements that cannot be measured are not improvements.
## 1. 500+ LOC Policy (Refactor Triggers)

Trigger immediate refactoring and/or module split when any condition below is met:

- Single file exceeds/expected to exceed 500 LOC (MUST split)
- Single function exceeds 100 LOC or has cyclomatic complexity (CC) > 10
- One module carries 3+ distinct domain responsibilities (SRP violation smell)
- Bidirectional/cyclic dependencies or rapidly growing dependency graph complexity
- Test runtime spikes or frequent unintended side effects on changes

Recommended split axes:

- Domain boundaries (e.g., data ingestion, feature engineering, factor computation, signal generation, portfolio allocation, risk/checks)
- Layer boundaries (Interface/UseCase/Domain/Infra or Ports/Adapters)
- Strategy/Policy boundaries: hide algorithm families behind interfaces for hot-swapping

## 2. Plan-First Before Implementation

Write a concise design plan and obtain review/approval before coding (MUST).

Plan required content:

- Problem/Goal: what and why (include quantitative targets: performance, stability, complexity reduction)
- In-scope/Out-of-scope
- Architecture sketch: boundaries (modules/layers), data/control flow, replaceable points
- Public API: inputs/outputs, errors, constraints, versioning policy
- Dependencies: internal/external libs, upstream/downstream modules, data sources
- Test strategy: unit/integration/regression/property-based, success criteria
- Observability/logging/metrics: what to measure and where to emit
- Risks/mitigations: perf/memory/latency/data quality/drift, etc.
- Rollout/rollback plan: progressive release, feature flags, compatibility
- Definition of Done (DoD): pre-merge checklist, perf/quality gates

Approval process:

- Share plan → Q&A → revise → explicit approval (ACK) → start implementation (MUST)

## 3. Design Principles and Pattern Usage

- Follow SOLID, DRY, KISS, YAGNI
- Use Strategy, Factory/Abstract Factory, Adapter, Facade, Observer/Event, Template Method, Decorator
- Consider Repository and Use Case (application service) layers, CQRS where needed
- Prefer dependency injection (DI) and interface-first design
- Adopt Hexagonal (Ports & Adapters), Layered, or Plugin architectures for replaceability

Pattern selection guidelines:

- Frequent algorithmic swapping → Strategy
- External system/data-source variability → Adapter + Port
- Complex subsystem simplified API → Facade
- Runtime extensibility (plugins) → Registry-based Factory + Interface

## 4. Module Boundaries, Coupling, and Cohesion

- Draw boundaries along “axes of change.” Group items that change together; separate independent change vectors.
- Stable dependency direction: policies depend on details, never the reverse.
- Minimize data model exposure across boundaries.

Measurement and reporting (MUST):

- File header must include Lines, Public API, Deps In/Out, Coupling (Low/Medium/High) with rationale.
- Complexity: CC, number of functions/classes, average function length.
- Dependency list (top 5) and directionality.

## 5. File Header Template (recommended for all source files)

```text
# <Module/File Name>
- Lines: <N>
- Public API: <functions/classes exported>
- Deps In (Afferent): <#> [top callers or modules]
- Deps Out (Efferent): <#> [key dependencies]
- Coupling: <Low|Medium|High> (rationale: …)
- Cohesion: <Feature|Layer|Utility> (notes)
- Owner: <name>, Reviewers: <names>
- Last Updated: <YYYY-MM-DD>
```

## 6. Testing Strategy

- Unit: isolate pure logic; spec-based cases plus edge/error paths
- Integration: verify interactions at boundaries (ports) with real adapters
- Regression/Snapshot: lock critical scenarios and key metrics (e.g., PnL, Sharpe, risk)
- Property-based: verify invariants/constraints (normalization, conservation laws, etc.) via generated tests
- Coverage targets: set line/branch thresholds by module criticality

## 7. Observability

- Structured logging (levels, correlation IDs), key metrics (latency/error/perf), notable events
- Tag experiments/versions to track effects of change
- Regular perf/memory/IO profiling with reports

## 8. Performance and Resource Constraints

- Specify input scale and timing constraints in the plan
- Analyze algorithmic complexity, memory ceilings, parallelization/batching strategy
- Define criteria for caching/streaming/lazy evaluation

## 9. Security and Data Governance

- Segregate/mask sensitive data; least privilege access
- Scan third-party deps for licenses/vulnerabilities
- Reproducible data pipelines (schema versions, source hashes)

## 10. Documentation and Code Style

- Module README: purpose, public API, examples, constraints, versioning
- Type hints, clear naming, consistent formatter/linter
- Maintain CHANGELOG and ADRs (Architecture Decision Records)

## 11. Automated Quality Gates

- Pre-commit/CI should block or warn on:
  - File > 500 LOC, function > 100 LOC, CC > 10
  - Public API changes without version/CHANGELOG updates
  - Test/coverage/format/lint failures

## 12. Code Review Checklist (summary)

- Requirements met; scope aligned; no plan deviations
- Proper boundaries/dependency direction; low coupling, high cohesion
- Public API minimal and clear; error/exception handling consistent
- Perf/resource/threading/IO considerations addressed
- Tests sufficient; observability added/updated
- Docs/header/CHANGELOG/ADRs updated

## 13. Change Management

- Record design decisions as ADRs (problem/options/decision/rationale/impact)
- Progressive releases with rollback plans; use feature flags

## 14. Example: Split Strategy for Factor Computation

- When “factor computation” nears 500 LOC:
  - Modularize common utilities (window ops, normalization)
  - Implement each factor as a Strategy behind a common interface
  - Abstract data access behind a Repository (Port) with swappable Adapters
  - Separate simulation/backtest orchestration as a Use Case to keep dependency direction stable

## 15. Definition of Done (DoD)

- Plan approved (ACK) and recorded
- File headers updated (lines/coupling, etc.)
- Tests/observability/docs/ADR/CHANGELOG updated
- Quality gates passing and reviews approved

---

## 16. Run code

- MUST use `uv run` for python refer to pyproject.toml
- e.g. `uv run {project}`

Appendix A. Design Plan Template

```text
# Title: <problem/feature>
- Goals/Metrics:
- In-Scope/Out-of-Scope:
- Architecture/Boundaries:
- Public API:
- Dependencies (internal/external):
- Test Strategy:
- Observability/Metrics:
- Performance/Resource Constraints:
- Risks/Mitigations:
- Rollout/Rollback:
- Definition of Done (DoD):
- Timeline/Owner/Reviewers:
```

Appendix B. Module README Template

```text
# <Module>
- Purpose:
- Public API:
- Examples:
- Constraints/Assumptions:
- Versioning/Compatibility:
- Internal Structure (summary):
```

Appendix C. Refactoring Checklist

- 500+ LOC or CC thresholds exceeded
- SRP violations (mixed responsibilities)
- Frequent extension points lacking interfaces
- Weak tests/frequent regressions
- Dependency direction inversion/cycles

Appendix D. Coupling Classification (example)

- Low: one-way deps, few stable interfaces, low swap cost
- Medium: some external deps, limited blast radius
- High: bidirectional/cyclic/wide blast radius → split immediately
