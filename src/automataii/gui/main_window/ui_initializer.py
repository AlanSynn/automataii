"""UI initialization for the main window."""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget

from automataii.gui.tabs.landing_tab import LandingTab
from automataii.gui.tabs.image_processing import ImageProcessingTab
from automataii.gui.tabs.editor.editor_tab_coordinator import EditorTabCoordinator
from automataii.gui.tabs.mechanism_generation import MechanismGenerationTab
from automataii.gui.tabs.options_tab import OptionsTab

if TYPE_CHECKING:
    from .main_window import AutomataDesigner


class UIInitializer:
    """Handles UI initialization for the main window."""

    def __init__(self, main_window: 'AutomataDesigner'):
        self.main_window = main_window

    def initialize(self):
        """Sets up the main user interface layout and widgets."""
        self._setup_central_widget()
        self._create_tabs()
        self._load_custom_fonts()

    def _setup_central_widget(self):
        """Set up the central widget and main layout."""
        main_widget = QWidget()
        self.main_window.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        self.main_window.tab_widget = QTabWidget()
        main_layout.addWidget(self.main_window.tab_widget)

    def _create_tabs(self):
        """Create and add all application tabs."""
        # Tab 0: Landing Page
        self.main_window.landing_tab = LandingTab(self.main_window)
        self.main_window.tab_widget.addTab(self.main_window.landing_tab, "1 Welcome")

        # Tab 1: Image Processing
        self.main_window.image_proc_tab = ImageProcessingTab(self.main_window)
        self.main_window.tab_widget.addTab(self.main_window.image_proc_tab, "2 Character Selection")

        # Tab 2: Editor & Simulation
        self.main_window.editor_tab = EditorTabCoordinator(
            self.main_window.ik_manager,
            self.main_window.project_data_manager,
            self.main_window.skeleton_manager,
            self.main_window
        )
        self.main_window.tab_widget.addTab(self.main_window.editor_tab, "3 Path Drawing")

        # Tab 3: Mechanism Generation
        self.main_window.mechanism_generation_tab = MechanismGenerationTab(self.main_window)
        self.main_window.tab_widget.addTab(self.main_window.mechanism_generation_tab, "4 Mechanism Generation")

        # Tab 4: Options
        self.main_window.options_tab = OptionsTab(
            initial_anim_duration=self.main_window.ik_manager.animation_duration
        )
        self.main_window.tab_widget.addTab(self.main_window.options_tab, "5 Options")

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