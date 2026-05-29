# MS4N P0 Implementation Task Breakdown

작성일: 2026-05-14
상태: **4주 internal pilot MVP backlog**
상위 방향: `plan/09-ms4n-implementation-architecture-plan.md`

## 1. Definition of Done for P0

Naming constraint: the top-level tab is **Lab**. Do not introduce an MS4N-prefixed tab class, presentation tab package, or tab objectName in implementation; use `LabTab`, `presentation/qt/tabs/lab`, and `tab_lab`.


P0 is done when a facilitator can run one 45–60 minute internal pilot using the bar-board linkage kit and export analyzable data.

Required user-visible behavior:

1. Lab tab opens without breaking existing tabs.
2. Facilitator selects a P0 kit asset from manifest, including `kit/bar-board.svg`.
3. Facilitator selects or identifies one mechanism/part.
4. System captures a JSON-safe before snapshot.
5. Facilitator records one breakdown/change and one repair action.
6. System captures a JSON-safe after snapshot.
7. Learner explanation and facilitator move tags are saved.
8. Trace Duel shows either before/after summary or predicted/observed summary.
9. Motion Autopsy table shows episode rows.
10. Export writes `episodes.jsonl`, `coding_sheet.csv`, and a minimal autopsy sheet.

Required engineering behavior:

- No Qt objects in domain/application data models.
- No project serializer migration in P0.
- Existing `.automataii` layer payload round-trip remains intact.
- Existing Mechanism Design tests still pass.
- New MS4N tests pass.

## 2. Implementation phases

### Phase P0-A — Schema and metrics foundation

Target duration: Week 1, first half.

Files to add:

```text
src/automataii/domain/ms4n/__init__.py
src/automataii/domain/ms4n/episodes.py
src/automataii/domain/ms4n/repair_taxonomy.py
src/automataii/domain/ms4n/trace.py
src/automataii/domain/ms4n/kit_assets.py
```

Key classes/functions:

- `BreakdownRepairEpisode`
- `MechanismStateSnapshot`
- `MechanicalChange`
- `BreakdownEvent`
- `RepairAction`
- `LearnerExplanation`
- `FacilitatorMove`
- `ArtifactRef`
- `TraceRef`
- `TraceSummary`
- `summarize_trace(points)`
- `compare_trace_summaries(before, after)`

Acceptance criteria:

- Dataclasses are frozen where practical.
- `to_dict()` or serializer helper returns JSON-safe values.
- `NaN`/`inf` trace values are rejected before export or layer bridge storage; no silent filtering.
- Traces over 500 points are deterministically downsampled to 500 points while preserving first/last points and recording `original_point_count`, `was_downsampled`, and `sampling_rule`.
- `change_count` and `repair_count` are enforced: `status="repaired"` is invalid when either count exceeds 1. Multi-change troubleshooting must remain `open`/`unresolved` with `constraint_violation_note`.
- No `Any` in public type signatures unless unavoidable for JSON value alias.

Tests:

```text
tests/domain/ms4n/test_episode_models.py
tests/domain/ms4n/test_trace_metrics.py
```

### Phase P0-B — Kit manifest and catalog

Target duration: Week 1, second half.

Files to add:

```text
kit/ms4n-kit-manifest.json
src/automataii/infrastructure/ms4n/__init__.py
src/automataii/infrastructure/ms4n/kit_manifest_loader.py
src/automataii/application/ms4n/__init__.py
src/automataii/application/ms4n/kit_catalog_service.py
```

Manifest must include at minimum:

- `kit/bar-board.svg`
- `kit/ms4n-00-bar-board-guide.svg`
- `kit/ms4n-01-linkage-bars.svg`
- `kit/ms4n-06-trace-prompt-cards.svg`
- `kit/ms4n-07-fabrication-checks.svg`

Acceptance criteria:

- Manifest schema version is `ms4n.kit.v1`.
- Missing file behavior is tested and explicit.
- UI does not read JSON directly; it uses `KitCatalogService`.
- Each asset declares mechanism types, change types, evidence outputs, and pilot priority.

Tests:

```text
tests/application/ms4n/test_kit_catalog_service.py
tests/infrastructure/ms4n/test_kit_manifest_loader.py
```

### Phase P0-C — Episode service and bridge repository

Target duration: Week 2, first half.

Files to add:

```text
src/automataii/application/ms4n/episode_service.py
src/automataii/application/ms4n/layer_data_bridge.py
src/automataii/application/ms4n/trace_snapshot.py
src/automataii/application/ms4n/view_models.py
```

Responsibilities:

- Start an episode draft.
- Capture before snapshot from JSON-safe mechanism state.
- Attach prediction/breakdown/change.
- Attach one repair action.
- Capture after snapshot.
- Attach learner explanation and facilitator moves.
- Validate completeness.
- Convert to/from `MechanismData.layer_data["ms4n"]` payload. This bridge is the hard validation boundary and must reject non-finite values, dropped required fields, and Qt-object-derived `None` before the permissive project serializer sees the payload.

Acceptance criteria:

- Incomplete episode is represented as `status="open"`, not silently exported as complete.
- `status="repaired"` requires before snapshot, repair action, after snapshot, and explanation or explicit absence note.
- Participant identifiers are hashes/aliases only.
- `layer_data` bridge preserves existing `generated_path_data` and unrelated keys.

Tests:

```text
tests/application/ms4n/test_episode_service.py
tests/application/ms4n/test_layer_data_bridge.py
tests/test_ms4n_project_layer_data_bridge.py
```

### Phase P0-D — Trace snapshot seam from Mechanism Design

Target duration: Week 2, second half.

Files to add or minimally modify:

```text
src/automataii/presentation/qt/tabs/mechanism_design/ms4n_snapshot_adapter.py
```

Optional existing file touch if needed:

```text
src/automataii/presentation/qt/tabs/mechanism_design/tab.py
```

Responsibilities:

- Read selected mechanism id/type/params if available.
- Call `PathTraceManager.get_trace_points(mechanism_id)`.
- Convert `QPointF` to `TracePoint` tuples.
- Return JSON-safe snapshot input for application service.

Acceptance criteria:

- Adapter is read-only.
- Adapter does not mutate `MechanismDesignTab` state.
- First add/consume an explicit public snapshot source contract such as `get_ms4n_snapshot_source(mechanism_id) -> Mapping[str, JsonValue]`; do not read `_path_trace_manager`, `mechanism_layers`, or other private state directly from the adapter.
- `QPointF` never leaves presentation boundary.
- Empty trace is valid and tagged as such.

Tests:

```text
tests/presentation/qt/tabs/mechanism_design/test_ms4n_snapshot_adapter.py
# or tests/application/ms4n/test_trace_snapshot.py for pure conversion helpers
```

### Phase P0-E — Export services

Target duration: Week 3, first half.

Files to add:

```text
src/automataii/application/ms4n/export_service.py
src/automataii/application/ms4n/autopsy_sheet_service.py
src/automataii/infrastructure/ms4n/jsonl_writer.py
src/automataii/infrastructure/ms4n/coding_csv_writer.py
src/automataii/infrastructure/ms4n/bundle_writer.py
```

Exports:

```text
research/episodes.jsonl
research/coding_sheet.csv
research/facilitator_moves.csv
autopsy/<episode_id>_sheet.md
traces/<episode_id>_before.json
traces/<episode_id>_after.json
manifest.json
```

Acceptance criteria:

- JSONL has one episode per line.
- CSV headers are stable.
- Exports are deterministic with fixed fixture timestamps.
- Unknown extension/export mode fails loudly.
- Export does not require GUI file dialogs.

Tests:

```text
tests/application/ms4n/test_export_service.py
tests/application/ms4n/test_autopsy_sheet_service.py
tests/infrastructure/ms4n/test_jsonl_writer.py
tests/infrastructure/ms4n/test_coding_csv_writer.py
tests/infrastructure/ms4n/test_bundle_writer.py
```

### Phase P0-F — Lab UI skeleton

Target duration: Week 3, second half.

Files to add:

```text
src/automataii/presentation/qt/tabs/lab/__init__.py
src/automataii/presentation/qt/tabs/lab/tab.py
src/automataii/presentation/qt/tabs/lab/presenter.py
src/automataii/presentation/qt/tabs/lab/view_protocol.py
src/automataii/presentation/qt/tabs/lab/widgets/__init__.py
src/automataii/presentation/qt/tabs/lab/widgets/kit_catalog_panel.py
src/automataii/presentation/qt/tabs/lab/widgets/episode_builder_panel.py
src/automataii/presentation/qt/tabs/lab/widgets/trace_duel_panel.py
src/automataii/presentation/qt/tabs/lab/widgets/motion_autopsy_panel.py
src/automataii/presentation/qt/tabs/lab/widgets/facilitator_log_panel.py
```

Files to modify:

```text
src/automataii/presentation/qt/main_window.py
src/automataii/presentation/qt/tabs/__init__.py
```

P0 UI constraints:

- Plain Qt widgets are enough.
- No dashboard.
- No camera dependency.
- No AI suggestions.
- QFileDialog may be used only for selecting export directory; core export service must be testable without it.

Acceptance criteria:

- Offscreen widget instantiation passes.
- Tab registration does not break current tab switching.
- Presenter can load manifest, build a dummy episode, and trigger export with mocked services.

Tests:

```text
tests/presentation/lab/test_lab_presenter.py
tests/ui/tabs/test_lab_tab.py
```

### Phase P0-G — Internal pilot rehearsal

Target duration: Week 4.

Activities:

- Run one internal session with bar-board + one 4-bar linkage.
- Intentionally introduce one controlled breakdown, e.g. tight washer/friction, collision tab, wrong pivot.
- Capture at least 3 episodes including one unresolved/abandoned case if it occurs.
- Export bundle.
- Check whether coding CSV rows are analyzable.
- Revise schema only if fields block analysis.

Artifacts:

```text
pilot/ms4n_internal_rehearsal_<date>/
  bundle/
  field_notes.md
  codebook_sanity_check.md
```

Do not commit real participant data. Use fake/internal pilot aliases only.

## 3. File-by-file backlog

| ID | Priority | File(s) | Work | Done when |
|---|---:|---|---|---|
| MS4N-001 | P0 | `domain/ms4n/episodes.py` | Episode dataclasses | JSON-safe round-trip tests pass |
| MS4N-002 | P0 | `domain/ms4n/repair_taxonomy.py` | Small vocabularies | Invalid vocab rejected |
| MS4N-003 | P0 | `domain/ms4n/trace.py` | Trace summaries and comparisons | Empty/one-point/normal trace tests pass |
| MS4N-004 | P0 | `kit/ms4n-kit-manifest.json` | Manifest references existing kit sheets | Loader validates paths |
| MS4N-005 | P0 | `infrastructure/ms4n/kit_manifest_loader.py` | Manifest loader | Missing field/file policy tested |
| MS4N-006 | P0 | `application/ms4n/kit_catalog_service.py` | UI-friendly asset queries | Filter tests pass |
| MS4N-007 | P0 | `application/ms4n/episode_service.py` | Episode state/use-case methods | Complete/incomplete validation tested |
| MS4N-008 | P0 | `application/ms4n/layer_data_bridge.py` | Bridge to `MechanismData.layer_data` | Existing layer keys preserved |
| MS4N-009 | P0 | `application/ms4n/trace_snapshot.py` | Pure trace conversion helpers | No Qt import; tuple tests pass |
| MS4N-010 | P0 | `presentation/qt/tabs/mechanism_design/ms4n_snapshot_adapter.py` | Read-only runtime snapshot adapter | Mocked tab/trace tests pass |
| MS4N-011 | P0 | `infrastructure/ms4n/jsonl_writer.py` | Episode JSONL | Stable JSONL golden test pass |
| MS4N-012 | P0 | `infrastructure/ms4n/coding_csv_writer.py` | Coding CSV | Stable header golden test pass |
| MS4N-013 | P0 | `application/ms4n/autopsy_sheet_service.py` | Markdown-only autopsy sheet | Snapshot/golden test pass |
| MS4N-014 | P0 | `application/ms4n/export_service.py` | Bundle orchestration | tmp_path integration test pass |
| MS4N-015 | P0 | `presentation/qt/tabs/lab/*` | UI skeleton + presenter | Offscreen smoke and presenter tests pass |
| MS4N-016 | P0 | `presentation/qt/main_window.py` | Add tab | main window/tab test passes |
| MS4N-017 | P0 | `tests/fixtures/ms4n/*` | Golden fixtures | Stable and anonymized |
| MS4N-018 | P0 | `plan/` + `.omx/plans/` | Keep research/engineering plan in sync | Review gate clear |

## 4. Explicit non-work for P0

Do not implement these until P0 pilot export works:

- automatic jam detector
- fiducial or camera tracking
- AI explanation scoring
- classroom dashboard
- cross-project analytics
- new project serializer migration
- multi-mechanism authoring wizard
- polished HTML/SVG/PDF poster generator
- automatic mechanism recommendation

## 5. Week-by-week plan

### Week 1 — Data contract first

- Write RED tests for episode schema, trace metrics, kit manifest loader.
- Implement domain data models and manifest loader.
- Freeze P0 vocabularies.

Gate:

```bash
uv run pytest tests/domain/ms4n tests/infrastructure/ms4n/test_kit_manifest_loader.py -v
```

### Week 2 — Episode flow without UI polish

- Implement application episode service.
- Implement layer_data bridge.
- Implement trace conversion and snapshot adapter.
- Validate project serializer bridge.

Gate:

```bash
uv run pytest tests/application/ms4n tests/test_ms4n_project_layer_data_bridge.py tests/ui/tabs/test_path_trace_manager.py -v
```

### Week 3 — Export and UI skeleton

- Implement JSONL/CSV/autopsy export.
- Build Lab tab skeleton.
- Wire tab in `main_window.py`.
- Verify offscreen smoke.

Gate:

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/presentation/lab tests/ui/tabs/test_lab_tab.py -v
uv run pytest tests/application/ms4n/test_export_service.py -v
```

### Week 4 — Pilot rehearsal and codebook sanity

- Use kit/bar-board with one controlled breakdown.
- Export data.
- Check if coding CSV supports planned qualitative coding.
- Revise only blocking fields.

Gate:

```bash
uv run pytest
uv run ruff check src/ tests/
uv run mypy src/automataii
```

## 6. Implementation order for actual coding

Recommended commit slices:

1. `ms4n domain schema and trace metrics`
2. `ms4n kit manifest and loader`
3. `ms4n episode service and layer_data bridge`
4. `ms4n export writers and autopsy sheet`
5. `lab tab skeleton`
6. `ms4n pilot fixtures and docs`

Each slice must include tests before moving to the next slice.

## 7. Reviewer-facing rationale

This plan intentionally treats failure as data, not as an error to hide. The implementation makes breakdown/repair episodes analyzable by preserving:

- mechanical variable changed,
- trace or motion consequence,
- physical observation or artifact reference,
- repair action,
- learner explanation,
- facilitator move.

That is the CHI-relevant software contribution: an inspectable scaffold that turns physical making breakdowns into structured explanation opportunities.

## 8. First coding slice must resolve review watchpoints

Before any UI implementation, the first coding slice must deliver these tests and code paths:

1. `tests/domain/ms4n/test_trace_metrics.py::test_trace_conversion_rejects_nan_and_infinite_coordinates`
2. `tests/domain/ms4n/test_trace_metrics.py::test_trace_normalization_downsamples_over_500_points_deterministically`
3. `tests/application/ms4n/test_episode_service.py::test_repaired_episode_rejects_more_than_one_primary_change`
4. `tests/application/ms4n/test_episode_service.py::test_repaired_episode_rejects_more_than_one_primary_repair`
5. `tests/application/ms4n/test_layer_data_bridge.py::test_bridge_rejects_non_finite_or_qt_derived_null_payloads`
6. `tests/presentation/qt/tabs/mechanism_design/test_ms4n_snapshot_adapter.py::test_adapter_consumes_public_snapshot_source_contract`

No Lab UI panel should be expanded until these boundary tests pass.
