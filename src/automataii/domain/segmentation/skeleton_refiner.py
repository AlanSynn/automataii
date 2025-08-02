"""
Skeleton-guided refinement for ML segmentation results.
Maps ML-detected regions to anatomically correct body parts using skeleton data.
"""

import logging
from typing import Dict, List, Tuple

import numpy as np
from scipy.spatial.distance import cdist

logger = logging.getLogger(__name__)


class SkeletonGuidedRefiner:
    """
    Assigns ML-detected parts to skeleton bones using anatomical knowledge.
    Implements the skeleton-guided assignment strategy from Gemini consultation.
    """
    
    def __init__(self):
        # Anatomical mapping from skeleton joints to body parts
        self.joint_to_part_mapping = {
            # Head region
            "head": "head",
            "head_top": "head", 
            "neck": "head",
            
            # Torso region
            "pelvis": "torso",
            "torso": "torso",
            "spine_base": "torso",
            "spine_top": "torso",
            
            # Arms
            "left_shoulder": "left_arm_upper",
            "left_elbow": "left_arm_upper", 
            "right_shoulder": "right_arm_upper",
            "right_elbow": "right_arm_upper",
            
            "left_wrist": "left_arm_lower",
            "left_hand": "left_arm_lower",
            "right_wrist": "right_arm_lower", 
            "right_hand": "right_arm_lower",
            
            # Legs
            "left_hip": "left_leg_upper",
            "left_knee": "left_leg_upper",
            "right_hip": "right_leg_upper", 
            "right_knee": "right_leg_upper",
            
            "left_ankle": "left_leg_lower",
            "left_foot": "left_leg_lower",
            "right_ankle": "right_leg_lower",
            "right_foot": "right_leg_lower",
        }
        
        # Expected part topology for validation
        self.part_adjacency = {
            "head": ["torso"],
            "torso": ["head", "left_arm_upper", "right_arm_upper", "left_leg_upper", "right_leg_upper"],
            "left_arm_upper": ["torso", "left_arm_lower"],
            "left_arm_lower": ["left_arm_upper"],
            "right_arm_upper": ["torso", "right_arm_lower"],
            "right_arm_lower": ["right_arm_upper"], 
            "left_leg_upper": ["torso", "left_leg_lower"],
            "left_leg_lower": ["left_leg_upper"],
            "right_leg_upper": ["torso", "right_leg_lower"],
            "right_leg_lower": ["right_leg_upper"],
        }
    
    def assign_to_skeleton(
        self, 
        raw_masks: List[np.ndarray], 
        skeleton_data: dict
    ) -> Dict[str, np.ndarray]:
        """
        Assign ML-detected masks to anatomical body parts using skeleton guidance.
        
        Args:
            raw_masks: List of binary masks from ML segmentation
            skeleton_data: Dictionary with joint positions and hierarchy
            
        Returns:
            Dictionary mapping anatomical part names to masks
        """
        if not raw_masks or not skeleton_data.get("joints"):
            logger.warning("No masks or skeleton data provided")
            return {}
            
        # Extract joint positions
        joint_positions = self._extract_joint_positions(skeleton_data)
        if not joint_positions:
            logger.warning("No valid joint positions found")
            return {}
        
        # Calculate mask centroids and properties
        mask_properties = []
        for i, mask in enumerate(raw_masks):
            if np.sum(mask) == 0:
                continue
                
            centroid = self._get_mask_centroid(mask)
            area = np.sum(mask)
            bbox = self._get_mask_bbox(mask)
            
            mask_properties.append({
                "index": i,
                "mask": mask,
                "centroid": centroid,
                "area": area,
                "bbox": bbox
            })
        
        if not mask_properties:
            logger.warning("No valid masks found")
            return {}
        
        # Assign masks to body parts using skeleton guidance
        part_assignments = self._assign_masks_to_parts(mask_properties, joint_positions)
        
        # Validate and refine assignments
        refined_assignments = self._refine_assignments(part_assignments, joint_positions)
        
        return refined_assignments
    
    def _extract_joint_positions(self, skeleton_data: dict) -> Dict[str, Tuple[float, float]]:
        """Extract joint positions from skeleton data."""
        joint_positions = {}
        
        joints = skeleton_data.get("joints", {})
        for joint_id, joint_data in joints.items():
            if isinstance(joint_data, dict) and "position" in joint_data:
                pos = joint_data["position"]
                if len(pos) >= 2:
                    joint_positions[joint_id] = (float(pos[0]), float(pos[1]))
        
        return joint_positions
    
    def _get_mask_centroid(self, mask: np.ndarray) -> Tuple[float, float]:
        """Calculate centroid of binary mask."""
        y_coords, x_coords = np.where(mask > 0)
        if len(y_coords) == 0:
            return (0.0, 0.0)
        
        centroid_x = float(np.mean(x_coords))
        centroid_y = float(np.mean(y_coords))
        return (centroid_x, centroid_y)
    
    def _get_mask_bbox(self, mask: np.ndarray) -> Tuple[int, int, int, int]:
        """Get bounding box of mask as (x1, y1, x2, y2)."""
        y_coords, x_coords = np.where(mask > 0)
        if len(y_coords) == 0:
            return (0, 0, 0, 0)
        
        return (
            int(np.min(x_coords)),
            int(np.min(y_coords)), 
            int(np.max(x_coords)),
            int(np.max(y_coords))
        )
    
    def _assign_masks_to_parts(
        self, 
        mask_properties: List[dict], 
        joint_positions: Dict[str, Tuple[float, float]]
    ) -> Dict[str, np.ndarray]:
        """Assign masks to body parts using distance to relevant joints."""
        part_assignments = {}
        used_mask_indices = set()
        
        # Group joints by body part
        parts_to_joints = {}
        for joint_id, part_name in self.joint_to_part_mapping.items():
            if joint_id in joint_positions:
                if part_name not in parts_to_joints:
                    parts_to_joints[part_name] = []
                parts_to_joints[part_name].append(joint_positions[joint_id])
        
        # For each body part, find the best matching mask
        for part_name, joint_coords in parts_to_joints.items():
            if not joint_coords:
                continue
                
            # Calculate average position of joints for this part
            avg_x = sum(coord[0] for coord in joint_coords) / len(joint_coords)
            avg_y = sum(coord[1] for coord in joint_coords) / len(joint_coords)
            part_center = (avg_x, avg_y)
            
            # Find closest mask that hasn't been used
            best_mask_idx = None
            best_distance = float('inf')
            
            for prop in mask_properties:
                mask_idx = prop["index"]
                if mask_idx in used_mask_indices:
                    continue
                
                # Calculate distance from mask centroid to part center
                centroid = prop["centroid"]
                distance = np.sqrt((centroid[0] - part_center[0])**2 + 
                                 (centroid[1] - part_center[1])**2)
                
                # Apply size penalty for very small or very large masks
                area_penalty = self._calculate_area_penalty(prop["area"], part_name)
                adjusted_distance = distance * area_penalty
                
                if adjusted_distance < best_distance:
                    best_distance = adjusted_distance
                    best_mask_idx = mask_idx
            
            # Assign best mask to this part
            if best_mask_idx is not None:
                mask_prop = next(p for p in mask_properties if p["index"] == best_mask_idx)
                part_assignments[part_name] = mask_prop["mask"]
                used_mask_indices.add(best_mask_idx)
                logger.debug(f"Assigned mask {best_mask_idx} to {part_name} (distance: {best_distance:.1f})")
        
        return part_assignments
    
    def _calculate_area_penalty(self, area: int, part_name: str) -> float:
        """Calculate penalty based on mask area relative to expected part size."""
        # Expected relative sizes (these are rough estimates)
        expected_sizes = {
            "head": 0.15,
            "torso": 0.35,
            "left_arm_upper": 0.08,
            "left_arm_lower": 0.06,
            "right_arm_upper": 0.08,
            "right_arm_lower": 0.06,
            "left_leg_upper": 0.12,
            "left_leg_lower": 0.10,
            "right_leg_upper": 0.12,
            "right_leg_lower": 0.10,
        }
        
        expected_ratio = expected_sizes.get(part_name, 0.1)
        
        # Assume total character area is roughly 10000 pixels (this varies by image)
        expected_area = expected_ratio * 10000
        
        # Calculate penalty - 1.0 for perfect size, higher for deviations
        if area == 0:
            return 10.0
        
        size_ratio = expected_area / area
        if size_ratio > 1:
            # Mask is smaller than expected
            penalty = 1.0 + (size_ratio - 1) * 0.5
        else:
            # Mask is larger than expected  
            penalty = 1.0 + (1 / size_ratio - 1) * 0.3
        
        return min(penalty, 5.0)  # Cap penalty at 5x
    
    def _refine_assignments(
        self, 
        initial_assignments: Dict[str, np.ndarray],
        joint_positions: Dict[str, Tuple[float, float]]
    ) -> Dict[str, np.ndarray]:
        """Refine assignments using topological constraints."""
        refined = initial_assignments.copy()
        
        # Check for missing critical parts and try to recover
        missing_parts = []
        for part_name in ["head", "torso"]:
            if part_name not in refined:
                missing_parts.append(part_name)
        
        if missing_parts:
            logger.warning(f"Missing critical parts: {missing_parts}")
            # Could implement recovery strategies here
        
        # Validate topological consistency
        for part_name, adjacent_parts in self.part_adjacency.items():
            if part_name not in refined:
                continue
                
            # Check if adjacent parts are spatially reasonable
            part_mask = refined[part_name]
            part_centroid = self._get_mask_centroid(part_mask)
            
            for adjacent_part in adjacent_parts:
                if adjacent_part not in refined:
                    continue
                    
                adjacent_mask = refined[adjacent_part]
                adjacent_centroid = self._get_mask_centroid(adjacent_mask)
                
                distance = np.sqrt(
                    (part_centroid[0] - adjacent_centroid[0])**2 + 
                    (part_centroid[1] - adjacent_centroid[1])**2
                )
                
                # Flag if parts are too far apart (could indicate misassignment)
                if distance > 200:  # Threshold in pixels
                    logger.debug(f"Parts {part_name} and {adjacent_part} are far apart ({distance:.1f}px)")
        
        return refined