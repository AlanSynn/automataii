"""
SkeletonManager module for managing skeleton data and conversions.
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
import math # For calculating limb lengths if needed

from PyQt6.QtCore import QObject, pyqtSignal, QPointF
from pydantic import ValidationError

# Import the new standardized models
from .models_skeleton import StandardizedJointModel, StandardizedSkeletonModel

# Define a structure for standardized joint info if needed, or use Dicts for now
# For example:
# @dataclass
# class Joint:
#     id: str
#     name: str
#     position: QPointF # or Tuple[float, float]
#     parent_id: Optional[str] = None
#     children_ids: List[str] = field(default_factory=list)


class SkeletonManager(QObject):
    """
    Manages skeleton data, including loading, processing, and providing access.
    Handles conversion from different formats (e.g., Animated Drawings) to a standard format.
    Internally uses StandardizedSkeletonModel.
    """
    skeleton_updated = pyqtSignal(dict) # Emits the new standardized skeleton data as a dict
    error_occurred = pyqtSignal(str)    # Emits an error message
    skeleton_data_cleared = pyqtSignal() # Emits when skeleton data is cleared

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._raw_input_skeleton_data: Optional[Dict[str, Any]] = None # Store the original input dict if needed for reprocessing
        self._standardized_skeleton_model: Optional[StandardizedSkeletonModel] = None
        logging.info("SkeletonManager initialized with new standardized models.")

    @property
    def raw_input_data(self) -> Optional[Dict[str, Any]]:
        """Returns the most recent raw input dictionary that was processed."""
        return self._raw_input_skeleton_data

    @property
    def standardized_model(self) -> Optional[StandardizedSkeletonModel]:
        """Returns the current StandardizedSkeletonModel instance."""
        return self._standardized_skeleton_model

    @property
    def joint_positions(self) -> Dict[str, Tuple[float, float]]:
        """Returns a dictionary of joint ID to (x,y) position from the standardized model."""
        if not self._standardized_skeleton_model:
            return {}
        return {joint_id: joint.position for joint_id, joint in self._standardized_skeleton_model.joints.items()}

    @property
    def joint_hierarchy(self) -> Dict[str, List[str]]:
        """Returns the parent_id -> [child_ids] hierarchy from the standardized model."""
        if not self._standardized_skeleton_model:
            return {}
        return self._standardized_skeleton_model.hierarchy

    @property
    def root_joints(self) -> List[str]: # Returns list of root joint IDs
        """Returns a list of root joint IDs from the standardized model."""
        if not self._standardized_skeleton_model:
            return []
        return self._standardized_skeleton_model.root_joint_ids

    def load_skeleton_from_dict(self, data: Optional[Dict[str, Any]], source_format: str = 'auto') -> bool:
        """
        Loads skeleton data from a dictionary, converting it to StandardizedSkeletonModel.

        Args:
            data: The dictionary containing skeleton data.
            source_format: 'auto', 'animated_drawings', or 'standard'.
                           If 'auto', tries to detect format.
        Returns:
            True if loading and processing were successful, False otherwise.
        """
        self.clear_data() # Start fresh
        if not data or not isinstance(data, dict):
            logging.warning("SkeletonManager: No data provided or data is not a dictionary.")
            # self.skeleton_updated.emit({}) # Emitted by clear_data
            return False

        self._raw_input_skeleton_data = data # Store the input
        logging.info(f"SkeletonManager: Loading skeleton from dict. Source format hint: {source_format}")

        processed_model: Optional[StandardizedSkeletonModel] = None
        detected_format = source_format

        if source_format == 'animated_drawings' or \
           (source_format == 'auto' and self._is_animated_drawings_format(data)):
            logging.info("SkeletonManager: Detected Animated Drawings format based on hint or content.")
            detected_format = 'animated_drawings'
            processed_model = self._process_animated_drawings_format(data)
        elif source_format == 'standard' or \
             (source_format == 'auto' and self._is_already_standardized_format(data)):
            logging.info("SkeletonManager: Detected Standardized format based on hint or content.")
            detected_format = 'standard'
            processed_model = self._process_already_standardized_format(data)
        else: # Fallback or if auto-detection failed and no clear format
            logging.warning(f"SkeletonManager: Unknown source format '{source_format}'. Attempting to process as Animated Drawings, then as Standard.")
            # Try Animated Drawings first as it's more common for raw input
            processed_model = self._process_animated_drawings_format(data)
            if processed_model:
                detected_format = 'animated_drawings'
            else: # If AD processing failed, try standard
                logging.info("SkeletonManager: Animated Drawings processing failed, trying as Standardized format.")
                processed_model = self._process_already_standardized_format(data)
                if processed_model:
                    detected_format = 'standard'

        if processed_model:
            self._standardized_skeleton_model = processed_model
            self._standardized_skeleton_model.source_format = detected_format
            logging.info(f"SkeletonManager: Skeleton data processed successfully as {detected_format}.")
            self.skeleton_updated.emit(self._standardized_skeleton_model.model_dump())
            return True
        else:
            logging.error("SkeletonManager: Failed to process skeleton data into any known format.")
            self.clear_data() # clear_data emits its own signals
            self.error_occurred.emit("Failed to process skeleton data (unknown format or invalid content).")
            return False

    def load_skeleton_from_project_data(self, raw_skeleton_list: Optional[List[Dict[str, Any]]], parts_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Loads skeleton data from a raw list of joint dictionaries (e.g., from ProjectDataManager's
        parsed PydanticCharacterDataModel.skeleton_joints) and converts to StandardizedSkeletonModel.

        Args:
            raw_skeleton_list: A list of dictionaries, where each dictionary defines a joint.
                               Expected to be in a format similar to Animated Drawings' 'skeleton' list
                               or PydanticSkeletonJointModel.model_dump() output.
            parts_data: Optional dictionary of PartInfo objects/data. Currently used for context like limb lengths.

        Returns:
            True if loading and processing were successful, False otherwise.
        """
        logging.info(f"SkeletonManager: Attempting to load skeleton from project data list (joint count: {len(raw_skeleton_list) if raw_skeleton_list else 0}).")
        if not raw_skeleton_list:
            logging.info("SkeletonManager: No raw skeleton list provided from project data. Clearing existing skeleton data.")
            self.clear_data()
            # self.skeleton_updated.emit({}) # Emitted by clear_data
            return True # Successfully cleared/processed empty list

        # The _process_animated_drawings_format expects a dict like: {"skeleton": [...]}
        # It can also derive some limb lengths from parts_data if available.
        wrapper_dict = {"skeleton": raw_skeleton_list}
        if parts_data:
            wrapper_dict["parts_data_for_limb_lengths"] = parts_data # Pass for potential use

        # This data typically comes from a parsed parts_info.json or char_cfg.yaml,
        # so it's likely 'animated_drawings' or a structure very close to it.
        return self.load_skeleton_from_dict(wrapper_dict, source_format='animated_drawings')

    def clear_data(self):
        """Clears all internal skeleton data and emits relevant signals."""
        logging.info("SkeletonManager: Clearing all internal skeleton data.")
        self._raw_input_skeleton_data = None
        self._standardized_skeleton_model = None
        self.skeleton_data_cleared.emit()
        self.skeleton_updated.emit({}) # Emit empty dict to signal state change to empty

    def _is_animated_drawings_format(self, data: Dict[str, Any]) -> bool:
        """Checks if the provided data dictionary matches the Animated Drawings char_cfg.yaml structure."""
        if 'skeleton' in data and isinstance(data['skeleton'], list):
            if not data['skeleton']: return True # Empty skeleton list is still valid AD format
            first_joint = data['skeleton'][0]
            if isinstance(first_joint, dict):
                 # Common keys: 'name', 'parent', and either 'coordinates' or 'loc'
                return 'name' in first_joint and \
                       'parent' in first_joint and \
                       ('coordinates' in first_joint or 'loc' in first_joint)
        return False

    def _is_already_standardized_format(self, data: Dict[str, Any]) -> bool:
        """Checks if data is already in our target StandardizedSkeletonModel format (or close to it)."""
        # Check for key fields of StandardizedSkeletonModel
        if 'joints' in data and isinstance(data['joints'], dict) and \
           'root_joint_ids' in data and isinstance(data['root_joint_ids'], list) and \
           'hierarchy' in data and isinstance(data['hierarchy'], dict):
            if not data['joints']: return True # Valid empty standardized model

            # Check first joint if available
            first_joint_id = next(iter(data['joints']), None)
            if first_joint_id:
                first_joint_data = data['joints'][first_joint_id]
                if isinstance(first_joint_data, dict) and \
                   'id' in first_joint_data and \
                   'name' in first_joint_data and \
                   'position' in first_joint_data:
                    return True
        return False

    def _process_animated_drawings_format(self, data: Dict[str, Any]) -> Optional[StandardizedSkeletonModel]:
        """
        Processes skeleton data from the Animated Drawings format (e.g., char_cfg.yaml content).
        Populates and returns a StandardizedSkeletonModel.
        """
        raw_joints_list = data.get('skeleton', [])
        if not isinstance(raw_joints_list, list):
            logging.warning("Animated Drawings format: 'skeleton' key is not a list or is missing.")
            return None

        std_skeleton = StandardizedSkeletonModel(source_format='animated_drawings')
        temp_joint_name_to_id: Dict[str, str] = {}
        temp_id_to_parent_name: Dict[str, Optional[str]] = {}

        for i, joint_info_raw in enumerate(raw_joints_list):
            if not isinstance(joint_info_raw, dict):
                logging.warning(f"Skipping non-dict joint entry in Animated Drawings skeleton: {joint_info_raw}")
                continue

            joint_name = joint_info_raw.get('name')
            parent_name = joint_info_raw.get('parent') # Could be None, empty string, or actual name
            coords = joint_info_raw.get('coordinates') or joint_info_raw.get('loc') # Prefer 'coordinates'

            # If 'coords' is None, check if 'position' (from Pydantic model dump) is present
            if coords is None and 'position' in joint_info_raw:
                coords = joint_info_raw['position']

            # Use 'id' from Pydantic model dump if 'name' is missing or for robustness
            if not joint_name and 'id' in joint_info_raw:
                joint_name = joint_info_raw['id']

            if not joint_name or coords is None:
                logging.warning(f"Skipping AD joint with missing name or coordinates: {joint_info_raw}")
                continue

            # Create a robust, unique ID. Using original name + index as fallback.
            # Standardized ID should ideally be clean (no spaces, etc.)
            unique_id_base = joint_name.replace(' ', '_').replace('.', '_')
            joint_id = f"{unique_id_base}_{i}"
            # Ensure ID is truly unique if names repeat (though AD format usually has unique names)
            while joint_id in std_skeleton.joints:
                joint_id += "_dup"

            if not isinstance(coords, list) or len(coords) != 2:
                logging.warning(f"Skipping AD joint '{joint_name}' due to invalid coordinates: {coords}")
                continue

            try:
                position_tuple = (float(coords[0]), float(coords[1]))
            except (ValueError, TypeError):
                logging.warning(f"Skipping AD joint '{joint_name}' due to non-numeric coordinates: {coords}")
                continue

            std_joint = StandardizedJointModel(
                id=joint_id,
                name=joint_name, # Standardized name is the AD name
                position=position_tuple,
                parent_id=None, # Will be resolved later
                label=joint_name, # Original name is same as standardized name here
                source_data=joint_info_raw.copy()
            )
            std_skeleton.joints[joint_id] = std_joint
            temp_joint_name_to_id[joint_name] = joint_id
            # Store parent_name for later hierarchy resolution. Handle if parent_name is an empty string or "None".
            temp_id_to_parent_name[joint_id] = parent_name if parent_name and str(parent_name).lower() != 'none' else None

            # Populate joint_map (original AD joint name to new standardized ID)
            if std_skeleton.joint_map is not None: # Pydantic initializes to {}
                 std_skeleton.joint_map[joint_name] = joint_id


        # Second pass: Resolve parent_ids and build hierarchy
        for joint_id, joint_model in std_skeleton.joints.items():
            parent_name = temp_id_to_parent_name.get(joint_id)
            if parent_name and parent_name in temp_joint_name_to_id:
                parent_id = temp_joint_name_to_id[parent_name]
                joint_model.parent_id = parent_id
                if std_skeleton.hierarchy is not None: # Pydantic initializes to {}
                    std_skeleton.hierarchy.setdefault(parent_id, []).append(joint_id)
            else:
                if std_skeleton.root_joint_ids is not None: # Pydantic initializes to []
                    std_skeleton.root_joint_ids.append(joint_id)

        # Attempt to calculate/derive limb_lengths if parts_data was provided
        # This part is heuristic and depends on conventions between char_cfg.yaml and parts naming.
        parts_data_for_lengths = data.get("parts_data_for_limb_lengths")
        if parts_data_for_lengths and isinstance(parts_data_for_lengths, dict) and std_skeleton.limb_lengths is not None:
            # Example heuristic: if a part's name corresponds to a joint name,
            # and that part has an 'roi', its height/width could be a proxy for limb length.
            # This is very rough. Animated Drawings sometimes provides 'limb_lengths' in char_cfg too.
            # A more robust approach would use `char_cfg.yaml`'s `limb_meta` if available.
            # For now, let's assume a simple direct calculation if joints align with visual parts.
            for joint_id_A, joint_A in std_skeleton.joints.items():
                if joint_A.parent_id and joint_A.parent_id in std_skeleton.joints:
                    joint_B = std_skeleton.joints[joint_A.parent_id]
                    dx = joint_A.position[0] - joint_B.position[0]
                    dy = joint_A.position[1] - joint_B.position[1]
                    length = math.sqrt(dx*dx + dy*dy)
                    # Try to find a descriptive name for this limb (e.g., parent_name-child_name)
                    limb_name_key = f"{joint_B.name}_to_{joint_A.name}"
                    std_skeleton.limb_lengths[limb_name_key] = length
                    # More sophisticated: Check 'limb_meta' if present in original 'data' from char_cfg
                    if "limb_meta" in data and isinstance(data["limb_meta"], dict):
                        for lm_key, lm_val in data["limb_meta"].items():
                             if isinstance(lm_val, (int, float)): # limb_meta often contains lengths directly
                                 std_skeleton.limb_lengths[lm_key] = float(lm_val)


        if not std_skeleton.joints:
            logging.warning("No valid joints processed from Animated Drawings format.")
            return None
        return std_skeleton

    def _process_already_standardized_format(self, data: Dict[str, Any]) -> Optional[StandardizedSkeletonModel]:
        """
        Processes data that is already expected to be in StandardizedSkeletonModel format.
        Mainly involves validation using Pydantic.
        """
        try:
            model = StandardizedSkeletonModel.model_validate(data)
            # Ensure basic consistency if loaded from raw dict (Pydantic does a lot, but double check hierarchy)
            if not model.hierarchy and model.joints: # Rebuild hierarchy if missing but joints exist
                for joint_id, joint in model.joints.items():
                    if joint.parent_id and joint.parent_id in model.joints:
                        model.hierarchy.setdefault(joint.parent_id, []).append(joint_id)
                    elif not joint.parent_id:
                        if joint_id not in model.root_joint_ids:
                             model.root_joint_ids.append(joint_id)
            if not model.root_joint_ids and model.joints and not any(j.parent_id for j in model.joints.values()):
                 model.root_joint_ids = list(model.joints.keys()) # All are roots if no parents

            return model
        except ValidationError as ve:
            logging.error(f"Data validation failed for StandardizedSkeletonModel format: {ve}", exc_info=True)
            self.error_occurred.emit(f"Invalid standardized skeleton data: {ve.errors()}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error processing pre-standardized format: {e}", exc_info=True)
            self.error_occurred.emit(f"Error processing skeleton: {e}")
            return None

    # --- Getter methods for specific joint information ---
    def get_joint_by_id(self, joint_id: str) -> Optional[StandardizedJointModel]:
        if self._standardized_skeleton_model and joint_id in self._standardized_skeleton_model.joints:
            return self._standardized_skeleton_model.joints[joint_id]
        return None

    def get_joint_by_name(self, name: str) -> Optional[StandardizedJointModel]:
        """Gets a joint by its 'name' field. Assumes names are reasonably unique or returns first match."""
        if self._standardized_skeleton_model:
            for joint in self._standardized_skeleton_model.joints.values():
                if joint.name == name:
                    return joint
        return None

    def get_joint_id_by_original_name(self, original_name: str) -> Optional[str]:
        """
        Retrieves the standardized joint ID using an original name from char_cfg.yaml (or similar source).
        Uses the 'joint_map' in the standardized model.
        """
        if self._standardized_skeleton_model and self._standardized_skeleton_model.joint_map:
            return self._standardized_skeleton_model.joint_map.get(original_name)
        return None


    def get_joint_position(self, joint_id_or_name: str) -> Optional[Tuple[float, float]]:
        joint = self.get_joint_by_id(joint_id_or_name) or self.get_joint_by_name(joint_id_or_name)
        return joint.position if joint else None

    def get_parent_joint(self, joint_id_or_name: str) -> Optional[StandardizedJointModel]:
        joint = self.get_joint_by_id(joint_id_or_name) or self.get_joint_by_name(joint_id_or_name)
        if joint and joint.parent_id and self._standardized_skeleton_model:
            return self._standardized_skeleton_model.joints.get(joint.parent_id)
        return None

    def get_child_joints(self, joint_id_or_name: str) -> List[StandardizedJointModel]:
        joint = self.get_joint_by_id(joint_id_or_name) or self.get_joint_by_name(joint_id_or_name)
        if joint and self._standardized_skeleton_model:
            child_ids = self._standardized_skeleton_model.hierarchy.get(joint.id, [])
            return [self._standardized_skeleton_model.joints[child_id] for child_id in child_ids if child_id in self._standardized_skeleton_model.joints]
        return []

    def get_limb_length(self, descriptive_limb_name: str) -> Optional[float]:
        """Gets a pre-calculated or defined limb length by its descriptive name."""
        if self._standardized_skeleton_model and self._standardized_skeleton_model.limb_lengths:
            return self._standardized_skeleton_model.limb_lengths.get(descriptive_limb_name)
        return None

if __name__ == '__main__':
    # Example Usage
    logging.basicConfig(level=logging.INFO)
    manager = SkeletonManager()

    # Example 1: Animated Drawings Format
    ad_skeleton_data = {
        "skeleton": [
            {"name": "hip", "parent": None, "coordinates": [0, 0]},
            {"name": "neck", "parent": "hip", "coordinates": [0, 50]},
            {"name": "head", "parent": "neck", "coordinates": [0, 70], "label_AD": "actual_head_part"},
            {"name": "left_shoulder", "parent": "neck", "coordinates": [-20, 50]},
            {"name": "left_elbow", "parent": "left_shoulder", "coordinates": [-40, 50]},
        ],
        "limb_meta": { # Example of how Animated Drawings might store some lengths
            "head_limb": 20.0,
            "left_upper_arm_limb": 25.0
        }
    }
    print("\n--- Loading Animated Drawings Skeleton ---")
    if manager.load_skeleton_from_dict(ad_skeleton_data):
        print("Successfully loaded AD skeleton.")
        if manager.standardized_model:
            print(f"  Model Source Format: {manager.standardized_model.source_format}")
            print(f"  Root joint IDs: {manager.standardized_model.root_joint_ids}")
            hip_joint = manager.get_joint_by_name("hip")
            if hip_joint:
                print(f"  Hip joint position: {hip_joint.position}")
                print(f"  Children of hip: {[child.name for child in manager.get_child_joints(hip_joint.id)]}")
            head_joint = manager.get_joint_by_name("head")
            if head_joint:
                print(f"  Head joint label from AD: {head_joint.label}") # Should be 'head'
                print(f"  Head parent: {manager.get_parent_joint(head_joint.id).name if manager.get_parent_joint(head_joint.id) else 'None'}")
            # Test limb lengths
            print(f"  Limb length 'hip_to_neck': {manager.get_limb_length('hip_to_neck')}")
            print(f"  Limb length from limb_meta 'head_limb': {manager.get_limb_length('head_limb')}")

    else:
        print("Failed to load AD skeleton.")

    # Example 2: Simulate loading data that's already standardized
    # (e.g. from a file saved by this manager previously)
    if manager.standardized_model:
        standard_data_to_simulate_load = manager.standardized_model.model_dump()
        print("\n--- Loading Already Standardized Skeleton (from previous AD load) ---")
        new_manager = SkeletonManager() # Use a new manager
        if new_manager.load_skeleton_from_dict(standard_data_to_simulate_load, source_format='standard'):
            print("Successfully loaded standard skeleton.")
            if new_manager.standardized_model:
                 print(f"  Root joint IDs: {new_manager.standardized_model.root_joint_ids}")
                 neck_joint = new_manager.get_joint_by_name("neck")
                 if neck_joint:
                    print(f"  Neck position: {neck_joint.position}")
        else:
            print("Failed to load standard skeleton.")


    # Example 3: Invalid/Empty Data
    print("\n--- Loading Empty Skeleton (None) ---")
    if not manager.load_skeleton_from_dict(None):
        print("Correctly handled Noneskeleton data.")

    print("\n--- Loading Empty Skeleton (empty dict) ---")
    if not manager.load_skeleton_from_dict({}): # This might be treated as invalid rather than empty
        print("Correctly handled empty dict as invalid or unprocessable.")

    print("\n--- Loading Empty AD Skeleton (skeleton: []) ---")
    empty_ad = {"skeleton": []}
    if manager.load_skeleton_from_dict(empty_ad, source_format='animated_drawings'):
        print("Successfully loaded empty AD skeleton.")
        if manager.standardized_model:
            print(f"  Joint count: {len(manager.standardized_model.joints)}")
    else:
        print("Failed to load empty AD skeleton.")


    def handle_skel_update(new_skel_dict: dict):
        print("\n--- skeleton_updated SIGNAL received (dict representation): ---")
        # print(new_skel_dict)
        if new_skel_dict and 'root_joint_ids' in new_skel_dict:
             print(f"Signal: Root joint IDs from dict: {new_skel_dict['root_joint_ids']}")
        # To access full model data, the receiver would typically call manager.standardized_model
        # Or, if the dict is complete, deserialize it: StandardizedSkeletonModel.model_validate(new_skel_dict)
        current_model = manager.standardized_model # Accessing via the manager instance
        if current_model:
            print(f"Signal: Neck position from manager model: {current_model.joints.get(current_model.joint_map.get('neck')).position if current_model.joint_map and current_model.joint_map.get('neck') in current_model.joints else 'N/A'}")


    manager.skeleton_updated.connect(handle_skel_update)
    print("\n--- Re-Loading Animated Drawings Skeleton to trigger signal ---")
    manager.load_skeleton_from_dict(ad_skeleton_data)

    # Test get functions with non-existent joint
    print("\n--- Testing non-existent joint ---")
    print("Position of 'non_existent_joint':", manager.get_joint_position("non_existent_joint"))
    print("Parent of 'non_existent_joint':", manager.get_parent_joint("non_existent_joint"))
    print("Children of 'non_existent_joint':", manager.get_child_joints("non_existent_joint"))

    # Test loading project data (list of dicts)
    project_skeleton_list = [
        {"id": "proj_hip", "name": "Hip", "position": [10, 10], "parent": None}, # Pydantic model's .model_dump() output
        {"id": "proj_spine", "name": "Spine", "position": [10, 60], "parent_id": "proj_hip"}, # Note: key used 'parent_id' vs 'parent'
    ]
    # To align with AD processing, it expects 'name', 'parent', 'coordinates'
    # So, this direct list might need adjustment or the processor needs to be more flexible.
    # For _process_animated_drawings_format, it would be:
    project_skeleton_list_for_ad_style = [
        {"name": "ProjectHip", "parent": None, "coordinates": [10,10], "source_id": "proj_hip"},
        {"name": "ProjectSpine", "parent": "ProjectHip", "coordinates": [10,60], "source_id": "proj_spine"}
    ]

    print("\n--- Loading Skeleton from Project Data (AD-style list) ---")
    if manager.load_skeleton_from_project_data(project_skeleton_list_for_ad_style):
        print("Successfully loaded skeleton from project data list.")
        if manager.standardized_model:
            print(f"  Root joint ID from project data: {manager.standardized_model.root_joint_ids}")
            spine_joint = manager.get_joint_by_name("ProjectSpine")
            if spine_joint:
                print(f"  ProjectSpine position: {spine_joint.position}")
                print(f"  ProjectSpine original source_id: {spine_joint.source_data.get('source_id') if spine_joint.source_data else 'N/A'}")
    else:
        print("Failed to load skeleton from project data list.")