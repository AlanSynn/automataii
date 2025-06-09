"""Joint configuration management for IK system."""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QPointF


class JointType(Enum):
    """Types of joints in the IK system."""
    REVOLUTE = "revolute"
    PRISMATIC = "prismatic"
    FIXED = "fixed"
    FREE = "free"


@dataclass
class JointConstraints:
    """Constraints for a joint."""
    min_angle: float = -180.0
    max_angle: float = 180.0
    min_distance: float = 0.0
    max_distance: float = float('inf')
    locked_axes: List[str] = None  # 'x', 'y', 'rotation'
    
    def __post_init__(self):
        if self.locked_axes is None:
            self.locked_axes = []


@dataclass
class JointConfig:
    """Configuration for a single joint."""
    name: str
    type: JointType
    parent: Optional[str] = None
    children: List[str] = None
    offset: QPointF = None  # Offset from parent
    rest_angle: float = 0.0
    constraints: JointConstraints = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.offset is None:
            self.offset = QPointF(0, 0)
        if self.constraints is None:
            self.constraints = JointConstraints()
        if self.metadata is None:
            self.metadata = {}


class JointConfigurationManager:
    """Manages joint configurations for the IK system."""
    
    def __init__(self):
        self._joints: Dict[str, JointConfig] = {}
        self._hierarchy: Dict[str, List[str]] = {}  # parent -> children
        self._joint_chains: Dict[str, List[str]] = {}  # limb -> joints
        
        logging.debug("JointConfigurationManager initialized")
    
    def add_joint(self, config: JointConfig) -> None:
        """Add a joint configuration."""
        self._joints[config.name] = config
        
        # Update hierarchy
        if config.parent:
            if config.parent not in self._hierarchy:
                self._hierarchy[config.parent] = []
            self._hierarchy[config.parent].append(config.name)
        
        logging.debug(f"Added joint: {config.name}")
    
    def remove_joint(self, name: str) -> None:
        """Remove a joint configuration."""
        if name not in self._joints:
            return
        
        config = self._joints[name]
        
        # Remove from parent's children
        if config.parent and config.parent in self._hierarchy:
            self._hierarchy[config.parent].remove(name)
        
        # Remove from hierarchy if it's a parent
        if name in self._hierarchy:
            del self._hierarchy[name]
        
        # Remove from chains
        for chain_joints in self._joint_chains.values():
            if name in chain_joints:
                chain_joints.remove(name)
        
        del self._joints[name]
        logging.debug(f"Removed joint: {name}")
    
    def get_joint(self, name: str) -> Optional[JointConfig]:
        """Get joint configuration."""
        return self._joints.get(name)
    
    def get_all_joints(self) -> Dict[str, JointConfig]:
        """Get all joint configurations."""
        return self._joints.copy()
    
    def add_chain(self, name: str, joint_names: List[str]) -> None:
        """Add a joint chain (e.g., for a limb)."""
        # Validate joints exist
        for joint_name in joint_names:
            if joint_name not in self._joints:
                raise ValueError(f"Joint '{joint_name}' not found")
        
        self._joint_chains[name] = joint_names
        logging.debug(f"Added chain '{name}': {joint_names}")
    
    def get_chain(self, name: str) -> Optional[List[str]]:
        """Get joint names in a chain."""
        return self._joint_chains.get(name)
    
    def get_children(self, joint_name: str) -> List[str]:
        """Get direct children of a joint."""
        return self._hierarchy.get(joint_name, [])
    
    def get_descendants(self, joint_name: str) -> List[str]:
        """Get all descendants of a joint."""
        descendants = []
        to_process = [joint_name]
        
        while to_process:
            current = to_process.pop(0)
            children = self.get_children(current)
            descendants.extend(children)
            to_process.extend(children)
        
        return descendants
    
    def get_chain_length(self, chain_name: str) -> float:
        """Calculate total length of a joint chain."""
        chain = self.get_chain(chain_name)
        if not chain or len(chain) < 2:
            return 0.0
        
        total_length = 0.0
        for i in range(len(chain) - 1):
            joint = self._joints.get(chain[i])
            if joint and joint.offset:
                total_length += (joint.offset.x()**2 + joint.offset.y()**2)**0.5
        
        return total_length
    
    def validate_hierarchy(self) -> List[str]:
        """Validate joint hierarchy for cycles and orphans."""
        errors = []
        
        # Check for cycles
        for joint_name in self._joints:
            visited = set()
            current = joint_name
            
            while current:
                if current in visited:
                    errors.append(f"Cycle detected at joint '{current}'")
                    break
                visited.add(current)
                
                config = self._joints.get(current)
                current = config.parent if config else None
        
        # Check for orphans (joints with invalid parents)
        for name, config in self._joints.items():
            if config.parent and config.parent not in self._joints:
                errors.append(f"Joint '{name}' has invalid parent '{config.parent}'")
        
        return errors
    
    def get_root_joints(self) -> List[str]:
        """Get all root joints (joints with no parent)."""
        return [name for name, config in self._joints.items() if not config.parent]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'joints': {
                name: {
                    'type': config.type.value,
                    'parent': config.parent,
                    'children': config.children,
                    'offset': {'x': config.offset.x(), 'y': config.offset.y()},
                    'rest_angle': config.rest_angle,
                    'constraints': {
                        'min_angle': config.constraints.min_angle,
                        'max_angle': config.constraints.max_angle,
                        'min_distance': config.constraints.min_distance,
                        'max_distance': config.constraints.max_distance,
                        'locked_axes': config.constraints.locked_axes
                    },
                    'metadata': config.metadata
                }
                for name, config in self._joints.items()
            },
            'chains': self._joint_chains
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load from dictionary."""
        self.clear()
        
        # Load joints
        for name, joint_data in data.get('joints', {}).items():
            constraints = JointConstraints(
                min_angle=joint_data['constraints']['min_angle'],
                max_angle=joint_data['constraints']['max_angle'],
                min_distance=joint_data['constraints']['min_distance'],
                max_distance=joint_data['constraints']['max_distance'],
                locked_axes=joint_data['constraints']['locked_axes']
            )
            
            config = JointConfig(
                name=name,
                type=JointType(joint_data['type']),
                parent=joint_data['parent'],
                children=joint_data['children'],
                offset=QPointF(joint_data['offset']['x'], joint_data['offset']['y']),
                rest_angle=joint_data['rest_angle'],
                constraints=constraints,
                metadata=joint_data['metadata']
            )
            
            self.add_joint(config)
        
        # Load chains
        self._joint_chains = data.get('chains', {})
    
    def clear(self) -> None:
        """Clear all configurations."""
        self._joints.clear()
        self._hierarchy.clear()
        self._joint_chains.clear()
        logging.info("JointConfigurationManager cleared")