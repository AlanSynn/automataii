import os
import logging
import yaml
from PyQt6.QtWidgets import QGraphicsView, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem
from PyQt6.QtGui import QPainter, QPixmap, QColor, QBrush, QPen
from PyQt6.QtCore import Qt, QPointF, QLineF, QEvent, QRectF
import math # Added for math.sqrt and math.atan2 if needed, though QLineF handles length
from typing import List, Optional # Added List and Optional

from .skeleton_item import SkeletonJoint, SkeletonLine
from ..core.models import JOINT_CONNECTIONS, JOINT_COLORS # Adjust import path

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
        self.setBackgroundBrush(QBrush(QColor(200, 200, 200), Qt.BrushStyle.SolidPattern))

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
        self._pinch_start_scale = 1.0

        # Scene items management
        self.image_item = None
        self.joints = {} # Dict mapping joint name (str) to SkeletonJoint
        self.joint_labels = {} # Dict mapping joint name (str) to QGraphicsTextItem
        self.lines = [] # List of SkeletonLine items

        # Data state
        self.original_skeleton_data = None # Store the originally loaded data format
        self.bounding_box = None
        self.bb_center = None

        # Debugging
        self.debug_mode = False
        self.debug_bb_item = None # QGraphicsRectItem for bounding box
        self.char_cfg_origin_marker = None # Marker for char_cfg origin

        # Perpendicular Cut Guides
        self.current_guide_lines = [] # To store QGraphicsLineItems for guides
        self.last_active_joint_for_guide = None

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
            self._pinch_start_scale = self.transform().m11() * gesture.scaleFactor()
        elif gesture.state() == Qt.GestureState.GestureUpdated and self._pinch_mode:
            target_scale = self._pinch_start_scale * gesture.scaleFactor()
            current_scale = self.transform().m11()
            if abs(target_scale - current_scale) > 0.01:
                 zoom_factor = target_scale / current_scale
                 self.scale(zoom_factor, zoom_factor)
        elif gesture.state() == Qt.GestureState.GestureFinished:
            self._pinch_mode = False

    def wheelEvent(self, event):
        """Handle mouse wheel for zooming when not pinching."""
        if not self._pinch_mode:
            zoom_in = event.angleDelta().y() > 0
            factor = 1.15 if zoom_in else 1 / 1.15
            self.scale(factor, factor)
            self.scene().update()

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

    def load_skeleton(self, skeleton_data_dict: dict):
        """Loads and displays skeleton data from a dictionary.

        Handles different dictionary formats (list-based, dict-based).
        Scales and positions the skeleton based on the loaded image and bounding box.
        """
        if not self.scene() or not self.image_item:
            logging.warning("Cannot load skeleton: Scene or image not ready.")
            return False

        logging.info(f"Loading skeleton data.")
        self.original_skeleton_data = skeleton_data_dict # Store for saving
        self._clear_skeleton()

        pixmap = self.image_item.pixmap()
        img_w, img_h = pixmap.width(), pixmap.height()
        logging.debug(f"Image size: {img_w}x{img_h}")
        logging.debug(f"Image item x, y: {self.image_item.pos().x()}, {self.image_item.pos().y()}")
        img_cx, img_cy = img_w / 2, img_h / 2

        # --- Add char_cfg origin marker ---
        self._clear_char_cfg_marker() # Clear previous marker if any

        # Extract bbox origin from char_cfg.yaml data
        char_cfg_origin_x = skeleton_data_dict.get('bbox_origin_x')
        char_cfg_origin_y = skeleton_data_dict.get('bbox_origin_y')
        char_cfg_origin_r = skeleton_data_dict.get('bbox_origin_r')
        char_cfg_origin_b = skeleton_data_dict.get('bbox_origin_b')

        if char_cfg_origin_x is not None and char_cfg_origin_y is not None:
            logging.info(f"Found char_cfg origin: ({char_cfg_origin_x}, {char_cfg_origin_y})")
            # Create a marker (small green circle) relative to the image item's origin (0,0)
            marker_size = 30 # Adjust size as needed
            # Center the ellipse on the coordinate
            self.char_cfg_origin_marker = QGraphicsEllipseItem(
                char_cfg_origin_x - marker_size / 2,
                char_cfg_origin_y - marker_size / 2,
                marker_size,
                marker_size
            )
            pen = QPen(Qt.GlobalColor.black, 1)
            pen.setCosmetic(True) # Keep pen width constant regardless of zoom
            self.char_cfg_origin_marker.setPen(pen) # Black outline
            self.char_cfg_origin_marker.setBrush(QBrush(Qt.GlobalColor.green)) # Green fill
            self.char_cfg_origin_marker.setZValue(5) # Ensure it's visible above image/lines/bbox
            # Set parent to image_item so it transforms with the image
            self.char_cfg_origin_marker.setParentItem(self.image_item)
            self.char_cfg_origin_marker.setVisible(self.debug_mode) # Visible only in debug mode initially
            # No need to add to scene directly as parent is set

            # Marker on the right bottom of the bounding box
            self.char_cfg_origin_marker_rb = QGraphicsEllipseItem(
                char_cfg_origin_r - marker_size / 2,
                char_cfg_origin_b - marker_size / 2,
                marker_size,
                marker_size
            )
            pen = QPen(Qt.GlobalColor.black, 1)
            pen.setCosmetic(True) # Keep pen width constant regardless of zoom
            self.char_cfg_origin_marker_rb.setPen(pen)
            self.char_cfg_origin_marker_rb.setBrush(QBrush(Qt.GlobalColor.green))
            self.char_cfg_origin_marker_rb.setZValue(5)
            self.char_cfg_origin_marker_rb.setParentItem(self.image_item)
            self.char_cfg_origin_marker_rb.setVisible(self.debug_mode) # Visible only in debug mode initially
            # No need to add to scene directly as parent is set
        else:
            logging.warning("Could not find 'bbox_origin_x' or 'bbox_origin_y' in char_cfg data.")
            self.char_cfg_origin_marker = None
        # --- End add char_cfg origin marker ---

        # Determine scale factor based on bounding box
        scale = 1.0
        bb_origin_x, bb_origin_y = 0.0, 0.0 # Top-left of bounding box
        if self.bounding_box:
            bb_w = self.bounding_box['right'] - self.bounding_box['left']
            bb_h = self.bounding_box['bottom'] - self.bounding_box['top']
            if bb_w > 0 and bb_h > 0:
                scale_x = img_w / bb_w
                scale_y = img_h / bb_h
                scale = min(scale_x, scale_y) # Uniform scaling
                bb_origin_x = self.bounding_box['left']
                bb_origin_y = self.bounding_box['top']
                logging.info(f"Using bounding box for scaling. BB WxH: {bb_w}x{bb_h}, Image WxH: {img_w}x{img_h}, Scale: {scale:.2f}")
            else:
                 logging.warning("Invalid bounding box dimensions, using scale 1.0")
        else:
            logging.info("No bounding box found, using scale 1.0")

        # Process skeleton structure
        skeleton_structure = skeleton_data_dict.get('skeleton')
        joint_details = {} # intermediate storage: name -> {'joint': SkeletonJoint, 'parent': str}

        # Handle list format (e.g., from char_cfg.yaml)
        if isinstance(skeleton_structure, list):
            logging.debug("Processing list-based skeleton format.")
            for joint_data in skeleton_structure:
                name = joint_data.get('name')
                loc = joint_data.get('loc')
                parent = joint_data.get('parent')
                if not name or not loc or len(loc) < 2:
                    logging.warning(f"Skipping invalid joint data: {joint_data}")
                    continue
                orig_x, orig_y = loc[0], loc[1] # Coordinates from config

                # --- Coordinate Transformation (Relative to Image Item) ---
                # Calculate coordinates within the image_item's local coordinate system
                # (where top-left of the pixmap is 0,0)
                item_relative_x, item_relative_y = 0, 0

                if self.bounding_box:
                    bb_left = self.bounding_box.get('left', 0)
                    bb_top = self.bounding_box.get('top', 0)
                    # Assume orig_x, orig_y are pixel offsets relative to bb_left, bb_top
                    item_relative_x = bb_left + orig_x
                    item_relative_y = bb_top + orig_y
                    logging.debug(f"Joint {name}: Orig({orig_x}, {orig_y}) + BB({bb_left:.1f}, {bb_top:.1f}) -> ItemRel({item_relative_x:.1f}, {item_relative_y:.1f})")
                else:
                    # Fallback: No bounding box. Assume orig_x, orig_y are relative to image top-left (0,0).
                    item_relative_x = orig_x
                    item_relative_y = orig_y
                    logging.debug(f"Joint {name} (no BB): Orig({orig_x}, {orig_y}) -> ItemRel({item_relative_x:.1f}, {item_relative_y:.1f})")
                # --- End Transformation ---

                # Create joint with coordinates relative to the parent (image_item)
                skel_joint = SkeletonJoint(name, item_relative_x, item_relative_y)
                # Set the image item as the parent. The joint will now transform with the image.
                skel_joint.setParentItem(self.image_item)
                # Store the joint (no need to add to scene directly)
                self.joints[name] = skel_joint
                joint_details[name] = {'joint': skel_joint, 'parent': parent}

                # Add joint label (if not root)
                if parent is not None:
                    label_text = f"{name}\n -> {parent}"
                    label_item = QGraphicsTextItem(label_text)
                    label_item.setDefaultTextColor(QColor("red"))
                    # Position label slightly offset from the joint
                    label_item.setPos(skel_joint.pos() + QPointF(5, -10))
                    label_item.setZValue(101) # Above joints/lines
                    label_item.setVisible(self.debug_mode) # Only show in debug mode
                    self.scene().addItem(label_item)
                    self.joint_labels[name] = label_item

            # Create lines from parent info
            for name, details in joint_details.items():
                parent_name = details['parent']
                if parent_name and parent_name in self.joints:
                    # Line itself is added to the scene, but uses child joints
                    line = SkeletonLine(self.joints[parent_name], details['joint'])
                    self.scene().addItem(line)
                    self.lines.append(line)

        # Handle dictionary format
        elif isinstance(skeleton_structure, dict):
            logging.debug("Processing dict-based skeleton format.")
            for name, joint_data in skeleton_structure.items():
                if 'x' not in joint_data or 'y' not in joint_data:
                    logging.warning(f"Skipping invalid joint data for '{name}': {joint_data}")
                    continue
                orig_x, orig_y = joint_data['x'], joint_data['y'] # Coordinates from config

                # --- Coordinate Transformation (Relative to Image Item) ---
                item_relative_x, item_relative_y = 0, 0
                if self.bounding_box:
                    bb_left = self.bounding_box.get('left', 0)
                    bb_top = self.bounding_box.get('top', 0)
                    item_relative_x = bb_left + orig_x
                    item_relative_y = bb_top + orig_y
                    logging.debug(f"Joint {name}: Orig({orig_x}, {orig_y}) + BB({bb_left:.1f}, {bb_top:.1f}) -> ItemRel({item_relative_x:.1f}, {item_relative_y:.1f})")
                else:
                    item_relative_x = orig_x
                    item_relative_y = orig_y
                    logging.debug(f"Joint {name} (no BB): Orig({orig_x}, {orig_y}) -> ItemRel({item_relative_x:.1f}, {item_relative_y:.1f})")
                # --- End Transformation ---

                # Create joint relative to parent and set parent
                skel_joint = SkeletonJoint(name, item_relative_x, item_relative_y)
                skel_joint.setParentItem(self.image_item)
                self.joints[name] = skel_joint
                # We don't have parent info directly here, rely on bone_list

                # Add joint label (if not root)
                if name in joint_data and 'parent' in joint_data:
                    parent_name = joint_data['parent']
                    if parent_name is not None and parent_name in self.joints:
                        label_text = f"{name}\n -> {parent_name}"
                        label_item = QGraphicsTextItem(label_text)
                        label_item.setDefaultTextColor(QColor("red"))
                        # Position label slightly offset from the joint
                        label_item.setPos(skel_joint.pos() + QPointF(5, -10))
                        label_item.setZValue(101) # Above joints/lines
                        label_item.setVisible(self.debug_mode) # Only show in debug mode
                        self.scene().addItem(label_item)
                        self.joint_labels[name] = label_item

            # Create lines from bone_list
            bone_list = skeleton_data_dict.get('bone_list', JOINT_CONNECTIONS) # Use default if not present
            for bone in bone_list:
                if len(bone) >= 2:
                    j1_name, j2_name = bone[0], bone[1]
                    if j1_name in self.joints and j2_name in self.joints:
                        # Add line to scene
                        line = SkeletonLine(self.joints[j1_name], self.joints[j2_name])
                        self.scene().addItem(line)
                        self.lines.append(line)
                    else:
                         logging.warning(f"Cannot create bone '{j1_name}'-'{j2_name}': one or both joints not found.")

        else:
            logging.error(f"Unsupported skeleton data format: {type(skeleton_structure)}")
            return False

        logging.info(f"Skeleton loaded: {len(self.joints)} joints, {len(self.lines)} lines.")
        self.reset_view() # Adjust view after loading
        return True

    def _clear_char_cfg_marker(self):
        """Removes the char_cfg origin marker from the scene."""
        if self.char_cfg_origin_marker:
            # Remove from scene if it's added (it might just have a parent)
            if self.char_cfg_origin_marker.scene():
                self.scene().removeItem(self.char_cfg_origin_marker)
            self.char_cfg_origin_marker = None

    def _clear_skeleton(self):
        """Removes all skeleton joints, lines, and the char_cfg marker from the scene."""
        self._clear_char_cfg_marker() # Clear the origin marker
        for joint in self.joints.values():
            if joint.scene(): self.scene().removeItem(joint)
        for line in self.lines:
            if line.scene(): self.scene().removeItem(line)
        self.joints.clear()
        self.lines.clear()
        self._clear_joint_labels() # Also clear labels when clearing skeleton

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
        if self.image_item:
            # Fit content slightly zoomed out
            rect = self.image_item.boundingRect()
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.scale(0.95, 0.95) # Zoom out slightly
            self.centerOn(rect.center())
        elif self.joints: # Fit skeleton if no image
             rect = self.scene().itemsBoundingRect()
             if rect.isValid(): self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def _update_joint_label_position(self, joint_name: str):
        """Updates the position of a joint's label based on the joint's current position."""
        if joint_name in self.joints and joint_name in self.joint_labels:
            joint_item = self.joints[joint_name]
            label_item = self.joint_labels[joint_name]
            label_item.setPos(joint_item.pos() + QPointF(5, -10))

    def _update_lines(self, joint_item: SkeletonJoint):
        """Updates the lines connected to a moved joint."""
        # In Python 3.8, joint_item.name might not exist if SkeletonJoint doesn't define it.
        # Assuming SkeletonJoint has a 'joint_name' attribute based on skeleton_item.py
        joint_name = joint_item.joint_name
        for line in self.lines:
            # Ensure comparison is with the correct attribute if line stores names
            if (line.joint1 and line.joint1.joint_name == joint_name) or \
               (line.joint2 and line.joint2.joint_name == joint_name):
                line.update_position()

        # Update label position when joint moves
        self._update_joint_label_position(joint_name)

    # --- Perpendicular Cut Guide Methods ---
    def get_lines_connected_to_joint(self, target_joint: SkeletonJoint) -> List[SkeletonLine]:
        """Finds all SkeletonLines connected to the target_joint."""
        connected_lines = []
        # self.lines is already populated with SkeletonLine items
        for line in self.lines:
            if line.joint1 == target_joint or line.joint2 == target_joint:
                connected_lines.append(line)
        return connected_lines

    def calculate_perpendicular_cut_guide(self, joint: SkeletonJoint) -> Optional[QLineF]:
        """
        Calculates a perpendicular guide line at a given joint.
        Returns a QLineF representing the guide, or None.
        """
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


    def update_and_draw_cut_guides(self, active_joint: Optional[SkeletonJoint]):
        """
        Clears old guides and draws a new one for the active_joint.
        Call this when the active joint changes (e.g., on hover or selection).
        """
        # Clear existing guides
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
    # --- End Perpendicular Cut Guide Methods ---