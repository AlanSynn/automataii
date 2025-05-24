"""
Inverse Kinematics (IK) Manager for Automataii.

This class will handle the logic and data related to the IK system,
including skeleton definition for IK, solving IK for limbs, and managing
IK-driven animation state.
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import math # Already present, but good to ensure

from PyQt6.QtCore import QObject, pyqtSignal, QPointF, QTimer, QElapsedTimer
from PyQt6.QtGui import QTransform

# Assuming StandardizedSkeletonModel and StandardizedJointModel are now the primary way
# SkeletonManager provides data, even if it's as a dictionary dump.
# IKManager will need to understand this structure.
from ..core.models_skeleton import StandardizedSkeletonModel, StandardizedJointModel # For type hinting if directly using models

# Placeholder for actual IK solver logic if it's separate
# from ..core.ik_solver import IKSolver # Example if you have a dedicated solver

class IKManager(QObject):
    """Manages IK related data, setup, and solving."""

    # Signal to indicate that the character's visual parts need updating based on IK solution
    character_visuals_updated = pyqtSignal(dict) # dict might contain part names and their new transforms
    # Signal to indicate that the overall animation state has changed (e.g., playing, stopped)
    animation_state_changed = pyqtSignal(str) # e.g., "playing", "stopped", "reset"
    # skeleton_updated = pyqtSignal(object) # REMOVED - IKManager should not re-emit general skeleton updates
    ik_solver_initialized = pyqtSignal(bool) # True if solver ready, False if failed or cleared
    error_occurred = pyqtSignal(str)

    def __init__(self, main_window_ref, parent: Optional[QObject] = None): # main_window_ref for statusbar or config access initially
        super().__init__(parent)
        self.main_window = main_window_ref # Keep a reference if needed, e.g. for status messages or part items

        # --- IK System Data (to be moved from MainWindow) ---
        self.sim_joints_config: Dict[str, Dict[str, Any]] = {}
        self.sim_limb_configs: Dict[str, Dict[str, Any]] = {}
        self.sim_limb_lengths: Dict[str, float] = {} # Stores actual lengths used by IK for parts
        self.sim_selectable_components: List[Dict[str, Any]] = []
        self.sim_two_bone_ik_effectors: List[str] = []
        self.sim_joint_bend_directions: Dict[str, int] = {}
        self._sim_dynamic_joints_data: Dict[str, Dict[str, Any]] = {} # Actual data store
        self.scene_joints_snapshot: Dict[str, Any] = {} # Stores calculated scene_joints

        # Mapping from IK part names to actual CharacterPartItem names
        self.ik_part_to_actual_part_name: Dict[str, str] = {
            "head": "head",
            "torso": "torso",
            "left_upper_arm": "left_arm_upper",
            "left_forearm": "left_arm_lower",
            "right_upper_arm": "right_arm_upper",
            "right_forearm": "right_arm_lower",
            "left_thigh": "left_leg_upper",
            "left_calf": "left_leg_lower",
            "right_thigh": "right_leg_upper",
            "right_calf": "right_leg_lower",
        }
        # This map links IK system's internal joint IDs (used in sim_joints_config keys)
        # to the *original names* found in char_cfg.yaml or similar source files.
        # SkeletonManager's standardized_model.joint_map will map these original names to standardized IDs.
        self.ik_joint_ids_to_source_names: Dict[str, str] = {
            "j_neck_base": "hip",       # Example: IK 'j_neck_base' might correspond to 'hip' in some AD char_cfg
            "j_head_tip": "head",      # IK 'j_head_tip' might be the 'head' joint in AD char_cfg
            "j_left_shoulder": "left_shoulder",
            "j_right_shoulder": "right_shoulder",
            "j_left_hip": "left_hip",
            "j_right_hip": "right_hip",
            "j_left_elbow": "left_elbow",
            "j_left_wrist": "left_hand",
            "j_right_elbow": "right_elbow",
            "j_right_wrist": "right_hand",
            "j_left_knee": "left_knee",
            "j_left_ankle": "left_foot",
            "j_right_knee": "right_knee",
            "j_right_ankle": "right_foot",
            # Add more as needed by your IK rig definition
        }

        # Active path definition target (if IKManager handles this interaction point)
        self._active_path_definition_target_joint_id: Optional[str] = None

        # --- Animation Timer & Control (to be moved from MainWindow) ---
        self.ik_animation_timer = QTimer(self)
        self.ik_animation_timer.setInterval(30)  # Approx 33 FPS
        self.ik_animation_timer.timeout.connect(self._run_ik_animation_step) # MODIFIED - Connect to own method

        self.ik_animation_speed: float = 0.5
        self.animation_duration: int = 3000 # milliseconds
        self._animation_start_time_qelapsed: Optional[QElapsedTimer] = None
        self._current_animation_progress: float = 0.0 # Normalized 0-1

        # Reference to the SkeletonManager (passed from MainWindow)
        self.skeleton_manager_ref: Optional['SkeletonManager'] = None # Keep as ref, avoid circular type hint with str

        # Project data references (populated by on_project_data_loaded or similar)
        self.project_dir: Optional[Path] = None # Still useful for context if IK needs to load related files
        self.project_parts_data: Dict[str, 'PartInfo'] = {} # Holds PartInfo for IK-relevant parts

        # Placeholder for an actual IK solving utility/library if used
        # self.ik_solver_instance = IKSolver()

        logging.info("IKManager initialized.")

    def set_animation_duration(self, duration_ms: int):
        """Sets the total duration for one loop of the IK animation."""
        if duration_ms > 0:
            self.animation_duration = duration_ms
            logging.info(f"IKManager: Animation duration set to {duration_ms} ms.")
        else:
            logging.warning(f"IKManager: Invalid animation duration: {duration_ms} ms. Must be positive.")

    def set_skeleton_manager(self, skeleton_manager_instance: 'SkeletonManager'): # Use string for type hint
        self.skeleton_manager_ref = skeleton_manager_instance
        if self.skeleton_manager_ref:
            try:
                self.skeleton_manager_ref.skeleton_updated.disconnect(self.on_skeleton_data_updated_from_manager)
            except TypeError:
                pass
            self.skeleton_manager_ref.skeleton_updated.connect(self.on_skeleton_data_updated_from_manager)
            logging.info("IKManager: SkeletonManager instance set and connected.")

    def set_project_parts_data(self, parts_data: Dict[str, 'PartInfo']):
        """Sets the parts data from the current project, used for animation paths etc."""
        self.project_parts_data = parts_data if parts_data is not None else {}
        logging.info(f"IKManager: Project parts data set. {len(self.project_parts_data)} parts.")
        self._update_animation_readiness()

    def _update_animation_readiness(self):
        """Checks if animation can be run and updates any related state."""
        # This is a placeholder for more complex logic if needed.
        # For example, update flags that start_animation checks.
        pass

    def on_skeleton_data_updated_from_manager(self, standardized_skeleton_dict: dict):
        """Called when SkeletonManager emits its skeleton_updated signal (with a dict)."""
        logging.info("IKManager: Received skeleton update (dict) from SkeletonManager.")
        if not standardized_skeleton_dict:
            logging.warning("IKManager: Received empty skeleton dict. Clearing IK definitions.")
            self._clear_ik_definitions()
            self.ik_solver_initialized.emit(False)
            return

        try:
            # Reconstruct the model from the dictionary for easier use, though direct dict access is also possible
            standardized_model = StandardizedSkeletonModel.model_validate(standardized_skeleton_dict)
            self._initialize_ik_definitions(standardized_model)
            self.ik_solver_initialized.emit(True)
        except Exception as e:
            logging.error(f"IKManager: Error processing standardized skeleton dict: {e}", exc_info=True)
            self._clear_ik_definitions()
            self.ik_solver_initialized.emit(False)
            self.error_occurred.emit(f"Error initializing IK from skeleton: {e}")

    def _clear_ik_definitions(self):
        """Clears all IK specific configurations and data."""
        self.sim_joints_config.clear()
        self.sim_limb_configs.clear()
        self.sim_limb_lengths.clear()
        self.sim_selectable_components.clear()
        self.sim_two_bone_ik_effectors.clear()
        self.sim_joint_bend_directions.clear()
        self._sim_dynamic_joints_data.clear()
        self.scene_joints_snapshot.clear()
        logging.info("IKManager: All IK definitions cleared.")
        self.ik_solver_initialized.emit(False)

    def _initialize_ik_definitions(self, std_skeleton_model: StandardizedSkeletonModel):
        self._clear_ik_definitions()
        logging.info(f"IKManager: Initializing IK definitions from StandardizedSkeletonModel (Source: {std_skeleton_model.source_format}).")

        if not std_skeleton_model.joints:
            logging.warning("IKManager: Cannot initialize IK definitions, standardized model has no joints.")
            self.character_visuals_updated.emit({})
            return

        # 1. Populate self.sim_joints_config and self.scene_joints_snapshot
        # We iterate through our IK rig's joint needs (self.ik_joint_ids_to_source_names)
        # and find the corresponding joint in the loaded std_skeleton_model.
        for ik_joint_key, source_joint_name_in_cfg in self.ik_joint_ids_to_source_names.items():
            # Find the standardized_id using the source_joint_name_in_cfg via std_skeleton_model.joint_map
            standardized_joint_id = None
            if std_skeleton_model.joint_map:
                standardized_joint_id = std_skeleton_model.joint_map.get(source_joint_name_in_cfg)

            # Fallback: if not in map, try direct name match in standardized joints
            if not standardized_joint_id:
                for j_id, j_model in std_skeleton_model.joints.items():
                    if j_model.name == source_joint_name_in_cfg or j_model.label == source_joint_name_in_cfg:
                        standardized_joint_id = j_id
                        break

            if standardized_joint_id and standardized_joint_id in std_skeleton_model.joints:
                std_joint_data = std_skeleton_model.joints[standardized_joint_id]
                pos_x, pos_y = std_joint_data.position
                self.sim_joints_config[ik_joint_key] = {
                    'x': pos_x,
                    'y': pos_y,
                    'label': std_joint_data.name # Use standardized name as label for IK joint
                }
                self.scene_joints_snapshot[ik_joint_key] = {
                    'x': pos_x,
                    'y': pos_y,
                    'angle': 0
                }
            else:
                logging.warning(f"IKManager: Could not find or map source joint '{source_joint_name_in_cfg}' (for IK joint '{ik_joint_key}') in standardized skeleton data.")

        # 2. Populate self.sim_limb_configs and self.sim_limb_lengths
        # Define IK limbs. An IK limb connects two IK joints from sim_joints_config.
        # The 'length_key' should correspond to a key in std_skeleton_model.limb_lengths or be calculated.
        # The 'part_name' is used to store the calculated/used length in self.sim_limb_lengths.
        potential_limbs_def = {
            # ik_limb_effector_key: {parent_ik_joint_key, length_source_key, visual_part_key_for_length_storage}
            'j_head_tip':       {'parent': 'j_neck_base',     'length_src': 'head',           'len_store_key': 'head'},
            'j_left_wrist':     {'parent': 'j_left_elbow',    'length_src': 'left_forearm',   'len_store_key': 'left_forearm'},
            'j_left_elbow':     {'parent': 'j_left_shoulder', 'length_src': 'left_upper_arm', 'len_store_key': 'left_upper_arm'},
            'j_right_wrist':    {'parent': 'j_right_elbow',   'length_src': 'right_forearm',  'len_store_key': 'right_forearm'},
            'j_right_elbow':    {'parent': 'j_right_shoulder','length_src': 'right_upper_arm','len_store_key': 'right_upper_arm'},
            'j_left_ankle':     {'parent': 'j_left_knee',     'length_src': 'left_calf',      'len_store_key': 'left_calf'},
            'j_left_knee':      {'parent': 'j_left_hip',      'length_src': 'left_thigh',     'len_store_key': 'left_thigh'},
            'j_right_ankle':    {'parent': 'j_right_knee',    'length_src': 'right_calf',     'len_store_key': 'right_calf'},
            'j_right_knee':     {'parent': 'j_right_hip',     'length_src': 'right_thigh',    'len_store_key': 'right_thigh'},
        }

        for ik_effector_key, limb_def in potential_limbs_def.items():
            parent_ik_key = limb_def['parent']
            length_source_key = limb_def['length_src'] # e.g., 'head', 'left_forearm' from std_model.limb_lengths
            length_storage_key = limb_def['len_store_key'] # Key for self.sim_limb_lengths

            if ik_effector_key in self.scene_joints_snapshot and parent_ik_key in self.scene_joints_snapshot:
                parent_snapshot = self.scene_joints_snapshot[parent_ik_key]
                effector_snapshot = self.scene_joints_snapshot[ik_effector_key]

                parent_pos = QPointF(parent_snapshot['x'], parent_snapshot['y'])
                effector_pos = QPointF(effector_snapshot['x'], effector_snapshot['y'])

                limb_vector = effector_pos - parent_pos
                calculated_length = limb_vector.manhattanLength()
                angle = math.degrees(math.atan2(limb_vector.y(), limb_vector.x())) if not limb_vector.isNull() else 0.0

                # Use length from standardized model if available, otherwise use calculated
                actual_length = calculated_length
                if std_skeleton_model.limb_lengths and length_source_key in std_skeleton_model.limb_lengths:
                    model_len = std_skeleton_model.limb_lengths[length_source_key]
                    if model_len > 0:
                        actual_length = model_len
                    else:
                        logging.debug(f"IKManager: Standardized model length for '{length_source_key}' is {model_len}, using calculated {calculated_length}.")

                if actual_length <= 1e-5: # Effectively zero
                     logging.warning(f"IKManager: Limb defined by effector '{ik_effector_key}' has zero or near-zero length ({actual_length}). May cause issues.")

                self.sim_limb_configs[ik_effector_key] = {
                    'parentAnchor': parent_ik_key,
                    'angle': angle,
                    'length': actual_length,
                    'label': length_storage_key # Use the storage key (visual part name) as label for the limb config
                }
                self.sim_limb_lengths[length_storage_key] = actual_length

                if ik_effector_key in self.scene_joints_snapshot:
                     self.scene_joints_snapshot[ik_effector_key]['angle'] = angle
            else:
                logging.warning(f"IKManager: Cannot define limb for effector '{ik_effector_key}'. Missing parent '{parent_ik_key}' or effector itself in scene_joints_snapshot.")

        # 3. Define sim_selectable_components (UI related, parts that can have paths)
        # These map to the IK rig's joint keys.
        self.sim_selectable_components = [
            {'label': 'Head',        'targetJointId': 'j_head_tip',    'partName': self.ik_part_to_actual_part_name.get('head')},
            {'label': 'Left Hand',   'targetJointId': 'j_left_wrist',  'partName': self.ik_part_to_actual_part_name.get('left_forearm')},
            {'label': 'Right Hand',  'targetJointId': 'j_right_wrist', 'partName': self.ik_part_to_actual_part_name.get('right_forearm')},
            {'label': 'Left Foot',   'targetJointId': 'j_left_ankle',  'partName': self.ik_part_to_actual_part_name.get('left_calf')},
            {'label': 'Right Foot',  'targetJointId': 'j_right_ankle', 'partName': self.ik_part_to_actual_part_name.get('right_calf')},
        ]
        self.sim_selectable_components = [
            comp for comp in self.sim_selectable_components if comp['targetJointId'] in self.sim_joints_config
        ]

        # 4. Define sim_two_bone_ik_effectors (IK rig keys for wrists, ankles)
        self.sim_two_bone_ik_effectors = [
            'j_left_wrist', 'j_right_wrist',
            'j_left_ankle', 'j_right_ankle'
        ]
        self.sim_two_bone_ik_effectors = [
            ik_key for ik_key in self.sim_two_bone_ik_effectors if ik_key in self.sim_joints_config
        ]

        # 5. Define sim_joint_bend_directions (IK rig keys for elbows, knees)
        self.sim_joint_bend_directions = {
            'j_left_elbow': -1, 'j_right_elbow': -1,
            'j_left_knee': 1,  'j_right_knee': 1
        }
        self.sim_joint_bend_directions = {
            ik_key:direction for ik_key, direction in self.sim_joint_bend_directions.items() if ik_key in self.sim_joints_config
        }

        self._sim_dynamic_joints_data = {
            ik_key: data.copy() for ik_key, data in self.scene_joints_snapshot.items()
        }
        logging.info(f"IKManager: sim_dynamic_joints initialized with {len(self._sim_dynamic_joints_data)} joints for the IK rig.")

        logging.debug(f"IKManager: sim_joints_config (IK Rig): {self.sim_joints_config}")
        logging.debug(f"IKManager: sim_limb_configs (IK Rig): {self.sim_limb_configs}")
        logging.debug(f"IKManager: sim_limb_lengths (IK Rig): {self.sim_limb_lengths}")

        self._update_character_part_visuals_from_ik()
        self.main_window.statusBar().showMessage("IKManager: IK definitions initialized from standardized model.", 3000)
        self.ik_solver_initialized.emit(True)

    def on_project_data_loaded(
        self,
        parts: Dict[str, 'PartInfo'],
        standardized_skeleton_dict: Optional[Dict[str, Any]], # Expecting dict from PDM now
        project_dir: Optional[Path]
    ):
        logging.info(f"IKManager: Project data received. Parts: {len(parts)}, Skel: {'Exists' if standardized_skeleton_dict else 'None'}")
        self.project_dir = project_dir
        self.project_parts_data = parts.copy()

        if standardized_skeleton_dict:
            self.on_skeleton_data_updated_from_manager(standardized_skeleton_dict)
        else:
            logging.warning("IKManager: No skeleton data in project. Clearing IK.")
            self.clear_ik_data()

    def clear_ik_data(self):
        """
        Clears all IK-related data, configurations, and stops animations.
        Resets IKManager to a state as if no project/skeleton is loaded.
        """
        logging.info("IKManager: Clearing all IK data and resetting state.")
        self.stop_animation()
        self._clear_ik_definitions()
        self._animation_start_time_qelapsed = None
        self._current_animation_progress = 0.0
        self.project_dir = None
        self.project_parts_data.clear()
        self.character_visuals_updated.emit({})
        self.ik_solver_initialized.emit(False)
        logging.info("IKManager: IK data cleared and state reset.")

    def _solve_single_bone_ik(self, ik_joint_key: str, target_pos: QPointF) -> Optional[QPointF]:
        if ik_joint_key not in self.sim_limb_configs:
            logging.warning(f"IKManager: No limb configuration for ik_joint_key '{ik_joint_key}' in _solve_single_bone_ik.")
            return None

        limb_config = self.sim_limb_configs[ik_joint_key]
        parent_anchor_ik_key = limb_config['parentAnchor']
        # Use the stored length from self.sim_limb_lengths, which corresponds to the visual part
        # The key for self.sim_limb_lengths should be the 'label' from limb_config
        limb_length_key = limb_config.get('label')
        limb_length = self.sim_limb_lengths.get(limb_length_key, 0.0) if limb_length_key else 0.0

        if parent_anchor_ik_key not in self._sim_dynamic_joints_data:
            logging.warning(f"IKManager: Parent anchor '{parent_anchor_ik_key}' not in dynamic joint data.")
            return None

        if limb_length <= 1e-5: # Effectively zero
            logging.warning(f"IKManager: Limb '{ik_joint_key}' (part: {limb_length_key}) has zero or negative length: {limb_length}. Placing at parent.")
            parent_joint_data = self._sim_dynamic_joints_data[parent_anchor_ik_key]
            parent_pos = QPointF(parent_joint_data['x'], parent_joint_data['y'])
            self._sim_dynamic_joints_data[ik_joint_key]['x'] = parent_pos.x()
            self._sim_dynamic_joints_data[ik_joint_key]['y'] = parent_pos.y()
            self._sim_dynamic_joints_data[ik_joint_key]['angle'] = parent_joint_data.get('angle', 0)
            return parent_pos

        parent_joint_data = self._sim_dynamic_joints_data[parent_anchor_ik_key]
        parent_pos = QPointF(parent_joint_data['x'], parent_joint_data['y'])

        direction_vector = target_pos - parent_pos
        current_dist_to_target = direction_vector.manhattanLength()

        if abs(current_dist_to_target) < 1e-5:
            new_effector_pos = QPointF(parent_pos)
            new_angle = self._sim_dynamic_joints_data[ik_joint_key].get('angle', parent_joint_data.get('angle', 0))
        else:
            normalized_direction = QPointF(direction_vector.x() / current_dist_to_target,
                                           direction_vector.y() / current_dist_to_target)
            new_effector_pos = parent_pos + normalized_direction * limb_length
            new_angle = math.degrees(math.atan2(normalized_direction.y(), normalized_direction.x()))

        self._sim_dynamic_joints_data[ik_joint_key]['x'] = new_effector_pos.x()
        self._sim_dynamic_joints_data[ik_joint_key]['y'] = new_effector_pos.y()
        self._sim_dynamic_joints_data[ik_joint_key]['angle'] = new_angle

        logging.debug(f"IKManager: _solve_single_bone_ik for {ik_joint_key} (part {limb_length_key}) -> New Pos: {new_effector_pos}, Angle: {new_angle}")
        return new_effector_pos

    def _solve_two_bone_ik(self, upper_limb_effector_ik_key: str, lower_limb_effector_ik_key: str, target_pos: QPointF) -> Optional[Tuple[QPointF, QPointF]]:
        # upper_limb_effector_ik_key is the middle joint (e.g., j_left_elbow)
        # lower_limb_effector_ik_key is the end effector (e.g., j_left_wrist)

        if upper_limb_effector_ik_key not in self.sim_limb_configs or \
           lower_limb_effector_ik_key not in self.sim_limb_configs:
            logging.warning(f"IKManager: Missing limb config for '{upper_limb_effector_ik_key}' or '{lower_limb_effector_ik_key}'.")
            return None

        upper_limb_config = self.sim_limb_configs[upper_limb_effector_ik_key]
        lower_limb_config = self.sim_limb_configs[lower_limb_effector_ik_key]

        root_ik_key = upper_limb_config['parentAnchor'] # e.g., j_left_shoulder
        middle_ik_key = upper_limb_effector_ik_key      # e.g., j_left_elbow
        end_effector_ik_key = lower_limb_effector_ik_key # e.g., j_left_wrist

        if root_ik_key not in self._sim_dynamic_joints_data:
            logging.warning(f"IKManager: Root IK joint '{root_ik_key}' not in dynamic joint data.")
            return None

        # Get lengths from self.sim_limb_lengths using the 'label' from limb_config as key
        len1_key = upper_limb_config.get('label')
        len2_key = lower_limb_config.get('label')
        len1 = self.sim_limb_lengths.get(len1_key, 0.0) if len1_key else 0.0
        len2 = self.sim_limb_lengths.get(len2_key, 0.0) if len2_key else 0.0

        if len1 <= 1e-5 or len2 <= 1e-5:
            logging.warning(f"IKManager: Limbs for two-bone IK ('{len1_key}', '{len2_key}') have zero/neg length (L1: {len1}, L2: {len2}).")
            root_pos_data = self._sim_dynamic_joints_data[root_ik_key]
            root_pos = QPointF(root_pos_data['x'], root_pos_data['y'])
            current_middle_pos_data = self._sim_dynamic_joints_data[middle_ik_key]
            current_end_pos_data = self._sim_dynamic_joints_data[end_effector_ik_key]
            return (QPointF(current_middle_pos_data['x'], current_middle_pos_data['y']),
                    QPointF(current_end_pos_data['x'], current_end_pos_data['y']))

        root_pos_data = self._sim_dynamic_joints_data[root_ik_key]
        root_pos = QPointF(root_pos_data['x'], root_pos_data['y'])

        dist_to_target_sq = (target_pos.x() - root_pos.x())**2 + (target_pos.y() - root_pos.y())**2
        dist_to_target = math.sqrt(dist_to_target_sq) if dist_to_target_sq > 0 else 0.0

        new_middle_pos = QPointF()
        new_end_effector_pos = QPointF()

        if dist_to_target > len1 + len2 - 1e-5: # Target is too far (with tolerance)
            logging.debug(f"IKManager: Target for {end_effector_ik_key} is unreachable. Stretching.")
            dx = target_pos.x() - root_pos.x()
            dy = target_pos.y() - root_pos.y()
            if dist_to_target < 1e-5 : # Target is at root, stretch along some default direction (e.g. previous or x-axis)
                # This case needs better handling, for now, stretch along x-axis or previous orientation
                prev_middle_angle_rad = math.radians(self._sim_dynamic_joints_data[middle_ik_key].get('angle', 0))
                dx = math.cos(prev_middle_angle_rad)
                dy = math.sin(prev_middle_angle_rad)
                if abs(dx) < 1e-5 and abs(dy) < 1e-5: dx = 1.0 # Default to x-axis if zero vector
                dist_to_target = 1.0 # Avoid div by zero, effectively just need direction

            new_end_effector_pos = root_pos + QPointF(dx / dist_to_target * (len1 + len2),
                                                  dy / dist_to_target * (len1 + len2))
            new_middle_pos = root_pos + QPointF(dx / dist_to_target * len1,
                                              dy / dist_to_target * len1)
        elif dist_to_target < abs(len1 - len2) + 1e-5: # Target is too close (with tolerance)
            logging.debug(f"IKManager: Target for {end_effector_ik_key} is too close. Adjusting.")
            dx = target_pos.x() - root_pos.x()
            dy = target_pos.y() - root_pos.y()

            if dist_to_target < 1e-5: # Target is (almost) at the root joint
                 # Limbs fold based on bend direction. Extend along a default axis or previous orientation.
                bend_direction = self.sim_joint_bend_directions.get(middle_ik_key, 1)
                # Get previous angle of root-to-middle segment to maintain general direction if possible
                prev_root_angle_rad = math.radians(self._sim_dynamic_joints_data[middle_ik_key].get('angle', 0))
                # If prev angle is 0, try a default (e.g. slightly downwards)
                if abs(prev_root_angle_rad) < 1e-5 : prev_root_angle_rad = math.radians(10 * bend_direction)

                new_middle_pos = root_pos + QPointF(len1 * math.cos(prev_root_angle_rad), len1 * math.sin(prev_root_angle_rad))
                # For the end effector, continue in same direction or fold back based on len1 vs len2 for min reach
                if len1 > len2:
                    new_end_effector_pos = new_middle_pos + QPointF(len2 * math.cos(prev_root_angle_rad + math.pi),
                                                                  len2 * math.sin(prev_root_angle_rad + math.pi))
                else:
                    new_end_effector_pos = new_middle_pos + QPointF(len2 * math.cos(prev_root_angle_rad),
                                                                  len2 * math.sin(prev_root_angle_rad))
            else:
                min_reach_dist = abs(len1 - len2)
                new_end_effector_pos = root_pos + QPointF(dx / dist_to_target * min_reach_dist,
                                                      dy / dist_to_target * min_reach_dist)
                # Place middle joint along this line appropriately, ensuring correct configuration
                if len1 > len2:
                    new_middle_pos = new_end_effector_pos + QPointF(dx / dist_to_target * len2,
                                                                    dy / dist_to_target * len2)
                else: # len2 >= len1
                    new_middle_pos = root_pos + QPointF(dx / dist_to_target * len1,
                                                        dy / dist_to_target * len1)
        else:
            cos_angle_beta = (dist_to_target_sq - len1*len1 - len2*len2) / (2 * len1 * len2)
            cos_angle_beta = max(-1.0, min(1.0, cos_angle_beta))
            angle_beta_rad = math.acos(cos_angle_beta)

            cos_angle_gamma = (len1*len1 + dist_to_target_sq - len2*len2) / (2 * len1 * dist_to_target)
            cos_angle_gamma = max(-1.0, min(1.0, cos_angle_gamma))
            angle_gamma_rad = math.acos(cos_angle_gamma)

            atan_angle_to_target_rad = math.atan2(target_pos.y() - root_pos.y(),
                                                  target_pos.x() - root_pos.x())

            bend_direction = self.sim_joint_bend_directions.get(middle_ik_key, 1)
            final_angle_root_to_middle_rad = atan_angle_to_target_rad - (angle_gamma_rad * bend_direction)

            new_middle_pos = root_pos + QPointF(len1 * math.cos(final_angle_root_to_middle_rad),
                                                len1 * math.sin(final_angle_root_to_middle_rad))
            new_end_effector_pos = QPointF(target_pos)

        vec_root_to_middle = new_middle_pos - root_pos
        angle_root_rad = math.atan2(vec_root_to_middle.y(), vec_root_to_middle.x()) if not vec_root_to_middle.isNull() else self._sim_dynamic_joints_data[middle_ik_key].get('angle',0)

        vec_middle_to_end = new_end_effector_pos - new_middle_pos
        angle_middle_rad = math.atan2(vec_middle_to_end.y(), vec_middle_to_end.x()) if not vec_middle_to_end.isNull() else self._sim_dynamic_joints_data[end_effector_ik_key].get('angle',0)

        self._sim_dynamic_joints_data[middle_ik_key]['x'] = new_middle_pos.x()
        self._sim_dynamic_joints_data[middle_ik_key]['y'] = new_middle_pos.y()
        self._sim_dynamic_joints_data[middle_ik_key]['angle'] = math.degrees(angle_root_rad)

        self._sim_dynamic_joints_data[end_effector_ik_key]['x'] = new_end_effector_pos.x()
        self._sim_dynamic_joints_data[end_effector_ik_key]['y'] = new_end_effector_pos.y()
        self._sim_dynamic_joints_data[end_effector_ik_key]['angle'] = math.degrees(angle_middle_rad)

        logging.debug(f"IKManager: _solve_two_bone_ik for {middle_ik_key}({len1_key}) & {end_effector_ik_key}({len2_key}) -> Mid: {new_middle_pos}, End: {new_end_effector_pos}")
        return (new_middle_pos, new_end_effector_pos)

    def _update_character_part_visuals_from_ik(self):
        """
        Updates the positions and rotations of CharacterPartItem instances
        based on the current state of self._sim_dynamic_joints_data.
        Emits character_visuals_updated signal.
        This method translates IK joint states to visual part transforms.
        """
        # This method needs to map from IK joint IDs (e.g., 'j_left_elbow', 'j_left_wrist')
        # to actual character part names (e.g., 'left_arm_upper', 'left_arm_lower')
        # and then calculate the necessary transformations (position, rotation) for those parts.

        if not self._sim_dynamic_joints_data:
            logging.debug("IKManager: No dynamic joint data to update visuals from.")
            self.character_visuals_updated.emit({}) # Emit empty to clear if necessary
            return

        part_transforms = {}

        # Iterate through defined IK limbs (sim_limb_configs) which map to visual parts
        for ik_effector_key, limb_config in self.sim_limb_configs.items():
            parent_anchor_ik_key = limb_config['parentAnchor']
            # The 'label' in limb_config is assumed to be the key for ik_part_to_actual_part_name
            # and also the key for sim_limb_lengths (e.g., 'left_upper_arm', 'head')
            visual_part_key = limb_config.get('label')
            actual_part_name = self.ik_part_to_actual_part_name.get(visual_part_key)

            if not actual_part_name:
                logging.debug(f"IKManager: No actual_part_name found for visual_part_key '{visual_part_key}' (effector {ik_effector_key})")
                continue

            if parent_anchor_ik_key in self._sim_dynamic_joints_data and ik_effector_key in self._sim_dynamic_joints_data:
                parent_joint_data = self._sim_dynamic_joints_data[parent_anchor_ik_key]
                effector_joint_data = self._sim_dynamic_joints_data[ik_effector_key]

                parent_pos = QPointF(parent_joint_data['x'], parent_joint_data['y'])
                # Effector position is ALREADY the distal end due to how sim_dynamic_joints is updated.
                # The 'angle' on the effector_joint_data is the global angle of THIS limb segment.
                part_x = parent_pos.x() # Visual part is typically anchored at its proximal joint
                part_y = parent_pos.y()
                rotation_degrees = effector_joint_data.get('angle', 0.0) # This angle IS the limb's orientation

                current_limb_length = self.sim_limb_lengths.get(visual_part_key, 0.0)

                part_transforms[actual_part_name] = {
                    'x': part_x,
                    'y': part_y,
                    'rotation': rotation_degrees,
                    'world_proximal_x': parent_pos.x(),
                    'world_proximal_y': parent_pos.y(),
                    # Distal point can be recalculated from parent, angle, and length for consistency if needed
                    'world_distal_x': parent_pos.x() + current_limb_length * math.cos(math.radians(rotation_degrees)),
                    'world_distal_y': parent_pos.y() + current_limb_length * math.sin(math.radians(rotation_degrees)),
                    'length': current_limb_length
                }
            else:
                logging.warning(f"IKManager: Missing dynamic joint data for limb part '{actual_part_name}' (parent IK key '{parent_anchor_ik_key}' or effector IK key '{ik_effector_key}')")

        # Handle torso separately if it's not treated as a regular limb
        torso_actual_name = self.ik_part_to_actual_part_name.get('torso')
        if torso_actual_name and torso_actual_name not in part_transforms: # If not handled by limb logic
            # Position torso based on a central IK joint, e.g., 'j_neck_base' or an average of hips
            torso_anchor_ik_key = 'j_neck_base' # Example, make this configurable if needed
            if torso_anchor_ik_key in self._sim_dynamic_joints_data:
                anchor_data = self._sim_dynamic_joints_data[torso_anchor_ik_key]
                part_transforms[torso_actual_name] = {
                    'x': anchor_data['x'],
                    'y': anchor_data['y'],
                    'rotation': anchor_data.get('angle', 0) # Use angle of anchor joint, or derive avg
                }
            else:
                logging.debug(f"IKManager: Torso anchor IK key '{torso_anchor_ik_key}' not in dynamic data, cannot position torso.")

        if part_transforms:
            logging.debug(f"IKManager: Emitting character_visuals_updated with transforms for: {list(part_transforms.keys())}")
            self.character_visuals_updated.emit(part_transforms)
        else:
            logging.debug("IKManager: No part transforms generated in _update_character_part_visuals_from_ik.")
            self.character_visuals_updated.emit({}) # Emit empty if nothing to update

    # --- Animation Control Methods (to be moved/adapted from MainWindow) ---
    def start_animation(self):
        """Starts the IK-driven animation."""
        if not self._sim_dynamic_joints_data or not self.scene_joints_snapshot:
            logging.warning("IKManager: Cannot start animation. IK system not fully initialized (no dynamic joints or snapshot).")
            self.main_window.statusBar().showMessage("Animation cannot start: IK not ready.", 3000)
            return False

        animation_possible = False
        if self.project_parts_data:
            for component_config in self.sim_selectable_components:
                part_name = component_config.get('partName')
                if part_name and part_name in self.project_parts_data:
                    part_info = self.project_parts_data[part_name]
                    # Check for motion_path_data (list of QPointF) or motion_path (QPainterPath)
                    has_path_data = hasattr(part_info, 'motion_path_data') and part_info.motion_path_data
                    has_painter_path = hasattr(part_info, 'motion_path') and part_info.motion_path and hasattr(part_info.motion_path, 'elementCount') and part_info.motion_path.elementCount() > 0
                    if has_path_data or has_painter_path:
                        animation_possible = True
                        break

        if not animation_possible:
            logging.warning("IKManager: Cannot start animation. No motion paths defined for animatable parts.")
            self.main_window.statusBar().showMessage("Animation cannot start: No motion paths defined.", 3000)
            return False

        logging.info("IKManager: Starting animation.")
        self.main_window.statusBar().showMessage("Playing IK Animation...", 2000)
        if self._animation_start_time_qelapsed is None:
            self._animation_start_time_qelapsed = QElapsedTimer()
        self._animation_start_time_qelapsed.start()
        self._current_animation_progress = 0.0
        if not self.ik_animation_timer.isActive():
            self.ik_animation_timer.start()

        self.animation_state_changed.emit("playing")
        return True

    def stop_animation(self):
        """Stops the IK-driven animation."""
        if self.ik_animation_timer.isActive():
            self.ik_animation_timer.stop()
            logging.info("IKManager: Animation stopped.")
            self.main_window.statusBar().showMessage("IK Animation stopped.", 2000)
        self.animation_state_changed.emit("stopped")

    def reset_animation_state(self):
        """Resets the animated parts to their initial positions based on scene_joints_snapshot."""
        self.stop_animation()
        if not self.scene_joints_snapshot:
            logging.warning("IKManager: Cannot reset animation state, scene_joints_snapshot is empty.")
            return

        logging.info("IKManager: Resetting animation state.")
        self._sim_dynamic_joints_data = {k: v.copy() for k, v in self.scene_joints_snapshot.items()}
        self._current_animation_progress = 0.0

        self._update_character_part_visuals_from_ik()
        self.main_window.statusBar().showMessage("IK Animation reset to initial pose.", 2000)
        self.animation_state_changed.emit("reset")

    def _extract_points_from_painter_path(self, painter_path) -> List[QPointF]:
        """Extracts QPointF coordinates from a QPainterPath."""
        points = []
        if not painter_path or not hasattr(painter_path, 'elementCount') or painter_path.elementCount() == 0:
            return points
        for i in range(painter_path.elementCount()):
            element = painter_path.elementAt(i)
            points.append(QPointF(element.x, element.y))
        return points

    def _get_point_on_path(self, path_obj: Any, progress: float) -> Optional[QPointF]:
        path_points: List[QPointF] = []
        if isinstance(path_obj, list):
            if all(isinstance(p, QPointF) for p in path_obj):
                path_points = path_obj
            else: # try to convert if it's list of tuples/lists
                try:
                    path_points = [QPointF(p[0], p[1]) for p in path_obj if isinstance(p, (list,tuple)) and len(p)==2]
                except:
                    logging.warning("IKManager: motion_path_data list contains non-convertible points.")
                    return None
        elif hasattr(path_obj, 'elementCount'): # QPainterPath
             path_points = self._extract_points_from_painter_path(path_obj)
        else:
            logging.warning(f"IKManager: Unsupported motion path type: {type(path_obj)}")
            return None

        if not path_points:
            return None
        if len(path_points) == 1:
            return path_points[0]

        total_length = 0
        segment_lengths = []
        for i in range(len(path_points) - 1):
            p1 = path_points[i]
            p2 = path_points[i+1]
            segment_length = QPointF(p2 - p1).manhattanLength()
            segment_lengths.append(segment_length)
            total_length += segment_length

        if total_length < 1e-5: # effectively zero length path
            return path_points[0]

        target_dist = progress * total_length
        target_dist = max(0, min(target_dist, total_length)) # Clamp progress to path bounds

        current_dist = 0
        for i in range(len(segment_lengths)):
            segment_len = segment_lengths[i]
            if current_dist + segment_len >= target_dist - 1e-5: # Add tolerance for float comparison
                p1 = path_points[i]
                p2 = path_points[i+1]
                remaining_dist = target_dist - current_dist
                if segment_len < 1e-5:
                    return p1 # Segment is a point, return start of segment
                segment_progress = remaining_dist / segment_len
                segment_progress = max(0.0, min(1.0, segment_progress)) # Clamp segment progress

                interpolated_x = p1.x() + (p2.x() - p1.x()) * segment_progress
                interpolated_y = p1.y() + (p2.y() - p1.y()) * segment_progress
                return QPointF(interpolated_x, interpolated_y)
            current_dist += segment_len

        return path_points[-1]

    def _run_ik_animation_step(self):
        if not self._animation_start_time_qelapsed or not self.ik_animation_timer.isActive():
            return

        elapsed_ms = self._animation_start_time_qelapsed.elapsed()
        if self.animation_duration <= 0: # Avoid division by zero if duration is invalid
            self._current_animation_progress = 0.0
        else:
            self._current_animation_progress = (elapsed_ms % self.animation_duration) / float(self.animation_duration)

        if elapsed_ms >= self.animation_duration and self.animation_duration > 0:
            self._animation_start_time_qelapsed.start()

        logging.debug(f"IKManager: Animation step, Progress: {self._current_animation_progress:.2f}")

        if not self.project_parts_data:
            logging.debug("IKManager: No project parts data loaded, skipping animation step.")
            return
        if not self.sim_joints_config: # Check if IK rig is initialized
            logging.debug("IKManager: IK rig (sim_joints_config) not initialized. Skipping animation step.")
            return

        solved_something = False
        for component_config in self.sim_selectable_components:
            part_name_for_path = component_config.get('partName') # This is the visual part that HAS the path
            target_ik_joint_key = component_config.get('targetJointId') # This is the IK effector to move

            if not part_name_for_path or not target_ik_joint_key:
                continue

            if part_name_for_path in self.project_parts_data:
                part_info = self.project_parts_data[part_name_for_path]

                motion_path_obj = None
                if hasattr(part_info, 'motion_path_data') and part_info.motion_path_data:
                    motion_path_obj = part_info.motion_path_data
                elif hasattr(part_info, 'motion_path') and part_info.motion_path:
                    motion_path_obj = part_info.motion_path

                if motion_path_obj:
                    interpolated_target_pos = self._get_point_on_path(motion_path_obj, self._current_animation_progress)

                    if interpolated_target_pos:
                        logging.debug(f"IKManager: Animating IK effector '{target_ik_joint_key}' for part '{part_name_for_path}' to {interpolated_target_pos}")

                        is_two_bone = False
                        upper_limb_effector_ik_key = None

                        if target_ik_joint_key in self.sim_two_bone_ik_effectors:
                            # target_ik_joint_key is an end-effector (e.g. j_left_wrist)
                            # Its parent in sim_limb_configs IS the middle joint (e.g. j_left_elbow)
                            if target_ik_joint_key in self.sim_limb_configs:
                                middle_joint_candidate = self.sim_limb_configs[target_ik_joint_key]['parentAnchor']
                                # Check if this middle_joint_candidate is also an effector for an upper limb
                                if middle_joint_candidate in self.sim_limb_configs: # i.e. it's an elbow/knee
                                    is_two_bone = True
                                    upper_limb_effector_ik_key = middle_joint_candidate

                        if is_two_bone and upper_limb_effector_ik_key:
                            logging.debug(f"  Calling _solve_two_bone_ik for {upper_limb_effector_ik_key} -> {target_ik_joint_key}")
                            self._solve_two_bone_ik(upper_limb_effector_ik_key, target_ik_joint_key, interpolated_target_pos)
                            solved_something = True
                        elif target_ik_joint_key in self.sim_limb_configs:
                            logging.debug(f"  Calling _solve_single_bone_ik for {target_ik_joint_key}")
                            self._solve_single_bone_ik(target_ik_joint_key, interpolated_target_pos)
                            solved_something = True
                        else:
                            logging.warning(f"IKManager: IK Effector '{target_ik_joint_key}' for part '{part_name_for_path}' is not configured as a limb in sim_limb_configs.")
            else:
                logging.debug(f"IKManager: Part '{part_name_for_path}' for path not found in project_parts_data.")

        if solved_something:
            self._update_character_part_visuals_from_ik()
        else:
            logging.debug("IKManager: No IK solving performed in this animation step.")

    @property
    def sim_dynamic_joints(self) -> Dict[str, Dict[str, Any]]:
        return self._sim_dynamic_joints_data

    @sim_dynamic_joints.setter
    def sim_dynamic_joints(self, value: Dict[str, Dict[str, Any]]):
        logging.debug(f"IKManager: sim_dynamic_joints_data being set. Keys: {list(value.keys()) if isinstance(value, dict) else 'Not a dict'}")
        if not isinstance(value, dict):
            logging.error("IKManager: Attempted to set sim_dynamic_joints with non-dict value.")
            return
        self._sim_dynamic_joints_data = value

    def get_dynamic_joint_data(self, ik_joint_key: str) -> Optional[Dict[str, Any]]:
        return self._sim_dynamic_joints_data.get(ik_joint_key)

    def update_dynamic_joint_data(self, ik_joint_key: str, data: Dict[str, Any]):
        if ik_joint_key in self._sim_dynamic_joints_data:
            self._sim_dynamic_joints_data[ik_joint_key].update(data)
        else:
            self._sim_dynamic_joints_data[ik_joint_key] = data

if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    import sys

    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)

    class MockMainWindow(QObject):
        def __init__(self):
            super().__init__()
            self.skeleton_manager_ref = None # Will be set by IKManager's test
            self.project_parts_data = {
                'left_arm_lower': { # Corresponds to 'left_forearm' in ik_part_to_actual_part_name
                    'motion_path_data': [QPointF(10,10), QPointF(20,20), QPointF(10,30)],
                    'name': 'left_arm_lower' # PartInfo would have a name
                }
            }
            self.editor_tab = type('MockEditorTab', (object,), {
                'on_simulation_state_changed': lambda self, is_playing, can_reset: logging.info(f"MockEditorTab: Sim state changed: playing={is_playing}, can_reset={can_reset}")
            })()

        def statusBar(self):
            class MockStatusBar:
                def showMessage(self, msg, timeout=0):
                    logging.info(f"STATUS: {msg}")
            return MockStatusBar()

    # Mock SkeletonManager that can emit skeleton_updated
    class MockSkeletonManagerForIK(QObject):
        skeleton_updated = pyqtSignal(dict)
        def __init__(self):
            super().__init__()
            self.standardized_model_instance: Optional[StandardizedSkeletonModel] = None

        def load_and_emit_sample_skeleton(self):
            # Create a sample StandardizedSkeletonModel dictionary
            sample_joints = {
                "std_hip": StandardizedJointModel(id="std_hip", name="Hip", position=(50,200), parent_id=None, label="hip_cfg"),
                "std_lshoulder": StandardizedJointModel(id="std_lshoulder", name="LShoulder", position=(30,180), parent_id="std_hip", label="left_shoulder_cfg"),
                "std_lelbow": StandardizedJointModel(id="std_lelbow", name="LElbow", position=(10,180), parent_id="std_lshoulder", label="left_elbow_cfg"),
                "std_lhand": StandardizedJointModel(id="std_lhand", name="LHand", position=(-10,180), parent_id="std_lelbow", label="left_hand_cfg"),
            }
            sample_model = StandardizedSkeletonModel(
                joints=sample_joints,
                root_joint_ids=["std_hip"],
                hierarchy={"std_hip": ["std_lshoulder"], "std_lshoulder": ["std_lelbow"], "std_lelbow": ["std_lhand"]},
                joint_map={"hip": "std_hip", "left_shoulder": "std_lshoulder", "left_elbow": "std_lelbow", "left_hand": "std_lhand" },
                limb_lengths={"left_upper_arm": 20.0, "left_forearm": 20.0} # Matching visual part keys
            )
            self.standardized_model_instance = sample_model
            logging.info("MockSkeletonManager: Emitting sample skeleton data.")
            self.skeleton_updated.emit(sample_model.model_dump())


    mock_main = MockMainWindow()
    ik_manager = IKManager(main_window_ref=mock_main)

    mock_skeleton_manager = MockSkeletonManagerForIK()
    ik_manager.set_skeleton_manager(mock_skeleton_manager) # Connect signals

    # Simulate project load, which gives IKManager parts data (paths for animation)
    ik_manager.set_project_parts_data(mock_main.project_parts_data)

    # Trigger skeleton load in mock SkeletonManager, which should propagate to IKManager
    mock_skeleton_manager.load_and_emit_sample_skeleton()

    # Test animation if IK is initialized
    if ik_manager.ik_solver_initialized: # Check internal flag if available, or infer from sim_joints_config
        logging.info("--- IK Manager appears initialized, attempting to start animation ---")
        ik_manager.set_animation_duration(1000) # 1 second loop
        if ik_manager.start_animation():
            logging.info("Mock animation started by IKManager.")
            QTimer.singleShot(1200, ik_manager.stop_animation) # Stop after >1 loop
            QTimer.singleShot(1300, ik_manager.reset_animation_state)
            QTimer.singleShot(1500, app.quit)
            sys.exit(app.exec())
        else:
            logging.error("IKManager start_animation() returned False.")
            app.quit()
    else:
        logging.error("IK Manager did not initialize properly after skeleton load.")
        app.quit()

    logging.info("IKManager test setup complete.")