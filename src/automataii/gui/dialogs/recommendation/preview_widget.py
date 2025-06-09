"""Mechanism preview widget for displaying mechanism visualizations."""

from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QColor,
    QPen,
    QPainterPath,
    QTransform,
)
from PyQt6.QtWidgets import (
    QWidget,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPathItem,
)

from .constants import PREVIEW_WIDGET_SIZE, BITTERSWEET, MECHANISM_TYPE_MAPPING
from .preview_renderer import MechanismPreviewRenderer


class MechanismPreviewWidget(QGraphicsView):
    """A widget to display a preview of a single mechanism."""

    def __init__(
        self, mechanism_data: Dict[str, Any], parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.mechanism_data = mechanism_data
        self.setFixedSize(*PREVIEW_WIDGET_SIZE)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QColor("#f8f8f8"))  # Light background
        
        self.renderer = MechanismPreviewRenderer(self.scene)
        self._render_preview()

    def _render_preview(self) -> None:
        """Render the mechanism preview."""
        self.scene.clear()
        margin = 5
        view_rect_f = QRectF(self.rect())
        view_rect_adjusted_f = view_rect_f.adjusted(margin, margin, -margin, -margin)
        self.scene.setSceneRect(view_rect_f)

        if not self.mechanism_data or not self.mechanism_data.get("type"):
            self._render_no_preview(view_rect_adjusted_f)
            return

        preview_type = self.mechanism_data.get("type")
        # Use type mapping to normalize type names
        preview_type = MECHANISM_TYPE_MAPPING.get(preview_type, preview_type)

        if preview_type in ["Cam & Follower", "Cam Profile"]:
            self.renderer.render_cam_preview(view_rect_adjusted_f)
        elif preview_type in ["4-Bar Linkage", "3-Bar Linkage"]:
            self.renderer.render_linkage_preview(view_rect_adjusted_f)
        elif preview_type == "Gears (Simple Pair)":
            self.renderer.render_gear_preview(view_rect_adjusted_f)
        else:
            self._render_no_preview(view_rect_adjusted_f, 
                                   f'Preview for "{preview_type}"\nnot implemented.')

        # Draw user's motion path if available
        self._draw_user_motion_path(view_rect_adjusted_f)

        # Fit view to scene contents
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _render_no_preview(self, bounds: QRectF, text: str = "No Preview") -> None:
        """Render a 'no preview' message."""
        text_item = self.scene.addText(text)
        text_item.setDefaultTextColor(Qt.GlobalColor.black)
        text_item.setPos(bounds.center() - text_item.boundingRect().center())

    def _draw_user_motion_path(self, bounds: QRectF) -> None:
        """Draws the user's motion path, scaled and centered within the given bounds."""
        user_path_local = self.mechanism_data.get("user_motion_path_local")
        if not isinstance(user_path_local, QPainterPath) or user_path_local.isEmpty():
            return

        path_bounds = user_path_local.boundingRect()
        if path_bounds.width() == 0 or path_bounds.height() == 0:
            return

        # Scale the path to fit within 80% of the preview bounds
        target_rect = bounds.adjusted(
            bounds.width() * 0.1,
            bounds.height() * 0.1,
            -bounds.width() * 0.1,
            -bounds.height() * 0.1,
        )

        scale_x = target_rect.width() / path_bounds.width()
        scale_y = target_rect.height() / path_bounds.height()
        scale = min(scale_x, scale_y)

        transform = QTransform()
        # 1. Translate path's top-left to origin
        transform.translate(-path_bounds.left(), -path_bounds.top())
        # 2. Scale
        transform.scale(scale, scale)
        # 3. Center in target rect
        scaled_path_bounds = transform.mapRect(path_bounds)
        transform.translate(
            target_rect.left()
            - scaled_path_bounds.left()
            + (target_rect.width() - scaled_path_bounds.width()) / 2,
            target_rect.top()
            - scaled_path_bounds.top()
            + (target_rect.height() - scaled_path_bounds.height()) / 2,
        )

        transformed_path = transform.map(user_path_local)

        path_item = QGraphicsPathItem(transformed_path)
        pen = QPen(BITTERSWEET, 3.0, Qt.PenStyle.DashLine)
        path_item.setPen(pen)
        path_item.setZValue(10)  # Draw on top of the mechanism
        self.scene.addItem(path_item)