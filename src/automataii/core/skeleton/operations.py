"""
Skeleton operations module for transformations and modifications.
"""

import logging
import math
from typing import Optional, Tuple, Set

from .models import StandardizedJointModel, StandardizedSkeletonModel


class SkeletonOperations:
    """Provides operations for modifying and transforming skeletons."""

    @staticmethod
    def extend_skeleton_lengths(
        skeleton_model: StandardizedSkeletonModel, scale_factor: float = 1.1
    ) -> bool:
        """
        Extends all skeleton bone lengths by the given scale factor.
        
        Args:
            skeleton_model: The skeleton model to modify
            scale_factor: The factor to scale bone lengths by (default 1.1 for 10% increase)
            
        Returns:
            True if successful, False otherwise
        """
        if not skeleton_model:
            logging.warning("No skeleton model provided to extend")
            return False
            
        try:
            logging.info(f"Extending skeleton lengths by factor {scale_factor}")
            
            # Store the root positions as they should not move
            root_positions = {}
            for root_id in skeleton_model.root_joint_ids:
                if root_id in skeleton_model.joints:
                    root_positions[root_id] = skeleton_model.joints[root_id].position
            
            # Process each joint starting from roots
            processed_joints = set()
            
            def scale_joint_recursive(joint_id: str, parent_pos: Optional[Tuple[float, float]] = None):
                if joint_id in processed_joints:
                    return
                    
                processed_joints.add(joint_id)
                joint = skeleton_model.joints.get(joint_id)
                if not joint:
                    return
                    
                # If this is not a root joint and has a parent position, scale its position
                if parent_pos is not None and joint.parent_id:
                    # Calculate the vector from parent to this joint
                    dx = joint.position[0] - parent_pos[0]
                    dy = joint.position[1] - parent_pos[1]
                    
                    # Scale the vector
                    new_dx = dx * scale_factor
                    new_dy = dy * scale_factor
                    
                    # Set new position
                    new_pos = (parent_pos[0] + new_dx, parent_pos[1] + new_dy)
                    joint.position = new_pos
                    
                    # Update limb length if it exists
                    parent_joint = skeleton_model.joints.get(joint.parent_id)
                    if parent_joint and skeleton_model.limb_lengths:
                        limb_key = f"{parent_joint.name}_to_{joint.name}"
                        if limb_key in skeleton_model.limb_lengths:
                            skeleton_model.limb_lengths[limb_key] *= scale_factor
                
                # Process children
                current_pos = joint.position
                child_ids = skeleton_model.hierarchy.get(joint_id, [])
                for child_id in child_ids:
                    scale_joint_recursive(child_id, current_pos)
            
            # Start scaling from each root
            for root_id in skeleton_model.root_joint_ids:
                if root_id in skeleton_model.joints:
                    scale_joint_recursive(root_id)
            
            # Scale all limb lengths that haven't been updated yet
            if skeleton_model.limb_lengths:
                for limb_name in list(skeleton_model.limb_lengths.keys()):
                    # This ensures any pre-calculated lengths are also scaled
                    skeleton_model.limb_lengths[limb_name] *= scale_factor
            
            logging.info(f"Successfully extended skeleton lengths by {scale_factor}")
            return True
            
        except Exception as e:
            logging.error(f"Error extending skeleton lengths: {e}", exc_info=True)
            return False

    @staticmethod
    def lock_joint(
        skeleton_model: StandardizedSkeletonModel,
        joint_id_or_name: str,
        locked: bool = True,
    ) -> bool:
        """
        Locks or unlocks a specific joint for IK solving.
        
        Args:
            skeleton_model: The skeleton model containing the joint
            joint_id_or_name: The ID or name of the joint to lock/unlock
            locked: True to lock, False to unlock
            
        Returns:
            True if successful, False otherwise
        """
        if not skeleton_model:
            logging.warning("No skeleton model provided")
            return False
            
        # Try to find by ID first
        joint = skeleton_model.joints.get(joint_id_or_name)
        
        # If not found by ID, search by name
        if not joint:
            for j in skeleton_model.joints.values():
                if j.name == joint_id_or_name:
                    joint = j
                    break
                    
        if not joint:
            logging.warning(f"Joint '{joint_id_or_name}' not found")
            return False
            
        joint.is_locked = locked
        logging.info(f"Joint '{joint.name}' (ID: {joint.id}) {'locked' if locked else 'unlocked'}")
        return True

    @staticmethod
    def unlock_all_joints(skeleton_model: StandardizedSkeletonModel) -> bool:
        """
        Unlocks all joints in the skeleton.
        
        Args:
            skeleton_model: The skeleton model to modify
            
        Returns:
            True if successful, False otherwise
        """
        if not skeleton_model:
            logging.warning("No skeleton model provided")
            return False
            
        for joint in skeleton_model.joints.values():
            joint.is_locked = False
            
        logging.info("All joints unlocked")
        return True

    @staticmethod
    def translate_skeleton(
        skeleton_model: StandardizedSkeletonModel, dx: float, dy: float
    ) -> bool:
        """
        Translate all joints in the skeleton by the given offset.
        
        Args:
            skeleton_model: The skeleton model to modify
            dx: X-axis translation
            dy: Y-axis translation
            
        Returns:
            True if successful, False otherwise
        """
        if not skeleton_model:
            return False
            
        try:
            for joint in skeleton_model.joints.values():
                joint.position = (joint.position[0] + dx, joint.position[1] + dy)
            return True
        except Exception as e:
            logging.error(f"Error translating skeleton: {e}")
            return False

    @staticmethod
    def rotate_skeleton(
        skeleton_model: StandardizedSkeletonModel,
        angle_degrees: float,
        center: Optional[Tuple[float, float]] = None,
    ) -> bool:
        """
        Rotate all joints in the skeleton around a center point.
        
        Args:
            skeleton_model: The skeleton model to modify
            angle_degrees: Rotation angle in degrees
            center: Center of rotation (x, y). If None, uses the average of all joint positions
            
        Returns:
            True if successful, False otherwise
        """
        if not skeleton_model or not skeleton_model.joints:
            return False
            
        try:
            # Calculate center if not provided
            if center is None:
                sum_x = sum(j.position[0] for j in skeleton_model.joints.values())
                sum_y = sum(j.position[1] for j in skeleton_model.joints.values())
                count = len(skeleton_model.joints)
                center = (sum_x / count, sum_y / count)
            
            # Convert angle to radians
            angle_rad = math.radians(angle_degrees)
            cos_angle = math.cos(angle_rad)
            sin_angle = math.sin(angle_rad)
            
            # Rotate each joint
            for joint in skeleton_model.joints.values():
                # Translate to origin
                x = joint.position[0] - center[0]
                y = joint.position[1] - center[1]
                
                # Rotate
                new_x = x * cos_angle - y * sin_angle
                new_y = x * sin_angle + y * cos_angle
                
                # Translate back
                joint.position = (new_x + center[0], new_y + center[1])
            
            return True
        except Exception as e:
            logging.error(f"Error rotating skeleton: {e}")
            return False

    @staticmethod
    def scale_skeleton(
        skeleton_model: StandardizedSkeletonModel,
        scale_x: float,
        scale_y: float,
        center: Optional[Tuple[float, float]] = None,
    ) -> bool:
        """
        Scale the skeleton by different factors on each axis.
        
        Args:
            skeleton_model: The skeleton model to modify
            scale_x: X-axis scale factor
            scale_y: Y-axis scale factor
            center: Center of scaling. If None, uses the average of all joint positions
            
        Returns:
            True if successful, False otherwise
        """
        if not skeleton_model or not skeleton_model.joints:
            return False
            
        try:
            # Calculate center if not provided
            if center is None:
                sum_x = sum(j.position[0] for j in skeleton_model.joints.values())
                sum_y = sum(j.position[1] for j in skeleton_model.joints.values())
                count = len(skeleton_model.joints)
                center = (sum_x / count, sum_y / count)
            
            # Scale each joint position
            for joint in skeleton_model.joints.values():
                # Translate to origin
                x = joint.position[0] - center[0]
                y = joint.position[1] - center[1]
                
                # Scale
                new_x = x * scale_x
                new_y = y * scale_y
                
                # Translate back
                joint.position = (new_x + center[0], new_y + center[1])
            
            # Update limb lengths if they exist
            if skeleton_model.limb_lengths:
                # For non-uniform scaling, we need to recalculate limb lengths
                SkeletonOperations._recalculate_limb_lengths(skeleton_model)
            
            return True
        except Exception as e:
            logging.error(f"Error scaling skeleton: {e}")
            return False

    @staticmethod
    def _recalculate_limb_lengths(skeleton_model: StandardizedSkeletonModel) -> None:
        """Recalculate all limb lengths based on current joint positions."""
        if not skeleton_model.limb_lengths:
            return
            
        # Clear existing lengths
        skeleton_model.limb_lengths.clear()
        
        # Recalculate based on hierarchy
        for joint_id, joint in skeleton_model.joints.items():
            if joint.parent_id and joint.parent_id in skeleton_model.joints:
                parent_joint = skeleton_model.joints[joint.parent_id]
                dx = joint.position[0] - parent_joint.position[0]
                dy = joint.position[1] - parent_joint.position[1]
                length = math.sqrt(dx * dx + dy * dy)
                
                limb_key = f"{parent_joint.name}_to_{joint.name}"
                skeleton_model.limb_lengths[limb_key] = length

    @staticmethod
    def mirror_skeleton(
        skeleton_model: StandardizedSkeletonModel,
        axis: str = "vertical",
        center: Optional[float] = None,
    ) -> bool:
        """
        Mirror the skeleton along a specified axis.
        
        Args:
            skeleton_model: The skeleton model to modify
            axis: 'vertical' for left-right mirror, 'horizontal' for top-bottom mirror
            center: The axis position. If None, uses the center of the skeleton
            
        Returns:
            True if successful, False otherwise
        """
        if not skeleton_model or not skeleton_model.joints:
            return False
            
        try:
            if axis == "vertical":
                # Calculate center x if not provided
                if center is None:
                    sum_x = sum(j.position[0] for j in skeleton_model.joints.values())
                    center = sum_x / len(skeleton_model.joints)
                
                # Mirror x coordinates
                for joint in skeleton_model.joints.values():
                    x_dist = joint.position[0] - center
                    joint.position = (center - x_dist, joint.position[1])
                    
            elif axis == "horizontal":
                # Calculate center y if not provided
                if center is None:
                    sum_y = sum(j.position[1] for j in skeleton_model.joints.values())
                    center = sum_y / len(skeleton_model.joints)
                
                # Mirror y coordinates
                for joint in skeleton_model.joints.values():
                    y_dist = joint.position[1] - center
                    joint.position = (joint.position[0], center - y_dist)
            else:
                logging.error(f"Invalid axis '{axis}'. Use 'vertical' or 'horizontal'")
                return False
            
            return True
        except Exception as e:
            logging.error(f"Error mirroring skeleton: {e}")
            return False