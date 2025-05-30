import logging
from pathlib import Path
from typing import Optional, Dict, List, Union, Any

from PyQt6.QtCore import QObject, pyqtSignal
import yaml

from ..core.models_team import TeamMember # Assuming this is still relevant or a placeholder
from ..core.models_project import ProjectFile, ProjectFileSet # Placeholder names
from ..core.models_skeleton import (StandardizedSkeletonModel, StandardizedJointModel,
                                     ANIMATED_DRAWINGS_NAME_MAP, STANDARD_JOINT_NAMES,
                                     SMPLSequenceSkeleton, SMPLSequenceJoint)
from ..utils.config_utils import load_config_from_yaml
from ..utils.path_utils import ensure_path

# Default scale if not provided by bounding_box.yaml
DEFAULT_SCALE = 1.0

class SkeletonManager(QObject):
    """Manages skeleton data, including loading, standardization, and providing access."""
    skeleton_updated = pyqtSignal(object)  # Emits dict representation of StandardizedSkeletonModel or None
    error_occurred = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._raw_skeleton_data: Optional[Any] = None
        self._current_standardized_model: Optional[StandardizedSkeletonModel] = None
        self._project_dir: Optional[Path] = None
        self._char_cfg_origin_offset: Optional[List[float]] = None # Store origin offset [x, y]
        self._scale_for_visualization: float = DEFAULT_SCALE

        logging.info(f"SkeletonManager (id:{id(self)}): Initialized.")

    def clear_data(self):
        """Clears all internal skeleton data and emits an update."""
        logging.info(f"SkeletonManager (id:{id(self)}): Clearing all internal skeleton data.")
        self._raw_skeleton_data = None
        self._current_standardized_model = None
        self._project_dir = None
        self._char_cfg_origin_offset = None
        self._scale_for_visualization = DEFAULT_SCALE
        logging.info(f"SkeletonManager (id:{id(self)}): Emitting skeleton_updated with None due to clear_data call.")
        self.skeleton_updated.emit(None)

    def load_skeleton(self,
                      skeleton_data: Union[Dict, List, Path, StandardizedSkeletonModel, None],
                      source_format_hint: Optional[str] = None,
                      project_dir: Optional[Path] = None) -> bool:
        """Loads skeleton data from various sources and attempts to standardize it."""
        logging.info(f"SkeletonManager (id:{id(self)}): Attempting to load skeleton. Hint: {source_format_hint}, Type: {type(skeleton_data)}")
        self.clear_data() # Start fresh, this will emit None initially

        if project_dir:
            self._project_dir = ensure_path(project_dir)

        if skeleton_data is None:
            logging.warning(f"SkeletonManager (id:{id(self)}): load_skeleton called with None data. Data cleared.")
            # clear_data() already emitted None, so no further emit needed here.
            return False

        if isinstance(skeleton_data, StandardizedSkeletonModel):
            logging.info(f"SkeletonManager (id:{id(self)}): Loading directly from StandardizedSkeletonModel instance.")
            self._current_standardized_model = skeleton_data
            self._raw_skeleton_data = self._current_standardized_model.model_dump() # Store a dict representation
            logging.info(f"SkeletonManager (id:{id(self)}): Emitting skeleton_updated with provided StandardizedSkeletonModel.")
            self.skeleton_updated.emit(self._current_standardized_model.model_dump())
            return True

        try:
            if isinstance(skeleton_data, Path) or isinstance(skeleton_data, str):
                file_path = ensure_path(skeleton_data)
                if not file_path.exists():
                    logging.error(f"SkeletonManager (id:{id(self)}): Skeleton file not found: {file_path}")
                    self.error_occurred.emit(f"Skeleton file not found: {file_path}")
                    # clear_data() already emitted None.
                    return False
                self._raw_skeleton_data = load_config_from_yaml(file_path)
                if not self._raw_skeleton_data:
                    logging.error(f"SkeletonManager (id:{id(self)}): Failed to load or parse YAML from {file_path}")
                    self.error_occurred.emit(f"Failed to parse skeleton YAML: {file_path}")
                     # clear_data() already emitted None.
                    return False
                # Determine format if not hinted, e.g. by inspecting keys if it's a dict
                if not source_format_hint and isinstance(self._raw_skeleton_data, dict):
                    if 'skeleton' in self._raw_skeleton_data and isinstance(self._raw_skeleton_data['skeleton'], list):
                         source_format_hint = "animated_drawings_char_cfg"
                    # Add other auto-detection logic if needed
            elif isinstance(skeleton_data, (dict, list)):
                self._raw_skeleton_data = skeleton_data
            else:
                logging.error(f"SkeletonManager (id:{id(self)}): Unsupported skeleton data type: {type(skeleton_data)}")
                self.error_occurred.emit(f"Unsupported skeleton data type: {type(skeleton_data)}")
                # clear_data() already emitted None.
                return False

            if not self._raw_skeleton_data:
                logging.error(f"SkeletonManager (id:{id(self)}): Raw skeleton data is empty after initial processing.")
                # clear_data() already emitted None.
                return False

            # Try to standardize
            if source_format_hint == "smpl_sequence" and isinstance(self._raw_skeleton_data, dict):
                self._current_standardized_model = self._standardize_smpl_sequence(self._raw_skeleton_data)
            elif (source_format_hint == "animated_drawings_char_cfg" or not source_format_hint) and isinstance(self._raw_skeleton_data, dict):
                 # Default to trying animated_drawings if hint is for it or no hint and it's a dict
                logging.info(f"SkeletonManager (id:{id(self)}): Detected Animated Drawings format based on hint or content.")
                self._current_standardized_model = self._standardize_animated_drawings(self._raw_skeleton_data)
            else:
                logging.warning(f"SkeletonManager (id:{id(self)}): Unknown or unhandled skeleton format hint: {source_format_hint} for data type {type(self._raw_skeleton_data)}. Attempting generic standardization.")
                # Add a generic standardization attempt if possible or fail
                self._current_standardized_model = self._standardize_generic(self._raw_skeleton_data)

            if self._current_standardized_model:
                logging.info(f"SkeletonManager (id:{id(self)}): Skeleton data processed successfully as {source_format_hint or 'detected format'}.")
                logging.info(f"SkeletonManager (id:{id(self)}): Emitting skeleton_updated with processed model.")
                self.skeleton_updated.emit(self._current_standardized_model.model_dump())
                return True
            else:
                logging.error(f"SkeletonManager (id:{id(self)}): Standardization failed for format hint '{source_format_hint}'.")
                self.error_occurred.emit(f"Standardization failed for format: {source_format_hint}")
                # clear_data() already emitted None and an emit for None is appropriate here if we didn't clear at start
                # However, since clear_data() IS called at the start, this path means a failure after that initial None.
                # Emitting None again is fine, or rely on the initial None from clear_data().
                # For clarity, let's ensure a None is emitted if we reach here after the initial clear_data().
                # This path should ideally not be hit if clear_data() ensures a None emit.
                # if self._current_standardized_model is None: # Should always be true if standardization failed
                #     logging.info(f"SkeletonManager (id:{id(self)}): Emitting skeleton_updated with None due to standardization failure.")
                #     self.skeleton_updated.emit(None)
                return False

        except Exception as e:
            logging.error(f"SkeletonManager (id:{id(self)}): Exception during skeleton loading/standardization. Error: {e}", exc_info=True)
            self.error_occurred.emit(f"Exception processing skeleton: {e}")
            # clear_data() was called at the start, so a None signal has been emitted.
            # We could emit another None here, but it might be redundant. Let's rely on the initial one.
            # self.skeleton_updated.emit(None) # This would be if we didn't call clear_data() at the start.
            return False

    def _standardize_animated_drawings(self, raw_data: Dict) -> Optional[StandardizedSkeletonModel]:
        """Standardizes skeleton data from the Animated Drawings char_cfg.yaml format."""
        logging.info(f"SkeletonManager (id:{id(self)}): Standardizing Animated Drawings format.")
        try:
            skeleton_info = raw_data.get('skeleton')
            if not skeleton_info or not isinstance(skeleton_info, list):
                logging.error(f"SkeletonManager (id:{id(self)}): 'skeleton' key missing or not a list in Animated Drawings raw data.")
                return None

            # Attempt to load origin and scale from bounding_box.yaml if project_dir is set
            if self._project_dir:
                bbox_path = self._project_dir / "bounding_box.yaml"
                if bbox_path.exists():
                    try:
                        bbox_data = load_config_from_yaml(bbox_path)
                        if bbox_data and isinstance(bbox_data, dict):
                            self._char_cfg_origin_offset = [
                                float(bbox_data.get('left', 0)),
                                float(bbox_data.get('top', 0))
                            ]
                            # Assuming scale might be stored or derived, placeholder for now
                            # self._scale_for_visualization = float(bbox_data.get('scale', DEFAULT_SCALE))
                            logging.info(f"SkeletonManager (id:{id(self)}): Loaded origin {self._char_cfg_origin_offset} from {bbox_path}")
                        else:
                            logging.warning(f"SkeletonManager (id:{id(self)}): bounding_box.yaml was empty or not a dict: {bbox_path}")
                    except Exception as e:
                        logging.error(f"SkeletonManager (id:{id(self)}): Error loading bounding_box.yaml from {bbox_path}: {e}")
                else:
                    logging.info(f"SkeletonManager (id:{id(self)}): No bounding_box.yaml found at {bbox_path}. Using default origin/scale.")

            if not self._char_cfg_origin_offset: # If not loaded from bounding_box.yaml
                 # Check if origin is directly in char_cfg.yaml (older format or fallback)
                raw_origin = raw_data.get('origin')
                if isinstance(raw_origin, list) and len(raw_origin) == 2:
                    try:
                        self._char_cfg_origin_offset = [float(raw_origin[0]), float(raw_origin[1])]
                        logging.info(f"SkeletonManager (id:{id(self)}): Used origin {self._char_cfg_origin_offset} from char_cfg.yaml itself.")
                    except ValueError:
                        logging.warning(f"SkeletonManager (id:{id(self)}): Could not parse origin {raw_origin} from char_cfg.yaml. Using [0,0].")
                        self._char_cfg_origin_offset = [0.0, 0.0]
                else:
                    logging.info(f"SkeletonManager (id:{id(self)}): No origin found in char_cfg.yaml or bounding_box.yaml. Using [0,0].")
                    self._char_cfg_origin_offset = [0.0, 0.0]

            origin_x, origin_y = self._char_cfg_origin_offset

            standardized_joints: Dict[str, StandardizedJointModel] = {}
            joint_map: Dict[str, str] = {}
            hierarchy: Dict[str, List[str]] = {}
            root_joint_ids: List[str] = []

            raw_joint_name_to_std_id: Dict[str, str] = {}

            # First pass: create all joints and map raw names to standard IDs
            for i, joint_entry in enumerate(skeleton_info):
                if not isinstance(joint_entry, dict):
                    logging.warning(f"SkeletonManager (id:{id(self)}): Joint entry is not a dict: {joint_entry}. Skipping.")
                    continue

                raw_name = joint_entry.get('name')
                if not raw_name:
                    logging.warning(f"SkeletonManager (id:{id(self)}): Joint entry missing 'name': {joint_entry}. Assigning default ID: unknown_joint_{i}")
                    raw_name = f"unknown_joint_{i}" # Should be unique enough for this scope

                # Determine standard ID (e.g., "left_shoulder")
                standard_id = ANIMATED_DRAWINGS_NAME_MAP.get(raw_name, raw_name) # Fallback to raw_name if not in map
                if standard_id in standardized_joints: # Handle potential duplicate standard IDs from multiple raw names mapping to one
                    logging.warning(f"SkeletonManager (id:{id(self)}): Duplicate standard ID '{standard_id}' generated (from raw '{raw_name}'). Appending index to ensure uniqueness.")
                    original_standard_id = standard_id
                    count = 1
                    while standard_id in standardized_joints:
                        standard_id = f"{original_standard_id}_{count}"
                        count += 1
                    logging.info(f"SkeletonManager (id:{id(self)}):  Resolved to new unique standard ID: '{standard_id}'.")

                raw_joint_name_to_std_id[raw_name] = standard_id
                joint_map[raw_name] = standard_id # Map original name to its chosen standard ID

                loc = joint_entry.get('loc')
                if not loc or not isinstance(loc, list) or len(loc) != 2:
                    logging.warning(f"SkeletonManager (id:{id(self)}): Joint '{raw_name}' (std: '{standard_id}') has invalid 'loc': {loc}. Using [0,0].")
                    position = [0.0, 0.0]
                else:
                    try:
                        position = [float(loc[0]) + origin_x, float(loc[1]) + origin_y]
                    except (ValueError, TypeError):
                        logging.warning(f"SkeletonManager (id:{id(self)}): Could not parse loc {loc} for joint '{raw_name}'. Using [0,0] relative to origin.")
                        position = [origin_x, origin_y]

                # Parent will be resolved in the second pass using raw_joint_name_to_std_id map
                standardized_joints[standard_id] = StandardizedJointModel(
                    id=standard_id,
                    name=raw_name, # Store original name for reference/debugging
                    position=position,
                    parent_id=None, # To be filled
                    label=raw_name # Use raw name as label for now
                )
                hierarchy[standard_id] = [] # Initialize empty list for children

            # Second pass: resolve parent_id and build hierarchy
            for joint_entry in skeleton_info:
                raw_name = joint_entry.get('name')
                if not raw_name or raw_name not in raw_joint_name_to_std_id:
                    continue # Already warned or handled

                current_std_id = raw_joint_name_to_std_id[raw_name]
                current_joint_model = standardized_joints[current_std_id]

                raw_parent_name = joint_entry.get('parent')
                if raw_parent_name and raw_parent_name in raw_joint_name_to_std_id:
                    parent_std_id = raw_joint_name_to_std_id[raw_parent_name]
                    current_joint_model.parent_id = parent_std_id
                    if parent_std_id in hierarchy:
                        hierarchy[parent_std_id].append(current_std_id)
                    else:
                        logging.warning(f"SkeletonManager (id:{id(self)}): Parent std_id '{parent_std_id}' (from raw '{raw_parent_name}') not found in hierarchy keys for child '{current_std_id}'. This shouldn't happen.")
                elif raw_parent_name:
                    logging.warning(f"SkeletonManager (id:{id(self)}): Parent raw name '{raw_parent_name}' for joint '{raw_name}' not found in processed joints map. Treating '{current_std_id}' as a root or near-root.")
                    root_joint_ids.append(current_std_id)
                else: # No parent specified
                    root_joint_ids.append(current_std_id)

            # Refine root_joint_ids: if a joint is in root_joint_ids but also has a parent, it's not a true root.
            # True roots are those in root_joint_ids that do not appear as a child of any other joint that has a parent.
            # A simpler way: true roots are those with parent_id=None.
            actual_root_ids = {jid for jid, model in standardized_joints.items() if model.parent_id is None}
            if not actual_root_ids and standardized_joints:
                logging.warning(f"SkeletonManager (id:{id(self)}): No joint has parent_id=None. Falling back to initially collected root_joint_ids or first joint if desperate.")
                if root_joint_ids:
                    actual_root_ids = set(root_joint_ids) # Use originally collected ones if all have parents (cycle?)
                elif standardized_joints:
                    actual_root_ids = {next(iter(standardized_joints))} # Desperate fallback

            # Ensure all joints in hierarchy have their children lists populated even if empty
            for j_id in standardized_joints:
                if j_id not in hierarchy:
                    hierarchy[j_id] = []

            # Calculate limb_lengths (placeholder, needs actual logic based on parts or defined lengths)
            limb_lengths: Dict[str, float] = {}
            # Example: if 'left_upper_arm' is a part name, and its length is known
            # limb_lengths["left_upper_arm"] = 50.0

            return StandardizedSkeletonModel(
                joints=standardized_joints,
                root_joint_ids=list(actual_root_ids),
                hierarchy=hierarchy,
                joint_map=joint_map, # Map of raw AD names to their unique standardized IDs
                limb_lengths=limb_lengths,
                source_format="animated_drawings_char_cfg",
                origin_offset_for_visualization=self._char_cfg_origin_offset,
                scale_for_visualization=self._scale_for_visualization
            )

        except Exception as e:
            logging.error(f"SkeletonManager (id:{id(self)}): Error standardizing Animated Drawings data: {e}", exc_info=True)
            return None

    def _standardize_smpl_sequence(self, raw_data: Dict) -> Optional[StandardizedSkeletonModel]:
        """Standardizes skeleton data from an SMPL sequence format."""
        logging.info(f"SkeletonManager (id:{id(self)}): Standardizing SMPL sequence format.")
        try:
            smpl_model = SMPLSequenceSkeleton.model_validate(raw_data)

            standardized_joints: Dict[str, StandardizedJointModel] = {}
            joint_map: Dict[str, str] = {} # Maps original SMPL joint names to standard IDs
            hierarchy: Dict[str, List[str]] = {}
            root_joint_ids: List[str] = []

            # Assuming smpl_model.joints is a list of SMPLSequenceJoint
            # We need to map SMPL joint indices/names to our STANDARD_JOINT_NAMES if possible
            # This requires a predefined mapping from SMPL (e.g., by index or common SMPL name) to our standard names.
            # For now, let's use SMPL joint names directly as their IDs if no other mapping is available.

            smpl_idx_to_std_id: Dict[int, str] = {}

            for i, smpl_joint in enumerate(smpl_model.joints):
                # Try to get a standard name, fallback to smpl_joint.name or generic ID
                # This part is highly dependent on how SMPL joint names/indices align with STANDARD_JOINT_NAMES
                std_id = smpl_joint.name if smpl_joint.name else f"smpl_joint_{i}"
                original_name = smpl_joint.name if smpl_joint.name else f"smpl_joint_{i}" # For joint_map

                # Ensure std_id is unique if multiple SMPL joints map to the same conceptual standard joint (unlikely with direct name use)
                if std_id in standardized_joints:
                    logging.warning(f"SkeletonManager (id:{id(self)}): Duplicate std_id '{std_id}' from SMPL joint '{original_name}'. Appending index.")
                    base_std_id = std_id
                    count = 1
                    while std_id in standardized_joints:
                        std_id = f"{base_std_id}_{count}"
                        count += 1

                smpl_idx_to_std_id[i] = std_id
                joint_map[original_name] = std_id

                # Position: SMPL data might be 3D. StandardizedJointModel expects [x,y] or [x,y,z].
                # For 2D projection, you might take (x,y) or (x,z) depending on camera, or use a projection matrix.
                # Assuming smpl_joint.position is [x,y,z], let's take [x,y] for now.
                pos_3d = smpl_joint.position
                pos_2d = [pos_3d[0], pos_3d[1]] if pos_3d and len(pos_3d) >= 2 else [0.0, 0.0]
                if len(pos_3d) >=3:
                     pos_2d = [pos_3d[0], pos_3d[1], pos_3d[2]] # Keep Z if present

                standardized_joints[std_id] = StandardizedJointModel(
                    id=std_id,
                    name=original_name, # Store original SMPL name
                    position=pos_2d,
                    parent_id=None, # To be filled
                    label=original_name # Use original name as label
                )
                hierarchy[std_id] = []

            # Second pass: resolve parent_id using smpl_model.parents (list of parent indices)
            if smpl_model.parents and len(smpl_model.parents) == len(smpl_model.joints):
                for i, parent_idx in enumerate(smpl_model.parents):
                    current_std_id = smpl_idx_to_std_id.get(i)
                    if current_std_id is None: continue

                    if parent_idx is not None and parent_idx != -1: # SMPL uses -1 for root parent
                        parent_std_id = smpl_idx_to_std_id.get(parent_idx)
                        if parent_std_id and parent_std_id in standardized_joints:
                            standardized_joints[current_std_id].parent_id = parent_std_id
                            if parent_std_id in hierarchy:
                                hierarchy[parent_std_id].append(current_std_id)
                            else: # Should not happen if all joints processed in first pass
                                hierarchy[parent_std_id] = [current_std_id]
                        else:
                            logging.warning(f"SkeletonManager (id:{id(self)}): SMPL parent_std_id for index {parent_idx} not found for child '{current_std_id}'. Treating child as root.")
                            root_joint_ids.append(current_std_id)
                    else: # Is a root joint
                        root_joint_ids.append(current_std_id)
            else:
                logging.warning(f"SkeletonManager (id:{id(self)}): SMPL parents array missing or mismatched length. Hierarchy may be incorrect.")
                # Fallback: assume all joints are roots if no parent info
                if not root_joint_ids:
                    root_joint_ids = list(standardized_joints.keys())

            actual_root_ids = {jid for jid, model in standardized_joints.items() if model.parent_id is None}
            if not actual_root_ids and standardized_joints:
                 actual_root_ids = {next(iter(standardized_joints))} # Desperate

            return StandardizedSkeletonModel(
                joints=standardized_joints,
                root_joint_ids=list(actual_root_ids),
                hierarchy=hierarchy,
                joint_map=joint_map,
                source_format="smpl_sequence"
            )

        except Exception as e:
            logging.error(f"SkeletonManager (id:{id(self)}): Error standardizing SMPL sequence data: {e}", exc_info=True)
            return None

    def _standardize_generic(self, raw_data: Any) -> Optional[StandardizedSkeletonModel]:
        """Placeholder for a generic standardization attempt if format is unknown."""
        logging.warning(f"SkeletonManager (id:{id(self)}): Generic standardization for type {type(raw_data)} not implemented yet.")
        # Implement basic heuristics if possible, e.g., if it's a list of dicts with 'name', 'position', 'parent' keys.
        return None

    @property
    def standardized_model(self) -> Optional[StandardizedSkeletonModel]:
        """Returns the current standardized skeleton model."""
        return self._current_standardized_model

    @property
    def raw_data(self) -> Optional[Any]:
        """Returns the raw skeleton data that was loaded."""
        return self._raw_skeleton_data

    @property
    def char_cfg_origin_offset_for_visualization(self) -> List[float]:
        """Returns the [x, y] origin offset used for char_cfg visualization. Defaults to [0,0]."""
        return self._char_cfg_origin_offset if self._char_cfg_origin_offset is not None else [0.0, 0.0]

    @property
    def scale_for_visualization(self) -> float:
        """Returns the scale factor used for char_cfg visualization. Defaults to 1.0."""
        return self._scale_for_visualization

    # --- Convenience methods for accessing standardized data ---
    def get_joint_by_id(self, joint_id: str) -> Optional[StandardizedJointModel]:
        if self._current_standardized_model and joint_id in self._current_standardized_model.joints:
            return self._current_standardized_model.joints[joint_id]
        return None

    def get_joint_by_source_name(self, source_name: str) -> Optional[StandardizedJointModel]:
        """Gets a joint by its original name (e.g., from char_cfg.yaml or SMPL)."""
        if self._current_standardized_model and self._current_standardized_model.joint_map:
            standard_id = self._current_standardized_model.joint_map.get(source_name)
            if standard_id:
                return self.get_joint_by_id(standard_id)
        logging.debug(f"SkeletonManager: Joint with source name '{source_name}' not found in current model map.")
        return None

    def get_all_joints(self) -> Dict[str, StandardizedJointModel]:
        if self._current_standardized_model:
            return self._current_standardized_model.joints
        return {}

    def get_hierarchy(self) -> Dict[str, List[str]]:
        if self._current_standardized_model:
            return self._current_standardized_model.hierarchy
        return {}

    def get_root_joint_ids(self) -> List[str]:
        if self._current_standardized_model:
            return self._current_standardized_model.root_joint_ids
        return []

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    manager = SkeletonManager()

    # Test 1: Clear data (should emit None)
    print("\n--- Test: Clear Data ---")
    def slot_skel_updated(data):
        print(f"SLOT: skeleton_updated received: {'Present with data' if data else 'None'}")
        if data and isinstance(data, dict) and 'joints' in data :
            print(f"  Joints: {list(data['joints'].keys())}")

    manager.skeleton_updated.connect(slot_skel_updated)
    manager.clear_data()

    # Test 2: Load Animated Drawings from a dummy dict
    print("\n--- Test: Load Animated Drawings (char_cfg like) ---")
    dummy_char_cfg_data = {
        'skeleton': [
            {'name': 'hip', 'parent': None, 'loc': [100, 200]},
            {'name': 'left_hip', 'parent': 'hip', 'loc': [90, 200]},
            {'name': 'left_knee', 'parent': 'left_hip', 'loc': [90, 150]},
            {'name': 'neck', 'parent': 'hip', 'loc': [100, 180]},
            {'name': 'head', 'parent': 'neck', 'loc': [100, 160]}
        ],
        'origin': [10, 20] # Test with origin in char_cfg
    }
    manager.load_skeleton(dummy_char_cfg_data, source_format_hint="animated_drawings_char_cfg")
    if manager.standardized_model:
        print(f"Model loaded. Root IDs: {manager.get_root_joint_ids()}")
        head_joint = manager.get_joint_by_source_name('head')
        if head_joint:
            print(f"Head joint (source 'head') position (after origin adjust): {head_joint.position}") # Should be [110, 180]
        print(f"Origin offset used: {manager.char_cfg_origin_offset_for_visualization}")
    else:
        print("Failed to load dummy char_cfg data.")

    # Test 3: Load failure (e.g., bad path or bad data)
    print("\n--- Test: Load Failure (bad path) ---")
    manager.load_skeleton(Path("non_existent_skeleton.yaml"))

    print("\n--- Test: Load SMPL Sequence (dummy) ---")
    dummy_smpl_data = {
        "joints": [
            {"name": "pelvis_smpl", "position": [0,0,0]},
            {"name": "left_hip_smpl", "position": [0.1, 0, 0]},
            {"name": "left_knee_smpl", "position": [0.1, -0.4, 0]},
        ],
        "parents": [-1, 0, 1] # pelvis is root, left_hip child of pelvis, left_knee child of left_hip
    }
    manager.load_skeleton(dummy_smpl_data, source_format_hint="smpl_sequence")
    if manager.standardized_model:
        print(f"SMPL Model loaded. Root IDs: {manager.get_root_joint_ids()}")
        print(f"Joints: {list(manager.get_all_joints().keys())}")
        # print(f"Hierarchy: {manager.get_hierarchy()}")
    else:
        print("Failed to load dummy SMPL data.")

    print("\n--- Test: Clear data again ---")
    manager.clear_data()

    # Test loading from StandardizedSkeletonModel instance directly
    print("\n--- Test: Load from StandardizedSkeletonModel instance ---")
    joints_direct = {
        "root": StandardizedJointModel(id="root", name="Root", position=[0,0], parent_id=None),
        "child": StandardizedJointModel(id="child", name="Child", position=[0,10], parent_id="root")
    }
    hierarchy_direct = {"root": ["child"], "child": []}
    model_instance = StandardizedSkeletonModel(joints=joints_direct, root_joint_ids=["root"], hierarchy=hierarchy_direct, joint_map={"Root":"root", "Child":"child"})
    manager.load_skeleton(model_instance)
    if manager.standardized_model and manager.standardized_model.joints.get("child"):
        print("Successfully loaded from StandardizedSkeletonModel instance. Child joint name:", manager.standardized_model.joints["child"].name)
    else:
        print("Failed to load from StandardizedSkeletonModel instance.")