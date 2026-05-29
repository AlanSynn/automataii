# Mechanism Foundry 오른쪽 패널 연구/제품 재설계 계획

작성일: 2026-05-14
관련 PRD: `.omx/plans/prd-mechanism-foundry-right-panel-research-redesign-20260514.md`
관련 Test Spec: `.omx/plans/test-spec-mechanism-foundry-right-panel-research-redesign-20260514.md`

## 1. 한 줄 결론

Mechanism Foundry의 오른쪽 패널은 “메커니즘 백과사전”이 아니라 **Mechanism Sensemaking Panel**이어야 한다. 즉, 사용자가 파라미터를 움직이는 순간마다 다음 단위를 보여줘야 한다.

> 무엇을 바꿨는가 → 운동이 어떻게 달라졌는가 → 왜 그럴 수 있는가 → 실제 키트에서는 무엇을 확인할 것인가 → 어떤 질문으로 설명할 것인가

이렇게 바꾸면 Foundry는 단순 UI가 아니라 MS4N/Lab 연구의 핵심 주장인 **mechanism-change / motion-consequence / explanation opportunity**를 매번 생성하는 연구 장치가 된다.

## 2. 현재 패널의 좋은 점과 부족한 점

### 좋은 점

- 이미 Foundry는 `QSplitter` 구조라 오른쪽 패널을 독립적으로 개선하기 쉽다.
- `EducationalInfoPanel`은 content JSON을 받아 title, goal, motions, components, trade-offs, cautions를 깔끔하게 렌더링한다.
- parameter sliders, current angle, selected output point, path preview/cache가 이미 존재하므로 “변경 → 운동 결과”를 만들 재료가 있다.
- 기존 Lab/MS4N 계획과 연결할 수 있는 trace/export 방향이 있다.

### 부족한 점

- 현재 오른쪽 패널은 정적 설명 중심이다.
- “방금 어떤 파라미터가 바뀌었는지”를 기억하지 않는다.
- “그 변경이 어떤 motion metric에 영향을 줬는지”를 보여주지 않는다.
- “physical kit에서 이 값이 어떤 부품/구멍/스페이서와 연결되는지”가 없다.
- “교사가 지금 물어볼 질문”이나 “연구자가 나중에 분석할 episode evidence”가 없다.

## 3. CHI급으로 보이는 핵심 전환

평범한 개선:

> 오른쪽 패널을 예쁘게 만들고 설명을 더 많이 넣는다.

CHI/HCI 연구다운 개선:

> 오른쪽 패널을 novice mechanism sensemaking의 micro-scaffold로 만들고, 변화 순간을 explanation episode로 구조화한다.

따라서 논문에서 팔 수 있는 것은 “좋은 UI”가 아니라 다음이다.

1. **Just-in-time causal scaffolding**: 조작 직후 explanation prompt가 뜬다.
2. **Mechanism-specific trace evidence**: path/metric 변화가 설명의 증거가 된다.
3. **Digital-physical bridge**: simulation relation이 physical kit에서 어떻게 깨질 수 있는지 보여준다.
4. **Teacher-mediated prompt infrastructure**: 교사가 묻기 좋은 질문이 자동으로 정렬된다.
5. **Research episode seed**: Lab으로 넘길 수 있는 작은 episode draft가 생긴다.

## 4. 권장 오른쪽 패널 구조

### A. Mechanism Story

- “4-bar: crank rotation → coupler path → output rocker swing”
- “Cam: rotating profile → follower lift → timed repeated motion”
- “Gear: driver teeth → ratio/direction → coordinated rotation”
- “Slider-crank: crank rotation → rod constraint → linear stroke”

목표: novice가 부품 이름을 외우기보다 input/transmission/output chain을 본다.

### B. Cause–Effect Microscope

표시:

```text
Changed: Input Link
Before: 40.0 mm
After: 55.0 mm
Likely consequence: sweep/path range changes
Why: the input crank radius changes the driven joint's reach.
Confidence: rule-based; verify with trace.
```

핵심: “정답 설명”이 아니라 “검증 가능한 hypothesis”로 말한다.

### C. Motion Evidence

간단한 metric 카드:

- path width / height
- output sweep angle
- follower lift range
- gear ratio
- slider stroke
- warning/dead-zone/collision-risk

초기 P0에서는 숫자 metric이 부족하면 text fallback으로 충분하다.

### D. Physical Build Bridge

예:

```text
Physical check:
- This length should snap to bar-board hole spacing.
- Use spacer stack if the coupler crosses another link.
- If the physical build jams, check looseness/friction/alignment first.
```

이 부분이 MS4N의 “digital-and-physical scaffold”를 Foundry 안에 연결한다.

### E. Explain / Try Next

매번 하나만 묻는다.

- “무엇이 더 커졌거나 작아졌나?”
- “왜 그 변화가 생겼다고 생각하나?”
- “다음에는 하나만 바꾼다면 무엇을 바꿀 것인가?”

폼을 길게 만들면 Foundry가 느려진다. 오른쪽 패널은 짧은 prompt만, 본격 기록은 Lab이 담당한다.

## 5. 10개 “와우” 모듈

| # | 모듈 | 왜 재밌나 | 연구적으로 남는 것 |
|---|---|---|---|
| 1 | One-Change Lens | 하나의 파라미터만 spotlight | one-change episode 식별 |
| 2 | Trace Duel Strip | before/after path가 작은 결투처럼 보임 | motion consequence evidence |
| 3 | Prediction Ghost | 바꾸기 전 예상 방향을 ghost로 찍음 | prediction vs observation |
| 4 | Motion Autopsy Mini-card | 이상한 움직임을 증상/원인/수리로 분해 | breakdown-repair seed |
| 5 | Cause Chips | amplitude/rhythm/phase/jam risk chip이 움직임 | mechanism-specific vocabulary |
| 6 | Physical Twin Hint | bar-board hole, spacer, cam lobe와 직접 연결 | digital-physical bridge |
| 7 | Teacher Question Mode | 교사용 질문 두 개 제시 | facilitator move 분석 |
| 8 | Expressive Translation | “wobble = nervous,” “slow rise = hesitation” | creative STEM 연결 |
| 9 | Send to Lab | 현재 변화 순간을 Lab episode draft로 전송 | study data pipeline |
| 10 | Negative Case Button | “이 설명은 도움이 안 됨/틀림”을 기록 | cherry-picking 방지 |

## 6. 구현 우선순위

### P0 — lightweight sensemaking panel

- `CauseEffectRule` 데이터 구조 추가.
- `resources/mechanism_content/*.json`에 선택적 `cause_effect_rules` 필드 추가.
- `EducationalInfoPanel`을 대체/확장하는 `MechanismSensemakingPanel` 추가.
- parameter change handler에서 before/after value와 parameter key 전달.
- mechanism switch 시 stale state reset.
- four-bar/cam 우선 규칙 4개 작성.
- 테스트 추가.

### P1 — visual evidence

- before/after mini trace summary.
- prediction ghost.
- physical kit mapping.
- teacher question mode.
- Send-to-Lab episode draft.

### P2 — research/demonstration strength

- camera/fiducial physical comparison.
- classroom dashboard.
- explanation clustering.
- alternative mechanism hypotheses.

## 7. 구체 파일 계획

```text
src/automataii/application/mechanism_foundry/sensemaking.py
  - CauseEffectRule
  - FoundrySensemakingEvent
  - SensemakingService

src/automataii/application/mechanism_foundry/content_loader.py
  - MechanismContent에 optional cause_effect_rules 또는 별도 parser 연결
  - 기존 JSON 호환 유지

src/automataii/presentation/qt/tabs/mechanism_foundry/sensemaking_panel.py
  - Qt widget
  - story / microscope / evidence / physical bridge / prompt sections

src/automataii/presentation/qt/tabs/mechanism_foundry/foundry_view.py
  - _create_info_panel에서 새 panel 사용
  - _on_parameter_changed에서 before/after event 전달
  - _load_mechanism에서 reset/update

resources/mechanism_content/four_bar.json
resources/mechanism_content/cam_follower.json
  - P0 rules 추가

tests/application/mechanism_foundry/test_sensemaking.py
tests/ui/tabs/mechanism_foundry/test_sensemaking_panel.py
tests/test_mechanism_foundry_view.py
  - parser, rule lookup, panel update, regression tests
```

## 8. Reviewer's-eye critique

### 강점

- 기존 MS4N research spine과 정확히 맞는다.
- “예쁜 설명 패널”보다 contribution이 분명하다.
- 교사/학습자/연구자 세 관점을 동시에 만족시킬 수 있다.
- Lab 탭과 경쟁하지 않고 Foundry를 연구 데이터의 entry point로 만든다.

### 약점/위험

- 패널이 너무 많은 정보를 담으면 Foundry의 조작성이 죽는다.
- rule-based 설명이 틀리거나 과도하게 결정론적으로 보일 수 있다.
- metric computation을 매 slider tick마다 하면 UI가 느려질 수 있다.
- UI만 바꾸고 실제 workshop evidence가 없으면 CHI contribution은 약하다.

### 대응

- P0는 “짧은 prompt + before/after + rule confidence”만 한다.
- 모든 설명은 “likely / try observing / verify with trace” 문체를 쓴다.
- metric은 debounce 이후 또는 path cache 활용만 한다.
- 연구 claim은 “learning improved”가 아니라 “explanation opportunity를 만들었다”로 제한한다.

## 9. 최종 권장 결정

다음 구현 라운드에서 바로 P0를 진행할 가치가 있다. 단, 구현 목표는 “오른쪽 패널을 예쁘게”가 아니라 다음으로 고정해야 한다.

> Foundry의 각 parameter edit을 small, inspectable, teacher-discussable mechanism-change episode로 바꾸는 오른쪽 패널.

이 방향이 CHI 논문에서 가장 강하다. 시스템 기여는 panel 자체가 아니라, Foundry–Lab–physical kit 사이에서 원인-결과 설명 단위를 만들어내는 interaction design pattern이다.

## 10. 근거 출처

- Resnick & Rosenbaum, “Designing for Tinkerability”: https://www.media.mit.edu/publications/designing-for-tinkerability/
- Ishii & Ullmer, “Tangible Bits,” CHI 1997: https://www.media.mit.edu/publications/tangible-bits-towards-seamless-interfaces-between-people-bits-and-atoms-2/
- Hornecker & Buur, “Getting a Grip on Tangible Interaction,” CHI 2006: https://portal.findresearcher.sdu.dk/en/publications/getting-a-grip-on-tangible-interaction-a-framework-on-physical-sp/
- Quintana et al., “A Scaffolding Design Framework for Software to Support Science Inquiry,” JLS 2004: https://eric.ed.gov/?id=EJ683043
