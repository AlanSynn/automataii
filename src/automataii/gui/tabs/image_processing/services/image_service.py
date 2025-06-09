"""
Image Service - Handles image loading and capture operations
"""
import os
import logging
import tempfile
import time
import cv2
from typing import Optional, Tuple

from PyQt6.QtWidgets import QFileDialog, QDialog, QMessageBox

from automataii.gui.dialogs.camera_dialog import CameraDialog


class ImageService:
    """Service for handling image loading and capture operations."""
    
    def __init__(self, parent=None):
        self.parent = parent
        
    def load_image_from_file(self, character_dir: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Load an image from file dialog.
        
        Returns:
            Tuple of (image_path, selected_filter) or (None, None) if cancelled
        """
        filepath, filter_used = QFileDialog.getOpenFileName(
            self.parent,
            "Load Input Image",
            character_dir or "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        
        if not filepath:
            return None, None
            
        if not os.path.exists(filepath):
            QMessageBox.warning(
                self.parent,
                "Load Error",
                f"File not found: {filepath}"
            )
            return None, None
            
        logging.info(f"Image loaded from file: {filepath}")
        return filepath, filter_used
        
    def capture_from_camera(self, active_dialogs: list) -> Optional[str]:
        """
        Capture image from camera.
        
        Args:
            active_dialogs: List to track active camera dialogs
            
        Returns:
            Path to captured image or None if cancelled/failed
        """
        try:
            dialog = CameraDialog(self.parent)
            active_dialogs.append(dialog)
            
            dialog.finished.connect(
                lambda: (
                    active_dialogs.remove(dialog)
                    if dialog in active_dialogs
                    else None
                )
            )
            
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.captured_image is not None:
                return self._save_captured_image(dialog.captured_image)
            
        except Exception as e:
            logging.error(f"Error opening camera dialog: {e}", exc_info=True)
            QMessageBox.critical(
                self.parent,
                "Camera Error",
                f"Could not open camera: {e}"
            )
            
        return None
        
    def _save_captured_image(self, image_data) -> Optional[str]:
        """Save captured image to temporary file."""
        temp_dir = tempfile.gettempdir()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        temp_path = os.path.join(temp_dir, f"automata_capture_{timestamp}.png")
        
        try:
            cv2.imwrite(temp_path, image_data)
            logging.info(f"Captured image saved to {temp_path}")
            return temp_path
        except Exception as e:
            logging.error(f"Failed to save captured image: {e}")
            QMessageBox.critical(
                self.parent,
                "Save Error",
                f"Could not save captured image: {e}"
            )
            return None