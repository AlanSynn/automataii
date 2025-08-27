Mechanism Tab – Real‑Time Simulation Performance PRD

작성자: Automataii Team (owner: Alan Synn)
대상 영역: `MechanismDesignTab` (UI/시뮬/렌더), `EditorView` (QGraphicsView), IK 파이프라인 연동
문서 목적: 메커니즘 탭 실시간 시뮬레이션 성능 저하 문제를 해결하기 위한 목표/지표/아키텍처/로드맵 제시

문제 배경
- 현상: 메커니즘 탭에서 애니메이션 재생 시 프레임 드랍, UI 렉, 팬/줌 지연 발생.
- 원인 후보:
  - 메인 UI 스레드에서 모든 계산/렌더/IK 타겟 업데이트를 동시 수행.
  - 프레임마다 다수의 `QGraphicsItem` 속성 변경(라인/폴리곤/원/패스) → 빈번한 재도색 및 인덱싱 비용.
  - Trace path 점 누적 시 `QPainterPath` 재구성 비용과 씬 업데이트 과다.
  - `QGraphicsView` 설정(FullViewportUpdate, 안티에일리어싱)으로 인한 오버헤드.
  - 다수 메커니즘 동시 업데이트, 필요 없는 오브젝트까지 매 프레임 갱신.
  - IK Solver까지 매 프레임 호출 → 체인 길이에 비례해 고비용.

목표(Goals)
- 사용자 체감 성능: 일반 맥북/노트북 환경에서 1080p, 1–3 메커니즘 활성 시
  - Balanced 모드: 45–60 FPS 유지, 팬/줌 조작 즉시 반응(입력-응답 < 50ms)
  - Fast 모드: 60 FPS 안정 + Trace/디테일 제한(고정 16.6ms budget)
- 확장성: 5+ 메커니즘 동시 활성에서도 30 FPS 이상 유지(시각 품질 일부 저하 허용)
- 안정성: 탭 전환/비활성 시 연산 중단(불필요한 CPU 사용 제거)

비목표(Non-Goals)
- QML/SceneGraph로의 대규모 마이그레이션(장기 검토), GPU 전용 커스텀 렌더러 도입.
- 모든 메커니즘 물리 시뮬의 고정밀 근사(목표는 인터랙티브 편집 성능 향상).

핵심 사용자 시나리오
- S1: 4bar/cam/gear 메커니즘 1–3개를 켜고, 파라미터 슬라이더를 조정하며 프리뷰.
- S2: 파트 선택/이동/줌/팬을 빠르게 반복.
- S3: Trace 경로 시각화 on/off 전환하면서 차이 비교.

성공 지표(성능/안정성)
- FPS: Balanced 모드 45+ FPS(평균), 1% Low ≥ 30 FPS.
- 입력 지연: 팬/줌/선택 응답 < 50ms.
- CPU 점유: 4코어 노트북 기준 평균 < 120% (멀티스레드 포함), 피크 < 200%.
- Drop frame rate: 5% 이하.
- 회귀 없음: 기존 기능/정확도(경로/IK 결과) 유지.

현재 아키텍처/핫스팟 요약
- 타이머: `QTimer.start(33)` ~30 FPS, `_update_animation`에서 모든 메커니즘 순회.
- 렌더: `EditorView`가 `FullViewportUpdate` + 안티에일리어싱.
- 씬 업데이트: 프레임마다 다수 `setLine/setRect/setPolygon/setPath` 호출.
- Trace: 매 프레임 `QPainterPath` 재생성 + setPath 호출, max_points=1000.
- IK 연동: 매 프레임 각 파트 target joint -> IKManager → FABRIK 호출.

제안 아키텍처(요지)
1) 렌더/시뮬 분리 + 프레임 스키핑
- 시뮬(계산)과 렌더(뷰 업데이트) 주기를 분리. 예: 시뮬 60Hz 내부 스텝, 렌더 30–60Hz.
- 메커니즘 N개일 때 라운드로빈/샘플링으로 프레임 스키핑(모든 메커니즘을 매 프레임 업데이트하지 않음).
- “마지막 계산 결과”만 UI 쓰레드에서 반영(드롭 가능한 프레임은 버림, 최신값만 적용).

2) UI 스레드 오프로드
- 계산 스레드(Worker, `QThread`/`concurrent.futures`)에서 메커니즘 포즈/트래킹 포인트 선계산.
- GUI 스레드 → 오직 최소한의 `QGraphicsItem` 속성 변경만 수행(배치 업데이트).

3) QGraphics 최적화
- `EditorView` 설정 변경:
  - `setViewportUpdateMode(MinimalViewportUpdate 또는 BoundingRectViewportUpdate)`
  - 성능 모드에서 `setRenderHint(Antialiasing, False)`
  - OpenGL 가속: `setViewport(QOpenGLWidget())` 옵션 제공(플래그 기반, 호환성 대비)
- `QGraphicsScene` 인덱싱:
  - 동적 오브젝트 많을 때 `setItemIndexMethod(QGraphicsScene.NoIndex)` 검토
  - 또는 BspTreeIndex vs NoIndex A/B 측정 뒤 선택

4) Trace/Path 업데이트 절감
- Trace decimation: 매 프레임 → N프레임에 1번만 path 갱신(예: stride=2~4)
- 점 수 cap 동적: 화면 배율/속도 따라 max_points를 250–500으로 자동 조정
- 구간 분할 업데이트: path 전체 재구성 대신 “append only” + 주기적 리빌드

5) LOD(수준별 디테일)
- Fast/Balanced/High 3단 프리셋:
  - Fast: 안티에일리어싱 off, 업데이트 stride↑, trace off(기본), IK 15–30Hz
  - Balanced: 안티에일리어싱 on, stride 중간, trace 250pts, IK 30Hz
  - High: 안티에일리어싱 on, stride=1, trace 500–1000pts, IK 60Hz(선택)
- 미가시/미선택 메커니즘은 업데이트 주기 늘리기(예: 비활성층 10–15 FPS 제한)

6) IK 호출 최적화
- 목표 위치 변화량이 epsilon 미만이면 해당 체인 solve 스킵(early out)
- 동일 프레임 내 중복 체인 업데이트 합치기(이미 있음 → 추가로 epsilon 적용)
- IK 해 풀기 빈도 제한: 렌더 프레임과 분리해 15–30Hz 고정(가시성/선택 상태에 따라 가변)

7) 데이터/함수 호출 최적화
- `to_scene_coords`/params lookup 등 per‑item 반복 조회 캐싱.
- numpy 배열에서 프레임 인덱싱 시 bounds clamping, reverse_direction 처리 등 비용 최소화.
- QGraphics 변경 전 구 값과 비교하여 “의미 있는 변화”일 때만 setLine/setRect 호출.

8) 탭/뷰 상태 최적화
- 탭 비활성/백그라운드 시 타이머 완전 정지(이미 일부 구현) + Worker 스레드도 슬립.
- 줌 아웃 상태에서 미세 업데이트 중단(픽셀 이동량 < 0.5px이면 스킵).

리스크/제약
- 스레딩: Qt 객체(UI) 접근은 GUI 스레드에서만 → 데이터 복사/락 정책 필요.
- OpenGL: 일부 환경/드라이버 호환성 이슈 → 옵션 플래그/자동 fallback 제공.
- 품질/정확도: decimation/stride 적용 시 시각적 정확도 저하 가능 → High 모드 보장.

측정/프로파일링 계획
- 타이머/프레임 측정: `_update_animation()`와 렌더 후킹에 `QElapsedTimer` 추가(옵션)
- 지표 수집: 평균 프레임 타임, 1%/5% low, IK 호출 횟수/스킵율, 씬 업데이트 수
- UI: 상태바/개발자 모드에서 FPS/업데이트 카운터 토글 표시
- A/B 실험: ViewportUpdateMode/Scene Indexing 조합별 비교

사용자 노출 옵션(설정/토글)
- Performance Preset: Fast / Balanced / High
- Show Trace: On/Off (Fast에서 기본 Off)
- OpenGL Acceleration: On/Off (실험적)
- IK Update Rate: Auto(기본) / 15 / 30 / 60 Hz

기술 구현 단계(로드맵)

Phase 0 — Quick Wins (~0.5–1일)
- EditorView 옵션 추가: `MinimalViewportUpdate`(기본), Fast 프리셋에서 안티에일리어싱 Off.
- Trace stride 도입: 기본 stride=2, max_points=500.
- 탭 비활성 시 모든 타이머/스레드 정지 강제.

Phase 1 — 구조 개선 (~2–3일)
- Render/Sim 분리: 내부 fixed step(예: 60Hz) + 렌더 30–60Hz, 최신값만 UI 반영.
- IK 업데이트 스로틀링: 15–30Hz로 제한(프리셋 연동) + epsilon 기반 스킵.
- QGraphics 변경 전 변화량 체크(동일 값 set 방지) + 배치 적용(씬 업데이트 coalesce).
- Scene Indexing 정책 옵션화(NoIndex vs BspTreeIndex) 및 기본값 선택.

Phase 2 — 고급 최적화 (~3–5일)
- OpenGL 뷰포트 옵션 제공 및 호환성 처리.
- Worker 스레드 도입: 메커니즘 포즈/경로 계산 전용, UI 스레드에는 snapshot만 전달.
- 비가시 메커니즘/오프스크린 culling(뷰포트 밖이면 업데이트 주기 drop).

Phase 3 — 장기 개선(선택)
- NumPy/Numba 최적화 또는 C++ 확장(핵심 수학 루프) 도입.
- Qt Quick/SceneGraph 기반 렌더링으로 이행 검토.

코드 변경 가이드(핵심 지점)
- `src/automataii/gui/views/editor_view.py`
  - `setViewportUpdateMode(MinimalViewportUpdate)` 기본화, 프리셋 따라 AA on/off.
  - (옵션) `setViewport(QOpenGLWidget())` 토글 추가.
- `src/automataii/gui/tabs/mechanism_design_tab.py`
  - `_update_animation`: 프레임 스키핑/stride/epsilon 스킵 적용, render/sim 분리 구조 반영.
  - Trace: stride와 점수 cap 동적 제어, append-only 경량 업데이트.
  - IK: update rate/throttle 적용 및 변화량 체크 후 호출.
  - 탭 활성/비활성 상태에서 타이머 관리 강화.
- `MechanismDesignTabLayout`
  - `QGraphicsScene.setItemIndexMethod(...)` 정책 옵션화.

릴리즈 플랜
- 1차(Phase 0+1): Fast/Balanced 프리셋 + 기본 최적화 반영, 실사용 수집.
- 2차(Phase 2): OpenGL/Worker 옵션 추가, 호환성 피드백 반영.
- 3차: 필요시 Numba/네이티브 확장 검토.

테스트 시나리오
- 1–5 메커니즘 조합, Trace on/off, 각 프리셋별 FPS & 입력 지연 측정.
- 확대/축소 × 4배, 대형 Path/많은 포인트, 빠른 파라미터 드래그.
- macOS/Windows 혼합, OpenGL on/off 호환성 체크.

리스크 완화
- 모든 실험적 기능은 설정 토글/프리셋 뒤에 배치.
- 장애/성능 회귀 시 프리셋 한 단계 다운그레이드로 즉시 회피 가능.

요약
- 핵심은 “최신 스냅샷만 반영, 불필요한 프레임/업데이트 제거, UI 스레드 부담 최소화”입니다.
- 위 단계별 조치로 즉시 체감 성능을 확보하고, 점진적으로 구조적 최적화를 도입합니다.

