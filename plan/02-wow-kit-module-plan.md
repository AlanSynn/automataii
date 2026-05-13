# MS4N Wow-Kit 모듈별 소프트웨어 추가 계획

## 1. 핵심 원칙

각 kit module은 다음 episode를 만들어야 한다.

> **기계적 변경 1개 → 운동 결과 1개 이상 → 학생 설명 1개 이상**

“와우”는 시각 효과가 아니라, 학생이 물리적으로 바꾼 것이 디지털 trace와 설명 데이터로 즉시 연결되는 순간에서 나온다.
따라서 모든 모듈은 **anti-gimmick 기준**을 통과해야 한다: 센서, 카메라, 캐릭터 효과, 자동 추천은 학습/연구 episode를 더 잘 남길 때만 유지하고, 실패해도 수동 입력으로 같은 증거를 남길 수 있어야 한다.

## 2. Kit module 우선순위

| Priority | Module | 이유 |
|---|---|---|
| P0 | Linkage Length Lab | 기존 linkage 기능과 path trace를 가장 잘 활용 가능 |
| P0 | Motion Trace Passport / Trace Cards | CHI evidence unit 생성의 핵심 |
| P0 | One-Change Challenge Cards | causal reasoning을 활동 규칙으로 고정 |
| P0 | Fabrication Checks / Jam Detective | 실패를 연구 데이터로 전환 |
| P1 | Cam Shape Composer | cam profile → follower graph가 강한 wow |
| P1 | Bar-Board Digital Guide | 물리-디지털 mapping 안정화 |
| P1 | Character Connectors | STEM + expression 연결 |
| P1 | Crank-Slider | 직관적 회전→직선 변환 |
| P2 | Gear Mood Dial | ratio visualization은 좋지만 gimmick 위험 있음 |
| P2 | Analog-Digital Twin Board | wow는 강하지만 camera/fiducial calibration risk 큼 |

## 3. 공통 소프트웨어 기능

- kit sheet 선택
- mechanism template 선택
- physical setup guide
- before state capture
- one-change lock
- after state capture
- trace comparison
- explanation prompt
- fabrication check
- JSONL/CSV export

공통 로그 필드:

```text
session_id
participant_hash/group_id
module_id
kit_sheet_id
mechanism_type
changed_parameter
before_parameters
after_parameters
trace_before_ref
trace_after_ref
motion_consequence_labels
student_prediction
student_explanation
fabrication_check_result
breakdown_repair
facilitator_intervention
```

## 4. Module A — Bar-Board Base + Guide

### 물리 자산

- `kit/bar-board.svg`
- `kit/ms4n-00-bar-board-guide.svg`

### 소프트웨어 추가

- digital bar-board grid
- coordinate labels A–K / 1–15
- pivot/anchor placement
- manual physical board mapping
- optional photo reference attach

### 기록할 evidence

- selected hole coordinates
- pivot/anchor before/after
- invalid placement attempts
- coordinate correction count
- student explanation of why location matters

### MVP flow

1. 학생이 board 좌표를 선택한다.
2. 앱에서 같은 좌표를 클릭한다.
3. mechanism template을 배치한다.
4. pivot 하나를 다른 좌표로 옮긴다.
5. trace/metric 차이를 본다.
6. 설명 prompt를 작성한다.

### Wow extension

- camera/fiducial board recognition
- physical-digital mismatch overlay
- classroom heatmap of difficult coordinates

### Gimmick 방지

자동 인식이 실패해도 manual coordinate entry가 같은 연구 데이터를 남겨야 한다.

## 5. Module B — Linkage Length Lab

### 물리 자산

- `kit/ms4n-01-linkage-bars.svg`
- existing `kit/bars-2.svg`

### 소프트웨어 추가

- four-bar preset mode
- link length one-change lock
- pivot position one-change lock
- Grashof/feasibility warning
- coupler/output point trace
- before/after path overlay

### 기록할 evidence

- bar count
- link lengths
- pivot coordinates
- coupler point
- output path before/after
- motion consequence labels: wider, smaller, reversed, stuck, smoother
- learner explanation

### MVP flow

1. 4-bar template 선택
2. physical bars로 조립
3. link length 또는 pivot 하나만 바꿈
4. trace overlay 확인
5. “왜 path가 달라졌나?” 설명

### Wow extension

- 5-bar/6-bar comparison
- desired trace challenge
- automatic detection from photo/fiducial

### Gimmick 방지

“멋진 궤적 만들기”보다 “어떤 link/pivot이 어떤 변화에 기여했는가”를 기록해야 한다.

## 6. Module C — Cam Shape Composer

### 물리 자산

- `kit/ms4n-02-cam-follower-kit.svg`

### 소프트웨어 추가

- cam profile library: circle, eccentric, oval, pear, bump
- follower displacement graph
- rise/dwell/fall annotation
- before/after graph comparison
- trace-to-cam explanation prompt

### 기록할 evidence

- cam profile id
- control points or profile parameters
- follower displacement curve
- max displacement delta
- rhythm/smoothness labels
- student explanation tied to cam shape

### MVP flow

1. cam profile 선택
2. follower graph 예측/확인
3. cam shape 하나 변경
4. graph와 physical motion 비교
5. “이 봉우리가 왜 움직임을 크게 만들었나?” 설명

### Wow extension

- hand-drawn cam recognition
- desired follower graph → suggested cam profile
- rhythm/music mapping

### Gimmick 방지

그래프를 예쁘게 보여주는 데서 끝나면 안 된다. 학생 설명은 반드시 cam shape region에 주석으로 연결한다.

## 7. Module D — Crank-Slider

### 물리 자산

- `kit/ms4n-03-crank-slider-kit.svg`

### 소프트웨어 추가

- crank length / rod length / slider axis parameters
- stroke length metric
- dead-center visualization
- slider displacement graph

### 기록할 evidence

- crank length
- rod length
- slider axis
- stroke delta
- dead center observation
- learner explanation

### MVP flow

1. crank-slider template 선택
2. crank radius 하나 변경
3. stroke length 변화 확인
4. physical slider motion과 비교
5. 설명 저장

### Wow extension

- video-tracked slider motion
- longest stroke challenge
- force/speed tradeoff visualization

### Gimmick 방지

자동차 엔진 analogy는 보조 자료로만 쓰고, 주 데이터는 crank length → stroke consequence에 둔다.

## 8. Module E — Gear Mood Dial

### 물리 자산

- `kit/ms4n-04-gears-pulleys-kit.svg`

### 소프트웨어 추가

- gear teeth/radius selection
- gear ratio calculator
- direction arrows
- input/output RPM comparison
- optional character motion label

### 기록할 evidence

- teeth count
- connection graph
- ratio
- direction change
- speed label
- learner explanation

### MVP flow

1. 2-gear setup
2. driven gear만 변경
3. speed/direction 변화 확인
4. “왜 느려졌나/빨라졌나?” 설명

### Wow extension

- multi-stage gear train
- pulley/belt path
- target speed challenge

### Gimmick 위험

“mood” label이 감성 놀이로만 보일 수 있다. ratio/direction/speed evidence와 반드시 묶는다.

## 9. Module F — Character Connectors

### 물리 자산

- `kit/ms4n-05-character-connectors.svg`

### 소프트웨어 추가

- mechanism output point → character joint mapping
- attachment point one-change mode
- motion scale/direction controls
- expression label annotation

### 기록할 evidence

- connected joint
- output point
- attachment coordinate
- joint angle/motion trace
- expression label
- learner explanation: mechanical cause + expressive effect

### MVP flow

1. mechanism output point 선택
2. character arm/wing/tail에 연결
3. attachment point 하나 변경
4. motion 표현 차이 비교
5. 설명 저장

### Wow extension

- multi-joint choreography
- emotion presets
- storyboard export

### Gimmick 방지

캐릭터 이야기가 mechanism variable을 흐리지 않게, “attachment point만 변경” 같은 one-change rule을 유지한다.

## 10. Module G — Trace Prompt Cards / Motion Trace Passport

### 물리 자산

- `kit/ms4n-06-trace-prompt-cards.svg`

### 소프트웨어 추가

- prompt card selector
- predicted trace input field
- actual trace capture
- before/after overlay
- explanation card export

### 기록할 evidence

- prompt id
- predicted trace reference
- actual trace points
- similarity score or qualitative mismatch label
- explanation text
- revision count

### MVP flow

1. prompt card 선택
2. 변경 전 예측 작성
3. mechanism 변경
4. actual trace 확인
5. mismatch 설명

### Wow extension

- hand-drawn prediction import
- trace wall/gallery
- printable explanation poster

### Gimmick 방지

카드는 활동 장식이 아니라 episode metadata를 생성해야 한다.

## 11. Module H — Fabrication Checks / Jam Detective

### 물리 자산

- `kit/ms4n-07-fabrication-checks.svg`

### 소프트웨어 추가

- tolerance checklist
- collision/jam risk tags
- spacer/washer recommendation note
- fabrication readiness score
- repair action logging

### 기록할 evidence

- check result
- breakdown type
- repair action
- before/after repair trace
- facilitator intervention
- final readiness

### MVP flow

1. 설계 후 fabrication check 실행
2. jam/collision/tolerance warning 확인
3. repair action 하나 선택
4. 재검사
5. “어떤 문제가 해결되었나?” 설명

### Wow extension

- auto-fix suggestion
- fabrication bundle BOM
- failure gallery

### Gimmick 방지

실패 태그만 붙이면 장난감화된다. breakdown taxonomy + repair evidence + before/after trace가 필수다.

## 12. Module I — Analog-Digital Twin Board

### 물리 자산

- `kit/bar-board.svg`
- `kit/ms4n-00-bar-board-guide.svg`
- optional marker blanks in `kit/ms4n-06-trace-prompt-cards.svg`

### 소프트웨어 추가

- P0: manual digital twin board
- P1: photo snapshot attach
- P2: fiducial marker detection and board calibration

### 기록할 evidence

- detected/manual board state
- calibration confidence
- mismatch between simulation and physical observation
- learner mismatch explanation

### MVP flow

1. manual board layout 입력
2. physical build photo attach
3. simulation vs physical note 작성

### Wow extension

- camera-based real-time board state recognition
- predicted vs observed overlay

### Gimmick 방지

실시간 인식보다 mismatch explanation이 연구 기여다. 인식 실패 시 manual fallback으로 같은 evidence를 남긴다.

## 13. 우선 구현 조합

### CHI 파일럿 최소 조합

- Bar-Board Base
- Linkage Length Lab
- Trace Prompt Cards
- Fabrication Checks
- Character Connectors 단일 joint

### CHI demo wow 조합

- Cam Shape Composer
- Motion Trace Passport
- Analog-Digital Twin Board manual/photo mode

### 나중 조합

- Gear Mood Dial
- multi-stage storyboard
- fiducial tracking
- AI explanation clustering
