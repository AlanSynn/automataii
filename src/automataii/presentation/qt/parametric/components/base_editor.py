"""
Base Editor - Abstract base class for mechanism editors.

Contains the ParametricHandle and MechanismEditor ABC.

Design Pattern: Template Method (abstract editor with concrete handle)
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QCursor, QPen
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
)

if TYPE_CHECKING:
    pass


@dataclass
class HandleStyle:
    """Visual style configuration for parametric handles."""

    size: float = 12.0
    color: QColor = field(default_factory=lambda: QColor(255, 100, 0))
    hover_color: QColor = field(default_factory=lambda: QColor(255, 150, 50))
    active_color: QColor = field(default_factory=lambda: QColor(255, 200, 100))
    border_width: float = 2.0
    border_color: QColor = field(default_factory=lambda: QColor(50, 50, 50))
    opacity: float = 0.9


class ParametricHandle(QGraphicsEllipseItem):
    """Interactive handle for parametric editing."""

    def __init__(
        self,
        center: QPointF,
        handle_id: str,
        param_name: str,
        on_moved: Callable | None = None,
        style: HandleStyle | None = None,
        constraints: dict | None = None,
    ):
        """
        Initialize parametric handle.

        Args:
            center: Initial position
            handle_id: Unique identifier
            param_name: Parameter being controlled
            on_moved: Callback for position changes
            style: Visual style configuration
            constraints: Movement constraints
        """
        self.style = style or HandleStyle()
        super().__init__(
            -self.style.size / 2,
            -self.style.size / 2,
            self.style.size,
            self.style.size,
        )

        self.handle_id = handle_id
        self.param_name = param_name
        self.on_moved = on_moved
        self.constraints = constraints or {}

        self._is_dragging = False
        self._drag_start = QPointF()
        self._original_pos = center

        self._setup_appearance()
        self._setup_interaction()
        try:
            self.setPos(center)
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

    def _setup_appearance(self):
        """Configure handle appearance."""
        self.setPen(QPen(self.style.border_color, self.style.border_width))
        self.setBrush(QBrush(self.style.color))
        self.setOpacity(self.style.opacity)
        self.setZValue(1000)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def _setup_interaction(self):
        """Configure interaction flags."""
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event):
        """Handle mouse hover enter."""
        self.setBrush(QBrush(self.style.hover_color))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Handle mouse hover leave."""
        if not self._is_dragging:
            self.setBrush(QBrush(self.style.color))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_start = event.scenePos()
            self._original_pos = self.scenePos()
            self.setBrush(QBrush(self.style.active_color))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse move with constraints."""
        if self._is_dragging and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.scenePos()
            new_pos = self._apply_constraints(new_pos)
            self.setPos(new_pos)
            if self.on_moved:
                self.on_moved(self.handle_id, new_pos)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self.setBrush(QBrush(self.style.hover_color))
        super().mouseReleaseEvent(event)

    def _apply_constraints(self, pos: QPointF) -> QPointF:
        """Apply movement constraints to position."""
        x, y = pos.x(), pos.y()

        # Bounding box constraints
        if "min_x" in self.constraints:
            x = max(x, self.constraints["min_x"])
        if "max_x" in self.constraints:
            x = min(x, self.constraints["max_x"])
        if "min_y" in self.constraints:
            y = max(y, self.constraints["min_y"])
        if "max_y" in self.constraints:
            y = min(y, self.constraints["max_y"])

        # Fixed axis constraints
        if "fixed_x" in self.constraints:
            try:
                x = float(self.constraints["fixed_x"])
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)
        if "fixed_y" in self.constraints:
            try:
                y = float(self.constraints["fixed_y"])
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

        # Grid snapping
        if "snap_grid" in self.constraints:
            grid_size = self.constraints["snap_grid"]
            x = round(x / grid_size) * grid_size
            y = round(y / grid_size) * grid_size

        # Distance constraints
        if "fixed_distance" in self.constraints:
            anchor = self.constraints["fixed_distance"]["anchor"]
            distance = self.constraints["fixed_distance"]["distance"]
            dx = x - anchor.x()
            dy = y - anchor.y()
            current_dist = math.sqrt(dx * dx + dy * dy)
            if current_dist > 0:
                scale = distance / current_dist
                x = anchor.x() + dx * scale
                y = anchor.y() + dy * scale

        # Radial constraints
        if "center" in self.constraints and (
            "min_radius" in self.constraints
            or "max_radius" in self.constraints
            or "angle" in self.constraints
        ):
            c = self.constraints["center"]
            dx = x - c.x()
            dy = y - c.y()
            r = math.sqrt(dx * dx + dy * dy)
            r_min = self.constraints.get("min_radius", 0.0)
            r_max = self.constraints.get("max_radius", float("inf"))
            r = max(r_min, min(r_max, r if r > 0 else r_min))
            if "angle" in self.constraints:
                ang_deg = float(self.constraints["angle"])
                ang = math.radians(ang_deg)
                x = c.x() + r * math.cos(ang)
                y = c.y() + r * math.sin(ang)
            else:
                if dx != 0 or dy != 0:
                    ang = math.atan2(dy, dx)
                    x = c.x() + r * math.cos(ang)
                    y = c.y() + r * math.sin(ang)

        return QPointF(x, y)


class MechanismEditor(ABC):
    """Abstract base class for mechanism-specific editors."""

    def __init__(self, mechanism_id: str, scene: QGraphicsScene):
        """
        Initialize mechanism editor.

        Args:
            mechanism_id: Unique mechanism identifier
            scene: Graphics scene for handles
        """
        self.mechanism_id = mechanism_id
        self.scene = scene
        self.handles: dict[str, ParametricHandle] = {}
        self.visual_items: list[QGraphicsItem] = []
        self.mechanism_data: dict[str, Any] = {}
        self._updating = False
        self.to_scene_coords: Callable | None = None
        self.to_mech_coords: Callable | None = None

    def _to_mech(self, scene_point: QPointF) -> tuple[float, float] | None:
        """Convert scene point to mechanism coordinates."""
        if self.to_mech_coords is None:
            return None
        try:
            import numpy as np

            arr = np.array([scene_point.x(), scene_point.y()], dtype=float)
            mech = self.to_mech_coords(arr)
            if hasattr(mech, "x"):
                return (float(mech.x()), float(mech.y()))
            return (float(mech[0]), float(mech[1]))
        except Exception:
            return None

    def _to_scene(self, mech_xy: tuple[float, float]) -> QPointF | None:
        """Convert mechanism coordinates to scene point."""
        if self.to_scene_coords is None:
            return None
        try:
            import numpy as np

            arr = np.array([mech_xy[0], mech_xy[1]], dtype=float)
            pt = self.to_scene_coords(arr)
            if hasattr(pt, "x"):
                return QPointF(pt.x(), pt.y())
            return QPointF(float(pt[0]), float(pt[1]))
        except Exception:
            return None

    def _reproject_handle(
        self, handle_id: str, mech_xy: tuple[float, float] | None
    ) -> None:
        """Reproject handle from mechanism to scene coordinates."""
        if handle_id not in self.handles or mech_xy is None:
            return
        pt = self._to_scene(mech_xy)
        if pt is not None:
            try:
                self.handles[handle_id].setPos(pt)
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

    @abstractmethod
    def create_handles(self, mechanism_data: dict[str, Any]) -> None:
        """Create interactive handles for the mechanism."""
        pass

    @abstractmethod
    def update_mechanism(self, param_changes: dict[str, Any]) -> dict[str, Any]:
        """Update mechanism parameters and return new simulation data."""
        pass

    @abstractmethod
    def update_visuals(self, simulation_data: dict[str, Any]) -> None:
        """Update visual representation based on simulation data."""
        pass

    def remove_handles(self) -> None:
        """Remove all handles from scene."""
        for handle in self.handles.values():
            if handle.scene():
                self.scene.removeItem(handle)
        self.handles.clear()

    def set_handles_visible(self, visible: bool) -> None:
        """Set visibility of all handles."""
        for handle in self.handles.values():
            handle.setVisible(visible)

    def get_current_parameters(self) -> dict[str, Any]:
        """Get current mechanism parameters."""
        try:
            params = self.mechanism_data.get("params", {})
            return dict(params)
        except Exception:
            return {}
