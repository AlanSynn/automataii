"""File I/O operations for body parts extraction."""

from typing import Dict, Any, Optional
from pathlib import Path
import json
import yaml
import cv2
import numpy as np

from .models import ExtractionResult


class FileIO:
    """Handles file reading and writing operations."""
    
    @staticmethod
    def read_config(config_path: Path) -> Optional[Dict[str, Any]]:
        """Read YAML configuration file.
        
        Args:
            config_path: Path to config file
            
        Returns:
            Configuration dictionary or None if failed
        """
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Failed to read config: {e}")
            return None
    
    @staticmethod
    def read_image(image_path: Path, flags: int = cv2.IMREAD_UNCHANGED) -> Optional[np.ndarray]:
        """Read image from file.
        
        Args:
            image_path: Path to image file
            flags: OpenCV imread flags
            
        Returns:
            Image array or None if failed
        """
        try:
            image = cv2.imread(str(image_path), flags)
            return image
        except Exception as e:
            print(f"Failed to read image: {e}")
            return None
    
    @staticmethod
    def save_json(data: Dict[str, Any], output_path: Path):
        """Save data as JSON file.
        
        Args:
            data: Data to save
            output_path: Path to save JSON file
        """
        with open(output_path, "w") as f:
            json.dump(data, f, indent=4)
    
    @staticmethod
    def save_extraction_result(result: ExtractionResult, output_path: Path):
        """Save extraction result to JSON file.
        
        Args:
            result: ExtractionResult object
            output_path: Path to save the result
        """
        data = result.to_dict()
        FileIO.save_json(data, output_path)
    
    @staticmethod
    def load_character_data(char_dir: Path) -> Optional[Dict[str, Any]]:
        """Load all character data from directory.
        
        Args:
            char_dir: Character directory path
            
        Returns:
            Dictionary with loaded data or None if failed
        """
        char_dir = Path(char_dir)
        
        # Check required files
        config_path = char_dir / "char_cfg.yaml"
        texture_path = char_dir / "texture.png"
        mask_path = char_dir / "mask.png"
        
        if not all(p.exists() for p in [config_path, texture_path, mask_path]):
            print(f"Missing required files in {char_dir}")
            return None
            
        # Load files
        config = FileIO.read_config(config_path)
        texture = FileIO.read_image(texture_path)
        mask = FileIO.read_image(mask_path, cv2.IMREAD_GRAYSCALE)
        
        if config is None or texture is None or mask is None:
            return None
            
        return {
            "config": config,
            "texture": texture,
            "mask": mask,
            "char_dir": char_dir
        }
    
    @staticmethod
    def ensure_directory(directory: Path) -> Path:
        """Ensure directory exists, create if needed.
        
        Args:
            directory: Directory path
            
        Returns:
            Directory path
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        return directory