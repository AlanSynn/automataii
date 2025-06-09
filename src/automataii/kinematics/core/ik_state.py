"""IK state management for the kinematics system."""

import logging
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, pyqtSignal, QPointF


@dataclass
class JointState:
    """State of a single joint."""
    position: QPointF
    angle: float = 0.0
    is_locked: bool = False
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class LimbState:
    """State of a limb (chain of joints)."""
    joint_names: List[str]
    is_active: bool = True
    target_position: Optional[QPointF] = None
    bend_direction: int = 1  # 1 or -1


class IKState(QObject):
    """Manages the state of the IK system.
    
    This class centralizes all IK-related state management,
    making it easier to track and update the system state.
    """
    
    # Signals
    state_changed = pyqtSignal(str)  # state_key that changed
    joints_updated = pyqtSignal(dict)  # all joint states
    limbs_updated = pyqtSignal(dict)  # all limb states
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        # Core state
        self._joints: Dict[str, JointState] = {}
        self._limbs: Dict[str, LimbState] = {}
        self._active_limbs: Set[str] = set()
        
        # Animation state
        self._is_animating = False
        self._animation_progress = 0.0
        self._animation_duration_ms = 2000
        
        # Solver state
        self._solver_initialized = False
        self._last_solver_error: Optional[str] = None
        
        logging.debug("IKState initialized")
    
    # Joint management
    def add_joint(self, name: str, position: QPointF, angle: float = 0.0) -> None:
        """Add or update a joint."""
        self._joints[name] = JointState(position=position, angle=angle)
        self.joints_updated.emit(self.get_all_joints())
        self.state_changed.emit("joints")
    
    def update_joint_position(self, name: str, position: QPointF) -> None:
        """Update joint position."""
        if name in self._joints:
            self._joints[name].position = position
            self.joints_updated.emit(self.get_all_joints())
            self.state_changed.emit("joint_position")
    
    def update_joint_angle(self, name: str, angle: float) -> None:
        """Update joint angle."""
        if name in self._joints:
            self._joints[name].angle = angle
            self.joints_updated.emit(self.get_all_joints())
            self.state_changed.emit("joint_angle")
    
    def lock_joint(self, name: str, locked: bool = True) -> None:
        """Lock or unlock a joint."""
        if name in self._joints:
            self._joints[name].is_locked = locked
            self.state_changed.emit("joint_lock")
    
    def get_joint(self, name: str) -> Optional[JointState]:
        """Get joint state."""
        return self._joints.get(name)
    
    def get_all_joints(self) -> Dict[str, Dict[str, Any]]:
        """Get all joints as dictionary."""
        return {
            name: {
                'position': state.position,
                'angle': state.angle,
                'is_locked': state.is_locked,
                'constraints': state.constraints
            }
            for name, state in self._joints.items()
        }
    
    # Limb management
    def add_limb(self, name: str, joint_names: List[str], 
                 bend_direction: int = 1) -> None:
        """Add a limb configuration."""
        self._limbs[name] = LimbState(
            joint_names=joint_names,
            bend_direction=bend_direction
        )
        self.limbs_updated.emit(self.get_all_limbs())
        self.state_changed.emit("limbs")
    
    def set_limb_target(self, name: str, target: QPointF) -> None:
        """Set target position for a limb."""
        if name in self._limbs:
            self._limbs[name].target_position = target
            self._active_limbs.add(name)
            self.state_changed.emit("limb_target")
    
    def activate_limb(self, name: str, active: bool = True) -> None:
        """Activate or deactivate a limb."""
        if name in self._limbs:
            self._limbs[name].is_active = active
            if active:
                self._active_limbs.add(name)
            else:
                self._active_limbs.discard(name)
            self.state_changed.emit("limb_active")
    
    def get_limb(self, name: str) -> Optional[LimbState]:
        """Get limb state."""
        return self._limbs.get(name)
    
    def get_all_limbs(self) -> Dict[str, Dict[str, Any]]:
        """Get all limbs as dictionary."""
        return {
            name: {
                'joint_names': state.joint_names,
                'is_active': state.is_active,
                'target_position': state.target_position,
                'bend_direction': state.bend_direction
            }
            for name, state in self._limbs.items()
        }
    
    def get_active_limbs(self) -> List[str]:
        """Get list of active limb names."""
        return list(self._active_limbs)
    
    # Animation state
    @property
    def is_animating(self) -> bool:
        """Check if animation is running."""
        return self._is_animating
    
    def set_animating(self, animating: bool) -> None:
        """Set animation state."""
        self._is_animating = animating
        self.state_changed.emit("animation")
    
    @property
    def animation_progress(self) -> float:
        """Get animation progress (0.0 to 1.0)."""
        return self._animation_progress
    
    def set_animation_progress(self, progress: float) -> None:
        """Set animation progress."""
        self._animation_progress = max(0.0, min(1.0, progress))
        self.state_changed.emit("animation_progress")
    
    @property
    def animation_duration_ms(self) -> int:
        """Get animation duration in milliseconds."""
        return self._animation_duration_ms
    
    def set_animation_duration(self, duration_ms: int) -> None:
        """Set animation duration."""
        self._animation_duration_ms = max(100, duration_ms)
        self.state_changed.emit("animation_duration")
    
    # Solver state
    @property
    def solver_initialized(self) -> bool:
        """Check if solver is initialized."""
        return self._solver_initialized
    
    def set_solver_initialized(self, initialized: bool) -> None:
        """Set solver initialization state."""
        self._solver_initialized = initialized
        self.state_changed.emit("solver")
    
    def set_solver_error(self, error: Optional[str]) -> None:
        """Set last solver error."""
        self._last_solver_error = error
        if error:
            logging.warning(f"IK solver error: {error}")
    
    @property
    def last_solver_error(self) -> Optional[str]:
        """Get last solver error."""
        return self._last_solver_error
    
    def clear(self) -> None:
        """Clear all state."""
        self._joints.clear()
        self._limbs.clear()
        self._active_limbs.clear()
        self._is_animating = False
        self._animation_progress = 0.0
        self._solver_initialized = False
        self._last_solver_error = None
        
        self.joints_updated.emit({})
        self.limbs_updated.emit({})
        self.state_changed.emit("cleared")
        
        logging.info("IKState cleared")