import logging
from pathlib import Path
from typing import Optional, List, Any, Tuple

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QLineF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QBrush, QColor, QTransform, QPainterPath, QMouseEvent, QPolygonF, QPainterPathStroker
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsSceneMouseEvent, QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QGraphicsPathItem, QGraphicsRectItem, QGraphicsEllipseItem

from automataii.core.models import PartInfo
from automataii.config.z_indices import (
    Z_PART_DEFAULT,
    Z_ANCHOR_POINT,
    Z_MOTION_PATH_LINE,
    Z_SELECTION_HIGHLIGHT as Z_ITEM_SELECTION_HIGHLIGHT
)

# Constants for hover effects
HOVER_PEN_COLOR = QColor(Qt.GlobalColor.yellow)
HOVER_PEN_WIDTH = 2

class CharacterPartItem(QGraphicsPixmapItem):
    """
    A QGraphicsPixmapItem representing a character part with its own texture,
    anchor point, motion path, and selection highlighting.
    """
    # --- Signals temporarily commented out ---
    # part_clicked = pyqtSignal(str)  # Emits part name when clicked
    # part_double_clicked = pyqtSignal(str) # Emits part name when double-clicked
    # position_changed_by_user = pyqtSignal(str, QPointF) # name, new_scene_pos

    def __init__(self, part_info: PartInfo, project_dir: Path, parent: Optional[QGraphicsItem] = None):
        # QObject.__init__(self) # Removed
        QGraphicsPixmapItem.__init__(self, parent) # Initialize QGraphicsPixmapItem (or super() if only one base class)
        # super().__init__(parent) # Alternative if only QGraphicsPixmapItem is base

        self.part_info = part_info
        self.project_dir = project_dir # Store project_dir for texture loading
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        self.part_pixmap: Optional[QPixmap] = None
        self._bounding_rect_local: QRectF = QRectF()
        self.anchor_offset: QPointF = QPointF()

        self.motion_path: Optional[QPainterPath] = None
        self.motion_path_item: Optional[QGraphicsPathItem] = None

        self.selection_highlight_item: Optional[QGraphicsRectItem] = None

        self._is_fixed: bool = part_info.fixed
        self.z_value = part_info.z_value if part_info.z_value is not None else Z_PART_DEFAULT
        self.setZValue(self.z_value)

        self._load_texture()
        self._setup_selection_highlight()

        if self.part_pixmap and not self.part_pixmap.isNull():
            self.anchor_offset = QPointF(self.part_pixmap.width() / 2, self.part_pixmap.height() / 2)
            self.setPos(QPointF(part_info.x, part_info.y))

        self.update_motion_path_visual()

    def _load_texture(self):
        """Loads the texture for this part from its individual PNG file."""
        if not self.part_info or not self.part_info.name:
            logging.error("CharacterPartItem: PartInfo or part name is missing, cannot load texture.")
            self._create_placeholder_pixmap()
            return

        svg_path = self.project_dir / f"{self.part_info.name}.svg"
        png_path = self.project_dir / f"{self.part_info.name}.png"

        loaded_successfully = False
        if svg_path.exists():
            temp_pixmap = QPixmap()
            if temp_pixmap.load(str(svg_path)):
                if self.part_info.roi and len(self.part_info.roi) == 4 and self.part_info.roi[2] > 0 and self.part_info.roi[3] > 0:
                    target_width, target_height = self.part_info.roi[2], self.part_info.roi[3]
                    self.part_pixmap = temp_pixmap.scaled(int(target_width), int(target_height),
                                                          Qt.AspectRatioMode.KeepAspectRatio,
                                                          Qt.TransformationMode.SmoothTransformation)
                else:
                    self.part_pixmap = temp_pixmap
                loaded_successfully = True
                logging.info(f"CharacterPartItem '{self.part_info.name}': Loaded SVG texture from {svg_path}")

        if not loaded_successfully and png_path.exists():
            self.part_pixmap = QPixmap(str(png_path))
            if not self.part_pixmap.isNull():
                loaded_successfully = True
                logging.info(f"CharacterPartItem '{self.part_info.name}': Loaded PNG texture from {png_path}")

        if not loaded_successfully or (self.part_pixmap and self.part_pixmap.isNull()):
            logging.warning(f"CharacterPartItem '{self.part_info.name}': Texture file not found at {svg_path} or {png_path}, or failed to load. Creating placeholder.")
            self._create_placeholder_pixmap()

        if self.part_pixmap:
             self.setPixmap(self.part_pixmap)
        self._bounding_rect_local = self.boundingRect()

    def _create_placeholder_pixmap(self):
        width = 50
        height = 50
        if self.part_info.roi and len(self.part_info.roi) == 4:
            width = int(self.part_info.roi[2]) if self.part_info.roi[2] > 0 else 50
            height = int(self.part_info.roi[3]) if self.part_info.roi[3] > 0 else 50

        self.part_pixmap = QPixmap(width, height)
        self.part_pixmap.fill(QColor(Qt.GlobalColor.lightGray))
        painter = QPainter(self.part_pixmap)
        pen = QPen(Qt.GlobalColor.red, 2)
        painter.setPen(pen)
        painter.drawLine(0, 0, width, height)
        painter.drawLine(width, 0, 0, height)
        if self.part_info and self.part_info.name:
             painter.drawText(self.part_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, self.part_info.name[:3])
        painter.end()
        self.setPixmap(self.part_pixmap)
        self._bounding_rect_local = QRectF(0,0, width, height)

    def name(self) -> str:
        return self.part_info.name

    @property
    def is_fixed(self) -> bool:
        return self._is_fixed

    def set_fixed(self, fixed: bool):
        self._is_fixed = fixed
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not fixed)

    def set_motion_path(self, path: Optional[QPainterPath]):
        self.motion_path = path
        self.update_motion_path_visual()

    def update_motion_path_visual(self):
        if self.motion_path_item and self.motion_path_item.scene():
            self.motion_path_item.scene().removeItem(self.motion_path_item)
            self.motion_path_item = None

        if self.motion_path and not self.motion_path.isEmpty():
            pen = QPen(QColor(0, 200, 0, 180), 1.5)
            pen.setCosmetic(True)
            self.motion_path_item = QGraphicsPathItem(self.motion_path)
            self.motion_path_item.setPen(pen)
            self.motion_path_item.setZValue(Z_MOTION_PATH_LINE)
            if self.scene():
                 self.scene().addItem(self.motion_path_item)
            logging.debug(f"Motion path visual updated for {self.name()}")
        else:
            logging.debug(f"No motion path to visualize for {self.name()}")

    def _setup_selection_highlight(self):
        pen = QPen(QColor(0, 120, 215, 200), 1.5)
        pen.setCosmetic(True)
        self.selection_highlight_item = QGraphicsRectItem()
        self.selection_highlight_item.setPen(pen)
        self.selection_highlight_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.selection_highlight_item.setZValue(Z_ITEM_SELECTION_HIGHLIGHT)
        self.selection_highlight_item.setVisible(False)

    def set_selected(self, selected: bool):
        if not self.selection_highlight_item:
            self._setup_selection_highlight()

        if selected:
            if self.selection_highlight_item and not self.selection_highlight_item.scene() and self.scene():
                self.scene().addItem(self.selection_highlight_item)
            if self.selection_highlight_item:
                self.selection_highlight_item.setRect(self.boundingRect())
                self.selection_highlight_item.setPos(self.scenePos())
                self.selection_highlight_item.setRotation(self.rotation())
                self.selection_highlight_item.setScale(self.scale())
                self.selection_highlight_item.setVisible(True)
        else:
            if self.selection_highlight_item:
                self.selection_highlight_item.setVisible(False)

    def boundingRect(self) -> QRectF:
        if self.part_pixmap and not self.part_pixmap.isNull():
            return QRectF(self.part_pixmap.rect())
        return self._bounding_rect_local if self._bounding_rect_local else QRectF(0,0,10,10)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        super().paint(painter, option, widget)
        if self.part_info.show_anchor:
            painter.setPen(QPen(Qt.GlobalColor.red, 2))
            painter.setBrush(QBrush(Qt.GlobalColor.red))
            painter.drawEllipse(self.anchor_offset, 3, 3)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """Handle item changes, like position changes by the user."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene():
            # self.position_changed_by_user.emit(self.name(), self.scenePos()) # Temporarily commented out
            # logging.debug(f"Part '{self.name()}' moved to {self.scenePos()}")
            pass # Avoid logging every pixel change during drag

        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.set_selected(bool(value))

        return super().itemChange(change, value)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle mouse press events on the part."""
        super().mousePressEvent(event) # Call base implementation for selection etc.
        if event.button() == Qt.MouseButton.LeftButton:
            # self.part_clicked.emit(self.name()) # Temporarily commented out
            logging.debug(f"CharacterPartItem '{self.name()}' clicked.")
            # Let the view or tab handle selection logic primarily
            # self.setSelected(True) # Scene selection handles this if ItemIsSelectable
            pass

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle mouse double-click events on the part."""
        super().mouseDoubleClickEvent(event)
        # self.part_double_clicked.emit(self.name()) # Temporarily commented out
        logging.debug(f"CharacterPartItem '{self.name()}' double-clicked.")
        # Example: Open properties dialog or enter rename mode
        pass

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        super().hoverLeaveEvent(event)

    def get_anchor_point_scene_pos(self) -> QPointF:
        return self.mapToScene(self.anchor_offset)

    def set_scene_position_from_anchor(self, scene_anchor_pos: QPointF):
        transform = QTransform().rotate(self.rotation())
        rotated_anchor_offset = transform.map(self.anchor_offset)
        new_pos = scene_anchor_pos - rotated_anchor_offset
        self.setPos(new_pos)

    def update_visual_from_part_info(self):
        if self.is_fixed != self.part_info.fixed:
            self.set_fixed(self.part_info.fixed)
        new_z = self.part_info.z_value if self.part_info.z_value is not None else Z_PART_DEFAULT
        if self.z_value != new_z:
            self.z_value = new_z
            self.setZValue(self.z_value)

        if hasattr(self.part_info, 'motion_path') and isinstance(self.part_info.motion_path, QPainterPath):
             if self.motion_path != self.part_info.motion_path:
                  self.set_motion_path(self.part_info.motion_path)
        elif hasattr(self.part_info, 'motion_path_data') and isinstance(self.part_info.motion_path_data, list):
            new_qpath = QPainterPath()
            if self.part_info.motion_path_data and len(self.part_info.motion_path_data) > 0 and isinstance(self.part_info.motion_path_data[0], QPointF) :
                new_qpath.moveTo(self.part_info.motion_path_data[0])
                for pt in self.part_info.motion_path_data[1:]:
                    if isinstance(pt, QPointF):
                         new_qpath.lineTo(pt)
            if self.motion_path != new_qpath:
                 self.set_motion_path(new_qpath)
        self.update()
