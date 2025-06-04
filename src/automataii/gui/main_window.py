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
    QPixmap,
    QTransform
)
from PyQt6.QtCore import (
    Qt,
    QPointF,
    QTimer,
    pyqtSlot,
    QRectF,
)
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# Local imports (adjust paths as needed)
from .image_view import ImageProcessingView
from .graphics_items.part_item import CharacterPartItem
from ..utils.styling import LIGHT_STYLE, DARK_STYLE, UIColors

from ..core.models import PartInfo # ProjectFileModel is in models_pydantic
from ..core.models_pydantic import ProjectFileModel # Added ProjectFileModel from correct location

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

# from qframelesswindow import FramelessMainWindow

TARGET_CONTROL_POINTS = 8


class AutomataDesigner(QMainWindow):
    """Main application window for the Automata Designer.

    Integrates image processing, skeleton editing, part assembly, motion definition,
    simulation, and blueprint generation.
    """

    def __init__(self, parent: Optional[QWidget] = None, debug_mode: bool = False):
        # print("Executing AutomataDesigner.__init__ from src/automataii/gui/main_window.py - THIS IS A VERY LOUD DEBUG PRINT!", flush=True) # REMOVED
        super().__init__(parent)
        # Force logging re-configuration here to ensure our prints are visible
        # logging.basicConfig(level=logging.DEBUG,
        #                     format='%(asctime)s - %(levelname)s - [%(name)s:%(module)s:%(lineno)d] %(message)s',
        #                     force=True) # REMOVED
        self.debug_mode = debug_mode
        # Use standard logging, assuming setup_logging in __main__ handles it.
        logging.info(f"Initializing AutomataDesigner... Debug mode: {self.debug_mode}")
        self.setWindowTitle("Automata Designer")
        # self.titleBar.raise_()
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

        # AFTER ALL MANAGERS AND UI ARE CREATED AND CONNECTED
        if self.skeleton_manager and self.ik_manager:
            logging.info(f"AutomataDesigner.__init__ (END): Linking SkeletonManager (id:{id(self.skeleton_manager)}) to IKManager (id:{id(self.ik_manager)}).")
            self.ik_manager.set_skeleton_manager(self.skeleton_manager)
            ik_sm_ref = self.ik_manager.skeleton_manager_ref
            logging.info(f"AutomataDesigner.__init__ (END): IKManager's skeleton_manager_ref is now id:{id(ik_sm_ref) if ik_sm_ref else 'None'}. Type: {type(ik_sm_ref)}")
            if ik_sm_ref is None:
                 logging.error("AutomataDesigner.__init__ (END): CRITICAL - IKManager.skeleton_manager_ref is None immediately after setting!")
            elif ik_sm_ref != self.skeleton_manager:
                 logging.error(f"AutomataDesigner.__init__ (END): CRITICAL - IKManager.skeleton_manager_ref (id:{id(ik_sm_ref)}) MISMATCHES self.skeleton_manager (id:{id(self.skeleton_manager)})!")
        else:
            logging.error("AutomataDesigner.__init__ (END): Critical error - SkeletonManager or IKManager not initialized before linking.")

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
        # Connect unit changed signal (assuming OptionsTab will have it)
        if hasattr(self.options_tab, 'unitChanged'):
            self.options_tab.unitChanged.connect(self._handle_unit_changed)
        else:
            logging.warning("MainWindow: OptionsTab does not have unitChanged signal. Unit selection may not work.")

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
    @pyqtSlot(dict, str)
    def handle_parts_generated_from_tab(self, annotation_results: dict, final_bpe_char_dir_str: str):
        """Handles the parts_generated signal from ImageProcessingTab."""
        logging.info(f"MainWindow: Received parts_generated. Annotation results output_dir: {annotation_results.get('output_dir')}, Final BPE dir: {final_bpe_char_dir_str}")

        parts_info_json_path = Path(final_bpe_char_dir_str) / "parts_info.json"
        source_char_cfg_path_str = annotation_results.get('char_cfg_path')

        if not source_char_cfg_path_str:
            logging.error("handle_parts_generated_from_tab: 'char_cfg_path' not found in annotation_results.")
            QMessageBox.critical(self, "Error", "char_cfg.yaml path not found in annotation data.")
            return

        source_char_cfg_path = Path(source_char_cfg_path_str)
        dest_char_cfg_path = Path(final_bpe_char_dir_str) / "char_cfg.yaml"

        if source_char_cfg_path.exists():
            try:
                import shutil
                shutil.copy2(source_char_cfg_path, dest_char_cfg_path)
                logging.info(f"Copied {source_char_cfg_path} to {dest_char_cfg_path} for ProjectDataManager.")

                # texture.png is no longer copied as it's not used as an atlas.
                # Individual part PNGs/SVGs are expected in final_bpe_char_dir_str.

                source_mask_path_str = annotation_results.get('mask_path')
                if source_mask_path_str:
                    source_mask_path = Path(source_mask_path_str)
                    dest_mask_path = Path(final_bpe_char_dir_str) / "mask.png"
                    if source_mask_path.exists():
                        shutil.copy2(source_mask_path, dest_mask_path)
                        logging.info(f"Copied {source_mask_path} to {dest_mask_path}.")
                    else:
                        logging.warning(f"Source mask.png not found at {source_mask_path}, cannot copy.")
                else:
                    logging.warning("'mask_path' not in annotation_results, cannot copy mask.png.")

            except Exception as e:
                logging.error(f"Failed to copy files to BPE output dir: {e}", exc_info=True)
                QMessageBox.warning(self, "File Copy Error", f"Could not copy necessary files for project loading: {e}")
        else:
            logging.warning(f"Source char_cfg.yaml not found at {source_char_cfg_path}, cannot copy to BPE output dir. ProjectDataManager might fail to load skeleton.")

        if not parts_info_json_path.exists():
             logging.error(f"CRITICAL ERROR IN MAINWINDOW: parts_info.json path derived as {parts_info_json_path} but file does not exist.")
             QMessageBox.critical(self, "Project Load Error", f"Internal error: Could not locate parts_info.json at {parts_info_json_path}.")
             return

        logging.info(f"Attempting to load project data from parts_info.json: {parts_info_json_path}")
        success = self.project_data_manager.load_project_from_file(str(parts_info_json_path))

        if success:
            self.statusBar().showMessage("Part data loaded successfully.", 3000)
            self.current_temp_char_dir = Path(final_bpe_char_dir_str)
            logging.info(f"MainWindow: Project loaded. Updated current_temp_char_dir to BPE output: {self.current_temp_char_dir}")

            # NEW: Capture visual state from ImageProcessingTab and set it as IK initial pose
            if hasattr(self.image_proc_tab, 'get_current_parts_visual_state'):
                visual_state = self.image_proc_tab.get_current_parts_visual_state()
                if visual_state:
                    logging.info(f"MainWindow: Captured visual state from ImageProcessingTab for {len(visual_state)} parts. Setting as IK initial pose.")
                    if self.ik_manager:
                        self.ik_manager.set_initial_pose_from_visual_data(visual_state)
                    else:
                        logging.error("MainWindow: IKManager not available to set initial pose.")
                else:
                    logging.warning("MainWindow: ImageProcessingTab returned no visual state to set for IK.")
            else:
                logging.warning("MainWindow: ImageProcessingTab does not have get_current_parts_visual_state method.")

        else:
            self.statusBar().showMessage("Failed to load part data. Check logs.", 5000)

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
    ):
        """Handles the project_data_loaded signal from ProjectDataManager."""
        if success:
            logging.info(
                f"MainWindow: Project data loaded successfully from {project_directory_path}"
            )
            self.project_dir = Path(project_directory_path) # Update project_dir in MainWindow, ensure it's Path

            # Texture atlas is no longer loaded here; CharacterPartItem handles individual textures.
            # logging.debug("MainWindow: Texture atlas loading skipped as parts load their own.")

            # Pass PartInfo data to EditorTab. It no longer needs texture_atlas_pixmap.
            self.editor_tab.set_parts_data(parts_info)

            # Update other tabs/managers as needed
            if hasattr(self.ik_manager, 'set_project_parts_data'):
                self.ik_manager.set_project_parts_data(parts_info)

            current_skeleton_data = self.project_data_manager.raw_skeleton_data
            if current_skeleton_data:
                self.skeleton_manager.load_skeleton_from_project_data(current_skeleton_data, parts_info)
            else:
                self.skeleton_manager.clear_data()

            self.image_proc_tab.on_parts_loaded_in_editor(True)

            self.setWindowTitle(f"Automata Designer - {Path(project_directory_path).name}")
            self.statusBar().showMessage(f"Project loaded: {project_directory_path}")
            self.action_manager.update_actions_for_project_state(True)

            if parts_info:
                logging.info(f"MainWindow: Project and parts data ({len(parts_info)} parts) loaded. Switching to editor tab if needed.")
                if self.tab_widget.currentWidget() != self.editor_tab:
                    self.switch_to_editor_tab()
            else:
                logging.info("MainWindow: Project loaded, but no specific parts data found in parts_info dict.")

        else:
            logging.error(f"MainWindow: Project loading failed from {project_directory_path}")
            self._clear_ui_for_failed_load()
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
        self.editor_tab.clear_editor_content()
        self.skeleton_manager.clear_data() # This will emit skeleton_updated with None
        if self.ik_manager:
            self.ik_manager.reset_all_ik_systems_and_data() # Use the new method name
        self.action_manager.update_actions_for_project_state(False)
        self.statusBar().showMessage("Project data cleared.")
        # Any other UI elements that need to be reset when project is cleared

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
            # Connect unit changed signal (assuming OptionsTab will have it)
            if hasattr(self.options_tab, 'unitChanged'):
                self.options_tab.unitChanged.connect(self._handle_unit_changed)
            else:
                logging.warning("MainWindow: OptionsTab does not have unitChanged signal. Unit selection may not work.")

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

            # Connect EditorTab.motion_path_updated to MainWindow handler
            if hasattr(self.editor_tab, 'motion_path_updated') and hasattr(self, '_handle_part_motion_path_update_from_editor_tab'):
                if not self._is_signal_connected(self.editor_tab.motion_path_updated, self._handle_part_motion_path_update_from_editor_tab):
                    self.editor_tab.motion_path_updated.connect(self._handle_part_motion_path_update_from_editor_tab)

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
        """Connect signals from various managers to MainWindow slots or other manager slots."""
        logging.debug("MainWindow: Connecting manager signals...")

        # ProjectDataManager signals
        if self.project_data_manager:
            try: self.project_data_manager.project_data_loaded.disconnect(self._handle_project_data_loaded)
            except TypeError: pass
            self.project_data_manager.project_data_loaded.connect(self._handle_project_data_loaded)

            try: self.project_data_manager.project_data_cleared.disconnect(self._handle_project_data_cleared)
            except TypeError: pass
            self.project_data_manager.project_data_cleared.connect(self._handle_project_data_cleared)

            try: self.project_data_manager.error_occurred.disconnect(self._handle_project_manager_error)
            except TypeError: pass
            self.project_data_manager.error_occurred.connect(self._handle_project_manager_error)

        # SkeletonManager signals
        if self.skeleton_manager:
            # Connect to a slot in MainWindow that might update UI or pass to other relevant managers
            try: self.skeleton_manager.skeleton_updated.disconnect(self._on_skeleton_manager_updated)
            except TypeError: pass
            self.skeleton_manager.skeleton_updated.connect(self._on_skeleton_manager_updated)

            # If IKManager needs direct skeleton updates from SkeletonManager
            if self.ik_manager:
                try: self.skeleton_manager.skeleton_updated.disconnect(self.ik_manager.on_skeleton_data_updated_from_manager)
                except TypeError: pass # Allow it to fail if not connected
                self.skeleton_manager.skeleton_updated.connect(self.ik_manager.on_skeleton_data_updated_from_manager)
                logging.info("MainWindow: Connected SkeletonManager.skeleton_updated to IKManager.on_skeleton_data_updated_from_manager")

        # IKManager signals
        if self.ik_manager:
            # Connect IK visuals update to a handler in MainWindow (or directly to EditorTab if appropriate)
            try: self.ik_manager.character_visuals_updated.disconnect(self._handle_ik_visuals_update)
            except TypeError: pass
            self.ik_manager.character_visuals_updated.connect(self._handle_ik_visuals_update)
            logging.info("MainWindow: Connected IKManager.character_visuals_updated to self._handle_ik_visuals_update")

            # Connect IK animation state to EditorTab's handler
            if hasattr(self, 'editor_tab') and self.editor_tab and hasattr(self.ik_manager, 'animation_state_changed'):
                try: self.ik_manager.animation_state_changed.disconnect(self.editor_tab.on_simulation_state_changed)
                except TypeError: pass
                self.ik_manager.animation_state_changed.connect(self.editor_tab.on_simulation_state_changed)
                logging.info("MainWindow: Connected IKManager.animation_state_changed to EditorTab.on_simulation_state_changed")

            # NEW: Connect skeleton_pose_updated from IKManager to a new handler in MainWindow
            if hasattr(self.ik_manager, 'skeleton_pose_updated'):
                try: self.ik_manager.skeleton_pose_updated.disconnect(self._handle_skeleton_pose_updated_from_ik)
                except TypeError: pass
                self.ik_manager.skeleton_pose_updated.connect(self._handle_skeleton_pose_updated_from_ik)
                logging.info("MainWindow: Connected IKManager.skeleton_pose_updated to self._handle_skeleton_pose_updated_from_ik")

        # ... any other manager signal connections ...

        logging.debug("MainWindow: Finished connecting manager signals.")

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
    def _handle_ik_visuals_update(self, part_transforms: Dict[str, Dict[str, Any]]):
        """Handles updates to part visuals from the IKManager.
           Transforms part-centric data to joint-centric for EditorView.
        """
        logging.debug(f"MainWindow._handle_ik_visuals_update: Received part_transforms: {part_transforms}")

        if not (self.editor_tab and self.editor_tab.editor_view and \
                  self.project_data_manager and self.project_data_manager.parts):
            logging.warning("MainWindow: Cannot handle IK visuals update. EditorTab, EditorView, or ProjectDataManager (with parts) is not available.")
            return

        if not part_transforms:
            logging.debug("MainWindow: Received empty part_transforms. No visual update needed.")
            return

        joint_centric_data: Dict[str, Dict[str, Any]] = {}
        for part_name, transform_data in part_transforms.items():
            part_info = self.project_data_manager.parts.get(part_name)

            if not part_info:
                logging.warning(f"MainWindow: PartInfo for '{part_name}' not found in ProjectDataManager. Skipping this part for IK update.")
                continue

            anchor_joint_id = part_info.anchor_joint_id
            if not anchor_joint_id:
                continue

            # ASSUMPTION: transform_data.get('position') IS the target scene_position for the anchor_joint_id.
            anchor_joint_target_pos_list = transform_data.get('position')  # Expected: List[float, float]
            part_target_rotation_degrees = transform_data.get('rotation_degrees')

            if anchor_joint_target_pos_list and isinstance(anchor_joint_target_pos_list, (list, tuple)) and len(anchor_joint_target_pos_list) == 2 and part_target_rotation_degrees is not None:
                try:
                    anchor_joint_target_scene_pos = QPointF(float(anchor_joint_target_pos_list[0]), float(anchor_joint_target_pos_list[1]))
                    part_target_rotation = float(part_target_rotation_degrees)

                    joint_centric_data[anchor_joint_id] = {
                        'scene_position': anchor_joint_target_scene_pos, # Directly use the position from IKManager
                        'world_rotation_degrees': part_target_rotation
                    }
                except (TypeError, ValueError) as e:
                    logging.warning(f"MainWindow: Error converting data for part '{part_name}' (joint '{anchor_joint_id}'): {e}. Data: P={anchor_joint_target_pos_list}, R={part_target_rotation_degrees}")
            else:
                logging.warning(f"MainWindow: Invalid or missing position/rotation for part '{part_name}' (joint '{anchor_joint_id}'). Data: P={anchor_joint_target_pos_list}, R={part_target_rotation_degrees}")

        if joint_centric_data:
            self.editor_tab.editor_view.update_visuals_from_animation_data(joint_centric_data)
        else:
            logging.info("MainWindow: No valid joint-centric data generated from part_transforms to update visuals.")

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
        elif setting_name == "unit_system": # Assuming this will be the setting_name from OptionsTab
            self._handle_unit_changed(str(value))
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

    @pyqtSlot(str)
    def _handle_unit_changed(self, unit: str):
        """Handles the unit system change from OptionsTab."""
        logging.info(f"MainWindow: Unit system changed to: {unit}")
        # Pass the new unit to EditorView
        if hasattr(self.editor_tab, 'editor_view') and hasattr(self.editor_tab.editor_view, 'set_display_unit'):
            self.editor_tab.editor_view.set_display_unit(unit)
        else:
            logging.warning("MainWindow: EditorView or its set_display_unit method not found.")

        # Pass the new unit to ImageProcessingView (via ImageProcessingTab)
        if hasattr(self.image_proc_tab, 'image_proc_view') and hasattr(self.image_proc_tab.image_proc_view, 'set_display_unit'):
            self.image_proc_tab.image_proc_view.set_display_unit(unit)
        else:
            logging.warning("MainWindow: ImageProcessingView or its set_display_unit method not found.")

        self.statusBar().showMessage(f"Display unit set to {unit}", 3000)

    def _handle_project_manager_error(self, error_message: str):
        """Handles error signals from the ProjectDataManager."""
        logging.error(f"ProjectDataManager error: {error_message}")
        QMessageBox.critical(self, "Project Error", f"An error occurred: {error_message}")

    def _load_project_into_editor_tab(self, project_file_model: ProjectFileModel):
        """Loads parts and skeleton data into the EditorTab's view."""
        logging.debug(f"MainWindow:_load_project_into_editor_tab - Attempting to load project: {project_file_model.project_name if project_file_model else 'None'}")
        if not self.editor_tab:
            logging.error("EditorTab not initialized. Cannot load project data.")
            return

        if not project_file_model or not project_file_model.character:
            logging.error("Invalid project_file_model or character data provided to _load_project_into_editor_tab.")
            self.editor_tab.clear_editor_content() # Clear tab if data is bad
            return

        parts_data = project_file_model.character.parts
        skeleton_data_pydantic_list = project_file_model.character.skeleton_joints # This is List[PydanticSkeletonJointModel]
        character_name = project_file_model.character.name
        hierarchy_dict = project_file_model.character.hierarchy_dict # This should be {parent_std_id: [child_std_id, ...]}

        # Convert Pydantic SkeletonJointModel list to the List[Dict[str, Any]] expected by visualize_skeleton
        skeleton_for_view = []
        if skeleton_data_pydantic_list:
            for pydantic_joint in skeleton_data_pydantic_list:
                joint_dict = {
                    'id': pydantic_joint.id, # Standardized ID
                    'name': pydantic_joint.name, # Original name/label from source
                    'position': QPointF(pydantic_joint.position[0], pydantic_joint.position[1]),
                    'parent': pydantic_joint.parent_id, # Standardized parent ID
                    'color': pydantic_joint.color,
                    'label': pydantic_joint.label # Original name from char_cfg for this joint
                }
                skeleton_for_view.append(joint_dict)

        logging.debug(f"MainWindow:_load_project_into_editor_tab - Prepared skeleton_for_view (count: {len(skeleton_for_view)}): {skeleton_for_view}")
        logging.debug(f"MainWindow:_load_project_into_editor_tab - Prepared hierarchy_dict (keys: {list(hierarchy_dict.keys()) if hierarchy_dict else 'None'}): {hierarchy_dict}")

        # Clear previous content and load new parts
        self.editor_tab.clear_editor_content()
        self.editor_tab.set_parts_data(parts_data)

        # Call visualize_skeleton on the EditorTab's EditorView instance
        if self.editor_tab.editor_view and skeleton_for_view:
            logging.debug(f"MainWindow: Calling editor_view.visualize_skeleton with {len(skeleton_for_view)} joints.")
            self.editor_tab.editor_view.visualize_skeleton(skeleton_for_view)
        elif self.editor_tab.editor_view:
            logging.debug("MainWindow: No skeleton data in project, clearing skeleton visualization.")
            self.editor_tab.editor_view.visualize_skeleton([]) # Clear if no skeleton

        # Ensure the view is updated and potentially fits content
        self.editor_tab.editor_view.scene().update() # Update scene
        # Consider calling fit_view or reset_view if appropriate after loading
        # self.editor_tab.editor_view.zoom_to_fit() # Example

        logging.info(f"MainWindow: Finished _load_project_into_editor_tab for {character_name}")

    @pyqtSlot(str, QPainterPath)
    def _handle_part_motion_path_update_from_editor_tab(self, part_name: str, motion_qpath: QPainterPath):
        """Handles the motion_path_updated signal from EditorTab and passes it to IKManager."""
        if not self.ik_manager:
            logging.warning("MainWindow: IKManager not available to handle motion path update.")
            return
        if hasattr(self.ik_manager, 'update_part_motion_path'):
            self.ik_manager.update_part_motion_path(part_name, motion_qpath)
            logging.info(f"MainWindow: Relayed motion path update for '{part_name}' to IKManager.")
        else:
            logging.warning("MainWindow: IKManager does not have 'update_part_motion_path' method.")

    @pyqtSlot(dict)
    def _handle_skeleton_pose_updated_from_ik(self, animated_pose_data_dict: Dict[str, Tuple[float, float]]):
        """Handles the raw animated skeleton pose update from IKManager."""
        logging.debug(f"MainWindow:_handle_skeleton_pose_updated_from_ik - Received animated_pose_data_dict (count: {len(animated_pose_data_dict)}): {animated_pose_data_dict if len(animated_pose_data_dict) < 5 else str(list(animated_pose_data_dict.items())[:5]) + '...'}")
        if self.editor_tab and self.editor_tab.editor_view:
            # Pass the raw animated data directly
            self.editor_tab.editor_view.update_skeleton_animation(animated_pose_data_dict)
        else:
            logging.warning("MainWindow: Cannot relay skeleton pose update, EditorTab or EditorView not available.")
