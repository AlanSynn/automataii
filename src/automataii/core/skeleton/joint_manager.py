"""
Joint management module for accessing and querying joints in a skeleton.
"""

from typing import Dict, List, Optional, Tuple

from .models import StandardizedJointModel, StandardizedSkeletonModel


class JointManager:
    """Manages joint access and queries for a skeleton."""

    def __init__(self, skeleton_model: Optional[StandardizedSkeletonModel] = None):
        self._skeleton_model = skeleton_model

    @property
    def skeleton_model(self) -> Optional[StandardizedSkeletonModel]:
        """Get the current skeleton model."""
        return self._skeleton_model

    @skeleton_model.setter
    def skeleton_model(self, model: Optional[StandardizedSkeletonModel]) -> None:
        """Set the skeleton model."""
        self._skeleton_model = model

    @property
    def joint_positions(self) -> Dict[str, Tuple[float, float]]:
        """Returns a dictionary of joint ID to (x,y) position from the standardized model."""
        if not self._skeleton_model:
            return {}
        return {
            joint_id: joint.position
            for joint_id, joint in self._skeleton_model.joints.items()
        }

    def get_joint_by_id(self, joint_id: str) -> Optional[StandardizedJointModel]:
        """Get a joint by its ID."""
        if self._skeleton_model and joint_id in self._skeleton_model.joints:
            return self._skeleton_model.joints[joint_id]
        return None

    def get_joint_by_name(self, name: str) -> Optional[StandardizedJointModel]:
        """Gets a joint by its 'name' field. Returns first match if multiple joints have the same name."""
        if self._skeleton_model:
            for joint in self._skeleton_model.joints.values():
                if joint.name == name:
                    return joint
        return None

    def get_joint_id_by_original_name(self, original_name: str) -> Optional[str]:
        """
        Retrieves the standardized joint ID using an original name from char_cfg.yaml (or similar source).
        Uses the 'joint_map' in the standardized model.
        """
        if self._skeleton_model and self._skeleton_model.joint_map:
            return self._skeleton_model.joint_map.get(original_name)
        return None

    def get_joint_position(
        self, joint_id_or_name: str
    ) -> Optional[Tuple[float, float]]:
        """Get the position of a joint by ID or name."""
        joint = self.get_joint_by_id(joint_id_or_name) or self.get_joint_by_name(
            joint_id_or_name
        )
        return joint.position if joint else None

    def get_parent_joint(
        self, joint_id_or_name: str
    ) -> Optional[StandardizedJointModel]:
        """Get the parent joint of a given joint."""
        joint = self.get_joint_by_id(joint_id_or_name) or self.get_joint_by_name(
            joint_id_or_name
        )
        if joint and joint.parent_id and self._skeleton_model:
            return self._skeleton_model.joints.get(joint.parent_id)
        return None

    def get_child_joints(self, joint_id_or_name: str) -> List[StandardizedJointModel]:
        """Get all child joints of a given joint."""
        joint = self.get_joint_by_id(joint_id_or_name) or self.get_joint_by_name(
            joint_id_or_name
        )
        if joint and self._skeleton_model:
            child_ids = self._skeleton_model.hierarchy.get(joint.id, [])
            return [
                self._skeleton_model.joints[child_id]
                for child_id in child_ids
                if child_id in self._skeleton_model.joints
            ]
        return []

    def get_limb_length(self, descriptive_limb_name: str) -> Optional[float]:
        """Gets a pre-calculated or defined limb length by its descriptive name."""
        if self._skeleton_model and self._skeleton_model.limb_lengths:
            return self._skeleton_model.limb_lengths.get(descriptive_limb_name)
        return None

    def get_locked_joints(self) -> List[str]:
        """Returns a list of joint IDs that are currently locked."""
        if not self._skeleton_model:
            return []
            
        return [
            joint_id 
            for joint_id, joint in self._skeleton_model.joints.items()
            if joint.is_locked
        ]

    def find_joints_by_label(self, label: str) -> List[StandardizedJointModel]:
        """Find all joints with a specific label."""
        if not self._skeleton_model:
            return []
            
        return [
            joint
            for joint in self._skeleton_model.joints.values()
            if joint.label == label
        ]

    def get_all_joint_ids(self) -> List[str]:
        """Get all joint IDs in the skeleton."""
        if not self._skeleton_model:
            return []
        return list(self._skeleton_model.joints.keys())

    def get_all_joint_names(self) -> List[str]:
        """Get all joint names in the skeleton."""
        if not self._skeleton_model:
            return []
        return [joint.name for joint in self._skeleton_model.joints.values()]