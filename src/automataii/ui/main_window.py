import json
import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import (
    pyqtSlot,
)
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from automataii.domain.kinematics.kinematics_system import KinematicsSystem
from automataii.models.runtime import PartInfo
from automataii.services.mechanism_manager import MechanismManager
from automataii.services.project_data_manager import ProjectDataManager
from automataii.services.skeleton_manager import SkeletonManager
from automataii.ui.actions.action_manager import ActionManager
from automataii.ui.tabs.editor.tab import EditorTab
from automataii.ui.tabs.image_processing import ImageProcessingTab
from automataii.ui.tabs.landing import LandingTab
from automataii.ui.tabs.mechanism_design.tab import MechanismDesignTab
from automataii.ui.tabs.mechanism_foundry import MechanismFoundryTab, EnhancedMacanismTab
from automataii.ui.tabs.options import OptionsTab
from automataii.ui.views.editor.view import EditorView
from automataii.utils.styling import DARK_STYLE, LIGHT_STYLE
from automataii.core.app_container import get_service
from automataii.services.motion_path_service import MotionPathService
from automataii.core.events import ProjectLoadedEvent, ProjectClearedEvent
from automataii.core.event_bus import get_global_event_bus
from automataii.ui.design_system import design_system, ThemeMode

logger = logging.getLogger(__name__)


class AutomataDesigner(QMainWindow):
    """Main application window for the Automata Designer."""

    def __init__(
        self, parent: QWidget | None = None, debug_mode: bool = False, experiment_mode: bool = False, container=None
    ):
        super().__init__(parent)
        self.debug_mode = debug_mode
        self.experiment_mode = experiment_mode
        self.container = container
        logging.info(f"Initializing AutomataDesigner... Debug mode: {self.debug_mode}")
        self.resize(1200, 680)
        self.setMinimumHeight(600)

        # Initialize event bus integration
        self.event_bus = get_global_event_bus()

        # Get services from DI container
        if container:
            self.motion_path_service = get_service(MotionPathService)
            logging.info("Initialized with dependency injection container")
        else:
            self.motion_path_service = None
            logging.warning("No DI container provided - falling back to legacy mode")

        self.updater = None
        self.action_manager = ActionManager(self)
        self.project_data_manager = ProjectDataManager(self)
        self.skeleton_manager = SkeletonManager(self)

        # Create Kinematics System. It's a dependency for some tabs.
        self.kinematics_system = KinematicsSystem(self.project_data_manager, self)

        # For convenience, though direct use should be minimized
        self.ik_manager = self.kinematics_system.ik_manager

        # Now initialize all tabs
        self._init_tabs()

        # Set the mechanism_design_tab reference in the kinematics_system
        self.kinematics_system.set_mechanism_tab(self.mechanism_design_tab)

        self.mechanism_manager = MechanismManager(self)

        self.project_dir: str | None = None
        self.main_toolbar = None
        self.shared_camera_state: dict[str, Any] | None = None
        self._previous_tab_index = 0
        self._signal_connections = []  # Track signal connections for cleanup

        self.light_style = LIGHT_STYLE
        self.dark_style = DARK_STYLE

        self._load_custom_fonts()
        self._init_ui_layout()
        self._create_menus()
        self._create_toolbar()
        self._connect_signals()

        # Apply design system stylesheet
        self._apply_design_system()

        self.setup_status_bar()
        logging.info("AutomataDesigner initialized.")

    def _init_tabs(self):
        """Initializes the tab widgets that are dependencies for other systems."""
        self.tab_widget = QTabWidget()
        self.landing_tab = LandingTab(self, experiment_mode=self.experiment_mode)
        self.image_proc_tab = ImageProcessingTab(self)
        self.editor_tab = EditorTab(self)
        self.mechanism_design_tab = MechanismDesignTab(self)
        self.mechanism_foundry_tab = MechanismFoundryTab(self)
        self.enhanced_mechanism_tab = EnhancedMacanismTab(self)
        self.options_tab = OptionsTab(self)

    def _init_ui_layout(self):
        """Sets up the main user interface layout and adds the initialized tabs."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.tab_widget)

        self.tab_widget.addTab(self.landing_tab, "Welcome")
        self.tab_widget.addTab(self.image_proc_tab, "Character Selection")
        self.tab_widget.addTab(self.editor_tab, "Path Editor")
        self.tab_widget.addTab(self.mechanism_design_tab, "Mechanism Design")
        self.tab_widget.addTab(self.mechanism_foundry_tab, "Foundry")
        self.tab_widget.addTab(self.enhanced_mechanism_tab, "Interactive Mechanism")
        if not self.experiment_mode:
            self.tab_widget.addTab(self.options_tab, "Options")

    def _connect_signals(self):
        """Connects all signals between components."""
        # --- Global and Manager Signals ---
        self._signal_connections.append(
            self.tab_widget.currentChanged.connect(self._on_tab_changed)
        )
        self._signal_connections.append(
            self.project_data_manager.project_data_loaded.connect(self._handle_project_data_loaded)
        )
        self._signal_connections.append(
            self.project_data_manager.project_data_cleared.connect(
                self._handle_project_data_cleared
            )
        )
        self._signal_connections.append(
            self.project_data_manager.error_occurred.connect(self._handle_project_manager_error)
        )
        self._signal_connections.append(
            self.skeleton_manager.skeleton_updated.connect(
                self.kinematics_system.on_skeleton_data_updated
            )
        )

        # --- Kinematics System Signals ---
        self.kinematics_system.pose_updated.connect(self.editor_tab.handle_ik_update)
        self.kinematics_system.pose_updated.connect(self.mechanism_design_tab.handle_ik_update)
        self.kinematics_system.animation_state_changed.connect(
            self.editor_tab.on_simulation_state_changed
        )

        # --- Tab-Specific Signals ---
        self.landing_tab.image_selected.connect(self._handle_landing_image_selected)
        self.image_proc_tab.parts_generated.connect(self.handle_parts_generated_from_tab)
        self.image_proc_tab.skeleton_updated.connect(self.handle_skeleton_updated_from_tab)
        self.image_proc_tab.request_editor_tab_switch.connect(self.switch_to_editor_tab)

        # --- Editor Tab -> Kinematics System ---
        self.editor_tab.request_play_simulation.connect(self.kinematics_system.start_animation)
        self.editor_tab.request_stop_simulation.connect(self.kinematics_system.stop_animation)
        self.editor_tab.request_reset_simulation.connect(self.kinematics_system.reset_animation)
        self.editor_tab.request_generate_blueprint.connect(self.generate_blueprint_impl)
        self.editor_tab.path_data_changed.connect(
            self.mechanism_design_tab.set_path_data_from_editor
        )
        self.editor_tab.motion_path_updated.connect(self._handle_part_motion_path_update)

        # --- Options Tab -> System ---
        self.options_tab.animationDurationChanged.connect(
            self.kinematics_system.set_animation_duration
        )
        self.options_tab.themeChanged.connect(self._apply_theme)
        self.options_tab.toolbarVisibilityChanged.connect(self._toggle_toolbar_visibility)
        self.options_tab.partPropertiesVisibilityChanged.connect(
            self.editor_tab.toggle_part_properties_panel_visibility
        )

        # --- Menu Actions ---
        self._connect_menu_actions()

    def _connect_menu_actions(self):
        """Connects actions from the ActionManager to their handlers."""
        self.action_manager.connect_action("load_parts", self.load_parts_dialog)
        self.action_manager.connect_action("save_project", self.save_project_dialog)
        self.action_manager.connect_action("exit", self.close)
        self.action_manager.connect_action("about", self.show_about_dialog)

        # View actions are context-sensitive to the current tab
        self.action_manager.connect_action(
            "zoom_in", lambda: self._get_current_view() and self._get_current_view().zoom_in()
        )
        self.action_manager.connect_action(
            "zoom_out", lambda: self._get_current_view() and self._get_current_view().zoom_out()
        )
        self.action_manager.connect_action(
            "zoom_fit", lambda: self._get_current_view() and self._get_current_view().zoom_to_fit()
        )
        self.action_manager.connect_action(
            "reset_view", lambda: self._get_current_view() and self._get_current_view().reset_view()
        )

    def _get_current_view(self) -> EditorView | None:
        """Gets the active EditorView from the current tab."""
        current_tab = self.tab_widget.currentWidget()
        if hasattr(current_tab, "view") and isinstance(current_tab.view, EditorView):
            return current_tab.view
        if hasattr(current_tab, "editor_view") and isinstance(current_tab.editor_view, EditorView):
            return current_tab.editor_view
        return None

    def setup_status_bar(self):
        """Initializes and configures the status bar."""
        if self.experiment_mode:
            experiment_label = QLabel("🧪 Experiment")
            experiment_label.setStyleSheet(
                "QLabel { color: #1982c4; font-weight: bold; padding: 2px 8px; }"
            )
            self.statusBar().addPermanentWidget(experiment_label)
        self.statusBar().showMessage("Ready")

    @pyqtSlot(str, QPainterPath)
    def _handle_part_motion_path_update(self, part_name: str, motion_qpath: QPainterPath):
        """
        Handles the motion_path_updated signal from EditorTab.
        This data is now managed by ProjectDataManager, which will notify other systems.
        """
        self.project_data_manager.update_motion_path_for_part(part_name, motion_qpath)

    @pyqtSlot(dict)
    def handle_skeleton_updated_from_tab(self, skeleton_data: dict):
        """Handles the skeleton_updated signal from ImageProcessingTab."""
        logging.info("MainWindow: Received skeleton_updated signal. Forwarding to SkeletonManager.")

        # Check if animation is running - prevent skeleton changes during animation
        if hasattr(self.kinematics_system, "ik_animator") and hasattr(
            self.kinematics_system.ik_animator, "is_running"
        ):
            if self.kinematics_system.ik_animator.is_running():
                logging.warning(
                    "Cannot update skeleton while animation is running. Stop animation first."
                )
                QMessageBox.warning(
                    self,
                    "Animation Active",
                    "Cannot update skeleton while animation is running.\nPlease stop the animation first.",
                )
                return

        self.skeleton_manager.load_skeleton_from_dict(
            skeleton_data, source_format="auto"
        )

        # Auto-switch to editor tab after skeleton is loaded
        self.switch_to_editor_tab()

    @pyqtSlot(bool, str, dict)
    def _handle_project_data_loaded(
        self, success: bool, project_dir: str, parts_info: dict[str, PartInfo]
    ):
        """Handles the project_data_loaded signal from ProjectDataManager."""
        if not success:
            QMessageBox.critical(
                self, "Load Project Error", f"Failed to load project from {project_dir}."
            )
            self.statusBar().showMessage("Project loading failed.")
            return

        logging.info(f"MainWindow: Project data loaded successfully from {project_dir}")
        self.project_dir = Path(project_dir)

        # Notify tabs and managers
        self.editor_tab.set_parts_data(parts_info)
        self.mechanism_design_tab.set_parts_data(parts_info)

        # Ensure both editor and mechanism tabs have current skeleton data if available
        if self.skeleton_manager.standardized_model is not None:
            current_skeleton = self.skeleton_manager.get_current_skeleton_data()
            if current_skeleton:
                self.editor_tab.cache_initial_skeleton(current_skeleton)
                self.mechanism_design_tab.cache_initial_skeleton(current_skeleton)

        skeleton_data = self.project_data_manager.raw_skeleton_data
        # Only load skeleton data if we have some, or if we don't have any existing skeleton
        if skeleton_data or self.skeleton_manager.standardized_model is None:
            self.skeleton_manager.load_skeleton_from_project_data(skeleton_data, parts_info)
        else:
            logging.info(
                "MainWindow: Preserving existing skeleton data, not loading empty skeleton from project."
            )
            # Ensure KinematicsSystem still has the preserved skeleton data
            if self.skeleton_manager.standardized_model:
                current_skeleton_dict = self.skeleton_manager.get_current_skeleton_data()
                if current_skeleton_dict:
                    self.kinematics_system.on_skeleton_data_updated(current_skeleton_dict)

        try:
            logging.info("MainWindow: Notifying image proc tab about parts loaded")
            self.image_proc_tab.on_parts_loaded_in_editor(True)
        except Exception as e:
            logging.error(f"Error notifying image proc tab: {e}")

        try:
            logging.info("MainWindow: Updating status bar")
            self.statusBar().showMessage(f"Project loaded: {project_dir}")
        except Exception as e:
            logging.error(f"Error updating status bar: {e}")

        try:
            logging.info("MainWindow: Updating action manager")
            self.action_manager.update_actions_for_project_state(True)
        except Exception as e:
            logging.error(f"Error updating action manager: {e}")

        if parts_info:
            try:
                logging.info("MainWindow: Switching to editor tab")
                self.switch_to_editor_tab()
                logging.info("MainWindow: Successfully switched to editor tab")
            except Exception as e:
                logging.error(f"Error switching to editor tab: {e}")
                import traceback
                traceback.print_exc()

    @pyqtSlot()
    def _handle_project_data_cleared(self):
        """Handles the project_data_cleared signal from ProjectDataManager."""
        logging.info("MainWindow: Handling project data cleared signal.")
        self.editor_tab.clear_editor_content()
        self.mechanism_design_tab.clear_mechanism_data()
        # Note: We don't clear skeleton data here as it may need to be preserved
        # The skeleton should only be cleared when explicitly needed
        self.action_manager.update_actions_for_project_state(False)
        self.statusBar().showMessage("Project data cleared.")

    @pyqtSlot()
    def generate_blueprint_impl(self):
        """Relays blueprint generation request to the appropriate handler."""
        if hasattr(self.mechanism_design_tab, "action_handler"):
            self.mechanism_design_tab.action_handler.handle_export_blueprint()
        else:
            QMessageBox.critical(self, "Error", "Blueprint generation feature is not available.")

    def load_parts_dialog(self):
        """Opens a file dialog to load parts from a JSON file."""
        start_dir = str(self.project_data_manager.project_dir or Path.home())
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Character Parts File", start_dir, "JSON files (*.json)"
        )
        if filepath:
            self.project_data_manager.load_project_from_file(filepath)

    def save_project_dialog(self):
        """Opens a file dialog to save the current project."""
        self.project_data_manager.save_project_dialog()

    def switch_to_editor_tab(self):
        """Switches the main tab widget to the Editor Tab."""
        for i in range(self.tab_widget.count()):
            if self.tab_widget.widget(i) == self.editor_tab:
                self.tab_widget.setCurrentIndex(i)
                return

    def _on_tab_changed(self, index: int):
        """Handle tab switching with proper lifecycle management."""
        # Get previous and current tabs
        previous_widget = (
            self.tab_widget.widget(self._previous_tab_index)
            if hasattr(self, "_previous_tab_index")
            else None
        )
        current_widget = self.tab_widget.widget(index)

        # Deactivate previous tab
        if previous_widget and hasattr(previous_widget, "deactivate_tab"):
            try:
                previous_widget.deactivate_tab()
                logging.debug(f"Deactivated tab: {previous_widget.__class__.__name__}")
            except Exception as e:
                logging.error(f"Error deactivating tab {previous_widget.__class__.__name__}: {e}")

        # Activate current tab
        if current_widget and hasattr(current_widget, "activate_tab"):
            try:
                current_widget.activate_tab()
                logging.debug(f"Activated tab: {current_widget.__class__.__name__}")
            except Exception as e:
                logging.error(f"Error activating tab {current_widget.__class__.__name__}: {e}")

        # Update previous tab index
        self._previous_tab_index = index

        # Existing skeleton consistency check
        if current_widget == self.editor_tab:
            if self.skeleton_manager.standardized_model and self.project_data_manager.parts:
                if not self.skeleton_manager.is_skeleton_compatible_with_parts(
                    self.project_data_manager.parts
                ):
                    logging.warning(
                        "Tab switch detected skeleton-part mismatch. Data may be inconsistent."
                    )
                    # Could show warning to user or attempt to resolve

        # Force garbage collection to clean up resources
        import gc

        gc.collect()

    def closeEvent(self, event):
        """Handle application close event with comprehensive resource cleanup."""
        logging.info("MainWindow: Application close event triggered")

        try:
            # Stop any running animations first
            if hasattr(self, "kinematics_system") and self.kinematics_system:
                self.kinematics_system.stop_animation()
                logging.debug("Stopped kinematics system animation")

            # Cleanup all tabs with proper exception handling
            for i in range(self.tab_widget.count()):
                tab_widget = self.tab_widget.widget(i)
                if tab_widget:
                    try:
                        if hasattr(tab_widget, "cleanup"):
                            tab_widget.cleanup()
                        elif hasattr(tab_widget, "deactivate_tab"):
                            tab_widget.deactivate_tab()
                        logging.debug(f"Cleaned up tab {i}: {tab_widget.__class__.__name__}")
                    except Exception as e:
                        logging.warning(f"Error cleaning up tab {i}: {e}")

            # Close project and save if needed
            if hasattr(self, "project_data_manager") and self.project_data_manager:
                try:
                    self.project_data_manager.close_project()
                    logging.debug("Closed project data manager")
                except Exception as e:
                    logging.warning(f"Error closing project data manager: {e}")

            # Shutdown motion path service
            if hasattr(self, "motion_path_service") and self.motion_path_service:
                try:
                    self.motion_path_service.shutdown()
                    logging.debug("Shutdown motion path service")
                except Exception as e:
                    logging.warning(f"Error shutting down motion path service: {e}")

            # Disconnect all signal connections with error handling
            if hasattr(self, "_signal_connections"):
                disconnected_count = 0
                for connection in self._signal_connections:
                    try:
                        # Check if connection has disconnect method
                        if hasattr(connection, 'disconnect'):
                            connection.disconnect()
                            disconnected_count += 1
                        else:
                            # Handle different connection types
                            try:
                                # Try PyQt signal disconnect
                                connection.disconnect()
                                disconnected_count += 1
                            except AttributeError:
                                # Connection may be a different type or already disconnected
                                pass
                    except (RuntimeError, TypeError, AttributeError):
                        pass  # Connection may already be disconnected or invalid
                self._signal_connections.clear()
                logging.debug(f"Disconnected {disconnected_count} signal connections")

            # Clear scene items to prevent memory leaks
            for i in range(self.tab_widget.count()):
                tab_widget = self.tab_widget.widget(i)
                if hasattr(tab_widget, "scene") and tab_widget.scene:
                    try:
                        tab_widget.scene.clear()
                        logging.debug(f"Cleared scene for tab {i}")
                    except Exception as e:
                        logging.warning(f"Error clearing scene for tab {i}: {e}")

            # Clear GPU memory if available
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logging.debug("Cleared GPU memory")
            except ImportError:
                pass
            except Exception as e:
                logging.warning(f"Error clearing GPU memory: {e}")

            # Force multiple garbage collection passes for thorough cleanup
            import gc
            for _ in range(3):
                collected = gc.collect()
                if collected == 0:
                    break
            logging.debug(f"Garbage collection completed - collected {collected} objects")

            logging.info("MainWindow: Resource cleanup completed successfully")

        except Exception as e:
            logging.error(f"MainWindow: Error during close event cleanup: {e}")

        # Accept the close event
        super().closeEvent(event)

    # --- All other methods (dialogs, UI toggles, etc.) remain largely the same ---
    # ... (show_about_dialog, _apply_theme, _toggle_toolbar_visibility, etc.) ...
    def _create_menus(self):
        menubar = self.menuBar()
        self.action_manager.setup_menus(menubar)

    def _create_toolbar(self):
        self.main_toolbar = QToolBar("Main Toolbar")
        self.main_toolbar.setMovable(False)
        self.action_manager.setup_toolbar(self.main_toolbar)
        self.addToolBar(self.main_toolbar)
        self.main_toolbar.hide()

    def _load_custom_fonts(self):
        pass

    def _apply_design_system(self):
        """Apply the design system stylesheet"""
        self.setStyleSheet(design_system.get_stylesheet())
        logging.info("Applied design system stylesheet")

    def _apply_theme(self, theme_name: str):
        """Apply theme using the design system"""
        theme_mode = ThemeMode.DARK if theme_name == "dark" else ThemeMode.LIGHT
        design_system.set_theme(theme_mode)
        self.setStyleSheet(design_system.get_stylesheet())
        logging.info(f"Applied {theme_name} theme using design system.")

    def _toggle_toolbar_visibility(self, visible: bool):
        if self.main_toolbar:
            self.main_toolbar.setVisible(visible)

    def show_about_dialog(self):
        QMessageBox.about(self, "About Automata Designer", "Version 0.2.0")

    def set_status(self, message: str):
        """Set status bar message."""
        self.statusBar().showMessage(message)

    @pyqtSlot(str)
    def _handle_landing_image_selected(self, image_path: str):
        if self.image_proc_tab._load_image_from_path(image_path):
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i) == self.image_proc_tab:
                    self.tab_widget.setCurrentIndex(i)
                    break
        else:
            QMessageBox.warning(
                self, "Image Load Error", f"Could not load: {Path(image_path).name}"
            )

    @pyqtSlot(dict, str)
    def handle_parts_generated_from_tab(
        self, annotation_results: dict, final_bpe_char_dir_str: str
    ):
        parts_info_json_path = Path(final_bpe_char_dir_str) / "parts_info.json"
        if not parts_info_json_path.exists():
            QMessageBox.critical(self, "Project Load Error", "Could not locate parts_info.json.")
            return

        # Check if we have existing skeleton data that should be preserved
        # Only preserve skeleton if we're loading parts from the same character/session
        has_skeleton = self.skeleton_manager.standardized_model is not None
        is_same_project = (
            self.project_dir and Path(final_bpe_char_dir_str).parent == self.project_dir
        )

        # Additionally check skeleton compatibility with new parts
        preserve_skeleton = False
        if has_skeleton and is_same_project:
            # Load parts temporarily to check compatibility
            try:
                with open(parts_info_json_path) as f:
                    parts_data = json.load(f)
                    parts_info = parts_data.get("parts_info", {})
                    preserve_skeleton = self.skeleton_manager.is_skeleton_compatible_with_parts(
                        parts_info
                    )
                    if not preserve_skeleton:
                        logging.warning(
                            "Skeleton incompatible with new parts, will reload skeleton."
                        )
            except Exception as e:
                logging.error(f"Error checking skeleton compatibility: {e}")
                preserve_skeleton = False

        if preserve_skeleton:
            logging.info("MainWindow: Preserving existing skeleton data while loading parts.")

        self.project_data_manager.load_project_from_file(
            str(parts_info_json_path), preserve_skeleton=preserve_skeleton
        )

    def _handle_project_manager_error(self, error_message: str):
        QMessageBox.critical(self, "Project Error", f"An error occurred: {error_message}")
