# ADR 001 — Telemetry & Automation Observability

**Status:** Accepted  
**Date:** 2025-10-20  

## Context

MM-4 introduces scenario automation (e.g., blueprint export) and requires
observable, reproducible runs to validate refactors before surfacing new UI
controllers. The existing telemetry utilities (`telemetry_span`) were only used
inside application flows, leaving automation scripts opaque. Scenario artifacts
needed consistent manifests/metrics so dashboards can track duration, unit
system, and mechanism coverage over time.

## Decision

1. Scenarios live under `automataii.scenarios.*` and emit their outputs to a
   caller-provided directory. Each run:
   - wraps work in `telemetry_span("scenario.<name>")`
   - writes `*_manifest.json` (deterministic inputs, controller metadata)
   - writes `*_metrics.json` (duration, timestamps, artifact paths)
   - logs completion in a structured format for scraping
2. CLI gains `--scenario`/`--scenario-output` so we can execute automation via
   `uv run automataii --scenario blueprint-export` without spinning up the UI.
3. A lightweight helper (`scripts/collect_scenario_metrics.py`) aggregates
   metrics folders for dashboards.

## Consequences

- Automation runs inherit telemetry defaults (respecting
  `AUTOMATAII_TELEMETRY=0`). If telemetry is disabled, the manifest/metrics
  files still surface the critical data.
- CLI automation can be invoked in CI or locally, enabling reproducible QA
  steps for MM-4.x before UI rollout.
- Additional scenarios must adopt the same manifest/metrics contract to keep
  dashboards consistent. The ADR positions telemetry output as a requirement for
  future automation features.
