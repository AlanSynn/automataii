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
        super().__init__(
            center.x() - self.style.size/2,
            center.y() - self.style.size/2,
            self.style.size,
            self.style.size
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
            self.setPos(new_pos - QPointF(self.style.size/2, self.style.size/2))
            
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
        self.to_scene_coords: Optional[Callable] = None  # Transformation function
    
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
        return self.mechanism_data.copy()


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
        constraints = {
            'min_x': -1000,
            'max_x': 1000,
            'min_y': -1000,
            'max_y': 1000
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
        """Handle anchor1 movement."""
        self.mechanism_data["params"]["anchor1_x"] = new_pos.x()
        self.mechanism_data["params"]["anchor1_y"] = new_pos.y()
        self._update_dependent_handles("anchor1", new_pos)
        self._trigger_mechanism_update()
    
    def _on_anchor2_moved(self, handle_id: str, new_pos: QPointF):
        """Handle anchor2 movement."""
        self.mechanism_data["params"]["anchor2_x"] = new_pos.x()
        self.mechanism_data["params"]["anchor2_y"] = new_pos.y()
        self._update_dependent_handles("anchor2", new_pos)
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
        
        self._trigger_mechanism_update()
    
    def _on_coupler_moved(self, handle_id: str, new_pos: QPointF):
        """Handle coupler point movement."""
        self.mechanism_data["params"]["coupler_x"] = new_pos.x()
        self.mechanism_data["params"]["coupler_y"] = new_pos.y()
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
            
            self.handles["crank"].setPos(
                new_crank_pos - QPointF(
                    self.handles["crank"].style.size/2,
                    self.handles["crank"].style.size/2
                )
            )
            
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
                
                self.handles["crank_length"].setPos(
                    midpoint - QPointF(
                        self.handles["crank_length"].style.size/2,
                        self.handles["crank_length"].style.size/2
                    )
                )
        finally:
            self._updating = False
    
    def _trigger_mechanism_update(self):
        """Trigger mechanism simulation update."""
        if self._updating:
            return
        
        # This would call back to the main mechanism system
        # to update the simulation with new parameters
        param_changes = {
            "anchor1": (self.mechanism_data["params"]["anchor1_x"], 
                       self.mechanism_data["params"]["anchor1_y"]),
            "anchor2": (self.mechanism_data["params"]["anchor2_x"],
                       self.mechanism_data["params"]["anchor2_y"]),
            "l2": self.mechanism_data["params"]["l2"],
            "l3": self.mechanism_data["params"].get("l3", 80),
            "l4": self.mechanism_data["params"]["l4"]
        }
        
        # Emit signal or callback to update mechanism
        logging.info(f"[4BAR-EDITOR] Updating mechanism with: {param_changes}")
    
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
        
        # Cam center handle
        center = QPointF(params.get("center_x", 0), params.get("center_y", 0))
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
        
        # Cam profile control points
        self._create_profile_handles(params)
        
        # Follower rod length handle
        self._create_follower_handle(params)
    
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
        rod_length = params.get("follower_rod_length", 100)
        
        # Position above cam
        follower_pos = QPointF(center.x(), center.y() - rod_length)
        
        handle = ParametricHandle(
            follower_pos,
            f"{self.mechanism_id}_follower",
            "follower",
            self._on_follower_moved,
            style=HandleStyle(size=12, color=QColor(100, 100, 255))
        )
        handle.setToolTip("Follower Rod - Drag to adjust length and position")
        
        # Constrain to vertical movement
        handle.constraints = {
            'min_y': center.y() - 200,
            'max_y': center.y() - 50,
            'fixed_x': center.x()
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
        """Handle cam center movement."""
        old_center = QPointF(
            self.mechanism_data["params"]["center_x"],
            self.mechanism_data["params"]["center_y"]
        )
        
        # Update center
        self.mechanism_data["params"]["center_x"] = new_pos.x()
        self.mechanism_data["params"]["center_y"] = new_pos.y()
        
        # Move all profile handles
        offset = new_pos - old_center
        for i in range(8):
            handle_key = f"profile_{i}"
            if handle_key in self.handles:
                handle = self.handles[handle_key]
                handle.setPos(handle.pos() + offset)
                handle.constraints['center'] = new_pos
        
        # Move follower handle
        if "follower" in self.handles:
            self.handles["follower"].constraints['fixed_x'] = new_pos.x()
            follower_pos = self.handles["follower"].scenePos()
            self.handles["follower"].setPos(
                QPointF(new_pos.x(), follower_pos.y()) - 
                QPointF(self.handles["follower"].style.size/2, 
                       self.handles["follower"].style.size/2)
            )
        
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
        """Handle follower rod movement."""
        center = QPointF(
            self.mechanism_data["params"]["center_x"],
            self.mechanism_data["params"]["center_y"]
        )
        
        # Calculate new rod length
        rod_length = abs(center.y() - new_pos.y())
        self.mechanism_data["params"]["follower_rod_length"] = rod_length
        
        # Update follower offset if needed
        self.mechanism_data["params"]["follower_offset_x"] = new_pos.x() - center.x()
        
        self._trigger_cam_update()
    
    def _trigger_cam_update(self):
        """Trigger cam mechanism update with physics."""
        # Perform physics-based simulation
        simulation_data = self._simulate_cam_follower_physics()
        
        # Update visuals
        self.update_visuals(simulation_data)
    
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
            # For now, use GearEditor for planetary gears as well
            # TODO: Create specialized PlanetaryGearEditor if needed
            editor = GearEditor(mechanism_id, self.scene)
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
    
    def disable_editing(self) -> None:
        """Disable parametric editing mode."""
        logging.info("[PARAMETRIC-EDITOR] Editing mode disabled")
        
        # Hide all handles
        for editor in self.editors.values():
            editor.set_handles_visible(False)
        
        # Stop update timer
        if self._update_timer.isActive():
            self._update_timer.stop()
            self._process_updates()  # Process any remaining updates