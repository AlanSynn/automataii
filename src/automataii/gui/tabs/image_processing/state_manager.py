"""
State Manager for Image Processing Tab

Manages the state of the image processing workflow and provides
centralized state queries for UI updates.
"""
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from automataii.processing.vision.annotations import AnnotationResults


class ImageProcessingState:
    """Manages the state of image processing operations."""
    
    def __init__(self):
        # File paths
        self.input_image_path: Optional[str] = None
        self.character_dir: Optional[str] = None
        self.current_temp_char_dir: Optional[str] = None
        self.current_parts_info_path: Optional[str] = None
        
        # Processing results
        self.current_annotation_results: Optional[AnnotationResults] = None
        self.skeleton_data: Optional[Dict[str, Any]] = None
        
        # UI state
        self.active_camera_dialogs: list = []
        
    def reset(self):
        """Reset all state to initial values."""
        self.input_image_path = None
        self.character_dir = None
        self.current_temp_char_dir = None
        self.current_parts_info_path = None
        self.current_annotation_results = None
        self.skeleton_data = None
        self.active_camera_dialogs.clear()
        
    def has_image(self) -> bool:
        """Check if an input image is loaded."""
        return bool(self.input_image_path)
        
    def has_skeleton(self) -> bool:
        """Check if skeleton data is available."""
        return bool(self.skeleton_data)
        
    def has_annotation_results(self) -> bool:
        """Check if annotation results are available."""
        return bool(self.current_annotation_results)
        
    def has_parts_info(self) -> bool:
        """Check if parts info has been generated."""
        return bool(self.current_parts_info_path and Path(self.current_parts_info_path).exists())
        
    def can_process_image(self) -> bool:
        """Check if image processing can be performed."""
        return self.has_image()
        
    def can_edit_skeleton(self) -> bool:
        """Check if skeleton editing is possible."""
        return self.has_skeleton()
        
    def can_save_skeleton(self) -> bool:
        """Check if skeleton can be saved."""
        return self.has_skeleton()
        
    def can_generate_parts(self) -> bool:
        """Check if parts generation is possible."""
        return self.has_skeleton() and self.has_annotation_results()
        
    def update_from_image_load(self, image_path: str):
        """Update state after loading an image."""
        self.input_image_path = image_path
        self._infer_character_dir(image_path)
        
    def _infer_character_dir(self, image_path: str):
        """Infer character directory from image path."""
        import os
        
        potential_char_dir = os.path.dirname(image_path)
        
        # Check for character data indicators
        if (
            os.path.exists(os.path.join(potential_char_dir, "character_data"))
            or os.path.exists(os.path.join(potential_char_dir, "output"))
            or os.path.exists(os.path.join(potential_char_dir, "parts_info.json"))
        ):
            self.character_dir = potential_char_dir
        elif os.path.basename(potential_char_dir) in ["source_images", "input_images", "images"]:
            self.character_dir = os.path.dirname(potential_char_dir)
        else:
            self.character_dir = potential_char_dir
            
        logging.info(f"Inferred character directory: {self.character_dir}")