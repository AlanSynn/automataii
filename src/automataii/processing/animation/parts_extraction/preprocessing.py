"""Image preprocessing utilities for body parts extraction."""

from typing import Tuple, Optional
import cv2
import numpy as np


class ImagePreprocessor:
    """Handles image preprocessing operations."""
    
    @staticmethod
    def calculate_scale_factor(image_shape: Tuple[int, int], 
                             max_dimension: int = 1024) -> float:
        """Calculate optimal scale factor based on image dimensions.
        
        Args:
            image_shape: (height, width) of the image
            max_dimension: Maximum dimension to scale to
            
        Returns:
            Scale factor to apply
        """
        max_dim = max(image_shape)
        
        if max_dim > max_dimension:
            return 512.0 / max_dim
        elif max_dim > 512:
            return 0.7
        else:
            return 1.0
    
    @staticmethod
    def resize_image(image: np.ndarray, scale_factor: float) -> np.ndarray:
        """Resize image by scale factor.
        
        Args:
            image: Input image
            scale_factor: Scale factor to apply
            
        Returns:
            Resized image
        """
        if scale_factor == 1.0:
            return image
            
        height, width = image.shape[:2]
        new_height = int(height * scale_factor)
        new_width = int(width * scale_factor)
        
        return cv2.resize(
            image,
            (new_width, new_height),
            interpolation=cv2.INTER_NEAREST
        )
    
    @staticmethod
    def create_coordinate_grids(height: int, width: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Create coordinate grids for vectorized operations.
        
        Args:
            height: Image height
            width: Image width
            
        Returns:
            Tuple of (y_grid, x_grid, flattened_coords)
        """
        y_grid, x_grid = np.mgrid[0:height, 0:width]
        coords = np.column_stack([x_grid.ravel(), y_grid.ravel()])
        
        return y_grid, x_grid, coords
    
    @staticmethod
    def clean_mask(mask: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        """Clean up a binary mask using morphological operations.
        
        Args:
            mask: Binary mask to clean
            kernel_size: Size of morphological kernel
            
        Returns:
            Cleaned mask
        """
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.medianBlur(mask, 3)
        
        return mask
    
    @staticmethod
    def extract_bounding_box(mask: np.ndarray, padding: int = 3) -> Optional[Tuple[int, int, int, int]]:
        """Extract bounding box from mask with padding.
        
        Args:
            mask: Binary mask
            padding: Padding to add around bounding box
            
        Returns:
            Tuple of (x, y, width, height) or None if mask is empty
        """
        points = cv2.findNonZero(mask)
        if points is None:
            return None
            
        x, y, w, h = cv2.boundingRect(points)
        
        # Add padding
        height, width = mask.shape
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(width - x, w + 2 * padding)
        h = min(height - y, h + 2 * padding)
        
        if w == 0 or h == 0:
            return None
            
        return x, y, w, h
    
    @staticmethod
    def prepare_rgba_image(image: np.ndarray, alpha_channel: Optional[np.ndarray] = None) -> np.ndarray:
        """Convert image to RGBA format with optional alpha channel.
        
        Args:
            image: Input image (grayscale, BGR, or BGRA)
            alpha_channel: Optional alpha channel to apply
            
        Returns:
            RGBA image
        """
        if image.ndim == 2:
            # Grayscale to BGRA
            bgr_texture = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            bgra_image = cv2.cvtColor(bgr_texture, cv2.COLOR_BGR2BGRA)
        elif image.shape[2] == 3:
            # BGR to BGRA
            bgra_image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
        else:
            # Already BGRA
            bgra_image = image.copy()
            
        # Apply alpha channel if provided
        if bgra_image.shape[2] == 4 and alpha_channel is not None:
            bgra_image[:, :, 3] = alpha_channel
            
        return bgra_image