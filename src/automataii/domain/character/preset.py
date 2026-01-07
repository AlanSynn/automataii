"""
Character Preset Domain Models.

Immutable value objects representing character presets for mechanism simulation.
These presets define dummy characters (silhouettes) that can be assigned to
mechanisms for visualization and simulation.

Architecture: Domain Layer - Pure business logic, no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True)
class SkeletonJoint:
    """Represents a joint in the character skeleton hierarchy.

    Attributes:
        id: Unique joint identifier (e.g., "left_shoulder", "right_knee")
        parent_id: ID of the parent joint (None for root)
        position: Default (x, y) position relative to parent
        children: IDs of child joints
    """

    id: str
    parent_id: str | None
    position: tuple[float, float]
    children: tuple[str, ...] = field(default_factory=tuple)

    def with_position(self, x: float, y: float) -> SkeletonJoint:
        """Create a copy with updated position."""
        return SkeletonJoint(
            id=self.id,
            parent_id=self.parent_id,
            position=(x, y),
            children=self.children,
        )


@dataclass(frozen=True)
class PresetPartData:
    """Definition of a single body part within a character preset.

    Attributes:
        name: Part name (e.g., "head", "upper_arm_L")
        svg_path: Path to the SVG silhouette asset
        anchor_joint: Joint ID this part is anchored to
        z_index: Drawing order (higher = drawn on top)
        default_transform: Default (x, y, rotation) transform
    """

    name: str
    svg_path: str
    anchor_joint: str
    z_index: int = 0
    default_transform: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "svg_path": self.svg_path,
            "anchor_joint": self.anchor_joint,
            "z_index": self.z_index,
            "default_transform": list(self.default_transform),
        }

    @classmethod
    def from_dict(cls, data: dict) -> PresetPartData:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            svg_path=data["svg_path"],
            anchor_joint=data["anchor_joint"],
            z_index=data.get("z_index", 0),
            default_transform=tuple(data.get("default_transform", [0.0, 0.0, 0.0])),
        )


@dataclass(frozen=True)
class CharacterPreset:
    """Immutable character preset configuration.

    A preset defines a complete dummy character including all body parts
    and skeleton structure. Used for assigning placeholder characters
    to mechanisms for simulation.

    Attributes:
        id: Unique preset identifier
        name: Human-readable display name
        parts: Mapping of part name to PresetPartData
        skeleton: Mapping of joint ID to SkeletonJoint
        thumbnail_path: Optional path to thumbnail image
        description: Optional description text
    """

    id: str
    name: str
    parts: Mapping[str, PresetPartData]
    skeleton: Mapping[str, SkeletonJoint]
    thumbnail_path: str | None = None
    description: str = ""

    def get_part(self, name: str) -> PresetPartData | None:
        """Get a part by name."""
        return self.parts.get(name)

    def get_joint(self, joint_id: str) -> SkeletonJoint | None:
        """Get a joint by ID."""
        return self.skeleton.get(joint_id)

    def get_root_joint(self) -> SkeletonJoint | None:
        """Get the root joint (joint with no parent)."""
        for joint in self.skeleton.values():
            if joint.parent_id is None:
                return joint
        return None

    def get_parts_sorted_by_z(self) -> Sequence[PresetPartData]:
        """Get parts sorted by z-index (drawing order)."""
        return tuple(sorted(self.parts.values(), key=lambda p: p.z_index))

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "parts": {name: part.to_dict() for name, part in self.parts.items()},
            "skeleton": {
                jid: {
                    "id": j.id,
                    "parent_id": j.parent_id,
                    "position": list(j.position),
                    "children": list(j.children),
                }
                for jid, j in self.skeleton.items()
            },
            "thumbnail_path": self.thumbnail_path,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CharacterPreset:
        """Create from dictionary."""
        parts = {
            name: PresetPartData.from_dict(pdata)
            for name, pdata in data.get("parts", {}).items()
        }
        skeleton = {
            jid: SkeletonJoint(
                id=jdata["id"],
                parent_id=jdata.get("parent_id"),
                position=tuple(jdata.get("position", [0, 0])),
                children=tuple(jdata.get("children", [])),
            )
            for jid, jdata in data.get("skeleton", {}).items()
        }
        return cls(
            id=data["id"],
            name=data["name"],
            parts=parts,
            skeleton=skeleton,
            thumbnail_path=data.get("thumbnail_path"),
            description=data.get("description", ""),
        )

    @classmethod
    def create_silhouette_human(cls) -> CharacterPreset:
        """Factory method to create the default human silhouette preset.

        Returns a preset with 10 body parts and standard humanoid skeleton.
        """
        # Skeleton joint definitions
        skeleton = {
            "root": SkeletonJoint(
                id="root", parent_id=None, position=(0, 0),
                children=("spine", "left_hip", "right_hip")
            ),
            "spine": SkeletonJoint(
                id="spine", parent_id="root", position=(0, -50),
                children=("neck",)
            ),
            "neck": SkeletonJoint(
                id="neck", parent_id="spine", position=(0, -40),
                children=("head", "left_shoulder", "right_shoulder")
            ),
            "head": SkeletonJoint(
                id="head", parent_id="neck", position=(0, -30),
                children=()
            ),
            "left_shoulder": SkeletonJoint(
                id="left_shoulder", parent_id="neck", position=(-25, 0),
                children=("left_elbow",)
            ),
            "left_elbow": SkeletonJoint(
                id="left_elbow", parent_id="left_shoulder", position=(-30, 0),
                children=("left_wrist",)
            ),
            "left_wrist": SkeletonJoint(
                id="left_wrist", parent_id="left_elbow", position=(-25, 0),
                children=()
            ),
            "right_shoulder": SkeletonJoint(
                id="right_shoulder", parent_id="neck", position=(25, 0),
                children=("right_elbow",)
            ),
            "right_elbow": SkeletonJoint(
                id="right_elbow", parent_id="right_shoulder", position=(30, 0),
                children=("right_wrist",)
            ),
            "right_wrist": SkeletonJoint(
                id="right_wrist", parent_id="right_elbow", position=(25, 0),
                children=()
            ),
            "left_hip": SkeletonJoint(
                id="left_hip", parent_id="root", position=(-15, 10),
                children=("left_knee",)
            ),
            "left_knee": SkeletonJoint(
                id="left_knee", parent_id="left_hip", position=(0, 40),
                children=("left_ankle",)
            ),
            "left_ankle": SkeletonJoint(
                id="left_ankle", parent_id="left_knee", position=(0, 40),
                children=()
            ),
            "right_hip": SkeletonJoint(
                id="right_hip", parent_id="root", position=(15, 10),
                children=("right_knee",)
            ),
            "right_knee": SkeletonJoint(
                id="right_knee", parent_id="right_hip", position=(0, 40),
                children=("right_ankle",)
            ),
            "right_ankle": SkeletonJoint(
                id="right_ankle", parent_id="right_knee", position=(0, 40),
                children=()
            ),
        }

        # Part definitions (10 parts)
        parts = {
            "head": PresetPartData(
                name="head",
                svg_path="resources/presets/characters/silhouette_human/parts/head.svg",
                anchor_joint="neck",
                z_index=10,
            ),
            "torso": PresetPartData(
                name="torso",
                svg_path="resources/presets/characters/silhouette_human/parts/torso.svg",
                anchor_joint="root",
                z_index=0,
            ),
            "upper_arm_L": PresetPartData(
                name="upper_arm_L",
                svg_path="resources/presets/characters/silhouette_human/parts/upper_arm.svg",
                anchor_joint="left_shoulder",
                z_index=5,
            ),
            "lower_arm_L": PresetPartData(
                name="lower_arm_L",
                svg_path="resources/presets/characters/silhouette_human/parts/lower_arm.svg",
                anchor_joint="left_elbow",
                z_index=6,
            ),
            "upper_arm_R": PresetPartData(
                name="upper_arm_R",
                svg_path="resources/presets/characters/silhouette_human/parts/upper_arm.svg",
                anchor_joint="right_shoulder",
                z_index=5,
            ),
            "lower_arm_R": PresetPartData(
                name="lower_arm_R",
                svg_path="resources/presets/characters/silhouette_human/parts/lower_arm.svg",
                anchor_joint="right_elbow",
                z_index=6,
            ),
            "upper_leg_L": PresetPartData(
                name="upper_leg_L",
                svg_path="resources/presets/characters/silhouette_human/parts/upper_leg.svg",
                anchor_joint="left_hip",
                z_index=3,
            ),
            "lower_leg_L": PresetPartData(
                name="lower_leg_L",
                svg_path="resources/presets/characters/silhouette_human/parts/lower_leg.svg",
                anchor_joint="left_knee",
                z_index=4,
            ),
            "upper_leg_R": PresetPartData(
                name="upper_leg_R",
                svg_path="resources/presets/characters/silhouette_human/parts/upper_leg.svg",
                anchor_joint="right_hip",
                z_index=3,
            ),
            "lower_leg_R": PresetPartData(
                name="lower_leg_R",
                svg_path="resources/presets/characters/silhouette_human/parts/lower_leg.svg",
                anchor_joint="right_knee",
                z_index=4,
            ),
        }

        return cls(
            id="silhouette_human",
            name="Human Silhouette",
            parts=parts,
            skeleton=skeleton,
            thumbnail_path="resources/presets/characters/silhouette_human/thumbnail.png",
            description="Simple human silhouette for mechanism simulation",
        )
