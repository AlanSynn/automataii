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
    roi: tuple[float, float, float, float] | None = None
    fill_color: str = "rgba(128,128,128,0.5)"
    fixed: bool = False
    opacity: float = 1.0
    group: str | None = None
    original_svg_path: str | None = None
    enhanced_svg_path: str | None = None
    effective_bbox_offset_x: float = 0.0
    effective_bbox_offset_y: float = 0.0
    show_anchor: bool = False
    local_pivot_offset: tuple[float, float] | None = None

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
            "roi": list(self.roi) if self.roi is not None else None,
            "fill_color": self.fill_color,
            "fixed": self.fixed,
            "opacity": self.opacity,
            "group": self.group,
            "original_svg_path": self.original_svg_path,
            "enhanced_svg_path": self.enhanced_svg_path,
            "effective_bbox_offset_x": self.effective_bbox_offset_x,
            "effective_bbox_offset_y": self.effective_bbox_offset_y,
            "show_anchor": self.show_anchor,
            "local_pivot_offset": (
                list(self.local_pivot_offset) if self.local_pivot_offset is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PartData:
        transform_data = data.get("transform", {})
        raw_texture_path = data.get("texture_path")
        if raw_texture_path is None:
            raw_texture_path = data.get("image_path", "")
        texture_path = str(raw_texture_path or "")

        raw_mask_path = data.get("mask_path")
        if raw_mask_path is None:
            raw_mask_path = texture_path
        mask_path = str(raw_mask_path or "")

        raw_roi = data.get("roi")
        roi: tuple[float, float, float, float] | None = None
        if isinstance(raw_roi, list | tuple) and len(raw_roi) >= 4:
            roi = (
                float(raw_roi[0]),
                float(raw_roi[1]),
                float(raw_roi[2]),
                float(raw_roi[3]),
            )

        raw_local_pivot = data.get("local_pivot_offset")
        local_pivot_offset: tuple[float, float] | None = None
        if isinstance(raw_local_pivot, list | tuple) and len(raw_local_pivot) >= 2:
            local_pivot_offset = (float(raw_local_pivot[0]), float(raw_local_pivot[1]))

        return cls(
            name=data["name"],
            texture_path=texture_path,
            mask_path=mask_path,
            anchor_joint=data["anchor_joint"],
            transform=Transform(
                x=transform_data.get("x", 0.0),
                y=transform_data.get("y", 0.0),
                rotation=transform_data.get("rotation", 0.0),
                scale=transform_data.get("scale", 1.0),
            ),
            z_index=data.get("z_index", 0),
            roi=roi,
            fill_color=data.get("fill_color", "rgba(128,128,128,0.5)"),
            fixed=bool(data.get("fixed", False)),
            opacity=float(data.get("opacity", 1.0)),
            group=data.get("group"),
            original_svg_path=data.get("original_svg_path"),
            enhanced_svg_path=data.get("enhanced_svg_path"),
            effective_bbox_offset_x=float(data.get("effective_bbox_offset_x", 0.0)),
            effective_bbox_offset_y=float(data.get("effective_bbox_offset_y", 0.0)),
            show_anchor=bool(data.get("show_anchor", False)),
            local_pivot_offset=local_pivot_offset,
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
    name: str | None = None
    parent: str | None = None
    is_locked: bool = False
    bend_direction: float = 1.0

    def with_position(self, pos: Point) -> JointData:
        return replace(self, position=pos)

    def with_locked(self, locked: bool) -> JointData:
        return replace(self, is_locked=locked)

    def to_dict(self) -> dict[str, Any]:
        joint_name = self.name or self.id
        return {
            "id": self.id,
            "name": joint_name,
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
            name=data.get("name") or data["id"],
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
class TimedPoint:
    """
    Point with timestamp for velocity/acceleration-aware animation.

    The timestamp is relative to the start of drawing (in seconds).
    This allows preserving the original drawing velocity for natural motion.
    """
    x: float
    y: float
    t: float  # Time in seconds from start

    def to_point(self) -> Point:
        return Point(x=self.x, y=self.y)

    def to_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.t)

    @classmethod
    def from_tuple(cls, data: tuple[float, float, float]) -> TimedPoint:
        return cls(x=data[0], y=data[1], t=data[2])

    @classmethod
    def from_point(cls, point: Point, t: float) -> TimedPoint:
        return cls(x=point.x, y=point.y, t=t)


@dataclass(frozen=True)
class PathData:
    """
    Motion path for a part with optional timing information.

    Produced by: EditorTab (user drawing)
    Consumed by: MechanismDesignTab

    If timed_points is provided, animation uses time-based interpolation
    to preserve original drawing velocity/acceleration.
    Otherwise, falls back to uniform interpolation over points.
    """
    part_name: str
    points: Sequence[Point] = field(default_factory=tuple)
    timed_points: Sequence[TimedPoint] | None = None  # Optional timing data
    total_duration: float = 0.0  # Total drawing duration in seconds
    is_closed: bool = False
    enabled: bool = True

    def with_points(self, points: Sequence[Point]) -> PathData:
        return replace(self, points=tuple(points))

    def with_timed_points(
        self,
        timed_points: Sequence[TimedPoint],
        total_duration: float,
    ) -> PathData:
        """Set timed points with duration."""
        points = tuple(tp.to_point() for tp in timed_points)
        return replace(
            self,
            points=points,
            timed_points=tuple(timed_points),
            total_duration=total_duration,
        )

    def with_enabled(self, enabled: bool) -> PathData:
        return replace(self, enabled=enabled)

    def get_point_at_progress(self, progress: float) -> Point | None:
        """
        Get interpolated point at given progress (0.0-1.0).

        If timed_points is available, uses time-based interpolation
        to preserve original velocity. Otherwise, uses uniform interpolation.
        """
        if not self.points:
            return None

        progress = max(0.0, min(1.0, progress))

        # Time-based interpolation if timing data available
        if self.timed_points and self.total_duration > 0:
            target_time = progress * self.total_duration
            return self._interpolate_at_time(target_time)

        # Fallback: uniform interpolation
        return self._interpolate_uniform(progress)

    def _interpolate_at_time(self, target_time: float) -> Point:
        """Interpolate position at given time using timed points."""
        if not self.timed_points:
            return self.points[0] if self.points else Point(0, 0)

        # Find surrounding points
        timed = list(self.timed_points)
        n = len(timed)

        if n == 1:
            return timed[0].to_point()

        # Clamp to valid range
        target_time = max(0.0, min(target_time, self.total_duration))

        # Binary search for the right segment
        for i in range(n - 1):
            if timed[i].t <= target_time <= timed[i + 1].t:
                # Linear interpolation within segment
                t0, t1 = timed[i].t, timed[i + 1].t
                if t1 - t0 < 1e-9:
                    return timed[i].to_point()

                alpha = (target_time - t0) / (t1 - t0)
                x = timed[i].x + alpha * (timed[i + 1].x - timed[i].x)
                y = timed[i].y + alpha * (timed[i + 1].y - timed[i].y)
                return Point(x=x, y=y)

        # Edge case: return last point
        return timed[-1].to_point()

    def _interpolate_uniform(self, progress: float) -> Point:
        """Uniform interpolation over points."""
        if not self.points:
            return Point(0, 0)

        n = len(self.points)
        if n == 1:
            return self.points[0]

        idx_float = progress * (n - 1)
        idx = int(idx_float)
        alpha = idx_float - idx

        if idx >= n - 1:
            return self.points[-1]

        p0, p1 = self.points[idx], self.points[idx + 1]
        x = p0.x + alpha * (p1.x - p0.x)
        y = p0.y + alpha * (p1.y - p0.y)
        return Point(x=x, y=y)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "part_name": self.part_name,
            "points": [p.to_tuple() for p in self.points],
            "is_closed": self.is_closed,
            "enabled": self.enabled,
        }
        if self.timed_points:
            result["timed_points"] = [tp.to_tuple() for tp in self.timed_points]
            result["total_duration"] = self.total_duration
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PathData:
        points_data = data.get("points", [])
        timed_data = data.get("timed_points")

        timed_points = None
        if timed_data:
            timed_points = tuple(TimedPoint.from_tuple(tp) for tp in timed_data)

        return cls(
            part_name=data["part_name"],
            points=tuple(Point.from_tuple(p) for p in points_data),
            timed_points=timed_points,
            total_duration=data.get("total_duration", 0.0),
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
    layer_data: Mapping[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def with_params(self, params: Mapping[str, Any]) -> MechanismData:
        return replace(self, params=dict(params))

    def with_layer_data(self, layer_data: Mapping[str, Any]) -> MechanismData:
        return replace(self, layer_data=dict(layer_data))

    def with_enabled(self, enabled: bool) -> MechanismData:
        return replace(self, enabled=enabled)

    @staticmethod
    def _json_safe(value: Any) -> Any:
        """Convert mechanism payload to JSON-safe values."""
        if value is None or isinstance(value, bool | int | float | str):
            return value

        if isinstance(value, Path):
            return str(value)

        if isinstance(value, Mapping):
            out: dict[str, Any] = {}
            for k, v in value.items():
                out[str(k)] = MechanismData._json_safe(v)
            return out

        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            return [MechanismData._json_safe(v) for v in value]

        # NumPy arrays/scalars or similar structures
        if hasattr(value, "tolist"):
            try:
                return MechanismData._json_safe(value.tolist())
            except Exception:
                pass

        # Drop Qt/runtime-heavy objects to avoid serialization failure
        return None

    def to_dict(self) -> dict[str, Any]:
        serialized = {
            "id": self.id,
            "part_name": self.part_name,
            "type": self.type,
            "params": self._json_safe(dict(self.params)) or {},
            "enabled": self.enabled,
        }
        if self.layer_data:
            serialized_layer_data = self._json_safe(dict(self.layer_data)) or {}
            if serialized_layer_data:
                serialized["layer_data"] = serialized_layer_data
        return serialized

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MechanismData:
        return cls(
            id=data["id"],
            part_name=data["part_name"],
            type=data["type"],
            params=data.get("params", {}),
            layer_data=data.get("layer_data", {}),
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
        image_path = None
        if image_path_str:
            parsed_image_path = Path(image_path_str)
            if not parsed_image_path.is_absolute() and project_dir is not None:
                parsed_image_path = project_dir / parsed_image_path
            image_path = parsed_image_path

        resolved_parts: dict[str, PartData] = {}
        for name, pdata in parts_data.items():
            normalized_part = dict(pdata)

            def _resolve_asset_path(raw_path: Any) -> str:
                if raw_path is None:
                    return ""
                path_str = str(raw_path)
                if not path_str:
                    return ""
                candidate = Path(path_str)
                if candidate.is_absolute() or project_dir is None:
                    return path_str
                return str(project_dir / candidate)

            if "texture_path" in normalized_part or "image_path" in normalized_part:
                normalized_part["texture_path"] = _resolve_asset_path(
                    normalized_part.get("texture_path", normalized_part.get("image_path", ""))
                )

            if "mask_path" in normalized_part:
                normalized_part["mask_path"] = _resolve_asset_path(normalized_part.get("mask_path", ""))

            if "original_svg_path" in normalized_part:
                normalized_part["original_svg_path"] = _resolve_asset_path(
                    normalized_part.get("original_svg_path")
                )
            if "enhanced_svg_path" in normalized_part:
                normalized_part["enhanced_svg_path"] = _resolve_asset_path(
                    normalized_part.get("enhanced_svg_path")
                )

            resolved_parts[name] = PartData.from_dict({**normalized_part, "name": name})

        return cls(
            project_dir=project_dir,
            image_path=image_path,
            metadata=ProjectMetadata.from_dict(data.get("metadata", {})),
            parts=resolved_parts,
            skeleton=SkeletonData.from_dict(skeleton_data) if skeleton_data else None,
            paths={name: PathData.from_dict({**pdata, "part_name": name}) for name, pdata in paths_data.items()},
            mechanisms={mid: MechanismData.from_dict(mdata) for mid, mdata in mechanisms_data.items()},
        )

    @classmethod
    def empty(cls) -> ProjectState:
        """Create empty state."""
        return cls()
