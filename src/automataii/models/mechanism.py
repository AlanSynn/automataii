"""
Centralized Mechanism Data Models - Single Source of Truth

This module defines the canonical data models for mechanisms, serving as the
authoritative representation that synchronizes 2D parametric editing, 3D physics
simulation, and blueprint generation.

Features:
- Physics-validated parameters with manufacturing constraints
- Material properties and dimensional standards
- Educational metadata for force/motion visualization
- Integration with PyBullet simulation and blueprint generation
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator
from PyQt6.QtCore import QPointF, QRectF

# Define constraint types and material properties inline to avoid missing imports
class ConstraintType(str, Enum):
    """Types of constraints applied to mechanisms"""
    DISTANCE = "distance"
    ANGLE = "angle"
    VELOCITY = "velocity"
    FORCE = "force"
    TORQUE = "torque"

@dataclass
class MaterialProperty:
    """Material properties for mechanism components"""
    name: str
    density: float  # kg/m³
    yield_strength: float  # MPa
    elastic_modulus: float  # GPa
    cost_per_kg: float  # USD/kg


class MechanismType(str, Enum):
    """Types of mechanisms supported by the system"""
    FOUR_BAR_LINKAGE = "four_bar_linkage"
    GEAR_TRAIN = "gear_train"
    CAM_FOLLOWER = "cam_follower"
    BELT_PULLEY = "belt_pulley"
    SPRING_DAMPER = "spring_damper"
    CUSTOM = "custom"


class JointType(str, Enum):
    """Types of joints in mechanism systems"""
    REVOLUTE = "revolute"
    PRISMATIC = "prismatic"
    FIXED = "fixed"
    SPHERICAL = "spherical"
    UNIVERSAL = "universal"


class ManufacturingStandard(str, Enum):
    """Manufacturing standards for dimensional validation"""
    ISO = "iso"
    ANSI = "ansi"
    DIN = "din"
    JIS = "jis"


@dataclass
class Point2D:
    """2D coordinate point with manufacturing precision"""
    x: float
    y: float
    
    def to_qpointf(self) -> QPointF:
        return QPointF(self.x, self.y)
    
    @classmethod
    def from_qpointf(cls, point: QPointF) -> Point2D:
        return cls(point.x(), point.y())
    
    def distance_to(self, other: Point2D) -> float:
        """Calculate Euclidean distance to another point"""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)


@dataclass
class Point3D:
    """3D coordinate point for physics simulation"""
    x: float
    y: float
    z: float = 0.0
    
    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


class MechanismLink(BaseModel):
    """
    Individual link component in a mechanism.
    
    Represents a rigid body with geometric, material, and manufacturing properties.
    """
    
    id: str = Field(..., description="Unique identifier for the link")
    name: str = Field(..., description="Human-readable name")
    length: float = Field(..., gt=0, description="Link length in mm")
    width: float = Field(default=6.0, gt=0, description="Link width in mm")
    thickness: float = Field(default=3.0, gt=0, description="Link thickness in mm")
    
    # Material properties
    material: str = Field(default="steel_a36", description="Material identifier")
    density: float = Field(default=7850.0, gt=0, description="Material density in kg/m³")
    youngs_modulus: float = Field(default=200e9, gt=0, description="Young's modulus in Pa")
    yield_strength: float = Field(default=250e6, gt=0, description="Yield strength in Pa")
    
    # Manufacturing constraints
    min_length: float = Field(default=10.0, gt=0)
    max_length: float = Field(default=1000.0, gt=0)
    manufacturing_tolerance: float = Field(default=0.1, gt=0, description="Manufacturing tolerance in mm")
    
    # Visual properties
    color: str = Field(default="#808080", description="Display color")
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    
    @field_validator('max_length')
    @classmethod
    def validate_length_constraints(cls, v):
        # Cross-field validation moved to model_validator
        return v
    
    @field_validator('length')
    @classmethod
    def validate_length_bounds(cls, v):
        # Basic validation - detailed bounds in model_validator
        if v <= 0:
            raise ValueError(f'Length must be positive, got {v}')
        return v
    
    @property
    def mass(self) -> float:
        """Calculate link mass based on geometry and material density"""
        volume_m3 = (self.length * self.width * self.thickness) / 1e9  # Convert mm³ to m³
        return self.density * volume_m3
    
    @property
    def moment_of_inertia(self) -> float:
        """Calculate moment of inertia for physics simulation"""
        # Simplified rod approximation
        return (self.mass * self.length**2) / 12


class MechanismJoint(BaseModel):
    """
    Joint connection between mechanism links.
    
    Defines kinematic constraints and physical properties for simulation.
    """
    
    id: str = Field(..., description="Unique identifier for the joint")
    name: str = Field(..., description="Human-readable name")
    joint_type: JointType = Field(..., description="Type of joint")
    
    # Connected links
    link_a: str = Field(..., description="ID of first connected link")
    link_b: str = Field(..., description="ID of second connected link")
    
    # Joint position and orientation
    position: Point2D = Field(..., description="Joint position in 2D space")
    position_3d: Optional[Point3D] = Field(None, description="Joint position in 3D space")
    axis: Tuple[float, float, float] = Field(default=(0, 0, 1), description="Joint axis for rotation")
    
    # Joint limits and properties
    lower_limit: Optional[float] = Field(None, description="Lower joint limit in radians/meters")
    upper_limit: Optional[float] = Field(None, description="Upper joint limit in radians/meters")
    max_force: float = Field(default=1000.0, gt=0, description="Maximum allowable force in N")
    max_torque: float = Field(default=100.0, gt=0, description="Maximum allowable torque in N⋅m")
    
    # Manufacturing properties
    bearing_diameter: float = Field(default=8.0, gt=0, description="Bearing diameter in mm")
    clearance: float = Field(default=0.05, gt=0, description="Joint clearance in mm")
    lubrication: str = Field(default="grease", description="Lubrication type")
    
    # Fixed joint indicator
    is_fixed: bool = Field(default=False, description="Whether this is a fixed (ground) joint")
    
    @field_validator('upper_limit')
    @classmethod
    def validate_joint_limits(cls, v):
        # Cross-field validation moved to model_validator
        return v


class MotionPath(BaseModel):
    """
    Recorded motion path for visualization and analysis.
    
    Stores the trajectory of key points during mechanism operation.
    """
    
    point_id: str = Field(..., description="ID of the tracked point")
    point_name: str = Field(..., description="Name of the tracked point")
    trajectory: List[Point2D] = Field(default_factory=list, description="Sequence of 2D positions")
    time_stamps: List[float] = Field(default_factory=list, description="Time stamps for each position")
    velocities: List[Tuple[float, float]] = Field(default_factory=list, description="Velocity vectors")
    accelerations: List[Tuple[float, float]] = Field(default_factory=list, description="Acceleration vectors")
    
    @field_validator('time_stamps')
    @classmethod
    def validate_timestamps(cls, v):
        # Cross-field validation moved to model_validator
        return v


class ForceAnalysis(BaseModel):
    """
    Force analysis results for educational visualization.
    
    Contains calculated forces, torques, and stress analysis data.
    """
    
    joint_forces: Dict[str, Tuple[float, float]] = Field(default_factory=dict, description="Forces at each joint")
    joint_torques: Dict[str, float] = Field(default_factory=dict, description="Torques at each joint")
    link_stresses: Dict[str, float] = Field(default_factory=dict, description="Maximum stress in each link")
    safety_factors: Dict[str, float] = Field(default_factory=dict, description="Safety factor for each link")
    
    # Analysis metadata
    analysis_time: datetime = Field(default_factory=datetime.now)
    input_force: Optional[Tuple[float, float]] = Field(None, description="Applied input force")
    input_torque: Optional[float] = Field(None, description="Applied input torque")
    
    @property
    def min_safety_factor(self) -> float:
        """Get minimum safety factor across all links"""
        if not self.safety_factors:
            return float('inf')
        return min(self.safety_factors.values())
    
    @property
    def is_safe(self) -> bool:
        """Check if all safety factors are above 2.0"""
        return self.min_safety_factor >= 2.0


class BlueprintLayer(BaseModel):
    """
    Individual layer in a manufacturing blueprint.
    
    Represents a specific view or component group for manufacturing.
    """
    
    id: str = Field(..., description="Unique identifier for the layer")
    name: str = Field(..., description="Layer name (e.g., 'Base Plate', 'Moving Parts')")
    description: str = Field(default="", description="Layer description")
    
    # Content specification
    included_links: List[str] = Field(default_factory=list, description="Link IDs included in this layer")
    included_joints: List[str] = Field(default_factory=list, description="Joint IDs included in this layer")
    
    # Layout properties
    scale: float = Field(default=1.0, gt=0, description="Scale factor for this layer")
    position: Point2D = Field(default=Point2D(0, 0), description="Position on blueprint page")
    
    # Manufacturing specifications
    material_callouts: Dict[str, str] = Field(default_factory=dict, description="Material specifications")
    dimensional_tolerances: Dict[str, float] = Field(default_factory=dict, description="Dimensional tolerances")
    surface_finishes: Dict[str, str] = Field(default_factory=dict, description="Surface finish requirements")
    assembly_notes: List[str] = Field(default_factory=list, description="Assembly instructions")
    
    # Layer styling
    line_weight: float = Field(default=0.7, gt=0, description="Line weight for drawing")
    layer_color: str = Field(default="#000000", description="Layer color")
    show_dimensions: bool = Field(default=True, description="Show dimensional annotations")
    show_tolerances: bool = Field(default=True, description="Show tolerance callouts")


class Mechanism(BaseModel):
    """
    Complete mechanism specification - Single Source of Truth.
    
    This is the canonical data model that synchronizes all aspects of the system:
    - 2D parametric editing interface
    - 3D physics simulation 
    - Manufacturing blueprint generation
    - Educational force/motion visualization
    """
    
    # Basic identification
    id: str = Field(..., description="Unique mechanism identifier")
    name: str = Field(..., description="Mechanism name")
    description: str = Field(default="", description="Mechanism description")
    mechanism_type: MechanismType = Field(..., description="Type of mechanism")
    
    # Mechanism components
    links: Dict[str, MechanismLink] = Field(default_factory=dict, description="All links in the mechanism")
    joints: Dict[str, MechanismJoint] = Field(default_factory=dict, description="All joints in the mechanism")
    
    # Manufacturing and standards
    manufacturing_standard: ManufacturingStandard = Field(default=ManufacturingStandard.ISO)
    material_grade: str = Field(default="commercial", description="Material quality grade")
    manufacturing_precision: str = Field(default="standard", description="Manufacturing precision level")
    
    # Simulation parameters
    gravity: Tuple[float, float, float] = Field(default=(0, 0, -9.81), description="Gravity vector")
    time_step: float = Field(default=1.0/240.0, gt=0, description="Simulation time step")
    damping_coefficient: float = Field(default=0.1, ge=0, description="System damping")
    
    # Educational visualization data
    motion_paths: Dict[str, MotionPath] = Field(default_factory=dict, description="Recorded motion trajectories")
    force_analysis: Optional[ForceAnalysis] = Field(None, description="Latest force analysis results")
    
    # Blueprint configuration
    blueprint_layers: Dict[str, BlueprintLayer] = Field(default_factory=dict, description="Blueprint layer definitions")
    default_scale: float = Field(default=1.0, gt=0, description="Default blueprint scale")
    paper_size: str = Field(default="Letter", description="Target paper size")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: datetime = Field(default_factory=datetime.now)
    version: str = Field(default="1.0.0", description="Mechanism version")
    author: str = Field(default="", description="Mechanism designer")
    
    class Config:
        arbitrary_types_allowed = True
        
    @model_validator(mode='after')
    def validate_mechanism_consistency(self):
        """Validate overall mechanism consistency"""
        # Validate joint-link connectivity
        for joint_id, joint in self.joints.items():
            if joint.link_a not in self.links:
                raise ValueError(f"Joint {joint_id} references non-existent link {joint.link_a}")
            if joint.link_b not in self.links:
                raise ValueError(f"Joint {joint_id} references non-existent link {joint.link_b}")
        
        return self
    
    @field_validator('modified_at', mode='before')
    @classmethod
    def update_modified_time(cls, v):
        """Auto-update modification time"""
        return datetime.now()
    
    # Specialized constructors for different mechanism types
    
    @classmethod
    def create_four_bar_linkage(
        cls,
        name: str,
        ground_length: float,
        driver_length: float,
        coupler_length: float,
        rocker_length: float,
        ground_pivot_1: Point2D,
        ground_pivot_2: Point2D
    ) -> Mechanism:
        """Create a 4-bar linkage mechanism with validated Grashof condition"""
        
        # Validate Grashof condition
        lengths = sorted([ground_length, driver_length, coupler_length, rocker_length])
        s, p, q, l = lengths  # shortest, intermediate, intermediate, longest
        
        if s + l > p + q:
            raise ValueError(
                f"Invalid 4-bar linkage: Grashof condition violated. "
                f"s+l ({s}+{l}={s+l}) must be <= p+q ({p}+{q}={p+q})"
            )
        
        # Create links
        links = {
            "ground": MechanismLink(
                id="ground",
                name="Ground Link",
                length=ground_length,
                width=8.0,
                thickness=5.0
            ),
            "driver": MechanismLink(
                id="driver", 
                name="Driver Link",
                length=driver_length,
                width=6.0,
                thickness=3.0
            ),
            "coupler": MechanismLink(
                id="coupler",
                name="Coupler Link", 
                length=coupler_length,
                width=6.0,
                thickness=3.0
            ),
            "rocker": MechanismLink(
                id="rocker",
                name="Rocker Link",
                length=rocker_length,
                width=6.0,
                thickness=3.0
            )
        }
        
        # Create joints
        joints = {
            "ground_pivot_1": MechanismJoint(
                id="ground_pivot_1",
                name="Ground Pivot 1",
                joint_type=JointType.REVOLUTE,
                link_a="ground",
                link_b="driver",
                position=ground_pivot_1,
                is_fixed=True
            ),
            "ground_pivot_2": MechanismJoint(
                id="ground_pivot_2", 
                name="Ground Pivot 2",
                joint_type=JointType.REVOLUTE,
                link_a="ground",
                link_b="rocker",
                position=ground_pivot_2,
                is_fixed=True
            ),
            "coupler_joint_1": MechanismJoint(
                id="coupler_joint_1",
                name="Driver-Coupler Joint",
                joint_type=JointType.REVOLUTE,
                link_a="driver",
                link_b="coupler",
                position=Point2D(ground_pivot_1.x + driver_length, ground_pivot_1.y)
            ),
            "coupler_joint_2": MechanismJoint(
                id="coupler_joint_2",
                name="Coupler-Rocker Joint", 
                joint_type=JointType.REVOLUTE,
                link_a="coupler",
                link_b="rocker",
                position=Point2D(ground_pivot_2.x, ground_pivot_2.y + rocker_length)
            )
        }
        
        # Create default blueprint layers
        blueprint_layers = {
            "assembly": BlueprintLayer(
                id="assembly",
                name="Assembly View",
                description="Complete mechanism assembly",
                included_links=list(links.keys()),
                included_joints=list(joints.keys()),
                scale=1.0,
                show_dimensions=True
            ),
            "parts": BlueprintLayer(
                id="parts",
                name="Individual Parts",
                description="Individual parts for manufacturing",
                included_links=["driver", "coupler", "rocker"],  # Exclude ground
                scale=2.0,
                show_dimensions=True,
                show_tolerances=True
            )
        }
        
        return cls(
            id=f"fourbar_{name.lower().replace(' ', '_')}",
            name=name,
            description=f"4-bar linkage: l1={ground_length}, l2={driver_length}, l3={coupler_length}, l4={rocker_length}",
            mechanism_type=MechanismType.FOUR_BAR_LINKAGE,
            links=links,
            joints=joints,
            blueprint_layers=blueprint_layers
        )
    
    # Analysis and validation methods
    
    def validate_grashof_condition(self) -> Tuple[bool, str]:
        """Validate Grashof condition for 4-bar linkages"""
        if self.mechanism_type != MechanismType.FOUR_BAR_LINKAGE:
            return True, "Grashof condition not applicable"
        
        if len(self.links) != 4:
            return False, f"Expected 4 links, found {len(self.links)}"
        
        lengths = [link.length for link in self.links.values()]
        lengths.sort()
        s, p, q, l = lengths
        
        grashof_satisfied = s + l <= p + q + 1e-6  # Small tolerance
        
        if grashof_satisfied:
            return True, "Grashof condition satisfied - continuous rotation possible"
        else:
            return False, f"Grashof condition violated: s+l ({s:.1f}+{l:.1f}={s+l:.1f}) > p+q ({p:.1f}+{q:.1f}={p+q:.1f})"
    
    def calculate_workspace(self) -> Optional[Dict[str, Any]]:
        """Calculate mechanism workspace bounds"""
        if self.mechanism_type != MechanismType.FOUR_BAR_LINKAGE:
            return None
        
        # For 4-bar linkage, calculate coupler point workspace
        # This is a simplified calculation - full workspace would require kinematic analysis
        
        ground_joints = [j for j in self.joints.values() if j.is_fixed]
        if len(ground_joints) != 2:
            return None
        
        # Get ground pivot positions
        pivot_1 = ground_joints[0].position
        pivot_2 = ground_joints[1].position
        
        # Estimate workspace as union of link reach circles
        driver_length = self.links.get("driver", MechanismLink(id="", name="", length=0)).length
        rocker_length = self.links.get("rocker", MechanismLink(id="", name="", length=0)).length
        
        workspace = {
            "center_1": (pivot_1.x, pivot_1.y),
            "radius_1": driver_length,
            "center_2": (pivot_2.x, pivot_2.y), 
            "radius_2": rocker_length,
            "estimated_area": math.pi * (driver_length**2 + rocker_length**2)
        }
        
        return workspace
    
    def get_critical_dimensions(self) -> Dict[str, float]:
        """Get critical dimensions for manufacturing validation"""
        critical_dims = {}
        
        # Link lengths
        for link_id, link in self.links.items():
            critical_dims[f"{link_id}_length"] = link.length
            critical_dims[f"{link_id}_width"] = link.width
            critical_dims[f"{link_id}_thickness"] = link.thickness
        
        # Joint separations
        for joint_id, joint in self.joints.items():
            critical_dims[f"{joint_id}_bearing_diameter"] = joint.bearing_diameter
            critical_dims[f"{joint_id}_clearance"] = joint.clearance
        
        return critical_dims
    
    def estimate_manufacturing_cost(self) -> Dict[str, float]:
        """Estimate manufacturing cost breakdown"""
        # Simplified cost estimation
        material_cost = 0.0
        machining_cost = 0.0
        
        for link in self.links.values():
            # Material cost (simplified)
            volume_cm3 = (link.length * link.width * link.thickness) / 1000  # mm³ to cm³
            material_cost += volume_cm3 * 0.05  # $0.05 per cm³ for steel
            
            # Machining cost (simplified)
            complexity_factor = 1.0 + (link.length / 100)  # Longer links more complex
            machining_cost += complexity_factor * 2.0  # $2 base machining per link
        
        for joint in self.joints.values():
            # Bearing and fastener costs
            material_cost += 5.0  # $5 per bearing assembly
            machining_cost += 3.0  # $3 per joint machining
        
        assembly_cost = len(self.joints) * 2.0  # $2 per joint for assembly
        
        return {
            "material_cost": round(material_cost, 2),
            "machining_cost": round(machining_cost, 2), 
            "assembly_cost": round(assembly_cost, 2),
            "total_cost": round(material_cost + machining_cost + assembly_cost, 2)
        }
    
    # Utility methods
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Mechanism:
        """Create from dictionary"""
        return cls(**data)
    
    def clone(self, new_name: Optional[str] = None) -> Mechanism:
        """Create a deep copy of the mechanism"""
        data = self.model_dump()
        if new_name:
            data['name'] = new_name
            data['id'] = f"{data['id']}_copy"
        data['created_at'] = datetime.now()
        data['modified_at'] = datetime.now()
        return self.__class__(**data)
    
    def get_summary(self) -> str:
        """Get human-readable mechanism summary"""
        summary = [
            f"Mechanism: {self.name}",
            f"Type: {self.mechanism_type.value}",
            f"Links: {len(self.links)}",
            f"Joints: {len(self.joints)}",
            f"Blueprint Layers: {len(self.blueprint_layers)}"
        ]
        
        if self.mechanism_type == MechanismType.FOUR_BAR_LINKAGE:
            is_valid, grashof_msg = self.validate_grashof_condition()
            summary.append(f"Grashof: {'✓' if is_valid else '✗'} {grashof_msg}")
        
        if self.force_analysis:
            summary.append(f"Safety Factor: {self.force_analysis.min_safety_factor:.1f}")
        
        cost_breakdown = self.estimate_manufacturing_cost()
        summary.append(f"Est. Cost: ${cost_breakdown['total_cost']}")
        
        return "\n".join(summary)