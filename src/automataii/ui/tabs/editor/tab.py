# src/automataii/ui/tabs/editor/tab.py

import logging
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import QHBoxLayout, QGraphicsScene
from automataii.ui.tabs.base.tab import BaseTab
from automataii.ui.views.editor_view import EditorView
from .state_manager import EditorStateManager
from .ui_panel import EditorControlPanel
from .scene_manager import EditorSceneManager
from .action_handler import EditorActionHandler

logger = logging.getLogger(__name__)

class EditorTab(BaseTab):
    """The main widget for the Editor Tab, orchestrating all components."""
    
    # Signals expected by main_window.py
    request_play_simulation = pyqtSignal()
    request_stop_simulation = pyqtSignal()
    request_reset_simulation = pyqtSignal()
    request_generate_blueprint = pyqtSignal()
    path_data_changed = pyqtSignal(str, object)  # part_name, path_data
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

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self.ui_panel)
        main_layout.addWidget(self.view, 1)

    def _connect_components(self):
        # UI Panel -> State/Action Handlers
        self.ui_panel.part_selected.connect(self.state.set_selected_part)
        self.ui_panel.start_drawing_clicked.connect(self._toggle_drawing_mode)
        self.ui_panel.clear_path_clicked.connect(self.action_handler.handle_clear_motion_path)
        self.ui_panel.play_clicked.connect(self.action_handler.handle_play_simulation)
        self.ui_panel.stop_clicked.connect(self.action_handler.handle_stop_simulation)
        self.ui_panel.reset_clicked.connect(self.action_handler.handle_reset_simulation)
        self.ui_panel.zoom_in_clicked.connect(self.view.zoom_in)
        self.ui_panel.zoom_out_clicked.connect(self.view.zoom_out)
        self.ui_panel.zoom_fit_clicked.connect(self.view.zoom_to_fit)

        # State -> UI Panel
        self.state.state_changed.connect(lambda: self.ui_panel.update_ui_from_state(self.state))

        # View -> Action Handler
        self.view.freehandPathCompleted.connect(self.action_handler.handle_freehand_path_completed)
        self.view.part_item_clicked.connect(self._handle_part_clicked)
        
        # Action Handler -> EditorTab signals (for main window)
        self.action_handler.request_play_simulation.connect(self.request_play_simulation.emit)
        self.action_handler.request_stop_simulation.connect(self.request_stop_simulation.emit)
        self.action_handler.request_reset_simulation.connect(self.request_reset_simulation.emit)
        self.action_handler.motion_path_updated.connect(self.motion_path_updated.emit)

    def _handle_part_clicked(self, part_item):
        """Handle when a part item is clicked in the view."""
        if part_item and part_item.part_info:
            part_name = part_item.part_info.name
            self.state.set_selected_part(part_name)

    def _toggle_drawing_mode(self, checked: bool):
        if checked and self.state.selected_part_name:
            self.view.set_mode("define_motion_path")
            target_item = self.scene_manager.current_editor_items.get(self.state.selected_part_name)
            if target_item:
                self.view.start_define_motion_path(target_item)
        else:
            self.view.set_mode("select")

    # Public API
    def set_parts_data(self, parts_info):
        project_dir = self.main_window.project_data_manager.project_dir
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

    def on_simulation_state_changed(self, state: str):
        """Handle simulation state changes from the kinematics system."""
        if state == "playing":
            self.ui_panel.set_simulation_playing(True)
        elif state == "stopped":
            self.ui_panel.set_simulation_playing(False)
        # Additional state handling can be added here

    def toggle_part_properties_panel_visibility(self, visible: bool):
        """Toggle the visibility of the part properties panel."""
        if hasattr(self.ui_panel, 'toggle_part_properties_visibility'):
            self.ui_panel.toggle_part_properties_visibility(visible)
