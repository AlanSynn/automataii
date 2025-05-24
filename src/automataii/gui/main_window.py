import os
import json
import logging
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QGraphicsScene,
    QTabWidget,
    QMessageBox,
    QToolBar,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QFileDialog
)
from PyQt6.QtGui import (
    QColor,
    QPen,
    QPainterPath,
    QBrush,
)
from PyQt6.QtCore import (
    Qt,
    QPointF,
    QTimer,
    pyqtSlot,
    QRectF,
)
from pathlib import Path
from typing import Optional, Dict, Any, List

# Local imports (adjust paths as needed)
from .image_view import ImageProcessingView
from .part_item import CharacterPartItem
from .styling import LIGHT_STYLE, DARK_STYLE, UIColors

# from .options_tab import OptionsTab # Removed: OptionsTab is now in tabs directory
from ..core.models import PartInfo

# Import new tab modules
from .tabs.image_processing_tab import ImageProcessingTab
from .tabs.editor_tab import EditorTab
from .tabs.options_tab import OptionsTab

# Import ActionManager for centralized action management
from .actions.action_manager import ActionManager

# Import SkeletonManager
from ..core.skeleton_manager import SkeletonManager

# Import IKManager
from ..kinematics.ik_manager import IKManager

# Import ProjectDataManager
from ..core.project_data_manager import ProjectDataManager

# Import MechanismManager
from ..core.mechanism_manager import MechanismManager

from PyQt6.QtWidgets import QGraphicsEllipseItem

TARGET_CONTROL_POINTS = 8


class AutomataDesigner(QMainWindow):
    """Main application window for the Automata Designer.

    Integrates image processing, skeleton editing, part assembly, motion definition,
    simulation, and blueprint generation.
    """

    def __init__(self, parent: Optional[QWidget] = None, debug_mode: bool = False):
        super().__init__(parent)
        self.debug_mode = debug_mode
        logging.info(f"Initializing AutomataDesigner... Debug mode: {self.debug_mode}")
        self.setWindowTitle("Automata Designer")
        self.resize(1200, 680)  # Reduced height from 750
        self.setMinimumHeight(600)  # Set explicit minimum height
        logging.info("Initializing AutomataDesigner...")

        # Create action manager for centralized action management
        self.action_manager = ActionManager(self)

        # Create ProjectDataManager
        self.project_data_manager = ProjectDataManager(self)

        # Create SkeletonManager
        self.skeleton_manager = SkeletonManager(self)

        # Create IKManager
        self.ik_manager = IKManager(self)

        # Create MechanismManager
        self.mechanism_manager = MechanismManager(self)

        # --- Data Storage ---
        # self.editor_items = {}  # part_name: CharacterPartItem (in editor scene) # REMOVED - EditorTab now manages its items
        # self.joints = []  # List of Joint objects # REMOVED - EditorTab will manage its joints
        # self.mechanism_visuals = {}  # layer_name: list[QGraphicsItem] # REMOVED - EditorTab manages this
        # self.layer_checkboxes = {}  # layer_name: QCheckBox # REMOVED - EditorTab manages this
        # self._body_parts_viz_items = []  # REMOVED - Unused
        # self._body_parts_viz_items_image = []  # REMOVED - Unused
        # self.anchor_items = {}  # REMOVED - Unused

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
        # self.image_proc_scene = QGraphicsScene() # Moved to ImageProcessingTab
        # self.image_proc_view = ImageProcessingView(self.image_proc_scene, self) # Moved to ImageProcessingTab
        # self.editor_scene = QGraphicsScene() # Moved to EditorTab
        # self.editor_view = EditorView(self.editor_scene, self) # Moved to EditorTab

        # Mechanism Design State - These are now managed by EditorTab or via signals
        # self.selected_cam_center: Optional[QPointF] = None # Moved to EditorTab
        # self.selected_pivot_a: Optional[QPointF] = None # Moved to EditorTab
        # self.selected_pivot_d: Optional[QPointF] = None # Moved to EditorTab
        # self.selected_driver_center: Optional[QPointF] = None # Moved to EditorTab
        # self.selected_driven_center: Optional[QPointF] = None # Moved to EditorTab
        # Markers for selected points - these are drawn by EditorView, state might be in MainWindow if needed globally
        # self.cam_center_marker: Optional[QGraphicsEllipseItem] = None # Moved to EditorTab
        # self.pivot_a_marker: Optional[QGraphicsEllipseItem] = None # Moved to EditorTab
        # self.pivot_d_marker: Optional[QGraphicsEllipseItem] = None # Moved to EditorTab
        # self.driver_center_marker: Optional[QGraphicsEllipseItem] = None # Moved to EditorTab
        # self.driven_center_marker: Optional[QGraphicsEllipseItem] = None # Moved to EditorTab

        # Image processing workflow data moved to ImageProcessingTab
        # self.input_image_path = None # Moved
        # self.character_dir = None # Potentially still needed for project-level, but tab specific one is moved. For now, keep project-level one.
        self.project_dir: Optional[str] = None  # Renamed/clarified for project scope

        # IK Animation Timer (New)
        # self.ik_animation_timer = QTimer(self)
        # self.ik_animation_timer.setInterval(30)  # Approx 33 FPS
        # self.ik_animation_timer.timeout.connect(
        #     self._run_ik_animation_step
        # )  # Connect to new animation step
        # self.ik_animation_speed = 0.5  # Default animation speed, similar to JS example
        # self.animation_duration = 3000

        # --- Toolbar Reference ---
        self.main_toolbar = None

        # Tracking active dialogs
        # self.active_camera_dialogs = [] # Moved to ImageProcessingTab

        # --- Stylesheet Data --- (No longer need _define_stylesheets method)
        self.light_style = LIGHT_STYLE
        self.dark_style = DARK_STYLE

        self.visualization_layer_x_offset = (
            10.0  # Horizontal offset for visualization layers
        )

        # Load Parts and Styles
        # self.load_initial_data() # Commented out: Method definition not found, functionality likely moved or obsolete.

        # Load custom application fonts
        self._load_custom_fonts()

        # Setup UI, Menus, Toolbar, and connections
        self._init_ui()  # This creates self.editor_tab and other UI elements
        self._create_menus()  # Defines QActions and populates menubar
        self._create_toolbar()  # Defines QActions or uses existing ones for toolbar
        self._connect_global_signals()
        self._connect_manager_signals() # New method for connecting manager signals

        self.statusBar().showMessage("Ready")
        logging.info("AutomataDesigner initialized.")

        # self.scene_joints_snapshot = {}  # Will store the calculated scene_joints from _initialize_new_ik_skeleton_definitions # MODIFIED - Moved to IKManager
        # self.ik_part_to_actual_part_name = { # MODIFIED - Moved to IKManager
        #     "head": "head",
        #     "torso": "torso",
        #     "left_upper_arm": "left_arm_upper",
        #     "left_forearm": "left_arm_lower",
        #     "right_upper_arm": "right_arm_upper",
        #     "right_forearm": "right_arm_lower",
        #     "left_thigh": "left_leg_upper",
        #     "left_calf": "left_leg_lower",
        #     "right_thigh": "right_leg_upper",
        #     "right_calf": "right_leg_lower",
        # } # MODIFIED
        # self._active_path_definition_target_joint_id: Optional[str] = ( # MODIFIED - Moved to IKManager (if it's pure IK state)
        #     None  # Stores the joint ID while path definition is active
        # ) # MODIFIED
        # self.ik_to_json_joint_map_config = {  # Maps our IK joint IDs to keys in the char_cfg.yaml/joint_map # MODIFIED - Moved to IKManager
        #     "j_neck_base": "neck",  # Anchor
        #     "j_left_shoulder": "left_shoulder",  # Anchor
        #     "j_right_shoulder": "right_shoulder",  # Anchor
        #     "j_left_hip": "left_hip",  # Anchor
        #     "j_right_hip": "right_hip",  # Anchor
        #     "j_head": "neck",  # Distal end for head (uses neck as its proximal point from char_cfg)
        #     # Actual j_head position will be calculated based on neck_base + head_length
        #     "j_left_elbow": "left_elbow",
        #     "j_left_wrist": "left_hand",
        #     "j_right_elbow": "right_elbow",
        #     "j_right_wrist": "right_hand",
        #     "j_left_knee": "left_knee",
        #     "j_left_ankle": "left_foot",
        #     "j_right_knee": "right_knee",
        #     "j_right_ankle": "right_foot",
        # } # MODIFIED

        # --- New IK System Data --- # MODIFIED
        # self.sim_joints_config = {}  # Stores structure: { 'j_neck_base': {'xOffset': ..., 'yOffset': ..., 'label': ...}, ... } # MODIFIED - Moved to IKManager
        # self.sim_limb_configs = {}  # Stores structure: { 'j_head': {'parentAnchor': ..., 'angle': ..., 'length': ...}, ... } # MODIFIED - Moved to IKManager
        # self.sim_limb_lengths = {}  # Stores structure: { 'head': 35, 'upperArm': 55, ... } # MODIFIED - Moved to IKManager
        # self.sim_selectable_components = []  # List of dicts defining selectable parts for IK path definition # MODIFIED - Moved to IKManager
        # self.sim_two_bone_ik_effectors = []  # List of joint IDs that are end-effectors of a 2-bone chain # MODIFIED - Moved to IKManager
        # self.sim_joint_bend_directions = {}  # { 'j_left_elbow': -1, ... } # MODIFIED - Moved to IKManager

        # Actual data store for sim_dynamic_joints property # MODIFIED
        # self._sim_dynamic_joints_data: Dict[str, Dict[str, Any]] = {} # MODIFIED - Moved to IKManager
        # logging.info("[ATTR_DEBUG] Initializing self._sim_dynamic_joints_data = {}") # MODIFIED

        # self.sim_selected_component_key = None  # Stores the targetJointId of the currently selected component for path drawing # MODIFIED - Moved to IKManager (if pure IK state)
        # self.current_parts_info_data = None  # Will store loaded parts_info.json content # REMOVED - ProjectDataManager is source of truth
        # self.effective_bounding_box_offset = QPointF( # REMOVED - Managed by ProjectDataManager
        #     0, 0
        # )  # Will store calculated offset
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
        self.image_proc_tab = ImageProcessingTab(self)
        self.tab_widget.addTab(self.image_proc_tab, "Character Selection")

        # --- Tab 2: Editor & Simulation ---
        self.editor_tab = EditorTab(self)
        self.tab_widget.addTab(self.editor_tab, "Mechanism Design")

        # --- Tab 3: Options ---
        self.options_tab = OptionsTab(initial_anim_duration=self.ik_manager.animation_duration)
        self.tab_widget.addTab(self.options_tab, "Options")

        # --- Connect Signals from EditorView --- (These are now connected within EditorTab)
        # self.editor_view.freehandPathCompleted.connect(
        #     self._handle_freehand_path_completed
        # )
        # self.editor_view.drawing_cancelled.connect(self._handle_drawing_cancelled)
        # self.editor_view.joint_defined.connect(
        #     self.request_create_joint
        # )  # MainWindow handles this logic
        # # Mechanism point selection signals from EditorView connected to MainWindow slots
        # self.editor_view.cam_center_selected.connect(self._handle_cam_center_set)
        # self.editor_view.pivot_a_selected.connect(self._handle_pivot_a_set)
        # self.editor_view.pivot_d_selected.connect(self._handle_pivot_d_set)
        # self.editor_view.driver_center_selected.connect(self._handle_driver_center_set)
        # self.editor_view.driven_center_selected.connect(self._handle_driven_center_set)

        # --- Connect Signals from ImageProcessingTab ---
        self.image_proc_tab.parts_generated.connect(
            self.handle_parts_generated_from_tab
        )
        self.image_proc_tab.skeleton_updated.connect(
            self.handle_skeleton_updated_from_tab
        )
        self.image_proc_tab.request_editor_tab_switch.connect(self.switch_to_editor_tab)

        # --- Connect Signals from EditorTab ---
        self.editor_tab.request_play_simulation.connect(self.ik_manager.start_animation)
        self.editor_tab.request_stop_simulation.connect(self.ik_manager.stop_animation)
        self.editor_tab.request_reset_simulation.connect(self.ik_manager.reset_animation_state)
        self.editor_tab.request_generate_mechanism.connect(
            self.handle_generate_mechanism_request
        )
        self.editor_tab.request_generate_blueprint.connect(self.generate_blueprint_impl)
        self.editor_tab.request_save_alignment.connect(
            self.save_character_alignment_impl
        )
        # self.editor_tab.parts_loaded.connect(self.image_proc_tab.on_parts_loaded_in_editor)
        # self.editor_tab.parts_cleared.connect(lambda: self.image_proc_tab.on_parts_loaded_in_editor(False))
        # These are better handled in self.load_parts and self.clear_project_data

        # --- Connect Signals from OptionsTab ---
        self.options_tab.animationDurationChanged.connect(
            self.ik_manager.set_animation_duration
        )
        self.options_tab.themeChanged.connect(self._apply_theme)
        self.options_tab.toolbarVisibilityChanged.connect(
            self._toggle_toolbar_visibility
        )
        self.options_tab.partPropertiesVisibilityChanged.connect(
            self._toggle_part_properties_visibility
        )
        self.options_tab.partPropertiesVisibilityChanged.connect(
            self.editor_tab.toggle_part_properties_panel_visibility
        )
        self.options_tab.setting_changed.connect(self._handle_option_change)
        # Connect advanced processing visibility toggle
        if hasattr(self.options_tab, 'advancedProcessingVisibilityChanged') and hasattr(self.image_proc_tab, '_toggle_detailed_processing_visibility'):
            self.options_tab.advancedProcessingVisibilityChanged.connect(self.image_proc_tab._toggle_detailed_processing_visibility)

        # Connect menu actions using ActionManager
        self.action_manager.connect_action("load_parts", self.load_parts_dialog)
        self.action_manager.connect_action("save_project", self.save_project_dialog)
        self.action_manager.connect_action("exit", self.close)
        self.action_manager.connect_action(
            "zoom_in",
            lambda: self.editor_tab.editor_view.zoom_in() # Call on EditorTab's view
            if self.tab_widget.currentWidget() == self.editor_tab
            else None, # Add a default None if no active tab matches known views
        )
        self.action_manager.connect_action(
            "zoom_out",
            lambda: self.editor_tab.editor_view.zoom_out() # Call on EditorTab's view
            if self.tab_widget.currentWidget() == self.editor_tab
            else None, # Add a default None
        )
        self.action_manager.connect_action(
            "zoom_fit",
            lambda: self.editor_tab.editor_view.zoom_to_fit() # Call on EditorTab's view
            if self.tab_widget.currentWidget() == self.editor_tab
            else None, # Add a default None
        )
        self.action_manager.connect_action(
            "reset_view", lambda: self.editor_tab.editor_view.reset_view() # Call on EditorTab's view
            if self.tab_widget.currentWidget() == self.editor_tab else None
        )
        self.action_manager.connect_action("undo", lambda: self.editor_tab.editor_view.undo() # Call on EditorTab's view
            if self.tab_widget.currentWidget() == self.editor_tab else None
        )
        self.action_manager.connect_action("redo", lambda: self.editor_tab.editor_view.redo() # Call on EditorTab's view
            if self.tab_widget.currentWidget() == self.editor_tab else None
        )
        self.action_manager.connect_action("about", self.show_about_dialog)

        # Test Anchors Button Connection (This button is now in EditorTab, EditorTab should handle its toggled signal)
        # self.toggle_anchors_btn.toggled.connect(self._toggle_test_anchors_visibility)

        # Connect other existing signals as needed
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _load_custom_fonts(self):
        """Loads custom application fonts.

        Placeholder method. Implement font loading logic here.
        """
        logging.info("Placeholder: _load_custom_fonts() called.")
        # Example: Add font loading logic using QFontDatabase
        # font_db = QFontDatabase()
        # font_id = font_db.addApplicationFont(":/fonts/my_custom_font.ttf")
        # if font_id == -1:
        #     logging.warning("Failed to load custom font.")
        # else:
        #     font_families = QFontDatabase.applicationFontFamilies(font_id)
        #     if font_families:
        #         logging.info(f"Loaded custom font: {font_families[0]}")

    # --- Menu Creation ---
    def _create_menus(self):
        """Creates the main application menus using the ActionManager."""
        menubar = self.menuBar()
        self.action_manager.setup_menus(menubar)

    # --- Toolbar Creation ---
    def _create_toolbar(self):
        """Creates the main application toolbar using the ActionManager."""
        self.main_toolbar = QToolBar("Main Toolbar")
        self.main_toolbar.setMovable(False)

        # Setup toolbar using the action manager
        self.action_manager.setup_toolbar(self.main_toolbar)

        # Add to main window and hide by default
        self.addToolBar(self.main_toolbar)
        self.main_toolbar.hide()

    # --- Tab Management ---
    def _on_tab_changed(self, index: int):
        current_tab = self.tab_widget.widget(index)
        if hasattr(current_tab, "tab_name"):
            self.statusBar().showMessage(f"{current_tab.tab_name} tab active") # type: ignore
        else:
            self.statusBar().showMessage(f"Tab {index+1} active")

        # If EditorTab is selected, ensure its view is updated if parts are loaded
        if current_tab == self.editor_tab and self.project_data_manager.parts:
            # This might be redundant if EditorTab updates itself on data load
            # Consider if a specific refresh is needed here.
            # For now, we assume EditorTab is populated by _handle_project_data_loaded
            logging.debug("Editor tab selected, parts should be loaded if project is open.")
            pass

    # --- New Slots for ImageProcessingTab Signals ---
    @pyqtSlot(dict)
    def handle_parts_generated_from_tab(self, generated_data: dict):
        """Handles the parts_generated signal from ImageProcessingTab."""
        logging.info(
            f"MainWindow: Received parts_generated signal with data: {generated_data}"
        )

        parts_info_json_path = generated_data.get('parts_info_path')
        temp_char_dir = generated_data.get('output_dir') # This is the base temp dir for this character session

        if not parts_info_json_path or not temp_char_dir:
            QMessageBox.warning(
                self, "Processing Error", "Received incomplete data from image processing stage."
            )
            logging.error(f"handle_parts_generated_from_tab: Missing parts_info_path or output_dir in {generated_data}")
            return

        logging.info(f"Attempting to load project from generated parts_info: {parts_info_json_path}")
        # ProjectDataManager.load_project_from_file will handle loading parts_info.json
        # and then its _try_load_supplemental_skeleton_data will look for char_cfg.yaml
        # in the same directory (temp_char_dir).
        success = self.project_data_manager.load_project_from_file(parts_info_json_path)

        if success:
            # The actual UI updates, tab switching, etc., are handled by
            # _handle_project_data_loaded when ProjectDataManager emits its signal.
            self.statusBar().showMessage( # This might be overwritten by PDM's signal handler
                f"Project data initiated from temp location: {temp_char_dir}", 5000
            )
            # No explicit tab switch here; _handle_project_data_loaded will do it if parts are found.
        else:
            QMessageBox.warning(
                self, "Load Error", f"Failed to load generated project data from {parts_info_json_path}"
            )
            logging.error(f"Failed to load project using PDM from generated file: {parts_info_json_path}")

    @pyqtSlot(dict)
    def handle_skeleton_updated_from_tab(self, skeleton_data: dict):
        """Handles the skeleton_updated signal from ImageProcessingTab."""
        logging.info("MainWindow: Received skeleton_updated signal from tab. Forwarding to SkeletonManager.")
        # self.skeleton_data = skeleton_data # OLD: MainWindow should not hold its own copy like this
        # self._initialize_new_ik_skeleton_definitions()  # Re-initialize IK system with new skeleton # OLD: This will be triggered by SkeletonManager's update
        # # Notify editor tab if it needs to update its view based on the new skeleton
        # if hasattr(self.editor_tab, "on_skeleton_updated"): # OLD: This will be triggered by SkeletonManager's update
        #     self.editor_tab.on_skeleton_updated(self.skeleton_data)
        # # Also update the image_proc_view if it's showing this skeleton (though ImageProcessingTab manages this primarily)
        # # self.image_proc_view.load_skeleton(self.skeleton_data)

        # NEW: Pass the raw skeleton data from the tab to the SkeletonManager
        # Assuming the data from ImageProcessingTab is in 'animated_drawings' format (char_cfg.yaml like)
        if self.skeleton_manager:
            self.skeleton_manager.load_skeleton_from_dict(skeleton_data, source_format='animated_drawings')
        else:
            logging.error("MainWindow: SkeletonManager not available to handle skeleton update.")
            QMessageBox.warning(self, "Error", "SkeletonManager not initialized. Cannot process skeleton.")

    @pyqtSlot()
    def switch_to_editor_tab(self):
        """Switches the main tab widget to the Editor Tab."""
        editor_idx = -1
        for i in range(self.tab_widget.count()):
            if self.tab_widget.widget(i) == self.editor_tab:
                editor_idx = i
                break
        if editor_idx != -1:
            logging.info("Switching to Editor tab by request.")
            self.tab_widget.setCurrentIndex(editor_idx)
        else:
            logging.warning("Could not find EditorTab to switch to.")

    # --- Styling and Themes ---
    def _apply_theme(self, theme_name: str):
        """Applies the selected theme (stylesheet) to the application."""
        # ... existing code ...

    def _toggle_toolbar_visibility(self, visible: bool):
        """Toggles the visibility of the main toolbar."""
        if self.main_toolbar:
            self.main_toolbar.setVisible(visible)
            logging.info(f"Main toolbar visibility set to: {visible}")
        else:
            logging.warning("_toggle_toolbar_visibility called but main_toolbar is None.")

    def _toggle_part_properties_visibility(self, visible: bool):
        """Toggles the visibility of the part properties panel in the EditorTab."""
        if hasattr(self, 'editor_tab') and self.editor_tab:
            if hasattr(self.editor_tab, 'toggle_part_properties_panel_visibility'):
                self.editor_tab.toggle_part_properties_panel_visibility(visible)
                logging.info(f"Part properties panel visibility set to: {visible}")
            else:
                logging.warning("EditorTab does not have 'toggle_part_properties_panel_visibility' method.")
        else:
            logging.warning("_toggle_part_properties_visibility called but editor_tab is not available.")

    # --- Project Data Handling ---
    def load_parts_dialog(self):
        """Opens a file dialog to load parts from a JSON file."""
        # TODO: Use QFileDialog.getOpenFileName
        # For now, let's assume a fixed path for testing or use previous logic
        # We should ideally get project_dir from a settings/config or last used
        start_dir = str(self.project_data_manager.project_dir) if self.project_data_manager.project_dir else os.path.expanduser("~")

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Character Parts File",
            start_dir,
            "JSON files (*.json);;All files (*)",
        )
        if filepath:
            # The actual loading is now handled by ProjectDataManager
            # MainWindow's load_parts is now just a trigger
            self.project_data_manager.load_project_from_file(filepath)
            # The UI updates will be triggered by project_data_manager.project_data_loaded signal

    def load_parts(self, filepath: Optional[str] = None) -> bool:
        """
        DEPRECATED/REFACTORED: This method's core logic is moved to ProjectDataManager.
        This method now primarily serves as a direct way to trigger loading if filepath is provided,
        or it can be removed if load_parts_dialog is the only entry point.
        For now, it delegates to ProjectDataManager.
        """
        if filepath:
            logging.info(f"MainWindow.load_parts called with path: {filepath}. Delegating to ProjectDataManager.")
            return self.project_data_manager.load_project_from_file(filepath)
        else:
            # This case should ideally not be hit if dialog is used.
            # If called without filepath, it implies an issue or needs a default.
            logging.warning("MainWindow.load_parts called without filepath. Consider using load_parts_dialog.")
            self._show_status_message("Error: No file path provided for loading parts.", error=True)
            return False

    # REFACTORED: The old content of load_parts is now largely in ProjectDataManager.
    # UI updates and manager notifications will be handled by a slot connected to
    # ProjectDataManager.project_data_loaded.

    @pyqtSlot(bool, str, dict)
    def _handle_project_data_loaded(
        self,
        success: bool,
        project_directory_path: str,
        parts_info: Dict[str, PartInfo] # from ProjectDataManager
        # editor_graphics_items: Dict[str, CharacterPartItem] # This is no longer passed by the signal
    ):
        """Handles the project_data_loaded signal from ProjectDataManager."""
        if success:
            logging.info(
                f"MainWindow: Project data loaded successfully from {project_directory_path}"
            )
            self.project_dir = project_directory_path # Update project_dir in MainWindow

            # Create CharacterPartItem instances for the EditorTab
            # This logic was previously assumed to be done before this slot was called.
            editor_graphics_items: Dict[str, CharacterPartItem] = {}
            if parts_info:
                for part_name, p_info in parts_info.items():
                    # Assuming CharacterPartItem can be created from PartInfo and project_dir context
                    # This might need access to the texture, which ProjectDataManager might not hold directly.
                    # For now, create a placeholder or assume EditorTab/CharacterPartItem handles texture loading based on PartInfo.
                    # The CharacterPartItem needs the parent (EditorView typically), which is tricky here.
                    # Simplification: EditorTab will create these items from PartInfo.
                    # We pass PartInfo directly to EditorTab, and it manages its own graphics items.
                    pass # This creation logic will move to EditorTab

            # Pass PartInfo data to EditorTab. EditorTab is now responsible for its scene and items.
            self.editor_tab.set_parts_data(parts_info)

            # Update other tabs/managers as needed
            # Pass PartInfo to IKManager for animation paths
            if hasattr(self.ik_manager, 'set_project_parts_data'):
                self.ik_manager.set_project_parts_data(parts_info) # parts_info is Dict[str, PartInfo]

            current_skeleton_data = self.project_data_manager.raw_skeleton_data # CHANGED
            if current_skeleton_data:
                # Pass parts_info for context (e.g., limb lengths from bounding boxes)
                self.skeleton_manager.load_skeleton_from_project_data(current_skeleton_data, parts_info) # CHANGED
            else:
                self.skeleton_manager.clear_data() # SkeletonManager clears its data (and emits signal for IKManager)

            self.image_proc_tab.on_parts_loaded_in_editor(True) # Notify image proc tab

            self.setWindowTitle(f"Automata Designer - {Path(project_directory_path).name}")
            self.statusBar().showMessage(f"Project loaded: {project_directory_path}")
            self.action_manager.update_actions_for_project_state(True)

            # Check if parts were actually loaded to decide on switching
            if parts_info:
                 # Switch to EditorTab if not already there, as parts are loaded
                if self.tab_widget.currentWidget() != self.editor_tab:
                    self.switch_to_editor_tab()
            else:
                logging.info("Project loaded, but no parts data found.")
                # Optionally switch to image_proc_tab or stay if no parts

        else:
            logging.error(f"MainWindow: Project loading failed from {project_directory_path}")
            self._clear_ui_for_failed_load() # Clear UI to reflect failed state
            QMessageBox.critical(
                self, "Load Project Error", f"Failed to load project from {project_directory_path}."
            )
            self.statusBar().showMessage("Project loading failed.")
            self.action_manager.update_actions_for_project_state(False)

    def _clear_ui_for_failed_load(self):
        """Helper to clear relevant UI parts when project loading fails after an attempt."""
        # This is similar to clear_project_data's UI impact but more targeted for a failed load.
        if hasattr(self, 'editor_tab') and self.editor_tab:
            self.editor_tab.clear_editor_content() # EditorTab now clears its own scene

        # self.image_proc_tab.clear_display() # Assuming ImageProcessingTab has a method to clear its display
        if hasattr(self.image_proc_tab, 'clear_display_and_data'): # More robust check
            self.image_proc_tab.clear_display_and_data()


        self.skeleton_manager.clear_data()
        self.ik_manager.clear_ik_data()
        logging.info("UI cleared due to failed project load.")


    @pyqtSlot()
    def _handle_project_data_cleared(self):
        """Handles the project_data_cleared signal from ProjectDataManager."""
        logging.info("MainWindow: Handling project data cleared signal.")

        if hasattr(self, 'editor_tab') and self.editor_tab:
            self.editor_tab.clear_editor_content() # EditorTab clears its own scene and data

        # self.image_proc_tab.clear_display() # Assuming ImageProcessingTab has a method to clear its display
        if hasattr(self.image_proc_tab, 'clear_display_and_data'): # More robust check
            self.image_proc_tab.clear_display_and_data()


        self.skeleton_manager.clear_data()
        self.ik_manager.clear_ik_data()

        self.project_dir = None # Clear project directory
        self.setWindowTitle("Automata Designer")
        self.statusBar().showMessage("Project cleared.")
        self.action_manager.update_actions_for_project_state(False)
        logging.info("Project data and relevant UI cleared.")


    def save_project_dialog(self):
        """Opens a file dialog to save the current project via ProjectDataManager."""
        if hasattr(self.project_data_manager, 'save_project_dialog'):
            self.project_data_manager.save_project_dialog()
        else:
            logging.error("ProjectDataManager does not have save_project_dialog method.")
            QMessageBox.critical(self, "Error", "Save project functionality is not available.")

    def load_project_dialog(self):
        """Opens a file dialog to load a project via ProjectDataManager."""
        # Note: This is different from load_parts_dialog.
        # This should be connected to the "Open Project" action.
        if hasattr(self.project_data_manager, 'load_project_dialog'):
            self.project_data_manager.load_project_dialog()
        else:
            logging.error("ProjectDataManager does not have load_project_dialog method.")
            QMessageBox.critical(self, "Error", "Load project functionality is not available.")

    # --- Slots for EditorTab Signals (Implement these) ---
    @pyqtSlot(str, dict)
    def handle_generate_mechanism_request(self, mechanism_type: str, params: dict):
        logging.info(
            f"MainWindow: Received request to generate mechanism: {mechanism_type} with params {params}"
        )
        target_part_name = params.get("target_part_name")
        if not target_part_name:
            QMessageBox.warning(self, "Mechanism Error", "No target part specified for mechanism generation.")
            return

        current_parts_data = self.project_data_manager.get_current_parts_data()
        if not current_parts_data or target_part_name not in current_parts_data:
            QMessageBox.warning(self, "Mechanism Error", f"Target part '{target_part_name}' not found in project data.")
            return

        target_part_info = current_parts_data[target_part_name]

        # TODO: Get editor scene center or relevant reference point
        # For now, using a default QPointF(0,0) or center of target part bounding box
        editor_scene_ref_point = QPointF(target_part_info.x, target_part_info.y) # Simplistic
        if self.editor_tab and self.editor_tab.editor_view:
            scene_rect = self.editor_tab.editor_view.sceneRect()
            editor_scene_ref_point = scene_rect.center()


        self.mechanism_manager.generate_mechanism(
            mechanism_type=mechanism_type,
            params=params, # These params include selected points like cam_center from EditorTab
            target_part_info=target_part_info,
            all_parts_info=current_parts_data,
            editor_scene_center=editor_scene_ref_point
        )

        self.statusBar().showMessage(
            f"Mechanism generation initiated for {target_part_name}: {mechanism_type}"
        )

    @pyqtSlot()
    def generate_blueprint_impl(self):
        logging.info("MainWindow: Received request to generate blueprint.")
        # Call actual blueprint generation logic here
        # Example: generate_blueprint_svg(self.parts, self.editor_items, "blueprint.svg")
        self.statusBar().showMessage("Blueprint generation requested.")

    @pyqtSlot()
    def save_character_alignment_impl(self):
        logging.info("MainWindow: Received request to save character alignment.")
        # Call actual alignment saving logic here
        self.statusBar().showMessage("Character alignment save requested.")

    # --- Simulation Control Methods (Play/Stop/Reset buttons in EditorTab, signals to these) ---
    # def _start_ik_animation(self): # MODIFIED - Moved to IKManager
    #     if not self.parts or not self.skeleton_data or not self.ik_solver: # MODIFIED
    #         logging.warning("Cannot start animation: No parts, skeleton, or IK solver.") # MODIFIED
    #         # Ensure EditorTab buttons are reset if animation doesn't start # MODIFIED
    #         if hasattr(self.editor_tab, "on_simulation_state_changed"): # MODIFIED
    #             self.editor_tab.on_simulation_state_changed( # MODIFIED
    #                 is_playing=False, can_reset=bool(self.parts) # MODIFIED
    #             ) # MODIFIED
    #         return # MODIFIED
    #     # ... (existing logic for _start_ik_animation) # MODIFIED
    #     if hasattr(self.editor_tab, "on_simulation_state_changed"): # MODIFIED
    #         self.editor_tab.on_simulation_state_changed( # MODIFIED
    #             is_playing=True, can_reset=False # MODIFIED
    #         ) # MODIFIED

    # def _stop_ik_animation(self): # MODIFIED - Moved to IKManager
    #     # ... (existing logic for _stop_ik_animation) # MODIFIED
    #     if hasattr(self.editor_tab, "on_simulation_state_changed"): # MODIFIED
    #         self.editor_tab.on_simulation_state_changed( # MODIFIED
    #             is_playing=False, can_reset=bool(self.parts) # MODIFIED
    #         ) # MODIFIED

    # def _reset_ik_animation_state(self): # MODIFIED - Moved to IKManager
    #     # ... (existing logic for _reset_ik_animation_state) # MODIFIED
    #     if hasattr(self.editor_tab, "on_simulation_state_changed"): # MODIFIED
    #         self.editor_tab.on_simulation_state_changed( # MODIFIED
    #             is_playing=False, can_reset=bool(self.parts) # MODIFIED
    #         ) # MODIFIED

    # --- IK Solver and Animation Step (To be moved to IKManager) --- # MODIFIED
    # def _run_ik_animation_step(self): # MODIFIED - Moved to IKManager
        # This entire method's logic needs to be transferred to IKManager._run_ik_animation_step
        # logging.debug("MainWindow: _run_ik_animation_step")
        # ... (complex logic involving part paths, IK solving, updating visuals) ...
    #     pass # MODIFIED

    # def _solve_single_bone_ik(self, joint_id: str, target_pos: QPointF) -> Optional[QPointF]: # MODIFIED - Moved to IKManager (Placeholder exists)
        # Logic to be transferred
    #     pass # MODIFIED

    # def _solve_two_bone_ik(self, upper_limb_id: str, lower_limb_id: str, target_pos: QPointF) -> Optional[Tuple[QPointF, QPointF]]: # MODIFIED - Moved to IKManager (Placeholder exists)
        # Logic to be transferred
    #     pass # MODIFIED

    # def _update_character_part_visuals_from_ik(self): # MODIFIED - Moved to IKManager (Placeholder exists, emits signal)
        # Logic to be transferred (or rather, ensure IKManager emits necessary data via its signal)
    #     pass # MODIFIED

    # Method for reset_all_animations_btn in EditorTab (if EditorTab calls it directly)
    def _reset_all_animations_button_clicked(self):
        logging.info("MainWindow: Resetting all animation paths and poses.")

        # Delegate clearing of motion path data from PartInfo objects to ProjectDataManager
        if hasattr(self.project_data_manager, 'clear_all_motion_paths'):
            self.project_data_manager.clear_all_motion_paths()
        else:
            logging.warning("ProjectDataManager does not have clear_all_motion_paths method.")
            # Fallback to old direct manipulation if method doesn't exist (for safety during refactor)
            current_parts_data = self.project_data_manager.get_current_parts_data()
            if current_parts_data:
                for part_info in current_parts_data.values():
                    if hasattr(part_info, 'motion_path_data'):
                        part_info.motion_path_data = None
                    if hasattr(part_info, 'motion_path'):
                        part_info.motion_path = []
            else:
                logging.warning("Cannot clear motion path data: No parts data loaded.")

        # Instruct EditorTab to clear its visual motion paths
        if self.editor_tab and hasattr(self.editor_tab, 'clear_all_visual_motion_paths'):
            self.editor_tab.clear_all_visual_motion_paths()
        else:
            logging.warning("EditorTab or its clear_all_visual_motion_paths method not found.")

        # Reset character pose to initial skeleton definition via IKManager
        self.ik_manager.reset_animation_state()  # This should reset poses to initial

        # Update EditorTab's view and button states
        if self.editor_tab:
            if hasattr(self.editor_tab, 'editor_view') and hasattr(self.editor_tab.editor_view, 'update_view'):
                self.editor_tab.editor_view.update_view()
            if hasattr(self.editor_tab, '_update_button_states'):
                self.editor_tab._update_button_states()

        self.statusBar().showMessage("All animation paths and character poses reset.")

    def _connect_global_signals(self):
        """Connects global signals like tab changes or theme changes."""
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Connect SkeletonManager signals
        self.skeleton_manager.skeleton_updated.connect(self._on_skeleton_manager_updated)
        self.skeleton_manager.skeleton_data_cleared.connect(self.ik_manager.clear_ik_data) # Also clear IK if skeleton cleared

        # Connect IKManager signals
        self.ik_manager.character_visuals_updated.connect(self._handle_ik_visuals_update)
        if hasattr(self, 'editor_tab') and self.editor_tab and hasattr(self.ik_manager, 'animation_state_changed'):
             self.ik_manager.animation_state_changed.connect(self.editor_tab.on_simulation_state_changed)

        # OptionsTab signals
        if hasattr(self, 'options_tab') and self.options_tab:
            self.options_tab.themeChanged.connect(self._apply_theme)
            # Connect animation duration change from OptionsTab to IKManager
            self.options_tab.animationDurationChanged.connect(self.ik_manager.set_animation_duration)
            # Initialize OptionsTab with current animation duration from IKManager
            self.options_tab.set_animation_duration_input(self.ik_manager.animation_duration / 1000.0)
            # Connect advanced processing visibility toggle
            if hasattr(self.options_tab, 'advancedProcessingVisibilityChanged') and hasattr(self.image_proc_tab, '_toggle_detailed_processing_visibility'):
                self.options_tab.advancedProcessingVisibilityChanged.connect(self.image_proc_tab._toggle_detailed_processing_visibility)

        # EditorTab signals
        if hasattr(self, 'editor_tab') and self.editor_tab:
            self.editor_tab.request_generate_mechanism.connect(self.handle_generate_mechanism_request)
            # self.editor_tab.request_save_alignment.connect(self.save_character_alignment_impl) # connect if this is the final handler
            # self.editor_tab.request_play_simulation.connect(self.ik_manager.start_animation) # connect to ik_manager
            # self.editor_tab.request_stop_simulation.connect(self.ik_manager.stop_animation)   # connect to ik_manager
            # self.editor_tab.request_reset_simulation.connect(self.ik_manager.reset_simulation) # connect to ik_manager
            # self.editor_tab.request_generate_blueprint.connect(self.generate_blueprint_impl) # connect if this is the final handler

            # More robust connections to IKManager, checking method existence
            if hasattr(self.ik_manager, 'start_animation'):
                self.editor_tab.request_play_simulation.connect(self.ik_manager.start_animation)
            if hasattr(self.ik_manager, 'stop_animation'):
                self.editor_tab.request_stop_simulation.connect(self.ik_manager.stop_animation)
            if hasattr(self.ik_manager, 'reset_animation_state'): # Ensure this method name is correct in IKManager
                self.editor_tab.request_reset_simulation.connect(self.ik_manager.reset_animation_state)

            # If save_character_alignment_impl is the final destination for the signal from EditorTab
            if hasattr(self, 'save_character_alignment_impl'):
                 self.editor_tab.request_save_alignment.connect(self.save_character_alignment_impl)

            # If generate_blueprint_impl is the final destination
            if hasattr(self, 'generate_blueprint_impl'):
                self.editor_tab.request_generate_blueprint.connect(self.generate_blueprint_impl)

            # Connect the new request_reset_all_animations signal
            if hasattr(self.editor_tab, 'request_reset_all_animations') and hasattr(self, '_reset_all_animations_button_clicked'):
                self.editor_tab.request_reset_all_animations.connect(self._reset_all_animations_button_clicked)

        # MechanismManager connections
        if hasattr(self, 'mechanism_manager') and hasattr(self.mechanism_manager, 'mechanism_visuals_ready'):
            # The slot self.editor_tab.handle_mechanism_visuals will be created in EditorTab
            if hasattr(self, 'editor_tab') and hasattr(self.editor_tab, 'handle_mechanism_visuals'):
                if not self._is_signal_connected(self.mechanism_manager.mechanism_visuals_ready, self.editor_tab.handle_mechanism_visuals):
                    self.mechanism_manager.mechanism_visuals_ready.connect(self.editor_tab.handle_mechanism_visuals)
            else:
                logging.warning("EditorTab or handle_mechanism_visuals slot not found for MechanismManager signal.")
        else:
            logging.warning("MechanismManager or its mechanism_visuals_ready signal not found.")

    def _connect_manager_signals(self):
        """Connect signals from various managers like ProjectDataManager."""
        # Ensure ProjectDataManager exists and has the signal
        if hasattr(self.project_data_manager, 'project_data_loaded_signal'): # Assuming signal name is project_data_loaded_signal
            self.project_data_manager.project_data_loaded_signal.connect(self._handle_project_data_loaded)
        elif hasattr(self.project_data_manager, 'project_data_loaded'): # Common naming convention
            self.project_data_manager.project_data_loaded.connect(self._handle_project_data_loaded)
        else:
            logging.warning("ProjectDataManager does not have a 'project_data_loaded' or 'project_data_loaded_signal' signal to connect.")

        if hasattr(self.project_data_manager, 'project_data_cleared_signal'): # Assuming signal name
            self.project_data_manager.project_data_cleared_signal.connect(self._handle_project_data_cleared)
        elif hasattr(self.project_data_manager, 'project_data_cleared'):
             self.project_data_manager.project_data_cleared.connect(self._handle_project_data_cleared)
        else:
            logging.warning("ProjectDataManager does not have a 'project_data_cleared' or 'project_data_cleared_signal' signal to connect.")

        if hasattr(self.project_data_manager, 'error_occurred_signal'): # Assuming signal name
            self.project_data_manager.error_occurred_signal.connect(self._handle_project_manager_error)
        elif hasattr(self.project_data_manager, 'error_occurred'):
            self.project_data_manager.error_occurred.connect(self._handle_project_manager_error)
        else:
            logging.warning("ProjectDataManager does not have an 'error_occurred' or 'error_occurred_signal' signal to connect.")

        # SkeletonManager connections (already in _connect_global_signals, ensure no duplication)
        if hasattr(self.skeleton_manager, 'skeleton_updated') and not self._is_signal_connected(self.skeleton_manager.skeleton_updated, self._on_skeleton_manager_updated):
            self.skeleton_manager.skeleton_updated.connect(self._on_skeleton_manager_updated)
        if hasattr(self.skeleton_manager, 'skeleton_data_cleared') and not self._is_signal_connected(self.skeleton_manager.skeleton_data_cleared, self.ik_manager.clear_ik_data):
             self.skeleton_manager.skeleton_data_cleared.connect(self.ik_manager.clear_ik_data)

        # IKManager connections (already in _connect_global_signals, ensure no duplication)
        if hasattr(self.ik_manager, 'character_visuals_updated') and not self._is_signal_connected(self.ik_manager.character_visuals_updated, self._handle_ik_visuals_update):
            self.ik_manager.character_visuals_updated.connect(self._handle_ik_visuals_update)

    def _is_signal_connected(self, signal, slot) -> bool:
        # Helper to check if a signal is connected to a specific slot
        # This is a basic check and might not be foolproof for all cases (e.g., lambdas, functools.partial)
        # For more robust checking, you might need to inspect receiver objects and names.
        # Qt doesn't provide a straightforward public API to list all connections easily.
        try:
            # This is a simplified check, real check is more complex.
            # For now, assume we need to ensure connections are made once.
            # A common pattern is to disconnect all first, then connect, to avoid duplicates.
            # However, for this refactoring, we focus on making the connections.
            # In a real scenario, one might track connections or use a more robust check.
            return False # Placeholder, assume not connected to allow connection
        except Exception:
            return False

    @pyqtSlot(dict)
    def _on_skeleton_manager_updated(self, standardized_skeleton_data: dict):
        """Slot called when SkeletonManager has new processed skeleton data."""
        logging.info("MainWindow: SkeletonManager updated. Notifying tabs. IKManager will handle its own re-initialization.")

        # Notify tabs that might need the direct standardized skeleton data
        if hasattr(self.image_proc_tab, 'on_skeleton_updated_externally'):
            self.image_proc_tab.on_skeleton_updated_externally(standardized_skeleton_data)

        if hasattr(self.editor_tab, 'on_skeleton_updated'):
            self.editor_tab.on_skeleton_updated(standardized_skeleton_data)

        # MODIFIED: Pass the received dictionary to the status bar update method
        self.update_status_bar_with_skeleton_info(standardized_skeleton_data)

    # MODIFIED: Method now accepts the skeleton data dictionary
    def update_status_bar_with_skeleton_info(self, skeleton_data_dict: Optional[dict]):
        if skeleton_data_dict and skeleton_data_dict.get('joints'):
            num_joints = len(skeleton_data_dict.get('joints', {}))
            self.statusBar().showMessage(f"Skeleton loaded/updated: {num_joints} joints.", 3000)
        else:
            self.statusBar().showMessage(f"Skeleton cleared or not loaded.", 3000)

    # --- New Slot for IKManager Signals ---
    @pyqtSlot(dict)
    def _handle_ik_visuals_update(self, part_transforms: dict):
        """Handles the character_visuals_updated signal from IKManager."""
        logging.debug(f"MainWindow: Received ik_visuals_update: {part_transforms}")
        if self.editor_tab and hasattr(self.editor_tab.editor_view, 'update_part_visuals_from_ik'):
            self.editor_tab.editor_view.update_part_visuals_from_ik(part_transforms)
        else:
            logging.warning("MainWindow: EditorView not available or does not have update_part_visuals_from_ik method.")

    def _connect_global_actions(self):
        """Connects QActions to their respective handler methods."""
        # File actions
        self.action_manager.connect_action("new_project", self.project_data_manager.new_project)
        self.action_manager.connect_action("open_project", self.project_data_manager.load_project_dialog)
        self.action_manager.connect_action("save_project", self.project_data_manager.save_project_dialog)
        self.action_manager.connect_action("save_project_as", self.project_data_manager.save_project_as_dialog)
        self.action_manager.connect_action("exit_app", self.close)

        # Edit actions (Note: undo/redo are now connected to EditorTab's methods)
        self.action_manager.connect_action(
            "undo",
            lambda: self.editor_tab.undo() # Call on EditorTab
            if self.tab_widget.currentWidget() == self.editor_tab and hasattr(self.editor_tab, 'undo')
            else None,
        )
        self.action_manager.connect_action(
            "redo",
            lambda: self.editor_tab.redo() # Call on EditorTab
            if self.tab_widget.currentWidget() == self.editor_tab and hasattr(self.editor_tab, 'redo')
            else None,
        )

        # View actions (connected to EditorTab's methods or MainWindow for general view changes)
        self.action_manager.connect_action(
            "zoom_in",
            lambda: self.editor_tab.zoom_in() # Call on EditorTab
            if self.tab_widget.currentWidget() == self.editor_tab and hasattr(self.editor_tab, 'zoom_in')
            else None,
        )
        self.action_manager.connect_action(
            "zoom_out",
            lambda: self.editor_tab.zoom_out() # Call on EditorTab
            if self.tab_widget.currentWidget() == self.editor_tab and hasattr(self.editor_tab, 'zoom_out')
            else None,
        )
        self.action_manager.connect_action(
            "zoom_fit",
            lambda: self.editor_tab.zoom_to_fit() # Call on EditorTab
            if self.tab_widget.currentWidget() == self.editor_tab and hasattr(self.editor_tab, 'zoom_to_fit')
            else None,
        )
        self.action_manager.connect_action(
            "reset_view",
            lambda: self.editor_tab.reset_view() # Call on EditorTab
            if self.tab_widget.currentWidget() == self.editor_tab and hasattr(self.editor_tab, 'reset_view')
            else None
        )
        # Toggle Toolbar (This is a MainWindow view change)
        self.action_manager.connect_action("toggle_toolbar", self.toggle_main_toolbar_visibility)
        # Toggle Statusbar (This is a MainWindow view change)
        # Assuming statusbar can be hidden/shown. If not, this action might do something else.
        # self.action_manager.connect_action("toggle_statusbar", self.toggle_statusbar_visibility)

        # Tools / Simulation actions
        # These might be connected to IKManager or EditorTab depending on responsibility
        self.action_manager.connect_action(
            "play_simulation",
            lambda: self.ik_manager.start_animation()
            if hasattr(self.ik_manager, 'start_animation')
            else None
        )
        self.action_manager.connect_action(
            "stop_simulation",
            lambda: self.ik_manager.stop_animation()
            if hasattr(self.ik_manager, 'stop_animation')
            else None
        )
        self.action_manager.connect_action(
            "reset_simulation",
            lambda: self.ik_manager.reset_animation_state() # Or reset_animation_state depending on IKManager API
            if hasattr(self.ik_manager, 'reset_animation_state')
            else None
        )

        # Help actions
        self.action_manager.connect_action("about", self.show_about_dialog) # Changed to show_about_dialog
        self.action_manager.connect_action("about_qt", self.show_about_qt_dialog) # Changed to show_about_qt_dialog

        # Connect toggle part properties action
        self.action_manager.connect_action(
            "toggle_part_props",
            self._toggle_part_properties_visibility # Connect to MainWindow method
        )

    def _handle_option_change(self, setting_name: str, value: Any):
        """Handles generic setting changes from the OptionsTab."""
        logging.info(f"Option changed: {setting_name} = {value}")
        # Add logic here to handle specific settings if needed,
        # though most are directly connected to their respective handlers.
        # This slot can be used for logging or for settings that don't have direct handlers.
        if setting_name == "theme":
            self._apply_theme(str(value)) # Already connected, but shows example
        elif setting_name == "animation_duration":
            self.ik_manager.set_animation_duration(int(float(value) * 1000)) # Convert seconds to ms
        elif setting_name == "toolbar_visibility":
            self._toggle_toolbar_visibility(bool(value))
        elif setting_name == "part_properties_visibility":
            self._toggle_part_properties_visibility(bool(value))
        elif setting_name == "debug_mode":
            # Assuming ImageProcessingTab has a method to set debug mode
            if hasattr(self.image_proc_tab, 'set_debug_mode'):
                self.image_proc_tab.set_debug_mode(bool(value))
            else:
                logging.warning("ImageProcessingTab does not have set_debug_mode method.")
        else:
            logging.warning(f"Unhandled option change: {setting_name}")

    def show_about_dialog(self):
        """Displays the 'About' dialog."""
        QMessageBox.about(self, "About Automata Designer",
                        "<p><b>Automata Designer</b></p>"
                        "<p>Version 0.1.0</p>"
                        "<p>Copyright &copy; 2024 Alan Synn</p>"
                        "<p>This application helps design and simulate automata mechanisms.</p>")

    def show_about_qt_dialog(self):
        """Displays the 'About Qt' dialog."""
        QMessageBox.aboutQt(self, "About Qt")

    def _handle_project_manager_error(self, error_message: str):
        """Handles error signals from the ProjectDataManager."""
        logging.error(f"ProjectDataManager error: {error_message}")
        QMessageBox.critical(self, "Project Error", f"An error occurred: {error_message}")
