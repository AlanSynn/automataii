"""
Parts Service - Handles body parts generation
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from PyQt6.QtWidgets import QProgressDialog, QMessageBox, QApplication
from PyQt6.QtCore import Qt

from automataii.processing.animation.body_parts_extractor import BodyPartsExtractor


class PartsService:
    """Service for handling body parts generation."""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.body_parts_extractor = None
        
    def generate_parts(
        self,
        annotation_results: Dict[str, Any],
        current_temp_char_dir: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate body parts from skeleton and image data.
        
        Args:
            annotation_results: Results from image annotation
            current_temp_char_dir: Temporary character directory
            
        Returns:
            Tuple of (parts_info_path, output_dir) or (None, None) if failed
        """
        if not self._validate_inputs(annotation_results, current_temp_char_dir):
            return None, None
            
        logging.info(
            f"Creating parts using BodyPartsExtractor. Input char_dir: {current_temp_char_dir}"
        )
        
        progress_dialog = QProgressDialog(
            "Generating body parts...",
            "Cancel",
            0,
            0,
            self.parent
        )
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setAutoClose(True)
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            # Define output directory
            bpe_output_dir = Path(current_temp_char_dir) / "bpe_output"
            bpe_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create extractor
            self.body_parts_extractor = BodyPartsExtractor(
                char_dir=str(current_temp_char_dir),
                output_dir=str(bpe_output_dir)
            )
            
            # Process parts
            self.body_parts_extractor.process()
            
            # Verify output
            expected_parts_info_path = bpe_output_dir / "parts_info.json"
            
            if not expected_parts_info_path.exists():
                logging.error(
                    f"CRITICAL: parts_info.json not found at {expected_parts_info_path}"
                )
                QMessageBox.critical(
                    self.parent,
                    "Parts Generation Error",
                    f"parts_info.json was not created at:\\n{expected_parts_info_path}"
                )
                return None, None
                
            logging.info(
                f"SUCCESS: parts_info.json found at {expected_parts_info_path}"
            )
            
            QMessageBox.information(
                self.parent,
                "Parts Generated",
                "Character parts generated successfully"
            )
            
            return str(expected_parts_info_path), str(bpe_output_dir)
            
        except Exception as e:
            logging.error(
                f"Error during part creation: {e}",
                exc_info=True
            )
            QMessageBox.critical(
                self.parent,
                "Part Creation Error",
                f"An error occurred: {e}"
            )
            return None, None
            
        finally:
            progress_dialog.close()
            
    def _validate_inputs(
        self,
        annotation_results: Dict[str, Any],
        current_temp_char_dir: str
    ) -> bool:
        """Validate inputs for parts generation."""
        if (
            not annotation_results
            or not annotation_results.get("texture_path")
            or not annotation_results.get("char_cfg_path")
            or not current_temp_char_dir
        ):
            QMessageBox.warning(
                self.parent,
                "Missing Data",
                "Cannot create parts. Required data not available. "
                "Please process image first."
            )
            return False
            
        return True