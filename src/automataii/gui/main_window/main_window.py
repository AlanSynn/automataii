"""Main application window for the Automata Designer.

This is the refactored main window that delegates responsibilities to
specialized coordinator and manager classes.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from PyQt6.QtWidgets import QMainWindow, QWidget, QMessageBox, QGraphicsItem, QGraphicsPixmapItem
from PyQt6.QtCore import pyqtSlot, QPointF
from PyQt6.QtGui import QPainterPath

from .ui_initializer import UIInitializer
from .menu_toolbar_manager import MenuToolbarManager
from .tab_manager import TabManager
from .signal_coordinator import SignalCoordinator
from .project_coordinator import ProjectCoordinator
from .animation_coordinator import AnimationCoordinator
from .theme_manager import ThemeManager

from automataii.processing.animation.parts_extraction.models import PartInfo
from automataii.gui.actions.action_manager import ActionManager
from automataii.core.managers.project_manager import ProjectDataManager
from automataii.core.skeleton.manager import SkeletonManager
from automataii.kinematics.ik_service_adapter import IKServiceAdapter
from automataii.core.managers.mechanism_manager import MechanismManager
from automataii.gui.graphics_items.part_item import CharacterPartItem

TARGET_CONTROL_POINTS = 8


class AutomataDesigner(QMainWindow):
    """Main application window for the Automata Designer.

    This class serves as the central hub that coordinates between different
    subsystems through specialized manager and coordinator classes.
    """

    def __init__(self, parent: Optional[QWidget] = None, debug_mode: bool = False):
        super().__init__(parent)
        self.debug_mode = debug_mode
        logging.info(f"Initializing AutomataDesigner... Debug mode: {self.debug_mode}")

        # Core settings
        self.resize(1200, 680)
        self.setMinimumHeight(600)

        # Initialize legacy attributes for compatibility
        self._init_legacy_attributes()

        # Initialize core managers
        self._init_core_managers()

        # Initialize coordinators
        self._init_coordinators()

        # Setup UI (must be done before signal connections)
        self.ui_initializer.initialize()

        # Setup connections (after UI is initialized)
        self.signal_coordinator.connect_all_signals()

        # Link managers
        self._link_managers()

        self.statusBar().showMessage("Ready")
        logging.info("AutomataDesigner initialized.")

    def _init_legacy_attributes(self):
        """Initialize legacy attributes for compatibility with existing code."""
        self.viewer_char_texture_item: Optional[QGraphicsPixmapItem] = None
        self.viewer_skeleton_items: List[QGraphicsItem] = []
        self.viewer_body_part_items: Dict[str, CharacterPartItem] = {}
        self.viewer_loaded_parts_info: Optional[dict] = None
        self.viewer_loaded_texture_path: Optional[str] = None
        self.viewer_scene = None
        self.viewer_view = None
        self.main_toolbar = None
        self.visualization_layer_x_offset = 10.0

    def _init_core_managers(self):
        """Initialize core application managers."""
        self.action_manager = ActionManager(self)
        self.project_data_manager = ProjectDataManager(self)
        self.skeleton_manager = SkeletonManager(self)
        self.ik_manager = IKServiceAdapter(self)
        self.mechanism_manager = MechanismManager(self)

        # Project state
        self.project_dir: Optional[Path] = None

    def _init_coordinators(self):
        """Initialize coordinator classes."""
        self.ui_initializer = UIInitializer(self)
        self.menu_toolbar_manager = MenuToolbarManager(self)
        self.tab_manager = TabManager(self)
        self.signal_coordinator = SignalCoordinator(self)
        self.project_coordinator = ProjectCoordinator(self)
        self.animation_coordinator = AnimationCoordinator(self)
        self.theme_manager = ThemeManager(self)

    def _link_managers(self):
        """Link managers that need references to each other."""
        if self.skeleton_manager and self.ik_manager:
            logging.info("Linking SkeletonManager to IKManager.")
            self.ik_manager.set_skeleton_manager(self.skeleton_manager)
        else:
            logging.error("Critical error - SkeletonManager or IKManager not initialized before linking.")

    # Public API methods that delegate to coordinators

    def load_parts_dialog(self):
        """Opens a file dialog to load parts from a JSON file."""
        self.project_coordinator.load_parts_dialog()

    def save_project_dialog(self):
        """Opens a file dialog to save the current project."""
        self.project_coordinator.save_project_dialog()

    def load_project_dialog(self):
        """Opens a file dialog to load a project."""
        self.project_coordinator.load_project_dialog()

    def show_about_dialog(self):
        """Displays the 'About' dialog."""
        QMessageBox.about(
            self,
            "About Automata Designer",
            "<p><b>Automata Designer</b></p>"
            "<p>Version 0.1.0</p>"
            "<p>Copyright &copy; 2024 Alan Synn</p>"
            "<p>This application helps design and simulate automata mechanisms.</p>",
        )

    def show_about_qt_dialog(self):
        """Displays the 'About Qt' dialog."""
        QMessageBox.aboutQt(self, "About Qt")