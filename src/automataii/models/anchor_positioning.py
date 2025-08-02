"""
Anchor Positioning Data Models

Data models and event structures for intelligent anchor positioning system.
Supports event-driven communication between UI components and validation services
for operation-aware mechanism design.

Architecture: Gemini's Strategic Event-Driven Design
- Structured event data for anchor position validation
- Comprehensive operational validation results
- Educational feedback integration
- Constraint violation reporting with spatial data
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from pydantic import BaseModel, Field

from .mechanism import Point2D


class AnchorConstraintType(str, Enum):
    """Types of anchor positioning constraints"""
    GEOMETRIC_REACHABILITY = "geometric_reachability"
    JOINT_LIMITS = "joint_limits"
    COLLISION_DETECTION = "collision_detection"
    GRASHOF_CONDITION = "grashof_condition"
    MANUFACTURING_FEASIBILITY = "manufacturing_feasibility"
    FORCE_LIMITS = "force_limits"
    STABILITY = "stability"


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues"""
    INFO = "info"          # Informational - design guidance
    WARNING = "warning"    # Should be addressed but not blocking
    ERROR = "error"        # Must be fixed for proper operation
    CRITICAL = "critical"  # Severe issue requiring immediate attention


@dataclass
class ConstraintViolation:
    """
    Constraint violation data for anchor positioning.
    
    Provides detailed information about why a proposed anchor
    position is invalid or suboptimal.
    """
    constraint_id: str
    joint_id: str
    constraint_type: str
    violation_type: str
    
    # Spatial information for visualization
    position: Point2D
    measured_value: float
    limit_value: float
    
    # Metadata
    severity: ValidationSeverity = ValidationSeverity.ERROR
    message: str = ""
    suggested_fix: str = ""
    
    # Educational context
    principle_violated: str = ""  # Physics/engineering principle
    learning_insight: str = ""    # Educational explanation


@dataclass
class MotionPathData:
    """
    Motion path data for operational range visualization.
    
    Contains trajectory information for mechanism components
    during their operational cycle.
    """
    component_id: str
    component_name: str
    path_points: List[Point2D]
    
    # Velocity and acceleration for advanced visualization
    velocity_vectors: List[Tuple[float, float]] = None
    acceleration_vectors: List[Tuple[float, float]] = None
    
    # Path characteristics
    is_continuous: bool = True
    has_reversals: bool = False
    max_velocity: float = 0.0
    max_acceleration: float = 0.0
    
    # Visualization properties
    path_color: str = "#0066CC"
    line_width: float = 2.0
    show_direction_arrows: bool = True


class OperationalValidationResult(BaseModel):
    """
    Comprehensive result of operational feasibility validation.
    
    Contains all data needed for UI feedback, visualization,
    and educational insights about anchor position changes.
    """
    
    mechanism_id: str = Field(..., description="ID of validated mechanism")
    anchor_id: str = Field(..., description="ID of anchor being modified")
    validation_time: datetime = Field(default_factory=datetime.now)
    computation_time: float = Field(default=0.0, description="Validation time in seconds")
    
    # Core validation results
    is_feasible: bool = Field(default=True, description="Overall operational feasibility")
    confidence_score: float = Field(default=1.0, description="Confidence in validation (0-1)")
    
    # Constraint violations and warnings
    constraint_violations: List[ConstraintViolation] = Field(
        default_factory=list, description="Constraint violations found"
    )
    
    # Operational analysis results
    operational_range: List[Point2D] = Field(
        default_factory=list, description="Reachable positions during operation"
    )
    motion_paths: List[MotionPathData] = Field(
        default_factory=list, description="Motion paths of mechanism components"
    )
    
    # Performance metrics
    operational_efficiency: float = Field(default=1.0, description="Efficiency rating (0-1)")
    mechanical_advantage_range: Tuple[float, float] = Field(
        default=(1.0, 1.0), description="Min/max mechanical advantage"
    )
    force_transmission_quality: float = Field(
        default=1.0, description="Force transmission quality (0-1)"
    )
    
    # Educational and optimization data
    educational_insights: List[str] = Field(
        default_factory=list, description="Learning insights for users"
    )
    optimization_suggestions: List[str] = Field(
        default_factory=list, description="Design improvement suggestions"
    )
    physics_principles: List[str] = Field(
        default_factory=list, description="Physics principles demonstrated"
    )
    
    class Config:
        arbitrary_types_allowed = True
    
    @property
    def has_errors(self) -> bool:
        """Check if validation has blocking errors"""
        return any(v.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] 
                  for v in self.constraint_violations)
    
    @property
    def has_warnings(self) -> bool:
        """Check if validation has non-blocking warnings"""
        return any(v.severity == ValidationSeverity.WARNING for v in self.constraint_violations)
    
    @property
    def operational_range_area(self) -> float:
        """Calculate area of operational range for optimization metrics"""
        if len(self.operational_range) < 3:
            return 0.0
        
        # Simple polygon area calculation using shoelace formula
        area = 0.0
        n = len(self.operational_range)
        
        for i in range(n):
            j = (i + 1) % n
            area += self.operational_range[i].x * self.operational_range[j].y
            area -= self.operational_range[j].x * self.operational_range[i].y
        
        return abs(area) / 2.0
    
    @property
    def operational_range_center(self) -> Point2D:
        """Calculate center point of operational range"""
        if not self.operational_range:
            return Point2D(0, 0)
        
        avg_x = sum(p.x for p in self.operational_range) / len(self.operational_range)
        avg_y = sum(p.y for p in self.operational_range) / len(self.operational_range)
        
        return Point2D(avg_x, avg_y)
    
    def add_violation(self, constraint_type: AnchorConstraintType, message: str,
                     position: Point2D = None, severity: ValidationSeverity = ValidationSeverity.ERROR):
        """Add a constraint violation with proper typing"""
        violation = ConstraintViolation(
            constraint_id=f"{constraint_type.value}_{len(self.constraint_violations)}",
            joint_id=self.anchor_id,
            constraint_type=constraint_type.value,
            violation_type=message,
            position=position or Point2D(0, 0),
            measured_value=0.0,
            limit_value=0.0,
            severity=severity,
            message=message
        )
        self.constraint_violations.append(violation)
    
    def add_educational_insight(self, insight: str, principle: str = ""):
        """Add educational insight with optional physics principle"""
        if insight not in self.educational_insights:
            self.educational_insights.append(insight)
        
        if principle and principle not in self.physics_principles:
            self.physics_principles.append(principle)
    
    def get_violations_by_severity(self, severity: ValidationSeverity) -> List[ConstraintViolation]:
        """Get violations filtered by severity level"""
        return [v for v in self.constraint_violations if v.severity == severity]
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary for logging/debugging"""
        return {
            'mechanism_id': self.mechanism_id,
            'anchor_id': self.anchor_id,
            'is_feasible': self.is_feasible,
            'confidence_score': self.confidence_score,
            'computation_time': self.computation_time,
            'violations_count': len(self.constraint_violations),
            'errors_count': len(self.get_violations_by_severity(ValidationSeverity.ERROR)),
            'warnings_count': len(self.get_violations_by_severity(ValidationSeverity.WARNING)),
            'operational_range_size': len(self.operational_range),
            'operational_range_area': self.operational_range_area,
            'operational_efficiency': self.operational_efficiency
        }


# Event Data Models for EventBus Communication

@dataclass
class AnchorPositionChangeRequested:
    """Event data for anchor position change request from UI"""
    mechanism_id: str
    anchor_id: str
    proposed_position: Tuple[float, float]
    requester: str = "interactive_handle"
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class AnchorValidationCompleted:
    """Event data for completed anchor position validation"""
    mechanism_id: str
    anchor_id: str
    is_feasible: bool
    operational_range: List[Point2D]
    constraint_violations: List[ConstraintViolation]
    motion_paths: List[MotionPathData]
    updated_mechanism: Dict[str, Any]
    educational_insights: List[str]
    requester: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class OperationalRangeUpdateRequested:
    """Event data for requesting operational range update"""
    mechanism_id: str
    include_motion_paths: bool = True
    include_force_analysis: bool = False
    resolution: int = 72  # Points around full cycle


@dataclass
class ConstraintViolationDetected:
    """Event data for constraint violation detection"""
    mechanism_id: str
    anchor_id: str
    violation: ConstraintViolation
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


# UI Component Data Models

@dataclass
class AnchorVisualizationSettings:
    """Settings for anchor positioning visualization"""
    show_operational_range: bool = True
    show_motion_paths: bool = False
    show_constraint_violations: bool = True
    show_optimization_suggestions: bool = False
    
    # Visualization parameters
    operational_range_opacity: float = 0.3
    operational_range_color: str = "#4A90E2"
    constraint_violation_color: str = "#FF4444"
    motion_path_color: str = "#00AA00"
    
    # Animation settings
    animate_motion_paths: bool = False
    animation_speed: float = 1.0
    path_trail_length: int = 20


@dataclass
class AnchorHandleState:
    """State data for intelligent anchor handles"""
    mechanism_id: str
    anchor_id: str
    is_operationally_valid: bool
    constraint_violations: List[ConstraintViolation]
    operational_range: List[Point2D]
    educational_tooltip: str = ""
    
    # Visual feedback state
    handle_color: str = "#CCCCCC"
    border_color: str = "#666666"
    show_warning_indicator: bool = False
    show_optimization_hint: bool = False
    
    def update_from_validation(self, validation_result: OperationalValidationResult):
        """Update handle state from validation result"""
        self.is_operationally_valid = validation_result.is_feasible
        self.constraint_violations = validation_result.constraint_violations
        self.operational_range = validation_result.operational_range
        
        # Update visual feedback
        if validation_result.is_feasible:
            if validation_result.has_warnings:
                self.handle_color = "#FFD700"  # Gold for warnings
                self.border_color = "#FFA500"  # Orange border
                self.show_warning_indicator = True
            else:
                self.handle_color = "#90EE90"  # Light green for valid
                self.border_color = "#00AA00"  # Green border
                self.show_warning_indicator = False
        else:
            self.handle_color = "#FFB6C1"  # Light red for invalid
            self.border_color = "#FF4444"  # Red border
            self.show_warning_indicator = False
        
        # Create educational tooltip
        if validation_result.educational_insights:
            self.educational_tooltip = " | ".join(validation_result.educational_insights)
        
        # Show optimization hints for suboptimal but valid configurations
        self.show_optimization_hint = (
            validation_result.is_feasible and 
            validation_result.operational_efficiency < 0.8
        )