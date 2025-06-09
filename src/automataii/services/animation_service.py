"""Service for handling animation operations."""

import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QPointF
from PyQt6.QtGui import QPainterPath

from automataii.services.joint_connection_manager import JointConnectionManager


class AnimationState(Enum):
    """Animation states."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    RESET = "reset"


@dataclass
class AnimationFrame:
    """Represents a single frame in animation."""
    timestamp: float
    positions: Dict[str, QPointF]  # part_name -> position
    rotations: Dict[str, float]    # part_name -> rotation angle
    joint_connected: bool = False  # Whether joint connections were applied
    parts_data: Optional[Dict[str, Dict[str, Any]]] = None  # Full part data for joint rendering


class AnimationService(QObject):
    """Service for managing animation operations.
    
    This service handles animation playback, state management,
    and frame interpolation, extracted from EditorTab.
    """
    
    # Signals
    state_changed = pyqtSignal(AnimationState)
    frame_updated = pyqtSignal(AnimationFrame)
    animation_completed = pyqtSignal()
    
    def __init__(self, fps: int = 30):
        super().__init__()
        
        self._state = AnimationState.STOPPED
        self._fps = fps
        self._timer = QTimer()
        self._timer.timeout.connect(self._on_timer_tick)
        
        # Animation data
        self._current_frame = 0
        self._total_frames = 0
        self._frames: List[AnimationFrame] = []
        self._duration_ms = 2000  # Default 2 seconds
        
        # Callbacks for custom frame processing
        self._frame_processors: List[Callable[[AnimationFrame], None]] = []
        
        # Joint connection manager
        self._joint_connection_manager: Optional[JointConnectionManager] = None
        
        logging.info(f"AnimationService initialized with {fps} FPS")
    
    @property
    def state(self) -> AnimationState:
        """Get current animation state."""
        return self._state
    
    @property
    def is_playing(self) -> bool:
        """Check if animation is currently playing."""
        return self._state == AnimationState.PLAYING
    
    @property
    def current_frame(self) -> int:
        """Get current frame number."""
        return self._current_frame
    
    @property
    def total_frames(self) -> int:
        """Get total number of frames."""
        return self._total_frames
    
    @property
    def progress(self) -> float:
        """Get animation progress (0.0 to 1.0)."""
        if self._total_frames == 0:
            return 0.0
        return self._current_frame / self._total_frames
    
    def set_duration(self, duration_ms: int) -> None:
        """Set animation duration in milliseconds."""
        if duration_ms <= 0:
            logging.warning("AnimationService: Invalid duration, using default")
            return
            
        self._duration_ms = duration_ms
        self._update_frame_count()
        logging.info(f"AnimationService: Duration set to {duration_ms}ms")
    
    def set_fps(self, fps: int) -> None:
        """Set frames per second."""
        if fps <= 0 or fps > 120:
            logging.warning("AnimationService: Invalid FPS, keeping current")
            return
            
        self._fps = fps
        self._update_frame_count()
        
        # Update timer interval if playing
        if self.is_playing:
            self._timer.setInterval(int(1000 / self._fps))
            
        logging.info(f"AnimationService: FPS set to {fps}")
    
    def load_animation_data(self, frames: List[AnimationFrame]) -> bool:
        """Load pre-computed animation frames.
        
        Args:
            frames: List of animation frames
            
        Returns:
            True if loaded successfully
        """
        if not frames:
            logging.warning("AnimationService: No frames to load")
            return False
            
        self._frames = frames
        self._total_frames = len(frames)
        self._current_frame = 0
        
        logging.info(f"AnimationService: Loaded {self._total_frames} frames")
        return True
    
    def generate_frames_from_paths(self, paths: Dict[str, QPainterPath], 
                                 initial_positions: Dict[str, QPointF]) -> bool:
        """Generate animation frames from motion paths.
        
        Args:
            paths: Dictionary mapping part names to motion paths
            initial_positions: Initial positions of parts
            
        Returns:
            True if frames generated successfully
        """
        if not paths:
            logging.warning("AnimationService: No paths provided")
            return False
            
        self._frames.clear()
        self._update_frame_count()
        
        # Generate frames by sampling paths
        for i in range(self._total_frames):
            t = i / max(1, self._total_frames - 1)  # Normalized time (0 to 1)
            timestamp = t * self._duration_ms / 1000.0
            
            positions = {}
            rotations = {}
            
            for part_name, path in paths.items():
                if path.isEmpty():
                    # Use initial position if no path
                    positions[part_name] = initial_positions.get(part_name, QPointF())
                    rotations[part_name] = 0.0
                else:
                    # Sample path at normalized time
                    percent = t * 100.0
                    point = path.pointAtPercent(percent)
                    positions[part_name] = point
                    
                    # Calculate rotation from path tangent
                    # This is simplified - actual implementation would be more complex
                    rotations[part_name] = 0.0
            
            frame = AnimationFrame(
                timestamp=timestamp,
                positions=positions,
                rotations=rotations,
                joint_connected=False
            )
            self._frames.append(frame)
        
        self._current_frame = 0
        logging.info(f"AnimationService: Generated {len(self._frames)} frames from paths")
        return True
    
    def play(self) -> bool:
        """Start or resume animation playback.
        
        Returns:
            True if started successfully
        """
        if not self._frames:
            logging.warning("AnimationService: No animation data loaded")
            return False
            
        if self._state == AnimationState.PLAYING:
            logging.info("AnimationService: Already playing")
            return True
        
        # Resume from current position or start from beginning
        if self._current_frame >= self._total_frames:
            self._current_frame = 0
        
        self._state = AnimationState.PLAYING
        self._timer.start(int(1000 / self._fps))
        
        self.state_changed.emit(self._state)
        logging.info("AnimationService: Playback started")
        return True
    
    def pause(self) -> None:
        """Pause animation playback."""
        if self._state != AnimationState.PLAYING:
            return
            
        self._timer.stop()
        self._state = AnimationState.PAUSED
        self.state_changed.emit(self._state)
        logging.info("AnimationService: Playback paused")
    
    def stop(self) -> None:
        """Stop animation and reset to beginning."""
        self._timer.stop()
        self._current_frame = 0
        self._state = AnimationState.STOPPED
        
        # Emit first frame if available
        if self._frames:
            self.frame_updated.emit(self._frames[0])
            
        self.state_changed.emit(self._state)
        logging.info("AnimationService: Playback stopped")
    
    def reset(self) -> None:
        """Reset animation to initial state."""
        self.stop()
        self._state = AnimationState.RESET
        self.state_changed.emit(self._state)
        logging.info("AnimationService: Animation reset")
    
    def seek_to_frame(self, frame_number: int) -> None:
        """Seek to specific frame.
        
        Args:
            frame_number: Frame number to seek to
        """
        if not self._frames:
            return
            
        frame_number = max(0, min(frame_number, self._total_frames - 1))
        self._current_frame = frame_number
        
        # Emit current frame
        self.frame_updated.emit(self._frames[self._current_frame])
        logging.debug(f"AnimationService: Seeked to frame {frame_number}")
    
    def seek_to_progress(self, progress: float) -> None:
        """Seek to specific progress point.
        
        Args:
            progress: Progress value (0.0 to 1.0)
        """
        if not self._frames:
            return
            
        progress = max(0.0, min(1.0, progress))
        frame_number = int(progress * (self._total_frames - 1))
        self.seek_to_frame(frame_number)
    
    def add_frame_processor(self, processor: Callable[[AnimationFrame], None]) -> None:
        """Add a custom frame processor.
        
        Args:
            processor: Function to process each frame
        """
        if processor not in self._frame_processors:
            self._frame_processors.append(processor)
            logging.debug("AnimationService: Added frame processor")
    
    def remove_frame_processor(self, processor: Callable[[AnimationFrame], None]) -> None:
        """Remove a frame processor.
        
        Args:
            processor: Function to remove
        """
        if processor in self._frame_processors:
            self._frame_processors.remove(processor)
            logging.debug("AnimationService: Removed frame processor")
    
    def clear(self) -> None:
        """Clear all animation data."""
        self.stop()
        self._frames.clear()
        self._total_frames = 0
        self._current_frame = 0
        logging.info("AnimationService: Cleared all animation data")
    
    def _update_frame_count(self) -> None:
        """Update total frame count based on duration and FPS."""
        self._total_frames = int(self._duration_ms * self._fps / 1000)
    
    def _on_timer_tick(self) -> None:
        """Handle timer tick during playback."""
        if not self._frames or self._current_frame >= self._total_frames:
            self._on_animation_complete()
            return
        
        # Get current frame
        frame = self._frames[self._current_frame]
        
        # Apply joint connections if manager is available and enabled
        if self._joint_connection_manager and self._joint_connection_manager.enabled:
            if frame.parts_data and not frame.joint_connected:
                # Apply joint connections to frame data
                modified_parts = self._joint_connection_manager.apply_to_animation_frame(
                    frame.parts_data
                )
                frame.parts_data = modified_parts
                frame.joint_connected = True
        
        # Emit frame
        self.frame_updated.emit(frame)
        
        # Process frame with custom processors
        for processor in self._frame_processors:
            try:
                processor(frame)
            except Exception as e:
                logging.error(f"AnimationService: Frame processor error: {e}")
        
        # Advance to next frame
        self._current_frame += 1
    
    def _on_animation_complete(self) -> None:
        """Handle animation completion."""
        self._timer.stop()
        self._state = AnimationState.STOPPED
        self._current_frame = 0
        
        self.animation_completed.emit()
        self.state_changed.emit(self._state)
        logging.info("AnimationService: Animation completed")
    
    def export_frames(self) -> List[Dict[str, Any]]:
        """Export animation frames as serializable data.
        
        Returns:
            List of frame dictionaries
        """
        exported_frames = []
        
        for frame in self._frames:
            frame_data = {
                'timestamp': frame.timestamp,
                'positions': {
                    part: {'x': pos.x(), 'y': pos.y()}
                    for part, pos in frame.positions.items()
                },
                'rotations': frame.rotations.copy()
            }
            exported_frames.append(frame_data)
        
        return exported_frames
    
    def set_joint_connection_manager(self, manager: Optional[JointConnectionManager]) -> None:
        """Set the joint connection manager for this animation service.
        
        Args:
            manager: Joint connection manager instance or None
        """
        self._joint_connection_manager = manager
        if manager:
            logging.info("AnimationService: Joint connection manager set")
        else:
            logging.info("AnimationService: Joint connection manager removed")
    
    def enable_joint_connections(self, enabled: bool) -> None:
        """Enable or disable joint connections for animation.
        
        Args:
            enabled: Whether to enable joint connections
        """
        if self._joint_connection_manager:
            self._joint_connection_manager.set_enabled(enabled)
            # Reset joint connection flags in frames when toggling
            for frame in self._frames:
                frame.joint_connected = False