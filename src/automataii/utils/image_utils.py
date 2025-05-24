import cv2
import numpy as np # Potentially useful for type hinting 'image'

def save_image(image: np.ndarray, output_path: str) -> bool:
    """Saves a NumPy array image to the specified path using OpenCV.

    Args:
        image: The image data as a NumPy array.
        output_path: The path to save the image to.

    Returns:
        True if saving was successful, False otherwise.
    """
    if image is not None:
        try:
            cv2.imwrite(output_path, image)
            return True
        except Exception as e:
            # Consider logging the error here
            print(f"Error saving image to {output_path}: {e}")
            return False
    return False