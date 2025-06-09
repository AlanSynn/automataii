"""Animation handling for body parts."""

from typing import Dict, Optional, Tuple
from pathlib import Path
import numpy as np

from .models import PartInfo, AnimationInfo
from .part_extractor import PartExtractor
from ..body_parts_animation import animate_body_part, save_animation
from ..part_definitions import BODY_PARTS


class AnimationHandler:
    """Handles animation generation for body parts."""
    
    def __init__(
        self,
        part_extractor: PartExtractor,
        num_frames: int = 30,
        fps: int = 24
    ):
        """Initialize animation handler.
        
        Args:
            part_extractor: PartExtractor instance
            num_frames: Number of animation frames
            fps: Frames per second
        """
        self.part_extractor = part_extractor
        self.num_frames = num_frames
        self.fps = fps
        
    def generate_animations(
        self,
        parts: Dict[str, PartInfo],
        part_images: Dict[str, np.ndarray],
        output_dir: Path
    ) -> Dict[str, AnimationInfo]:
        """Generate animations for all applicable parts.
        
        Args:
            parts: Dictionary of PartInfo objects
            part_images: Dictionary of part images
            output_dir: Directory to save animations
            
        Returns:
            Dictionary of AnimationInfo objects
        """
        animations = {}
        
        for part_name, part_info in parts.items():
            # Skip fixed parts
            if part_info.fixed:
                continue
                
            # Get animation pivot
            pivot = self._get_animation_pivot(part_name, part_info)
            if pivot is None:
                continue
                
            # Get part image
            if part_name not in part_images:
                continue
            part_image = part_images[part_name]
            
            # Generate animation
            animation_info = self._generate_part_animation(
                part_name, part_image, pivot, output_dir
            )
            
            if animation_info:
                animations[part_name] = animation_info
                
        return animations
    
    def _get_animation_pivot(
        self,
        part_name: str,
        part_info: PartInfo
    ) -> Optional[Tuple[int, int]]:
        """Get animation pivot point for a part.
        
        Args:
            part_name: Name of the body part
            part_info: PartInfo object
            
        Returns:
            Local pivot point (x, y) or None
        """
        part_def = BODY_PARTS.get(part_name, {})
        
        # Get proximal joint position
        joint_pos = self.part_extractor.get_proximal_joint_position(
            part_name, part_def
        )
        
        if joint_pos is None:
            return None
            
        # Convert to local coordinates
        roi_x, roi_y, _, _ = part_info.roi
        local_x = joint_pos[0] - int(roi_x)
        local_y = joint_pos[1] - int(roi_y)
        
        return (local_x, local_y)
    
    def _generate_part_animation(
        self,
        part_name: str,
        part_image: np.ndarray,
        pivot: Tuple[int, int],
        output_dir: Path
    ) -> Optional[AnimationInfo]:
        """Generate animation for a single part.
        
        Args:
            part_name: Name of the body part
            part_image: Part image
            pivot: Local pivot point
            output_dir: Directory to save animation
            
        Returns:
            AnimationInfo object or None
        """
        try:
            # Generate animation frames
            animation_frames = animate_body_part(
                part_image,
                pivot,
                num_frames=self.num_frames
            )
            
            # Save animation
            animation_path = output_dir / f"{part_name}_animation.gif"
            save_animation(
                animation_frames,
                str(animation_path),
                fps=self.fps
            )
            
            return AnimationInfo(
                animation_path=str(animation_path),
                num_frames=self.num_frames,
                fps=self.fps
            )
            
        except Exception as e:
            print(f"Failed to generate animation for {part_name}: {e}")
            return None