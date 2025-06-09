"""
Processing Service - Handles image processing operations
"""
import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import QProgressDialog, QMessageBox, QApplication
from PyQt6.QtCore import Qt

from automataii.processing.vision.annotations import image_to_annotations, AnnotationResults
from automataii.processing.vision.adaptive_annotations import image_to_annotations_adaptive
from automataii.utils.config import AppConfig


class ProcessingService:
    """Service for handling image processing operations."""

    def __init__(self, parent=None):
        self.parent = parent

    def process_image(self, input_image_path: str) -> Optional[AnnotationResults]:
        """
        Process the input image using image_to_annotations.

        Args:
            input_image_path: Path to the input image

        Returns:
            AnnotationResults or None if processing failed
        """
        if not input_image_path:
            QMessageBox.warning(
                self.parent,
                "Warning",
                "No input image path provided."
            )
            return None

        progress_dialog = QProgressDialog(
            "Processing image, please wait...",
            None,
            0,
            0,
            self.parent
        )
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setCancelButton(None)
        progress_dialog.show()
        QApplication.processEvents()

        try:
            # TODO: Use adaptive annotations if non-human support is enabled
            # if AppConfig.ENABLE_NON_HUMAN_SKELETONS:
            #     annotation_results = image_to_annotations_adaptive(input_image_path)
            # else:
            #     # Use standard human skeleton extraction
            annotation_results = image_to_annotations(input_image_path)

            if annotation_results and annotation_results.get("char_cfg_path"):
                logging.info(
                    f"Image processing successful. Results: {annotation_results}"
                )
                return annotation_results
            else:
                logging.error("Image processing failed - no results returned")
                QMessageBox.critical(
                    self.parent,
                    "Error",
                    "Image processing failed to generate annotations."
                )
                return None

        except Exception as e:
            logging.error(f"Error during image processing: {e}", exc_info=True)
            QMessageBox.critical(
                self.parent,
                "Processing Error",
                f"An unexpected error occurred: {e}"
            )
            return None

        finally:
            progress_dialog.close()