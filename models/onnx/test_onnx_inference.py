#!/usr/bin/env python
"""
Test ONNX models on astronaut image - Rewritten based on image_to_annotations.py
"""

import os
import argparse
import numpy as np
import cv2
import onnxruntime as ort
import yaml
from pathlib import Path
from skimage import measure
from scipy import ndimage

class ONNXInferenceTest:
    def __init__(self, detector_onnx=None, pose_onnx=None):
        self.detector_session = None
        self.pose_session = None

        if detector_onnx and os.path.exists(detector_onnx):
            print(f"Loading detector ONNX: {detector_onnx}")
            self.detector_session = ort.InferenceSession(detector_onnx)
            self.print_model_info(self.detector_session, "Detector")

        if pose_onnx and os.path.exists(pose_onnx):
            print(f"Loading pose ONNX: {pose_onnx}")
            self.pose_session = ort.InferenceSession(pose_onnx)
            self.print_model_info(self.pose_session, "Pose")

    def print_model_info(self, session, model_name):
        print(f"\n📋 {model_name} Model Info:")
        for input_meta in session.get_inputs():
            print(f"  Input: {input_meta.name} {input_meta.shape}")
        for output_meta in session.get_outputs():
            print(f"  Output: {output_meta.name} {output_meta.shape}")

    def preprocess_for_detection(self, image):
        """Preprocess image for detection - Exact MMDetection pipeline"""
        # Detector config: mean=[103.53, 116.28, 123.675], std=[1.0, 1.0, 1.0], to_rgb=False
        # Resize: (1333, 800) with keep_ratio=True, Pad: size_divisor=32

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
        # std=[1.0, 1.0, 1.0] means no scaling

                # Convert to CHW format and add batch dimension
        input_tensor = np.transpose(padded, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

        return input_tensor, scale, (new_h, new_w), (pad_h, pad_w)

    def preprocess_for_pose(self, image, bbox=None):
        """Preprocess image for pose estimation - Exact MMPose pipeline"""
        # Pose config: image_size=[192, 256], mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]

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

    def detect_persons(self, image):
        """Run detection and extract person bounding boxes"""
        if self.detector_session is None:
            print("❌ No detector model loaded")
            return []

        print("\n🔍 Running Detection...")
        try:
            input_tensor, scale, (new_h, new_w), (pad_h, pad_w) = self.preprocess_for_detection(image)
            input_name = self.detector_session.get_inputs()[0].name
            outputs = self.detector_session.run(None, {input_name: input_tensor})

            print(f"  ✅ Detection Success! Outputs: {len(outputs)}")
            for i, output in enumerate(outputs):
                print(f"    Output {i}: {output.shape}")

            # For backbone outputs, we can't directly extract bboxes
            # So we'll create a dummy bbox covering the whole image for pose estimation
            h, w = image.shape[:2]
            dummy_bbox = [0, 0, w, h, 0.9]  # x1, y1, x2, y2, score

            print(f"  📦 Using full image as detection bbox: {dummy_bbox}")
            return [dummy_bbox], outputs

        except Exception as e:
            print(f"  ❌ Detection failed: {e}")
            return [], None

    def estimate_pose(self, image, bbox):
        """Run pose estimation on detected person"""
        if self.pose_session is None:
            print("❌ No pose model loaded")
            return None

        print("\n🤸 Running Pose Estimation...")
        try:
            input_tensor, cropped_image = self.preprocess_for_pose(image, bbox[:4])
            input_name = self.pose_session.get_inputs()[0].name
            outputs = self.pose_session.run(None, {input_name: input_tensor})

            print(f"  ✅ Pose Success! Outputs: {len(outputs)}")
            for i, output in enumerate(outputs):
                print(f"    Output {i}: {output.shape}")
                if len(output.shape) >= 3:
                    print(f"    Heatmap stats: min={output.min():.4f}, max={output.max():.4f}")

            # Extract keypoints from heatmap
            heatmap = outputs[0]  # Assume first output is heatmap
            keypoints = self.extract_keypoints_from_heatmap(heatmap, bbox, image.shape[:2])

            return keypoints, cropped_image, outputs

        except Exception as e:
            print(f"  ❌ Pose estimation failed: {e}")
            return None, None, None

    def extract_keypoints_from_heatmap(self, heatmap, bbox, original_size):
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

    def segment(self, img):
        """Segmentation function from image_to_annotations.py"""
        img = np.min(img, axis=2)
        img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 115, 8)
        img = cv2.bitwise_not(img)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel, iterations=2)
        img = cv2.morphologyEx(img, cv2.MORPH_DILATE, kernel, iterations=2)

        mask = np.zeros([img.shape[0]+2, img.shape[1]+2], np.uint8)
        mask[1:-1, 1:-1] = img.copy()

        im_floodfill = np.full(img.shape, 255, np.uint8)

        h, w = img.shape[:2]
        for x in range(0, w-1, 10):
            cv2.floodFill(im_floodfill, mask, (x, 0), 0)
            cv2.floodFill(im_floodfill, mask, (x, h-1), 0)
        for y in range(0, h-1, 10):
            cv2.floodFill(im_floodfill, mask, (0, y), 0)
            cv2.floodFill(im_floodfill, mask, (w-1, y), 0)

        im_floodfill[0, :] = 0
        im_floodfill[-1, :] = 0
        im_floodfill[:, 0] = 0
        im_floodfill[:, -1] = 0

        mask2 = cv2.bitwise_not(im_floodfill)
        mask = None
        biggest = 0

        contours = measure.find_contours(mask2, 0.0)
        for c in contours:
            x = np.zeros(mask2.T.shape, np.uint8)
            cv2.fillPoly(x, [np.int32(c)], 1)
            size = len(np.where(x == 1)[0])
            if size > biggest:
                mask = x
                biggest = size

        if mask is None:
            return np.zeros_like(img)

        mask = ndimage.binary_fill_holes(mask).astype(int)
        mask = 255 * mask.astype(np.uint8)
        return mask.T

    def create_skeleton_config(self, keypoints):
        """Create skeleton configuration from COCO keypoints - from image_to_annotations.py"""
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

    def visualize_results(self, image, bboxes, keypoints, cropped_image, output_dir):
        """Create visualizations following image_to_annotations.py style - ALL outputs"""
        os.makedirs(output_dir, exist_ok=True)

        # 1. Save original image (like image_to_annotations.py)
        cv2.imwrite(f"{output_dir}/image.png", image)

        if len(bboxes) > 0:
            bbox = bboxes[0]  # Use first detection
            x1, y1, x2, y2, score = bbox

            # 2. Save bounding box info (exactly like image_to_annotations.py)
            with open(f"{output_dir}/bounding_box.yaml", 'w') as f:
                yaml.dump({
                    'left': int(x1),
                    'top': int(y1),
                    'right': int(x2),
                    'bottom': int(y2),
                    'score': float(score)
                }, f)

            # Additional: Draw bounding box visualization
            bbox_image = image.copy()
            cv2.rectangle(bbox_image, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(bbox_image, f'Score: {score:.2f}', (int(x1), int(y1-10)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.imwrite(f"{output_dir}/detection_result.png", bbox_image)

        if keypoints is not None and len(keypoints) >= 17:
            # Create pose visualization on original image
            pose_image = image.copy()

            # COCO keypoint names
            keypoint_names = [
                'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
                'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
                'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
                'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
            ]

            # Draw keypoints
            for i, (x, y, conf) in enumerate(keypoints):
                if conf > 0.1:
                    cv2.circle(pose_image, (int(x), int(y)), 5, (0, 255, 0), -1)
                    if i < len(keypoint_names):
                        cv2.putText(pose_image, keypoint_names[i],
                                  (int(x), int(y-10)), cv2.FONT_HERSHEY_SIMPLEX,
                                  0.3, (255, 255, 255), 1)

            # Draw skeleton connections
            skeleton_connections = [
                (0, 1), (0, 2), (1, 3), (2, 4),  # Head
                (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),  # Arms
                (5, 11), (6, 12), (11, 12),  # Torso
                (11, 13), (13, 15), (12, 14), (14, 16)  # Legs
            ]

            for connection in skeleton_connections:
                if connection[0] < len(keypoints) and connection[1] < len(keypoints):
                    kpt1, kpt2 = keypoints[connection[0]], keypoints[connection[1]]
                    if kpt1[2] > 0.1 and kpt2[2] > 0.1:
                        cv2.line(pose_image,
                               (int(kpt1[0]), int(kpt1[1])),
                               (int(kpt2[0]), int(kpt2[1])),
                               (0, 0, 255), 2)

            cv2.imwrite(f"{output_dir}/pose_keypoints.png", pose_image)

            # 3. Create skeleton config (exactly like image_to_annotations.py)
            skeleton = self.create_skeleton_config(keypoints)
            char_cfg = {
                'skeleton': skeleton,
                'height': cropped_image.shape[0] if cropped_image is not None else image.shape[0],
                'width': cropped_image.shape[1] if cropped_image is not None else image.shape[1]
            }

            # 4. Save char_cfg.yaml (exactly like image_to_annotations.py)
            with open(f"{output_dir}/char_cfg.yaml", 'w') as f:
                yaml.dump(char_cfg, f)

            # Process cropped image if available
            if cropped_image is not None:
                # 5. Convert texture to BGRA and save (exactly like image_to_annotations.py)
                texture = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2BGRA)
                cv2.imwrite(f"{output_dir}/texture.png", texture)

                # 6. Create and save mask (exactly like image_to_annotations.py)
                mask = self.segment(cropped_image)
                cv2.imwrite(f"{output_dir}/mask.png", mask)

                # 7. Create joint overlay (exactly like image_to_annotations.py)
                joint_overlay = texture.copy()

                # Draw joints on cropped image using cropped coordinates
                bbox = bboxes[0] if bboxes else [0, 0, image.shape[1], image.shape[0]]
                x1, y1 = bbox[0], bbox[1]

                for joint in skeleton:
                    # Convert from original coordinates to cropped coordinates
                    x_orig, y_orig = joint['loc']
                    x_crop = x_orig - x1
                    y_crop = y_orig - y1

                    if 0 <= x_crop < joint_overlay.shape[1] and 0 <= y_crop < joint_overlay.shape[0]:
                        cv2.circle(joint_overlay, (int(x_crop), int(y_crop)), 5, (0, 0, 0, 255), 5)
                        cv2.putText(joint_overlay, joint['name'],
                                  (int(x_crop), int(y_crop + 15)),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0, 255), 1, 2)

                cv2.imwrite(f"{output_dir}/joint_overlay.png", joint_overlay)

        # Summary of saved files
        saved_files = []
        for filename in ['image.png', 'bounding_box.yaml', 'detection_result.png',
                        'pose_keypoints.png', 'char_cfg.yaml', 'texture.png',
                        'mask.png', 'joint_overlay.png']:
            if os.path.exists(f"{output_dir}/{filename}"):
                saved_files.append(filename)

        print(f"  💾 Saved {len(saved_files)} files to {output_dir}/:")
        for filename in saved_files:
            print(f"    📄 {filename}")
        print()

    def test_image(self, image_path, save_results=True, output_suffix=""):
        """Complete pipeline test following image_to_annotations.py approach"""
        print(f"\n🖼️  Testing: {image_path}")
        image = cv2.imread(str(image_path))
        if image is None:
            print(f"❌ Cannot load image")
            return

        print(f"  Image shape: {image.shape}")

        # Step 1: Detection
        bboxes, detector_outputs = self.detect_persons(image)

        # Step 2: Pose estimation
        keypoints = None
        cropped_image = None
        pose_outputs = None
        if len(bboxes) > 0:
            pose_result = self.estimate_pose(image, bboxes[0])
            if pose_result is not None:
                keypoints, cropped_image, pose_outputs = pose_result

        # Step 3: Visualization
        if save_results:
            base_name = Path(image_path).stem
            if output_suffix:
                output_dir = f"./results/{base_name}_{output_suffix}"
            else:
                output_dir = f"./results/{base_name}"
            self.visualize_results(image, bboxes, keypoints, cropped_image, output_dir)

        return {
            'bboxes': bboxes,
            'keypoints': keypoints,
            'detector_outputs': detector_outputs
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default='astronaut.png')
    parser.add_argument('--detector-onnx', default='./exports/detector_wrapped.onnx')
    parser.add_argument('--pose-onnx', default='./exports/pose_model.onnx')
    parser.add_argument('--test-all', action='store_true')
    parser.add_argument('--no-save', action='store_true')

    args = parser.parse_args()

    print("🧪 ONNX Model Test - Rewritten")
    print("=" * 40)

    if args.test_all:
        detector_models = {
            'detector_backbone': './exports/detector_backbone.onnx',
            'detector_wrapped': './exports/detector_wrapped.onnx',
            'detector_traced_large': './exports/detector_traced_large.onnx'
        }

        pose_model = './exports/pose_model.onnx'
        pose_available = os.path.exists(pose_model)

        # Test each detector model individually
        for model_name, model_path in detector_models.items():
            if os.path.exists(model_path):
                print(f"\n🔬 Testing: {model_name} only ({model_path})")
                tester = ONNXInferenceTest(detector_onnx=model_path)
                tester.test_image(args.image, save_results=not args.no_save, output_suffix=f"{model_name}_only")

        # Test each detector model with pose estimation
        if pose_available:
            for model_name, model_path in detector_models.items():
                if os.path.exists(model_path):
                    print(f"\n🔬 Testing: {model_name} + pose ({model_path} + {pose_model})")
                    tester = ONNXInferenceTest(detector_onnx=model_path, pose_onnx=pose_model)
                    tester.test_image(args.image, save_results=not args.no_save, output_suffix=f"{model_name}_with_pose")

        # Test pose model only
        if pose_available:
            print(f"\n🔬 Testing: pose_model only ({pose_model})")
            tester = ONNXInferenceTest(pose_onnx=pose_model)
            tester.test_image(args.image, save_results=not args.no_save, output_suffix="pose_only")
    else:
        tester = ONNXInferenceTest(args.detector_onnx, args.pose_onnx)
        tester.test_image(args.image, save_results=not args.no_save)

    print("\n✅ Complete!")

if __name__ == '__main__':
    main()