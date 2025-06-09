"""Body part segmentation using skeleton-driven approach."""

from typing import Dict, Any, Optional, Tuple, List
import numpy as np
import cv2
from scipy.ndimage import gaussian_filter
from scipy.spatial.distance import cdist
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache


class SkeletonSegmenter:
    """Optimized skeleton-driven body part segmentation."""
    
    def __init__(
        self,
        mask: np.ndarray,
        joint_map: Dict[str, Tuple[int, int]],
        part_definitions: Dict[str, Any],
        scale_factor: float = 0.5,
    ):
        """Initialize segmenter.
        
        Args:
            mask: Binary mask of the character
            joint_map: Dictionary mapping joint names to positions
            part_definitions: Dictionary of part definitions
            scale_factor: Scale factor for faster processing
        """
        self.mask = mask
        self.joint_map = joint_map
        self.part_definitions = part_definitions
        self.height, self.width = mask.shape
        self.scale_factor = scale_factor
        
        # Pre-compute scaled versions
        self.scaled_height = int(self.height * scale_factor)
        self.scaled_width = int(self.width * scale_factor)
        self.scaled_mask = cv2.resize(
            mask,
            (self.scaled_width, self.scaled_height),
            interpolation=cv2.INTER_NEAREST,
        )
        
        # Pre-compute coordinate grids
        self.y_grid, self.x_grid = np.mgrid[
            0:self.scaled_height, 0:self.scaled_width
        ]
        self.coords = np.column_stack([self.x_grid.ravel(), self.y_grid.ravel()])
        
        # Cache for distance computations
        self._distance_cache = {}
        
    def segment(self) -> Dict[str, np.ndarray]:
        """Perform fast segmentation using vectorized operations.
        
        Returns:
            Dictionary mapping part names to binary masks
        """
        # Create part influence maps
        influence_maps = self._create_all_influence_maps()
        
        if not influence_maps:
            return {}
            
        # Stack all influence maps
        influence_stack = np.stack(list(influence_maps.values()), axis=0)
        
        # Find maximum influence per pixel (vectorized)
        max_indices = np.argmax(influence_stack, axis=0)
        
        # Create masks
        part_masks = {}
        part_names = list(influence_maps.keys())
        
        for idx, part_name in enumerate(part_names):
            # Create binary mask at scaled resolution
            scaled_mask = (max_indices == idx).astype(np.uint8) * 255
            scaled_mask = cv2.bitwise_and(scaled_mask, self.scaled_mask)
            
            # Upscale to original resolution
            full_mask = cv2.resize(
                scaled_mask, (self.width, self.height), 
                interpolation=cv2.INTER_NEAREST
            )
            
            # Clean up
            full_mask = self._postprocess_mask(full_mask)
            full_mask = cv2.bitwise_and(full_mask, self.mask)
            
            part_masks[part_name] = full_mask
            
        return part_masks
    
    def _create_all_influence_maps(self) -> Dict[str, np.ndarray]:
        """Create all influence maps using parallel processing."""
        influence_maps = {}
        
        # Process parts in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            for part_name, part_def in self.part_definitions.items():
                future = executor.submit(
                    self._create_part_influence, part_name, part_def
                )
                futures[part_name] = future
                
            for part_name, future in futures.items():
                influence = future.result()
                if influence is not None:
                    influence_maps[part_name] = influence
                    
        return influence_maps
    
    def _create_part_influence(
        self, part_name: str, part_def: Dict[str, Any]
    ) -> Optional[np.ndarray]:
        """Create influence map for a single part."""
        joints = part_def.get("joints", [])
        if not joints:
            return None
            
        # Map joints to actual names
        mapped_joints = self._map_joints(joints)
        if not mapped_joints:
            return None
            
        # Scale joint positions
        scaled_joints = self._scale_joint_positions(mapped_joints)
        
        # Create influence map
        influence = self._compute_influence_map(scaled_joints)
        
        # Apply part-specific modulation
        influence = self._modulate_influence(influence, part_name)
        
        return influence
    
    def _map_joints(self, joints: List[str]) -> List[str]:
        """Map joint names to actual joint names in joint_map."""
        mapped_joints = []
        for joint in joints:
            if joint in self.joint_map:
                mapped_joints.append(joint)
            else:
                # Try to find by prefix
                for jname in self.joint_map:
                    if jname.startswith(joint):
                        mapped_joints.append(jname)
                        break
        return mapped_joints
    
    def _scale_joint_positions(self, joints: List[str]) -> List[Tuple[int, int]]:
        """Scale joint positions by scale factor."""
        scaled_joints = []
        for joint in joints:
            x, y = self.joint_map[joint]
            scaled_joints.append(
                (int(x * self.scale_factor), int(y * self.scale_factor))
            )
        return scaled_joints
    
    def _compute_influence_map(self, joints: List[Tuple[int, int]]) -> np.ndarray:
        """Compute influence map from joint positions."""
        influence = np.zeros((self.scaled_height, self.scaled_width), dtype=np.float32)
        
        # Bone influences (vectorized)
        for i in range(len(joints) - 1):
            bone_influence = self._create_bone_influence(joints[i], joints[i + 1])
            influence = np.maximum(influence, bone_influence)
            
        # Joint influences (vectorized)
        joint_positions = np.array(joints)
        if joint_positions.shape[0] > 0:
            # Compute distances from all pixels to all joints at once
            distances = cdist(self.coords, joint_positions, metric="euclidean")
            
            # Gaussian influence for each joint
            sigma = 30 * self.scale_factor
            joint_influences = np.exp(-(distances**2) / (2 * sigma**2))
            
            # Take maximum influence across all joints
            max_joint_influence = np.max(joint_influences, axis=1)
            max_joint_influence = max_joint_influence.reshape(
                self.scaled_height, self.scaled_width
            )
            influence = np.maximum(influence, max_joint_influence)
            
        return influence
    
    def _create_bone_influence(
        self, p1: Tuple[int, int], p2: Tuple[int, int]
    ) -> np.ndarray:
        """Create influence map for a bone (line segment)."""
        # Cache key
        cache_key = (p1, p2)
        if cache_key in self._distance_cache:
            return self._distance_cache[cache_key]
            
        # Line parameters
        p1 = np.array(p1, dtype=np.float32)
        p2 = np.array(p2, dtype=np.float32)
        line_vec = p2 - p1
        line_length = np.linalg.norm(line_vec)
        
        if line_length == 0:
            return np.zeros((self.scaled_height, self.scaled_width), dtype=np.float32)
            
        line_vec_norm = line_vec / line_length
        
        # Vectorized distance to line segment
        # Vector from p1 to each pixel
        pixel_vecs = self.coords - p1
        
        # Project onto line
        projections = np.dot(pixel_vecs, line_vec_norm)
        projections = np.clip(projections, 0, line_length)
        
        # Closest points on line
        closest_points = p1 + projections[:, np.newaxis] * line_vec_norm
        
        # Distances
        distances = np.linalg.norm(self.coords - closest_points, axis=1)
        distances = distances.reshape(self.scaled_height, self.scaled_width)
        
        # Convert to influence
        sigma = (20 + line_length * 0.1) * self.scale_factor
        influence = np.exp(-(distances**2) / (2 * sigma**2))
        
        # Cache result
        self._distance_cache[cache_key] = influence
        
        return influence
    
    def _modulate_influence(self, influence: np.ndarray, part_name: str) -> np.ndarray:
        """Apply part-specific modulation to influence map."""
        if "head" in part_name:
            # Boost upper region
            y_gradient = np.linspace(1, 0, self.scaled_height)[:, np.newaxis]
            influence *= 1 + 0.5 * y_gradient
            
        elif "torso" in part_name:
            # Slight blur and boost
            influence = gaussian_filter(influence, sigma=2)
            influence *= 1.2
            
        elif any(term in part_name for term in ["arm", "leg"]):
            # Light blur
            influence = gaussian_filter(influence, sigma=1)
            
        return influence
    
    def _postprocess_mask(self, mask: np.ndarray) -> np.ndarray:
        """Post-process mask with morphological operations."""
        # Simple morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # Fast median filter
        mask = cv2.medianBlur(mask, 3)
        
        return mask