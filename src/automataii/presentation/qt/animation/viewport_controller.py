"""
Common Viewport Controller.

Unified zoom/pan/reset for any QGraphicsView.
Eliminates duplication across ImageProcessingView, EditorView, MechanismView.

Architecture: Presentation Layer
Pattern: Strategy (pluggable behaviors)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QGraphicsView

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class ViewportConfig:
    """Configuration for viewport behavior."""

    zoom_factor_base: float = 1.05
    min_zoom_level: int = -47
    max_zoom_level: int = 47
    pan_sensitivity: float = 1.0
    fit_margin: float = 50.0
    smooth_zoom: bool = False
    invert_zoom: bool = False
    anchor_under_mouse: bool = True


class ViewportController(QObject):
    """
    Unified viewport controller for QGraphicsView.

    Features:
    - Zoom in/out with configurable factor
    - Pan with sensitivity control
    - Fit to content with margins
    - Reset to default view
    - Mouse wheel zoom support
    - Pinch gesture support (optional)

    Usage:
        view = QGraphicsView(scene)
        controller = ViewportController(view)

        # Configure
        controller.config.zoom_factor_base = 1.1
        controller.config.min_zoom_level = -20

        # Operations
        controller.zoom_in()
        controller.zoom_out()
        controller.zoom_to_fit()
        controller.reset_view()
        controller.pan(QPointF(10, 0))

        # Handle wheel events (call from view)
        controller.handle_wheel_event(event)
    """

    # Signals
    zoom_changed = pyqtSignal(int, float)  # level, scale
    view_reset = pyqtSignal()

    def __init__(
        self,
        view: QGraphicsView,
        config: ViewportConfig | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)

        self._view = view
        self._config = config or ViewportConfig()
        self._zoom_level = 0
        self._initial_transform = view.transform()

        # Apply initial configuration
        self._apply_config()

        logger.debug(f"ViewportController attached to {view.__class__.__name__}")

    @property
    def config(self) -> ViewportConfig:
        return self._config

    @property
    def zoom_level(self) -> int:
        return self._zoom_level

    @property
    def zoom_scale(self) -> float:
        return self._config.zoom_factor_base**self._zoom_level

    @property
    def view(self) -> QGraphicsView:
        return self._view

    def _apply_config(self) -> None:
        """Apply configuration to the view."""
        cfg = self._config

        # Transformation anchors
        if cfg.anchor_under_mouse:
            self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        else:
            self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        self._view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

    # =========================================================================
    # ZOOM OPERATIONS
    # =========================================================================

    def zoom_in(self, steps: int = 1) -> None:
        """Zoom in by specified steps."""
        self._apply_zoom(steps)

    def zoom_out(self, steps: int = 1) -> None:
        """Zoom out by specified steps."""
        self._apply_zoom(-steps)

    def zoom_to_level(self, level: int) -> None:
        """Set zoom to specific level."""
        self._zoom_level = max(
            self._config.min_zoom_level,
            min(self._config.max_zoom_level, level),
        )
        self._update_view_transform()

    def zoom_to_scale(self, scale: float) -> None:
        """Set zoom to achieve specific scale factor."""
        import math

        if scale <= 0:
            return

        level = int(math.log(scale) / math.log(self._config.zoom_factor_base))
        self.zoom_to_level(level)

    def _apply_zoom(self, delta: int) -> None:
        """Apply zoom delta."""
        new_level = self._zoom_level + delta

        if new_level < self._config.min_zoom_level:
            new_level = self._config.min_zoom_level
        elif new_level > self._config.max_zoom_level:
            new_level = self._config.max_zoom_level

        if new_level != self._zoom_level:
            self._zoom_level = new_level
            self._update_view_transform()
            self.zoom_changed.emit(self._zoom_level, self.zoom_scale)

    def _update_view_transform(self) -> None:
        """Update view transform based on zoom level."""
        scale = self.zoom_scale
        self._view.resetTransform()
        self._view.scale(scale, scale)

    # =========================================================================
    # PAN OPERATIONS
    # =========================================================================

    def pan(self, delta: QPointF) -> None:
        """Pan the view by delta amount."""
        sensitivity = self._config.pan_sensitivity

        # Get current scroll positions
        h_bar = self._view.horizontalScrollBar()
        v_bar = self._view.verticalScrollBar()

        # Apply pan with sensitivity
        h_bar.setValue(int(h_bar.value() - delta.x() * sensitivity))
        v_bar.setValue(int(v_bar.value() - delta.y() * sensitivity))

    def center_on(self, point: QPointF) -> None:
        """Center the view on a specific point."""
        self._view.centerOn(point)

    def center_on_scene(self) -> None:
        """Center the view on the scene center."""
        scene = self._view.scene()
        if scene:
            rect = scene.itemsBoundingRect()
            self._view.centerOn(rect.center())

    # =========================================================================
    # FIT OPERATIONS
    # =========================================================================

    def zoom_to_fit(self, margin: float | None = None) -> None:
        """Fit all content in view with optional margin."""
        scene = self._view.scene()
        if not scene:
            return

        # Get bounding rect of all items
        rect = scene.itemsBoundingRect()
        if rect.isEmpty():
            return

        # Add margin
        m = margin if margin is not None else self._config.fit_margin
        rect = rect.adjusted(-m, -m, m, m)

        # Fit in view
        self._view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

        # Calculate resulting zoom level
        self._calculate_zoom_from_transform()
        self.zoom_changed.emit(self._zoom_level, self.zoom_scale)

    def zoom_to_rect(self, rect: QRectF, margin: float = 0) -> None:
        """Fit a specific rect in view."""
        if rect.isEmpty():
            return

        if margin > 0:
            rect = rect.adjusted(-margin, -margin, margin, margin)

        self._view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._calculate_zoom_from_transform()
        self.zoom_changed.emit(self._zoom_level, self.zoom_scale)

    def _calculate_zoom_from_transform(self) -> None:
        """Calculate zoom level from current view transform."""
        import math

        transform = self._view.transform()
        scale = transform.m11()  # Horizontal scale factor

        if scale > 0:
            self._zoom_level = int(math.log(scale) / math.log(self._config.zoom_factor_base))
            # Clamp to valid range
            self._zoom_level = max(
                self._config.min_zoom_level,
                min(self._config.max_zoom_level, self._zoom_level),
            )

    # =========================================================================
    # RESET OPERATIONS
    # =========================================================================

    def reset_view(self) -> None:
        """Reset view to initial state."""
        self._zoom_level = 0
        self._view.resetTransform()
        self._view.setTransform(self._initial_transform)
        self.center_on_scene()
        self.view_reset.emit()
        logger.debug("Viewport reset")

    def set_initial_transform(self) -> None:
        """Capture current transform as initial state."""
        self._initial_transform = self._view.transform()

    # =========================================================================
    # EVENT HANDLING
    # =========================================================================

    def handle_wheel_event(self, event: QWheelEvent) -> bool:
        """
        Handle mouse wheel event for zooming.

        Returns:
            True if event was handled
        """
        # Get scroll amount
        delta = event.angleDelta().y()

        if delta == 0:
            return False

        # Calculate zoom steps (120 units = 1 step typically)
        steps = delta // 120

        if self._config.invert_zoom:
            steps = -steps

        if steps != 0:
            if steps > 0:
                self.zoom_in(steps)
            else:
                self.zoom_out(-steps)
            return True

        return False

    # =========================================================================
    # CAMERA STATE (for tab switching)
    # =========================================================================

    def get_camera_state(self) -> dict:
        """Get current camera state for persistence."""
        return {
            "zoom_level": self._zoom_level,
            "h_scroll": self._view.horizontalScrollBar().value(),
            "v_scroll": self._view.verticalScrollBar().value(),
            "transform": {
                "m11": self._view.transform().m11(),
                "m12": self._view.transform().m12(),
                "m21": self._view.transform().m21(),
                "m22": self._view.transform().m22(),
                "dx": self._view.transform().dx(),
                "dy": self._view.transform().dy(),
            },
        }

    def set_camera_state(self, state: dict) -> None:
        """Restore camera state from persistence."""
        if not state:
            return

        # Restore zoom level
        self._zoom_level = state.get("zoom_level", 0)
        self._update_view_transform()

        # Restore scroll positions
        h_scroll = state.get("h_scroll", 0)
        v_scroll = state.get("v_scroll", 0)
        self._view.horizontalScrollBar().setValue(h_scroll)
        self._view.verticalScrollBar().setValue(v_scroll)

        self.zoom_changed.emit(self._zoom_level, self.zoom_scale)
