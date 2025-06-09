import sys
import cv2
import json
import numpy as np
from skimage import measure
from scipy import ndimage
from pathlib import Path
import yaml
import logging
import os
import torch
from typing import Optional, TypedDict

# Import needed modules from mmdet and mmpose
from mmdet.apis import inference_detector, init_detector
from mmpose.apis import inference_top_down_pose_model, init_pose_model

# Automataii specific imports
from automataii.utils.paths import get_session_temp_dir


# Define a more specific return type if possible, e.g. a TypedDict or a custom Pydantic model
# For now, let's assume it returns the path to the directory and key file paths
class AnnotationResults(TypedDict):
    output_dir: str
    char_cfg_path: str
    texture_path: str
    mask_path: str
    # Add other relevant paths if needed, e.g., joint_overlay_path


def image_to_annotations(img_fn: str) -> Optional[AnnotationResults]:
    """
    Given the RGB image located at img_fn, runs detection, segmentation, and pose estimation for drawn character within it.
    Crops the image and saves texture, mask, and character config files necessary for animation.
    Writes to a session-specific temporary directory.

    Args:
        img_fn: path to RGB image

    Returns:
        Optional[AnnotationResults]: A dictionary containing paths to the generated files if successful, None otherwise.
    """
    logger = logging.getLogger(__name__)

    try:
        # Determine session ID from image filename stem
        session_id = Path(img_fn).stem
        if not session_id:
            logger.error("Could not determine a valid session ID from img_fn.")
            return None

        # Get a unique temporary directory for this processing session
        # This directory will be cleared if it already exists from a previous run with the same session_id
        outdir = get_session_temp_dir(session_id=session_id, clear_existing=True)
        logger.info(f"Processing {img_fn}, outputting to temporary directory: {outdir}")

        # read image
        img = cv2.imread(img_fn)

        # Get original image dimensions *before* potential resize
        orig_h, orig_w = img.shape[:2]

        # copy the original image into the output_dir
        cv2.imwrite(str(outdir / "image.png"), img)

        # ensure it's rgb
        if len(img.shape) != 3:
            msg = f"image must have 3 channels (rgb). Found {len(img.shape)}"
            logging.critical(msg)
            assert False, msg

        # Initialize scale factor
        scale = 1.0

        # resize if needed
        # if np.max(img.shape) > 1000:
        #     scale = 1000 / np.max(img.shape)
        #     img = cv2.resize(img, (round(scale * img.shape[1]), round(scale * img.shape[0])))

        # Get model paths
        model_dir = Path(__file__).parent.parent.parent / "models"
        model_dir.mkdir(exist_ok=True, parents=True)

        # Check if models exist, if not, notify user to download them
        detector_config = model_dir / "detector_config.py"
        detector_weights = model_dir / "detector_weights.pth"
        pose_config = model_dir / "pose_config.py"
        pose_weights = model_dir / "pose_weights.pth"

        # Check if model files exist
        if not (
            detector_config.exists()
            and detector_weights.exists()
            and pose_config.exists()
            and pose_weights.exists()
        ):
            msg = f"""
            Model files not found in {model_dir}. Please download the model files:

            To manually copy model files:
            1. Copy drawn_humanoid_detector/config.py to models/detector_config.py
            2. Copy drawn_humanoid_detector/latest.pth to models/detector_weights.pth
            3. Copy drawn_humanoid_pose_estimator/config.py to models/pose_config.py
            4. Copy drawn_humanoid_pose_estimator/best_AP_epoch_72.pth to models/pose_weights.pth

            You can find these files in the original project's torchserve/model-store directory.
            """
            logging.critical(msg)
            assert False, msg

        # Initialize detector and pose estimator models
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Initialize the detector
        detector = init_detector(
            str(detector_config), str(detector_weights), device=device
        )

        # Initialize the pose estimator
        pose_estimator = init_pose_model(
            str(pose_config), str(pose_weights), device=device
        )

        # Run detector on the image
        det_results = inference_detector(detector, img)

        # Process detection results
        if isinstance(det_results, tuple):
            bbox_result, segm_result = det_results
        else:
            bbox_result, segm_result = det_results, None

        # Get bounding boxes with scores
        detection_results = []
        for class_index, class_result in enumerate(bbox_result):
            class_name = detector.CLASSES[class_index]
            for bbox in class_result:
                score = float(bbox[-1])
                if score >= 0.7:  # Apply threshold similar to TorchServe handler
                    detection_results.append(
                        {
                            "class_name": class_name,
                            "bbox": bbox[:-1].tolist(),
                            "score": score,
                        }
                    )

        # Sort by score (descending)
        detection_results.sort(key=lambda x: x["score"], reverse=True)

        # if no drawn humanoids detected, abort
        if len(detection_results) == 0:
            msg = "Could not detect any drawn humanoids in the image. Aborting"
            logging.critical(msg)
            assert False, msg

        # otherwise, report # detected and score of highest.
        msg = f"Detected {len(detection_results)} humanoids in image. Using detection with highest score {detection_results[0]['score']}."
        logging.info(msg)

        # calculate the coordinates of the character bounding box
        bbox = np.array(detection_results[0]["bbox"])
        l, t, r, b = [round(x) for x in bbox]

        # Give margin to the bounding box
        scale = 0.1
        l -= int(scale * l)
        t -= int(scale * t)
        r += int(scale * r)
        b += int(scale * b)

        # dump the bounding box results along with original image dimensions
        with open(str(outdir / "bounding_box.yaml"), "w") as f:
            yaml.dump(
                {
                    "left": l,
                    "top": t,
                    "right": r,
                    "bottom": b,
                    "original_width": orig_w,
                    "original_height": orig_h,
                },
                f,
            )

        # crop the image
        cropped = img[t:b, l:r]

        # get segmentation mask
        mask = segment(cropped)

        # Prepare person results format for mmpose
        person_results = [
            {"bbox": detection_results[0]["bbox"] + [detection_results[0]["score"]]}
        ]

        # Run pose estimation on cropped image
        pose_results, _ = inference_top_down_pose_model(
            pose_estimator,
            cropped,
            person_results=None,  # Use None to get all poses in the image
            format="xyxy",
        )

        # if no skeleton detected, abort
        if len(pose_results) == 0:
            msg = "Could not detect any skeletons within the character bounding box. Expected exactly 1. Aborting."
            logging.critical(msg)
            assert False, msg

        # if more than one skeleton detected,
        if 1 < len(pose_results):
            msg = f"Detected {len(pose_results)} skeletons with the character bounding box. Expected exactly 1. Aborting."
            logging.critical(msg)
            assert False, msg

        # get x y coordinates of detection joint keypoints
        kpts = pose_results[0]["keypoints"][:, :2]

        # use them to build character skeleton rig
        skeleton = []
        skeleton.append(
            {
                "loc": [round(x) for x in (kpts[11] + kpts[12]) / 2],
                "name": "root",
                "parent": None,
            }
        )
        skeleton.append(
            {
                "loc": [round(x) for x in (kpts[11] + kpts[12]) / 2],
                "name": "hip",
                "parent": "root",
            }
        )
        skeleton.append(
            {
                "loc": [round(x) for x in (kpts[5] + kpts[6]) / 2],
                "name": "torso",
                "parent": "hip",
            }
        )
        skeleton.append(
            {"loc": [round(x) for x in kpts[0]], "name": "neck", "parent": "torso"}
        )
        skeleton.append(
            {
                "loc": [round(x) for x in kpts[6]],
                "name": "right_shoulder",
                "parent": "torso",
            }
        )
        skeleton.append(
            {
                "loc": [round(x) for x in kpts[8]],
                "name": "right_elbow",
                "parent": "right_shoulder",
            }
        )
        skeleton.append(
            {
                "loc": [round(x) for x in kpts[10]],
                "name": "right_hand",
                "parent": "right_elbow",
            }
        )
        skeleton.append(
            {
                "loc": [round(x) for x in kpts[5]],
                "name": "left_shoulder",
                "parent": "torso",
            }
        )
        skeleton.append(
            {
                "loc": [round(x) for x in kpts[7]],
                "name": "left_elbow",
                "parent": "left_shoulder",
            }
        )
        skeleton.append(
            {
                "loc": [round(x) for x in kpts[9]],
                "name": "left_hand",
                "parent": "left_elbow",
            }
        )
        skeleton.append(
            {"loc": [round(x) for x in kpts[12]], "name": "right_hip", "parent": "root"}
        )
        skeleton.append(
            {
                "loc": [round(x) for x in kpts[14]],
                "name": "right_knee",
                "parent": "right_hip",
            }
        )
        skeleton.append(
            {
                "loc": [round(x) for x in kpts[16]],
                "name": "right_foot",
                "parent": "right_knee",
            }
        )
        skeleton.append(
            {"loc": [round(x) for x in kpts[11]], "name": "left_hip", "parent": "root"}
        )
        skeleton.append(
            {
                "loc": [round(x) for x in kpts[13]],
                "name": "left_knee",
                "parent": "left_hip",
            }
        )
        skeleton.append(
            {
                "loc": [round(x) for x in kpts[15]],
                "name": "left_foot",
                "parent": "left_knee",
            }
        )

        # Add original coordinates to the skeleton
        for joint in skeleton:
            cropped_loc = joint["loc"]
            joint["loc_original"] = [
                round(l + cropped_loc[0]),
                round(t + cropped_loc[1]),
            ]

        # create the character config dictionary
        char_cfg = {
            "skeleton": skeleton,
            "height": cropped.shape[0],  # Cropped image height
            "width": cropped.shape[1],  # Cropped image width
            "bbox_origin_x": l,  # BBox top-left X in original (potentially resized) image
            "bbox_origin_y": t,  # BBox top-left Y in original (potentially resized) image
            "bbox_origin_r": r,  # BBox right in original (potentially resized) image
            "bbox_origin_b": b,  # BBox bottom in original (potentially resized) image
            "resize_scale": scale,  # Scale factor applied to original image (1.0 if no resize)
        }

        # convert texture to RGBA and save
        cropped = cv2.cvtColor(cropped, cv2.COLOR_BGR2BGRA)
        cv2.imwrite(str(outdir / "texture.png"), cropped)

        # save mask
        cv2.imwrite(str(outdir / "mask.png"), mask)

        # dump character config to yaml
        char_cfg_path = outdir / "char_cfg.yaml"
        with open(char_cfg_path, "w") as f:
            yaml.dump(char_cfg, f)

        # create joint viz overlay for inspection purposes
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

        logger.info(f"Annotation generation complete for {img_fn}. Output at {outdir}")

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
            f"Error during image_to_annotations for {img_fn}: {e}", exc_info=True
        )
        return None


def segment(img: np.ndarray) -> np.ndarray:
    """threshold"""
    img = np.min(img, axis=2)
    img = cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 115, 8
    )
    img = cv2.bitwise_not(img)

    """ morphops """
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel, iterations=2)
    img = cv2.morphologyEx(img, cv2.MORPH_DILATE, kernel, iterations=2)

    """ floodfill """
    mask = np.zeros([img.shape[0] + 2, img.shape[1] + 2], np.uint8)
    mask[1:-1, 1:-1] = img.copy()

    # im_floodfill is results of floodfill. Starts off all white
    im_floodfill = np.full(img.shape, 255, np.uint8)

    # choose 10 points along each image side. use as seed for floodfill.
    h, w = img.shape[:2]
    for x in range(0, w - 1, 10):
        cv2.floodFill(im_floodfill, mask, (x, 0), 0)
        cv2.floodFill(im_floodfill, mask, (x, h - 1), 0)
    for y in range(0, h - 1, 10):
        cv2.floodFill(im_floodfill, mask, (0, y), 0)
        cv2.floodFill(im_floodfill, mask, (w - 1, y), 0)

    # make sure edges aren't character. necessary for contour finding
    im_floodfill[0, :] = 0
    im_floodfill[-1, :] = 0
    im_floodfill[:, 0] = 0
    im_floodfill[:, -1] = 0

    """ retain largest contour """
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
        msg = "Found no contours within image"
        logging.critical(msg)
        assert False, msg

    mask = ndimage.binary_fill_holes(mask).astype(int)
    mask = 255 * mask.astype(np.uint8)

    return mask.T


if __name__ == "__main__":
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True, parents=True)
    # Configure logging simply for the __main__ test
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "image_to_annotations_main.log"),
            logging.StreamHandler(),  # Also print to console for __main__
        ],
    )
    logger_main = logging.getLogger(__name__)

    if len(sys.argv) < 2:
        logger_main.error(
            "Usage: python image_to_annotations.py <image_path> [output_base_dir]"
        )
        sys.exit(1)

    img_fn_arg = sys.argv[1]

    # The script now manages its own output directory within the temp system
    # The second argument is no longer used for output path by image_to_annotations itself.

    logger_main.info(f"Running image_to_annotations for image: {img_fn_arg}")
    annotation_results = image_to_annotations(img_fn_arg)

    if annotation_results:
        logger_main.info(
            f"Successfully generated annotations. Results: {annotation_results}"
        )
        # Example: print path to char_cfg.yaml
        # print(f"Character config: {annotation_results['char_cfg_path']}")
    else:
        logger_main.error(f"Failed to generate annotations for {img_fn_arg}")
