"""
Callback Configurator for MechanismDesignTab.

Extracted from god class decomposition to consolidate all service/controller
callback configuration into a single coordinator.

Design Pattern: Configurator (handles dependency wiring)
Architecture: Hexagonal - Presentation Layer
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab


class TabCallbackConfigurator:
    """
    Consolidates callback configuration for MechanismDesignTab services and controllers.

    This class wires up all the callback dependencies between the Tab and its
    extracted services/controllers in a single location, reducing boilerplate.
    """

    def __init__(self, tab: MechanismDesignTab) -> None:
        """
        Initialize configurator with Tab reference.

        Args:
            tab: The MechanismDesignTab to configure
        """
        self._tab = tab

    def configure_all(self) -> None:
        """Configure all services and controllers with their callbacks."""
        self._configure_anchor_movement_handler()
        self._configure_skeleton_handler()
        self._configure_animation_controller()
        self._configure_animation_frame_coordinator()
        self._configure_tab_data_coordinator()
        self._configure_scene_management_service()
        self._configure_layer_selection_controller()
        self._configure_parametric_mode_controller()
        self._configure_recommendation_controller()
        self._configure_mechanism_generation_service()

    def _configure_anchor_movement_handler(self) -> None:
        """Configure callbacks for the anchor movement handler."""

        def on_params_updated_with_signal(mechanism_id: str, layer_data: dict) -> None:
            """Handle parameter updates: regenerate visuals AND emit signal for undo support."""
            # 1. Regenerate mechanism simulation for visual feedback
            self._tab.parametric_manager._regenerate_mechanism_simulation(mechanism_id, layer_data)

            # 2. Emit signal to propagate changes to StateManager (for undo/redo)
            if hasattr(self._tab, 'mechanism_parameters_changed'):
                params = layer_data.get("params", {})
                self._tab.mechanism_parameters_changed.emit(mechanism_id, dict(params))

        self._tab._anchor_movement_handler.configure_callbacks(
            on_params_updated=on_params_updated_with_signal,
            on_visuals_recreate=self._tab._recreate_mechanism_visuals,
            on_handles_update=self._tab._update_other_handles,
            on_view_refresh=self._tab.mechanism_view.update,
        )

    def _configure_skeleton_handler(self) -> None:
        """Configure callbacks for the skeleton visualization handler."""
        self._tab._skeleton_handler.configure_callbacks(
            get_main_window=lambda: self._tab.main_window,
            get_current_editor_items=lambda: self._tab.current_editor_items,
            get_parts_data=lambda: self._tab.parts_data,
            is_animation_running=self._tab._is_animation_running,
            position_parts_at_anchor_joints=self._tab._position_parts_at_anchor_joints,
        )

    def _configure_animation_controller(self) -> None:
        """Configure callbacks for the animation lifecycle controller."""
        self._tab._animation_controller.configure_callbacks(
            get_main_window=lambda: self._tab.main_window,
            get_mechanism_layers=lambda: self._tab.mechanism_layers,
            get_part_enabled_state=lambda: self._tab.part_enabled_state,
            get_parts_data=lambda: self._tab.parts_data,
            get_presenter=lambda: self._tab._presenter,
            get_ui_state_manager=lambda: self._tab.ui_state_manager,
            calculate_mechanism_output=self._tab._calculate_mechanism_output,
            update_mechanism_visuals_for_animation=self._tab._update_mechanism_visuals_for_animation,
            get_target_joint_for_mechanism_control=self._tab._get_target_joint_for_mechanism_control,
            get_standardized_joint_id=self._tab._get_standardized_joint_id,
            ensure_skeleton_visualization=self._tab._ensure_skeleton_visualization,
            setup_mechanism_ik_integration=self._tab._setup_mechanism_ik_integration,
            reset_skeleton_to_initial_state=self._tab._reset_skeleton_to_initial_state,
            position_parts_at_anchor_joints=self._tab._position_parts_at_anchor_joints,
            clear_animation_cache=self._tab._clear_animation_cache,
        )

    def _configure_animation_frame_coordinator(self) -> None:
        """Configure callbacks for the animation frame coordinator."""
        self._tab._animation_frame_coordinator.configure_callbacks(
            calculate_output=self._tab._calculate_mechanism_output,
            get_target_joint=self._tab._get_target_joint_for_mechanism_control,
            get_standardized_joint=self._tab._get_standardized_joint_id,
            update_visuals=self._tab._update_mechanism_visuals_for_animation,
            stop_timer=self._tab.animation_timer.stop,
        )

    def _configure_tab_data_coordinator(self) -> None:
        """Configure callbacks for the tab data coordinator."""
        self._tab._tab_data_coordinator.configure_callbacks(
            clear_mechanism_for_part=self._tab._clear_mechanism_for_part,
            part_has_mechanism=self._tab._part_has_mechanism,
        )

    def _configure_scene_management_service(self) -> None:
        """Configure callbacks for the scene management service."""
        self._tab._scene_management_service.configure_callbacks(
            is_visual_item_invalid=self._tab._is_visual_item_invalid,
            safe_remove_visual_items=self._tab._safe_remove_visual_items,
        )

    def _configure_layer_selection_controller(self) -> None:
        """Configure callbacks for layer selection controller."""
        self._tab._layer_selection_controller.configure_callbacks(
            get_mechanism_layers_list=lambda: self._tab.mechanism_layers_list,
            get_mechanism_layers=lambda: self._tab.mechanism_layers,
            get_path_data=lambda: self._tab.path_data,
            get_part_enabled_state=lambda: self._tab.part_enabled_state,
            get_current_editor_items=lambda: self._tab.current_editor_items,
            get_mechanism_view=lambda: self._tab.mechanism_view,
            get_scene=lambda: self._tab.mechanism_scene,
            get_parametric_mode_enabled=lambda: self._tab.parametric_mode_enabled,
            get_presenter=lambda: self._tab._presenter,
            get_presenter_view_model=lambda: self._tab._presenter_view_model,
            clear_animation_cache=self._tab._clear_animation_cache,
            reset_skeleton=self._tab._reset_skeleton_to_initial_state,
            update_parametric_handles=self._tab._update_parametric_handles_for_selection,
            hide_parametric_handles=self._tab._hide_all_parametric_handles,
            update_mechanism_layers_list=self._tab._update_mechanism_layers_list,
            update_all_ui_states=self._tab._update_all_ui_states,
            part_has_mechanism=self._tab._part_has_mechanism,
            set_selected_part_name=lambda name: setattr(self._tab, 'selected_part_name', name),
            set_part_enabled_state=lambda name, val: self._tab.part_enabled_state.__setitem__(name, val),
        )

    def _configure_parametric_mode_controller(self) -> None:
        """Configure callbacks for parametric mode controller."""
        self._tab._parametric_mode_controller.configure_callbacks(
            get_parametric_manager=lambda: self._tab.parametric_manager,
            get_parametric_editor=lambda: self._tab.parametric_editor,
            get_mechanism_layers=lambda: self._tab.mechanism_layers,
            get_presenter=lambda: self._tab._presenter,
            update_all_ui_states=self._tab._update_all_ui_states,
            set_selected_part_name=lambda name: setattr(self._tab, 'selected_part_name', name),
        )

    def _configure_recommendation_controller(self) -> None:
        """Configure callbacks for recommendation controller."""
        self._tab._recommendation_controller.configure_callbacks(
            get_path_data=lambda: self._tab.path_data,
            get_part_enabled_state=lambda: self._tab.part_enabled_state,
            get_selected_part_name=lambda: self._tab.selected_part_name,
            get_mechanism_layers_list=lambda: self._tab.mechanism_layers_list,
            get_mechanism_layers=lambda: self._tab.mechanism_layers,
            get_scene=lambda: self._tab.mechanism_scene,
            get_character_position=self._tab._get_character_position,
            tab_data_coordinator=self._tab._tab_data_coordinator,
            instantiation_service=self._tab._mechanism_instantiation,
            set_selected_part_name=lambda name: setattr(self._tab, 'selected_part_name', name),
            presenter_select_part=self._tab._mvp_presenter.select_part if self._tab._mvp_presenter else None,
            generate_mechanism_from_candidate=self._tab._generate_mechanism_from_candidate,
            add_mechanism_layer=self._tab._add_mechanism_layer,
            handle_mechanism_visuals=self._tab.handle_mechanism_visuals,
            create_4bar_visuals=lambda d: self._tab.visuals_factory.create_4bar_linkage_visuals(d, None),
        )

    def _configure_mechanism_generation_service(self) -> None:
        """Configure callbacks for mechanism generation service."""
        from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_utils import (
            convert_json_params_to_internal,
        )
        from automataii.presentation.qt.utils.geometry import qpainterpath_to_numpy_array
        self._tab._mechanism_generation_service.configure_callbacks(
            create_layer_data=self._tab._mechanism_instantiation.create_layer_data_from_candidate,
            verify_coupler=lambda ld, pd, sc: self._tab.mechanism_service.verify_coupler_joint_connection(
                ld, pd, sc, self._tab._get_scene_transform_function, self._tab._calculate_mechanism_output
            ) if hasattr(self._tab, '_initial_skeleton_data_cache') else False,
            adjust_mechanism=lambda ld, pd, sc: self._tab.mechanism_service.adjust_mechanism_to_target_joint(
                ld, pd, sc, self._tab._calculate_mechanism_output, qpainterpath_to_numpy_array
            ) if hasattr(self._tab, '_initial_skeleton_data_cache') else False,
            extract_key_points=self._tab._extract_key_points_from_simulation,
            convert_params=convert_json_params_to_internal,
        )
