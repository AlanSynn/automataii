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
    QScrollArea, QSizePolicy, QGraphicsEllipseItem, QGraphicsLineItem
)
from PyQt6.QtGui import QColor, QPen, QAction, QPainterPath, QPixmap, QPolygonF, QTransform, QBrush, QImage, QFontDatabase, QPainterPathStroker
from PyQt6.QtCore import Qt, QPointF, QTimer, pyqtSlot, QSize, QLineF
from pathlib import Path
from typing import Optional

# Local imports (adjust paths as needed)
from .editor_view import EditorView
from .image_view import ImageProcessingView
from .part_item import CharacterPartItem
from .camera_dialog import CameraDialog
from .styling import LIGHT_STYLE, DARK_STYLE
from .options_tab import OptionsTab
from ..core.models import PartInfo, Joint
from ..kinematics.ik_solver import solve_ik_ccd
from ..generation.cam import generate_cam_profile
from ..generation.blueprint import generate_blueprint_svg
from ..utils.helpers import transform_to_dict, qpainterpath_to_points, points_to_closed_bezier_path # Utility functions

# Attempt to import image processing functionality (optional)
from ..animate.image_to_annotations import image_to_annotations
from ..animate.annotations_to_animation import annotations_to_animation
from ..animate.image_to_animation import image_to_animation
# Import body part extractor
from ..animate.body_parts_extractor import process_character

# Import new generation modules
from ..generation.linkage import generate_3bar_linkage, generate_4bar_linkage
from ..generation.gear import generate_gear_pair


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
        self.simulation_items = {} # part_name: CharacterPartItem (in simulation scene)
        self.joints = [] # List of Joint objects
        self.kinematic_chains = {} # end_effector_name: list[CharacterPartItem]
        self.mechanism_visuals = {} # layer_name: list[QGraphicsItem]
        self.layer_checkboxes = {} # layer_name: QCheckBox

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

        # Simulation Timer
        self.timer = QTimer(self)
        self.timer.setInterval(30) # Approx 33 FPS
        self.timer.timeout.connect(self.update_simulation)
        self.animation_time = 0.0
        self.animation_duration = 0.5 # Default duration set to 0.5s

        # --- Toolbar Reference ---
        self.main_toolbar = None

        # Tracking active dialogs
        self.active_camera_dialogs = []

        # --- Stylesheet Data --- (No longer need _define_stylesheets method)
        self.light_style = LIGHT_STYLE
        self.dark_style = DARK_STYLE

        # Load Parts and Styles
        self.load_initial_data()

        # Load custom application fonts
        self._load_custom_fonts()

        # Setup UI, Menus, Toolbar, and connections
        self._init_ui() # Applies initial theme
        self._create_menus()
        self._create_toolbar()
        self._connect_ui_actions()

        self.statusBar().showMessage("Ready")
        logging.info("AutomataDesigner initialized.")

    # --- UI Initialization ---

    def _init_ui(self):
        """Sets up the main user interface layout and widgets."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # --- Tab 1: Image Processing ---
        image_proc_tab = self._create_image_processing_tab()
        self.tab_widget.addTab(image_proc_tab, "Character")

        # --- Tab 2: Editor & Simulation ---
        editor_tab = self._create_editor_tab()
        self.tab_widget.addTab(editor_tab, "Mechanism Design")

        # --- Tab 3: Options ---
        self.options_tab = OptionsTab(initial_anim_duration=self.animation_duration)
        self.tab_widget.addTab(self.options_tab, "Options")

        # --- Connect Signals from EditorView ---
        self.editor_view.freehandPathCompleted.connect(self._handle_freehand_path_completed)
        self.editor_view.drawing_cancelled.connect(self._handle_drawing_cancelled) # Already exists, ensure it's used appropriately
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

    def _create_image_processing_tab(self):
        """Creates the widget and layout for the Image Processing tab."""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Left Control Panel
        control_panel = QWidget()
        # Restore preferred size policy for this tab's panel
        control_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        # control_panel.setMaximumWidth(scroll_area.width() - scroll_area.verticalScrollBar().sizeHint().width() - 5) # Ensure content fits width
        # Let setWidgetResizable handle the width constraint, focus on vertical layout
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(0, 5, 0, 0)
        panel_layout.setSpacing(10)
        panel_layout.setContentsMargins(5, 10, 5, 10) # Add some horizontal margins too
        panel_layout.setSpacing(15) # Increase spacing between groups

        # Input Group
        input_group = QGroupBox("Input Drawing")
        input_layout = QVBoxLayout(input_group)
        style = self.style()
        self.load_image_btn = QPushButton("Load Image")
        self.capture_image_btn = QPushButton("Capture Camera") # Placeholder icon
        input_layout.addWidget(self.load_image_btn)
        input_layout.addWidget(self.capture_image_btn)
        panel_layout.addWidget(input_group)

        # Processing Group
        proc_group = QGroupBox("Processing")
        proc_layout = QVBoxLayout(proc_group)
        self.process_image_btn = QPushButton(" Process Image")
        # self.edit_skeleton_btn = QPushButton(" Edit Skeleton")
        proc_layout.addWidget(self.process_image_btn)
        # proc_layout.addWidget(self.edit_skeleton_btn)
        panel_layout.addWidget(proc_group)

        # Output Group
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)
        # self.save_skeleton_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), " Save Skeleton")
        self.create_parts_btn = QPushButton(" Generate Body Parts")
        # output_layout.addWidget(self.save_skeleton_btn)
        output_layout.addWidget(self.create_parts_btn)
        panel_layout.addWidget(output_group)

        panel_layout.addStretch()

        # Right View Area
        self.image_proc_scene = QGraphicsScene()
        self.image_proc_view = ImageProcessingView(self.image_proc_scene, self)

        layout.addWidget(control_panel)
        layout.addWidget(self.image_proc_view, 1)
        return widget

    def _create_editor_tab(self):
        """Creates the widget and layout for the Editor & Simulation tab."""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # --- Left Control Panel (Rebuilt) ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(280) # Adjusted width
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        control_panel = QWidget() # Container widget for the scroll area
        # Allow vertical expansion, but let horizontal size be ignored by layout if needed
        control_panel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        # control_panel.setMaximumWidth(scroll_area.width() - scroll_area.verticalScrollBar().sizeHint().width() - 5) # Ensure content fits width
        # Let setWidgetResizable handle the width constraint, focus on vertical layout
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10) # Increased margins
        panel_layout.setSpacing(12) # Adjusted spacing

        # Group 1: Parts List
        parts_group = QGroupBox("Character Parts")
        parts_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        parts_layout = QVBoxLayout(parts_group)
        self.parts_list = QListWidget()
        self.parts_list.setToolTip("List of loaded character parts")
        self.parts_list.setMinimumHeight(100) # Ensure it doesn't collapse too much
        parts_layout.addWidget(self.parts_list)
        panel_layout.addWidget(parts_group)

        # Group 2: Selected Part Properties
        props_group = QGroupBox("Selected Part Properties")
        props_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.part_props = QFormLayout(props_group)
        self.part_props.setSpacing(8) # Spacing within the form
        self.z_value_spin = QDoubleSpinBox()
        self.z_value_spin.setRange(-100, 100)
        self.z_value_spin.setSingleStep(0.1)
        self.z_value_spin.setToolTip("Adjust Z-depth (layering)")
        self.z_value_spin.setEnabled(False) # Initially disabled
        self.fixed_part_check = QCheckBox("Fixed in Place")
        self.fixed_part_check.setToolTip("If checked, this part will not move during simulation (unless it is the root of a chain being driven by IK).")
        self.fixed_part_check.setEnabled(False)
        self.part_props.addRow("Z-Value:", self.z_value_spin)
        self.part_props.addRow(self.fixed_part_check)
        props_group.setEnabled(False) # Disable group initially
        panel_layout.addWidget(props_group)

        # Group 3: Assembly & Joints
        assembly_group = QGroupBox("Assembly & Joints")
        assembly_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        assembly_layout = QHBoxLayout(assembly_group) # Use QHBoxLayout for horizontal buttons
        assembly_layout.setSpacing(10)

        self.define_joint_btn = QPushButton("Joint")
        self.define_joint_btn.setCheckable(True)
        self.define_joint_btn.setToolTip("Click two parts in the view to define a joint between them")
        self.define_joint_btn.setEnabled(False) # Disable initially

        self.show_skeleton_btn = QPushButton("Skeleton")
        self.show_skeleton_btn.setCheckable(True) # Make it a toggle button
        self.show_skeleton_btn.setToolTip("Temporarily display the skeleton structure and auto-generated joints")
        self.show_skeleton_btn.setEnabled(False) # Disable initially (needs skeleton data)

        assembly_layout.addWidget(self.define_joint_btn)
        assembly_layout.addWidget(self.show_skeleton_btn)

        panel_layout.addWidget(assembly_group)

        # Group 4: Motion Path Definition
        motion_path_group = QGroupBox("Motion Path")
        motion_path_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        motion_path_layout = QVBoxLayout(motion_path_group)
        self.define_motion_path_btn = QPushButton("Define Motion Path")
        self.define_motion_path_btn.setCheckable(True)
        self.define_motion_path_btn.setToolTip("Toggle mode to draw a motion path for the selected part.")
        self.define_motion_path_btn.setEnabled(False)
        motion_path_layout.addWidget(self.define_motion_path_btn)

        self.clear_motion_path_btn = QPushButton("Clear Motion Path")
        self.clear_motion_path_btn.setToolTip("Clear the motion path for the selected part.")
        self.clear_motion_path_btn.setEnabled(False)
        motion_path_layout.addWidget(self.clear_motion_path_btn)

        # Add path type and loop type (commented out for now, simplify to freehand polyline first)
        # self.path_type_label = QLabel("Path Drawing Type:")
        # self.path_type_combo = QComboBox()
        # self.path_type_combo.addItems(["Freehand", "Bézier"])
        # self.path_type_combo.setToolTip("Choose how path points are connected (Freehand = lines, Bézier = smooth curves).")
        # self.path_type_combo.setEnabled(False)
        # motion_path_layout.addWidget(self.path_type_label)
        # motion_path_layout.addWidget(self.path_type_combo)

        # self.loop_type_label = QLabel("Path Loop Type:")
        # self.loop_type_combo = QComboBox()
        # self.loop_type_combo.addItems(["Open Loop", "Closed Loop"])
        # self.loop_type_combo.setToolTip("Choose if the path should be open or automatically closed.")
        # self.loop_type_combo.setEnabled(False)
        # motion_path_layout.addWidget(self.loop_type_label)
        # motion_path_layout.addWidget(self.loop_type_combo)

        panel_layout.addWidget(motion_path_group)

        # Group 5: Motion & Simulation
        motion_sim_group = QGroupBox("Motion & Simulation")
        motion_sim_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        motion_sim_layout = QFormLayout(motion_sim_group)
        motion_sim_layout.setSpacing(10) # Adjust spacing for form layout

        # Path Type Selection - REMOVED
        # self.path_type_combo = QComboBox()
        # self.path_type_combo.addItems(["Freehand", "Bézier"]) # Add Bézier option
        # self.path_type_combo.setCurrentText("Freehand") # Default to Freehand
        # self.path_type_combo.setToolTip("Select the drawing method for the motion path.")
        # motion_sim_layout.addRow("Path Type:", self.path_type_combo)

        # Loop Type Selection - REMOVED
        # self.loop_type_combo = QComboBox()
        # self.loop_type_combo.addItems(["Closed Loop", "Open Loop"])
        # self.loop_type_combo.setCurrentText("Closed Loop") # Default to Closed Loop
        # self.loop_type_combo.setToolTip("Choose if the path should automatically close.")
        # motion_sim_layout.addRow("Loop:", self.loop_type_combo)

        # Motion Definition Button - REMOVED (self.define_motion_path_btn in "Motion Path" group is used)
        # self.define_motion_btn = QPushButton(" Define Motion Path")
        # self.define_motion_btn.setCheckable(True)
        # self.define_motion_btn.setToolTip("Draw the desired motion path for the selected part's center")
        # self.define_motion_btn.setEnabled(False) # Disabled until a non-fixed part is selected
        # motion_sim_layout.addRow(self.define_motion_btn)

        # Simulation Controls
        sim_button_layout = QHBoxLayout()
        sim_button_layout.setSpacing(6)
        style = self.style()
        self.play_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "")
        self.play_btn.setToolTip("Play Simulation")
        self.stop_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), "")
        self.stop_btn.setToolTip("Stop Simulation")
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "")
        self.reset_sim_btn.setToolTip("Restart Simulation")
        self.reset_sim_btn.setEnabled(False)
        sim_button_layout.addWidget(self.play_btn)
        sim_button_layout.addWidget(self.stop_btn)
        sim_button_layout.addWidget(self.reset_sim_btn)

        # Add simulation buttons spanning both columns
        motion_sim_layout.addRow(sim_button_layout)

        panel_layout.addWidget(motion_sim_group)

        # Group 5: Mechanism Design
        mech_design_group = QGroupBox("Mechanism Design")
        mech_design_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding) # Allow vertical expansion
        mech_design_layout = QVBoxLayout(mech_design_group)
        mech_design_layout.setSpacing(10)

        # Mechanism Type Selector
        mech_type_layout = QFormLayout()
        self.mechanism_type_combo = QComboBox()
        self.mechanism_type_combo.addItems([
            "Cam & Follower",
            "3-Bar Linkage",
            "4-Bar Linkage",
            "Gears (Simple Pair)"
        ])
        self.mechanism_type_combo.setToolTip("Select the type of mechanism to generate")
        mech_type_layout.addRow("Type:", self.mechanism_type_combo)
        mech_design_layout.addLayout(mech_type_layout)

        # --- Type-Specific Inputs Container ---
        self.mech_inputs_container = QWidget()
        self.mech_inputs_layout = QVBoxLayout(self.mech_inputs_container)
        self.mech_inputs_layout.setContentsMargins(0, 5, 0, 0)
        self.mech_inputs_layout.setSpacing(8)
        mech_design_layout.addWidget(self.mech_inputs_container)

        # --- Input Group: Cam ---
        self.cam_inputs_group = QGroupBox("Cam Settings")
        cam_inputs_layout = QVBoxLayout(self.cam_inputs_group)
        self.select_cam_center_btn = QPushButton("Select Cam Center")
        self.select_cam_center_btn.setToolTip("Click in the scene to set the cam rotation center (default: torso center)")
        cam_inputs_layout.addWidget(self.select_cam_center_btn)
        # TODO: Add follower type, radius inputs later
        self.mech_inputs_layout.addWidget(self.cam_inputs_group)

        # --- Input Group: 3-Bar ---
        self.three_bar_inputs_group = QGroupBox("3-Bar Linkage Settings")
        three_bar_layout = QVBoxLayout(self.three_bar_inputs_group)
        self.select_pivot_a_3bar_btn = QPushButton("Select Fixed Pivot A")
        self.select_pivot_a_3bar_btn.setToolTip("Click in the scene to set the first fixed pivot")
        three_bar_layout.addWidget(self.select_pivot_a_3bar_btn)
        # TODO: Add inputs for other constraints/lengths
        self.mech_inputs_layout.addWidget(self.three_bar_inputs_group)

        # --- Input Group: 4-Bar ---
        self.four_bar_inputs_group = QGroupBox("4-Bar Linkage Settings")
        four_bar_layout = QVBoxLayout(self.four_bar_inputs_group)
        self.select_pivot_a_4bar_btn = QPushButton("Select Fixed Pivot A")
        self.select_pivot_a_4bar_btn.setToolTip("Click in the scene to set the first fixed pivot")
        four_bar_layout.addWidget(self.select_pivot_a_4bar_btn)
        self.select_pivot_d_4bar_btn = QPushButton("Select Fixed Pivot D")
        self.select_pivot_d_4bar_btn.setToolTip("Click in the scene to set the second fixed pivot")
        four_bar_layout.addWidget(self.select_pivot_d_4bar_btn)
        # TODO: Add inputs for coupler point, lengths
        self.mech_inputs_layout.addWidget(self.four_bar_inputs_group)

        # --- Input Group: Gears ---
        self.gear_inputs_group = QGroupBox("Gear Settings")
        gear_inputs_layout = QFormLayout(self.gear_inputs_group) # Use Form layout
        gear_button_layout = QHBoxLayout() # For buttons
        self.select_driver_center_btn = QPushButton("Driver Center")
        self.select_driver_center_btn.setToolTip("Click to set driver gear center")
        self.select_driven_center_btn = QPushButton("Driven Center")
        self.select_driven_center_btn.setToolTip("Click to set driven gear center")
        gear_button_layout.addWidget(self.select_driver_center_btn)
        gear_button_layout.addWidget(self.select_driven_center_btn)
        gear_inputs_layout.addRow("Select Centers:", gear_button_layout) # Add buttons horizontally

        self.gear_ratio_spin = QDoubleSpinBox()
        self.gear_ratio_spin.setRange(0.01, 100.0) # Example range
        self.gear_ratio_spin.setSingleStep(0.1)
        self.gear_ratio_spin.setValue(1.0)
        self.gear_ratio_spin.setToolTip("Set gear ratio (Driven Radius / Driver Radius)")
        gear_inputs_layout.addRow("Gear Ratio:", self.gear_ratio_spin)
        self.mech_inputs_layout.addWidget(self.gear_inputs_group)

        # --- Generate Button ---
        self.generate_mechanism_btn = QPushButton("Generate Mechanism")
        self.generate_mechanism_btn.setToolTip("Generate the selected mechanism based on the current setup")
        self.generate_mechanism_btn.setEnabled(False) # Initially disabled
        mech_design_layout.addWidget(self.generate_mechanism_btn)
        mech_design_layout.addStretch() # Push generate button down a bit

        panel_layout.addWidget(mech_design_group)

        # Initialize visibility of specific input groups
        self._update_mechanism_inputs_ui(self.mechanism_type_combo.currentText())

        # Group 5.5: Mechanism Layers
        self.layer_group = QGroupBox("Mechanism Layers")
        self.layer_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.layer_layout = QVBoxLayout(self.layer_group)
        self.layer_layout.setSpacing(6)
        # Layer checkboxes will be added dynamically
        panel_layout.addWidget(self.layer_group)

        # Group 6: Export (RESTORED)
        export_group = QGroupBox("Export")
        export_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        export_layout = QVBoxLayout(export_group)
        self.blueprint_btn = QPushButton(" Generate Blueprint (SVG)")
        self.blueprint_btn.setToolTip("Generate an SVG blueprint of all parts for fabrication")
        export_layout.addWidget(self.blueprint_btn)
        panel_layout.addWidget(export_group)

        panel_layout.addStretch() # Add stretch at the end (RESTORED)

        scroll_area.setWidget(control_panel) # Put the panel inside the scroll area

        # --- Right View Area (Editor) ---
        self.editor_scene = QGraphicsScene()
        self.editor_view = EditorView(self.editor_scene, self)

        # Add the scroll area (containing the panel) and the view to the main layout
        layout.addWidget(scroll_area)
        layout.addWidget(self.editor_view, 1)
        return widget

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
        self.process_image_btn.clicked.connect(self.process_image)
        # self.edit_skeleton_btn.clicked.connect(self.edit_skeleton)
        # self.save_skeleton_btn.clicked.connect(self.save_skeleton)
        self.create_parts_btn.clicked.connect(self.create_parts_from_skeleton)

        # Tab 2: Editor
        self.parts_list.currentItemChanged.connect(self._handle_part_selection_change)
        self.parts_list.itemClicked.connect(self._handle_part_list_click)
        self.z_value_spin.valueChanged.connect(self._update_selected_part_z)
        self.fixed_part_check.stateChanged.connect(self._update_selected_part_fixed)
        self.define_motion_path_btn.toggled.connect(self._toggle_define_motion_path_mode)
        self.clear_motion_path_btn.clicked.connect(self._clear_selected_item_motion_path)
        self.define_joint_btn.toggled.connect(self._toggle_define_joint_mode)
        self.show_skeleton_btn.toggled.connect(self._show_skeleton_and_joints)
        # self.define_motion_btn.toggled.connect(self._toggle_define_motion_path_mode) # REMOVED - define_motion_btn is removed
        # self.set_cam_center_btn.clicked.connect(self._start_cam_center_selection)
        # self.set_cam_follower_btn.clicked.connect(self.set_cam_follower)
        self.generate_mechanism_btn.clicked.connect(self._generate_mechanism_auto) # 변경된 버튼에 연결
        self.mechanism_type_combo.currentTextChanged.connect(self._update_mechanism_inputs_ui)
        self.mechanism_type_combo.currentTextChanged.connect(self._update_generate_mechanism_button_state) # Also update button state on type change
        self.play_btn.clicked.connect(self.play_simulation)
        self.stop_btn.clicked.connect(self.stop_simulation)
        self.reset_sim_btn.clicked.connect(self.reset_simulation)
        self.blueprint_btn.clicked.connect(self.generate_blueprint)

        # Editor View Signals
        self.editor_view.joint_defined.connect(self.request_create_joint)
        # self.editor_view.end_effector_selected.connect(self._handle_end_effector_set) # Removed in UI cleanup
        self.editor_view.cam_center_selected.connect(self._handle_cam_center_set)
        self.editor_view.drawing_cancelled.connect(self._handle_drawing_cancelled)
        self.editor_view.pivot_a_selected.connect(self._handle_pivot_a_set)
        self.editor_view.pivot_d_selected.connect(self._handle_pivot_d_set)
        self.editor_view.driver_center_selected.connect(self._handle_driver_center_set)
        self.editor_view.driven_center_selected.connect(self._handle_driven_center_set)

        # Tab 3: Options (Connect signals from OptionsTab instance)
        self.options_tab.animationDurationChanged.connect(self._update_animation_duration)
        self.options_tab.themeChanged.connect(self._apply_theme)
        self.options_tab.toolbarVisibilityChanged.connect(self._toggle_toolbar_visibility) # Connect new signal

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

    # --- Action Handlers & Slots ---

    # Slot for part selection change in list
    def _handle_part_selection_change(self, current_item, previous_item):
        can_define_path = False
        is_part_selected = current_item is not None

        if current_item:
            self.update_part_properties(current_item, previous_item)
            # Select in scene as well
            part_name = current_item.data(Qt.ItemDataRole.UserRole)
            item = self.editor_items.get(part_name)
            if item:
                self.editor_scene.clearSelection()
                item.setSelected(True)
                # Only enable if the selected item exists and is not fixed
                if not item.is_fixed:
                    can_define_path = True
        else:
            # Clear properties if nothing selected
            self.z_value_spin.setEnabled(False)
            self.fixed_part_check.setEnabled(False)

        # Enable/disable UI elements based on selection
        # Find the QGroupBox by iterating through children of panel_layout's parent (control_panel)
        control_panel = self.parts_list.parent().parent() # Assuming Parts List -> Parts Group -> Control Panel
        props_group = control_panel.findChild(QGroupBox, "Selected Part Properties")
        cam_group = control_panel.findChild(QGroupBox, "Cam Mechanism")

        if props_group: props_group.setEnabled(is_part_selected)
        if cam_group: cam_group.setEnabled(is_part_selected)

        self.define_joint_btn.setEnabled(is_part_selected)

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
                                       f"Body parts extracted to:\n{output_dir}\n\nLoad these parts into the editor now?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                parts_json_path = os.path.join(output_dir, 'parts_info.json')
                if os.path.exists(parts_json_path):
                     self.load_parts(filepath=parts_json_path)
                     self.tab_widget.setCurrentIndex(1) # Switch to editor tab
                else:
                     QMessageBox.warning(self, "Load Error", f"Could not find parts_info.json in {output_dir}")
        except Exception as e:
            QApplication.restoreOverrideCursor()
            error_msg = f"Failed to extract body parts: {e}"
            logging.error(f"{error_msg}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Extraction Error", error_msg)
            self.statusBar().showMessage("Body part extraction failed.")

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
            else: # Loading from parts_data dictionary
                logging.info("Loading parts from provided data dictionary.")
                loaded_data = parts_data
                # Assume base path is character_dir if loading from data
                base_path = self.character_dir or "." # Use current dir as fallback

            # Clear existing editor state
            self._clear_editor_state()

            character_data = loaded_data.get('character', {})
            parts_structure = character_data.get('parts', {})

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
                        editor_item.setPos(initial_pos_data.get('x', 0), initial_pos_data.get('y', 0))
                        logging.debug(f"Positioning '{name}' using saved position: {initial_pos_data}")
                    elif roi_data and isinstance(roi_data, (list, tuple)) and len(roi_data) == 4:
                        # Use ROI top-left corner if available (from parts_info.json)
                        try:
                            x_min, y_min = int(roi_data[0]), int(roi_data[1])
                            editor_item.setPos(x_min, y_min)
                            logging.debug(f"Positioning '{name}' using ROI: ({x_min}, {y_min})")
                        except (ValueError, TypeError):
                            logging.warning(f"Invalid ROI data for '{name}': {roi_data}. Falling back to skeleton.")
                            # Fallback to skeleton if ROI is invalid
                            if name in skeleton_map:
                                loc = skeleton_map[name] # Correct indentation
                                # Check and set position *inside* this block
                                if len(loc) >= 2: # Correct indentation
                                    editor_item.setPos(loc[0], loc[1])
                                    logging.debug(f"Positioning '{name}' using skeleton (ROI fallback): {loc}")
                                else: # Correct indentation
                                    logging.warning(f"Invalid skeleton location data for '{name}' during ROI fallback: {loc}")
                            else:
                                logging.warning(f"Could not find skeleton data for '{name}' during ROI fallback.")
                    elif name in skeleton_map: # 3. Fallback to skeleton joint location
                        loc = skeleton_map[name]
                        if len(loc) >= 2:
                             editor_item.setPos(loc[0], loc[1])
                             logging.debug(f"Positioning '{name}' using skeleton (fallback): {loc}")
                    else:
                        logging.warning(f"Could not determine initial position for '{name}'. Placing at (0,0).")
                        editor_item.setPos(0, 0) # Default to origin if no info found
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
                                # Joint location is usually the child's pivot point in world coordinates
                                joint_loc_scene = QPointF(float(loc_data[0]), float(loc_data[1]))

                                # Map scene location to local coordinates for each part
                                parent_joint_pos_local = parent_item.mapFromScene(joint_loc_scene)
                                child_joint_pos_local = child_item.mapFromScene(joint_loc_scene)

                                # Create the joint
                                self._create_and_add_joint(parent_item, child_item,
                                                          parent_joint_pos_local, child_joint_pos_local)
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

            self.editor_view.zoom_to_fit()
            self.statusBar().showMessage(f"Loaded {len(self.parts)} parts and {len(self.joints)} joints.")

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
        self.kinematic_chains.clear()
        self._clear_mechanism_visuals() # Clear mechanism visuals and layers
        # self.cam_follower_item = None # No longer needed with automatic approach
        # self.driving_cam_center = None # No longer needed with automatic approach

        # Reset property widgets
        self.z_value_spin.setValue(0)
        self.z_value_spin.setEnabled(False)
        self.fixed_part_check.setChecked(False)
        self.fixed_part_check.setEnabled(False)

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
        joint_name = f"Joint_{parent_item.part_info.name}-{child_item.part_info.name}"
        joint = Joint(parent_item, child_item, parent_pos, child_pos, name=joint_name)
        self.joints.append(joint)

        # Set relationships (needed for kinematics/simulation)
        parent_item.child_joints.append(joint)
        child_item.parent_joint = joint

        logging.info(f"Created joint: {joint_name}")
        self.statusBar().showMessage(f"Created joint: {joint_name}")

        # TODO: Visualize the joint in the editor?

    # --- Motion Definition Actions ---

    def _toggle_define_motion_path_mode(self, checked: bool):
        selected_item = self.get_selected_editor_item()

        if checked:
            if not selected_item:
                QMessageBox.warning(self, "No Part Selected", "Please select a character part before defining a motion path.")
                self.define_motion_path_btn.setChecked(False)
                return

            # Clear existing motion path on the item before starting new definition
            # This ensures the part_item's visual is also cleared.
            if selected_item.motion_path and not selected_item.motion_path.isEmpty():
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Icon.Question)
                msg_box.setText(f"A motion path already exists for '{selected_item.part_info.name}'.")
                msg_box.setInformativeText("Do you want to overwrite it?")
                msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg_box.setDefaultButton(QMessageBox.StandardButton.No)
                ret = msg_box.exec()
                if ret == QMessageBox.StandardButton.No:
                    self.define_motion_path_btn.setChecked(False)
                    return

            selected_item.update_motion_path_visual(QPainterPath()) # Clear it visually and internally
            self.editor_view.start_define_motion_path(selected_item)
            self.statusBar().showMessage(f"Defining motion path for {selected_item.part_info.name}. Draw freely. Uncheck button or right-click to cancel.")
        else:
            # This is called when the button is unchecked by the user.
            # If a path was being drawn, EditorView should finalize/cancel itself.
            # The editor_view.finish_motion_path_drawing() handles emitting points if needed.
            self.editor_view.finish_motion_path_drawing() # Ensure mode is exited and cleanup occurs
            self.statusBar().showMessage("Motion path definition stopped.")

        self._update_generate_mechanism_button_state()
        self.clear_motion_path_btn.setEnabled(selected_item is not None and selected_item.motion_path is not None and not selected_item.motion_path.isEmpty())

    @pyqtSlot(list)
    def _handle_freehand_path_completed(self, points: list):
        """Receives the list of QPointF from EditorView when freehand drawing is done.
        Converts the points to a closed Bézier curve and applies it to the selected part.
        """
        logging.debug(f"MainWindow received freehand path with {len(points)} raw scene points.")
        selected_item = self.editor_view._target_part_for_path # Get the item from EditorView state

        if selected_item and self.define_motion_path_btn.isChecked():
            if not points:
                selected_item.update_motion_path_visual(QPainterPath()) # Clear path
                logging.info(f"Freehand path for '{selected_item.part_info.name}' was empty, cleared.")
                self.statusBar().showMessage(f"Motion path for '{selected_item.part_info.name}' was empty.")
                self._update_button_states_after_path_change(selected_item)
                return

            # 1. Convert raw scene points to item's local coordinates.
            local_points_raw = [selected_item.mapFromScene(p) for p in points]
            logging.debug(f"Converted to {len(local_points_raw)} local points.")

            # 2. Simplify the points
            num_raw_points = len(local_points_raw)
            simplified_local_points = []

            if num_raw_points < 3: # Not enough for Bezier, use as is for polyline
                simplified_local_points = local_points_raw
                logging.debug(f"Using {num_raw_points} points directly as not enough for Bezier/simplification.")
            else:
                # Aim for roughly 1/3, but ensure at least 3 points for Bezier.
                # And not too many for very dense paths. Max around 25-30?
                target_points = max(3, min(num_raw_points // 3, 30))

                if num_raw_points <= target_points or num_raw_points <= 6: # If already few points, or close to target
                    simplified_local_points = local_points_raw
                    logging.debug(f"Using raw {num_raw_points} points as simplification isn't beneficial or target met.")
                else:
                    step = num_raw_points / target_points
                    for i in range(target_points):
                        index = int(i * step)
                        # Ensure index is within bounds (can happen with floating point inaccuracies)
                        index = min(index, num_raw_points -1)
                        simplified_local_points.append(local_points_raw[index])

                    # Ensure the very last original point is included for closure, if not already.
                    # This helps maintain the overall shape better than just relying on decimated points.
                    if simplified_local_points and local_points_raw[-1] != simplified_local_points[-1]:
                        # Check if the last point is already "close enough" to the last simplified one.
                        # This avoids adding a near-duplicate point.
                        last_raw_pt = local_points_raw[-1]
                        last_simp_pt = simplified_local_points[-1]
                        # Define a small tolerance, e.g., 1 pixel in local coordinates
                        tolerance_sq = 1.0 * 1.0
                        dx = last_raw_pt.x() - last_simp_pt.x()
                        dy = last_raw_pt.y() - last_simp_pt.y()
                        if (dx*dx + dy*dy) > tolerance_sq:
                            simplified_local_points.append(local_points_raw[-1])

                logging.debug(f"Simplified from {num_raw_points} to {len(simplified_local_points)} local points.")


            # 3. Generate Path (Bezier or Polyline)
            if len(simplified_local_points) >= 3:
                bezier_path = points_to_closed_bezier_path(simplified_local_points)
                if not bezier_path.isEmpty():
                    selected_item.update_motion_path_visual(bezier_path)
                    logging.info(f"Closed Bézier motion path set for '{selected_item.part_info.name}' from {len(simplified_local_points)} points.")
                    self.statusBar().showMessage(f"Bézier motion path defined for '{selected_item.part_info.name}'.")
                else: # Bezier generation failed
                    selected_item.update_motion_path_visual(QPainterPath()) # Clear path
                    logging.warning(f"Failed to generate Bézier path for '{selected_item.part_info.name}' (using {len(simplified_local_points)} points), path cleared.")
                    self.statusBar().showMessage(f"Could not generate Bézier path for '{selected_item.part_info.name}'.")
            elif simplified_local_points: # 1 or 2 points
                path = QPainterPath()
                path.moveTo(simplified_local_points[0])
                for point_local in simplified_local_points[1:]:
                    path.lineTo(point_local)
                selected_item.update_motion_path_visual(path)
                logging.info(f"Polyline motion path ({len(simplified_local_points)} points, not enough for Bézier) set for '{selected_item.part_info.name}'.")
                self.statusBar().showMessage(f"Simple path defined for '{selected_item.part_info.name}'.")
            else: # No points left
                selected_item.update_motion_path_visual(QPainterPath())
                logging.info(f"Path for '{selected_item.part_info.name}' became empty after processing, cleared.")
                self.statusBar().showMessage(f"Motion path for '{selected_item.part_info.name}' was empty or invalid.")
        else:
            logging.warning("Could not set motion path: No selected item or define mode not active.")
            if selected_item: # If define mode was just unchecked, clear path on item.
                 selected_item.update_motion_path_visual(QPainterPath())

        self._update_button_states_after_path_change(selected_item) # Ensure this is called

    def _update_button_states_after_path_change(self, selected_item: Optional[CharacterPartItem]):
        """Helper to update button states related to motion path after a change."""
        if selected_item:
            self.clear_motion_path_btn.setEnabled(selected_item.motion_path is not None and not selected_item.motion_path.isEmpty())
        else:
            self.clear_motion_path_btn.setEnabled(False)

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
        """Triggers the visualization of the skeleton and joints in the editor view."""
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

            # Pass skeleton data and potentially joint data to the view
            # The view will be responsible for drawing temporary items
            self.editor_view.visualize_skeleton(self.skeleton_data, self.joints)
        else:
            # Hide the visualization
            self.editor_view._clear_skeleton_visualization()

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
        link_item.setPen(QPen(Qt.PenStyle.NoPen)) # No outline
        link_color = QColor("green")
        link_color.setAlphaF(0.7) # Slightly less transparent
        link_item.setBrush(QBrush(link_color))
        link_item.setZValue(300) # Increase Z-value significantly

        # --- Create Joint Circles --- #
        joint_radius = 6 # Slightly larger joints
        parent_joint_circle = QGraphicsEllipseItem(-joint_radius, -joint_radius, joint_radius*2, joint_radius*2)
        parent_joint_circle.setPos(parent_joint_scene)
        parent_joint_circle.setBrush(QBrush(QColor("yellow")))
        parent_joint_circle.setPen(QPen(Qt.PenStyle.NoPen))
        parent_joint_circle.setZValue(310) # Keep above bar

        child_joint_circle = QGraphicsEllipseItem(-joint_radius, -joint_radius, joint_radius*2, joint_radius*2)
        child_joint_circle.setPos(child_joint_scene)
        child_joint_circle.setBrush(QBrush(QColor("yellow")))
        child_joint_circle.setPen(QPen(Qt.PenStyle.NoPen))
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
        marker.setPen(QPen(Qt.PenStyle.NoPen))
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


    def _generate_mechanism_auto(self):
        """Generates the selected mechanism based on the editor state and gathered inputs."""
        selected_item = self.get_selected_editor_item()
        mechanism_type = self.mechanism_type_combo.currentText()

        logging.info(f"Attempting to generate mechanism of type: {mechanism_type}")

        if not selected_item: # Basic check, specific checks below
            QMessageBox.warning(self, "No Part Selected", "Please select a character part.")
            return

        self._clear_mechanism_visuals() # Clear previous visuals

        # --- Get Common Inputs ---
        motion_path_required = mechanism_type in ["Cam & Follower", "3-Bar Linkage", "4-Bar Linkage"]
        target_path_scene = None
        if motion_path_required:
            if not selected_item.motion_path or selected_item.motion_path.isEmpty():
                # Access name via part_info
                QMessageBox.warning(self, "No Motion Path", f"Part '{selected_item.part_info.name}' needs a defined motion path for {mechanism_type}.")
                return
            target_path_scene = selected_item.mapToScene(selected_item.motion_path)

        # --- Call Type-Specific Generation ---
        try:
            if mechanism_type == "Cam & Follower":
                # Determine cam center (use selected or default to torso)
                cam_center = self.selected_cam_center
                if cam_center is None:
                    torso_item = self.editor_items.get("torso")
                    if not torso_item:
                        QMessageBox.warning(self, "Torso Not Found", "Please select a Cam Center or ensure a 'torso' part exists.")
                        return
                    cam_center = torso_item.sceneBoundingRect().center()
                    logging.info("Using torso center as default cam center.")

                smoothed_path = self._resample_path_as_polygon(target_path_scene)
                cam_profile_path = generate_cam_profile(smoothed_path, cam_center)
                if cam_profile_path and not cam_profile_path.isEmpty():
                    cam_item = QGraphicsPathItem(cam_profile_path)
                    cam_item.setPen(QPen(QColor("#FF00FF"), 2))
                    cam_item.setBrush(QColor(255, 0, 255, 100))
                    self._add_mechanism_visual("Generated Cam Profile", cam_item)
                    # Visualize the actual center used
                    self._update_point_marker('cam_center_used', cam_center, QColor("magenta"))
                    self.driving_cam_center = cam_center # Store for potential simulation use
                else:
                    QMessageBox.information(self, "Cam Generation", "Failed to generate cam profile or profile is empty.")

            elif mechanism_type == "3-Bar Linkage":
                if self.selected_pivot_a is None:
                     QMessageBox.warning(self, "Input Missing", "Please select Fixed Pivot A.")
                     return
                linkage_data = generate_3bar_linkage(target_path_scene, self.selected_pivot_a)
                if linkage_data:
                    QMessageBox.information(self, "3-Bar Linkage", f"Placeholder generated: {linkage_data.get('message')}")
                    self._visualize_linkage_data(linkage_data)
                else:
                    QMessageBox.warning(self, "3-Bar Linkage", "Failed to generate 3-bar linkage (placeholder). See logs.")

            elif mechanism_type == "4-Bar Linkage":
                if self.selected_pivot_a is None or self.selected_pivot_d is None:
                     QMessageBox.warning(self, "Input Missing", "Please select Fixed Pivot A and Fixed Pivot D.")
                     return
                linkage_data = generate_4bar_linkage(target_path_scene, self.selected_pivot_a, self.selected_pivot_d)
                if linkage_data:
                    QMessageBox.information(self, "4-Bar Linkage", f"Placeholder generated: {linkage_data.get('message')}")
                    self._visualize_linkage_data(linkage_data)
                else:
                    QMessageBox.warning(self, "4-Bar Linkage", "Failed to generate 4-bar linkage (placeholder). See logs.")

            elif mechanism_type == "Gears (Simple Pair)":
                if self.selected_driver_center is None or self.selected_driven_center is None:
                     QMessageBox.warning(self, "Input Missing", "Please select Driver and Driven Gear Centers.")
                     return
                gear_ratio = self.gear_ratio_spin.value()
                gear_data = generate_gear_pair(driver_center=self.selected_driver_center,
                                                driven_center=self.selected_driven_center,
                                                gear_ratio=gear_ratio)
                if gear_data:
                    QMessageBox.information(self, "Gears (Simple Pair)", f"Placeholder generated: {gear_data.get('message')}")
                    self._visualize_gear_data(gear_data)
                else:
                    QMessageBox.warning(self, "Gears (Simple Pair)", "Failed to generate gears (placeholder). See logs.")

        except Exception as e:
            logging.error(f"Error during mechanism generation ({mechanism_type}): {e}", exc_info=True)
            QMessageBox.critical(self, "Generation Error", f"An error occurred while generating the {mechanism_type}: {e}")

        # Update layer visibility checkboxes if they exist
        for name, checkbox in self.layer_checkboxes.items():
            checkbox.setChecked(True) # Make new visuals visible by default
        self.editor_scene.update()

    def _resample_path_as_polygon(self, path: QPainterPath, num_samples: int = 100) -> QPolygonF:
        """Resamples a QPainterPath into a QPolygonF with a fixed number of samples.

        Args:
            path: The QPainterPath to resample (expected in scene coordinates).
            num_samples: The number of points to sample along the path.

        Returns:
            A QPolygonF representing the resampled path.
        """
        polygon = QPolygonF()
        if path.isEmpty() or num_samples < 2:
            return polygon # Return empty polygon if path is empty or not enough samples

        for i in range(num_samples):
            percent = i / (num_samples - 1) # Go from 0.0 to 1.0
            point = path.pointAtPercent(percent)
            polygon.append(point)

        # Ensure the polygon is closed if the path suggests it might be (e.g. for cam profiles)
        # For a general resampling, explicit closure might not always be desired here,
        # but for cam follower paths, it's usually a closed loop.
        # The points_to_closed_bezier_path already ensures a sort of closure for the motion_path itself.
        # If the input path is visually closed, pointAtPercent(1.0) should be very close to pointAtPercent(0.0).
        # QPolygonF doesn't have an explicit closeSubpath like QPainterPath.
        # If the first and last points are not identical, add the first point at the end to close it.
        if num_samples > 1 and polygon.first() != polygon.last():
             # This check is often redundant if path.pointAtPercent(0) == path.pointAtPercent(1) for closed paths
             # but can be a safeguard. For cam generation, generate_cam_profile might expect this.
             # However, the generate_cam_profile takes a QPolygonF which is a list of points.
             # The "closed" nature is handled by how it iterates over those points.
             pass # For now, let generate_cam_profile handle interpretation of the point list.

        return polygon

    # --- Simulation Methods (Placeholder/Basic Implementation) ---
    def play_simulation(self):
        """Starts or resumes the simulation."""
        if not self.kinematic_chains:
            self.build_kinematic_chains()
        if not self.kinematic_chains:
            self.statusBar().showMessage("Cannot start simulation: No valid kinematic chains.")
            return

        logging.info("Starting/Resuming simulation...")
        self.editor_view.set_mode('simulation')
        self.editor_view._save_original_transforms() # Save state before starting
        self.animation_time = 0.0 # Reset time or use current time if resuming
        self.timer.start()
        self.statusBar().showMessage("Simulation running...")
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.reset_sim_btn.setEnabled(True)

    def stop_simulation(self):
        """Stops the simulation."""
        if self.timer.isActive():
            logging.info("Stopping simulation.")
            self.timer.stop()
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
        self.animation_time = 0.0
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(False)
        self.statusBar().showMessage("Simulation reset.")

    def update_simulation(self):
        """Performs one step of the simulation (called by timer)."""
        if not self.timer.isActive() or not self.kinematic_chains:
            return

        delta_time = self.timer.interval() / 1000.0  # Convert ms to s
        self.animation_time += delta_time
        # Loop animation based on duration
        # Ensure animation_duration is not zero to prevent division errors
        current_animation_duration = self.animation_duration
        if current_animation_duration <= 0:
            current_animation_duration = 0.01 # Use a very small positive default if it's zero or negative

        progress = (self.animation_time % current_animation_duration) / current_animation_duration

        logging.debug(f"Sim Update: SetDuration={self.animation_duration:.2f}, ActualDuration={current_animation_duration:.2f}, Time={self.animation_time:.2f}, Prog={progress:.3f}")

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
            except Exception as e:
                logging.error(f"Error in IK solver for {end_effector_name}: {e}", exc_info=True)
                self.stop_simulation()
                break # Stop processing further chains on error

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