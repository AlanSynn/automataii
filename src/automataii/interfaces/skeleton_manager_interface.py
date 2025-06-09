"""Interface for Skeleton Manager to enable dependency injection."""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List, Tuple
from PyQt6.QtCore import QPointF


class SkeletonManagerInterface(ABC):
    """Interface for Skeleton Manager.
    
    This interface defines the contract for skeleton management,
    enabling dependency injection and easier testing.
    """
    
    @abstractmethod
    def load_skeleton_from_annotations(self, annotation_data: Dict[str, Any]) -> bool:
        """Load skeleton from annotation data.
        
        Args:
            annotation_data: Dictionary containing skeleton annotations
            
        Returns:
            True if loaded successfully
        """
        pass
    
    @abstractmethod
    def get_standardized_skeleton_dict(self) -> Optional[Dict[str, Any]]:
        """Get standardized skeleton data.
        
        Returns:
            Dictionary of standardized skeleton data or None
        """
        pass
    
    @abstractmethod
    def get_joint_position(self, joint_name: str) -> Optional[QPointF]:
        """Get position of a specific joint.
        
        Args:
            joint_name: Name of the joint
            
        Returns:
            Joint position or None if not found
        """
        pass
    
    @abstractmethod
    def get_joint_angle(self, joint_name: str) -> Optional[float]:
        """Get angle of a specific joint.
        
        Args:
            joint_name: Name of the joint
            
        Returns:
            Joint angle in radians or None if not found
        """
        pass
    
    @abstractmethod
    def get_bone_length(self, bone_name: str) -> Optional[float]:
        """Get length of a specific bone.
        
        Args:
            bone_name: Name of the bone
            
        Returns:
            Bone length or None if not found
        """
        pass
    
    @abstractmethod
    def get_joint_hierarchy(self) -> Dict[str, List[str]]:
        """Get joint hierarchy.
        
        Returns:
            Dictionary mapping parent joints to child joints
        """
        pass
    
    @abstractmethod
    def get_joint_by_standardized_name(self, std_name: str) -> Optional[Dict[str, Any]]:
        """Get joint data by standardized name.
        
        Args:
            std_name: Standardized joint name
            
        Returns:
            Joint data dictionary or None
        """
        pass
    
    @abstractmethod
    def update_joint_position(self, joint_name: str, position: QPointF) -> bool:
        """Update position of a joint.
        
        Args:
            joint_name: Name of the joint
            position: New position
            
        Returns:
            True if updated successfully
        """
        pass
    
    @abstractmethod
    def update_joint_angle(self, joint_name: str, angle: float) -> bool:
        """Update angle of a joint.
        
        Args:
            joint_name: Name of the joint
            angle: New angle in radians
            
        Returns:
            True if updated successfully
        """
        pass
    
    @abstractmethod
    def calculate_forward_kinematics(self) -> Dict[str, QPointF]:
        """Calculate forward kinematics for all joints.
        
        Returns:
            Dictionary mapping joint names to calculated positions
        """
        pass
    
    @abstractmethod
    def calculate_inverse_kinematics(
        self, 
        end_effector: str, 
        target_position: QPointF
    ) -> Optional[Dict[str, float]]:
        """Calculate inverse kinematics.
        
        Args:
            end_effector: Name of the end effector joint
            target_position: Target position for the end effector
            
        Returns:
            Dictionary of joint angles or None if no solution
        """
        pass
    
    @abstractmethod
    def get_skeleton_bounds(self) -> Tuple[QPointF, QPointF]:
        """Get bounding box of the skeleton.
        
        Returns:
            Tuple of (min_point, max_point)
        """
        pass
    
    @abstractmethod
    def validate_skeleton(self) -> Tuple[bool, List[str]]:
        """Validate skeleton structure.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        pass
    
    @abstractmethod
    def reset_to_default_pose(self) -> None:
        """Reset skeleton to default pose."""
        pass
    
    @abstractmethod
    def export_skeleton_data(self) -> Dict[str, Any]:
        """Export skeleton data for serialization.
        
        Returns:
            Serializable dictionary of skeleton data
        """
        pass