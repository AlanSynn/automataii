"""Image loading and management for the image view."""

import os
import logging
import yaml
from typing import Optional, Dict, Tuple
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem
from PyQt6.QtGui import QPixmap, QPen, QColor
from PyQt6.QtCore import Qt


class ImageManager:
    """Handles image loading and bounding box management."""
    
    def __init__(self, view):
        self.view = view
        self.image_item: Optional[QGraphicsPixmapItem] = None
        self.bounding_box: Optional[Dict] = None
        self.bb_center: Optional[Tuple[float, float]] = None
    
    def load_image(self, image_path: str) -> bool:
        """Loads and displays an image, clearing previous items."""
        if not self.view.scene():
            logging.error("ImageManager: View has no scene.")
            return False
        
        logging.info(f"ImageManager: Loading image: {image_path}")
        
        # Clear previous image
        if self.image_item:
            logging.info("ImageManager: Removing previous image item")
            self.view.scene().removeItem(self.image_item)
            self.image_item = None
        
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            logging.error(f"ImageManager: Failed to load image from: {image_path}")
            return False
        
        logging.info(f"ImageManager: Image loaded successfully ({pixmap.width()}x{pixmap.height()})")
        self.image_item = self.view.scene().addPixmap(pixmap)
        self.image_item.setZValue(0)  # Ensure image is behind skeleton
        
        logging.info(f"ImageManager: Image item added to scene")
        logging.info(f"ImageManager: Scene now has {len(self.view.scene().items())} items")
        logging.info(
            f"ImageManager: Image item location from canvas: {self.image_item.pos().x()}, "
            f"{self.image_item.pos().y()}"
        )
        logging.info(
            f"ImageManager: Image item location from scene: {self.image_item.scenePos().x()}, "
            f"{self.image_item.scenePos().y()}"
        )
        
        # Force scene update
        self.view.scene().update()
        logging.info("ImageManager: Scene update called")
        
        # Load associated bounding box data
        self._load_bounding_box(image_path)
        
        return True
    
    def _load_bounding_box(self, image_path: str):
        """Loads bounding box data from a YAML file."""
        self.bounding_box = None
        self.bb_center = None
        
        if not self.image_item:
            logging.warning("Cannot load bounding box without an image item.")
            return
        
        loaded_bb_data = None
        try:
            # Infer character_data path relative to the image
            base_dir = os.path.dirname(image_path)
            char_data_dir = os.path.join(base_dir, "character_data")
            if not os.path.isdir(char_data_dir):
                # Maybe image is already in character_data?
                if os.path.basename(base_dir) == "character_data":
                    char_data_dir = base_dir
                else:  # Fallback: assume it's one level up
                    char_data_dir = os.path.join(
                        os.path.dirname(base_dir), "character_data"
                    )
            
            bb_file = (
                os.path.join(char_data_dir, "bounding_box.yaml")
                if os.path.isdir(char_data_dir)
                else None
            )
            
            if bb_file and os.path.exists(bb_file):
                with open(bb_file, "r") as f:
                    loaded_bb_data = yaml.safe_load(f)
                # Validate format
                if not (
                    loaded_bb_data
                    and all(
                        k in loaded_bb_data for k in ["left", "right", "top", "bottom"]
                    )
                ):
                    logging.warning(f"Invalid bounding box format in {bb_file}")
                    loaded_bb_data = None
            else:
                logging.info(f"No bounding_box.yaml found near {image_path}")
        except Exception as e:
            logging.error(f"Error loading bounding box data: {e}")
            loaded_bb_data = None
        
        # Assign to bounding_box only if data was loaded and validated
        self.bounding_box = loaded_bb_data
        
        # Process and create debug item only if bounding_box is valid
        if self.bounding_box:
            try:
                bb_left = self.bounding_box["left"]
                bb_top = self.bounding_box["top"]
                bb_right = self.bounding_box["right"]
                bb_bottom = self.bounding_box["bottom"]
                bb_w = bb_right - bb_left
                bb_h = bb_bottom - bb_top
                
                self.bb_center = ((bb_left + bb_right) / 2, (bb_top + bb_bottom) / 2)
                logging.info(
                    f"Loaded bounding box: {self.bounding_box}, Center: {self.bb_center}"
                )
                
                # Notify debug renderer if available
                if hasattr(self.view, 'debug_renderer'):
                    self.view.debug_renderer.create_bounding_box_debug_item(
                        bb_left, bb_top, bb_w, bb_h, self.image_item
                    )
                
            except KeyError as ke:
                logging.error(f"Missing key in bounding_box data: {ke}")
                self.bounding_box = None
                self.bb_center = None
        
        # Update viewport if debug mode is on
        if hasattr(self.view, 'debug_renderer') and self.view.debug_renderer.debug_mode:
            self.view.viewport().update()
    
    def clear(self):
        """Clear all image-related items."""
        if self.image_item and self.image_item.scene():
            self.view.scene().removeItem(self.image_item)
        self.image_item = None
        self.bounding_box = None
        self.bb_center = None