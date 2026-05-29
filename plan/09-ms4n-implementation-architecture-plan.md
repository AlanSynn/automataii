# MS4N Implementation Architecture Plan: Jams as Explanations

작성일: 2026-05-14
상태: **코딩 착수 전 architecture gate**
연결 문서: `plan/08-ms4n-jams-as-explanations-execution-plan.md`, `.omx/context/ms4n-implementation-plan-20260514T035600Z.md`

## 1. 핵심 결정

### 1.0 Naming decision

The user-facing top-level surface is **Lab**, not an MS4N-prefixed Lab label. MS4N remains the research/backend bounded context (`domain/application/infrastructure/ms4n`), while the presentation surface uses `presentation/qt/tabs/lab`, `LabTab`, `self.lab_tab`, and `tab_lab`.


MS4N P0는 기존 Automataii를 “정답 메커니즘 생성기”로 확장하지 않는다. P0의 구현 목표는 다음 research unit을 안정적으로 캡처하고 내보내는 것이다.

> **한 번의 기계적 변경 / 고장 / 수리 → 한 번의 motion consequence → 한 번의 설명 episode**

따라서 구현은 다음으로 좁힌다.

1. **별도 Lab surface**를 추가한다.
2. 기존 `MechanismDesignTab`은 simulation/authoring engine으로 유지한다.
3. `MechanismDesignTab`에는 P0에서 **읽기 전용 snapshot/trace seam**만 둔다.
4. 연구 데이터는 `domain/application/infrastructure/ms4n` 신규 slice에 둔다.
5. P0 저장은 `episodes.jsonl`, `coding_sheet.csv`, `facilitator_moves.csv`, trace JSON, `manifest.json`, 그리고 `autopsy_sheet.md` export 중심이다. HTML/SVG/PDF poster export는 P0.5/P1로 미룬다.
6. `.automataii` project persistence는 P0에서는 `MechanismData.layer_data["ms4n"]` bridge만 사용하고, P1에서 root `ProjectState.ms4n_sessions`로 승격한다.

## 2. 현재 코드 구조에서 근거가 되는 touchpoint

| 역할 | 현재 파일 | 구현 의미 |
|---|---|---|
| Domain mechanism state | `src/automataii/domain/mechanisms/core/state.py` | `MechanismState`는 pure Python dataclass이므로 snapshot 모델의 reference pattern으로 사용한다. |
| Mechanism project persistence | `src/automataii/application/project/models.py` | `MechanismData.layer_data`가 이미 JSON-safe extension bridge 역할을 한다. |
| Serializer | `src/automataii/application/project/serializer.py` | `CURRENT_VERSION = "2.0"`; P0에서는 migration을 피한다. |
| Path trace | `src/automataii/presentation/qt/tabs/mechanism_design/path_trace_manager.py` | `get_trace_points(mechanism_id) -> list[QPointF]`가 있으므로 Qt point를 tuple로 변환하는 adapter가 필요하다. |
| Main tab registration | `src/automataii/presentation/qt/main_window.py` | `_init_ui()`에서 Lab tab을 추가한다. |
| Blueprint/export precedent | `src/automataii/application/blueprint/composer.py` | export는 application service + infrastructure writer 구조를 따른다. |
| Telemetry precedent | `src/automataii/infrastructure/telemetry/telemetry.py` | episode/export event에 span을 붙인다. |
| Kit assets | `kit/bar-board.svg`, `kit/ms4n-*.svg` | manifest 기반으로 P0 module을 software에서 참조한다. |

## 3. Architecture topology

```text
Domain
  automataii.domain.ms4n
    episodes.py            # JSON-safe research episode dataclasses
    repair_taxonomy.py     # symptom/cause/repair/facilitator vocabularies
    trace.py               # TracePoint, TraceSummary, before/after metrics
    kit_assets.py          # KitAsset, KitManifest contracts

Application
  automataii.application.ms4n
    episode_service.py     # create/update/validate breakdown-repair episodes
    trace_snapshot.py      # Qt-free trace normalization contracts
    export_service.py      # StudyBundle, JSONL/CSV/autopsy export orchestration
    layer_data_bridge.py   # P0 bridge to MechanismData.layer_data["ms4n"]
    kit_catalog_service.py # manifest query API for UI

Infrastructure
  automataii.infrastructure.ms4n
    jsonl_writer.py        # deterministic append/write JSONL
    coding_csv_writer.py   # deterministic coding sheet CSV
    kit_manifest_loader.py # validate kit/ms4n-kit-manifest.json
    bundle_writer.py       # write study bundle directory

Presentation
  automataii.presentation.qt.tabs.lab
    tab.py                 # separate QWidget surface
    presenter.py           # talks to application.ms4n services
    view_protocol.py       # view contract
    widgets/
      kit_catalog_panel.py
      episode_builder_panel.py
      trace_duel_panel.py
      motion_autopsy_panel.py
      facilitator_log_panel.py

Thin read-only seam
  automataii.presentation.qt.tabs.mechanism_design.ms4n_snapshot_adapter.py
    # Consumes a public read-only snapshot source and converts PathTraceManager QPointF into JSON-safe data.
```

### Why package name `ms4n`, not `jams`

P0 research spine is “Jams as Explanations,” but the toolkit includes kit manifest, trace duel, worksheets, and future classroom modules. Therefore top-level bounded context should be `ms4n`; jam/breakdown concepts live inside `episodes.py` and `repair_taxonomy.py`.

## 4. P0/P1/P2 scope boundary

### P0 — internal pilot MVP

Build only what makes the CHI research data structure real.

- 4-bar/bar-board focused workflow.
- Manual session setup and mechanism selection.
- Before snapshot capture.
- One predicted/observed/breakdown trace capture.
- One symptom/cause tag.
- One repair action.
- One after snapshot capture.
- Learner explanation prompt.
- Facilitator move tag.
- JSONL export.
- Coding CSV export.
- Minimal printable motion autopsy sheet.
- Kit manifest that includes `kit/bar-board.svg` and existing `kit/ms4n-*.svg` assets.

### P1 — study-ready persistence and artifact bundle

- `ProjectState.ms4n_sessions` or `ProjectState.research_sessions` first-class schema.
- Serializer version bump `2.0 -> 2.1` with migration from `layer_data["ms4n"]`.
- Project-wide MS4N session browser.
- Trace/photo/video asset bundling.
- More polished autopsy sheet layout.
- More kit modules beyond the P0 jam/trace/autopsy set.

### P2 — wow demo / CHI extension

- Camera/fiducial-assisted physical observation.
- Automatic jam classification.
- Explanation clustering or instructor dashboard.
- Cross-mechanism classroom wall / gallery.
- AI critique of learner explanation, only after human coding protocol is stable.

## 5. Data model freeze for P0

All P0 data must be JSON-safe and must not contain Qt objects, callables, absolute internal runtime paths, or raw participant identifiers.

### 5.1 Required episode shape

```python
BreakdownRepairEpisode:
  schema_version: str = "ms4n.episode.v1"
  episode_id: str
  session_id: str
  participant_hash: str | None
  mechanism_id: str
  mechanism_type: str
  part_name: str
  kit_asset_ids: tuple[str, ...]
  before_snapshot: MechanismStateSnapshot
  prediction: LearnerPrediction | None
  breakdown: BreakdownEvent | None
  change: MechanicalChange | None
  repair_action: RepairAction | None
  after_snapshot: MechanismStateSnapshot | None
  motion_consequence: MotionConsequence | None
  learner_explanation: LearnerExplanation | None
  facilitator_moves: tuple[FacilitatorMove, ...]
  artifact_refs: tuple[ArtifactRef, ...]
  status: Literal["open", "repaired", "abandoned", "unresolved"]
  change_count: int
  repair_count: int
  constraint_violation_note: str | None
  created_at: str
  completed_at: str | None
```

### 5.1.1 P0 one-change / one-repair enforcement

P0 completed episodes must preserve the core explanatory unit. Therefore `status="repaired"` is valid only when `change_count <= 1` and `repair_count <= 1`. If a real session contains more than one primary change or more than one repair before a new snapshot, `validate_for_p0()` must reject completion as `repaired`; the episode must stay `status="open"` or `status="unresolved"` and include `constraint_violation_note`. This keeps multi-change troubleshooting available as data without letting it count as a clean P0 episode.

### 5.2 Snapshot shape

```python
MechanismStateSnapshot:
  snapshot_id: str
  mechanism_id: str
  mechanism_type: str
  parameters: Mapping[str, JsonValue]
  key_points: Mapping[str, tuple[float, float]]
  trace_ref: TraceRef | None
  trace_summary: TraceSummary | None
  physical_observation_note: str | None
  coordinate_space: Literal["scene", "mechanism_local", "physical_note"]
```

### 5.3 Trace contract

```python
TracePoint = tuple[int, float, float]  # frame_index, x, y
TraceRef:
  trace_id: str
  source: Literal["simulated", "predicted", "physical_manual", "photo_ref", "video_ref"]
  coordinate_space: Literal["scene", "mechanism_local", "physical_note"]
  points: tuple[TracePoint, ...]
  sampling_rule: str
  max_points: int
```

Rules:

- `QPointF` is only allowed in presentation adapter input.
- application/domain sees only tuple/list primitives.
- Non-finite trace coordinates are **rejected**, never silently filtered or serialized. The validation boundary must fail before JSONL/CSV/project bridge export.
- P0 trace normalization has a hard `max_points=500`. Inputs over 500 points are deterministically downsampled to 500 points by stable index selection that preserves the first and last point, and stores `original_point_count`, `was_downsampled=True`, and `sampling_rule="uniform_downsample_to_500"`. Golden tests must lock this behavior.

### 5.4 Repair/facilitator taxonomy

P0 vocabularies should be intentionally small.

```text
symptom:
  jam, wobble, slip, weak_motion, collision, phase_lag, stuck_dead_zone, unexpected_trace

suspected_cause:
  friction, looseness, alignment, collision, tolerance, overconstraint, material_flex, wrong_pivot, wrong_link_length

repair_action:
  add_spacer, remove_spacer, tighten_joint, loosen_joint, move_pivot, shorten_link, lengthen_link, change_attachment, reroute_character_connection, remake_part

facilitator_move:
  ask_prediction, ask_what_changed, ask_compare_trace, point_to_part, point_to_motion, suggest_test, explain_mechanism, manage_safety, fabrication_help, no_intervention
```

Important: `facilitator_moves` is P0, not P1, because it controls a major CHI confound: whether explanations came from the scaffold or from instructor hints.

## 6. Project persistence decision

### P0 bridge

Store optional project-local MS4N state at:

```python
MechanismData.layer_data["ms4n"] = {
  "schema_version": "ms4n.layer.v1",
  "episode_ids": ["episode_..."],
  "episodes": [...],
  "last_export_ref": "relative/path/or/id"
}
```

Why this is acceptable:

- `MechanismData._json_safe()` already recursively converts mappings/sequences and drops Qt/runtime-heavy objects.
- Existing serializer version stays `2.0`.
- Pilot data can be exported even if project schema is not yet migrated.

Risk:

- Cross-mechanism session search is weak.
- Type validation is mostly in MS4N services/tests, not project model.

Mitigation:

- Use the same episode schema as future P1 root storage.
- Do not make `layer_data` the only export source; maintain explicit study bundle export.

### P1 migration

Add root state:

```python
ProjectState.ms4n_sessions: Mapping[str, MS4NSession]
```

Then add `V2ToV2_1MS4NMigrator`:

```text
mechanisms[*].layer_data["ms4n"].episodes -> project.ms4n_sessions[*].episodes
```

## 7. UI placement and flow

### Decision: separate `Lab` tab + explicit public read-only bridge

The preferred surface is a new top-level tab because MS4N is a pedagogy/research workflow, not just a mechanism parameter editor. The bridge must not poke private `MechanismDesignTab` state directly; the first implementation slice must add a public read-only method/protocol such as `get_ms4n_snapshot_source(mechanism_id) -> Mapping[str, JsonValue]`, and the adapter consumes only that protocol plus copied trace points.

Add to `src/automataii/presentation/qt/main_window.py` near current tab registration:

```python
self.lab_tab = LabTab(self)
self.lab_tab.setObjectName("tab_lab")
lab_title = "6. Lab" if self.experiment_mode else "Lab"
self.tab_widget.addTab(self.lab_tab, lab_title)
```

Experiment-mode numbering must be revisited because Foundry is currently tab 5 and Options is hidden in experiment mode.

### P0 panels

1. **Kit Catalog Panel**
   - loads `kit/ms4n-kit-manifest.json`
   - shows P0 assets and bar-board dependency
2. **Episode Builder Panel**
   - select mechanism/part
   - capture before
   - record one change or breakdown
   - capture after
3. **Trace Duel Panel**
   - predicted vs simulated or before vs after trace
   - P0 can be side-by-side summary + simple preview, not rich overlay
4. **Motion Autopsy Panel**
   - event rows: frame/symptom/cause/repair/explanation
   - export sheet
5. **Facilitator Log Panel**
   - tag facilitator moves
   - preserve “no intervention” cases

## 8. Kit integration

Add:

```text
kit/ms4n-kit-manifest.json
```

Manifest schema:

```json
{
  "schema_version": "ms4n.kit.v1",
  "assets": [
    {
      "id": "bar-board",
      "filename": "kit/bar-board.svg",
      "module_name_ko": "바 보드 베이스",
      "module_name_en": "Bar Board Base",
      "mechanism_types": ["four_bar", "linkage"],
      "change_types": ["pivot_position", "link_length", "spacing"],
      "evidence_outputs": ["trace_before", "trace_after", "learner_explanation"],
      "pilot_priority": "P0"
    }
  ]
}
```

P0 kit modules:

- `bar-board.svg` as required base.
- `ms4n-00-bar-board-guide.svg` as alignment/pivot guide.
- `ms4n-01-linkage-bars.svg` as linkage variation sheet.
- `ms4n-06-trace-prompt-cards.svg` as trace/prediction prompts.
- `ms4n-07-fabrication-checks.svg` as fabrication check/reflection sheet.
- Optional new `ms4n-08-jam-detective.svg` after software schema stabilizes.

## 9. Export contract

Study bundle directory:

```text
ms4n_study_bundle_<session_id>/
  README.md
  manifest.json
  research/
    episodes.jsonl
    coding_sheet.csv
    facilitator_moves.csv
  traces/
    <episode_id>_before.json
    <episode_id>_after.json
  autopsy/
    <episode_id>_sheet.md
  kit/
    selected_assets.json
    bar-board.svg              # copied if allowed by local workflow
```

P0 must not require HTML, SVG, or PDF poster generation. HTML/SVG/PDF autopsy posters belong to P0.5/P1 unless a later test spec explicitly promotes them.

## 10. Telemetry and logging

Use existing telemetry style, but do not log raw learner text to normal app logs by default.

Event names:

- `ms4n.session.created`
- `ms4n.episode.started`
- `ms4n.trace.captured`
- `ms4n.breakdown.tagged`
- `ms4n.repair.recorded`
- `ms4n.explanation.saved`
- `ms4n.bundle.exported`

Privacy rule: study exports may contain explanations; application telemetry should contain counts/status/durations only.

## 11. Rejected alternatives

| Alternative | Rejected because |
|---|---|
| Put all P0 widgets inside `MechanismDesignTab` | Fast but worsens an already complex tab and mixes pedagogy/research workflow with authoring/simulation. |
| Start with `ProjectState.ms4n_sessions` migration | Architecturally cleaner, but increases P0 risk; bridge first, migrate after pilot schema stabilizes. |
| Camera/fiducial physical tracking in P0 | Too much implementation and study risk; manual trace/photo ref is enough for first evidence. |
| AI explanation scoring in P0 | Undermines human coding validity and can distract from mechanism-first contribution. |
| Full bundle/PDF/poster generator in P0 | Nice demo, but JSONL/CSV/autopsy markdown proves the research pipeline first. |

## 12. Architecture acceptance criteria

P0 architecture is ready for implementation only when all are true:

- `domain/ms4n` imports no PyQt6, filesystem writer, or presentation module.
- `application/ms4n` owns episode validation and export orchestration.
- `infrastructure/ms4n` owns file reading/writing only.
- `presentation/qt/tabs/lab` owns widgets only.
- `mechanism_design` changes are limited to a read-only snapshot/trace adapter or public accessor.
- `QPointF -> TracePoint` conversion is tested with non-finite rejection and deterministic `max_points=500` downsampling.
- `layer_data["ms4n"]` round-trip is tested, and `application/ms4n/layer_data_bridge.py` is the hard validation boundary before permissive `MechanismData._json_safe()` serialization.
- JSONL/CSV output is deterministic and golden-testable.
- P0 non-goals remain out of scope.

## 13. Code-review resolution addendum (2026-05-14)

The first code-review pass returned `REQUEST CHANGES`. The implementation contract is now tightened as follows:

1. **Trace policy is fixed.** Non-finite coordinates are rejected. Over-500-point traces are deterministically downsampled to exactly 500 points, preserving first and last points and recording `original_point_count`, `was_downsampled`, and `sampling_rule`.
2. **One-change/one-repair is enforceable.** A `repaired` P0 episode cannot contain more than one primary mechanical change or repair. Multi-change cases are still data, but must remain `open`/`unresolved` with `constraint_violation_note`.
3. **Bridge validation is explicit.** `application/ms4n/layer_data_bridge.py` must validate MS4N payloads before `MechanismData._json_safe()` serialization and before export writers.
4. **Snapshot seam is public and read-only.** `ms4n_snapshot_adapter.py` must consume a public `get_ms4n_snapshot_source(...)`-style contract, not private `MechanismDesignTab` fields.
5. **P0 export is normalized.** P0 exports JSONL, coding CSV, facilitator CSV, trace JSON, manifest JSON, and markdown autopsy sheets only. HTML/SVG/PDF export is P0.5/P1.
6. **PRD/test-spec durability is fixed.** `.omx/plans` handoff artifacts are mirrored into tracked `plan/12` and `plan/13` documents.
