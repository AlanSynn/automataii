"""
Mechanical Character Data Models - Disney Research Style

Comprehensive data models for computational mechanical character design.
Enables creation of complete mechanical systems from user-defined motion goals,
including automatic base generation, actuator sizing, and manufacturing specs.

Architecture: Disney Research Computational Character Design
- Goal-based design from user anchor positions
- Complete system synthesis with base and actuators
- Manufacturing-ready specifications and assembly
- Multi-mechanism coordination and optimization
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass

from pydantic import BaseModel, Field, validator

from .mechanism import Point2D, Point3D, Mechanism


class MotionGoalType(str, Enum):
    """Types of motion goals that can be specified by users"""
    PATH_TRACE = "path_trace"           # End-effector follows specific path
    POINT_TO_POINT = "point_to_point"   # Move between discrete positions
    OSCILLATION = "oscillation"         # Rhythmic back-and-forth motion
    ROTATION = "rotation"               # Continuous rotational motion
    COMPLEX_MOTION = "complex_motion"   # Multi-component coordinated motion


class ActuatorType(str, Enum):
    """Types of actuators available for character drive"""
    SERVO_MOTOR = "servo_motor"         # Precise position control
    STEPPER_MOTOR = "stepper_motor"     # High torque, discrete positioning
    DC_MOTOR = "dc_motor"               # Continuous rotation, speed control
    PNEUMATIC = "pneumatic"             # High force, binary positions
    LINEAR_ACTUATOR = "linear_actuator" # Direct linear motion
    CUSTOM = "custom"                   # User-specified requirements


class ManufacturingProcess(str, Enum):
    """Manufacturing processes available for fabrication"""
    LASER_CUTTING = "laser_cutting"     # 2D sheet material cutting
    CNC_MILLING = "cnc_milling"         # Precise material removal
    THREE_D_PRINTING = "3d_printing"    # Additive manufacturing
    INJECTION_MOLDING = "injection_molding" # High volume plastic parts
    SHEET_METAL = "sheet_metal"         # Bending and forming operations
    ASSEMBLY = "assembly"               # Hardware and fastener installation


@dataclass
class MotionGoal:
    """
    User-defined motion goal for mechanical character.
    
    Represents desired motion behavior that the system will
    synthesize mechanisms to achieve.
    """
    goal_id: str
    goal_type: MotionGoalType
    target_points: List[Point2D]        # Key positions in motion
    timing_constraints: Optional[Dict[str, float]] = None  # Speed, acceleration limits
    force_requirements: Optional[Dict[str, float]] = None  # Load, torque requirements
    priority: float = 1.0               # Relative importance (0-1)
    
    # Motion characteristics
    is_cyclic: bool = True              # Does motion repeat cyclically?
    cycle_duration: float = 1.0         # Duration of one complete cycle (seconds)
    smoothness_requirement: float = 0.8 # Required motion smoothness (0-1)
    
    # Constraints
    workspace_bounds: Optional[Tuple[Point2D, Point2D]] = None  # (min, max) workspace
    collision_avoidance: List[Point2D] = None  # Points to avoid
    
    def __post_init__(self):
        if self.collision_avoidance is None:
            self.collision_avoidance = []


@dataclass
class ActuatorSpec:
    """
    Specification for actuator required by mechanical character.
    
    Defines requirements and placement for motors/actuators
    that will drive the mechanical system.
    """
    actuator_id: str
    actuator_type: ActuatorType
    position: Point3D                   # Mounting position in character
    orientation: Tuple[float, float, float] = (0, 0, 0)  # Euler angles (deg)
    
    # Performance requirements
    max_torque: float = 0.0            # N⋅m
    max_speed: float = 0.0             # RPM or linear units/sec
    max_power: float = 0.0             # Watts
    precision: float = 0.01            # Position accuracy requirement
    
    # Physical specifications
    mounting_interface: str = "standard" # Mounting method
    electrical_requirements: Dict[str, Any] = None  # Voltage, current, etc.
    mass: float = 0.0                  # kg
    envelope: Tuple[float, float, float] = (0, 0, 0)  # (length, width, height) in mm
    
    # Connection specifications
    driven_mechanism_id: str = ""      # Which mechanism this actuator drives
    drive_connection_type: str = "direct" # direct, geared, belt, etc.
    gear_ratio: float = 1.0            # If geared connection
    
    def __post_init__(self):
        if self.electrical_requirements is None:
            self.electrical_requirements = {}


class StructuralBase(BaseModel):
    """
    Structural base/chassis for mechanical character.
    
    Automatically generated to connect all mechanisms and
    provide mounting for actuators and fixed pivots.
    """
    
    base_id: str = Field(..., description="Unique base identifier")
    base_type: str = Field(default="optimized", description="Generation algorithm used")
    
    # Geometric definition
    outline_points: List[Point2D] = Field(default_factory=list, description="Base perimeter")
    thickness: float = Field(default=6.0, description="Base thickness in mm")
    material: str = Field(default="aluminum", description="Base material")
    
    # Mounting points
    pivot_mounts: List[Dict[str, Any]] = Field(default_factory=list, description="Fixed pivot mounting points")
    actuator_mounts: List[Dict[str, Any]] = Field(default_factory=list, description="Actuator mounting points")
    
    # Structural properties
    mass: float = Field(default=0.0, description="Estimated mass in kg")
    center_of_mass: Point3D = Field(default=Point3D(0, 0, 0), description="Center of mass location")
    structural_efficiency: float = Field(default=0.8, description="Material efficiency (0-1)")
    
    # Manufacturing specifications
    manufacturing_process: ManufacturingProcess = Field(default=ManufacturingProcess.LASER_CUTTING)
    fabrication_notes: List[str] = Field(default_factory=list, description="Special fabrication requirements")
    
    @property
    def base_area(self) -> float:
        """Calculate base area from outline points"""
        if len(self.outline_points) < 3:
            return 0.0
        
        # Shoelace formula for polygon area
        area = 0.0
        n = len(self.outline_points)
        for i in range(n):
            j = (i + 1) % n
            area += self.outline_points[i].x * self.outline_points[j].y
            area -= self.outline_points[j].x * self.outline_points[i].y
        
        return abs(area) / 2.0
    
    @property
    def perimeter_length(self) -> float:
        """Calculate base perimeter length"""
        if len(self.outline_points) < 2:
            return 0.0
        
        length = 0.0
        n = len(self.outline_points)
        for i in range(n):
            j = (i + 1) % n
            dx = self.outline_points[j].x - self.outline_points[i].x
            dy = self.outline_points[j].y - self.outline_points[i].y
            length += math.sqrt(dx*dx + dy*dy)
        
        return length


@dataclass
class ManufacturingSpecs:
    """
    Complete manufacturing specifications for mechanical character.
    
    Includes bill of materials, fabrication files, and assembly instructions
    for complete character production.
    """
    character_id: str
    
    # Bill of Materials
    standard_components: List[Dict[str, Any]]    # Bearings, fasteners, etc.
    custom_fabricated: List[Dict[str, Any]]      # Parts to be manufactured
    actuators_and_electronics: List[Dict[str, Any]]  # Motors, controllers, etc.
    
    # Fabrication files
    fabrication_files: Dict[str, str]           # Process -> file path mapping
    assembly_drawings: List[str]                # Drawing file paths
    
    # Cost and time estimation
    estimated_cost: float = 0.0                 # Total cost in USD
    estimated_fabrication_time: float = 0.0     # Hours
    estimated_assembly_time: float = 0.0        # Hours
    
    # Quality specifications
    tolerance_requirements: Dict[str, float] = None
    surface_finish_requirements: Dict[str, str] = None
    testing_procedures: List[str] = None
    
    def __post_init__(self):
        if self.tolerance_requirements is None:
            self.tolerance_requirements = {}
        if self.surface_finish_requirements is None:
            self.surface_finish_requirements = {}
        if self.testing_procedures is None:
            self.testing_procedures = []


class PerformanceAnalysis(BaseModel):
    """
    Performance analysis of complete mechanical character.
    
    Evaluates efficiency, force transmission, and operational
    characteristics of the synthesized system.
    """
    
    character_id: str = Field(..., description="Character being analyzed")
    analysis_timestamp: datetime = Field(default_factory=datetime.now)
    
    # Motion performance
    motion_accuracy: float = Field(default=0.0, description="How well motion matches goals (0-1)")
    motion_smoothness: float = Field(default=0.0, description="Motion smoothness metric (0-1)")
    cycle_efficiency: float = Field(default=0.0, description="Energy efficiency per cycle (0-1)")
    
    # Force analysis
    max_actuator_torque: float = Field(default=0.0, description="Peak torque requirement (N⋅m)")
    average_power_consumption: float = Field(default=0.0, description="Average power (Watts)")
    force_transmission_quality: float = Field(default=0.0, description="Force transmission efficiency (0-1)")
    
    # Structural analysis
    base_structural_adequacy: float = Field(default=0.0, description="Base strength adequacy (0-1)")
    mechanism_stress_factors: Dict[str, float] = Field(default_factory=dict, description="Stress per mechanism")
    overall_safety_factor: float = Field(default=0.0, description="Minimum safety factor")
    
    # Manufacturing metrics
    manufacturability_score: float = Field(default=0.0, description="Ease of manufacturing (0-1)")
    assembly_complexity: float = Field(default=0.0, description="Assembly difficulty (0-1)")
    material_efficiency: float = Field(default=0.0, description="Material usage efficiency (0-1)")
    
    # Educational metrics
    demonstrated_principles: List[str] = Field(default_factory=list, description="Physics principles shown")
    learning_value: float = Field(default=0.0, description="Educational value score (0-1)")
    
    @property
    def overall_performance_score(self) -> float:
        """Calculate overall performance score"""
        weights = {
            'motion_accuracy': 0.25,
            'cycle_efficiency': 0.20,
            'force_transmission_quality': 0.20,
            'manufacturability_score': 0.15,
            'overall_safety_factor': 0.10,
            'learning_value': 0.10
        }
        
        # Normalize safety factor to 0-1 scale (assume 2.0 is ideal)
        normalized_safety = min(1.0, self.overall_safety_factor / 2.0)
        
        score = (
            weights['motion_accuracy'] * self.motion_accuracy +
            weights['cycle_efficiency'] * self.cycle_efficiency +
            weights['force_transmission_quality'] * self.force_transmission_quality +
            weights['manufacturability_score'] * self.manufacturability_score +
            weights['overall_safety_factor'] * normalized_safety +
            weights['learning_value'] * self.learning_value
        )
        
        return min(1.0, max(0.0, score))


class MechanicalCharacterModel(BaseModel):
    """
    Complete mechanical character specification.
    
    Disney Research-style computational mechanical character that includes
    complete system definition from user goals to manufacturing specifications.
    
    This is the central data model that orchestrates the entire character
    design system, from user intent to fabrication-ready specifications.
    """
    
    # Identity and metadata
    character_id: str = Field(..., description="Unique character identifier")
    character_name: str = Field(default="Mechanical Character", description="User-friendly name")
    creation_timestamp: datetime = Field(default_factory=datetime.now)
    last_modified: datetime = Field(default_factory=datetime.now)
    
    # Design goals (user input)
    design_goals: List[MotionGoal] = Field(default_factory=list, description="User-defined motion goals")
    design_constraints: Dict[str, Any] = Field(default_factory=dict, description="Global design constraints")
    
    # Synthesized mechanisms
    synthesized_mechanisms: List[Mechanism] = Field(default_factory=list, description="Generated mechanisms")
    mechanism_coordination: Dict[str, Any] = Field(default_factory=dict, description="Inter-mechanism coordination")
    
    # Structural foundation
    structural_base: Optional[StructuralBase] = Field(default=None, description="Generated base/chassis")
    
    # Actuation system
    actuator_specs: List[ActuatorSpec] = Field(default_factory=list, description="Required actuators")
    control_system: Dict[str, Any] = Field(default_factory=dict, description="Control system specifications")
    
    # Manufacturing and production
    manufacturing_specs: Optional[ManufacturingSpecs] = Field(default=None, description="Manufacturing specifications")
    
    # Performance and analysis
    performance_analysis: Optional[PerformanceAnalysis] = Field(default=None, description="Performance analysis")
    
    # Design status
    synthesis_status: str = Field(default="draft", description="Design completion status")
    validation_status: str = Field(default="not_validated", description="Validation status")
    
    class Config:
        arbitrary_types_allowed = True
    
    @validator('last_modified', pre=True, always=True)
    def set_last_modified(cls, v):
        return datetime.now()
    
    @property
    def total_mechanisms(self) -> int:
        """Get total number of mechanisms in character"""
        return len(self.synthesized_mechanisms)
    
    @property
    def total_actuators(self) -> int:
        """Get total number of actuators required"""
        return len(self.actuator_specs)
    
    @property
    def design_complexity_score(self) -> float:
        """Calculate design complexity score (0-1)"""
        complexity_factors = {
            'mechanisms': min(1.0, len(self.synthesized_mechanisms) / 10.0),
            'goals': min(1.0, len(self.design_goals) / 5.0),
            'actuators': min(1.0, len(self.actuator_specs) / 3.0),
            'coordination': min(1.0, len(self.mechanism_coordination) / 5.0)
        }
        
        return sum(complexity_factors.values()) / len(complexity_factors)
    
    @property
    def is_manufacturable(self) -> bool:
        """Check if character has complete manufacturing specifications"""
        return (
            self.manufacturing_specs is not None and
            self.structural_base is not None and
            len(self.actuator_specs) > 0 and
            self.validation_status == "validated"
        )
    
    def add_motion_goal(self, goal: MotionGoal):
        """Add motion goal and update modification timestamp"""
        self.design_goals.append(goal)
        self.last_modified = datetime.now()
        self.synthesis_status = "needs_synthesis"
    
    def add_synthesized_mechanism(self, mechanism: Mechanism):
        """Add synthesized mechanism to character"""
        self.synthesized_mechanisms.append(mechanism)
        self.last_modified = datetime.now()
    
    def get_mechanisms_by_type(self, mechanism_type: str) -> List[Mechanism]:
        """Get all mechanisms of specific type"""
        return [m for m in self.synthesized_mechanisms if m.mechanism_type.value == mechanism_type]
    
    def get_actuator_by_id(self, actuator_id: str) -> Optional[ActuatorSpec]:
        """Get actuator specification by ID"""
        for actuator in self.actuator_specs:
            if actuator.actuator_id == actuator_id:
                return actuator
        return None
    
    def calculate_total_power_requirement(self) -> float:
        """Calculate total power requirement for all actuators"""
        return sum(actuator.max_power for actuator in self.actuator_specs)
    
    def calculate_estimated_mass(self) -> float:
        """Calculate estimated total mass of character"""
        base_mass = self.structural_base.mass if self.structural_base else 0.0
        actuator_mass = sum(actuator.mass for actuator in self.actuator_specs)
        mechanism_mass = sum(getattr(m, 'estimated_mass', 0.0) for m in self.synthesized_mechanisms)
        
        return base_mass + actuator_mass + mechanism_mass
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary for logging/debugging"""
        return {
            'character_id': self.character_id,
            'character_name': self.character_name,
            'design_goals_count': len(self.design_goals),
            'mechanisms_count': len(self.synthesized_mechanisms),
            'actuators_count': len(self.actuator_specs),
            'has_base': self.structural_base is not None,
            'has_manufacturing_specs': self.manufacturing_specs is not None,
            'synthesis_status': self.synthesis_status,
            'validation_status': self.validation_status,
            'complexity_score': self.design_complexity_score,
            'is_manufacturable': self.is_manufacturable,
            'estimated_mass': self.calculate_estimated_mass(),
            'total_power': self.calculate_total_power_requirement()
        }