# src/automataii/gui/tabs/mechanism_design/action_handler.py
import logging
import uuid
import numpy as np
from PyQt6.QtCore import QObject, QPointF
from PyQt6.QtWidgets import QInputDialog, QMessageBox, QDialog, QFileDialog
from automataii.gui.dialogs.recommendation_dialog import MechanismRecommendationDialog
from automataii.utils.paths import resolve_path
from automataii.gui.tabs.mechanism_design_utils import convert_json_params_to_internal
from .utils import get_scene_transform_function, extract_key_points_from_simulation
from .visuals import visual_factory

logger = logging.getLogger(__name__)

class MechanismActionHandler(QObject):
    """
    (Controller) Handles user actions like button clicks.
    This class contains the business logic for generating, recommending,
    and exporting mechanisms.
    """
    def __init__(self, main_window, state_manager, scene_manager, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.state = state_manager
        self.scene_manager = scene_manager

    def handle_get_recommendations(self):
        """Handles the 'Get Mechanism' button click."""
        enabled_parts_with_paths = {
            name: path for name, path in self.state.path_data.items()
            if self.state.part_enabled_state.get(name, True) and path and not path.isEmpty()
        }

        if not enabled_parts_with_paths:
            QMessageBox.warning(self.main_window, "Warning", "No enabled parts with motion paths.")
            return

        target_part_name = self.state.selected_part_name
        if not target_part_name or target_part_name not in enabled_parts_with_paths:
            QMessageBox.warning(self.main_window, "Warning", "Please select a part with a motion path from the list.")
            return

        target_path = enabled_parts_with_paths[target_part_name]
        
        generated_paths_file = resolve_path("src/automataii/kinematics/generated_mechanism_paths.json")
        dialog = MechanismRecommendationDialog(target_path, generated_paths_file, parent=self.main_window)
        dialog.setWindowTitle(f"Mechanism Recommendations for {target_part_name}")
        
        dialog.mechanism_preview_selected.connect(self.scene_manager.preview_mechanism)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_mechanism = dialog.selected_mechanism_data
            if selected_mechanism:
                self._generate_mechanism_from_candidate(selected_mechanism)
        
        self.scene_manager.clear_preview()

    def _generate_mechanism_from_candidate(self, candidate_data):
        """Generates and adds a new mechanism to the state from a recommendation."""
        part_name = self.state.selected_part_name
        self.state.clear_mechanisms_for_part(part_name)

        mechanism_id = str(uuid.uuid4())[:8]
        mechanism_type_value = candidate_data.get('type', 'Unknown')
        raw_params = candidate_data.get('parameters', {})
        params = convert_json_params_to_internal(mechanism_type_value, raw_params)

        mechanism_type_mapping = {
            "4-Bar Linkage": "4_bar_linkage", "4-bar Coupler": "4_bar_linkage",
            "Cam & Follower": "cam", "Cam-Follower": "cam",
            "Gears (Simple Pair)": "gear", "Gear Contact": "gear", "Simple Gear": "gear",
            "Planetary Gear": "planetary_gear",
        }
        internal_type = mechanism_type_mapping.get(mechanism_type_value, "4_bar_linkage")

        layer_data = {
            "id": mechanism_id,
            "type": internal_type,
            "part_name": part_name,
            "params": params,
            "generated_path": self.state.path_data.get(part_name),
            "transform_params": candidate_data.get("transform_params"),
            "full_simulation_data": candidate_data.get("full_simulation_data", {}),
        }
        
        key_points = extract_key_points_from_simulation(layer_data["full_simulation_data"], internal_type)
        layer_data["key_points"] = key_points

        self._adjust_mechanism_to_target_joint(layer_data)
        
        self.state.add_mechanism(mechanism_id, layer_data)

    def _adjust_mechanism_to_target_joint(self, layer_data: dict):
        """Adjusts the mechanism's position to align its output with the target skeleton joint."""
        part_name = layer_data.get("part_name")
        part_info = self.state.parts_data.get(part_name)
        ik_manager = self.main_window.ik_manager

        if not all([part_name, part_info, ik_manager, self.state.initial_skeleton_data]):
            return

        target_joint_id = ik_manager.get_end_effector_for_part(part_name)
        if not target_joint_id:
            return

        joints_dict = self.state.initial_skeleton_data.get("joints", {})
        joint_data = joints_dict.get(target_joint_id)
        if not joint_data:
            return

        target_joint_pos = QPointF(*joint_data.get("position", [0, 0]))

        # Calculate the mechanism's initial output position in scene coordinates
        initial_output_pos = visual_factory.get_initial_output(layer_data)
        if not initial_output_pos:
            return

        # Calculate the offset needed to align the mechanism
        offset = target_joint_pos - initial_output_pos
        
        if offset.manhattanLength() < 1: # No significant offset
            return

        # Apply the offset to the mechanism's key points
        if "key_points" in layer_data and layer_data["key_points"]:
            to_scene = get_scene_transform_function(layer_data)
            
            # We need to find the inverse of the scene transform for the offset
            # This is a simplified approach: we assume the transform is mostly translation and uniform scale
            p1 = to_scene([0,0])
            p2 = to_scene([1,1])
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            
            # Assuming uniform scaling and no rotation for simplicity of inverse
            scale = (dx + dy) / 2.0 
            if abs(scale) < 1e-6: return

            offset_in_mech_space = np.array([offset.x() / scale, offset.y() / scale])

            for key, point in layer_data["key_points"].items():
                if point:
                    layer_data["key_points"][key] = (np.array(point) + offset_in_mech_space).tolist()
        
        # Also adjust the transform parameters' center
        if "transform_params" in layer_data and "center" in layer_data["transform_params"]:
             layer_data["transform_params"]["center"] = (np.array(layer_data["transform_params"]["center"]) + offset_in_mech_space).tolist()

        logger.info(f"Adjusted mechanism '{layer_data['id']}' by offset {offset} to align with joint '{target_joint_id}'.")


    def handle_export_blueprint(self):
        """Handles the 'Export Blueprint' button click."""
        if not self.state.mechanism_layers:
            QMessageBox.warning(self.main_window, "Warning", "No mechanisms to export.")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Save Blueprint", "", "SVG Files (*.svg)"
        )

        if not save_path:
            return

        try:
            from automataii.gui.exporters.blueprint_exporter import BlueprintExporter
            
            exporter = BlueprintExporter(
                self.state.parts_data,
                self.state.mechanism_layers,
                self.state.initial_skeleton_data
            )
            exporter.export(save_path)
            QMessageBox.information(self.main_window, "Success", f"Blueprint exported to {save_path}")
        except Exception as e:
            logger.error(f"Failed to export blueprint: {e}")
            QMessageBox.critical(self.main_window, "Error", f"Failed to export blueprint: {e}")