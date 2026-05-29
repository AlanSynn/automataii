# MS4N Execution Plan: Jams as Explanations

## 1. Goal

Turn MS4N from a broad automata learning toolkit into a CHI-grade research artifact centered on this claim:

> Physical breakdowns in novice automata making can be designed as inspectable repair-reasoning episodes rather than treated as mere fabrication errors.

## 2. P0 scope: 3 modules only

P0 must be narrow. Build only the minimum set that creates CHI-quality evidence.

### Module 1 — Jam Detective Box

Physical parts:
- tight washer
- loose washer/fastener
- spacer stack
- friction insert
- collision tab
- flexible link
- stiff link
- labeled symptom cards

Software:
- breakdown tag selector
- symptom note
- repair hypothesis prompt
- one repair action selector
- before/after trace reference

Evidence:
- breakdown tag
- physical photo/video reference
- repair action
- after-state motion consequence
- learner explanation

### Module 2 — Trace Duel

Physical parts:
- trace card
- pen hole/coupler marker
- before/after trace slots

Software:
- predicted trace capture
- digital trace capture
- physical observation note
- before/after overlay

Evidence:
- prediction
- actual/simulated trace
- mismatch category
- explanation revision

### Module 3 — Motion Autopsy Table

Physical/display artifact:
- A3/A2 worksheet/poster template
- slots for before photo, jam symptom, repair, after trace, explanation

Software:
- printable autopsy sheet export
- `episodes.jsonl` and `coding_sheet.csv`
- facilitator intervention log

Evidence:
- complete breakdown-repair episode record
- classroom display
- analysis-ready export

## 3. Software P0 implementation spec

### 3.1 Data model

Add MS4N research data as a clean application/domain slice.

```python
MechanismChangeEpisode:
  episode_id: str
  session_id: str
  mechanism_id: str
  kit_module_ids: list[str]
  before_state: MechanismStateSnapshot
  prediction: LearnerPrediction | None
  change: MechanicalChange | None
  breakdown: BreakdownEvent | None
  repair_hypothesis: LearnerExplanation | None
  repair_action: RepairAction | None
  after_state: MechanismStateSnapshot | None
  motion_consequence: MotionConsequence | None
  learner_explanation: LearnerExplanation | None
  facilitator_move: FacilitatorMove | None
  artifact_refs: ArtifactRefs
```

```python
BreakdownEvent:
  symptom: Literal['jam', 'wobble', 'slip', 'weak_motion', 'collision', 'phase_lag', 'stuck_dead_zone']
  suspected_causes: list[Literal['friction', 'looseness', 'alignment', 'collision', 'tolerance', 'overconstraint', 'material_flex']]
  evidence_ref: str | None
```

```python
RepairAction:
  action_type: Literal['add_spacer', 'remove_spacer', 'tighten_joint', 'loosen_joint', 'move_pivot', 'shorten_link', 'lengthen_link', 'change_attachment', 'reroute_character_connection']
  before_value: str | float | None
  after_value: str | float | None
  rationale_text: str
```

### 3.2 Suggested file paths

P0:

```text
src/automataii/domain/ms4n/episodes.py
src/automataii/domain/ms4n/repair_taxonomy.py
src/automataii/application/ms4n/episode_service.py
src/automataii/application/ms4n/export_service.py
src/automataii/infrastructure/ms4n/jsonl_writer.py
src/automataii/presentation/qt/tabs/lab/
```

If schema migration feels too heavy, bridge through existing mechanism `layer_data` for internal pilot only, then migrate to first-class `ResearchSession` before formal study.

### 3.3 UI flow

Lab P0 panels:

1. **Episode Setup**
   - select mechanism
   - select kit module
   - capture before state

2. **Prediction / Breakdown**
   - “What do you expect?”
   - or “What symptom happened?”

3. **One Repair**
   - select one repair action
   - capture after state

4. **Trace Duel**
   - show before/after or predicted/observed trace
   - tag mismatch

5. **Explanation**
   - What changed?
   - How did motion change?
   - Why did the repair matter?

6. **Export**
   - autopsy sheet
   - JSONL
   - coding CSV

## 4. Kit fabrication plan

### Existing assets reused

- `kit/bar-board.svg`
- `kit/ms4n-00-bar-board-guide.svg`
- `kit/ms4n-01-linkage-bars.svg`
- `kit/ms4n-06-trace-prompt-cards.svg`
- `kit/ms4n-07-fabrication-checks.svg`

### New or revised sheet needs

1. **Jam Detective Tokens**
   - symptom cards
   - cause tags
   - repair tags

2. **Tolerance Test Strips**
   - same linkage with tight/loose hole variants
   - spacer height variants

3. **Motion Autopsy Poster**
   - before/change/after/explain sections
   - QR/file ID slot

These can be added either as revisions to `ms4n-06` and `ms4n-07` or as `ms4n-08-jam-detective.svg`.

## 5. Pilot protocol

### Internal mini-pilot first

Purpose: verify that usable episodes happen, not prove learning.

Session length target: 45–60 minutes.

Tasks:
1. Build a simple linkage on bar-board.
2. Predict or record initial trace.
3. Introduce one controlled breakdown or encounter natural breakdown.
4. Diagnose symptom.
5. Apply one repair.
6. Compare trace/motion.
7. Explain repair.

Gate:
- at least 3 usable episodes per session
- at least 1 breakdown-repair episode
- facilitator log is analyzable
- export works

### Main study options

Option A — rich qualitative workshop:
- best for early CHI artifact/design knowledge paper
- collect dense video/log/artifact data
- avoid causal learning claims

Option B — comparison study:
- baseline kit vs MS4N repair scaffold
- stronger if claiming scaffold changes explanation behavior
- more operational burden

Recommended: start with Option A, then add lightweight comparison only if pilot data is strong.

## 6. Coding scheme

### Episode types

- prediction episode
- one-change episode
- breakdown episode
- repair hypothesis episode
- repair action episode
- explanation revision episode
- facilitator intervention episode
- non-episode / unproductive manipulation

### Breakdown tags

- friction
- looseness
- alignment
- collision
- tolerance
- overconstraint
- material flex
- unclear/multiple

### Explanation quality levels

1. descriptive only: “it moved more”
2. parameter-linked: “the pivot moved up”
3. causal: “moving the pivot shortened the lever path, so the arm moved less”
4. evidence-backed: references trace/photo/physical test
5. transfer-ready: predicts another edit or repair

## 7. Figure plan

### Figure 1 — System overview

Physical kit + Lab + Motion Autopsy export.

### Figure 2 — Breakdown-repair episode

Before → jam symptom → hypothesis → one repair → trace change → explanation.

### Figure 3 — Trace Duel

Prediction trace vs observed trace vs repaired trace.

### Figure 4 — Repair taxonomy

Breakdown cause × repair action × motion consequence.

### Figure 5 — Classroom wall

Motion autopsy sheets as data + teaching artifacts.

## 8. 4-week sprint

### Week 1 — Research spine freeze

- Freeze title and thesis around Jams as Explanations.
- Define P0 tags and prompts.
- Select 2 mechanism tasks only: linkage pivot and linkage joint tolerance.

### Week 2 — Episode capture MVP

- Create episode schema.
- Implement JSONL writer or mock export.
- Create printable Motion Autopsy template.
- Prepare 3–4 Jam Detective cards.

### Week 3 — Kit rehearsal

- Build physical P0 kit.
- Test whether intended breakdowns actually occur.
- Time assembly.
- Write facilitator script.

### Week 4 — Internal mini-pilot

- Run internal sessions.
- Collect sample episodes.
- Code a small subset.
- Decide whether CHI story is viable.

## 9. Acceptance gate before larger study

Proceed only if:

- [ ] physical breakdowns happen but do not derail the session
- [ ] learners can articulate at least tentative repair hypotheses
- [ ] the one-repair constraint is understandable
- [ ] trace/photo/artifact evidence can be linked to episode IDs
- [ ] facilitators can log interventions without disrupting activity
- [ ] the paper can avoid unsupported learning-gain claims

## 10. CHI contribution statement draft

This paper contributes:

1. **MS4N, a mechanism-first physical-digital scaffold** that structures novice automata making around one-change and breakdown-repair episodes.
2. **The breakdown-repair episode as an analytic unit** for studying how learners predict, observe, explain, and repair motion in physical automata.
3. **Empirical insights and design considerations** for treating physical mismatch, jam, friction, and tolerance not as errors to hide, but as productive materials for teacher-mediated causal explanation.

## 11. What to stop doing

Stop trying to make all 10 modules equally central.

For CHI paper 1, do not foreground:
- gear mood dial
- full character puppet authoring
- AI explanation scoring
- real-time camera twin
- classroom dashboard
- broad creativity improvement

These can appear as future work or demo extensions, but the paper must be about breakdown/repair reasoning.

---

## 12. Post-review required changes before CHI-scale study

2차 reviewer가 `REQUEST CHANGES/WATCH`를 준 이유는 실행 방향이 틀려서가 아니라, submission-grade evidence protocol이 아직 약했기 때문이다. 아래 항목은 P0 이후 study 전에 반드시 반영한다.

### 12.1 Participant and session planning placeholders

Do not invent final participant counts. Use the following as design gates.

- Internal mini-pilot: enough sessions to test whether the protocol produces usable episodes.
- Pilot study: enough novice participants/teams to test codebook stability and data capture reliability.
- CHI-scale empirical claim: proceed only if the corpus contains repeated patterns, negative cases, and triangulated evidence.

Report actual numbers only after sessions are complete.

### 12.2 Data sufficiency rule

A dataset is considered paper-ready only if it contains:

- multiple mechanism variables, but no more than two P0 variables for scope control;
- successful and failed repair attempts;
- at least one case where physical mismatch becomes explanation;
- at least one case where mismatch remains unresolved;
- facilitator-mediated and learner-led explanations distinguished;
- enough repeated patterns to support cross-case claims.

### 12.3 MechanismStateSnapshot rule

`MechanismStateSnapshot` must be pure Python and JSON-safe. It must not store Qt objects such as `QPointF`.

Suggested shape:

```python
MechanismStateSnapshot:
  mechanism_type: str
  parameters: dict[str, float | str | bool]
  key_points: dict[str, tuple[float, float]]
  trace_ref: str | None
  artifact_ref: str | None
  timestamp: str
```

Presentation-layer trace points must be converted to plain tuples before export.

### 12.4 Physical observed trace rule

For P0, physical observed traces may be manual or photo/video-referenced. But every physical observation must have:

- observation id
- source type: manual_note | photo | video | traced_overlay | sensor
- file/reference path if available
- who recorded it
- relation to episode id
- confidence or limitation note

### 12.5 Facilitator script constraint

Facilitators should ask, not solve.

Allowed default prompts:
- “무슨 증상이 보이나요?”
- “어떤 원인을 의심하나요?”
- “한 가지만 고친다면 무엇을 바꾸겠나요?”
- “고친 뒤 motion이 어떻게 달라졌나요?”
- “trace/photo에서 어떤 증거를 봤나요?”

Restricted moves:
- 직접 정답 제공
- 학생 대신 repair 수행
- 여러 변경을 한 번에 지시
- trace 없이 결과를 판정

If restricted moves occur, log them and treat the episode as facilitator-led.

### 12.6 Prior-work action item

Before writing the paper introduction/related work, create a literature matrix for:

- constructionist/tinkerable learning
- tangible STEM kits
- productive failure / debugging-as-learning
- repair/craft pedagogy
- fabrication-aware CAD
- simulation-physical mismatch
- creative automata/mechanism authoring

The paper must explain why “breakdown-repair episode” is not just productive failure renamed.
