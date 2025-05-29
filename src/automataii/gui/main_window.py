import sys
import os
import json
import logging
import traceback
import time
import tempfile
import yaml
import cv2
import random
import math
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGraphicsScene, QFileDialog, QSplitter, QLabel, QListWidget, QListWidgetItem,
    QDoubleSpinBox, QCheckBox, QFormLayout, QTabWidget, QMessageBox, QProgressDialog,
    QGraphicsPathItem, QGroupBox, QApplication, QStyle, QDialog, QToolBar, QComboBox, QGraphicsItem,
    QScrollArea, QSizePolicy, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsItemGroup, QGraphicsRectItem, QGraphicsPolygonItem
)
from PyQt6.QtGui import QColor, QPen, QAction, QPainterPath, QPixmap, QPolygonF, QTransform, QBrush, QImage, QFontDatabase, QPainterPathStroker
from PyQt6.QtCore import Qt, QPointF, QTimer, pyqtSlot, QSize, QLineF, QRectF, pyqtSignal, QMetaObject, Q_ARG
from pathlib import Path
from typing import Optional, Dict, Any, List

# Local imports (adjust paths as needed)
from .editor_view import EditorView
from .image_view import ImageProcessingView
from .part_item import CharacterPartItem
from .camera_dialog import CameraDialog
from .styling import LIGHT_STYLE, DARK_STYLE
# from .options_tab import OptionsTab # Removed: OptionsTab is now in tabs directory
from ..core.models import PartInfo, Joint
from ..kinematics.ik_solver import solve_ik_ccd
from ..generation.cam import generate_cam_profile
from ..generation.blueprint import generate_blueprint_svg
from ..utils.helpers import transform_to_dict, qpainterpath_to_points, points_to_closed_bezier_path # Utility functions
from .anchor_item import AnchorItem # Import AnchorItem
from automataii.gui.recommendation_dialog import MechanismRecommendationDialog # Added

# Import new tab modules
from .tabs.image_processing_tab import ImageProcessingTab
from .tabs.editor_tab import EditorTab
from .tabs.options_tab import OptionsTab


# Attempt to import image processing functionality (optional)
from ..animate.image_to_annotations import image_to_annotations
from ..animate.annotations_to_animation import annotations_to_animation
from ..animate.image_to_animation import image_to_animation
# Import body part extractor
from ..animate.body_parts_extractor import process_character

# Import new generation modules
from ..generation.linkage import generate_3bar_linkage, generate_4bar_linkage
from ..generation.gear import generate_gear_pair

# Define UIColors class for consistent styling (ideally in styling.py)
class UIColors:
    COMPONENT_FRONT = QColor("#87CEEB")  # SkyBlue
    COMPONENT_BACK = QColor("#4682B4")   # SteelBlue
    COMPONENT_BORDER = QColor(Qt.GlobalColor.black)

    PIN_FRONT = QColor("#FFD700") # Gold
    PIN_BACK = QColor("#DAA520")  # Goldenrod
    PIN_BORDER = QColor(Qt.GlobalColor.black)

    CAM_FRONT = QColor("#ADD8E6") # LightBlue
    CAM_BACK = QColor("#5F9EA0")  # CadetBlue
    CAM_BORDER = QColor(Qt.GlobalColor.black)
    SHAFT_FRONT = QColor("#D3D3D3") # LightGray
    SHAFT_BACK = QColor("#A9A9A9")  # DarkGray
    SHAFT_BORDER = QColor(Qt.GlobalColor.black)

    GEAR_BODY_FRONT = QColor("#C0C0C0") # Silver
    GEAR_BODY_BACK = QColor("#708090")  # SlateGray
    GEAR_BODY_BORDER = QColor(Qt.GlobalColor.black)
    GEAR_TOOTH_FRONT = QColor("#DCDCDC") # Gainsboro
    GEAR_TOOTH_BACK = QColor("#A9A9A9")  # DarkGray
    GEAR_TOOTH_BORDER = QColor(Qt.GlobalColor.darkGray) # Slightly lighter border for teeth

    TEXT_PRIMARY = QColor("#E0E0E0")
    MOTION_PATH_COLOR = QColor(0, 255, 0, 150)
    DEBUG_HELPER_COLOR = QColor(255, 0, 255, 180) # Magenta for helpers

TARGET_CONTROL_POINTS = 8

class AutomataDesigner(QMainWindow):
    """Main application window for the Automata Designer.

    Integrates image processing, skeleton editing, part assembly, motion definition,
    simulation, and blueprint generation.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Automata Designer")
        self.resize(1200, 680) # Reduced height from 750
        self.setMinimumHeight(600) # Set explicit minimum height
        logging.info("Initializing AutomataDesigner...")

        # --- Data Storage ---
        self.parts = {} # part_name: PartInfo
        self.editor_items = {} # part_name: CharacterPartItem (in editor scene)
        # self.simulation_items = {} # part_name: CharacterPartItem (in simulation scene) # Not used by new system
        self.joints = [] # List of Joint objects
        # self.kinematic_chains = {} # REMOVED
        self.mechanism_visuals = {} # layer_name: list[QGraphicsItem]
        self.layer_checkboxes = {} # layer_name: QCheckBox
        self._body_parts_viz_items = [] # List of visualization items for body parts under skeleton
        self._body_parts_viz_items_image = [] # List of visualization items for body parts in image view
        self.anchor_items = {} # anchor_id: AnchorItem

        # --- Viewer Tab Data ---
        self.viewer_char_texture_item: Optional[QGraphicsPixmapItem] = None
        self.viewer_skeleton_items: List[QGraphicsItem] = []
        self.viewer_body_part_items: Dict[str, CharacterPartItem] = {}
        self.viewer_loaded_parts_info: Optional[dict] = None
        self.viewer_loaded_texture_path: Optional[str] = None
        # Placeholder for the actual scene and view for the viewer tab
        self.viewer_scene: Optional[QGraphicsScene] = None
        self.viewer_view: Optional[EditorView] = None


        # --- Initialize scenes and views that were previously in tab creation methods ---
        self.image_proc_scene = QGraphicsScene()
        self.image_proc_view = ImageProcessingView(self.image_proc_scene, self)
        self.editor_scene = QGraphicsScene()
        self.editor_view = EditorView(self.editor_scene, self)


        # Mechanism Design State
        self.selected_cam_center: Optional[QPointF] = None
        self.selected_pivot_a: Optional[QPointF] = None
        self.selected_pivot_d: Optional[QPointF] = None
        self.selected_driver_center: Optional[QPointF] = None
        self.selected_driven_center: Optional[QPointF] = None
        # Markers for selected points
        self.cam_center_marker: Optional[QGraphicsEllipseItem] = None
        self.pivot_a_marker: Optional[QGraphicsEllipseItem] = None
        self.pivot_d_marker: Optional[QGraphicsEllipseItem] = None
        self.driver_center_marker: Optional[QGraphicsEllipseItem] = None
        self.driven_center_marker: Optional[QGraphicsEllipseItem] = None

        # Image processing workflow data
        self.input_image_path = None
        self.character_dir = None
        self.skeleton_data = None # Loaded skeleton dict

        # IK Animation Timer (New)
        self.ik_animation_timer = QTimer(self)
        self.ik_animation_timer.setInterval(30) # Approx 33 FPS
        self.ik_animation_timer.timeout.connect(self._run_ik_animation_step) # Connect to new animation step
        self.ik_animation_speed = 0.5 # Default animation speed, similar to JS example
        self.animation_duration = 3000

        # --- Toolbar Reference ---
        self.main_toolbar = None

        # Tracking active dialogs
        self.active_camera_dialogs = []

        # --- Stylesheet Data --- (No longer need _define_stylesheets method)
        self.light_style = LIGHT_STYLE
        self.dark_style = DARK_STYLE

        self.visualization_layer_x_offset = 10.0  # Horizontal offset for visualization layers

        # Load Parts and Styles
        self.load_initial_data()

        # Load custom application fonts
        self._load_custom_fonts()

        # Setup UI, Menus, Toolbar, and connections
        self._init_ui() # This creates self.editor_tab and other UI elements
        self._create_menus() # Defines QActions and populates menubar
        self._create_toolbar() # Defines QActions or uses existing ones for toolbar
        self._connect_ui_actions() # Connects all signals now that UI and actions exist

        self.statusBar().showMessage("Ready")
        logging.info("AutomataDesigner initialized.")

        self.scene_joints_snapshot = {} # Will store the calculated scene_joints from _initialize_new_ik_skeleton_definitions
        self.ik_part_to_actual_part_name = {
            'head': 'head',
            'torso': 'torso',
            'left_upper_arm': 'left_arm_upper',
            'left_forearm': 'left_arm_lower',
            'right_upper_arm': 'right_arm_upper',
            'right_forearm': 'right_arm_lower',
            'left_thigh': 'left_leg_upper',
            'left_calf': 'left_leg_lower',
            'right_thigh': 'right_leg_upper',
            'right_calf': 'right_leg_lower'
        }
        self._active_path_definition_target_joint_id: Optional[str] = None # Stores the joint ID while path definition is active
        self.ik_to_json_joint_map_config = { # Maps our IK joint IDs to keys in the char_cfg.yaml/joint_map
            'j_neck_base': 'neck',      # Anchor
            'j_left_shoulder': 'left_shoulder', # Anchor
            'j_right_shoulder': 'right_shoulder',# Anchor
            'j_left_hip': 'left_hip',      # Anchor
            'j_right_hip': 'right_hip',     # Anchor

            'j_head': 'neck',          # Distal end for head (uses neck as its proximal point from char_cfg)
                                        # Actual j_head position will be calculated based on neck_base + head_length
            'j_left_elbow': 'left_elbow',
            'j_left_wrist': 'left_hand',
            'j_right_elbow': 'right_elbow',
            'j_right_wrist': 'right_hand',
            'j_left_knee': 'left_knee',
            'j_left_ankle': 'left_foot',
            'j_right_knee': 'right_knee',
            'j_right_ankle': 'right_foot'
        }

        # --- New IK System Data ---
        self.sim_joints_config = {} # Stores structure: { 'j_neck_base': {'xOffset': ..., 'yOffset': ..., 'label': ...}, ... }
        self.sim_limb_configs = {}  # Stores structure: { 'j_head': {'parentAnchor': ..., 'angle': ..., 'length': ...}, ... }
        self.sim_limb_lengths = {} # Stores structure: { 'head': 35, 'upperArm': 55, ... }
        self.sim_selectable_components = [] # List of dicts defining selectable parts for IK path definition
        self.sim_two_bone_ik_effectors = [] # List of joint IDs that are end-effectors of a 2-bone chain
        self.sim_joint_bend_directions = {} # { 'j_left_elbow': -1, ... }

        # Actual data store for sim_dynamic_joints property
        self._sim_dynamic_joints_data: Dict[str, Dict[str, Any]] = {}
        logging.info("[ATTR_DEBUG] Initializing self._sim_dynamic_joints_data = {}")

        self.sim_selected_component_key = None # Stores the targetJointId of the currently selected component for path drawing
        self.current_parts_info_data = None # Will store loaded parts_info.json content
        self.effective_bounding_box_offset = QPointF(0,0) # Will store calculated offset
        # ... (other attributes remain the same) ...

    # --- UI Initialization ---

    def _init_ui(self):
        """Sets up the main user interface layout and widgets."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # --- Tab 1: Image Processing ---
        image_proc_tab = ImageProcessingTab(self) # Pass self (main_window)
        self.tab_widget.addTab(image_proc_tab, "Character Selection")

        # --- Tab 2: Editor & Simulation ---
        self.editor_tab = EditorTab(self) # Pass self (main_window) - Assign to self.editor_tab
        self.tab_widget.addTab(self.editor_tab, "Mechanism Design")

        # --- Tab 3: Options ---
        self.options_tab = OptionsTab(initial_anim_duration=self.animation_duration)
        self.tab_widget.addTab(self.options_tab, "Options")

        # --- Connect Signals from EditorView ---
        self.editor_view.freehandPathCompleted.connect(self._handle_freehand_path_completed)
        self.editor_view.drawing_cancelled.connect(self._handle_drawing_cancelled) # Already exists, ensure it\'s used appropriately
        self.editor_view.joint_defined.connect(self.request_create_joint) # Already exists
        # Connect other EditorView signals as needed (cam_center_selected, etc.)
        self.editor_view.cam_center_selected.connect(self._handle_cam_center_set)
        self.editor_view.pivot_a_selected.connect(self._handle_pivot_a_set)
        self.editor_view.pivot_d_selected.connect(self._handle_pivot_d_set)
        self.editor_view.driver_center_selected.connect(self._handle_driver_center_set)
        self.editor_view.driven_center_selected.connect(self._handle_driven_center_set)


        # --- Connect Signals from Options Tab ---
        self.options_tab.animationDurationChanged.connect(self._update_animation_duration)
        self.options_tab.themeChanged.connect(self._apply_theme)
        self.options_tab.toolbarVisibilityChanged.connect(self._toggle_toolbar_visibility) # Connect new signal
        self.options_tab.debugModeChanged.connect(self.image_proc_view.set_debug_mode)

        # Apply Initial Theme (Light by default)
        self.setStyleSheet(self.light_style)
        self.options_tab.set_theme("Light") # Ensure combo matches initial theme

    # --- Menu Creation ---
    def _create_menus(self):
        """Creates the main application menus."""
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")
        if not hasattr(self, 'action_load_parts'):
            self.action_load_parts = QAction("&Load Character Parts...", self)
        if not hasattr(self, 'action_save_project'):
            self.action_save_project = QAction("&Save Project...", self)
            self.action_save_project.setShortcut("Ctrl+S")
        if not hasattr(self, 'action_exit'):
            self.action_exit = QAction("E&xit", self)
            self.action_exit.setShortcut("Ctrl+Q")

        file_menu.addAction(self.action_load_parts)
        file_menu.addAction(self.action_save_project)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

        # View Menu
        view_menu = menubar.addMenu("&View")
        self.action_zoom_in = QAction("Zoom &In", self)
        self.action_zoom_in.setShortcut("Ctrl++")
        self.action_zoom_out = QAction("Zoom &Out", self)
        self.action_zoom_out.setShortcut("Ctrl+-")
        self.action_zoom_fit = QAction("Zoom to &Fit", self)
        self.action_zoom_fit.setShortcut("Ctrl+0")
        self.action_reset_view = QAction("&Reset View", self)

        view_menu.addAction(self.action_zoom_in)
        view_menu.addAction(self.action_zoom_out)
        view_menu.addAction(self.action_zoom_fit)
        view_menu.addAction(self.action_reset_view)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        self.action_about = QAction("&About...", self)
        help_menu.addAction(self.action_about)

    # --- Toolbar Creation ---
    def _create_toolbar(self):
        """Creates the main application toolbar."""
        self.main_toolbar = QToolBar("Main Toolbar") # Store reference
        self.main_toolbar.setMovable(False) # Keep it fixed
        # Use a slightly larger icon size for the updated style
        icon_size = QSize(20, 20)
        self.main_toolbar.setIconSize(icon_size)

        # Use standard icons for a cleaner look
        style = self.style()
        # Ensure actions are created before adding them
        if not hasattr(self, 'action_load_parts'):
            self.action_load_parts = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "Open...", self)
        else:
            self.action_load_parts.setText("Open...") # Shorter text for toolbar
            self.action_load_parts.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))

        if not hasattr(self, 'action_save_project'):
            self.action_save_project = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "Save...", self)
            self.action_save_project.setShortcut("Ctrl+S")
        else:
            self.action_save_project.setText("Save...")
            self.action_save_project.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))

        # Placeholder for New/Export - create dummy actions for now
        action_new = QAction(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon), "New", self) # Placeholder icon
        action_export = QAction(style.standardIcon(QStyle.StandardPixmap.SP_ArrowRight), "Export", self) # Placeholder icon

        self.main_toolbar.addAction(action_new)
        self.main_toolbar.addAction(self.action_load_parts)
        self.main_toolbar.addAction(self.action_save_project)
        self.main_toolbar.addAction(action_export)

        self.addToolBar(self.main_toolbar)
        self.main_toolbar.hide() # Hide by default

    # --- Signal Connections ---
    def _connect_ui_actions(self):
        """Connects UI elements (buttons, menus, list widgets, and tab signals) to methods."""
        # Tab 1: Image Processing
        self.load_image_btn.clicked.connect(self.load_input_image)
        self.capture_image_btn.clicked.connect(self.capture_image)
        # self.process_image_btn.clicked.connect(self.process_image)
        # self.edit_skeleton_btn.clicked.connect(self.edit_skeleton)
        # self.save_skeleton_btn.clicked.connect(self.save_skeleton)
        # self.create_parts_btn.clicked.connect(self.create_parts_from_skeleton)
        self.next_stage_btn.clicked.connect(self.next_stage)

        # Tab 2: Editor
        self.parts_list.currentItemChanged.connect(self._handle_part_selection_change)
        self.parts_list.itemClicked.connect(self._handle_part_list_click)
        self.z_value_spin.valueChanged.connect(self._update_selected_part_z)
        self.fixed_part_check.stateChanged.connect(self._update_selected_part_fixed)
        self.define_motion_path_btn.toggled.connect(self._toggle_define_motion_path_mode)
        self.clear_motion_path_btn.clicked.connect(self._clear_selected_item_motion_path)

        self.generate_mechanism_btn.clicked.connect(self._generate_mechanism_auto)
        self.mechanism_type_combo.currentTextChanged.connect(self._update_mechanism_inputs_ui)
        self.mechanism_type_combo.currentTextChanged.connect(self._update_generate_mechanism_button_state) # Also update button state on type change
        # Connect new IK animation buttons
        self.play_btn.clicked.connect(self._start_ik_animation)
        self.stop_btn.clicked.connect(self._stop_ik_animation)
        self.reset_sim_btn.clicked.connect(self._reset_ik_animation_state)
        self.blueprint_btn.clicked.connect(self.generate_blueprint)

        # Connect the new "Reset All Animations" button from EditorTab
        if hasattr(self.editor_tab, 'reset_all_animations_btn'): # editor_tab is an instance of EditorTab
            self.editor_tab.reset_all_animations_btn.clicked.connect(self._reset_all_animations_button_clicked)
        else:
            logging.warning("EditorTab does not have 'reset_all_animations_btn'. Connection failed.")

        # Character Alignment Button
        self.save_alignment_btn.clicked.connect(self.save_character_alignment)

        # Editor View Signals
        self.editor_view.joint_defined.connect(self.request_create_joint)
        # self.editor_view.end_effector_selected.connect(self._handle_end_effector_set) # Removed in UI cleanup
        self.editor_view.cam_center_selected.connect(self._handle_cam_center_set)
        self.editor_view.drawing_cancelled.connect(self._handle_drawing_cancelled)
        self.editor_view.pivot_a_selected.connect(self._handle_pivot_a_set)
        self.editor_view.pivot_d_selected.connect(self._handle_pivot_d_set)
        self.editor_view.driver_center_selected.connect(self._handle_driver_center_set)
        self.editor_view.driven_center_selected.connect(self._handle_driven_center_set)

        # Zoom control signals
        self.zoom_combo.currentTextChanged.connect(self._handle_zoom_change)
        self.fit_btn.clicked.connect(self._handle_zoom_change_fit)
        self.editor_view.zoom_changed.connect(self._update_zoom_combo_from_view)

        # Image processing zoom control signals
        self.image_zoom_combo.currentTextChanged.connect(self._handle_image_zoom_change)
        self.image_fit_btn.clicked.connect(self._handle_image_zoom_change_fit)

        # Tab 3: Options (Connect signals from OptionsTab instance)
        self.options_tab.animationDurationChanged.connect(self._update_animation_duration)
        self.options_tab.themeChanged.connect(self._apply_theme)
        self.options_tab.toolbarVisibilityChanged.connect(self._toggle_toolbar_visibility) # Connect new signal
        self.options_tab.partPropertiesVisibilityChanged.connect(self._toggle_part_properties_visibility) # Connect new signal

        # Menu Actions (Ensure these are still connected)
        if hasattr(self, 'action_load_parts'):
            self.action_load_parts.triggered.connect(self.load_parts)
        if hasattr(self, 'action_save_project'):
            self.action_save_project.triggered.connect(self.save_project)
        if hasattr(self, 'action_exit'):
            self.action_exit.triggered.connect(self.close)
        self.action_zoom_in.triggered.connect(lambda: self.editor_view.scale(1.15, 1.15))
        self.action_zoom_out.triggered.connect(lambda: self.editor_view.scale(1 / 1.15, 1 / 1.15))
        self.action_zoom_fit.triggered.connect(lambda: self.editor_view.zoom_to_fit())
        self.action_reset_view.triggered.connect(lambda: self.editor_view.reset_view())
        self.action_about.triggered.connect(self.show_about)

        # Test Anchors Button Connection
        self.toggle_anchors_btn.toggled.connect(self._toggle_test_anchors_visibility)

        # Viewer Tab Connections (New)
        if hasattr(self, 'viewer_load_btn'): # Check if viewer tab elements are created
            self.viewer_load_btn.clicked.connect(self._viewer_load_character_data)
            self.viewer_show_skeleton_check.toggled.connect(self._viewer_toggle_skeleton)
            self.viewer_show_body_parts_check.toggled.connect(self._viewer_toggle_body_parts)

    # --- Action Handlers & Slots ---

    # Slot for part selection change in list
    def _handle_part_selection_change(self, current_item, previous_item):
        can_define_path = False
        is_part_selected = current_item is not None

        # Hide anchor on previously selected item if it exists
        if previous_item:
            prev_part_name = previous_item.data(Qt.ItemDataRole.UserRole)
            prev_editor_item = self.editor_items.get(prev_part_name)
            if prev_editor_item:
                prev_editor_item.set_anchor_visibility(False)

        if current_item:
            self.update_part_properties(current_item, previous_item)
            part_name = current_item.data(Qt.ItemDataRole.UserRole)
            item = self.editor_items.get(part_name)
            if item:
                self.editor_scene.clearSelection()
                item.setSelected(True)
                # Show anchor only if in Mechanism Design Tab
                if self.tab_widget.widget(self.tab_widget.currentIndex()) == self.tab_widget.findChild(QWidget, "Mechanism Design"):
                    item.set_anchor_visibility(True)
                else:
                    item.set_anchor_visibility(False)

                if not item.is_fixed:
                    can_define_path = True
        else:
            self.z_value_spin.setEnabled(False)
            self.fixed_part_check.setEnabled(False)
            # Ensure any potentially visible anchor is hidden if selection is cleared
            for editor_item_val in self.editor_items.values():
                editor_item_val.set_anchor_visibility(False)

        # Enable/disable UI elements based on selection
        # Find the QGroupBox by iterating through children of panel_layout's parent (control_panel)
        control_panel = self.parts_list.parent().parent() # Assuming Parts List -> Parts Group -> Control Panel
        props_group = control_panel.findChild(QGroupBox, "Selected Part Properties")
        cam_group = control_panel.findChild(QGroupBox, "Cam Mechanism")

        if props_group: props_group.setEnabled(is_part_selected)
        if cam_group: cam_group.setEnabled(is_part_selected)

        # self.define_joint_btn.setEnabled(is_part_selected)

        # Motion path button depends on selection AND fixed status
        self.define_motion_path_btn.setEnabled(can_define_path)

        # If selection cleared, ensure define motion mode is off
        if not can_define_path and self.define_motion_path_btn.isChecked():
            self.define_motion_path_btn.setChecked(False)

        # Disable properties directly if nothing selected (redundant if group is disabled, but safe)
        if not is_part_selected:
            self.z_value_spin.setEnabled(False)
            self.fixed_part_check.setEnabled(False)

        selected_item = self.get_selected_editor_item() # Get current selection reliably

        # Determine if generate mechanism button should be enabled
        can_generate_mechanism = False
        if selected_item and selected_item.motion_path and not selected_item.motion_path.isEmpty():
            # Add a log to confirm the check passes
            logging.debug(f"Enabling Generate Mechanism for {selected_item.part_info.name}. Path exists and is not empty.")
            can_generate_mechanism = True
        else:
            # Add a log for why it's disabled
            if not selected_item:
                logging.debug("Disabling Generate Mechanism: No item selected.")
            elif selected_item and not selected_item.motion_path:
                logging.debug(f"Disabling Generate Mechanism for {selected_item.part_info.name}: motion_path is None.")
            elif selected_item and selected_item.motion_path.isEmpty():
                logging.debug(f"Disabling Generate Mechanism for {selected_item.part_info.name}: motion_path is empty.")

        # Enable Generate Mechanism button if part selected and has path
        self.generate_mechanism_btn.setEnabled(can_generate_mechanism)

    # Slot for clicking item in list (redundant with selection change?)
    def _handle_part_list_click(self, list_item):
        part_name = list_item.data(Qt.ItemDataRole.UserRole)
        if part_name in self.editor_items:
            item = self.editor_items[part_name]
            if not item.isSelected(): # Avoid redundant selection if already selected
                self.editor_scene.clearSelection()
                item.setSelected(True)
            self.editor_view.centerOn(item) # Center view on clicked item
        self.update_part_properties(list_item) # Update properties regardless

    # --- Image Processing Actions ---
    def load_input_image(self):
        """Loads an image for processing via file dialog."""
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Input Image", "",
                                                    "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if not filepath:
            return
        if self.image_proc_view.load_image(filepath):
            self.input_image_path = filepath
            self.character_dir = os.path.dirname(filepath) # Assume character dir is same level
            self.statusBar().showMessage(f"Loaded input image: {os.path.basename(filepath)}")
        else:
            QMessageBox.warning(self, "Load Error", f"Could not load image: {filepath}")
        self.process_image()
        self.create_parts_from_skeleton()

    def capture_image(self):
        """Opens camera dialog to capture an image."""
        try:
            dialog = CameraDialog(self)
            self.active_camera_dialogs.append(dialog)
            dialog.finished.connect(lambda: self.active_camera_dialogs.remove(dialog) if dialog in self.active_camera_dialogs else None)

            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.captured_image is not None:
                temp_dir = tempfile.gettempdir()
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                temp_path = os.path.join(temp_dir, f"automata_capture_{timestamp}.png")
                try:
                    cv2.imwrite(temp_path, dialog.captured_image)
                    logging.info(f"Captured image saved to {temp_path}")
                    if self.image_proc_view.load_image(temp_path):
                        self.input_image_path = temp_path
                        self.character_dir = temp_dir # Use temp dir for captured image
                        self.statusBar().showMessage(f"Loaded captured image: {os.path.basename(temp_path)}")
                    else:
                         QMessageBox.warning(self, "Load Error", "Failed to load captured image into view.")
                except Exception as e:
                     logging.error(f"Failed to save captured image: {e}")
                     QMessageBox.critical(self, "Save Error", f"Could not save captured image: {e}")
        except Exception as e:
            logging.error(f"Error opening camera dialog: {e}", exc_info=True)
            QMessageBox.critical(self, "Camera Error", f"Could not open camera: {e}")

        self.process_image()
        self.create_parts_from_skeleton()

    def process_image(self):
        """Runs the external image_to_annotations process."""
        logging.info(f"Processing image: {self.input_image_path}")
        if not self.input_image_path:
            QMessageBox.warning(self, "Process Error", "Please load or capture an image first.")
            return

        # Define output directory relative to input image
        output_dir = os.path.join(os.path.dirname(self.input_image_path), "character_data")
        os.makedirs(output_dir, exist_ok=True)
        self.character_dir = output_dir # Update character dir
        logging.info(f"Processing image '{self.input_image_path}' into '{output_dir}'")

        progress = QProgressDialog("Processing image with AnimatedDrawings...", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setValue(10)
        QApplication.processEvents() # Ensure dialog shows

        try:
            # --- Call the image_to_annotations function --- #
            image_to_annotations(self.input_image_path, output_dir)
            progress.setValue(50)
            QApplication.processEvents()
            logging.info("image_to_annotations function completed.")

            # --- Load results --- #
            processed_image_path = os.path.join(output_dir, "image.png")
            skeleton_file = os.path.join(output_dir, "char_cfg.yaml")

            if not os.path.exists(processed_image_path) or not os.path.exists(skeleton_file):
                raise FileNotFoundError("Required output files (image.png, char_cfg.yaml) not found after processing.")

            logging.info("Loading processed image and skeleton...")
            # Load the processed image (which might be segmented)
            if not self.image_proc_view.load_image(processed_image_path):
                raise RuntimeError("Failed to load the processed image.png into view.")
            # self.input_image_path = processed_image_path # Update path
            progress.setValue(70)
            QApplication.processEvents()

            # Load the skeleton
            if not self.load_skeleton(skeleton_file):
                raise RuntimeError("Failed to load the generated char_cfg.yaml skeleton file.")

            progress.setValue(100)
            QMessageBox.information(self, "Success", "Image processed and skeleton loaded successfully.")

        except Exception as e:
            logging.error(f"Error during image processing: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Processing Error", f"Failed to process image: {e}")
            if progress.isVisible(): progress.cancel()

    def load_skeleton(self, skeleton_filepath=None):
        """Loads a skeleton YAML file into the image processing view."""
        if not skeleton_filepath:
            skeleton_filepath, _ = QFileDialog.getOpenFileName(self, "Load Skeleton", self.character_dir or "", "YAML Files (*.yaml *.yml)")
        if not skeleton_filepath or not os.path.exists(skeleton_filepath):
            if skeleton_filepath: # Only show error if a path was given but invalid
                 logging.warning(f"Skeleton file not found: {skeleton_filepath}")
                 QMessageBox.warning(self, "Load Error", f"Skeleton file not found: {os.path.basename(skeleton_filepath)}")
            return False

        try:
            with open(skeleton_filepath, 'r') as f:
                skeleton_data = yaml.safe_load(f)
            if not skeleton_data or 'skeleton' not in skeleton_data:
                raise ValueError("Invalid or empty skeleton file format.")

            if self.image_proc_view.load_skeleton(skeleton_data):
                self.skeleton_data = skeleton_data # Store loaded data
                # Update character_dir based on skeleton file location if not set
                if not self.character_dir or not self.input_image_path:
                    self.character_dir = os.path.dirname(skeleton_filepath)
                self.statusBar().showMessage(f"Loaded skeleton: {os.path.basename(skeleton_filepath)}")
                logging.info(f"Skeleton loaded from {skeleton_filepath}")
                return True
            else:
                raise RuntimeError("ImageProcessingView failed to load skeleton data.")

        except Exception as e:
            logging.error(f"Failed to load skeleton from {skeleton_filepath}: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Load Skeleton Error", f"Failed to load skeleton: {e}")
            return False

    def edit_skeleton(self):
        """Enables skeleton editing in the image processing view."""
        if not self.image_proc_view.joints:
            QMessageBox.information(self, "Edit Skeleton", "No skeleton loaded to edit. Please process an image or load a skeleton first.")
            return
        # Joints are already editable if loaded
        QMessageBox.information(self, "Edit Skeleton", "Skeleton joints are now active. Drag them to adjust positions.")
        self.tab_widget.setCurrentIndex(0) # Switch to image processing tab

    def save_skeleton(self):
        """Saves the current state of the skeleton in the image view."""
        if not self.image_proc_view.joints:
            QMessageBox.warning(self, "Save Error", "No skeleton data loaded to save.")
            return

        # Default save path (overwrite original or ask)
        default_path = os.path.join(self.character_dir, "char_cfg.yaml") if self.character_dir else "char_cfg.yaml"
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Skeleton As", default_path, "YAML Files (*.yaml *.yml)")

        if not save_path:
            return

        try:
            current_skeleton_data = self.image_proc_view.get_skeleton_data()
            if not current_skeleton_data:
                raise ValueError("Could not retrieve skeleton data from view.")

            with open(save_path, 'w') as f:
                yaml.dump(current_skeleton_data, f, default_flow_style=None, sort_keys=False)

            self.skeleton_data = current_skeleton_data # Update stored data
            self.statusBar().showMessage(f"Skeleton saved to {os.path.basename(save_path)}")
            logging.info(f"Skeleton saved to {save_path}")

        except Exception as e:
            logging.error(f"Failed to save skeleton: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Save Skeleton Error", f"Could not save skeleton: {e}")

    def create_parts_from_skeleton(self):
        """Triggers the body part extraction process using the current character data."""
        logging.info("'Create Parts from Skeleton' button clicked.")

        if not self.character_dir or not os.path.isdir(self.character_dir):
            QMessageBox.warning(self, "Missing Character Data",
                                "Please load an image or ensure the character data directory is set correctly.")
            logging.warning("Cannot create parts: character_dir not set or invalid.")
            return # Correct indentation

        # Check for required files in character_dir
        required_files = ['char_cfg.yaml', 'image.png', 'mask.png']
        missing_files = [f for f in required_files if not os.path.exists(os.path.join(self.character_dir, f))]
        if missing_files:
            QMessageBox.warning(self, "Missing Files",
                                f"The following required files are missing in {self.character_dir}:\n" +
                                f"{', '.join(missing_files)}\nCannot proceed with part extraction.")
            logging.warning(f"Cannot create parts: Missing files {missing_files} in {self.character_dir}")
            return

        # Determine output directory (next to character_dir)
        try:
            parent_dir = os.path.dirname(os.path.abspath(self.character_dir))
            output_dir = os.path.join(parent_dir, 'body_parts_output')
        except Exception as e:
            logging.error(f"Error determining output directory: {e}")
            QMessageBox.critical(self, "Error", f"Could not determine output directory: {e}")
            return

        logging.info(f"Starting body part extraction. Input: {self.character_dir}, Output: {output_dir}")
        self.statusBar().showMessage(f"Extracting body parts into {os.path.basename(output_dir)}... Please wait.")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            # Ensure the body_parts_extractor handles the case where output_dir might be inside char_dir
            process_character(self.character_dir, output_dir)
            QApplication.restoreOverrideCursor()
            self.statusBar().showMessage(f"Body parts extracted successfully to {output_dir}")
            logging.info(f"Body part extraction successful. Output: {output_dir}")
            # Ask user if they want to load the generated parts
            reply = QMessageBox.question(self, "Parts Extracted",
                                       f"Load these parts into the editor!",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                parts_json_path = os.path.join(output_dir, 'parts_info.json')
                if os.path.exists(parts_json_path):
                     logging.debug(f"Loading parts from: {parts_json_path}")
                     self.load_parts(filepath=parts_json_path)
                     logging.debug(f"After load_parts: {len(self.parts)} parts, {len(self.editor_items)} editor items")
                     # Show body parts with 50% opacity below skeleton
                     logging.debug("Calling _visualize_body_parts_under_skeleton()")
                     self._visualize_body_parts_under_skeleton()
                     # Also visualize in image processing view if skeleton data exists
                    #  if self.skeleton_data:
                    #      self._visualize_body_parts_in_image_view()
                else:
                     QMessageBox.warning(self, "Load Error", f"Could not find parts_info.json in {output_dir}")
        except Exception as e:
            QApplication.restoreOverrideCursor()
            error_msg = f"Failed to extract body parts: {e}"
            logging.error(f"{error_msg}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Extraction Error", error_msg)
            self.statusBar().showMessage("Body part extraction failed.")

    def _visualize_body_parts_under_skeleton(self):
        """Visualizes body parts with 50% opacity under the skeleton."""
        logging.debug(f"_visualize_body_parts_under_skeleton called. Parts: {len(self.parts) if self.parts else 0}, Editor items: {len(self.editor_items) if self.editor_items else 0}")

        if not self.parts or not self.editor_items:
            logging.warning("No body parts loaded to visualize under skeleton.")
            return

        # Clear any existing body part visualization
        self._clear_body_parts_visualization()
        self._clear_body_parts_visualization_image_view(make_original_visible=True)

        logging.info("Visualizing body parts with 50% opacity under skeleton.")
        logging.debug(f"Available editor items: {list(self.editor_items.keys())}")

        successful_items = 0
        for part_name, part_item in self.editor_items.items():
            logging.debug(f"Processing part: {part_name}")

            # Create a copy of the part item for visualization
            if hasattr(part_item, 'part_info') and part_item.part_info:
                logging.debug(f"Creating visualization for {part_name}")
                try:
                    viz_item = CharacterPartItem(part_item.part_info)

                    # Set the same position and transform as the original [Mechanism Tab]
                    original_pos = part_item.pos()
                    viz_item.setPos(original_pos.x(), original_pos.y())
                    viz_item.setTransform(part_item.transform())
                    viz_item.setRotation(part_item.rotation())

                    # Set 50% opacity
                    viz_item.setOpacity(0.5)

                    # Set z-value below skeleton (skeleton is at 500-501)
                    viz_item.setZValue(100)

                    # Make it non-interactive
                    viz_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                    viz_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

                    # Add to scene
                    self.editor_scene.addItem(viz_item)
                    logging.debug(f"Added {part_name} visualization to scene at pos {viz_item.pos()}, z-value {viz_item.zValue()}, opacity {viz_item.opacity()}")

                    # Store reference for cleanup
                    if not hasattr(self, '_body_parts_viz_items'):
                        self._body_parts_viz_items = []
                    self._body_parts_viz_items.append(viz_item)
                    successful_items += 1

                except Exception as e:
                    logging.error(f"Error creating visualization for {part_name}: {e}")
            else:
                logging.debug(f"Skipping {part_name}: no part_info or invalid part_item")

        logging.info(f"Added {successful_items} body part visualizations under skeleton (total viz items: {len(self._body_parts_viz_items)}).")

    def _clear_body_parts_visualization(self):
        """Removes body parts visualization items from the scene."""
        if not hasattr(self, '_body_parts_viz_items') or not self._body_parts_viz_items:
            return

        logging.debug(f"Clearing {len(self._body_parts_viz_items)} body parts visualization items.")
        for item in self._body_parts_viz_items:
            if item.scene():
                self.editor_scene.removeItem(item)
        self._body_parts_viz_items.clear()

    def _handle_zoom_change(self, zoom_text):
        """Handle zoom level change from combo box."""
        try:
            if zoom_text.lower() == "fit":
                self.editor_view.zoom_to_fit()
                return

            # Parse percentage (e.g., "100%" -> 1.0)
            if zoom_text.endswith('%'):
                zoom_value = float(zoom_text[:-1]) / 100.0
            else:
                zoom_value = float(zoom_text) / 100.0

            # Reset transform and apply new zoom
            self.editor_view.resetTransform()
            self.editor_view.scale(zoom_value, zoom_value)

            # Update combo box to show exact percentage
            self.zoom_combo.blockSignals(True)
            self.zoom_combo.setCurrentText(f"{int(zoom_value * 100)}%")
            self.zoom_combo.blockSignals(False)

        except ValueError:
            # Invalid input, reset to 100%
            self.zoom_combo.blockSignals(True)
            self.zoom_combo.setCurrentText("100%")
            self.zoom_combo.blockSignals(False)
            self.editor_view.resetTransform()

    def _handle_zoom_change_fit(self):
        """Handle fit button click."""
        self.editor_view.zoom_to_fit()
        # Update combo box to reflect current zoom after fit
        current_scale = self.editor_view.transform().m11()
        zoom_percent = int(current_scale * 100)
        self.zoom_combo.blockSignals(True)
        self.zoom_combo.setCurrentText(f"{zoom_percent}%")
        self.zoom_combo.blockSignals(False)

    def _update_zoom_combo_from_view(self, scale_factor):
        """Update zoom combo box when zoom changes from view (mouse wheel, etc.)."""
        zoom_percent = int(scale_factor * 100)
        self.zoom_combo.blockSignals(True)
        self.zoom_combo.setCurrentText(f"{zoom_percent}%")
        self.zoom_combo.blockSignals(False)

    def _handle_image_zoom_change(self, zoom_text):
        """Handle zoom level change from image processing combo box."""
        try:
            if zoom_text.lower() == "fit":
                self.image_proc_view.zoom_to_fit()
                return

            # Parse percentage (e.g., "100%" -> 1.0)
            if zoom_text.endswith('%'):
                zoom_value = float(zoom_text[:-1]) / 100.0
            else:
                zoom_value = float(zoom_text) / 100.0

            # Reset transform and apply new zoom
            self.image_proc_view.resetTransform()
            self.image_proc_view.scale(zoom_value, zoom_value)

            # Update combo box to show exact percentage
            self.image_zoom_combo.blockSignals(True)
            self.image_zoom_combo.setCurrentText(f"{int(zoom_value * 100)}%")
            self.image_zoom_combo.blockSignals(False)

        except ValueError:
            # Invalid input, reset to 100%
            self.image_zoom_combo.blockSignals(True)
            self.image_zoom_combo.setCurrentText("100%")
            self.image_zoom_combo.blockSignals(False)
            self.image_proc_view.resetTransform()

    def _handle_image_zoom_change_fit(self):
        """Handle fit button click for image processing view."""
        self.image_proc_view.zoom_to_fit()
        # Update combo box to reflect current zoom after fit
        current_scale = self.image_proc_view.transform().m11()
        zoom_percent = int(current_scale * 100)
        self.image_zoom_combo.blockSignals(True)
        self.image_zoom_combo.setCurrentText(f"{zoom_percent}%")
        self.image_zoom_combo.blockSignals(False)

    def _visualize_body_parts_in_image_view(self):
        """Visualizes body parts with 50% opacity in the image processing view."""
        if not self.parts or not self.editor_items:
            logging.warning("No body parts loaded to visualize in image view.")
            return

        # Hide the main original image if body parts are about to be shown
        if self.image_proc_view and self.image_proc_view.image_item: # Corrected attribute name
            self.image_proc_view.image_item.setVisible(False)
            logging.debug("Hiding original image in image_proc_view for body part visualization.")

        # Clear any existing body part visualization in image view
        self._clear_body_parts_visualization_image_view(make_original_visible=False) # Pass flag to prevent flicker

        logging.info("Visualizing body parts with 50% opacity in image processing view.")

        for part_name, part_item in self.editor_items.items():
            # Create a copy of the part item for visualization
            if hasattr(part_item, 'part_info') and part_item.part_info:
                try:
                    viz_item = CharacterPartItem(part_item.part_info)

                    # Set the same position and transform as the original [Character Selection Tab]
                    original_pos = part_item.pos()
                    print(f"original_pos: {original_pos}")

                    viz_item.setPos(original_pos.x(), original_pos.y())
                    viz_item.setTransform(part_item.transform())
                    viz_item.setRotation(part_item.rotation())

                    # Set 50% opacity
                    viz_item.setOpacity(0.5)

                    # Set z-value below skeleton
                    viz_item.setZValue(100)

                    # Make it non-interactive
                    viz_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                    viz_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

                    # Add to image processing scene
                    self.image_proc_scene.addItem(viz_item)

                    # Store reference for cleanup
                    if not hasattr(self, '_body_parts_viz_items_image'):
                        self._body_parts_viz_items_image = []
                    self._body_parts_viz_items_image.append(viz_item)

                except Exception as e:
                    logging.error(f"Error creating image view visualization for {part_name}: {e}")

        # self.viewer_scene.update() # Ensure redraw
        if self.image_proc_scene: # Update the correct scene for this tab
            self.image_proc_scene.update()

    def _clear_body_parts_visualization_image_view(self, make_original_visible: bool = True):
        """Removes body parts visualization items from the image processing scene."""
        if not hasattr(self, '_body_parts_viz_items_image') or not self._body_parts_viz_items_image:
            # Still ensure original image becomes visible if requested and no items to clear
            if make_original_visible and self.image_proc_view and self.image_proc_view.image_item: # Corrected attribute name
                self.image_proc_view.image_item.setVisible(True)
                logging.debug("Ensured original image is visible in image_proc_view as no body parts were visualized.")
            return

        logging.debug(f"Clearing {len(self._body_parts_viz_items_image)} body parts visualization items from image view.")
        for item in self._body_parts_viz_items_image:
            if item.scene():
                self.image_proc_scene.removeItem(item)
        self._body_parts_viz_items_image.clear()

        # Show the main original image again if requested
        if make_original_visible and self.image_proc_view and self.image_proc_view.image_item: # Corrected attribute name
            self.image_proc_view.image_item.setVisible(True)
            logging.debug("Restored original image visibility in image_proc_view after clearing body parts.")

    def next_stage(self):
        try:
            parent_dir = os.path.dirname(os.path.abspath(self.character_dir))
            output_dir = os.path.join(parent_dir, 'body_parts_output')
        except Exception as e:
            logging.error(f"Error determining output directory: {e}")
            QMessageBox.critical(self, "Error", f"Could not determine output directory: {e}")
            return

        is_character_exist = self.character_dir is not None and self.character_dir != ""
        parts_json_path = os.path.join(output_dir, 'parts_info.json')
        if os.path.exists(parts_json_path):
             self.load_parts(filepath=parts_json_path)
        else:
             QMessageBox.warning(self, "Load Error", f"Could not find parts_info.json in {output_dir}")


        if self.tab_widget.currentIndex() == 0:
            self.tab_widget.setCurrentIndex(1) # Switch to editor tab
            if self.editor_items: # Check if parts are loaded
                self.editor_view.zoom_to_fit() # Zoom to fit character

    # --- Editor Actions ---

    def load_parts(self, filepath=None, parts_data=None):
        """Loads character parts into the editor scene, either from a file or data dict."""
        if not filepath and not parts_data:
            filepath, _ = QFileDialog.getOpenFileName(self, "Load Character Parts", self.character_dir or "",
                                                      "JSON Files (*.json)")
            if not filepath:
                return

        try:
            if filepath:
                logging.info(f"Loading parts from file: {filepath}")
                with open(filepath, 'r') as f:
                    loaded_data = json.load(f)
                base_path = os.path.dirname(filepath)
                self.current_parts_info_data = loaded_data # <--- SET THE ATTRIBUTE HERE
            else: # Loading from parts_data dictionary
                logging.info("Loading parts from provided data dictionary.")
                loaded_data = parts_data
                # Assume base path is character_dir if loading from data
                base_path = self.character_dir or "." # Use current dir as fallback
                self.current_parts_info_data = loaded_data # <--- AND HERE FOR CONSISTENCY

            # Clear existing editor state
            self._clear_editor_state()

            character_data = loaded_data.get('character', {})
            parts_structure = character_data.get('parts', {})

            # Load bounding_box.yaml for global offset
            effective_bounding_box_offset = QPointF(0, 0)
            raw_bbox_left = 0.0
            raw_bbox_top = 0.0

            if self.character_dir:
                bounding_box_path = os.path.join(self.character_dir, "bounding_box.yaml")
                if os.path.exists(bounding_box_path):
                    try:
                        with open(bounding_box_path, 'r') as f:
                            bbox_data = yaml.safe_load(f)
                        if isinstance(bbox_data, dict) and 'left' in bbox_data and 'top' in bbox_data:
                            raw_bbox_left = float(bbox_data['left'])
                            raw_bbox_top = float(bbox_data['top'])
                            logging.info(f"Loaded raw bounding box values: left={raw_bbox_left}, top={raw_bbox_top}")
                        else:
                            logging.warning(f"Invalid bounding_box.yaml format in {bounding_box_path}")
                    except Exception as e:
                        logging.warning(f"Error loading bounding_box.yaml from {bounding_box_path}: {e}")
                else:
                    logging.info(f"bounding_box.yaml not found in {self.character_dir}, raw bbox offset will be (0,0).")

                alignment_delta_x = 0.0
                alignment_delta_y = 0.0
                alignment_offset_path = os.path.join(self.character_dir, "alignment_offset.yaml")
                if os.path.exists(alignment_offset_path):
                    try:
                        with open(alignment_offset_path, 'r') as f:
                            align_data = yaml.safe_load(f)
                        if isinstance(align_data, dict) and 'delta_x' in align_data and 'delta_y' in align_data:
                            alignment_delta_x = float(align_data['delta_x'])
                            alignment_delta_y = float(align_data['delta_y'])
                            logging.info(f"Loaded alignment delta: dx={alignment_delta_x}, dy={alignment_delta_y}")
                        else:
                            logging.warning(f"Invalid alignment_offset.yaml format in {alignment_offset_path}")
                    except Exception as e:
                        logging.warning(f"Error loading alignment_offset.yaml from {alignment_offset_path}: {e}")
                else:
                    logging.info(f"alignment_offset.yaml not found in {self.character_dir}, using delta (0,0).")

                effective_bounding_box_offset = QPointF(raw_bbox_left - alignment_delta_x, raw_bbox_top - alignment_delta_y)
                logging.info(f"Effective bounding box offset for positioning: {effective_bounding_box_offset}")
            else:
                logging.warning("self.character_dir is not set. Cannot load bounding box or alignment offset. Effective offset will be (0,0).")


            # Load skeleton data if available (for positioning)
            current_skeleton = None
            if self.skeleton_data: # Use already loaded skeleton
                 current_skeleton = self.skeleton_data
            elif self.character_dir: # Try loading from character_dir
                 skel_path = os.path.join(self.character_dir, "char_cfg.yaml")
                 if os.path.exists(skel_path):
                     try:
                         with open(skel_path, 'r') as f:
                             current_skeleton = yaml.safe_load(f)
                         logging.info(f"Loaded associated skeleton from {skel_path} for positioning.")
                     except Exception as e:
                          logging.warning(f"Error loading associated skeleton {skel_path}: {e}")

            skeleton_map = {}
            if current_skeleton:
                skel_struct = current_skeleton.get('skeleton', [])
                if isinstance(skel_struct, list):
                     skeleton_map = {j.get('name'): j.get('loc') for j in skel_struct if j.get('name') and j.get('loc')}
                elif isinstance(skel_struct, dict):
                     skeleton_map = {name: [d.get('x', 0), d.get('y', 0)] for name, d in skel_struct.items() if isinstance(d, dict)}

            # Load parts
            for name, info in parts_structure.items():
                # Resolve relative paths
                if 'svg_path' in info and not os.path.isabs(info['svg_path']):
                    info['svg_path'] = os.path.normpath(os.path.join(base_path, info['svg_path']))
                if 'image_path' in info and not os.path.isabs(info['image_path']):
                     info['image_path'] = os.path.normpath(os.path.join(base_path, info['image_path']))

                part_info = PartInfo(name, info)
                self.parts[name] = part_info

                # Create visual item if possible
                if not part_info.qpainter_path.isEmpty() or (hasattr(part_info, 'image_path') and part_info.image_path):
                    editor_item = CharacterPartItem(part_info)

                    # --- Corrected Positioning Logic ---
                    initial_pos_data = info.get('position') # 1. Check for saved project position
                    roi_data = info.get('roi')            # 2. Check for ROI from extraction

                    if initial_pos_data and isinstance(initial_pos_data, dict):
                        # Use saved position if available
                        saved_x = initial_pos_data.get('x', 0)
                        saved_y = initial_pos_data.get('y', 0)
                        # Saved positions are assumed to be already correct absolute scene positions or relative to the desired aligned origin.
                        # So, if they exist, they should ideally bypass the bbox offsetting,
                        # OR they should be saved relative to the texture.png origin, just like ROI.
                        # For now, let's assume saved positions are final and don't apply effective_bounding_box_offset.
                        # This might need review based on how save_project stores them.
                        # If saved_project positions are relative to texture origin, then uncomment and test:
                        # editor_item.setPos(saved_x - effective_bounding_box_offset.x(), saved_y - effective_bounding_box_offset.y())
                        editor_item.setOpacity(0.5)
                        editor_item.setPos(saved_x, saved_y)
                        logging.debug(f"Positioning '{name}' using saved project position: ({saved_x}, {saved_y})")
                    elif roi_data and isinstance(roi_data, (list, tuple)) and len(roi_data) == 4:
                        # Use ROI top-left corner if available (from parts_info.json)
                        try:
                            x_min, y_min = int(roi_data[0]), int(roi_data[1]) # These are relative to texture.png
                            editor_item.setPos(x_min - effective_bounding_box_offset.x(), y_min - effective_bounding_box_offset.y())
                            logging.debug(f"Positioning '{name}' using ROI with effective BBox offset: ({x_min - effective_bounding_box_offset.x()}, {y_min - effective_bounding_box_offset.y()})")
                        except (ValueError, TypeError):
                            logging.warning(f"Invalid ROI data for '{name}': {roi_data}. Falling back.")
                            # Fallback logic (e.g., to skeleton or origin) should also use effective_bounding_box_offset
                            if name in skeleton_map:
                                loc = skeleton_map[name]
                                if len(loc) >= 2:
                                    editor_item.setPos(loc[0] - effective_bounding_box_offset.x(), loc[1] - effective_bounding_box_offset.y())
                                    logging.debug(f"Positioning '{name}' using skeleton (ROI fallback) with effective BBox offset: ({loc[0] - effective_bounding_box_offset.x()}, {loc[1] - effective_bounding_box_offset.y()})")
                                # ... more error handling ...
                            else:
                                editor_item.setPos(0 - effective_bounding_box_offset.x(), 0 - effective_bounding_box_offset.y())
                    elif name in skeleton_map: # 3. Fallback to skeleton joint location
                        loc = skeleton_map[name] # These are relative to texture.png
                        if len(loc) >= 2:
                             editor_item.setPos(loc[0] - effective_bounding_box_offset.x(), loc[1] - effective_bounding_box_offset.y())
                             logging.debug(f"Positioning '{name}' using skeleton (fallback) with effective BBox offset: ({loc[0] - effective_bounding_box_offset.x()}, {loc[1] - effective_bounding_box_offset.y()})")
                    else:
                        logging.warning(f"Could not determine initial position for '{name}'. Placing at (0,0) relative to effective BBox offset.")
                        editor_item.setPos(0 - effective_bounding_box_offset.x(), 0 - effective_bounding_box_offset.y())
                    # --- End Corrected Positioning Logic ---

                    # Restore other saved properties
                    editor_item.setZValue(info.get('z_value', 0))
                    # Check if this part should be fixed (either from data or if it's the torso)
                    is_fixed_from_data = info.get('is_fixed', False)
                    if name == "torso":
                        editor_item.is_fixed = True
                        editor_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                        logging.info(f"Part '{name}' automatically marked as fixed (torso).")
                    else:
                        editor_item.is_fixed = is_fixed_from_data
                        # Explicitly set movable flag based on loaded fixed state
                        editor_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not is_fixed_from_data)
                    if 'transform' in info:
                         # TODO: Implement _dict_to_transform
                         pass # editor_item.setTransform(_dict_to_transform(info['transform']))
                    if 'motion_path' in info:
                         # TODO: Implement _points_to_qpainterpath
                         pass # motion_path = _points_to_qpainterpath(info['motion_path'])
                         # if motion_path: editor_item.set_motion_path(motion_path)
                    if 'end_effector' in info:
                         ee = info['end_effector']
                         if isinstance(ee, dict):
                             editor_item.end_effector_offset = QPointF(ee.get('x', 0), ee.get('y', 0))
                             editor_item._update_end_effector_marker()

                    # Add item to the scene FIRST, then update properties
                    self.editor_scene.addItem(editor_item)
                    # STORE the created item in the dictionary
                    self.editor_items[name] = editor_item

                    # Add name to the list widget in the UI
                    list_item = QListWidgetItem(name)
                    list_item.setData(Qt.ItemDataRole.UserRole, name)
                    self.parts_list.addItem(list_item)
                else:
                    logging.warning(f"Part '{name}' has no visual representation (SVG or Image). Skipping add to scene.")

            # --- Automatic Joint Creation from Skeleton --- #
            # Use skeleton data from the loaded parts_info.json directly if available
            skeleton_from_parts_info = character_data.get('skeleton')

            # Define mapping from skeleton joint names to part names
            # This mapping might need adjustment based on the specific character structure
            skeleton_to_part_map = {
                # Skeleton Name : Part Name
                "neck": "head",
                "torso": "torso", # Direct match
                "left_shoulder": "left_arm_upper",
                "left_elbow": "left_arm_lower",
                "right_shoulder": "right_arm_upper",
                "right_elbow": "right_arm_lower",
                "left_hip": "left_leg_upper",
                "left_knee": "left_leg_lower",
                "right_hip": "right_leg_upper",
                "right_knee": "right_leg_lower",
                # Names without direct part correspondence (e.g., end points or base)
                "root": "torso", # Often root connects to torso or a base
                "hip": "torso",
                "left_hand": "left_arm_lower", # Hand connects to lower arm
                "right_hand": "right_arm_lower",
                "left_foot": "left_leg_lower",
                "right_foot": "right_leg_lower",
            }

            if isinstance(skeleton_from_parts_info, list) and skeleton_from_parts_info:
                logging.info("Attempting to create joints automatically based on skeleton in parts_info.json...")
                joint_count = 0
                for joint_info in skeleton_from_parts_info:
                    child_skeleton_name = joint_info.get('name')
                    parent_skeleton_name = joint_info.get('parent')
                    loc_data = joint_info.get('loc')

                    if child_skeleton_name and parent_skeleton_name and loc_data and len(loc_data) >= 2:
                        # Use the map to get the actual part names
                        child_part_name = skeleton_to_part_map.get(child_skeleton_name)
                        parent_part_name = skeleton_to_part_map.get(parent_skeleton_name)

                        if not child_part_name or not parent_part_name:
                            logging.debug(f"Skipping auto-joint: Could not map skeleton names '{parent_skeleton_name}' or '{child_skeleton_name}' to part names.")
                            continue

                        child_item = self.editor_items.get(child_part_name)
                        parent_item = self.editor_items.get(parent_part_name)

                        if child_item and parent_item:
                            try:
                                # Use anchor_offset as the local joint position
                                parent_anchor_pos = parent_item.anchor_offset
                                child_anchor_pos = child_item.anchor_offset

                                joint_name = f"Joint_{parent_item.part_info.name}-{child_item.part_info.name}"
                                # The parent_pos and child_pos from EditorView are scene positions of clicks.
                                # For the Joint object, we need positions local to each part item, referring to their anchors.
                                joint = Joint(parent_item, child_item, parent_anchor_pos, child_anchor_pos, name=joint_name)
                                self.joints.append(joint)

                                # Set relationships (needed for kinematics/simulation)
                                parent_item.child_joints.append(joint)
                                child_item.parent_joint = joint

                                logging.info(f"Created joint: {joint_name}")
                                self.statusBar().showMessage(f"Created joint: {joint_name}")

                                # Create the joint using the new anchor_offsets
                                self._create_and_add_joint(parent_item, child_item,
                                                          parent_item.anchor_offset, child_item.anchor_offset)
                                joint_count += 1
                            except Exception as e:
                                logging.warning(f"Could not automatically create joint between mapped parts '{parent_part_name}' and '{child_part_name}' (from skeleton {parent_skeleton_name} -> {child_skeleton_name}) at {loc_data}: {e}")
                        else:
                            logging.debug(f"Skipping auto-joint: Mapped Parent ('{parent_part_name}') or Child ('{child_part_name}') item not found in editor_items.")
                    else:
                         logging.debug(f"Skipping auto-joint: Missing info in skeleton entry: {joint_info}")

                if joint_count > 0:
                    logging.info(f"Automatically created {joint_count} joints from skeleton data.")
            else:
                 logging.info("No skeleton data found in parts_info.json or it's empty. Skipping automatic joint creation.")
            # --- End Automatic Joint Creation ---

            # Load joints if they exist in the data (Saved project joints - might overlap with auto-created)
            joints_structure = loaded_data.get('joints', [])
            for joint_data in joints_structure:
                 parent_name = joint_data.get('parent')
                 child_name = joint_data.get('child')
                 parent_pos_data = joint_data.get('parent_pos')
                 child_pos_data = joint_data.get('child_pos')

                 if parent_name in self.editor_items and child_name in self.editor_items and parent_pos_data and child_pos_data:
                     parent_item = self.editor_items[parent_name]
                     child_item = self.editor_items[child_name]
                     parent_pos = QPointF(parent_pos_data.get('x', 0), parent_pos_data.get('y', 0))
                     child_pos = QPointF(child_pos_data.get('x', 0), child_pos_data.get('y', 0))

                     # Create and add the joint
                     self._create_and_add_joint(parent_item, child_item, parent_pos, child_pos)
                 else:
                      logging.warning(f"Could not load joint due to missing parts or positions: {joint_data}")

            # Load cam info
            cam_center_data = loaded_data.get("cam_center")
            if cam_center_data and isinstance(cam_center_data, dict):
                 self.driving_cam_center = QPointF(cam_center_data.get('x', 0), cam_center_data.get('y', 0))
                 self._update_cam_center_marker() # Visualize it

            cam_follower_name = loaded_data.get("cam_follower")
            if cam_follower_name and cam_follower_name in self.editor_items:
                 self.cam_follower_item = self.editor_items[cam_follower_name]
                 logging.info(f"Loaded cam follower: {cam_follower_name}")

            # Zoom to fit the loaded character
            if self.editor_items: # Ensure there are items to fit
                self.editor_view.zoom_to_fit()
                logging.info("Zoomed to fit loaded character in editor view.")

            self.statusBar().showMessage(f"Loaded {len(self.parts)} parts and {len(self.joints)} joints.")

            # Enable alignment button after parts are loaded
            self.save_alignment_btn.setEnabled(True)

            # --- Initialize the NEW IK system based on loaded data ---
            logging.debug(f"Before IK init check: self.current_parts_info_data is set: {self.current_parts_info_data is not None}")
            logging.debug(f"Before IK init check: len(self.editor_items): {len(self.editor_items)}")
            if self.current_parts_info_data and self.editor_items: # Ensure necessary data is present
                logging.info("Calling _initialize_new_ik_skeleton_definitions from load_parts.")
                self._initialize_new_ik_skeleton_definitions()
            else:
                logging.warning("Skipping IK skeleton initialization in load_parts: current_parts_info_data or editor_items missing.")
            # --- End NEW IK System Initialization ---

        except Exception as e:
            logging.error(f"Error loading parts: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Load Error", f"Failed to load character parts: {e}")
            self._clear_editor_state()

    def _clear_editor_state(self):
        """Clears all parts, joints, and related state from the editor."""
        logging.debug("Clearing editor state...")
        # Clear parts and their visuals from the scene and list
        for item in self.editor_items.values():
            item.update_motion_path_visual(None) # Clear persistent path visual
            if item.scene() == self.editor_scene:
                self.editor_scene.removeItem(item)
        self.editor_items.clear()
        self.parts.clear()
        self.joints.clear()
        # self.kinematic_chains.clear() # REMOVED
        self._clear_mechanism_visuals() # Clear mechanism visuals and layers
        self._clear_body_parts_visualization() # Clear body parts visualization
        self._clear_body_parts_visualization_image_view() # Clear image view body parts visualization
        # self.cam_follower_item = None # No longer needed with automatic approach
        # self.driving_cam_center = None # No longer needed with automatic approach

        # Reset property widgets
        self.z_value_spin.setValue(0)
        self.z_value_spin.setEnabled(False)
        self.fixed_part_check.setChecked(False)
        self.fixed_part_check.setEnabled(False)

        # Disable alignment button when clearing state
        self.save_alignment_btn.setEnabled(False)

        # Clear new IK system state
        logging.info("[ATTR_DEBUG] In _clear_editor_state: About to access self.sim_dynamic_joints (getter) and call .clear()")
        if hasattr(self, '_sim_dynamic_joints_data') and isinstance(self._sim_dynamic_joints_data, dict):
            self._sim_dynamic_joints_data.clear()
            logging.info("[ATTR_DEBUG] In _clear_editor_state: self._sim_dynamic_joints_data.clear() was called.")
        elif not hasattr(self, '_sim_dynamic_joints_data'):
            logging.warning("[ATTR_DEBUG] In _clear_editor_state: _sim_dynamic_joints_data was MISSING. Initializing as empty dict.")
            self._sim_dynamic_joints_data = {}
        else:
            logging.warning("[ATTR_DEBUG] In _clear_editor_state: _sim_dynamic_joints_data was missing, so no clear() called on sim_dynamic_joints.")

        self.sim_selected_component_key = None
        # ... rest of the method

    def get_selected_editor_item(self):
        """Returns the currently selected CharacterPartItem in the editor scene."""
        # Guard against calls during initialization before editor_scene exists
        if not hasattr(self, 'editor_scene') or self.editor_scene is None:
            return None

        selected = self.editor_scene.selectedItems()
        if selected and isinstance(selected[0], CharacterPartItem):
            return selected[0]
        # Fallback to list selection if scene has no selection
        selected_list = self.parts_list.selectedItems()
        if selected_list:
            part_name = selected_list[0].data(Qt.ItemDataRole.UserRole)
            return self.editor_items.get(part_name)
        return None

    def update_part_properties(self, current_list_item, previous_list_item=None):
        """Updates the property widgets based on the selected part in the list."""
        item = None
        if current_list_item:
            part_name = current_list_item.data(Qt.ItemDataRole.UserRole)
            item = self.editor_items.get(part_name)

        if item:
            self.z_value_spin.setEnabled(True)
            self.fixed_part_check.setEnabled(True)
            # Block signals temporarily to avoid feedback loops
            self.z_value_spin.blockSignals(True)
            self.fixed_part_check.blockSignals(True)
            self.z_value_spin.setValue(item.zValue())
            self.fixed_part_check.setChecked(item.is_fixed)
            self.z_value_spin.blockSignals(False)
            self.fixed_part_check.blockSignals(False)
        else:
            self.z_value_spin.setEnabled(False)
            self.fixed_part_check.setEnabled(False)
            self.z_value_spin.setValue(0)
            self.fixed_part_check.setChecked(False)

    def _update_selected_part_z(self, value: float):
        """Slot to update the Z-value of the selected part."""
        item = self.get_selected_editor_item()
        if item:
            item.setZValue(value)
            logging.debug(f"Set Z-value of {item.part_info.name} to {value}")

    def _update_selected_part_fixed(self, state: int):
        """Slot to update the fixed status of the selected part."""
        item = self.get_selected_editor_item()
        if item:
            is_fixed = (state == Qt.CheckState.Checked.value)
            item.is_fixed = is_fixed
            item.update() # Trigger repaint to show/hide fixed marker
            logging.debug(f"Set fixed status of {item.part_info.name} to {is_fixed}")
            if is_fixed:
                # Fixed parts cannot be moved
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            else:
                 item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

    # --- Joint & Assembly Actions ---

    def _toggle_define_joint_mode(self, checked: bool):
        """Toggles the joint definition mode in the editor view."""
        if checked:
            self.editor_view.start_define_joint()
            # Uncheck other mode buttons if necessary (e.g., define motion)
            if self.define_motion_path_btn.isChecked():
                 self.define_motion_path_btn.setChecked(False)
        else:
            # If user unchecks button, ensure mode is reset in view
            if self.editor_view.current_mode == 'define_joint':
                self.editor_view.set_mode('select')

    @pyqtSlot(dict)
    def request_create_joint(self, joint_data: dict):
        """Receives joint data from EditorView signal and creates the joint."""
        parent_item = joint_data.get('parent_item')
        child_item = joint_data.get('child_item')
        parent_pos = joint_data.get('parent_pos')
        child_pos = joint_data.get('child_pos')

        if parent_item and child_item and parent_pos and child_pos:
            self._create_and_add_joint(parent_item, child_item, parent_pos, child_pos)
        else:
            logging.error(f"Invalid joint data received from view: {joint_data}")
            self.statusBar().showMessage("Error: Could not create joint.")

    def _create_and_add_joint(self, parent_item, child_item, parent_pos, child_pos):
        """Creates a Joint object, adds it to the list, and sets up relationships."""
        # Use anchor_offset as the local joint position
        parent_anchor_pos = parent_item.anchor_offset
        child_anchor_pos = child_item.anchor_offset

        joint_name = f"Joint_{parent_item.part_info.name}-{child_item.part_info.name}"
        # The parent_pos and child_pos from EditorView are scene positions of clicks.
        # For the Joint object, we need positions local to each part item, referring to their anchors.
        joint = Joint(parent_item, child_item, parent_anchor_pos, child_anchor_pos, name=joint_name)
        self.joints.append(joint)

        # Set relationships (needed for kinematics/simulation)
        parent_item.child_joints.append(joint)
        child_item.parent_joint = joint

        logging.info(f"Created joint: {joint_name}")
        self.statusBar().showMessage(f"Created joint: {joint_name}")

        # TODO: Visualize the joint in the editor?

    # --- Motion Definition Actions ---

    def _toggle_define_motion_path_mode(self, checked: bool):
        if checked:
            # Ensure IK data is initialized before attempting to define a path
            if not hasattr(self, '_sim_dynamic_joints_data') or not self._sim_dynamic_joints_data:
                QMessageBox.warning(self, "IK System Not Ready",
                                    "Please load a character and ensure its IK skeleton is defined before defining motion paths.")
                self.define_motion_path_btn.setChecked(False)
                self._active_path_definition_target_joint_id = None
                return

            # Directly query the parts_list for current selection when button is toggled ON
            selected_list_items = self.parts_list.selectedItems()
            if not selected_list_items:
                QMessageBox.warning(self, "No Component Selected", "Please select a component from the list before defining a motion path.")
                self.define_motion_path_btn.setChecked(False)
                self._active_path_definition_target_joint_id = None
                return

            current_list_widget_item = selected_list_items[0]
            target_joint_id_from_user_role = current_list_widget_item.data(Qt.ItemDataRole.UserRole)
            display_text_from_display_role = current_list_widget_item.data(Qt.ItemDataRole.DisplayRole)

            logging.info(f"[LIST_ITEM_DATA_DEBUG] For selected item '{current_list_widget_item.text()}':")
            logging.info(f"  Retrieved UserRole data: '{target_joint_id_from_user_role}' (Type: {type(target_joint_id_from_user_role)})")
            logging.info(f"  Retrieved DisplayRole data: '{display_text_from_display_role}' (Type: {type(display_text_from_display_role)})")

            target_joint_id_from_list = target_joint_id_from_user_role

            if not target_joint_id_from_list:
                QMessageBox.warning(self, "Selection Error", f"The selected component '{display_text_from_display_role}' has no associated ID (UserRole was None).")
                self.define_motion_path_btn.setChecked(False)
                self._active_path_definition_target_joint_id = None
                return

            self.sim_selected_component_key = target_joint_id_from_list
            logging.info(f"[PathDefineToggle] Using targetJointId (from UserRole): {target_joint_id_from_list}")

            self._active_path_definition_target_joint_id = target_joint_id_from_list
            logging.info(f"[PATH_DEFINE_TOGGLE_DEBUG] _active_path_definition_target_joint_id: {self._active_path_definition_target_joint_id}")

            target_joint_id_for_path = self._active_path_definition_target_joint_id

            # Access sim_dynamic_joints safely (already checked it's not None/empty above)
            # The property getter for self.sim_dynamic_joints will handle returning the dict.
            dynamic_joint_data = self.sim_dynamic_joints.get(target_joint_id_for_path)

            if dynamic_joint_data and dynamic_joint_data.get('path'):
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Icon.Question)
                msg_box.setText(f"A motion path already exists for component '{dynamic_joint_data.get('label', target_joint_id_for_path)}'.")
                msg_box.setInformativeText("Do you want to overwrite it?")
                msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg_box.setDefaultButton(QMessageBox.StandardButton.No)
                ret = msg_box.exec()
                if ret == QMessageBox.StandardButton.No:
                    self.define_motion_path_btn.setChecked(False)
                    self._active_path_definition_target_joint_id = None
                    return

            if dynamic_joint_data: # If proceeding with overwrite or new path, clear existing path data for this joint
                dynamic_joint_data['path'] = []
                if 'animation' in dynamic_joint_data: # Ensure animation dict exists
                    dynamic_joint_data['animation']['active'] = False
                self._clear_visual_motion_path_for_joint(target_joint_id_for_path)
            # else: # This case should ideally not be hit if target_joint_id_for_path is valid from selection and sim_dynamic_joints is populated
                # logging.warning(f"_toggle_define_motion_path_mode: dynamic_joint_data for '{target_joint_id_for_path}' is None, though sim_dynamic_joints itself is not. This is unexpected.")

            self.editor_view.start_define_motion_path(None) # Pass None as item, new IK system doesn't rely on CharacterPartItem here
            status_label = dynamic_joint_data.get('label', target_joint_id_for_path) if dynamic_joint_data else target_joint_id_for_path
            self.statusBar().showMessage(f"Defining motion path for component {status_label}. Draw freely. Uncheck button or right-click to cancel.")
        else:
            # This block is called when the button is unchecked, either manually or programmatically.
            self.editor_view.finish_motion_path_drawing() # This will trigger _handle_freehand_path_completed if a path was drawn
            self.statusBar().showMessage("Motion path definition stopped.")
            self._active_path_definition_target_joint_id = None # Clear the latched target

        # Update button states (clear button mainly)
        can_clear = False
        current_sim_selected_key_for_clear_btn = getattr(self, 'sim_selected_component_key', None)

        # Ensure sim_dynamic_joints backing data exists and is a dict, then check key and path
        if hasattr(self, '_sim_dynamic_joints_data') and isinstance(self._sim_dynamic_joints_data, dict) and self._sim_dynamic_joints_data and current_sim_selected_key_for_clear_btn in self._sim_dynamic_joints_data:
            joint_to_check = self._sim_dynamic_joints_data.get(current_sim_selected_key_for_clear_btn)
            if joint_to_check:
                 can_clear = bool(joint_to_check.get('path'))
        self.clear_motion_path_btn.setEnabled(can_clear)

    @pyqtSlot(list)
    def _handle_freehand_path_completed(self, points: list):
        """Receives the list of QPointF (scene coordinates) from EditorView for the NEW IK system.
        Applies it to the sim_dynamic_joint's path that was targeted during path definition.
        """
        logging.debug(f"[NEW_IK_PATH_COMPLETE] Received {len(points)} raw scene points.")

        target_joint_id = getattr(self, '_active_path_definition_target_joint_id', None)

        if not target_joint_id:
            logging.warning("[NEW_IK_PATH_COMPLETE] No active path definition target joint ID. Path not applied.")
            if self.define_motion_path_btn.isChecked():
                self.define_motion_path_btn.setChecked(False) # This also clears _active_path_definition_target_joint_id
            return

        if target_joint_id not in self.sim_dynamic_joints:
            logging.warning(f"[NEW_IK_PATH_COMPLETE] Target IK joint ID '{target_joint_id}' (from _active_path_definition_target_joint_id) not found in sim_dynamic_joints. Path not applied.")
            if self.define_motion_path_btn.isChecked():
                self.define_motion_path_btn.setChecked(False)
            return

        joint_to_animate = self.sim_dynamic_joints[target_joint_id]

        if not points or len(points) == 0: # Allow single point paths if desired, but len < 1 means no path.
            logging.warning(f"[NEW_IK_PATH_COMPLETE] Path for IK joint '{target_joint_id}' is empty. Clearing any existing path.")
            joint_to_animate['path'] = []
            joint_to_animate['animation']['active'] = False
            self._clear_visual_motion_path_for_joint(target_joint_id)
            self._update_button_states_after_path_change_new_ik(target_joint_id)
            if self.define_motion_path_btn.isChecked():
                self.define_motion_path_btn.setChecked(False)
            return

        # Store the raw scene points directly
        joint_to_animate['path'] = points
        logging.info(f"[NEW_IK_PATH_COMPLETE] Stored {len(points)} scene points for IK joint '{target_joint_id}'.")

        path_length = 0.0
        if len(points) > 1:
            for i in range(len(points) - 1):
                p1 = points[i]
                p2 = points[i+1]
                path_length += QLineF(p1, p2).length()
        joint_to_animate['animation']['pathLength'] = path_length

        is_closed = False
        if len(points) > 1:
            start_pt = points[0]
            end_pt = points[-1]
            if QLineF(start_pt, end_pt).length() < 5.0: # Threshold for considering path closed
                is_closed = True
        joint_to_animate['animation']['isClosedLoop'] = is_closed

        joint_to_animate['animation']['active'] = True
        joint_to_animate['animation']['progress'] = 0.0
        joint_to_animate['animation']['direction'] = 1
        # Speed is typically a global or per-joint setting, defaulting in _initialize_sim_dynamic_joints

        logging.info(f"[NEW_IK_PATH_COMPLETE] Motion path set for IK joint '{joint_to_animate.get('label', target_joint_id)}'. Length: {path_length:.2f}, Closed: {is_closed}")
        self.statusBar().showMessage(f"Motion path defined for '{joint_to_animate.get('label', target_joint_id)}'.")

        self._draw_visual_motion_path_for_joint(target_joint_id)
        self._update_button_states_after_path_change_new_ik(target_joint_id)

        if self.define_motion_path_btn.isChecked():
            self.define_motion_path_btn.setChecked(False) # This will call _toggle_define_motion_path_mode(False) which clears _active_path_definition_target_joint_id

    # Ensure a corresponding _update_button_states_after_path_change_new_ik method exists or rename the call
    def _update_button_states_after_path_change_new_ik(self, target_joint_id: Optional[str]):
        """Helper to update button states related to motion path for new IK system."""
        can_clear = False
        if target_joint_id and target_joint_id in self.sim_dynamic_joints:
            can_clear = bool(self.sim_dynamic_joints[target_joint_id].get('path'))

        # Ensure self.clear_motion_path_btn is accessible, e.g., self.editor_tab.clear_motion_path_btn if it's on a tab
        # Assuming self.clear_motion_path_btn is directly accessible for now:
        if hasattr(self, 'clear_motion_path_btn'):
             self.clear_motion_path_btn.setEnabled(can_clear)
        elif hasattr(self, 'editor_tab') and hasattr(self.editor_tab, 'clear_motion_path_btn'):
             self.editor_tab.clear_motion_path_btn.setEnabled(can_clear)
        else:
            logging.warning("_update_button_states_after_path_change_new_ik: clear_motion_path_btn not found.")

    def _clear_selected_item_motion_path(self):
        """Clears the motion path for the currently selected CharacterPartItem."""
        selected_item = self.get_selected_editor_item()
        if selected_item:
            selected_item.update_motion_path_visual(QPainterPath()) # Clears path and visual
            logging.info(f"Cleared motion path for '{selected_item.part_info.name}'.")
            self.statusBar().showMessage(f"Motion path cleared for '{selected_item.part_info.name}'.")
            self._update_generate_mechanism_button_state()
            self.clear_motion_path_btn.setEnabled(False)
            # If define mode is active, cancelling it might be good UX
            if self.define_motion_path_btn.isChecked():
                self.define_motion_path_btn.setChecked(False) # This will trigger _toggle_define_motion_path_mode(False)
        else:
            QMessageBox.information(self, "No Selection", "Please select a part to clear its motion path.")

    # @pyqtSlot()
    # def _update_motion_path_settings_for_selected_part(self):
    #     selected_item = self.get_selected_editor_item()
    #     if selected_item and selected_item.motion_path and not selected_item.motion_path.isEmpty():
    #         # This implies a path exists, and user is changing type/loop for it.
    #         # The EditorView._update_interpolated_path_visual (if restored) would use these.
    #         # For now, this doesn't actively change the path, but could if we re-enable smoothing.
    #         logging.debug(f"Motion path settings changed for {selected_item.part_info.name}")
    #         # Potentially re-render the path if EditorView had logic based on these combos
    #         # self.editor_view.redraw_existing_motion_path_for_item(selected_item, self.path_type_combo.currentText(), self.loop_type_combo.currentText())
    #     pass


    def _start_cam_center_selection(self):
        self.editor_view.set_mode('select_cam_center')
        self.statusBar().showMessage("Click on the scene to define the Cam Center.")

    def _handle_drawing_cancelled(self):
        """Handles cancellation of drawing operations from EditorView."""
        logging.debug("MainWindow: Drawing cancelled signal received.")
        if self.define_motion_path_btn.isChecked():
            self.define_motion_path_btn.setChecked(False) # This will call _toggle_define_motion_path_mode(False)
                                                        # which calls editor_view.finish_motion_path_drawing() or similar cleanup.
        # Add similar handling for other drawing modes if they emit this signal
        self.statusBar().showMessage("Drawing operation cancelled.")
        self._update_generate_mechanism_button_state()
        current_item = self.get_selected_editor_item()
        if current_item:
            self.clear_motion_path_btn.setEnabled(current_item.motion_path is not None and not current_item.motion_path.isEmpty())
        else:
            self.clear_motion_path_btn.setEnabled(False)

    def closeEvent(self, event):
        # Ask for confirmation before closing
        logging.info("Closing application...")
        for dialog in self.active_camera_dialogs[:]:
            try:
                if dialog:
                    dialog.stop_camera()
                    dialog.close()
            except Exception as e:
                 logging.warning(f"Error closing camera dialog: {e}")
        self.active_camera_dialogs.clear()
        self._clear_body_parts_visualization()
        self._clear_body_parts_visualization_image_view()
        super().closeEvent(event)

    # --- Layer Management --- #

    def _clear_mechanism_visuals(self):
        """Removes all generated mechanism visuals and layer controls."""
        logging.debug("Clearing all mechanism visuals and layers.")
        # Remove items from scene
        for layer_name, items in self.mechanism_visuals.items():
            for item in items:
                if item and item.scene():
                    self.editor_scene.removeItem(item)
        self.mechanism_visuals.clear()

        # Remove checkboxes from UI
        for checkbox in self.layer_checkboxes.values():
            self.layer_layout.removeWidget(checkbox)
            checkbox.deleteLater()
        self.layer_checkboxes.clear()

    def _add_mechanism_visual(self, layer_name: str, item: QGraphicsItem, visible: bool = True):
        """Adds a visual item to a specific layer and creates a toggle checkbox if needed."""
        if not item:
            return

        # Add item to the internal dictionary
        if layer_name not in self.mechanism_visuals:
            self.mechanism_visuals[layer_name] = []
        self.mechanism_visuals[layer_name].append(item)

        # Add item to the scene
        if item.scene() != self.editor_scene:
             self.editor_scene.addItem(item)
        item.setVisible(visible) # Set initial visibility

        # Create checkbox if it doesn't exist for this layer
        if layer_name not in self.layer_checkboxes:
            checkbox = QCheckBox(layer_name)
            checkbox.setChecked(visible)
            checkbox.toggled.connect(lambda checked, ln=layer_name: self._toggle_layer_visibility(ln, checked))
            self.layer_layout.addWidget(checkbox)
            self.layer_checkboxes[layer_name] = checkbox
        else:
            # Ensure checkbox reflects the desired initial visibility if layer already exists
            self.layer_checkboxes[layer_name].setChecked(visible)

    def _toggle_layer_visibility(self, layer_name: str, visible: bool):
        """Shows or hides all items associated with a specific layer."""
        logging.debug(f"Toggling layer '{layer_name}' visibility to {visible}")
        if layer_name in self.mechanism_visuals:
            for item in self.mechanism_visuals[layer_name]:
                if item:
                    item.setVisible(visible)
        else:
             logging.warning(f"Attempted to toggle visibility for non-existent layer: {layer_name}")

    # --- Options Tab Slots ---
    def _update_animation_duration(self, value: float):
        """Updates the simulation animation duration."""
        self.animation_duration = value
        logging.info(f"Animation duration set to {value} seconds.")
        self.statusBar().showMessage(f"Animation duration: {value:.1f} s")

    def _toggle_toolbar_visibility(self, visible: bool):
        """Shows or hides the main toolbar."""
        if self.main_toolbar:
            self.main_toolbar.setVisible(visible)
            logging.info(f"Toolbar visibility set to: {visible}")

    def _toggle_part_properties_visibility(self, checked: bool):
        """Shows or hides the \'Selected Part Properties\' group box."""
        if hasattr(self, 'part_properties_group') and self.part_properties_group is not None:
            self.part_properties_group.setVisible(checked)
            # The QAction text update is no longer needed as this will be controlled by OptionsTab checkbox
            logging.info(f"Part Properties visibility set to: {checked}")
        else:
            logging.warning("part_properties_group not found, cannot toggle visibility.")

    # Re-add _apply_theme method
    def _apply_theme(self, theme_name: str):
        """Applies the selected theme (Light or Dark)."""
        logging.info(f"Applying theme: {theme_name}")
        if theme_name == "Dark":
            self.setStyleSheet(self.dark_style)
        else: # Default to Light
            self.setStyleSheet(self.light_style)
        self.statusBar().showMessage(f"Theme changed to {theme_name}")

    def _load_custom_fonts(self):
        """Loads custom fonts from the gui/fonts directory."""
        fonts_dir = Path(__file__).parent / "fonts"
        font_files = [
            "Segoe UI.ttf",
            "Segoe UI Italic.ttf",
            "Segoe UI Bold.ttf",
            "Segoe UI Bold Italic.ttf"
        ]
        loaded_families = set()

        for font_file in font_files:
            font_path = fonts_dir / font_file
            if font_path.exists():
                font_id = QFontDatabase.addApplicationFont(str(font_path))
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        loaded_families.update(families)
                        logging.debug(f"Successfully loaded font: {families[0]} from {font_file}")
                    else:
                        logging.warning(f"Could not retrieve font family name from {font_file}")
                else:
                    logging.error(f"Failed to load font: {font_file} (ID was -1)")
            else:
                logging.warning(f"Font file not found: {font_path}")

        if loaded_families:
            logging.info(f"Loaded custom font families: {', '.join(loaded_families)}")
        else:
            logging.warning("No custom fonts were loaded.")

    def load_initial_data(self):
        """Loads any initial data needed for the application (placeholder)."""
        logging.info("Loading initial application data...")
        # TODO: Implement loading of default parts, configurations, etc. if needed
        pass

    # --- Skeleton Visualization --- #
    def _show_skeleton_and_joints(self, checked: bool):
        """Triggers the visualization of the skeleton and joints in both views."""
        logging.debug(f"Show Skeleton button toggled: {checked}")
        if checked:
            if not self.skeleton_data:
                logging.warning("Cannot show skeleton: No skeleton data loaded.")
                QMessageBox.information(self, "Show Skeleton", "No skeleton data is currently loaded.")
                # Uncheck the button if data is missing
                self.show_skeleton_btn.blockSignals(True)
                self.show_skeleton_btn.setChecked(False)
                self.show_skeleton_btn.blockSignals(False)
                return

            # Pass skeleton data to both views
            # Editor view
            self.editor_view.visualize_skeleton(self.skeleton_data, self.joints)
            # Image processing view
            self.image_proc_view.visualize_skeleton(self.skeleton_data, self.joints)

            # Also show body parts with 50% opacity under skeleton in both views
            logging.debug("Skeleton visualization enabled - calling _visualize_body_parts_under_skeleton()")
            self._visualize_body_parts_under_skeleton()
            self._visualize_body_parts_in_image_view()
        else:
            # Hide the visualization in both views
            logging.debug("Skeleton visualization disabled - clearing body parts visualization")
            self.editor_view._clear_skeleton_visualization()
            self.image_proc_view._clear_skeleton_visualization()
            self._clear_body_parts_visualization()
            self._clear_body_parts_visualization_image_view()

    def _create_linkage_placeholder(self, joint: Joint):
        """Creates visual placeholders for a linkage bar and joint."""
        if not joint or not joint.parent_item or not joint.child_item:
            return None, None

        parent_item = joint.parent_item
        child_item = joint.child_item

        # Get joint positions in scene coordinates
        parent_joint_scene = parent_item.mapToScene(joint.parent_pos)
        child_joint_scene = child_item.mapToScene(joint.child_pos)

        # --- Create Linkage Bar --- #
        line = QLineF(parent_joint_scene, child_joint_scene)
        link_path = QPainterPath()
        pen_width = 12 # Increased thickness
        link_path.moveTo(line.p1())
        link_path.lineTo(line.p2())

        # Use QPainterPathStroker for rounded ends
        stroker = QPainterPathStroker()
        stroker.setWidth(pen_width)
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        stroked_path = stroker.createStroke(link_path)

        link_item = QGraphicsPathItem(stroked_path)
        link_item.setPen(QPen(Qt.NoPen)) # No outline
        link_color = QColor("green")
        link_color.setAlphaF(0.7) # Slightly less transparent
        link_item.setBrush(QBrush(link_color))
        link_item.setZValue(300) # Increase Z-value significantly

        # --- Create Joint Circles --- #
        joint_radius = 6 # Slightly larger joints
        parent_joint_circle = QGraphicsEllipseItem(-joint_radius, -joint_radius, joint_radius*2, joint_radius*2)
        parent_joint_circle.setPos(parent_joint_scene)
        parent_joint_circle.setBrush(QBrush(QColor("yellow")))
        parent_joint_circle.setPen(QPen(Qt.NoPen))
        parent_joint_circle.setZValue(310) # Keep above bar

        child_joint_circle = QGraphicsEllipseItem(-joint_radius, -joint_radius, joint_radius*2, joint_radius*2)
        child_joint_circle.setPos(child_joint_scene)
        child_joint_circle.setBrush(QBrush(QColor("yellow")))
        child_joint_circle.setPen(QPen(Qt.NoPen))
        child_joint_circle.setZValue(310)

        return [link_item, parent_joint_circle, child_joint_circle]

    def _visualize_linkage_data(self, linkage_data: dict):
        """Visualizes linkage data (pivots and links) from the generation functions."""
        if not linkage_data or not isinstance(linkage_data, dict):
            return

        linkage_type = linkage_data.get("type", "unknown_linkage")
        pivots = linkage_data.get("pivots", {})
        links = linkage_data.get("links", {})

        # Visualize fixed pivots
        for pivot_name, pos in pivots.items():
            if "fixed" in pivot_name and isinstance(pos, QPointF):
                marker = QGraphicsEllipseItem(-6, -6, 12, 12) # Larger fixed pivot marker
                marker.setPos(pos)
                marker.setBrush(QColor("blue") if "fixed_a" in pivot_name else QColor("darkblue"))
                marker.setPen(QPen(QColor("black"), 1))
                self._add_mechanism_visual(f"{linkage_type} Pivot: {pivot_name}", marker)

        # Visualize moving pivot paths (if they are lists of points)
        # For now, just mark the first point of moving pivots if they exist
        for pivot_name, pos_data in pivots.items():
            if "moving" in pivot_name and isinstance(pos_data, list) and pos_data:
                pos = pos_data[0]
                if isinstance(pos, QPointF):
                    marker = QGraphicsEllipseItem(-4, -4, 8, 8)
                    marker.setPos(pos)
                    marker.setBrush(QColor("cyan"))
                    self._add_mechanism_visual(f"{linkage_type} Pivot (Moving Start): {pivot_name}", marker)
            elif "coupler_point" in pivot_name and isinstance(pos_data, list) and pos_data:
                 pos = pos_data[0]
                 if isinstance(pos, QPointF):
                    marker = QGraphicsEllipseItem(-4, -4, 8, 8)
                    marker.setPos(pos)
                    marker.setBrush(QColor("orange")) # Distinct color for coupler point
                    self._add_mechanism_visual(f"{linkage_type} Coupler Start: {pivot_name}", marker)


        # Visualize links (if they are lists of QLineF or single QLineF)
        link_pen = QPen(QColor("green"), 2)
        for link_name, link_data in links.items():
            if isinstance(link_data, list) and link_data: # Path of a link over time
                line_item = QGraphicsPathItem()
                path = QPainterPath(link_data[0].p1())
                for line_segment in link_data:
                    path.lineTo(line_segment.p2()) # This assumes segments are connected, or use p1 for non-continuous
                line_item.setPath(path) # This will only draw the first state as a polyline
                # For actual animation, one would update this path or create multiple items
                # For now, just draw the first segment of the list of lines.
                first_segment = link_data[0]
                line_graphic = QGraphicsLineItem(first_segment)
                line_graphic.setPen(link_pen)
                self._add_mechanism_visual(f"{linkage_type} Link (First State): {link_name}", line_graphic)
            elif isinstance(link_data, QLineF): # A single fixed link
                line_graphic = QGraphicsLineItem(link_data)
                line_graphic.setPen(link_pen)
                self._add_mechanism_visual(f"{linkage_type} Link: {link_name}", line_graphic)

        logging.info(f"Visualized placeholder for {linkage_type}.")

    def _visualize_gear_data(self, gear_data: dict):
        """Visualizes gear data from the generation functions."""
        if not gear_data or not isinstance(gear_data, dict) or gear_data.get("type") != "gear_pair":
            return

        driver = gear_data.get("driver_gear")
        driven = gear_data.get("driven_gear")

        if driver and isinstance(driver.get("path"), QPainterPath):
            driver_item = QGraphicsPathItem(driver["path"])
            driver_item.setPen(QPen(QColor("gray"), 2))
            driver_item.setBrush(QColor(200, 200, 200, 150))
            self._add_mechanism_visual("Driver Gear", driver_item)
            # Center marker for driver
            d_center_marker = QGraphicsEllipseItem(-4,-4,8,8); d_center_marker.setPos(driver["center"]); d_center_marker.setBrush(QColor("darkgray"))
            self._add_mechanism_visual("Driver Gear Center", d_center_marker)

        if driven and isinstance(driven.get("path"), QPainterPath):
            driven_item = QGraphicsPathItem(driven["path"])
            driven_item.setPen(QPen(QColor("darkred"), 2))
            driven_item.setBrush(QColor(139, 0, 0, 150))
            self._add_mechanism_visual("Driven Gear", driven_item)
            # Center marker for driven
            v_center_marker = QGraphicsEllipseItem(-4,-4,8,8); v_center_marker.setPos(driven["center"]); v_center_marker.setBrush(QColor("red"))
            self._add_mechanism_visual("Driven Gear Center", v_center_marker)

        logging.info("Visualized placeholder for gear pair.")

    # --- Mechanism Design Actions & Slots ---

    def _update_mechanism_inputs_ui(self, selected_type: str):
        """Shows/hides the relevant input group boxes based on the selected mechanism type."""
        self.cam_inputs_group.setVisible(selected_type == "Cam & Follower")
        self.three_bar_inputs_group.setVisible(selected_type == "3-Bar Linkage")
        self.four_bar_inputs_group.setVisible(selected_type == "4-Bar Linkage")
        self.gear_inputs_group.setVisible(selected_type == "Gears (Simple Pair)")
        # Update button state as requirements might change
        self._update_generate_mechanism_button_state()
        # Clear potentially irrelevant selected points when type changes? Optional.
        # self._clear_selected_mechanism_points()


    def _start_cam_center_selection(self):
        """Activates cam center selection mode in the editor view."""
        self.editor_view.set_mode('select_cam_center')
        self.statusBar().showMessage("Click on the scene to define the Cam Center.")

    def _start_pivot_a_selection(self):
        """Activates fixed pivot A selection mode."""
        self.editor_view.set_mode('select_pivot_a')
        self.statusBar().showMessage("Click on the scene to define Fixed Pivot A.")

    def _start_pivot_d_selection(self):
        """Activates fixed pivot D selection mode."""
        self.editor_view.set_mode('select_pivot_d')
        self.statusBar().showMessage("Click on the scene to define Fixed Pivot D.")

    def _start_driver_center_selection(self):
        """Activates driver gear center selection mode."""
        self.editor_view.set_mode('select_driver_center')
        self.statusBar().showMessage("Click on the scene to define the Driver Gear Center.")

    def _start_driven_center_selection(self):
        """Activates driven gear center selection mode."""
        self.editor_view.set_mode('select_driven_center')
        self.statusBar().showMessage("Click on the scene to define the Driven Gear Center.")

    # Slots to receive selected points from EditorView
    @pyqtSlot(QPointF)
    def _handle_cam_center_set(self, scene_pos: QPointF):
        self.selected_cam_center = scene_pos
        self._update_point_marker('cam_center', scene_pos, QColor("cyan"))
        self.statusBar().showMessage(f"Cam Center set at ({scene_pos.x():.1f}, {scene_pos.y():.1f}).")
        self._update_generate_mechanism_button_state()

    @pyqtSlot(QPointF)
    def _handle_pivot_a_set(self, scene_pos: QPointF):
        self.selected_pivot_a = scene_pos
        self._update_point_marker('pivot_a', scene_pos, QColor("blue"))
        self.statusBar().showMessage(f"Pivot A set at ({scene_pos.x():.1f}, {scene_pos.y():.1f}).")
        self._update_generate_mechanism_button_state()

    @pyqtSlot(QPointF)
    def _handle_pivot_d_set(self, scene_pos: QPointF):
        self.selected_pivot_d = scene_pos
        self._update_point_marker('pivot_d', scene_pos, QColor("darkblue"))
        self.statusBar().showMessage(f"Pivot D set at ({scene_pos.x():.1f}, {scene_pos.y():.1f}).")
        self._update_generate_mechanism_button_state()

    @pyqtSlot(QPointF)
    def _handle_driver_center_set(self, scene_pos: QPointF):
        self.selected_driver_center = scene_pos
        self._update_point_marker('driver_center', scene_pos, QColor("darkgray"))
        self.statusBar().showMessage(f"Driver Center set at ({scene_pos.x():.1f}, {scene_pos.y():.1f}).")
        self._update_generate_mechanism_button_state()

    @pyqtSlot(QPointF)
    def _handle_driven_center_set(self, scene_pos: QPointF):
        self.selected_driven_center = scene_pos
        self._update_point_marker('driven_center', scene_pos, QColor("red"))
        self.statusBar().showMessage(f"Driven Center set at ({scene_pos.x():.1f}, {scene_pos.y():.1f}).")
        self._update_generate_mechanism_button_state()


    def _update_point_marker(self, marker_type: str, pos: QPointF, color: QColor):
        """Creates or updates a visual marker for a selected point."""
        marker_attr = f"{marker_type}_marker"
        existing_marker = getattr(self, marker_attr, None)

        if existing_marker and existing_marker.scene():
            self.editor_scene.removeItem(existing_marker)

        if pos is None: # If position is cleared, just remove marker
            setattr(self, marker_attr, None)
            return

        # Create a simple circle marker
        radius = 5
        marker = QGraphicsEllipseItem(-radius, -radius, radius*2, radius*2)
        marker.setPos(pos)
        marker.setBrush(color)
        marker.setPen(QPen(Qt.NoPen))
        marker.setZValue(250) # High Z-value
        self.editor_scene.addItem(marker)
        setattr(self, marker_attr, marker) # Store reference

    def _clear_selected_mechanism_points(self):
        """Clears all stored selected points and their visual markers."""
        points_to_clear = ['cam_center', 'pivot_a', 'pivot_d', 'driver_center', 'driven_center']
        for point_type in points_to_clear:
            setattr(self, f"selected_{point_type}", None)
            self._update_point_marker(point_type, None, QColor()) # Pass None pos to remove marker
        self._update_generate_mechanism_button_state()

    def _update_generate_mechanism_button_state(self, text=None):
        """Enables the mechanism generation button based on selection and type-specific requirements."""
        selected_part = self.get_selected_editor_item()
        mechanism_type = self.mechanism_type_combo.currentText()
        enabled = False

        if selected_part:
            has_motion_path = selected_part.motion_path is not None and not selected_part.motion_path.isEmpty()

            if mechanism_type == "Cam & Follower":
                # Needs path and cam center (user selected or default available)
                can_use_default_center = self.editor_items.get("torso") is not None
                enabled = has_motion_path and (self.selected_cam_center is not None or can_use_default_center)
            elif mechanism_type == "3-Bar Linkage":
                # Needs path and pivot A
                enabled = has_motion_path and self.selected_pivot_a is not None
            elif mechanism_type == "4-Bar Linkage":
                # Needs path, pivot A, and pivot D
                enabled = has_motion_path and self.selected_pivot_a is not None and self.selected_pivot_d is not None
            elif mechanism_type == "Gears (Simple Pair)":
                # Needs driver center and driven center
                enabled = self.selected_driver_center is not None and self.selected_driven_center is not None

        self.generate_mechanism_btn.setEnabled(enabled)
        # Optional: Add tooltip explaining why it's disabled
        if not enabled:
            tooltip_text = "Select a mechanism type and provide the required inputs (e.g., select part with path, set pivots/centers)."
            self.generate_mechanism_btn.setToolTip(tooltip_text)
        else:
            self.generate_mechanism_btn.setToolTip("Generate the selected mechanism based on the current setup")


    def _generate_mechanism_auto(self) -> None:
        selected_items = self.editor_scene.selectedItems()
        selected_part: Optional[CharacterPartItem] = None

        if len(selected_items) == 1 and isinstance(selected_items[0], CharacterPartItem):
            selected_part = selected_items[0]
        elif not selected_items:
            # Try to use torso as a reference if no part is explicitly selected
            # self.torso_item should be updated if parts change
            current_torso = next((item for item in self.editor_items.values() if item.part_info.name.lower() == "torso"), None)
            if not current_torso and self.editor_items: # Fallback to first item
                 current_torso = next(iter(self.editor_items.values()), None)

            if current_torso:
                selected_part = current_torso
                self.statusBar().showMessage(f"No specific part selected, using '{selected_part.part_info.name}' as reference.", 2000)
            else:
                 # This case means no items in editor at all, or selected_part logic error
                 if self.mechanism_type_combo.currentText() != "Cam & Follower":
                     self.statusBar().showMessage("Generating default mechanism (no reference part).", 2000)
                     # Allow default generation for non-cam types without any reference part
                 else:
                    self.statusBar().showMessage("Please select a character part (especially for Cam).", 3000)
                    return
        else:
            self.statusBar().showMessage("Please select a single character part for mechanism generation.", 3000)
            return

        cam_center_scene = self.editor_scene.sceneRect().center() # Default to scene center
        if selected_part:
            cam_center_scene = selected_part.sceneBoundingRect().center()
        elif self.torso_item: # self.torso_item should be updated when parts list changes
             cam_center_scene = self.torso_item.sceneBoundingRect().center()

        user_motion_path_for_preview = None
        if selected_part and hasattr(selected_part, 'motion_path') and \
           selected_part.motion_path and not selected_part.motion_path.isEmpty():
            user_motion_path_for_preview = selected_part.motion_path

        recommendations = []
        selected_mechanism_type_str = self.mechanism_type_combo.currentText()

        # --- Recommendation 1: Based on user's current selection ---
        rec1_data = None
        if selected_mechanism_type_str == "Cam & Follower":
            if selected_part and selected_part.motion_path and not selected_part.motion_path.isEmpty():
                # Sample QPointF from the motion path instead of QPainterPath.Element
                # to provide to generate_cam_profile.
                num_motion_path_samples = 100  # Number of points to sample from the motion path
                if num_motion_path_samples == 1:
                    resampled_path_points = [selected_part.motion_path.pointAtPercent(0.0)]
                elif num_motion_path_samples > 1:
                    resampled_path_points = [selected_part.motion_path.pointAtPercent(i / (num_motion_path_samples - 1.0)) for i in range(num_motion_path_samples)]
                else: # num_motion_path_samples <= 0
                    resampled_path_points = []

                rec1_data = generate_cam_profile(
                    cam_center_scene, resampled_path_points, follower_radius=5, return_dict=True
                )
                if rec1_data:
                    rec1_data["name"] = f"{selected_part.part_info.name} Cam"
                    rec1_data["source_motion_path_item"] = selected_part # Keep reference
            else:
                # Provide a default cam if no path
                rec1_data = generate_cam_profile(cam_center_scene, [], follower_radius=5, return_dict=True, base_radius_override=40)
                if rec1_data: rec1_data["name"] = "Default Cam"
        elif selected_mechanism_type_str == "4-Bar Linkage":
            rec1_data = generate_4bar_linkage(base_pos=cam_center_scene, scale=max(30.0,selected_part.boundingRect().width()*0.1 if selected_part else 50.0))
            if rec1_data: rec1_data["name"] = "Suggested 4-Bar"
        elif selected_mechanism_type_str == "3-Bar Linkage":
            rec1_data = generate_3bar_linkage(base_pos=cam_center_scene, scale=max(30.0,selected_part.boundingRect().width()*0.1 if selected_part else 40.0))
            if rec1_data: rec1_data["name"] = "Suggested 3-Bar"
        elif selected_mechanism_type_str == "Gears (Simple Pair)":
            s_rad = max(20.0, selected_part.boundingRect().width()*0.05 if selected_part else 30.0)
            rec1_data = generate_gear_pair(center_pos=cam_center_scene, r1=s_rad, r2=s_rad*0.75)
            if rec1_data:
                rec1_data["name"] = "Suggested Gears"

        if rec1_data and user_motion_path_for_preview:
            rec1_data["user_motion_path_local"] = user_motion_path_for_preview

        if rec1_data: recommendations.append(rec1_data)
        else: recommendations.append(None) # Keep structure for dialog

        # --- Recommendation 2 & 3: Alternatives ---
        alt_types_priority = ["4-Bar Linkage", "Gears (Simple Pair)", "Cam & Follower", "3-Bar Linkage"]
        current_types_in_recs = {rec1_data.get("type") if rec1_data else None}

        for alt_type in alt_types_priority:
            if len(recommendations) >= 3: break
            if alt_type not in current_types_in_recs and alt_type is not None:
                alt_data = None
                alt_scale = max(30.0, selected_part.boundingRect().width()*0.1 if selected_part else 40.0)
                alt_ref_pos = QPointF(cam_center_scene.x() + (alt_scale*2 if len(recommendations) % 2 == 1 else -alt_scale*2),
                                      cam_center_scene.y() + (alt_scale if len(recommendations) % 2 == 1 else -alt_scale) )

                if alt_type == "Cam & Follower":
                    alt_data = generate_cam_profile(alt_ref_pos, [], follower_radius=5, return_dict=True, base_radius_override=alt_scale*0.8)
                    if alt_data: alt_data["name"] = "Alt: Basic Cam"
                elif alt_type == "4-Bar Linkage":
                    alt_data = generate_4bar_linkage(base_pos=alt_ref_pos, scale=alt_scale)
                    if alt_data: alt_data["name"] = "Alt: 4-Bar"
                elif alt_type == "3-Bar Linkage":
                    alt_data = generate_3bar_linkage(base_pos=alt_ref_pos, scale=alt_scale*0.8)
                    if alt_data: alt_data["name"] = "Alt: 3-Bar"
                elif alt_type == "Gears (Simple Pair)":
                    alt_data = generate_gear_pair(center_pos=alt_ref_pos, r1=alt_scale, r2=alt_scale*0.66)
                    if alt_data:
                        alt_data["name"] = "Alt: Gears"

                if alt_data and user_motion_path_for_preview:
                    alt_data["user_motion_path_local"] = user_motion_path_for_preview

                if alt_data:
                    recommendations.append(alt_data)
                    current_types_in_recs.add(alt_type)

        final_recommendations = [rec for rec in recommendations if rec is not None][:3]
        while len(final_recommendations) < 1 and len(final_recommendations) <3 : # Ensure at least one, up to 3.
             # Add a very generic placeholder if all generations failed
             final_recommendations.append({"type":"Info", "name":"Placeholder", "description":"Additional mechanism option."})

        if not final_recommendations:
            QMessageBox.information(self, "Mechanism Generation", "Could not generate any mechanism recommendations at this time.")
            return

        selected_mechanism_data = MechanismRecommendationDialog.get_recommendation(final_recommendations, self)

        if selected_mechanism_data and selected_mechanism_data.get("type") != "Info":
            self._clear_mechanism_visuals() # Clear previous mechanism visuals
            QMetaObject.invokeMethod(self, "_display_selected_mechanism_slot", Qt.QueuedConnection,
                                     Q_ARG(dict, selected_mechanism_data),
                                     Q_ARG(object, selected_part if selected_part else None))
        else:
            self.statusBar().showMessage("Mechanism generation cancelled or no valid selection.", 3000)

    def _handle_mechanism_type_change(self, type_str: str):
        selected_items = self.editor_scene.selectedItems()
        allow_generation = False
        if type_str == "Cam & Follower":
            if selected_items and isinstance(selected_items[0], CharacterPartItem):
                part_item = selected_items[0]
                if part_item.motion_path and not part_item.motion_path.isEmpty():
                    allow_generation = True
            # If no part selected, or part has no path, cam generation button remains disabled
            # unless we decide to allow default cam generation without selection.
        else: # For Linkages and Gears
            allow_generation = True # They can be generated with default parameters even without a selection or specific motion path

        self.generate_mechanism_btn.setEnabled(allow_generation)

    @pyqtSlot(dict, CharacterPartItem)
    def _display_selected_mechanism_slot(self, mechanism_data: Dict[str, Any], selected_part_ref: Optional[CharacterPartItem]):
        self._display_selected_mechanism(mechanism_data, selected_part_ref)

    def _display_selected_mechanism(self, mechanism_data: Dict[str, Any], selected_part: Optional[CharacterPartItem]):
        mechanism_type = mechanism_data.get("type")
        mechanism_name = mechanism_data.get("name", "Unnamed Mechanism")
        self.statusBar().showMessage(f"Visualizing: {mechanism_name} (Details TODO)", 3000)
        print(f"TODO: Implement full visualization for {mechanism_name}")
        print(f"Mechanism Data: {mechanism_data}")

        generated_visuals: List[QGraphicsItem] = []

        if mechanism_type == "Cam & Follower":
            generated_visuals = self._visualize_cam_data_detailed(mechanism_data, selected_part)
        elif mechanism_type == "linkage": # Covers both 3-bar and 4-bar from generation
            generated_visuals = self._visualize_linkage_data_detailed(mechanism_data)
        elif mechanism_type == "gears":
            generated_visuals = self._visualize_gear_data_detailed(mechanism_data)
        else:
            # Fallback for unknown types or if detailed view not implemented
            text_label = self.editor_scene.addText(f"Selected: {mechanism_name}\n(Detailed view pending for type: {mechanism_type})")
            text_label.setDefaultTextColor(UIColors.TEXT_PRIMARY)
            text_label.setPos(self.editor_scene.sceneRect().center() - QPointF(text_label.boundingRect().width()/2, text_label.boundingRect().height()/2))
            text_label.setZValue(200) # Ensure it's visible
            generated_visuals.append(text_label)

        if generated_visuals:
            # Add to scene (items in groups are added when group is added)
            # for item in generated_visuals:
            #     if not item.scene(): # Add top-level items/groups to scene
            #         self.editor_scene.addItem(item)

            layer_name = f"Generated: {mechanism_name}"
            # _clear_mechanism_visuals() is called before this method via _generate_mechanism_auto,
            # so we are always adding a new layer here.
            self._add_layer_toggle(layer_name, generated_visuals, clear_others=False) # clear_others is False because it's pre-cleared

            # The _add_layer_toggle method now handles adding items to scene,
            # self.mechanism_visuals, and creating the checkbox.

            # Old direct management here, now encapsulated in _add_layer_toggle:
            # if layer_name not in self.layer_checkboxes:
            #     checkbox = QCheckBox(layer_name)
            #     checkbox.setChecked(True)
            #     checkbox.toggled.connect(lambda checked, ln=layer_name: self._toggle_layer_visibility(ln, checked))
            #     self.layer_layout.addWidget(checkbox)
            #     self.layer_checkboxes[layer_name] = checkbox
            # else:
            #     self.layer_checkboxes[layer_name].setChecked(True)
            # self.mechanism_visuals[layer_name] = generated_visuals
            # for vis_item in generated_visuals:
            #     vis_item.setVisible(True)

            self.statusBar().showMessage(f"Displayed: {mechanism_name}", 3000)
        else:
            self.statusBar().showMessage(f"No visuals generated for {mechanism_name}.", 3000)

    def _clear_mechanism_visuals(self) -> None:
        # Existing logic to clear visuals... ensure it works with new layer management
        layers_to_remove_from_listwidget = [] # This was for a QListWidget, now direct checkboxes
        checkboxes_to_remove_from_layout = []

        for layer_name, items_in_layer in list(self.mechanism_visuals.items()): # Iterate over a copy for safe deletion
            for item in items_in_layer:
                if item and item.scene() == self.editor_scene:
                    # If item is a QGraphicsItemGroup, its children are removed automatically when group is removed.
                    self.editor_scene.removeItem(item)

            # Mark checkbox for removal from UI if it exists
            if layer_name in self.layer_checkboxes:
                checkboxes_to_remove_from_layout.append(self.layer_checkboxes.pop(layer_name))
            # No list widget items to track here as per new design

        self.mechanism_visuals.clear()

        # Remove checkboxes from their layout (self.layer_layout)
        for checkbox in checkboxes_to_remove_from_layout:
            if checkbox: # Check if not None
                self.layer_layout.removeWidget(checkbox)
                checkbox.deleteLater()

        # self.statusBar().showMessage("Cleared previous mechanism visuals.", 1500) # Message can be set by caller


    def _add_layer_toggle(self, name: str, items: List[QGraphicsItem], clear_others: bool = False) -> None:
        if clear_others:
            # This case implies that _clear_mechanism_visuals() should have been called *before* this method.
            # If for some reason it wasn't, this would be the place to defensively call it.
            # However, current flow from _generate_mechanism_auto ensures pre-clearing.
            logging.debug(f"_add_layer_toggle called with clear_others=True for layer '{name}'. Assuming pre-clear done.")
            # self._clear_mechanism_visuals() # Potentially, if not guaranteed by caller
            pass

        if not items:
            return

        # If a layer checkbox with this name already exists, remove it first to refresh.
        # This is crucial if clear_others=False and we are re-generating the same mechanism.
        if name in self.layer_checkboxes:
            old_checkbox = self.layer_checkboxes.pop(name)
            self.layer_layout.removeWidget(old_checkbox)
            old_checkbox.deleteLater()
            # Associated visuals in self.mechanism_visuals[name] should also be cleared if this is a refresh.
            # This is typically handled by an external call to _clear_mechanism_visuals before calling this.
            if name in self.mechanism_visuals:
                for old_item in self.mechanism_visuals.pop(name, []):
                    if old_item and old_item.scene():
                        self.editor_scene.removeItem(old_item)

        self.mechanism_visuals[name] = items # Store/update items for this layer name

        checkbox = QCheckBox(name)
        checkbox.setChecked(True)
        # Connect to _toggle_layer_visibility which uses self.mechanism_visuals dictionary
        checkbox.toggled.connect(lambda checked, layer_id=name: self._toggle_layer_visibility(layer_id, checked))
        self.layer_layout.addWidget(checkbox)
        self.layer_checkboxes[name] = checkbox

        for item in items:
            if item and not item.scene(): # Add to scene if not already there (e.g. top-level groups)
                self.editor_scene.addItem(item)
            if item: item.setVisible(True) # Ensure new items are visible

    # --- Simulation Methods (Placeholder/Basic Implementation) ---
    def play_simulation(self):
        """Starts or resumes the simulation."""
        if not self.kinematic_chains:
            self.build_kinematic_chains()
        if not self.kinematic_chains:
            self.statusBar().showMessage("Cannot start simulation: No valid kinematic chains.")
            return

        logging.info("Starting simulation and saving current part states...")
        # Save the current transforms of all parts as the 'initial state' for this play session.
        # This is done in EditorView, which has access to the items.
        self.editor_view._save_original_transforms()

        self.editor_view.set_mode('simulation')
        self.ik_animation_speed = 0.5 # Default animation speed, similar to JS example
        self.ik_animation_timer.start()
        self.statusBar().showMessage("Simulation running...")
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.reset_sim_btn.setEnabled(True)

    def stop_simulation(self):
        """Stops the simulation."""
        if self.ik_animation_timer.isActive():
            logging.info("Stopping simulation.")
            self.ik_animation_timer.stop()
            self.statusBar().showMessage("Simulation stopped.")
            self.editor_view.set_mode('select') # Restore editor interaction
            self.play_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        else:
            self.statusBar().showMessage("Simulation not running.")

    def reset_simulation(self):
        """Stops the simulation and resets parts to their initial state."""
        self.stop_simulation()
        logging.info("Resetting simulation state.")
        self.editor_view.reset_simulation() # View handles restoring transforms
        self.ik_animation_speed = 0.5 # Default animation speed, similar to JS example
        self.ik_animation_timer.stop()
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(False)
        self.statusBar().showMessage("Simulation reset.")

        # # self.initial_part_rotations.clear()
        # for name, item in self.editor_items.items():
        #     self.initial_part_rotations[name] = item.rotation()
        # logging.info(f"Updated initial rotations for {len(self.initial_part_rotations)} parts after reset.")

    def update_simulation(self):
        """Performs one step of the simulation (called by timer)."""
        if not self.ik_animation_timer.isActive() or not self.kinematic_chains:
            return

        delta_time = self.ik_animation_timer.interval()
        self.ik_animation_speed += delta_time
        # Loop animation based on duration
        # Ensure animation_duration is not zero to prevent division errors
        current_animation_duration = self.animation_duration
        if current_animation_duration <= 0:
            current_animation_duration = 3000

        progress = (self.ik_animation_speed % current_animation_duration) / current_animation_duration

        logging.debug(f"Sim Update: SetDuration={self.animation_duration:.2f}, ActualDuration={current_animation_duration:.2f}, Time={self.ik_animation_speed:.2f}, Prog={progress:.3f}")

        for end_effector_name, chain_items in self.kinematic_chains.items():
            # Ensure chain items are valid CharacterPartItem instances from self.editor_items
            chain = [self.editor_items.get(item.part_info.name) for item in chain_items if item.part_info.name in self.editor_items]
            if not chain or not isinstance(chain[-1], CharacterPartItem) or not chain[-1].motion_path:
                logging.debug(f"Skipping chain for {end_effector_name}: invalid chain or no motion path.")
                continue

            end_effector_part = chain[-1]
            target_pos_on_path = end_effector_part.motion_path.pointAtPercent(progress)

            # The motion path is defined in the local coordinates of the end_effector_part.
            # We need the target position in scene coordinates for the IK solver.
            target_pos_scene = end_effector_part.mapToScene(target_pos_on_path)

            logging.debug(f"  Chain '{end_effector_name}': Target Scene Pos = ({target_pos_scene.x():.1f}, {target_pos_scene.y():.1f})")
            try:
                solve_ik_ccd(chain, target_pos_scene, iterations=10, tolerance=1.5)

                # After IK, restore initial orientations for all non-fixed parts in the chain
                for item in chain:
                    if item.is_fixed: # Do not attempt to modify fixed items
                        continue

                    part_name = item.part_info.name
                    initial_rot = self.initial_part_rotations.get(part_name)

                    if initial_rot is not None:
                        current_item_pos = item.pos() # Preserve position set by IK
                        item.setRotation(initial_rot) # Restore original orientation
                        item.setPos(current_item_pos) # Re-apply position
                    else:
                        logging.warning(f"Could not find initial rotation for part '{part_name}' during simulation update.")

            except Exception as e:
                logging.error(f"Error in IK solver for {end_effector_name}: {e}", exc_info=True)
            # self.stop_simulation() # Removed to allow continuous looping
            # break # Removed to allow other chains to process even if one fails

        self.editor_scene.update() # Update scene after all chains are processed

    def build_kinematic_chains(self):
        """Builds kinematic chains from fixed parts to parts with motion paths."""
        self.kinematic_chains.clear()
        potential_end_effectors = [
            item for item in self.editor_items.values()
            if item.motion_path and not item.motion_path.isEmpty()
        ]

        if not potential_end_effectors:
            logging.info("Build Chains: No motion paths found.")
            return

        for ee_item in potential_end_effectors:
            chain = []
            current_item = ee_item
            visited_in_chain = set()
            while current_item and current_item not in visited_in_chain:
                visited_in_chain.add(current_item)
                chain.insert(0, current_item) # Prepend to get base -> tip order
                if current_item.is_fixed:
                    break # Reached a fixed base
                if current_item.parent_joint and current_item.parent_joint.parent_item != current_item:
                    current_item = current_item.parent_joint.parent_item
                else:
                    # No valid parent to continue chain upwards
                    chain = [] # Invalidate chain if no fixed base found
                    break

            if chain and chain[0].is_fixed and chain[-1] == ee_item:
                chain_name = ee_item.part_info.name  # Use part_info.name as chain identifier
                self.kinematic_chains[chain_name] = chain
                logging.info(f"Built chain for '{chain_name}': {[item.part_info.name for item in chain]}")
            elif ee_item: # Log if a chain for a specific ee_item was not valid
                logging.warning(f"Could not build valid chain for end effector '{ee_item.part_info.name}'. Ensure it connects to a fixed part.")

        if self.kinematic_chains:
            self.statusBar().showMessage(f"Built {len(self.kinematic_chains)} kinematic chain(s).")
        else:
            self.statusBar().showMessage("No valid kinematic chains built.")
            QMessageBox.warning(self, "Build Chains Failed",
                                "Could not build valid kinematic chains. Ensure parts with motion paths are connected by joints to a fixed part.")


    # --- Blueprint Generation --- #
    def generate_blueprint(self):
        """Generates an SVG blueprint of all parts."""
        if not self.editor_items:
            QMessageBox.warning(self, "No Parts Selected", "Please select parts to generate a blueprint.")
            return

        # Create a new SVG file
        svg_file = generate_blueprint_svg(self.editor_items)
        if svg_file:
            # Save the SVG file
            save_path, _ = QFileDialog.getSaveFileName(self, "Save Blueprint", "", "SVG Files (*.svg)")
            if save_path:
                try:
                    with open(save_path, 'w') as f:
                        f.write(svg_file)
                    logging.info(f"Blueprint saved to {save_path}")
                    self.statusBar().showMessage(f"Blueprint saved to {os.path.basename(save_path)}")
                except Exception as e:
                    logging.error(f"Failed to save blueprint: {e}")
                    QMessageBox.critical(self, "Save Error", f"Could not save blueprint: {e}")
            else:
                logging.warning("Blueprint not saved: No save path provided.")
        else:
            logging.warning("Blueprint not generated: No valid parts selected.")

    # --- Utility & Helper Methods ---

    def save_project(self):
        """Save the current project state (parts, joints, cam info) to a JSON file."""
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Project", self.character_dir or "", "Automata Project Files (*.json)")
        if not filepath:
            return

        logging.info(f"Saving project to {filepath}")
        try:
            project_data = {
                "project_name": "Automata Project", # Can be customized
                "parts": {},
                "joints": [],
                "selected_cam_center": None,
                "selected_pivot_a": None,
                "selected_pivot_d": None,
                "selected_driver_center": None,
                "selected_driven_center": None,
                # Store other relevant state like animation duration if needed
            }

            # Save parts data
            for name, item in self.editor_items.items():
                part_data = {
                    "name": name,
                    "svg_path_file": os.path.relpath(item.part_info.svg_path_file, self.character_dir) if self.character_dir and item.part_info.svg_path_file and os.path.isabs(item.part_info.svg_path_file) else item.part_info.svg_path_file,
                    "image_path": os.path.relpath(item.part_info.image_path, self.character_dir) if self.character_dir and item.part_info.image_path and os.path.isabs(item.part_info.image_path) else item.part_info.image_path,
                    "position": {"x": item.pos().x(), "y": item.pos().y()},
                    "z_value": item.zValue(),
                    "is_fixed": item.is_fixed,
                    "transform": transform_to_dict(item.transform()),
                    "fill_color": item.part_info.fill_color.name() if item.part_info.fill_color else None
                }
                if item.motion_path and not item.motion_path.isEmpty():
                    part_data["motion_path"] = qpainterpath_to_points(item.motion_path)
                if item.end_effector_offset:
                    part_data["end_effector"] = {"x": item.end_effector_offset.x(), "y": item.end_effector_offset.y()}
                project_data["parts"][name] = part_data

            # Save joints
            for joint in self.joints:
                joint_data = {
                    "parent_name": joint.parent_item.name,
                    "child_name": joint.child_item.name,
                    "parent_pos_local": {"x": joint.parent_pos.x(), "y": joint.parent_pos.y()},
                    "child_pos_local": {"x": joint.child_pos.x(), "y": joint.child_pos.y()},
                    "name": joint.name
                }
                project_data["joints"].append(joint_data)

            # Save selected points for mechanisms
            if self.selected_cam_center: project_data["selected_cam_center"] = {"x": self.selected_cam_center.x(), "y": self.selected_cam_center.y()}
            if self.selected_pivot_a: project_data["selected_pivot_a"] = {"x": self.selected_pivot_a.x(), "y": self.selected_pivot_a.y()}
            if self.selected_pivot_d: project_data["selected_pivot_d"] = {"x": self.selected_pivot_d.x(), "y": self.selected_pivot_d.y()}
            if self.selected_driver_center: project_data["selected_driver_center"] = {"x": self.selected_driver_center.x(), "y": self.selected_driver_center.y()}
            if self.selected_driven_center: project_data["selected_driven_center"] = {"x": self.selected_driven_center.x(), "y": self.selected_driven_center.y()}

            with open(filepath, 'w') as f:
                json.dump(project_data, f, indent=2)

            self.statusBar().showMessage(f"Project saved to {os.path.basename(filepath)}")
            logging.info("Project saved successfully.")

        except Exception as e:
            logging.error(f"Failed to save project: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Save Error", f"Failed to save project: {e}")
            self.statusBar().showMessage("Failed to save project")

    def show_about(self):
        """Displays the About dialog."""
        QMessageBox.about(self, "About Automata Designer",
                        "Automata Designer v1.0\n\n"
                        "Tool for designing 2.5D mechanical automata.\n"
                        "Features image processing, skeleton editing, part assembly, \n"
                        "kinematic simulation, cam generation, and blueprint export.")

    # --- Anchor Point Methods (New) ---
    def _toggle_test_anchors_visibility(self, checked: bool):
        if checked:
            self._add_test_anchors()
        else:
            self._clear_test_anchors()

    def _add_test_anchors(self):
        self._clear_test_anchors() # Clear any previous ones first

        anchor_configs = [
            {"id": "anchor_center", "color": QColor("magenta"), "offset_type": "center"},
            {"id": "anchor_offset_1", "color": QColor("orange"), "offset_type": "offset", "offset_val": QPointF(50, 0)},
            {"id": "anchor_offset_2", "color": QColor("cyan"), "offset_type": "offset", "offset_val": QPointF(0, -50)},
            {"id": "anchor_free_1", "color": QColor("yellow"), "offset_type": "absolute", "offset_val": QPointF(100,20)}
        ]

        base_pos = QPointF(self.editor_view.width() / 2, self.editor_view.height() / 2) # Default scene center
        ref_item = self.editor_items.get("torso")
        if not ref_item and self.editor_items:
            ref_item = next(iter(self.editor_items.values())) # Get first available part

        if ref_item:
            base_pos = ref_item.sceneBoundingRect().center()
            logging.info(f"Base position for anchors from '{ref_item.part_info.name}' center: {base_pos}")
        else:
            logging.info(f"No reference part found for anchors, using default scene center: {base_pos}")

        for config in anchor_configs:
            anchor_id = config["id"]
            color = config["color"]
            pos = QPointF(base_pos) # Start with base_pos

            if config["offset_type"] == "offset" and ref_item:
                # Offset from the reference item's top-left scene position + local offset for more stability if item moves
                # Or, more simply, offset from the calculated base_pos (which is ref_item's center)
                pos += config["offset_val"]
            elif config["offset_type"] == "absolute":
                pos = config["offset_val"] # Use as direct scene coordinates

            anchor = AnchorItem(anchor_id=anchor_id, radius=7, color=color)
            anchor.setPos(pos)
            anchor.anchorMoved.connect(self._handle_anchor_moved)
            # anchor.anchorSelected.connect(self._handle_anchor_selected) # Optional: if needed
            # anchor.anchorLostFocus.connect(self._handle_anchor_lost_focus) # Optional: if needed
            self.editor_scene.addItem(anchor)
            self.anchor_items[anchor_id] = anchor
            logging.debug(f"Added {anchor}")
        self.statusBar().showMessage(f"Added {len(self.anchor_items)} test anchors.")

    def _clear_test_anchors(self):
        if not self.anchor_items:
            return
        for anchor_id, anchor_item in list(self.anchor_items.items()): # Iterate over a copy for safe removal
            if anchor_item.scene():
                self.editor_scene.removeItem(anchor_item)
            # Disconnect signals to prevent issues if object persists temporarily
            try:
                anchor_item.anchorMoved.disconnect(self._handle_anchor_moved)
                # anchor_item.anchorSelected.disconnect(self._handle_anchor_selected)
                # anchor_item.anchorLostFocus.disconnect(self._handle_anchor_lost_focus)
            except TypeError: # Raised if not connected
                pass
            del self.anchor_items[anchor_id]
        logging.debug("Cleared all test anchors.")
        self.statusBar().showMessage("Test anchors cleared.")

    def _handle_anchor_moved(self, anchor_id: str, scene_pos: QPointF):
        logging.info(f"Anchor '{anchor_id}' was moved to scene position: ({scene_pos.x():.1f}, {scene_pos.y():.1f})")
        # Here, you could update corresponding logical points if these anchors
        # are tied to mechanism definitions, e.g.:
        # if anchor_id == "cam_center_anchor" and self.selected_cam_center is not None:
        #     self.selected_cam_center = scene_pos
        #     # maybe update a visual marker for the logical point too

    # def _handle_anchor_selected(self, anchor_id: str):
    #     logging.debug(f"Anchor '{anchor_id}' selected.")
    #     self.statusBar().showMessage(f"Anchor '{anchor_id}' selected.")

    # def _handle_anchor_lost_focus(self, anchor_id: str):
    #     logging.debug(f"Anchor '{anchor_id}' lost focus.")

    # --- End Anchor Point Methods ---

    # --- 2.5D Shape Helper Methods ---

    def _create_2d_item_group(
        self,
        shape_creation_func_front: callable, # func() -> QGraphicsItem
        shape_creation_func_back: callable,  # func(offset_x, offset_y) -> QGraphicsItem
        item_z_value: float = 0,
        offset_dx: float = 1.5,
        offset_dy: float = 1.5
    ) -> List[QGraphicsItem]:
        """
        Creates a pair of graphics items (back and front) for a 2.5D effect.
        The functions provided should return configured QGraphicsItems (e.g. QGraphicsPathItem, QGraphicsEllipseItem).
        The back function will receive offset_dx and offset_dy to shift its position.
        """
        back_item = shape_creation_func_back(offset_dx, offset_dy)
        front_item = shape_creation_func_front()

        back_item.setZValue(item_z_value)
        front_item.setZValue(item_z_value + 0.1) # Front item slightly above back

        return [back_item, front_item]


    def _create_2d_ellipse_items(self, rect: QRectF, front_brush: QBrush, back_brush: QBrush, pen: QPen, offset_scale: float = 2.0) -> List[QGraphicsItem]:
        """Creates a 2.5D ellipse (back and front QGraphicsEllipseItem). Rect defines bounds at (0,0)."""
        offset_x = offset_scale
        offset_y = offset_scale

        back_ellipse = QGraphicsEllipseItem(rect)
        back_ellipse.setPos(offset_x, offset_y)
        back_ellipse.setBrush(back_brush)
        back_ellipse.setPen(QPen(Qt.NoPen))

        front_ellipse = QGraphicsEllipseItem(rect)
        front_ellipse.setBrush(front_brush)
        front_ellipse.setPen(pen)
        return [back_ellipse, front_ellipse]

    def _create_2d_rect_items(self, rect: QRectF, front_brush: QBrush, back_brush: QBrush, pen: QPen, offset_scale: float = 2.0, back_pen: Optional[QPen] = None) -> List[QGraphicsItem]:
        """Creates a 2.5D rectangle (back and front QGraphicsRectItem). Rect defines bounds at (0,0)."""
        offset_x = offset_scale
        offset_y = offset_scale
        if back_pen is None:
            back_pen = QPen(Qt.NoPen)

        back_rect = QGraphicsRectItem(rect)
        back_rect.setPos(offset_x, offset_y)
        back_rect.setBrush(back_brush)
        back_rect.setPen(back_pen)

        front_rect = QGraphicsRectItem(rect)
        front_rect.setBrush(front_brush)
        front_rect.setPen(pen)
        return [back_rect, front_rect]

    def _create_2d_path_items(self, path: QPainterPath, front_brush: QBrush, back_brush: QBrush, pen: QPen, offset_scale: float = 2.0) -> List[QGraphicsItem]:
        """Creates a 2.5D shape from a QPainterPath (back and front QGraphicsPathItem)."""
        offset_x = offset_scale
        offset_y = offset_scale

        back_path_item = QGraphicsPathItem(path)
        back_path_item.setPos(offset_x, offset_y)
        back_path_item.setBrush(back_brush)
        back_path_item.setPen(QPen(Qt.NoPen))

        front_path_item = QGraphicsPathItem(path)
        front_path_item.setBrush(front_brush)
        front_path_item.setPen(pen)
        return [back_path_item, front_path_item]

    def _create_2d_polygon_items(self, polygon: QPolygonF, front_brush: QBrush, back_brush: QBrush, pen: QPen, offset_scale: float = 2.0) -> List[QGraphicsItem]:
        """Creates a 2.5D shape from a QPolygonF (back and front QGraphicsPolygonItem)."""
        offset_x = offset_scale
        offset_y = offset_scale

        back_poly_item = QGraphicsPolygonItem(polygon.translated(offset_x, offset_y))
        back_poly_item.setBrush(back_brush)
        back_poly_item.setPen(QPen(Qt.NoPen))

        front_poly_item = QGraphicsPolygonItem(polygon)
        front_poly_item.setBrush(front_brush)
        front_poly_item.setPen(pen)
        return [back_poly_item, front_poly_item]

    # --- Mechanism Visualization Methods (Detailed) ---

    def _visualize_cam_data_detailed(self, mechanism_data: Dict[str, Any],
                                   selected_part: Optional[CharacterPartItem]) -> List[QGraphicsItem]:
        """Generates detailed QGraphicsItems for a cam mechanism with 2.5D effect."""
        visual_items = []
        cam_center_list = mechanism_data.get("cam_center_scene", [0,0])
        cam_center = QPointF(cam_center_list[0], cam_center_list[1])

        # Cam Profile (Pitch Curve)
        # The profile_path_qt is relative to (0,0) assuming cam's center of rotation is (0,0).
        # So we add items to a group, and move the group, or add items directly and setPos on them.
        # For cam, the profile rotates, so it's simpler if path is defined around (0,0) and item is rotated at cam_center.

        cam_profile_path: QPainterPath = mechanism_data.get("profile_path_qt")
        if cam_profile_path and not cam_profile_path.isEmpty():
            pen = QPen(UIColors.CAM_BORDER, 1.5)

            # Create a parent QGraphicsItem for the cam (profile + shaft) to handle positioning and rotation
            cam_group_item = QGraphicsItemGroup() # Using QGraphicsItemGroup for simplicity

            # Cam Profile items (back and front)
            # These are added to cam_group_item, so their pos is relative to it.
            # Since cam_profile_path is already relative to its rotation center (0,0),
            # these items are added at (0,0) within the group.
            profile_items = self._create_2d_path_items(
                cam_profile_path,
                QBrush(UIColors.CAM_FRONT),
                QBrush(UIColors.CAM_BACK),
                pen,
                offset_scale=2.0
            )
            for item in profile_items:
                cam_group_item.addToGroup(item)

            # Cam Shaft
            # shaft_radius = mechanism_data.get("base_radius", 30) * 0.2  # Example from preview
            # Use a more consistent shaft size, perhaps relative to cam_profile_path bounds or a fixed moderate size.
            min_dist_to_center = mechanism_data.get("min_dist_pitch_curve_to_center", 20)
            shaft_radius = max(5.0, min_dist_to_center * 0.3 if min_dist_to_center > 0 else 10.0) # Ensure positive, reasonable size
            if "base_radius" in mechanism_data: # Prefer explicit base_radius if available from generation
                shaft_radius = max(5.0, mechanism_data["base_radius"] * 0.25)

            shaft_rect = QRectF(-shaft_radius, -shaft_radius, shaft_radius*2, shaft_radius*2)
            shaft_pen = QPen(UIColors.SHAFT_BORDER, 1)
            shaft_items = self._create_2d_ellipse_items(
                shaft_rect,
                QBrush(UIColors.SHAFT_FRONT),
                QBrush(UIColors.SHAFT_BACK),
                shaft_pen,
                offset_scale=1.5
            )
            for item in shaft_items:
                # Shaft is also centered at (0,0) within the cam_group_item
                cam_group_item.addToGroup(item)

            cam_group_item.setPos(cam_center) # Position the whole group
            cam_group_item.setZValue(100) # Ensure cam is reasonably layered
            visual_items.append(cam_group_item)

            # Optional: Visualize follower and its path if relevant part is provided
            if selected_part and selected_part.motion_path and not selected_part.motion_path.isEmpty():
                # Draw the target motion path for the follower
                target_path_item = QGraphicsPathItem(selected_part.motion_path)
                # Path is local to part, so setPos and setTransform of the path_item to match the part
                # The path itself should be drawn relative to the part item's origin (0,0)
                target_path_item.setPen(QPen(UIColors.MOTION_PATH_COLOR, 2, Qt.PenStyle.DashLine))
                # Position and transform the path item exactly like its parent part item.
                # This is crucial if the part item itself is transformed (rotated/scaled).
                # The CharacterPartItem.motion_path is already in its local coordinates.
                path_parent_group = QGraphicsItemGroup() # Group to hold the path, apply part's transform to group
                path_parent_group.addToGroup(target_path_item) # target_path_item is at (0,0) in this group
                path_parent_group.setPos(selected_part.pos())
                path_parent_group.setTransform(selected_part.sceneTransform()) # Use sceneTransform for correct world orientation and scale
                path_parent_group.setZValue(90)
                visual_items.append(path_parent_group)

    # --- New IK Animation System ---
    def _solve_single_bone_ik(self, pivot_pos: QPointF, target_pos_on_path: QPointF, limb_length: float, initial_angle_rad: float) -> QPointF:
        """Calculates the new position of a single bone's end joint.

        Args:
            pivot_pos: The scene position of the fixed pivot (parent joint).
            target_pos_on_path: The desired scene position for the end joint (on the path).
            limb_length: The length of the limb.
            initial_angle_rad: The initial angle of the limb, used if target is too close to pivot.

        Returns:
            The new scene position for the end joint.
        """
        dx = target_pos_on_path.x() - pivot_pos.x()
        dy = target_pos_on_path.y() - pivot_pos.y()
        distance_to_target = math.sqrt(dx * dx + dy * dy)

        if distance_to_target < 0.1: # Target is too close to the pivot
            new_x = pivot_pos.x() + math.cos(initial_angle_rad) * limb_length
            new_y = pivot_pos.y() + math.sin(initial_angle_rad) * limb_length
        else:
            # Place the joint along the vector from pivot to target, at limb_length distance
            new_x = pivot_pos.x() + (dx / distance_to_target) * limb_length
            new_y = pivot_pos.y() + (dy / distance_to_target) * limb_length
        return QPointF(new_x, new_y)

    def _solve_two_bone_ik(self, root_pos: QPointF, target_pos: QPointF, L1: float, L2: float, bend_dir: int,
                             initial_middle_pos_relative: QPointF, initial_end_pos_relative: QPointF) -> Dict[str, QPointF]:
        """Calculates positions for a two-bone IK chain (middle and end joints).

        Args:
            root_pos: Scene position of the root joint (e.g., shoulder).
            target_pos: Desired scene position for the end effector (e.g., wrist).
            L1: Length of the first bone (e.g., upper arm).
            L2: Length of the second bone (e.g., forearm).
            bend_dir: Bend direction (-1 for clockwise, 1 for counter-clockwise).
            initial_middle_pos_relative: Initial position of middle joint relative to root, for degenerate cases.
            initial_end_pos_relative: Initial position of end joint relative to middle, for degenerate cases.

        Returns:
            A dictionary {"M": QPointF_middle, "E": QPointF_end}.
        """
        Mx, My, Ex, Ey = 0.0, 0.0, 0.0, 0.0
        dx = target_pos.x() - root_pos.x()
        dy = target_pos.y() - root_pos.y()
        dist_sq = dx * dx + dy * dy
        dist = math.sqrt(dist_sq)

        epsilon = 0.1 # Small threshold

        if dist < epsilon: # Target is at or very near the root
            Mx = root_pos.x() + initial_middle_pos_relative.x()
            My = root_pos.y() + initial_middle_pos_relative.y()
            # End relative to NEW Middle position
            Ex = Mx + initial_end_pos_relative.x()
            Ey = My + initial_end_pos_relative.y()
            return {"M": QPointF(Mx, My), "E": QPointF(Ex, Ey)}

        # Angle of the vector from Root to Target
        angle_rt = math.atan2(dy, dx)

        # Law of cosines to find angle 'a1' at the Root joint (between R-M and R-T)
        # Clamp cos_a1 to [-1, 1] to handle unreachable targets (too far or too close)
        cos_a1_num = L1 * L1 + dist_sq - L2 * L2
        cos_a1_den = 2 * L1 * dist

        if abs(cos_a1_den) < epsilon: # Avoid division by zero if L1 or dist is ~0
            cos_a1 = 1.0 # Stretch or default pose
        else:
            cos_a1 = cos_a1_num / cos_a1_den

        cos_a1 = max(-1.0, min(1.0, cos_a1))
        a1 = math.acos(cos_a1)

        # Calculate the angle for the middle joint M
        m_angle = angle_rt + (a1 * bend_dir)

        Mx = root_pos.x() + math.cos(m_angle) * L1
        My = root_pos.y() + math.sin(m_angle) * L1

        # End effector E should ideally be at target_pos if reachable.
        # Recalculate E from M to ensure L2 is maintained, especially in stretched cases.
        dx_me = target_pos.x() - Mx
        dy_me = target_pos.y() - My
        dist_me = math.sqrt(dx_me * dx_me + dy_me * dy_me)

        if dist_me < epsilon: # M is at target, E should be L2 away in some default direction from M
            # This case needs a defined default direction for the second limb if M lands on target.
            # For now, use the initial relative position of E to M.
            # A more robust way would be to get the initial angle of the L2 limb itself.
            angle_l2_default = math.atan2(initial_end_pos_relative.y(), initial_end_pos_relative.x())
            Ex = Mx + math.cos(angle_l2_default) * L2
            Ey = My + math.sin(angle_l2_default) * L2
        else:
            Ex = Mx + (dx_me / dist_me) * L2
            Ey = My + (dy_me / dist_me) * L2

        return {"M": QPointF(Mx, My), "E": QPointF(Ex, Ey)}

    def _run_ik_animation_step(self):
        """Performs one step of the IK animation for all active components."""
        if not self.ik_animation_timer.isActive() or not self.sim_dynamic_joints:
            return

        active_animations_found = False
        for joint_id_to_animate, animated_joint_data in self.sim_dynamic_joints.items():
            anim_config = animated_joint_data.get('animation')
            path_points = animated_joint_data.get('path')

            if not anim_config or not anim_config.get('active') or not path_points or len(path_points) == 0:
                continue
            active_animations_found = True

            component_def = next((comp for comp in self.sim_selectable_components if comp['targetJointId'] == joint_id_to_animate), None)
            if not component_def:
                logging.warning(f"IK Step: Component definition not found for animating joint '{joint_id_to_animate}'. Skipping.")
                continue

            # --- Calculate Target Position on Path ---
            target_pos_on_path = QPointF() # Initialize
            if len(path_points) == 1:
                target_pos_on_path = path_points[0]
            elif anim_config.get('isClosedLoop'):
                # Progress is 0 to 1 for closed loop
                anim_config['progress'] = (anim_config['progress'] + anim_config.get('speed', self.ik_animation_speed) / (anim_config.get('pathLength', 1) or 1)) % 1.0
                if anim_config['progress'] < 0: anim_config['progress'] += 1.0

                target_dist_on_loop = anim_config['progress'] * anim_config.get('pathLength', 0)
                current_dist_along_path = 0.0
                segment_idx = 0
                # For closed loop, path_points itself should ideally contain the duplicate start point at the end for simpler segment calculation.
                # If not, the loop range needs to be up to len(path_points) and use modulo for p2.
                # Assuming path_points for closed loop has N+1 points where point[N] == point[0]
                num_segments = len(path_points) - 1 if anim_config.get('isClosedLoop') and len(path_points) > 1 else len(path_points)
                # The JS example has path.push(startPoint) for closed loops, so path_points has the duplicate.

                for segment_idx in range(len(path_points) -1): # Iterate through segments
                    p1 = path_points[segment_idx]
                    p2 = path_points[segment_idx + 1]
                    segment_qline = QLineF(p1,p2)
                    segment_len = segment_qline.length()
                    if current_dist_along_path + segment_len >= target_dist_on_loop:
                        break # Target is in this segment
                    current_dist_along_path += segment_len
                else: # Loop completed without break, means target_dist_on_loop might be exactly at the end or slightly past due to float precision
                    segment_idx = max(0, len(path_points) - 2) # Use last segment

                p1_seg = path_points[segment_idx]
                p2_seg = path_points[segment_idx + 1]
                segment_qline_final = QLineF(p1_seg, p2_seg)
                segment_len_final = segment_qline_final.length()
                segment_progress_ratio = (target_dist_on_loop - current_dist_along_path) / (segment_len_final or 1.0)
                segment_progress_ratio = max(0.0, min(1.0, segment_progress_ratio))
                target_pos_on_path = segment_qline_final.pointAt(segment_progress_ratio)

            else: # Open path, ping-pong
                anim_config['progress'] += anim_config.get('direction', 1) * anim_config.get('speed', self.ik_animation_speed)
                if anim_config['progress'] >= len(path_points) - 1:
                    anim_config['progress'] = len(path_points) - 1
                    anim_config['direction'] = -1
                elif anim_config['progress'] <= 0:
                    anim_config['progress'] = 0
                    anim_config['direction'] = 1

                idx1 = math.floor(anim_config['progress'])
                idx2 = math.ceil(anim_config['progress'])
                t_interp = anim_config['progress'] - idx1

                p1 = path_points[idx1]
                # Ensure idx2 is within bounds for p2, especially if progress is exactly len-1
                p2 = path_points[min(idx2, len(path_points) - 1)]

                target_pos_on_path = QPointF(p1.x() * (1 - t_interp) + p2.x() * t_interp,
                                                p1.y() * (1 - t_interp) + p2.y() * t_interp)

            # --- Apply IK ---
            is_two_bone_ik_chain = joint_id_to_animate in self.sim_two_bone_ik_effectors

            if is_two_bone_ik_chain:
                # targetJointId for the component is the end-effector (e.g., j_left_wrist)
                end_effector_ik_id = joint_id_to_animate
                middle_joint_ik_id = component_def['pivotJointId'] # e.g., j_left_elbow

                middle_limb_config = self.sim_limb_configs.get(middle_joint_ik_id)
                end_limb_config = self.sim_limb_configs.get(end_effector_ik_id)

                if not middle_limb_config or not end_limb_config:
                    logging.warning(f"IK Step: Missing limb config for 2-bone chain: {middle_joint_ik_id} or {end_effector_ik_id}")
                    continue

                root_joint_ik_id = middle_limb_config.get('parentAnchor') or middle_limb_config.get('parentJoint')
                if not root_joint_ik_id or root_joint_ik_id not in self.sim_dynamic_joints:
                    logging.warning(f"IK Step: Root joint '{root_joint_ik_id}' for 2-bone chain not found in sim_dynamic_joints.")
                    continue

                root_joint_data = self.sim_dynamic_joints[root_joint_ik_id]
                middle_joint_data = self.sim_dynamic_joints[middle_joint_ik_id]
                # end_effector_joint_data is animated_joint_data (already have it)

                L1 = middle_limb_config.get('length', 0)
                L2 = end_limb_config.get('length', 0)
                bend_direction = self.sim_joint_bend_directions.get(middle_joint_ik_id, 1)

                # Initial relative positions for degenerate cases (target at root)
                initial_root_pos = QPointF(root_joint_data['initial_x'], root_joint_data['initial_y'])
                initial_middle_pos = QPointF(middle_joint_data['initial_x'], middle_joint_data['initial_y'])
                initial_end_pos = QPointF(animated_joint_data['initial_x'], animated_joint_data['initial_y'])

                init_mid_rel_to_root = initial_middle_pos - initial_root_pos
                init_end_rel_to_mid = initial_end_pos - initial_middle_pos

                ik_solution = self._solve_two_bone_ik(
                    QPointF(root_joint_data['x'], root_joint_data['y']),
                    target_pos_on_path, L1, L2, bend_direction,
                    init_mid_rel_to_root, init_end_rel_to_mid
                )

                middle_joint_data['x'] = ik_solution["M"].x()
                middle_joint_data['y'] = ik_solution["M"].y()
                animated_joint_data['x'] = ik_solution["E"].x() # This is the end effector
                animated_joint_data['y'] = ik_solution["E"].y()

            else: # Single bone IK (e.g. head, upper arm, thigh)
                pivot_joint_ik_id = component_def['pivotJointId']
                if not pivot_joint_ik_id or pivot_joint_ik_id not in self.sim_dynamic_joints:
                    logging.warning(f"IK Step: Pivot joint '{pivot_joint_ik_id}' for single bone IK not found in sim_dynamic_joints.")
                    continue

                pivot_joint_data = self.sim_dynamic_joints[pivot_joint_ik_id]
                current_limb_config = self.sim_limb_configs.get(joint_id_to_animate)
                if not current_limb_config:
                    logging.warning(f"IK Step: Limb config for '{joint_id_to_animate}' not found.")
                    continue

                limb_len = current_limb_config.get('length', 0)
                # Use initial_angle from the dynamic joint data, which should store the initial config angle
                initial_ang_rad = animated_joint_data.get('initial_angle', current_limb_config.get('angle', 0.0))


                new_pos = self._solve_single_bone_ik(
                    QPointF(pivot_joint_data['x'], pivot_joint_data['y']),
                    target_pos_on_path, limb_len, initial_ang_rad
                )
                animated_joint_data['x'] = new_pos.x()
                animated_joint_data['y'] = new_pos.y()

        if active_animations_found:
            self._update_character_part_visuals_from_ik()
            self.editor_scene.update()
        else:
            # No active animations, stop timer to save resources
            if self.ik_animation_timer.isActive():
                logging.info("No active IK animations found. Stopping timer.")
                self._stop_ik_animation()

    def _update_character_part_visuals_from_ik(self):
        """Updates the position and rotation of CharacterPartItems based on sim_dynamic_joints."""
        if not self.editor_items or not self.sim_dynamic_joints or not self.sim_limb_configs:
            # logging.debug("_update_character_part_visuals_from_ik: Missing data, skipping update.")
            return

        # Update limbs first
        for child_ik_joint_id, limb_config in self.sim_limb_configs.items():
            part_name = limb_config.get('partName')
            character_part_item = self.editor_items.get(part_name)
            if not character_part_item:
                # logging.warning(f"Visual Update: Part '{part_name}' not in editor_items for limb {child_ik_joint_id}.")
                continue

            parent_ik_joint_id = limb_config.get('parentAnchor') or limb_config.get('parentJoint')
            if not parent_ik_joint_id:
                # logging.warning(f"Visual Update: No parent IK joint for limb {child_ik_joint_id} ('{part_name}').")
                continue

            parent_joint_data = self.sim_dynamic_joints.get(parent_ik_joint_id)
            child_joint_data = self.sim_dynamic_joints.get(child_ik_joint_id)

            if not parent_joint_data or not child_joint_data:
                # logging.warning(f"Visual Update: Missing dynamic joint data for {parent_ik_joint_id} or {child_ik_joint_id}.")
                continue

            parent_pos_scene = QPointF(parent_joint_data['x'], parent_joint_data['y'])
            child_pos_scene = QPointF(child_joint_data['x'], child_joint_data['y'])

            character_part_item.setPos(parent_pos_scene)
            vec_to_child = child_pos_scene - parent_pos_scene
            angle_rad = math.atan2(vec_to_child.y(), vec_to_child.x())
            angle_deg = math.degrees(angle_rad)
            character_part_item.setRotation(angle_deg)
            character_part_item.setScale(1.0)

        torso_actual_name = self.ik_part_to_actual_part_name.get('torso', 'torso')
        torso_item = self.editor_items.get(torso_actual_name)
        if torso_item:
            torso_anchor_id_for_pos = 'j_neck_base'
            if torso_anchor_id_for_pos in self.sim_joints_config and torso_anchor_id_for_pos in self.sim_dynamic_joints:
                torso_ref_anchor_data = self.sim_dynamic_joints[torso_anchor_id_for_pos]
                torso_ref_scene_pos = QPointF(torso_ref_anchor_data['x'], torso_ref_anchor_data['y'])
                torso_anchor_config = self.sim_joints_config[torso_anchor_id_for_pos]
                local_offset_to_anchor = QPointF(torso_anchor_config['xOffset'], torso_anchor_config['yOffset'])
                torso_target_item_origin_scene = torso_ref_scene_pos - local_offset_to_anchor
                torso_item.setPos(torso_target_item_origin_scene)
                torso_item.setRotation(0)
                torso_item.setScale(1.0)
            else:
                # If torso anchor setup is missing, do nothing to torso position for now.
                pass

    def _start_ik_animation(self):
        """Starts or resumes the IK-based animation."""
        if not self.sim_dynamic_joints:
            self.statusBar().showMessage("Cannot start animation: IK data not initialized.")
            logging.warning("Attempted to start IK animation, but sim_dynamic_joints is empty.")
            return

        can_animate = any(
            joint_data.get('animation', {}).get('active', False) and joint_data.get('path')
            for joint_data in self.sim_dynamic_joints.values()
        )
        if not can_animate:
            self.statusBar().showMessage("No active motion paths defined for any component.")
            return

        if self.ik_animation_timer.isActive():
            logging.info("IK animation already running.")
            return

        logging.info("Starting IK animation.")
        self.ik_animation_timer.start()
        self.statusBar().showMessage("IK Animation running...")
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.reset_sim_btn.setEnabled(True)

    def _stop_ik_animation(self):
        logging.info("Stopping IK animation.")
        self.ik_animation_timer.stop()
        self.statusBar().showMessage("IK Animation stopped.")
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(True)

    def _reset_ik_animation_state(self, reset_paths: bool = False):
        """Stops IK animation and resets all dynamic joints to their initial positions and angles.
        Optionally clears all drawn paths.
        """
        self._stop_ik_animation()
        logging.info(f"Resetting IK animation state. Reset paths: {reset_paths}")

        for joint_id, joint_data in self.sim_dynamic_joints.items():
            joint_data['x'] = joint_data['initial_x']
            joint_data['y'] = joint_data['initial_y']
            if 'initial_angle' in joint_data: # For movable joints
                joint_data['angle'] = joint_data['initial_angle'] # Reset angle if stored

            if reset_paths:
                joint_data['path'] = []
                if 'animation' in joint_data:
                    joint_data['animation']['active'] = False
                    joint_data['animation']['progress'] = 0
                    joint_data['animation']['direction'] = 1
                    joint_data['animation']['isClosedLoop'] = False
                    joint_data['animation']['pathLength'] = 0
                self._clear_visual_motion_path_for_joint(joint_id) # Clear visual path

        self._update_character_part_visuals_from_ik() # Update visuals to initial state
        self.editor_scene.update()

        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(False) # Disable after reset
        status_msg = "IK Animation state reset."
        if reset_paths:
            status_msg += " All paths cleared."
            # Update UI states for path definition and clearing
            self.define_motion_path_btn.setEnabled(self.parts_list.currentItem() is not None) # Re-enable based on selection
            self.clear_motion_path_btn.setEnabled(False) # No paths to clear now
        self.statusBar().showMessage(status_msg)

    def _reset_all_animations_button_clicked(self):
        """Handler for the new 'Reset All Animations' button."""
        reply = QMessageBox.question(self, "Reset All Animations",
                                     "This will clear all drawn motion paths and reset character pose. Continue?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._reset_ik_animation_state(reset_paths=True)

    # --- End New IK Animation System ---

    # --- Character Alignment Method (New) ---
    def save_character_alignment(self):
        """Saves the current character's alignment offset based on the torso's position."""
        if not self.character_dir:
            QMessageBox.warning(self, "Alignment Error", "Character data directory is not set. Cannot save alignment.")
            return

        torso_item = self.editor_items.get("torso")
        if not torso_item:
            selected_item = self.get_selected_editor_item()
            if selected_item:
                QMessageBox.warning(self, "Alignment Warning",
                                    f"'torso' part not found. Using selected part '{selected_item.part_info.name}' as reference for alignment. Ensure this part has a defined ROI in its PartInfo.")
                torso_item = selected_item
            else:
                QMessageBox.warning(self, "Alignment Error", "No 'torso' part found and no other part selected. Cannot determine reference for alignment.")
                return

        s_ref_new_pos = torso_item.pos()

        if not torso_item.part_info or not torso_item.part_info.roi or len(torso_item.part_info.roi) != 4:
            QMessageBox.warning(self, "Alignment Error", f"Reference part '{torso_item.part_info.name}' does not have valid ROI data. Cannot calculate alignment.")
            return

        p_ref_in_texture_x = float(torso_item.part_info.roi[0])
        p_ref_in_texture_y = float(torso_item.part_info.roi[1])

        raw_bbox_left = 0.0
        raw_bbox_top = 0.0
        bounding_box_path = os.path.join(self.character_dir, "bounding_box.yaml")
        if os.path.exists(bounding_box_path):
            try:
                with open(bounding_box_path, 'r') as f:
                    bbox_data = yaml.safe_load(f)
                if isinstance(bbox_data, dict) and 'left' in bbox_data and 'top' in bbox_data:
                    raw_bbox_left = float(bbox_data['left'])
                    raw_bbox_top = float(bbox_data['top'])
                else:
                    raise ValueError("Invalid bounding_box.yaml format")
            except Exception as e:
                QMessageBox.critical(self, "Alignment Error", f"Error reading bounding_box.yaml: {e}")
                return
        else:
            QMessageBox.critical(self, "Alignment Error", "bounding_box.yaml not found. Cannot calculate alignment.")
            return

        delta_x_new = raw_bbox_left - (p_ref_in_texture_x - s_ref_new_pos.x())
        delta_y_new = raw_bbox_top - (p_ref_in_texture_y - s_ref_new_pos.y())

        alignment_offset_path = os.path.join(self.character_dir, "alignment_offset.yaml")
        alignment_data = {'delta_x': delta_x_new, 'delta_y': delta_y_new}
        try:
            with open(alignment_offset_path, 'w') as f:
                yaml.dump(alignment_data, f, default_flow_style=False)
            logging.info(f"Saved character alignment offset: dx={delta_x_new}, dy={delta_y_new} to {alignment_offset_path}")
            QMessageBox.information(self, "Alignment Saved",
                                  f"Character alignment saved successfully.\nDelta X: {delta_x_new:.2f}, Delta Y: {delta_y_new:.2f}\nReload character to see changes.")
        except Exception as e:
            logging.error(f"Error saving alignment_offset.yaml: {e}")
            QMessageBox.critical(self, "Alignment Error", f"Could not save alignment offset: {e}")

    # --- Blueprint Generation --- #
    def generate_blueprint(self):
        pass

    # --- End Property for sim_dynamic_joints ---

    def _initialize_sim_dynamic_joints(self):
        """Initializes the runtime state of sim_dynamic_joints based on scene_joints_snapshot and configs."""
        temp_dynamic_joints = {}
        logging.info(f"Initializing sim_dynamic_joints. Have scene_joints_snapshot with {len(self.scene_joints_snapshot)} entries.")

        if not self.scene_joints_snapshot:
            logging.error("Cannot initialize sim_dynamic_joints: self.scene_joints_snapshot is empty. Make sure _initialize_new_ik_skeleton_definitions populates it.")
            logging.info("[ATTR_DEBUG] Calling sim_dynamic_joints setter with empty dict due to missing snapshot.")
            self.sim_dynamic_joints = {}
            return

        all_potential_joint_ids = set(self.sim_joints_config.keys()) | set(self.sim_limb_configs.keys())

        for joint_id in all_potential_joint_ids:
            initial_pos = self.scene_joints_snapshot.get(joint_id)
            if not initial_pos:
                logging.warning(f"Dynamic Joints Init: Initial position for joint_id '{joint_id}' not found in self.scene_joints_snapshot. Skipping.")
                continue

            abs_x = initial_pos.x()
            abs_y = initial_pos.y()
            is_anchor = joint_id in self.sim_joints_config

            base_data = {
                'id': joint_id,
                'x': abs_x, 'y': abs_y,
                'initial_x': abs_x, 'initial_y': abs_y,
                'isAnchor': is_anchor
            }
            if is_anchor:
                anchor_config = self.sim_joints_config[joint_id]
                base_data['label'] = anchor_config.get('label', joint_id)
                base_data['partName'] = anchor_config.get('partName')
            elif joint_id in self.sim_limb_configs:
                limb_config = self.sim_limb_configs[joint_id]
                base_data['label'] = limb_config.get('label', joint_id)
                base_data['partName'] = limb_config.get('partName')
                base_data['initial_angle'] = limb_config.get('angle', 0.0)
                base_data['length'] = limb_config.get('length', 0.0)
                base_data['parentAnchorId'] = limb_config.get('parentAnchor')
                base_data['parentJointId'] = limb_config.get('parentJoint')
                base_data['path'] = []
                base_data['animation'] = {
                    'active': False, 'progress': 0, 'direction': 1, 'speed': self.ik_animation_speed, # Use instance speed
                    'isClosedLoop': False, 'pathLength': 0
                }
            else:
                logging.error(f"Joint ID {joint_id} is neither in sim_joints_config nor sim_limb_configs during dynamic joint init.")
                continue

            temp_dynamic_joints[joint_id] = base_data

        logging.info(f"[ATTR_DEBUG] Calling sim_dynamic_joints setter with fully populated dict of size {len(temp_dynamic_joints)}.")
        self.sim_dynamic_joints = temp_dynamic_joints

        logging.info(f"Initialized {len(self.sim_dynamic_joints)} dynamic joints for new IK system from scene_joints_snapshot.")

    def _populate_ik_component_list_ui(self):
        """Populates the parts_list QListWidget with selectable components for the new IK system."""
        self.parts_list.clear()
        logging.info(f"Populating IK component list UI. Available selectable components: {len(self.sim_selectable_components)}")
        for comp_def in self.sim_selectable_components:
            list_item = QListWidgetItem(comp_def['name'])
            stored_data_for_user_role = comp_def['targetJointId']
            list_item.setData(Qt.ItemDataRole.UserRole, stored_data_for_user_role)
            self.parts_list.addItem(list_item)
        logging.info(f"Finished populating IK component list UI with {self.parts_list.count()} items.") # Use count() for QListWidget

    def _initialize_new_ik_skeleton_definitions(self):
        """Initializes IK data structures using loaded parts_info.json and CharacterPartItems,
        making joint coordinates relative to the torso's neck, then placing this relative skeleton
        at the torso's current scene position.
        """
        logging.info("Attempting to initialize NEW IK skeleton definitions (Relative to Torso Neck Approach)...")

        if not self.current_parts_info_data or not self.editor_items:
            logging.warning("Cannot initialize IK definitions: current_parts_info_data or editor_items not available.")
            self.sim_joints_config = {}
            self.sim_limb_lengths = {}
            self.sim_limb_configs = {}
            self.scene_joints_snapshot = {}
            self.sim_selectable_components = []
            self.sim_two_bone_ik_effectors = [] # Ensure these are also initialized as empty
            self.sim_joint_bend_directions = {} # Ensure these are also initialized as empty
            self._initialize_sim_dynamic_joints() # Corrected: Ensure this is called to set sim_dynamic_joints (even if empty)
            self._populate_ik_component_list_ui()
            return

        # Correctly access joint_map nested under 'character'
        character_data_for_ik = self.current_parts_info_data.get('character', {})
        joint_map_texture = character_data_for_ik.get('joint_map', {})

        if not joint_map_texture:
            logging.error("'character.joint_map' not found in current_parts_info_data. Cannot define IK skeleton.")
            # Still try to initialize other things to avoid subsequent AttributeErrors
            self.sim_joints_config = {}
            self.sim_limb_lengths = {}
            self.sim_limb_configs = {}
            self.scene_joints_snapshot = {}
            self.sim_selectable_components = []
            self.sim_two_bone_ik_effectors = []
            self.sim_joint_bend_directions = {}
            self._initialize_sim_dynamic_joints()
            self._populate_ik_component_list_ui()
            return

        torso_actual_name = self.ik_part_to_actual_part_name.get('torso')
        torso_item = self.editor_items.get(torso_actual_name)
        if not torso_item:
            logging.error("Torso CharacterPartItem not found. Cannot define IK skeleton relative to torso.")
            # Still try to initialize other things
            self.sim_joints_config = {}
            self.sim_limb_lengths = {}
            self.sim_limb_configs = {}
            self.scene_joints_snapshot = {}
            self.sim_selectable_components = []
            _initialize_sim_dynamic_joints()
            self._populate_ik_component_list_ui()
            return

        # Ensure ik_to_json_joint_map_config and ik_part_to_actual_part_name are populated if they can be empty initially
        if not self.ik_to_json_joint_map_config:
            logging.warning("ik_to_json_joint_map_config is empty. Attempting to use default if possible or skip IK setup.")
            # Provide a default or handle gracefully
            # For now, let's assume it must be populated from elsewhere or this is an error state.
            # If this is a critical config, we might populate with a default or raise an error.
            # For robustness, let's try to proceed but log a clear warning.
            # self.ik_to_json_joint_map_config = DEFAULT_IK_TO_JSON_MAP # Example default

        if not self.ik_part_to_actual_part_name:
            logging.warning("ik_part_to_actual_part_name is empty. This might lead to issues mapping IK parts to CharacterPartItems.")
            # self.ik_part_to_actual_part_name = DEFAULT_IK_TO_ACTUAL_PART_MAP # Example default


        torso_scene_ref_pos = torso_item.pos()
        logging.info(f"Using Torso '{torso_actual_name}' at scene reference position: {torso_scene_ref_pos} for placing the relative skeleton.")

        logging.debug(f"IK Init: joint_map_texture keys: {list(joint_map_texture.keys()) if joint_map_texture else 'None or Empty'}")
        neck_json_key = self.ik_to_json_joint_map_config.get('j_neck_base', 'neck')
        logging.debug(f"IK Init: Attempting to use neck_json_key: '{neck_json_key}'")

        if neck_json_key not in joint_map_texture:
            logging.error(f"Key '{neck_json_key}' (for j_neck_base) not found in joint_map_texture. Cannot establish texture origin offset.")
            # ... (early exit logic as before) ...
            self.sim_joints_config = {}
            self.sim_limb_lengths = {}
            self.sim_limb_configs = {}
            self.scene_joints_snapshot = {}
            self.sim_selectable_components = []
            self.sim_two_bone_ik_effectors = []
            self.sim_joint_bend_directions = {}
            self._initialize_sim_dynamic_joints()
            self._populate_ik_component_list_ui()
            return

        logging.debug(f"IK Init: Found '{neck_json_key}' in joint_map_texture.")
        neck_texture_coords_raw = joint_map_texture[neck_json_key]
        logging.debug(f"IK Init: Raw neck_texture_coords for '{neck_json_key}': {neck_texture_coords_raw}")

        if not isinstance(neck_texture_coords_raw, list) or len(neck_texture_coords_raw) != 2:
            logging.error(f"Invalid texture coordinates for '{neck_json_key}': {neck_texture_coords_raw}. Expected list of 2 numbers. Cannot establish texture origin.")
            # ... (early exit logic as before) ...
            self.sim_joints_config = {}
            self.sim_limb_lengths = {}
            self.sim_limb_configs = {}
            self.scene_joints_snapshot = {}
            self.sim_selectable_components = []
            self.sim_two_bone_ik_effectors = []
            self.sim_joint_bend_directions = {}
            self._initialize_sim_dynamic_joints()
            self._populate_ik_component_list_ui()
            return

        logging.debug(f"IK Init: neck_texture_coords_raw is a valid list of 2.")
        try:
            texture_space_origin_for_relative_skeleton = QPointF(float(neck_texture_coords_raw[0]), float(neck_texture_coords_raw[1]))
            logging.info(f"Texture space origin for relative skeleton (from '{neck_json_key}' in joint_map) is: {texture_space_origin_for_relative_skeleton}")
        except ValueError as e:
            logging.error(f"Could not convert neck coordinates '{neck_texture_coords_raw}' to float: {e}. Cannot establish texture origin.")
            self.sim_joints_config = {}
            self.sim_limb_lengths = {}
            self.sim_limb_configs = {}
            self.scene_joints_snapshot = {}
            self.sim_selectable_components = []
            self.sim_two_bone_ik_effectors = []
            self.sim_joint_bend_directions = {}
            self._initialize_sim_dynamic_joints()
            self._populate_ik_component_list_ui()
            return

        # ... rest of the method ...

        self.scene_joints_snapshot = {}
        logging.debug(f"IK Init: Populating scene_joints_snapshot. Number of items in ik_to_json_joint_map_config: {len(self.ik_to_json_joint_map_config)}")
        for ik_joint_id, json_key_for_map in self.ik_to_json_joint_map_config.items():
            if json_key_for_map in joint_map_texture:
                raw_tex_coords_list_for_joint = joint_map_texture[json_key_for_map]
                if not isinstance(raw_tex_coords_list_for_joint, list) or len(raw_tex_coords_list_for_joint) != 2:
                    logging.warning(f"IK Init: Invalid raw texture_coords for '{json_key_for_map}' (used by {ik_joint_id}): {raw_tex_coords_list_for_joint}. Skipping snapshot for this joint.")
                    continue
                try:
                    joint_texture_qpoint = QPointF(float(raw_tex_coords_list_for_joint[0]), float(raw_tex_coords_list_for_joint[1]))
                    joint_relative_to_texture_origin = joint_texture_qpoint - texture_space_origin_for_relative_skeleton
                    self.scene_joints_snapshot[ik_joint_id] = torso_scene_ref_pos + joint_relative_to_texture_origin
                    logging.debug(f"  IK Init: Snapshot for {ik_joint_id} (from json '{json_key_for_map}'): scene_pos={self.scene_joints_snapshot[ik_joint_id]}")
                except ValueError as e:
                    logging.error(f"IK Init: ValueError converting coordinates for '{json_key_for_map}' (used by {ik_joint_id}): {raw_tex_coords_list_for_joint} - {e}. Skipping snapshot.")
                    continue
            else:
                logging.warning(f"IK Init: Joint key '{json_key_for_map}' for IK joint '{ik_joint_id}' not found in joint_map_texture.")
        logging.debug(f"IK Init: Finished populating scene_joints_snapshot. Size: {len(self.scene_joints_snapshot)}")

        # Special handling for 'j_head' position based on 'j_neck_base'
        if 'j_neck_base' in self.scene_joints_snapshot and 'j_head' in self.ik_to_json_joint_map_config:
            neck_scene_pos = self.scene_joints_snapshot['j_neck_base']
            head_length = self.sim_limb_lengths.get('head', 50.0)
            if 'j_head' not in self.scene_joints_snapshot:
                logging.info(f"Estimating IK joint 'j_head' from j_neck_base ({neck_scene_pos}) with length: {head_length}")
                self.scene_joints_snapshot['j_head'] = QPointF(neck_scene_pos.x(), neck_scene_pos.y() - head_length)
            else:
                logging.info(f"Using pre-calculated scene_joints_snapshot for j_head: {self.scene_joints_snapshot['j_head']}")
        elif 'j_neck_base' not in self.scene_joints_snapshot:
            logging.error("Neck base ('j_neck_base') not in self.scene_joints_snapshot. Cannot estimate head tip for 'j_head'. Critical error.")
        elif 'j_head' not in self.ik_to_json_joint_map_config:
            logging.warning("'j_head' not defined in ik_to_json_joint_map_config. Cannot ensure its position.")
        logging.debug(f"IK Init: After j_head handling, scene_joints_snapshot size: {len(self.scene_joints_snapshot)}")

        self.sim_joints_config = {}
        torso_scene_origin_for_anchor_offsets = torso_item.pos()
        anchor_ik_ids_on_torso = ['j_neck_base', 'j_left_shoulder', 'j_right_shoulder', 'j_left_hip', 'j_right_hip']
        logging.debug(f"IK Init: Populating sim_joints_config for {len(anchor_ik_ids_on_torso)} anchors.")
        for ik_id in anchor_ik_ids_on_torso:
            if ik_id in self.scene_joints_snapshot:
                anchor_final_scene_pos = self.scene_joints_snapshot[ik_id]
                offset_x = anchor_final_scene_pos.x() - torso_scene_ref_pos.x()
                offset_y = anchor_final_scene_pos.y() - torso_scene_ref_pos.y()
                self.sim_joints_config[ik_id] = {
                    'xOffset': offset_x,
                    'yOffset': offset_y,
                    'label': ik_id,
                    'partName': torso_actual_name
                }
            else:
                logging.error(f"Scene position for essential anchor IK joint '{ik_id}' not found in scene_joints_snapshot. Skipping anchor config for it.")
        logging.debug(f"IK Init: Finished populating sim_joints_config. Size: {len(self.sim_joints_config)}")

        self.sim_limb_lengths = {}
        self.sim_limb_configs = {}
        limb_segment_definitions = [
            ('j_head',        'j_neck_base',     'head',   'head',            'Head',            'j_head',                'j_neck_base'),
            ('j_left_elbow',  'j_left_shoulder', 'upperArm', 'left_upper_arm',  'Left Upper Arm',  'j_left_elbow',          'j_left_shoulder'),
            ('j_left_wrist',  'j_left_elbow',    'forearm', 'left_forearm',    'Left Forearm',    'j_left_wrist',          'j_left_elbow'),
            ('j_right_elbow', 'j_right_shoulder','upperArm', 'right_upper_arm', 'Right Upper Arm', 'j_right_elbow',         'j_right_shoulder'),
            ('j_right_wrist', 'j_right_elbow',   'forearm', 'right_forearm',   'Right Forearm',   'j_right_wrist',         'j_right_elbow'),
            ('j_left_knee',   'j_left_hip',      'thigh','left_thigh',      'Left Thigh',      'j_left_knee',           'j_left_hip'),
            ('j_left_ankle',  'j_left_knee',     'calf', 'left_calf',       'Left Calf',       'j_left_ankle',          'j_left_knee'),
            ('j_right_knee',  'j_right_hip',     'thigh','right_thigh',     'Right Thigh',     'j_right_knee',          'j_right_hip'),
            ('j_right_ankle', 'j_right_knee',    'calf', 'right_calf',      'Right Calf',      'j_right_ankle',         'j_right_knee'),
        ]
        logging.debug(f"IK Init: Populating sim_limb_configs for {len(limb_segment_definitions)} limb segments.")
        for child_ik_id, parent_ik_id, length_key_ref, ik_part_concept, label, scene_child_key, scene_parent_key in limb_segment_definitions:
            actual_part_name = self.ik_part_to_actual_part_name.get(ik_part_concept)
            if not actual_part_name:
                logging.warning(f"No actual part name mapping for IK concept '{ik_part_concept}'. Skipping limb {child_ik_id}.")
                continue
            if scene_child_key in self.scene_joints_snapshot and scene_parent_key in self.scene_joints_snapshot:
                child_final_scene_pos = self.scene_joints_snapshot[scene_child_key]
                parent_final_scene_pos = self.scene_joints_snapshot[scene_parent_key]
                dx_len = child_final_scene_pos.x() - parent_final_scene_pos.x()
                dy_len = child_final_scene_pos.y() - parent_final_scene_pos.y()
                length = math.sqrt(dx_len**2 + dy_len**2)
                if length < 1.0:
                    logging.warning(f"Calculated length for {length_key_ref} ({actual_part_name}) is near zero ({length:.2f}). Using default of 10. ChildPos: {child_final_scene_pos}, ParentPos: {parent_final_scene_pos}")
                    length = self.sim_limb_lengths.get(length_key_ref, 10.0)
                self.sim_limb_lengths[length_key_ref] = length
                angle = math.atan2(dy_len, dx_len)
                parent_type_key = 'parentAnchor' if parent_ik_id in self.sim_joints_config else 'parentJoint'
                self.sim_limb_configs[child_ik_id] = {
                    parent_type_key: parent_ik_id,
                    'angle': angle,
                    'lengthKey': length_key_ref,
                    'length': length,
                    'label': label,
                    'partName': actual_part_name
                }
            else:
                missing_keys_info = []
                if scene_child_key not in self.scene_joints_snapshot: missing_keys_info.append(f"child '{scene_child_key}'")
                if scene_parent_key not in self.scene_joints_snapshot: missing_keys_info.append(f"parent '{scene_parent_key}'")
                logging.error(f"Missing scene positions for limb segment {parent_ik_id} -> {child_ik_id}. Keys missing: {', '.join(missing_keys_info)}. Cannot define limb. Skipping.")
        logging.debug(f"IK Init: Finished populating sim_limb_configs. Size: {len(self.sim_limb_configs)}")
        logging.debug(f"IK Init: sim_limb_lengths after calculation: {self.sim_limb_lengths}")

        self.sim_selectable_components = []
        logging.debug(f"IK Init: Populating sim_selectable_components from {len(self.sim_limb_configs)} limb configs.")
        for ik_joint_id, limb_config_entry in self.sim_limb_configs.items():
            parent_joint_id_for_limb = limb_config_entry.get('parentAnchor') or limb_config_entry.get('parentJoint')
            if limb_config_entry.get('label') and limb_config_entry.get('partName') and parent_joint_id_for_limb:
                component_to_add = {
                    'name': limb_config_entry['label'],
                    'targetJointId': ik_joint_id,
                    'pivotJointId': parent_joint_id_for_limb,
                    'partName': limb_config_entry['partName']
                }
                self.sim_selectable_components.append(component_to_add)
        logging.debug(f"IK Init: Finished populating sim_selectable_components. Size: {len(self.sim_selectable_components)}")

        self.sim_two_bone_ik_effectors = ['j_left_wrist', 'j_right_wrist', 'j_left_ankle', 'j_right_ankle']
        self.sim_joint_bend_directions = {
            'j_left_elbow': -1, 'j_right_elbow': 1,
            'j_left_knee': 1,  'j_right_knee': 1
        }

        js_limb_lengths = { 'head': 35, 'upperArm': 55, 'forearm': 50, 'thigh': 65, 'calf': 60 }
        for key, val in js_limb_lengths.items():
            if key not in self.sim_limb_lengths:
                logging.info(f"Using predefined JS length for '{key}': {val}")
                self.sim_limb_lengths[key] = val
            for limb_cfg in self.sim_limb_configs.values():
                if limb_cfg.get('lengthKey') == key:
                    limb_cfg['length'] = val
        logging.debug(f"IK Init: sim_limb_lengths after JS override: {self.sim_limb_lengths}")

        logging.debug(f"IK Init: About to call _initialize_sim_dynamic_joints.")
        self._initialize_sim_dynamic_joints()
        logging.debug(f"IK Init: Finished _initialize_sim_dynamic_joints. _sim_dynamic_joints_data size: {len(self._sim_dynamic_joints_data) if hasattr(self, '_sim_dynamic_joints_data') else 'AttributeMissing'}")

        logging.debug(f"IK Init: About to call _populate_ik_component_list_ui.")
        self._populate_ik_component_list_ui()
        logging.debug(f"IK Init: Finished _populate_ik_component_list_ui.")

    # --- Property for sim_dynamic_joints to debug access ---
