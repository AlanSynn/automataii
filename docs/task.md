# 매커니즘 디자인 탭 재설계 태스크

## 목표
매커니즘 디자인 탭을 Editor Tab과 유사한 흐름으로 재구성하여, 파트의 모션 패스를 기반으로 매커니즘을 추천받고 시뮬레이션할 수 있도록 만들기

## 요구사항
1. Mechanism Layers: "Part Name - Mechanism Type" 형식으로 표시 (예: "Left arm lower - 4 Bar Linkage")
2. Target Part와 Type 선택 제거, Get Recommendations 버튼만 유지
3. Parametric Design을 2번 섹션 안으로 이동
4. Animation을 Editor Tab처럼 Play/Stop/Reset 버튼으로 구성
5. Generate Blueprint를 별도 4번 섹션으로 분리

## UI 구조 변경

### 1. Mechanism Layers (기존 유지)
- 리스트 형식으로 매커니즘 레이어 표시
- 표시 형식: "Part Name - Mechanism Type"
- 매커니즘이 없으면 파트 이름만 표시
- Enable/Disable 체크박스 유지

### 2. Mechanism Generation (간소화)
- Get Recommendations 버튼만 유지
- Parametric Design 하위 섹션 포함
  - "Select a mechanism layer to adjust parameters" 정보 레이블
  - Start Parametric Editing 버튼

### 3. Animation (Editor Tab 스타일)
- Animation status label
- Play/Stop/Reset 버튼 (Editor Tab과 동일한 디자인)
- 매커니즘이 파트를 구동하는 애니메이션

### 4. Blueprint Generation
- Generate Blueprint 버튼만 포함

### 5. View Controls (기존 유지)
- Zoom 컨트롤 버튼들

## 기능 흐름

### Get Recommendations 워크플로우
1. 사용자가 Editor Tab에서 파트 선택 및 모션 패스 정의
2. Mechanism Design Tab으로 이동
3. Get Recommendations 클릭
4. 현재 선택된 파트의 모션 패스 확인
5. MechanismRecommendationDialog 표시
6. 사용자가 매커니즘 선택 후 OK
7. 선택된 매커니즘이 씬에 추가되고 Layers 리스트에 표시

### Animation 워크플로우
1. Mechanism Layer 선택
2. Play 버튼 클릭
3. 매커니즘이 연결된 파트를 구동하는 애니메이션 재생
4. Stop으로 중지, Reset으로 초기 위치로 복귀

## 코드 수정 계획

### 1. _setup_ui() 메서드 수정
- Generation Group 간소화 (Target Part, Type 콤보박스 제거)
- Parametric Design을 Generation Group 안으로 이동
- Animation Group을 Editor Tab 스타일로 변경
- Blueprint Group을 별도 섹션으로 추가

### 2. _connect_signals() 메서드 수정
- 제거된 UI 요소들의 시그널 연결 제거
- reset 버튼 시그널 추가

### 3. _on_get_recommendations() 메서드 수정
- 현재 선택된 파트 자동 감지
- 선택된 파트의 패스 존재 여부 확인
- 패스가 없으면 경고 메시지

### 4. 애니메이션 관련 메서드 수정
- _on_start_animation(): Play 버튼 동작
- _on_stop_animation(): Stop 버튼 동작
- _on_reset_animation(): Reset 버튼 동작 (새로 추가)
- _update_animation_status(): 상태 레이블 업데이트

### 5. 레이어 관리 메서드 수정
- _add_mechanism_layer(): "Part Name - Mechanism Type" 형식으로 표시
- _on_layer_selection_changed(): 선택된 레이어에서 파트 정보 추출

## 구현 순서
1. UI 구조 변경 (_setup_ui 메서드)
2. 시그널 연결 수정 (_connect_signals 메서드)
3. Get Recommendations 로직 수정
4. Animation 컨트롤 구현
5. 레이어 표시 형식 변경
6. 테스트 및 디버깅

## 주의사항
- Editor Tab과의 일관성 유지 (버튼 스타일, 레이아웃 등)
- 기존 기능을 해치지 않으면서 점진적으로 수정
- 사용자 경험을 중심으로 한 직관적인 워크플로우 구현