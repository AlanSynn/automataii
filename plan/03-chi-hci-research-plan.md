# MS4N CHI/HCI 연구 방향 계획

## 1. 연구 초점

MS4N은 초보자가 automata를 만들 때 “완성된 캐릭터”보다 **기계적 변경과 운동 결과의 관계**를 먼저 관찰·예측·설명하도록 돕는 digital + physical scaffold이다.

핵심 증거 단위:

> **하나의 기계적 변경 → 하나의 운동 결과 → 하나의 설명 기회**

연구의 초점은 “MS4N이 학습을 향상시켰다”를 즉시 주장하는 것이 아니라, MS4N이 어떤 **explanation opportunities**, **breakdown/repair episodes**, **teacher/facilitator interventions**, **trace-supported reasoning**을 만들어내는지 분석하는 것이다.

## 2. CHI 포지셔닝

CHI 2027 papers page는 accepted paper가 originality, significance, validity, research quality, presentation clarity 측면에서 우수해야 한다고 설명한다. CHI contribution guide는 artifact/technique, systems/tools, understanding users, methodology 등 여러 contribution type을 인정하지만 HCI에 대한 original research contribution이 필요하다고 한다.

MS4N은 다음 세 contribution을 묶는 방향이 가장 강하다.

1. **Artifact/System contribution**  
   physical kit + software trace + explanation prompt + fabrication check를 통합한 mechanism-first automata scaffold.

2. **Empirical understanding contribution**  
   초보자가 mechanism-motion 관계를 어떻게 예측, 오해, 수정, 설명하는지에 대한 episode 기반 분석.

3. **Design knowledge/method contribution**  
   creative STEM making에서 “one-change episode”를 설계·분석 단위로 삼는 transferable design principles.

## 3. 연구 질문

### RQ1. Mechanism-first scaffold는 초보자의 설계 추론을 어떻게 구조화하는가?

- 초보자는 link length, pivot, cam profile, gear ratio, attachment point를 어떤 원인으로 해석하는가?
- trace overlay와 prompt가 “그냥 해보기”를 “예측-비교-설명”으로 바꾸는가?
- 어떤 순간에 설명이 descriptive에서 causal/predictive로 이동하는가?

### RQ2. Digital simulation과 physical kit의 차이는 어떤 학습/설명 기회를 만드는가?

- simulation과 실제 motion이 다를 때 사용자는 friction, tolerance, collision, looseness를 어떻게 해석하는가?
- fabrication check가 실패를 줄이는가보다, 실패를 설명 가능한 repair episode로 바꾸는가?
- facilitator는 mismatch 순간을 어떻게 학습 질문으로 바꾸는가?

### RQ3. Mechanism Change Episode는 CHI/HCI 연구 증거로 어떻게 포착될 수 있는가?

- 로그, trace, worksheet, video, artifact, interview를 하나의 사건으로 어떻게 연결하는가?
- 어떤 episode가 단순 조작이고, 어떤 episode가 reasoning evidence인가?
- coding reliability를 어떻게 확보할 것인가?

### RQ4. Creative agency와 mechanism understanding은 어떻게 함께 형성되는가?

- 사용자는 system recommendation을 따르는가, 자기 expressive goal에 맞게 재해석하는가?
- 캐릭터 표현은 mechanism understanding을 흐리게 하는가, 강화하는가?
- 설명 가능한 움직임이 creative artifact 평가 기준이 될 수 있는가?

## 4. Claim-evidence ledger

| Claim | 필요한 evidence | 수집 방법 | 위험 통제 |
|---|---|---|---|
| MS4N은 mechanism-motion relation을 inspectable하게 만든다 | before/after trace, parameter log, prompt response | system log, trace export, worksheet | 단순 시각화와 explanation을 구분 |
| One-change constraint는 causal reasoning episode를 만든다 | 변경 변수가 하나로 제한된 episode와 설명 | prompt card log, UI lock state, video | 여러 변수를 동시에 바꾼 경우 별도 코딩 |
| Physical kit는 simulation mismatch를 repair reasoning으로 바꿀 수 있다 | jam/collision/friction episode, repair action | fabrication check, video, facilitator log | 실패율 감소 claim 금지 |
| Teacher/facilitator는 system prompt가 놓치는 explanation opportunity를 보완한다 | intervention log, before/after learner action | facilitator script/log, transcript | facilitator effect를 별도 분석 |
| MS4N의 기여는 tool 자체가 아니라 reusable design principles이다 | cross-case themes, boundary conditions, failures | thematic/interaction analysis | 일반화 범위 명시 |

## 5. Related work matrix 계획

실제 논문 작성 시 아래 축으로 related work를 재배치한다. 지금 단계에서는 citation을 추가 발굴/검증해야 한다.

| 축 | 기존 연구가 주로 하는 것 | MS4N의 차별화 포인트 |
|---|---|---|
| Constructionist/tinkerable learning environments | 조작, feedback, iteration을 통해 추상 개념을 구체화 | mechanical motion의 part-change → motion-change → explanation 단위를 foreground |
| Mechanical papercraft / automata kits | 제작, assembly, creative expression | construction output보다 mechanism reasoning episode를 기록/분석 |
| Computational mechanism design | target motion에서 mechanism 생성/최적화 | 정답 mechanism 생성보다 novice inspectability와 explanation scaffold |
| Tangible/AR learning systems | 물리 조작과 디지털 feedback 연결 | physical-digital mismatch를 failure가 아닌 repair/explanation data로 사용 |
| Fabrication-aware CAD | 제작 전 오류/간섭/공차 검출 | fabrication warning을 teacher-mediated reflection prompt로 설계 |
| Learning analytics/process traces | 로그 기반 learning process 분석 | trace를 mechanism-level causal episode와 physical artifact에 연결 |

## 6. Study protocol 초안

### 6.1 파일럿

목적: 연구 결과 주장 전에 workflow와 데이터 품질을 검증한다.

확인할 것:

- 한 세션에서 episode가 충분히 생기는가?
- 학생이 세 prompt에 답할 수 있는가?
- physical kit 조립 시간이 과도하지 않은가?
- trace export가 분석 가능한가?
- facilitator intervention 기준이 명확한가?

### 6.2 본 연구 세션 구조

1. **동의 및 배경 설문**
   - mechanism/CAD/making 경험
   - 영상/음성/사진/로그 동의 항목 분리

2. **사전 설명 과제**
   - 간단한 linkage/cam motion을 보고 “왜 움직이는지” 설명

3. **튜토리얼**
   - bar-board 좌표
   - one-change rule
   - trace card 사용법

4. **Task 1: Linkage one-change challenge**
   - pivot 또는 link length 하나만 변경
   - before/after trace 비교
   - explanation capture

5. **Task 2: Cam or fabrication repair challenge**
   - cam shape change 또는 jam detective
   - mismatch/repair episode 기록

6. **Task 3: Character connection**
   - mechanism output을 character motion에 연결
   - expressive intent와 mechanical cause를 함께 설명

7. **사후 인터뷰**
   - 가장 중요한 변경 2–3개 회상
   - 예상과 달랐던 motion
   - system/kit/prompt/facilitator가 도움이 된 순간

### 6.3 수집 데이터

- screen recording
- interaction logs
- `episodes.jsonl`
- before/after trace JSON
- worksheet/prompt responses
- physical artifact photos/videos
- fabrication check logs
- facilitator intervention logs
- interviews/transcripts

## 7. 분석 계획

### 7.1 Episode coding

기본 코드:

- change type: pivot, link_length, cam_profile, gear_ratio, attachment, spacer/material
- consequence type: amplitude, direction, speed, rhythm, path_shape, smoothness, jam
- explanation type: descriptive, causal, predictive, analogical, partial/incorrect, evidence-backed
- repair type: add spacer, move pivot, shorten link, change cam, reduce collision, abandon
- facilitator move: prompt, hint, demonstration, correction, reframing, direct fix

### 7.2 Explanation quality rubric

| Level | 기준 |
|---|---|
| 0 | 설명 없음 또는 unrelated |
| 1 | 관찰만 말함: “더 커졌다” |
| 2 | 변경과 결과를 연결: “링크를 길게 해서 더 커졌다” |
| 3 | mechanism principle을 포함: “피벗에서 멀어져 회전 반경이 커졌다” |
| 4 | 예측/대안까지 포함: “더 줄이면 진폭은 작아지지만 jam은 줄 수 있다” |

### 7.3 Reliability plan

- 최소 2명의 coder가 pilot subset을 독립 코딩
- codebook 수정 후 main data coding
- disagreement resolution memo 작성
- Cohen’s kappa 또는 percent agreement는 데이터 성격에 맞게 보고
- 정성 연구일 경우 reflexive memo와 positionality를 함께 보고

## 8. 윤리/개인정보

- IRB 또는 기관 ethics review 필요 여부 확인
- 미성년자 포함 시 보호자 동의 + child assent
- 영상/음성/작품 사진/로그 동의 분리
- raw video와 anonymized transcript 분리 보관
- participant hash 사용
- 공개 데이터에는 얼굴, 이름, 학교, 고유 작품 식별 정보 제거
- facilitator-student 권력관계와 참여 압박 방지 설명

## 9. 결과 작성 시 금지 claim

실제 데이터 없이는 다음을 쓰지 않는다.

- MS4N improves learning.
- MS4N improves creativity.
- MS4N reduces fabrication failures.
- Novices can easily build automata.
- MS4N outperforms existing systems.

대신 다음처럼 쓴다.

- MS4N surfaces explanation opportunities.
- We characterize how learners interpret mechanism-motion relations.
- We identify breakdown and repair patterns.
- We derive design considerations for teacher-mediated creative STEM toolkits.

## 10. CHI readiness gate

제출 전 반드시 있어야 할 것:

- 실제 participant/session/procedure/data source 명시
- claim-evidence ledger 완성
- related work matrix 기반 positioning
- episode examples 3–5개
- failure/repair cases
- limitations and boundary conditions
- ethics note
- supplementary material plan: protocol, codebook, sample exported JSONL, kit photos/SVGs

## 11. 공식 기준 참고

- CHI 2027 Papers: https://chi2027.acm.org/authors/papers/
- CHI 2026 Contributions to CHI: https://chi2026.acm.org/contributions-to-chi/
- CHI 2026 Guide to Successful Submission: https://chi2026.acm.org/guide-to-a-successful-submission/
