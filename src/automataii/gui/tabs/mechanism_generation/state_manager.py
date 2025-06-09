"""State management for mechanism generation tab."""

import logging
from typing import Optional, Dict, List
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, pyqtSignal, QPointF
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import QGraphicsItem

from ...graphics_items.part_item import CharacterPartItem


@dataclass
class MechanismState:
    """Holds the state for mechanism generation."""
    
    # Selected items
    selected_part_name: Optional[str] = None
    selected_cam_center: Optional[QPointF] = None
    selected_pivot_a: Optional[QPointF] = None
    selected_pivot_d: Optional[QPointF] = None
    mechanism_selecting_mode: Optional[str] = None
    
    # Data storage
    character_parts: Dict[str, CharacterPartItem] = field(default_factory=dict)
    motion_paths: Dict[str, QPainterPath] = field(default_factory=dict)
    current_mechanisms: List[Dict] = field(default_factory=list)
    mechanism_visual_items: List[QGraphicsItem] = field(default_factory=list)
    
    # Simulation state
    is_mechanism_simulating: bool = False
    current_simulation_state: str = "stopped"


class StateManager(QObject):
    """Manages state for mechanism generation."""
    
    # Signals for state changes
    state_changed = pyqtSignal()
    part_selection_changed = pyqtSignal(str)  # part_name
    simulation_state_changed = pyqtSignal(str)  # state_string
    mechanisms_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self._state = MechanismState()
        self._logger = logging.getLogger(__name__)
    
    @property
    def state(self) -> MechanismState:
        """Get current state."""
        return self._state
    
    def set_selected_part(self, part_name: Optional[str]):
        """Set the selected part."""
        if self._state.selected_part_name != part_name:
            self._state.selected_part_name = part_name
            self._logger.info(f"Selected part changed to: {part_name}")
            self.part_selection_changed.emit(part_name if part_name else "")
            self.state_changed.emit()
    
    def set_cam_center(self, point: Optional[QPointF]):
        """Set cam center point."""
        self._state.selected_cam_center = point
        self._logger.info(f"Cam center set to: {point}")
        self.state_changed.emit()
    
    def set_pivot_a(self, point: Optional[QPointF]):
        """Set pivot A point."""
        self._state.selected_pivot_a = point
        self._logger.info(f"Pivot A set to: {point}")
        self.state_changed.emit()
    
    def set_pivot_d(self, point: Optional[QPointF]):
        """Set pivot D point."""
        self._state.selected_pivot_d = point
        self._logger.info(f"Pivot D set to: {point}")
        self.state_changed.emit()
    
    def set_mechanism_selecting_mode(self, mode: Optional[str]):
        """Set mechanism point selection mode."""
        self._state.mechanism_selecting_mode = mode
        self.state_changed.emit()
    
    def update_character_parts(self, parts: Dict[str, CharacterPartItem]):
        """Update character parts."""
        self._state.character_parts = parts.copy()
        self.state_changed.emit()
    
    def set_character_parts(self, parts: Dict[str, CharacterPartItem]):
        """Set character parts (alias for update_character_parts)."""
        self.update_character_parts(parts)
    
    def update_motion_paths(self, paths: Dict[str, QPainterPath]):
        """Update motion paths."""
        self._state.motion_paths = paths.copy()
        self.state_changed.emit()
    
    def add_mechanism(self, mechanism_data: Dict):
        """Add a generated mechanism."""
        self._state.current_mechanisms.append(mechanism_data)
        self._logger.info(f"Added mechanism: {mechanism_data.get('type', 'Unknown')}")
        self.mechanisms_updated.emit()
        self.state_changed.emit()
    
    def remove_mechanism(self, index: int):
        """Remove a mechanism by index."""
        if 0 <= index < len(self._state.current_mechanisms):
            removed = self._state.current_mechanisms.pop(index)
            self._logger.info(f"Removed mechanism: {removed.get('type', 'Unknown')}")
            self.mechanisms_updated.emit()
            self.state_changed.emit()
    
    def set_simulation_state(self, state: str):
        """Set simulation state."""
        self._state.current_simulation_state = state
        self._state.is_mechanism_simulating = (state == "playing")
        self.simulation_state_changed.emit(state)
        self.state_changed.emit()
    
    def add_visual_item(self, item: QGraphicsItem):
        """Add a visual item for mechanism display."""
        self._state.mechanism_visual_items.append(item)
    
    def clear_visual_items(self):
        """Clear all visual items."""
        self._state.mechanism_visual_items.clear()
    
    def has_selected_part_with_path(self) -> bool:
        """Check if selected part has a motion path."""
        if not self._state.selected_part_name:
            return False
        
        path = self._state.motion_paths.get(self._state.selected_part_name)
        return path is not None and not path.isEmpty()
    
    def has_mechanisms(self) -> bool:
        """Check if any mechanisms are generated."""
        return bool(self._state.current_mechanisms)
    
    def clear_all(self):
        """Clear all state."""
        self._state = MechanismState()
        self._logger.info("State cleared")
        self.state_changed.emit()
        self.mechanisms_updated.emit()