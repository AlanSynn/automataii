"""High-level service API for IK system."""

import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal, QPointF
from PyQt6.QtGui import QPainterPath

from .ik_coordinator import IKCoordinator

if TYPE_CHECKING:
    from ..core.skeleton_manager import SkeletonManager
    from ..gui.graphics_items.part_item import CharacterPartItem


class IKService(QObject):
    """High-level service interface for the IK system.
    
    This class provides a simplified API for interacting with the
    IK system, hiding implementation details from the rest of the
    application.
    """
    
    # Signals
    character_updated = pyqtSignal(dict)  # part transforms
    skeleton_updated = pyqtSignal(dict)  # joint positions
    animation_state_changed = pyqtSignal(str)  # playing/stopped
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self._coordinator = IKCoordinator(self)
        self._skeleton_manager: Optional['SkeletonManager'] = None
        self._part_items: Dict[str, 'CharacterPartItem'] = {}
        
        # Part name mappings
        self._ik_to_part_mapping = {
            "left_arm": "left_arm_upper",
            "right_arm": "right_arm_upper",
            "left_leg": "left_leg_upper",
            "right_leg": "right_leg_upper",
        }
        
        self._setup_connections()
        
        logging.info("IKService initialized")
    
    def _setup_connections(self):
        """Set up signal connections."""
        self._coordinator.solver_initialized.connect(self._on_solver_initialized)
        self._coordinator.ik_solved.connect(self._on_ik_solved)
        self._coordinator.animation_updated.connect(self._on_animation_updated)
        self._coordinator.error_occurred.connect(self.error_occurred)
    
    def set_skeleton_manager(self, skeleton_manager: 'SkeletonManager'):
        """Set reference to skeleton manager."""
        self._skeleton_manager = skeleton_manager
        
        # Connect to skeleton updates
        if hasattr(skeleton_manager, 'skeleton_data_updated'):
            skeleton_manager.skeleton_data_updated.connect(self._on_skeleton_updated)
    
    def set_part_items(self, part_items: Dict[str, 'CharacterPartItem']):
        """Set character part items for visual updates."""
        self._part_items = part_items
    
    def initialize_from_skeleton(self, skeleton_data: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize IK system from skeleton data.
        
        Args:
            skeleton_data: Optional skeleton data. If None, uses skeleton manager.
            
        Returns:
            True if successful
        """
        if skeleton_data is None and self._skeleton_manager:
            skeleton_data = self._skeleton_manager.get_current_skeleton_data()
        
        if not skeleton_data:
            logging.error("No skeleton data available for IK initialization")
            return False
        
        return self._coordinator.initialize_from_skeleton(skeleton_data)
    
    def set_motion_paths(self, motion_paths: Dict[str, QPainterPath]):
        """Set motion paths for parts.
        
        Args:
            motion_paths: Dict mapping part names to motion paths
        """
        # Convert part names to limb names
        limb_paths = {}
        for part_name, path in motion_paths.items():
            limb_name = self._part_to_limb_name(part_name)
            if limb_name:
                limb_paths[limb_name] = path
        
        self._coordinator.set_motion_paths(limb_paths)
    
    def start_animation(self):
        """Start IK animation."""
        self._coordinator.start_animation()
        self.animation_state_changed.emit("playing")
    
    def stop_animation(self):
        """Stop IK animation."""
        self._coordinator.stop_animation()
        self.animation_state_changed.emit("stopped")
    
    def reset_animation(self):
        """Reset animation to beginning."""
        self._coordinator.reset_animation()
        self.animation_state_changed.emit("reset")
    
    def set_animation_duration(self, duration_ms: int):
        """Set animation duration in milliseconds."""
        self._coordinator.animation.set_duration(duration_ms)
    
    def set_animation_loop(self, loop: bool):
        """Set whether animation should loop."""
        self._coordinator.animation.set_loop(loop)
    
    def solve_limb_ik(self, limb_name: str, target: QPointF) -> bool:
        """Manually solve IK for a limb.
        
        Args:
            limb_name: Name of limb
            target: Target position
            
        Returns:
            True if successful
        """
        solution = self._coordinator.solve_limb(limb_name, target)
        return solution is not None and solution.success
    
    def get_joint_positions(self) -> Dict[str, QPointF]:
        """Get current joint positions."""
        joints = self._coordinator.state.get_all_joints()
        return {name: data['position'] for name, data in joints.items()}
    
    def get_joint_angles(self) -> Dict[str, float]:
        """Get current joint angles."""
        joints = self._coordinator.state.get_all_joints()
        return {name: data['angle'] for name, data in joints.items()}
    
    def is_initialized(self) -> bool:
        """Check if IK system is initialized."""
        return self._coordinator.state.solver_initialized
    
    def is_animating(self) -> bool:
        """Check if animation is playing."""
        return self._coordinator.state.is_animating
    
    def clear(self):
        """Clear all IK data."""
        self._coordinator.clear()
    
    @property
    def coordinator(self):
        """Get the IK coordinator (for internal use)."""
        return self._coordinator
    
    def _part_to_limb_name(self, part_name: str) -> Optional[str]:
        """Convert part name to limb name."""
        # Check direct mapping
        for limb_name, mapped_part in self._ik_to_part_mapping.items():
            if part_name == mapped_part:
                return limb_name
        
        # Check if part name contains limb indicators
        if 'arm' in part_name.lower():
            if 'left' in part_name.lower():
                return 'left_arm'
            elif 'right' in part_name.lower():
                return 'right_arm'
        elif 'leg' in part_name.lower():
            if 'left' in part_name.lower():
                return 'left_leg'
            elif 'right' in part_name.lower():
                return 'right_leg'
        
        return None
    
    def _on_solver_initialized(self, success: bool, joint_config: Dict[str, Any]):
        """Handle solver initialization."""
        if success:
            logging.info("IK solver initialized successfully")
            self.skeleton_updated.emit(joint_config)
        else:
            logging.error("IK solver initialization failed")
    
    def _on_ik_solved(self, solution_data: Dict[str, Any]):
        """Handle IK solution."""
        # Update character visuals if part items are available
        if self._part_items:
            self._update_character_visuals(solution_data)
    
    def _on_animation_updated(self, progress: float):
        """Handle animation update."""
        # Could emit progress or handle frame updates
        pass
    
    def _on_skeleton_updated(self, skeleton_data: Dict[str, Any]):
        """Handle skeleton data update from skeleton manager."""
        # Re-initialize if needed
        if self.is_initialized():
            self.initialize_from_skeleton(skeleton_data)
    
    def _update_character_visuals(self, solution_data: Dict[str, Any]):
        """Update character part visuals based on IK solution."""
        # This would update part transforms based on joint positions
        # Implementation depends on how parts are connected to joints
        
        transforms = {}
        # ... transform calculation logic ...
        
        if transforms:
            self.character_updated.emit(transforms)