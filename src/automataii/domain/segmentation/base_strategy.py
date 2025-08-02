"""
Base strategy pattern for character segmentation approaches.
Implements the Strategic pattern recommended by Gemini consultation.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class BaseSegmentationStrategy(ABC):
    """Abstract base class for character segmentation strategies."""
    
    def __init__(self, name: str):
        self.name = name
        self.confidence_threshold = 0.5
        self.min_part_size = 100  # Minimum pixels for a valid part
    
    @abstractmethod
    def segment(
        self, 
        image: np.ndarray, 
        mask: np.ndarray, 
        skeleton_data: dict
    ) -> Dict[str, np.ndarray]:
        """
        Segment character into body parts.
        
        Args:
            image: Input image as numpy array (H, W, 3)
            mask: Character mask as numpy array (H, W)
            skeleton_data: Skeleton joint positions and hierarchy
            
        Returns:
            Dictionary mapping part names to their segmentation masks
        """
        pass
    
    @abstractmethod
    def get_confidence_scores(self) -> Dict[str, float]:
        """
        Get confidence scores for the last segmentation.
        
        Returns:
            Dictionary mapping part names to confidence scores (0.0-1.0)
        """
        pass
    
    def validate_segmentation(
        self, 
        segmentation_masks: Dict[str, np.ndarray],
        skeleton_data: dict
    ) -> Tuple[bool, Dict[str, str]]:
        """
        Validate segmentation quality and provide diagnostic information.
        
        Args:
            segmentation_masks: Part name to mask mapping
            skeleton_data: Skeleton data for validation
            
        Returns:
            Tuple of (is_valid, validation_messages)
        """
        is_valid = True
        messages = {}
        
        # Check if we have the minimum expected parts
        expected_parts = {"head", "torso", "left_arm_upper", "left_arm_lower", 
                         "right_arm_upper", "right_arm_lower", "left_leg_upper", 
                         "left_leg_lower", "right_leg_upper", "right_leg_lower"}
        
        found_parts = set(segmentation_masks.keys())
        missing_parts = expected_parts - found_parts
        
        if missing_parts:
            is_valid = False
            messages["missing_parts"] = f"Missing parts: {missing_parts}"
        
        # Check part sizes
        for part_name, mask in segmentation_masks.items():
            part_size = np.sum(mask > 0)
            if part_size < self.min_part_size:
                is_valid = False
                messages[f"{part_name}_too_small"] = f"Part {part_name} only has {part_size} pixels"
        
        # Check for overlap between parts
        total_mask = np.zeros_like(list(segmentation_masks.values())[0])
        for part_name, mask in segmentation_masks.items():
            overlap = np.sum((total_mask > 0) & (mask > 0))
            if overlap > 0:
                messages[f"{part_name}_overlap"] = f"Part {part_name} overlaps with other parts ({overlap} pixels)"
            total_mask += mask
        
        return is_valid, messages
    
    def set_parameters(self, **kwargs):
        """Set strategy-specific parameters."""
        if "confidence_threshold" in kwargs:
            self.confidence_threshold = kwargs["confidence_threshold"]
        if "min_part_size" in kwargs:
            self.min_part_size = kwargs["min_part_size"]


class SegmentationResult:
    """Container for segmentation results with metadata."""
    
    def __init__(
        self, 
        masks: Dict[str, np.ndarray],
        confidence_scores: Dict[str, float],
        strategy_name: str,
        processing_time: float = 0.0,
        validation_result: Optional[Tuple[bool, Dict[str, str]]] = None
    ):
        self.masks = masks
        self.confidence_scores = confidence_scores
        self.strategy_name = strategy_name
        self.processing_time = processing_time
        self.validation_result = validation_result
        
    @property
    def is_valid(self) -> bool:
        """Check if segmentation passed validation."""
        return self.validation_result is not None and self.validation_result[0]
    
    @property
    def part_count(self) -> int:
        """Get number of segmented parts."""
        return len(self.masks)
    
    @property
    def average_confidence(self) -> float:
        """Get average confidence score across all parts."""
        if not self.confidence_scores:
            return 0.0
        return sum(self.confidence_scores.values()) / len(self.confidence_scores)