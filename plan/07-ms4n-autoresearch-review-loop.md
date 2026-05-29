# MS4N Autoresearch Review Loop: 여러 agent 루프 결과와 의사결정

## 1. Purpose

이 문서는 MS4N의 “더 신기하고 재밌는 CHI-grade 방향”을 찾기 위해 수행한 agent-based autoresearch loop를 정리한다. 목표는 단순히 아이디어를 많이 내는 것이 아니라, CHI reviewer가 받아들일 수 있는 **narrow, evidence-grounded research spine**을 선택하는 것이다.

## 2. Loop structure

### Loop 1 — Divergent ideation

Agents:
- Researcher: CHI-grade wild contribution 후보
- Designer: wow kit module 후보 10개
- Architect: 실제 Automataii 구조에서 가능한 software architecture
- Test engineer: evidence/study/coding plan
- Planner: 3-loop autoresearch and sprint plan

질문:
- 어떤 방향이 정말 신기한가?
- 어떤 방향이 paper contribution으로 살아남는가?
- 어떤 방향은 demo gimmick인가?
- 어떤 evidence가 없으면 reject인가?

### Loop 2 — Reviewer narrowing

Critic/CHI AC role이 냉정하게 평가했다.

핵심 판정:

> 기본 방향 그대로는 RR~RRX 위험. Strong full paper를 원하면 “mechanism-first scaffold”라는 넓은 주장보다, physical failure/mismatch를 causal reasoning episode로 전환하는 radical design stance로 좁혀야 한다.

### Loop 3 — Synthesis and execution planning

선택된 spine:

1. **Jams as Explanations / Failure-as-Data** — primary paper spine
2. **Mechanism Change Episode Method** — analytical method
3. **Prediction–Trace–Repair Board** — demo and evidence layer
4. **Counterfactual Automata** — core interaction technique
5. **Motion Lineage** — optional representation layer

## 3. Agent findings synthesis

### 3.1 Researcher synthesis

Top suggestions:
- Counterfactual Automata
- Misconception Atlas
- Productive Mechanical Friction
- Debateable Automata
- Motion Lineage

Strong insight:

> MS4N should not be framed as motion generation. It should be framed as embodied counterfactual reasoning and evidence-backed explanation.

Adopted into plan:
- prediction step before edit
- counterfactual variant comparison
- explanation stress-test as P1
- motion lineage as optional secondary representation

### 3.2 Designer synthesis

Top kit ideas:
- Path Signature Lab
- Pivot Migration Board
- Coupler Point Constellation
- Dead-Zone & Lock-Up Kit
- Motion Consequence Cards
- Transparent Layer Mechanism
- Error-as-Data Tolerance Kit
- Inverse Design Challenge
- Mechanism-to-Character Puppet
- Before/After Explanation Wall

Strong insight:

> The kit becomes wow when a student physically changes something and immediately sees the trace and explanation data change.

Adopted into plan:
- Jam Detective Box
- Motion Autopsy Table
- Trace Duel
- Counterfactual Cards
- Motion Lineage Wall

### 3.3 Architect synthesis

Feasible architecture:
- Add pedagogy/research data layer, not new mechanism engine first.
- Preserve Clean Architecture.
- P0 can use existing mechanism state, batch simulation, path trace, blueprint export, and JSON-safe `layer_data` as bridge.
- Hardware/camera should be P1/P2.

Adopted architecture:
- P0: local/manual evidence capture
- P1: counterfactual service + lineage + observation import
- P2: camera/fiducial/classroom atlas

### 3.4 Test engineer synthesis

Strong evaluation principles:
- Process evidence matters more than final artifact beauty.
- Claim should be backed by logs + participant explanation + artifact/trace.
- Negative cases and failed repairs must be included.
- Avoid “learning improves” unless pre/post/comparison supports it.

Adopted study strategy:
- episode coding
- repair taxonomy
- facilitator intervention log
- rich vignettes
- claim-evidence matrix

### 3.5 Critic synthesis

Harsh verdict:
- Broad toolkit framing: RR~RRX risk.
- Best pivot: Failure-as-Data.
- P0 must be at most 3 modules.
- Do not claim failure reduction, learning gain, or creativity gain without evidence.

Adopted paper framing:

> Jams as Explanations: physical breakdown as mechanism-specific explanation opportunity.

## 4. Final narrowing decision

### Selected primary spine

**Failure-as-Data / Jams as Explanations**

Reason:
- Most original compared with “digital + physical STEM kit.”
- Directly uses the messy physical nature of automata rather than hiding it.
- Creates clear evidence unit: breakdown → hypothesis → one repair → motion consequence → explanation.
- Aligns with CHI artifact + empirical + design knowledge contribution types.

### Selected core method

**Mechanism Change Episode** extended to **Breakdown-Repair Episode**.

```text
before_state
prediction
one_change_or_breakdown
motion_consequence_or_symptom
repair_hypothesis
repair_action
after_state
learner_explanation
facilitator_move
artifacts
```

### Selected demo layer

**Prediction–Trace–Repair Board** with manual fallback.

Reason:
- Strong video/demo moment.
- Does not require P0 camera tracking.
- Makes digital/physical mismatch visible.

## 5. Rejected or deferred alternatives

| Alternative | Decision | Reason |
|---|---|---|
| Full camera/fiducial twin | Defer P2 | high calibration and demo risk |
| AI tutor/explanation scoring | Defer P2 | privacy, validation, claim risk |
| Full gear/cam/linkage suite | Defer | scope diffusion |
| Classroom dashboard | Defer P2 | privacy and infrastructure risk |
| Creativity improvement study | Reject for now | needs separate validated construct |
| Learning gain claim | Reject for now | needs pre/post or comparable evidence |
| Pure character puppet paper | Demo only | too easy to become cute add-on |
| Generic inverse design challenge | Defer | competes with MotionSmith-like synthesis framing |

## 6. Reviewer-style score forecast

### Current broad MS4N plan

- Overall: RR/RRX
- Strength: good artifact and educational motivation
- Weakness: too broad, incremental toolkit risk, unclear core contribution

### Narrowed Failure-as-Data paper

- Overall: ARR potential
- Could reach A if:
  - real repair episodes are compelling,
  - coding scheme is rigorous,
  - physical failure is treated as HCI knowledge, not nuisance,
  - paper writes strong design principles.

### Main risks

1. The episodes are too few or too anecdotal.
2. Facilitators do all the explanatory work.
3. The system looks like logging rather than scaffolding.
4. The kit is too complex to reproduce.
5. The paper overclaims learning.

## 7. Validator checklist

The chosen direction passes the current autoresearch validator if:

- [x] genuinely surprising direction selected: failure as explanation
- [x] evidence path specified: repair episodes, trace, video, artifact, facilitator logs
- [x] software implications specified: episode model, breakdown tags, repair timeline, JSONL export
- [x] kit implications specified: Jam Detective Box, Motion Autopsy Table, Trace Duel, Counterfactual Cards
- [x] risks stated: overclaiming, facilitator confound, camera risk, anecdotal data
- [x] CHI forecast stated: RR/RRX baseline, ARR/A potential if evidence is strong
- [x] no fabricated results or participant counts claimed

## 8. Next loop trigger

Run another loop only after one of the following exists:

1. Internal mini-pilot data with at least 5 usable episodes.
2. A draft Lab UI flow.
3. A sample `episodes.jsonl` file.
4. A paper abstract using the new Failure-as-Data framing.

Until then, ideation should stop and P0 execution should begin.

## 9. Second-pass reviewer loop

2차 critic review verdict는 **REQUEST CHANGES/WATCH**였다. 핵심 지적은 방향이 약하다는 것이 아니라, CHI submission-grade evidence protocol이 아직 부족하다는 점이었다.

Requested changes:

1. productive failure / repair learning / debugging-as-learning / tangible STEM / simulation-physical mismatch 대비 prior-work positioning을 추가할 것.
2. “3 usable episodes/session”보다 강한 evidence threshold와 negative-case 기준을 둘 것.
3. facilitator confound를 분리하는 coding field와 interpretation rule을 만들 것.
4. prediction, breakdown, repair action, trace evidence, explanation revision, facilitator move의 필수/선택 필드를 고정할 것.
5. contribution statement를 “MS4N system”보다 “breakdown-repair episode method + scaffolded evidence capture”로 좁힐 것.

Resolution:

- `plan/06-ms4n-wild-chi-directions.md`에 prior-work positioning matrix, evidence adequacy thresholds, facilitator confound handling, required episode fields를 추가했다.
- `plan/08-ms4n-jams-as-explanations-execution-plan.md`에 `MechanismStateSnapshot` JSON-safe rule, physical observed trace rule, facilitator script constraints, prior-work action item을 추가했다.

Updated status:

- **APPROVE/CLEAR for planning handoff**
- **WATCH for CHI submission readiness until real pilot evidence exists**
