"""
Physics Validation Data Models - UI Integration Support

This module defines structured data models for physics validation results,
enabling clear communication between the SimulationService and UI components
through the event-driven architecture.

Features:
- Structured validation states and error reporting
- Force vector and constraint violation data for visualization
- Educational feedback data for user learning
- Integration with UI status indicators and 2D scene rendering
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field, validator

from .mechanism import Point2D, Point3D


class ValidationState(str, Enum):
    """Physics validation states for UI status indicators"""
    NOT_VALIDATED = "not_validated"    # Gray - Initial state
    VALIDATING = "validating"          # Yellow/Spinning - In progress
    SUCCESS = "success"                # Green - Validation passed
    WARNING = "warning"                # Orange - Has warnings but usable
    FAILURE = "failure"                # Red - Validation failed


class FailureType(str, Enum):
    """Types of physics validation failures"""
    GRASHOF_VIOLATION = "grashof_violation"
    TORQUE_EXCEEDED = "torque_exceeded"
    FORCE_EXCEEDED = "force_exceeded"
    CONSTRAINT_VIOLATION = "constraint_violation"
    UNSTABLE_STRUCTURE = "unstable_structure"
    COLLISION_DETECTED = "collision_detected"
    GEOMETRIC_INFEASIBLE = "geometric_infeasible"
    MATERIAL_FAILURE = "material_failure"
    MANUFACTURING_IMPOSSIBLE = "manufacturing_impossible"


class SeverityLevel(str, Enum):
    """Severity levels for validation issues"""
    INFO = "info"          # Informational - no action needed
    WARNING = "warning"    # Should be addressed but not blocking
    ERROR = "error"        # Must be fixed before export
    CRITICAL = "critical"  # Severe issue requiring immediate attention


@dataclass
class ValidationFailure:
    """Individual validation failure or warning"""
    component_id: str
    component_name: str
    failure_type: FailureType
    severity: SeverityLevel
    message: str
    technical_details: str = ""
    suggested_fix: str = ""
    
    # Spatial information for highlighting in 2D view
    highlight_position: Optional[Point2D] = None
    highlight_bounds: Optional[Tuple[float, float, float, float]] = None  # x, y, width, height
    
    # Quantitative data for analysis
    measured_value: Optional[float] = None
    limit_value: Optional[float] = None
    safety_factor: Optional[float] = None


@dataclass
class ForceVector:
    """Force vector for visualization in 2D scene"""
    component_id: str
    position: Point2D
    force_x: float  # Force in X direction (N)
    force_y: float  # Force in Y direction (N)
    
    # Visualization properties
    color: str = "#FF4444"  # Red for high forces
    scale_factor: float = 1.0
    show_magnitude_label: bool = True
    
    @property
    def magnitude(self) -> float:
        """Calculate force magnitude"""
        return math.sqrt(self.force_x**2 + self.force_y**2)
    
    @property
    def angle_degrees(self) -> float:
        """Calculate force angle in degrees"""
        return math.degrees(math.atan2(self.force_y, self.force_x))
    
    def get_visualization_color(self) -> str:
        """Get color based on force magnitude"""
        magnitude = self.magnitude
        
        if magnitude < 50:  # Low force
            return "#00AA00"  # Green
        elif magnitude < 150:  # Medium force
            return "#FFAA00"  # Orange
        else:  # High force
            return "#FF4444"  # Red


@dataclass
class ConstraintViolation:
    """Constraint violation data for visualization"""
    constraint_id: str
    joint_id: str
    constraint_type: str  # "revolute", "prismatic", "fixed"
    violation_type: str   # "limit_exceeded", "force_exceeded", "unstable"
    
    position: Point2D
    measured_value: float
    limit_value: float
    
    # Visualization properties
    severity: SeverityLevel = SeverityLevel.ERROR
    highlight_color: str = "#FF0000"
    show_details: bool = True


@dataclass
class MotionPathData:
    """Motion path data for educational visualization"""
    component_id: str
    component_name: str
    path_points: List[Point2D]
    velocity_vectors: List[Tuple[float, float]]  # (vx, vy) at each point
    acceleration_vectors: List[Tuple[float, float]]  # (ax, ay) at each point
    
    # Visualization properties
    path_color: str = "#0066CC"
    show_velocity: bool = False
    show_acceleration: bool = False
    animation_duration: float = 2.0  # seconds


class PhysicsValidationResult(BaseModel):
    """
    Complete physics validation result for UI integration.
    
    This model contains all data needed by the UI to:
    - Update status indicators
    - Enable/disable buttons
    - Visualize forces and constraints in 2D scene
    - Provide educational feedback to users
    """
    
    # Basic validation state
    mechanism_id: str = Field(..., description="ID of validated mechanism")
    validation_state: ValidationState = Field(..., description="Overall validation state")
    validation_time: datetime = Field(default_factory=datetime.now)
    computation_time: float = Field(default=0.0, description="Validation time in seconds")
    
    # Validation results
    failures: List[ValidationFailure] = Field(default_factory=list, description="Validation failures and warnings")
    force_vectors: List[ForceVector] = Field(default_factory=list, description="Force vectors for visualization")
    constraint_violations: List[ConstraintViolation] = Field(default_factory=list, description="Constraint violations")
    motion_paths: List[MotionPathData] = Field(default_factory=list, description="Motion path data")
    
    # Summary statistics
    max_force_magnitude: float = Field(default=0.0, description="Maximum force in mechanism (N)")
    min_safety_factor: float = Field(default=float('inf'), description="Minimum safety factor")
    total_mechanical_advantage: float = Field(default=1.0, description="Overall mechanical advantage")
    
    # Manufacturing validation
    is_manufacturable: bool = Field(default=True, description="Can be manufactured as designed")
    estimated_cost: float = Field(default=0.0, description="Estimated manufacturing cost ($)")
    manufacturing_notes: List[str] = Field(default_factory=list, description="Manufacturing recommendations")
    
    # Educational metadata
    educational_insights: List[str] = Field(default_factory=list, description="Learning points for students")
    physics_principles: List[str] = Field(default_factory=list, description="Physics principles demonstrated")
    
    class Config:
        arbitrary_types_allowed = True
    
    @property
    def has_failures(self) -> bool:
        """Check if validation has any failures"""
        return len(self.failures) > 0
    
    @property
    def has_errors(self) -> bool:
        """Check if validation has blocking errors"""
        return any(f.severity in [SeverityLevel.ERROR, SeverityLevel.CRITICAL] for f in self.failures)
    
    @property
    def has_warnings(self) -> bool:
        """Check if validation has non-blocking warnings"""
        return any(f.severity == SeverityLevel.WARNING for f in self.failures)
    
    @property
    def can_export_blueprint(self) -> bool:
        """Check if mechanism can be exported to blueprint"""
        return self.validation_state in [ValidationState.SUCCESS, ValidationState.WARNING] and not self.has_errors
    
    @property
    def status_color(self) -> str:
        """Get status indicator color for UI"""
        color_map = {
            ValidationState.NOT_VALIDATED: "#999999",  # Gray
            ValidationState.VALIDATING: "#FFAA00",     # Orange
            ValidationState.SUCCESS: "#00AA00",        # Green
            ValidationState.WARNING: "#FFAA00",        # Orange
            ValidationState.FAILURE: "#FF4444"         # Red
        }
        return color_map.get(self.validation_state, "#999999")
    
    @property
    def status_message(self) -> str:
        """Get human-readable status message"""
        if self.validation_state == ValidationState.NOT_VALIDATED:
            return "Physics validation not performed"
        elif self.validation_state == ValidationState.VALIDATING:
            return "Running physics validation..."
        elif self.validation_state == ValidationState.SUCCESS:
            return f"Validation successful - Safety factor: {self.min_safety_factor:.1f}"
        elif self.validation_state == ValidationState.WARNING:
            warning_count = len([f for f in self.failures if f.severity == SeverityLevel.WARNING])
            return f"Validation passed with {warning_count} warnings"
        elif self.validation_state == ValidationState.FAILURE:
            error_count = len([f for f in self.failures if f.severity in [SeverityLevel.ERROR, SeverityLevel.CRITICAL]])
            return f"Validation failed - {error_count} errors found"
        
        return "Unknown validation state"
    
    def get_failures_by_severity(self, severity: SeverityLevel) -> List[ValidationFailure]:
        """Get failures filtered by severity level"""
        return [f for f in self.failures if f.severity == severity]
    
    def get_component_failures(self, component_id: str) -> List[ValidationFailure]:
        """Get failures for specific component"""
        return [f for f in self.failures if f.component_id == component_id]
    
    def get_force_vector(self, component_id: str) -> Optional[ForceVector]:
        """Get force vector for specific component"""
        for fv in self.force_vectors:
            if fv.component_id == component_id:
                return fv
        return None
    
    def add_educational_insight(self, insight: str):
        """Add educational insight for student learning"""
        if insight not in self.educational_insights:
            self.educational_insights.append(insight)
    
    def add_physics_principle(self, principle: str):
        """Add physics principle demonstrated by this mechanism"""
        if principle not in self.physics_principles:
            self.physics_principles.append(principle)
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary for logging/debugging"""
        return {
            'mechanism_id': self.mechanism_id,
            'state': self.validation_state.value,
            'computation_time': self.computation_time,
            'failures_count': len(self.failures),
            'errors_count': len(self.get_failures_by_severity(SeverityLevel.ERROR)),
            'warnings_count': len(self.get_failures_by_severity(SeverityLevel.WARNING)),
            'max_force': self.max_force_magnitude,
            'min_safety_factor': self.min_safety_factor,
            'can_export': self.can_export_blueprint,
            'is_manufacturable': self.is_manufacturable,
            'estimated_cost': self.estimated_cost
        }


class LivePhysicsUpdate(BaseModel):
    """
    Lightweight physics update for real-time parameter feedback.
    
    Used during parametric editing to provide immediate visual feedback
    without running full physics simulation.
    """
    
    mechanism_id: str = Field(..., description="ID of mechanism being updated")
    update_time: datetime = Field(default_factory=datetime.now)
    
    # Quick validation results
    is_geometrically_valid: bool = Field(default=True, description="Basic geometric validity")
    has_collisions: bool = Field(default=False, description="Collision detection result")
    is_stable: bool = Field(default=True, description="Basic stability check")
    
    # Component-specific feedback
    component_status: Dict[str, str] = Field(default_factory=dict, description="Status per component")
    warning_components: List[str] = Field(default_factory=list, description="Components with warnings")
    error_components: List[str] = Field(default_factory=list, description="Components with errors")
    
    # Quick force estimates (simplified)
    estimated_max_force: float = Field(default=0.0, description="Quick force estimate")
    estimated_safety_factor: float = Field(default=float('inf'), description="Quick safety estimate")
    
    @property
    def overall_status(self) -> str:
        """Get overall status for UI feedback"""
        if self.error_components:
            return "error"
        elif self.warning_components or not self.is_stable or self.has_collisions:
            return "warning"
        elif self.is_geometrically_valid:
            return "good"
        else:
            return "unknown"
    
    @property
    def status_color(self) -> str:
        """Get color for real-time feedback"""
        status = self.overall_status
        if status == "error":
            return "#FF4444"
        elif status == "warning":
            return "#FFAA00"
        elif status == "good":
            return "#00AA00"
        else:
            return "#999999"


# Event data models for UI integration

@dataclass
class ValidatePhysicsRequested:
    """Event data for physics validation request"""
    mechanism_id: str
    mechanism_data: Dict[str, Any]  # Serialized mechanism data
    validation_level: str = "full"  # "full", "quick", "manufacturing"
    requester: str = "ui"  # Who requested the validation


@dataclass
class PhysicsValidationCompleted:
    """Event data for completed physics validation"""
    result: PhysicsValidationResult
    
    
@dataclass
class LivePhysicsUpdateRequested:
    """Event data for live physics update request"""
    mechanism_id: str
    changed_parameters: Dict[str, Any]
    
    
@dataclass
class LivePhysicsUpdateCompleted:
    """Event data for completed live physics update"""
    update: LivePhysicsUpdate


# UI Component Data Models

@dataclass
class ValidationStatusIndicatorState:
    """State data for validation status indicator widget"""
    validation_state: ValidationState
    message: str
    color: str
    tooltip: str = ""
    show_spinner: bool = False
    
    @classmethod
    def from_validation_result(cls, result: PhysicsValidationResult) -> 'ValidationStatusIndicatorState':
        """Create indicator state from validation result"""
        return cls(
            validation_state=result.validation_state,
            message=result.status_message,
            color=result.status_color,
            tooltip=f"Validation completed in {result.computation_time:.2f}s",
            show_spinner=(result.validation_state == ValidationState.VALIDATING)
        )
    
    @classmethod
    def validating(cls, message: str = "Validating...") -> 'ValidationStatusIndicatorState':
        """Create validating state"""
        return cls(
            validation_state=ValidationState.VALIDATING,
            message=message,
            color="#FFAA00",
            show_spinner=True
        )
    
    @classmethod
    def not_validated(cls) -> 'ValidationStatusIndicatorState':
        """Create not validated state"""
        return cls(
            validation_state=ValidationState.NOT_VALIDATED,
            message="Not Validated",
            color="#999999",
            tooltip="Click 'Validate Physics' to check mechanism"
        )


@dataclass
class PhysicsVisualizationSettings:
    """Settings for physics visualization in 2D scene"""
    show_force_vectors: bool = False
    show_constraint_violations: bool = True
    show_motion_paths: bool = False
    show_safety_factors: bool = False
    
    # Visualization parameters
    force_vector_scale: float = 1.0
    force_vector_threshold: float = 10.0  # Minimum force to show (N)
    motion_path_steps: int = 50
    animation_speed: float = 1.0
    
    # Colors
    force_color_low: str = "#00AA00"
    force_color_medium: str = "#FFAA00"
    force_color_high: str = "#FF4444"
    violation_color: str = "#FF0000"
    path_color: str = "#0066CC"