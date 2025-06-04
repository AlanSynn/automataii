import os
import logging
import yaml
from PyQt6.QtWidgets import QGraphicsView, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsLineItem
from PyQt6.QtGui import QPainter, QPixmap, QColor, QBrush, QPen
from PyQt6.QtCore import Qt, QPointF, QLineF, QEvent, QRectF
import math # Added for math.sqrt and math.atan2 if needed, though QLineF handles length
from typing import List, Optional, Dict, Tuple, Any
import numpy as np
import cv2 # Added for cv2.findContours etc.
from PyQt6.QtWidgets import QApplication

from ...core.models import PartInfo
from ...utils.svg_utils import contour_to_svg_path
from ..graphics_items.part_item import CharacterPartItem # UPDATED
# from .graphics_items.skeleton_item import SkeletonJoint, SkeletonLine # UPDATED # Commented out
from ..graphics_items.anchor_item import AnchorItem # UPDATED (if it was moved, otherwise adjust)

# --- Helper Functions for Vector Math (can be static or outside class) ---
def normalize_vector(vector: QPointF) -> QPointF:
    """Normalizes a QPointF vector."""
    line = QLineF(QPointF(0, 0), vector)
    length = line.length()
    if length == 0:
        return QPointF(0, 0)
    return vector / length

def perpendicular_vector(vector: QPointF) -> QPointF:
    """Returns a vector perpendicular to the input vector (rotated 90 deg counter-clockwise)."""
    return QPointF(-vector.y(), vector.x())
# --- End Helper Functions ---

class ImageProcessingView(QGraphicsView):
    """View for displaying the input image and editing the skeleton overlay.

    Manages loading images, loading/saving skeleton data, and skeleton interaction.
    Provides zooming and panning functionality.
    """
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Set background color to gray
        # self.setBackgroundBrush(QBrush(QColor(200, 200, 200), Qt.BrushStyle.SolidPattern)) # REMOVED

        # Zoom/Pan setup
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        # Touch/Pinch setup
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.grabGesture(Qt.GestureType.PinchGesture)
        self._pinch_mode = False
        self._pinch_start_view_scale = 1.0

        # Scene items management
        self.image_item = None
        self.joints = {} # Dict mapping joint name (str) to SkeletonJoint
        self.joint_labels = {} # Dict mapping joint name (str) to QGraphicsTextItem
        self.lines = [] # List of SkeletonLine items

        # Interactive Character Parts in this view
        self.part_items: Dict[str, CharacterPartItem] = {}
        self.joint_to_part_map: Dict[str, CharacterPartItem] = {} # Maps skeleton joint name to its controlling CharacterPartItem
        self.skeleton_to_part_map: Dict[str, str] = {} # Initialize skeleton_to_part_map

        # Data state
        self.original_skeleton_data = None # Store the originally loaded data format
        self.bounding_box = None
        self.bb_center = None
        self._skeleton_viz_items = [] # List of temporary skeleton visualization items

        # Debugging
        self.debug_mode = False
        self.debug_bb_item = None # QGraphicsRectItem for bounding box
        self.char_cfg_origin_marker = None # Marker for char_cfg origin

        # Perpendicular Cut Guides
        self.current_guide_lines = [] # To store QGraphicsLineItems for guides
        self.last_active_joint_for_guide = None

        # For dragging joints
        # self.dragged_joint_item: Optional[SkeletonJoint] = None # Commented out
        self.dragged_joint_item = None # Keep attribute, but type is now generic
        self.drag_start_pos: Optional[QPointF] = None
        self.drag_start_pos_offset: Optional[QPointF] = None

        # Zoom control variables (new, similar to EditorView)
        self._zoom_level = 0
        self._zoom_factor_base = 1.05 # Base factor for low sensitivity (each step is 5% zoom)
        self._min_zoom_level = -47 # Approx 1.05^-47 ~= 0.1
        self._max_zoom_level = 47  # Approx 1.05^47 ~= 10.0

        # Rounded corners and white background for the viewport
        self.viewport().setStyleSheet("background-color: white; border-radius: 10px;")

        # Unit and DPI settings
        self.display_unit = "cm"  # Default unit: 'cm', 'inch', or 'px'
        try:
            self.dpi = QApplication.primaryScreen().logicalDotsPerInch()
        except AttributeError:
            self.dpi = 96 # Common default DPI
            logging.warning(f"Could not get screen DPI, defaulting to {self.dpi} DPI.")
        logging.info(f"ImageProcessingView initialized with DPI: {self.dpi}, default unit: {self.display_unit}")

    def set_display_unit(self, unit: str):
        """Sets the display unit for the grid and updates the view."""
        if unit.lower() in ["cm", "inch", "px"]:
            self.display_unit = unit.lower()
            logging.info(f"ImageProcessingView: Display unit set to {self.display_unit}")
            self.viewport().update() # Trigger a repaint of the background
        else:
            logging.warning(f"ImageProcessingView: Invalid display unit '{unit}'. Using current: {self.display_unit}")

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draws a grid background based on the current display unit."""
        super().drawBackground(painter, rect) # Draw the default background first

        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.display_unit == "cm":
            cm_to_inch = 1 / 2.54
            grid_size_pixels = int(self.dpi * cm_to_inch) # 1 cm in pixels
        elif self.display_unit == "inch":
            grid_size_pixels = int(self.dpi) # 1 inch in pixels
        else: # Default to pixels or if unit is 'px'
            grid_size_pixels = 20 # Default pixel grid size

        if grid_size_pixels <= 0: # Safety check
            grid_size_pixels = 20
            logging.warning(f"Calculated grid size is invalid ({grid_size_pixels}), defaulting to 20px.")

        light_pen = QPen(QColor(230, 230, 230), 1)
        dark_pen = QPen(QColor(200, 200, 200), 1.5)

        major_interval = 1 if self.display_unit in ["cm", "inch"] else 5

        visible_rect = self.mapToScene(self.viewport().rect()).boundingRect()

        left = int(visible_rect.left() / grid_size_pixels) * grid_size_pixels
        top = int(visible_rect.top() / grid_size_pixels) * grid_size_pixels
        right = visible_rect.right()
        bottom = visible_rect.bottom()

        x = left
        count_v = int(round(visible_rect.left() / grid_size_pixels))
        while x < right:
            painter.setPen(dark_pen if count_v % major_interval == 0 else light_pen)
            painter.drawLine(QLineF(x, top, x, bottom))
            x += grid_size_pixels
            count_v += 1

        y = top
        count_h = int(round(visible_rect.top() / grid_size_pixels))
        while y < bottom:
            painter.setPen(dark_pen if count_h % major_interval == 0 else light_pen)
            painter.drawLine(QLineF(left, y, right, y))
            y += grid_size_pixels
            count_h += 1

        painter.restore()

    # --- Debugging Methods ---

    def set_debug_mode(self, enable: bool):
        """Enables or disables the debug drawing mode."""
        if self.debug_mode == enable:
            return
        self.debug_mode = enable
        logging.info(f"Debug mode set to: {self.debug_mode}")
        if self.debug_bb_item:
            self.debug_bb_item.setVisible(self.debug_mode)
        # Also toggle char_cfg marker visibility if it exists
        if self.char_cfg_origin_marker:
            self.char_cfg_origin_marker.setVisible(self.debug_mode)
        # Trigger a repaint to update foreground drawing
        self.viewport().update()

    def _clear_debug_items(self):
        """Removes debug-related graphics items from the scene."""
        if self.debug_bb_item and self.debug_bb_item.scene():
            self.scene().removeItem(self.debug_bb_item)
        self.debug_bb_item = None
        # Trigger repaint if debug mode is on to clear text
        if self.debug_mode:
            self.viewport().update()

    # --- Event Handling (Zoom/Pan/Gestures) ---

    def viewportEvent(self, event: QEvent):
        """Handle gesture events."""
        if event.type() == QEvent.Type.Gesture:
            return self.gestureEvent(event)
        return super().viewportEvent(event)

    def gestureEvent(self, event: QEvent):
        """Handle pinch gestures."""
        gesture = event.gesture(Qt.GestureType.PinchGesture)
        if gesture:
            self._pinch_triggered(gesture)
            return True
        return super().viewportEvent(event) # Pass other gestures

    def _pinch_triggered(self, gesture):
        """Handle pinch gesture logic for zooming."""
        if gesture.state() == Qt.GestureState.GestureStarted:
            self._pinch_mode = True
            self._pinch_start_view_scale = self.transform().m11()
        elif gesture.state() == Qt.GestureState.GestureUpdated and self._pinch_mode:
            target_scale = self._pinch_start_view_scale * gesture.scaleFactor()

            # Clamp the target scale
            target_scale = max(self._zoom_factor_base ** self._min_zoom_level, min(target_scale, self._zoom_factor_base ** self._max_zoom_level))
            target_scale = max(0.1, min(target_scale, 10.0)) # Absolute limits

            current_view_scale = self.transform().m11()
            if abs(target_scale - current_view_scale) > 0.001:
                 zoom_factor_to_apply = target_scale / current_view_scale
                 self.scale(zoom_factor_to_apply, zoom_factor_to_apply)
        elif gesture.state() == Qt.GestureState.GestureFinished:
            self._pinch_mode = False
            # Update zoom level to closest discrete step after pinch zooming
            current_scale = self.transform().m11()
            if current_scale > 0 and self._zoom_factor_base > 1 and self._zoom_factor_base != 0:
                closest_zoom_level = round(math.log(current_scale, self._zoom_factor_base))
                self._zoom_level = max(self._min_zoom_level, min(closest_zoom_level, self._max_zoom_level))

    def zoom(self, step: int):
        """Zooms the view by a given step, adjusting the discrete zoom level."""
        if step == 0:
            return

        new_zoom_level = self._zoom_level + step
        new_zoom_level = max(self._min_zoom_level, min(new_zoom_level, self._max_zoom_level))

        if new_zoom_level != self._zoom_level:
            current_scale = self.transform().m11()
            target_scale = self._zoom_factor_base ** new_zoom_level
            target_scale = max(0.1, min(target_scale, 10.0)) # Absolute limits

            if abs(target_scale - current_scale) < 0.00001 and ((step > 0 and self._zoom_level == self._max_zoom_level) or (step < 0 and self._zoom_level == self._min_zoom_level)):
                self._zoom_level = new_zoom_level # Ensure level is updated
                return

            if current_scale <= 0: # Safeguard
                self.resetTransform()
                current_scale = 1.0
                self._zoom_level = 0
                effective_step = max(self._min_zoom_level, min(step, self._max_zoom_level)) if step != 0 else 0
                new_zoom_level = self._zoom_level + effective_step
                new_zoom_level = max(self._min_zoom_level, min(new_zoom_level, self._max_zoom_level))
                target_scale = self._zoom_factor_base ** new_zoom_level
                target_scale = max(0.1, min(target_scale, 10.0))

            factor_to_apply = target_scale / current_scale if current_scale != 0 else target_scale
            if abs(factor_to_apply - 1.0) > 0.000001:
                self.scale(factor_to_apply, factor_to_apply)

            self._zoom_level = new_zoom_level
            # self.zoom_changed.emit(self.transform().m11()) # ImageProcessingView does not have this signal by default
            self.scene().update()

    def wheelEvent(self, event):
        """Handle mouse wheel for zooming based on discrete zoom levels."""
        if self._pinch_mode:
            return

        delta = event.angleDelta().y()
        step = 0
        if delta > 0:
            step = 1
        elif delta < 0:
            step = -1

        self.zoom(step)

    def drawForeground(self, painter: QPainter, rect: QRectF):
        """Draws debug information on top of the view."""
        super().drawForeground(painter, rect)

        if not self.debug_mode:
            return

        painter.save()
        painter.setPen(QColor("yellow"))
        # Use view coordinates for text overlay
        view_rect = self.viewport().rect()
        text_flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
        text_margin = 5
        current_y = text_margin

        debug_text = "--- DEBUG INFO ---\n"

        if self.image_item:
            pixmap_size = self.image_item.pixmap().size()
            scene_pos = self.image_item.scenePos()
            scene_rect = self.image_item.sceneBoundingRect()
            debug_text += f"Image:\n"
            debug_text += f"  Orig Size: {pixmap_size.width()}x{pixmap_size.height()}\n"
            debug_text += f"  Scene Pos: ({scene_pos.x():.1f}, {scene_pos.y():.1f})\n"
            debug_text += f"  Scene Rect: ({scene_rect.left():.1f}, {scene_rect.top():.1f}) W: {scene_rect.width():.1f} H: {scene_rect.height():.1f}\n"
        else:
            debug_text += "Image: Not Loaded\n"

        if self.bounding_box:
            bb = self.bounding_box
            bb_w = bb['right'] - bb['left']
            bb_h = bb['bottom'] - bb['top']
            debug_text += f"Bounding Box (Loaded):\n"
            debug_text += f"  L: {bb['left']} R: {bb['right']} T: {bb['top']} B: {bb['bottom']}\n"
            debug_text += f"  W: {bb_w} H: {bb_h}\n"
            if self.bb_center:
                 debug_text += f"  Center: ({self.bb_center[0]:.1f}, {self.bb_center[1]:.1f})\n"
        else:
            debug_text += "Bounding Box: Not Loaded\n"

        # View information
        visible_scene_rect = self.mapToScene(view_rect).boundingRect()
        debug_text += f"View:\n"
        debug_text += f"  Viewport Rect: {view_rect.width()}x{view_rect.height()}\n"
        debug_text += f"  Visible Scene Rect: ({visible_scene_rect.left():.1f}, {visible_scene_rect.top():.1f}) W: {visible_scene_rect.width():.1f} H: {visible_scene_rect.height():.1f}\n"
        # Draw text in the top-left corner of the viewport
        painter.drawText(QRectF(text_margin, current_y, view_rect.width() - 2 * text_margin, view_rect.height()), text_flags, debug_text)

        painter.restore()

    # --- Image and Skeleton Loading ---

    def load_image(self, image_path: str):
        """Loads and displays an image, clearing previous non-skeleton items."""
        if not self.scene():
            logging.error("ImageProcessingView has no scene.")
            return False

        logging.info(f"Loading image: {image_path}")

        # Clear previous items BEFORE loading new ones
        self._clear_skeleton() # Clear skeleton first
        self._clear_debug_items() # Clear debug items
        if self.image_item:
            self.scene().removeItem(self.image_item)
            self.image_item = None

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            logging.error(f"Failed to load image from: {image_path}")
            return False

        logging.info(f"Image loaded successfully ({pixmap.width()}x{pixmap.height()})")
        self.image_item = self.scene().addPixmap(pixmap)
        self.image_item.setZValue(0) # Ensure image is behind skeleton
        logging.info(f"Image item location from canvas: {self.image_item.pos().x()}, {self.image_item.pos().y()}")
        logging.info(f"Image item location from scene: {self.image_item.scenePos().x()}, {self.image_item.scenePos().y()}")

        if self.debug_mode:
            # Get the scene's bounding rect
            scene_rect = self.scene().itemsBoundingRect()
            logging.info(f"Scene bounding rect: {scene_rect.x()}, {scene_rect.y()}, {scene_rect.width()}, {scene_rect.height()}")

            # Draw the scene rect outline
            rect_item = QGraphicsRectItem(scene_rect)
            rect_item.setPen(QPen(QColor("red"), 2))
            # rect_item.setBrush(Qt.BrushStyle(NoBrush))
            rect_item.setZValue(1) # Ensure it's drawn above the image but below joints potentially
            self.scene().addItem(rect_item)

        # Clear joint labels if reloading image
        self._clear_joint_labels()
        self._clear_char_cfg_marker()
        self.clear_character_parts() # Clear interactive parts as well
        # Attempt to load associated bounding box data
        self._load_bounding_box(image_path)

        self.reset_view() # Fit image in view
        return True

    def _clear_joint_labels(self):
        """Removes all joint label text items from the scene."""
        for label_item in self.joint_labels.values():
            if label_item.scene():
                self.scene().removeItem(label_item)
        self.joint_labels.clear()

    def _load_bounding_box(self, image_path: str):
        """Loads bounding box data from a YAML file and creates debug rectangle."""
        # Clear previous debug items first
        self._clear_debug_items()
        self.bounding_box = None # Initialize to None
        self.bb_center = None

        if not self.image_item:
            logging.warning("Cannot load bounding box without an image item.")
            return

        loaded_bb_data = None # Temporary variable for loaded data
        try:
            # Infer character_data path relative to the image
            base_dir = os.path.dirname(image_path)
            char_data_dir = os.path.join(base_dir, "character_data")
            if not os.path.isdir(char_data_dir):
                # Maybe image is already in character_data?
                if os.path.basename(base_dir) == "character_data":
                    char_data_dir = base_dir
                else: # Fallback: assume it's one level up
                    char_data_dir = os.path.join(os.path.dirname(base_dir),
                    "character_data")
                # logging.warning(f"No character_data directory found near {image_path}")
                # return

            bb_file = os.path.join(char_data_dir, "bounding_box.yaml") if os.path.isdir(char_data_dir) else None

            if bb_file and os.path.exists(bb_file):
                with open(bb_file, 'r') as f:
                    loaded_bb_data = yaml.safe_load(f)
                # Validate format *after* loading
                if not (loaded_bb_data and all(k in loaded_bb_data for k in ['left', 'right', 'top', 'bottom'])):
                    logging.warning(f"Invalid bounding box format in {bb_file}")
                    loaded_bb_data = None # Reset to None if format is invalid
            else:
                 logging.info(f"No bounding_box.yaml found near {image_path}")
                 # loaded_bb_data remains None
        except Exception as e:
            logging.error(f"Error loading bounding box data: {e}")
            loaded_bb_data = None # Ensure it's None on error

        # Assign to self.bounding_box only if data was loaded and validated
        self.bounding_box = loaded_bb_data

        # Process and create debug item only if self.bounding_box is valid
        if self.bounding_box:
            try:
                bb_left = self.bounding_box['left']
                bb_top = self.bounding_box['top']
                bb_right = self.bounding_box['right']
                bb_bottom = self.bounding_box['bottom']
                bb_w = bb_right - bb_left
                bb_h = bb_bottom - bb_top

                self.bb_center = ( (bb_left + bb_right) / 2, (bb_top + bb_bottom) / 2 )
                logging.info(f"Loaded bounding box: {self.bounding_box}, Center: {self.bb_center}")

                # Create the debug rectangle item ONLY if dimensions are valid
                if bb_w > 0 and bb_h > 0:
                    self.debug_bb_item = QGraphicsRectItem(bb_left, bb_top, bb_w, bb_h)
                    self.debug_bb_item.setParentItem(self.image_item)
                    pen = QPen(QColor("blue"), 2)
                    pen.setCosmetic(True)
                    self.debug_bb_item.setPen(pen)
                    # self.debug_bb_item.setBrush(Qt.BrushStyle.NoBrush)
                    self.debug_bb_item.setZValue(1)
                    self.debug_bb_item.setVisible(self.debug_mode)
                    logging.info("Created debug bounding box rectangle.")
                else:
                    logging.warning(f"Invalid bounding box dimensions (W={bb_w}, H={bb_h}), cannot create debug rectangle.")
                    self.bounding_box = None # Treat as invalid if dimensions are bad
                    self.bb_center = None
            except KeyError as ke:
                logging.error(f"Missing key in bounding_box data: {ke}")
                self.bounding_box = None # Treat as invalid if keys are missing
                self.bb_center = None
        # No need for else block, self.bounding_box is already None if loading failed

        # Update viewport if debug mode is on (to refresh text overlay)
        if self.debug_mode:
            self.viewport().update()

    def load_skeleton(self, skeleton_data_dict: Optional[dict]):
        """Loads skeleton data and visualizes it.
        'skeleton_data_dict' is expected to be the direct output of yaml.safe_load from char_cfg.yaml
        or a similar dictionary structure.
        Example: {'skeleton': [{'name': 'hip', 'parent': None, 'loc': [0,0]}, ...], 'scale': 1.0, 'offset': [0,0]}
        """
        if not self.scene() or not self.image_item:
            logging.error("Scene or image_item not available for skeleton loading.")
            return False

        # Handle None input gracefully
        if skeleton_data_dict is None:
            logging.info("ImageProcessingView: load_skeleton called with None. Clearing skeleton.")
            self._clear_skeleton() # Clear previous skeleton visuals and data
            self.original_skeleton_data = None
            self.scene().update()
            return True # Successfully handled None by clearing

        logging.info(f"ImageProcessingView: load_skeleton called with keys: {list(skeleton_data_dict.keys()) if skeleton_data_dict else 'None'}")
        self._clear_skeleton() # Clear previous skeleton visuals and data

        self.original_skeleton_data = skeleton_data_dict # Store the raw data

        char_cfg_skeleton_list = skeleton_data_dict.get('skeleton')
        if not isinstance(char_cfg_skeleton_list, list):
            logging.error(f"Skeleton data format error: 'skeleton' key not found or not a list. Got: {type(char_cfg_skeleton_list)}")
            self.original_skeleton_data = None # Clear if format is bad
            return False

        # --- Placeholder for non-interactive visualization (if needed directly in this view) ---
        # This section can be expanded if a simple, non-editable overlay is desired here.
        # For now, the primary purpose is to process and hold self.original_skeleton_data.
        # Interactive editing was via SkeletonJoint/SkeletonLine, which are removed.

        # Example of how you might store joint positions if needed by other parts of this view:
        # temp_joint_positions = {}
        # for joint_data in char_cfg_skeleton_list:
        #     name = joint_data.get('name')
        #     loc = joint_data.get('loc')
        #     if name and loc and len(loc) == 2:
        #         # These positions are relative to char_cfg origin/bounding box
        #         # They would need transformation to scene coordinates if drawn directly.
        #         temp_joint_positions[name] = QPointF(loc[0], loc[1])
        # logging.info(f"ImageProcessingView: Parsed {len(temp_joint_positions)} joint positions (raw from char_cfg).")
        # --- End Placeholder ---

        # Mark that skeleton data is "loaded" for this view, even if not fully visualized interactively.
        logging.info("ImageProcessingView: Skeleton data processed (raw data stored). Interactive editing is disabled.")
        self.scene().update()
        return True # Indicate success in processing the data format

    def _clear_char_cfg_marker(self):
        """Removes the char_cfg origin marker from the scene."""
        if self.char_cfg_origin_marker:
            # Remove from scene if it's added (it might just have a parent)
            if self.char_cfg_origin_marker.scene():
                self.scene().removeItem(self.char_cfg_origin_marker)
            self.char_cfg_origin_marker = None

    def _clear_skeleton(self):
        """Clears skeleton-related items (joints, lines, labels) from the scene."""
        for joint in self.joints.values():
            if joint.scene():
                self.scene().removeItem(joint)
        self.joints.clear()

        for line in self.lines:
            if line.scene():
                self.scene().removeItem(line)
        self.lines.clear()
        self._clear_joint_labels()
        self._clear_char_cfg_marker()
        self.clear_character_parts() # Also clear character parts when skeleton is cleared

    # --- Skeleton Data Retrieval ---

    def get_skeleton_data(self):
        """Returns the current skeleton data, preserving original format if possible.

        Coordinates are *not* transformed back to original space; they remain
        relative to the loaded image coordinate system.
        """
        if not self.joints:
            return None

        output_data = {}
        output_skeleton = None

        # Try to preserve original structure
        if self.original_skeleton_data:
            output_data = self.original_skeleton_data.copy() # Preserve other keys
            original_structure = self.original_skeleton_data.get('skeleton')

            if isinstance(original_structure, list):
                output_skeleton = []
                original_map = {j.get('name'): j for j in original_structure if j.get('name')} # Map for easy lookup
                for name, skel_joint in self.joints.items():
                    # Update existing or add new
                    new_joint_data = original_map.get(name, {'name': name}).copy()
                    new_joint_data['loc'] = [int(skel_joint.pos().x()), int(skel_joint.pos().y())]
                    # Preserve parent if it existed
                    if 'parent' not in new_joint_data:
                        new_joint_data['parent'] = None # Or try to infer?
                    output_skeleton.append(new_joint_data)

            elif isinstance(original_structure, dict):
                output_skeleton = {} # Keep dict structure
                for name, skel_joint in self.joints.items():
                     # Update existing or add new
                    new_joint_data = original_structure.get(name, {}).copy()
                    new_joint_data['x'] = int(skel_joint.pos().x())
                    new_joint_data['y'] = int(skel_joint.pos().y())
                    output_skeleton[name] = new_joint_data
                # Preserve bone_list if it exists
                if 'bone_list' in self.original_skeleton_data:
                     output_data['bone_list'] = self.original_skeleton_data['bone_list']

        # Fallback: create list format if no original data
        if output_skeleton is None:
            output_skeleton = []
            for name, skel_joint in self.joints.items():
                output_skeleton.append({
                    'name': name,
                    'loc': [int(skel_joint.pos().x()), int(skel_joint.pos().y())],
                    'parent': None # Cannot easily infer parent here
                })

        output_data['skeleton'] = output_skeleton
        return output_data

    # --- View Control ---

    def reset_view(self):
        """Resets the view transformation and fits the image if available."""
        self.resetTransform()
        self._zoom_level = 0 # Reset zoom level
        if self.image_item:
            # Fit content slightly zoomed out
            rect = self.image_item.boundingRect()
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.scale(0.95, 0.95) # Zoom out slightly
            self.centerOn(rect.center())
            # After fitInView, update _zoom_level to match the new scale
            current_scale = self.transform().m11()
            if current_scale > 0 and self._zoom_factor_base > 1 and self._zoom_factor_base != 0:
                self._zoom_level = round(math.log(current_scale, self._zoom_factor_base))
                self._zoom_level = max(self._min_zoom_level, min(self._zoom_level, self._max_zoom_level))
            else:
                self._zoom_level = 0
        elif self.joints: # Fit skeleton if no image
             rect = self.scene().itemsBoundingRect()
             if rect.isValid(): self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_to_fit(self):
        """Zoom to fit all items in the view."""
        if self.image_item:
            # Fit image with some padding
            rect = self.image_item.boundingRect()
            if rect.isValid():
                padding = 20
                rect.adjust(-padding, -padding, padding, padding)
                self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
                # After fitInView, update _zoom_level to match the new scale
                current_scale = self.transform().m11()
                if current_scale > 0 and self._zoom_factor_base > 1 and self._zoom_factor_base != 0:
                    self._zoom_level = round(math.log(current_scale, self._zoom_factor_base))
                    self._zoom_level = max(self._min_zoom_level, min(self._zoom_level, self._max_zoom_level))
                else:
                    self._zoom_level = 0
        elif self.scene(): # Fallback to scene bounding rect if no image_item
            rect = self.scene().itemsBoundingRect()
            if rect.isValid():
                padding = 20
                rect.adjust(-padding, -padding, padding, padding)
                self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
                current_scale = self.transform().m11()
                if current_scale > 0 and self._zoom_factor_base > 1 and self._zoom_factor_base != 0:
                    self._zoom_level = round(math.log(current_scale, self._zoom_factor_base))
                    self._zoom_level = max(self._min_zoom_level, min(self._zoom_level, self._max_zoom_level))
                else:
                    self._zoom_level = 0

    def visualize_skeleton(self, skeleton_data: dict, joint_items: list = None):
        """Temporarily draws the skeleton structure on the scene."""
        self._clear_skeleton_visualization() # Clear previous visualization

        if not skeleton_data or 'skeleton' not in skeleton_data or not isinstance(skeleton_data['skeleton'], list):
            logging.warning("visualize_skeleton called with invalid or missing skeleton data.")
            return

        skeleton_list = skeleton_data['skeleton']
        joint_locations = {j['name']: QPointF(float(j['loc'][0]), float(j['loc'][1]))
                           for j in skeleton_list if j.get('name') and j.get('loc') and len(j.get('loc')) >= 2}

        bone_pen = QPen(QColor("#FF5733"), 2, Qt.PenStyle.SolidLine) # Bright orange for bones
        joint_brush = QBrush(QColor("#FFC300")) # Yellow for joints
        joint_pen = QPen(QColor("#C70039"), 1)    # Dark red outline for joints
        joint_radius = 4

        # Draw bones
        for joint_info in skeleton_list:
            child_name = joint_info.get('name')
            parent_name = joint_info.get('parent')

            if child_name in joint_locations and parent_name and parent_name in joint_locations:
                p1 = joint_locations[parent_name]
                p2 = joint_locations[child_name]
                bone_line = QGraphicsLineItem(QLineF(p1, p2))
                bone_line.setPen(bone_pen)
                bone_line.setZValue(500) # Draw on top
                self.scene().addItem(bone_line)
                self._skeleton_viz_items.append(bone_line)

        # Draw joints (circles)
        for name, loc in joint_locations.items():
            joint_circle = QGraphicsEllipseItem(loc.x() - joint_radius, loc.y() - joint_radius,
                                                joint_radius * 2, joint_radius * 2)
            joint_circle.setBrush(joint_brush)
            joint_circle.setPen(joint_pen)
            joint_circle.setZValue(501) # Draw on top of bones
            self.scene().addItem(joint_circle)
            self._skeleton_viz_items.append(joint_circle)

        logging.info(f"Visualizing skeleton with {len(joint_locations)} joints and associated bones.")

    def _clear_skeleton_visualization(self):
        """Clears temporary skeleton visualization items (not the interactive ones)."""
        for item in self._skeleton_viz_items:
            if item.scene():
                self.scene().removeItem(item)
        self._skeleton_viz_items.clear()

    def _update_joint_label_position(self, joint_name: str):
        """Updates the position of a joint's label based on the joint's current position."""
        if joint_name in self.joints and joint_name in self.joint_labels:
            joint_item = self.joints[joint_name]
            label_item = self.joint_labels[joint_name]
            label_item.setPos(joint_item.pos() + QPointF(5, -10))

    def _update_lines(self, joint_item):
        """Updates the lines connected to a moved joint."""
        # joint_item: SkeletonJoint # Commented out type hint
        """Updates lines connected to the moved joint."""
        # for line in self.lines[:]: # Iterate over a copy
        #     if line.joint1 == joint_item or line.joint2 == joint_item:
        #         line.update_position()
        pass # Placeholder

    def get_lines_connected_to_joint(self, target_joint):
        # target_joint: SkeletonJoint # Commented out type hint
        """Returns a list of SkeletonLine items connected to the target joint."""
        # connected_lines = []
        # for line in self.lines:
        #     if line.joint1 == target_joint or line.joint2 == target_joint:
        #         connected_lines.append(line)
        # return connected_lines
        return [] # Return empty list

    def calculate_perpendicular_cut_guide(self, joint):
        # joint: SkeletonJoint # Commented out type hint
        """Calculates a perpendicular line segment at the joint, oriented along its bone(s)."""
        if not joint or not joint.scene(): # Ensure joint is valid and in scene
            return None

        joint_pos = joint.pos() # This should be in parent (image_item) coordinates

        # If joint's parent is the image_item, map joint_pos to scene coordinates
        # for guide calculation if lines are drawn in scene coordinates directly.
        # However, SkeletonLine uses joint.pos() directly, which are parent-relative.
        # So, if guides are added directly to scene, they need scene coordinates.
        # If guides are parented to image_item, joint_pos is fine.
        # For simplicity, let's assume guides are added to scene directly.
        # If image_item exists and joint is its child, transform:
        # if self.image_item and joint.parentItem() == self.image_item:
        #     joint_scene_pos = self.image_item.mapToScene(joint_pos)
        # else:
        #     joint_scene_pos = joint.scenePos() # Fallback if not parented as expected

        # The SkeletonLines connect joints using their pos() which is parent-relative.
        # So vectors between joint.pos() values are correct in image_item's coord system.
        # The guide line itself, if added to the scene directly, will need scene coordinates.

        connected_lines = self.get_lines_connected_to_joint(joint)

        guide_direction = QPointF(0,0)

        if not connected_lines:
            logging.debug(f"No connected lines for joint {joint.joint_name} to calculate guide.")
            return None

        if len(connected_lines) == 1:
            # Terminal joint (connected to one bone)
            line = connected_lines[0]
            other_joint = line.joint1 if line.joint2 == joint else line.joint2
            if not other_joint: return None

            bone_vector = other_joint.pos() - joint_pos # Vector in image_item coordinates
            guide_direction = perpendicular_vector(bone_vector)

        else: # len(connected_lines) >= 2 (intermediate joint)
            # For simplicity, consider the first two connected lines.
            line1 = connected_lines[0]
            other_joint1 = line1.joint1 if line1.joint2 == joint else line1.joint2
            if not other_joint1: return None

            line2 = connected_lines[1]
            other_joint2 = line2.joint1 if line2.joint2 == joint else line2.joint2
            if not other_joint2: return None

            vec1 = other_joint1.pos() - joint_pos # Vector in image_item coordinates
            vec2 = other_joint2.pos() - joint_pos # Vector in image_item coordinates

            norm_vec1 = normalize_vector(vec1)
            norm_vec2 = normalize_vector(vec2)

            if (norm_vec1 + norm_vec2).isNull():
                guide_direction = perpendicular_vector(norm_vec1)
            else:
                bisector_direction = normalize_vector(norm_vec1 + norm_vec2)
                guide_direction = perpendicular_vector(bisector_direction)

        if guide_direction.isNull():
            logging.debug(f"Guide direction is null for {joint.joint_name}")
            return None

        normalized_guide_dir = normalize_vector(guide_direction)
        guide_length = 60  # pixels in local image_item scale

        # Guide line points are relative to the joint's position (which is in image_item coords)
        p1_local = joint_pos + normalized_guide_dir * (guide_length / 2)
        p2_local = joint_pos - normalized_guide_dir * (guide_length / 2)

        # If image_item exists, map these local points to scene coordinates
        if self.image_item:
            p1_scene = self.image_item.mapToScene(p1_local)
            p2_scene = self.image_item.mapToScene(p2_local)
            return QLineF(p1_scene, p2_scene)
        else: # Fallback if no image_item, assume joint_pos is already scene_pos (less likely)
            return QLineF(joint_pos + normalized_guide_dir * (guide_length / 2),
                          joint_pos - normalized_guide_dir * (guide_length / 2))

    def update_and_draw_cut_guides(self, active_joint: Optional[Any]): # Changed type hint from SkeletonJoint
        """Updates and draws perpendicular cut guides for the active joint."""
        # Clear existing guide lines
        for item in self.current_guide_lines:
            if item.scene():
                self.scene().removeItem(item)
        self.current_guide_lines = []

        if not active_joint or not self.scene(): # Ensure scene is available
            return

        guide_line_data = self.calculate_perpendicular_cut_guide(active_joint)

        if guide_line_data:
            pen = QPen(QColor("cyan"), 1.5, Qt.PenStyle.DashLine)
            pen.setCosmetic(True) # Keep pen width constant regardless of zoom
            guide_item = self.scene().addLine(guide_line_data, pen)
            guide_item.setZValue(150) # Ensure it's visible above most things
            self.current_guide_lines.append(guide_item)
            logging.debug(f"Drew cut guide for joint {active_joint.joint_name}")

    # --- New methods for managing interactive CharacterPartItems ---
    def clear_character_parts(self):
        """Removes all CharacterPartItem instances from this view's scene."""
        logging.debug(f"ImageProcessingView: Clearing {len(self.part_items)} character part items.")
        for part_item in self.part_items.values():
            if part_item.scene() == self.scene():
                self.scene().removeItem(part_item)
        self.part_items.clear()
        self.joint_to_part_map.clear()

    def load_character_parts(self, parts_data: Dict[str, PartInfo], skeleton_to_part_map: Dict[str, str], effective_bbox_offset: QPointF):
        """
        Loads and displays CharacterPartItems based on parts_data.
        These are interactive parts, distinct from simple skeleton visualization.
        """
        self.clear_character_parts() # Clear existing parts first

        if not self.scene():
            logging.error("ImageProcessingView: Scene not available to load character parts.")
            return

        if not parts_data:
            logging.warning("ImageProcessingView: No parts_data provided to load_character_parts.")
            return

        logging.info(f"ImageProcessingView: Loading {len(parts_data)} character parts.")

        self.skeleton_to_part_map = skeleton_to_part_map # Store the map

        for part_name, part_info_obj in parts_data.items():
            if not isinstance(part_info_obj, PartInfo):
                logging.warning(f"ImageProcessingView: Item '{part_name}' in parts_data is not a PartInfo object. Skipping.")
                continue

            try:
                # Create the CharacterPartItem
                part_item = CharacterPartItem(part_info_obj)

                # Positioning logic (simplified from MainWindow.load_parts, assuming SVGs are self-contained)
                # The key is that PartInfo.roi should be relative to texture.png origin
                # if an image_path is primary, or svg coordinates are relative to (0,0) of part.
                # This view positions relative to the overall texture.png, so bbox_offset is key.

                # Default position is (0,0) minus the effective bbox_offset (aligns texture origin with scene origin)
                item_x = 0.0 # Start with texture origin (0,0)
                item_y = 0.0

                if part_info_obj.roi and len(part_info_obj.roi) == 4:
                    # If ROI exists, part's origin (top-left of its image/svg) is at roi[0], roi[1] within texture.png
                    # So, add roi[0] and roi[1] to the base position.
                    item_x += part_info_obj.roi[0]
                    item_y += part_info_obj.roi[1]
                    logging.debug(f"ImageProcessingView: Positioning '{part_name}' using ROI ({part_info_obj.roi[0]}, {part_info_obj.roi[1]}). Pos: ({item_x}, {item_y})")
                else:
                    # If no ROI, might need a fallback based on a convention (e.g., skeleton joint pos)
                    # For now, it will be at texture origin (0,0) if no ROI
                    logging.debug(f"ImageProcessingView: Positioning '{part_name}' at texture origin (0,0) due to no ROI.")


                part_item.setPos(item_x, item_y)
                part_item.setZValue(10) # Parts above image, below skeleton visuals
                part_item.setVisible(False) # Initially hidden, controlled by a checkbox

                self.scene().addItem(part_item)
                self.part_items[part_name] = part_item

                # Map controlling skeleton joint to this part item
                # Iterate through skeleton_to_part_map to find which skeleton joint controls this part_name
                for skel_joint_name, controlled_part_name in skeleton_to_part_map.items():
                    if controlled_part_name == part_name:
                        self.joint_to_part_map[skel_joint_name] = part_item
                        logging.debug(f"ImageProcessingView: Mapped skeleton joint '{skel_joint_name}' to control part '{part_name}'.")
                        break # Assuming one primary controlling joint per part for simplicity

            except Exception as e:
                logging.error(f"ImageProcessingView: Error creating/loading CharacterPartItem for '{part_name}': {e}")

        logging.info(f"ImageProcessingView: Loaded {len(self.part_items)} part items. Mapped {len(self.joint_to_part_map)} joints to parts.")

    def show_skeleton_visuals(self, show: bool):
        """Shows or hides the skeleton joint and line visuals."""
        for joint_item in self.joints.values():
            joint_item.setVisible(show)
        for label_item in self.joint_labels.values():
            label_item.setVisible(show)
        for line_item in self.lines:
            line_item.setVisible(show)
        logging.debug(f"ImageProcessingView: Skeleton visuals visibility set to {show}")

    def show_part_visuals(self, show: bool):
        """Shows or hides the CharacterPartItem visuals."""
        for part_item in self.part_items.values():
            part_item.setVisible(show)
        logging.debug(f"ImageProcessingView: Character part visuals visibility set to {show}")
        # When showing parts, typically hide the base image texture
        if self.image_item:
            self.image_item.setVisible(not show)

    def mousePressEvent(self, event: QEvent):
        # Check if the click is on a joint
        item = self.itemAt(event.pos())
        # if isinstance(item, SkeletonJoint): # Commented out
        #     self.dragged_joint_item = item
        #     self.drag_start_pos = event.scenePos()
        #     self.drag_start_pos_offset = self.dragged_joint_item.scenePos() - self.drag_start_pos
        #     # Bring to front
        #     self.dragged_joint_item.setZValue(self.dragged_joint_item.zValue() + 1)
        #     self.update_and_draw_cut_guides(self.dragged_joint_item) # Update guides for active joint
        #     return # Consume event if joint is clicked
        # else: # Clicked on background or other item
        #     self.dragged_joint_item = None
        #     self.update_and_draw_cut_guides(None) # Clear guides if no joint is active

        super().mousePressEvent(event) # Call super for panning etc.

    def mouseMoveEvent(self, event: QEvent):
        if self.dragged_joint_item and self.drag_start_pos:
            current_scene_pos = event.scenePos()
            # Calculate new position based on drag start and current mouse position
            # This provides a more direct drag feel compared to just setting item's pos to mouse pos
            # new_pos = self.dragged_joint_item.mapToParent(self.dragged_joint_item.mapFromScene(current_scene_pos + self.drag_start_pos_offset))
            # self.dragged_joint_item.setPos(new_pos) # this was causing issues

            # Simpler: move the joint to the current mouse position in scene coordinates
            self.dragged_joint_item.setPos(current_scene_pos + self.drag_start_pos_offset)

            self._update_lines(self.dragged_joint_item)
            self._update_joint_label_position(self.dragged_joint_item.name) # Update label
            self._update_linked_part_position(self.dragged_joint_item.name, self.dragged_joint_item.scenePos())
            self.update_and_draw_cut_guides(self.dragged_joint_item) # Update guides for active joint
            return # Consume event

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QEvent):
        # if self.dragged_joint_item:
        #     # Reset Z-value
        #     self.dragged_joint_item.setZValue(self.dragged_joint_item.zValue() -1)
        #     self.dragged_joint_item = None
        #     self.drag_start_pos = None
        #     self.drag_start_pos_offset = None
        #     # Do not clear guides here, they stay until another joint is selected or background clicked
        #     # self.update_and_draw_cut_guides(None) # This would clear them
        #     return # Consume event

        super().mouseReleaseEvent(event)

    def _update_linked_part_position(self, joint_name: str, new_joint_scene_pos: QPointF):
        """Moves the CharacterPartItem linked to the given joint name.

        The CharacterPartItem should be moved such that its anchor_offset
        (in its local coordinates) aligns with the new_joint_scene_pos.
        """
        # Determine which part this joint is an anchor for.
        # Convention: 'neck' joint anchors 'head' part, 'left_elbow' anchors 'left_arm_lower'.
        # We need a more direct mapping or a consistent naming convention.
        # For now, let's assume skeleton_to_part_map gives us the part name controlled by this joint.
        # But the key of skeleton_to_part_map is the skeleton joint name, and value is part name.
        # We need to find which *part* has this *joint_name* as its primary anchor.

        # Example logic: if 'head' part has 'neck' as its anchor in its PartInfo or similar.
        # Or iterate through self.part_items and check their anchor logic.

        # For now, let's refine skeleton_to_part_map and assume it means:
        # joint_name (e.g., "neck") controls part_name (e.g., "head").
        # The part_name's anchor_offset is assumed to correspond to this joint_name.

        part_name_to_move = None
        # Find which part is conceptually "attached" to this joint as its anchor
        for pn, pi in self.part_items.items():
            # This requires part_info to store which skeleton joint it's anchored to
            # or a convention like part_name 'head' corresponds to joint 'neck'
            # Let's use the self.skeleton_to_part_map directly for now, assuming it's structured
            # such that skeleton_to_part_map[joint_name] = part_that_this_joint_is_the_anchor_of
            if self.skeleton_to_part_map.get(joint_name) == pn:
                 part_name_to_move = pn
                 break
            # A more robust way might be needed if the map isn't 1-to-1 for this purpose
            # e.g. if "torso" is mapped from multiple skeleton joints.

        # Fallback or more direct logic:
        # If a part's name matches the joint name (e.g., 'head' part and 'head' joint if mapping is like that)
        # or if the convention is that 'neck' joint controls 'head' part.
        # Let's assume self.skeleton_to_part_map[joint_name] gives the correct part.
        part_name_to_move = self.skeleton_to_part_map.get(joint_name)


        if part_name_to_move and part_name_to_move in self.part_items:
            part_item = self.part_items[part_name_to_move]

            # The part_item's anchor_offset is the local point that should align with new_joint_scene_pos.
            # We need to find the new position for the part_item's origin (its top-left in scene).
            # If part_item's origin is at P_origin_scene, and its anchor is at A_local (in its own coords),
            # then A_scene = P_origin_scene + transform.map(A_local).
            # We want A_scene to be new_joint_scene_pos.
            # So, P_origin_scene = new_joint_scene_pos - transform.map(A_local).

            # Get the vector from part_item's origin to its anchor_offset, in scene coordinates (ignoring current part position)
            anchor_vector_in_scene = part_item.transform().map(part_item.anchor_offset) - part_item.transform().map(QPointF(0,0))

            # The new position of the part's origin
            new_part_origin_scene_pos = new_joint_scene_pos - anchor_vector_in_scene
            part_item.setPos(new_part_origin_scene_pos)
            logging.debug(f"Moved part '{part_name_to_move}' to scene pos {part_item.pos()} to align its anchor with joint '{joint_name}' at {new_joint_scene_pos}")
        else:
            logging.debug(f"No part found or mapped to move for joint '{joint_name}'. Searched for part: {part_name_to_move}")