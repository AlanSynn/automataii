"""Top-level tab bar with wheel/trackpad tab scrolling."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QTabBar, QWidget


class ScrollableTabBar(QTabBar):
    """A compact tab bar that scrolls through tabs without native ``<>`` buttons."""

    MAX_TAB_WIDTH = 150
    MIN_TAB_WIDTH = 88

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setUsesScrollButtons(False)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setExpanding(False)
        self.setStyleSheet(
            """
            QTabBar::tab {
                padding: 6px 9px;
                margin-right: 1px;
            }
            """
        )

    def tabSizeHint(self, index: int) -> QSize:
        """Cap wide labels against current width so primary tabs stay visible."""
        size = super().tabSizeHint(index)
        tab_count = max(1, self.count())
        available_width = max(0, self.width() - 12)
        target_width = self.MAX_TAB_WIDTH
        if available_width:
            target_width = max(
                self.MIN_TAB_WIDTH,
                min(self.MAX_TAB_WIDTH, available_width // tab_count),
            )
        size.setWidth(max(self.MIN_TAB_WIDTH, min(size.width(), target_width)))
        return size

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        """Move to the neighboring tab when users scroll on the tab strip."""
        if event is None:
            super().wheelEvent(event)
            return

        delta = self._dominant_wheel_delta(event)
        if delta == 0 or self.count() <= 1:
            super().wheelEvent(event)
            return

        step = -1 if delta > 0 else 1
        target_index = max(0, min(self.count() - 1, self.currentIndex() + step))
        if target_index == self.currentIndex():
            event.accept()
            return

        self.setCurrentIndex(target_index)
        event.accept()

    @staticmethod
    def _dominant_wheel_delta(event: QWheelEvent) -> int:
        angle_delta = event.angleDelta()
        pixel_delta = event.pixelDelta()
        x_delta = angle_delta.x() or pixel_delta.x()
        y_delta = angle_delta.y() or pixel_delta.y()
        return x_delta if abs(x_delta) > abs(y_delta) else y_delta
