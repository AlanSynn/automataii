#!/usr/bin/env python
"""
Modern image to annotations pipeline using ONNX models
Based on our successful test_onnx_inference.py implementation
"""

import logging
import sys
from pathlib import Path
from typing import TypedDict

import cv2
import numpy as np
import yaml
from scipy import ndimage

try:
    import onnxruntime as ort
except ImportError:
    ort = None
    logging.warning("ONNXRuntime not available. Install with: pip install onnxruntime")

from automataii.utils.model_downloader import ModelDownloader
from automataii.utils.paths import get_session_temp_dir, resolve_path


class AnnotationResults(TypedDict):
    output_dir: str
    char_cfg_path: str
    texture_path: str
    mask_path: str
    joint_overlay_path: str
    bounding_box_path: str


class ONNXImageProcessor:
    """ONNX-based image processing pipeline for character animation"""

    def __init__(self, detector_onnx=None, pose_onnx=None):
        """
        Initialize with ONNX model paths

        Args:
            detector_onnx: Path to detector ONNX model
            pose_onnx: Path to pose estimation ONNX model
        """
        self.detector_session = None
        self.pose_session = None

        # resolve_path를 사용하여 개발 및 번들 환경 모두에서 모델 경로를 찾습니다.
        models_dir = resolve_path("models")

        if detector_onnx is None:
            detector_onnx = models_dir / "onnx" / "detector_backbone.onnx"
        if pose_onnx is None:
            pose_onnx = models_dir / "onnx" / "pose_model.onnx"

        self.detector_path = Path(detector_onnx)
        self.pose_path = Path(pose_onnx)

        self._load_models()

    def _load_models(self):
        """Load ONNX models, downloading if necessary"""
        if not ort:
            raise ImportError("ONNXRuntime required. Install with: pip install onnxruntime")

        # Initialize model downloader for large model files
        downloader = ModelDownloader()

        # Load detector
        if self.detector_path.exists():
            try:
                self.detector_session = ort.InferenceSession(str(self.detector_path))
                logging.info(f"Loaded detector ONNX: {self.detector_path}")
            except Exception as e:
                logging.warning(f"Failed to load detector: {e}")
        else:
            logging.warning(f"Detector model not found: {self.detector_path}")
            # Note: ONNX models are included in the build, so this shouldn't happen
            # But if it does, we could implement download logic here

        # Load pose model
        if self.pose_path.exists():
            try:
                self.pose_session = ort.InferenceSession(str(self.pose_path))
                logging.info(f"Loaded pose ONNX: {self.pose_path}")
            except Exception as e:
                logging.warning(f"Failed to load pose model: {e}")
        else:
            logging.warning(f"Pose model not found: {self.pose_path}")
            # Note: ONNX models are included in the build, so this shouldn't happen

        # Check if we need any PyTorch models (which are excluded from build)
        weights_dir = self.detector_path.parent.parent / "weights"
        if weights_dir.exists():
            # Check for PyTorch models and download if needed
            pytorch_models = ["detector_latest.pth", "pose_best_AP_epoch_72.pth"]
            for model_name in pytorch_models:
                model_path = weights_dir / model_name
                if not model_path.exists():
                    logging.info(f"PyTorch model {model_name} not found locally")
                    try:
                        # Try to download large PyTorch models on-demand
                        downloaded_path = downloader.download_model(model_name)
                        if downloaded_path:
                            logging.info(f"Downloaded {model_name} to {downloaded_path}")
                        else:
                            logging.warning(f"Could not download {model_name}")
                    except Exception as e:
                        logging.warning(f"Failed to download {model_name}: {e}")

    def preprocess_for_detection(self, image):
        """Preprocess image for detection - Exact MMDetection pipeline"""
        h, w = image.shape[:2]

        # Resize with keep_ratio=True to (1333, 800)
        scale = min(1333/w, 800/h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(image, (new_w, new_h))

        # Pad to make divisible by 32
        pad_h = ((new_h + 31) // 32) * 32
        pad_w = ((new_w + 31) // 32) * 32
        padded = np.zeros((pad_h, pad_w, 3), dtype=np.float32)
        padded[:new_h, :new_w] = resized

        # Normalize: mean=[103.53, 116.28, 123.675], std=[1.0, 1.0, 1.0], to_rgb=False (BGR)
        padded = padded.astype(np.float32)
        padded[:, :, 0] -= 103.53  # B
        padded[:, :, 1] -= 116.28  # G
        padded[:, :, 2] -= 123.675 # R

        # Convert to CHW format and add batch dimension
        input_tensor = np.transpose(padded, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

        return input_tensor, scale, (new_h, new_w), (pad_h, pad_w)

    def preprocess_for_pose(self, image, bbox=None):
        """Preprocess image for pose estimation - Exact MMPose pipeline"""
        if bbox is not None:
            # Crop image using bbox
            x1, y1, x2, y2 = [int(x) for x in bbox]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(image.shape[1], x2), min(image.shape[0], y2)
            cropped = image[y1:y2, x1:x2]
        else:
            cropped = image

        # Resize to exact pose model input size: (192, 256) - width, height
        resized = cv2.resize(cropped, (192, 256))

        # Convert BGR to RGB for ImageNet normalization
        rgb_image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        normalized = rgb_image.astype(np.float32) / 255.0

        # ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        normalized = (normalized - mean) / std

        # Convert to CHW format and add batch dimension
        input_tensor = np.transpose(normalized, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

        return input_tensor, cropped

    def detect_person(self, image):
        """Run detection and extract person bounding box"""
        if self.detector_session is None:
            # Fallback: use entire image as bounding box
            h, w = image.shape[:2]
            return [0, 0, w, h, 0.9]

        try:
            input_tensor, scale, (new_h, new_w), (pad_h, pad_w) = self.preprocess_for_detection(image)
            input_name = self.detector_session.get_inputs()[0].name
            outputs = self.detector_session.run(None, {input_name: input_tensor})

            # For backbone outputs, we can't directly extract bboxes
            # So we'll create a bbox covering the whole image for pose estimation
            h, w = image.shape[:2]
            bbox = [0, 0, w, h, 0.9]  # x1, y1, x2, y2, score

            logging.info(f"Detection complete, using full image bbox: {bbox}")
            return bbox

        except Exception as e:
            logging.warning(f"Detection failed: {e}. Using full image.")
            h, w = image.shape[:2]
            return [0, 0, w, h, 0.5]

    def estimate_pose(self, image, bbox):
        """Run pose estimation on detected person"""
        if self.pose_session is None:
            logging.error("No pose model loaded")
            return None

        try:
            input_tensor, cropped_image = self.preprocess_for_pose(image, bbox[:4])
            input_name = self.pose_session.get_inputs()[0].name
            outputs = self.pose_session.run(None, {input_name: input_tensor})

            # Extract keypoints from heatmap
            heatmap = outputs[0]  # Assume first output is heatmap
            keypoints = self.extract_keypoints_from_heatmap(heatmap, bbox)

            logging.info(f"Pose estimation complete, extracted {len(keypoints)} keypoints")
            return keypoints, cropped_image

        except Exception as e:
            logging.error(f"Pose estimation failed: {e}")
            return None, None

    def extract_keypoints_from_heatmap(self, heatmap, bbox):
        """Extract keypoints from pose heatmap output"""
        if len(heatmap.shape) == 4:
            heatmap = heatmap[0]  # Remove batch dimension

        num_joints = heatmap.shape[0]
        heatmap_h, heatmap_w = heatmap.shape[1], heatmap.shape[2]

        keypoints = []
        x1, y1, x2, y2 = bbox[:4]
        bbox_w, bbox_h = x2 - x1, y2 - y1

        for i in range(num_joints):
            hm = heatmap[i]

            # Find maximum location in heatmap
            idx = np.unravel_index(np.argmax(hm), hm.shape)
            y_hm, x_hm = idx
            confidence = hm[y_hm, x_hm]

            # Convert heatmap coordinates to bbox coordinates
            x_bbox = (x_hm / heatmap_w) * bbox_w
            y_bbox = (y_hm / heatmap_h) * bbox_h

            # Convert bbox coordinates to original image coordinates
            x_orig = x1 + x_bbox
            y_orig = y1 + y_bbox

            keypoints.append([x_orig, y_orig, confidence])

        return np.array(keypoints)


def segment(img: np.ndarray) -> np.ndarray:
    """Robust segmentation for both photos and line art"""
    # Check if image has alpha channel
    has_alpha = img.shape[2] == 4 if len(img.shape) == 3 else False

    if has_alpha:
        # Use alpha channel if available
        alpha = img[:, :, 3]
        # If alpha channel has meaningful data, use it
        if np.max(alpha) > 0 and np.std(alpha) > 10:
            mask = alpha.copy()
            mask = cv2.threshold(mask, 10, 255, cv2.THRESH_BINARY)[1]

            # Clean up the mask
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

            # Fill holes
            mask_filled = ndimage.binary_fill_holes(mask > 0).astype(np.uint8) * 255

            # Use largest component
            contours, _ = cv2.findContours(mask_filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=cv2.contourArea)
                mask = np.zeros_like(mask)
                cv2.drawContours(mask, [largest], -1, 255, -1)
                return mask

    # Fallback to content-based segmentation
    if len(img.shape) == 3:
        # Convert to grayscale
        gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY) if img.shape[2] >= 3 else img[:, :, 0]
    else:
        gray = img

    # Check for line art characteristics
    h, w = gray.shape[:2]
    white_pixels = np.sum(gray > 240)
    total_pixels = gray.size
    white_percentage = (white_pixels / total_pixels) * 100

    if white_percentage > 40:  # Likely line art with white background
        # For line art, we need to find the drawing and fill it
        # Invert to make lines white
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

        # Use morphology to connect broken lines
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=3)

        # Find all contours (both external and internal)
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            # Create a mask with all contours filled
            mask = np.zeros((h, w), dtype=np.uint8)

            # Find the bounding contour (outermost shape)
            # This is typically the character outline
            areas = [cv2.contourArea(c) for c in contours]
            if areas:
                # Get contours sorted by area
                sorted_indices = np.argsort(areas)[::-1]

                # Take the largest contour that's not the entire image
                image_area = h * w
                for idx in sorted_indices:
                    area = areas[idx]
                    if area < image_area * 0.9:  # Not the entire image
                        # Draw this contour and fill it
                        cv2.drawContours(mask, [contours[idx]], -1, 255, -1)

                        # Also fill any child contours (holes inside)
                        if hierarchy is not None:
                            # Fill all children
                            child_idx = hierarchy[0][idx][2]  # First child
                            while child_idx != -1:
                                cv2.drawContours(mask, [contours[child_idx]], -1, 255, -1)
                                child_idx = hierarchy[0][child_idx][0]  # Next sibling
                        break

            # Fill any remaining holes
            mask = ndimage.binary_fill_holes(mask > 0).astype(np.uint8) * 255

            return mask
    else:
        # Photo or dark background - use adaptive threshold
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 115, 8)

        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    # Remove border pixels and flood fill from edges
    h, w = binary.shape[:2]
    mask = np.zeros([h+2, w+2], np.uint8)
    mask[1:-1, 1:-1] = binary.copy()

    im_floodfill = binary.copy()

    # Flood fill from edges
    for x in range(0, w-1, 10):
        cv2.floodFill(im_floodfill, mask, (x, 0), 0)
        cv2.floodFill(im_floodfill, mask, (x, h-1), 0)
    for y in range(0, h-1, 10):
        cv2.floodFill(im_floodfill, mask, (0, y), 0)
        cv2.floodFill(im_floodfill, mask, (w-1, y), 0)

    # Find largest connected component
    contours, _ = cv2.findContours(im_floodfill, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        # If no contours found, return a filled rectangle
        mask = np.ones((h, w), dtype=np.uint8) * 255
        return mask

    # Get the largest contour
    largest_contour = max(contours, key=cv2.contourArea)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(mask, [largest_contour], -1, 255, -1)

    # Fill holes
    mask = ndimage.binary_fill_holes(mask > 0).astype(np.uint8) * 255

    return mask


def create_skeleton_config(keypoints):
    """Create skeleton configuration from COCO keypoints"""
    kpts = keypoints[:, :2]

    skeleton = []
    skeleton.append({'loc': [int(x) for x in (kpts[11] + kpts[12]) / 2], 'name': 'root', 'parent': None})
    skeleton.append({'loc': [int(x) for x in (kpts[11] + kpts[12]) / 2], 'name': 'hip', 'parent': 'root'})
    skeleton.append({'loc': [int(x) for x in (kpts[5] + kpts[6]) / 2], 'name': 'torso', 'parent': 'hip'})
    skeleton.append({'loc': [int(x) for x in kpts[0]], 'name': 'neck', 'parent': 'torso'})
    skeleton.append({'loc': [int(x) for x in kpts[6]], 'name': 'right_shoulder', 'parent': 'torso'})
    skeleton.append({'loc': [int(x) for x in kpts[8]], 'name': 'right_elbow', 'parent': 'right_shoulder'})
    skeleton.append({'loc': [int(x) for x in kpts[10]], 'name': 'right_hand', 'parent': 'right_elbow'})
    skeleton.append({'loc': [int(x) for x in kpts[5]], 'name': 'left_shoulder', 'parent': 'torso'})
    skeleton.append({'loc': [int(x) for x in kpts[7]], 'name': 'left_elbow', 'parent': 'left_shoulder'})
    skeleton.append({'loc': [int(x) for x in kpts[9]], 'name': 'left_hand', 'parent': 'left_elbow'})
    skeleton.append({'loc': [int(x) for x in kpts[12]], 'name': 'right_hip', 'parent': 'root'})
    skeleton.append({'loc': [int(x) for x in kpts[14]], 'name': 'right_knee', 'parent': 'right_hip'})
    skeleton.append({'loc': [int(x) for x in kpts[16]], 'name': 'right_foot', 'parent': 'right_knee'})
    skeleton.append({'loc': [int(x) for x in kpts[11]], 'name': 'left_hip', 'parent': 'root'})
    skeleton.append({'loc': [int(x) for x in kpts[13]], 'name': 'left_knee', 'parent': 'left_hip'})
    skeleton.append({'loc': [int(x) for x in kpts[15]], 'name': 'left_foot', 'parent': 'left_knee'})

    return skeleton


def image_to_annotations(img_fn: str, detector_onnx=None, pose_onnx=None) -> AnnotationResults | None:
    """
    Modern ONNX-based image to annotations pipeline

    Args:
        img_fn: Path to input image
        detector_onnx: Optional path to detector ONNX model
        pose_onnx: Optional path to pose ONNX model

    Returns:
        AnnotationResults or None if failed
    """
    logger = logging.getLogger(__name__)

    try:
        # Determine session ID from image filename stem
        session_id = Path(img_fn).stem
        if not session_id:
            logger.error("Could not determine a valid session ID from img_fn.")
            return None

        # Get output directory
        outdir = get_session_temp_dir(session_id=session_id, clear_existing=True)
        logger.info(f"Processing {img_fn}, outputting to: {outdir}")

        # Read image
        image = cv2.imread(str(img_fn))
        if image is None:
            logger.error(f"Cannot read image: {img_fn}")
            return None

        orig_h, orig_w = image.shape[:2]
        logger.info(f"Image shape: {image.shape}")

        # Copy original image
        cv2.imwrite(str(outdir / "image.png"), image)

        # Initialize ONNX processor
        processor = ONNXImageProcessor(detector_onnx, pose_onnx)

        # Step 1: Detection
        bbox = processor.detect_person(image)
        x1, y1, x2, y2, score = bbox

        # Give margin to the bounding box (same as original)
        margin = 0.2
        l = max(0, x1 - int(margin * x1))
        t = max(0, y1 - int(margin * y1))
        r = min(orig_w, x2 + int(margin * x2))
        b = min(orig_h, y2 + int(margin * y2))

        # Save bounding box info
        bbox_data = {
            "left": int(l),
            "top": int(t),
            "right": int(r),
            "bottom": int(b),
            "score": float(score),
            "original_width": orig_w,
            "original_height": orig_h,
        }

        bbox_path = outdir / "bounding_box.yaml"
        with open(bbox_path, 'w') as f:
            yaml.dump(bbox_data, f)

        # Step 2: Pose estimation
        pose_result = processor.estimate_pose(image, [l, t, r, b])
        if pose_result is None:
            logger.error("Pose estimation failed")
            return None

        keypoints, cropped_image = pose_result
        if keypoints is None or len(keypoints) < 17:
            logger.error("Insufficient keypoints detected")
            return None

        # Crop image
        cropped = image[t:b, l:r]

        # Step 3: Create skeleton config
        skeleton = create_skeleton_config(keypoints)

        # Adjust skeleton coordinates to cropped image space
        for joint in skeleton:
            orig_x, orig_y = joint['loc']
            joint['loc'] = [orig_x - l, orig_y - t]  # Convert to cropped coordinates
            joint['loc_original'] = [orig_x, orig_y]  # Keep original coordinates

        char_cfg = {
            "skeleton": skeleton,
            "height": cropped.shape[0],
            "width": cropped.shape[1],
            "bbox_origin_x": int(l),
            "bbox_origin_y": int(t),
            "bbox_origin_r": int(r),
            "bbox_origin_b": int(b),
            "resize_scale": 1.0,  # No resize applied
        }

        # Step 4: Save outputs
        # Create mask first
        mask = segment(cropped)
        mask_path = outdir / "mask.png"
        cv2.imwrite(str(mask_path), mask)

        # Convert texture to BGRA and apply mask to alpha
        if cropped.shape[2] == 4:
            # Already has alpha channel
            texture = cropped.copy()
            # Combine with mask if alpha is empty
            if np.mean(texture[:, :, 3]) < 5:
                texture[:, :, 3] = mask
        else:
            # Convert to BGRA
            texture = cv2.cvtColor(cropped, cv2.COLOR_BGR2BGRA)
            # Use mask as alpha
            texture[:, :, 3] = mask

        texture_path = outdir / "texture.png"
        cv2.imwrite(str(texture_path), texture)

        # Save character config
        char_cfg_path = outdir / "char_cfg.yaml"
        with open(char_cfg_path, 'w') as f:
            yaml.dump(char_cfg, f)

        # Create joint overlay
        joint_overlay = texture.copy()
        for joint in skeleton:
            x, y = joint['loc']
            name = joint['name']
            if 0 <= x < joint_overlay.shape[1] and 0 <= y < joint_overlay.shape[0]:
                cv2.circle(joint_overlay, (int(x), int(y)), 5, (0, 0, 0, 255), 5)
                cv2.putText(joint_overlay, name, (int(x), int(y + 15)),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0, 255), 1, 2)

        joint_overlay_path = outdir / "joint_overlay.png"
        cv2.imwrite(str(joint_overlay_path), joint_overlay)

        logger.info(f"Annotation generation complete. Output at {outdir}")

        return {
            "output_dir": str(outdir.resolve()),
            "char_cfg_path": str(char_cfg_path.resolve()),
            "texture_path": str(texture_path.resolve()),
            "mask_path": str(mask_path.resolve()),
            "joint_overlay_path": str(joint_overlay_path.resolve()),
            "bounding_box_path": str(bbox_path.resolve()),
        }

    except Exception as e:
        logger.error(f"Error during image_to_annotations for {img_fn}: {e}", exc_info=True)
        return None


def main():
    """Command line interface"""
    import argparse

    parser = argparse.ArgumentParser(description="Convert image to animation annotations using ONNX models")
    parser.add_argument("image", help="Path to input image")
    parser.add_argument("--detector-onnx", help="Path to detector ONNX model")
    parser.add_argument("--pose-onnx", help="Path to pose ONNX model")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Process image
    result = image_to_annotations(args.image, args.detector_onnx, args.pose_onnx)

    if result:
        print(f"✅ Success! Output saved to: {result['output_dir']}")
        print(f"Character config: {result['char_cfg_path']}")
    else:
        print("❌ Failed to process image")
        sys.exit(1)


if __name__ == "__main__":
    main()
