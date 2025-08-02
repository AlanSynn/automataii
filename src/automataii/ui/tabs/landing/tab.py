# src/automataii/ui/tabs/landing/tab.py

import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout

from automataii.ui.tabs.base.tab import BaseTab

from .action_handler import LandingActionHandler
from .state_manager import LandingStateManager
from .ui_panel import LandingUIPanel

logger = logging.getLogger(__name__)


class LandingTab(BaseTab):
    """
    Landing tab orchestrator following the new architecture pattern.

    This class acts as the main coordinator, connecting:
    - LandingStateManager: Manages state for example images
    - LandingActionHandler: Handles business logic and user actions
    - LandingUIPanel: Pure UI component for the landing page layout
    """

    # Signal emitted when an image is selected
    image_selected = pyqtSignal(str)  # Emits the selected image path

    def __init__(self, main_window, parent=None, experiment_mode=False):
        super().__init__(main_window, parent)
        self.experiment_mode = experiment_mode

        # Initialize components
        self.state_manager: LandingStateManager | None = None
        self.action_handler: LandingActionHandler | None = None
        self.ui_panel: LandingUIPanel | None = None

        # Initialize architecture
        self._init_architecture()

        # Start loading images
        self._load_initial_data()

    def _init_architecture(self) -> None:
        """Initialize the architecture components and connect them."""
        # Create state manager
        self.state_manager = LandingStateManager(self)

        # Create action handler
        self.action_handler = LandingActionHandler(self.state_manager, self)

        # Create UI panel
        self.ui_panel = LandingUIPanel(self)

        # Set up layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui_panel)

        # Connect components
        self._connect_components()

        logger.info("LandingTab architecture initialized")

    def _connect_components(self) -> None:
        """Connect signals between components."""
        # Connect state manager to UI updates
        self.state_manager.state_changed.connect(self._on_state_changed)
        self.state_manager.images_loaded.connect(self.ui_panel.update_images_display)

        # Connect action handler to main window
        self.action_handler.image_selected.connect(self.image_selected.emit)

        # Connect UI panel to action handler
        self.ui_panel.image_selected.connect(self.action_handler.handle_image_selected)

        # Set experiment mode if needed
        if self.experiment_mode:
            self.state_manager.set_experiment_mode(True)

    def _on_state_changed(self) -> None:
        """Handle state changes and update UI accordingly."""
        if self.ui_panel and self.state_manager:
            self.ui_panel.update_ui_from_state(self.state_manager)

    def _load_initial_data(self) -> None:
        """Load initial data (example images)."""
        if self.action_handler:
            self.action_handler.handle_load_example_images()

    def refresh(self) -> None:
        """Refresh the example images display."""
        if self.action_handler:
            self.action_handler.handle_refresh()

    def clear(self) -> None:
        """Clear all data and reset to initial state."""
        if self.state_manager:
            self.state_manager.clear_all()
        if self.ui_panel:
            self.ui_panel.clear_images()

    def get_state_manager(self) -> LandingStateManager | None:
        """Get the state manager for external access."""
        return self.state_manager

    def get_action_handler(self) -> LandingActionHandler | None:
        """Get the action handler for external access."""
        return self.action_handler

    def get_ui_panel(self) -> LandingUIPanel | None:
        """Get the UI panel for external access."""
        return self.ui_panel

    def activate_tab(self) -> None:
        """Called when the tab becomes active."""
        super().activate_tab()  # Call parent to apply theme styles
        logger.debug("LandingTab activated")
        # Resume any background tasks if needed
        if self.action_handler:
            self.action_handler.resume_background_tasks()

        # Ensure UI is up to date
        self._on_state_changed()

    def deactivate_tab(self) -> None:
        """Called when the tab becomes inactive."""
        logger.debug("LandingTab deactivated")
        # Pause any background tasks to save resources
        if self.action_handler:
            self.action_handler.pause_background_tasks()

        # Clear any temporary UI states
        if self.ui_panel:
            self.ui_panel.clear_temporary_states()

        # Force garbage collection for this tab's resources
        import gc

        gc.collect()
