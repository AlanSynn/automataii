# src/automataii/ui/tabs/landing/action_handler.py

import logging

from PyQt6.QtCore import QObject, pyqtSignal

from automataii.utils.paths import get_project_root, resolve_path

logger = logging.getLogger(__name__)


class LandingActionHandler(QObject):
    """
    Handles all business logic and user actions for the Landing tab.
    """

    # Signal for communication with main window
    image_selected = pyqtSignal(str)  # Emits selected image path

    def __init__(self, state_manager, parent=None):
        super().__init__(parent)
        self.state = state_manager
        self.parent_widget = parent

        # Configure example directories
        self.example_dirs = [
            resolve_path("src/examples"),
            # Add fallback paths if needed
            get_project_root() / "src" / "examples",
        ]

    def handle_load_example_images(self) -> None:
        """Load example images from the examples directories."""
        logger.info("Loading example images...")

        # Set loading state
        self.state.set_loading_state(True)
        self.state.set_status_message("Loading example images...")

        try:
            # Find all image files
            image_paths = []
            supported_formats = ["*.png", "*.jpg", "*.jpeg", "*.gif"]

            for example_dir in self.example_dirs:
                if example_dir.exists():
                    logger.info(f"Looking for example images in: {example_dir}")
                    for format_pattern in supported_formats:
                        # Get direct images in examples directory
                        for img_path in example_dir.glob(format_pattern):
                            if img_path.is_file():
                                image_paths.append(img_path)
                                logger.debug(f"Found example image: {img_path}")

            # Remove duplicates and sort
            image_paths = sorted(set(image_paths))

            # Update state based on results
            if not image_paths:
                self.state.set_status_message("No example images found")
                logger.warning("No example images found in any of the example directories")
            else:
                self.state.set_status_message("")  # Clear status message on success
                logger.info(f"Loaded {len(image_paths)} example images")

            # Set the images in state
            self.state.set_example_images(image_paths)

        except Exception as e:
            logger.error(f"Error loading example images: {e}")
            self.state.set_status_message("Error loading example images")
            self.state.set_example_images([])

        finally:
            self.state.set_loading_state(False)

    def handle_image_selected(self, image_path: str) -> None:
        """Handle when an example image is selected."""
        logger.info(f"Example image selected: {image_path}")

        # Emit signal for main window to handle
        # This will typically switch to ImageProcessingTab and load the image
        self.image_selected.emit(image_path)

    def handle_refresh(self) -> None:
        """Handle refresh request."""
        logger.info("Refreshing example images...")
        self.handle_load_example_images()

    def pause_background_tasks(self) -> None:
        """Pause any background tasks when tab is deactivated."""
        logger.debug("LandingActionHandler: Pausing background tasks")
        # For landing tab, there are typically no long-running background tasks
        # But this method is required for the tab lifecycle interface
        pass

    def resume_background_tasks(self) -> None:
        """Resume any background tasks when tab is activated."""
        logger.debug("LandingActionHandler: Resuming background tasks")
        # For landing tab, there are typically no long-running background tasks
        # But this method is provided for consistency
        pass
