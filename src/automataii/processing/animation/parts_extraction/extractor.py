"""Main body parts extractor class."""

from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import time
import numpy as np

from .models import (
    CharacterData, ExtractionResult, PartInfo, AnimationInfo
)
from .file_io import FileIO
from .joint_mapper import JointMapper
from .preprocessing import ImagePreprocessor
from .segmentation import SkeletonSegmenter
from .part_extractor import PartExtractor
from .visualization import Visualizer
from .animation_handler import AnimationHandler
from ..part_definitions import BODY_PARTS


class BodyPartsExtractor:
    """Main class for extracting body parts from character images."""

    def __init__(
        self,
        char_dir: str,
        output_dir: Optional[str] = None,
        generate_animations: bool = False,
        num_frames: int = 30,
        fps: int = 24,
    ):
        """Initialize body parts extractor.

        Args:
            char_dir: Character directory path
            output_dir: Output directory path
            generate_animations: Whether to generate animations
            num_frames: Number of animation frames
            fps: Animation frames per second
        """
        self.char_dir = Path(char_dir)
        self.output_dir = Path(output_dir) if output_dir else self.char_dir / "parts"
        self.generate_animations = generate_animations
        self.num_frames = num_frames
        self.fps = fps

        # Ensure output directory exists
        FileIO.ensure_directory(self.output_dir)

    def process(self) -> Optional[ExtractionResult]:
        """Process character and extract body parts.

        Returns:
            ExtractionResult or None if processing failed
        """
        # Load character data
        print(f"Loading character data from {self.char_dir}")
        char_data = FileIO.load_character_data(self.char_dir)
        if not char_data:
            print("Failed to load character data")
            return None

        config = char_data["config"]
        texture = char_data["texture"]
        mask = char_data["mask"]

        # Create joint map
        print("Creating joint map")
        joint_map = self._create_joint_map(config)
        if not joint_map:
            print("No joints found in configuration")
            return None

        # Segment body parts
        print("Segmenting body parts")
        start_time = time.time()
        part_masks = self._segment_body_parts(mask, joint_map)
        print(f"Segmentation took {time.time() - start_time:.2f} seconds")

        if not part_masks:
            print("No body parts segmented")
            return None

        # Extract character information
        character = self._create_character_data(config)

        # Extract individual parts
        print("Extracting individual body parts")
        part_extractor = PartExtractor(texture, joint_map)
        part_images = {}

        for part_name, part_mask in part_masks.items():
            part_info = part_extractor.extract_part(
                part_name, part_mask, self.output_dir
            )
            if part_info:
                character.parts[part_name] = part_info

                # Load part image for animation
                if self.generate_animations:
                    part_image = FileIO.read_image(Path(part_info.image_path))
                    if part_image is not None:
                        part_images[part_name] = part_image

        # Generate animations if requested
        if self.generate_animations and part_images:
            print("Generating animations")
            animation_handler = AnimationHandler(
                part_extractor, self.num_frames, self.fps
            )
            animations = animation_handler.generate_animations(
                character.parts, part_images, self.output_dir
            )
            character.animations = animations

        # Create visualizations
        print("Creating visualizations")
        visualizer = Visualizer(self.output_dir)

        segmentation_path = visualizer.create_segmentation_visualization(
            mask, part_masks, joint_map
        )

        animation_paths = {
            name: info.animation_path
            for name, info in character.animations.items()
        } if character.animations else None

        visualizer.create_html_viewer(
            character, self.char_dir, segmentation_path, animation_paths
        )

        # Extract skeleton joints
        character.skeleton_joints = JointMapper.extract_joints_from_config(config)

        # Create result
        result = ExtractionResult(
            character=character,
            part_masks=part_masks,
            joint_map=joint_map
        )

        # Save result
        print("Saving results")
        FileIO.save_extraction_result(
            result, self.output_dir / "parts_info.json"
        )

        print(f"Processing complete. Results saved to {self.output_dir}")
        return result

    def _create_joint_map(self, config: Dict[str, Any]) -> Dict[str, Tuple[int, int]]:
        """Create joint map from configuration.

        Args:
            config: Character configuration

        Returns:
            Joint map dictionary
        """
        # Try different possible keys for skeleton data
        skeleton_data = config.get("skeleton")
        if not skeleton_data and "joints" in config:
            skeleton_data = config

        if skeleton_data:
            return JointMapper.create_joint_map(skeleton_data)

        return {}

    def _segment_body_parts(
        self,
        mask: Any,
        joint_map: Dict[str, Tuple[int, int]]
    ) -> Dict[str, Any]:
        """Segment body parts using skeleton-driven approach.

        Args:
            mask: Character mask
            joint_map: Joint positions

        Returns:
            Dictionary of part masks
        """
        # Calculate scale factor
        preprocessor = ImagePreprocessor()
        scale_factor = preprocessor.calculate_scale_factor(mask.shape)

        # Create segmenter
        segmenter = SkeletonSegmenter(
            mask, joint_map, BODY_PARTS, scale_factor
        )

        # Perform segmentation
        part_masks = segmenter.segment()

        # Ensure all expected parts have masks
        for part_name in BODY_PARTS:
            if part_name not in part_masks:
                part_masks[part_name] = np.zeros_like(mask)

        return part_masks

    def _create_character_data(self, config: Dict[str, Any]) -> CharacterData:
        """Create CharacterData from configuration.

        Args:
            config: Character configuration

        Returns:
            CharacterData object
        """
        return CharacterData(
            name=config.get("name", self.char_dir.name),
            width=int(config.get("width", 0)),
            height=int(config.get("height", 0))
        )