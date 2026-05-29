<!-- Mirrored from .omx/plans for git-visible review durability. Keep in sync with the OMX PRD artifact. -->

# PRD: MS4N Jams-as-Explanations Implementation

Date: 2026-05-14
Autopilot phase: ralplan -> ralph
Status: Approved for implementation planning; not yet approved for broad feature coding beyond P0.

## 1. Product goal

Naming constraint: the user-facing top-level tab is **Lab**. MS4N remains the research/project name and backend bounded context, but UI labels/classes/packages should not use an MS4N-prefixed Lab label.


Build the minimum Automataii software support needed for MS4N's CHI-facing P0 claim:

> A physical breakdown in novice automata making can be captured as an inspectable repair-reasoning episode: mechanism variable, motion consequence, repair action, learner explanation, and facilitator move.

## 2. Users

- Primary: researcher/facilitator running an internal pilot.
- Secondary: teacher reviewing student explanations.
- Secondary: novice learner responding to prompts and comparing motion changes.

## 3. P0 scope

P0 must support one bar-board / 4-bar-centered internal pilot.

### Required modules

1. **Jam Detective Box**
   - symptom/cause/repair tags;
   - before/after state references;
   - explanation prompt.
2. **Trace Duel**
   - predicted vs observed or before vs after trace summary;
   - manual physical observation note;
   - JSON-safe trace capture.
3. **Motion Autopsy Table**
   - tabular breakdown-repair record;
   - facilitator move log;
   - minimal printable/exportable sheet.

## 4. Functional requirements

### FR1 — MS4N bounded context

Add a new `automataii.domain.ms4n`, `automataii.application.ms4n`, and `automataii.infrastructure.ms4n` slice.

Acceptance:

- Domain imports no PyQt6, QWidget, QPainterPath, QPointF, QFileDialog, or file writer.
- Application services own episode validation and export orchestration.
- Infrastructure owns manifest loading and file writing.

### FR2 — Episode schema

Represent `BreakdownRepairEpisode` with:

- `schema_version`;
- session/episode ids;
- anonymized participant alias/hash;
- mechanism id/type/part;
- kit asset ids;
- before and after snapshots;
- prediction/breakdown/change/repair fields;
- motion consequence;
- learner explanation or explicit absence;
- facilitator moves;
- artifact refs;
- status including unresolved/abandoned;
- `change_count`, `repair_count`, and `constraint_violation_note`.

P0 enforcement: `status="repaired"` is valid only when `change_count <= 1` and `repair_count <= 1`. If either count exceeds one, the service must reject repaired completion and keep the episode `open` or `unresolved` with a required `constraint_violation_note`.

Acceptance:

- JSON-safe round trip is tested.
- Non-finite trace values are rejected before export/storage; no silent filtering is allowed.
- No raw names/emails are part of the model.

### FR3 — Kit manifest

Add `kit/ms4n-kit-manifest.json` referencing current kit assets, including `kit/bar-board.svg`.

Acceptance:

- Manifest loader validates schema version and file presence.
- Kit catalog service returns P0 assets to UI.

### FR4 — Trace snapshot seam

Add a read-only seam from Mechanism Design to MS4N.

Acceptance:

- `PathTraceManager.get_trace_points()` remains presentation-owned.
- `QPointF` converts to `TracePoint = tuple[int, float, float]` before application/domain use.
- Non-finite trace coordinates are rejected before export/storage.
- Traces over 500 points are deterministically downsampled to 500 while preserving first/last points and recording downsampling metadata.
- Adapter consumes a public read-only snapshot source contract and does not read private Mechanism Design state directly.
- Adapter does not mutate Mechanism Design state.

### FR5 — P0 persistence bridge

Use `MechanismData.layer_data["ms4n"]` as a P0 bridge only.

Acceptance:

- Existing `generated_path_data` and unrelated layer keys survive.
- `application/ms4n/layer_data_bridge.py` is the hard validation boundary before permissive project serialization.
- Raw saved JSON contains no `NaN`, `Infinity`, Qt-object-derived `null`, or dropped required fields.
- Existing project serializer version stays `2.0`.
- Bridge tests cover `.automataii` round-trip.

### FR6 — Study export

Write a study bundle with:

```text
research/episodes.jsonl
research/coding_sheet.csv
research/facilitator_moves.csv
autopsy/<episode_id>_sheet.md
traces/<episode_id>_before.json
traces/<episode_id>_after.json
manifest.json
```

Acceptance:

- Export can run without GUI file dialog.
- JSONL and CSV are deterministic.
- Empty/unresolved episodes are represented without claiming repair success.

### FR7 — Lab UI

Add a separate Lab tab with minimal panels:

- Kit Catalog;
- Episode Builder;
- Trace Duel;
- Motion Autopsy;
- Facilitator Log.

Acceptance:

- Tab instantiates offscreen.
- Presenter can build a fake/dummy episode with mocked services.
- Tab registration does not break existing tabs.

## 5. Non-goals

P0 does not include:

- automatic jam detection;
- camera/fiducial physical tracking;
- AI explanation scoring;
- classroom dashboard;
- ProjectState schema migration;
- polished PDF poster export;
- multi-mechanism authoring wizard;
- causal claims about learning gains.

## 6. Research requirements

The system must preserve negative and unresolved cases, not only success cases.

Required analysis fields:

- symptom;
- suspected cause;
- repair action;
- before/after trace summary;
- learner explanation;
- facilitator move;
- physical observation note;
- artifact references;
- status.

Allowed claims after P0 pilot:

- records;
- surfaces;
- structures;
- characterizes;
- supports qualitative analysis;
- reveals design considerations.

Disallowed without stronger evidence:

- improves learning;
- improves creativity;
- outperforms baseline;
- reduces failure.

## 7. Implementation references

Detailed implementation plan:

- `plan/09-ms4n-implementation-architecture-plan.md`
- `plan/10-ms4n-p0-implementation-task-breakdown.md`
- `plan/11-ms4n-implementation-test-plan.md`

## 8. Implementation readiness decision

Ready for P0 coding after this PRD only if the corresponding test spec is accepted and RED tests are written first.
