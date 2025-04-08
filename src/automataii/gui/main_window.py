import sys
import os
import json
import logging
import traceback
import time
import tempfile
import yaml
import cv2
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGraphicsScene, QFileDialog, QSplitter, QLabel, QListWidget, QListWidgetItem,
    QDoubleSpinBox, QCheckBox, QFormLayout, QTabWidget, QMessageBox, QProgressDialog,
    QGraphicsPathItem, QGroupBox, QApplication, QStyle, QDialog, QToolBar, QComboBox, QGraphicsItem
)
from PyQt6.QtGui import QColor, QPen, QAction, QPainterPath
from PyQt6.QtCore import Qt, QPointF, QTimer, pyqtSlot, QSize

# Local imports (adjust paths as needed)
from .editor_view import EditorView
from .image_view import ImageProcessingView
from .part_item import CharacterPartItem
from .camera_dialog import CameraDialog
from .styling import LIGHT_STYLE, DARK_STYLE
from .options_tab import OptionsTab
from ..core.models import PartInfo, Joint
from ..kinematics.ik_solver import solve_ik_ccd
from ..generation.cam import generate_cam_profile # Function needs to be created
from ..generation.blueprint import generate_blueprint_svg # Function needs to be created
from ..utils.helpers import transform_to_dict, qpainterpath_to_points # Utility functions

# Attempt to import image processing functionality (optional)
from ..animate.image_to_annotations import image_to_annotations
from ..animate.annotations_to_animation import annotations_to_animation
from ..animate.image_to_animation import image_to_animation
# Import body part extractor
from ..animate.body_parts_extractor import process_character


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
        self.cam_profile_item = None # QGraphicsPathItem for cam profile viz
        self.driving_cam_center = QPointF(0, 0)
        self.cam_follower_item = None # CharacterPartItem designated as follower
        self.cam_center_marker = None # QGraphicsItem for cam center viz

        # Image processing workflow data
        self.input_image_path = None
        self.character_dir = None
        self.skeleton_data = None # Loaded skeleton dict

        # Simulation Timer
        self.timer = QTimer(self)
        self.timer.setInterval(30) # Approx 33 FPS
        self.timer.timeout.connect(self.update_simulation)
        self.animation_time = 0.0
        self.animation_duration = 5.0 # Default duration

        # Tracking active dialogs
        self.active_camera_dialogs = []

        # --- Stylesheet Data --- (No longer need _define_stylesheets method)
        self.light_style = LIGHT_STYLE
        self.dark_style = DARK_STYLE

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
        self.tab_widget.addTab(image_proc_tab, "1. Image Processing")

        # --- Tab 2: Editor & Simulation ---
        editor_tab = self._create_editor_tab()
        self.tab_widget.addTab(editor_tab, "2. Editor & Simulation")

        # --- Tab 3: Options ---
        self.options_tab = OptionsTab(initial_anim_duration=self.animation_duration)
        self.tab_widget.addTab(self.options_tab, "Options")

        # --- Connect Signals from Options Tab ---
        self.options_tab.animationDurationChanged.connect(self._update_animation_duration)
        self.options_tab.themeChanged.connect(self._apply_theme)
        # Connect debug mode signal to the image view's slot
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
        control_panel.setFixedWidth(250)
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(0, 5, 0, 0)
        panel_layout.setSpacing(10)

        # Input Group
        input_group = QGroupBox("Input Drawing")
        input_layout = QVBoxLayout(input_group)
        style = self.style()
        self.load_image_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), " Load Image...")
        self.capture_image_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), " Capture Image...") # Placeholder icon
        input_layout.addWidget(self.load_image_btn)
        input_layout.addWidget(self.capture_image_btn)
        panel_layout.addWidget(input_group)

        # Processing Group
        proc_group = QGroupBox("Processing")
        proc_layout = QVBoxLayout(proc_group)
        self.process_image_btn = QPushButton(" Process Image")
        self.edit_skeleton_btn = QPushButton(" Edit Skeleton")
        proc_layout.addWidget(self.process_image_btn)
        proc_layout.addWidget(self.edit_skeleton_btn)
        panel_layout.addWidget(proc_group)

        # Output Group
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)
        self.save_skeleton_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), " Save Skeleton")
        self.create_parts_btn = QPushButton(" Create Parts from Skeleton")
        output_layout.addWidget(self.save_skeleton_btn)
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

        # Left Control Panel
        control_panel = QWidget()
        control_panel.setFixedWidth(250)
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(0, 5, 0, 0)
        panel_layout.setSpacing(10)

        # Parts List Group
        parts_group = QGroupBox("Character Parts")
        parts_layout = QVBoxLayout(parts_group)
        self.parts_list = QListWidget()
        self.parts_list.setToolTip("List of loaded character parts")
        parts_layout.addWidget(self.parts_list)
        panel_layout.addWidget(parts_group)

        # Properties Group
        props_group = QGroupBox("Selected Part Properties")
        self.part_props = QFormLayout(props_group)
        self.z_value_spin = QDoubleSpinBox()
        self.z_value_spin.setRange(-100, 100)
        self.z_value_spin.setSingleStep(0.1)
        self.z_value_spin.setToolTip("Adjust Z-depth (layering)")
        self.fixed_part_check = QCheckBox("Fixed in Place")
        self.fixed_part_check.setToolTip("Prevent this part from moving during simulation or IK")
        self.part_props.addRow("Z-Value:", self.z_value_spin)
        self.part_props.addRow(self.fixed_part_check)
        panel_layout.addWidget(props_group)

        # Assembly Group
        assembly_group = QGroupBox("Assembly & Joints")
        assembly_layout = QVBoxLayout(assembly_group)
        self.define_joint_btn = QPushButton(" Define Joint")
        self.define_joint_btn.setCheckable(True)
        self.define_joint_btn.setToolTip("Click parts to define a joint between them")
        assembly_layout.addWidget(self.define_joint_btn)
        panel_layout.addWidget(assembly_group)

        # Motion Group
        motion_group = QGroupBox("Motion Definition")
        motion_layout = QVBoxLayout(motion_group)
        self.define_motion_btn = QPushButton(" Define Motion Path")
        self.define_motion_btn.setCheckable(True)
        self.define_motion_btn.setToolTip("Draw the desired motion path for the selected part")
        self.set_effector_btn = QPushButton(" Set End Effector Point")
        self.set_effector_btn.setToolTip("Click the point on the selected part that should follow the path")
        self.preview_motion_btn = QPushButton(" Preview Path Motion")
        motion_layout.addWidget(self.define_motion_btn)
        motion_layout.addWidget(self.set_effector_btn)
        motion_layout.addWidget(self.preview_motion_btn)
        panel_layout.addWidget(motion_group)

        # Cam Mechanism Group
        cam_group = QGroupBox("Cam Mechanism")
        cam_layout = QVBoxLayout(cam_group)
        self.set_cam_center_btn = QPushButton(" Set Cam Center")
        self.set_cam_center_btn.setToolTip("Click the rotation center for the driving cam")
        self.set_cam_follower_btn = QPushButton(" Set as Cam Follower")
        self.set_cam_follower_btn.setToolTip("Designate the selected part as the cam follower")
        self.generate_cam_btn = QPushButton(" Generate Cam Profile")
        self.generate_cam_btn.setToolTip("Generate the cam shape based on follower path and center")
        cam_layout.addWidget(self.set_cam_center_btn)
        cam_layout.addWidget(self.set_cam_follower_btn)
        cam_layout.addWidget(self.generate_cam_btn)
        panel_layout.addWidget(cam_group)

        # Simulation Group
        sim_group = QGroupBox("Simulation")
        sim_layout = QHBoxLayout(sim_group)
        style = self.style()
        self.play_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), " Play")
        self.stop_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), " Stop")
        self.reset_sim_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward), " Reset") # Placeholder icon
        sim_layout.addWidget(self.play_btn)
        sim_layout.addWidget(self.stop_btn)
        sim_layout.addWidget(self.reset_sim_btn)
        panel_layout.addWidget(sim_group)

        # Blueprint Group
        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout(export_group)
        self.blueprint_btn = QPushButton(" Generate Blueprint (SVG)")
        self.blueprint_btn.setToolTip("Generate an SVG blueprint for fabrication")
        export_layout.addWidget(self.blueprint_btn)
        panel_layout.addWidget(export_group)

        panel_layout.addStretch()

        # Right View Area (Editor)
        self.editor_scene = QGraphicsScene()
        self.editor_view = EditorView(self.editor_scene, self)

        layout.addWidget(control_panel)
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
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False) # Keep it fixed
        toolbar.setIconSize(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton).actualSize(QSize(16, 16))) # Smaller icons?

        # Use standard icons for a cleaner look
        style = self.style()
        # Ensure actions are created before adding them
        if not hasattr(self, 'action_load_parts'):
            self.action_load_parts = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "Open...", self)
            # Connect signal here if menus aren't the primary connection point anymore
            # self.action_load_parts.triggered.connect(self.load_parts)
        else:
            self.action_load_parts.setText("Open...") # Shorter text for toolbar
            self.action_load_parts.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))

        if not hasattr(self, 'action_save_project'):
            self.action_save_project = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "Save...", self)
            self.action_save_project.setShortcut("Ctrl+S")
             # Connect signal here if menus aren't the primary connection point anymore
            # self.action_save_project.triggered.connect(self.save_project)
        else:
            self.action_save_project.setText("Save...")
            self.action_save_project.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))

        # Placeholder for New/Export - create dummy actions for now
        action_new = QAction(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon), "New", self) # Placeholder icon
        action_export = QAction(style.standardIcon(QStyle.StandardPixmap.SP_ArrowRight), "Export", self) # Placeholder icon

        toolbar.addAction(action_new)
        toolbar.addAction(self.action_load_parts)
        toolbar.addAction(self.action_save_project)
        toolbar.addAction(action_export)
        # Add separator? toolbar.addSeparator()

        self.addToolBar(toolbar)

    # --- Signal Connections ---
    def _connect_ui_actions(self):
        """Connects UI elements (buttons, menus, list widgets, and tab signals) to methods."""
        # Tab 1: Image Processing
        self.load_image_btn.clicked.connect(self.load_input_image)
        self.capture_image_btn.clicked.connect(self.capture_image)
        self.process_image_btn.clicked.connect(self.process_image)
        self.edit_skeleton_btn.clicked.connect(self.edit_skeleton)
        self.save_skeleton_btn.clicked.connect(self.save_skeleton)
        self.create_parts_btn.clicked.connect(self.create_parts_from_skeleton)

        # Tab 2: Editor
        self.parts_list.currentItemChanged.connect(self._handle_part_selection_change)
        self.parts_list.itemClicked.connect(self._handle_part_list_click)
        self.z_value_spin.valueChanged.connect(self._update_selected_part_z)
        self.fixed_part_check.stateChanged.connect(self._update_selected_part_fixed)
        self.define_joint_btn.toggled.connect(self._toggle_define_joint_mode)
        self.define_motion_btn.toggled.connect(self._toggle_define_motion_path_mode)
        self.set_effector_btn.clicked.connect(self._start_end_effector_selection)
        self.preview_motion_btn.clicked.connect(self.preview_motion_path)
        self.set_cam_center_btn.clicked.connect(self._start_cam_center_selection)
        self.set_cam_follower_btn.clicked.connect(self.set_cam_follower)
        self.generate_cam_btn.clicked.connect(self.generate_cam_mechanism)
        self.play_btn.clicked.connect(self.play_simulation)
        self.stop_btn.clicked.connect(self.stop_simulation)
        self.reset_sim_btn.clicked.connect(self.reset_simulation)
        self.blueprint_btn.clicked.connect(self.generate_blueprint)

        # Editor View Signals
        self.editor_view.joint_defined.connect(self.request_create_joint)
        self.editor_view.end_effector_selected.connect(self._handle_end_effector_set) # Connect signal
        self.editor_view.cam_center_selected.connect(self._handle_cam_center_set)
        self.editor_view.drawing_cancelled.connect(self._handle_drawing_cancel)

        # Tab 3: Options (Connect signals from OptionsTab instance)
        self.options_tab.animationDurationChanged.connect(self._update_animation_duration)
        self.options_tab.themeChanged.connect(self._apply_theme) # Re-add theme connection

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
        if current_item:
            self.update_part_properties(current_item, previous_item)
            # Select in scene as well
            part_name = current_item.data(Qt.ItemDataRole.UserRole)
            if part_name in self.editor_items:
                self.editor_scene.clearSelection()
                self.editor_items[part_name].setSelected(True)
        else:
            # Clear properties if nothing selected
            self.z_value_spin.setEnabled(False)
            self.fixed_part_check.setEnabled(False)

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
            return

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
                                loc = skeleton_map[name]
                                if len(loc) >= 2:
                                     editor_item.setPos(loc[0], loc[1])
                                     logging.debug(f"Positioning '{name}' using skeleton (ROI fallback): {loc}")
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
                    editor_item.is_fixed = info.get('is_fixed', False)
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

                    self.editor_scene.addItem(editor_item)
                    self.editor_items[name] = editor_item

                    # Add to list widget
                    list_item = QListWidgetItem(name)
                    list_item.setData(Qt.ItemDataRole.UserRole, name)
                    self.parts_list.addItem(list_item)
                else:
                    logging.warning(f"Part '{name}' has no visual representation (SVG or Image). Skipping add to scene.")

            # Load joints if they exist in the data
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
        """Clears all items and data related to the editor tab."""
        self.editor_scene.clear()
        self.parts_list.clear()
        self.parts.clear()
        self.editor_items.clear()
        self.joints.clear()
        self.kinematic_chains.clear()
        self.cam_profile_item = None
        self.cam_follower_item = None
        self.driving_cam_center = QPointF(0, 0)
        self.cam_center_marker = None
        # Reset property widgets
        self.z_value_spin.setValue(0)
        self.z_value_spin.setEnabled(False)
        self.fixed_part_check.setChecked(False)
        self.fixed_part_check.setEnabled(False)

    def get_selected_editor_item(self):
        """Returns the currently selected CharacterPartItem in the editor scene."""
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
            if self.define_motion_btn.isChecked():
                 self.define_motion_btn.setChecked(False)
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
        """Toggles the motion path drawing mode in the editor view."""
        if checked:
            # Uncheck other mode buttons
            if self.define_joint_btn.isChecked():
                self.define_joint_btn.setChecked(False)
            self.editor_view.start_define_motion_path()
        else:
             # If user unchecks button, finish the path drawing
            if self.editor_view.current_mode == 'define_motion_path':
                self.editor_view.finish_motion_path_drawing()

    def _start_end_effector_selection(self):
        """Initiates the end effector point selection mode."""
        self.editor_view.start_select_end_effector()

    @pyqtSlot(QPointF, QPointF)
    def _handle_end_effector_set(self, local_pos: QPointF, scene_pos: QPointF):
        """Handles the signal emitted when the end effector point is set in the view."""
        item = self.get_selected_editor_item()
        if item:
             # The view already updated the item's offset and marker
             logging.info(f"End effector point set for '{item.part_info.name}' at local {local_pos}")
             self.statusBar().showMessage(f"End effector set for '{item.part_info.name}'")
        else:
             logging.warning("End effector set signal received, but no item selected?")

    def preview_motion_path(self):
        """Previews the motion of the selected part along its defined path."""
        item = self.get_selected_editor_item()
        if not item:
            QMessageBox.warning(self, "Preview Error", "Please select a part with a motion path.")
            return
        if not item.motion_path or item.motion_path.isEmpty():
             QMessageBox.warning(self, "Preview Error", "Selected part has no motion path defined.")
             return

        # --- Simple Preview Animation --- #
        if hasattr(self, "_preview_timer") and self._preview_timer.isActive():
            self._preview_timer.stop()

        self._preview_item = item
        self._preview_original_pos = item.pos()
        self._preview_time = 0.0
        self._preview_duration = 3.0 # 3 second preview

        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(20) # 50 FPS

        def update_preview_frame():
            self._preview_time += self._preview_timer.interval() / 1000.0
            progress = (self._preview_time % self._preview_duration) / self._preview_duration
            if self._preview_time > self._preview_duration:
                 self._preview_item.setPos(self._preview_original_pos)
                 self._preview_timer.stop()
                 self.statusBar().showMessage("Motion preview finished.")
                 del self._preview_timer # Clean up timer
                 return

            path_pos = self._preview_item.motion_path.pointAtPercent(progress)
            self._preview_item.setPos(path_pos)

        self._preview_timer.timeout.connect(update_preview_frame)
        self._preview_timer.start()
        self.statusBar().showMessage(f"Previewing motion for '{item.part_info.name}'...")

    # --- Cam Mechanism Actions ---

    def _start_cam_center_selection(self):
        """Initiates the cam center point selection mode."""
        self.editor_view.start_select_cam_center()

    @pyqtSlot(QPointF)
    def _handle_cam_center_set(self, scene_pos: QPointF):
        """Handles the signal emitted when the cam center is set in the view."""
        self.driving_cam_center = scene_pos
        self._update_cam_center_marker()
        logging.info(f"Cam center set at {scene_pos}")
        self.statusBar().showMessage(f"Cam center set at ({scene_pos.x():.1f}, {scene_pos.y():.1f})")

    def _update_cam_center_marker(self):
        """Updates the visual marker for the cam center."""
        if not self.editor_scene:
            return
        # Remove old marker
        if self.cam_center_marker and self.cam_center_marker.scene() == self.editor_scene:
            self.editor_scene.removeItem(self.cam_center_marker)
        # Create new marker (cross shape)
        path = QPainterPath()
        size = 10
        path.moveTo(-size, 0)
        path.lineTo(size, 0)
        path.moveTo(0, -size)
        path.lineTo(0, size)
        self.cam_center_marker = self.editor_scene.addPath(path, QPen(QColor("cyan"), 2))
        self.cam_center_marker.setPos(self.driving_cam_center)
        self.cam_center_marker.setZValue(100) # Ensure visible

    def set_cam_follower(self):
        """Sets the currently selected part as the cam follower."""
        item = self.get_selected_editor_item()
        if not item:
            QMessageBox.warning(self, "Cam Follower Error", "Please select a part to designate as the cam follower.")
            return
        if not item.motion_path or item.motion_path.isEmpty():
             QMessageBox.warning(self, "Cam Follower Error", f"Selected part '{item.part_info.name}' has no motion path defined.")
             return

        self.cam_follower_item = item
        logging.info(f"Part '{item.part_info.name}' set as cam follower.")
        self.statusBar().showMessage(f"'{item.part_info.name}' set as cam follower.")

    def generate_cam_mechanism(self):
        """Generates the cam profile based on the follower's path and center."""
        if not self.driving_cam_center:
            QMessageBox.warning(self, "Cam Generation Error", "Please set the cam center point first.")
            return
        if not self.cam_follower_item:
             QMessageBox.warning(self, "Cam Generation Error", "Please set the cam follower part first.")
             return

        motion_path = self.cam_follower_item.motion_path
        if not motion_path or motion_path.isEmpty(): # Should be checked by set_cam_follower, but double-check
            QMessageBox.warning(self, "Cam Generation Error", f"Follower '{self.cam_follower_item.part_info.name}' has no motion path.")
            return

        logging.info(f"Generating cam profile for follower '{self.cam_follower_item.part_info.name}' around center {self.driving_cam_center}")
        try:
            # Call the generation function (needs implementation)
            cam_path = generate_cam_profile(motion_path, self.driving_cam_center)
            if not cam_path or cam_path.isEmpty():
                raise ValueError("Generated cam path is empty or invalid.")

            # Remove previous profile visualization
            if self.cam_profile_item and self.cam_profile_item.scene():
                 self.editor_scene.removeItem(self.cam_profile_item)

            # Add new profile visualization
            self.cam_profile_item = self.editor_scene.addPath(cam_path, QPen(QColor("magenta"), 2))
            self.cam_profile_item.setZValue(-10) # Draw behind parts
            self.cam_profile_item.setPos(self.driving_cam_center) # Position relative to center

            self.statusBar().showMessage("Cam profile generated successfully.")
            logging.info("Cam profile generated and visualized.")

        except Exception as e:
            logging.error(f"Error generating cam profile: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Cam Generation Error", f"Failed to generate cam profile: {e}")
            if self.cam_profile_item and self.cam_profile_item.scene():
                 self.editor_scene.removeItem(self.cam_profile_item)
            self.cam_profile_item = None

    # --- Simulation Actions ---

    def build_kinematic_chains(self):
        """Builds the kinematic chains required for IK simulation."""
        self.kinematic_chains.clear()
        items_with_paths = [item for item in self.editor_items.values() if item.motion_path and not item.motion_path.isEmpty()]

        if not items_with_paths:
            QMessageBox.information(self, "Build Chains", "No motion paths found on any parts. Cannot build chains.")
            return

        built_chains_count = 0
        for end_effector_item in items_with_paths:
            chain = []
            current_item = end_effector_item
            visited = set()
            while current_item and current_item not in visited:
                visited.add(current_item)
                chain.insert(0, current_item) # Prepend to get base -> tip order
                if current_item.is_fixed:
                    break # Found the root
                # Traverse up the hierarchy using parent_joint
                if hasattr(current_item, 'parent_joint') and current_item.parent_joint:
                    current_item = current_item.parent_joint.parent_item
                else:
                    current_item = None # Reached top without fixed base

            # Check if chain is valid (ends with a fixed part)
            if chain and chain[0].is_fixed:
                self.kinematic_chains[end_effector_item.part_info.name] = chain
                built_chains_count += 1
                logging.info(f"Built chain for '{end_effector_item.part_info.name}': {[item.part_info.name for item in chain]}")
            elif chain:
                logging.warning(f"Kinematic chain for '{end_effector_item.part_info.name}' does not end in a fixed part. Discarding.")
            else:
                logging.warning(f"Could not build valid kinematic chain for '{end_effector_item.part_info.name}'. Check joints and fixed parts.")

        if built_chains_count > 0:
            self.statusBar().showMessage(f"Built {built_chains_count} kinematic chain(s). Ready for simulation.")
        else:
            self.statusBar().showMessage("Could not build any valid kinematic chains. Check joints and ensure at least one part is fixed.")
            QMessageBox.warning(self, "Build Chains Failed", "Could not build any valid kinematic chains. Ensure parts are connected by joints and at least one part in each chain is marked as fixed.")

    def play_simulation(self):
        """Starts the kinematic simulation."""
        if not self.editor_items:
            QMessageBox.warning(self, "Simulation Error", "No parts loaded in the editor.")
            return
        # Ensure chains are built
        if not self.kinematic_chains:
            self.build_kinematic_chains()
            if not self.kinematic_chains:
                 # build_kinematic_chains already showed a message
                 return

        logging.info("Starting simulation...")
        # Prepare simulation scene (copy state from editor)
        self._copy_state_to_simulation_scene()

        self.animation_time = 0.0
        self.timer.start()
        self.statusBar().showMessage("Simulation running...")
        # Disable editor interactions during simulation?
        self.editor_view.set_mode('simulation') # Use editor view's mode management

    def stop_simulation(self):
        """Stops the kinematic simulation."""
        if self.timer.isActive():
            logging.info("Stopping simulation.")
            self.timer.stop()
            self.statusBar().showMessage("Simulation stopped.")
            self.editor_view.set_mode('select') # Restore editor interaction
        else:
             self.statusBar().showMessage("Simulation not running.")

    def reset_simulation(self):
        """Stops the simulation and resets parts to their initial state."""
        self.stop_simulation() # Ensure timer is stopped
        logging.info("Resetting simulation state.")
        self.editor_view.reset_simulation() # Let the view handle resetting transforms
        self.animation_time = 0.0
        # Clear any simulation-specific visualizations if needed
        self.statusBar().showMessage("Simulation reset.")

    def update_simulation(self):
        """Performs one step of the simulation (called by timer)."""
        delta_time = self.timer.interval() / 1000.0
        self.animation_time += delta_time
        # Use modulo for looping animation
        progress = (self.animation_time % self.animation_duration) / self.animation_duration

        if not self.kinematic_chains:
            logging.warning("Update simulation called with no kinematic chains.")
            self.stop_simulation()
            return

        # Process each defined kinematic chain
        for end_effector_name, chain in self.kinematic_chains.items():
            # Get the corresponding items in the *editor* scene (simulation happens here)
            editor_chain = [self.editor_items.get(item.part_info.name) for item in chain]
            editor_end_effector = editor_chain[-1] if editor_chain else None

            if not editor_end_effector or not editor_end_effector.motion_path or editor_end_effector.motion_path.isEmpty():
                continue # Skip chains without a valid end effector or path

            # 1. Calculate Target Position on the path
            target_pos = editor_end_effector.motion_path.pointAtPercent(progress)
            # Visualize target? (Optional)
            # if not hasattr(self, 'ik_target_marker'): self.ik_target_marker = ...
            # self.ik_target_marker.setPos(target_pos)

            # 2. Call IK Solver
            # Ensure all items in the chain exist
            if all(item is not None for item in editor_chain):
                solve_ik_ccd(editor_chain, target_pos, iterations=15, tolerance=0.5)
            else:
                logging.warning(f"Skipping IK for chain '{end_effector_name}' due to missing items.")

        # Update the scene to show results
        self.editor_scene.update()

    def _copy_state_to_simulation_scene(self):
        """Copies the current state (transforms, etc.) from editor items.
        This is primarily used to store the *initial* state before simulation starts.
        The actual simulation modifies the editor items directly.
        """
        self.editor_view._save_original_transforms() # Use the view's method

    # --- Blueprint Generation --- #

    def generate_blueprint(self):
        """Generates an SVG blueprint of all parts."""
        if not self.editor_items:
            QMessageBox.warning(self, "Blueprint Error", "No parts loaded to generate a blueprint.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Blueprint As", self.character_dir or "", "SVG Files (*.svg)")
        if not save_path:
            return

        logging.info(f"Generating SVG blueprint to {save_path}")
        try:
            # Call the generation function (needs implementation)
            svg_content = generate_blueprint_svg(list(self.editor_items.values()))

            if not svg_content:
                raise ValueError("Blueprint generation returned empty content.")

            with open(save_path, 'w') as f:
                f.write(svg_content)

            self.statusBar().showMessage(f"Blueprint saved to {os.path.basename(save_path)}")
            logging.info("Blueprint generated successfully.")
            # Optionally open the file?
            # import webbrowser
            # webbrowser.open(save_path)

        except Exception as e:
            logging.error(f"Error generating blueprint: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Blueprint Error", f"Failed to generate blueprint: {e}")

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
                "cam_center": None,
                "cam_follower": None
            }

            # Save parts data
            for name, item in self.editor_items.items():
                part_data = {
                    "name": name,
                    "svg_path": os.path.relpath(item.part_info.svg_path_file, self.character_dir) if self.character_dir and item.part_info.svg_path_file else item.part_info.svg_path_file, # Store relative path if possible
                    "image_path": os.path.relpath(item.part_info.image_path, self.character_dir) if self.character_dir and item.part_info.image_path else item.part_info.image_path,
                    "position": {"x": item.pos().x(), "y": item.pos().y()},
                    "z_value": item.zValue(),
                    "is_fixed": item.is_fixed,
                    "transform": transform_to_dict(item.transform()), # Use helper
                    "fill_color": item.part_info.fill_color # Save color
                }

                # Save motion path if any
                if item.motion_path and not item.motion_path.isEmpty():
                    # Using the helper function now
                    part_data["motion_path"] = qpainterpath_to_points(item.motion_path)

                # Save end effector if any
                if item.end_effector_offset:
                    part_data["end_effector"] = {
                        "x": item.end_effector_offset.x(),
                        "y": item.end_effector_offset.y()
                    }

                project_data["parts"][name] = part_data

            # Save joints
            for joint in self.joints:
                joint_data = {
                    "parent": joint.parent_item.part_info.name,
                    "child": joint.child_item.part_info.name,
                    "parent_pos": {"x": joint.parent_pos.x(), "y": joint.parent_pos.y()},
                    "child_pos": {"x": joint.child_pos.x(), "y": joint.child_pos.y()}
                    # Could also save joint.angle if needed
                }
                project_data["joints"].append(joint_data)

            # Save cam center if any
            if self.driving_cam_center:
                project_data["cam_center"] = {
                    "x": self.driving_cam_center.x(),
                    "y": self.driving_cam_center.y()
                }

            # Save cam follower if any
            if self.cam_follower_item:
                project_data["cam_follower"] = self.cam_follower_item.part_info.name

            # Write to file
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

    def _handle_drawing_cancel(self):
        """Handles cancellation signals from the EditorView."""
        # Ensure corresponding mode buttons are unchecked
        if self.define_joint_btn.isChecked(): self.define_joint_btn.setChecked(False)
        if self.define_motion_btn.isChecked(): self.define_motion_btn.setChecked(False)
        # Add others if needed (cam center etc)

    def closeEvent(self, event):
        """Handles window close event, ensuring camera cleanup."""
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

    # --- Options Tab Slots ---
    def _update_animation_duration(self, value: float):
        """Updates the simulation animation duration."""
        self.animation_duration = value
        logging.info(f"Animation duration set to {value} seconds.")
        self.statusBar().showMessage(f"Animation duration: {value:.1f} s")

    # Re-add _apply_theme method
    def _apply_theme(self, theme_name: str):
        """Applies the selected theme (Light or Dark)."""
        logging.info(f"Applying theme: {theme_name}")
        if theme_name == "Dark":
            self.setStyleSheet(self.dark_style)
        else: # Default to Light
            self.setStyleSheet(self.light_style)
        self.statusBar().showMessage(f"Theme changed to {theme_name}")