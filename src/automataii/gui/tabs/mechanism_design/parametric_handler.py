# src/automataii/gui/tabs/mechanism_design/parametric_handler.py
import logging
from PyQt6.QtCore import QObject, pyqtSignal, QPointF

from .parametric.controllers.parameter_controller import ParameterController
from .parametric.handles.anchor_handle import AnchorHandle
from .scene_manager import MechanismSceneManager
from .state_manager import MechanismStateManager
from .utils import extract_key_points_from_simulation
from automataii.kinematics.mechanism_simulator import MechanismSimulator

logger = logging.getLogger(__name__)

class ParametricDesignHandler(QObject):
    """
    (Controller) Handles the logic for the parametric editing mode.
    It communicates with the ParameterController to manage interactive handles in the scene,
    and re-runs simulations on parameter changes.
    """
    def __init__(self, state_manager: MechanismStateManager, scene_manager: MechanismSceneManager, parent=None):
        super().__init__(parent)
        self.state = state_manager
        self.scene_manager = scene_manager
        self.is_mode_active = False
        
        self.controller = ParameterController(self.state)
        self.simulator = MechanismSimulator()
        self.active_handles = {}  # mechanism_id -> list of handle_ids

        self._connect_signals()

    def _connect_signals(self):
        """Connect signals between the controller and other components."""
        self.controller.mechanism_parameters_changed.connect(self._recalculate_mechanism)
        self.controller.visual_refresh_requested.connect(self.scene_manager.update_mechanism_visuals)
        self.controller.manipulation_started.connect(self.scene_manager.parent_widget.animation_controller.stop)

    def toggle_parametric_mode(self, is_active: bool):
        """Activates or deactivates the parametric editing mode."""
        self.is_mode_active = is_active
        if is_active:
            self._create_handles_for_all_mechanisms()
        else:
            self._remove_all_handles()
        
        logger.info(f"Parametric mode {'activated' if is_active else 'deactivated'}.")

    def _recalculate_mechanism(self, mechanism_id: str, updated_params: dict):
        """
        Re-runs the simulation with new parameters and updates the state.
        """
        if mechanism_id not in self.state.mechanism_layers:
            return

        # Create a copy to modify
        layer_data = self.state.mechanism_layers[mechanism_id].copy()
        
        # Update params
        if "params" not in layer_data:
            layer_data["params"] = {}
        layer_data["params"].update(updated_params)

        # Re-run simulation
        sim_data = self.simulator.run_simulation(layer_data["type"], layer_data["params"])
        
        if sim_data:
            layer_data["full_simulation_data"] = sim_data
            key_points = extract_key_points_from_simulation(sim_data, layer_data["type"])
            layer_data["key_points"] = key_points
            
            # Update the entire layer in the state manager to trigger a full refresh
            self.state.update_mechanism_layer(mechanism_id, layer_data)
        else:
            logger.warning(f"Recalculation failed for mechanism {mechanism_id} with params {updated_params}")

    def handle_mechanism_added(self, mechanism_id: str):
        """Creates handles for a newly added mechanism if the mode is active."""
        if self.is_mode_active:
            if mechanism_id in self.state.mechanism_layers:
                self._create_handles_for_mechanism(mechanism_id, self.state.mechanism_layers[mechanism_id])

    def handle_mechanisms_cleared(self):
        """Removes all handles when all mechanisms are cleared."""
        if self.is_mode_active:
            self._remove_all_handles()

    def _create_handles_for_all_mechanisms(self):
        """Creates interactive handles for all mechanisms in the current state."""
        self._remove_all_handles()
        for mid, layer_data in self.state.mechanism_layers.items():
            self._create_handles_for_mechanism(mid, layer_data)

    def _create_handles_for_mechanism(self, mechanism_id: str, layer_data: dict):
        """Creates handles for a single mechanism."""
        if layer_data.get("type") == "4_bar_linkage":
            self._create_4_bar_linkage_handles(mechanism_id, layer_data)
        # Add other mechanism types here

    def _create_4_bar_linkage_handles(self, mechanism_id: str, layer_data: dict):
        """Creates AnchorHandles for a 4-bar linkage."""
        key_points = layer_data.get("key_points", {})
        to_scene = self.scene_manager.visuals.visual_factory.get_scene_transform_function(layer_data)

        pivots = {
            "ground_pivot_1": key_points.get("ground_pivot_1"),
            "ground_pivot_2": key_points.get("ground_pivot_2"),
        }

        for name, pos_data in pivots.items():
            if not pos_data:
                continue
            
            scene_pos = to_scene(pos_data)
            
            handle = AnchorHandle(
                mechanism_id=mechanism_id,
                anchor_name=name,
                initial_position=scene_pos,
                mechanism_data=layer_data,
                update_callback=self._on_handle_updated
            )
            
            handle_id = self.controller.register_handle(handle)
            self.scene_manager.scene.addItem(handle)
            
            if mechanism_id not in self.active_handles:
                self.active_handles[mechanism_id] = []
            self.active_handles[mechanism_id].append(handle_id)

    def _on_handle_updated(self, anchor_name: str, new_pos: QPointF):
        """Callback from a handle when it's moved."""
        # This is a simplified update. The controller will handle the main logic.
        # We might need to trigger a recalculation here if not handled by the controller's signals.
        logger.debug(f"Handle {anchor_name} updated to {new_pos}")

    def _remove_all_handles(self):
        """Removes all active handles from the scene and controller."""
        for mid, handle_ids in self.active_handles.items():
            for handle_id in handle_ids:
                handle = self.controller.handle_registry.get(handle_id)
                if handle:
                    self.scene_manager.scene.removeItem(handle)
                self.controller.unregister_handle(handle_id)
        self.active_handles.clear()

    def update_on_state_change(self):
        """Called when the global state changes to refresh handles if mode is active."""
        if self.is_mode_active:
            self._create_handles_for_all_mechanisms()
