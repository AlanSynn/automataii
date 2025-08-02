"""
Pydantic models for data validation and structure, particularly for project files.
"""

from pydantic import BaseModel, Field, validator
from typing import Literal
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
    motion_path_data: MotionPathDataModel | None = None  # Or List[QPointFModel] if simpler
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
        arbitrary_types_allowed = (
            True  # For QPointF if we decide to store it directly (not recommended for JSON)
        )

    @validator("roi")
    def roi_must_have_four_elements(cls, v):
        if v is not None and len(v) != 4:
            raise ValueError("roi must contain four float elements: [x, y, width, height]")
        return v

    @validator("local_pivot_offset")
    def local_pivot_offset_must_have_two_elements(cls, v):
        if v is not None and len(v) != 2:
            raise ValueError("local_pivot_offset must contain two float elements: [x, y]")
        return v


class SkeletonJointModel(BaseModel):
    """Pydantic model for skeleton joint data."""

    id: str
    name: str
    position: list[float]  # [x, y]
    parent: str | None = None
    color: list[int] | None = None  # [r, g, b, a] optional
    label_offset: list[float] | None = Field(None, alias="labelOffset")  # [dx, dy] optional

    @validator("position")
    def position_must_have_two_elements(cls, v):
        if len(v) != 2:
            raise ValueError("position must contain two float elements: [x, y]")
        return v

    @validator("color")
    def color_must_have_three_or_four_elements(cls, v):
        if v is not None and len(v) not in [3, 4]:
            raise ValueError("color must contain three (RGB) or four (RGBA) integer elements")
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


# --- Mechanism Models ---


class CamMechanismModel(BaseModel):
    """Pydantic model for cam mechanism data."""
    
    type: Literal["cam"] = "cam"
    base_radius: float = Field(gt=0, description="Base radius of the cam in mm")
    rise: float = Field(gt=0, description="Maximum rise of the cam follower in mm")
    offset: float = Field(default=0.0, description="Vertical offset of the follower in mm")
    cam_center: QPointFModel = Field(description="Center position of the cam")
    follower_position: QPointFModel = Field(description="Initial position of the follower")
    angular_velocity: float = Field(default=1.0, description="Angular velocity in rad/s")
    
    # Advanced cam parameters
    dwell_start: float = Field(default=0.0, ge=0, le=2*3.14159, description="Start angle of dwell in radians")
    dwell_end: float = Field(default=0.0, ge=0, le=2*3.14159, description="End angle of dwell in radians")
    motion_law: str = Field(default="harmonic", pattern="^(harmonic|cycloidal|polynomial)$", description="Motion law for cam profile")
    
    @validator("dwell_end")
    def validate_dwell_angles(cls, v, values):
        if "dwell_start" in values and v < values["dwell_start"]:
            raise ValueError("dwell_end must be greater than dwell_start")
        return v


class BeltMechanismModel(BaseModel):
    """Pydantic model for belt/pulley mechanism data."""
    
    type: Literal["belt"] = "belt"
    pulley_1_radius: float = Field(gt=0, description="Radius of first pulley in mm")
    pulley_2_radius: float = Field(gt=0, description="Radius of second pulley in mm")
    pulley_1_center: QPointFModel = Field(description="Center position of first pulley")
    pulley_2_center: QPointFModel = Field(description="Center position of second pulley")
    belt_tension: float = Field(default=10.0, gt=0, description="Belt tension in N")
    
    # Belt configuration
    belt_type: str = Field(default="flat", pattern="^(flat|v_belt|timing)$", description="Type of belt")
    belt_width: float = Field(default=10.0, gt=0, description="Belt width in mm")
    belt_thickness: float = Field(default=2.0, gt=0, description="Belt thickness in mm")
    
    # Advanced parameters
    slip_coefficient: float = Field(default=0.0, ge=0, le=1.0, description="Belt slip coefficient (0=no slip)")
    angular_velocity_1: float = Field(default=1.0, description="Angular velocity of first pulley in rad/s")
    
    @validator("pulley_2_center")
    def validate_pulley_separation(cls, v, values):
        if "pulley_1_center" in values:
            p1 = values["pulley_1_center"]
            distance = ((v.x - p1.x)**2 + (v.y - p1.y)**2)**0.5
            min_distance = values.get("pulley_1_radius", 0) + values.get("pulley_2_radius", 0)
            if distance < min_distance:
                raise ValueError("Pulleys are too close together")
        return v


class SpringMechanismModel(BaseModel):
    """Pydantic model for spring/damper mechanism data."""
    
    type: Literal["spring"] = "spring"
    spring_constant: float = Field(gt=0, description="Spring constant in N/m")
    damping_coefficient: float = Field(default=0.0, ge=0, description="Damping coefficient in N·s/m")
    rest_length: float = Field(gt=0, description="Rest length of spring in mm")
    
    # Attachment points
    attachment_1: QPointFModel = Field(description="First attachment point")
    attachment_2: QPointFModel = Field(description="Second attachment point")
    
    # Physical properties
    mass: float = Field(default=1.0, gt=0, description="Mass attached to spring in kg")
    max_compression: float = Field(default=0.8, gt=0, lt=1.0, description="Max compression ratio (0-1)")
    max_extension: float = Field(default=2.0, gt=1.0, description="Max extension ratio (>1)")
    
    # Spring geometry
    coil_diameter: float = Field(default=10.0, gt=0, description="Coil diameter in mm")
    wire_diameter: float = Field(default=1.0, gt=0, description="Wire diameter in mm")
    number_of_coils: int = Field(default=10, gt=0, description="Number of active coils")
    
    # Dynamic properties
    initial_velocity: float = Field(default=0.0, description="Initial velocity in m/s")
    external_force: float = Field(default=0.0, description="External force in N")
    
    @validator("max_compression")
    def validate_compression(cls, v):
        if v <= 0 or v >= 1:
            raise ValueError("max_compression must be between 0 and 1")
        return v


class MechanismLayerModel(BaseModel):
    """Unified model for mechanism layer data."""
    
    id: str = Field(description="Unique identifier for the mechanism")
    name: str = Field(description="Human-readable name")
    type: str = Field(description="Mechanism type identifier")
    
    # Generic parameters that apply to all mechanisms
    position: QPointFModel = Field(description="Base position of the mechanism")
    rotation: float = Field(default=0.0, description="Rotation angle in radians")
    scale: float = Field(default=1.0, gt=0, description="Scale factor")
    visible: bool = Field(default=True, description="Visibility flag")
    
    # Mechanism-specific data (union type based on mechanism type)
    params: dict = Field(default_factory=dict, description="Mechanism-specific parameters")
    key_points: dict[str, list[float]] = Field(default_factory=dict, description="Key points for parametric editing")
    
    # Simulation state
    simulation_time: float = Field(default=0.0, description="Current simulation time")
    simulation_speed: float = Field(default=1.0, gt=0, description="Simulation speed multiplier")
    
    # Visual properties
    color: str = Field(default="#0066CC", description="Primary color for rendering")
    line_width: float = Field(default=2.0, gt=0, description="Line width for rendering")
    opacity: float = Field(default=1.0, ge=0, le=1.0, description="Opacity for rendering")
    
    @validator("params")
    def validate_mechanism_params(cls, v, values):
        """Validate that params contain required fields based on mechanism type."""
        mech_type = values.get("type", "")
        
        if mech_type == "cam":
            required_fields = ["base_radius", "rise", "offset"]
        elif mech_type == "belt":
            required_fields = ["pulley_1_radius", "pulley_2_radius"]
        elif mech_type == "spring":
            required_fields = ["spring_constant", "rest_length"]
        else:
            return v  # Unknown type, skip validation
            
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Missing required parameter '{field}' for mechanism type '{mech_type}'")
        
        return v


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
    print(f"CharacterDataModel with alias: {char_model_alias.model_dump_json(indent=2)}")
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
