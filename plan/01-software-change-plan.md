# MS4N 소프트웨어 변경 계획

## 1. 목표

Automataii를 MS4N 연구/키트 흐름에 맞게 확장한다. 핵심은 다음을 앱의 1급 개념으로 만드는 것이다.

> `MechanismChangeEpisode = before state + changed parameter + after state + motion consequence + learner explanation + breakdown/repair`

현재 앱에는 mechanism generation, path trace, blueprint export, telemetry가 이미 있으므로 새 기능은 이를 재사용하되, 연구 데이터와 키트 매핑을 위한 별도 MS4N layer를 추가한다.

## 2. 기존 코드 터치포인트

| 영역 | 현재 파일/모듈 | 현재 역할 | MS4N gap |
|---|---|---|---|
| Mechanism Foundry | `src/automataii/application/mechanism_foundry/controller.py`, `catalog.py`, `service.py` | mechanism 선택/파라미터/preview/export | kit sheet와 mechanism recipe 연결 없음 |
| Mechanism transfer | `src/automataii/application/mechanism_transfer/spec.py`, `service.py` | Foundry → Design transfer package | episode metadata, kit asset ids 없음 |
| Mechanism Design | `src/automataii/presentation/qt/tabs/mechanism_design/` | simulation, animation, parametric edit, blueprint button | before/after learning episode UI 없음 |
| Path tracing | `src/automataii/presentation/qt/tabs/mechanism_design/path_trace_manager.py` | animation trace visual buffer | persistent research trace artifact 아님 |
| Blueprint/export | `src/automataii/application/blueprint/composer.py`, `src/automataii/application/managers/blueprint_manager.py`, `src/automataii/infrastructure/generation/svg/blueprint.py` | SVG/PDF fabrication export | MS4N bundle/kit manifest/export provenance 없음 |
| Telemetry | `src/automataii/infrastructure/telemetry/telemetry.py` | generic span logging | learner episode schema 없음 |
| Camera | `src/automataii/presentation/qt/dialogs/camera_dialog.py` | capture seam | fiducial/board detection pipeline 없음 |
| Kit assets | `kit/MS4N_KIT_README.md`, `kit/ms4n-*.svg` | physical kit sheets | app runtime manifest 없음 |

## 3. 권장 아키텍처

### 3.1 새 domain package

추가 후보:

```text
src/automataii/domain/ms4n/
  __init__.py
  episodes.py
  kit_assets.py
  motion_metrics.py
  research_codes.py
```

#### `episodes.py`

순수 dataclass/value object만 둔다. Qt, SVG, filesystem 의존 금지.

```python
@dataclass(frozen=True)
class MechanismStateSnapshot:
    mechanism_id: str
    mechanism_type: str
    parameters: Mapping[str, float | str | bool]
    key_points: Mapping[str, tuple[float, float]]
    trace_ref: str | None = None

@dataclass(frozen=True)
class ChangedParameter:
    name: str
    before: float | str | bool
    after: float | str | bool
    change_type: str  # pivot, link_length, cam_profile, gear_ratio, attachment, spacer

@dataclass(frozen=True)
class MotionConsequence:
    labels: tuple[str, ...]  # wider, faster, reversed, smoother, jammed
    metrics: Mapping[str, float | bool]
    confidence: str

@dataclass(frozen=True)
class LearnerExplanation:
    text: str
    modality: str  # text, audio, worksheet, facilitator_transcript
    prompt_ids: tuple[str, ...]

@dataclass(frozen=True)
class BreakdownRepair:
    occurred: bool
    breakdown_type: str | None  # friction, collision, tolerance, overconstraint
    repair_action: str | None

@dataclass(frozen=True)
class MechanismChangeEpisode:
    episode_id: str
    session_id: str
    participant_hash: str | None
    kit_asset_ids: tuple[str, ...]
    before: MechanismStateSnapshot
    change: ChangedParameter
    after: MechanismStateSnapshot
    consequence: MotionConsequence
    explanation: LearnerExplanation | None
    breakdown_repair: BreakdownRepair | None
```

#### `motion_metrics.py`

before/after trace 비교 함수:

- path length
- bounding box width/height
- approximate area
- dominant direction change
- speed/rhythm proxy
- jam/empty trace detection
- trace similarity score

### 3.2 새 application package

```text
src/automataii/application/ms4n/
  __init__.py
  episode_service.py
  kit_catalog_service.py
  research_session_service.py
  trace_exporter.py
  fabrication_planner.py
```

#### `episode_service.py`

책임:

- before snapshot capture
- changed parameter 검증
- after snapshot capture
- motion metrics 계산
- explanation attach
- breakdown/repair attach
- final episode validation

#### `kit_catalog_service.py`

책임:

- `kit/ms4n-kit-manifest.json` 또는 packaged resource 로딩
- sheet preview path, mechanism types, compatible params 제공
- missing asset validation

Manifest 예시:

```json
{
  "schema_version": "ms4n.kit.v1",
  "assets": [
    {
      "id": "ms4n-01-linkage-bars",
      "filename": "kit/ms4n-01-linkage-bars.svg",
      "module_name_ko": "Linkage Length Lab",
      "mechanism_types": ["four_bar", "linkages"],
      "change_types": ["link_length", "pivot_position"],
      "evidence_outputs": ["trace_before", "trace_after", "path_diff", "learner_explanation"],
      "pilot_priority": "P0"
    }
  ]
}
```

#### `research_session_service.py`

책임:

- participant/group pseudonym
- consent flags
- session/task ids
- facilitator intervention log
- anonymized export 준비

#### `trace_exporter.py`

책임:

- JSONL export
- CSV coding sheet export
- media/artifact reference manifest
- no raw PII by default

#### `fabrication_planner.py`

책임:

- selected mechanism + selected kit sheet → study bundle plan
- board pitch/hole radius/checklist validation
- existing blueprint export 결과와 kit files bundle

### 3.3 infrastructure additions

```text
src/automataii/infrastructure/ms4n/
  kit_manifest_loader.py
  research_log_writer.py
  fabrication_bundle_writer.py
```

- `kit_manifest_loader.py`: JSON schema validation
- `research_log_writer.py`: append-only JSONL writer
- `fabrication_bundle_writer.py`: `README.md`, `manifest.json`, selected SVGs, blueprint SVG/PDF, trace JSON, coding sheet zip 생성

### 3.4 presentation additions

권장: 별도 tab.

```text
src/automataii/presentation/qt/tabs/lab/
  tab.py
  presenter.py
  view_protocol.py
  widgets/kit_catalog_panel.py
  widgets/episode_builder_panel.py
  widgets/trace_compare_panel.py
  widgets/explanation_prompt_panel.py
  widgets/fabrication_check_panel.py
```

왜 별도 tab인가:

- Mechanism Design tab은 이미 복잡하다.
- MS4N은 연구/학습 workflow가 핵심이라 기존 authoring UX와 목적이 다르다.
- CHI 파일럿에서는 “무엇을 기록했는지”가 명확해야 한다.

## 4. UI 변경 계획

### 4.1 Lab tab 구성

1. **Kit Catalog Panel**
   - `bar-board`, linkage, cam, crank-slider, gear, character, prompt, fabrication sheet 선택
   - P0/P1/P2 priority 표시

2. **Digital Board / Mechanism Setup**
   - bar-board grid
   - pivot/anchor point 선택
   - mechanism recipe 선택
   - manual input 우선, camera detection은 P2

3. **One-Change Episode Builder**
   - before capture
   - changed parameter 선택
   - after capture
   - consequence label 선택/자동 제안

4. **Trace Compare Panel**
   - before/after overlay
   - path metric delta
   - jam/invalid trace warning

5. **Explanation Prompt Panel**
   - “무엇을 바꿨나?”
   - “움직임이 어떻게 달라졌나?”
   - “왜 그렇게 됐나?”
   - audio ref는 P1, text는 P0

6. **Fabrication Check Panel**
   - selected kit asset checklist
   - pitch/hole/spacer/collision/tolerance notes
   - export study bundle

## 5. Telemetry / research logging

기존 `telemetry_span`은 operation diagnostics로 유지한다. MS4N 연구 데이터는 별도 JSONL로 저장한다.

### Telemetry events

```text
ms4n.session.start
ms4n.kit_asset.selected
ms4n.episode.before_captured
ms4n.episode.parameter_changed
ms4n.episode.after_captured
ms4n.episode.consequence_computed
ms4n.episode.explanation_submitted
ms4n.episode.breakdown_logged
ms4n.fabrication.bundle_exported
```

### JSONL event

```json
{
  "schema_version": "ms4n.episode.v1",
  "event_type": "episode_completed",
  "session_id": "s001",
  "episode_id": "e004",
  "participant_hash": "p_hash",
  "kit_assets": ["ms4n-01-linkage-bars"],
  "mechanism": {"id": "mech_1", "type": "four_bar"},
  "change": {"parameter": "pivot_B", "before": "C4", "after": "C5"},
  "motion_consequence": {"labels": ["wider_path"], "metrics": {"path_area_delta": 0.31}},
  "learner_explanation": {"text": "...", "modality": "text"},
  "breakdown_repair": {"occurred": false},
  "artifacts": {"trace_before": "...", "trace_after": "..."}
}
```

## 6. Fabrication / export 변경

새 action:

```text
Export MS4N Study Bundle
```

Bundle 구조:

```text
ms4n_bundle/
  README.md
  manifest.json
  kit/
    selected_sheet.svg
    bar-board.svg
  blueprint/
    mechanism_blueprint.svg
    mechanism_blueprint.pdf
  traces/
    episode_before.json
    episode_after.json
  research/
    episodes.jsonl
    coding_sheet.csv
```

기존 `BlueprintComposer`/`BlueprintExportManager`는 유지하고, MS4N bundle writer가 그 결과물을 포함한다.

## 7. 구현 마일스톤

### Phase 0 — 계획/manifest

- `plan/` 문서 확정
- `kit/ms4n-kit-manifest.json` 초안
- data schema review

### Phase 1 — Data foundation

- `domain/ms4n` dataclass 추가
- `motion_metrics` unit tests
- `application/ms4n/episode_service.py`
- JSONL export tests

### Phase 2 — UI prototype

- `Lab` tab skeleton
- Kit Catalog panel
- One-Change Episode Builder
- Explanation Prompt form

### Phase 3 — Trace integration

- existing `PathTraceManager`에서 trace points export hook 추가
- before/after compare service
- trace overlay UI

### Phase 4 — Fabrication bundle

- kit manifest loader
- fabrication checklist panel
- study bundle exporter

### Phase 5 — Pilot readiness

- anonymized export
- facilitator intervention log
- coding sheet export
- GUI smoke test

## 8. 테스트 계획

| 테스트 | 목적 |
|---|---|
| unit: `motion_metrics` | trace 비교 계산 검증 |
| unit: `MechanismChangeEpisode` validation | episode completeness 검증 |
| unit: `kit_manifest_loader` | missing file/schema error 검증 |
| integration: episode service | before-change-after-consequence-explanation flow |
| integration: bundle writer | SVG/trace/JSONL/coding sheet package 생성 |
| GUI smoke: Lab tab | tab load, kit selection, explanation form |
| golden export: JSONL/CSV | 연구 데이터 schema 안정성 |

## 9. 범위 조절 결정

P0에서는 camera/fiducial을 하지 않는다. 대신 manual board mapping + photo/video reference를 지원한다.
P1에서 optional image capture, P2에서 fiducial detection을 검토한다.
