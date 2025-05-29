# MainWindow.py 리팩토링 및 마이그레이션 계획

## 1. 목표

- `main_window.py` 파일의 크기를 줄이고 가독성 및 유지보수성을 향상시킨다.
- PyQt6 애플리케이션의 모듈성을 증대시킨다.
- `QAction` 및 메뉴/툴바 관리를 보다 체계적으로 개선한다.
- 각 기능별로 로직을 분리하여 관심사 분리(Separation of Concerns) 원칙을 강화한다.
- 향후 기능 확장 및 테스트 용이성을 확보한다.

## 2. 현재 문제점 분석 (`main_window.py`)

- **거대한 파일 크기**: 현재 약 3700줄 이상으로, 단일 파일에 너무 많은 책임과 코드가 집중되어 있음.
- **낮은 가독성**: 특정 기능을 찾거나 이해하기 어려움.
- **유지보수의 어려움**: 코드 수정 시 다른 부분에 미치는 영향을 파악하기 힘듦.
- **QAction 관리**: `_create_menus`, `_create_toolbar`, `_connect_ui_actions` 등에서 `QAction`이 생성, 연결되고 있으나, 관련된 로직이 분산되어 있음.
- **UI 초기화 및 연결 로직의 복잡성**: `_init_ui`와 `_connect_ui_actions` 메서드가 매우 길고 다양한 UI 요소들의 초기화와 시그널-슬롯 연결을 한 곳에서 처리하고 있음.
- **탭별 로직 혼재**: 각 탭 (Image Processing, Editor, Options) 관련 로직이 `MainWindow`에 직접 구현되어 있어, 탭별 독립성이 부족함.
- **메서드 역할 과다**: 일부 메서드 (예: `load_parts`, `_generate_mechanism_auto`)가 너무 많은 작업을 수행하고 있음.
- **데이터 관리**: `parts`, `editor_items`, `joints` 등 다양한 상태 데이터가 `MainWindow` 인스턴스 변수로 직접 관리되고 있어, 데이터 흐름 추적이 복잡할 수 있음.
- **IK 시스템 로직**: 새로운 IK 시스템 관련 데이터(`sim_joints_config`, `sim_limb_configs` 등) 및 메서드(`_initialize_new_ik_skeleton_definitions`, `_run_ik_animation_step` 등)가 `MainWindow`에 집중됨.

## 3. 리팩토링 전략 및 단계

### 3.1. 사전 준비

- **버전 관리**: Git을 사용하여 모든 변경 사항을 추적하고, 각 주요 단계별로 브랜치를 생성한다.
- **기본 테스트**: 최소한의 UI 상호작용 테스트를 준비하여 리팩토링 후 기능 회귀가 없는지 빠르게 확인할 수 있도록 한다. (가능하다면 `pytest-qt` 활용)
- **스타일 가이드 준수**: Ruff 등을 활용하여 코드 스타일 일관성을 유지한다.

### 3.2. 1단계: `QAction` 및 메뉴/툴바 관리 개선

- **목표**: `QAction`의 정의, 설정, 연결 로직을 중앙 집중화하고 모듈화한다.
- **방법**:
    1.  **`ActionManager` 클래스 생성**:
        -   `app/core/actions.py` 또는 `app/ui/actions/action_manager.py` 위치에 생성.
        -   애플리케이션 전체에서 사용될 `QAction`들을 딕셔너리 형태로 관리 (`self.actions = {'load_parts': QAction(...), ...}`).
        -   액션 생성, 단축키 설정, 아이콘 설정, 툴팁 설정 등의 로직을 포함하는 메서드 제공 (예: `create_action()`).
        -   액션 활성화/비활성화 상태 관리 메서드 제공.
    2.  **`MainWindow`에서 `ActionManager` 사용**:
        -   `MainWindow`는 `ActionManager` 인스턴스를 소유.
        -   `_create_menus` 및 `_create_toolbar` 메서드는 `ActionManager`를 통해 액션을 가져와 메뉴와 툴바에 추가하도록 수정.
        -   `_connect_ui_actions`에서 액션 관련 시그널 연결 부분을 `ActionManager` 내부 또는 `MainWindow`의 별도 메서드로 분리하여 `ActionManager`를 통해 액션 객체에 접근하여 연결.
- **기대 효과**:
    -   `QAction` 정의와 사용 분리.
    -   메뉴/툴바 생성 로직 간결화.
    -   액션 관련 코드 재사용성 증가.

### 3.3. 2단계: 탭별 로직 분리 및 UI 모듈화 심화

- **목표**: 각 탭(`ImageProcessingTab`, `EditorTab`, `OptionsTab`)이 자신의 UI 요소 및 관련 로직을 최대한 내부에서 관리하도록 한다. `MainWindow`는 탭 컨테이너 역할과 탭 간의 데이터/상태 동기화 중재자 역할에 집중한다.
- **방법**:
    1.  **`ImageProcessingTab` 개선**:
        -   현재 `MainWindow`에 있는 이미지 로드/캡처/처리, 스켈레톤 로드/편집/저장, 파츠 생성 등의 버튼 및 관련 메서드 로직을 `ImageProcessingTab`으로 이동.
        -   `ImageProcessingTab`은 필요한 `QAction` (예: `ActionManager`를 통해)을 직접 참조하거나, `MainWindow`로부터 필요한 액션만 전달받아 사용.
        -   `MainWindow`의 관련 멤버 변수 (`input_image_path`, `character_dir`, `skeleton_data` 등) 중 탭에 종속적인 것들은 `ImageProcessingTab`으로 이동. `MainWindow`는 탭 간 공유가 필요한 최소한의 데이터만 관리.
        -   시그널을 사용하여 탭의 상태 변경이나 작업 완료를 `MainWindow`에 알림 (예: `parts_generated = pyqtSignal(str)` - 파츠 정보 파일 경로 전달).
    2.  **`EditorTab` 개선**:
        -   `parts_list`, `z_value_spin`, `fixed_part_check`, 메커니즘 관련 UI 요소(콤보박스, 버튼 등), IK 애니메이션 버튼 등의 컨트롤과 관련된 로직을 `EditorTab` 내부로 최대한 이동.
        -   `MainWindow`의 `_handle_part_selection_change`, `_update_selected_part_z` 등 `EditorTab` UI와 직접적으로 관련된 메서드들을 `EditorTab`으로 이전.
        -   `EditorTab`은 `editor_view`와 `editor_scene`에 대한 강한 참조를 유지하고, 이와 관련된 상호작용을 주로 담당.
        -   `MainWindow`와의 통신은 시그널/슬롯 또는 `MainWindow`가 제공하는 인터페이스 메서드를 통해 수행.
        -   IK 시스템 관련 UI 상호작용(예: 모션 경로 정의 버튼 토글, 애니메이션 재생/중지)은 `EditorTab`에서 처리하고, 실제 IK 로직은 `MainWindow` 또는 별도의 `IKManager`를 호출.
    3.  **`OptionsTab`**: 현재 구조가 비교적 잘 분리되어 있으므로, 필요한 경우 `MainWindow`와의 인터페이스만 명확히 한다.
- **기대 효과**:
    -   `MainWindow`의 책임 감소 및 코드 단순화.
    -   각 탭의 독립성 및 재사용성 증가.
    -   탭별 기능 변경 및 확장이 용이해짐.

### 3.4. 3단계: `MainWindow`의 핵심 기능 및 데이터 관리 재정의

- **목표**: `MainWindow`를 애플리케이션의 핵심 조정자 역할로 재정의한다. 주요 데이터(파츠, 조인트 등) 관리를 위한 모델 클래스 도입을 고려한다.
- **방법**:
    1.  **데이터 모델 클래스 도입 (선택 사항, 장기적 관점)**:
        -   `app/core/models.py` 등에 `ProjectDataModel` 또는 `CharacterModel` 같은 클래스를 만들어 `parts`, `joints`, `skeleton_data` 등의 핵심 데이터를 관리.
        -   `MainWindow` 및 각 QCursortab은 이 모델을 공유하거나, 모델의 변경 알림을 받아 UI를 업데이트.
        -   이는 상당한 변경이므로, 우선 데이터 접근 메서드를 `MainWindow`에 명확히 정의하는 것부터 시작할 수 있음.
    2.  **`MainWindow`의 역할**:
        -   애플리케이션 생명주기 관리 (시작, 종료).
        -   메인 윈도우 레이아웃 및 탭 위젯 관리.
        -   `ActionManager`를 통한 전역 액션 관리 및 메뉴/툴바 설정.
        -   탭 간의 주요 데이터 흐름 조정 (예: `ImageProcessingTab`에서 파츠 생성 완료 시 `EditorTab`에 파츠 로드 신호 전달).
        -   프로젝트 저장/로드 로직 (핵심 데이터 모델을 사용한다면 모델의 직렬화/역직렬화 호출).
        -   상태 표시줄 메시지 관리.
        -   전역 설정(테마 등) 적용.
    3.  **메서드 분리 및 단순화**:
        -   `load_parts`: 파싱 로직, UI 업데이트 로직, IK 초기화 로직 등으로 분리.
        -   `_initialize_new_ik_skeleton_definitions`: 매우 복잡하므로, 여러 헬퍼 메서드로 나누거나 `IKManager` 클래스로 분리 고려.
        -   `_generate_mechanism_auto`: 메커니즘 추천 로직, UI 표시 로직 분리.
        -   `_visualize_...` 메서드들은 `EditorView` 또는 별도의 `VisualizationManager`로 이동 고려.
- **기대 효과**:
    -   `MainWindow`의 역할 명확화 및 코드베이스 간소화.
    -   데이터 관리의 일관성 및 예측 가능성 향상.
    -   테스트 용이성 증대.

### 3.5. 4단계: IK 시스템 및 시뮬레이션 로직 분리

- **목표**: IK 및 시뮬레이션 관련 로직을 `MainWindow`에서 별도의 관리 클래스(들)로 분리한다.
- **방법**:
    1.  **`IKManager` 클래스 생성**:
        -   `app/kinematics/ik_manager.py` 또는 유사 위치.
        -   `sim_joints_config`, `sim_limb_configs`, `sim_limb_lengths`, `_sim_dynamic_joints_data`, `scene_joints_snapshot` 등의 IK 관련 데이터 관리.
        -   `_initialize_new_ik_skeleton_definitions`, `_solve_single_bone_ik`, `_solve_two_bone_ik`, `_update_character_part_visuals_from_ik` 등의 메서드 이동.
        -   `MainWindow`는 `IKManager` 인스턴스를 소유하고, IK 관련 요청을 위임.
    2.  **`SimulationManager` 클래스 생성 (선택적)**:
        -   애니메이션 타이머(`ik_animation_timer`), 애니메이션 스텝(`_run_ik_animation_step`), 재생/중지/리셋 로직 등을 관리.
        -   `IKManager`와 상호작용하여 IK 계산을 요청하고, 결과를 `EditorView`나 관련 시각화 요소에 반영하도록 지시.
        -   현재 `_run_ik_animation_step`이 IK 계산과 직접적으로 연결되어 있으므로, `IKManager`가 타이머를 소유하고 애니메이션 스텝을 직접 처리하는 것도 한 방법.
- **기대 효과**:
    -   IK 및 시뮬레이션 로직의 응집도 향상.
    -   `MainWindow`의 복잡도 감소.
    -   IK 시스템의 독립적인 테스트 및 개선 용이.

### 3.6. 5단계: 유틸리티 및 헬퍼 함수 분리

- **목표**: 범용적으로 사용될 수 있는 유틸리티 함수들을 `app/utils/` 디렉토리 하위의 적절한 파일로 분리한다.
- **방법**:
    -   `transform_to_dict`, `qpainterpath_to_points`, `points_to_closed_bezier_path` 등은 이미 `utils.helpers`에 있을 수 있으나, `MainWindow` 내부에 유사한 로컬 헬퍼가 있다면 이동.
    -   2.5D 도형 생성 헬퍼 (`_create_2d_ellipse_items`, `_create_2d_rect_items` 등)는 `app/ui/widgets/shape_utils.py` 등으로 분리 가능.
- **기대 효과**:
    -   코드 재사용성 증대.
    -   `MainWindow` 코드 라인 수 감소.

## 4. 단계별 검토 및 테스트

- 각 단계 완료 후, 코드 리뷰를 수행한다.
- UI 기능 테스트를 통해 기존 기능이 올바르게 작동하는지 확인한다.
- 성능에 영향을 미칠 수 있는 변경 사항이 있는지 검토한다.

## 5. 장기적인 고려 사항

- **테스트 커버리지 확대**: `pytest`와 `pytest-qt`를 사용하여 단위 테스트 및 통합 테스트를 점진적으로 추가한다.
- **Pydantic 모델 활용**: `parts_info.json` 로드 및 프로젝트 저장/로드 시 데이터 유효성 검증 및 구조화를 위해 Pydantic 모델 사용을 고려한다.
- **상태 관리 패턴 도입**: 복잡한 UI 상태 변경이 많아지면, Flux/Redux와 유사한 단방향 데이터 흐름 패턴 또는 PyQt의 모델/뷰 프레임워크를 더 적극적으로 활용하는 방안을 검토한다.
- **C++ 확장 모듈과의 인터페이스 최적화**: `automataii.core`, `automataii.kinematics` 등 C++ 바인딩 모듈과의 데이터 교환 방식을 검토하고, 필요시 인터페이스를 개선하여 성능 및 안정성을 높인다.

---

이 계획은 제안이며, 실제 진행 상황과 코드 구조에 따라 유연하게 조정될 수 있습니다. 각 단계는 더 작은 작업으로 세분화될 수 있습니다.