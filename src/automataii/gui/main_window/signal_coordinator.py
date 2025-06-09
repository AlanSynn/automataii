"""Signal connection management for the main window."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import AutomataDesigner


class SignalCoordinator:
    """Coordinates all signal connections between components."""
    
    def __init__(self, main_window: 'AutomataDesigner'):
        self.main_window = main_window
        
    def connect_all_signals(self):
        """Connect all signals between components."""
        self._connect_ui_signals()
        self._connect_tab_signals()
        self._connect_manager_signals()
        self._connect_action_signals()
        
    def _connect_ui_signals(self):
        """Connect UI-related signals."""
        # Tab widget signals
        self.main_window.tab_widget.currentChanged.connect(
            self.main_window.tab_manager.on_tab_changed
        )
        
        # Menu and toolbar setup
        self.main_window.menu_toolbar_manager.create_menus()
        self.main_window.menu_toolbar_manager.create_toolbar()
        
    def _connect_tab_signals(self):
        """Connect signals from various tabs."""
        # Landing tab
        self.main_window.landing_tab.image_selected.connect(
            self.main_window.tab_manager.handle_landing_image_selected
        )
        
        # Image processing tab
        if hasattr(self.main_window, 'project_coordinator') and self.main_window.project_coordinator:
            if hasattr(self.main_window.project_coordinator, 'handle_parts_generated_from_tab'):
                self.main_window.image_proc_tab.parts_generated.connect(
                    self.main_window.project_coordinator.handle_parts_generated_from_tab
                )
            
            if hasattr(self.main_window.project_coordinator, 'handle_skeleton_updated_from_tab'):
                self.main_window.image_proc_tab.skeleton_updated.connect(
                    self.main_window.project_coordinator.handle_skeleton_updated_from_tab
                )
        self.main_window.image_proc_tab.request_editor_tab_switch.connect(
            self.main_window.tab_manager.switch_to_editor_tab
        )
        
        # Editor tab
        self.main_window.editor_tab.request_play_simulation.connect(
            self.main_window.ik_manager.start_animation
        )
        self.main_window.editor_tab.request_stop_simulation.connect(
            self.main_window.ik_manager.stop_animation
        )
        self.main_window.editor_tab.request_reset_simulation.connect(
            self.main_window.ik_manager.reset_animation_state
        )
        if hasattr(self.main_window, 'project_coordinator') and self.main_window.project_coordinator:
            self.main_window.editor_tab.request_save_alignment.connect(
                self.main_window.project_coordinator.save_character_alignment_impl
            )
        self.main_window.editor_tab.paths_ready_for_mechanism.connect(
            self.main_window.tab_manager.handle_paths_ready_for_mechanism
        )
        
        if hasattr(self.main_window.editor_tab, "request_generate_mechanism") and hasattr(self.main_window, 'animation_coordinator') and self.main_window.animation_coordinator:
            self.main_window.editor_tab.request_generate_mechanism.connect(
                self.main_window.animation_coordinator.handle_generate_mechanism_request
            )
        
        if hasattr(self.main_window.editor_tab, "request_generate_blueprint") and hasattr(self.main_window, 'project_coordinator') and self.main_window.project_coordinator:
            self.main_window.editor_tab.request_generate_blueprint.connect(
                self.main_window.project_coordinator.generate_blueprint_impl
            )
        
        if hasattr(self.main_window.editor_tab, "request_reset_all_animations") and hasattr(self.main_window, 'animation_coordinator') and self.main_window.animation_coordinator:
            self.main_window.editor_tab.request_reset_all_animations.connect(
                self.main_window.animation_coordinator.reset_all_animations_button_clicked
            )
        
        if hasattr(self.main_window.editor_tab, "motion_path_updated") and hasattr(self.main_window, 'animation_coordinator') and self.main_window.animation_coordinator:
            self.main_window.editor_tab.motion_path_updated.connect(
                self.main_window.animation_coordinator.handle_part_motion_path_update_from_editor_tab
            )
        
        # Mechanism generation tab
        if hasattr(self.main_window, 'animation_coordinator') and self.main_window.animation_coordinator:
            self.main_window.mechanism_generation_tab.request_generate_mechanism.connect(
                self.main_window.animation_coordinator.handle_generate_mechanism_request
            )
        if hasattr(self.main_window, 'project_coordinator') and self.main_window.project_coordinator:
            self.main_window.mechanism_generation_tab.request_generate_blueprint.connect(
                self.main_window.project_coordinator.generate_blueprint_impl
            )
        self.main_window.mechanism_generation_tab.request_play_simulation.connect(
            self.main_window.ik_manager.start_animation
        )
        self.main_window.mechanism_generation_tab.request_stop_simulation.connect(
            self.main_window.ik_manager.stop_animation
        )
        self.main_window.mechanism_generation_tab.request_reset_simulation.connect(
            self.main_window.ik_manager.reset_animation_state
        )
        
        # Options tab
        self.main_window.options_tab.animationDurationChanged.connect(
            self.main_window.ik_manager.set_animation_duration
        )
        if hasattr(self.main_window, 'theme_manager') and self.main_window.theme_manager:
            self.main_window.options_tab.themeChanged.connect(
                self.main_window.theme_manager.apply_theme
            )
        if hasattr(self.main_window, 'menu_toolbar_manager') and self.main_window.menu_toolbar_manager:
            self.main_window.options_tab.toolbarVisibilityChanged.connect(
                self.main_window.menu_toolbar_manager.toggle_toolbar_visibility
            )
        self.main_window.options_tab.partPropertiesVisibilityChanged.connect(
            self._toggle_part_properties_visibility
        )
        self.main_window.options_tab.setting_changed.connect(
            self._handle_option_change
        )
        
        # Connect advanced processing visibility toggle
        if hasattr(self.main_window.options_tab, "advancedProcessingVisibilityChanged"):
            if hasattr(self.main_window.image_proc_tab, "_toggle_detailed_processing_visibility"):
                self.main_window.options_tab.advancedProcessingVisibilityChanged.connect(
                    self.main_window.image_proc_tab._toggle_detailed_processing_visibility
                )
        
        # Connect unit changed signal
        if hasattr(self.main_window.options_tab, "unitChanged") and hasattr(self.main_window, 'theme_manager') and self.main_window.theme_manager:
            self.main_window.options_tab.unitChanged.connect(
                self.main_window.theme_manager.handle_unit_changed
            )
        
    def _connect_manager_signals(self):
        """Connect signals from various managers."""
        # ProjectDataManager signals
        if self.main_window.project_data_manager and hasattr(self.main_window, 'project_coordinator') and self.main_window.project_coordinator:
            self.main_window.project_data_manager.project_data_loaded.connect(
                self.main_window.project_coordinator.handle_project_data_loaded
            )
            self.main_window.project_data_manager.project_data_cleared.connect(
                self.main_window.project_coordinator.handle_project_data_cleared
            )
            self.main_window.project_data_manager.error_occurred.connect(
                self.main_window.project_coordinator.handle_project_manager_error
            )
        
        # SkeletonManager signals
        if self.main_window.skeleton_manager and hasattr(self.main_window, 'animation_coordinator') and self.main_window.animation_coordinator:
            self.main_window.skeleton_manager.skeleton_updated.connect(
                self.main_window.animation_coordinator.on_skeleton_manager_updated
            )
            
            # Connect to IKManager
            if self.main_window.ik_manager:
                self.main_window.skeleton_manager.skeleton_updated.connect(
                    self.main_window.ik_manager.on_skeleton_data_updated_from_manager
                )
        
        # IKManager signals
        if self.main_window.ik_manager and hasattr(self.main_window, 'animation_coordinator') and self.main_window.animation_coordinator:
            self.main_window.ik_manager.character_visuals_updated.connect(
                self.main_window.animation_coordinator.handle_ik_visuals_update
            )
            
            if hasattr(self.main_window.ik_manager, "animation_state_changed"):
                self.main_window.ik_manager.animation_state_changed.connect(
                    self.main_window.editor_tab.on_simulation_state_changed
                )
                self.main_window.ik_manager.animation_state_changed.connect(
                    self.main_window.mechanism_generation_tab.on_simulation_state_changed
                )
            
            if hasattr(self.main_window.ik_manager, "skeleton_pose_updated"):
                self.main_window.ik_manager.skeleton_pose_updated.connect(
                    self.main_window.animation_coordinator.handle_skeleton_pose_updated_from_ik
                )
        
        # MechanismManager signals
        if self.main_window.mechanism_manager and hasattr(self.main_window.mechanism_manager, "mechanism_visuals_ready"):
            if hasattr(self.main_window.editor_tab, "handle_mechanism_visuals"):
                self.main_window.mechanism_manager.mechanism_visuals_ready.connect(
                    self.main_window.editor_tab.handle_mechanism_visuals
                )
    
    def _connect_action_signals(self):
        """Connect menu and toolbar actions."""
        am = self.main_window.action_manager
        
        am.connect_action("load_parts", self.main_window.load_parts_dialog)
        am.connect_action("save_project", self.main_window.save_project_dialog)
        am.connect_action("exit", self.main_window.close)
        am.connect_action("about", self.main_window.show_about_dialog)
        
        # View actions
        am.connect_action("zoom_in", lambda: self._handle_view_action("zoom_in"))
        am.connect_action("zoom_out", lambda: self._handle_view_action("zoom_out"))
        am.connect_action("zoom_fit", lambda: self._handle_view_action("zoom_to_fit"))
        am.connect_action("reset_view", lambda: self._handle_view_action("reset_view"))
        am.connect_action("undo", lambda: self._handle_view_action("undo"))
        am.connect_action("redo", lambda: self._handle_view_action("redo"))
    
    def _handle_view_action(self, action: str):
        """Handle view-related actions for the current tab."""
        if self.main_window.tab_widget.currentWidget() == self.main_window.editor_tab:
            view = self.main_window.editor_tab.editor_view
            if view:
                getattr(view, action)()
    
    def _toggle_part_properties_visibility(self, visible: bool):
        """Toggle the visibility of part properties panel."""
        if hasattr(self.main_window.editor_tab, "toggle_part_properties_panel_visibility"):
            self.main_window.editor_tab.toggle_part_properties_panel_visibility(visible)
            logging.info(f"Part properties panel visibility set to: {visible}")
    
    def _handle_option_change(self, setting_name: str, value):
        """Handle generic setting changes from options tab."""
        logging.info(f"Option changed: {setting_name} = {value}")
        
        if setting_name == "theme":
            if hasattr(self.main_window, 'theme_manager') and self.main_window.theme_manager:
                self.main_window.theme_manager.apply_theme(str(value))
        elif setting_name == "animation_duration":
            if self.main_window.ik_manager:
                self.main_window.ik_manager.set_animation_duration(int(float(value) * 1000))
        elif setting_name == "toolbar_visibility":
            if hasattr(self.main_window, 'menu_toolbar_manager') and self.main_window.menu_toolbar_manager:
                self.main_window.menu_toolbar_manager.toggle_toolbar_visibility(bool(value))
        elif setting_name == "part_properties_visibility":
            self._toggle_part_properties_visibility(bool(value))
        elif setting_name == "unit_system":
            if hasattr(self.main_window, 'theme_manager') and self.main_window.theme_manager:
                self.main_window.theme_manager.handle_unit_changed(str(value))
        elif setting_name == "debug_mode":
            if hasattr(self.main_window.image_proc_tab, "set_debug_mode"):
                self.main_window.image_proc_tab.set_debug_mode(bool(value))
        else:
            logging.warning(f"Unhandled option change: {setting_name}")