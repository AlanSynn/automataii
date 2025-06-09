"""Refactored image processing view using modular components."""

import logging
import math
from typing import Optional, Dict
from PyQt6.QtCore import Qt, QEvent, QPointF, QRectF
from PyQt6.QtGui import QPainter

from .base_view import BaseImageView
from .zoom_handler import ZoomHandler
from .grid_renderer import GridRenderer
from .debug_renderer import DebugRenderer
from .image_manager import ImageManager
from .skeleton_manager import SkeletonManager
from .part_manager import PartManager
from .guide_renderer import GuideRenderer
from .event_handler import EventHandler
from ....core.managers.project_manager import ProjectDataManager


class ImageProcessingView(BaseImageView):
    """View for displaying the input image and editing the skeleton overlay.

    This is a refactored version that delegates responsibilities to specialized
    components for better maintainability and separation of concerns.
    """

    def __init__(self, scene, project_data_manager: ProjectDataManager, parent=None):
        super().__init__(scene, parent)
        self.project_data_manager = project_data_manager

        # Initialize component managers
        self.zoom_handler = ZoomHandler(self)
        self.grid_renderer = GridRenderer(self)
        self.debug_renderer = DebugRenderer(self)
        self.image_manager = ImageManager(self)
        self.skeleton_manager = SkeletonManager(self)
        self.part_manager = PartManager(
            self, project_dir=self.project_data_manager.project_dir
        )
        self.guide_renderer = GuideRenderer(self)
        self.event_handler = EventHandler(self)

        # Legacy compatibility - expose some commonly accessed attributes
        self._setup_legacy_attributes()

    def _setup_legacy_attributes(self):
        """Setup attributes for backward compatibility."""
        # Direct references to maintain compatibility
        self.debug_mode = property(
            lambda self: self.debug_renderer.debug_mode,
            lambda self, value: self.debug_renderer.set_debug_mode(value)
        ).fget(self)

        # Scene items references
        self.image_item = property(
            lambda self: self.image_manager.image_item
        ).fget(self)

        self.joints = self.skeleton_manager.joints
        self.joint_labels = self.skeleton_manager.joint_labels
        self.lines = self.skeleton_manager.lines
        self.original_skeleton_data = property(
            lambda self: self.skeleton_manager.original_skeleton_data
        ).fget(self)

        self.part_items = self.part_manager.part_items
        self.joint_to_part_map = self.part_manager.joint_to_part_map
        self.skeleton_to_part_map = self.part_manager.skeleton_to_part_map

        self.bounding_box = property(
            lambda self: self.image_manager.bounding_box
        ).fget(self)
        self.bb_center = property(
            lambda self: self.image_manager.bb_center
        ).fget(self)

        # Event handling
        self.dragged_joint_item = property(
            lambda self: self.event_handler.dragged_joint_item
        ).fget(self)

        # Debug items
        self.debug_bb_item = property(
            lambda self: self.debug_renderer.debug_bb_item
        ).fget(self)
        self.char_cfg_origin_marker = property(
            lambda self: self.debug_renderer.char_cfg_origin_marker
        ).fget(self)

        # Guide lines
        self.current_guide_lines = self.guide_renderer.current_guide_lines
        self.last_active_joint_for_guide = self.guide_renderer.last_active_joint_for_guide

        # Skeleton visualization items
        self._skeleton_viz_items = self.skeleton_manager._skeleton_viz_items

    # --- View Configuration ---

    def set_debug_mode(self, enable: bool):
        """Enables or disables the debug drawing mode."""
        self.debug_renderer.set_debug_mode(enable)

    # --- Drawing Methods ---

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draws a grid background based on the current display unit."""
        super().drawBackground(painter, rect)
        self.grid_renderer.draw_grid(painter, rect)

    def drawForeground(self, painter: QPainter, rect: QRectF):
        """Draws debug information on top of the view."""
        super().drawForeground(painter, rect)
        self.debug_renderer.draw_debug_info(painter, rect)

    # --- Event Handling ---

    def viewportEvent(self, event: QEvent):
        """Handle gesture events."""
        if event.type() == QEvent.Type.Gesture:
            return self.gestureEvent(event)
        return super().viewportEvent(event)

    def gestureEvent(self, event: QEvent):
        """Handle pinch gestures."""
        if self.zoom_handler.handle_gesture_event(event):
            return True
        return super().viewportEvent(event)

    def wheelEvent(self, event):
        """Handle mouse wheel for zooming."""
        delta = event.angleDelta().y()
        self.zoom_handler.handle_wheel_event(delta)

    def mousePressEvent(self, event: QEvent):
        """Handle mouse press events."""
        if not self.event_handler.handle_mouse_press(event, event.pos()):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QEvent):
        """Handle mouse move events."""
        if not self.event_handler.handle_mouse_move(event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QEvent):
        """Handle mouse release events."""
        if not self.event_handler.handle_mouse_release(event):
            super().mouseReleaseEvent(event)

    # --- Public API Methods ---

    def load_image(self, image_path: str) -> bool:
        """Loads and displays an image, clearing previous non-skeleton items."""
        # Clear previous items
        self._clear_skeleton()
        self._clear_debug_items()

        success = self.image_manager.load_image(image_path)

        if success:
            self._clear_joint_labels()
            self._clear_char_cfg_marker()
            self.clear_character_parts()
            self.reset_view()

        return success

    def load_skeleton(self, skeleton_data_dict: Optional[dict]) -> bool:
        """Loads skeleton data and visualizes it."""
        return self.skeleton_manager.load_skeleton(skeleton_data_dict)

    def get_skeleton_data(self) -> Optional[dict]:
        """Returns the current skeleton data."""
        return self.skeleton_manager.get_skeleton_data()

    def visualize_skeleton(self, skeleton_data: dict, joint_items: list = None):
        """Temporarily draws the skeleton structure on the scene."""
        self.skeleton_manager.visualize_skeleton(skeleton_data, joint_items)

    def load_character_parts(
        self,
        parts_data: Dict,
        skeleton_to_part_map: Dict[str, str],
        effective_bbox_offset: QPointF,
    ):
        """Loads and displays CharacterPartItems based on parts_data."""
        self.part_manager.load_character_parts(
            parts_data, skeleton_to_part_map, effective_bbox_offset
        )

    def show_skeleton_visuals(self, show: bool):
        """Shows or hides the skeleton joint and line visuals."""
        self.skeleton_manager.show_skeleton_visuals(show)

    def show_part_visuals(self, show: bool):
        """Shows or hides the CharacterPartItem visuals."""
        self.part_manager.show_part_visuals(show)

    def update_and_draw_cut_guides(self, active_joint: Optional[any]):
        """Updates and draws perpendicular cut guides for the active joint."""
        self.guide_renderer.update_and_draw_cut_guides(active_joint)

    # --- View Control ---

    def zoom(self, step: int):
        """Zooms the view by a given step."""
        self.zoom_handler.zoom(step)

    def reset_view(self):
        """Resets the view transformation and sets zoom to 100%."""
        self.zoom_handler.reset_zoom()

        if self.image_manager.image_item:
            # Center the view on the image
            self.centerOn(self.image_manager.image_item.boundingRect().center())
        elif self.skeleton_manager.joints:
            # Fit skeleton if no image
            rect = self.scene().itemsBoundingRect()
            if rect.isValid():
                self.centerOn(rect.center())

    def zoom_to_fit(self):
        """Zoom to fit all items in the view."""
        logging.info("ImageView: zoom_to_fit called")
        target_rect = None

        if self.image_manager.image_item:
            target_rect = self.image_manager.image_item.boundingRect()
            logging.info(f"ImageView: Using image item bounding rect: {target_rect}")
        elif self.scene():
            target_rect = self.scene().itemsBoundingRect()
            logging.info(f"ImageView: Using scene items bounding rect: {target_rect}")

        # Check view size
        view_size = self.size()
        logging.info(f"ImageView: View size: {view_size.width()}x{view_size.height()}")

        if target_rect and target_rect.isValid():
            padding = 20
            target_rect.adjust(-padding, -padding, padding, padding)
            logging.info(f"ImageView: Fitting to rect with padding: {target_rect}")
            self.fitInView(target_rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.zoom_handler.update_zoom_level_from_scale()
            logging.info("ImageView: fitInView completed")
        else:
            logging.warning("ImageView: No valid target rect for zoom_to_fit")

    # --- Private helper methods for backward compatibility ---

    def _clear_skeleton(self):
        """Clears skeleton-related items from the scene."""
        self.skeleton_manager.clear_skeleton()

    def _clear_debug_items(self):
        """Removes debug-related graphics items from the scene."""
        self.debug_renderer.clear_debug_items()

    def _clear_joint_labels(self):
        """Removes all joint label text items from the scene."""
        self.skeleton_manager.clear_joint_labels()

    def _clear_char_cfg_marker(self):
        """Removes the char_cfg origin marker from the scene."""
        self.debug_renderer.clear_char_cfg_marker()

    def clear_character_parts(self):
        """Removes all CharacterPartItem instances from this view's scene."""
        self.part_manager.clear_character_parts()

    def _clear_skeleton_visualization(self):
        """Clears temporary skeleton visualization items."""
        self.skeleton_manager.clear_skeleton_visualization()

    def _update_joint_label_position(self, joint_name: str):
        """Updates the position of a joint's label."""
        self.skeleton_manager.update_joint_label_position(joint_name)

    def _update_lines(self, joint_item):
        """Updates the lines connected to a moved joint."""
        self.skeleton_manager.update_lines(joint_item)

    def get_lines_connected_to_joint(self, target_joint):
        """Returns a list of line items connected to the target joint."""
        return self.skeleton_manager.get_lines_connected_to_joint(target_joint)

    def calculate_perpendicular_cut_guide(self, joint):
        """Calculates a perpendicular line segment at the joint."""
        return self.guide_renderer.calculate_perpendicular_cut_guide(joint)

    def _update_linked_part_position(self, joint_name: str, new_joint_scene_pos: QPointF):
        """Moves the CharacterPartItem linked to the given joint name."""
        self.part_manager.update_linked_part_position(joint_name, new_joint_scene_pos)

    def _load_bounding_box(self, image_path: str):
        """Loads bounding box data from a YAML file."""
        # This is now handled internally by image_manager
        pass