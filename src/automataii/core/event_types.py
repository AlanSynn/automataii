"""
Event Type Definitions for Automataii

Centralized definition of all event types used throughout the application
for type-safe event-driven communication.

Architecture: Gemini's Strategic Event-Driven Design
- Centralized event type definitions for consistency
- String-based enum for serialization compatibility
- Organized by functional domain for maintainability
"""

from enum import Enum


class EventType(str, Enum):
    """
    Centralized event type definitions for the Automataii application.
    
    Organized by functional domain to maintain clarity and prevent
    conflicts between different subsystems.
    """
    
    # === Core System Events ===
    APPLICATION_STARTED = "application_started"
    APPLICATION_SHUTDOWN = "application_shutdown"
    PROJECT_LOADED = "project_loaded"
    PROJECT_SAVED = "project_saved"
    PROJECT_CLOSED = "project_closed"
    
    # === UI State Events ===
    TAB_ACTIVATED = "tab_activated"
    TAB_DEACTIVATED = "tab_deactivated"
    UI_STATE_CHANGED = "ui_state_changed"
    
    # === Mechanism Design Events ===
    MECHANISM_CREATED = "mechanism_created"
    MECHANISM_UPDATED = "mechanism_updated"
    MECHANISM_DELETED = "mechanism_deleted"
    MECHANISM_PARAMETER_CHANGED = "mechanism_parameter_changed"
    MECHANISM_STATE_CHANGED = "mechanism_state_changed"
    
    # === Physics Validation Events ===
    PHYSICS_VALIDATION_REQUESTED = "physics_validation_requested"
    PHYSICS_VALIDATION_COMPLETED = "physics_validation_completed"
    SIMULATION_STARTED = "simulation_started"
    SIMULATION_COMPLETED = "simulation_completed"
    SIMULATION_ERROR = "simulation_error"
    LIVE_PHYSICS_UPDATE_REQUESTED = "live_physics_update_requested"
    LIVE_PHYSICS_UPDATE_COMPLETED = "live_physics_update_completed"
    
    # === Anchor Positioning Events (NEW) ===
    ANCHOR_POSITION_CHANGE_REQUESTED = "anchor_position_change_requested"
    ANCHOR_VALIDATION_COMPLETED = "anchor_validation_completed"
    OPERATIONAL_RANGE_UPDATED = "operational_range_updated"
    CONSTRAINT_VIOLATION_DETECTED = "constraint_violation_detected"
    
    # === Blueprint Export Events ===
    BLUEPRINT_EXPORT_REQUESTED = "blueprint_export_requested"
    BLUEPRINT_GENERATION_COMPLETED = "blueprint_generation_completed"
    BLUEPRINT_GENERATION_ERROR = "blueprint_generation_error"
    
    # === Animation Events ===
    ANIMATION_STARTED = "animation_started"
    ANIMATION_STOPPED = "animation_stopped"
    ANIMATION_PAUSED = "animation_paused"
    ANIMATION_FRAME_UPDATED = "animation_frame_updated"
    
    # === Kinematics Events ===
    IK_SOLVE_REQUESTED = "ik_solve_requested"
    IK_SOLVE_COMPLETED = "ik_solve_completed"
    POSE_UPDATED = "pose_updated"
    SKELETON_UPDATED = "skeleton_updated"
    
    # === Parametric Editing Events ===
    PARAMETRIC_MODE_TOGGLED = "parametric_mode_toggled"
    PARAMETER_HANDLE_CREATED = "parameter_handle_created"
    PARAMETER_HANDLE_DESTROYED = "parameter_handle_destroyed"
    PARAMETER_VALUE_CHANGED = "parameter_value_changed"
    
    # === Visualization Events ===
    SCENE_UPDATED = "scene_updated"
    VISUAL_ELEMENT_ADDED = "visual_element_added"
    VISUAL_ELEMENT_REMOVED = "visual_element_removed"
    VISUALIZATION_SETTINGS_CHANGED = "visualization_settings_changed"
    
    # === Error and Debug Events ===
    ERROR_OCCURRED = "error_occurred"
    WARNING_ISSUED = "warning_issued"
    DEBUG_INFO_UPDATED = "debug_info_updated"
    PERFORMANCE_METRIC_UPDATED = "performance_metric_updated"
    
    # === Educational Events ===
    EDUCATIONAL_INSIGHT_GENERATED = "educational_insight_generated"
    LEARNING_OBJECTIVE_ACHIEVED = "learning_objective_achieved"
    PHYSICS_PRINCIPLE_DEMONSTRATED = "physics_principle_demonstrated"
    
    # === Computational Character Events (NEW - Disney Research Style) ===
    CHARACTER_DESIGN_STARTED = "character_design_started"
    CHARACTER_DESIGN_COMPLETED = "character_design_completed"
    MOTION_GOALS_INTERPRETED = "motion_goals_interpreted"
    MECHANISM_SYNTHESIZED = "mechanism_synthesized"
    
    # Base generation events
    BASE_GENERATION_REQUESTED = "base_generation_requested"
    BASE_GENERATION_COMPLETED = "base_generation_completed"
    BASE_GENERATION_ERROR = "base_generation_error"
    
    # Force analysis events
    FORCE_ANALYSIS_REQUESTED = "force_analysis_requested"
    FORCE_ANALYSIS_COMPLETED = "force_analysis_completed"
    ACTUATOR_OPTIMIZED = "actuator_optimized"
    
    # Manufacturing events
    MANUFACTURING_SPECS_GENERATED = "manufacturing_specs_generated"
    BOM_CREATED = "bom_created"
    FABRICATION_FILES_EXPORTED = "fabrication_files_exported"