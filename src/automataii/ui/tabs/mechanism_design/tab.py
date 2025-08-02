# mechanism_design/tab.py

import logging

from PyQt6.QtWidgets import QGraphicsScene, QHBoxLayout

from automataii.ui.tabs.base.tab import BaseTab
from automataii.ui.views.editor.view import EditorView
from automataii.core.event_bus import EventBus
from automataii.services.simulation_service import SimulationService
from automataii.services.blueprint_service import BlueprintService
from automataii.services.character_design_service import CharacterDesignService
from automataii.services.anchor_positioning_service import AnchorPositioningService
from automataii.services.base_generation_service import BaseGenerationService
from automataii.services.force_analysis_service import ForceAnalysisService

from .action_handler_enhanced import EnhancedMechanismActionHandler
from .animation_controller import MechanismAnimationController
from .parametric_handler import ParametricDesignHandler
from .scene_manager import MechanismSceneManager
from .state_manager import MechanismStateManager
from .ui_panel_enhanced import EnhancedMechanismControlPanel

logger = logging.getLogger(__name__)


class MechanismDesignTab(BaseTab):
    """
    Enhanced Mechanism Design Tab with Disney Research-style computational character design.
    
    Implements Gemini's strategic architecture for manufacturing-grade mechanism design:
    - Physics-validated design workflow with PyBullet integration
    - Disney Research computational character synthesis from anchor positioning
    - Automatic base generation and actuator optimization
    - Event-driven communication between components  
    - Multi-layer blueprint generation optimized for letter-size printing
    - Educational visualization of forces, constraints, and motion paths
    - Manufacturing safety validation and complete fabrication specifications
    
    The tab orchestrates specialized managers, enhanced action handlers, physics services,
    and computational character services to provide a professional mechanism design experience.
    """

    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self._is_active = False
        self._setup_managers_and_ui()
        self._connect_components()
        logger.info("Enhanced MechanismDesignTab initialized with physics validation support.")

    def _setup_managers_and_ui(self):
        """Setup enhanced managers, physics services, and UI components"""
        
        # Initialize core graphics components
        self.scene = QGraphicsScene(self)
        self.view = EditorView(self.scene, self, mechanism_mode=True)

        # Initialize state and scene management
        self.state = MechanismStateManager(self)
        self.scene_manager = MechanismSceneManager(self.scene, self.state, self)
        self.animation_controller = MechanismAnimationController(self.state, self)
        
        # Initialize event-driven architecture
        # Use main window's event bus if available, otherwise create one
        if hasattr(self.main_window, 'event_bus') and self.main_window.event_bus:
            self.event_bus = self.main_window.event_bus
        else:
            self.event_bus = EventBus()
            logger.warning("Main window has no event bus - created local instance")
        
        # Initialize physics services
        self.simulation_service = SimulationService(
            event_bus=self.event_bus,
            parent=self
        )
        self.blueprint_service = BlueprintService(
            event_bus=self.event_bus,
            parent=self
        )
        
        # Initialize computational character services (Disney Research style)
        self.anchor_positioning_service = AnchorPositioningService(
            event_bus=self.event_bus,
            parent=self
        )
        self.base_generation_service = BaseGenerationService(
            event_bus=self.event_bus,
            parent=self
        )
        self.force_analysis_service = ForceAnalysisService(
            event_bus=self.event_bus,
            parent=self
        )
        self.character_design_service = CharacterDesignService(
            event_bus=self.event_bus,
            parent=self
        )
        
        # Configure character design service with dependent services
        self.character_design_service.set_synthesis_services(
            anchor_service=self.anchor_positioning_service,
            base_service=self.base_generation_service,
            force_service=self.force_analysis_service
        )
        
        # Initialize enhanced UI panel (with physics validation controls)
        self.ui_panel = EnhancedMechanismControlPanel(self)
        
        # Initialize enhanced action handler (with physics integration)
        self.action_handler = EnhancedMechanismActionHandler(
            main_window=self.main_window,
            state_manager=self.state,
            scene_manager=self.scene_manager,
            ui_panel=self.ui_panel,
            event_bus=self.event_bus,
            parent=self
        )
        
        # Initialize parametric handler (unchanged)
        self.parametric_handler = ParametricDesignHandler(self.state, self.scene_manager, self)

        # Create horizontal layout for mechanism design
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(self._design_system.spacing.md)
        main_layout.addWidget(self.ui_panel)
        main_layout.addWidget(self.view, 1)
        
        logger.info("Enhanced mechanism design components initialized with physics validation and computational character design support")

    def _connect_components(self):
        """Connect enhanced components with physics validation signals"""
        
        # --- Existing UI actions -> Action Handler / Controllers ---
        self.ui_panel.recommendation_requested.connect(
            self.action_handler.handle_get_recommendations
        )
        self.ui_panel.play_clicked.connect(self.animation_controller.start)
        self.ui_panel.stop_clicked.connect(self.animation_controller.stop)
        self.ui_panel.reset_clicked.connect(self.animation_controller.reset)
        self.ui_panel.parametric_mode_toggled.connect(
            self.parametric_handler.toggle_parametric_mode
        )
        self.ui_panel.export_blueprint_requested.connect(
            self.action_handler.handle_export_blueprint
        )
        self.ui_panel.debug_mode_toggled.connect(self.scene_manager.toggle_debug_visuals)

        # --- NEW: Physics validation connections ---
        self.ui_panel.validate_physics_requested.connect(
            self.action_handler.handle_validate_physics
        )
        self.ui_panel.physics_visualization_changed.connect(
            self.action_handler.handle_physics_visualization_changed
        )
        self.ui_panel.live_physics_feedback_toggled.connect(
            self.action_handler.handle_live_physics_feedback_toggled
        )

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
        
        # --- Animation Controller Connections ---
        self.animation_controller.tick.connect(self.scene_manager.update_animation_frame)
        self.animation_controller.reset_animation.connect(lambda: self.scene_manager.update_animation_frame(0))
        
        # --- NEW: Computational Character Service Connections ---
        # Connect character design service signals to UI for feedback
        self.character_design_service.character_synthesis_started.connect(
            self._on_character_synthesis_started
        )
        self.character_design_service.character_synthesis_completed.connect(
            self._on_character_synthesis_completed
        )
        self.character_design_service.mechanism_synthesized.connect(
            self._on_mechanism_synthesized
        )
        self.character_design_service.base_generated.connect(
            self._on_base_generated
        )
        self.character_design_service.actuators_optimized.connect(
            self._on_actuators_optimized
        )
        
        logger.info("Enhanced component connections established with physics validation and computational character design support")

    # --- Public API Methods ---
    def set_path_data_from_editor(self, path_data):
        """
        Handles updates to path data from the editor, ensuring state consistency.
        
        Enhanced to reset physics validation when mechanisms change.
        """
        logger.info(f"MechanismDesignTab: Received path data from editor with {len(path_data) if path_data else 0} paths")
        if path_data:
            for part_name, path in path_data.items():
                logger.debug(f"  - {part_name}: {type(path).__name__} with {path.elementCount() if hasattr(path, 'elementCount') else 'unknown'} elements")
        
        current_parts = set(path_data.keys()) if path_data else set()
        previous_parts = set(self.state.path_data.keys())

        # Determine which parts' paths were removed or changed
        parts_to_clear = previous_parts - current_parts
        for part_name in current_parts:
            if part_name in self.state.path_data and path_data.get(
                part_name
            ) != self.state.path_data.get(part_name):
                parts_to_clear.add(part_name)

        # Clear mechanisms for affected parts
        mechanisms_cleared = False
        for part_name in parts_to_clear:
            self.state.clear_mechanisms_for_part(part_name)
            mechanisms_cleared = True
            logger.info(f"Cleared mechanism for part '{part_name}' due to path change.")

        # Reset physics validation if mechanisms were cleared
        if mechanisms_cleared:
            self.action_handler.reset_physics_validation()

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
        """
        Clears all mechanism data and resets associated systems including physics validation.
        
        Enhanced to reset physics validation state when clearing mechanisms.
        """
        logger.info("Clearing all mechanism data and physics validation.")
        self.animation_controller.reset()
        self.action_handler.reset_physics_validation()
        self.state.clear_all()

    def activate_tab(self):
        """Called when the tab becomes active."""
        super().activate_tab()  # Call parent to apply theme styles
        self._is_active = True
        logger.info("Mechanism Design Tab is now active.")
        # Connect to expensive signals only when the tab is active
        if hasattr(self.main_window, "kinematics_system") and self.main_window.kinematics_system:
            try:
                self.main_window.kinematics_system.pose_updated.connect(self.handle_ik_update)
            except (TypeError, RuntimeError) as e:
                logger.warning(f"Could not connect to kinematics system in activate_tab: {e}")

    def deactivate_tab(self):
        """Called when the tab is hidden."""
        self._is_active = False
        self.animation_controller.stop()  # Stop animation when tab is not visible
        logger.info("Mechanism Design Tab is now inactive.")
        # Disconnect from expensive signals when the tab is not visible
        if hasattr(self.main_window, "kinematics_system") and self.main_window.kinematics_system:
            try:
                self.main_window.kinematics_system.pose_updated.disconnect(self.handle_ik_update)
            except (TypeError, RuntimeError) as e:
                logger.warning(
                    f"Could not disconnect from kinematics system in deactivate_tab: {e}"
                )

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
                    effector_id = self.main_window.ik_manager.get_end_effector_for_part(
                        layer_data["part_name"]
                    )
                    if effector_id:
                        targets[effector_id] = output_pos
        return targets
    
    # --- Enhanced API Methods for Physics Validation ---
    
    def get_physics_validation_status(self):
        """Get current physics validation status for external queries"""
        return self.action_handler.get_last_validation_result()
    
    def is_physics_validated(self) -> bool:
        """Check if current mechanisms have been physics validated"""
        result = self.action_handler.get_last_validation_result()
        return result is not None and result.can_export_blueprint
    
    # --- Computational Character Service Signal Handlers ---
    
    def _on_character_synthesis_started(self, character_id: str):
        """Handle character synthesis start"""
        logger.info(f"Character synthesis started: {character_id}")
        # Update UI to show synthesis is in progress
        if hasattr(self.ui_panel, 'set_character_synthesis_status'):
            self.ui_panel.set_character_synthesis_status("synthesizing", character_id)
    
    def _on_character_synthesis_completed(self, character_id: str, summary: dict):
        """Handle character synthesis completion"""
        logger.info(f"Character synthesis completed: {character_id}")
        logger.info(f"Character summary: {summary}")
        
        # Update UI to show completion
        if hasattr(self.ui_panel, 'set_character_synthesis_status'):
            self.ui_panel.set_character_synthesis_status("complete", character_id)
        
        # Update scene visualization with complete character
        if hasattr(self.scene_manager, 'visualize_complete_character'):
            self.scene_manager.visualize_complete_character(character_id, summary)
    
    def _on_mechanism_synthesized(self, mechanism_id: str, mechanism_data: dict):
        """Handle mechanism synthesis from character design"""
        logger.info(f"Mechanism synthesized: {mechanism_id}")
        
        # Add synthesized mechanism to the scene
        if hasattr(self.scene_manager, 'add_synthesized_mechanism'):
            self.scene_manager.add_synthesized_mechanism(mechanism_id, mechanism_data)
    
    def _on_base_generated(self, character_id: str, base_data: dict):
        """Handle structural base generation"""
        logger.info(f"Base generated for character: {character_id}")
        logger.info(f"Base area: {base_data.get('base_area', 0):.1f} mm²")
        
        # Visualize generated base in scene
        if hasattr(self.scene_manager, 'visualize_structural_base'):
            self.scene_manager.visualize_structural_base(character_id, base_data)
    
    def _on_actuators_optimized(self, character_id: str, actuator_specs: list):
        """Handle actuator optimization completion"""
        logger.info(f"Actuators optimized for character: {character_id}")
        logger.info(f"Total actuators required: {len(actuator_specs)}")
        
        # Visualize actuator placements
        if hasattr(self.scene_manager, 'visualize_actuator_placements'):
            self.scene_manager.visualize_actuator_placements(character_id, actuator_specs)
        
        # Update UI with actuator specifications
        if hasattr(self.ui_panel, 'update_actuator_specifications'):
            self.ui_panel.update_actuator_specifications(actuator_specs)
    
    def start_character_design(self, character_name: str = None) -> str:
        """Start a new computational character design session"""
        character_id = self.character_design_service.start_new_character_design(character_name)
        logger.info(f"Started new computational character design: {character_id}")
        return character_id
    
    def get_current_character(self):
        """Get the current character being designed"""
        return self.character_design_service.get_current_character()
    
    def cleanup(self):
        """
        Clean up resources when tab is destroyed.
        
        Enhanced to properly clean up physics services, computational character services,
        and event subscriptions.
        """
        try:
            # Stop animation and clear state
            self.animation_controller.stop()
            
            # Clean up enhanced action handler
            if hasattr(self.action_handler, 'cleanup'):
                self.action_handler.cleanup()
            
            # Clean up physics services
            if hasattr(self.simulation_service, 'cleanup'):
                self.simulation_service.cleanup()
            if hasattr(self.blueprint_service, 'cleanup'):
                self.blueprint_service.cleanup()
            
            # Clean up computational character services
            if hasattr(self.character_design_service, 'cleanup'):
                self.character_design_service.cleanup()
            if hasattr(self.anchor_positioning_service, 'cleanup'):
                self.anchor_positioning_service.cleanup()
            if hasattr(self.base_generation_service, 'cleanup'):
                self.base_generation_service.cleanup()
            if hasattr(self.force_analysis_service, 'cleanup'):
                self.force_analysis_service.cleanup()
            
            logger.info("Enhanced mechanism design tab with computational character services cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during enhanced tab cleanup: {e}")
