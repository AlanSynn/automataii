"""
Main SkeletonManager that orchestrates all skeleton-related operations.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from .models import StandardizedJointModel, StandardizedSkeletonModel
from .format_converter import SkeletonFormatConverter
from .joint_manager import JointManager
from .hierarchy_manager import HierarchyManager
from .operations import SkeletonOperations
from .serializer import SkeletonSerializer


class SkeletonManager(QObject):
    """
    Main manager for skeleton data, coordinating all skeleton-related operations.
    """

    # Signals
    skeleton_updated = pyqtSignal(dict)  # Emits the new standardized skeleton data as a dict
    error_occurred = pyqtSignal(str)  # Emits an error message
    skeleton_data_cleared = pyqtSignal()  # Emits when skeleton data is cleared

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        # Internal state
        self._raw_input_skeleton_data: Optional[Dict[str, Any]] = None
        self._standardized_skeleton_model: Optional[StandardizedSkeletonModel] = None
        
        # Component managers
        self._joint_manager = JointManager()
        self._hierarchy_manager = HierarchyManager()
        
        logging.info("SkeletonManager initialized with modular components.")

    # ========== Properties ==========

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
        """Returns a dictionary of joint ID to (x,y) position."""
        return self._joint_manager.joint_positions

    @property
    def joint_hierarchy(self) -> Dict[str, List[str]]:
        """Returns the parent_id -> [child_ids] hierarchy."""
        return self._hierarchy_manager.joint_hierarchy

    @property
    def root_joints(self) -> List[str]:
        """Returns a list of root joint IDs."""
        return self._hierarchy_manager.root_joints

    # ========== Loading Methods ==========

    def load_skeleton_from_dict(
        self, data: Optional[Dict[str, Any]], source_format: str = "auto"
    ) -> bool:
        """
        Loads skeleton data from a dictionary.
        
        Args:
            data: The dictionary containing skeleton data
            source_format: 'auto', 'animated_drawings', or 'standard'
            
        Returns:
            True if loading was successful, False otherwise
        """
        self.clear_data()
        
        if not data:
            logging.warning("SkeletonManager: No data provided.")
            return False
            
        self._raw_input_skeleton_data = data
        logging.info(f"SkeletonManager: Loading skeleton from dict. Format: {source_format}")
        
        # Use format converter to process the data
        processed_model = SkeletonFormatConverter.convert_from_dict(data, source_format)
        
        if processed_model:
            self._set_skeleton_model(processed_model)
            logging.info(f"SkeletonManager: Skeleton data processed successfully.")
            self.skeleton_updated.emit(self._standardized_skeleton_model.model_dump())
            return True
        else:
            logging.error("SkeletonManager: Failed to process skeleton data.")
            self.clear_data()
            self.error_occurred.emit("Failed to process skeleton data.")
            return False

    def load_skeleton_from_project_data(
        self,
        raw_skeleton_list: Optional[List[Dict[str, Any]]],
        parts_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Loads skeleton data from a project data list.
        
        Args:
            raw_skeleton_list: List of joint dictionaries
            parts_data: Optional parts data for context
            
        Returns:
            True if loading was successful, False otherwise
        """
        logging.info(f"SkeletonManager: Loading from project data (joints: {len(raw_skeleton_list) if raw_skeleton_list else 0})")
        
        if not raw_skeleton_list:
            self.clear_data()
            return True
            
        # Use format converter
        processed_model = SkeletonFormatConverter.convert_from_project_data(
            raw_skeleton_list, parts_data
        )
        
        if processed_model:
            self._set_skeleton_model(processed_model)
            self.skeleton_updated.emit(self._standardized_skeleton_model.model_dump())
            return True
        else:
            self.clear_data()
            self.error_occurred.emit("Failed to process project skeleton data.")
            return False

    def load_skeleton_from_file(self, file_path: Path) -> bool:
        """
        Load skeleton from a JSON file.
        
        Args:
            file_path: Path to the skeleton JSON file
            
        Returns:
            True if loading was successful, False otherwise
        """
        model = SkeletonSerializer.load_from_file(file_path)
        if model:
            self._set_skeleton_model(model)
            self.skeleton_updated.emit(self._standardized_skeleton_model.model_dump())
            return True
        else:
            self.error_occurred.emit(f"Failed to load skeleton from {file_path}")
            return False

    # ========== Saving Methods ==========

    def save_skeleton_to_file(self, file_path: Path) -> bool:
        """
        Save the current skeleton to a JSON file.
        
        Args:
            file_path: Path where to save the skeleton
            
        Returns:
            True if saving was successful, False otherwise
        """
        if not self._standardized_skeleton_model:
            self.error_occurred.emit("No skeleton data to save.")
            return False
            
        success = SkeletonSerializer.save_to_file(self._standardized_skeleton_model, file_path)
        if not success:
            self.error_occurred.emit(f"Failed to save skeleton to {file_path}")
        return success

    # ========== Joint Access Methods (delegated) ==========

    def get_joint_by_id(self, joint_id: str) -> Optional[StandardizedJointModel]:
        """Get a joint by its ID."""
        return self._joint_manager.get_joint_by_id(joint_id)

    def get_joint_by_name(self, name: str) -> Optional[StandardizedJointModel]:
        """Get a joint by its name."""
        return self._joint_manager.get_joint_by_name(name)

    def get_joint_id_by_original_name(self, original_name: str) -> Optional[str]:
        """Get joint ID by original name from source format."""
        return self._joint_manager.get_joint_id_by_original_name(original_name)

    def get_joint_position(self, joint_id_or_name: str) -> Optional[Tuple[float, float]]:
        """Get joint position by ID or name."""
        return self._joint_manager.get_joint_position(joint_id_or_name)

    def get_parent_joint(self, joint_id_or_name: str) -> Optional[StandardizedJointModel]:
        """Get parent joint."""
        return self._joint_manager.get_parent_joint(joint_id_or_name)

    def get_child_joints(self, joint_id_or_name: str) -> List[StandardizedJointModel]:
        """Get child joints."""
        return self._joint_manager.get_child_joints(joint_id_or_name)

    def get_limb_length(self, descriptive_limb_name: str) -> Optional[float]:
        """Get limb length by name."""
        return self._joint_manager.get_limb_length(descriptive_limb_name)

    def get_locked_joints(self) -> List[str]:
        """Get list of locked joint IDs."""
        return self._joint_manager.get_locked_joints()

    # ========== Hierarchy Methods (delegated) ==========

    def get_ancestors(self, joint_id: str) -> List[str]:
        """Get all ancestor joint IDs."""
        return self._hierarchy_manager.get_ancestors(joint_id)

    def get_descendants(self, joint_id: str) -> List[str]:
        """Get all descendant joint IDs."""
        return self._hierarchy_manager.get_descendants(joint_id)

    def validate_hierarchy(self) -> List[str]:
        """Validate hierarchy consistency."""
        return self._hierarchy_manager.validate_hierarchy()

    # ========== Operation Methods (delegated) ==========

    def extend_skeleton_lengths(self, scale_factor: float = 1.1) -> bool:
        """Extend skeleton bone lengths."""
        if not self._standardized_skeleton_model:
            logging.warning("No skeleton model loaded to extend")
            return False
            
        success = SkeletonOperations.extend_skeleton_lengths(
            self._standardized_skeleton_model, scale_factor
        )
        
        if success:
            self.skeleton_updated.emit(self._standardized_skeleton_model.model_dump())
        return success

    def lock_joint(self, joint_id_or_name: str, locked: bool = True) -> bool:
        """Lock or unlock a joint."""
        if not self._standardized_skeleton_model:
            logging.warning("No skeleton model loaded")
            return False
            
        success = SkeletonOperations.lock_joint(
            self._standardized_skeleton_model, joint_id_or_name, locked
        )
        
        if success:
            self.skeleton_updated.emit(self._standardized_skeleton_model.model_dump())
        return success

    def unlock_all_joints(self) -> bool:
        """Unlock all joints."""
        if not self._standardized_skeleton_model:
            logging.warning("No skeleton model loaded")
            return False
            
        success = SkeletonOperations.unlock_all_joints(self._standardized_skeleton_model)
        
        if success:
            self.skeleton_updated.emit(self._standardized_skeleton_model.model_dump())
        return success

    def translate_skeleton(self, dx: float, dy: float) -> bool:
        """Translate the entire skeleton."""
        if not self._standardized_skeleton_model:
            return False
            
        success = SkeletonOperations.translate_skeleton(
            self._standardized_skeleton_model, dx, dy
        )
        
        if success:
            self.skeleton_updated.emit(self._standardized_skeleton_model.model_dump())
        return success

    def rotate_skeleton(
        self, angle_degrees: float, center: Optional[Tuple[float, float]] = None
    ) -> bool:
        """Rotate the skeleton."""
        if not self._standardized_skeleton_model:
            return False
            
        success = SkeletonOperations.rotate_skeleton(
            self._standardized_skeleton_model, angle_degrees, center
        )
        
        if success:
            self.skeleton_updated.emit(self._standardized_skeleton_model.model_dump())
        return success

    # ========== Utility Methods ==========

    def clear_data(self):
        """Clear all skeleton data."""
        logging.info("SkeletonManager: Clearing all skeleton data.")
        self._raw_input_skeleton_data = None
        self._standardized_skeleton_model = None
        self._joint_manager.skeleton_model = None
        self._hierarchy_manager.skeleton_model = None
        self.skeleton_data_cleared.emit()
        self.skeleton_updated.emit({})

    def get_skeleton_as_dict(self) -> Dict[str, Any]:
        """Get the current skeleton as a dictionary."""
        if not self._standardized_skeleton_model:
            return {}
        return SkeletonSerializer.to_dict(self._standardized_skeleton_model)

    def get_skeleton_as_json(self, indent: int = 2) -> str:
        """Get the current skeleton as JSON string."""
        if not self._standardized_skeleton_model:
            return "{}"
        return SkeletonSerializer.to_json(self._standardized_skeleton_model, indent)

    def export_simplified(self) -> Dict[str, Any]:
        """Export a simplified version of the skeleton."""
        if not self._standardized_skeleton_model:
            return {}
        return SkeletonSerializer.export_simplified(self._standardized_skeleton_model)

    # ========== Private Methods ==========

    def _set_skeleton_model(self, model: StandardizedSkeletonModel) -> None:
        """Set the skeleton model and update component managers."""
        self._standardized_skeleton_model = model
        self._joint_manager.skeleton_model = model
        self._hierarchy_manager.skeleton_model = model