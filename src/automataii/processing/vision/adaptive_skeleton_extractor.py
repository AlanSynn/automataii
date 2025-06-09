"""
Adaptive skeleton extraction that can handle different character types.
"""

import logging
from typing import Optional, Dict, List, Tuple, Any
import numpy as np
import cv2
from pathlib import Path

from automataii.core.models.skeleton import StandardizedSkeletonModel, StandardizedJointModel
from automataii.core.models.skeleton_types import (
    SkeletonType, SkeletonTemplate, create_skeleton_from_template, get_skeleton_template
)
from automataii.core.skeleton_type_detector import SkeletonTypeDetector


class AdaptiveSkeletonExtractor:
    """Extracts skeletons adaptively based on character type."""
    
    def __init__(self, enable_non_human: bool = False):
        """
        Initialize the adaptive skeleton extractor.
        
        Args:
            enable_non_human: Whether to enable non-human skeleton detection
        """
        self.enable_non_human = enable_non_human
        self.type_detector = SkeletonTypeDetector()
        self.logger = logging.getLogger(__name__)
        
    def extract_skeleton(
        self,
        image: np.ndarray,
        pose_results: Optional[List[Dict]] = None,
        mask: Optional[np.ndarray] = None,
        bbox: Optional[Tuple[int, int, int, int]] = None,
        force_type: Optional[SkeletonType] = None
    ) -> Optional[StandardizedSkeletonModel]:
        """
        Extract skeleton from image adaptively based on character type.
        
        Args:
            image: Input image
            pose_results: Human pose detection results (if available)
            mask: Character segmentation mask
            bbox: Character bounding box (x, y, w, h)
            force_type: Force a specific skeleton type
            
        Returns:
            StandardizedSkeletonModel or None if extraction fails
        """
        if not self.enable_non_human and force_type is None:
            # Use traditional human skeleton extraction
            if pose_results:
                return self._extract_human_skeleton_from_pose(pose_results, bbox)
            else:
                self.logger.warning("No pose results available for human skeleton extraction")
                return None
                
        # Determine skeleton type
        if force_type:
            skeleton_type = force_type
            confidence = 1.0
        else:
            # Classify based on available data
            if pose_results:
                # Try to use pose keypoints for classification
                pose_keypoints = self._extract_pose_keypoints(pose_results)
                classification = self.type_detector.classify_from_pose_data(pose_keypoints)
            elif mask is not None and bbox:
                # Use image features for classification
                contour = self._extract_contour_from_mask(mask)
                classification = self.type_detector.classify_from_image_features(
                    contour, bbox, mask
                )
            else:
                self.logger.warning("Insufficient data for skeleton type classification")
                return None
                
            skeleton_type = classification.primary_type
            confidence = classification.confidence
            
            self.logger.info(
                f"Detected skeleton type: {skeleton_type.value} "
                f"(confidence: {confidence:.2f})"
            )
            
        # Extract skeleton based on type
        if skeleton_type == SkeletonType.HUMANOID and pose_results:
            return self._extract_human_skeleton_from_pose(pose_results, bbox)
        elif skeleton_type == SkeletonType.UNKNOWN:
            self.logger.warning("Unknown skeleton type detected")
            return None
        else:
            # Use template-based extraction for non-human types
            return self._extract_skeleton_from_template(
                skeleton_type, image, mask, bbox
            )
            
    def _extract_human_skeleton_from_pose(
        self,
        pose_results: List[Dict],
        bbox: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[StandardizedSkeletonModel]:
        """Extract human skeleton from pose detection results."""
        if not pose_results or len(pose_results) == 0:
            return None
            
        # Get keypoints from first detection
        kpts = pose_results[0]["keypoints"][:, :2]
        
        # Build skeleton structure (same as original)
        joints = {}
        hierarchy = {}
        
        # Calculate offset if bbox provided
        offset_x = bbox[0] if bbox else 0
        offset_y = bbox[1] if bbox else 0
        
        # Define joint mappings
        joint_mappings = [
            ("root", (kpts[11] + kpts[12]) / 2, None),
            ("hip", (kpts[11] + kpts[12]) / 2, "root"),
            ("torso", (kpts[5] + kpts[6]) / 2, "hip"),
            ("neck", kpts[0], "torso"),
            ("right_shoulder", kpts[6], "torso"),
            ("right_elbow", kpts[8], "right_shoulder"),
            ("right_hand", kpts[10], "right_elbow"),
            ("left_shoulder", kpts[5], "torso"),
            ("left_elbow", kpts[7], "left_shoulder"),
            ("left_hand", kpts[9], "left_elbow"),
            ("right_hip", kpts[12], "root"),
            ("right_knee", kpts[14], "right_hip"),
            ("right_foot", kpts[16], "right_knee"),
            ("left_hip", kpts[11], "root"),
            ("left_knee", kpts[13], "left_hip"),
            ("left_foot", kpts[15], "left_knee"),
        ]
        
        # Create joints
        for joint_id, position, parent_id in joint_mappings:
            joint = StandardizedJointModel(
                id=joint_id,
                name=joint_id.replace("_", " ").title(),
                position=(
                    float(position[0] + offset_x),
                    float(position[1] + offset_y)
                ),
                parent_id=parent_id
            )
            joints[joint_id] = joint
            
            # Build hierarchy
            if parent_id:
                if parent_id not in hierarchy:
                    hierarchy[parent_id] = []
                hierarchy[parent_id].append(joint_id)
                
        # Find root joints
        root_joint_ids = ["root"]
        
        return StandardizedSkeletonModel(
            joints=joints,
            root_joint_ids=root_joint_ids,
            hierarchy=hierarchy,
            source_format="pose_detection",
            metadata={
                "skeleton_type": SkeletonType.HUMANOID.value,
                "extraction_method": "pose_keypoints"
            }
        )
        
    def _extract_skeleton_from_template(
        self,
        skeleton_type: SkeletonType,
        image: np.ndarray,
        mask: Optional[np.ndarray],
        bbox: Optional[Tuple[int, int, int, int]]
    ) -> Optional[StandardizedSkeletonModel]:
        """Extract skeleton using template matching."""
        template = get_skeleton_template(skeleton_type)
        if not template:
            self.logger.error(f"No template found for skeleton type: {skeleton_type}")
            return None
            
        # Calculate scale and offset based on bbox
        if bbox:
            x, y, w, h = bbox
            scale = max(w, h)
            offset = (x, y)
        else:
            # Use image dimensions
            h, w = image.shape[:2]
            scale = max(w, h)
            offset = (0, 0)
            
        # Create skeleton from template
        skeleton = create_skeleton_from_template(template, scale, offset)
        
        # Optionally refine joint positions based on image features
        if mask is not None:
            skeleton = self._refine_skeleton_positions(skeleton, mask, bbox)
            
        return skeleton
        
    def _extract_pose_keypoints(
        self, 
        pose_results: List[Dict]
    ) -> Dict[str, Tuple[float, float]]:
        """Extract pose keypoints as a dictionary."""
        if not pose_results or len(pose_results) == 0:
            return {}
            
        kpts = pose_results[0]["keypoints"][:, :2]
        
        # Map to common keypoint names (COCO format)
        keypoint_names = [
            "nose", "left_eye", "right_eye", "left_ear", "right_ear",
            "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
            "left_wrist", "right_wrist", "left_hip", "right_hip",
            "left_knee", "right_knee", "left_ankle", "right_ankle"
        ]
        
        keypoints = {}
        for i, name in enumerate(keypoint_names):
            if i < len(kpts):
                keypoints[name] = tuple(kpts[i])
                
        return keypoints
        
    def _extract_contour_from_mask(self, mask: np.ndarray) -> np.ndarray:
        """Extract the main contour from a mask."""
        # Ensure mask is binary
        if mask.dtype != np.uint8:
            mask = (mask > 0).astype(np.uint8) * 255
            
        # Find contours
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours:
            return np.array([])
            
        # Return the largest contour
        largest_contour = max(contours, key=cv2.contourArea)
        return largest_contour
        
    def _refine_skeleton_positions(
        self,
        skeleton: StandardizedSkeletonModel,
        mask: np.ndarray,
        bbox: Optional[Tuple[int, int, int, int]]
    ) -> StandardizedSkeletonModel:
        """Refine skeleton joint positions based on image features."""
        # This is a placeholder for more sophisticated refinement
        # Could use techniques like:
        # - Medial axis transform
        # - Distance transform
        # - Feature point detection
        # - Machine learning-based refinement
        
        # For now, just return the skeleton as-is
        return skeleton
        
    def create_custom_skeleton(
        self,
        joint_positions: Dict[str, Tuple[float, float]],
        bone_connections: List[Tuple[str, str]],
        skeleton_type: SkeletonType = SkeletonType.CUSTOM
    ) -> StandardizedSkeletonModel:
        """
        Create a custom skeleton from user-defined joints and connections.
        
        Args:
            joint_positions: Dictionary of joint IDs to positions
            bone_connections: List of (parent_id, child_id) tuples
            skeleton_type: Type of skeleton
            
        Returns:
            StandardizedSkeletonModel
        """
        joints = {}
        hierarchy = {}
        
        # Create joints
        for joint_id, position in joint_positions.items():
            joint = StandardizedJointModel(
                id=joint_id,
                name=joint_id.replace("_", " ").title(),
                position=position,
                parent_id=None  # Will be set based on connections
            )
            joints[joint_id] = joint
            
        # Build hierarchy from connections
        for parent_id, child_id in bone_connections:
            if parent_id in joints and child_id in joints:
                joints[child_id].parent_id = parent_id
                
                if parent_id not in hierarchy:
                    hierarchy[parent_id] = []
                hierarchy[parent_id].append(child_id)
                
        # Find root joints
        root_joint_ids = [
            joint_id for joint_id, joint in joints.items()
            if joint.parent_id is None
        ]
        
        return StandardizedSkeletonModel(
            joints=joints,
            root_joint_ids=root_joint_ids,
            hierarchy=hierarchy,
            source_format="custom",
            metadata={
                "skeleton_type": skeleton_type.value,
                "extraction_method": "user_defined"
            }
        )