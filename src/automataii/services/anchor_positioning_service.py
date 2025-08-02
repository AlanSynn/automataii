"""
Intelligent Anchor Positioning Service

Event-driven service for validating anchor position changes with operational
feasibility analysis. Ensures mechanism configurations remain functionally
viable throughout interactive editing.

Architecture: Gemini's Strategic Event-Driven Design
- Decoupled from UI layer through EventBus communication
- Comprehensive operational validation beyond static geometry
- Real-time feedback for interactive design optimization
- Integration with existing physics validation system
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Any

from PyQt6.QtCore import QObject

from ..core.event_bus import EventBus
from ..core.event_types import EventType
from ..models.mechanism import Mechanism, Point2D
from ..models.anchor_positioning import (
    AnchorPositionChangeRequested,
    AnchorValidationCompleted,
    OperationalValidationResult,
    ConstraintViolation,
    MotionPathData
)
from ..domain.kinematics.mechanism_validator import MechanismValidator

logger = logging.getLogger(__name__)


class AnchorPositioningService(QObject):
    """
    Intelligent anchor positioning service with operational feasibility analysis.
    
    Implements Gemini's strategic architecture for operation-aware anchor positioning:
    - Event-driven validation of anchor position changes
    - Comprehensive operational feasibility analysis
    - Real-time constraint violation detection
    - Integration with physics validation system
    - Educational feedback for design optimization
    
    The service ensures that any anchor position change results in a mechanically
    viable configuration that can operate throughout its intended range.
    """
    
    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        
        # Initialize mechanism validator for operational analysis
        self.validator = MechanismValidator()
        
        # Cache for mechanism state to avoid repeated lookups
        self._mechanism_cache = {}
        self._validation_cache = {}
        
        # Subscribe to anchor positioning events
        self._subscribe_to_events()
        
        logger.info("AnchorPositioningService initialized with operational validation support")
    
    def _subscribe_to_events(self):
        """Subscribe to relevant events from UI and other services"""
        
        # Primary anchor positioning event
        self.event_bus.subscribe(
            EventType.ANCHOR_POSITION_CHANGE_REQUESTED,
            self._handle_anchor_position_request
        )
        
        # Mechanism state changes (invalidate cache)
        self.event_bus.subscribe(
            EventType.MECHANISM_PARAMETER_CHANGED,
            self._handle_mechanism_state_change
        )
        
        # Physics validation completion (enhance with operational data)
        self.event_bus.subscribe(
            EventType.PHYSICS_VALIDATION_COMPLETED,
            self._handle_physics_validation_completed
        )
    
    def _handle_anchor_position_request(self, event_data: Dict[str, Any]):
        """
        Process anchor position change request with comprehensive validation.
        
        Implements Gemini's operational analysis strategy:
        1. Extract and validate request data
        2. Get current mechanism configuration
        3. Apply proposed anchor change
        4. Validate operational feasibility
        5. Calculate operational range and constraints
        6. Publish detailed validation results
        """
        try:
            # Extract event data
            mechanism_id = event_data.get('mechanism_id')
            anchor_id = event_data.get('anchor_id')
            proposed_position = event_data.get('proposed_position')
            requester = event_data.get('requester', 'unknown')
            
            if not all([mechanism_id, anchor_id, proposed_position]):
                logger.error("Invalid anchor position request - missing required data")
                return
            
            logger.debug(f"Processing anchor position request: {mechanism_id}:{anchor_id} -> {proposed_position}")
            
            # Get current mechanism state
            current_mechanism = self._get_mechanism_from_cache(mechanism_id)
            if not current_mechanism:
                logger.warning(f"Mechanism {mechanism_id} not found for anchor positioning")
                self._publish_validation_failure(mechanism_id, anchor_id, "Mechanism not found")
                return
            
            # Create proposed mechanism with new anchor position
            proposed_mechanism = self._apply_anchor_change(
                current_mechanism, anchor_id, proposed_position
            )
            
            if not proposed_mechanism:
                logger.error(f"Failed to apply anchor change for {mechanism_id}:{anchor_id}")
                self._publish_validation_failure(mechanism_id, anchor_id, "Failed to apply change")
                return
            
            # Validate operational feasibility
            validation_result = self.validator.validate_operational_feasibility(proposed_mechanism)
            
            # Enhance with educational insights
            self._add_educational_insights(validation_result, current_mechanism, proposed_mechanism)
            
            # Publish comprehensive validation results
            self._publish_validation_results(
                mechanism_id, anchor_id, validation_result, proposed_mechanism, requester
            )
            
            logger.info(f"Anchor validation completed: {mechanism_id}:{anchor_id} -> "
                       f"{'VALID' if validation_result.is_feasible else 'INVALID'}")
            
        except Exception as e:
            logger.error(f"Error processing anchor position request: {e}")
            self._publish_validation_failure(
                event_data.get('mechanism_id', 'unknown'),
                event_data.get('anchor_id', 'unknown'),
                f"Validation error: {str(e)}"
            )
    
    def _get_mechanism_from_cache(self, mechanism_id: str) -> Optional[Mechanism]:
        """
        Get mechanism from cache or create from current state.
        
        This bridges the gap between the existing state management
        and the centralized Mechanism model architecture.
        """
        # Check cache first
        if mechanism_id in self._mechanism_cache:
            return self._mechanism_cache[mechanism_id]
        
        # TODO: In real implementation, this would query the state manager
        # For now, create a placeholder mechanism for demonstration
        mechanism = self._create_mechanism_placeholder(mechanism_id)
        
        if mechanism:
            self._mechanism_cache[mechanism_id] = mechanism
        
        return mechanism
    
    def _create_mechanism_placeholder(self, mechanism_id: str) -> Optional[Mechanism]:
        """
        Create mechanism placeholder for demonstration.
        
        In real implementation, this would query the actual state manager
        or mechanism repository to get current mechanism configuration.
        """
        try:
            # Create a basic 4-bar linkage for demonstration
            mechanism = Mechanism.create_four_bar_linkage(
                name=f"Mechanism {mechanism_id}",
                ground_length=100.0,
                driver_length=80.0,
                coupler_length=120.0,
                rocker_length=90.0,
                ground_pivot_1=Point2D(0, 0),
                ground_pivot_2=Point2D(100, 0)
            )
            
            return mechanism
            
        except Exception as e:
            logger.error(f"Failed to create mechanism placeholder: {e}")
            return None
    
    def _apply_anchor_change(self, mechanism: Mechanism, anchor_id: str, 
                           new_position: Tuple[float, float]) -> Optional[Mechanism]:
        """
        Apply anchor position change to mechanism configuration.
        
        Creates a new mechanism instance with the updated anchor position,
        preserving all other parameters and constraints.
        """
        try:
            # Create a copy of the mechanism
            updated_mechanism = mechanism.model_copy(deep=True)
            
            # Update the appropriate anchor position
            new_point = Point2D(new_position[0], new_position[1])
            
            if anchor_id == "ground_pivot_1":
                # Update first ground pivot
                if "ground_pivot_1" in updated_mechanism.joints:
                    updated_mechanism.joints["ground_pivot_1"].position = new_point
                
                # Recalculate ground link length
                if "ground_pivot_2" in updated_mechanism.joints:
                    pivot2 = updated_mechanism.joints["ground_pivot_2"].position
                    ground_length = math.sqrt(
                        (new_point.x - pivot2.x)**2 + (new_point.y - pivot2.y)**2
                    )
                    
                    # Update ground link length in mechanism
                    if "ground" in updated_mechanism.links:
                        updated_mechanism.links["ground"].length = ground_length
            
            elif anchor_id == "ground_pivot_2":
                # Update second ground pivot
                if "ground_pivot_2" in updated_mechanism.joints:
                    updated_mechanism.joints["ground_pivot_2"].position = new_point
                
                # Recalculate ground link length
                if "ground_pivot_1" in updated_mechanism.joints:
                    pivot1 = updated_mechanism.joints["ground_pivot_1"].position
                    ground_length = math.sqrt(
                        (new_point.x - pivot1.x)**2 + (new_point.y - pivot1.y)**2
                    )
                    
                    # Update ground link length in mechanism
                    if "ground" in updated_mechanism.links:
                        updated_mechanism.links["ground"].length = ground_length
            
            else:
                logger.warning(f"Unknown anchor_id: {anchor_id}")
                return None
            
            return updated_mechanism
            
        except Exception as e:
            logger.error(f"Failed to apply anchor change: {e}")
            return None
    
    def _add_educational_insights(self, validation_result: OperationalValidationResult,
                                current_mechanism: Mechanism, proposed_mechanism: Mechanism):
        """
        Add educational insights to validation result.
        
        Provides learning opportunities by explaining the mechanical
        principles and constraints involved in the configuration change.
        """
        try:
            insights = []
            
            # Compare ground link lengths
            current_ground_length = self._get_ground_link_length(current_mechanism)
            proposed_ground_length = self._get_ground_link_length(proposed_mechanism)
            
            if abs(proposed_ground_length - current_ground_length) > 10:
                length_change = proposed_ground_length - current_ground_length
                insights.append(
                    f"Ground link length changed by {length_change:.1f}mm - "
                    f"this affects the entire mechanism's motion characteristics"
                )
            
            # Grashof condition analysis
            if not validation_result.is_feasible:
                grashof_violations = [v for v in validation_result.constraint_violations 
                                    if "grashof" in v.violation_type.lower()]
                if grashof_violations:
                    insights.append(
                        "Grashof condition violated - mechanism may not have continuous rotation. "
                        "Try adjusting anchor positions to create a more balanced linkage."
                    )
            
            # Operational range analysis
            if validation_result.operational_range:
                range_size = len(validation_result.operational_range)
                if range_size < 36:  # Less than 10% of full circle
                    insights.append(
                        f"Limited operational range ({range_size} positions) - "
                        f"consider adjusting link lengths for broader motion"
                    )
            
            validation_result.educational_insights = insights
            
        except Exception as e:
            logger.error(f"Failed to add educational insights: {e}")
    
    def _get_ground_link_length(self, mechanism: Mechanism) -> float:
        """Get ground link length from mechanism"""
        try:
            if "ground" in mechanism.links:
                return mechanism.links["ground"].length
            return 0.0
        except Exception:
            return 0.0
    
    def _publish_validation_results(self, mechanism_id: str, anchor_id: str,
                                  validation_result: OperationalValidationResult,
                                  updated_mechanism: Mechanism, requester: str):
        """Publish comprehensive validation results to UI components"""
        
        event_data = AnchorValidationCompleted(
            mechanism_id=mechanism_id,
            anchor_id=anchor_id,
            is_feasible=validation_result.is_feasible,
            operational_range=validation_result.operational_range,
            constraint_violations=validation_result.constraint_violations,
            motion_paths=validation_result.motion_paths,
            updated_mechanism=updated_mechanism.to_dict(),
            educational_insights=validation_result.educational_insights,
            requester=requester
        )
        
        self.event_bus.publish(EventType.ANCHOR_VALIDATION_COMPLETED, event_data.__dict__)
        
        # Also publish operational range update for visualization
        if validation_result.operational_range:
            self.event_bus.publish(
                EventType.OPERATIONAL_RANGE_UPDATED,
                {
                    'mechanism_id': mechanism_id,
                    'operational_range': [
                        {'x': p.x, 'y': p.y} for p in validation_result.operational_range
                    ]
                }
            )
    
    def _publish_validation_failure(self, mechanism_id: str, anchor_id: str, error_message: str):
        """Publish validation failure for UI feedback"""
        
        event_data = AnchorValidationCompleted(
            mechanism_id=mechanism_id,
            anchor_id=anchor_id,
            is_feasible=False,
            operational_range=[],
            constraint_violations=[
                ConstraintViolation(
                    constraint_id="validation_error",
                    joint_id=anchor_id,
                    constraint_type="system_error",
                    violation_type=error_message,
                    position=Point2D(0, 0),
                    measured_value=0.0,
                    limit_value=0.0
                )
            ],
            motion_paths=[],
            updated_mechanism={},
            educational_insights=[f"Validation failed: {error_message}"],
            requester="system"
        )
        
        self.event_bus.publish(EventType.ANCHOR_VALIDATION_COMPLETED, event_data.__dict__)
    
    def _handle_mechanism_state_change(self, event_data: Dict[str, Any]):
        """Handle mechanism state changes by invalidating cache"""
        mechanism_id = event_data.get('mechanism_id')
        if mechanism_id:
            # Invalidate cached mechanism data
            self._mechanism_cache.pop(mechanism_id, None)
            self._validation_cache.pop(mechanism_id, None)
            logger.debug(f"Invalidated cache for mechanism {mechanism_id}")
    
    def _handle_physics_validation_completed(self, event_data: Dict[str, Any]):
        """Integrate physics validation results with anchor positioning data"""
        try:
            mechanism_id = event_data.get('mechanism_id')
            if not mechanism_id:
                return
            
            # Store physics validation results for integration with anchor validation
            result_data = event_data.get('result', {})
            if result_data:
                self._validation_cache[mechanism_id] = result_data
                logger.debug(f"Cached physics validation for mechanism {mechanism_id}")
            
        except Exception as e:
            logger.error(f"Error handling physics validation completion: {e}")
    
    def get_cached_mechanism(self, mechanism_id: str) -> Optional[Mechanism]:
        """Get cached mechanism for external access"""
        return self._mechanism_cache.get(mechanism_id)
    
    def clear_cache(self, mechanism_id: Optional[str] = None):
        """Clear mechanism cache (all or specific mechanism)"""
        if mechanism_id:
            self._mechanism_cache.pop(mechanism_id, None)
            self._validation_cache.pop(mechanism_id, None)
            logger.info(f"Cleared cache for mechanism {mechanism_id}")
        else:
            self._mechanism_cache.clear()
            self._validation_cache.clear()
            logger.info("Cleared all mechanism cache")
    
    def cleanup(self):
        """Clean up resources and event subscriptions"""
        self.clear_cache()
        # Event bus subscriptions are automatically cleaned up
        logger.info("AnchorPositioningService cleaned up")