# AGENTS.md — Engineering Codex for System Development

**Author:** Alan Synn · [alan@alansynn.com](mailto:alan@alansynn.com)
**Scope:** Unified standards for research and system software design, implementation, and deployment.

---

## 1. Purpose

* Design research code to evolve into long-lived, production-grade systems.
* Every change must carry intent, measurement, and recoverability.
* Modularity, testability, observability, and replaceability are non-negotiable defaults.

---

## 2. Core Principles

* **Modular-first:** Decompose into single-responsibility components.
* **Interface-driven:** Define minimal, focused contracts between modules.
* **Dependency inversion:** Depend on abstractions, never concrete implementations.
* **Composition over inheritance:** Build features by combining modules, not subclassing.
* **Plan before code:** Architectural plan and review are mandatory before implementation.
* **Each module includes tests, metrics, and clear boundaries.**
* **Stable public APIs; replaceable internals.**
* **Every change must be observable and measurable.**

---

## 3. Plan-First Implementation Flow

**Design Plan (mandatory before implementation):**

1. **Problem / Goal** — include quantitative targets (throughput, latency, complexity reduction).
2. **In-Scope / Out-of-Scope.**
3. **Architecture Overview** — modules, layers, data/control flow, replaceable points.
4. **Public API** — inputs, outputs, error semantics, versioning, constraints.
5. **Dependencies** — internal modules, external libraries, data sources.
6. **Test Strategy** — unit/integration/regression/property-based, with success criteria.
7. **Observability Plan** — logging, metrics, tracing, tag structure.
8. **Performance / Resource Constraints** — input scale, latency targets, memory/IO ceilings.
9. **Risks / Mitigations** — performance bottlenecks, data drift, dependency instability.
10. **Rollout / Rollback Plan.**
11. **Definition of Done (DoD)** — tests, docs, metrics, and review gates.

**Approval flow:** Draft → Review/Q&A → Revise → Explicit ACK → Implementation.
No code without approved design.

---

## 4. Design and Pattern Guidelines

* Follow **SOLID**, **DRY**, **KISS**, **YAGNI**.
* Recommended patterns:

  * **Strategy** – interchangeable algorithms.
  * **Adapter / Port** – handle variability of external systems.
  * **Facade** – expose simplified APIs for complex subsystems.
  * **Factory / Registry** – runtime plugin extensibility.
  * **Decorator** – extend behavior without modifying base code.
  * **Observer / Event** – decoupled reactive communication.
* Architectural styles:

  * **Hexagonal (Ports & Adapters)** for replaceability.
  * **Layered Architecture** for separation of concerns.
  * **Plugin / Microkernel** for runtime extensibility.
  * **CQRS** where command/query separation improves clarity.

---

## 5. Module Boundaries and Dependencies

* Define boundaries along **axes of change**: group what changes together, separate what changes for different reasons.
* Maintain **stable dependency direction**: policies depend on details only through abstractions.
* Keep internal data models private; minimize cross-boundary exposure.
* Each module owns its API, internals, and test suite.
* Default goals: **low coupling, high cohesion, explicit ownership.**

---

## 6. Testing Strategy

* **Unit tests:** pure logic, normal and edge/error paths.
* **Integration tests:** module boundary interactions with real adapters when possible.
* **Regression/Snapshot tests:** lock key scenarios and critical metrics.
* **Property-based tests:** validate invariants and constraints with generated data.
* **Coverage:** thresholds per module criticality (e.g., > 80 % for core modules).
* No code merges without relevant tests.

---

## 7. Observability and Metrics

* Structured logging with levels and correlation IDs.
* Core metrics: latency, throughput, error rate, resource usage.
* Tag versions and experiment IDs to trace effects over time.
* Regular profiling (CPU, memory, IO) and baseline maintenance.
* Every improvement must have measurable impact.

---

## 8. Execution and Tooling

* Use consistent execution/build/test scripts across environments.
* Keep development, CI, and production environments aligned.
* Formatting, linting, and CI configurations must be standardized project-wide.

---

## 9. Definition of Done (DoD)

* Approved design plan (ACK).
* All tests and CI checks pass.
* Observability and metrics integrated.
* Documentation (README, CHANGELOG, ADRs) updated.
* Code review approved.
* Public API version updated if changed.
* Rollout/rollback plan recorded.

---

## Closing Note

This codex is designed for **system builders** who integrate research and production code into coherent, measurable, and resilient systems.
All unnecessary constraints are removed—focus is on **design discipline, observability, and replaceability**.
Before merging any change, ask yourself:

> “Why does this change exist?”
> “How will I measure its effect?”
> “How can I roll it back safely?”
