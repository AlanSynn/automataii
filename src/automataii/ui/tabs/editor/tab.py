# src/automataii/ui/tabs/editor/tab.py

import logging
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import QGraphicsScene, QHBoxLayout

from automataii.ui.tabs.base.tab import BaseTab
from automataii.ui.views.editor.view import EditorView

from automataii.ui.views.editor.state_manager import EditorMode

from .action_handler import EditorActionHandler
from .scene_manager import EditorSceneManager
from .state_manager import EditorStateManager
from .ui_panel import EditorControlPanel

logger = logging.getLogger(__name__)


class EditorTab(BaseTab):
    """The main widget for the Editor Tab, orchestrating all components."""

    # Signals expected by main_window.py
    request_play_simulation = pyqtSignal()
    request_stop_simulation = pyqtSignal()
    request_reset_simulation = pyqtSignal()
    request_generate_blueprint = pyqtSignal()
    path_data_changed = pyqtSignal(dict)  # Dictionary of all path data
    motion_path_updated = pyqtSignal(str, QPainterPath)  # part_name, motion_qpath

    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self._setup_components()
        self._connect_components()
        logger.info("EditorTab initialized with new architecture.")

    def _setup_components(self):
        self.scene = QGraphicsScene(self)
        self.view = EditorView(self.scene, self)
        self.state = EditorStateManager(self)
        self.scene_manager = EditorSceneManager(self.scene, self.state, self)
        self.action_handler = EditorActionHandler(self.state, self.scene_manager, self)
        self.ui_panel = EditorControlPanel(self)

        # Create horizontal layout for editor
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(self._design_system.spacing.md)
        main_layout.addWidget(self.ui_panel)
        main_layout.addWidget(self.view, 1)

    def _connect_components(self):
        # UI Panel -> State/Action Handlers
        self.ui_panel.part_selected.connect(self.state.set_selected_part)
        self.ui_panel.start_drawing_clicked.connect(self._toggle_drawing_mode)
        self.ui_panel.clear_path_clicked.connect(self.action_handler.handle_clear_motion_path)
        self.ui_panel.path_closed_changed.connect(self._handle_path_closed_changed)
        self.ui_panel.play_clicked.connect(self.action_handler.handle_play_simulation)
        self.ui_panel.stop_clicked.connect(self.action_handler.handle_stop_simulation)
        self.ui_panel.reset_clicked.connect(self.action_handler.handle_reset_simulation)
        self.ui_panel.smoothness_changed.connect(self._handle_smoothness_changed)
        self.ui_panel.zoom_in_clicked.connect(self.view.zoom_in)
        self.ui_panel.zoom_out_clicked.connect(self.view.zoom_out)
        self.ui_panel.zoom_fit_clicked.connect(self.view.zoom_to_fit)

        # State -> UI Panel
        self.state.state_changed.connect(lambda: self.ui_panel.update_ui_from_state(self.state))
        self.state.state_changed.connect(self._handle_state_changed)

        # View -> Action Handler
        self.view.freehandPathCompleted.connect(self.action_handler.handle_freehand_path_completed)
        self.view.part_item_clicked.connect(self._handle_part_clicked)

        # Action Handler -> EditorTab signals (for main window)
        self.action_handler.request_play_simulation.connect(self.request_play_simulation.emit)
        self.action_handler.request_stop_simulation.connect(self.request_stop_simulation.emit)
        self.action_handler.request_reset_simulation.connect(self.request_reset_simulation.emit)
        self.action_handler.motion_path_updated.connect(self.motion_path_updated.emit)

    def _handle_state_changed(self):
        """Handle when the editor state changes."""
        # Reset button state when not in motion path mode
        current_mode = getattr(self.state, 'current_mode', None)
        if current_mode != EditorMode.MOTION_PATH:
            if self.ui_panel.define_motion_path_btn.isChecked():
                self.ui_panel.define_motion_path_btn.setChecked(False)
                logger.debug("Reset motion path button state")

    def _handle_part_clicked(self, part_item):
        """Handle when a part item is clicked in the view."""
        logger.info(f"PART_CLICK: Part item clicked: {part_item}")
        if part_item and part_item.part_info:
            part_name = part_item.part_info.name
            logger.info(f"PART_CLICK: Setting selected part to: {part_name}")
            self.state.set_selected_part(part_name)
            logger.info(f"PART_CLICK: Selected part name is now: {self.state.selected_part_name}")
        else:
            logger.warning(f"PART_CLICK: Invalid part item or missing part_info. Item: {part_item}, has part_info: {hasattr(part_item, 'part_info') if part_item else False}")

    def _toggle_drawing_mode(self, checked: bool):
        logger.info(f"TOGGLE_DRAWING: Drawing mode toggled to: {checked}")
        logger.info(f"TOGGLE_DRAWING: Current selected part: {self.state.selected_part_name}")
        
        if checked and self.state.selected_part_name:
            logger.info(f"TOGGLE_DRAWING: Starting motion path for part: {self.state.selected_part_name}")
            logger.debug(f"Available items in scene: {list(self.scene_manager.current_editor_items.keys())}")
            
            target_item = self.scene_manager.current_editor_items.get(self.state.selected_part_name)
            if target_item:
                logger.info(f"TOGGLE_DRAWING: Found target item: {target_item}")
                # IMPORTANT: Set the selected part in the view's state before entering motion path mode
                self.view.state.set_selected_part(self.state.selected_part_name, target_item)
                logger.info(f"TOGGLE_DRAWING: Set view state selected part to: {self.state.selected_part_name}")
                
                self.view.set_mode("motion_path")
                self.view.start_define_motion_path(target_item)
            else:
                logger.warning(f"No target item found for part: {self.state.selected_part_name}")
                # Reset button state
                self.ui_panel.define_motion_path_btn.setChecked(False)
        elif checked:
            logger.warning("TOGGLE_DRAWING: Cannot start motion path drawing: no part selected")
            # Uncheck the button since we can't start drawing mode
            self.ui_panel.define_motion_path_btn.setChecked(False)
        else:
            logger.info("TOGGLE_DRAWING: Exiting motion path mode")
            self.view.set_mode("pan_zoom")

    def _handle_path_closed_changed(self, closed: bool):
        """Handle when the closed path checkbox is toggled."""
        # Update the motion path mode with the closed setting
        if hasattr(self.view, "input_handler") and self.view.input_handler:
            motion_path_mode = self.view.input_handler._modes.get(EditorMode.MOTION_PATH)
            if motion_path_mode and hasattr(motion_path_mode, "set_closed_path"):
                motion_path_mode.set_closed_path(closed)
        logger.debug(f"Motion path closed setting changed to: {closed}")

    def _handle_smoothness_changed(self, value: int):
        """Handle when the smoothness slider value changes."""
        # Update the motion path mode with the smoothness setting
        if hasattr(self.view, "input_handler") and self.view.input_handler:
            motion_path_mode = self.view.input_handler._modes.get(EditorMode.MOTION_PATH)
            if motion_path_mode and hasattr(motion_path_mode, "set_smoothness"):
                motion_path_mode.set_smoothness(value)

        # Also update any existing paths for the selected part
        if self.state.selected_part_name and self.state.selected_part_name in self.state.path_data:
            self.action_handler.handle_smoothness_changed(self.state.selected_part_name, value)

        logger.debug(f"Motion path smoothness changed to: {value}%")

    # Public API
    def set_parts_data(self, parts_info):
        project_dir = self.main_window.project_data_manager.project_dir
        # Convert to Path object for scene_manager which expects Path type
        if project_dir and not isinstance(project_dir, Path):
            project_dir = Path(project_dir)
        self.state.set_parts_data(parts_info)
        self.scene_manager.set_parts_data(parts_info, project_dir)

    def cache_initial_skeleton(self, skeleton_data):
        self.state.cache_initial_skeleton(skeleton_data)
        self.scene_manager.position_parts_at_anchor_joints()
        self.scene_manager.ensure_skeleton_visualization()  # Add skeleton visualization

    def handle_ik_update(self, ik_results):
        self.scene_manager.update_visuals_from_animation_data(ik_results)

    def clear_editor_content(self):
        self.state.clear_all()
        self.scene_manager.clear_scene()

    def on_simulation_state_changed(self, is_playing: bool, can_reset: bool = True):
        """Handle simulation state changes from the kinematics system."""
        # Convert boolean state to string format
        if is_playing:
            state = "playing"
        elif can_reset:
            state = "stopped"
        else:
            state = "idle"
            
        # Update the internal state
        self.state.set_simulation_state(state)
        
        # UI will be updated automatically through the state_changed signal
        logger.debug(f"EditorTab: Simulation state changed to: {state} (playing={is_playing}, can_reset={can_reset})")

    def toggle_part_properties_panel_visibility(self, visible: bool):
        """Toggle the visibility of the part properties panel."""
        if hasattr(self.ui_panel, "toggle_part_properties_visibility"):
            self.ui_panel.toggle_part_properties_visibility(visible)

    def activate_tab(self) -> None:
        """Called when the tab becomes active."""
        super().activate_tab()  # Call parent to apply theme styles
        logger.debug("EditorTab activated")
        # Resume any animations or background tasks
        if self.action_handler:
            self.action_handler.resume_animations()

        # Scene will be updated automatically through signals

    def deactivate_tab(self) -> None:
        """Called when the tab becomes inactive."""
        logger.debug("EditorTab deactivated")
        # Pause any animations to save resources
        if self.action_handler:
            self.action_handler.pause_animations()

        # Clear any temporary graphics items and motion paths
        if self.scene:
            # Remove temporary items like motion path overlays
            temp_items = [
                item
                for item in self.scene.items()
                if hasattr(item, "is_temporary") and item.is_temporary
            ]
            for item in temp_items:
                self.scene.removeItem(item)
                if hasattr(item, "deleteLater"):
                    item.deleteLater()

        # Clear any active tool states
        if self.view and hasattr(self.view, "input_handler"):
            self.view.input_handler.clear_active_state()

        # Force garbage collection for this tab's resources
        import gc

        gc.collect()
