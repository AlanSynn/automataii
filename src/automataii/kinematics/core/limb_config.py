"""Limb configuration for IK system."""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QPointF


class LimbType(Enum):
    """Types of limbs in the IK system."""
    ARM = "arm"
    LEG = "leg"
    SPINE = "spine"
    NECK = "neck"
    TAIL = "tail"
    CUSTOM = "custom"


class SolverType(Enum):
    """Types of IK solvers for limbs."""
    SINGLE_BONE = "single_bone"
    TWO_BONE = "two_bone"
    CHAIN = "chain"
    FABRIK = "fabrik"


@dataclass
class LimbConfig:
    """Configuration for a limb (kinematic chain)."""
    name: str
    type: LimbType
    joints: List[str]  # Ordered list of joint names
    solver_type: SolverType
    end_effector: str  # Name of the end effector joint
    bend_direction: int = 1  # 1 or -1 for elbow/knee bend
    pole_target: Optional[QPointF] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        
        # Validate joints
        if not self.joints:
            raise ValueError(f"Limb '{self.name}' must have at least one joint")
        
        # Validate solver type based on joint count
        joint_count = len(self.joints)
        if self.solver_type == SolverType.SINGLE_BONE and joint_count != 2:
            raise ValueError(f"Single bone solver requires exactly 2 joints, got {joint_count}")
        elif self.solver_type == SolverType.TWO_BONE and joint_count != 3:
            raise ValueError(f"Two bone solver requires exactly 3 joints, got {joint_count}")


class LimbConfigurationManager:
    """Manages limb configurations for the IK system."""
    
    def __init__(self):
        self._limbs: Dict[str, LimbConfig] = {}
        self._limb_groups: Dict[str, List[str]] = {}  # Group name -> limb names
        
        logging.debug("LimbConfigurationManager initialized")
    
    def add_limb(self, config: LimbConfig) -> None:
        """Add a limb configuration."""
        self._limbs[config.name] = config
        
        # Auto-group by type
        type_group = f"{config.type.value}s"
        if type_group not in self._limb_groups:
            self._limb_groups[type_group] = []
        self._limb_groups[type_group].append(config.name)
        
        logging.debug(f"Added limb: {config.name} (type: {config.type.value})")
    
    def remove_limb(self, name: str) -> None:
        """Remove a limb configuration."""
        if name not in self._limbs:
            return
        
        config = self._limbs[name]
        
        # Remove from groups
        for group_limbs in self._limb_groups.values():
            if name in group_limbs:
                group_limbs.remove(name)
        
        del self._limbs[name]
        logging.debug(f"Removed limb: {name}")
    
    def get_limb(self, name: str) -> Optional[LimbConfig]:
        """Get limb configuration."""
        return self._limbs.get(name)
    
    def get_all_limbs(self) -> Dict[str, LimbConfig]:
        """Get all limb configurations."""
        return self._limbs.copy()
    
    def get_limbs_by_type(self, limb_type: LimbType) -> List[LimbConfig]:
        """Get all limbs of a specific type."""
        return [
            config for config in self._limbs.values()
            if config.type == limb_type
        ]
    
    def get_limbs_by_solver(self, solver_type: SolverType) -> List[LimbConfig]:
        """Get all limbs using a specific solver type."""
        return [
            config for config in self._limbs.values()
            if config.solver_type == solver_type
        ]
    
    def add_group(self, group_name: str, limb_names: List[str]) -> None:
        """Add a custom limb group."""
        # Validate limbs exist
        for limb_name in limb_names:
            if limb_name not in self._limbs:
                raise ValueError(f"Limb '{limb_name}' not found")
        
        self._limb_groups[group_name] = limb_names
        logging.debug(f"Added limb group '{group_name}': {limb_names}")
    
    def get_group(self, group_name: str) -> Optional[List[str]]:
        """Get limb names in a group."""
        return self._limb_groups.get(group_name)
    
    def create_standard_humanoid_limbs(self, joint_prefix: str = "j_") -> None:
        """Create standard humanoid limb configurations."""
        # Left arm
        self.add_limb(LimbConfig(
            name="left_arm",
            type=LimbType.ARM,
            joints=[f"{joint_prefix}left_shoulder", f"{joint_prefix}left_elbow", f"{joint_prefix}left_wrist"],
            solver_type=SolverType.TWO_BONE,
            end_effector=f"{joint_prefix}left_wrist",
            bend_direction=1
        ))
        
        # Right arm
        self.add_limb(LimbConfig(
            name="right_arm",
            type=LimbType.ARM,
            joints=[f"{joint_prefix}right_shoulder", f"{joint_prefix}right_elbow", f"{joint_prefix}right_wrist"],
            solver_type=SolverType.TWO_BONE,
            end_effector=f"{joint_prefix}right_wrist",
            bend_direction=-1
        ))
        
        # Left leg
        self.add_limb(LimbConfig(
            name="left_leg",
            type=LimbType.LEG,
            joints=[f"{joint_prefix}left_hip", f"{joint_prefix}left_knee", f"{joint_prefix}left_ankle"],
            solver_type=SolverType.TWO_BONE,
            end_effector=f"{joint_prefix}left_ankle",
            bend_direction=-1
        ))
        
        # Right leg
        self.add_limb(LimbConfig(
            name="right_leg",
            type=LimbType.LEG,
            joints=[f"{joint_prefix}right_hip", f"{joint_prefix}right_knee", f"{joint_prefix}right_ankle"],
            solver_type=SolverType.TWO_BONE,
            end_effector=f"{joint_prefix}right_ankle",
            bend_direction=-1
        ))
        
        logging.info("Created standard humanoid limb configurations")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'limbs': {
                name: {
                    'type': config.type.value,
                    'joints': config.joints,
                    'solver_type': config.solver_type.value,
                    'end_effector': config.end_effector,
                    'bend_direction': config.bend_direction,
                    'pole_target': {
                        'x': config.pole_target.x(),
                        'y': config.pole_target.y()
                    } if config.pole_target else None,
                    'metadata': config.metadata
                }
                for name, config in self._limbs.items()
            },
            'groups': self._limb_groups
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load from dictionary."""
        self.clear()
        
        # Load limbs
        for name, limb_data in data.get('limbs', {}).items():
            pole_target = None
            if limb_data.get('pole_target'):
                pole_target = QPointF(
                    limb_data['pole_target']['x'],
                    limb_data['pole_target']['y']
                )
            
            config = LimbConfig(
                name=name,
                type=LimbType(limb_data['type']),
                joints=limb_data['joints'],
                solver_type=SolverType(limb_data['solver_type']),
                end_effector=limb_data['end_effector'],
                bend_direction=limb_data['bend_direction'],
                pole_target=pole_target,
                metadata=limb_data.get('metadata', {})
            )
            
            self.add_limb(config)
        
        # Load groups
        self._limb_groups = data.get('groups', {})
    
    def clear(self) -> None:
        """Clear all configurations."""
        self._limbs.clear()
        self._limb_groups.clear()
        logging.info("LimbConfigurationManager cleared")