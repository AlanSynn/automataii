"""Individual body part extraction logic."""

from typing import Tuple, Optional, Dict, Any
import cv2
import numpy as np
from pathlib import Path

from .models import PartInfo
from .preprocessing import ImagePreprocessor
from .joint_mapper import JointMapper
from ..part_definitions import BODY_PARTS


class PartExtractor:
    """Handles extraction of individual body parts from segmented masks."""
    
    def __init__(self, texture: np.ndarray, joint_map: Dict[str, Tuple[int, int]]):
        """Initialize part extractor.
        
        Args:
            texture: Full character texture image
            joint_map: Dictionary mapping joint names to positions
        """
        self.texture = texture
        self.joint_map = joint_map
        self.preprocessor = ImagePreprocessor()
        
    def extract_part(
        self, 
        part_name: str, 
        part_mask: np.ndarray,
        output_dir: Path
    ) -> Optional[PartInfo]:
        """Extract a single body part.
        
        Args:
            part_name: Name of the body part
            part_mask: Binary mask for the part
            output_dir: Directory to save extracted part
            
        Returns:
            PartInfo object or None if extraction failed
        """
        # Extract bounding box and image
        extraction_result = self._extract_part_image(part_mask)
        if extraction_result is None:
            return None
            
        part_texture, alpha_channel, bbox = extraction_result
        roi_x, roi_y, roi_w, roi_h = bbox
        
        # Save part image
        png_path = output_dir / f"{part_name}.png"
        self._save_part_image(part_texture, alpha_channel, png_path)
        
        # Calculate pivot point
        part_def = BODY_PARTS.get(part_name, {})
        local_pivot = self._calculate_local_pivot(
            part_name, part_def, bbox
        )
        
        # Create PartInfo
        return PartInfo(
            name=part_name,
            roi=(float(roi_x), float(roi_y), float(roi_w), float(roi_h)),
            image_path=str(png_path),
            fill_color=part_def.get(
                "color", 
                f"rgba(128,128,128,0.5)"
            ),
            local_pivot_offset=local_pivot,
            z_value=float(part_def.get("z_value", 0.0)),
            fixed=bool(part_def.get("fixed", False)),
            anchor_joint_id=part_def.get("anchor_joint")
        )
    
    def _extract_part_image(
        self, part_mask: np.ndarray
    ) -> Optional[Tuple[np.ndarray, np.ndarray, Tuple[int, int, int, int]]]:
        """Extract part image from full texture using mask.
        
        Args:
            part_mask: Binary mask for the part
            
        Returns:
            Tuple of (part_texture, alpha_channel, bbox) or None
        """
        if part_mask is None or np.sum(part_mask) == 0:
            return None
            
        if part_mask.dtype != np.uint8:
            part_mask = part_mask.astype(np.uint8)
            
        # Get bounding box
        bbox = self.preprocessor.extract_bounding_box(part_mask)
        if bbox is None:
            return None
            
        x, y, w, h = bbox
        
        # Extract part texture and alpha
        part_texture_cropped = self.texture[y:y + h, x:x + w]
        alpha_channel_cropped = part_mask[y:y + h, x:x + w]
        alpha_channel_cropped = np.where(
            alpha_channel_cropped > 0, 255, 0
        ).astype(np.uint8)
        
        return part_texture_cropped, alpha_channel_cropped, bbox
    
    def _save_part_image(
        self, 
        part_texture: np.ndarray, 
        alpha_channel: np.ndarray,
        output_path: Path
    ):
        """Save part image as RGBA PNG.
        
        Args:
            part_texture: Part texture image
            alpha_channel: Alpha channel for the part
            output_path: Path to save the image
        """
        # Convert to RGBA
        bgra_image = self.preprocessor.prepare_rgba_image(
            part_texture, alpha_channel
        )
        
        # Save
        cv2.imwrite(str(output_path), bgra_image)
    
    def _calculate_local_pivot(
        self,
        part_name: str,
        part_def: Dict[str, Any],
        bbox: Tuple[int, int, int, int]
    ) -> Tuple[float, float]:
        """Calculate local pivot point for the part.
        
        Args:
            part_name: Name of the body part
            part_def: Part definition from BODY_PARTS
            bbox: Bounding box (x, y, width, height)
            
        Returns:
            Local pivot offset (x, y) within the part
        """
        roi_x, roi_y, roi_w, roi_h = bbox
        
        # Default pivot at center
        local_pivot_x = float(roi_w / 2)
        local_pivot_y = float(roi_h / 2)
        
        # Use anchor joint if available
        anchor_joint_id = part_def.get("anchor_joint")
        if anchor_joint_id and self.joint_map:
            # Find anchor joint
            anchor_joint_name = JointMapper.find_joint_by_prefix(
                self.joint_map, anchor_joint_id
            )
            
            if anchor_joint_name:
                anchor_x, anchor_y = self.joint_map[anchor_joint_name]
                local_pivot_x = float(anchor_x - roi_x)
                local_pivot_y = float(anchor_y - roi_y)
                
        return (local_pivot_x, local_pivot_y)
    
    def get_proximal_joint_position(
        self,
        part_name: str,
        part_def: Dict[str, Any]
    ) -> Optional[Tuple[int, int]]:
        """Get the proximal joint position for animation.
        
        Args:
            part_name: Name of the body part
            part_def: Part definition
            
        Returns:
            Joint position (x, y) or None
        """
        if part_name == "head":
            joint_name = "neck"
        elif part_name == "torso":
            return None
        else:
            joints = part_def.get("joints")
            if not joints or not isinstance(joints, list) or len(joints) == 0:
                return None
            joint_name = joints[0]
            
        # Find joint in map
        proximal_joint = JointMapper.find_joint_by_prefix(
            self.joint_map, joint_name
        )
        
        if proximal_joint:
            return self.joint_map[proximal_joint]
            
        return None