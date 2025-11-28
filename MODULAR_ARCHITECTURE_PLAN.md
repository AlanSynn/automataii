# MechanismDesignTab Modular Architecture Plan

## Current State
- **File**: `src/automataii/presentation/qt/tabs/mechanism_design/tab.py`
- **LOC**: 4,431 lines
- **Functions**: 92 methods
- **Problem**: God class mixing 8+ responsibilities

## Target Architecture

```
mechanism_design/
├── __init__.py
├── tab.py                              # Thin orchestrator (~300 LOC)
├── controllers/
│   ├── __init__.py
│   ├── animation_controller.py         # Animation lifecycle (Cluster 3)
│   ├── parametric_handles_controller.py # Handle management (Cluster 7)
│   └── mechanism_generation_controller.py # Mechanism creation (Cluster 6)
├── services/
│   ├── __init__.py
│   ├── skeleton_service.py             # Skeleton handling (Cluster 2)
│   ├── transform_service.py            # Coordinate transforms (Cluster 5)
│   └── visual_management_service.py    # Visual items (Cluster 0)
└── managers/
    ├── __init__.py
    ├── data_state_manager.py           # Data/state management (Cluster 1)
    └── interaction_manager.py          # Mouse/drag interaction (Cluster 4)
```

## Module Responsibilities

### 1. AnimationController (~100 LOC)
**From Cluster 3** (cohesion: 0.225)
- `_configure_animation_controller_callbacks`
- `_is_animation_running`
- `_reset_skeleton_to_initial_state`
- `_on_start_animation`
- `_on_stop_animation`
- `_on_reset_animation`

**Interface**:
```python
class AnimationController:
    def start(self) -> None
    def stop(self) -> None
    def reset(self) -> None
    def is_running(self) -> bool
```

### 2. ParametricHandlesController (~425 LOC)
**From Cluster 7** (cohesion: 0.185)
- `_update_all_ui_states`
- `_rotate_mechanism`
- `_update_other_handles`
- `_show_free_edit_feedback`
- `_create_gear_handles`
- `_update_parametric_handles_for_selection`
- `_hide_all_parametric_handles`
- `_update_handle_positions_from_key_points`
- `_update_handle_positions_for_mechanism`

**Interface**:
```python
class ParametricHandlesController:
    def create_handles(self, mechanism_id: str, layer_data: dict) -> list[QGraphicsItem]
    def update_handle_positions(self, mechanism_id: str) -> None
    def hide_all(self) -> None
    def rotate_mechanism(self, mechanism_id: str, angle: float) -> None
```

### 3. MechanismGenerationController (~1450 LOC)
**From Cluster 6** (cohesion: 0.098)
- `_register_mechanism_controller`
- `_get_character_position`
- `_preview_mechanism`
- `_generate_mechanism_from_candidate`
- `_adjust_mechanism_to_target_joint`
- `_extract_key_points_from_simulation`
- `_calculate_mechanism_output`
- `_calculate_mechanism_output_manual`
- `_get_standardized_joint_id`
- `_update_mechanism_visuals_for_animation`
- `apply_performance_preset`
- `_generate_joint_motion_path`
- `_on_anchor_moved`
- `_get_anchor_positions_for_mechanism`

**Interface**:
```python
class MechanismGenerationController:
    def generate_from_candidate(self, candidate: dict) -> dict
    def calculate_output(self, mech_type: str, params: dict, time: float) -> QPointF
    def preview(self, mechanism_data: dict) -> None
    def update_visuals_for_animation(self, mechanism_id: str, time: float) -> None
```

### 4. SkeletonHandlingService (~375 LOC)
**From Cluster 2** (cohesion: 0.152)
- `on_skeleton_manager_updated`
- `cache_initial_skeleton`
- `on_skeleton_updated`
- `_ensure_skeleton_visualization`
- `_format_skeleton_for_visualization`
- `_convert_skeleton_data_for_animation`
- `_verify_coupler_joint_connection`
- `_safe_remove_visual_items`
- `prepare_tab_activation`
- `_is_visual_item_invalid`
- `handle_ik_update`

**Interface**:
```python
class SkeletonHandlingService:
    def update_from_manager(self, skeleton_data: dict) -> None
    def cache_initial(self, skeleton_data: dict) -> None
    def ensure_visualization(self, skeleton_data: dict) -> None
    def handle_ik_update(self, ik_results: dict) -> None
```

### 5. TransformService (~330 LOC)
**From Cluster 5** (cohesion: 0.340 - highest)
- `_handle_recommendation_selection`
- `_get_scene_transform_function`
- `_get_inverse_scene_transform_function`

**Interface**:
```python
class TransformService:
    def get_to_scene_transform(self, layer_data: dict) -> Callable
    def get_to_mechanism_transform(self, layer_data: dict) -> Callable
```

### 6. DataStateManager (~1070 LOC)
**From Cluster 1** (cohesion: 0.092)
- `_on_presenter_view_update`
- `load_generated_paths`
- `set_path_data_from_editor`
- `set_parts_data`
- `_position_parts_at_anchor_joints`
- `_update_parts_from_skeleton`
- `_clear_scene_preserve_skeleton`
- `_setup_mechanism_ik_integration`
- `clear_mechanism_data`
- `_on_get_recommendations`
- `_clear_mechanism_for_part`
- `_update_animation`
- `_display_paths_in_preview`
- `_add_control_points_for_path`
- `_update_mechanism_layers_list`
- `_clear_animation_cache`
- `cleanup_tab_resources`
- `deactivate_tab`
- `activate_tab`
- `_on_layer_selection_changed`
- `_on_layer_item_clicked`
- `_set_line_if_changed`
- `center_on_character`

**Interface**:
```python
class DataStateManager:
    def set_path_data(self, path_data: dict) -> None
    def set_parts_data(self, parts_data: dict) -> None
    def clear_all(self) -> None
    def update_layers_list(self) -> None
```

### 7. InteractionManager (~220 LOC)
**From Cluster 4** (cohesion: 0.165)
- `_get_target_joint_for_mechanism_control`
- `showEvent`
- `_create_rotation_handle`
- Inner class with mouse events
- `_disable_mechanism_visual_interaction`
- `_enable_mechanism_visual_interaction`

**Interface**:
```python
class InteractionManager:
    def create_rotation_handle(self, mechanism_id: str, center: QPointF) -> QGraphicsItem
    def enable_interaction(self) -> None
    def disable_interaction(self) -> None
```

## Extraction Order (by cohesion, highest first)

1. **TransformService** (0.340) - Cleanest extraction, pure functions
2. **AnimationController** (0.225) - Already partially extracted
3. **ParametricHandlesController** (0.185) - Handle-specific logic
4. **InteractionManager** (0.165) - UI interaction layer
5. **SkeletonHandlingService** (0.152) - Skeleton-specific logic
6. **MechanismGenerationController** (0.098) - Core generation logic
7. **DataStateManager** (0.092) - State coordination (last, most coupled)

## Delegation Pattern

The thin `tab.py` orchestrator will use **callback injection**:

```python
class MechanismDesignTab(QWidget):
    def __init__(self, ...):
        # Initialize services
        self._transform_service = TransformService()
        self._animation_controller = AnimationController(...)
        self._handles_controller = ParametricHandlesController(...)

        # Wire callbacks
        self._animation_controller.configure_callbacks(
            get_mechanism_enabled_state=lambda: self.mechanism_enabled_state,
            update_animation=self._update_animation,
        )

    # Delegate to services
    def _on_start_animation(self):
        self._animation_controller.start()
```

## Success Criteria

- [ ] Main tab.py < 500 LOC
- [ ] Each module has single responsibility
- [ ] No circular dependencies
- [ ] Golden master tests pass 100%
- [ ] All existing functionality preserved
