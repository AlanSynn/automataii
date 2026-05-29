# MS4N Wild CHI Directions: 신기하지만 증거로 버틸 수 있는 방향

## 0. 결론 먼저

현재 MS4N의 기본 방향인 “mechanism-first digital-and-physical automata scaffold”는 좋지만, 그대로 쓰면 CHI 리뷰어에게 **잘 만든 교육용 키트 + 로그 분석**으로 보일 위험이 있다. 더 강하게 가려면 넓히는 것이 아니라 **radical narrowing**이 필요하다.

가장 강한 새 방향은 다음이다.

> **Jams as Explanations:** MS4N은 제작 실패를 줄이는 도구가 아니라, jam, 마찰, 헐거움, 충돌, 공차 오차를 초보자의 기계적 추론과 repair explanation으로 바꾸는 physical-digital scaffold이다.

즉, “잘 돌아가는 자동인형”보다 더 CHI다운 질문은 이것이다.

> 왜 안 돌아갔고, 무엇을 바꾸면, 어떤 motion consequence가 생기며, 학습자는 그것을 어떻게 설명하는가?

이 방향은 기존 `plan/00–05`의 “one mechanical change → one motion consequence → one explanation opportunity”를 유지하되, 가장 재미있는 순간을 **성공이 아니라 고장/불일치/수리**로 옮긴다.

## 1. CHI reviewer model

공식 CHI 2027 Papers 페이지는 accepted papers가 originality, significance, validity, research quality, presentation clarity에서 뛰어나야 한다고 설명한다. 또한 CHI 2026 contribution guide는 artifact/technique, empirical, theory, argument 등 다양한 기여 유형을 인정하지만, 모든 경우 HCI에 대한 original research contribution이 필요하다고 말한다.

따라서 MS4N은 아래처럼 보여야 한다.

| 약한 framing | 강한 framing |
|---|---|
| automata kit with software | physical breakdown을 explanation opportunity로 바꾸는 HCI scaffold |
| trace overlay tool | prediction–mismatch–repair evidence system |
| novice learning kit | novice mechanical reasoning을 포착하는 episode method |
| fabrication checker | failure-as-data interface |
| character animation tool | mechanical cause가 expressive motion으로 번역되는 reasoning medium |

공식 기준상 submission은 paper 자체로 contribution을 이해할 수 있어야 하고, 연구 품질과 방법 상세도 충분해야 한다. 따라서 이 문서의 모든 방향은 “wow demo”가 아니라 claim-evidence ledger와 함께 제안한다.

References:
- CHI 2027 Papers: https://chi2027.acm.org/authors/papers/
- CHI 2026 Contributions to CHI: https://chi2026.acm.org/contributions-to-chi/
- CHI 2026 Guide: https://chi2026.acm.org/guide-to-a-successful-submission/

## 2. North Star

### Paper thesis candidate

> MS4N is a mechanism-first physical-digital scaffold that turns novice automata making into analyzable mechanism-change and breakdown-repair episodes, revealing how learners predict, observe, explain, and repair motion through constrained one-change interactions.

### 한국어 thesis

> MS4N은 초보자의 자동인형 제작을 완성품 중심 활동이 아니라, 하나의 기계적 변경과 하나의 고장/불일치를 통해 운동 원인과 수리 전략을 설명하는 episode들의 연속으로 재구성한다.

### 가장 강한 제목 후보

1. **Jams as Explanations: Designing Mechanism-First Scaffolds for Repair Reasoning in Novice Automata Making**
2. **When Automata Fail: Turning Physical Breakdowns into Explainable Motion Episodes**
3. **One Change, One Motion, One Repair: Mechanism-First Scaffolding for Creative STEM Automata Making**
4. **The Motion Autopsy Table: Making Mechanical Cause and Failure Inspectable in Paper Automata**
5. **From Trace to Repair: Physical-Digital Mismatch as a Learning Resource in Automata Making**

## 3. Ranked wild directions

### 1위 — Jams as Explanations / Failure-as-Data

**Hook:** 실패를 피하지 않는다. 오히려 실패를 가장 중요한 learning artifact로 만든다.

**What is wild:** 대부분의 fabrication/CAD 도구는 failure를 줄이거나 숨기려 한다. MS4N은 jam, friction, looseness, collision을 **causal reasoning event**로 바꾼다.

**Kit idea:**
- `Jam Detective` sheet
- friction washer set
- loose joint vs tight joint fastener set
- spacer stack
- collision tab
- “symptom cards”: stuck, wobble, delayed rise, overshoot, weak swing

**Software idea:**
- Breakdown logging panel
- before/after repair trace overlay
- failure-mode tag: friction, alignment, collision, tolerance, overconstraint, material stiffness
- “repair hypothesis” prompt
- repair timeline replay

**Learner episode:**
1. Mechanism works in simulation.
2. Physical build jams or behaves differently.
3. Student tags symptom.
4. Student changes one spacer, pivot, link, washer, or connection.
5. Trace or video evidence shows consequence.
6. Student explains why the repair changed the motion.

**Evidence needed:**
- video + artifact photo + trace/log triangulation
- repair episode codebook
- facilitator intervention log
- successful and failed repairs
- 3–5 rich vignettes in paper

**Forbidden claim:** “MS4N reduces failures.” Safer claim: “MS4N turns failures into analyzable repair episodes.”

**Score forecast:** ARR → A potential if actual repair episodes are strong; RR if episodes are thin.

### 2위 — Counterfactual Automata

**Hook:** Every mechanical edit becomes a tangible counterfactual: “If this explanation is true, what should happen when we move this pivot?”

**What is wild:** 만들기 활동을 small causal experiment로 바꾼다. 결과물을 만드는 것이 아니라 **반사실 기계 실험**을 수행한다.

**Kit idea:**
- One-Change Challenge Cards
- Pivot migration board
- link-length A/B comparison bars
- “near-miss” mechanism cards

**Software idea:**
- before prediction capture
- counterfactual variant generator
- ghost traces for “what if pivot moved two holes”
- explanation stress-test: learner explanation을 검증할 next edit 제안

**Learner episode:**
1. Student predicts motion.
2. Student changes one variable.
3. MS4N shows expected/actual/counterfactual traces.
4. Student revises causal explanation.

**Evidence needed:**
- prediction accuracy and revision quality
- causal chain coding
- transfer task: new mechanism, same reasoning
- baseline vs MS4N optional comparison

**Score forecast:** ARR 가능. Strong if framed as embodied counterfactual reasoning, not just parameter exploration.

### 3위 — Prediction–Trace–Repair Board

**Hook:** 디지털 twin이 정답이 아니라, 틀렸을 때 더 좋은 교사가 된다.

**What is wild:** simulation과 physical build의 mismatch를 noise가 아니라 explanation material로 만든다.

**Kit idea:**
- `bar-board.svg` 기반 physical board
- printable trace passport
- physical build photo slot
- optional fiducial markers as P2 only

**Software idea:**
- predicted trace vs observed trace overlay
- manual observed trace import at P0
- physical observation note
- mismatch categories: phase lag, amplitude loss, collision, wobble, dead zone

**Learner episode:**
1. Digital prediction says motion should be smooth.
2. Physical build shows wobble or jam.
3. Student identifies mismatch.
4. Student performs one repair.
5. Student explains why simulation and physical build diverged.

**Score forecast:** RR → ARR. Visually compelling, but risky if it becomes “camera demo.” Must keep manual fallback.

### 4위 — Motion Lineage

**Hook:** 완성작 하나가 아니라, motion이 어떻게 진화했는지를 보여준다.

**What is wild:** CAD history가 아니라 **mechanical motion genealogy**를 만든다. 학생의 여러 edit가 motion family tree로 남는다.

**Kit idea:**
- class “motion lineage wall”
- before/after trace stickers
- lineage cards: ancestor, mutation, consequence, explanation

**Software idea:**
- edit tree where each node stores parameters, trace, explanation
- motion signature clustering
- printable lineage poster

**Evidence needed:**
- whether students use lineage to compare mechanisms
- expert/facilitator assessment of teaching value
- artifact walkthroughs

**Score forecast:** ARR 가능 but needs evidence that lineage is more than pretty history UI.

### 5위 — Misconception Atlas

**Hook:** MS4N이 좋은 작품만 모으는 것이 아니라, 초보자의 기계적 오해를 지도화한다.

**What is wild:** wrong explanations become a research contribution.

**Kit idea:**
- prediction cards deliberately targeting common wrong intuitions
- “why was my prediction wrong?” cards

**Software idea:**
- explanation code tags
- misconception candidates: longer means faster, taller cam equals path shape, near pivot always means bigger motion, gear bigger always stronger/faster
- class-level anonymized misconception atlas

**Evidence needed:**
- codebook and inter-rater reliability
- repeated misconception patterns
- design implications for scaffolding

**Score forecast:** ARR stable if empirical corpus is strong; less visually wow than Failure-as-Data.

### 6위 — Productive Mechanical Friction

**Hook:** 초보자 친화성은 항상 friction 제거가 아니다. 적절한 어려움이 explanation을 만든다.

**What is wild:** HCI tools often lower barriers; MS4N calibrates barriers.

**Kit/software idea:**
- explanation gate before simulation reveal
- limited one-change rule
- reversible failure moments
- “no auto-fix before hypothesis” mode

**Evidence needed:**
- frustration vs usefulness balance
- whether friction generates richer explanations
- negative cases

**Score forecast:** high variance RR → A. Strong argument paper angle, but risky if users hate it.

### 7위 — Debateable Automata

**Hook:** 같은 motion을 두 팀이 서로 다른 mechanism으로 설명하고 논쟁한다.

**What is wild:** automata making becomes collaborative mechanical argumentation.

**Kit/software idea:**
- competing proposal cards
- evidence tokens: trace, photo, repair, parameter
- “mechanism court” classroom activity

**Evidence needed:**
- discourse analysis
- peer challenge/repair sequences
- facilitator notes

**Score forecast:** ARR if discourse data is strong; scope risk high.

### 8위 — Mechanism-to-Character Puppet Translation

**Hook:** 같은 기계 motion이 팔, 다리, 꼬리, 얼굴에 붙을 때 meaning이 바뀐다.

**What is wild:** mechanical cause and expressive interpretation are coupled.

**Kit/software idea:**
- transparent layer character sheets
- output-point-to-limb connector
- gesture explanation prompt

**Evidence needed:**
- whether expression motivates deeper mechanism reasoning
- body mapping explanations

**Score forecast:** RR → ARR. Great demo, but must avoid becoming “cute character add-on.”

### 9위 — Classroom Motion Atlas

**Hook:** 한 교실의 모든 mechanical edits가 collective motion dataset이 된다.

**What is wild:** classroom becomes a motion laboratory.

**Kit/software idea:**
- local atlas only at P0
- anonymous motion signatures
- teacher-curated examples

**Evidence needed:**
- teacher/facilitator value
- privacy-safe workflow
- cross-team comparison moments

**Score forecast:** RR → ARR but too large for first paper unless scoped tightly.

### 10위 — Explanation Stress-Test Engine

**Hook:** 학생의 설명을 받아서 “그 설명이 맞다면 다음 변화는 무엇을 만들어야 하는가?”를 시험한다.

**What is wild:** explanation becomes executable hypothesis.

**Kit/software idea:**
- rule-based explanation templates
- counterexample prompts
- next-edit suggestion card

**Evidence needed:**
- explanation revision before/after stress-test
- transfer to unseen edits

**Score forecast:** ARR if rule-based and tightly scoped; risky if LLM/AI claim enters without evidence.

## 4. Decision matrix

Scale: 5 = strongest. Risk: 5 = highest risk.

| Direction | Novelty | Evidence strength | Feasibility | CHI fit | Wow | Risk | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Jams as Explanations | 5 | 5 | 4 | 5 | 4 | 3 | Primary spine |
| Counterfactual Automata | 5 | 4 | 4 | 5 | 4 | 3 | Core interaction |
| Prediction–Trace–Repair Board | 4 | 4 | 3 | 4 | 5 | 4 | Demo/evidence layer |
| Motion Lineage | 4 | 4 | 3 | 4 | 4 | 3 | Strong secondary |
| Misconception Atlas | 4 | 5 | 4 | 5 | 3 | 2 | Empirical backbone |
| Productive Mechanical Friction | 5 | 3 | 4 | 4 | 4 | 5 | Provocative framing |
| Debateable Automata | 4 | 4 | 3 | 4 | 4 | 4 | Later study |
| Mechanism-to-Character Puppet | 3 | 3 | 4 | 3 | 5 | 3 | Demo layer only |
| Classroom Motion Atlas | 4 | 4 | 2 | 4 | 4 | 5 | P2/research infra |
| Explanation Stress-Test | 5 | 4 | 3 | 4 | 4 | 4 | P1 if rule-based |

## 5. Recommended paper architecture

### Primary contribution

**A physical-digital scaffold and analysis method for turning automata breakdowns into mechanism-change episodes.**

### Secondary contribution

**An empirical characterization of novice repair reasoning in automata making.**

### Design contribution

**Design considerations for productive mechanical friction in creative STEM toolkits.**

### Artifact contribution

**Lab + Jam Detective Kit + Trace Passport + One-Change Challenge Cards.**

## 6. Revised research questions

RQ1. How do novices predict, observe, explain, and repair motion when automata making is structured around one-change episodes?

RQ2. How do physical breakdowns and digital-physical mismatches become resources for causal explanation rather than mere fabrication errors?

RQ3. What design features help facilitators turn jams, friction, looseness, and collisions into teachable repair reasoning moments?

RQ4. What design principles emerge for mechanism-first creative STEM toolkits that intentionally preserve productive mechanical friction?

## 7. The “wow” kit should look like this

### A. Motion Autopsy Table

A physical table layout where each team places:
- before mechanism photo
- predicted trace
- actual trace
- breakdown symptom card
- one repair action
- after trace
- explanation quote

This becomes both classroom display and research data structure.

### B. Jam Detective Box

A box of intentionally different fasteners/spacers:
- tight washer
- loose paper fastener
- friction washer
- tall spacer
- short spacer
- collision tab
- flexible link
- stiff link

Students draw a symptom card and must diagnose with one-change experiments.

### C. Counterfactual Cards

Cards ask:
- “If your explanation is true, what happens if the pivot moves one hole up?”
- “If friction is the cause, what repair should change the trace?”
- “If link length is the cause, which trace feature should change?”

### D. Trace Duel

Students first draw expected trace. Then software/physical trace overlays it. The goal is not to be correct immediately; the goal is to revise explanation using evidence.

### E. Motion Lineage Wall

Every team prints a small lineage strip:

```text
Version 0 -> Jam -> Hypothesis -> One repair -> New trace -> Revised explanation
```

The classroom ends with a gallery of mechanical mutations and repair stories.

## 8. Software changes implied

P0 software should not start with AI or camera. It should implement the evidence spine.

### P0

- `MechanismChangeEpisode`
- `BreakdownRepairEpisode`
- one-change lock
- before/after trace capture
- prediction prompt
- repair hypothesis prompt
- breakdown tag
- JSONL/CSV export
- printable Motion Autopsy Sheet

### P1

- counterfactual variant generator
- rule-based explanation stress-test
- local motion lineage tree
- physical observation import: manual trace/photo/video reference
- facilitator intervention log

### P2

- camera/fiducial tracking
- class motion atlas
- misconception clustering
- dashboard
- optional AI-assisted coding, not AI tutoring

## 9. Claims allowed vs forbidden

### Allowed now

- MS4N is designed to surface explanation opportunities.
- MS4N records mechanism-change and breakdown-repair episodes.
- MS4N treats physical mismatch as an analyzable interaction event.
- We investigate how novices and facilitators use these episodes in automata making.

### Allowed after sufficient evidence

- Participants used breakdowns to generate repair hypotheses.
- Trace overlays were used as evidence in explanation and repair.
- Facilitators used MS4N artifacts to ask mechanism-specific questions.
- The one-change constraint helped structure causal comparison.

### Forbidden without stronger data

- MS4N improves learning.
- MS4N improves creativity.
- MS4N reduces fabrication failure.
- MS4N outperforms existing systems.
- Novices can easily build automata.
- Trace causes understanding.

## 10. Score forecast

Current baseline if submitted as broad toolkit: **RR–RRX**.

With the proposed narrowing:

| Evidence level | Forecast |
|---|---|
| Only system description + internal demo | RR/RRX |
| Pilot with rich repair vignettes but limited corpus | RR/ARR |
| Dense workshop data, codebook, repair taxonomy, negative cases | ARR |
| Strong empirical corpus + excellent video + transferable design principles | ARR/A potential |

No plan can guarantee acceptance. But this pivot gives MS4N the kind of originality and significance CHI reviewers can understand: not just a cool automata kit, but a way to make messy physical failure into inspectable HCI knowledge.

---

## 11. Post-review tightening: what makes this not just productive failure?

2차 CHI-style review는 방향은 강하지만, prior-work positioning과 evidence threshold가 더 구체적이어야 한다고 판단했다. 아래 보강을 최종 research spine에 반영한다.

### 11.1 Prior-work positioning matrix

| Related stream | What they often foreground | Risk if MS4N sounds similar | MS4N's sharper distinction |
|---|---|---|---|
| Constructionist / tinkerable learning environments | manipulation, feedback, iteration, learner agency | “또 다른 maker learning kit” | MS4N의 단위는 open-ended tinkering이 아니라 **mechanism-change / breakdown-repair episode**이다. |
| Tangible STEM kits | physical construction and embodied exploration | “physical kit + worksheet” | MS4N은 physical construction보다 **physical mismatch를 explanation evidence로 보존**하는 데 초점을 둔다. |
| Fabrication-aware CAD | manufacturability checks, error prevention, optimization | “fabrication checker” | MS4N은 failure를 줄인다고 주장하지 않고, **failure를 inspectable repair reasoning material로 전환**한다. |
| Debugging-as-learning / productive failure | failure as learning opportunity | “productive failure를 automata에 적용했을 뿐” | MS4N의 새로움은 failure 일반론이 아니라 **기계적 변수, motion trace, repair action, learner explanation을 한 episode schema로 연결**하는 것이다. |
| Simulation-physical mismatch tools | model-vs-reality comparison | “digital twin mismatch demo” | MS4N은 prediction accuracy가 아니라 **mismatch가 어떻게 facilitator-mediated causal question이 되는지**를 분석한다. |
| Creative automata authoring / mechanism synthesis | desired motion to candidate mechanism | “MotionSmith류 authoring tool” | MS4N은 end-to-end authoring보다 **wrong prediction, jam, tolerance, repair**를 중심 데이터로 삼는다. |

### 11.2 Narrow contribution statement

Primary contribution은 “MS4N system”이 아니라 다음으로 고정한다.

> **A breakdown-repair episode method and scaffolded evidence-capture system for studying how novices and facilitators turn physical automata failures into mechanism-specific causal explanations.**

System은 이 method를 가능하게 하는 artifact/probe이다. 논문 contribution 순서는 다음처럼 쓴다.

1. **Breakdown-repair episode**: novice automata making에서 failure를 분석 가능한 HCI 단위로 정의한다.
2. **MS4N scaffold**: kit, trace, prompt, repair tags, autopsy sheet로 해당 episode를 생성·보존하게 한다.
3. **Empirical/design insights**: 실제 workshop/pilot에서 failure, repair, facilitator moves가 어떻게 explanation으로 전환되는지 분석한다.

### 11.3 Evidence adequacy thresholds

결과를 발명하지 않기 위해 수치는 “목표/게이트”로만 둔다.

| Evidence item | Minimum gate before full CHI submission | Why needed |
|---|---|---|
| Usable breakdown-repair episodes | target: at least 20 analyzable episodes across sessions, including failed repairs | isolated anecdotes 방지 |
| Rich vignettes | 3–5 complete cases with video/photo/log/trace/explanation | paper narrative와 evidence 연결 |
| Negative cases | at least 3 cases where scaffold did not produce explanation or repair | cherry-picking 방지 |
| Facilitator moves | every intervention tagged as question/hint/direct fix/demonstration/reframing | facilitator confound 분리 |
| Coding reliability | second coder on subset; revise codebook if agreement/consensus is weak | qualitative rigor |
| Data triangulation | each central finding uses at least two of log/trace/video/photo/interview/worksheet | validity |
| Ethics readiness | consent for video/photo/audio/log/artifact, anonymization path | CHI human-subjects quality |

If these gates fail, the paper should remain a systems/demo or pilot paper, not claim full empirical contribution.

### 11.4 Facilitator confound handling

The paper must not imply that MS4N independently teaches. The stronger and safer stance is:

> MS4N is a **teacher-mediated explanation infrastructure** that makes the right moments visible, recordable, and discussable.

Required coding field:

```text
facilitator_move:
  none
  question_only
  hint
  direct_instruction
  physical_demonstration
  repair_done_by_facilitator
  reframing_or_analogy
```

Interpretation rule:
- If explanation occurs only after direct instruction, count it as facilitator-led, not system-scaffolded.
- If MS4N artifact/trace/tag prompts the facilitator to ask a mechanism-specific question, count it as scaffold-mediated facilitation.
- If learner independently references trace/photo/repair tag, count it as learner-led evidence use.

### 11.5 Required episode fields

A breakdown-repair episode is valid only if it contains:

Required:
- episode id
- before state or photo/trace reference
- breakdown symptom
- suspected cause or “unknown”
- one repair action
- after state or photo/trace reference
- learner explanation or explicit absence of explanation
- facilitator move tag

Optional but valuable:
- prediction before repair
- counterfactual next edit
- motion metrics
- confidence rating
- artifact/poster reference
- interview excerpt

### 11.6 Updated forecast

| State | Forecast |
|---|---|
| Current documents only | planning complete, not submission-ready |
| P0 prototype + internal mini-pilot | RR/ARR 가능성 평가 가능 |
| 20+ analyzable episodes + codebook + negative cases | ARR plausible |
| Strong vignettes + facilitator confound analysis + transferable principles | ARR/A potential |

This is still not a guarantee. It is a route to make MS4N legible as HCI research rather than a cool kit.
