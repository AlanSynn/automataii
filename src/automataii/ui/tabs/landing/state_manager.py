# src/automataii/ui/tabs/landing/state_manager.py

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class LandingStateManager(QObject):
    """
    Manages state for the Landing tab.
    Simple state management for example image display.
    """

    # Signals
    state_changed = pyqtSignal()
    images_loaded = pyqtSignal(list)  # Specific signal for image loading completion

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Image data
        self.example_image_paths: list[Path] = []

        # UI state
        self.is_loading: bool = True
        self.status_message: str = "Loading example images..."

        # Configuration
        self.experiment_mode: bool = False

    def set_example_images(self, image_paths: list[Path]) -> None:
        """Set the list of example image paths."""
        self.example_image_paths = image_paths.copy()
        self.images_loaded.emit(self.example_image_paths)
        self.state_changed.emit()
        logger.info(f"StateManager: Set {len(image_paths)} example images")

    def set_loading_state(self, loading: bool) -> None:
        """Set the loading state."""
        if self.is_loading != loading:
            self.is_loading = loading
            self.state_changed.emit()

    def set_status_message(self, message: str) -> None:
        """Set the status message."""
        if self.status_message != message:
            self.status_message = message
            self.state_changed.emit()

    def set_experiment_mode(self, experiment_mode: bool) -> None:
        """Set experiment mode flag."""
        if self.experiment_mode != experiment_mode:
            self.experiment_mode = experiment_mode
            self.state_changed.emit()

    def clear_all(self) -> None:
        """Clear all state data."""
        self.example_image_paths.clear()
        self.is_loading = True
        self.status_message = "Loading example images..."
        self.state_changed.emit()
        logger.info("LandingStateManager: All data cleared")
