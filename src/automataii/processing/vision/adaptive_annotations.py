"""
Adaptive annotations module that can handle different character types.
This extends the original annotations.py with support for non-human skeletons.
"""

import sys
import cv2
import json
import numpy as np
from pathlib import Path
import yaml
import logging
from typing import Optional, Dict, Any, Tuple

from automataii.processing.vision.annotations import (
    AnnotationResults, segment
)

# These functions need to be implemented or imported from the correct location
def fillhole(mask):
    """Fill holes in binary mask"""
    # TODO: Implement fillhole functionality
    return mask

def grabcut(img, mask, num_iter=5):
    """Apply GrabCut algorithm for foreground segmentation"""
    # TODO: Implement grabcut functionality
    return mask

def getLargestCC(mask):
    """Get largest connected component"""
    # TODO: Implement getLargestCC functionality
    return mask
from automataii.processing.vision.adaptive_skeleton_extractor import AdaptiveSkeletonExtractor
from automataii.core.models.skeleton_types import SkeletonType
from automataii.utils.paths import get_session_temp_dir
from automataii.utils.config import AppConfig

# Import needed modules from mmdet and mmpose
from mmdet.apis import inference_detector, init_detector
from mmpose.apis import inference_top_down_pose_model, init_pose_model


def image_to_annotations_adaptive(
    img_fn: str,
    force_skeleton_type: Optional[SkeletonType] = None,
    enable_non_human: Optional[bool] = None
) -> Optional[AnnotationResults]:
    """
    Adaptive version of image_to_annotations that can handle different character types.
    
    Args:
        img_fn: Path to RGB image
        force_skeleton_type: Force a specific skeleton type (optional)
        enable_non_human: Override the global setting for non-human skeleton support
        
    Returns:
        AnnotationResults dictionary if successful, None otherwise
    """
    logger = logging.getLogger(__name__)
    
    # Check if non-human skeleton support is enabled
    if enable_non_human is None:
        enable_non_human = getattr(AppConfig, 'ENABLE_NON_HUMAN_SKELETONS', False)
    
    try:
        # Determine session ID from image filename stem
        session_id = Path(img_fn).stem
        if not session_id:
            logger.error("Could not determine a valid session ID from img_fn.")
            return None

        # Get a unique temporary directory for this processing session
        outdir = get_session_temp_dir(session_id=session_id, clear_existing=True)
        logger.info(f"Processing {img_fn}, outputting to temporary directory: {outdir}")

        # Read image
        img = cv2.imread(img_fn)
        
        # Get original image dimensions
        orig_h, orig_w = img.shape[:2]
        
        # Copy the original image into the output_dir
        cv2.imwrite(str(outdir / "image.png"), img)
        
        # Ensure it's rgb
        if len(img.shape) != 3:
            msg = f"image must have 3 channels (rgb). Found {len(img.shape)}"
            logging.critical(msg)
            assert False, msg
        
        # Initialize scale factor
        scale = 1.0
        
        # Get model paths
        model_dir = Path(__file__).parent.parent.parent / "models"
        model_dir.mkdir(exist_ok=True, parents=True)
        
        # Check if models exist
        detector_config = model_dir / "detector_config.py"
        detector_weights = model_dir / "detector_weights.pth"
        pose_config = model_dir / "pose_config.py"
        pose_weights = model_dir / "pose_weights.pth"
        
        # Initialize pose results
        pose_results = None
        
        # Only use pose detection if models are available and we're not forcing a non-human type
        if (detector_config.exists() and detector_weights.exists() and 
            pose_config.exists() and pose_weights.exists() and
            (force_skeleton_type is None or force_skeleton_type == SkeletonType.HUMANOID)):
            
            try:
                # Initialize detector
                detector = init_detector(
                    str(detector_config), str(detector_weights), device="cuda:0"
                )
                detection_results = inference_detector(detector, img)
                
                # Get person detections
                bboxes = detection_results[0]
                if len(bboxes) > 0:
                    # Initialize pose estimator
                    pose_estimator = init_pose_model(
                        str(pose_config), str(pose_weights), device="cuda:0"
                    )
                    
                    # Get pose results for the first detection
                    person_results = [{"bbox": bboxes[0][:4]}]
                    pose_results = inference_top_down_pose_model(
                        pose_estimator, img, person_results, format="xyxy"
                    )
            except Exception as e:
                logger.warning(f"Pose detection failed: {e}. Will try alternative methods.")
                pose_results = None
        
        # Segment the character
        img_mask = segment(img)
        img_mask = fillhole(img_mask)
        img_mask = getLargestCC(img_mask).astype(np.uint8)
        img_mask = fillhole(img_mask)
        
        # Get bounding box
        bbox_obj = cv2.boundingRect(img_mask)
        l = bbox_obj[0]
        t = bbox_obj[1]
        r = bbox_obj[0] + bbox_obj[2]
        b = bbox_obj[1] + bbox_obj[3]
        
        # Crop
        cropped = img[t:b, l:r]
        mask = img_mask[t:b, l:r]
        
        # Initialize adaptive skeleton extractor
        skeleton_extractor = AdaptiveSkeletonExtractor(enable_non_human=enable_non_human)
        
        # Extract skeleton adaptively
        skeleton_model = skeleton_extractor.extract_skeleton(
            image=cropped,
            pose_results=pose_results,
            mask=mask,
            bbox=(0, 0, cropped.shape[1], cropped.shape[0]),
            force_type=force_skeleton_type
        )
        
        if skeleton_model is None:
            logger.error("Failed to extract skeleton")
            return None
        
        # Convert StandardizedSkeletonModel to char_cfg format
        skeleton = []
        for joint_id, joint in skeleton_model.joints.items():
            skeleton_joint = {
                "loc": [round(joint.position[0]), round(joint.position[1])],
                "name": joint_id,
                "parent": joint.parent_id,
                "loc_original": [
                    round(joint.position[0] + l),
                    round(joint.position[1] + t)
                ]
            }
            skeleton.append(skeleton_joint)
        
        # Create the character config dictionary
        char_cfg = {
            "skeleton": skeleton,
            "height": cropped.shape[0],
            "width": cropped.shape[1],
            "bbox_origin_x": l,
            "bbox_origin_y": t,
            "bbox_origin_r": r,
            "bbox_origin_b": b,
            "resize_scale": scale,
            "skeleton_type": skeleton_model.metadata.get("skeleton_type", "unknown"),
            "extraction_method": skeleton_model.metadata.get("extraction_method", "unknown")
        }
        
        # Convert texture to RGBA and save
        cropped = cv2.cvtColor(cropped, cv2.COLOR_BGR2BGRA)
        cv2.imwrite(str(outdir / "texture.png"), cropped)
        
        # Save mask
        cv2.imwrite(str(outdir / "mask.png"), mask)
        
        # Dump character config to yaml
        char_cfg_path = outdir / "char_cfg.yaml"
        with open(char_cfg_path, "w") as f:
            yaml.dump(char_cfg, f)
        
        # Create joint viz overlay
        joint_overlay = cropped.copy()
        for joint in skeleton:
            x, y = joint["loc"]
            name = joint["name"]
            cv2.circle(joint_overlay, (int(x), int(y)), 5, (0, 0, 0), 5)
            cv2.putText(
                joint_overlay,
                name,
                (int(x), int(y + 15)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1,
                2,
            )
        joint_overlay_path = outdir / "joint_overlay.png"
        cv2.imwrite(str(joint_overlay_path), joint_overlay)
        
        # Save bounding box info
        bounding_box_cfg = {
            "bounding_box": [l, t, r, b],
            "original_dimensions": [orig_w, orig_h],
            "cropped_dimensions": [cropped.shape[1], cropped.shape[0]],
        }
        with open(outdir / "bounding_box.yaml", "w") as f:
            yaml.dump(bounding_box_cfg, f)
        
        logger.info(f"Adaptive annotation generation complete for {img_fn}. Output at {outdir}")
        
        return {
            "output_dir": str(outdir.resolve()),
            "char_cfg_path": str(char_cfg_path.resolve()),
            "texture_path": str((outdir / "texture.png").resolve()),
            "mask_path": str((outdir / "mask.png").resolve()),
            "joint_overlay_path": str(joint_overlay_path.resolve()),
            "bounding_box_path": str((outdir / "bounding_box.yaml").resolve()),
        }
        
    except Exception as e:
        logger.error(
            f"Error during adaptive image_to_annotations for {img_fn}: {e}", exc_info=True
        )
        return None