# mechanism_design/tab.py

import logging
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QGraphicsScene
from PyQt6.QtCore import Qt
from automataii.gui.views.editor_view import EditorView
from .state_manager import MechanismStateManager
from .ui_panel import MechanismControlPanel
from .scene_manager import MechanismSceneManager
from .animation_controller import MechanismAnimationController
from .action_handler import MechanismActionHandler
from .parametric_handler import ParametricDesignHandler

logger = logging.getLogger(__name__)

class MechanismDesignTab(QWidget):
    """
    The main widget for the Mechanism Design Tab, acting as an orchestrator.
    It initializes and connects all the specialized managers and handlers.
    """
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._is_active = False
        self._setup_managers_and_ui()
        self._connect_components()
        logger.info("MechanismDesignTab initialized with new architecture.")

    def _setup_managers_and_ui(self):
        self.scene = QGraphicsScene(self)
        self.view = EditorView(self.scene, self, mechanism_mode=True)
        
        self.state = MechanismStateManager(self)
        self.scene_manager = MechanismSceneManager(self.scene, self.state, self)
        self.animation_controller = MechanismAnimationController(self.state, self)
        self.action_handler = MechanismActionHandler(self.main_window, self.state, self.scene_manager, self)
        self.parametric_handler = ParametricDesignHandler(self.state, self.scene_manager, self)
        
        self.ui_panel = MechanismControlPanel(self)

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self.ui_panel)
        main_layout.addWidget(self.view, 1)

    def _connect_components(self):
        # --- UI actions -> Action Handler / Controllers ---
        self.ui_panel.recommendation_requested.connect(self.action_handler.handle_get_recommendations)
        self.ui_panel.play_clicked.connect(self.animation_controller.start)
        self.ui_panel.stop_clicked.connect(self.animation_controller.stop)
        self.ui_panel.reset_clicked.connect(self.animation_controller.reset)
        self.ui_panel.parametric_mode_toggled.connect(self.parametric_handler.toggle_parametric_mode)
        self.ui_panel.export_blueprint_requested.connect(self.action_handler.handle_export_blueprint)
        self.ui_panel.debug_mode_toggled.connect(self.scene_manager.toggle_debug_visuals)

        # --- UI actions -> State Manager ---
        self.ui_panel.part_selected.connect(self.state.set_selected_part)
        self.ui_panel.part_toggled.connect(self.state.toggle_part_enabled)
        self.ui_panel.mechanism_toggled.connect(self.state.toggle_mechanism_enabled)
        
        # --- State Manager -> UI Panel and Scene Manager ---
        # A single state_changed signal is now robust enough due to fixes in the UI panel
        self.state.state_changed.connect(self.ui_panel.update_ui_from_state)
        self.state.state_changed.connect(self.scene_manager.update_scene_from_state)

        # Specific signals for more complex operations
        self.state.mechanism_added.connect(self.scene_manager.add_mechanism_visuals)
        self.state.mechanisms_cleared.connect(self.scene_manager.clear_all_mechanisms)
        self.state.mechanism_layer_updated.connect(self.scene_manager.update_mechanism_visuals)

        # --- Parametric Handler Connections ---
        self.state.mechanism_layer_updated.connect(self.parametric_handler.update_on_state_change)
        self.state.mechanism_added.connect(self.parametric_handler.handle_mechanism_added)
        self.state.mechanisms_cleared.connect(self.parametric_handler.handle_mechanisms_cleared)

    # --- Public API Methods ---
    def set_path_data_from_editor(self, path_data):
        """Handles updates to path data from the editor, ensuring state consistency."""
        current_parts = set(path_data.keys()) if path_data else set()
        previous_parts = set(self.state.path_data.keys())
        
        # Determine which parts' paths were removed or changed
        parts_to_clear = previous_parts - current_parts
        for part_name in current_parts:
            if (part_name in self.state.path_data and 
                path_data.get(part_name) != self.state.path_data.get(part_name)):
                parts_to_clear.add(part_name)

        # Clear mechanisms for affected parts
        for part_name in parts_to_clear:
            self.state.clear_mechanisms_for_part(part_name)
            logger.info(f"Cleared mechanism for part '{part_name}' due to path change.")
            
        self.state.update_path_data(path_data)

    def set_parts_data(self, parts_data):
        self.state.update_parts_data(parts_data)

    def cache_initial_skeleton(self, skeleton_data):
        self.state.cache_initial_skeleton(skeleton_data)
        self.scene_manager.ensure_skeleton_visualization(skeleton_data)

    def handle_ik_update(self, ik_results):
        if self._is_active:
            self.scene_manager.update_skeleton_from_ik(ik_results)

    def clear_mechanism_data(self):
        """Clears all mechanism data and resets associated systems like IK."""
        logger.info("Clearing all mechanism data.")
        self.animation_controller.reset()
        self.state.clear_all()

    # --- Qt Event Handlers ---
    def showEvent(self, event):
        """Called when the tab becomes visible."""
        super().showEvent(event)
        self._is_active = True
        logger.info("Mechanism Design Tab is now active.")
        # Connect to expensive signals only when the tab is active
        if hasattr(self.main_window, 'kinematics_system') and self.main_window.kinematics_system:
            try:
                self.main_window.kinematics_system.pose_updated.connect(self.handle_ik_update)
            except (TypeError, RuntimeError) as e:
                logger.warning(f"Could not connect to kinematics system in showEvent: {e}")

    def hideEvent(self, event):
        """Called when the tab is hidden."""
        super().hideEvent(event)
        self._is_active = False
        self.animation_controller.stop() # Stop animation when tab is not visible
        logger.info("Mechanism Design Tab is now inactive.")
        # Disconnect from expensive signals when the tab is not visible
        if hasattr(self.main_window, 'kinematics_system') and self.main_window.kinematics_system:
            try:
                self.main_window.kinematics_system.pose_updated.disconnect(self.handle_ik_update)
            except (TypeError, RuntimeError) as e:
                logger.warning(f"Could not disconnect from kinematics system in hideEvent: {e}")

    def get_mechanism_targets(self, progress: float) -> dict:
        """
        Calculates the target positions for all active mechanisms at a given progress.
        """
        targets = {}
        # Do not proceed if the IK manager doesn't have a skeleton loaded yet.
        if not self.main_window.ik_manager or not self.main_window.ik_manager.skeleton_model:
            return targets

        time = progress * 2 * 3.14159  # Convert progress (0-1) to time (0-2pi)
        for mid, layer_data in self.state.mechanism_layers.items():
            if self.state.mechanism_enabled_state.get(mid, True):
                # Use the new method in scene_manager to get the output position
                output_pos = self.scene_manager.get_mechanism_output_position(mid, time)
                if output_pos:
                    effector_id = self.main_window.ik_manager.get_end_effector_for_part(layer_data["part_name"])
                    if effector_id:
                        targets[effector_id] = output_pos
        return targets

