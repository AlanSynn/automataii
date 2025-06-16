#!/usr/bin/env python
"""
Process images using legacy MMDetection and MMPose APIs
Based on image_to_annotations.py approach
"""

import os
import sys
import argparse
import numpy as np
from pathlib import Path
import cv2
import torch
import warnings
import yaml
warnings.filterwarnings('ignore')

# Import legacy APIs like image_to_annotations.py
try:
    from mmdet.apis import inference_detector, init_detector
    from mmpose.apis import inference_top_down_pose_model, init_pose_model
    import mmcv
except ImportError as e:
    print(f"Error importing MM libraries: {e}")
    print("Please install with:")
    print("pip install mmdet mmpose mmcv-full")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Process images with legacy MMDet/MMPose APIs')
    parser.add_argument('--image', type=str, default='astronaut.png',
                        help='Path to input image')
    parser.add_argument('--det-config', type=str, required=True,
                        help='Path to detector config')
    parser.add_argument('--det-checkpoint', type=str, required=True,
                        help='Path to detector checkpoint')
    parser.add_argument('--pose-config', type=str, required=True,
                        help='Path to pose config')
    parser.add_argument('--pose-checkpoint', type=str, required=True,
                        help='Path to pose checkpoint')
    parser.add_argument('--device', type=str, default='cuda:0',
                        help='Device to run on')

    args = parser.parse_args()

    print("🧪 Legacy API Test - Starting...")

    # Initialize detector - exactly like image_to_annotations.py
    print("Initializing detector...")
    detector = init_detector(
        str(args.det_config), str(args.det_checkpoint), device=args.device
    )
    print(f"✅ Detector initialized: {detector.__class__.__name__}")

    # Initialize pose estimator - exactly like image_to_annotations.py
    print("Initializing pose estimator...")
    pose_estimator = init_pose_model(
        str(args.pose_config), str(args.pose_checkpoint), device=args.device
    )
    print(f"✅ Pose estimator initialized: {pose_estimator.__class__.__name__}")

    # Read image
    image = cv2.imread(str(args.image))
    if image is None:
        raise ValueError(f"Cannot read image: {args.image}")

    print(f"\n🖼️ Processing image: {args.image}")
    print(f"Image shape: {image.shape}")

    # Run detector - exactly like image_to_annotations.py
    print("🔍 Running detection...")
    det_results = inference_detector(detector, image)
    print(f"Detection completed. Result type: {type(det_results)}")

    # Process detection results - exactly like image_to_annotations.py
    if isinstance(det_results, tuple):
        bbox_result, segm_result = det_results
    else:
        bbox_result, segm_result = det_results, None

    # Get bounding boxes with scores - exactly like image_to_annotations.py
    detection_results = []
    for class_index, class_result in enumerate(bbox_result):
        class_name = detector.CLASSES[class_index]
        for bbox in class_result:
            score = float(bbox[-1])
            if score >= 0.5:  # Use 0.5 threshold
                detection_results.append(
                    {
                        "class_name": class_name,
                        "bbox": bbox[:-1].tolist(),
                        "score": score,
                    }
                )

    # Sort by score (descending) - exactly like image_to_annotations.py
    detection_results.sort(key=lambda x: x["score"], reverse=True)

    print(f"📦 Detected {len(detection_results)} objects with score >= 0.5")

    if len(detection_results) > 0:
        best_detection = detection_results[0]
        print(f"Best detection: {best_detection['class_name']} (score: {best_detection['score']:.3f})")

        # Get bbox and apply margin like image_to_annotations.py
        bbox = np.array(best_detection["bbox"])
        l, t, r, b = [round(x) for x in bbox]

        # Give margin to the bounding box - exactly like image_to_annotations.py
        scale = 0.2
        l -= int(scale * l)
        t -= int(scale * t)
        r += int(scale * r)
        b += int(scale * b)

        # Ensure bbox is within image bounds
        h, w = image.shape[:2]
        l = max(0, l)
        t = max(0, t)
        r = min(w, r)
        b = min(h, b)

        # Crop the image - exactly like image_to_annotations.py
        cropped = image[t:b, l:r]
        print(f"Cropped image shape: {cropped.shape}")

        # Run pose estimation on cropped image - exactly like image_to_annotations.py
        print("🤸 Running pose estimation...")
        pose_results, _ = inference_top_down_pose_model(
            pose_estimator,
            cropped,
            person_results=None,  # Use None to get all poses in the image
            format="xyxy",
        )

        print(f"Pose estimation completed. Found {len(pose_results)} poses")

        if len(pose_results) > 0:
            pose_result = pose_results[0]
            keypoints = pose_result["keypoints"]
            print(f"Keypoints shape: {keypoints.shape}")
            print(f"Sample keypoints (first 3): {keypoints[:3]}")

            # Save results
            output_dir = f"./results/{Path(args.image).stem}_legacy"
            os.makedirs(output_dir, exist_ok=True)

            # Save original image
            cv2.imwrite(f"{output_dir}/image.png", image)

            # Save bounding box
            with open(f"{output_dir}/bounding_box.yaml", 'w') as f:
                yaml.dump({
                    'left': l,
                    'top': t,
                    'right': r,
                    'bottom': b,
                    'score': best_detection['score']
                }, f)

            # Save cropped texture
            texture = cv2.cvtColor(cropped, cv2.COLOR_BGR2BGRA)
            cv2.imwrite(f"{output_dir}/texture.png", texture)

            # Create simple visualization
            vis_image = image.copy()
            cv2.rectangle(vis_image, (l, t), (r, b), (0, 255, 0), 2)
            cv2.putText(vis_image, f'{best_detection["score"]:.2f}', (l, t-5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # Draw keypoints on original image
            for kpt in keypoints:
                x_crop, y_crop, conf = kpt
                if conf > 0.3:
                    x_orig = l + x_crop
                    y_orig = t + y_crop
                    cv2.circle(vis_image, (int(x_orig), int(y_orig)), 3, (255, 0, 0), -1)

            cv2.imwrite(f"{output_dir}/visualization.png", vis_image)

            print(f"💾 Results saved to: {output_dir}")
            print("✅ Legacy API test completed successfully!")
        else:
            print("❌ No poses detected")
    else:
        print("❌ No objects detected")


if __name__ == '__main__':
    main()