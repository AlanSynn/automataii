"""Animation and IK-related operations coordination for the main window."""

import logging
from typing import TYPE_CHECKING, Dict, Any, Optional, Tuple

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import pyqtSlot, QPointF, QObject
from PyQt6.QtGui import QPainterPath

if TYPE_CHECKING:
    from .main_window import AutomataDesigner


class AnimationCoordinator(QObject):
    """Coordinates animation and IK-related operations."""
    
    def __init__(self, main_window: 'AutomataDesigner'):
        super().__init__()
        self.main_window = main_window
        
    @pyqtSlot(dict)
    def on_skeleton_manager_updated(self, standardized_skeleton_data_dict: Optional[dict]):
        """Slot called when SkeletonManager has new processed skeleton data."""
        logging.info(
            "MainWindow: SkeletonManager updated. Notifying tabs. IKManager will handle its own re-initialization if needed."
        )
        
        # Cache the initial skeleton data in EditorTab
        if hasattr(self.main_window.editor_tab, "cache_initial_skeleton"):
            self.main_window.editor_tab.cache_initial_skeleton(standardized_skeleton_data_dict)
        else:
            logging.warning(
                "MainWindow: EditorTab does not have cache_initial_skeleton method."
            )
        
        # Notify tabs that might need the direct standardized skeleton data for display
        if hasattr(self.main_window.image_proc_tab, "on_skeleton_updated_externally"):
            self.main_window.image_proc_tab.on_skeleton_updated_externally(
                standardized_skeleton_data_dict
            )
        
        if hasattr(self.main_window.editor_tab, "on_skeleton_updated"):
            self.main_window.editor_tab.on_skeleton_updated(standardized_skeleton_data_dict)
        
        # Update status bar
        self.update_status_bar_with_skeleton_info(standardized_skeleton_data_dict)
    
    def update_status_bar_with_skeleton_info(self, skeleton_data_dict: Optional[dict]):
        """Update status bar with skeleton information."""
        if skeleton_data_dict and skeleton_data_dict.get("joints"):
            num_joints = len(skeleton_data_dict.get("joints", {}))
            self.main_window.statusBar().showMessage(
                f"Skeleton loaded/updated: {num_joints} joints.", 3000
            )
        else:
            self.main_window.statusBar().showMessage("Skeleton cleared or not loaded.", 3000)
    
    @pyqtSlot(dict)
    def handle_ik_visuals_update(self, part_transforms: Dict[str, Dict[str, Any]]):
        """Handles updates to part visuals from the IKManager."""
        if self.main_window.editor_tab:
            self.main_window.editor_tab.handle_ik_update(part_transforms)
    
    @pyqtSlot(dict)
    def handle_skeleton_pose_updated_from_ik(
        self, animated_pose_data_dict: Dict[str, Tuple[float, float]]
    ):
        """Handles the raw animated skeleton pose update from IKManager."""
        logging.debug(
            f"MainWindow:handle_skeleton_pose_updated_from_ik - Received animated_pose_data_dict (count: {len(animated_pose_data_dict)})"
        )
        if self.main_window.editor_tab and self.main_window.editor_tab.editor_view:
            self.main_window.editor_tab.editor_view.update_skeleton_animation(
                animated_pose_data_dict
            )
        else:
            logging.warning(
                "MainWindow: Cannot relay skeleton pose update, EditorTab or EditorView not available."
            )
    
    @pyqtSlot(str, QPainterPath)
    def handle_part_motion_path_update_from_editor_tab(
        self, part_name: str, motion_qpath: QPainterPath
    ):
        """Handles the motion_path_updated signal from EditorTab and passes it to IKManager."""
        if not self.main_window.ik_manager:
            logging.warning(
                "MainWindow: IKManager not available to handle motion path update."
            )
            return
        if hasattr(self.main_window.ik_manager, "update_part_motion_path"):
            self.main_window.ik_manager.update_part_motion_path(part_name, motion_qpath)
            logging.info(
                f"MainWindow: Relayed motion path update for '{part_name}' to IKManager."
            )
        else:
            logging.warning(
                "MainWindow: IKManager does not have 'update_part_motion_path' method."
            )
    
    @pyqtSlot(str, dict)
    def handle_generate_mechanism_request(self, mechanism_type: str, params: dict):
        """Handle mechanism generation request."""
        logging.info(
            f"MainWindow: Received request to generate mechanism: {mechanism_type} with params {params}"
        )
        target_part_name = params.get("target_part_name")
        if not target_part_name:
            QMessageBox.warning(
                self.main_window,
                "Mechanism Error",
                "No target part specified for mechanism generation.",
            )
            return
        
        current_parts_data = self.main_window.project_data_manager.get_current_parts_data()
        if not current_parts_data or target_part_name not in current_parts_data:
            QMessageBox.warning(
                self.main_window,
                "Mechanism Error",
                f"Target part '{target_part_name}' not found in project data.",
            )
            return
        
        target_part_info = current_parts_data[target_part_name]
        
        # Get editor scene reference point
        editor_scene_ref_point = QPointF(target_part_info.x, target_part_info.y)
        if self.main_window.editor_tab and self.main_window.editor_tab.editor_view:
            scene_rect = self.main_window.editor_tab.editor_view.sceneRect()
            editor_scene_ref_point = scene_rect.center()
        
        mechanism_data = self.main_window.mechanism_manager.generate_mechanism(
            mechanism_type=mechanism_type,
            params=params,
            target_part_info=target_part_info,
            all_parts_info=current_parts_data,
            editor_scene_center=editor_scene_ref_point,
        )
        
        self.main_window.statusBar().showMessage(
            f"Mechanism generation initiated for {target_part_name}: {mechanism_type}"
        )
        
        # Notify mechanism generation tab about the new mechanism
        if mechanism_data and hasattr(self.main_window, 'mechanism_generation_tab'):
            self.main_window.mechanism_generation_tab.on_mechanism_generated(mechanism_data)
    
    @pyqtSlot()
    def reset_all_animations_button_clicked(self):
        """Reset all animation paths and poses."""
        logging.info("MainWindow: Resetting all animation paths and poses.")
        
        # Clear motion path data
        if hasattr(self.main_window.project_data_manager, "clear_all_motion_paths"):
            self.main_window.project_data_manager.clear_all_motion_paths()
        else:
            logging.warning(
                "ProjectDataManager does not have clear_all_motion_paths method."
            )
            # Fallback to old direct manipulation
            current_parts_data = self.main_window.project_data_manager.get_current_parts_data()
            if current_parts_data:
                for part_info in current_parts_data.values():
                    if hasattr(part_info, "motion_path_data"):
                        part_info.motion_path_data = None
                    if hasattr(part_info, "motion_path"):
                        part_info.motion_path = []
            else:
                logging.warning("Cannot clear motion path data: No parts data loaded.")
        
        # Instruct EditorTab to clear its visual motion paths
        if self.main_window.editor_tab and hasattr(
            self.main_window.editor_tab, "clear_all_visual_motion_paths"
        ):
            self.main_window.editor_tab.clear_all_visual_motion_paths()
        else:
            logging.warning(
                "EditorTab or its clear_all_visual_motion_paths method not found."
            )
        
        # Reset character pose to initial skeleton definition
        self.main_window.ik_manager.reset_animation_state()
        
        # Update EditorTab's view and button states
        if self.main_window.editor_tab:
            if hasattr(self.main_window.editor_tab, "editor_view") and hasattr(
                self.main_window.editor_tab.editor_view, "update_view"
            ):
                self.main_window.editor_tab.editor_view.update_view()
            if hasattr(self.main_window.editor_tab, "_update_button_states"):
                self.main_window.editor_tab._update_button_states()
        
        self.main_window.statusBar().showMessage("All animation paths and character poses reset.")