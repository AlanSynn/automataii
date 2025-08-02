# src/automataii/ui/views/image_processing/modes/debug_mode.py

import logging

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QPainter
from PyQt6.QtWidgets import QGraphicsView

from .base_mode import IImageProcessingMode

logger = logging.getLogger(__name__)


class DebugMode(IImageProcessingMode):
    """
    Mode for debug visualization and information display.
    Handles debug overlay rendering and debug-specific interactions.
    """

    def __init__(self, state_manager, view_ref: QGraphicsView | None = None):
        super().__init__(state_manager, view_ref)

    def handle_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse press - debug mode doesn't consume press events."""
        return False

    def handle_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse move - debug mode doesn't consume move events."""
        return False

    def handle_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse release - debug mode doesn't consume release events."""
        return False

    def handle_draw_foreground(self, painter: QPainter, rect: QRectF) -> bool:
        """Handle debug foreground drawing."""
        if not self.state.debug_mode or not self.view_ref:
            return False

        painter.save()
        painter.setPen(QColor("yellow"))

        # Use view coordinates for text overlay
        view_rect = self.view_ref.viewport().rect()
        text_flags = (
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
        )

        debug_text = self._generate_debug_text()

        # Draw debug text in the top-left corner
        painter.drawText(
            QRectF(5, 5, view_rect.width() - 10, view_rect.height()), text_flags, debug_text
        )

        painter.restore()
        return True

    def _generate_debug_text(self) -> str:
        """Generate debug information text."""
        debug_text = "--- DEBUG INFO ---\n"

        # Image information
        if self.state.current_image_pixmap:
            pixmap_size = self.state.current_image_pixmap.size()
            debug_text += f"Image: {pixmap_size.width()}x{pixmap_size.height()}\n"
            debug_text += f"Path: {self.state.current_image_path}\n"
        else:
            debug_text += "Image: Not Loaded\n"

        # Bounding box information
        if self.state.bounding_box:
            bb = self.state.bounding_box
            bb_w = bb["right"] - bb["left"]
            bb_h = bb["bottom"] - bb["top"]
            debug_text += f"Bounding Box: {bb_w}x{bb_h}\n"
            debug_text += f"Center: {self.state.bb_center}\n"
        else:
            debug_text += "Bounding Box: Not Loaded\n"

        # View information
        if self.view_ref:
            view_rect = self.view_ref.viewport().rect()
            visible_scene_rect = self.view_ref.mapToScene(view_rect).boundingRect()
            debug_text += f"View: {view_rect.width()}x{view_rect.height()}\n"
            debug_text += f"Visible Scene: {visible_scene_rect.width():.1f}x{visible_scene_rect.height():.1f}\n"

        # State information
        debug_text += f"Mode: {self.state.current_mode.value}\n"
        debug_text += f"Zoom: {self.state.zoom_level:.2f}x\n"
        debug_text += f"Unit: {self.state.display_unit}\n"
        debug_text += f"DPI: {self.state.dpi}\n"

        # Parts information
        debug_text += f"Parts: {len(self.state.part_items)}\n"
        debug_text += f"Joint Map: {len(self.state.joint_to_part_map)}\n"

        return debug_text

    def get_cursor(self):
        """Return cursor for debug mode."""
        return Qt.CursorShape.ArrowCursor

    def enter_mode(self) -> None:
        """Setup when entering debug mode."""
        logger.debug("Entered debug mode")

    def exit_mode(self) -> None:
        """Cleanup when exiting debug mode."""
        logger.debug("Exited debug mode")

    def update_mode_state(self) -> None:
        """Update debug mode state."""
        # No periodic updates needed for debug mode
        pass
