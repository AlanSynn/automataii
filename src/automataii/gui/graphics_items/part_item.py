import logging
from pathlib import Path
from typing import Optional, List, Any, Tuple

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QLineF
from PyQt6.QtGui import (
    QPixmap,
    QPainter,
    QPen,
    QBrush,
    QColor,
    QTransform,
    QPainterPath,
    QMouseEvent,
    QPolygonF,
    QPainterPathStroker,
)
from PyQt6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsSceneMouseEvent,
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QWidget,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
)

from automataii.core.models import PartInfo
from automataii.config.z_indices import (
    Z_PART_DEFAULT,
    Z_ANCHOR_POINT,
    Z_MOTION_PATH_LINE,
    Z_SELECTION_HIGHLIGHT as Z_ITEM_SELECTION_HIGHLIGHT,
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

    def __init__(
        self,
        part_info: PartInfo,
        project_dir: Path,
        parent: Optional[QGraphicsItem] = None,
        debug_mode: bool = False,
    ):
        # QObject.__init__(self) # Removed
        QGraphicsPixmapItem.__init__(
            self, parent
        )  # Initialize QGraphicsPixmapItem (or super() if only one base class)
        # super().__init__(parent) # Alternative if only QGraphicsPixmapItem is base

        self.part_info = part_info
        self.project_dir = project_dir  # Store project_dir for texture loading
        self.debug_mode = debug_mode  # ADDED: Store debug_mode
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        self.part_pixmap: Optional[QPixmap] = None
        self._bounding_rect_local: QRectF = QRectF()
        self.anchor_offset: QPointF = QPointF()
        self.anchor_joint_id: Optional[str] = part_info.anchor_joint_id
        self.end_effector_offset: Optional[QPointF] = None  # IK end effector point
        self.parent_item_name: Optional[str] = None  # Parent part name for IK chain

        self.motion_path: Optional[QPainterPath] = None
        self.motion_path_item: Optional[QGraphicsPathItem] = None

        self.selection_highlight_item: Optional[QGraphicsRectItem] = None

        self._is_fixed: bool = part_info.fixed
        self._is_joint_locked: bool = False  # Whether the associated joint is locked for IK
        self.z_value = (
            part_info.z_value if part_info.z_value is not None else Z_PART_DEFAULT
        )
        self.setZValue(self.z_value)

        # 초기 회전각을 명시적으로 0으로 설정 (월드 기준)
        self.setRotation(0.0)
        self._initial_world_rotation = 0.0  # 초기 월드 회전값은 항상 0
        self._initial_local_rotation = 0.0  # 초기 로컬 회전값도 0

        self._load_texture()
        self._setup_selection_highlight()

        # Revised anchor_offset and initial position logic
        if (
            self.part_info.local_pivot_offset
            and len(self.part_info.local_pivot_offset) == 2
        ):
            self.anchor_offset = QPointF(
                self.part_info.local_pivot_offset[0],
                self.part_info.local_pivot_offset[1],
            )
            # Log warning if anchor_offset is at (0,0) which might indicate a problem
            if self.anchor_offset.x() == 0 and self.anchor_offset.y() == 0:
                logging.warning(
                    f"CharacterPartItem '{self.name()}': anchor_offset is (0,0) - this might cause alignment issues"
                )
            else:
                logging.debug(
                    f"CharacterPartItem '{self.name()}': Set anchor_offset from local_pivot_offset: {self.anchor_offset}"
                )
        elif (
            self.part_pixmap and not self.part_pixmap.isNull()
        ):  # Fallback to center if no local_pivot_offset
            self.anchor_offset = QPointF(
                self.part_pixmap.width() / 2, self.part_pixmap.height() / 2
            )
            logging.debug(
                f"CharacterPartItem '{self.name()}': local_pivot_offset not found or invalid, using pixmap center as anchor_offset: {self.anchor_offset}"
            )
        else:  # Fallback if pixmap also not available (e.g. placeholder creation failed, though unlikely)
            self.anchor_offset = QPointF(0, 0)
            logging.warning(
                f"CharacterPartItem '{self.name()}': Could not determine anchor_offset, defaulting to (0,0)."
            )

        self.setTransformOriginPoint(self.anchor_offset)

        # Set initial position based on part_info.x, y if available, otherwise default to (0,0) for now.
        # The actual scene positioning should be handled by a layout manager or a higher-level setup logic.
        initial_x = getattr(self.part_info, "x", 0.0)
        initial_y = getattr(self.part_info, "y", 0.0)
        self.setPos(QPointF(initial_x, initial_y))
        logging.debug(
            f"CharacterPartItem '{self.name()}': Initial raw position set to ({initial_x}, {initial_y}). Transform origin: {self.transformOriginPoint()}"
        )

        if self.part_pixmap and not self.part_pixmap.isNull():
            self._bounding_rect_local = QRectF(
                0, 0, self.part_pixmap.width(), self.part_pixmap.height()
            )
        elif (
            hasattr(self, "_bounding_rect_local") and not self._bounding_rect_local
        ):  # Ensure it is initialized if placeholder path was taken
            self._bounding_rect_local = QRectF(0, 0, 50, 50)  # Default placeholder size

        self.update_motion_path_visual()

    def _load_texture(self):
        """Loads the texture for this part from its image file (PNG)."""
        if not self.part_info or not self.part_info.name:
            logging.error(
                "CharacterPartItem: PartInfo or part name is missing, cannot load texture."
            )
            self._create_placeholder_pixmap()
            return

        potential_path_str: Optional[str] = None

        # 1. Prioritize image_path if it's absolute and exists
        if self.part_info.image_path and Path(self.part_info.image_path).is_absolute():
            if Path(self.part_info.image_path).exists():
                potential_path_str = self.part_info.image_path
                logging.info(
                    f"CharacterPartItem '{self.part_info.name}': Attempting to load texture from absolute image_path: {potential_path_str}"
                )
            else:
                logging.warning(
                    f"CharacterPartItem '{self.part_info.name}': Absolute image_path does not exist: {self.part_info.image_path}"
                )

        # 2. If not loaded, try project_dir + image_path (if image_path is relative) or project_dir + name.png
        if not potential_path_str:
            if self.part_info.image_path:  # Could be a relative path or just a filename
                path_to_try = self.project_dir / self.part_info.image_path
            else:  # Fallback to name.png if image_path is not set
                path_to_try = self.project_dir / f"{self.part_info.name}.png"

            if path_to_try.exists():
                potential_path_str = str(path_to_try)
                logging.info(
                    f"CharacterPartItem '{self.part_info.name}': Attempting to load texture from resolved path: {potential_path_str}"
                )
            else:
                # Construct the old fallback name.png path just in case it's the only one available during transition
                legacy_png_path = self.project_dir / f"{self.part_info.name}.png"
                if legacy_png_path.exists():
                    potential_path_str = str(legacy_png_path)
                    logging.info(
                        f"CharacterPartItem '{self.part_info.name}': Attempting to load texture from legacy path: {potential_path_str}"
                    )
                else:
                    logging.warning(
                        f"CharacterPartItem '{self.part_info.name}': Texture file not found at {path_to_try}"
                        f"{' or ' + str(legacy_png_path) if str(path_to_try) != str(legacy_png_path) else ''}. Creating placeholder."
                    )

        loaded_successfully = False
        if potential_path_str:
            temp_pixmap = QPixmap(potential_path_str)
            if not temp_pixmap.isNull():
                # Apply ROI scaling if ROI is valid and specifies dimensions
                if (
                    self.part_info.roi
                    and len(self.part_info.roi) == 4
                    and self.part_info.roi[2] > 0
                    and self.part_info.roi[3] > 0
                ):
                    target_width, target_height = (
                        int(self.part_info.roi[2]),
                        int(self.part_info.roi[3]),
                    )
                    self.part_pixmap = temp_pixmap.scaled(
                        target_width,
                        target_height,
                        Qt.AspectRatioMode.KeepAspectRatio,  # Or IgnoreAspectRatio if ROI defines exact output size
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    logging.info(
                        f"CharacterPartItem '{self.part_info.name}': Loaded and scaled texture from {potential_path_str} to {target_width}x{target_height}"
                    )
                else:
                    self.part_pixmap = temp_pixmap  # Use as is
                    logging.info(
                        f"CharacterPartItem '{self.part_info.name}': Loaded texture from {potential_path_str}"
                    )
                loaded_successfully = True
            else:
                logging.error(
                    f"CharacterPartItem '{self.part_info.name}': Failed to load QPixmap from {potential_path_str}"
                )

        if not loaded_successfully:
            # If potential_path_str was None, the earlier warning about file not found already occurred.
            # If it was not None but loading failed, this ensures placeholder creation.
            if (
                potential_path_str
            ):  # Only log this specific message if a path was attempted
                logging.warning(
                    f"CharacterPartItem '{self.part_info.name}': Failed to load texture from {potential_path_str}. Creating placeholder."
                )
            self._create_placeholder_pixmap()

        if self.part_pixmap:
            self.setPixmap(self.part_pixmap)
        # self._bounding_rect_local = self.boundingRect() # This will be set after pixmap is set and position is known, or in __init__

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
            painter.drawText(
                self.part_pixmap.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self.part_info.name[:3],
            )
        painter.end()
        self.setPixmap(self.part_pixmap)
        self._bounding_rect_local = QRectF(0, 0, width, height)

    def name(self) -> str:
        return self.part_info.name

    @property
    def is_fixed(self) -> bool:
        return self._is_fixed

    def set_fixed(self, fixed: bool):
        self._is_fixed = fixed
    
    @property
    def is_joint_locked(self) -> bool:
        """Returns True if the joint associated with this part is locked for IK solving."""
        return self._is_joint_locked
    
    def set_joint_locked(self, locked: bool):
        """Sets whether the joint associated with this part is locked for IK solving."""
        self._is_joint_locked = locked
        # Note: We might want to disable movement for locked joints, but that's handled separately
        # from the is_fixed property. For now, just store the state.

    def set_motion_path(self, path: Optional[QPainterPath]):
        self.motion_path = path
        self.update_motion_path_visual()

    def update_motion_path_visual(self):
        # EditorView is now responsible for drawing the final motion paths.
        # This CharacterPartItem will hold the motion_path data, but not draw it directly.
        if self.motion_path_item and self.motion_path_item.scene():
            # If this item previously managed its own path visual, ensure it's cleaned up.
            # This might be redundant if EditorView is the sole manager, but safe.
            self.motion_path_item.scene().removeItem(self.motion_path_item)
            self.motion_path_item = None
            logging.debug(
                f"CharacterPartItem '{self.name()}': Cleared any self-managed motion_path_item. EditorView should handle visuals."
            )

        if self.motion_path and not self.motion_path.isEmpty():
            logging.debug(
                f"CharacterPartItem '{self.name()}': Has motion_path data. Visuals are managed by EditorView."
            )
        else:
            logging.debug(f"CharacterPartItem '{self.name()}': No motion path data.")

    def _setup_selection_highlight(self):
        pen = QPen(QColor(253, 126, 20, 255), 3.0)  # Orange color, thicker border
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
            if (
                self.selection_highlight_item
                and not self.selection_highlight_item.scene()
                and self.scene()
            ):
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
        return (
            self._bounding_rect_local
            if self._bounding_rect_local
            else QRectF(0, 0, 10, 10)
        )

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ):
        super().paint(painter, option, widget)

        if self.debug_mode:
            painter.save()

            # Draw bounding box
            pen_bbox = QPen(Qt.GlobalColor.red, 0.5)  # Thin red line for bbox
            pen_bbox.setCosmetic(True)
            painter.setPen(pen_bbox)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect())

            # Draw anchor_offset (transform origin)
            anchor_color = Qt.GlobalColor.blue
            painter.setPen(QPen(anchor_color, 1))
            painter.setBrush(QBrush(anchor_color))
            # Draw a small circle for the anchor_offset
            painter.drawEllipse(self.anchor_offset, 2, 2)

            # Draw text information
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            painter.setPen(Qt.GlobalColor.black)

            text_lines = [
                f"Name: {self.name()}",
                f"ScenePos: ({self.scenePos().x():.1f}, {self.scenePos().y():.1f})",
                f"Pos: ({self.pos().x():.1f}, {self.pos().y():.1f})",
                f"AnchorOffset: ({self.anchor_offset.x():.1f}, {self.anchor_offset.y():.1f})",
                f"Rotation: {self.rotation():.1f}",
                f"Z: {self.zValue():.1f}",
            ]

            # Position text slightly offset from the top-left of the bounding rect
            text_y_offset = 0
            for i, line in enumerate(text_lines):
                painter.drawText(
                    QPointF(
                        self.boundingRect().left() + 2,
                        self.boundingRect().top() + 10 + i * 10,
                    ),
                    line,
                )
                text_y_offset += 10

            painter.restore()

        if (
            self.part_info.show_anchor
        ):  # This is a separate flag, not tied to debug_mode
            painter.save()
            painter.setPen(
                QPen(Qt.GlobalColor.magenta, 2)
            )  # Changed color to differentiate from debug anchor
            painter.setBrush(QBrush(Qt.GlobalColor.magenta))
            painter.drawEllipse(self.anchor_offset, 3, 3)  # Slightly larger
            painter.restore()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """Handle item changes, like position changes by the user."""
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
            and self.scene()
        ):
            # self.position_changed_by_user.emit(self.name(), self.scenePos()) # Temporarily commented out
            # logging.debug(f"Part '{self.name()}' moved to {self.scenePos()}")
            pass  # Avoid logging every pixel change during drag

        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.set_selected(bool(value))

        return super().itemChange(change, value)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle mouse press events on the part."""
        super().mousePressEvent(event)  # Call base implementation for selection etc.
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
        # Given that self.transformOriginPoint is self.anchor_offset,
        # and item.setRotation() rotates around this transformOriginPoint.
        # The vector from the item's origin (0,0) to its anchor_offset,
        # when transformed by rotation and scale around the anchor_offset itself,
        # effectively results in the anchor_offset (in its new orientation)
        # being at self.anchor_offset relative to the item's origin, if the item's origin were (0,0).
        # Thus, item.pos() + self.anchor_offset (in the scene's rotated sense) should be scene_anchor_pos.
        # This simplifies to: item.pos() = scene_anchor_pos - self.anchor_offset
        new_pos = scene_anchor_pos - self.anchor_offset
        self.setPos(new_pos)

        # Debug logging for torso alignment issues
        if self.name() == "torso":
            logging.info(
                f"CharacterPartItem 'torso': Setting position from anchor. "
                f"scene_anchor_pos={scene_anchor_pos}, anchor_offset={self.anchor_offset}, "
                f"resulting pos={new_pos}"
            )
