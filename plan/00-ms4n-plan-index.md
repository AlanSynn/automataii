# MS4N 통합 계획 인덱스

작성일: 2026-05-13
목표: `kit/bar-board.svg` 기반 MS4N 물리 키트와 Automataii 소프트웨어를 연결하여, CHI 타깃의 **mechanism-first creative STEM scaffold**를 구현·연구할 수 있는 실행 계획을 정리한다.

## 1. 핵심 방향

### Naming decision

사용자-facing top-level surface 이름은 **Lab**으로 고정한다. 논문/연구 프로젝트 이름은 MS4N으로 유지하지만, 앱 탭/클래스/테스트/문서에서 MS4N-prefixed Lab 표기는 쓰지 않는다. 구현 계획상 presentation package는 `presentation/qt/tabs/lab`, tab class는 `LabTab`, objectName은 `tab_lab`을 사용한다.


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

1. Lab mode 또는 tab 추가 계획
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
- 기존 Mechanism Design tab을 더 복잡하게 뒤엉키게 하지 않는다. 가능하면 별도 `Lab` surface로 분리한다.

## 6. 권장 최종 결정

**별도 `Lab` tab + `domain/application/infrastructure/ms4n` 모듈을 추가한다.**
기존 Mechanism Design은 simulation/authoring engine으로 유지하고, Lab은 kit guidance, episode capture, explanation prompts, research export를 담당한다.

## 7. Implementation-gate additions (2026-05-14)

| 파일 | 역할 |
|---|---|
| `plan/09-ms4n-implementation-architecture-plan.md` | Jams-as-Explanations를 현재 Clean Architecture 구조에 어디/어떻게 추가할지 결정한 구현 아키텍처 계획 |
| `plan/10-ms4n-p0-implementation-task-breakdown.md` | 4주 P0 internal pilot MVP 기준 파일별 백로그와 DoD |
| `plan/11-ms4n-implementation-test-plan.md` | P0 구현 전 RED 테스트, 회귀 테스트, golden fixture, pilot readiness gate |
| `plan/12-ms4n-implementation-prd.md` | `.omx/plans` PRD의 git-visible mirror; coding gate 공유용 |
| `plan/13-ms4n-implementation-test-spec.md` | `.omx/plans` test-spec의 git-visible mirror; CI/reviewer 공유용 |
| `plan/14-ms4n-implementation-code-review.md` | code-review 결과의 git-visible mirror; APPROVE/CLEAR gate evidence |
| `plan/15-ms4n-lab-rename-code-review.md` | Lab naming rename review 결과의 git-visible mirror; APPROVE/CLEAR gate evidence |
| `plan/16-mechanism-foundry-right-panel-research-redesign.md` | Mechanism Foundry 오른쪽 패널을 static info에서 mechanism-change/motion-consequence/explanation scaffold로 바꾸는 연구·제품 재설계 계획 |

2026-05-14 implementation gate의 결론: P0는 별도 `Lab` tab과 `domain/application/infrastructure/ms4n` slice로 구현하되, 기존 `MechanismDesignTab`에는 read-only snapshot/trace adapter만 둔다. Project schema migration은 P1로 미루고 P0에서는 `MechanismData.layer_data["ms4n"]` bridge와 study bundle export를 사용한다.
