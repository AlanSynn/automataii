# src/automataii/ui/tabs/image_processing/scene_manager.py

import logging

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QGraphicsScene

from automataii.ui.views.image_processing.view import ImageProcessingView

logger = logging.getLogger(__name__)


class ImageProcessingSceneManager(QObject):
    """
    Manages the QGraphicsScene and ImageProcessingView for the Image Processing tab.
    Handles all visual updates based on state changes.
    """

    def __init__(
        self, scene: QGraphicsScene, view: ImageProcessingView, state_manager, parent=None
    ):
        super().__init__(parent)
        self.scene = scene
        self.view = view
        self.state = state_manager

        # Connect to state changes
        self.state.image_path_changed.connect(self._on_image_path_changed)
        self.state.skeleton_data_changed.connect(self._on_skeleton_data_changed)
        self.state.state_changed.connect(self._on_state_changed)

    def _on_image_path_changed(self, image_path: str) -> None:
        """Handle image path changes by loading the image into the view."""
        if image_path:
            logger.info(f"Loading image into view: {image_path}")
            self.view.load_image(image_path)
        else:
            logger.info("Clearing image from view")
            self.clear_scene()

    def _on_skeleton_data_changed(self, skeleton_data: dict) -> None:
        """Handle skeleton data changes by updating the view."""
        if skeleton_data:
            logger.info("Loading skeleton data into view")
            self.view.load_skeleton(skeleton_data)
        else:
            logger.info("Clearing skeleton from view")
            # If the view has a method to clear skeleton, use it
            if hasattr(self.view, "_clear_skeleton"):
                self.view._clear_skeleton()

    def _on_state_changed(self) -> None:
        """Handle general state changes."""
        # Update edit mode based on state
        if hasattr(self.view, "set_edit_mode"):
            self.view.set_edit_mode(self.state.is_editing_skeleton)

    def clear_scene(self) -> None:
        """Clear the entire scene."""
        self.scene.clear()
        if hasattr(self.view, "clear_view"):
            self.view.clear_view()

    def get_current_skeleton_data(self) -> dict | None:
        """Get the current skeleton data from the view."""
        if hasattr(self.view, "get_skeleton_data"):
            return self.view.get_skeleton_data()
        return None

    def set_skeleton_edit_mode(self, enabled: bool) -> None:
        """Enable or disable skeleton editing mode."""
        if hasattr(self.view, "set_edit_mode"):
            self.view.set_edit_mode(enabled)
            logger.info(f"Skeleton edit mode: {'enabled' if enabled else 'disabled'}")

    def reset_view(self) -> None:
        """Reset the view to default state."""
        if hasattr(self.view, "reset_view"):
            self.view.reset_view()

    def zoom_in(self) -> None:
        """Zoom in the view."""
        self.view.zoom(1)

    def zoom_out(self) -> None:
        """Zoom out the view."""
        self.view.zoom(-1)

    def zoom_to_fit(self) -> None:
        """Zoom to fit the content."""
        self.view.zoom_to_fit()

    def update_skeleton_from_external(self, skeleton_data: dict) -> None:
        """Update skeleton from external source (e.g., editor tab)."""
        # This is called when skeleton is updated externally
        # We update the view directly and then sync with state
        if skeleton_data and hasattr(self.view, "load_skeleton_data"):
            self.view.load_skeleton_data(skeleton_data)
            # Note: We don't update state here as this is an external update
            # The tab will handle state synchronization
