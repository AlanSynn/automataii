"""Debug information rendering for the image view."""

import logging
from typing import Optional
from PyQt6.QtWidgets import QGraphicsRectItem
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QRectF


class DebugRenderer:
    """Handles debug mode rendering and visualization."""
    
    def __init__(self, view):
        self.view = view
        self.debug_mode = False
        self.debug_bb_item: Optional[QGraphicsRectItem] = None
        self.char_cfg_origin_marker = None
    
    def set_debug_mode(self, enable: bool):
        """Enables or disables the debug drawing mode."""
        if self.debug_mode == enable:
            return
        
        self.debug_mode = enable
        logging.info(f"Debug mode set to: {self.debug_mode}")
        
        if self.debug_bb_item:
            self.debug_bb_item.setVisible(self.debug_mode)
        
        if self.char_cfg_origin_marker:
            self.char_cfg_origin_marker.setVisible(self.debug_mode)
        
        # Trigger a repaint to update foreground drawing
        self.view.viewport().update()
    
    def clear_debug_items(self):
        """Removes debug-related graphics items from the scene."""
        if self.debug_bb_item and self.debug_bb_item.scene():
            self.view.scene().removeItem(self.debug_bb_item)
        self.debug_bb_item = None
        
        # Trigger repaint if debug mode is on to clear text
        if self.debug_mode:
            self.view.viewport().update()
    
    def create_bounding_box_debug_item(self, bb_left: float, bb_top: float, 
                                     bb_width: float, bb_height: float,
                                     parent_item=None):
        """Create debug rectangle for bounding box."""
        if bb_width > 0 and bb_height > 0:
            self.debug_bb_item = QGraphicsRectItem(bb_left, bb_top, bb_width, bb_height)
            if parent_item:
                self.debug_bb_item.setParentItem(parent_item)
            
            pen = QPen(QColor("blue"), 2)
            pen.setCosmetic(True)
            self.debug_bb_item.setPen(pen)
            self.debug_bb_item.setZValue(1)
            self.debug_bb_item.setVisible(self.debug_mode)
            logging.info("Created debug bounding box rectangle.")
        else:
            logging.warning(
                f"Invalid bounding box dimensions (W={bb_width}, H={bb_height}), "
                "cannot create debug rectangle."
            )
    
    def draw_debug_info(self, painter: QPainter, rect: QRectF):
        """Draws debug information on top of the view."""
        if not self.debug_mode:
            return
        
        painter.save()
        painter.setPen(QColor("yellow"))
        
        # Use view coordinates for text overlay
        view_rect = self.view.viewport().rect()
        text_flags = (
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap
        )
        text_margin = 5
        current_y = text_margin
        
        debug_text = "--- DEBUG INFO ---\n"
        
        # Image info
        if hasattr(self.view, 'image_item') and self.view.image_item:
            pixmap_size = self.view.image_item.pixmap().size()
            scene_pos = self.view.image_item.scenePos()
            scene_rect = self.view.image_item.sceneBoundingRect()
            debug_text += f"Image:\n"
            debug_text += f"  Orig Size: {pixmap_size.width()}x{pixmap_size.height()}\n"
            debug_text += f"  Scene Pos: ({scene_pos.x():.1f}, {scene_pos.y():.1f})\n"
            debug_text += f"  Scene Rect: ({scene_rect.left():.1f}, {scene_rect.top():.1f}) "
            debug_text += f"W: {scene_rect.width():.1f} H: {scene_rect.height():.1f}\n"
        else:
            debug_text += "Image: Not Loaded\n"
        
        # Bounding box info
        if hasattr(self.view, 'bounding_box') and self.view.bounding_box:
            bb = self.view.bounding_box
            bb_w = bb["right"] - bb["left"]
            bb_h = bb["bottom"] - bb["top"]
            debug_text += f"Bounding Box (Loaded):\n"
            debug_text += f"  L: {bb['left']} R: {bb['right']} T: {bb['top']} B: {bb['bottom']}\n"
            debug_text += f"  W: {bb_w} H: {bb_h}\n"
            if hasattr(self.view, 'bb_center') and self.view.bb_center:
                debug_text += f"  Center: ({self.view.bb_center[0]:.1f}, {self.view.bb_center[1]:.1f})\n"
        else:
            debug_text += "Bounding Box: Not Loaded\n"
        
        # View information
        visible_scene_rect = self.view.mapToScene(view_rect).boundingRect()
        debug_text += f"View:\n"
        debug_text += f"  Viewport Rect: {view_rect.width()}x{view_rect.height()}\n"
        debug_text += f"  Visible Scene Rect: ({visible_scene_rect.left():.1f}, {visible_scene_rect.top():.1f}) "
        debug_text += f"W: {visible_scene_rect.width():.1f} H: {visible_scene_rect.height():.1f}\n"
        
        # Draw text in the top-left corner of the viewport
        painter.drawText(
            QRectF(
                text_margin,
                current_y,
                view_rect.width() - 2 * text_margin,
                view_rect.height(),
            ),
            text_flags,
            debug_text,
        )
        
        painter.restore()
    
    def clear_char_cfg_marker(self):
        """Removes the char_cfg origin marker from the scene."""
        if self.char_cfg_origin_marker:
            if self.char_cfg_origin_marker.scene():
                self.view.scene().removeItem(self.char_cfg_origin_marker)
            self.char_cfg_origin_marker = None