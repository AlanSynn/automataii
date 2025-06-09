"""
Skeleton Service - Handles skeleton loading, editing, and saving operations
"""
import os
import logging
import yaml
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox, QLabel
from PyQt6.QtCore import Qt


class SkeletonService:
    """Service for handling skeleton-related operations."""
    
    def __init__(self, parent=None):
        self.parent = parent
        
    def load_skeleton_from_file(self, char_cfg_filepath: str) -> Optional[Dict[str, Any]]:
        """
        Load skeleton data from a YAML file.
        
        Args:
            char_cfg_filepath: Path to the character config file
            
        Returns:
            Skeleton data dictionary or None if loading failed
        """
        if not char_cfg_filepath or not os.path.exists(char_cfg_filepath):
            if char_cfg_filepath:
                logging.warning(f"Skeleton file not found: {char_cfg_filepath}")
                QMessageBox.warning(
                    self.parent,
                    "Load Error",
                    f"Skeleton file not found: {os.path.basename(char_cfg_filepath)}"
                )
            return None
            
        try:
            with open(char_cfg_filepath, "r") as f:
                loaded_skeleton_data = yaml.safe_load(f)
                
            if not loaded_skeleton_data or "skeleton" not in loaded_skeleton_data:
                raise ValueError("Invalid or empty skeleton file format.")
                
            logging.info(f"Skeleton loaded from {char_cfg_filepath}")
            return loaded_skeleton_data
            
        except Exception as e:
            logging.error(
                f"Failed to load skeleton from {char_cfg_filepath}: {e}",
                exc_info=True
            )
            QMessageBox.critical(
                self.parent,
                "Load Skeleton Error",
                f"Failed to load skeleton: {e}"
            )
            return None
            
    def save_skeleton(self, skeleton_data: Dict[str, Any], character_dir: Optional[str] = None) -> Optional[str]:
        """
        Save skeleton data to a YAML file.
        
        Args:
            skeleton_data: Skeleton data to save
            character_dir: Default directory for save dialog
            
        Returns:
            Path where skeleton was saved or None if cancelled/failed
        """
        if not skeleton_data:
            QMessageBox.warning(
                self.parent,
                "Save Error",
                "No skeleton data to save."
            )
            return None
            
        default_path = (
            os.path.join(character_dir, "char_cfg.yaml")
            if character_dir
            else "char_cfg.yaml"
        )
        
        save_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            "Save Skeleton As",
            default_path,
            "YAML Files (*.yaml *.yml)"
        )
        
        if not save_path:
            return None
            
        try:
            with open(save_path, "w") as f:
                yaml.dump(skeleton_data, f, default_flow_style=None, sort_keys=False)
                
            logging.info(f"Skeleton saved to {save_path}")
            return save_path
            
        except Exception as e:
            logging.error(f"Failed to save skeleton: {e}", exc_info=True)
            QMessageBox.critical(
                self.parent,
                "Save Skeleton Error",
                f"Could not save skeleton: {e}"
            )
            return None
            
    def extend_skeleton(self, skeleton_manager, factor: float = 1.1) -> bool:
        """
        Extend skeleton bone lengths by a factor.
        
        Args:
            skeleton_manager: Skeleton manager instance
            factor: Extension factor (default 1.1 for 10% increase)
            
        Returns:
            True if successful, False otherwise
        """
        if not skeleton_manager or not skeleton_manager.standardized_model:
            QMessageBox.warning(
                self.parent,
                "Extend Skeleton",
                "No skeleton loaded to extend."
            )
            return False
            
        # Confirm action with user
        reply = QMessageBox.question(
            self.parent,
            "Extend Skeleton",
            f"This will increase all skeleton bone lengths by {int((factor - 1) * 100)}%. "
            "This action cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if skeleton_manager.extend_skeleton_lengths(factor):
                QMessageBox.information(
                    self.parent,
                    "Extend Skeleton",
                    f"Skeleton lengths extended by {int((factor - 1) * 100)}% successfully."
                )
                return True
            else:
                QMessageBox.critical(
                    self.parent,
                    "Extend Skeleton",
                    "Failed to extend skeleton lengths."
                )
                return False
                
        return False
        
    def show_lock_joints_dialog(self, skeleton_manager) -> bool:
        """
        Show dialog for locking/unlocking joints.
        
        Args:
            skeleton_manager: Skeleton manager instance
            
        Returns:
            True if changes were made, False otherwise
        """
        if not skeleton_manager or not skeleton_manager.standardized_model:
            QMessageBox.warning(
                self.parent,
                "Lock/Unlock Joints",
                "No skeleton loaded."
            )
            return False
            
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Lock/Unlock Joints")
        dialog.setModal(True)
        dialog.resize(300, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Add instructions
        label = QLabel("Check joints to lock them during IK solving:")
        layout.addWidget(label)
        
        # Create list widget with checkable items
        list_widget = QListWidget()
        
        # Add all joints to the list
        skeleton_model = skeleton_manager.standardized_model
        for joint_id, joint in skeleton_model.joints.items():
            item = QListWidgetItem(f"{joint.name} ({joint_id})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if joint.is_locked else Qt.CheckState.Unchecked
            )
            item.setData(Qt.ItemDataRole.UserRole, joint_id)
            list_widget.addItem(item)
            
        layout.addWidget(list_widget)
        
        # Add buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(button_box)
        
        changes_made = False
        
        def accept_changes():
            nonlocal changes_made
            # Update joint lock states
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                joint_id = item.data(Qt.ItemDataRole.UserRole)
                is_locked = item.checkState() == Qt.CheckState.Checked
                skeleton_manager.lock_joint(joint_id, is_locked)
                
            changes_made = True
            dialog.accept()
            
        button_box.accepted.connect(accept_changes)
        button_box.rejected.connect(dialog.reject)
        
        dialog.exec()
        return changes_made