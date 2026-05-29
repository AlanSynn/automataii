<!-- Mirrored from .omx/plans for git-visible review durability. Keep in sync with the OMX test-spec artifact. -->

# Test Spec: MS4N Jams-as-Explanations P0

Date: 2026-05-14
Linked PRD: `.omx/plans/prd-ms4n-jams-implementation-20260514.md`

## 1. Required test files

```text
tests/domain/ms4n/test_episode_models.py
tests/domain/ms4n/test_trace_metrics.py
tests/domain/ms4n/test_repair_taxonomy.py
tests/infrastructure/ms4n/test_kit_manifest_loader.py
tests/application/ms4n/test_kit_catalog_service.py
tests/application/ms4n/test_episode_service.py
tests/application/ms4n/test_layer_data_bridge.py
tests/test_ms4n_project_layer_data_bridge.py
tests/application/ms4n/test_trace_snapshot.py
tests/infrastructure/ms4n/test_jsonl_writer.py
tests/infrastructure/ms4n/test_coding_csv_writer.py
tests/infrastructure/ms4n/test_bundle_writer.py
tests/application/ms4n/test_autopsy_sheet_service.py
tests/application/ms4n/test_export_service.py
tests/presentation/lab/test_lab_presenter.py
tests/ui/tabs/test_lab_tab.py
```

## 2. Required fixtures

```text
tests/fixtures/ms4n/episode_repaired.sample.json
tests/fixtures/ms4n/episode_unresolved.sample.json
tests/fixtures/ms4n/episodes.sample.jsonl
tests/fixtures/ms4n/coding_sheet.sample.csv
tests/fixtures/ms4n/autopsy_sheet.sample.md
tests/fixtures/ms4n/kit_manifest.sample.json
tests/fixtures/ms4n/project_with_ms4n_layer_payload.automataii.json
```

## 3. Critical assertions

### Schema

- Episode `to_dict` output is JSON serializable.
- Repaired episode requires before snapshot, repair action, after snapshot, and explanation or explicit absence note.
- Unresolved/abandoned episode remains exportable.
- Facilitator moves are captured.
- Change count and repair count are represented and enforced: repaired P0 episodes reject more than one primary change or repair.

### Trace

- Presentation adapter converts QPointF-like input to primitive `(frame_index, x, y)` tuples before application/domain boundaries.
- Order and start-frame offset are preserved.
- Non-finite coordinates are rejected; tests must assert failure, not filtering.
- Over-500-point traces are downsampled deterministically to 500 points, preserving first/last and storing metadata.
- Empty and one-point traces are valid.

### Bridge

- `MechanismData.layer_data["ms4n"]` round-trips through `ProjectSerializer`.
- Existing layer data, including `generated_path_data`, is preserved.
- Runtime-heavy/Qt objects are not exported.
- Raw saved JSON contains no `NaN`, `Infinity`, Qt-object-derived `null`, or missing required MS4N fields.

### Export

- JSONL writes one episode per line.
- CSV header order is stable.
- Autopsy sheet includes before/change/after/explain/facilitator fields.
- P0 export contract is markdown-only for autopsy sheets; HTML/SVG/PDF are P0.5/P1 unless later promoted with tests.
- Bundle export writes all required files under `tmp_path`.

### UI

- Lab tab instantiates with `QT_QPA_PLATFORM=offscreen`.
- Required panels exist.
- Presenter can load manifest and save explanation via mocked services.
- MS4N snapshot adapter consumes a public read-only snapshot source contract rather than private Mechanism Design state.
- Export action calls export service; QFileDialog is monkeypatched.

## 4. Regression commands

During development:

```bash
uv run pytest tests/domain/ms4n -v
uv run pytest tests/application/ms4n -v
uv run pytest tests/infrastructure/ms4n -v
```

Bridge regressions:

```bash
uv run pytest tests/test_project_serializer_assets.py tests/test_ms4n_project_layer_data_bridge.py -v
uv run pytest tests/ui/tabs/test_path_trace_manager.py -v
```

UI smoke:

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/presentation/lab tests/ui/tabs/test_lab_tab.py -v
```

Pre-pilot gate:

```bash
uv run pytest
uv run ruff check src/ tests/
uv run mypy src/automataii
```

## 5. Current planning-only verification

For this planning pass, fresh evidence is:

- plan docs exist and include the critic-required anchors;
- current serializer/path trace bridge assumptions are verified by existing targeted tests;
- no application code was changed in this pass.
