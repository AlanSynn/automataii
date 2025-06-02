"""
Inverse Kinematics (IK) Manager for Automataii.

This class will handle the logic and data related to the IK system,
including skeleton definition for IK, solving IK for limbs, and managing
IK-driven animation state.
"""
import logging
from typing import Optional, Dict, Any, List, Tuple, Set
from pathlib import Path
import math # Already present, but good to ensure
import inspect # For logging the caller in the property setter
import numpy as np

from PyQt6.QtCore import QObject, pyqtSignal, QPointF, QTimer, QElapsedTimer, QLineF
from PyQt6.QtGui import QTransform, QPainterPath

# Assuming StandardizedSkeletonModel and StandardizedJointModel are now the primary way
# SkeletonManager provides data, even if it's as a dictionary dump.
# IKManager will need to understand this structure.
from ..core.models_skeleton import StandardizedSkeletonModel, StandardizedJointModel # For type hinting if directly using models

# Placeholder for actual IK solver logic if it's separate
# from ..core.ik_solver import IKSolver # Example if you have a dedicated solver

# Helper function for vector operations if needed (e.g., angle, normalization)
def get_angle_between_points(p1: QPointF, p2: QPointF) -> float:
    return math.atan2(p2.y() - p1.y(), p2.x() - p1.x())

class IKManager(QObject):
    """Manages IK related data, setup, and solving."""

    # Signal to indicate that the character's visual parts need updating based on IK solution
    character_visuals_updated = pyqtSignal(dict) # dict might contain part names and their new transforms
    # Signal to indicate that the overall animation state has changed (e.g., playing, stopped)
    animation_state_changed = pyqtSignal(str) # e.g., "playing", "stopped", "reset"
    # skeleton_updated = pyqtSignal(object) # REMOVED - IKManager should not re-emit general skeleton updates
    ik_solver_initialized = pyqtSignal(bool, dict) # success, initial_joint_config {joint_name: {'position': QPointF, 'angle': float}}
    error_occurred = pyqtSignal(str)
    simulation_data_generated = pyqtSignal(dict) # For mechanism generation later
    skeleton_pose_updated = pyqtSignal(dict) # NEW SIGNAL for raw joint positions

    def __init__(self, main_window_ref, parent: Optional[QObject] = None): # main_window_ref for statusbar or config access initially
        super().__init__(parent)
        self.main_window = main_window_ref # Keep a reference if needed, e.g. for status messages or part items

        logging.info(f"IKManager (id:{id(self)}): Initializing IKManager instance.")

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

        # For managing initialization based on data availability
        self.__internal_current_skeleton_data: Optional[Dict[str, Any]] = None
        self._current_joint_connections: Optional[List[Tuple[str, str]]] = None
        self._pending_motion_paths: Dict[str, QPainterPath] = {}
        self._initial_snapshot: Dict[str, Any] = {} # Ensure _initial_snapshot is initialized

        # Debug: Track initialization attempts
        self._init_attempts = 0

        logging.info(f"IKManager (id:{id(self)}): IKManager instance initialized.")

    def _get_standardized_joint_id(self, abstract_or_original_name: str) -> Optional[str]:
        """Looks up the standardized joint ID from an abstract IK rig name or original source name."""
        if not self._current_skeleton_data or 'joint_map' not in self._current_skeleton_data:
            logging.error(f"IKManager: Cannot get standardized ID for '{abstract_or_original_name}'. Missing skeleton data or joint_map.")
            return None

        joint_map = self._current_skeleton_data['joint_map']

        # First, check if the abstract_or_original_name is directly a key in joint_map (original name)
        if abstract_or_original_name in joint_map:
            std_id = joint_map[abstract_or_original_name]
            # logging.debug(f"IKManager._get_standardized_joint_id: Mapped '{abstract_or_original_name}' (original) to STD ID '{std_id}'")
            return std_id

        # Second, check if it's already a standardized ID (i.e., a value in joint_map)
        # This handles cases where a standardized ID might be passed inadvertently.
        # Or if the abstract name IS the standardized name (unlikely for current rig def).
        # if abstract_or_original_name in joint_map.values():
        #     # logging.debug(f"IKManager._get_standardized_joint_id: Input '{abstract_or_original_name}' is already a STD ID.")
        #     return abstract_or_original_name

        # Third, attempt to find it by checking if any *value* in the joint_map's *values* (which are std_ids)
        # matches the input, assuming the input itself might be a standardized ID already.
        # This is a bit redundant with the above, but can be a safeguard.
        # Or, if the abstract names used in sim_limb_configs *are* the standardized names.
        # Let's assume for now the abstract names (like 'left_elbow') are keys in joint_map.

        logging.warning(f"IKManager._get_standardized_joint_id: Could not find a direct mapping for abstract/original name '{abstract_or_original_name}' in joint_map. Keys: {list(joint_map.keys())}")
        # Fallback: maybe the abstract_or_original_name IS the standardized name and was used directly.
        # Check if abstract_or_original_name exists as a key in sim_joints_config (which uses std_ids)
        if abstract_or_original_name in self.sim_joints_config:
             logging.warning(f"IKManager._get_standardized_joint_id: Name '{abstract_or_original_name}' was not in joint_map, but found as a direct key in sim_joints_config. Assuming it's a standardized ID.")
             return abstract_or_original_name

        logging.error(f"IKManager._get_standardized_joint_id: Failed to map '{abstract_or_original_name}' to any known standardized ID.")
        return None

    @property
    def _current_skeleton_data(self) -> Optional[Dict[str, Any]]:
        return self.__internal_current_skeleton_data

    @_current_skeleton_data.setter
    def _current_skeleton_data(self, value: Optional[Dict[str, Any]]):
        try:
            caller_function = inspect.stack()[1].function
        except IndexError:
            caller_function = "unknown_caller"

        old_value_state = "IS None" if self.__internal_current_skeleton_data is None else f"EXISTS (Keys: {list(self.__internal_current_skeleton_data.keys()) if self.__internal_current_skeleton_data else 'EMPTY'})"
        new_value_state = "IS None" if value is None else f"EXISTS (Keys: {list(value.keys()) if value else 'EMPTY'})"

        logging.info(f"IKManager (id:{id(self)}) @_current_skeleton_data.SETTER: Called by '{caller_function}'. Changing from '{old_value_state}' to '{new_value_state}'.")

        if value is None:
            logging.debug(f"IKManager (id:{id(self)}) @_current_skeleton_data.SETTER: Value is being set to None.")
        elif isinstance(value, dict) and 'joints' in value:
            logging.debug(f"IKManager (id:{id(self)}) @_current_skeleton_data.SETTER: Value is a dict with {len(value['joints'])} joints.")
        elif isinstance(value, dict):
            logging.debug(f"IKManager (id:{id(self)}) @_current_skeleton_data.SETTER: Value is a dict, but 'joints' key is missing. Keys: {list(value.keys())}")
        else:
            logging.debug(f"IKManager (id:{id(self)}) @_current_skeleton_data.SETTER: Value is not a dict or None. Type: {type(value)}.")

        self.__internal_current_skeleton_data = value
        # Log AFTER assignment to confirm the internal attribute's state
        confirm_state = "IS None" if self.__internal_current_skeleton_data is None else f"CONFIRMED EXISTS (Keys: {list(self.__internal_current_skeleton_data.keys()) if self.__internal_current_skeleton_data else 'EMPTY'})"
        if self.__internal_current_skeleton_data and isinstance(self.__internal_current_skeleton_data, dict) and 'joints' in self.__internal_current_skeleton_data:
            confirm_state += f", 'joints' key present with {len(self.__internal_current_skeleton_data['joints'])} items."
        elif self.__internal_current_skeleton_data and isinstance(self.__internal_current_skeleton_data, dict):
            confirm_state += f", 'joints' key MISSING."
        logging.info(f"IKManager (id:{id(self)}) @_current_skeleton_data.SETTER: __internal_current_skeleton_data is NOW {confirm_state} (post-assignment). Caller was '{caller_function}'.")

    def set_animation_duration(self, duration_ms: int):
        """Sets the total duration for one loop of the IK animation."""
        if duration_ms > 0:
            self.animation_duration = duration_ms
            logging.info(f"IKManager: Animation duration set to {duration_ms} ms.")
        else:
            logging.warning(f"IKManager: Invalid animation duration: {duration_ms} ms. Must be positive.")

    def set_skeleton_manager(self, skeleton_manager_instance: Optional['SkeletonManager']): # Use string for type hint & allow None
        old_ref_id = id(self.skeleton_manager_ref) if self.skeleton_manager_ref else None
        new_ref_id = id(skeleton_manager_instance) if skeleton_manager_instance else None
        logging.info(f"IKManager (id:{id(self)}): set_skeleton_manager called. Old ref_id: {old_ref_id}, New ref_id: {new_ref_id}. New instance type: {type(skeleton_manager_instance)}")

        if self.skeleton_manager_ref:
            try:
                # Ensure we don't double-connect if called multiple times with the same valid instance
                self.skeleton_manager_ref.skeleton_updated.disconnect(self.on_skeleton_data_updated_from_manager)
                logging.debug(f"IKManager (id:{id(self)}): Disconnected from old SkeletonManager (id:{old_ref_id}).")
            except TypeError: # Typically means it wasn't connected or ref was None already
                logging.debug(f"IKManager (id:{id(self)}): TypeError while disconnecting from old SkeletonManager (id:{old_ref_id}), might have been None or not connected.")
            except RuntimeError as e:
                 logging.warning(f"IKManager (id:{id(self)}): RuntimeError while disconnecting from old SkeletonManager (id:{old_ref_id}): {e}. This can happen if the underlying C++ object is deleted.")

        self.skeleton_manager_ref = skeleton_manager_instance

        if self.skeleton_manager_ref:
            try:
                self.skeleton_manager_ref.skeleton_updated.connect(self.on_skeleton_data_updated_from_manager)
                logging.info(f"IKManager (id:{id(self)}): Connected to new SkeletonManager (id:{new_ref_id}).")
            except Exception as e:
                logging.error(f"IKManager (id:{id(self)}): Failed to connect to new SkeletonManager (id:{new_ref_id}): {e}", exc_info=True)
        else:
            logging.warning(f"IKManager (id:{id(self)}): SkeletonManager instance was set to None.")

    def set_project_parts_data(self, parts_data: Dict[str, 'PartInfo']):
        """Sets the parts data from the current project, used for animation paths etc."""
        logging.info(f"IKManager: set_project_parts_data called. Received {len(parts_data)} parts. Pending paths: {list(self._pending_motion_paths.keys())}")
        if 'head' in parts_data:
            logging.info(f"IKManager: 'head' part IS IN incoming parts_data for set_project_parts_data.")
            head_part_info_incoming = parts_data['head']
            logging.info(f"IKManager: 'head' (incoming) motion_path_data IS {'SET' if hasattr(head_part_info_incoming, 'motion_path_data') and head_part_info_incoming.motion_path_data else 'None/Empty'}")
        else:
            logging.info(f"IKManager: 'head' part IS NOT in incoming parts_data for set_project_parts_data.")

        self.project_parts_data = parts_data.copy() # Create a copy
        if 'head' in self.project_parts_data:
            logging.info(f"IKManager: 'head' part exists in self.project_parts_data after copy.")
        else:
            logging.info(f"IKManager: 'head' part DOES NOT exist in self.project_parts_data after copy.")


        # Apply any pending motion paths that might have been set before parts data
        for part_name, path in self._pending_motion_paths.items():
            if part_name in self.project_parts_data:
                logging.info(f"IKManager: Applying pending motion path for part '{part_name}'.")
                self.project_parts_data[part_name].motion_path_data = path # motion_path_data should be QPainterPath
                if part_name == 'head':
                    logging.info(f"IKManager: Applied PENDING motion path for 'head'. Path elements: {path.elementCount() if path else 'None'}")
                    logging.info(f"IKManager: project_parts_data['head'].motion_path_data IS NOW {'SET' if self.project_parts_data['head'].motion_path_data else 'None/Empty'}")
            else:
                logging.warning(f"IKManager: Could not apply pending motion path for '{part_name}'. Part not found in self.project_parts_data after copy.")

        self._pending_motion_paths.clear()

        if 'head' in self.project_parts_data:
            head_part_info_final = self.project_parts_data['head']
            logging.info(f"IKManager: AFTER pending paths, project_parts_data['head'].motion_path_data IS {'SET' if hasattr(head_part_info_final, 'motion_path_data') and head_part_info_final.motion_path_data else 'None/Empty'}")
        else:
            logging.info(f"IKManager: AFTER pending paths, 'head' part still not in self.project_parts_data.")


        self._try_initialize_solver()

    def _try_initialize_solver(self) -> None:
        """
        Attempts to initialize the IK solver if all necessary data (skeleton, parts) is present.
        """
        self._init_attempts += 1
        log_msg_skel = "IS None" if self._current_skeleton_data is None else f"EXISTS (Keys: {list(self._current_skeleton_data.keys()) if self._current_skeleton_data else 'EMPTY'})"
        if self._current_skeleton_data and 'joints' in self._current_skeleton_data:
            log_msg_skel += f", 'joints' key present with {len(self._current_skeleton_data['joints'])} items."
        elif self._current_skeleton_data:
            log_msg_skel += f", 'joints' key MISSING."

        log_msg_parts = "IS Empty/None" if not self.project_parts_data else f"EXISTS ({len(self.project_parts_data)} parts)"
        logging.debug(f"IKManager: _try_initialize_solver attempt #{self._init_attempts}. Skeleton data details: {log_msg_skel}. Parts data: {log_msg_parts}")

        if not self._current_skeleton_data or not self._current_skeleton_data.get('joints'): # Check for 'joints' key specifically
            logging.info("IKManager: _try_initialize_solver: Still waiting for valid skeleton data (must exist and contain a 'joints' key).")
            # Do not emit False here, as parts might be set and skeleton is pending (or vice-versa)
            return

        if not self.project_parts_data:
            logging.info("IKManager: _try_initialize_solver: Still waiting for project parts data.")
            # Do not emit False here
            return

        # If we reach here, both skeleton and parts data are present.
        logging.info("IKManager: _try_initialize_solver: Prerequisites met (skeleton & parts data). Proceeding with full IK solver initialization attempt.")
        # Clear previous solver state before attempting new initialization
        # but keep self._current_skeleton_data and self.project_parts_data
        self.stop_animation()
        self.ik_solver = None
        self.dynamic_joints.clear()
        # self.sim_joints_config.clear() # This will be repopulated by initialize_ik_solver
        self.scene_joints_snapshot.clear()
        self._clear_ik_definitions(emit_signal=False) # <--- Make sure this is clear_ik_definitions

        success = self.initialize_ik_solver() # This method will use _current_skeleton_data and project_parts_data
        if success:
            logging.info("IKManager: IK Solver initialized successfully.")
            self.ik_solver_initialized.emit(True, self.sim_joints_config.copy())
        else:
            logging.error("IKManager: IK Solver initialization FAILED.")
            self.ik_solver_initialized.emit(False, {})

    def initialize_ik_solver(self) -> bool:
        """
        Initializes the IK solver with the current skeleton and parts data.
        This involves defining IK chains, end-effectors, and their motion paths.
        Returns True if successful, False otherwise.
        """
        if not self._current_skeleton_data or not self._current_skeleton_data.get('joints'): # Check for 'joints' key
            logging.error("IKManager: Cannot initialize solver, skeleton data (or its 'joints') is missing.")
            return False
        if not self.project_parts_data:
            logging.error("IKManager: Cannot initialize solver, project parts data is missing.")
            return False

        self.ik_solver = "DummySolver" # Mark as initialized
        logging.info("IKManager: (Placeholder) IK solver marked as initialized.")

        self._sim_dynamic_joints_data.clear() # Use the internal attribute directly
        self.sim_joints_config.clear()
        # self.scene_joints_snapshot.clear() # This was an old attribute, use _initial_snapshot
        self._initial_snapshot.clear() # Now guaranteed to exist

        logging.debug(f"IKManager DEBUG: About to iterate self._current_skeleton_data['joints']. Item count: {len(self._current_skeleton_data['joints']) if 'joints' in self._current_skeleton_data else 'joints key missing'}")
        for joint_id, joint_data_dict in self._current_skeleton_data['joints'].items():
            logging.debug(f"IKManager DEBUG: Processing joint_id: {joint_id}, joint_data: {joint_data_dict}")
            pos_list = joint_data_dict.get('position')
            logging.debug(f"IKManager DEBUG:   pos_list for {joint_id}: {pos_list}")

            if pos_list and len(pos_list) == 2:
                self.sim_joints_config[joint_id] = {
                    'position': QPointF(pos_list[0], pos_list[1]),
                    'angle': 0.0, # Initial angle
                    'parent': joint_data_dict.get('parent_id'), # Use 'parent_id'
                    'name': joint_id, # Store the joint's own id (original name from char_cfg)
                    'children': joint_data_dict.get('child_ids', []) # Store children if available
                }
                # A more robust way to define dynamic joints is needed based on rig definition.
                # For now, let's assume most non-root joints could be dynamic.
                # Standardized names are like 'left_shoulder', 'hip', 'head'.
                # Example: mark limb joints as dynamic
                if "hip" not in joint_id.lower() and \
                   "neck" not in joint_id.lower() and \
                   "head" != joint_id.lower() and \
                   "torso" != joint_id.lower(): # Crude exclusion of some base/central joints
                    self._sim_dynamic_joints_data[joint_id] = self.sim_joints_config[joint_id].copy()
                    logging.debug(f"IKManager DEBUG:     Added {joint_id} to _sim_dynamic_joints_data.")
                else:
                    logging.debug(f"IKManager DEBUG:     {joint_id} NOT added to _sim_dynamic_joints_data based on name filter.")
            else:
                logging.warning(f"IKManager WARNING: Could not populate sim_joints_config for {joint_id} due to missing/invalid position data: {pos_list}")

        self._initial_snapshot = {
            name: data.copy() for name, data in self.sim_joints_config.items()
        }

        num_dynamic_joints = len(self._sim_dynamic_joints_data)
        num_snapshot_items = len(self._initial_snapshot)
        num_sim_config_joints = len(self.sim_joints_config)

        # ---- ADD DEBUG LOGS ----
        logging.debug(f"IKManager DEBUG: num_sim_config_joints = {num_sim_config_joints}")
        logging.debug(f"IKManager DEBUG: num_dynamic_joints = {num_dynamic_joints}")
        logging.debug(f"IKManager DEBUG: num_snapshot_items = {num_snapshot_items}")
        # ---- END DEBUG LOGS ----

        logging.info(f"IKManager: Initialization complete. Configured joints: {num_sim_config_joints}. Dynamic joints: {num_dynamic_joints}. Items in initial snapshot: {num_snapshot_items}.")
        logging.debug("IKManager DEBUG: Past the 'Initialization complete' log.") # DEBUG

        # --- Populate IK Rig Specific Data ---
        # These should ideally be loaded from a rig definition file or derived more robustly.

        # 1. Define which components are selectable/animatable via paths
        self.sim_selectable_components = [
            {'name': 'Head Control',        'partName': 'head',           'targetJointId': 'neck'}, # CHANGED targetJointId to 'neck'
            {'name': 'Left Hand Control',   'partName': 'left_arm_lower', 'targetJointId': 'left_hand'},
            {'name': 'Right Hand Control',  'partName': 'right_arm_lower','targetJointId': 'right_hand'},
            # Add other controls as needed
            {'name': 'Left Foot Control',   'partName': 'left_leg_lower', 'targetJointId': 'left_foot'},
            {'name': 'Right Foot Control',  'partName': 'right_leg_lower','targetJointId': 'right_foot'},
            # {'name': 'Torso Control',       'partName': 'torso',          'targetJointId': 'hip'}, # or 'torso' if 'torso' is an IK joint
        ]
        logging.debug(f"IKManager: Populated sim_selectable_components: {self.sim_selectable_components}")

        # 2. Define which targetJointIds are end-effectors of two-bone IK chains
        self.sim_two_bone_ik_effectors = ['left_hand', 'right_hand', 'left_foot', 'right_foot']
        logging.debug(f"IKManager: Populated sim_two_bone_ik_effectors: {self.sim_two_bone_ik_effectors}")

        # 3. Define limb configurations (parent anchor and part label for length lookup)
        # Keys are the 'effector' joint IDs (middle or end).
        # 'label' should correspond to keys in visual part names for length.
        self.sim_limb_configs = {
            # 'head':         {'parentAnchor': 'neck',          'label': 'head'}, # REMOVED - Head is controlled by 'neck' IK joint directly
            'left_elbow':   {'parentAnchor': 'left_shoulder', 'label': 'left_arm_upper'},
            'left_hand':    {'parentAnchor': 'left_elbow',    'label': 'left_arm_lower'},
            'right_elbow':  {'parentAnchor': 'right_shoulder','label': 'right_arm_upper'},
            'right_hand':   {'parentAnchor': 'right_elbow',   'label': 'right_arm_lower'},
            # Add legs if they are part of the animated drawing skeleton and parts
            'left_knee':    {'parentAnchor': 'left_hip',      'label': 'left_leg_upper'},
            'left_foot':    {'parentAnchor': 'left_knee',     'label': 'left_leg_lower'},
            'right_knee':   {'parentAnchor': 'right_hip',     'label': 'right_leg_upper'},
            'right_foot':   {'parentAnchor': 'right_foot',    'label': 'right_leg_lower'},
        }
        logging.debug(f"IKManager: Populated sim_limb_configs: {self.sim_limb_configs}")

        # 4. Define preferred bend directions for middle joints (e.g., elbows, knees)
        # 1 for positive bend (e.g. elbow bends "forwards"), -1 for negative ("backwards")
        # These are relative to a default pose or a plane.
        self.sim_joint_bend_directions = {
            'left_elbow': 1,
            'right_elbow': 1,
            'left_knee': -1,  # 무릎은 보통 뒤로 굽혀짐
            'right_knee': -1,
        }
        logging.debug(f"IKManager: Populated sim_joint_bend_directions: {self.sim_joint_bend_directions}")

        # 5. Populate sim_limb_lengths from project_parts_data
        # This uses the 'label' from sim_limb_configs as the key into project_parts_data (visual part name)
        self.sim_limb_lengths.clear()
        for limb_effector_key, config in self.sim_limb_configs.items():
            part_label_for_length = config.get('label')
            if part_label_for_length and part_label_for_length in self.project_parts_data:
                part_info = self.project_parts_data[part_label_for_length]
                # Calculate length: distance from its anchor point to some "tip" or use bounding box
                # For simplicity, let's use height of bounding box if available, or a default.
                # A more accurate measure would be distance between joint connection points defined on the part.
                length = 0
                if part_info.roi and len(part_info.roi) == 4: # x,y,w,h
                    length = float(part_info.roi[3]) # Use height as a proxy for length
                if length <= 0: length = 50 # Default length if ROI is bad or part has no height
                self.sim_limb_lengths[part_label_for_length] = length
                logging.debug(f"IKManager: Set limb length for '{part_label_for_length}' to {length}")
            elif part_label_for_length:
                logging.warning(f"IKManager: Part '{part_label_for_length}' for length measurement not found in project_parts_data. Using default for {limb_effector_key}.")
                self.sim_limb_lengths[part_label_for_length] = 50 # Default length

        logging.debug(f"IKManager: Populated sim_limb_lengths: {self.sim_limb_lengths}")
        # --- End Populate IK Rig ---

        return True

    def on_skeleton_data_updated_from_manager(self, standardized_skeleton_dict: Optional[dict]): # Allow None
        """Called when SkeletonManager emits its skeleton_updated signal (with a dict)."""
        logging.info(f"IKManager (id:{id(self)}): Received skeleton update (dict) from SkeletonManager.")
        if not standardized_skeleton_dict:
            logging.warning(f"IKManager (id:{id(self)}): Received empty skeleton dict. Clearing IK definitions.")
            self._clear_ik_definitions()
            self.ik_solver_initialized.emit(False, {})
            self._current_skeleton_data = None # Explicitly nullify if skeleton is gone (will use setter)
            # logging.info(f"IKManager (id:{id(self)}): self._current_skeleton_data is NOW None (due to empty input dict).") # Setter will log this
            return

        try:
            standardized_model = StandardizedSkeletonModel.model_validate(standardized_skeleton_dict)
            self._current_skeleton_data = standardized_model.model_dump() # Will use setter
            self._current_joint_connections = standardized_model.hierarchy

            # log_msg_skel_on_update = "IS None" if self._current_skeleton_data is None else f"EXISTS (Keys: {list(self._current_skeleton_data.keys()) if self._current_skeleton_data else 'EMPTY'})" # Getter will be used
            # if self._current_skeleton_data and 'joints' in self._current_skeleton_data:
            #     log_msg_skel_on_update += f", 'joints' key present with {len(self._current_skeleton_data['joints'])} items."
            # elif self._current_skeleton_data:
            #     log_msg_skel_on_update += f", 'joints' key MISSING."
            # logging.info(f"IKManager (id:{id(self)}).on_skeleton_data_updated: self._current_skeleton_data successfully SET. Details: {log_msg_skel_on_update}") # Setter logs details

            self._try_initialize_solver()
        except Exception as e:
            logging.error(f"IKManager (id:{id(self)}): Error processing standardized skeleton dict: {e}", exc_info=True)
            self._clear_ik_definitions()
            self._current_skeleton_data = None # Explicitly nullify on error (will use setter)
            # logging.info(f"IKManager (id:{id(self)}): self._current_skeleton_data is NOW None (due to exception).") # Setter will log this
            self.ik_solver_initialized.emit(False, {})
            self.error_occurred.emit(f"Error initializing IK from skeleton: {e}")

    def _clear_ik_definitions(self, emit_signal=True) -> None:
        """Clears IK solver-derived configurations and resets animation state.
           Does NOT clear input data like _current_skeleton_data or project_parts_data.
        """
        logging.info(f"IKManager (id:{id(self)}): Clearing IK solver-derived definitions and animation state.")
        self.stop_animation() # Stops timer and resets animation variables
        self.ik_solver = None

        # Clear structures derived/populated by initialize_ik_solver or during IK processing
        if hasattr(self, '_sim_dynamic_joints_data'):
            self._sim_dynamic_joints_data.clear()
        if hasattr(self, 'sim_joints_config'): # This is also a primary output of initialization
            self.sim_joints_config.clear()
        if hasattr(self, 'sim_limb_configs'):
            self.sim_limb_configs.clear()
        if hasattr(self, 'sim_limb_lengths'):
            self.sim_limb_lengths.clear()
        if hasattr(self, 'scene_joints_snapshot'): # Populated during initialization
            self.scene_joints_snapshot.clear()
        if hasattr(self, 'sim_selectable_components'):
            self.sim_selectable_components.clear()
        if hasattr(self, 'sim_two_bone_ik_effectors'):
            self.sim_two_bone_ik_effectors.clear()
        if hasattr(self, 'sim_joint_bend_directions'):
            self.sim_joint_bend_directions.clear()

        # DO NOT clear these here: _current_skeleton_data, _current_joint_connections, _pending_motion_paths
        # They are input data for the IK solver.

        if emit_signal:
            self.ik_solver_initialized.emit(False, {})
            logging.debug(f"IKManager (id:{id(self)}): Emitted ik_solver_initialized(False) due to _clear_ik_definitions.")

    def reset_all_ik_systems_and_data(self) -> None: # Renamed from clear_ik_data
        """Clears ALL data including project parts, current skeleton, and IK definitions."""
        logging.info(f"IKManager (id:{id(self)}): Clearing ALL IK data (full clear including skeleton and parts references) via reset_all_ik_systems_and_data.")
        self.project_parts_data.clear()
        self._pending_motion_paths.clear()
        self._current_skeleton_data = None # Will use setter
        self._current_joint_connections = None
        self._clear_ik_definitions(emit_signal=True)
        logging.info(f"IKManager (id:{id(self)}): All IK data cleared and state reset (after reset_all_ik_systems_and_data).")

    def _solve_single_bone_ik(self, target_joint_abstract_name: str, anchor_joint_abstract_name: str, target_position: np.ndarray) -> Dict[str, Dict[str, Any]]:
        """
        Solves IK for a single bone (e.g., head controlled by neck, anchored at torso).
        The target_joint_abstract_name ('neck') is placed at target_position.
        The anchor_joint_abstract_name ('torso') is its base.
        """
        updated_configs: Dict[str, Dict[str, Any]] = {}

        target_joint_id_std = self._get_standardized_joint_id(target_joint_abstract_name) # std_id for "neck"
        if not target_joint_id_std:
            logging.warning(f"IKM._solve_single_bone_ik: Could not find standardized ID for target joint '{target_joint_abstract_name}'.")
            return {}

        anchor_joint_id_std = self._get_standardized_joint_id(anchor_joint_abstract_name) # std_id for "torso"
        if not anchor_joint_id_std:
            logging.warning(f"IKM._solve_single_bone_ik: Could not find standardized ID for anchor joint '{anchor_joint_abstract_name}'.")
            return {}

        # --- BEGIN ADDED DEBUG LOGGING ---
        logging.debug(f"IKM._solve_single_bone_ik: Attempting to solve for target_abs='{target_joint_abstract_name}' (std='{target_joint_id_std}') "
                      f"anchored by anchor_abs='{anchor_joint_abstract_name}' (std='{anchor_joint_id_std}') at target_pos={target_position}.")
        logging.debug(f"IKM._solve_single_bone_ik: Current self.sim_joints_config keys: {list(self.sim_joints_config.keys())}")

        if self._current_skeleton_data:
            joint_map_debug = self._current_skeleton_data.get('joint_map', {})
            source_map_debug = self._current_skeleton_data.get('source_to_std_id_map', {})
            skeleton_joints_keys_debug = list(self._current_skeleton_data.get('joints', {}).keys())
            logging.debug(f"IKM._solve_single_bone_ik: joint_map provided by SkeletonManager: {joint_map_debug}")
            logging.debug(f"IKM._solve_single_bone_ik: source_to_std_id_map provided by SkeletonManager: {source_map_debug}")
            logging.debug(f"IKM._solve_single_bone_ik: Standardized joint IDs from SkeletonManager (these are the expected keys for sim_joints_config): {skeleton_joints_keys_debug}")
        else:
            logging.warning("IKM._solve_single_bone_ik: self._current_skeleton_data is None, cannot log joint maps.")
        # --- END ADDED DEBUG LOGGING ---

        # The anchor_joint_id_std is the joint that remains fixed or is the base of this single bone.
        # Its current position is the base from which the target_joint_id_std will be placed.
        if anchor_joint_id_std not in self.sim_joints_config: # Check if the resolved anchor_joint_id_std is actually in sim_joints_config
            logging.error(f"IKM._solve_single_bone_ik: Anchor joint ID '{anchor_joint_id_std}' (derived from abstract '{anchor_joint_abstract_name}') "
                          f"NOT FOUND in sim_joints_config. This will cause a KeyError. Available keys: {list(self.sim_joints_config.keys())}")
            return {}
        base_joint_pos = self.sim_joints_config[anchor_joint_id_std]['position'] # ERROR LIKELY HERE if anchor_joint_id_std is not a valid key

        # For a single bone, the target joint simply moves to the target_position.
        updated_configs[target_joint_id_std] = {
            'position': QPointF(target_position[0], target_position[1]),
            'angle': 0.0,
            'parent': anchor_joint_id_std,
            'name': target_joint_id_std,
            'children': []
        }

        return updated_configs

    def _solve_two_bone_ik(self, root_pos: QPointF, target_pos: QPointF, length1: float, length2: float, root_joint_std_id: str) -> Optional[Tuple[QPointF, QPointF]]:
        """
        Solves 2-bone IK for a given root, target, and bone lengths.
        Returns (middle_joint_pos, end_effector_pos) or None if unsolvable.
        """
        p0 = root_pos
        target = target_pos
        l1 = length1
        l2 = length2

        if l1 <= 0 or l2 <= 0:
            logging.error(f"IKM: Invalid bone lengths l1={l1}, l2={l2} for {root_joint_std_id}. Cannot solve.")
            safe_l1 = l1 if l1 > 0 else 1.0
            safe_l2 = l2 if l2 > 0 else 1.0
            p1_bail = QPointF(p0.x(), p0.y() + safe_l1)
            p2_bail = QPointF(p1_bail.x(), p1_bail.y() + safe_l2)
            return p1_bail, p2_bail

        dx = target.x() - p0.x()
        dy = target.y() - p0.y()
        dist_sq = dx*dx + dy*dy
        dist = math.sqrt(dist_sq) if dist_sq > 1e-12 else 0.0

        bend_direction = float(self.sim_joint_bend_directions.get(root_joint_std_id, -1.0)) # Default to -1 for typical elbow/knee

        # Constants from __init__ or class level
        # _max_elbow_flexion_deg = self.DEFAULT_MAX_ELBOW_FLEXION_DEG (assuming these are set)
        # _epsilon_dist = self.DEFAULT_EPSILON_DIST
        # _near_max_reach_threshold = self.DEFAULT_NEAR_MAX_REACH_THRESHOLD
        # _near_min_reach_threshold = self.DEFAULT_NEAR_MIN_REACH_THRESHOLD
        # Ensure these are accessible, e.g., self._max_elbow_flexion_deg if defined in __init__
        # For safety, let's use direct values if not sure about self.DEFAULT_... availability here.
        # It's better if these are correctly initialized as self. _max_elbow_flexion_deg etc. in __init__

        _max_elbow_flexion_deg = getattr(self, '_max_elbow_flexion_deg', 160.0)
        _epsilon_dist = getattr(self, '_epsilon_dist', 1.0)
        _near_max_reach_threshold = getattr(self, '_near_max_reach_threshold', 5.0)
        _near_min_reach_threshold = getattr(self, '_near_min_reach_threshold', 5.0)


        min_elbow_internal_angle_rad = math.pi - math.radians(_max_elbow_flexion_deg)
        min_elbow_internal_angle_rad = max(0.0, min(math.pi, min_elbow_internal_angle_rad))

        cos_min_elbow_angle = math.cos(min_elbow_internal_angle_rad)
        d_min_sq_with_limit = l1*l1 + l2*l2 - 2*l1*l2*cos_min_elbow_angle
        if d_min_sq_with_limit < 0: d_min_sq_with_limit = 0
        d_min_with_limit = math.sqrt(d_min_sq_with_limit)

        # Case 1: Target is extremely close to the root joint.
        if dist < _epsilon_dist:
            logging.debug(f"  IKM ({root_joint_std_id}): Target AT ROOT ({dist:.2f} < {_epsilon_dist}). Using rest orientation.")
            # Ensure sim_joint_rest_angles is initialized and accessible
            # sim_joint_rest_angles = getattr(self, 'sim_joint_rest_angles', {})
            base_angle_rad = math.radians(self.sim_joint_rest_angles.get(root_joint_std_id, 90.0))
            p1_x = p0.x() + l1 * math.cos(base_angle_rad)
            p1_y = p0.y() + l1 * math.sin(base_angle_rad)
            p1_new = QPointF(p1_x, p1_y)
            angle_of_bone2_from_p1 = base_angle_rad + bend_direction * (math.pi - min_elbow_internal_angle_rad)
            p2_x = p1_new.x() + l2 * math.cos(angle_of_bone2_from_p1)
            p2_y = p1_new.y() + l2 * math.sin(angle_of_bone2_from_p1)
            p2_new = QPointF(p2_x, p2_y)
            return p1_new, p2_new

        # Case 2: Target is too far (or very close to max reach). Straighten limb towards target.
        elif dist >= (l1 + l2 - _near_max_reach_threshold):
            logging.debug(f"  IKM ({root_joint_std_id}): Target TOO FAR/near max reach ({dist:.2f} vs {l1+l2:.2f}). Forcing straight.")
            angle_root_to_target = math.atan2(dy, dx)
            p1_x = p0.x() + l1 * math.cos(angle_root_to_target)
            p1_y = p0.y() + l1 * math.sin(angle_root_to_target)
            p1_new = QPointF(p1_x, p1_y)
            p2_x = p1_new.x() + l2 * math.cos(angle_root_to_target)
            p2_y = p1_new.y() + l2 * math.sin(angle_root_to_target)
            p2_new = QPointF(p2_x, p2_y)
            return p1_new, p2_new

        # Case 3: Target is too close for the elbow's flexion limit.
        elif dist < (d_min_with_limit + _near_min_reach_threshold):
            logging.debug(f"  IKM ({root_joint_std_id}): Target TOO CLOSE for flexion limit ({dist:.2f} vs {d_min_with_limit:.2f}). Aiming with max fold.")
            angle_root_to_target = math.atan2(dy, dx)
            dist_eff = d_min_with_limit

            if dist_eff < _epsilon_dist: # d_min_with_limit is near zero
                 logging.debug(f"  IKM ({root_joint_std_id}): d_min_with_limit is near zero. Using rest pose logic (from Case 3).")
                 # sim_joint_rest_angles = getattr(self, 'sim_joint_rest_angles', {})
                 base_angle_rad = math.radians(self.sim_joint_rest_angles.get(root_joint_std_id, 90.0))
                 p1_x = p0.x() + l1 * math.cos(base_angle_rad)
                 p1_y = p0.y() + l1 * math.sin(base_angle_rad)
                 p1_new = QPointF(p1_x, p1_y)
                 angle_of_bone2_from_p1 = base_angle_rad + bend_direction * (math.pi - min_elbow_internal_angle_rad)
                 p2_x = p1_new.x() + l2 * math.cos(angle_of_bone2_from_p1)
                 p2_y = p1_new.y() + l2 * math.sin(angle_of_bone2_from_p1)
                 p2_new = QPointF(p2_x, p2_y)
                 return p1_new, p2_new

            cos_alpha_eff_numerator = dist_eff*dist_eff + l1*l1 - l2*l2
            cos_alpha_eff_denominator = 2 * dist_eff * l1

            if abs(cos_alpha_eff_denominator) < 1e-9:
                logging.warning(f"  IKM ({root_joint_std_id}): Denominator zero in Case 3 alpha. Fallback straighten to target dir with max fold.")
                p1_x_f = p0.x() + l1 * math.cos(angle_root_to_target)
                p1_y_f = p0.y() + l1 * math.sin(angle_root_to_target)
                p1_new_f = QPointF(p1_x_f, p1_y_f)
                angle_bone2_world_f = angle_root_to_target + bend_direction * (math.pi - min_elbow_internal_angle_rad)
                p2_x_f = p1_new_f.x() + l2 * math.cos(angle_bone2_world_f)
                p2_y_f = p1_new_f.y() + l2 * math.sin(angle_bone2_world_f)
                p2_new_f = QPointF(p2_x_f, p2_y_f)
                return p1_new_f, p2_new_f

            cos_alpha_eff = cos_alpha_eff_numerator / cos_alpha_eff_denominator
            cos_alpha_eff = max(-1.0, min(1.0, cos_alpha_eff))
            alpha_eff_rad = math.acos(cos_alpha_eff)

            angle1_final_rad = angle_root_to_target - (bend_direction * alpha_eff_rad)

            p1_x = p0.x() + l1 * math.cos(angle1_final_rad)
            p1_y = p0.y() + l1 * math.sin(angle1_final_rad)
            p1_new = QPointF(p1_x, p1_y)

            angle_elbow_bend_from_bone1_line_rad = bend_direction * (math.pi - min_elbow_internal_angle_rad)

            p2_x = p1_new.x() + l2 * math.cos(angle1_final_rad + angle_elbow_bend_from_bone1_line_rad)
            p2_y = p1_new.y() + l2 * math.sin(angle1_final_rad + angle_elbow_bend_from_bone1_line_rad)
            p2_new = QPointF(p2_x, p2_y)
            return p1_new, p2_new

        # Case 4: Standard triangle solve
        else:
            logging.debug(f"  IKM ({root_joint_std_id}): Target in normal range ({dist:.2f}). Triangle solve.")
            l1_sq = l1*l1
            l2_sq = l2*l2

            cos_angle2_numerator = l1_sq + l2_sq - dist_sq
            cos_angle2_denominator = 2 * l1 * l2

            if abs(cos_angle2_denominator) < 1e-9:
                 logging.warning(f"  IKM ({root_joint_std_id}): Denominator zero for cos_angle2. Fallback straighten.")
                 angle_root_to_target_s = math.atan2(dy, dx)
                 p1_x_s = p0.x() + l1 * math.cos(angle_root_to_target_s)
                 p1_y_s = p0.y() + l1 * math.sin(angle_root_to_target_s)
                 p1_new_s = QPointF(p1_x_s, p1_y_s)
                 p2_x_s = p1_new_s.x() + l2 * math.cos(angle_root_to_target_s)
                 p2_y_s = p1_new_s.y() + l2 * math.sin(angle_root_to_target_s)
                 p2_new_s = QPointF(p2_x_s, p2_y_s)
                 return p1_new_s, p2_new_s

            cos_angle2 = cos_angle2_numerator / cos_angle2_denominator
            cos_angle2 = max(-1.0, min(1.0, cos_angle2))
            angle2_triangle_rad = math.acos(cos_angle2)

            angle2_triangle_rad = max(angle2_triangle_rad, min_elbow_internal_angle_rad)

            cos_alpha_numerator = dist_sq + l1_sq - l2_sq
            cos_alpha_denominator = 2 * dist * l1

            if abs(cos_alpha_denominator) < 1e-9:
                 logging.warning(f"  IKM ({root_joint_std_id}): Denominator zero for cos_alpha. Fallback straighten.")
                 angle_root_to_target_s2 = math.atan2(dy, dx)
                 p1_x_s2 = p0.x() + l1 * math.cos(angle_root_to_target_s2)
                 p1_y_s2 = p0.y() + l1 * math.sin(angle_root_to_target_s2)
                 p1_new_s2 = QPointF(p1_x_s2, p1_y_s2)
                 angle_bone2_world_s2 = angle_root_to_target_s2 + bend_direction * (math.pi - angle2_triangle_rad)
                 p2_x_s2 = p1_new_s2.x() + l2 * math.cos(angle_bone2_world_s2)
                 p2_y_s2 = p1_new_s2.y() + l2 * math.sin(angle_bone2_world_s2)
                 p2_new_s2 = QPointF(p2_x_s2, p2_y_s2)
                 return p1_new_s2, p2_new_s2

            cos_alpha = cos_alpha_numerator / cos_alpha_denominator
            cos_alpha = max(-1.0, min(1.0, cos_alpha))
            alpha_rad = math.acos(cos_alpha)

            angle_root_to_target_rad = math.atan2(dy, dx)
            angle1_final_rad = angle_root_to_target_rad - (bend_direction * alpha_rad)

            p1_x = p0.x() + l1 * math.cos(angle1_final_rad)
            p1_y = p0.y() + l1 * math.sin(angle1_final_rad)
            p1_new = QPointF(p1_x, p1_y)

            angle_elbow_bend_from_bone1_line_rad = bend_direction * (math.pi - angle2_triangle_rad)

            p2_x = p1_new.x() + l2 * math.cos(angle1_final_rad + angle_elbow_bend_from_bone1_line_rad)
            p2_y = p1_new.y() + l2 * math.sin(angle1_final_rad + angle_elbow_bend_from_bone1_line_rad)
            p2_new = QPointF(p2_x, p2_y)

            return p1_new, p2_new

    def _update_character_part_visuals_from_ik(self) -> None:
        """
        Updates the visual representation of character parts based on solved IK joint positions.
        This involves deriving part positions/rotations from global IK joint configurations.
        Emits `character_visuals_updated` signal.
        """
        updated_visuals: Dict[str, Dict[str, Any]] = {}
        processed_visual_parts: Set[str] = set()

        if not self.project_parts_data:
            logging.warning("IKManager FK: Missing project_parts_data for FK update.")
            return
        if not self.sim_joints_config:
            logging.warning("IKManager FK: Missing sim_joints_config for FK update.")
            return
        if not self.sim_limb_configs:
            logging.warning("IKManager FK: Missing sim_limb_configs for FK update (limb segments might not be processed correctly).")
            # Continue, as some parts might still be processable via sim_selectable_components
        if not self._current_skeleton_data or 'joint_map' not in self._current_skeleton_data:
            logging.error("IKManager FK: Missing skeleton data or joint_map for FK update.")
            return

        # 애니메이션 진행률이 0이면 모든 파트를 초기 상태(월드 앵글 0)로 설정
        is_initial_state = abs(self._current_animation_progress) < 1e-6

        # 1. Process Limb Segments first
        # These are parts that visually represent a bone between two IK joints.
        # Example: 'left_arm_upper' (visual part) is defined by 'left_shoulder' (parent IK) and 'left_elbow' (child IK).
        logging.debug(f"IKManager FK: Processing {len(self.sim_limb_configs)} limb configs. Is initial state: {is_initial_state}")
        # sim_limb_configs: keys are abstract effector names (e.g. 'left_elbow', 'left_hand')
        # values contain abstract parentAnchor names (e.g. 'left_shoulder', 'left_elbow')
        for ik_effector_abstract_name, limb_config_data in self.sim_limb_configs.items():
            parent_ik_anchor_abstract_name = limb_config_data.get('parentAnchor')
            visual_part_name = limb_config_data.get('label') # This label should match a key in project_parts_data

            if not parent_ik_anchor_abstract_name or not visual_part_name:
                logging.warning(f"IKManager FK: Skipping limb config for abstract effector '{ik_effector_abstract_name}' due to missing parentAnchor or label.")
                continue

            if visual_part_name not in self.project_parts_data:
                logging.warning(f"IKManager FK: Visual part '{visual_part_name}' for limb (effector '{ik_effector_abstract_name}') not found in project_parts_data.")
                continue

            parent_ik_anchor_std_id = self._get_standardized_joint_id(parent_ik_anchor_abstract_name)
            ik_effector_std_id = self._get_standardized_joint_id(ik_effector_abstract_name)

            if not parent_ik_anchor_std_id or not ik_effector_std_id:
                logging.warning(f"IKManager FK: Could not get standardized IDs for limb '{visual_part_name}' (parent_abs: '{parent_ik_anchor_abstract_name}', effector_abs: '{ik_effector_abstract_name}').")
                continue

            if parent_ik_anchor_std_id not in self.sim_joints_config or ik_effector_std_id not in self.sim_joints_config:
                logging.warning(f"IKManager FK: Standardized IK joints '{parent_ik_anchor_std_id}' or '{ik_effector_std_id}' for limb '{visual_part_name}' not found in sim_joints_config.")
                continue

            # --- BEGIN ADDED DEBUG LOGGING (Limb - Parent) ---
            parent_joint_config_entry = self.sim_joints_config.get(parent_ik_anchor_std_id)
            logging.debug(f"IKManager FK (Limb Parent Check): For visual part '{visual_part_name}', parent IK std_id '{parent_ik_anchor_std_id}'. sim_joints_config entry: {parent_joint_config_entry}")
            # --- END ADDED DEBUG LOGGING ---
            parent_ik_joint_pos = self.sim_joints_config[parent_ik_anchor_std_id].get('position')

            # --- BEGIN ADDED DEBUG LOGGING (Limb - Child/Effector) ---
            child_joint_config_entry = self.sim_joints_config.get(ik_effector_std_id)
            logging.debug(f"IKManager FK (Limb Child Check): For visual part '{visual_part_name}', child/effector IK std_id '{ik_effector_std_id}'. sim_joints_config entry: {child_joint_config_entry}")
            # --- END ADDED DEBUG LOGGING ---
            child_ik_joint_pos = self.sim_joints_config[ik_effector_std_id].get('position')

            if not parent_ik_joint_pos or not child_ik_joint_pos:
                logging.warning(f"IKManager FK: Missing position data for standardized IK joints '{parent_ik_anchor_std_id}' or '{ik_effector_std_id}'.")
                continue

            position_for_visual = parent_ik_joint_pos

            # 초기 상태에서는 회전을 0으로 설정
            if is_initial_state:
                rotation_for_visual_deg = 0.0
            else:
                delta_x = child_ik_joint_pos.x() - parent_ik_joint_pos.x()
                delta_y = child_ik_joint_pos.y() - parent_ik_joint_pos.y()
                rotation_for_visual_rad = math.atan2(delta_y, delta_x)
                rotation_for_visual_deg = math.degrees(rotation_for_visual_rad)

            updated_visuals[visual_part_name] = {
                'pos_x': position_for_visual.x(),   # NEW WAY
                'pos_y': position_for_visual.y(),   # NEW WAY
                'rotation_degrees': rotation_for_visual_deg
            }
            processed_visual_parts.add(visual_part_name)
            logging.debug(f"IKManager FK (Limb): Updated '{visual_part_name}' (ParentIK_abs: {parent_ik_anchor_abstract_name}/{parent_ik_anchor_std_id}, ChildIK_abs: {ik_effector_abstract_name}/{ik_effector_std_id}). Pos_x: {position_for_visual.x()}, Pos_y: {position_for_visual.y()}, Rot: {rotation_for_visual_deg:.1f}")

        # 2. Process Other Controlled Parts (e.g., head, torso, if not covered by limbs)
        logging.debug(f"IKManager FK: Processing {len(self.sim_selectable_components)} selectable components for non-limb parts. Is initial state: {is_initial_state}")
        # sim_selectable_components: values contain abstract targetJointId
        for component_config in self.sim_selectable_components:
            visual_part_name = component_config.get('partName')
            target_ik_joint_abstract_name = component_config.get('targetJointId')

            if not visual_part_name or not target_ik_joint_abstract_name:
                logging.warning(f"IKManager FK: Skipping selectable component due to missing partName or targetJointId: {component_config.get('name')}")
                continue

            if visual_part_name in processed_visual_parts:
                logging.debug(f"IKManager FK: Visual part '{visual_part_name}' already processed as a limb segment. Skipping.")
                continue

            if visual_part_name not in self.project_parts_data:
                logging.warning(f"IKManager FK: Visual part '{visual_part_name}' for selectable component '{component_config.get('name')}' not in project_parts_data.")
                continue

            target_ik_joint_std_id = self._get_standardized_joint_id(target_ik_joint_abstract_name)
            if not target_ik_joint_std_id:
                logging.warning(f"IKManager FK: Could not get standardized ID for target abstract joint '{target_ik_joint_abstract_name}' of selectable '{visual_part_name}'.")
                continue

            if target_ik_joint_std_id not in self.sim_joints_config:
                logging.warning(f"IKManager FK: Target standardized IK joint '{target_ik_joint_std_id}' (from abstract '{target_ik_joint_abstract_name}') for selectable '{visual_part_name}' not in sim_joints_config.")
                continue

            target_ik_joint_data = self.sim_joints_config[target_ik_joint_std_id]
            # --- BEGIN ADDED DEBUG LOGGING (Selectable Target) ---
            logging.debug(f"IKManager FK (Selectable Target Check): For visual part '{visual_part_name}', target IK std_id '{target_ik_joint_std_id}'. Full entry from sim_joints_config: {target_ik_joint_data}")
            # --- END ADDED DEBUG LOGGING ---
            position_for_visual = target_ik_joint_data.get('position')

            if not position_for_visual:
                logging.warning(f"IKManager FK: Missing position data for target standardized IK joint '{target_ik_joint_std_id}'.")
                continue

            # 초기 상태에서는 회전을 0으로 설정
            if is_initial_state:
                rotation_for_visual_deg = 0.0
            else:
                rotation_for_visual_deg = 0.0
                # The 'parent' stored in sim_joints_config[target_ik_joint_std_id] IS already a standardized ID (or None)
                parent_of_target_ik_joint_std_id = target_ik_joint_data.get('parent')

                if parent_of_target_ik_joint_std_id and parent_of_target_ik_joint_std_id in self.sim_joints_config:
                    parent_ik_joint_data = self.sim_joints_config[parent_of_target_ik_joint_std_id]
                    parent_ik_joint_pos = parent_ik_joint_data.get('position')
                    if parent_ik_joint_pos:
                        delta_x = position_for_visual.x() - parent_ik_joint_pos.x()
                        delta_y = position_for_visual.y() - parent_ik_joint_pos.y()
                        if abs(delta_x) > 1e-6 or abs(delta_y) > 1e-6:
                            rotation_rad = math.atan2(delta_y, delta_x)
                            rotation_for_visual_deg = math.degrees(rotation_rad)
                        else:
                            rotation_for_visual_deg = target_ik_joint_data.get('angle', 0.0)
                            logging.debug(f"IKManager FK: Target STD IK '{target_ik_joint_std_id}' and parent STD '{parent_of_target_ik_joint_std_id}' at same pos. Using stored angle {rotation_for_visual_deg:.1f} for '{visual_part_name}'.")
                    else:
                        rotation_for_visual_deg = target_ik_joint_data.get('angle', 0.0)
                        logging.debug(f"IKManager FK: Parent STD IK '{parent_of_target_ik_joint_std_id}' missing pos. Using stored angle {rotation_for_visual_deg:.1f} for '{visual_part_name}'.")
                else:
                    rotation_for_visual_deg = target_ik_joint_data.get('angle', 0.0)
                    logging.debug(f"IKManager FK: No parent for target STD IK '{target_ik_joint_std_id}'. Using stored angle {rotation_for_visual_deg:.1f} for '{visual_part_name}'.")

            updated_visuals[visual_part_name] = {
                'pos_x': position_for_visual.x(),   # NEW WAY
                'pos_y': position_for_visual.y(),   # NEW WAY
                'rotation_degrees': rotation_for_visual_deg
            }
            processed_visual_parts.add(visual_part_name)
            logging.debug(f"IKManager FK (Selectable): Updated '{visual_part_name}' (TargetIK_abs: {target_ik_joint_abstract_name}/{target_ik_joint_std_id}). Pos_x: {position_for_visual.x()}, Pos_y: {position_for_visual.y()}, Rot: {rotation_for_visual_deg:.1f}")

        if updated_visuals:
            logging.info(f"IKManager FK: Emitting character_visuals_updated with {len(updated_visuals)} parts.")
            self.character_visuals_updated.emit(updated_visuals)
        else:
            logging.debug("IKManager FK: No visual updates to emit from FK process.")

        # 3. IK 체인을 구성하여 solve_ik_ccd 호출 (다리 움직임을 위해)
        if hasattr(self.main_window, 'editor_tab') and self.main_window.editor_tab:
            editor_items = self.main_window.editor_tab.current_editor_items

            # 왼쪽 다리 IK 체인 구성
            left_leg_chain = []
            if 'torso' in editor_items:
                left_leg_chain.append(editor_items['torso'])
            if 'left_leg_upper' in editor_items:
                left_leg_chain.append(editor_items['left_leg_upper'])
            if 'left_leg_lower' in editor_items:
                left_leg_chain.append(editor_items['left_leg_lower'])

            # 왼발 목표 위치가 있으면 IK 적용
            if len(left_leg_chain) >= 2 and 'left_foot' in self.sim_joints_config:
                target_pos = self.sim_joints_config['left_foot'].get('position')
                if target_pos:
                    from ..kinematics.ik_solver import solve_ik_ccd
                    logging.debug(f"IKManager: Applying CCD IK for left leg chain with {len(left_leg_chain)} items")
                    solve_ik_ccd(left_leg_chain, target_pos, iterations=10, tolerance=1.0)

            # 오른쪽 다리 IK 체인 구성
            right_leg_chain = []
            if 'torso' in editor_items:
                right_leg_chain.append(editor_items['torso'])
            if 'right_leg_upper' in editor_items:
                right_leg_chain.append(editor_items['right_leg_upper'])
            if 'right_leg_lower' in editor_items:
                right_leg_chain.append(editor_items['right_leg_lower'])

            # 오른발 목표 위치가 있으면 IK 적용
            if len(right_leg_chain) >= 2 and 'right_foot' in self.sim_joints_config:
                target_pos = self.sim_joints_config['right_foot'].get('position')
                if target_pos:
                    from ..kinematics.ik_solver import solve_ik_ccd
                    logging.debug(f"IKManager: Applying CCD IK for right leg chain with {len(right_leg_chain)} items")
                    solve_ik_ccd(right_leg_chain, target_pos, iterations=10, tolerance=1.0)

            # 왼쪽 팔 IK 체인 구성
            left_arm_chain = []
            if 'torso' in editor_items:
                left_arm_chain.append(editor_items['torso'])
            if 'left_arm_upper' in editor_items:
                left_arm_chain.append(editor_items['left_arm_upper'])
            if 'left_arm_lower' in editor_items:
                left_arm_chain.append(editor_items['left_arm_lower'])

            # 왼손 목표 위치가 있으면 IK 적용
            if len(left_arm_chain) >= 2 and 'left_hand' in self.sim_joints_config:
                target_pos = self.sim_joints_config['left_hand'].get('position')
                if target_pos:
                    from ..kinematics.ik_solver import solve_ik_ccd
                    logging.debug(f"IKManager: Applying CCD IK for left arm chain with {len(left_arm_chain)} items")
                    solve_ik_ccd(left_arm_chain, target_pos, iterations=10, tolerance=1.0)

            # 오른쪽 팔 IK 체인 구성
            right_arm_chain = []
            if 'torso' in editor_items:
                right_arm_chain.append(editor_items['torso'])
            if 'right_arm_upper' in editor_items:
                right_arm_chain.append(editor_items['right_arm_upper'])
            if 'right_arm_lower' in editor_items:
                right_arm_chain.append(editor_items['right_arm_lower'])

            # 오른손 목표 위치가 있으면 IK 적용
            if len(right_arm_chain) >= 2 and 'right_hand' in self.sim_joints_config:
                target_pos = self.sim_joints_config['right_hand'].get('position')
                if target_pos:
                    from ..kinematics.ik_solver import solve_ik_ccd
                    logging.debug(f"IKManager: Applying CCD IK for right arm chain with {len(right_arm_chain)} items")
                    solve_ik_ccd(right_arm_chain, target_pos, iterations=10, tolerance=1.0)

    # --- Animation Control Methods (to be moved/adapted from MainWindow) ---
    def start_animation(self):
        """Starts the IK-driven animation."""
        solver_ok = self.ik_solver is not None
        dynamic_joints_ok = bool(self.dynamic_joints) and len(self.dynamic_joints) > 0
        snapshot_ok = bool(self._initial_snapshot) and len(self._initial_snapshot) > 0

        logging.debug(f"IKManager.start_animation Conditions: solver_ok: {solver_ok} (solver: {self.ik_solver}), dynamic_joints_ok: {dynamic_joints_ok} (len: {len(self.dynamic_joints if self.dynamic_joints is not None else [])}), snapshot_ok: {snapshot_ok} (len: {len(self._initial_snapshot if self._initial_snapshot is not None else [])})")

        if not (solver_ok and dynamic_joints_ok and snapshot_ok):
            logging.warning("IKManager: Cannot start animation. Pre-conditions not met (solver, dynamic joints, or snapshot).")
            self.animation_state_changed.emit("stopped") # Notify that animation attempt failed
            # self.main_window.statusBar().showMessage("Animation cannot start: IK not ready.", 3000) # MainWindow should listen to animation_state_changed
            return

        if self._animation_start_time_qelapsed and self._animation_start_time_qelapsed.isValid() and not self._animation_start_time_qelapsed.hasExpired(0):
            logging.debug("IKManager: Animation already started.")
            return

        animation_possible = False
        for part_name, part_info in self.project_parts_data.items(): # Iterate with names for logging
            has_path = part_info.motion_path_data and not part_info.motion_path_data.isEmpty()
            if has_path:
                animation_possible = True
                break
        # The previous combined loop was incorrect. This simplified check is better for now.
        # The original outer loop for dynamic_joints was not used effectively.

        if not animation_possible:
            logging.warning("IKManager: Cannot start animation. No motion paths defined for any parts in project_parts_data.")
            self.main_window.statusBar().showMessage("Animation cannot start: No motion paths defined.", 3000)
            return

        # 애니메이션 시작 전에 모든 파트를 초기 상태로 리셋
        logging.info("IKManager: Resetting all parts to initial state before starting animation.")
        # if hasattr(self.main_window, 'editor_tab') and self.main_window.editor_tab:
        #     editor_items = self.main_window.editor_tab.current_editor_items
        #     for part_name, part_item in editor_items.items():
        #         # 각 파트의 회전을 0으로 리셋
        #         part_item.setRotation(0.0)
        #         # 초기 월드 회전값도 0으로 확인
        #         if not hasattr(part_item, '_initial_world_rotation'):
        #             part_item._initial_world_rotation = 0.0

                # 파트의 초기 위치로 이동 (PartInfo에서)
                # if part_name in self.project_parts_data:
                #     part_info = self.project_parts_data[part_name]
                #     part_item.setPos(QPointF(part_info.x, part_info.y))

        # 스켈레톤 조인트도 초기 상태로 리셋
        if self._initial_snapshot:
            self.sim_joints_config = {k: v.copy() for k, v in self._initial_snapshot.items()}
            self._sim_dynamic_joints_data = {k: v.copy() for k, v in self._initial_snapshot.items() if k in self._sim_dynamic_joints_data}

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
        """Resets the animation state to initial state."""
        self.stop_animation()

        # 스켈레톤 조인트를 초기 상태로 리셋
        if self._initial_snapshot:
            logging.info("IKManager: Resetting animation state from initial snapshot.")
            self.sim_joints_config = {k: v.copy() for k, v in self._initial_snapshot.items()}
            self._sim_dynamic_joints_data = {k: v.copy() for k, v in self._initial_snapshot.items() if k in self._sim_dynamic_joints_data}
        else:
            logging.warning("IKManager: No initial snapshot available for reset.")
            return

        # 모든 파트를 초기 상태(월드 앵글 0)로 리셋
        if hasattr(self.main_window, 'editor_tab') and self.main_window.editor_tab:
            editor_items = self.main_window.editor_tab.current_editor_items
            for part_name, part_item in editor_items.items():
                # 각 파트의 회전을 0으로 리셋
                part_item.setRotation(0.0)
                # 초기 월드 회전값도 0으로 확인
                if not hasattr(part_item, '_initial_world_rotation'):
                    part_item._initial_world_rotation = 0.0

                # 파트의 초기 위치로 이동 (PartInfo에서)
                if part_name in self.project_parts_data:
                    part_info = self.project_parts_data[part_name]
                    part_item.setPos(QPointF(part_info.x, part_info.y))

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
            return # Animation not running or timer not active

        elapsed_ms = self._animation_start_time_qelapsed.elapsed()
        if self.animation_duration <= 0: # Avoid division by zero if duration is invalid
            self._current_animation_progress = 0.0
        else:
            self._current_animation_progress = (elapsed_ms % self.animation_duration) / float(self.animation_duration)

        if elapsed_ms >= self.animation_duration and self.animation_duration > 0:
            # Loop the animation by restarting the elapsed timer
            self._animation_start_time_qelapsed.start()
            # Ensure progress resets to 0 at the exact loop point
            # This might be slightly off due to timer granularity, but usually fine.

        # Ensure progress is strictly within [0, 1) for path calculations
        if self._current_animation_progress >= 1.0:
            self._current_animation_progress = 0.0 # Loop
        # Or stop: self.stop_animation(); return

        logging.debug(f"IKManager._run_ik_animation_step: Progress {self._current_animation_progress:.2f}")

        if not self.project_parts_data:
            logging.warning("IKManager._run_ik_animation_step: Missing project_parts_data.")
            return

        if not self.sim_joints_config: # Check if the IK rig definition is loaded
            logging.warning("IKManager._run_ik_animation_step: Missing sim_joints_config (IK not fully initialized).")
            return

        if not self.sim_selectable_components:
            logging.warning("IKManager._run_ik_animation_step: No sim_selectable_components defined.")
            return

        if not self._current_skeleton_data or 'joint_map' not in self._current_skeleton_data:
            logging.error("IKManager._run_ik_animation_step: Missing skeleton data or joint_map.")
            return

        # This is where the core IK logic happens and self.dynamic_joints gets updated.
        # The existing logic iterates sim_selectable_components, finds paths, solves IK, and updates dynamic_joints.
        # We will assume that by the end of this loop, self.dynamic_joints contains the latest animated joint positions.

        # --- Existing IK solving logic (simplified representation) ---
        for component in self.sim_selectable_components:
            target_ik_joint_abstract_name = component.get('targetJointId') # e.g., j_left_wrist
            if not target_ik_joint_abstract_name:
                continue

            part_name_for_path = component.get('partName') # e.g., left_arm_lower (visual part this IK component drives)
            part_info = self.project_parts_data.get(part_name_for_path)

            if part_info and part_info.motion_path_data:
                motion_path_obj = part_info.motion_path_data # This should be QPainterPath
                target_pos_on_path = self._get_point_on_path(motion_path_obj, self._current_animation_progress)

                if target_pos_on_path:
                    if target_ik_joint_abstract_name in self.sim_two_bone_ik_effectors:
                        # This is the effector joint (e.g., 'left_hand')
                        effector_limb_config = self.sim_limb_configs.get(target_ik_joint_abstract_name)
                        if not effector_limb_config:
                            logging.warning(f"IKM._run_ik_animation_step: No limb config for effector '{target_ik_joint_abstract_name}'.")
                            continue

                        middle_joint_abstract_name = effector_limb_config.get('parentAnchor') # e.g., 'left_elbow'
                        part_label_for_l2 = effector_limb_config.get('label') # e.g., 'left_arm_lower' (visual part for bone l2)

                        if not middle_joint_abstract_name or not part_label_for_l2:
                            logging.warning(f"IKM._run_ik_animation_step: Incomplete limb config for effector '{target_ik_joint_abstract_name}' (missing parentAnchor or label).")
                            continue

                        # Now find the root joint and the label for l1 using the middle joint's config
                        middle_limb_config = self.sim_limb_configs.get(middle_joint_abstract_name)
                        if not middle_limb_config:
                            logging.warning(f"IKM._run_ik_animation_step: No limb config for middle joint '{middle_joint_abstract_name}'.")
                            continue

                        root_joint_abstract_name = middle_limb_config.get('parentAnchor') # e.g., 'left_shoulder'
                        part_label_for_l1 = middle_limb_config.get('label') # e.g., 'left_arm_upper' (visual part for bone l1)

                        if not root_joint_abstract_name or not part_label_for_l1:
                            logging.warning(f"IKM._run_ik_animation_step: Incomplete limb config for middle joint '{middle_joint_abstract_name}' (missing parentAnchor or label).")
                            continue

                        # Get standardized IDs
                        root_std_id = self._get_standardized_joint_id(root_joint_abstract_name)
                        middle_std_id = self._get_standardized_joint_id(middle_joint_abstract_name)
                        effector_std_id = self._get_standardized_joint_id(target_ik_joint_abstract_name) # This is the target

                        if not root_std_id or not middle_std_id or not effector_std_id:
                            logging.warning(f"IKM._run_ik_animation_step: Could not get all std IDs for chain {root_joint_abstract_name} -> {middle_joint_abstract_name} -> {target_ik_joint_abstract_name}.")
                            continue

                        # Get current root position (p0 for the 2-bone IK solver)
                        if root_std_id not in self.sim_joints_config or 'position' not in self.sim_joints_config[root_std_id]:
                            logging.warning(f"IKM._run_ik_animation_step: Root joint '{root_std_id}' (from abstract '{root_joint_abstract_name}') position not found in sim_joints_config.")
                            continue
                        current_root_pos_for_ik = self.sim_joints_config[root_std_id]['position'] # This is a QPointF

                        # Get bone lengths
                        length1 = self.sim_limb_lengths.get(part_label_for_l1)
                        length2 = self.sim_limb_lengths.get(part_label_for_l2)

                        if length1 is None or length2 is None or length1 <= 0 or length2 <= 0: # Check for positive lengths
                            logging.warning(f"IKM._run_ik_animation_step: Invalid or missing lengths for chain: l1 (part '{part_label_for_l1}')={length1}, l2 (part '{part_label_for_l2}')={length2}.")
                            continue

                        logging.debug(f"IKM._run_ik_animation_step: Calling _solve_two_bone_ik for: "
                                      f"root_pos={current_root_pos_for_ik}, target_pos={target_pos_on_path}, "
                                      f"l1={length1}, l2={length2}, root_joint_std_id='{root_std_id}'")

                        # Call the solver
                        # def _solve_two_bone_ik(self, root_pos: QPointF, target_pos: QPointF, length1: float, length2: float, root_joint_std_id: str)
                        solved_points = self._solve_two_bone_ik(current_root_pos_for_ik, target_pos_on_path, length1, length2, root_std_id)

                        if solved_points:
                            p1_new, p2_new = solved_points # p1_new is the new middle joint, p2_new is the new effector joint
                            # Update sim_joints_config with new positions
                            if middle_std_id in self.sim_joints_config:
                                self.sim_joints_config[middle_std_id]['position'] = p1_new
                            else:
                                logging.warning(f"IKM._run_ik_animation_step: Middle joint std_id '{middle_std_id}' not found in sim_joints_config to update position.")

                            if effector_std_id in self.sim_joints_config:
                                self.sim_joints_config[effector_std_id]['position'] = p2_new
                            else:
                                logging.warning(f"IKM._run_ik_animation_step: Effector joint std_id '{effector_std_id}' not found in sim_joints_config to update position.")

                            logging.debug(f"  IKM Solved and updated: Middle ('{middle_std_id}') -> {p1_new}, Effector ('{effector_std_id}') -> {p2_new}")
                        else:
                            logging.warning(f"IKM._run_ik_animation_step: _solve_two_bone_ik returned None for chain rooted at '{root_std_id}' (abstract: '{root_joint_abstract_name}').")
                    else: # Assume single point control / 1-bone IK
                        # Find anchor for 1-bone IK
                        limb_config = self.sim_limb_configs.get(target_ik_joint_abstract_name)
                        anchor_joint_abstract_name = limb_config.get('parentAnchor') if limb_config else None
                        if anchor_joint_abstract_name:
                            # Correctly use the result of _solve_single_bone_ik
                            solved_single_bone_data = self._solve_single_bone_ik(target_ik_joint_abstract_name, anchor_joint_abstract_name, np.array([target_pos_on_path.x(), target_pos_on_path.y()]))
                            if solved_single_bone_data:
                                for joint_std_id, data_updates in solved_single_bone_data.items():
                                    if joint_std_id in self.sim_joints_config:
                                        self.sim_joints_config[joint_std_id].update(data_updates)
                                    else:
                                        # This case should ideally not happen if solver is initialized properly
                                        self.sim_joints_config[joint_std_id] = data_updates
                                    logging.debug(f"IKM._run_ik_animation_step: Updated sim_joints_config for '{joint_std_id}' from _solve_single_bone_ik.")
                        else:
                            # This case might mean the joint is a root or directly manipulated, not part of a limb chain here.
                            # Or it's a component that doesn't move via IK but has a path (e.g. root itself moving along a path)
                            # We might need to update its position directly if so.
                            target_std_id = self._get_standardized_joint_id(target_ik_joint_abstract_name)
                            if target_std_id and target_std_id in self.sim_joints_config: # Check sim_joints_config now
                                self.sim_joints_config[target_std_id]['position'] = target_pos_on_path
                                # Potentially update angle if it's a root or has a fixed orientation relative to path
                                logging.debug(f"IKM._run_ik_animation_step: Directly moved joint '{target_std_id}' (from abs '{target_ik_joint_abstract_name}') to path position {target_pos_on_path}.")
                            else:
                                logging.warning(f"IKManager._run_ik_animation_step: Could not apply single-point control for abstract joint '{target_ik_joint_abstract_name}'. STD ID '{target_std_id}' not found or not in sim_joints_config.")
                else:
                    logging.debug(f"IKManager._run_ik_animation_step: No target_pos_on_path for component '{part_name_for_path}' at progress {self._current_animation_progress:.2f}.")
            else:
                logging.debug(f"IKManager._run_ik_animation_step: No motion path for component linked to IK joint abstract name '{target_ik_joint_abstract_name}'. Single-bone IK cannot be attempted without a target. Skipping for this component.")
        # --- End of existing IK solving logic (simplified) ---

        # After all IK updates, dynamic_joints holds the current pose.
        # Now, update character part visuals based on the new IK pose.
        self._update_character_part_visuals_from_ik() # This emits character_visuals_updated for parts

        # NEW: Prepare and emit raw joint positions for SkeletonGraphicsItem
        # Populate from self.sim_joints_config as it's the most up-to-date source of solved positions
        animated_joint_scene_positions: Dict[str, Tuple[float, float]] = {}
        if self.sim_joints_config:
            for joint_std_id, joint_data in self.sim_joints_config.items():
                pos = joint_data.get('position') # position is a QPointF
                if pos is not None: # Ensure position exists and is a QPointF
                    animated_joint_scene_positions[joint_std_id] = (pos.x(), pos.y())
                else:
                    logging.warning(f"IKManager._run_ik_animation_step: Joint '{joint_std_id}' in sim_joints_config missing 'position' QPointF data.")

        if animated_joint_scene_positions:
            self.skeleton_pose_updated.emit(animated_joint_scene_positions)

    def get_world_rotation_degrees(self, transform: QTransform) -> float:
        """Extracts rotation in degrees from a QTransform object."""
        # atan2(shearY, scaleY)
        # atan2(m21, m11) for rotation can be ambiguous with scaling/shearing.
        # A more robust way might be needed if complex transforms are used.
        # For simple rotation and uniform scaling:
        # angle_rad = math.atan2(transform.m21(), transform.m11())
        # However, QTransform.rotation() is intended for this but works on QMatrix, not QTransform directly.
        # Let's use a common approach for 2D affine transform:
        # rotation = atan2(m21/scaleX, m11/scaleX) or atan2(m12/scaleY, m22/scaleY) (careful with sign)
        # For QTransform, m11, m12, m21, m22 store scale, shear, and rotation.
        # If no shear and uniform scale sx=sy=s: m11=s*cos, m21=s*sin -> atan2(m21,m11) works.
        # If scale is not 1, it cancels out in atan2(s*sin, s*cos).
        # This should be reasonably robust for transforms typically applied to QGraphicsItems (translation, rotation, scale).
        angle_rad = math.atan2(transform.m21(), transform.m11())
        return math.degrees(angle_rad)

    def capture_current_scene_pose_as_initial(self):
        """
        Captures the current visual pose of character parts from the scene
        and sets this as the new initial pose for the IK skeleton.
        """
        logging.info("IKM: Attempting to capture current scene pose as initial IK state.")
        if not self.main_window or not hasattr(self.main_window, 'editor_tab') or \
           not self.main_window.editor_tab or not hasattr(self.main_window.editor_tab, 'current_editor_items'):
            logging.error("IKM: Editor tab or current_editor_items not accessible.")
            self.error_occurred.emit("Editor data not found for capturing pose.")
            return

        scene_items = self.main_window.editor_tab.current_editor_items
        if not scene_items:
            logging.error("IKM: No current editor items in editor tab.")
            self.error_occurred.emit("No scene items to capture pose from.")
            return

        if not self._current_skeleton_data or 'joints' not in self._current_skeleton_data:
            logging.error("IKM: Skeleton data not loaded. Cannot capture pose.")
            self.error_occurred.emit("Skeleton data not loaded.")
            return
        if not self.project_parts_data:
            logging.error("IKM: Project parts data not loaded. Cannot capture pose.")
            self.error_occurred.emit("Project parts data not loaded.")
            return
        if not self.sim_joints_config:
            logging.warning("IKM: sim_joints_config is empty. Attempting to initialize solver first.")
            # Try to initialize if it hasn't been, this populates sim_limb_configs etc.
            if not self.initialize_ik_solver():
                logging.error("IKM: Failed to initialize IK solver. Cannot capture pose.")
                self.error_occurred.emit("IK Solver failed to initialize.")
                return
            if not self.sim_joints_config: # Check again after attempt
                logging.error("IKM: sim_joints_config still empty after initialization attempt.")
                self.error_occurred.emit("IK Solver state invalid after init.")
                return


        new_sim_joints_config = {jid: data.copy() for jid, data in self.sim_joints_config.items()}
        processed_visual_parts = set()

        # Phase 1: Handle the torso/root first, as other parts might be relative to it implicitly
        # This is a heuristic. A more robust way would be to define a clear root visual part.
        # Let's assume "torso" visual part dictates the position/orientation of the "hip" IK joint.
        torso_visual_part_name = "torso"
        hip_ik_abstract_name = "hip" # As defined in char_cfg.yaml, mapped by ik_joint_ids_to_source_names or directly.
                                   # Or use the root joint from skeleton_manager if available.

        if torso_visual_part_name in scene_items and torso_visual_part_name in self.project_parts_data:
            torso_scene_item = scene_items[torso_visual_part_name]
            hip_std_id = self._get_standardized_joint_id(hip_ik_abstract_name)

            if hip_std_id and hip_std_id in new_sim_joints_config:
                new_sim_joints_config[hip_std_id]['position'] = torso_scene_item.scenePos()
                new_sim_joints_config[hip_std_id]['angle'] = self.get_world_rotation_degrees(torso_scene_item.sceneTransform())
                logging.debug(f"IKM_Capture: Set root IK joint '{hip_std_id}' from visual part '{torso_visual_part_name}' "
                              f"Pos: {new_sim_joints_config[hip_std_id]['position']}, Angle: {new_sim_joints_config[hip_std_id]['angle']:.2f}")
                processed_visual_parts.add(torso_visual_part_name)


        # Phase 2: Process limb segments defined in sim_limb_configs
        # These visual parts define a bone between two IK joints.
        for ik_effector_abs, limb_config in self.sim_limb_configs.items():
            parent_anchor_abs = limb_config.get('parentAnchor')
            visual_part_label = limb_config.get('label') # This is the key for project_parts_data & scene_items

            if not parent_anchor_abs or not visual_part_label:
                logging.warning(f"IKM_Capture: Skipping limb config for effector '{ik_effector_abs}' due to missing parent or label.")
                continue
            if visual_part_label not in scene_items:
                logging.warning(f"IKM_Capture: Visual part '{visual_part_label}' for limb not in scene_items. Skipping.")
                continue
            if visual_part_label not in self.sim_limb_lengths or self.sim_limb_lengths[visual_part_label] <= 0:
                logging.warning(f"IKM_Capture: Missing or invalid length for visual part '{visual_part_label}'. Skipping.")
                continue

            scene_part_item = scene_items[visual_part_label]
            parent_anchor_std = self._get_standardized_joint_id(parent_anchor_abs)
            child_effector_std = self._get_standardized_joint_id(ik_effector_abs)

            if not parent_anchor_std or not child_effector_std:
                logging.warning(f"IKM_Capture: Could not get std IDs for limb '{visual_part_label}'. Skipping.")
                continue
            if parent_anchor_std not in new_sim_joints_config or child_effector_std not in new_sim_joints_config:
                logging.warning(f"IKM_Capture: Std joints for limb '{visual_part_label}' not in config. Skipping.")
                continue

            # The visual part's scenePos is its pivot, assumed to be at the parent_anchor_std joint.
            current_parent_pos = scene_part_item.scenePos()
            current_part_world_angle_deg = self.get_world_rotation_degrees(scene_part_item.sceneTransform())

            new_sim_joints_config[parent_anchor_std]['position'] = current_parent_pos
            # The 'angle' for the parent_anchor_std should represent the orientation of the bone segment
            # that starts at parent_anchor_std and ends at child_effector_std.
            new_sim_joints_config[parent_anchor_std]['angle'] = current_part_world_angle_deg

            length = self.sim_limb_lengths[visual_part_label]
            rad_angle = math.radians(current_part_world_angle_deg)
            new_child_effector_pos = QPointF(
                current_parent_pos.x() + length * math.cos(rad_angle),
                current_parent_pos.y() + length * math.sin(rad_angle)
            )
            new_sim_joints_config[child_effector_std]['position'] = new_child_effector_pos
            # The 'angle' for child_effector_std will be determined if it's a parent in another limb_config,
            # or by sim_selectable_components if it's a terminal joint with its own visual part.
            logging.debug(f"IKM_Capture: Processed limb visual part '{visual_part_label}'.")
            logging.debug(f"  Parent IK '{parent_anchor_std}': Pos={current_parent_pos}, Angle={current_part_world_angle_deg:.2f}")
            logging.debug(f"  Child IK  '{child_effector_std}': Pos={new_child_effector_pos}")
            processed_visual_parts.add(visual_part_label)

        # Phase 3: Process other selectable components (e.g., head)
        # These might be terminal parts or parts whose primary IK joint wasn't a parent_anchor in sim_limb_configs.
        for comp_config in self.sim_selectable_components:
            visual_part_name = comp_config.get('partName') # Visual part driving this
            target_ik_joint_abs = comp_config.get('targetJointId') # IK joint being controlled

            if not visual_part_name or not target_ik_joint_abs:
                continue
            if visual_part_name in processed_visual_parts and \
               any(limb_cfg.get('label') == visual_part_name for limb_cfg in self.sim_limb_configs.values()):
                # This visual part was already used to define a limb segment.
                # Its corresponding IK joints (parent and child of that segment) are already set.
                # We might only care about the target_ik_joint_abs if it's an *effector* of that limb
                # and this selectable_component is meant to set its *terminal orientation*.
                # For now, if visual_part_name was a limb label, assume its IK joints are mostly handled.
                # The 'angle' of the effector might need specific handling here if this component
                # defines its independent rotation.
                log_msg_skip_sel = (f"IKM_Capture: Visual part '{visual_part_name}' for selectable target '{target_ik_joint_abs}' "
                                    f"was already processed as a limb label. ")

                # Check if target_ik_joint_abs is an effector from sim_limb_configs
                target_ik_joint_std_check = self._get_standardized_joint_id(target_ik_joint_abs)
                is_effector_of_limb = False
                if target_ik_joint_std_check:
                     is_effector_of_limb = any(self._get_standardized_joint_id(eff_abs) == target_ik_joint_std_check
                                              for eff_abs in self.sim_limb_configs.keys())

                if is_effector_of_limb:
                    # The position of this target_ik_joint (effector) was set by limb processing.
                    # This selectable_component might be intended to set its *angle* if it's a terminal joint.
                    scene_item = scene_items.get(visual_part_name)
                    if scene_item and target_ik_joint_std_check in new_sim_joints_config:
                        # Assume visual_part_name's rotation defines the angle of the target_ik_joint_std itself.
                        # This is for terminal joints like hands, feet, head.
                        new_sim_joints_config[target_ik_joint_std_check]['angle'] = self.get_world_rotation_degrees(scene_item.sceneTransform())
                        logging.debug(log_msg_skip_sel + f"Updated angle of IK effector '{target_ik_joint_std_check}' to {new_sim_joints_config[target_ik_joint_std_check]['angle']:.2f} based on visual '{visual_part_name}'.")
                    else:
                        logging.debug(log_msg_skip_sel + "Skipping further updates for this selectable component.")
                else:
                     logging.debug(log_msg_skip_sel + "Skipping (not a direct effector of a processed limb).")
                continue # Move to next selectable component

            if visual_part_name not in scene_items:
                logging.warning(f"IKM_Capture: Visual part '{visual_part_name}' for selectable component not in scene_items. Skipping.")
                continue

            scene_item = scene_items[visual_part_name]
            target_ik_joint_std = self._get_standardized_joint_id(target_ik_joint_abs)

            if not target_ik_joint_std or target_ik_joint_std not in new_sim_joints_config:
                logging.warning(f"IKM_Capture: Target IK joint '{target_ik_joint_abs}' (std: {target_ik_joint_std}) for visual '{visual_part_name}' not valid. Skipping.")
                continue

            # This handles parts like "head" (visual) controlled by "neck" (IK joint)
            # where "neck" is not a parent_anchor of a limb defined by "head" visual part.
            new_sim_joints_config[target_ik_joint_std]['position'] = scene_item.scenePos()
            new_sim_joints_config[target_ik_joint_std]['angle'] = self.get_world_rotation_degrees(scene_item.sceneTransform())
            logging.debug(f"IKM_Capture: Processed selectable component for visual part '{visual_part_name}'.")
            logging.debug(f"  Target IK '{target_ik_joint_std}': Pos={new_sim_joints_config[target_ik_joint_std]['position']}, Angle={new_sim_joints_config[target_ik_joint_std]['angle']:.2f}")
            processed_visual_parts.add(visual_part_name)


        # Finalize
        self.sim_joints_config = new_sim_joints_config
        self._initial_snapshot = {k: v.copy() for k, v in self.sim_joints_config.items()}
        logging.info("IKM: Successfully captured current scene pose and updated initial snapshot.")

        # Trigger visual updates to reflect the new initial pose
        self._update_character_part_visuals_from_ik() # Emits character_visuals_updated

        final_joint_scene_positions = {
            jid: (data['position'].x(), data['position'].y())
            for jid, data in self.sim_joints_config.items() if 'position' in data and data['position'] is not None
        }
        if final_joint_scene_positions:
            self.skeleton_pose_updated.emit(final_joint_scene_positions)

        self.animation_state_changed.emit("reset") # Notify UI that state has been reset
        if self.main_window and hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage("IK pose reset to current scene configuration.", 3000)

    def set_initial_pose_from_visual_data(self, visual_parts_data: Dict[str, Dict[str, Any]]):
        """
        Sets the initial pose of the IK skeleton based on a provided dictionary of visual part transforms.
        Assumes initialize_ik_solver() has already run and populated sim_limb_configs, etc.

        Args:
            visual_parts_data: Dict where keys are visual part names (e.g., "head", "left_arm_upper")
                               and values are dicts {'position': QPointF, 'rotation_degrees': float},
                               representing the desired scene position of the part's pivot and its world rotation.
        """
        logging.info(f"IKM: Setting initial pose from provided visual data for {len(visual_parts_data)} parts.")

        if not self._current_skeleton_data or 'joints' not in self._current_skeleton_data:
            logging.error("IKM: Skeleton data not loaded. Cannot set initial pose from visuals.")
            self.error_occurred.emit("Skeleton data not loaded for pose setting.")
            return
        if not self.project_parts_data: # Need this for part info like which IK joint a visual part maps to.
            logging.error("IKM: Project parts data not loaded. Cannot map visual parts to IK joints.")
            self.error_occurred.emit("Project parts data not loaded for pose setting.")
            return
        if not self.sim_joints_config or not self.sim_limb_configs or not self.sim_limb_lengths:
            logging.warning("IKM: Core IK rig definitions (sim_joints_config, sim_limb_configs, sim_limb_lengths) "
                            "are not yet populated. Attempting to run initialize_ik_solver().")
            if not self.initialize_ik_solver(): # This populates based on skeleton and part dimensions
                logging.error("IKM: Failed to initialize IK solver. Cannot set pose from visuals.")
                self.error_occurred.emit("IK Solver failed to initialize during pose setting.")
                return
            if not self.sim_joints_config: # Check again
                logging.error("IKM: sim_joints_config still empty after init attempt. Aborting pose setting.")
                return

        new_sim_joints_config = {jid: data.copy() for jid, data in self.sim_joints_config.items()}

        # Phase 1: Parts directly controlled by an IK joint (e.g., head by neck)
        for comp_config in self.sim_selectable_components:
            visual_part_name = comp_config.get('partName')
            target_ik_joint_abs = comp_config.get('targetJointId')

            if not visual_part_name or not target_ik_joint_abs:
                continue
            if visual_part_name not in visual_parts_data:
                logging.debug(f"IKM.set_initial_pose: Visual data for selectable part '{visual_part_name}' not provided. Skipping.")
                continue

            part_visual_info = visual_parts_data[visual_part_name]
            desired_pivot_pos = part_visual_info['position']
            desired_rotation = part_visual_info['rotation_degrees'] # World rotation of the part

            target_ik_joint_std = self._get_standardized_joint_id(target_ik_joint_abs)
            if not target_ik_joint_std or target_ik_joint_std not in new_sim_joints_config:
                logging.warning(f"IKM.set_initial_pose: Target IK joint '{target_ik_joint_abs}' (std: {target_ik_joint_std}) for visual '{visual_part_name}' not valid. Skipping.")
                continue

            new_sim_joints_config[target_ik_joint_std]['position'] = desired_pivot_pos
            new_sim_joints_config[target_ik_joint_std]['angle'] = desired_rotation # Use the provided rotation
            logging.debug(f"IKM.set_initial_pose (Selectable): Set IK joint '{target_ik_joint_std}' pos to {desired_pivot_pos}, angle to {desired_rotation} from visual part '{visual_part_name}'.")

        # Phase 2: Limb segments.
        for ik_effector_abs, limb_config_data in self.sim_limb_configs.items():
            visual_part_label = limb_config_data.get('label')
            parent_anchor_ik_abs = limb_config_data.get('parentAnchor')

            if not visual_part_label or not parent_anchor_ik_abs:
                continue
            if visual_part_label not in visual_parts_data:
                logging.debug(f"IKM.set_initial_pose: Visual data for limb part '{visual_part_label}' not provided. Skipping.")
                continue
            if visual_part_label not in self.sim_limb_lengths or self.sim_limb_lengths[visual_part_label] <= 0:
                logging.warning(f"IKM.set_initial_pose: Missing/invalid length for visual part '{visual_part_label}'. Skipping.")
                continue

            part_visual_info = visual_parts_data[visual_part_label]
            desired_parent_ik_pos = part_visual_info['position']
            desired_part_rotation_deg = part_visual_info['rotation_degrees']

            parent_anchor_ik_std = self._get_standardized_joint_id(parent_anchor_ik_abs)
            child_effector_ik_std = self._get_standardized_joint_id(ik_effector_abs)

            if not parent_anchor_ik_std or not child_effector_ik_std:
                logging.warning(f"IKM.set_initial_pose: Could not get std IK IDs for limb '{visual_part_label}'. Skipping.")
                continue
            if parent_anchor_ik_std not in new_sim_joints_config or child_effector_ik_std not in new_sim_joints_config:
                logging.warning(f"IKM.set_initial_pose: Std IK joints for limb '{visual_part_label}' not in config. Skipping.")
                continue

            new_sim_joints_config[parent_anchor_ik_std]['position'] = desired_parent_ik_pos
            # If desired_part_rotation_deg is 0, this implies the limb should be oriented at 0 degrees.
            # The angle of the parent IK joint itself is more for internal IK solver state if needed.
            # However, to ensure the initial state reflects 0 rotation for the part, we can set the parent IK joint's angle.
            new_sim_joints_config[parent_anchor_ik_std]['angle'] = desired_part_rotation_deg

            limb_length = self.sim_limb_lengths[visual_part_label]
            rad_angle = math.radians(desired_part_rotation_deg) # Use the provided rotation

            child_ik_pos_x = desired_parent_ik_pos.x() + limb_length * math.cos(rad_angle)
            child_ik_pos_y = desired_parent_ik_pos.y() + limb_length * math.sin(rad_angle)
            new_sim_joints_config[child_effector_ik_std]['position'] = QPointF(child_ik_pos_x, child_ik_pos_y)

            logging.debug(f"IKM.set_initial_pose (Limb): For visual part '{visual_part_label}':")
            logging.debug(f"  Parent IK '{parent_anchor_ik_std}' pos set to {desired_parent_ik_pos}, angle set to {desired_part_rotation_deg}. Rot used for child: {desired_part_rotation_deg}")
            logging.debug(f"  Child IK  '{child_effector_ik_std}' pos calculated to {new_sim_joints_config[child_effector_ik_std]['position']}.")

        self.sim_joints_config = new_sim_joints_config
        self._initial_snapshot = {k: v.copy() for k, v in self.sim_joints_config.items()}
        logging.info("IKM: Successfully set initial IK pose from visual data and updated initial snapshot.")

        self._current_animation_progress = 0.0
        self._update_character_part_visuals_from_ik()

        final_joint_scene_positions = {
            jid: (data['position'].x(), data['position'].y())
            for jid, data in self.sim_joints_config.items() if 'position' in data and data['position'] is not None
        }
        if final_joint_scene_positions:
            self.skeleton_pose_updated.emit(final_joint_scene_positions)

        self.animation_state_changed.emit("reset")
        if self.main_window and hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage("IK pose initialized from provided visual data.", 3000)

    @property
    def dynamic_joints(self) -> Dict[str, Dict[str, Any]]:
        return self._sim_dynamic_joints_data

    @dynamic_joints.setter
    def dynamic_joints(self, value: Dict[str, Dict[str, Any]]):
        logging.debug(f"IKManager: dynamic_joints setter called with {len(value)} items.")
        self._sim_dynamic_joints_data = value

    def get_dynamic_joint_data(self, ik_joint_key: str) -> Optional[Dict[str, Any]]:
        return self._sim_dynamic_joints_data.get(ik_joint_key)

    def update_dynamic_joint_data(self, ik_joint_key: str, data: Dict[str, Any]):
        if ik_joint_key in self._sim_dynamic_joints_data:
            self._sim_dynamic_joints_data[ik_joint_key].update(data)
        else:
            self._sim_dynamic_joints_data[ik_joint_key] = data

    def update_part_motion_path(self, part_name: str, motion_qpath: QPainterPath):
        """Updates the motion path for a specific part in the IKManager's project_parts_data."""
        # Log current state of skeleton_manager_ref AT THE VERY START
        sm_ref_id_at_entry = id(self.skeleton_manager_ref) if self.skeleton_manager_ref else None
        sm_model_exists_at_entry = (self.skeleton_manager_ref and self.skeleton_manager_ref.standardized_model) is not None
        logging.info(f"IKManager (id:{id(self)}).update_part_motion_path ENTRY for '{part_name}'. skeleton_manager_ref ID: {sm_ref_id_at_entry}, its model exists: {sm_model_exists_at_entry}")
        if part_name == 'head':
            logging.info(f"IKManager: update_part_motion_path CALLED FOR 'head'. Path elements: {motion_qpath.elementCount() if motion_qpath else 'None'}")

        current_skel_state_at_entry = "IS None" if self._current_skeleton_data is None else f"EXISTS (Keys: {list(self._current_skeleton_data.keys()) if self._current_skeleton_data else 'EMPTY'})"
        if self._current_skeleton_data and 'joints' in self._current_skeleton_data:
            current_skel_state_at_entry += f", 'joints' key present with {len(self._current_skeleton_data['joints'])} items."
        elif self._current_skeleton_data:
            current_skel_state_at_entry += f", 'joints' key MISSING."
        logging.info(f"IKManager (id:{id(self)}).update_part_motion_path (pre-workaround) for '{part_name}'. _current_skeleton_data state: {current_skel_state_at_entry}")

        if not self.project_parts_data:
            logging.warning(f"IKManager (id:{id(self)}): Cannot update motion path for '{part_name}'. project_parts_data is not set. Storing path as pending.")
            self._pending_motion_paths[part_name] = motion_qpath
            if part_name == 'head':
                logging.info(f"IKManager: 'head's path stored as PENDING because project_parts_data is not set.")
            # Log state of _current_skeleton_data here for context, even if pending
            final_skel_state_for_log = "IS None" if self._current_skeleton_data is None else f"EXISTS (Keys: {list(self._current_skeleton_data.keys()) if self._current_skeleton_data else 'EMPTY'})"
            logging.info(f"IKManager.update_part_motion_path (project_parts_data not set, pending '{part_name}'): Final _current_skeleton_data state for this call: {final_skel_state_for_log}")
            return # Do not try to initialize solver if parts data is missing

        if part_name in self.project_parts_data:
            part_info = self.project_parts_data[part_name]
            part_info.motion_path_data = motion_qpath # Ensure QPainterPath is stored in motion_path_data
            logging.info(f"IKManager (id:{id(self)}): Updated motion path for part '{part_name}'. Path elements: {motion_qpath.elementCount() if motion_qpath else 'None'}")
            if part_name == 'head':
                logging.info(f"IKManager: 'head' motion_path_data directly updated in self.project_parts_data['head'].")
                logging.info(f"IKManager: project_parts_data['head'].motion_path_data IS NOW {'SET' if self.project_parts_data['head'].motion_path_data else 'None/Empty'}")
        else:
            logging.warning(f"IKManager (id:{id(self)}): Part '{part_name}' not found in project_parts_data. Storing path as pending.")
            self._pending_motion_paths[part_name] = motion_qpath
            if part_name == 'head':
                logging.info(f"IKManager: 'head's path stored as PENDING because 'head' not in project_parts_data.")
            # No return here, still try to init solver if other conditions met, though this part won't have a path for now

        # Log state of _current_skeleton_data BEFORE calling _try_initialize_solver
        final_skel_state_before_try_init = "IS None" if self._current_skeleton_data is None else f"EXISTS (Keys: {list(self._current_skeleton_data.keys()) if self._current_skeleton_data else 'EMPTY'})"
        if self._current_skeleton_data and 'joints' in self._current_skeleton_data:
            final_skel_state_before_try_init += f", 'joints' key present with {len(self._current_skeleton_data['joints'])} items."
        elif self._current_skeleton_data:
            final_skel_state_before_try_init += f", 'joints' key MISSING."
        logging.info(f"IKManager.update_part_motion_path (before _try_initialize_solver): Final _current_skeleton_data state for this call: {final_skel_state_before_try_init}")

        self._try_initialize_solver() # Re-check if solver is now ready


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