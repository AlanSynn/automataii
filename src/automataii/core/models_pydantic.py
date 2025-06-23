"""
Pydantic models for data validation and structure, particularly for project files.
"""


from pydantic import BaseModel, Field, validator
from PyQt6.QtCore import QPointF  # For type hinting, will be validated as tuple/list

# --- Utility Types ---


class QPointFModel(BaseModel):
    """Represents a QPointF as a tuple for serialization/validation."""

    x: float
    y: float

    @validator("x", "y", pre=True, allow_reuse=True)
    def validate_number(cls, v):
        try:
            return float(v)
        except (ValueError, TypeError):
            raise ValueError("Coordinate must be a number")

    @classmethod
    def from_qpointf(cls, point: QPointF):
        return cls(x=point.x(), y=point.y())

    @classmethod
    def from_tuple(cls, t: tuple[float, float]):
        return cls(x=t[0], y=t[1])

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    def to_qpointf(self) -> QPointF:
        return QPointF(self.x, self.y)


class MotionPathDataModel(BaseModel):  # Placeholder for more complex motion path data
    # For now, let's assume it could be a list of points or a more structured object
    # This needs to align with how QPainterPath or list of QPointF is actually stored if serialized.
    # If it's a QPainterPath, direct Pydantic modeling is hard. Usually, it's a list of commands/points.
    # For simplicity, let's assume it's a list of QPointF-like tuples for now if serialized.
    path_points: list[QPointFModel] | None = None
    # Or, if it's raw SVG path string:
    # svg_path_string: Optional[str] = None


# --- Core Models ---


class PartInfoModel(BaseModel):
    """Pydantic model for individual part data from project files."""

    name: str  # Will be populated from the key of the parts dictionary
    roi: list[float] | None = None  # Region of Interest [x, y, width, height]
    z_value: float = 0.0
    image_path: str | None = None  # Path to the image file (e.g., PNG)
    fill_color: str = "rgba(128,128,128,0.5)"  # Default gray
    fixed: bool = False
    opacity: float = 1.0
    group: str | None = None  # Group identifier for the part

    # Fields that might be populated by other processes or specific to certain views/data sources
    # These are often not directly in the minimal parts_info.json but might be if project saving evolves
    original_svg_path: str | None = None  # Path to original, unmodified SVG
    enhanced_svg_path: str | None = None  # Path to a high-quality version of the SVG

    # Offset data, likely calculated, but good to have if it's ever stored
    effective_bbox_offset_x: float = 0.0
    effective_bbox_offset_y: float = 0.0

    # Motion path data - this is complex.
    # If stored in JSON, it would likely be a simplified representation (e.g., list of points)
    # or a reference to an external file. For now, assume it might be a list of QPointF-like tuples.
    motion_path_data: MotionPathDataModel | None = (
        None  # Or List[QPointFModel] if simpler
    )
    show_anchor: bool = False  # Default to not showing the anchor
    local_pivot_offset: list[float] | None = Field(
        default=None,
        description="Local pivot offset [x, y] relative to the part's own origin (top-left of its ROI/image)",
    )
    anchor_joint_id: str | None = Field(
        default=None,
        description="ID of the skeleton joint this part is primarily anchored to",
    )

    class Config:
        arbitrary_types_allowed = True  # For QPointF if we decide to store it directly (not recommended for JSON)

    @validator("roi")
    def roi_must_have_four_elements(cls, v):
        if v is not None and len(v) != 4:
            raise ValueError(
                "roi must contain four float elements: [x, y, width, height]"
            )
        return v

    @validator("local_pivot_offset")
    def local_pivot_offset_must_have_two_elements(cls, v):
        if v is not None and len(v) != 2:
            raise ValueError(
                "local_pivot_offset must contain two float elements: [x, y]"
            )
        return v


class SkeletonJointModel(BaseModel):
    """Pydantic model for skeleton joint data."""

    id: str
    name: str
    position: list[float]  # [x, y]
    parent: str | None = None
    color: list[int] | None = None  # [r, g, b, a] optional
    label_offset: list[float] | None = Field(
        None, alias="labelOffset"
    )  # [dx, dy] optional

    @validator("position")
    def position_must_have_two_elements(cls, v):
        if len(v) != 2:
            raise ValueError("position must contain two float elements: [x, y]")
        return v

    @validator("color")
    def color_must_have_three_or_four_elements(cls, v):
        if v is not None and len(v) not in [3, 4]:
            raise ValueError(
                "color must contain three (RGB) or four (RGBA) integer elements"
            )
        return v

    @validator("label_offset")
    def label_offset_must_have_two_elements(cls, v):
        if v is not None and len(v) != 2:
            raise ValueError("label_offset must contain two float elements: [dx, dy]")
        return v

    class Config:
        populate_by_name = True


class CharacterDataModel(BaseModel):
    """Pydantic model for the 'character' object in project files."""

    name: str
    parts: dict[str, PartInfoModel] = Field(default_factory=dict)
    skeleton_joints: list[SkeletonJointModel] = Field(
        default_factory=list, alias="skeleton"
    )  # Alias for older format too
    # Allow 'skeleton' as an alias for 'skeleton_joints' for backwards compatibility

    @validator("parts", pre=True)
    def populate_part_names(cls, v):
        if isinstance(v, dict):
            for name, part_data in v.items():
                if isinstance(part_data, dict) and "name" not in part_data:
                    part_data["name"] = name
        return v

    @validator("skeleton_joints", pre=True, always=True)
    def use_skeleton_if_skeleton_joints_empty(cls, v, values):
        # This validator is tricky because `values` gives already validated fields.
        # Pydantic processes fields in order. If 'skeleton' is defined later, this won't see it.
        # The alias on the field itself is usually better.
        # For now, we assume `alias='skeleton'` on the field handles reading from 'skeleton'.
        # If 'skeleton_joints' specifically exists but is empty, and 'skeleton' exists with data,
        # this logic is more complex.
        # The alias `Field(..., alias='skeleton')` should handle the case where 'skeleton_joints' is absent
        # and 'skeleton' exists. If 'skeleton_joints' is present (even if empty), it takes precedence.
        return v


class ProjectMetadata(BaseModel):
    """Metadata for Automataii projects."""

    name: str
    description: str | None = None
    version: str = "1.0.0"
    created_at: str | None = None
    modified_at: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)

    class Config:
        extra = "allow"  # Allow additional fields for extensibility


class ProjectFileModel(BaseModel):
    """Root Pydantic model for the entire project file (e.g., parts_info.json)."""

    character: CharacterDataModel
    metadata: ProjectMetadata | None = None


# Example usage (for testing and understanding)
if __name__ == "__main__":
    # Example 1: Valid PartInfo data
    part_data_valid = {
        "name": "head",
        "svg_path_file": "path/to/head.svg",
        "roi": [10.0, 10.0, 20.0, 20.0],
        "z_value": 1.0,
        "fixed": True,
        "motion_path_data": {"path_points": [(0.0, 0.0), (1.0, 1.0)]},
    }
    part_model_valid = PartInfoModel(**part_data_valid)
    print(f"Valid PartInfoModel: {part_model_valid.model_dump_json(indent=2)}")

    # Example 2: PartInfo data with missing optional fields
    part_data_minimal = {"name": "torso", "svg_path_file": "path/to/torso.svg"}
    part_model_minimal = PartInfoModel(**part_data_minimal)
    print(f"Minimal PartInfoModel: {part_model_minimal.model_dump_json(indent=2)}")

    # Example 3: Invalid PartInfo data (roi wrong size)
    part_data_invalid_roi = {
        "name": "arm",
        "svg_path_file": "path/to/arm.svg",
        "roi": [10.0, 10.0],
    }
    try:
        PartInfoModel(**part_data_invalid_roi)
    except ValueError as e:
        print(f"Invalid PartInfo data (expected error): {e}")

    # Example 4: Valid SkeletonJoint data
    joint_data_valid = {
        "id": "j1",
        "name": "neck",
        "position": [20.0, 30.0],
        "parent": "torso",
    }
    joint_model_valid = SkeletonJointModel(**joint_data_valid)
    print(f"Valid SkeletonJointModel: {joint_model_valid.model_dump_json(indent=2)}")

    joint_data_with_offset = {
        "id": "j2",
        "name": "head_top",
        "position": [20.0, 10.0],
        "parent": "j1",
        "labelOffset": [5.0, -2.0],
    }
    joint_model_with_offset = SkeletonJointModel(**joint_data_with_offset)
    print(
        f"Valid SkeletonJointModel with offset: {joint_model_with_offset.model_dump_json(indent=2)}"
    )

    # Example 5: Valid CharacterData
    character_data_valid = {
        "name": "DummyCharacter",
        "parts": {
            "head": {
                "svg_path_file": "head.svg",
                "roi": [10, 10, 20, 20],
                "z_value": 1,
            },
            "torso": {
                "svg_path_file": "torso.svg",
                "roi": [0, 30, 40, 50],
                "z_value": 0,
                "motion_path_data": {"path_points": [[0, 0], [1, 1]]},
            },
        },
        "skeleton_joints": [  # Using 'skeleton_joints'
            {"id": "j1", "name": "neck", "position": [20, 30]},
            {"id": "j2", "name": "head_top", "position": [20, 10], "parent": "j1"},
        ],
    }
    char_model_valid = CharacterDataModel(**character_data_valid)
    print(f"Valid CharacterDataModel: {char_model_valid.model_dump_json(indent=2)}")

    # Example 6: Valid CharacterData using 'skeleton' alias
    character_data_alias = {
        "name": "AliasCharacter",
        "parts": {"body": {"svg_path_file": "body.svg"}},
        "skeleton": [  # Using 'skeleton' alias
            {"id": "s1", "name": "root", "position": [0, 0]}
        ],
    }
    char_model_alias = CharacterDataModel(**character_data_alias)
    print(
        f"CharacterDataModel with alias: {char_model_alias.model_dump_json(indent=2)}"
    )
    assert len(char_model_alias.skeleton_joints) == 1
    assert char_model_alias.skeleton_joints[0].name == "root"

    # Example 7: Full ProjectFile
    project_file_data = {"character": character_data_valid}
    project_model = ProjectFileModel(**project_file_data)
    print(f"Valid ProjectFileModel: {project_model.model_dump_json(indent=2)}")
    assert project_model.character.parts["head"].name == "head"

    # Example 8: QPointFModel validation
    qpf_list = [10.0, 20.5]
    qpf_model_from_list = QPointFModel(root=qpf_list)
    print(
        f"QPointFModel from list: {qpf_model_from_list.root}, QPointF: {qpf_model_from_list.to_qpointf()}"
    )

    qpointf_obj = QPointF(5.5, -2.1)
    qpf_model_from_qpointf = QPointFModel(root=qpointf_obj)  # type: ignore
    print(
        f"QPointFModel from QPointF: {qpf_model_from_qpointf.root}, QPointF: {qpf_model_from_qpointf.to_qpointf()}"
    )

    try:
        QPointFModel(root=("a", "b"))  # type: ignore
    except ValueError as e:
        print(f"QPointFModel error (expected): {e}")

    print("Pydantic models defined and basic tests passed.")
