# Parametric Editor Module
# Lines: ~1200
# Public API: ParametricEditor, MechanismEditor, FourBarEditor, CamEditor, GearEditor, PlanetaryGearEditor
# Deps In: mechanism_design_tab.py
# Deps Out: PyQt6, numpy, logging, math
# Coupling: Low (interface-based design for mechanism editing)
# Cohesion: Feature (parametric editing functionality)
# Owner: Alan Synn
# Last Updated: 2025-01-20

"""
Parametric editor for interactive mechanism manipulation.
Provides intuitive handles and controls for modifying mechanism parameters in real-time.
"""

from __future__ import annotations
from typing import Any, Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import logging
import math
import numpy as np
from PyQt6.QtCore import (
    Qt, QPointF, QRectF, pyqtSignal, QObject, QTimer
)
from PyQt6.QtGui import (
    QPen, QBrush, QColor, QPainter, QPolygonF, QCursor
)
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsPolygonItem, QGraphicsScene, QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem, QWidget
)

if TYPE_CHECKING:
    from automataii.gui.tabs.mechanism_design_tab import MechanismDesignTab


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
    
    def __init__(self, 
                 center: QPointF,
                 handle_id: str,
                 param_name: str,
                 on_moved: Optional[Callable] = None,
                 style: Optional[HandleStyle] = None,
                 constraints: Optional[dict] = None):
        """
        Initialize parametric handle.
        
        Args:
            center: Initial position
            handle_id: Unique identifier
            param_name: Parameter being controlled
            on_moved: Callback for position changes
            style: Visual style configuration
            constraints: Movement constraints (min/max bounds, snap grid, etc.)
        """
        self.style = style or HandleStyle()
        # Centered local geometry: rect around origin; position is set via setPos(scene_center)
        super().__init__(-self.style.size/2, -self.style.size/2, self.style.size, self.style.size)
        
        self.handle_id = handle_id
        self.param_name = param_name
        self.on_moved = on_moved
        self.constraints = constraints or {}
        
        self._is_dragging = False
        self._drag_start = QPointF()
        self._original_pos = center
        
        self._setup_appearance()
        self._setup_interaction()
        # Place at initial scene position
        try:
            self.setPos(center)
        except Exception:
            pass
    
    def _setup_appearance(self):
        """Configure handle appearance."""
        self.setPen(QPen(self.style.border_color, self.style.border_width))
        self.setBrush(QBrush(self.style.color))
        self.setOpacity(self.style.opacity)
        self.setZValue(1000)  # Above mechanism visuals
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
            
            # Apply constraints
            new_pos = self._apply_constraints(new_pos)
            
            # Update position
            self.setPos(new_pos)
            
            # Notify callback
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
        if 'min_x' in self.constraints:
            x = max(x, self.constraints['min_x'])
        if 'max_x' in self.constraints:
            x = min(x, self.constraints['max_x'])
        if 'min_y' in self.constraints:
            y = max(y, self.constraints['min_y'])
        if 'max_y' in self.constraints:
            y = min(y, self.constraints['max_y'])

        # Fixed axis constraints
        if 'fixed_x' in self.constraints:
            try:
                x = float(self.constraints['fixed_x'])
            except Exception:
                pass
        if 'fixed_y' in self.constraints:
            try:
                y = float(self.constraints['fixed_y'])
            except Exception:
                pass
        
        # Grid snapping
        if 'snap_grid' in self.constraints:
            grid_size = self.constraints['snap_grid']
            x = round(x / grid_size) * grid_size
            y = round(y / grid_size) * grid_size
        
        # Distance constraints (e.g., maintain link length)
        if 'fixed_distance' in self.constraints:
            anchor = self.constraints['fixed_distance']['anchor']
            distance = self.constraints['fixed_distance']['distance']
            
            dx = x - anchor.x()
            dy = y - anchor.y()
            current_dist = math.sqrt(dx*dx + dy*dy)
            
            if current_dist > 0:
                scale = distance / current_dist
                x = anchor.x() + dx * scale
                y = anchor.y() + dy * scale

        # Radial constraints around a center (for cam profile, etc.)
        if 'center' in self.constraints and (
            'min_radius' in self.constraints or 'max_radius' in self.constraints or 'angle' in self.constraints
        ):
            c = self.constraints['center']
            dx = x - c.x()
            dy = y - c.y()
            r = math.sqrt(dx*dx + dy*dy)
            # Clamp radius if requested
            r_min = self.constraints.get('min_radius', 0.0)
            r_max = self.constraints.get('max_radius', float('inf'))
            r = max(r_min, min(r_max, r if r > 0 else r_min))
            # Lock angle if provided
            if 'angle' in self.constraints:
                ang_deg = float(self.constraints['angle'])
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
        # Coordinate transforms (optional). If set, they should be inverse pairs.
        self.to_scene_coords: Optional[Callable] = None  # mech -> scene
        self.to_mech_coords: Optional[Callable] = None   # scene -> mech

    # ------- Transform helpers -------
    def _to_mech(self, scene_point: QPointF) -> Optional[tuple[float, float]]:
        if self.to_mech_coords is None:
            return None
        try:
            import numpy as np
            arr = np.array([scene_point.x(), scene_point.y()], dtype=float)
            mech = self.to_mech_coords(arr)
            if hasattr(mech, 'x'):
                return (float(mech.x()), float(mech.y()))
            return (float(mech[0]), float(mech[1]))
        except Exception:
            return None

    def _to_scene(self, mech_xy: tuple[float, float]) -> Optional[QPointF]:
        if self.to_scene_coords is None:
            return None
        try:
            import numpy as np
            arr = np.array([mech_xy[0], mech_xy[1]], dtype=float)
            pt = self.to_scene_coords(arr)
            if hasattr(pt, 'x'):
                return QPointF(pt.x(), pt.y())
            return QPointF(float(pt[0]), float(pt[1]))
        except Exception:
            return None

    def _reproject_handle(self, handle_id: str, mech_xy: Optional[tuple[float, float]]) -> None:
        if handle_id not in self.handles or mech_xy is None:
            return
        pt = self._to_scene(mech_xy)
        if pt is not None:
            try:
                self.handles[handle_id].setPos(pt)
            except Exception:
                pass
    
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
        """Get current mechanism parameters (params sub-dict only)."""
        try:
            params = self.mechanism_data.get("params", {})
            # Return a shallow copy to avoid mutation by receivers
            return dict(params)
        except Exception:
            return {}


class FourBarEditor(MechanismEditor):
    """Editor for 4-bar linkage mechanisms with full vertex control."""
    
    def create_handles(self, mechanism_data: dict[str, Any]) -> None:
        """Create handles for all vertices and link midpoints."""
        self.mechanism_data = mechanism_data
        params = mechanism_data.get("params", {})
        
        # CRITICAL: Check if we're using raw params or need to extract from simulation data
        # The params contain scene coordinates already (set in _enable_parametric_mode)
        # But we should verify they're actually scene coordinates
        
        # Extract positions - these should already be in scene coordinates
        # from _enable_parametric_mode's transformation
        p1 = QPointF(params.get("anchor1_x", 0), params.get("anchor1_y", 0))
        p2 = QPointF(params.get("anchor2_x", 100), params.get("anchor2_y", 0))
        
        # Calculate other joint positions based on the anchors
        # These calculations should produce scene coordinates since anchors are in scene coords
        crank_pos = self._calculate_crank_position(p1, params)
        rocker_pos = self._calculate_rocker_position(p2, params)
        coupler_pos = self._calculate_coupler_position(params)
        
        # Create handles for all joints
        handle_configs = [
            ("anchor1", p1, "Fixed Pivot 1", self._on_anchor1_moved),
            ("anchor2", p2, "Fixed Pivot 2", self._on_anchor2_moved),
            ("crank", crank_pos, "Crank Joint", self._on_crank_moved),
            ("rocker", rocker_pos, "Rocker Joint", self._on_rocker_moved),
            ("coupler", coupler_pos, "Coupler Point", self._on_coupler_moved),
        ]
        
        # Create handles with appropriate constraints
        for handle_id, position, tooltip, callback in handle_configs:
            constraints = self._get_handle_constraints(handle_id)
            
            handle = ParametricHandle(
                position,
                f"{self.mechanism_id}_{handle_id}",
                handle_id,
                callback,
                style=self._get_handle_style(handle_id),
                constraints=constraints
            )
            handle.setToolTip(tooltip)
            
            self.scene.addItem(handle)
            self.handles[handle_id] = handle
        
        # Add link length adjustment handles (midpoints)
        self._create_link_handles()

        # Normalize handles to current transform (round-trip scene→mech→scene)
        try:
            for hid, h in self.handles.items():
                mech = self._to_mech(h.scenePos())
                if mech is not None:
                    self._reproject_handle(hid, mech)
        except Exception:
            pass
    
    def _create_link_handles(self):
        """Create handles at link midpoints for length adjustment."""
        # Get current joint positions
        if "anchor1" in self.handles and "crank" in self.handles:
            p1 = self.handles["anchor1"].scenePos()
            p_crank = self.handles["crank"].scenePos()
            
            # Crank length handle
            midpoint = (p1 + p_crank) / 2
            handle = ParametricHandle(
                midpoint,
                f"{self.mechanism_id}_crank_length",
                "crank_length",
                self._on_crank_length_changed,
                style=self._get_link_handle_style()
            )
            handle.setToolTip("Drag to adjust crank length")
            self.scene.addItem(handle)
            self.handles["crank_length"] = handle
    
    def _get_handle_style(self, handle_id: str) -> HandleStyle:
        """Get style for specific handle type."""
        if "anchor" in handle_id:
            return HandleStyle(
                size=14,
                color=QColor(100, 150, 255),
                hover_color=QColor(150, 200, 255)
            )
        elif handle_id == "coupler":
            return HandleStyle(
                size=10,
                color=QColor(255, 150, 100),
                hover_color=QColor(255, 200, 150)
            )
        else:
            return HandleStyle()
    
    def _get_link_handle_style(self) -> HandleStyle:
        """Get style for link adjustment handles."""
        return HandleStyle(
            size=8,
            color=QColor(150, 255, 150),
            hover_color=QColor(200, 255, 200),
            opacity=0.7
        )
    
    def _get_handle_constraints(self, handle_id: str) -> dict:
        """Get movement constraints for handle."""
        # Remove all constraints for anchors to allow free movement
        if handle_id in ["anchor1", "anchor2"]:
            # No constraints - allow completely free movement
            return {}
            
        # For other handles, apply reasonable constraints
        constraints = {
            'min_x': -2000,
            'max_x': 2000,
            'min_y': -2000,
            'max_y': 2000
        }
        
        # Add specific constraints based on handle type
        if handle_id == "crank":
            # Maintain crank length from anchor1
            if "anchor1" in self.handles:
                anchor_pos = self.handles["anchor1"].scenePos()
                crank_length = self.mechanism_data.get("params", {}).get("l2", 60)
                constraints['fixed_distance'] = {
                    'anchor': anchor_pos,
                    'distance': crank_length
                }
        elif handle_id == "rocker":
            # Maintain rocker length from anchor2
            if "anchor2" in self.handles:
                anchor_pos = self.handles["anchor2"].scenePos()
                rocker_length = self.mechanism_data.get("params", {}).get("l4", 70)
                constraints['fixed_distance'] = {
                    'anchor': anchor_pos,
                    'distance': rocker_length
                }
        
        return constraints
    
    def _calculate_crank_position(self, anchor1: QPointF, params: dict) -> QPointF:
        """Calculate crank joint position."""
        # First check if we have direct scene coordinates stored
        if "crank_x" in params and "crank_y" in params:
            return QPointF(params["crank_x"], params["crank_y"])
        
        # Otherwise calculate from angle and length
        angle = params.get("crank_angle", 0)
        length = params.get("l2", 60)
        x = anchor1.x() + length * math.cos(math.radians(angle))
        y = anchor1.y() + length * math.sin(math.radians(angle))
        return QPointF(x, y)
    
    def _calculate_rocker_position(self, anchor2: QPointF, params: dict) -> QPointF:
        """Calculate rocker joint position."""
        # First check if we have direct scene coordinates stored
        if "rocker_x" in params and "rocker_y" in params:
            return QPointF(params["rocker_x"], params["rocker_y"])
        
        # Otherwise calculate from angle and length
        angle = params.get("rocker_angle", 45)
        length = params.get("l4", 70)
        x = anchor2.x() + length * math.cos(math.radians(angle))
        y = anchor2.y() + length * math.sin(math.radians(angle))
        return QPointF(x, y)
    
    def _calculate_coupler_position(self, params: dict) -> QPointF:
        """Calculate coupler point position."""
        # Use the scene coordinates if available
        if "coupler_x" in params and "coupler_y" in params:
            return QPointF(params["coupler_x"], params["coupler_y"])
        
        # Fallback to default
        return QPointF(params.get("coupler_point_x", 350), params.get("coupler_point_y", 250))
    
    def _on_anchor1_moved(self, handle_id: str, new_pos: QPointF):
        """Handle anchor1 movement - allow free dragging."""
        # Compute delta from previous anchor position
        old_scene = QPointF(
            self.mechanism_data["params"].get("anchor1_x", new_pos.x()),
            self.mechanism_data["params"].get("anchor1_y", new_pos.y())
        )
        delta = new_pos - old_scene
        self._last_move_delta = delta

        # Update both scene and mechanism-space parameters
        self.mechanism_data["params"]["anchor1_x"] = new_pos.x()
        self.mechanism_data["params"]["anchor1_y"] = new_pos.y()
        mech = self._to_mech(new_pos)
        if mech is not None:
            self.mechanism_data["params"]["m_anchor1_x"] = mech[0]
            self.mechanism_data["params"]["m_anchor1_y"] = mech[1]
        
        # Update dependent handles to maintain linkage structure
        self._update_dependent_handles("anchor1", new_pos)
        # Reproject from mechanism-space to ensure consistency
        if mech is not None:
            self._reproject_handle("anchor1", mech)
        
        # Trigger visual update
        self._trigger_mechanism_update()
    
    def _on_anchor2_moved(self, handle_id: str, new_pos: QPointF):
        """Handle anchor2 movement - allow free dragging."""
        # Compute delta from previous anchor position
        old_scene = QPointF(
            self.mechanism_data["params"].get("anchor2_x", new_pos.x()),
            self.mechanism_data["params"].get("anchor2_y", new_pos.y())
        )
        delta = new_pos - old_scene
        self._last_move_delta = delta

        # Update both scene and mechanism-space parameters
        self.mechanism_data["params"]["anchor2_x"] = new_pos.x()
        self.mechanism_data["params"]["anchor2_y"] = new_pos.y()
        mech = self._to_mech(new_pos)
        if mech is not None:
            self.mechanism_data["params"]["m_anchor2_x"] = mech[0]
            self.mechanism_data["params"]["m_anchor2_y"] = mech[1]
        
        # Update dependent handles to maintain linkage structure
        self._update_dependent_handles("anchor2", new_pos)
        if mech is not None:
            self._reproject_handle("anchor2", mech)
        
        # Trigger visual update
        self._trigger_mechanism_update()
    
    def _on_crank_moved(self, handle_id: str, new_pos: QPointF):
        """Handle crank joint movement."""
        # Update crank angle and potentially length
        anchor1 = self.handles["anchor1"].scenePos()
        dx = new_pos.x() - anchor1.x()
        dy = new_pos.y() - anchor1.y()
        
        angle = math.degrees(math.atan2(dy, dx))
        length = math.sqrt(dx*dx + dy*dy)
        
        self.mechanism_data["params"]["crank_angle"] = angle
        self.mechanism_data["params"]["l2"] = length
        
        self._update_dependent_handles("crank", new_pos)
        mech = self._to_mech(new_pos)
        if mech is not None:
            self.mechanism_data["params"]["m_crank_x"] = mech[0]
            self.mechanism_data["params"]["m_crank_y"] = mech[1]
            self._reproject_handle("crank", mech)
        self._trigger_mechanism_update()
    
    def _on_rocker_moved(self, handle_id: str, new_pos: QPointF):
        """Handle rocker joint movement."""
        anchor2 = self.handles["anchor2"].scenePos()
        dx = new_pos.x() - anchor2.x()
        dy = new_pos.y() - anchor2.y()
        
        angle = math.degrees(math.atan2(dy, dx))
        length = math.sqrt(dx*dx + dy*dy)
        
        self.mechanism_data["params"]["rocker_angle"] = angle
        self.mechanism_data["params"]["l4"] = length
        
        mech = self._to_mech(new_pos)
        if mech is not None:
            self.mechanism_data["params"]["m_rocker_x"] = mech[0]
            self.mechanism_data["params"]["m_rocker_y"] = mech[1]
            self._reproject_handle("rocker", mech)
        self._trigger_mechanism_update()
    
    def _on_coupler_moved(self, handle_id: str, new_pos: QPointF):
        """Handle coupler point movement."""
        params = self.mechanism_data.get("params", {})
        params["coupler_x"] = new_pos.x()
        params["coupler_y"] = new_pos.y()

        # Normalize coupler offset to mechanism space (local to coupler link)
        try:
            # Require transforms and current crank/rocker positions
            if self.to_mech_coords and "crank" in self.handles and "rocker" in self.handles:
                p3_scene = self.handles["crank"].scenePos()
                p4_scene = self.handles["rocker"].scenePos()

                p3_mech = self._to_mech(p3_scene)
                p4_mech = self._to_mech(p4_scene)
                p_c_mech = self._to_mech(new_pos)

                if p3_mech is not None and p4_mech is not None and p_c_mech is not None:
                    import numpy as _np
                    v = _np.array([p4_mech[0] - p3_mech[0], p4_mech[1] - p3_mech[1]], dtype=float)
                    L = float(_np.hypot(v[0], v[1]))
                    if L > 1e-9:
                        u = v / L
                        n = _np.array([-u[1], u[0]], dtype=float)
                        rel = _np.array([p_c_mech[0] - p3_mech[0], p_c_mech[1] - p3_mech[1]], dtype=float)
                        params["coupler_point_x"] = float(rel.dot(u))
                        params["coupler_point_y"] = float(rel.dot(n))
        except Exception:
            # Keep scene-space coupler only if normalization failed
            pass

        self._trigger_mechanism_update()
    
    def _on_crank_length_changed(self, handle_id: str, new_pos: QPointF):
        """Handle crank length adjustment."""
        anchor1 = self.handles["anchor1"].scenePos()
        crank = self.handles["crank"].scenePos()
        
        # Calculate new length based on handle position
        # Project onto the line between anchor1 and crank
        v = crank - anchor1
        u = new_pos - anchor1
        
        if v.x() != 0 or v.y() != 0:
            t = (u.x() * v.x() + u.y() * v.y()) / (v.x() * v.x() + v.y() * v.y())
            t = max(0.3, min(2.0, t))  # Limit to 30% to 200% of original
            
            new_length = math.sqrt(v.x()*v.x() + v.y()*v.y()) * t
            self.mechanism_data["params"]["l2"] = new_length
            
            # Update crank position
            angle = math.degrees(math.atan2(v.y(), v.x()))
            new_crank_pos = QPointF(
                anchor1.x() + new_length * math.cos(math.radians(angle)),
                anchor1.y() + new_length * math.sin(math.radians(angle))
            )
            
            self.handles["crank"].setPos(new_crank_pos)
            
            self._trigger_mechanism_update()
    
    def _update_dependent_handles(self, changed_handle: str, new_pos: QPointF):
        """Update handles that depend on the changed handle."""
        if self._updating:
            return
        
        self._updating = True
        
        try:
            # Update link length handles
            if changed_handle in ["anchor1", "crank"] and "crank_length" in self.handles:
                p1 = self.handles["anchor1"].scenePos()
                p_crank = self.handles["crank"].scenePos()
                midpoint = (p1 + p_crank) / 2
                
                self.handles["crank_length"].setPos(midpoint)
        finally:
            self._updating = False
    
    def _trigger_mechanism_update(self):
        """Trigger mechanism simulation update without transformation."""
        if self._updating:
            return
        
        # Direct parameter pass-through without transformation
        # The positions are already in scene coordinates
        param_changes = {
            "anchor1_x": self.mechanism_data["params"]["anchor1_x"],
            "anchor1_y": self.mechanism_data["params"]["anchor1_y"],
            "anchor2_x": self.mechanism_data["params"]["anchor2_x"],
            "anchor2_y": self.mechanism_data["params"]["anchor2_y"],
            "l2": self.mechanism_data["params"].get("l2", 60),
            "l3": self.mechanism_data["params"].get("l3", 80),
            "l4": self.mechanism_data["params"].get("l4", 70)
        }
        
        # Store the changes directly without transformation
        self.mechanism_data["params"].update(param_changes)
        
        # Log without transformation messages
        logging.debug(f"[4BAR-EDITOR] Updated mechanism parameters")
    
    def update_mechanism(self, param_changes: dict[str, Any]) -> dict[str, Any]:
        """Update mechanism and return new simulation data."""
        # Update internal data
        for key, value in param_changes.items():
            if key in self.mechanism_data["params"]:
                self.mechanism_data["params"][key] = value
        
        # Perform 4-bar simulation
        simulation_data = self._simulate_4bar_motion()
        
        return simulation_data
    
    def _simulate_4bar_motion(self) -> dict[str, Any]:
        """Simulate 4-bar linkage motion."""
        params = self.mechanism_data["params"]
        
        # Extract parameters
        p1 = np.array([params["anchor1_x"], params["anchor1_y"]])
        p2 = np.array([params["anchor2_x"], params["anchor2_y"]])
        l1 = np.linalg.norm(p2 - p1)  # Ground link
        l2 = params["l2"]  # Crank
        l3 = params.get("l3", 80)  # Coupler
        l4 = params["l4"]  # Rocker
        
        # Generate motion path
        angles = np.linspace(0, 360, 100)
        path_points = []
        
        for angle in angles:
            # Calculate crank position
            theta2 = np.radians(angle)
            p3 = p1 + l2 * np.array([np.cos(theta2), np.sin(theta2)])
            
            # Solve for rocker position (simplified)
            # In reality, this needs proper 4-bar kinematics solution
            # Using circle intersection to find p4
            
            # Distance from p3 to p2
            d = np.linalg.norm(p3 - p2)
            
            if d > l3 + l4 or d < abs(l3 - l4):
                # No solution - mechanism locked
                continue
            
            # Calculate rocker angle
            a = (d*d + l4*l4 - l3*l3) / (2 * d * l4)
            a = np.clip(a, -1, 1)
            theta4_offset = np.arccos(a)
            
            # Base angle from p2 to p3
            base_angle = np.arctan2(p3[1] - p2[1], p3[0] - p2[0])
            
            # Rocker position
            theta4 = base_angle + theta4_offset
            p4 = p2 + l4 * np.array([np.cos(theta4), np.sin(theta4)])
            
            # Coupler point (on the line from p3 to p4)
            t = 0.5  # Midpoint for now
            coupler = p3 * (1 - t) + p4 * t
            
            path_points.append({
                "angle": angle,
                "crank": p3.tolist(),
                "rocker": p4.tolist(),
                "coupler": coupler.tolist()
            })
        
        return {
            "type": "4bar",
            "path": path_points,
            "params": params
        }
    
    def update_visuals(self, simulation_data: dict[str, Any]) -> None:
        """Update mechanism visuals based on simulation."""
        # This would update the visual representation
        # Implementation depends on the visualization system
        pass


class CamEditor(MechanismEditor):
    """Editor for cam mechanisms with physics-based follower."""
    
    def create_handles(self, mechanism_data: dict[str, Any]) -> None:
        """Create handles for cam shape and follower rod."""
        self.mechanism_data = mechanism_data
        params = mechanism_data.get("params", {})
        
        # Get cam position - use stored position if available
        if 'cam_position' in mechanism_data:
            cam_position = mechanism_data['cam_position']
            center = QPointF(cam_position[0], cam_position[1])
        else:
            # Fallback to default center if not specified
            center = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        
        # Store center in params for consistency
        params["center_x"] = center.x()
        params["center_y"] = center.y()
        
        # Cam center handle
        center_handle = ParametricHandle(
            center,
            f"{self.mechanism_id}_center",
            "center",
            self._on_center_moved,
            style=HandleStyle(size=16, color=QColor(100, 200, 100))
        )
        center_handle.setToolTip("Cam Center - Drag to move")
        self.scene.addItem(center_handle)
        self.handles["center"] = center_handle
        
        # Ensure defaults for core cam parameters
        base_radius = float(params.get("base_radius", 25.0))
        eccentricity = float(params.get("eccentricity", 10.0))
        params["base_radius"] = base_radius
        params["eccentricity"] = eccentricity

        # Default analytic cam phase parameters
        params.setdefault("rise_deg", 90.0)
        params.setdefault("high_dwell_deg", 60.0)
        params.setdefault("return_deg", 30.0)
        params.setdefault("align_max_deg", 90.0)

        # Follower rod length handle
        self._create_follower_handle(params)

        # Angle handles for profile control (rise/return/dwells orientation)
        try:
            self._create_cam_angle_handles(QPointF(params.get("center_x", 0), params.get("center_y", 0)), params)
        except Exception as e:
            logging.debug(f"[CAM-EDITOR] Skipped angle handles: {e}")
    
    def _create_profile_handles(self, params: dict):
        """Create handles for cam profile control."""
        center = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        base_radius = params.get("base_radius", 40)
        
        # Create 8 control points around the cam
        num_points = 8
        for i in range(num_points):
            angle = i * 360 / num_points
            rad = math.radians(angle)
            
            # Get radius at this angle from profile
            radius = self._get_cam_radius_at_angle(angle, params)
            
            x = center.x() + radius * math.cos(rad)
            y = center.y() + radius * math.sin(rad)
            
            handle = ParametricHandle(
                QPointF(x, y),
                f"{self.mechanism_id}_profile_{i}",
                f"profile_{i}",
                lambda hid, pos, idx=i: self._on_profile_moved(idx, pos),
                style=HandleStyle(size=10, color=QColor(255, 200, 100))
            )
            handle.setToolTip(f"Profile Point {i} - Drag to reshape cam")
            
            # Constrain to radial movement
            handle.constraints = {
                'min_radius': base_radius * 0.8,
                'max_radius': base_radius * 2.0,
                'center': center,
                'angle': angle
            }
            
            self.scene.addItem(handle)
            self.handles[f"profile_{i}"] = handle
    
    def _create_follower_handle(self, params: dict):
        """Create handle for follower rod adjustment."""
        center = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        base_radius = params.get("base_radius", 25.0)
        rod_length = params.get("follower_rod_length", 40.0)
        
        # Get scaling factors if available
        cam_scale_factor = self.mechanism_data.get('cam_scale_factor', 1.0)
        rod_length_multiplier = self.mechanism_data.get('rod_length_multiplier', 1.0)
        
        # Apply scaling
        scaled_base_radius = base_radius * cam_scale_factor
        scaled_rod_length = rod_length * rod_length_multiplier
        
        # Position follower above cam (gravity physics)
        # Follower should be above the cam by base_radius + rod_length
        follower_pos = QPointF(center.x(), center.y() - (scaled_base_radius + scaled_rod_length))
        
        handle = ParametricHandle(
            follower_pos,
            f"{self.mechanism_id}_follower",
            "follower",
            self._on_follower_moved,
            style=HandleStyle(size=12, color=QColor(100, 100, 255))
        )
        handle.setToolTip("Follower Rod - Drag vertically to adjust length")
        
        # Constrain to vertical movement only
        handle.constraints = {
            'min_y': center.y() - 300,  # Maximum rod length
            'max_y': center.y() - (scaled_base_radius + 20),  # Minimum rod length (must be above cam)
            'fixed_x': center.x()  # Keep horizontally aligned with cam center
        }
        
        self.scene.addItem(handle)
        self.handles["follower"] = handle
    
    def _get_cam_radius_at_angle(self, angle: float, params: dict) -> float:
        """Get cam radius at specific angle."""
        base_radius = params.get("base_radius", 40)
        lift = params.get("lift", 20)
        
        # Simple sinusoidal cam profile
        # Can be replaced with more complex profiles
        profile_angle = math.radians(angle)
        radius = base_radius + lift * (1 + math.cos(profile_angle)) / 2
        
        return radius
    
    def _on_center_moved(self, handle_id: str, new_pos: QPointF):
        """Handle cam center movement - update all related fields."""
        old_center = QPointF(
            self.mechanism_data["params"].get("center_x", 0),
            self.mechanism_data["params"].get("center_y", 0)
        )
        
        # Update center position in params (scene and mech)
        self.mechanism_data["params"]["center_x"] = new_pos.x()
        self.mechanism_data["params"]["center_y"] = new_pos.y()
        mech = self._to_mech(new_pos)
        if mech is not None:
            self.mechanism_data["params"]["m_center_x"] = mech[0]
            self.mechanism_data["params"]["m_center_y"] = mech[1]
        
        # CRITICAL: Also update cam_position for visual creation
        self.mechanism_data["cam_position"] = [new_pos.x(), new_pos.y()]
        
        # Update key_points if it exists
        if "key_points" not in self.mechanism_data:
            self.mechanism_data["key_points"] = {}
        self.mechanism_data["key_points"]["cam_center"] = [new_pos.x(), new_pos.y()]
        
        logging.debug(f"[CAM-EDITOR] Updated center to ({new_pos.x():.1f}, {new_pos.y():.1f})")
        
        # Calculate offset for moving other handles
        offset = new_pos - old_center
        
        # Move follower handle to maintain relative position
        if "follower" in self.handles:
            follower_handle = self.handles["follower"]
            # Update follower's constraint to follow cam center
            follower_handle.constraints['fixed_x'] = new_pos.x()
            # Move follower vertically with cam
            current_follower_pos = follower_handle.scenePos()
            new_follower_pos = current_follower_pos + offset
            follower_handle.setPos(new_follower_pos)
        
        self._trigger_cam_update()
    
    def _on_profile_moved(self, index: int, new_pos: QPointF):
        """Handle cam profile point movement."""
        center = QPointF(
            self.mechanism_data["params"]["center_x"],
            self.mechanism_data["params"]["center_y"]
        )
        
        # Calculate new radius
        dx = new_pos.x() - center.x()
        dy = new_pos.y() - center.y()
        new_radius = math.sqrt(dx*dx + dy*dy)
        
        # Store profile modification
        if "profile_mods" not in self.mechanism_data["params"]:
            self.mechanism_data["params"]["profile_mods"] = {}
        
        angle = index * 360 / 8
        self.mechanism_data["params"]["profile_mods"][angle] = new_radius
        
        self._trigger_cam_update()
    
    def _on_follower_moved(self, handle_id: str, new_pos: QPointF):
        """Handle follower movement - adjust rod length."""
        center = QPointF(
            self.mechanism_data["params"]["center_x"],
            self.mechanism_data["params"]["center_y"]
        )
        
        # Get current scaling factors
        base_radius = self.mechanism_data["params"].get("base_radius", 25.0)
        cam_scale_factor = self.mechanism_data.get('cam_scale_factor', 1.0)
        scaled_base_radius = base_radius * cam_scale_factor
        
        # Calculate new rod length based on follower position
        # Follower is above cam, so rod_length = |center.y - follower.y| - base_radius
        distance_from_center = abs(center.y() - new_pos.y())
        new_rod_length = max(20, distance_from_center - scaled_base_radius)  # Minimum rod length of 20
        
        # Update rod length in params (unscaled value)
        rod_length_multiplier = self.mechanism_data.get('rod_length_multiplier', 1.0)
        if rod_length_multiplier > 0:
            self.mechanism_data["params"]["follower_rod_length"] = new_rod_length / rod_length_multiplier
        else:
            self.mechanism_data["params"]["follower_rod_length"] = new_rod_length
        
        # Store mech-space follower y if needed in future (optional)
        self._trigger_cam_update()

    # ===== Cam angle handles and helpers =====
    def _create_cam_angle_handles(self, center: QPointF, params: dict) -> None:
        ui_radius = 50.0

        def pos_for_angle(deg: float) -> QPointF:
            a = math.radians(deg)
            return QPointF(center.x() + ui_radius * math.cos(a), center.y() + ui_radius * math.sin(a))

        align_max = float(params.get("align_max_deg", 90.0))
        rise_deg = float(params.get("rise_deg", 90.0))
        high_dwell_deg = float(params.get("high_dwell_deg", 60.0))
        return_deg = float(params.get("return_deg", 30.0))

        angles_abs = {
            "align_max": align_max,
            "rise_end": self._wrap_deg(align_max + rise_deg),
            "dwell_high_end": self._wrap_deg(align_max + rise_deg + high_dwell_deg),
            "return_end": self._wrap_deg(align_max + rise_deg + high_dwell_deg + return_deg),
        }

        constraints = {
            'center': center,
            'min_radius': ui_radius,
            'max_radius': ui_radius,
        }

        defs = [
            ("align_max", "Align Max (orientation)", self._on_align_max_moved),
            ("rise_end", "Rise End", self._on_rise_end_moved),
            ("dwell_high_end", "High Dwell End", self._on_dwell_high_end_moved),
            ("return_end", "Return End", self._on_return_end_moved),
        ]

        for hid, tip, cb in defs:
            handle = ParametricHandle(
                pos_for_angle(angles_abs[hid]),
                f"{self.mechanism_id}_{hid}",
                hid,
                cb,
                style=HandleStyle(size=10, color=QColor(220, 120, 80)),
                constraints=constraints,
            )
            handle.setToolTip(tip)
            self.scene.addItem(handle)
            self.handles[hid] = handle

    def _wrap_deg(self, deg: float) -> float:
        d = deg % 360.0
        return d + 360.0 if d < 0 else d

    def _angle_from(self, origin: QPointF, p: QPointF) -> float:
        return self._wrap_deg(math.degrees(math.atan2(p.y() - origin.y(), p.x() - origin.x())))

    def _pos_angle_diff(self, start_deg: float, end_deg: float) -> float:
        d = self._wrap_deg(end_deg) - self._wrap_deg(start_deg)
        return d if d >= 0 else d + 360.0

    def _refresh_angle_handles(self) -> None:
        params = self.mechanism_data.get("params", {})
        center = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        ui_radius = 50.0
        def pos_for_angle(deg: float) -> QPointF:
            a = math.radians(deg)
            return QPointF(center.x() + ui_radius * math.cos(a), center.y() + ui_radius * math.sin(a))

        align = float(params.get("align_max_deg", 90.0))
        rise = float(params.get("rise_deg", 90.0))
        dwell = float(params.get("high_dwell_deg", 60.0))
        ret = float(params.get("return_deg", 30.0))

        targets = {
            "align_max": align,
            "rise_end": self._wrap_deg(align + rise),
            "dwell_high_end": self._wrap_deg(align + rise + dwell),
            "return_end": self._wrap_deg(align + rise + dwell + ret),
        }
        for hid, ang in targets.items():
            h = self.handles.get(hid)
            if h:
                try:
                    h.setPos(pos_for_angle(ang))
                except Exception:
                    pass

    # Callbacks for angle handle moves
    def _on_align_max_moved(self, handle_id: str, new_pos: QPointF):
        params = self.mechanism_data.get("params", {})
        c = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        params["align_max_deg"] = float(self._angle_from(c, new_pos))
        self._refresh_angle_handles()
        self._trigger_cam_update()

    def _on_rise_end_moved(self, handle_id: str, new_pos: QPointF):
        params = self.mechanism_data.get("params", {})
        c = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        align = float(params.get("align_max_deg", 90.0))
        end = float(self._angle_from(c, new_pos))
        params["rise_deg"] = float(self._pos_angle_diff(align, end))
        self._refresh_angle_handles()
        self._trigger_cam_update()

    def _on_dwell_high_end_moved(self, handle_id: str, new_pos: QPointF):
        params = self.mechanism_data.get("params", {})
        c = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        align = float(params.get("align_max_deg", 90.0))
        rise = float(params.get("rise_deg", 90.0))
        end = float(self._angle_from(c, new_pos))
        params["high_dwell_deg"] = float(self._pos_angle_diff(align + rise, end))
        self._refresh_angle_handles()
        self._trigger_cam_update()

    def _on_return_end_moved(self, handle_id: str, new_pos: QPointF):
        params = self.mechanism_data.get("params", {})
        c = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        align = float(params.get("align_max_deg", 90.0))
        rise = float(params.get("rise_deg", 90.0))
        dwell = float(params.get("high_dwell_deg", 60.0))
        end = float(self._angle_from(c, new_pos))
        params["return_deg"] = float(self._pos_angle_diff(align + rise + dwell, end))
        self._refresh_angle_handles()
        self._trigger_cam_update()
    
    def _trigger_cam_update(self):
        """Trigger cam mechanism update - let the main system handle it."""
        # Don't do local simulation - let the parametric system handle updates
        # This will be called through the _queue_update callback
        logging.debug(f"[CAM-EDITOR] Triggered update for cam mechanism")
    
    def _simulate_cam_follower_physics(self) -> dict[str, Any]:
        """Simulate cam-follower interaction with proper physics."""
        params = self.mechanism_data["params"]
        center = np.array([params["center_x"], params["center_y"]])
        rod_length = params["follower_rod_length"]
        
        # Generate cam rotation angles
        angles = np.linspace(0, 360, 100)
        follower_positions = []
        cam_profiles = []
        
        for angle in angles:
            # Get cam radius at current angle
            radius = self._get_cam_radius_at_angle(angle, params)
            
            # Apply profile modifications if any
            if "profile_mods" in params:
                # Interpolate modifications
                for mod_angle, mod_radius in params["profile_mods"].items():
                    if abs(angle - mod_angle) < 45:  # Influence range
                        weight = 1 - abs(angle - mod_angle) / 45
                        radius = radius * (1 - weight) + mod_radius * weight
            
            # Calculate cam profile point
            rad = math.radians(angle)
            cam_point = center + radius * np.array([np.cos(rad), np.sin(rad)])
            cam_profiles.append(cam_point.tolist())
            
            # Calculate follower position (maintaining contact)
            # The follower must maintain contact with the cam surface
            # For a flat-faced follower
            follower_y = center[1] - radius - rod_length
            
            # Add spring force for more realistic motion
            spring_force = 0.1 * (follower_y - (center[1] - params["base_radius"] - rod_length))
            follower_y += spring_force
            
            follower_positions.append([center[0], follower_y])
        
        return {
            "type": "cam",
            "cam_profile": cam_profiles,
            "follower_path": follower_positions,
            "params": params
        }
    
    def update_mechanism(self, param_changes: dict[str, Any]) -> dict[str, Any]:
        """Update cam mechanism."""
        for key, value in param_changes.items():
            if key in self.mechanism_data["params"]:
                self.mechanism_data["params"][key] = value
        
        return self._simulate_cam_follower_physics()
    
    def update_visuals(self, simulation_data: dict[str, Any]) -> None:
        """Update cam visuals."""
        # Implementation depends on visualization system
        pass


class GearEditor(MechanismEditor):
    """Editor for gear mechanisms with position and size control."""
    
    def create_handles(self, mechanism_data: dict[str, Any]) -> None:
        """Create handles for gear position and size."""
        self.mechanism_data = mechanism_data
        params = mechanism_data.get("params", {})
        
        # Gear 1 (driver) handles
        self._create_gear_handles(
            gear_id="gear1",
            center=QPointF(params.get("gear1_x", 0), params.get("gear1_y", 0)),
            radius=params.get("gear1_radius", 40),
            is_driver=True
        )
        
        # Gear 2 (driven) handles  
        self._create_gear_handles(
            gear_id="gear2",
            center=QPointF(params.get("gear2_x", 100), params.get("gear2_y", 0)),
            radius=params.get("gear2_radius", 60),
            is_driver=False
        )
        
        # Mesh adjustment handle
        self._create_mesh_handle()
    
    def _create_gear_handles(self, gear_id: str, center: QPointF, 
                            radius: float, is_driver: bool):
        """Create handles for a single gear."""
        # Center handle for position
        center_handle = ParametricHandle(
            center,
            f"{self.mechanism_id}_{gear_id}_center",
            f"{gear_id}_center",
            lambda hid, pos, gid=gear_id: self._on_gear_center_moved(gid, pos),
            style=HandleStyle(
                size=14,
                color=QColor(100, 200, 100) if is_driver else QColor(100, 100, 200)
            )
        )
        center_handle.setToolTip(f"{gear_id.title()} Center - Drag to move")
        self.scene.addItem(center_handle)
        self.handles[f"{gear_id}_center"] = center_handle
        
        # Radius handle for size
        radius_pos = QPointF(center.x() + radius, center.y())
        radius_handle = ParametricHandle(
            radius_pos,
            f"{self.mechanism_id}_{gear_id}_radius",
            f"{gear_id}_radius",
            lambda hid, pos, gid=gear_id: self._on_gear_radius_changed(gid, pos),
            style=HandleStyle(size=10, color=QColor(255, 200, 100))
        )
        radius_handle.setToolTip(f"{gear_id.title()} Radius - Drag to resize")
        
        # Constrain to radial movement
        radius_handle.constraints = {
            'center': center,
            'min_radius': 20,
            'max_radius': 150
        }
        
        self.scene.addItem(radius_handle)
        self.handles[f"{gear_id}_radius"] = radius_handle
    
    def _create_mesh_handle(self):
        """Create handle for adjusting gear meshing."""
        params = self.mechanism_data["params"]
        
        # Position between gears
        center1 = QPointF(params.get("gear1_x", 0), params.get("gear1_y", 0))
        center2 = QPointF(params.get("gear2_x", 100), params.get("gear2_y", 0))
        midpoint = (center1 + center2) / 2
        
        mesh_handle = ParametricHandle(
            midpoint,
            f"{self.mechanism_id}_mesh",
            "mesh",
            self._on_mesh_adjusted,
            style=HandleStyle(size=8, color=QColor(255, 255, 100), opacity=0.6)
        )
        mesh_handle.setToolTip("Gear Mesh - Drag to adjust spacing")
        
        self.scene.addItem(mesh_handle)
        self.handles["mesh"] = mesh_handle
    
    def _on_gear_center_moved(self, gear_id: str, new_pos: QPointF):
        """Handle gear center movement."""
        # Update position
        self.mechanism_data["params"][f"{gear_id}_x"] = new_pos.x()
        self.mechanism_data["params"][f"{gear_id}_y"] = new_pos.y()
        
        # Update radius handle position
        radius_handle_key = f"{gear_id}_radius"
        if radius_handle_key in self.handles:
            radius = self.mechanism_data["params"][f"{gear_id}_radius"]
            radius_handle = self.handles[radius_handle_key]
            radius_handle.setPos(
                QPointF(new_pos.x() + radius, new_pos.y()) -
                QPointF(radius_handle.style.size/2, radius_handle.style.size/2)
            )
            radius_handle.constraints['center'] = new_pos
        
        # Update mesh handle
        self._update_mesh_handle()
        
        # Auto-adjust meshing
        self._auto_adjust_gear_mesh()
        
        self._trigger_gear_update()
    
    def _on_gear_radius_changed(self, gear_id: str, new_pos: QPointF):
        """Handle gear radius change."""
        center = QPointF(
            self.mechanism_data["params"][f"{gear_id}_x"],
            self.mechanism_data["params"][f"{gear_id}_y"]
        )
        
        # Calculate new radius
        dx = new_pos.x() - center.x()
        dy = new_pos.y() - center.y()
        new_radius = math.sqrt(dx*dx + dy*dy)
        
        # Update radius
        self.mechanism_data["params"][f"{gear_id}_radius"] = new_radius
        
        # Auto-adjust meshing to maintain contact
        self._auto_adjust_gear_mesh()
        
        self._trigger_gear_update()
    
    def _on_mesh_adjusted(self, handle_id: str, new_pos: QPointF):
        """Handle mesh adjustment."""
        # Calculate new spacing based on handle position
        center1 = QPointF(
            self.mechanism_data["params"]["gear1_x"],
            self.mechanism_data["params"]["gear1_y"]
        )
        center2 = QPointF(
            self.mechanism_data["params"]["gear2_x"],
            self.mechanism_data["params"]["gear2_y"]
        )
        
        # Project new position onto line between centers
        v = center2 - center1
        u = new_pos - center1
        
        if v.x() != 0 or v.y() != 0:
            t = (u.x() * v.x() + u.y() * v.y()) / (v.x() * v.x() + v.y() * v.y())
            t = max(0.3, min(0.7, t))  # Keep handle between gears
            
            # Adjust gear2 position to change spacing
            new_center2 = center1 + v * (2 * t)
            self.mechanism_data["params"]["gear2_x"] = new_center2.x()
            self.mechanism_data["params"]["gear2_y"] = new_center2.y()
            
            # Update gear2 center handle
            if "gear2_center" in self.handles:
                handle = self.handles["gear2_center"]
                handle.setPos(
                    new_center2 - QPointF(handle.style.size/2, handle.style.size/2)
                )
            
            self._trigger_gear_update()
    
    def _update_mesh_handle(self):
        """Update mesh handle position."""
        if "mesh" not in self.handles:
            return
        
        center1 = QPointF(
            self.mechanism_data["params"]["gear1_x"],
            self.mechanism_data["params"]["gear1_y"]
        )
        center2 = QPointF(
            self.mechanism_data["params"]["gear2_x"],
            self.mechanism_data["params"]["gear2_y"]
        )
        
        midpoint = (center1 + center2) / 2
        handle = self.handles["mesh"]
        handle.setPos(
            midpoint - QPointF(handle.style.size/2, handle.style.size/2)
        )
    
    def _auto_adjust_gear_mesh(self):
        """Automatically adjust gear positions for proper meshing."""
        params = self.mechanism_data["params"]
        
        center1 = np.array([params["gear1_x"], params["gear1_y"]])
        center2 = np.array([params["gear2_x"], params["gear2_y"]])
        r1 = params["gear1_radius"]
        r2 = params["gear2_radius"]
        
        # Calculate current distance
        current_distance = np.linalg.norm(center2 - center1)
        
        # Ideal distance for proper meshing (with small clearance)
        ideal_distance = r1 + r2 + 2  # 2 units clearance
        
        if abs(current_distance - ideal_distance) > 0.1:
            # Adjust gear2 position to achieve ideal distance
            direction = (center2 - center1) / current_distance if current_distance > 0 else np.array([1, 0])
            new_center2 = center1 + direction * ideal_distance
            
            params["gear2_x"] = new_center2[0]
            params["gear2_y"] = new_center2[1]
            
            # Update handles
            if "gear2_center" in self.handles:
                handle = self.handles["gear2_center"]
                handle.setPos(
                    QPointF(new_center2[0], new_center2[1]) - 
                    QPointF(handle.style.size/2, handle.style.size/2)
                )
    
    def _trigger_gear_update(self):
        """Trigger gear mechanism update."""
        simulation_data = self._simulate_gear_motion()
        self.update_visuals(simulation_data)
    
    def _simulate_gear_motion(self) -> dict[str, Any]:
        """Simulate gear motion."""
        params = self.mechanism_data["params"]
        
        # Calculate gear ratio
        r1 = params["gear1_radius"]
        r2 = params["gear2_radius"]
        gear_ratio = r2 / r1
        
        # Generate motion data
        angles = np.linspace(0, 360, 100)
        gear1_angles = angles
        gear2_angles = -angles / gear_ratio  # Opposite direction
        
        return {
            "type": "gear",
            "gear1_angles": gear1_angles.tolist(),
            "gear2_angles": gear2_angles.tolist(),
            "params": params
        }
    
    def update_mechanism(self, param_changes: dict[str, Any]) -> dict[str, Any]:
        """Update gear mechanism."""
        for key, value in param_changes.items():
            if key in self.mechanism_data["params"]:
                self.mechanism_data["params"][key] = value
        
        return self._simulate_gear_motion()
    
    def update_visuals(self, simulation_data: dict[str, Any]) -> None:
        """Update gear visuals."""
        # Implementation depends on visualization system
        pass




class PlanetaryGearEditor(MechanismEditor):
    """Editor for planetary gears with basic controls (sun center, planet radius, arm length)."""

    def create_handles(self, mechanism_data: dict[str, Any]) -> None:
        self.mechanism_data = mechanism_data
        params = mechanism_data.get("params", {})
        # Defaults
        cx = float(params.get("sun_x", 0.0)); cy = float(params.get("sun_y", 0.0))
        r_sun = float(params.get("r_sun", 20.0))
        r_planet = float(params.get("r_planet", 30.0))
        arm_length = float(params.get("arm_length", 15.0))
        params["sun_x"], params["sun_y"] = cx, cy
        params["r_sun"], params["r_planet"], params["arm_length"] = r_sun, r_planet, arm_length
        center = QPointF(cx, cy)
        # Sun center handle
        sun_center = ParametricHandle(center, f"{self.mechanism_id}_sun_center", "sun_center", self._on_sun_center_moved, style=HandleStyle(size=14, color=QColor(200,200,80)))
        sun_center.setToolTip("Sun Center - Drag to move")
        self.scene.addItem(sun_center); self.handles["sun_center"] = sun_center
        # Planet radius handle (controls r_planet)
        pr_handle = ParametricHandle(QPointF(cx + r_planet, cy), f"{self.mechanism_id}_planet_radius", "planet_radius", self._on_planet_radius_changed, style=HandleStyle(size=10, color=QColor(255, 200, 100)))
        pr_handle.setToolTip("Planet Radius - Drag to resize")
        pr_handle.constraints = {'center': center, 'min_radius': 5.0, 'max_radius': 200.0}
        self.scene.addItem(pr_handle); self.handles["planet_radius"] = pr_handle
        # Arm length handle (from initial planet pos)
        arm_pos = QPointF(cx + r_sun + r_planet + arm_length, cy)
        arm_handle = ParametricHandle(arm_pos, f"{self.mechanism_id}_arm_length", "arm_length", self._on_arm_length_changed, style=HandleStyle(size=8, color=QColor(255,255,100)))
        arm_handle.setToolTip("Arm Length - Drag radially to adjust")
        arm_handle.constraints = {'center': QPointF(cx + r_sun + r_planet, cy), 'min_radius': 0.0, 'max_radius': 300.0}
        self.scene.addItem(arm_handle); self.handles["arm_length"] = arm_handle

    def _on_sun_center_moved(self, handle_id: str, new_pos: QPointF):
        self.mechanism_data["params"]["sun_x"] = float(new_pos.x())
        self.mechanism_data["params"]["sun_y"] = float(new_pos.y())
        # Update dependent constraint centers
        if "planet_radius" in self.handles:
            self.handles["planet_radius"].constraints['center'] = new_pos
        if "arm_length" in self.handles:
            r_sun = float(self.mechanism_data["params"].get("r_sun", 20.0))
            r_planet = float(self.mechanism_data["params"].get("r_planet", 30.0))
            self.handles["arm_length"].constraints['center'] = QPointF(new_pos.x() + r_sun + r_planet, new_pos.y())
        self._trigger_update()

    def _on_planet_radius_changed(self, handle_id: str, new_pos: QPointF):
        c = QPointF(self.mechanism_data["params"].get("sun_x", 0.0), self.mechanism_data["params"].get("sun_y", 0.0))
        dx, dy = new_pos.x() - c.x(), new_pos.y() - c.y()
        r = (dx*dx + dy*dy) ** 0.5
        self.mechanism_data["params"]["r_planet"] = float(max(1.0, r))
        # Update arm length center
        if "arm_length" in self.handles:
            r_sun = float(self.mechanism_data["params"].get("r_sun", 20.0))
            self.handles["arm_length"].constraints['center'] = QPointF(c.x() + r_sun + r, c.y())
        self._trigger_update()

    def _on_arm_length_changed(self, handle_id: str, new_pos: QPointF):
        c = QPointF(self.mechanism_id and self.mechanism_data["params"].get("sun_x", 0.0), self.mechanism_data["params"].get("sun_y", 0.0))
        r_sun = float(self.mechanism_data["params"].get("r_sun", 20.0))
        r_planet = float(self.mechanism_data["params"].get("r_planet", 30.0))
        arm_center = QPointF(c.x() + r_sun + r_planet, c.y())
        dx, dy = new_pos.x() - arm_center.x(), new_pos.y() - arm_center.y()
        arm_len = max(0.0, (dx*dx + dy*dy) ** 0.5)
        self.mechanism_data["params"]["arm_length"] = float(arm_len)
        self._trigger_update()

    def _trigger_update(self):
        # No local simulation; rely on parametric manager to regenerate visuals
        pass

    def update_mechanism(self, param_changes: dict[str, Any]) -> dict[str, Any]:
        for k, v in param_changes.items():
            if k in self.mechanism_data.get("params", {}):
                self.mechanism_data["params"][k] = v
        return {"type": "planetary_gear", "params": self.mechanism_data.get("params", {})}

    def update_visuals(self, simulation_data: dict[str, Any]) -> None:
        pass
class ParametricEditor(QObject):
    """Main parametric editor controller."""
    
    # Signals
    mechanism_updated = pyqtSignal(str, dict)  # mechanism_id, params
    visual_refresh_requested = pyqtSignal(str)  # mechanism_id
    
    def __init__(self, scene: QGraphicsScene):
        """
        Initialize parametric editor.
        
        Args:
            scene: Graphics scene for handles
        """
        super().__init__()
        self.scene = scene
        self.editors: dict[str, MechanismEditor] = {}
        self.active_editor: Optional[MechanismEditor] = None
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._process_updates)
        self._update_timer.setInterval(16)  # ~60 FPS
        self._pending_updates: set[str] = set()
    
    def create_editor(self, mechanism_id: str, mechanism_data: dict[str, Any]) -> MechanismEditor:
        """
        Create appropriate editor for mechanism type.
        
        Args:
            mechanism_id: Unique mechanism identifier
            mechanism_data: Mechanism configuration data
            
        Returns:
            Created mechanism editor
        """
        mechanism_type = mechanism_data.get("type")
        
        # Remove existing editor if any
        if mechanism_id in self.editors:
            self.remove_editor(mechanism_id)
        
        # Create new editor based on type
        if mechanism_type == "4_bar_linkage":
            editor = FourBarEditor(mechanism_id, self.scene)
        elif mechanism_type == "cam":
            editor = CamEditor(mechanism_id, self.scene)
        elif mechanism_type in ["gear", "simple_gear"]:
            editor = GearEditor(mechanism_id, self.scene)
        elif mechanism_type == "planetary_gear":
            editor = PlanetaryGearEditor(mechanism_id, self.scene)
        else:
            logging.warning(f"Unknown mechanism type: {mechanism_type}")
            return None
        
        # Initialize editor
        editor.create_handles(mechanism_data)
        # Store the original mechanism data for reference
        editor.original_mechanism_data = mechanism_data
        self.editors[mechanism_id] = editor
        
        # Connect update callback
        for handle in editor.handles.values():
            original_callback = handle.on_moved
            handle.on_moved = lambda hid, pos, cb=original_callback, mid=mechanism_id: (
                cb(hid, pos) if cb else None,
                self._queue_update(mid)
            )
        
        logging.info(f"[PARAMETRIC-EDITOR] Created {mechanism_type} editor for {mechanism_id}")
        
        return editor
    
    def remove_editor(self, mechanism_id: str) -> None:
        """Remove editor and its handles."""
        if mechanism_id in self.editors:
            editor = self.editors[mechanism_id]
            editor.remove_handles()
            del self.editors[mechanism_id]
            
            if self.active_editor == editor:
                self.active_editor = None
    
    def set_active_editor(self, mechanism_id: Optional[str]) -> None:
        """Set the active editor for the selected mechanism."""
        logging.info(f"[PARAMETRIC-EDITOR] Setting active editor to: {mechanism_id}")
        logging.info(f"[PARAMETRIC-EDITOR] Available editors: {list(self.editors.keys())}")
        
        # Hide all editors
        for editor_id, editor in self.editors.items():
            editor.set_handles_visible(False)
            logging.debug(f"[PARAMETRIC-EDITOR] Hidden editor {editor_id}")
        
        # Show selected editor
        if mechanism_id and mechanism_id in self.editors:
            self.active_editor = self.editors[mechanism_id]
            self.active_editor.set_handles_visible(True)
            # Get editor type from class name
            editor_type = self.active_editor.__class__.__name__
            # Try to get part name if stored
            part_name = "unknown"
            if hasattr(self.active_editor, 'original_mechanism_data'):
                part_name = self.active_editor.original_mechanism_data.get("part_name", "unknown")
            logging.info(f"[PARAMETRIC-EDITOR] ✅ Activated editor {mechanism_id} (part: {part_name}, type: {editor_type})")
        else:
            self.active_editor = None
            if mechanism_id:
                logging.warning(f"[PARAMETRIC-EDITOR] ⚠️ No editor found for mechanism {mechanism_id}")
    
    def _queue_update(self, mechanism_id: str) -> None:
        """Queue mechanism update for batching."""
        self._pending_updates.add(mechanism_id)
        
        if not self._update_timer.isActive():
            self._update_timer.start()
    
    def _process_updates(self) -> None:
        """Process pending mechanism updates."""
        if not self._pending_updates:
            self._update_timer.stop()
            return
        
        for mechanism_id in self._pending_updates:
            if mechanism_id in self.editors:
                editor = self.editors[mechanism_id]
                params = editor.get_current_parameters()
                
                # Emit update signal
                self.mechanism_updated.emit(mechanism_id, params)
        
        self._pending_updates.clear()
    
    def update_mechanism_visuals(self, mechanism_id: str, 
                                simulation_data: dict[str, Any]) -> None:
        """Update visuals for a mechanism."""
        if mechanism_id in self.editors:
            self.editors[mechanism_id].update_visuals(simulation_data)
    
    def enable_editing(self) -> None:
        """Enable parametric editing mode."""
        logging.info("[PARAMETRIC-EDITOR] Editing mode enabled")
        
        # Show handles for active editor
        if self.active_editor:
            self.active_editor.set_handles_visible(True)
    
    def validate_physics_constraints(self) -> tuple[bool, str]:
        """
        Validate physics constraints for all active mechanisms.
        This is called when exiting parametric editing mode.
        
        Returns:
            tuple: (is_valid, error_message)
        """
        logging.info("[PARAMETRIC-EDITOR] Validating physics constraints...")
        
        for mech_id, editor in self.editors.items():
            # Validate based on mechanism type
            if isinstance(editor, CamEditor):
                # Validate CAM gravity physics
                mech_data = editor.mechanism_data  # Direct access to mechanism_data
                cam_center = QPointF(mech_data.get('cam_center_x', 0), mech_data.get('cam_center_y', 0))
                follower_pos = QPointF(mech_data.get('follower_x', 0), mech_data.get('follower_y', cam_center.y() - 100))
                
                # Check gravity constraint: follower must be above cam
                if follower_pos.y() >= cam_center.y():
                    error_msg = f"CAM mechanism physics constraint violated: Follower must be above cam center (gravity constraint)"
                    logging.warning(f"[PHYSICS-VALIDATION] {error_msg}")
                    return False, error_msg
                    
            elif isinstance(editor, FourBarEditor):
                # Validate Grashof condition for 4-bar linkage
                mech_data = editor.mechanism_data  # Direct access to mechanism_data
                
                # Get link lengths
                anchor1 = QPointF(mech_data.get('anchor1_x', 0), mech_data.get('anchor1_y', 0))
                anchor2 = QPointF(mech_data.get('anchor2_x', 200), mech_data.get('anchor2_y', 0))
                joint1 = QPointF(mech_data.get('joint1_x', 50), mech_data.get('joint1_y', 100))
                joint2 = QPointF(mech_data.get('joint2_x', 150), mech_data.get('joint2_y', 100))
                
                # Calculate link lengths
                ground_link = ((anchor2.x() - anchor1.x())**2 + (anchor2.y() - anchor1.y())**2)**0.5
                link1 = ((joint1.x() - anchor1.x())**2 + (joint1.y() - anchor1.y())**2)**0.5
                link2 = ((joint2.x() - anchor2.x())**2 + (joint2.y() - anchor2.y())**2)**0.5
                coupler = ((joint2.x() - joint1.x())**2 + (joint2.y() - joint1.y())**2)**0.5
                
                # Check Grashof condition
                lengths = [ground_link, link1, link2, coupler]
                s = min(lengths)
                l = max(lengths)
                p, q = sorted([length for length in lengths if length != s and length != l])
                
                if s + l > p + q:
                    error_msg = f"4-bar linkage Grashof condition violated: shortest + longest > sum of other two links"
                    logging.warning(f"[PHYSICS-VALIDATION] {error_msg}")
                    # For now, just log the warning but don't block (can be made stricter later)
                    # return False, error_msg
                    
            elif isinstance(editor, GearEditor):
                # Validate gear mesh constraints
                mech_data = editor.mechanism_data  # Direct access to mechanism_data
                
                # Check gear ratios and center distances
                # This is a placeholder for gear-specific validation
                pass
                
        logging.info("[PARAMETRIC-EDITOR] Physics constraints validation completed successfully")
        return True, ""

    def disable_editing(self) -> None:
        """Disable parametric editing mode and validate physics constraints."""
        logging.info("[PARAMETRIC-EDITOR] Editing mode disabled")
        
        # Validate physics constraints before finalizing
        is_valid, error_msg = self.validate_physics_constraints()
        if not is_valid:
            # Show warning to user but don't prevent exit
            # In production, you might want to show a dialog or confirmation
            logging.warning(f"[PARAMETRIC-EDITOR] Physics validation failed: {error_msg}")
            # TODO: Add user notification via QMessageBox or status bar
        
        # Hide all handles
        for editor in self.editors.values():
            editor.set_handles_visible(False)
        
        # Stop update timer
        if self._update_timer.isActive():
            self._update_timer.stop()
            self._process_updates()  # Process any remaining updates  # Process any remaining updates
