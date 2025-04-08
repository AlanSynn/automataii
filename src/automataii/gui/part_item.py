import logging
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QBrush, QPainterPath, QTransform
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QLineF

class CharacterPartItem(QGraphicsItem):
    """Graphical representation of a character part"""
    def __init__(self, part_info, parent=None):
        super().__init__(parent)
        self.part_info = part_info
        # Keep original path if needed for other calculations
        # self.original_qpainter_path = part_info.qpainter_path

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setAcceptHoverEvents(True)
        self.is_fixed = False  # Whether part is fixed in place
        self.is_hover = False  # Whether mouse is hovering over this item
        self.setZValue(part_info.z_value)  # Set Z order

        # Image loading
        self.pixmap = None
        if hasattr(part_info, 'image_path') and part_info.image_path:
            try:
                self.pixmap = QPixmap(part_info.image_path)
                if self.pixmap.isNull():
                    logging.warning(f"Failed to load image: {part_info.image_path}")
                    self.pixmap = None
            except Exception as e:
                logging.error(f"Error loading image {part_info.image_path}: {e}")
                self.pixmap = None

        # Motion path for animation
        self.motion_path = None
        self.motion_path_visual_item = None # Item to visually show the path in the scene
        self.mechanism_path = None
        self.mechanism_path_item = None

        # End effector (for IK)
        self.end_effector_offset = None  # Local coordinates point
        self.end_effector_marker = None
        self.ik_target_point = None  # Scene coordinates for IK target

        # Child joints (for kinematic chain)
        self.child_joints = []

        # --- Translate SVG Path based on ROI --- #
        self.shape_path_for_drawing = QPainterPath() # Initialize empty
        original_path = part_info.qpainter_path
        roi = part_info.roi

        if roi and isinstance(roi, (list, tuple)) and len(roi) == 4:
            try:
                x_min, y_min = float(roi[0]), float(roi[1])
                # Create a translated copy for drawing and shape detection
                self.shape_path_for_drawing = original_path.translated(-x_min, -y_min)
                logging.debug(f"Translated path for '{self.part_info.name}' by (-{x_min}, -{y_min})")
            except (ValueError, TypeError):
                logging.warning(f"Invalid ROI for {self.part_info.name}: {roi}. Using original path coordinates.")
                self.shape_path_for_drawing = QPainterPath(original_path) # Use a copy
        else:
            logging.debug(f"No ROI found for {self.part_info.name}. Using original path coordinates.")
            self.shape_path_for_drawing = QPainterPath(original_path) # Use a copy
        # --- End Path Translation --- #

        self._path_points = []

    def boundingRect(self):
        """Return the bounding rect of the part, relative to the item's local origin (0,0)."""
        if self.pixmap:
            # Pixmap is already cropped, its rect is correct relative to local (0,0)
            return QRectF(self.pixmap.rect())
        elif not self.shape_path_for_drawing.isEmpty():
            # Use the translated path for bounding rect calculation
            return self.shape_path_for_drawing.boundingRect()
        return QRectF(-5, -5, 10, 10)  # Fallback small rect around origin

    def shape(self):
        """Return the precise shape of the item for collision detection and interactions."""
        # Return the translated path for accurate shape detection
        return self.shape_path_for_drawing

    def paint(self, painter: QPainter, option, widget):
        """Paint the character part"""
        # Draw outline
        pen = QPen(Qt.GlobalColor.blue, 2, Qt.PenStyle.DashLine) if self.isSelected() else QPen(Qt.GlobalColor.black, 1)
        painter.setPen(pen)

        # If we have a pixmap, draw it
        if self.pixmap:
            painter.drawPixmap(0, 0, self.pixmap)

        # Draw path outline using the translated path
        if not self.shape_path_for_drawing.isEmpty():
            if self.isSelected() or self.is_hover:
                # Highlight when selected or hovered
                brush_color = QColor(255, 255, 0, 40) # Semi-transparent yellow
            else:
                # Draw with part's color
                try:
                    brush_color = QColor(self.part_info.fill_color)
                except ValueError:
                     logging.warning(f"Invalid fill color for {self.part_info.name}: {self.part_info.fill_color}. Using default.")
                     brush_color = QColor('rgba(128,128,128,0.5)')
                brush_color.setAlpha(100)  # Semi-transparent

            painter.setBrush(QBrush(brush_color))
            painter.drawPath(self.shape_path_for_drawing) # Draw the translated path

            # NOTE: Assigned motion path is drawn separately by update_motion_path_visual

        # Draw fixed marker if part is fixed
        if self.is_fixed:
            painter.setPen(QPen(Qt.GlobalColor.red, 2))
            painter.setBrush(QBrush(Qt.GlobalColor.red))
            painter.drawEllipse(QPointF(0, 0), 5, 5)

        # Draw end effector marker if defined
        if self.end_effector_offset:
             self._update_end_effector_marker()

    def _update_end_effector_marker(self):
        """Update the visual marker for end effector"""
        if not self.end_effector_offset or not self.scene():
            return

        # Remove old marker if exists
        if self.end_effector_marker:
            self.scene().removeItem(self.end_effector_marker)
            self.end_effector_marker = None

        # Create a new marker
        self.end_effector_marker = self.scene().addEllipse(
            -4, -4, 8, 8,
            QPen(Qt.GlobalColor.red, 2),
            QBrush(Qt.GlobalColor.yellow)
        )
        self.end_effector_marker.setParentItem(self)
        self.end_effector_marker.setPos(self.end_effector_offset)
        self.end_effector_marker.setZValue(self.zValue() + 1)  # Show above part

    def mousePressEvent(self, event):
        # Override to get click position for joint definition, etc.
        super().mousePressEvent(event)
        logging.debug(f"{self.part_info.name} clicked at local pos: {event.pos()}")
        # Could emit a signal to pass to MainWindow if needed

    def hoverEnterEvent(self, event):
        """Highlight effect when mouse hovers over part"""
        self.is_hover = True
        self.update()  # Trigger repaint
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Remove highlight when mouse leaves"""
        self.is_hover = False
        self.update()  # Trigger repaint
        super().hoverLeaveEvent(event)

    def update_motion_path_visual(self, path: QPainterPath = None):
        """Updates the persistent visual representation of the assigned motion path."""
        self.motion_path = path # Store the actual path data

        # --- Set End Effector Offset to Center if Path is Assigned --- #
        if path and not path.isEmpty():
            center_offset = self.boundingRect().center()
            if self.end_effector_offset != center_offset:
                self.end_effector_offset = center_offset
                self._update_end_effector_marker() # Update visual marker
                logging.debug(f"Set end effector offset for {self.part_info.name} to center: {center_offset}")
        else:
            # Clear offset if path is removed
            if self.end_effector_offset is not None:
                self.end_effector_offset = None
                self._update_end_effector_marker()
        # --- End End Effector Offset --- #

        # Remove existing visual item first
        if self.motion_path_visual_item and self.motion_path_visual_item.scene():
            self.scene().removeItem(self.motion_path_visual_item)
            self.motion_path_visual_item = None

        # Create new visual item if path is valid
        if path and not path.isEmpty() and self.scene():
            pen = QPen(QColor(0, 180, 0, 120), 1.5, Qt.PenStyle.SolidLine) # Thin green line
            self.motion_path_visual_item = self.scene().addPath(path, pen)
            self.motion_path_visual_item.setZValue(100) # Draw above most items (adjust as needed)
            logging.debug(f"Added persistent motion path visual for {self.part_info.name}")

    def set_motion_path(self, path, end_effector_point=None):
        """DEPRECATED: Use update_motion_path_visual instead. Kept for potential compatibility."""
        logging.warning("set_motion_path is deprecated. Use update_motion_path_visual.")

    def set_mechanism_path(self, path):
        """Set mechanism-generated path for this part and visualize it"""
        if path is None:
             # Clear existing path if path is None
            if self.mechanism_path_item and self.scene():
                self.scene().removeItem(self.mechanism_path_item)
            self.mechanism_path_item = None
            self.mechanism_path = None
            return

        self.mechanism_path = QPainterPath(path)  # Create a copy of the path

        # Remove existing mechanism path visualization if any
        if self.mechanism_path_item and self.scene():
            self.scene().removeItem(self.mechanism_path_item)
            self.mechanism_path_item = None

        # Create visual representation of the mechanism path
        if self.scene():
            # Blue color for mechanism-generated path
            pen = QPen(QColor(0, 120, 255), 3, Qt.PenStyle.SolidLine)
            self.mechanism_path_item = self.scene().addPath(self.mechanism_path, pen)
            self.mechanism_path_item.setZValue(self.zValue() - 0.2)  # Behind the user path

        # Update end effector marker
        self._update_end_effector_marker()

    # --- End Effector Selection --- #

    def start_select_end_effector(self):
        """Starts the mode to select the end effector point on the selected part."""
        self._path_points = []

    # --- Center Offset Calculation --- #
    def get_center_offset(self):
        """Calculates the offset from the item's origin (0,0) to its visual center."""
        # Use bounding rect center as a simple approximation
        return self.boundingRect().center()

    # --- End Effector Selection --- #