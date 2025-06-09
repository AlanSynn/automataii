"""Adapter to make IKService compatible with IKManagerInterface."""

import logging
from typing import Dict, Any, Optional

from PyQt6.QtCore import pyqtSignal, QObject

from .ik_service import IKService


class IKServiceAdapter(QObject):
    """Adapter class to make IKService compatible with IKManagerInterface.
    
    This allows gradual migration from the old IKManager to the new
    refactored IK system.
    """
    
    # Signals (forwarded from IKService)
    animation_state_changed = pyqtSignal(str)
    character_visuals_updated = pyqtSignal(dict)
    frame_updated = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._service = IKService(self)
        self._animation_duration = 2000
        
        # Forward signals
        self._service.animation_state_changed.connect(self.animation_state_changed)
        self._service.character_updated.connect(self.character_visuals_updated)
        self._service.coordinator.animation_updated.connect(self.frame_updated)
        
        logging.info("IKServiceAdapter initialized")
    
    @property
    def animation_duration(self) -> int:
        """Get animation duration in milliseconds."""
        return self._animation_duration
    
    @property
    def is_animating(self) -> bool:
        """Check if animation is currently playing."""
        return self._service.is_animating()
    
    def start_animation(self) -> None:
        """Start the animation."""
        self._service.start_animation()
    
    def stop_animation(self) -> None:
        """Stop the animation."""
        self._service.stop_animation()
    
    def reset_animation_state(self) -> None:
        """Reset animation to initial state."""
        self._service.reset_animation()
    
    def set_animation_duration(self, duration_ms: int) -> None:
        """Set animation duration."""
        self._animation_duration = duration_ms
        self._service.set_animation_duration(duration_ms)
    
    def update_skeleton_data(self, skeleton_data: Dict[str, Any]) -> None:
        """Update skeleton data for IK calculations."""
        self._service.initialize_from_skeleton(skeleton_data)
    
    def update_motion_paths(self, motion_paths: Dict[str, Any]) -> None:
        """Update motion paths for parts."""
        self._service.set_motion_paths(motion_paths)
    
    def get_current_joint_positions(self) -> Dict[str, Any]:
        """Get current positions of all joints."""
        return self._service.get_joint_positions()
    
    def set_mechanism_data(self, mechanism_data: Dict[str, Any]) -> None:
        """Set mechanism data for simulation."""
        # This might need custom implementation based on how
        # mechanism data is used
        logging.warning("set_mechanism_data not fully implemented in adapter")
    
    def set_skeleton_manager(self, skeleton_manager):
        """Set skeleton manager reference."""
        self._service.set_skeleton_manager(skeleton_manager)
    
    def set_part_items(self, part_items):
        """Set part items for visual updates."""
        self._service.set_part_items(part_items)
    
    def clear(self):
        """Clear all IK data."""
        self._service.clear()
    
    def reset_all_ik_systems_and_data(self):
        """Reset all IK systems and data (compatibility method)."""
        self._service.clear()
    
    def clear_ik_data(self):
        """Clear IK data (compatibility method)."""
        self._service.clear()
    
    def set_project_parts_data(self, parts_info: Dict[str, Any]):
        """Set project parts data (compatibility method)."""
        self._service.set_part_items(parts_info)
    
    @property
    def service(self) -> IKService:
        """Get underlying IK service."""
        return self._service
    
    def on_skeleton_data_updated_from_manager(self, skeleton_data: Dict[str, Any]) -> None:
        """Handle skeleton data updates from skeleton manager (compatibility method)."""
        self.update_skeleton_data(skeleton_data)