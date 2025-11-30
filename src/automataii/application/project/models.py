"""
Project State Data Models.

Immutable data classes representing the Single Source of Truth
for all cross-tab data in the application.

Architecture: Application Layer (Hexagonal)
Pattern: Immutable Value Objects with Factory Methods
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

# =============================================================================
# PRIMITIVE VALUE OBJECTS
# =============================================================================

@dataclass(frozen=True)
class Point:
    """2D point (immutable)."""
    x: float
    y: float

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    @classmethod
    def from_tuple(cls, t: tuple[float, float]) -> Point:
        return cls(x=t[0], y=t[1])


@dataclass(frozen=True)
class Transform:
    """2D transform (position, rotation, scale)."""
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    scale: float = 1.0


# =============================================================================
# PART DATA
# =============================================================================

@dataclass(frozen=True)
class PartData:
    """
    Single character part data.

    Produced by: ImageProcessingTab
    Consumed by: EditorTab, MechanismDesignTab
    """
    name: str
    texture_path: str  # Relative to project dir
    mask_path: str     # Relative to project dir
    anchor_joint: str
    transform: Transform = field(default_factory=Transform)
    z_index: int = 0

    def with_transform(self, transform: Transform) -> PartData:
        return replace(self, transform=transform)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "texture_path": self.texture_path,
            "mask_path": self.mask_path,
            "anchor_joint": self.anchor_joint,
            "transform": {
                "x": self.transform.x,
                "y": self.transform.y,
                "rotation": self.transform.rotation,
                "scale": self.transform.scale,
            },
            "z_index": self.z_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PartData:
        transform_data = data.get("transform", {})
        return cls(
            name=data["name"],
            texture_path=data["texture_path"],
            mask_path=data["mask_path"],
            anchor_joint=data["anchor_joint"],
            transform=Transform(
                x=transform_data.get("x", 0.0),
                y=transform_data.get("y", 0.0),
                rotation=transform_data.get("rotation", 0.0),
                scale=transform_data.get("scale", 1.0),
            ),
            z_index=data.get("z_index", 0),
        )


# =============================================================================
# SKELETON DATA
# =============================================================================

@dataclass(frozen=True)
class JointData:
    """
    Single skeleton joint.

    Mutable fields (via replace):
    - position: Modified by IK solver or manual editing
    - is_locked: Toggled by user
    - bend_direction: Set in joint properties
    """
    id: str
    position: Point
    parent: str | None = None
    is_locked: bool = False
    bend_direction: float = 1.0

    def with_position(self, pos: Point) -> JointData:
        return replace(self, position=pos)

    def with_locked(self, locked: bool) -> JointData:
        return replace(self, is_locked=locked)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "position": self.position.to_tuple(),
            "parent": self.parent,
            "is_locked": self.is_locked,
            "bend_direction": self.bend_direction,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JointData:
        pos = data.get("position", [0, 0])
        return cls(
            id=data["id"],
            position=Point(x=pos[0], y=pos[1]),
            parent=data.get("parent"),
            is_locked=data.get("is_locked", False),
            bend_direction=data.get("bend_direction", 1.0),
        )


@dataclass(frozen=True)
class BoneData:
    """Bone connecting two joints."""
    from_joint: str
    to_joint: str

    def to_dict(self) -> dict[str, str]:
        return {"from": self.from_joint, "to": self.to_joint}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> BoneData:
        return cls(from_joint=data["from"], to_joint=data["to"])


@dataclass(frozen=True)
class SkeletonData:
    """
    Complete skeleton with joints and bones.

    Produced by: ImageProcessingTab
    Consumed by: EditorTab, MechanismDesignTab
    Modified by: EditorTab (joint positions, locks)
    """
    joints: Mapping[str, JointData] = field(default_factory=dict)
    bones: Sequence[BoneData] = field(default_factory=tuple)
    root_joint: str = ""

    def with_joint(self, joint: JointData) -> SkeletonData:
        """Update or add a joint."""
        new_joints = dict(self.joints)
        new_joints[joint.id] = joint
        return replace(self, joints=new_joints)

    def get_joint(self, joint_id: str) -> JointData | None:
        return self.joints.get(joint_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_joint": self.root_joint,
            "joints": {jid: j.to_dict() for jid, j in self.joints.items()},
            "bones": [b.to_dict() for b in self.bones],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkeletonData:
        joints_data = data.get("joints", {})
        bones_data = data.get("bones", [])
        return cls(
            root_joint=data.get("root_joint", ""),
            joints={jid: JointData.from_dict({**jd, "id": jid}) for jid, jd in joints_data.items()},
            bones=tuple(BoneData.from_dict(b) for b in bones_data),
        )


# =============================================================================
# PATH DATA
# =============================================================================

@dataclass(frozen=True)
class PathData:
    """
    Motion path for a part.

    Produced by: EditorTab (user drawing)
    Consumed by: MechanismDesignTab
    """
    part_name: str
    points: Sequence[Point] = field(default_factory=tuple)
    is_closed: bool = False
    enabled: bool = True

    def with_points(self, points: Sequence[Point]) -> PathData:
        return replace(self, points=tuple(points))

    def with_enabled(self, enabled: bool) -> PathData:
        return replace(self, enabled=enabled)

    def to_dict(self) -> dict[str, Any]:
        return {
            "part_name": self.part_name,
            "points": [p.to_tuple() for p in self.points],
            "is_closed": self.is_closed,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PathData:
        points_data = data.get("points", [])
        return cls(
            part_name=data["part_name"],
            points=tuple(Point.from_tuple(p) for p in points_data),
            is_closed=data.get("is_closed", False),
            enabled=data.get("enabled", True),
        )


# =============================================================================
# MECHANISM DATA
# =============================================================================

@dataclass(frozen=True)
class MechanismData:
    """
    Mechanism layer data.

    Produced by: MechanismDesignTab
    Consumed by: MechanismDesignTab (for animation)
    """
    id: str
    part_name: str
    type: str  # "4_bar_linkage", "cam", "gear", "planetary_gear"
    params: Mapping[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def with_params(self, params: Mapping[str, Any]) -> MechanismData:
        return replace(self, params=dict(params))

    def with_enabled(self, enabled: bool) -> MechanismData:
        return replace(self, enabled=enabled)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "part_name": self.part_name,
            "type": self.type,
            "params": dict(self.params),
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MechanismData:
        return cls(
            id=data["id"],
            part_name=data["part_name"],
            type=data["type"],
            params=data.get("params", {}),
            enabled=data.get("enabled", True),
        )


# =============================================================================
# PROJECT METADATA
# =============================================================================

@dataclass(frozen=True)
class ProjectMetadata:
    """Project metadata for versioning and tracking."""
    version: str = "2.0"
    name: str = "Untitled"
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)

    def with_modified(self) -> ProjectMetadata:
        return replace(self, modified_at=datetime.now())

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectMetadata:
        return cls(
            version=data.get("version", "2.0"),
            name=data.get("name", "Untitled"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            modified_at=datetime.fromisoformat(data["modified_at"]) if "modified_at" in data else datetime.now(),
        )


# =============================================================================
# PROJECT STATE (Single Source of Truth)
# =============================================================================

@dataclass(frozen=True)
class ProjectState:
    """
    Immutable project state - Single Source of Truth.

    All cross-tab data is stored here. Tabs subscribe to changes
    and mutate through ProjectStateManager.

    Factory methods create new state instances (immutability).
    """
    # Project location
    project_dir: Path | None = None
    image_path: Path | None = None

    # Core data
    parts: Mapping[str, PartData] = field(default_factory=dict)
    skeleton: SkeletonData | None = None
    paths: Mapping[str, PathData] = field(default_factory=dict)
    mechanisms: Mapping[str, MechanismData] = field(default_factory=dict)

    # Metadata
    metadata: ProjectMetadata = field(default_factory=ProjectMetadata)

    # =========================================================================
    # FACTORY METHODS (create new state)
    # =========================================================================

    def with_project_dir(self, path: Path | None) -> ProjectState:
        return replace(self, project_dir=path)

    def with_image_path(self, path: Path | None) -> ProjectState:
        return replace(self, image_path=path)

    def with_parts(self, parts: Mapping[str, PartData]) -> ProjectState:
        return replace(self, parts=dict(parts), metadata=self.metadata.with_modified())

    def with_part(self, part: PartData) -> ProjectState:
        new_parts = dict(self.parts)
        new_parts[part.name] = part
        return replace(self, parts=new_parts, metadata=self.metadata.with_modified())

    def without_part(self, part_name: str) -> ProjectState:
        new_parts = {k: v for k, v in self.parts.items() if k != part_name}
        return replace(self, parts=new_parts, metadata=self.metadata.with_modified())

    def with_skeleton(self, skeleton: SkeletonData | None) -> ProjectState:
        return replace(self, skeleton=skeleton, metadata=self.metadata.with_modified())

    def with_paths(self, paths: Mapping[str, PathData]) -> ProjectState:
        return replace(self, paths=dict(paths), metadata=self.metadata.with_modified())

    def with_path(self, path: PathData) -> ProjectState:
        new_paths = dict(self.paths)
        new_paths[path.part_name] = path
        return replace(self, paths=new_paths, metadata=self.metadata.with_modified())

    def without_path(self, part_name: str) -> ProjectState:
        new_paths = {k: v for k, v in self.paths.items() if k != part_name}
        return replace(self, paths=new_paths, metadata=self.metadata.with_modified())

    def with_mechanisms(self, mechanisms: Mapping[str, MechanismData]) -> ProjectState:
        return replace(self, mechanisms=dict(mechanisms), metadata=self.metadata.with_modified())

    def with_mechanism(self, mechanism: MechanismData) -> ProjectState:
        new_mechanisms = dict(self.mechanisms)
        new_mechanisms[mechanism.id] = mechanism
        return replace(self, mechanisms=new_mechanisms, metadata=self.metadata.with_modified())

    def without_mechanism(self, mechanism_id: str) -> ProjectState:
        new_mechanisms = {k: v for k, v in self.mechanisms.items() if k != mechanism_id}
        return replace(self, mechanisms=new_mechanisms, metadata=self.metadata.with_modified())

    def with_metadata(self, metadata: ProjectMetadata) -> ProjectState:
        return replace(self, metadata=metadata)

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    def is_empty(self) -> bool:
        return not self.parts and self.skeleton is None

    def has_parts(self) -> bool:
        return bool(self.parts)

    def has_skeleton(self) -> bool:
        return self.skeleton is not None

    def has_paths(self) -> bool:
        return bool(self.paths)

    def has_mechanisms(self) -> bool:
        return bool(self.mechanisms)

    def get_part(self, name: str) -> PartData | None:
        return self.parts.get(name)

    def get_path(self, part_name: str) -> PathData | None:
        return self.paths.get(part_name)

    def get_mechanism(self, mechanism_id: str) -> MechanismData | None:
        return self.mechanisms.get(mechanism_id)

    def get_mechanisms_for_part(self, part_name: str) -> list[MechanismData]:
        return [m for m in self.mechanisms.values() if m.part_name == part_name]

    def get_enabled_paths(self) -> dict[str, PathData]:
        return {k: v for k, v in self.paths.items() if v.enabled}

    def get_enabled_mechanisms(self) -> dict[str, MechanismData]:
        return {k: v for k, v in self.mechanisms.items() if v.enabled}

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "metadata": self.metadata.to_dict(),
            "image_path": str(self.image_path) if self.image_path else None,
            "parts": {name: part.to_dict() for name, part in self.parts.items()},
            "skeleton": self.skeleton.to_dict() if self.skeleton else None,
            "paths": {name: path.to_dict() for name, path in self.paths.items()},
            "mechanisms": {mid: mech.to_dict() for mid, mech in self.mechanisms.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], project_dir: Path | None = None) -> ProjectState:
        """Deserialize from dictionary."""
        parts_data = data.get("parts", {})
        paths_data = data.get("paths", {})
        mechanisms_data = data.get("mechanisms", {})
        skeleton_data = data.get("skeleton")

        image_path_str = data.get("image_path")

        return cls(
            project_dir=project_dir,
            image_path=Path(image_path_str) if image_path_str else None,
            metadata=ProjectMetadata.from_dict(data.get("metadata", {})),
            parts={name: PartData.from_dict({**pdata, "name": name}) for name, pdata in parts_data.items()},
            skeleton=SkeletonData.from_dict(skeleton_data) if skeleton_data else None,
            paths={name: PathData.from_dict({**pdata, "part_name": name}) for name, pdata in paths_data.items()},
            mechanisms={mid: MechanismData.from_dict(mdata) for mid, mdata in mechanisms_data.items()},
        )

    @classmethod
    def empty(cls) -> ProjectState:
        """Create empty state."""
        return cls()
