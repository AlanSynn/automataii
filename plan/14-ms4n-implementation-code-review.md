<!-- Mirrored from .omx/plans for git-visible review durability. Keep in sync with the OMX code-review artifact. -->

# Code Review: MS4N Jams-as-Explanations Implementation Plan

Date: 2026-05-14
Scope: planning and implementation-gate artifacts for MS4N P0 Jams-as-Explanations.

## Verdict

- Code-reviewer recommendation: **APPROVE**
- Architectural status: **CLEAR**
- Final recommendation: **APPROVE**

## Files reviewed

Tracked/shareable plan artifacts:

- `plan/00-ms4n-plan-index.md`
- `plan/06-ms4n-wild-chi-directions.md`
- `plan/07-ms4n-autoresearch-review-loop.md`
- `plan/08-ms4n-jams-as-explanations-execution-plan.md`
- `plan/09-ms4n-implementation-architecture-plan.md`
- `plan/10-ms4n-p0-implementation-task-breakdown.md`
- `plan/11-ms4n-implementation-test-plan.md`
- `plan/12-ms4n-implementation-prd.md`
- `plan/13-ms4n-implementation-test-spec.md`

Local OMX handoff artifacts:

- `.omx/plans/prd-ms4n-jams-implementation-20260514.md`
- `.omx/plans/test-spec-ms4n-jams-implementation-20260514.md`

## Review loop summary

### First code-review pass

Result: `REQUEST CHANGES` / architecture `WATCH`.

Findings:

1. Trace/schema contract allowed ambiguous non-finite handling and soft max count.
2. One-change/one-repair rule was represented but not operationalized.
3. `.omx/plans` PRD/test-spec were ignored by git and needed tracked mirrors.
4. Architecture wanted explicit bridge validation and public read-only snapshot seam.
5. P0 export contract drifted between markdown/HTML/SVG.

### Resolution

The plan now requires:

- non-finite trace coordinates are rejected before export/storage;
- over-500-point traces are deterministically downsampled with first/last preserved and metadata recorded;
- `status="repaired"` is invalid when `change_count > 1` or `repair_count > 1`;
- multi-change episodes remain `open` or `unresolved` with `constraint_violation_note`;
- `application/ms4n/layer_data_bridge.py` is the hard validation boundary before permissive `MechanismData._json_safe()` serialization;
- `ms4n_snapshot_adapter.py` consumes a public read-only `get_ms4n_snapshot_source(...)`-style contract rather than private `MechanismDesignTab` state;
- P0 export is normalized to JSONL, coding CSV, facilitator CSV, trace JSON, manifest JSON, and markdown autopsy sheets only;
- `.omx/plans` PRD/test-spec are mirrored into git-visible `plan/12` and `plan/13`.

### Second code-review pass

Code-reviewer result: **APPROVE**, 0 issues.

Architect result: substantive architecture concerns resolved; remaining WATCH was only that `plan/12` and `plan/13` were not yet git tracked. This was resolved by staging the plan artifacts.

Evidence:

```text
git ls-files --error-unmatch plan/12-ms4n-implementation-prd.md plan/13-ms4n-implementation-test-spec.md
# plan/12-ms4n-implementation-prd.md
# plan/13-ms4n-implementation-test-spec.md
```

Therefore architectural status is upgraded to **CLEAR** for the planning gate.

## Verification evidence

- Anchor completeness check for `plan/09` through `plan/13`: **OK**.
- Shareability check: `plan/12` and `plan/13` are present in git index.
- Targeted regression:

```text
uv run pytest tests/test_project_serializer_assets.py tests/ui/tabs/test_path_trace_manager.py -q
51 passed in 1.47s
```

Code-reviewer rerun independently reported the same targeted regression passing with 51 tests.

## Remaining risks for implementation

These are not planning blockers, but must be handled in the first coding slice:

1. Write RED tests before implementing MS4N domain models.
2. Keep `domain/ms4n` free of PyQt and file I/O imports.
3. Implement bridge validation before relying on `MechanismData._json_safe()`.
4. Add public read-only Mechanism Design snapshot source before the adapter consumes runtime state.
5. Keep HTML/SVG/PDF autopsy export out of P0 unless tests are promoted.

## Final recommendation

**APPROVE / CLEAR** — the implementation gate is sufficiently concrete for P0 test-first coding.
