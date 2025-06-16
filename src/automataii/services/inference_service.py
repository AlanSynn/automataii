import cv2
import numpy as np
import onnxruntime as ort
from pathlib import Path

class InferenceService:
    def __init__(self, model_dir: Path):
        """
        Initializes the ONNX inference service.

        Args:
            model_dir: Path to the directory containing 'detector.onnx' and 'pose.onnx'.
        """
        detector_path = model_dir / "detector.onnx"
        pose_path = model_dir / "pose.onnx"

        if not detector_path.exists() or not pose_path.exists():
            raise FileNotFoundError(
                f"ONNX models not found in {model_dir}. "
                "Please run the 'tools/export_to_onnx.sh' script first."
            )

        # Create inference sessions
        self.detector_session = ort.InferenceSession(str(detector_path))
        self.pose_session = ort.InferenceSession(str(pose_path))

        # Get input details
        self.detector_input_name = self.detector_session.get_inputs()[0].name
        self.detector_input_shape = self.detector_session.get_inputs()[0].shape[2:]  # (height, width)

        self.pose_input_name = self.pose_session.get_inputs()[0].name
        self.pose_input_shape = self.pose_session.get_inputs()[0].shape[2:]  # (height, width)

    def _preprocess_image(self, image: np.ndarray, target_shape: tuple) -> np.ndarray:
        """
        Preprocesses an image for ONNX model inference.
        Resizes, normalizes, and transposes the image.
        """
        # Note: This is a generic preprocessing function.
        # You MUST match the exact preprocessing steps used during model training.
        # This often includes specific mean/std normalization and BGR-to-RGB conversion.
        h, w = target_shape
        resized_image = cv2.resize(image, (w, h))

        # Normalize to [0, 1] and convert to CHW format
        input_tensor = resized_image.astype(np.float32) / 255.0
        input_tensor = np.transpose(input_tensor, (2, 0, 1)) # HWC to CHW

        # Add batch dimension
        return np.expand_dims(input_tensor, axis=0)

    def run_detection(self, image: np.ndarray) -> list:
        """
        Runs object detection on the input image.

        Args:
            image: A NumPy array representing the image (H, W, C).

        Returns:
            A list of detected bounding boxes.
            The format of the output depends on the model's post-processing.
        """
        input_tensor = self._preprocess_image(image, self.detector_input_shape)

        # Run inference
        outputs = self.detector_session.run(None, {self.detector_input_name: input_tensor})

        # Post-processing will be required here to decode the model output
        # into bounding boxes, scores, and labels. This is highly model-specific.
        # Example: bboxes = self._postprocess_detection(outputs)
        print("Detector output shape:", [o.shape for o in outputs])
        return outputs # Returning raw output for now

    def run_pose_estimation(self, image: np.ndarray, bboxes: list) -> list:
        """
        Runs pose estimation for the given bounding boxes.

        Args:
            image: A NumPy array representing the image (H, W, C).
            bboxes: A list of bounding boxes from the detector.

        Returns:
            A list of poses. The format is model-specific.
        """
        # For pose estimation, you typically crop the image for each bounding box
        # and run inference on each crop.
        all_poses = []
        for bbox in bboxes:
            # Note: Cropping logic needs to be implemented
            # x1, y1, x2, y2 = bbox
            # cropped_image = image[y1:y2, x1:x2]

            input_tensor = self._preprocess_image(image, self.pose_input_shape)

            outputs = self.pose_session.run(None, {self.pose_input_name: input_tensor})

            # Post-processing is needed to convert output into keypoints.
            print("Pose output shape:", [o.shape for o in outputs])
            all_poses.append(outputs)

        return all_poses

# Example usage (for testing)
if __name__ == '__main__':
    # This assumes you have run the export script and have the onnx models
    # and a sample image file.
    try:
        models_path = Path(__file__).parent.parent / "models" / "onnx"
        service = InferenceService(models_path)

        sample_image_path = "peppa_pig.jpg" # A placeholder, use a real image path
        if Path(sample_image_path).exists():
            img = cv2.imread(sample_image_path)

            # 1. Run detection
            detected_objects = service.run_detection(img)

            # 2. Assume detected_objects are processed into bboxes
            # mock_bboxes = [[10, 10, 100, 150]] # Mock bbox for testing
            # poses = service.run_pose_estimation(img, mock_bboxes)
            # print("Pose estimation complete.")
        else:
            print(f"Sample image not found at {sample_image_path}, skipping example run.")

    except FileNotFoundError as e:
        print(e)