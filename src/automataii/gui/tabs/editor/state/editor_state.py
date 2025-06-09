"""Editor state management."""

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from enum import Enum

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath


class EditorMode(Enum):
    """Editor interaction modes."""
    SELECT = "select"
    DRAW_PATH = "draw_path"
    DEFINE_JOINT = "define_joint"
    PAN = "pan"
    ZOOM = "zoom"


class SimulationState(Enum):
    """Simulation states."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    RESET = "reset"


@dataclass
class PartState:
    """State of a single part."""
    name: str
    position: QPointF
    rotation: float = 0.0
    z_value: float = 0.0
    is_fixed: bool = False
    is_selected: bool = False
    has_motion_path: bool = False
    motion_path: Optional[QPainterPath] = None
    anchor_joint_id: Optional[str] = None


@dataclass
class EditorState:
    """Complete state of the editor."""
    # Mode and selection
    mode: EditorMode = EditorMode.SELECT
    selected_part_name: Optional[str] = None
    
    # Parts state
    parts: Dict[str, PartState] = field(default_factory=dict)
    
    # Simulation state
    simulation_state: SimulationState = SimulationState.STOPPED
    simulation_progress: float = 0.0
    
    # View state
    zoom_level: float = 1.0
    view_center: QPointF = field(default_factory=QPointF)
    
    # Path drawing state
    is_drawing_path: bool = False
    current_path_points: List[QPointF] = field(default_factory=list)
    
    # Joint definition state
    is_defining_joint: bool = False
    joint_definition_parts: List[str] = field(default_factory=list)
    
    # Skeleton state
    has_skeleton: bool = False
    skeleton_visible: bool = True
    
    # Mechanism state
    active_mechanisms: List[str] = field(default_factory=list)
    
    # UI state
    part_properties_visible: bool = True
    show_grid: bool = False
    snap_to_grid: bool = False
    grid_size: int = 10
    
    def get_selected_part(self) -> Optional[PartState]:
        """Get the currently selected part state."""
        if self.selected_part_name:
            return self.parts.get(self.selected_part_name)
        return None
    
    def select_part(self, part_name: Optional[str]) -> None:
        """Select a part by name."""
        # Deselect all parts
        for part in self.parts.values():
            part.is_selected = False
        
        # Select new part
        self.selected_part_name = part_name
        if part_name and part_name in self.parts:
            self.parts[part_name].is_selected = True
    
    def add_part(self, part_state: PartState) -> None:
        """Add or update a part."""
        self.parts[part_state.name] = part_state
    
    def remove_part(self, part_name: str) -> None:
        """Remove a part."""
        if part_name in self.parts:
            del self.parts[part_name]
            if self.selected_part_name == part_name:
                self.selected_part_name = None
    
    def clear_parts(self) -> None:
        """Clear all parts."""
        self.parts.clear()
        self.selected_part_name = None
    
    def update_part_property(self, part_name: str, property_name: str, value: Any) -> bool:
        """Update a specific property of a part.
        
        Args:
            part_name: Name of the part
            property_name: Name of the property to update
            value: New value
            
        Returns:
            True if updated successfully
        """
        if part_name in self.parts and hasattr(self.parts[part_name], property_name):
            setattr(self.parts[part_name], property_name, value)
            return True
        return False
    
    def get_parts_with_paths(self) -> Dict[str, PartState]:
        """Get all parts that have motion paths."""
        return {
            name: part for name, part in self.parts.items()
            if part.has_motion_path and part.motion_path
        }
    
    def can_animate(self) -> bool:
        """Check if animation is possible."""
        return bool(self.get_parts_with_paths()) and self.simulation_state != SimulationState.PLAYING
    
    def can_draw_path(self) -> bool:
        """Check if path drawing is allowed."""
        return (
            self.selected_part_name is not None and
            self.simulation_state != SimulationState.PLAYING and
            not self.is_defining_joint
        )
    
    def reset_interaction_state(self) -> None:
        """Reset all interaction states."""
        self.is_drawing_path = False
        self.current_path_points.clear()
        self.is_defining_joint = False
        self.joint_definition_parts.clear()
        self.mode = EditorMode.SELECT