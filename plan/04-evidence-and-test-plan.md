# MS4N Evidence and Test Plan

## 1. 목적

이 문서는 두 가지 검증을 동시에 다룬다.

1. **연구 evidence 검증**: MS4N이 어떤 episode를 남기며, 어떤 claim을 뒷받침할 수 있는가.
2. **소프트웨어/키트 검증**: 구현 후 어떤 테스트가 있어야 data와 fabrication export를 신뢰할 수 있는가.

## 2. Mechanism Change Episode schema

필수 필드:

```yaml
schema_version: ms4n.episode.v1
episode_id: string
session_id: string
participant_hash: string | null
started_at: iso_datetime
completed_at: iso_datetime | null
kit_assets:
  - asset_id
mechanism:
  id: string
  type: string
before_state:
  parameters: object
  key_points: object
  trace_ref: string | null
change:
  change_type: string
  parameter: string
  before: scalar
  after: scalar
after_state:
  parameters: object
  key_points: object
  trace_ref: string | null
motion_consequence:
  labels: list[string]
  metrics: object
learner_explanation:
  modality: text|audio|worksheet|facilitator_transcript
  text_or_ref: string
  prompt_ids: list[string]
breakdown_repair:
  occurred: boolean
  breakdown_type: string | null
  repair_action: string | null
facilitator:
  intervention_occurred: boolean
  intervention_type: string | null
artifacts:
  photos: list[string]
  videos: list[string]
  blueprint: string | null
  worksheet: string | null
```

## 3. Data capture checklist

### 매 episode마다 필수

- [ ] before state 저장
- [ ] changed parameter가 하나인지 확인
- [ ] after state 저장
- [ ] trace before/after 또는 관찰 메모 저장
- [ ] motion consequence label 저장
- [ ] learner explanation 저장
- [ ] facilitator intervention 여부 저장
- [ ] breakdown/repair 여부 저장

### physical kit 사용 시 추가

- [ ] 사용한 sheet/parts id
- [ ] board coordinate 또는 manual physical setup note
- [ ] fabrication check 결과
- [ ] jam/collision/friction/tolerance tag
- [ ] repair action
- [ ] final artifact photo/video reference

## 4. Claim-evidence ledger

| Claim | 최소 evidence | 충분 evidence | 금지 claim |
|---|---|---|---|
| explanation opportunities가 생긴다 | prompt response + trace | before/after + video + explanation + interview | understanding improved |
| one-change rule이 causal reasoning을 돕는다 | one parameter changed + explanation | multiple episodes showing prediction/comparison | better learning without comparison |
| fabrication check가 repair reasoning을 만든다 | warning + repair note | warning + physical failure/repair + explanation | reduces failures statistically |
| trace comparison supports reflection | trace overlay viewed + explanation | trace used in redesign decision | trace improves accuracy |
| teacher/facilitator scaffold가 유용하다 | intervention log | intervention-before/after behavior | teachers prefer MS4N unless surveyed |

## 5. Coding scheme

### Change type

- `pivot_position`
- `link_length`
- `cam_profile`
- `gear_ratio`
- `connection_point`
- `character_attachment`
- `spacer_material`
- `fabrication_repair`

### Motion consequence

- `amplitude_increased`
- `amplitude_decreased`
- `path_widened`
- `path_narrowed`
- `direction_reversed`
- `speed_changed`
- `rhythm_changed`
- `smoother`
- `jerkier`
- `jammed`
- `no_visible_change`

### Explanation quality

| Code | 설명 |
|---|---|
| `none` | 설명 없음 |
| `descriptive` | 결과만 말함 |
| `change_result_link` | 변경과 결과를 연결 |
| `mechanism_causal` | 기계 원리 포함 |
| `predictive` | 다음 변경/대안 예측 포함 |
| `incorrect_but_causal` | 틀렸지만 causal 가설 있음 |
| `evidence_backed` | trace/physical evidence를 지칭 |

### Breakdown type

- `friction`
- `collision`
- `loose_joint`
- `overconstrained`
- `misalignment`
- `material_bending`
- `sensor_or_detection_failure`
- `software_model_mismatch`

### Repair action

- `move_pivot`
- `change_link_length`
- `change_cam`
- `add_spacer`
- `reduce_load`
- `change_attachment`
- `simplify_mechanism`
- `manual_override`

## 6. Reliability plan

- pilot data 20–25%를 두 coder가 독립 코딩
- codebook ambiguity memo 작성
- disagreement resolution meeting 기록
- main coding 전 codebook freeze
- 정량 신뢰도 보고 가능 시 Cohen’s kappa 또는 percent agreement 보고
- qualitative claims는 representative episode vignette로 grounded evidence 제공

## 7. 소프트웨어 테스트 계획

### Unit tests

| 대상 | 테스트 |
|---|---|
| `domain/ms4n/episodes.py` | required fields, immutability, serialization round-trip |
| `motion_metrics.py` | empty trace, identical trace, widened path, reversed direction |
| `kit_assets.py` | missing file, invalid mechanism type, duplicate asset id |
| `research_codes.py` | allowed code validation |

### Application tests

| 대상 | 테스트 |
|---|---|
| `episode_service.py` | before → change → after → consequence → explanation complete flow |
| `kit_catalog_service.py` | manifest load, asset existence, priority filter |
| `trace_exporter.py` | JSONL append, CSV coding sheet export, anonymized participant hash |
| `fabrication_planner.py` | selected sheet + blueprint + trace bundle manifest |

### Integration tests

- Foundry mechanism selected → MS4N episode starts
- Mechanism Design trace points → before/after export
- Blueprint export → MS4N bundle contains SVG/PDF/manifest
- Telemetry event emitted without PII

### GUI smoke tests

- Lab tab loads
- kit asset selected
- one-change episode form completed
- explanation saved
- export bundle dialog opens

### Golden files

- `tests/fixtures/ms4n/episode_completed.jsonl`
- `tests/fixtures/ms4n/coding_sheet.csv`
- `tests/fixtures/ms4n/bundle_manifest.json`

## 8. Fresh verification for current planning artifacts

현재 문서 단계에서 검증해야 할 것:

- [ ] `plan/` 아래 6개 Markdown 파일 존재
- [ ] 각 파일이 비어 있지 않음
- [ ] `kit/ms4n-*.svg` 8개 존재
- [ ] `kit/generate_ms4n_kit.py` 재생성 가능
- [ ] XML parse/render 검증 가능
- [ ] 계획 문서가 source path와 kit asset을 명시

## 9. 제출 전 evidence gate

CHI submission 전:

- [ ] participant count / setting / dates / procedure 작성
- [ ] IRB/ethics note 작성
- [ ] claim-evidence ledger 업데이트
- [ ] related work matrix citation 검증
- [ ] 3–5 episode vignette 작성
- [ ] failure/repair taxonomy 결과 포함
- [ ] supplementary artifact bundle 준비
