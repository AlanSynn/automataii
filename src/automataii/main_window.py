from typing import Dict, Optional, List
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPainterPath
import logging

class MainWindow:
    def _on_project_data_loaded(self, project_dir: Path, parts_data: Dict[str, PartInfo], skeleton_data_for_project: Optional[List[Dict]]):
        """Handles successful project data loading from ProjectDataManager."""
        logging.info(f"MainWindow: Project data loaded successfully from {project_dir}")
        self.current_project_dir = project_dir
        self.current_temp_char_dir = project_dir # After BPE, this is the definitive character asset location

        # Clear existing content in EditorTab first
        if self.editor_tab:
            self.editor_tab.clear_editor_content() # This also clears its view

        # Load parts into EditorTab
        if self.editor_tab and parts_data:
            self.editor_tab.set_parts_data(parts_data, project_dir)
            # status_message += f" {len(parts_data)} parts loaded into editor."

        # Update IKManager with parts data
        if self.ik_manager and parts_data:
            self.ik_manager.set_project_parts_data(parts_data)

        # Load skeleton data into SkeletonManager, which will then update IKManager via signal
        if skeleton_data_for_project:
            logging.info("SkeletonManager: Attempting to load skeleton from project data list (joint count: "
                         f"{len(skeleton_data_for_project) if skeleton_data_for_project else 'N/A'}).")
            success = self.skeleton_manager.load_skeleton(skeleton_data_for_project, source_format_hint="animated_drawings")
            if success:
                logging.info(f"MainWindow: Skeleton re-loaded into SkeletonManager based on project data. IKManager ID: {id(self.ik_manager) if self.ik_manager else 'N/A'}. Expect IKManager to re-initialize.")
            else:
                logging.error("MainWindow: Failed to re-load skeleton into SkeletonManager from project data.")
        else:
            logging.warning("MainWindow: No skeleton_data_for_project provided during project load.")
            # Ensure skeleton is cleared if project has no skeleton
            self.skeleton_manager.clear_data()
            logging.info(f"MainWindow: Cleared SkeletonManager due to no skeleton in project. IKManager ID: {id(self.ik_manager) if self.ik_manager else 'N/A'}.")


        if self.image_processing_tab:
            self.image_processing_tab.on_project_parts_loaded_in_editor(True)

        self.update_all_tab_states()
        self.statusBar().showMessage(f"Project loaded from: {project_dir.name}", 5000)
        logging.info(f"MainWindow: Project and parts data ({len(parts_data) if parts_data else 0} parts) loaded. Switching to editor tab if needed.")
        if self.config.get("switchToEditorTabOnProjectLoad", True):
            QTimer.singleShot(100, lambda: self.switch_to_tab_by_name("Editor"))

        logging.info(f"MainWindow: Project loaded. Updated current_temp_char_dir to BPE output: {self.current_temp_char_dir}")
        # After everything is set up, trigger zoom to fit
        if self.editor_tab and self.editor_tab.editor_view:
            QTimer.singleShot(150, self.editor_tab.editor_view.zoom_to_fit_all_parts) # Delay slightly


    def _handle_freehand_path_completed(self, part_name: str, path: QPainterPath):
        logging.info(f"Freehand motion path completed for {part_name} with {path.elementCount()} points.")
        if self.ik_manager:
            logging.info(f"MainWindow: Relaying motion path update for '{part_name}' to IKManager (id: {id(self.ik_manager)}). Current IKManager._current_skeleton_data state: {self.ik_manager._current_skeleton_data is not None}")
            self.ik_manager.update_part_motion_path(part_name, path)
        else:
            logging.warning("IKManager not available to update motion path.")

    def _on_request_define_motion_path(self, part_name: str):
        pass # Added pass to satisfy linter, original content not shown

    def _on_editor_view_interaction_mode_changed(self, mode: str):
        """Handles mode changes from the EditorView (e.g., select, defining_path)."""

class AutomataDesigner(QMainWindow):
    # Signals
    request_load_project = pyqtSignal()
    request_save_project = pyqtSignal()
    request_save_project_as = pyqtSignal()
    request_export_character = pyqtSignal()
    request_exit_application = pyqtSignal()
    project_data_loaded_for_editor = pyqtSignal(dict, Path) # parts_data, project_dir for textures
    status_message_updated = pyqtSignal(str)
    view_reset_requested = pyqtSignal()
    simulation_state_changed_externally = pyqtSignal(str) # e.g. from IKManager 'running', 'stopped'

    # For communication with IKManager about skeleton
    skeleton_data_for_ik_update = pyqtSignal(object) # StandardizedSkeletonModel or None

    def __init__(self, app_instance: QApplication, debug_mode: bool = False):
        super().__init__()
        # Ensure logging is configured early if not already done by main entry point
        # basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] %(message)s')
        logging.info("AutomataDesigner.__init__: ########## STARTING INITIALIZATION ########## Debug mode: %s", debug_mode)
        self.app = app_instance
        self.debug_mode = debug_mode
        self.current_project_dir: Optional[Path] = None
        self.current_temp_char_dir: Optional[Path] = None # Used by BPE, then PDM points to its output
        self.setWindowTitle("Automata Designer II: The Characterining") # New, improved title!
        self.setGeometry(100, 100, 1700, 1300) # Slightly larger
        logging.info("AutomataDesigner.__init__: Window properties set.")

        # Initialize core components / managers
        logging.info("AutomataDesigner.__init__: Initializing ProjectDataManager...")
        self.project_data_manager = ProjectDataManager(main_window_ref=self)
        logging.info("AutomataDesigner.__init__: ProjectDataManager initialized (ID: %s).", id(self.project_data_manager))

        logging.info("AutomataDesigner.__init__: Initializing SkeletonManager...")
        self.skeleton_manager = SkeletonManager(self) # Parent is self (AutomataDesigner)
        logging.info("AutomataDesigner.__init__: SkeletonManager initialized (ID: %s).", id(self.skeleton_manager))

        logging.info("AutomataDesigner.__init__: Initializing IKManager...")
        self.ik_manager = IKManager(main_window_ref=self) # Parent is self
        logging.info("AutomataDesigner.__init__: IKManager initialized (ID: %s).", id(self.ik_manager))

        logging.info(f"AutomataDesigner.__init__: >>> About to call self.ik_manager.set_skeleton_manager. IKManager instance ID: {id(self.ik_manager)}, SkeletonManager instance ID: {id(self.skeleton_manager)}.")
        self.ik_manager.set_skeleton_manager(self.skeleton_manager) # CRITICAL LINK
        logging.info(f"AutomataDesigner.__init__: <<< SUCCESSFULLY CALLED self.ik_manager.set_skeleton_manager. IKManager ID: {id(self.ik_manager)}, SkeletonManager ID: {id(self.skeleton_manager)}.")

        # VERIFY the reference in IKManager
        if self.ik_manager.skeleton_manager_ref:
            logging.info(f"AutomataDesigner.__init__: >>> VERIFICATION: IKManager's skeleton_manager_ref is ID: {id(self.ik_manager.skeleton_manager_ref)}. This should match SkeletonManager ID above ({id(self.skeleton_manager)}).")
            if id(self.ik_manager.skeleton_manager_ref) != id(self.skeleton_manager):
                 logging.error("AutomataDesigner.__init__: CRITICAL MISMATCH! IKManager.skeleton_manager_ref ID (%s) does NOT match self.skeleton_manager ID (%s)!", id(self.ik_manager.skeleton_manager_ref), id(self.skeleton_manager))
        else:
            logging.warning("AutomataDesigner.__init__: >>> VERIFICATION CRITICAL! IKManager's skeleton_manager_ref is None immediately after setting!")

        logging.info("AutomataDesigner.__init__: Initializing MechanismManager...")
        self.mechanism_manager = MechanismManager(self) # Parent is self
        logging.info("AutomataDesigner.__init__: MechanismManager initialized (ID: %s).", id(self.mechanism_manager))

        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_statusbar()
        self._create_central_widget_and_tabs()
        self._connect_signals()
        self._load_custom_fonts() # Placeholder for custom font loading

        # Initialize options/settings from a config or defaults
        self.options_dialog = OptionsDialog(parent=self) # Keep a reference
        self.options_dialog.options_changed.connect(self._handle_options_changed)
        # Apply initial default options (e.g., animation duration)
        # This ensures IKManager gets an initial value if not loading a project immediately.
        initial_anim_duration = self.options_dialog.get_option("animation_duration")
        if isinstance(initial_anim_duration, (int, float)): # Check if it's a number
             self.ik_manager.set_animation_duration(int(initial_anim_duration * 1000)) # ms

        logging.info("AutomataDesigner.__init__: ########## INITIALIZATION COMPLETE ##########")

    # ... rest of the class ...