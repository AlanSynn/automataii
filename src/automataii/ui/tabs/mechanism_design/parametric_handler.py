# src/automataii/gui/tabs/mechanism_design/parametric_handler.py
import logging

from PyQt6.QtCore import QObject

from automataii.domain.kinematics.mechanism_simulator import MechanismSimulator

from .parametric.controllers.parameter_controller import ParameterController
from .scene_manager import MechanismSceneManager
from .state_manager import MechanismStateManager
from .utils import extract_key_points_from_simulation

logger = logging.getLogger(__name__)


class ParametricDesignHandler(QObject):
    """
    (Controller) Handles the logic for the parametric editing mode.
    Uses the new modular factory system to create mechanism-specific parametric editors.
    """

    def __init__(
        self,
        state_manager: MechanismStateManager,
        scene_manager: MechanismSceneManager,
        parent=None,
    ):
        super().__init__(parent)
        self.state = state_manager
        self.scene_manager = scene_manager
        self.is_mode_active = False

        self.controller = ParameterController(self.state)
        self.simulator = MechanismSimulator()

        # New modular system: mechanism_id -> ParametricMechanismInterface
        self.active_editors = {}  # mechanism_id -> parametric_editor

        # Import factory
        from .parametric.factory import ParametricFactory

        self.factory = ParametricFactory

        self._connect_signals()

    def _connect_signals(self):
        """Connect signals between the controller and other components."""
        self.controller.mechanism_parameters_changed.connect(self._recalculate_mechanism)
        self.controller.visual_refresh_requested.connect(
            self.scene_manager.update_mechanism_visuals
        )
        self.controller.manipulation_started.connect(
            self.scene_manager.parent_widget.animation_controller.stop
        )

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
            logger.warning(
                f"Recalculation failed for mechanism {mechanism_id} with params {updated_params}"
            )

    def handle_mechanism_added(self, mechanism_id: str):
        """Creates handles for a newly added mechanism if the mode is active."""
        if self.is_mode_active:
            if mechanism_id in self.state.mechanism_layers:
                self._create_handles_for_mechanism(
                    mechanism_id, self.state.mechanism_layers[mechanism_id]
                )

    def handle_mechanisms_cleared(self):
        """Removes all handles when all mechanisms are cleared."""
        if self.is_mode_active:
            self._remove_all_handles()

    def _create_handles_for_all_mechanisms(self):
        """Creates interactive handles for all mechanisms in the current state using the modular factory."""
        self._remove_all_handles()
        for mid, layer_data in self.state.mechanism_layers.items():
            self._create_handles_for_mechanism(mid, layer_data)

    def _create_handles_for_mechanism(self, mechanism_id: str, layer_data: dict):
        """Creates handles for a single mechanism using the parametric factory."""
        try:
            # Check if mechanism supports parametric editing
            if not self.factory.is_supported(layer_data):
                logger.info(
                    f"Mechanism {mechanism_id} ({layer_data.get('type')}) does not support parametric editing"
                )
                return

            # Create parametric editor using factory
            editor = self.factory.create_parametric_editor(
                mechanism_id, layer_data, self.scene_manager
            )

            if editor:
                # Activate the editor (creates and shows handles)
                editor.activate()

                # Store the editor for later management
                self.active_editors[mechanism_id] = editor

                logger.info(
                    f"Created parametric editor for {mechanism_id} ({layer_data.get('type')})"
                )
            else:
                logger.warning(f"Failed to create parametric editor for {mechanism_id}")

        except Exception as e:
            logger.error(f"Error creating parametric editor for {mechanism_id}: {e}")

    def _remove_all_handles(self):
        """Removes all active handles from the scene using the modular system."""
        for mechanism_id, editor in self.active_editors.items():
            try:
                editor.deactivate()
                logger.debug(f"Deactivated parametric editor for {mechanism_id}")
            except Exception as e:
                logger.error(f"Error deactivating parametric editor for {mechanism_id}: {e}")

        self.active_editors.clear()

    def get_supported_mechanisms(self) -> list[str]:
        """Get list of mechanism types that support parametric editing."""
        return self.factory.get_supported_mechanisms()

    def is_mechanism_supported(self, layer_data: dict) -> bool:
        """Check if a mechanism supports parametric editing."""
        return self.factory.is_supported(layer_data)

    def get_active_editor_count(self) -> int:
        """Get number of active parametric editors."""
        return len(self.active_editors)

    def get_mechanism_constraints(self, mechanism_id: str) -> dict:
        """Get constraint information for a specific mechanism."""
        editor = self.active_editors.get(mechanism_id)
        if editor and hasattr(editor, "get_constraint_info"):
            return editor.get_constraint_info()
        return {}

    def update_on_state_change(self):
        """Called when the global state changes to refresh handles if mode is active."""
        if self.is_mode_active:
            self._create_handles_for_all_mechanisms()
