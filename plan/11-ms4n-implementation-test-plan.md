# MS4N P0 Implementation Test Plan

작성일: 2026-05-14
범위: `Jams as Explanations` P0 implementation tests
상위 문서: `plan/09-ms4n-implementation-architecture-plan.md`, `plan/10-ms4n-p0-implementation-task-breakdown.md`

## 1. Test strategy

P0 test strategy is RED -> GREEN -> regression.

1. Write schema and export tests before implementation.
2. Keep domain tests Qt-free.
3. Keep application export tests GUI-free.
4. Use offscreen Qt only for widget smoke tests.
5. Use golden fixtures for JSONL/CSV/autopsy sheet stability.
6. Run existing serializer/path trace tests to catch bridge regressions.

## 2. Test matrix

| Area | Test file | Main claim protected |
|---|---|---|
| Domain episode schema | `tests/domain/ms4n/test_episode_models.py` | Episode data is JSON-safe, deterministic, validatable. |
| Trace metrics | `tests/domain/ms4n/test_trace_metrics.py` | Trace summaries handle empty/one-point/normal traces. |
| Repair taxonomy | `tests/domain/ms4n/test_repair_taxonomy.py` | Symptom/cause/repair/facilitator codes stay bounded. |
| Kit manifest | `tests/infrastructure/ms4n/test_kit_manifest_loader.py` | Manifest references real kit files and valid schema. |
| Kit catalog service | `tests/application/ms4n/test_kit_catalog_service.py` | UI gets filtered P0 assets without reading JSON directly. |
| Episode service | `tests/application/ms4n/test_episode_service.py` | Before/change/repair/after/explanation lifecycle is valid. |
| Layer bridge | `tests/application/ms4n/test_layer_data_bridge.py` | `layer_data["ms4n"]` preserves schema and unrelated keys. |
| Project serializer bridge | `tests/test_ms4n_project_layer_data_bridge.py` | `.automataii` round-trip keeps MS4N payload. |
| Trace conversion | `tests/application/ms4n/test_trace_snapshot.py` | `QPointF`-like values become primitive trace tuples at boundary. |
| JSONL writer | `tests/infrastructure/ms4n/test_jsonl_writer.py` | One episode per line, stable key order. |
| CSV writer | `tests/infrastructure/ms4n/test_coding_csv_writer.py` | Coding CSV header/order is stable. |
| Autopsy sheet | `tests/application/ms4n/test_autopsy_sheet_service.py` | Sheet rows include breakdown, repair, explanation, facilitator move. |
| Bundle export | `tests/application/ms4n/test_export_service.py` | Study bundle contains required files. |
| Presenter | `tests/presentation/lab/test_lab_presenter.py` | UI orchestration works with mocked services. |
| Qt smoke | `tests/ui/tabs/test_lab_tab.py` | Tab instantiates offscreen and key panels exist. |
| Existing path trace regression | `tests/ui/tabs/test_path_trace_manager.py` | Adapter does not break trace manager. |
| Existing serializer regression | `tests/test_project_serializer_assets.py` | Existing layer payload behavior still holds. |

## 3. RED tests to write first

### 3.1 Episode schema

Test names:

```python
def test_breakdown_episode_to_dict_is_json_safe()
def test_breakdown_episode_round_trips_required_fields()
def test_breakdown_episode_rejects_non_finite_trace_values()
def test_repaired_episode_requires_before_repair_after_and_explanation_or_absence_note()
def test_episode_preserves_facilitator_moves()
def test_episode_records_unresolved_status_without_forcing_success()
def test_episode_counts_change_and_repair_actions()
def test_repaired_episode_rejects_more_than_one_primary_change()
def test_repaired_episode_rejects_more_than_one_primary_repair()
def test_multi_change_episode_requires_constraint_violation_note_and_unresolved_status()
```

Required fixture fields:

```python
episode_id="ep_001"
session_id="session_fake_001"
participant_hash="p_hash_fake"
mechanism_id="mech_1"
mechanism_type="four_bar"
part_name="right_arm"
kit_asset_ids=("bar-board", "ms4n-01-linkage-bars")
```

### 3.2 Trace conversion

Test names:

```python
def test_trace_points_are_frame_x_y_tuples()
def test_trace_conversion_preserves_order()
def test_trace_conversion_applies_start_frame_offset()
def test_trace_conversion_rejects_nan_and_infinite_coordinates()
def test_trace_summary_handles_empty_trace()
def test_trace_summary_handles_single_point_trace()
def test_trace_normalization_downsamples_over_500_points_deterministically()
def test_trace_downsampling_preserves_first_and_last_points()
```

Expected point format:

```python
((10, 120.0, 80.0), (11, 121.5, 80.5), (12, 122.0, 81.0))
```

### 3.3 Project layer bridge

Test names:

```python
def test_layer_data_bridge_adds_ms4n_without_removing_generated_path_data()
def test_serializer_round_trip_preserves_ms4n_layer_payload()
def test_serializer_drops_qt_runtime_object_but_keeps_ms4n_json_payload()
def test_bridge_extracts_empty_payload_when_ms4n_key_missing()
```

Sample payload:

```python
layer_data = {
    "generated_path_data": {"points": [[100.0, 100.0], [120.0, 120.0]], "is_closed": False},
    "ms4n": {
        "schema_version": "ms4n.layer.v1",
        "episode_ids": ["ep_001"],
        "episodes": [{"schema_version": "ms4n.episode.v1", "episode_id": "ep_001"}],
    },
}
```

### 3.4 Export files

JSONL tests:

```python
def test_jsonl_writer_writes_one_episode_per_line()
def test_jsonl_writer_uses_stable_key_order()
def test_jsonl_writer_round_trips_with_json_loads()
def test_jsonl_writer_rejects_non_json_safe_payload()
```

CSV tests:

```python
def test_coding_csv_writes_expected_header_order()
def test_coding_csv_flattens_trace_summary_not_raw_points_by_default()
def test_coding_csv_includes_facilitator_move_summary()
def test_coding_csv_escapes_commas_and_newlines()
```

Expected coding CSV header:

```text
episode_id,session_id,mechanism_id,mechanism_type,part_name,status,symptom,suspected_causes,repair_action,change_count,repair_count,trace_point_count,before_bbox,after_bbox,motion_delta_summary,learner_explanation_present,facilitator_moves,artifact_ref_count
```

### 3.5 UI smoke

Test names:

```python
def test_lab_tab_instantiates_offscreen(qapp)
def test_lab_tab_contains_required_panels(qapp)
def test_presenter_loads_manifest_into_kit_panel(monkeypatch)
def test_presenter_saves_explanation_to_episode_draft(monkeypatch)
def test_export_button_calls_export_service_with_selected_directory(monkeypatch)
```

Rules:

- Do not show real windows.
- Patch QFileDialog.
- Patch services; do not write real files except under `tmp_path`.

## 4. Fixtures and golden files

Add:

```text
tests/fixtures/ms4n/
  episode_repaired.sample.json
  episode_unresolved.sample.json
  episodes.sample.jsonl
  coding_sheet.sample.csv
  autopsy_sheet.sample.md
  kit_manifest.sample.json
  project_with_ms4n_layer_payload.automataii.json
```

Golden rules:

- Freeze timestamps in fixtures.
- Normalize float formatting to stable precision.
- No raw names/emails/video faces in fixtures.
- Use fake ids only: `session_fake_001`, `p_hash_fake`, `ep_001`.

## 5. Regression commands

### During implementation slices

```bash
uv run pytest tests/domain/ms4n -v
uv run pytest tests/application/ms4n -v
uv run pytest tests/infrastructure/ms4n -v
```

### Bridge regression

```bash
uv run pytest tests/test_project_serializer_assets.py tests/test_ms4n_project_layer_data_bridge.py -v
uv run pytest tests/ui/tabs/test_path_trace_manager.py -v
```

### UI smoke

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/presentation/lab tests/ui/tabs/test_lab_tab.py -v
```

### Full pre-pilot quality gate

```bash
uv run pytest
uv run ruff check src/ tests/
uv run mypy src/automataii
```

## 6. Acceptance gates

### Gate A — Schema stable

Passes when:

- domain tests pass;
- JSON serialization works;
- facilitator move and unresolved episode are represented;
- no PyQt import appears under `src/automataii/domain/ms4n`.

### Gate B — Existing project behavior safe

Passes when:

- `tests/test_project_serializer_assets.py` still passes;
- MS4N layer bridge round-trip passes;
- no serializer version bump is required.

### Gate C — Export analyzable

Passes when:

- bundle export integration test writes required files;
- JSONL can be parsed line by line;
- CSV can be opened as rows with stable headers;
- autopsy sheet includes before/change/after/explain/facilitator fields.

### Gate D — UI usable enough for internal pilot

Passes when:

- Lab tab opens offscreen;
- presenter can create one episode with mocked snapshot input;
- export action writes bundle under `tmp_path` in tests.

### Gate E — Pilot readiness

Passes when:

- all targeted tests pass;
- full test suite or documented subset passes;
- ruff and mypy pass or known unrelated failures are documented;
- one dry-run bundle is generated with fake data.

## 7. Current planning verification targets

Because this document is a pre-implementation plan, current validation checks should verify:

- `plan/09`, `plan/10`, `plan/11`, tracked PRD mirror `plan/12`, and tracked test-spec mirror `plan/13` exist.
- PRD and test-spec exist under `.omx/plans/`.
- Documents include the critic-required anchors:
  - P0 Definition of Done;
  - file-by-file architecture plan;
  - JSON-safe schema freeze;
  - trace capture contract;
  - one-change/one-repair rule;
  - tests tied to files;
  - 4-week task budget.
- Existing bridge assumptions hold via current regression tests.

## 8. Code-review regression tests added to plan

The code-review pass required these policies to be test-locked before coding proceeds:

- `test_trace_conversion_rejects_nan_and_infinite_coordinates`
- `test_trace_normalization_downsamples_over_500_points_deterministically`
- `test_trace_downsampling_preserves_first_and_last_points`
- `test_repaired_episode_rejects_more_than_one_primary_change`
- `test_repaired_episode_rejects_more_than_one_primary_repair`
- `test_multi_change_episode_requires_constraint_violation_note_and_unresolved_status`
- `test_bridge_rejects_non_finite_or_qt_derived_null_payloads`
- `test_saved_project_json_contains_no_nan_infinity_or_qt_derived_nulls`
- `test_snapshot_adapter_uses_public_snapshot_source_contract`
- `test_p0_export_contract_excludes_html_svg_pdf_without_promoted_tests`
