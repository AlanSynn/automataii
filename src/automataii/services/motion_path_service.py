"""
Motion Path Service

Event-driven service for handling motion path operations.
Replaces direct signal-slot connections with proper event bus architecture.
"""

import logging
from typing import Dict, List, Optional

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

from automataii.core.event_bus import get_global_event_bus
from automataii.core.events import (
    MotionPathCompletedEvent,
    MotionPathClearedEvent,
    MotionPathStartedEvent,
    MotionPathPointAddedEvent,
    MotionPathCancelledEvent,
    ErrorEvent,
    InfoEvent,
)
from automataii.services.di import Injectable


logger = logging.getLogger(__name__)


class MotionPathService(Injectable):
    """
    Service for managing motion paths using event-driven architecture.
    
    This service:
    - Listens for motion path events from UI components
    - Manages motion path data state
    - Publishes events for other components to consume
    - Validates motion path operations
    """
    
    def __init__(self):
        super().__init__()
        self.event_bus = get_global_event_bus()
        self._motion_paths: Dict[str, QPainterPath] = {}
        self._active_drawing_sessions: Dict[str, List[QPointF]] = {}
        
        # Subscribe to motion path events
        self._setup_event_subscriptions()
        
        logger.info("MotionPathService initialized with event bus architecture")
    
    def _setup_event_subscriptions(self):
        """Setup event subscriptions for motion path handling."""
        self.event_bus.subscribe(
            MotionPathStartedEvent,
            self._handle_motion_path_started,
        )
        self.event_bus.subscribe(
            MotionPathPointAddedEvent,
            self._handle_motion_path_point_added,
        )
        self.event_bus.subscribe(
            MotionPathCompletedEvent,
            self._handle_motion_path_completed,
        )
        self.event_bus.subscribe(
            MotionPathCancelledEvent,
            self._handle_motion_path_cancelled,
        )
        self.event_bus.subscribe(
            MotionPathClearedEvent,
            self._handle_motion_path_cleared,
        )
    
    def _handle_motion_path_started(self, event: MotionPathStartedEvent):
        """Handle when motion path drawing starts."""
        part_name = event.part_name
        
        # Clear any existing drawing session for this part
        if part_name in self._active_drawing_sessions:
            logger.warning(f"Motion path drawing already active for part {part_name}")
            self._active_drawing_sessions[part_name].clear()
        else:
            self._active_drawing_sessions[part_name] = []
        
        logger.info(f"Started motion path drawing for part: {part_name}")
        
        # Publish info event
        self.event_bus.publish(InfoEvent(
            info_message=f"Started drawing motion path for {part_name}",
            source_component="MotionPathService"
        ))
    
    def _handle_motion_path_point_added(self, event: MotionPathPointAddedEvent):
        """Handle when a point is added to motion path."""
        part_name = event.part_name
        point = event.point
        
        if part_name not in self._active_drawing_sessions:
            logger.error(f"No active drawing session for part {part_name}")
            self.event_bus.publish(ErrorEvent(
                error_message=f"No active drawing session for part {part_name}",
                error_type="motion_path_error",
                source_component="MotionPathService"
            ))
            return
        
        # Add point to active session
        self._active_drawing_sessions[part_name].append(point)
        
        logger.debug(f"Added point {point} to motion path for part {part_name}")
    
    def _handle_motion_path_completed(self, event: MotionPathCompletedEvent):
        """Handle when motion path drawing is completed."""
        part_name = event.part_name
        path_points = event.path_points
        
        if not self._validate_motion_path(path_points):
            self.event_bus.publish(ErrorEvent(
                error_message=f"Invalid motion path for part {part_name}",
                error_type="motion_path_validation_error",
                source_component="MotionPathService"
            ))
            return
        
        # Create QPainterPath from points
        motion_path = self._create_painter_path(path_points)
        
        # Store the motion path
        self._motion_paths[part_name] = motion_path
        
        # Clean up active session
        if part_name in self._active_drawing_sessions:
            del self._active_drawing_sessions[part_name]
        
        logger.info(f"Motion path completed for part {part_name} with {len(path_points)} points")
        
        # Publish info event
        self.event_bus.publish(InfoEvent(
            info_message=f"Motion path completed for {part_name}",
            source_component="MotionPathService"
        ))
        
        # TODO: Emit event for project data manager to save the path
        # This would trigger ProjectDataManager to update its motion path data
    
    def _handle_motion_path_cancelled(self, event: MotionPathCancelledEvent):
        """Handle when motion path drawing is cancelled."""
        part_name = event.part_name
        
        # Clean up active session
        if part_name in self._active_drawing_sessions:
            del self._active_drawing_sessions[part_name]
        
        logger.info(f"Motion path drawing cancelled for part: {part_name}")
        
        # Publish info event
        self.event_bus.publish(InfoEvent(
            info_message=f"Motion path drawing cancelled for {part_name}",
            source_component="MotionPathService"
        ))
    
    def _handle_motion_path_cleared(self, event: MotionPathClearedEvent):
        """Handle when motion path is cleared for a part."""
        part_name = event.part_name
        
        # Remove from stored paths
        if part_name in self._motion_paths:
            del self._motion_paths[part_name]
        
        # Clean up any active session
        if part_name in self._active_drawing_sessions:
            del self._active_drawing_sessions[part_name]
        
        logger.info(f"Motion path cleared for part: {part_name}")
        
        # Publish info event  
        self.event_bus.publish(InfoEvent(
            info_message=f"Motion path cleared for {part_name}",
            source_component="MotionPathService"
        ))
    
    def _validate_motion_path(self, path_points: List[QPointF]) -> bool:
        """Validate motion path points."""
        if not path_points:
            return False
        
        if len(path_points) < 2:
            logger.warning("Motion path needs at least 2 points")
            return False
        
        # Check for valid coordinates
        for point in path_points:
            if not isinstance(point, QPointF):
                return False
            if not (-100000 <= point.x() <= 100000 and -100000 <= point.y() <= 100000):
                logger.warning(f"Point coordinates out of reasonable range: {point}")
                return False
        
        return True
    
    def _create_painter_path(self, path_points: List[QPointF]) -> QPainterPath:
        """Create QPainterPath from list of points."""
        path = QPainterPath()
        
        if not path_points:
            return path
        
        path.moveTo(path_points[0])
        for point in path_points[1:]:
            path.lineTo(point)
        
        return path
    
    # Public API methods
    
    def get_motion_path(self, part_name: str) -> Optional[QPainterPath]:
        """Get the motion path for a specific part."""
        return self._motion_paths.get(part_name)
    
    def has_motion_path(self, part_name: str) -> bool:
        """Check if a part has a motion path."""
        path = self._motion_paths.get(part_name)
        return path is not None and not path.isEmpty()
    
    def get_all_motion_paths(self) -> Dict[str, QPainterPath]:
        """Get all motion paths."""
        return self._motion_paths.copy()
    
    def is_drawing_active(self, part_name: str) -> bool:
        """Check if motion path drawing is active for a part."""
        return part_name in self._active_drawing_sessions
    
    def get_active_drawing_points(self, part_name: str) -> List[QPointF]:
        """Get the current points in an active drawing session."""
        return self._active_drawing_sessions.get(part_name, []).copy()
    
    def clear_all_motion_paths(self):
        """Clear all motion paths."""
        cleared_parts = list(self._motion_paths.keys())
        self._motion_paths.clear()
        self._active_drawing_sessions.clear()
        
        logger.info(f"Cleared all motion paths for parts: {cleared_parts}")
        
        # Publish events for each cleared part
        for part_name in cleared_parts:
            self.event_bus.publish(MotionPathClearedEvent(part_name=part_name))
    
    def shutdown(self):
        """Shutdown the service and cleanup resources."""
        logger.info("Shutting down MotionPathService")
        self._motion_paths.clear()
        self._active_drawing_sessions.clear()
        
        # Note: Event bus will handle unsubscribing during shutdown