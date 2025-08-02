"""
Hybrid ML strategy combining CharSegNet with skeleton-guided refinement.
Implements the strategic approach recommended by Gemini consultation.
"""

import logging
import time
from typing import Dict, List, Optional

import numpy as np

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

from .base_strategy import BaseSegmentationStrategy, SegmentationResult
from .skeleton_refiner import SkeletonGuidedRefiner

if TORCH_AVAILABLE:
    try:
        from .model import CharSegNet
        MODEL_AVAILABLE = True
    except ImportError:
        CharSegNet = None
        MODEL_AVAILABLE = False
else:
    CharSegNet = None
    MODEL_AVAILABLE = False

logger = logging.getLogger(__name__)


class HybridMLStrategy(BaseSegmentationStrategy):
    """
    Advanced segmentation strategy using ML model with skeleton guidance.
    
    Combines the existing CharSegNet model with anatomical knowledge
    from skeleton data to produce robust, pose-invariant segmentation.
    """
    
    def __init__(
        self, 
        model_config: Optional[Dict] = None,
        use_skeleton_refinement: bool = True
    ):
        super().__init__("HybridML")
        
        self.model_config = model_config or {}
        self.use_skeleton_refinement = use_skeleton_refinement
        
        # Check for torch availability
        if not TORCH_AVAILABLE:
            logger.warning("PyTorch not available. HybridMLStrategy will use fallback segmentation only.")
            
        # Initialize components
        self.model: Optional = None
        self.skeleton_refiner = SkeletonGuidedRefiner() if use_skeleton_refinement else None
        self.device = torch.device("cuda" if TORCH_AVAILABLE and torch.cuda.is_available() else "cpu") if TORCH_AVAILABLE else None
        
        # Last segmentation metadata
        self._last_confidence_scores = {}
        self._last_processing_time = 0.0
        
        # Model loading is deferred until first use
        self._model_initialized = False
        
    def _initialize_model(self):
        """Initialize the CharSegNet model lazily."""
        if self._model_initialized:
            return
            
        if not TORCH_AVAILABLE or not MODEL_AVAILABLE:
            logger.warning("PyTorch or CharSegNet model not available. Skipping model initialization.")
            self.model = None
            self._model_initialized = True
            return
            
        try:
            sam_model_type = self.model_config.get("sam_model_type", "vit_h")
            sam_checkpoint = self.model_config.get("sam_checkpoint")
            freeze_encoder = self.model_config.get("freeze_encoder", False)
            
            logger.info(f"Initializing CharSegNet with {sam_model_type}")
            self.model = CharSegNet(
                sam_model_type=sam_model_type,
                sam_checkpoint=sam_checkpoint,
                freeze_encoder=freeze_encoder
            )
            
            self.model.to(self.device)
            self.model.eval()
            
            logger.info(f"CharSegNet initialized successfully on {self.device}")
            self._model_initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize CharSegNet: {e}")
            # Fall back to basic segmentation
            self.model = None
            self._model_initialized = True
    
    def segment(
        self, 
        image: np.ndarray, 
        mask: np.ndarray, 
        skeleton_data: dict
    ) -> Dict[str, np.ndarray]:
        """
        Perform hybrid ML + skeleton-guided segmentation.
        
        Args:
            image: Input image as numpy array (H, W, 3)
            mask: Character mask as numpy array (H, W) 
            skeleton_data: Skeleton joint positions and hierarchy
            
        Returns:
            Dictionary mapping part names to their segmentation masks
        """
        start_time = time.time()
        
        try:
            # Initialize model if needed
            self._initialize_model()
            
            if self.model is None:
                logger.warning("Model not available, falling back to basic segmentation")
                return self._fallback_segmentation(image, mask, skeleton_data)
            
            # Perform ML segmentation
            raw_masks = self._ml_segment(image, mask)
            
            if not raw_masks:
                logger.warning("ML segmentation failed, falling back to basic approach")
                return self._fallback_segmentation(image, mask, skeleton_data)
            
            # Apply skeleton-guided refinement
            if self.skeleton_refiner and skeleton_data:
                refined_masks = self.skeleton_refiner.assign_to_skeleton(
                    raw_masks, skeleton_data
                )
            else:
                # Convert raw masks to part assignments without skeleton guidance
                refined_masks = self._assign_without_skeleton(raw_masks)
            
            # Validate and clean up results
            final_masks = self._post_process_masks(refined_masks, mask)
            
            self._last_processing_time = time.time() - start_time
            logger.info(f"Hybrid segmentation completed in {self._last_processing_time:.2f}s, found {len(final_masks)} parts")
            
            return final_masks
            
        except Exception as e:
            logger.error(f"Hybrid segmentation failed: {e}")
            self._last_processing_time = time.time() - start_time
            return self._fallback_segmentation(image, mask, skeleton_data)
    
    def _ml_segment(self, image: np.ndarray, mask: np.ndarray) -> List[np.ndarray]:
        """Perform ML-based segmentation using CharSegNet."""
        try:
            # Prepare input tensor
            image_tensor = self._prepare_input_tensor(image, mask)
            
            if image_tensor is None:
                return []
            
            # Run model inference
            if TORCH_AVAILABLE:
                with torch.no_grad():
                    output = self.model(image_tensor)
            else:
                return []
            
            # Extract segmentation masks from model output
            raw_masks = self._extract_masks_from_output(output, image.shape[:2])
            
            # Calculate confidence scores
            self._calculate_confidence_scores(output, raw_masks)
            
            return raw_masks
            
        except Exception as e:
            logger.error(f"ML segmentation failed: {e}")
            return []
    
    def _prepare_input_tensor(self, image: np.ndarray, mask: np.ndarray) -> Optional:
        """Convert numpy image to tensor format expected by CharSegNet."""
        if not TORCH_AVAILABLE:
            return None
            
        try:
            # Apply character mask to focus on relevant region
            masked_image = image.copy()
            if mask is not None and mask.shape[:2] == image.shape[:2]:
                # Expand mask to 3 channels
                mask_3d = np.stack([mask] * 3, axis=-1)
                masked_image = masked_image * (mask_3d > 0)
            
            # Convert to tensor format (B, C, H, W)
            image_tensor = torch.from_numpy(masked_image).permute(2, 0, 1).unsqueeze(0).float()
            image_tensor = image_tensor.to(self.device)
            
            return image_tensor
            
        except Exception as e:
            logger.error(f"Failed to prepare input tensor: {e}")
            return None
    
    def _extract_masks_from_output(
        self, 
        model_output: Dict[str, any], 
        original_size: tuple
    ) -> List[np.ndarray]:
        """Extract individual part masks from CharSegNet output."""
        masks = []
        
        try:
            if not TORCH_AVAILABLE:
                return masks
                
            # Use final logits if available, otherwise fall back to stage2
            if "final_logits" in model_output and model_output["final_logits"] is not None:
                logits = model_output["final_logits"]
            elif "stage2_logits" in model_output and model_output["stage2_logits"] is not None:
                logits = model_output["stage2_logits"]
            else:
                logger.warning("No valid logits found in model output")
                return masks
            
            # Convert logits to predictions
            predictions = torch.argmax(logits, dim=1).cpu().numpy()  # (B, H, W)
            
            # Extract unique classes (excluding background)
            unique_classes = np.unique(predictions[0])
            background_class = 0
            
            for class_id in unique_classes:
                if class_id == background_class:
                    continue
                    
                # Create binary mask for this class
                class_mask = (predictions[0] == class_id).astype(np.uint8)
                
                # Resize to original image size if needed
                if class_mask.shape != original_size:
                    import cv2
                    class_mask = cv2.resize(
                        class_mask, 
                        (original_size[1], original_size[0]), 
                        interpolation=cv2.INTER_NEAREST
                    )
                
                # Only include masks with significant area
                if np.sum(class_mask) > self.min_part_size:
                    masks.append(class_mask)
            
        except Exception as e:
            logger.error(f"Failed to extract masks from model output: {e}")
        
        return masks
    
    def _calculate_confidence_scores(
        self, 
        model_output: Dict[str, any], 
        masks: List[np.ndarray]
    ):
        """Calculate confidence scores for extracted masks."""
        self._last_confidence_scores = {}
        
        try:
            if not TORCH_AVAILABLE:
                # Assign default confidence when torch is not available
                for i in range(len(masks)):
                    self._last_confidence_scores[f"mask_{i}"] = 0.5
                return
                
            if "final_logits" in model_output and model_output["final_logits"] is not None:
                logits = model_output["final_logits"]
                probabilities = torch.softmax(logits, dim=1)
                
                # Calculate average confidence for each mask
                for i, mask in enumerate(masks):
                    if np.sum(mask) > 0:
                        # Convert mask to tensor for indexing
                        mask_tensor = torch.from_numpy(mask).bool().to(self.device)
                        
                        # Get probabilities for this mask region
                        mask_probs = probabilities[0, :, mask_tensor]
                        max_probs = torch.max(mask_probs, dim=0)[0]
                        avg_confidence = torch.mean(max_probs).item()
                        
                        self._last_confidence_scores[f"mask_{i}"] = avg_confidence
            
        except Exception as e:
            logger.debug(f"Failed to calculate confidence scores: {e}")
            # Assign default confidence
            for i in range(len(masks)):
                self._last_confidence_scores[f"mask_{i}"] = 0.5
    
    def _assign_without_skeleton(self, raw_masks: List[np.ndarray]) -> Dict[str, np.ndarray]:
        """Assign masks to parts without skeleton guidance (fallback)."""
        part_assignments = {}
        
        # Simple assignment based on mask properties
        for i, mask in enumerate(raw_masks):
            if np.sum(mask) == 0:
                continue
                
            # Estimate part type based on mask position and size
            centroid_y = np.mean(np.where(mask > 0)[0])
            mask_area = np.sum(mask)
            image_height = mask.shape[0]
            
            # Rough heuristics for part assignment
            relative_y = centroid_y / image_height
            
            if relative_y < 0.3 and mask_area > 1000:
                part_name = "head"
            elif relative_y < 0.6 and mask_area > 2000:
                part_name = "torso"
            elif mask_area > 500:
                # Assign remaining parts based on order
                limb_parts = ["left_arm_upper", "right_arm_upper", "left_leg_upper", "right_leg_upper",
                            "left_arm_lower", "right_arm_lower", "left_leg_lower", "right_leg_lower"]
                assigned_count = len([k for k in part_assignments.keys() if k in limb_parts])
                if assigned_count < len(limb_parts):
                    part_name = limb_parts[assigned_count]
                else:
                    part_name = f"part_{i}"
            else:
                continue  # Skip very small masks
            
            part_assignments[part_name] = mask
        
        return part_assignments
    
    def _post_process_masks(
        self, 
        masks: Dict[str, np.ndarray], 
        character_mask: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """Clean up and validate mask assignments."""
        processed_masks = {}
        
        for part_name, mask in masks.items():
            if mask is None or np.sum(mask) == 0:
                continue
            
            # Ensure mask is within character boundary
            if character_mask is not None:
                mask = mask * (character_mask > 0)
            
            # Remove very small regions
            if np.sum(mask) < self.min_part_size:
                logger.debug(f"Skipping {part_name} - too small ({np.sum(mask)} pixels)")
                continue
            
            # Clean up mask (remove holes, smooth edges)
            cleaned_mask = self._clean_mask(mask)
            
            if np.sum(cleaned_mask) > 0:
                processed_masks[part_name] = cleaned_mask
        
        return processed_masks
    
    def _clean_mask(self, mask: np.ndarray) -> np.ndarray:
        """Apply morphological operations to clean up mask."""
        try:
            import cv2
            
            # Remove small holes
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            cleaned = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
            
            # Remove small noise
            cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
            
            return cleaned
            
        except ImportError:
            # Fall back to basic cleaning if OpenCV not available
            return mask
    
    def _fallback_segmentation(
        self, 
        image: np.ndarray, 
        mask: np.ndarray, 
        skeleton_data: dict
    ) -> Dict[str, np.ndarray]:
        """Fallback to basic segmentation when ML approach fails."""
        logger.info("Using fallback segmentation approach")
        
        # Import and use existing FastSkeletonSegmenter as fallback
        try:
            from automataii.domain.animation.body_parts_extractor import FastSkeletonSegmenter
            from automataii.domain.animation.part_definitions import BODY_PARTS
            
            # Create joint map for FastSkeletonSegmenter
            joint_map = {}
            if skeleton_data and "joints" in skeleton_data:
                for joint_name, joint_data in skeleton_data["joints"].items():
                    if isinstance(joint_data, dict) and "position" in joint_data:
                        pos = joint_data["position"]
                        if len(pos) >= 2:
                            joint_map[joint_name] = (int(pos[0]), int(pos[1]))
            
            if joint_map and mask is not None:
                fallback_segmenter = FastSkeletonSegmenter(
                    mask=mask,
                    joint_map=joint_map,
                    part_definitions=BODY_PARTS,
                    scale_factor=0.5
                )
                result = fallback_segmenter.segment_fast()
                if result:
                    return result
            
        except Exception as e:
            logger.error(f"Fallback segmentation also failed: {e}")
        
        # Ultimate fallback - return the full character mask as torso
        if mask is not None and np.sum(mask) > 0:
            return {"torso": mask}
        
        return {}
    
    def get_confidence_scores(self) -> Dict[str, float]:
        """Get confidence scores for the last segmentation."""
        return self._last_confidence_scores.copy()
    
    def set_model_config(self, config: Dict):
        """Update model configuration (requires reinitialization)."""
        self.model_config.update(config)
        self._model_initialized = False
        self.model = None
    
    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics."""
        return {
            "last_processing_time": self._last_processing_time,
            "device": str(self.device),
            "model_initialized": self._model_initialized
        }