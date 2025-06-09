"""Data models for body parts extraction."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


@dataclass
class JointInfo:
    """Information about a skeleton joint."""
    name: str
    position: Tuple[int, int]
    parent: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.name,
            "name": self.name,
            "position": list(self.position),
            "parent": self.parent
        }


@dataclass
class PartInfo:
    """Information about an extracted body part."""
    name: str
    roi: Tuple[float, float, float, float]  # x, y, width, height
    image_path: str
    fill_color: str = "rgba(128,128,128,0.5)"
    local_pivot_offset: Tuple[float, float] = (0.0, 0.0)
    z_value: float = 0.0
    fixed: bool = False
    anchor_joint_id: Optional[str] = None
    show_anchor: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "roi": list(self.roi),
            "image_path": self.image_path,
            "fill_color": self.fill_color,
            "local_pivot_offset": list(self.local_pivot_offset),
            "z_value": self.z_value,
            "fixed": self.fixed,
            "anchor_joint_id": self.anchor_joint_id
        }
    
    @classmethod
    def from_pydantic(cls, pydantic_model, project_dir=None) -> 'PartInfo':
        """Create PartInfo from Pydantic model."""
        # Convert Pydantic model to PartInfo
        return cls(
            name=pydantic_model.name,
            roi=tuple(pydantic_model.roi) if pydantic_model.roi else (0.0, 0.0, 0.0, 0.0),
            image_path=pydantic_model.image_path or "",
            fill_color=pydantic_model.fill_color,
            local_pivot_offset=tuple(pydantic_model.local_pivot_offset) if pydantic_model.local_pivot_offset else (0.0, 0.0),
            z_value=pydantic_model.z_value,
            fixed=pydantic_model.fixed,
            anchor_joint_id=pydantic_model.anchor_joint_id,
            show_anchor=getattr(pydantic_model, 'show_anchor', True)
        )


@dataclass
class AnimationInfo:
    """Information about part animations."""
    animation_path: str
    num_frames: int = 30
    fps: int = 24


@dataclass
class CharacterData:
    """Complete character data including parts and skeleton."""
    name: str
    width: int
    height: int
    parts: Dict[str, PartInfo] = field(default_factory=dict)
    skeleton_joints: List[JointInfo] = field(default_factory=list)
    animations: Dict[str, AnimationInfo] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "parts": {name: part.to_dict() for name, part in self.parts.items()},
            "skeleton_joints": [joint.to_dict() for joint in self.skeleton_joints],
            "animations": {
                name: {"animation_path": anim.animation_path}
                for name, anim in self.animations.items()
            }
        }


@dataclass
class ExtractionResult:
    """Result of body parts extraction process."""
    character: CharacterData
    part_masks: Dict[str, np.ndarray] = field(default_factory=dict)
    joint_map: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation for JSON serialization."""
        return {
            "character": self.character.to_dict()
        }


@dataclass
class PartDefinition:
    """Definition of a body part."""
    joints: List[str]
    color: str
    z_value: float
    fixed: bool
    anchor_joint: str