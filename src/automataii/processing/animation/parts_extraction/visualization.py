"""Visualization utilities for body parts extraction."""

from typing import Dict, Tuple, Optional, List
import cv2
import numpy as np
from pathlib import Path

from .models import PartInfo, CharacterData
from ..templates import HTML_VIEWER_TEMPLATE, PART_CARD_TEMPLATE


class Visualizer:
    """Handles visualization of segmentation results."""
    
    # Color mapping for different body parts
    PART_COLORS = {
        "head": (255, 0, 0),
        "torso": (0, 255, 0),
        "left_arm_upper": (0, 0, 255),
        "left_arm_lower": (255, 255, 0),
        "right_arm_upper": (255, 0, 255),
        "right_arm_lower": (0, 255, 255),
        "left_leg_upper": (128, 0, 0),
        "left_leg_lower": (0, 128, 0),
        "right_leg_upper": (0, 0, 128),
        "right_leg_lower": (128, 128, 0),
    }
    
    def __init__(self, output_dir: Path):
        """Initialize visualizer.
        
        Args:
            output_dir: Directory to save visualizations
        """
        self.output_dir = Path(output_dir)
        
    def create_segmentation_visualization(
        self,
        mask: np.ndarray,
        part_masks: Dict[str, np.ndarray],
        joint_map: Dict[str, Tuple[int, int]]
    ) -> str:
        """Create visualization of segmentation results.
        
        Args:
            mask: Original character mask
            part_masks: Dictionary of part masks
            joint_map: Dictionary of joint positions
            
        Returns:
            Path to saved visualization
        """
        height, width = mask.shape
        vis_image = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Draw each part with its color
        for part_name, part_mask in part_masks.items():
            if part_name in self.PART_COLORS:
                color = self.PART_COLORS[part_name]
                colored_mask = np.zeros((height, width, 3), dtype=np.uint8)
                colored_mask[part_mask > 0] = color
                vis_image = cv2.addWeighted(vis_image, 1.0, colored_mask, 0.5, 0)
                
        # Draw joints
        for joint_name, joint_pos in joint_map.items():
            cv2.circle(vis_image, joint_pos, 5, (255, 255, 255), -1)
            cv2.putText(
                vis_image,
                joint_name,
                (joint_pos[0] + 5, joint_pos[1] - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )
            
        # Save visualization
        output_path = self.output_dir / "segmentation_vis.png"
        cv2.imwrite(str(output_path), vis_image)
        
        return str(output_path)
    
    def create_html_viewer(
        self,
        character_data: CharacterData,
        char_dir: Path,
        segmentation_path: str,
        animations: Optional[Dict[str, str]] = None
    ):
        """Create HTML viewer for results.
        
        Args:
            character_data: Character data with parts
            char_dir: Original character directory
            segmentation_path: Path to segmentation visualization
            animations: Optional dictionary of animation paths
        """
        # Generate part cards
        part_cards = self._generate_part_cards(character_data.parts, animations)
        
        # Get relative paths
        texture_path = Path(char_dir) / "image.png"
        texture_rel_path = texture_path.relative_to(self.output_dir.parent)
        segmentation_rel_path = Path(segmentation_path).name
        
        # Generate HTML
        html_content = HTML_VIEWER_TEMPLATE.format(
            texture_path=str(texture_rel_path),
            segmentation_path=segmentation_rel_path,
            part_cards=part_cards,
        )
        
        # Save HTML
        html_output_path = self.output_dir / "viewer.html"
        with open(html_output_path, "w") as f:
            f.write(html_content)
            
    def _generate_part_cards(
        self,
        parts: Dict[str, PartInfo],
        animations: Optional[Dict[str, str]] = None
    ) -> str:
        """Generate HTML cards for body parts.
        
        Args:
            parts: Dictionary of PartInfo objects
            animations: Optional dictionary of animation paths
            
        Returns:
            HTML string for part cards
        """
        part_cards = ""
        
        for part_name, part_info in parts.items():
            image_path = Path(part_info.image_path).name
            svg_path = ""  # SVG generation not implemented yet
            
            animation_element = ""
            if animations and part_name in animations:
                animation_path = Path(animations[part_name]).name
                animation_element = (
                    f'<div class="animation-container">'
                    f'<h4>Animation</h4>'
                    f'<img src="{animation_path}" alt="{part_name} Animation" '
                    f'class="part-animation">'
                    f'</div>'
                )
                
            part_card = PART_CARD_TEMPLATE.format(
                part_name=part_name.replace("_", " ").title(),
                image_path=image_path,
                svg_path=svg_path,
                animation_element=animation_element,
            )
            part_cards += part_card
            
        return part_cards
    
    @staticmethod
    def draw_skeleton(
        image: np.ndarray,
        joint_map: Dict[str, Tuple[int, int]],
        connections: Optional[List[Tuple[str, str]]] = None
    ) -> np.ndarray:
        """Draw skeleton on image.
        
        Args:
            image: Image to draw on
            joint_map: Dictionary of joint positions
            connections: Optional list of joint connections
            
        Returns:
            Image with skeleton drawn
        """
        result = image.copy()
        
        # Draw joints
        for joint_name, (x, y) in joint_map.items():
            cv2.circle(result, (x, y), 3, (0, 255, 0), -1)
            
        # Draw connections if provided
        if connections:
            for joint1, joint2 in connections:
                if joint1 in joint_map and joint2 in joint_map:
                    pt1 = joint_map[joint1]
                    pt2 = joint_map[joint2]
                    cv2.line(result, pt1, pt2, (0, 255, 0), 2)
                    
        return result