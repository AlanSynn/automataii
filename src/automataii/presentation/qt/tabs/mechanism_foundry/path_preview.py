"""
Path Preview Overlay - Visual overlay for mechanism motion path preview
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsScene

if TYPE_CHECKING:
    from automataii.application.mechanism_foundry.path_cache import CachedPath, PathCache
    from automataii.domain.mechanisms.core.protocols import Mechanism
else:
    from automataii.application.mechanism_foundry.path_cache import CachedPath, PathCache


class PathPreviewOverlay:
    def __init__(self, scene: QGraphicsScene, cache: PathCache):
        self._scene = scene
        self._cache = cache
        self._items: dict[str, list[QGraphicsItem]] = {}
        self._enabled = True
        self._fade_timer = QTimer()
        self._fade_timer.timeout.connect(self._auto_hide)
        self._fade_timer.setSingleShot(True)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled:
            self.hide_path()

    def show_path(
        self,
        mechanism: Mechanism,
        parameters: dict[str, float],
        point_name: str,
        auto_fade: bool = False,
    ) -> None:
        if not self._enabled:
            return

        if point_name in self._items:
            return

        cached_path = self._cache.compute_and_cache(mechanism, parameters, point_name)
        self._draw_path(cached_path, point_name)

        if auto_fade:
            self._fade_timer.start(2000)

    def hide_path(self, point_name: str | None = None) -> None:
        if point_name is None:
            for items in self._items.values():
                for item in items:
                    self._scene.removeItem(item)
            self._items.clear()
        elif point_name in self._items:
            for item in self._items[point_name]:
                self._scene.removeItem(item)
            del self._items[point_name]
        self._fade_timer.stop()

    def toggle_visibility(self) -> None:
        self._enabled = not self._enabled
        if not self._enabled:
            self.hide_path()

    def _draw_path(self, cached_path: CachedPath, point_name: str) -> None:
        """Optimized: Uses single QPainterPath instead of hundreds of line items."""
        points = cached_path.points
        if len(points) < 2:
            return

        items: list[QGraphicsItem] = []

        # Build single path for all segments (1 item instead of 360+)
        painter_path = QPainterPath()
        x0, y0 = points[0]
        painter_path.moveTo(x0, y0)
        for x, y in points[1:]:
            painter_path.lineTo(x, y)
        painter_path.closeSubpath()

        path_pen = QPen(QColor(0, 206, 209, 150), 2)
        path_pen.setStyle(Qt.PenStyle.DashLine)
        path_item = QGraphicsPathItem(painter_path)
        path_item.setPen(path_pen)
        path_item.setZValue(100)
        path_item.setData(0, "path_preview")
        self._scene.addItem(path_item)
        items.append(path_item)

        # Markers (reduced: every 36 points → ~10 markers)
        marker_pen = QPen(QColor(0, 206, 209, 200), 1)
        marker_brush = QBrush(QColor(0, 206, 209, 180))
        marker_interval = max(1, len(points) // 10)

        for i in range(0, len(points), marker_interval):
            x, y = points[i]
            marker = self._scene.addEllipse(x - 3, y - 3, 6, 6, marker_pen, marker_brush)
            if marker:
                marker.setZValue(101)
                marker.setData(0, "path_preview")
                items.append(marker)

        # Direction arrows (reduced: 8 → 4)
        arrow_path = QPainterPath()
        arrow_interval = max(1, len(points) // 4)

        for i in range(0, len(points), arrow_interval):
            if i + 1 >= len(points):
                break

            x1, y1 = points[i]
            x2, y2 = points[i + 1]

            dx = x2 - x1
            dy = y2 - y1
            length = (dx * dx + dy * dy) ** 0.5

            if length < 1:
                continue

            dx /= length
            dy /= length

            arrow_length = 8
            arrow_width = 5

            tip_x = x1 + dx * arrow_length * 1.5
            tip_y = y1 + dy * arrow_length * 1.5

            left_x = tip_x - dx * arrow_length + dy * arrow_width
            left_y = tip_y - dy * arrow_length - dx * arrow_width
            right_x = tip_x - dx * arrow_length - dy * arrow_width
            right_y = tip_y - dy * arrow_length + dx * arrow_width

            arrow_path.moveTo(tip_x, tip_y)
            arrow_path.lineTo(left_x, left_y)
            arrow_path.moveTo(tip_x, tip_y)
            arrow_path.lineTo(right_x, right_y)

        if not arrow_path.isEmpty():
            arrow_pen = QPen(QColor(0, 206, 209, 220), 2)
            arrow_item = QGraphicsPathItem(arrow_path)
            arrow_item.setPen(arrow_pen)
            arrow_item.setZValue(102)
            arrow_item.setData(0, "path_preview")
            self._scene.addItem(arrow_item)
            items.append(arrow_item)

        self._items[point_name] = items

    def _auto_hide(self) -> None:
        self.hide_path()
