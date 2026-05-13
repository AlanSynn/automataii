# MS4N 통합 계획 인덱스

작성일: 2026-05-13  
목표: `kit/bar-board.svg` 기반 MS4N 물리 키트와 Automataii 소프트웨어를 연결하여, CHI 타깃의 **mechanism-first creative STEM scaffold**를 구현·연구할 수 있는 실행 계획을 정리한다.

## 1. 핵심 방향

MS4N의 중심 단위는 완성품이 아니라 다음 episode이다.

> **하나의 기계적 변경 → 하나의 운동 결과 → 하나의 설명 기회**

따라서 소프트웨어는 “정답 메커니즘 생성기”가 아니라, 사용자가 물리/디지털 변경을 비교하고 설명하도록 돕는 **episode capture + trace + fabrication reflection system**으로 바뀌어야 한다.

## 2. 이번 계획서 산출물

| 파일 | 역할 |
|---|---|
| `plan/00-ms4n-plan-index.md` | 전체 목표, 산출물, 우선순위, non-goals |
| `plan/01-software-change-plan.md` | 소프트웨어 아키텍처 변경, 코드 터치포인트, 데이터 모델, UI/테스트 계획 |
| `plan/02-wow-kit-module-plan.md` | kit sheet별 소프트웨어 지원 기능, evidence, gimmick 방지 기준 |
| `plan/03-chi-hci-research-plan.md` | CHI/HCI 연구 질문, 기여 프레이밍, 프로토콜, 관련연구 매트릭스 |
| `plan/04-evidence-and-test-plan.md` | Mechanism Change Episode schema, 데이터 캡처, 코딩/신뢰도, 테스트 계획 |
| `plan/05-review-gate-and-risk-register.md` | 리뷰어 관점 gate, 소프트웨어/제작/연구 리스크와 fallback |

## 3. 현재 근거

### 기존 소프트웨어 자산

- Mechanism Foundry: `src/automataii/application/mechanism_foundry/`, `src/automataii/presentation/qt/tabs/mechanism_foundry/`
- Mechanism Design tab: `src/automataii/presentation/qt/tabs/mechanism_design/`
- path trace manager: `src/automataii/presentation/qt/tabs/mechanism_design/path_trace_manager.py`
- mechanism transfer: `src/automataii/application/mechanism_transfer/`
- blueprint/export: `src/automataii/application/blueprint/composer.py`, `src/automataii/application/managers/blueprint_manager.py`, `src/automataii/infrastructure/generation/svg/blueprint.py`
- telemetry: `src/automataii/infrastructure/telemetry/telemetry.py`
- camera capture seam: `src/automataii/presentation/qt/dialogs/camera_dialog.py`

### 기존/신규 kit 자산

- base board: `kit/bar-board.svg`
- previous bars: `kit/bars-2.svg`
- generated MS4N sheets: `kit/ms4n-00-bar-board-guide.svg` through `kit/ms4n-07-fabrication-checks.svg`
- regeneration script: `kit/generate_ms4n_kit.py`
- kit README: `kit/MS4N_KIT_README.md`

### 공식 CHI 기준 메모

- CHI 2027 papers page는 CHI papers가 originality, significance, validity, research quality, presentation clarity에서 우수해야 한다고 설명한다: https://chi2027.acm.org/authors/papers/
- CHI 2027 full paper deadline은 2026-09-10 AoE이다: https://chi2027.acm.org/authors/papers/
- CHI contribution guide는 artifact/technique, systems/tools, user understanding 등 다양한 contribution type을 인정하지만, HCI에 대한 original research contribution을 요구한다: https://chi2026.acm.org/contributions-to-chi/

## 4. 우선순위 결정

### P0: CHI 파일럿에 필요한 최소 기능

1. MS4N Lab mode 또는 tab 추가 계획
2. `MechanismChangeEpisode` 데이터 모델
3. kit catalog/manifest loader
4. before/after trace 저장 및 비교
5. 설명 prompt 저장
6. fabrication check 결과 저장
7. anonymized JSONL/CSV export

### P1: Wow demo를 강화하는 기능

1. bar-board digital twin grid
2. trace overlay / side-by-side comparison
3. cam profile → follower graph
4. linkage length/pivot one-change challenge
5. fabrication bundle export

### P2: 범위가 큰 확장

1. camera/fiducial auto-detection
2. AI explanation clustering
3. smart sensor module
4. classroom live dashboard
5. inverse design recommendation

## 5. Non-goals

- 이번 단계에서 10개 kit module을 모두 완전 구현하지 않는다.
- learning gain 또는 creativity improvement를 데이터 없이 주장하지 않는다.
- camera/fiducial을 P0로 두지 않는다. 반드시 manual fallback부터 만든다.
- 기존 Mechanism Design tab을 더 복잡하게 뒤엉키게 하지 않는다. 가능하면 별도 `MS4N Lab` surface로 분리한다.

## 6. 권장 최종 결정

**별도 `MS4N Lab` tab + `domain/application/infrastructure/ms4n` 모듈을 추가한다.**  
기존 Mechanism Design은 simulation/authoring engine으로 유지하고, MS4N Lab은 kit guidance, episode capture, explanation prompts, research export를 담당한다.
