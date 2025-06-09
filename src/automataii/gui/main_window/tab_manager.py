"""Tab management for the main window."""

import logging
from typing import TYPE_CHECKING, Dict, Any
from pathlib import Path

from PyQt6.QtCore import pyqtSlot, QObject
from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from .main_window import AutomataDesigner


class TabManager(QObject):
    """Manages tab switching and tab-related operations."""
    
    def __init__(self, main_window: 'AutomataDesigner'):
        super().__init__()
        self.main_window = main_window
        
    @pyqtSlot(int)
    def on_tab_changed(self, index: int):
        """Handle tab change events."""
        current_tab = self.main_window.tab_widget.widget(index)
        if hasattr(current_tab, "tab_name"):
            self.main_window.statusBar().showMessage(f"{current_tab.tab_name} tab active")
        else:
            self.main_window.statusBar().showMessage(f"Tab {index + 1} active")
        
        # If EditorTab is selected, ensure its view is updated if parts are loaded
        if current_tab == self.main_window.editor_tab:
            if (
                hasattr(self.main_window.editor_tab, "editor_view")
                and self.main_window.editor_tab.editor_view is not None
            ):
                self.main_window.editor_tab.editor_view.zoom_to_fit()
    
    @pyqtSlot()
    def switch_to_editor_tab(self):
        """Switches the main tab widget to the Editor Tab."""
        editor_idx = -1
        for i in range(self.main_window.tab_widget.count()):
            if self.main_window.tab_widget.widget(i) == self.main_window.editor_tab:
                editor_idx = i
                break
        if editor_idx != -1:
            logging.info("Switching to Editor tab by request.")
            self.main_window.tab_widget.setCurrentIndex(editor_idx)
        else:
            logging.warning("Could not find EditorTab to switch to.")
    
    @pyqtSlot()
    def switch_to_mechanism_generation_tab(self):
        """Switches the main tab widget to the Mechanism Generation Tab."""
        mech_idx = -1
        for i in range(self.main_window.tab_widget.count()):
            if self.main_window.tab_widget.widget(i) == self.main_window.mechanism_generation_tab:
                mech_idx = i
                break
        if mech_idx != -1:
            logging.info("Switching to Mechanism Generation tab by request.")
            self.main_window.tab_widget.setCurrentIndex(mech_idx)
        else:
            logging.warning("Could not find MechanismGenerationTab to switch to.")
    
    @pyqtSlot(str)
    def handle_landing_image_selected(self, image_path: str):
        """Handles image selection from the landing tab."""
        logging.info(f"TabManager: Landing tab selected image: {image_path}")
        
        if hasattr(self.main_window, "image_proc_tab") and self.main_window.image_proc_tab is not None:
            logging.info("TabManager: Image processing tab exists, attempting to load image")
            
            # Load the image in the image processing tab
            loaded_successfully = self.main_window.image_proc_tab._load_image_from_path(image_path)
            logging.info(f"TabManager: Image load result: {loaded_successfully}")
            
            if loaded_successfully:
                # Switch to the image processing tab
                for i in range(self.main_window.tab_widget.count()):
                    if self.main_window.tab_widget.widget(i) == self.main_window.image_proc_tab:
                        logging.info(f"TabManager: Switching to image processing tab (index {i})")
                        self.main_window.tab_widget.setCurrentIndex(i)
                        
                        # Force view to update size and zoom after tab switch
                        from PyQt6.QtCore import QTimer
                        def delayed_zoom():
                            if hasattr(self.main_window.image_proc_tab, 'view_manager'):
                                view = self.main_window.image_proc_tab.view_manager.view
                                logging.info(f"TabManager: View size after tab switch: {view.size().width()}x{view.size().height()}")
                                view.zoom_to_fit()
                                logging.info("TabManager: Called zoom_to_fit after tab switch")
                        
                        QTimer.singleShot(100, delayed_zoom)  # Small delay to let UI update
                        
                        logging.info(
                            f"TabManager: Switched to Image Processing Tab and loaded {Path(image_path).name}"
                        )
                        self.main_window.statusBar().showMessage(
                            f"Loaded: {Path(image_path).name}", 3000
                        )
                        # Detailed processing group visibility is now controlled by user preference
                        break
            else:
                logging.error(
                    f"TabManager: Failed to load image {image_path} in ImageProcessingTab."
                )
                QMessageBox.warning(
                    self.main_window,
                    "Image Load Error",
                    f"Could not load the selected image: {Path(image_path).name}",
                )
        else:
            logging.error(
                "TabManager: image_proc_tab is not available or not initialized."
            )
            QMessageBox.critical(
                self.main_window, "Error", "Image Processing Tab is not available."
            )
    
    @pyqtSlot(dict, dict)
    def handle_paths_ready_for_mechanism(self, parts_dict: Dict, paths_dict: Dict):
        """Handle paths ready signal from editor tab and send to mechanism generation tab."""
        logging.info(f"MainWindow: Received {len(parts_dict)} parts and {len(paths_dict)} paths for mechanism generation")
        
        # Get skeleton data if available
        skeleton_data = None
        if hasattr(self.main_window, 'skeleton_manager') and self.main_window.skeleton_manager:
            skeleton_data = self.main_window.skeleton_manager.get_standardized_skeleton_dict()
        
        # Send data to mechanism generation tab
        if hasattr(self.main_window, 'mechanism_generation_tab') and self.main_window.mechanism_generation_tab:
            self.main_window.mechanism_generation_tab.receive_character_and_paths(parts_dict, paths_dict, skeleton_data)