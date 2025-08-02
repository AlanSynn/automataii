"""
Intelligent Anchor Handle - Operation-Aware Anchor Positioning

Enhanced anchor handle with real-time operational feasibility validation.
Integrates with AnchorPositioningService through event-driven architecture
to provide immediate feedback on mechanism viability during interactive editing.

Architecture: Gemini's Strategic Event-Driven Design
- Event-driven communication with validation service
- Real-time visual feedback based on operational analysis
- Educational tooltips and constraint violation highlighting
- Smooth integration with existing parametric system
"""

import logging
import math
from typing import Dict, List, Optional, Callable, Any

from PyQt6.QtCore import QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPen, QBrush, QPainter
from PyQt6.QtWidgets import QGraphicsEllipseItem, QToolTip

from .....core.event_bus import EventBus
from .....core.event_types import EventType
from .....models.mechanism import Point2D
from .....models.anchor_positioning import (
    AnchorPositionChangeRequested,
    AnchorValidationCompleted,
    AnchorHandleState,
    ConstraintViolation
)
from .base_handle import BaseHandle

logger = logging.getLogger(__name__)


class IntelligentAnchorHandle(BaseHandle):
    """
    Intelligent anchor handle with operational feasibility awareness.
    
    Features:
    - Real-time operational validation through event-driven architecture
    - Visual feedback based on mechanism feasibility analysis
    - Educational tooltips with physics principles and constraints
    - Constraint violation highlighting with spatial awareness
    - Optimization suggestions for design improvement
    
    Workflow:
    1. User drags anchor → Publishes AnchorPositionChangeRequested event
    2. AnchorPositioningService validates → Comprehensive operational analysis
    3. Service publishes AnchorValidationCompleted → Handle updates visual feedback
    4. User sees immediate color-coded feedback and educational tooltips
    """
    
    # Enhanced color scheme for operational feedback
    COLOR_VALID = QColor(144, 238, 144)        # Light green - operationally valid
    COLOR_VALID_BORDER = QColor(0, 170, 0)     # Green border
    COLOR_WARNING = QColor(255, 215, 0)        # Gold - valid with warnings
    COLOR_WARNING_BORDER = QColor(255, 165, 0) # Orange border
    COLOR_INVALID = QColor(255, 182, 193)      # Light red - operationally invalid
    COLOR_INVALID_BORDER = QColor(255, 68, 68) # Red border
    COLOR_VALIDATING = QColor(255, 255, 224)   # Light yellow - validation in progress
    COLOR_VALIDATING_BORDER = QColor(255, 215, 0) # Gold border
    
    # Signals for educational integration
    educational_insight_generated = pyqtSignal(str, str)  # (insight, principle)
    constraint_violation_detected = pyqtSignal(str, list)  # (anchor_id, violations)
    
    def __init__(
        self,
        mechanism_id: str,
        anchor_name: str,
        initial_position: QPointF,
        mechanism_data: dict,
        event_bus: EventBus,
        update_callback: Callable[[str, QPointF], None] = None,
        parent=None
    ):
        """
        Initialize intelligent anchor handle with operational validation.
        
        Args:
            mechanism_id: Unique mechanism identifier
            anchor_name: Name of anchor point ('ground_pivot_1', 'ground_pivot_2')
            initial_position: Starting position in scene coordinates
            mechanism_data: Reference to mechanism layer data
            event_bus: EventBus for communication with validation service
            update_callback: Function to call when anchor moves (legacy support)
            parent: Qt parent object
        """
        super().__init__(
            mechanism_id, anchor_name, initial_position, None, None, parent
        )
        
        # Event-driven architecture components
        self.event_bus = event_bus
        self.mechanism_data = mechanism_data
        self.update_callback = update_callback
        
        # Operational validation state
        self.handle_state = AnchorHandleState(
            mechanism_id=mechanism_id,
            anchor_id=anchor_name,
            is_operationally_valid=True,
            constraint_violations=[],
            operational_range=[]
        )
        
        # Visual feedback components
        self.operational_range_item = None
        self.constraint_indicators = []
        self.validation_timer = QTimer()
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self._request_validation)
        
        # Debouncing for smooth interaction
        self.validation_debounce_ms = 150  # 150ms debounce for real-time feedback
        self.pending_position = None
        
        # Setup enhanced appearance and event subscriptions
        self._setup_intelligent_appearance()
        self._subscribe_to_validation_events()
        
        logger.info(f"Created IntelligentAnchorHandle for {anchor_name} with operational validation")
    
    def _setup_intelligent_appearance(self):
        """Setup enhanced visual appearance for operational feedback"""
        # Larger size for enhanced visibility and interaction
        self.HANDLE_RADIUS = 25.0
        self.HOVER_RADIUS = 30.0
        self.ACTIVE_RADIUS = 35.0
        
        # Initial appearance (valid until proven otherwise)
        self._update_visual_feedback()
        
        # Enhanced visibility
        self.setVisible(True)
        self.setOpacity(1.0)
        self.setZValue(1000)  # High z-value for visibility
        
        logger.debug(f"Enhanced appearance setup for {self.anchor_name}")
    
    def _subscribe_to_validation_events(self):
        """Subscribe to validation events from AnchorPositioningService"""
        
        # Subscribe to anchor validation completion
        self.event_bus.subscribe(
            EventType.ANCHOR_VALIDATION_COMPLETED,
            self._handle_validation_result
        )
        
        # Subscribe to operational range updates for visualization
        self.event_bus.subscribe(
            EventType.OPERATIONAL_RANGE_UPDATED,
            self._handle_operational_range_update
        )
        
        # Subscribe to constraint violation detection
        self.event_bus.subscribe(
            EventType.CONSTRAINT_VIOLATION_DETECTED,
            self._handle_constraint_violation
        )
    
    def mouseMoveEvent(self, event):
        """Enhanced mouse move with operational validation"""
        if not self._is_dragging or not self._is_enabled:
            return
        
        new_position = event.scenePos()
        
        # Update visual position immediately for responsiveness
        self.setPos(new_position)
        
        # Store pending position for validation
        self.pending_position = new_position
        
        # Set validating state for immediate feedback
        self._set_validating_state()
        
        # Debounce validation requests for smooth interaction
        self.validation_timer.start(self.validation_debounce_ms)
        
        # Call parent for standard handling
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release with final validation"""
        super().mouseReleaseEvent(event)
        
        # Trigger immediate validation on release
        if self.pending_position:
            self.validation_timer.stop()
            self._request_validation()
    
    def _request_validation(self):
        """Request operational validation from AnchorPositioningService"""
        if not self.pending_position:
            return
        
        try:
            # Create validation request event
            validation_request = AnchorPositionChangeRequested(
                mechanism_id=self.mechanism_id,
                anchor_id=self.anchor_name,
                proposed_position=(self.pending_position.x(), self.pending_position.y()),
                requester="intelligent_anchor_handle"
            )
            
            # Publish validation request
            self.event_bus.publish(
                EventType.ANCHOR_POSITION_CHANGE_REQUESTED,
                validation_request.__dict__
            )
            
            logger.debug(f"Validation requested for {self.anchor_name} at {self.pending_position}")
            
        except Exception as e:
            logger.error(f"Failed to request validation: {e}")
            self._set_error_state(f"Validation request failed: {str(e)}")
    
    def _handle_validation_result(self, event_data: Dict[str, Any]):
        """Handle validation result from AnchorPositioningService"""
        try:
            # Check if this result is for our anchor
            if event_data.get('anchor_id') != self.anchor_name:
                return
            
            # Extract validation results
            is_feasible = event_data.get('is_feasible', False)
            constraint_violations = event_data.get('constraint_violations', [])
            operational_range = event_data.get('operational_range', [])
            educational_insights = event_data.get('educational_insights', [])
            
            # Update handle state
            self.handle_state.is_operationally_valid = is_feasible
            self.handle_state.constraint_violations = constraint_violations
            self.handle_state.operational_range = operational_range
            
            # Update visual feedback
            self._update_visual_feedback()
            
            # Apply parameter change if valid
            if is_feasible and self.pending_position:
                self._apply_parameter_change(self.pending_position)
            
            # Emit educational insights
            for insight in educational_insights:
                self.educational_insight_generated.emit(insight, "Operational Analysis")
            
            # Emit constraint violations for external handling
            if constraint_violations:
                self.constraint_violation_detected.emit(self.anchor_name, constraint_violations)
            
            # Clear pending position
            self.pending_position = None
            
            logger.debug(f"Validation completed for {self.anchor_name}: {'VALID' if is_feasible else 'INVALID'}")
            
        except Exception as e:
            logger.error(f"Error handling validation result: {e}")
            self._set_error_state(f"Validation processing failed: {str(e)}")
    
    def _handle_operational_range_update(self, event_data: Dict[str, Any]):
        """Handle operational range update for visualization"""
        try:
            mechanism_id = event_data.get('mechanism_id')
            if mechanism_id != self.mechanism_id:
                return
            
            operational_range = event_data.get('operational_range', [])
            
            # Update operational range visualization
            self._update_operational_range_visualization(operational_range)
            
        except Exception as e:
            logger.error(f"Error handling operational range update: {e}")
    
    def _handle_constraint_violation(self, event_data: Dict[str, Any]):
        """Handle constraint violation detection"""
        try:
            anchor_id = event_data.get('anchor_id')
            if anchor_id != self.anchor_name:
                return
            
            violation = event_data.get('violation')
            if violation:
                # Create visual indicator for constraint violation
                self._create_constraint_indicator(violation)
            
        except Exception as e:
            logger.error(f"Error handling constraint violation: {e}")
    
    def _update_visual_feedback(self):
        """Update visual appearance based on operational validation state"""
        try:
            if self.handle_state.is_operationally_valid:
                if self.handle_state.constraint_violations:
                    # Valid but with warnings
                    self._set_warning_state()
                else:
                    # Fully valid
                    self._set_valid_state()
            else:
                # Invalid configuration
                self._set_invalid_state()
            
            # Update educational tooltip
            self._update_educational_tooltip()
            
        except Exception as e:
            logger.error(f"Error updating visual feedback: {e}")
    
    def _set_valid_state(self):
        """Set visual appearance for valid operational state"""
        self.handle_state.handle_color = self.COLOR_VALID.name()
        self.handle_state.border_color = self.COLOR_VALID_BORDER.name()
        
        # Update Qt appearance
        self.setBrush(QBrush(self.COLOR_VALID))
        self.setPen(QPen(self.COLOR_VALID_BORDER, 3))
        
        logger.debug(f"Set valid state for {self.anchor_name}")
    
    def _set_warning_state(self):
        """Set visual appearance for valid but warned state"""
        self.handle_state.handle_color = self.COLOR_WARNING.name()
        self.handle_state.border_color = self.COLOR_WARNING_BORDER.name()
        self.handle_state.show_warning_indicator = True
        
        # Update Qt appearance
        self.setBrush(QBrush(self.COLOR_WARNING))
        self.setPen(QPen(self.COLOR_WARNING_BORDER, 3))
        
        logger.debug(f"Set warning state for {self.anchor_name}")
    
    def _set_invalid_state(self):
        """Set visual appearance for invalid operational state"""
        self.handle_state.handle_color = self.COLOR_INVALID.name()
        self.handle_state.border_color = self.COLOR_INVALID_BORDER.name()
        
        # Update Qt appearance
        self.setBrush(QBrush(self.COLOR_INVALID))
        self.setPen(QPen(self.COLOR_INVALID_BORDER, 3))
        
        logger.debug(f"Set invalid state for {self.anchor_name}")
    
    def _set_validating_state(self):
        """Set visual appearance for validation in progress"""
        # Temporary visual feedback during validation
        self.setBrush(QBrush(self.COLOR_VALIDATING))
        self.setPen(QPen(self.COLOR_VALIDATING_BORDER, 3))
    
    def _set_error_state(self, error_message: str):
        """Set visual appearance for validation error state"""
        self.setBrush(QBrush(QColor(255, 100, 100)))  # Bright red for errors
        self.setPen(QPen(QColor(200, 0, 0), 4))
        
        # Set error tooltip
        self.setToolTip(f"Validation Error: {error_message}")
        
        logger.warning(f"Set error state for {self.anchor_name}: {error_message}")
    
    def _update_educational_tooltip(self):
        """Update educational tooltip with insights and constraints"""
        try:
            tooltip_parts = []
            
            # Basic anchor information
            tooltip_parts.append(f"Anchor: {self.anchor_name}")
            tooltip_parts.append(f"Position: ({self.pos().x():.1f}, {self.pos().y():.1f})")
            
            # Operational status
            if self.handle_state.is_operationally_valid:
                tooltip_parts.append("✓ Operationally Valid")
            else:
                tooltip_parts.append("✗ Operationally Invalid")
            
            # Constraint violations
            if self.handle_state.constraint_violations:
                tooltip_parts.append("Constraints:")
                for violation in self.handle_state.constraint_violations[:3]:  # First 3 violations
                    tooltip_parts.append(f"  • {violation.message}")
                
                if len(self.handle_state.constraint_violations) > 3:
                    remaining = len(self.handle_state.constraint_violations) - 3
                    tooltip_parts.append(f"  • ... and {remaining} more")
            
            # Educational insights
            if self.handle_state.educational_tooltip:
                tooltip_parts.append("💡 " + self.handle_state.educational_tooltip)
            
            # Operational range info
            if self.handle_state.operational_range:
                range_size = len(self.handle_state.operational_range)
                tooltip_parts.append(f"Operational Range: {range_size} positions")
            
            # Set combined tooltip
            tooltip_text = "\n".join(tooltip_parts)
            self.setToolTip(tooltip_text)
            
        except Exception as e:
            logger.error(f"Error updating educational tooltip: {e}")
    
    def _apply_parameter_change(self, new_position: QPointF):
        """Apply anchor position change to mechanism data"""
        try:
            # Update position in mechanism data
            key_points = self.mechanism_data.get("key_points", {})
            if not key_points:
                key_points = {}
                self.mechanism_data["key_points"] = key_points
            
            # Update the anchor position
            key_points[self.anchor_name] = [new_position.x(), new_position.y()]
            
            # Call legacy update callback if provided
            if self.update_callback:
                self.update_callback(self.anchor_name, new_position)
            
            logger.debug(f"Applied parameter change for {self.anchor_name} to {new_position}")
            
        except Exception as e:
            logger.error(f"Failed to apply parameter change: {e}")
    
    def _update_operational_range_visualization(self, operational_range: List[Dict[str, float]]):
        """Update operational range visualization in scene"""
        try:
            # Remove existing operational range visualization
            if self.operational_range_item and self.scene():
                self.scene().removeItem(self.operational_range_item)
                self.operational_range_item = None
            
            # Create new operational range visualization if data available
            if operational_range and len(operational_range) > 2:
                # Convert range data to QPointF list
                range_points = [QPointF(p['x'], p['y']) for p in operational_range]
                
                # Create visualization item (simplified - would be enhanced in production)
                # This would create a semi-transparent path showing operational range
                logger.debug(f"Updated operational range visualization with {len(range_points)} points")
            
        except Exception as e:
            logger.error(f"Error updating operational range visualization: {e}")
    
    def _create_constraint_indicator(self, violation: ConstraintViolation):
        """Create visual indicator for constraint violation"""
        try:
            # Create small red circle at violation position
            indicator = QGraphicsEllipseItem(-5, -5, 10, 10)
            indicator.setBrush(QBrush(QColor(255, 0, 0)))
            indicator.setPen(QPen(QColor(200, 0, 0), 2))
            indicator.setPos(violation.position.x, violation.position.y)
            
            # Add to scene if available
            if self.scene():
                self.scene().addItem(indicator)
                self.constraint_indicators.append(indicator)
            
            logger.debug(f"Created constraint indicator for violation: {violation.message}")
            
        except Exception as e:
            logger.error(f"Error creating constraint indicator: {e}")
    
    def _calculate_parameter_from_position(self, scene_pos: QPointF) -> QPointF:
        """Calculate anchor position from handle position (same for anchors)"""
        return scene_pos
    
    def get_current_parameter_value(self) -> QPointF:
        """Get current anchor position"""
        try:
            key_points = self.mechanism_data.get("key_points", {})
            if key_points and self.anchor_name in key_points:
                pos_data = key_points[self.anchor_name]
                return QPointF(pos_data[0], pos_data[1])
            else:
                return self.pos()
        except Exception as e:
            logger.warning(f"Could not get current anchor position: {e}")
            return self.pos()
    
    def get_operational_state(self) -> AnchorHandleState:
        """Get current operational state for external access"""
        return self.handle_state
    
    def is_operationally_valid(self) -> bool:
        """Check if anchor is in operationally valid state"""
        return self.handle_state.is_operationally_valid
    
    def get_constraint_violations(self) -> List[ConstraintViolation]:
        """Get current constraint violations"""
        return self.handle_state.constraint_violations
    
    def cleanup(self):
        """Clean up resources and visual elements"""
        try:
            # Stop validation timer
            self.validation_timer.stop()
            
            # Remove operational range visualization
            if self.operational_range_item and self.scene():
                self.scene().removeItem(self.operational_range_item)
                self.operational_range_item = None
            
            # Remove constraint indicators
            for indicator in self.constraint_indicators:
                if self.scene():
                    self.scene().removeItem(indicator)
            self.constraint_indicators.clear()
            
            logger.debug(f"Cleaned up IntelligentAnchorHandle for {self.anchor_name}")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        pos = self.pos()
        valid_status = "VALID" if self.handle_state.is_operationally_valid else "INVALID"
        return (
            f"IntelligentAnchorHandle({self.mechanism_id}:{self.anchor_name} "
            f"at {pos.x():.1f},{pos.y():.1f} - {valid_status})"
        )