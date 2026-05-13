# MS4N Review Gate and Risk Register

## 1. 현재 팀 리뷰 판정

초기 critic review verdict:

- Recommendation: **REQUEST CHANGES**
- Architectural status: **BLOCK**
- 주요 blocker: `plan/` 디렉토리에 사용자 요청 산출물이 없었음.

이 문서 세트는 그 blocker를 해결하기 위해 작성되었다.

Post-fix target verdict:

- Recommendation: **APPROVE** once all six `plan/` artifacts pass file/content verification.
- Architectural status: **CLEAR** for planning scope only; implementation remains gated by the software/test plan.

## 2. Review gate

### Gate A — 계획 문서 complete

통과 조건:

- [ ] `plan/00-ms4n-plan-index.md`
- [ ] `plan/01-software-change-plan.md`
- [ ] `plan/02-wow-kit-module-plan.md`
- [ ] `plan/03-chi-hci-research-plan.md`
- [ ] `plan/04-evidence-and-test-plan.md`
- [ ] `plan/05-review-gate-and-risk-register.md`

### Gate B — software implementation readiness

통과 조건:

- [ ] `MechanismChangeEpisode` schema 확정
- [ ] kit manifest schema 확정
- [ ] MS4N Lab tab vs existing tab integration decision 확정
- [ ] P0/P1/P2 feature scope 확정
- [ ] test plan accepted

### Gate C — CHI research readiness

통과 조건:

- [ ] RQs 확정
- [ ] study protocol 작성
- [ ] participant/recruitment plan 작성
- [ ] IRB/ethics path 확인
- [ ] codebook 초안 작성
- [ ] facilitator script 작성
- [ ] claim-evidence ledger 작성

### Gate D — pilot readiness

통과 조건:

- [ ] kit 조립 시간 확인
- [ ] trace capture 작동
- [ ] explanation prompt 저장
- [ ] JSONL export 작동
- [ ] physical failure logging 가능
- [ ] facilitator intervention log 가능

## 3. Risk register

| Risk | Severity | Likelihood | Trigger | Mitigation | Owner |
|---|---:|---:|---|---|---|
| 10개 kit module을 모두 구현하려다 범위 폭발 | High | High | P0에 camera/AI/gear/storyboard 모두 포함 | P0는 linkage+trace+fabrication 중심 | PI/engineering |
| camera/fiducial demo 실패 | High | Medium | 조명/가림/캘리브레이션 실패 | P0 manual mapping, P1 photo attach, P2 fiducial | engineering |
| trace가 연구 evidence로 부족 | High | Medium | trace만 있고 설명/영상/맥락 없음 | episode schema에 explanation, facilitator, artifact refs 필수 | research |
| learning gain 과장 | High | Medium | pre/post 없이 improves claim | characterize/derive/identify language 사용 | writing |
| fabrication failures가 세션을 망침 | Medium | High | jam/friction으로 task 중단 | Jam Detective로 failure를 data로 전환, backup examples | kit |
| facilitator effect와 system effect 혼재 | Medium | High | facilitator가 정답을 대신 줌 | intervention log와 facilitator script | research |
| privacy/IRB 문제 | High | Medium | minors/video/audio 사용 | consent 분리, anonymized export, ethics note | research |
| 기존 Mechanism Design tab 복잡도 증가 | Medium | Medium | MS4N UI를 기존 tab에 계속 삽입 | 별도 MS4N Lab tab | engineering |
| worksheet studio가 gimmick화 | Medium | Medium | 예쁜 포스터만 생성 | evidence picker와 episode refs 필수 | design |
| Gear Mood Dial이 감성 라벨 놀이로 흐름 | Medium | Medium | mood만 있고 ratio evidence 없음 | ratio/speed/direction 로그 필수 | design |
| Storyboard가 mechanism variable을 흐림 | Medium | Medium | narrative만 있고 one-change 없음 | attachment point one-change rule | design |
| 데이터 export가 분석 불가능 | High | Medium | schema drift, missing fields | golden JSONL/CSV tests | engineering |

## 4. Anti-gimmick checklist

모든 wow feature는 아래를 통과해야 한다.

- [ ] 어떤 기계적 변경을 다루는가?
- [ ] 어떤 motion consequence를 생성/관찰하는가?
- [ ] 학생이 어떤 prompt에 답하는가?
- [ ] trace/log/worksheet/video 중 어떤 evidence가 남는가?
- [ ] 실패했을 때 repair episode로 전환되는가?
- [ ] manual fallback이 있는가?
- [ ] CHI contribution 문장과 직접 연결되는가?

## 5. Software scope decision

### 승인

- `MS4N Lab` 별도 tab
- `domain/application/infrastructure/ms4n` 신규 package
- JSONL/CSV research export
- kit manifest loader
- before/after trace compare
- fabrication bundle writer

### 보류

- real-time camera/fiducial board detection
- AI explanation scoring/clustering
- multi-classroom dashboard
- smart sensor modules
- full inverse design recommendation

## 6. Research claim decision

### 허용 claim

- MS4N exposes explanation opportunities.
- MS4N helps structure mechanism-change episodes.
- We characterize novice breakdown and repair patterns.
- We derive design considerations for mechanism-first creative STEM toolkits.

### 금지 claim / forbidden claim unless evidence exists

- MS4N improves learning.
- MS4N improves creativity.
- MS4N reduces fabrication failure.
- MS4N is better than existing systems.
- Novices can easily build automata with MS4N.

## 7. Reviewer objection 대비

| 예상 objection | 대응 |
|---|---|
| “좋은 키트 데모일 뿐 HCI 지식이 약하다” | design principles + episode taxonomy + failure/repair analysis |
| “기존 automata kit와 차이가 불명확하다” | related work matrix에서 mechanism-change evidence unit 강조 |
| “시스템이 너무 많아 어떤 요소가 효과인지 모른다” | P0 one-change + trace + fabrication으로 범위 제한 |
| “데이터가 anecdotal이다” | episode schema, codebook, reliability plan, triangulation |
| “physical fabrication variance가 너무 크다” | variance를 breakdown/repair evidence로 분석하되 reliability metrics도 수집 |
| “privacy/ethics가 약하다” | IRB note, consent separation, anonymized export |

## 8. 다음 실행 순서

1. plan docs review
2. `kit/ms4n-kit-manifest.json` 작성
3. `domain/ms4n` dataclass + tests
4. `application/ms4n` episode service + exporter
5. MS4N Lab tab skeleton
6. trace comparison MVP
7. fabrication bundle MVP
8. pilot protocol and facilitator script
