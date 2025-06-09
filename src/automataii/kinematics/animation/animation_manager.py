"""Animation management for IK system."""

import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QElapsedTimer, QPointF

from ..core import IKState


@dataclass
class AnimationKeyframe:
    """A single keyframe in an animation."""
    time: float  # Time in seconds
    targets: Dict[str, QPointF]  # Limb name -> target position
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AnimationManager(QObject):
    """Manages IK animations and playback.
    
    This class handles animation timing, keyframe interpolation,
    and coordination with the IK solver.
    """
    
    # Signals
    frame_updated = pyqtSignal(float)  # progress (0.0-1.0)
    animation_started = pyqtSignal()
    animation_stopped = pyqtSignal()
    animation_completed = pyqtSignal()
    target_positions_updated = pyqtSignal(dict)  # limb -> position
    
    def __init__(self, ik_state: IKState, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self._ik_state = ik_state
        
        # Animation data
        self._keyframes: List[AnimationKeyframe] = []
        self._duration_ms = 2000
        self._loop = True
        self._speed = 1.0
        
        # Playback state
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_frame)
        self._elapsed_timer = QElapsedTimer()
        self._start_time = 0
        self._is_playing = False
        self._current_progress = 0.0
        
        # Callbacks
        self._frame_callback: Optional[Callable[[float], None]] = None
        
        logging.debug("AnimationManager initialized")
    
    def set_duration(self, duration_ms: int) -> None:
        """Set animation duration in milliseconds."""
        self._duration_ms = max(100, duration_ms)
        self._ik_state.set_animation_duration(duration_ms)
        logging.debug(f"Animation duration set to {duration_ms}ms")
    
    def set_loop(self, loop: bool) -> None:
        """Set whether animation should loop."""
        self._loop = loop
    
    def set_speed(self, speed: float) -> None:
        """Set playback speed multiplier."""
        self._speed = max(0.1, min(10.0, speed))
    
    def add_keyframe(self, keyframe: AnimationKeyframe) -> None:
        """Add a keyframe to the animation."""
        self._keyframes.append(keyframe)
        self._keyframes.sort(key=lambda k: k.time)
        logging.debug(f"Added keyframe at time {keyframe.time}")
    
    def clear_keyframes(self) -> None:
        """Clear all keyframes."""
        self._keyframes.clear()
        logging.debug("Cleared all keyframes")
    
    def load_motion_paths(self, motion_paths: Dict[str, Any]) -> None:
        """Load motion paths and create keyframes.
        
        Args:
            motion_paths: Dict mapping limb names to motion path data
        """
        self.clear_keyframes()
        
        # Sample paths at regular intervals
        sample_count = 20  # Number of keyframes to create
        
        for i in range(sample_count + 1):
            progress = i / sample_count
            time = progress * (self._duration_ms / 1000.0)
            
            targets = {}
            for limb_name, path_data in motion_paths.items():
                # Sample position from path
                if hasattr(path_data, 'pointAtPercent'):
                    # QPainterPath
                    point = path_data.pointAtPercent(progress)
                elif isinstance(path_data, list) and len(path_data) > 0:
                    # List of points
                    index = int(progress * (len(path_data) - 1))
                    point = path_data[index]
                else:
                    continue
                
                targets[limb_name] = point
            
            if targets:
                self.add_keyframe(AnimationKeyframe(time=time, targets=targets))
        
        logging.info(f"Loaded {len(self._keyframes)} keyframes from motion paths")
    
    def start(self) -> None:
        """Start animation playback."""
        if self._is_playing:
            return
        
        self._is_playing = True
        self._elapsed_timer.start()
        self._start_time = self._elapsed_timer.elapsed()
        
        # Start update timer at 60 FPS
        self._timer.start(16)
        
        self._ik_state.set_animating(True)
        self.animation_started.emit()
        
        logging.info("Animation started")
    
    def stop(self) -> None:
        """Stop animation playback."""
        if not self._is_playing:
            return
        
        self._is_playing = False
        self._timer.stop()
        
        self._ik_state.set_animating(False)
        self.animation_stopped.emit()
        
        logging.info("Animation stopped")
    
    def reset(self) -> None:
        """Reset animation to beginning."""
        self.stop()
        self._current_progress = 0.0
        self._ik_state.set_animation_progress(0.0)
        self.frame_updated.emit(0.0)
        
        # Update targets for first frame
        if self._keyframes:
            self.target_positions_updated.emit(self._keyframes[0].targets)
        
        logging.info("Animation reset")
    
    def set_frame_callback(self, callback: Optional[Callable[[float], None]]) -> None:
        """Set callback for frame updates.
        
        Args:
            callback: Function that takes progress (0.0-1.0) as argument
        """
        self._frame_callback = callback
    
    def _update_frame(self) -> None:
        """Update animation frame (called by timer)."""
        if not self._is_playing or not self._keyframes:
            return
        
        # Calculate elapsed time
        current_time = self._elapsed_timer.elapsed()
        elapsed_ms = (current_time - self._start_time) * self._speed
        
        # Calculate progress
        progress = elapsed_ms / self._duration_ms
        
        if progress >= 1.0:
            if self._loop:
                # Loop animation
                progress = progress % 1.0
                self._start_time = current_time - (progress * self._duration_ms / self._speed)
            else:
                # Stop at end
                progress = 1.0
                self.stop()
                self.animation_completed.emit()
        
        self._current_progress = progress
        self._ik_state.set_animation_progress(progress)
        
        # Interpolate targets
        targets = self._interpolate_targets(progress)
        if targets:
            self.target_positions_updated.emit(targets)
        
        # Emit progress
        self.frame_updated.emit(progress)
        
        # Call callback if set
        if self._frame_callback:
            self._frame_callback(progress)
    
    def _interpolate_targets(self, progress: float) -> Dict[str, QPointF]:
        """Interpolate target positions for current progress.
        
        Args:
            progress: Animation progress (0.0-1.0)
            
        Returns:
            Dict mapping limb names to interpolated positions
        """
        if not self._keyframes:
            return {}
        
        # Convert progress to time
        time = progress * (self._duration_ms / 1000.0)
        
        # Find surrounding keyframes
        prev_frame = None
        next_frame = None
        
        for i, frame in enumerate(self._keyframes):
            if frame.time <= time:
                prev_frame = frame
            else:
                next_frame = frame
                break
        
        # Handle edge cases
        if prev_frame is None:
            return self._keyframes[0].targets.copy()
        if next_frame is None:
            return self._keyframes[-1].targets.copy()
        
        # Interpolate between frames
        frame_duration = next_frame.time - prev_frame.time
        if frame_duration <= 0:
            return prev_frame.targets.copy()
        
        t = (time - prev_frame.time) / frame_duration
        
        targets = {}
        for limb_name in prev_frame.targets:
            if limb_name in next_frame.targets:
                p1 = prev_frame.targets[limb_name]
                p2 = next_frame.targets[limb_name]
                
                # Linear interpolation
                x = p1.x() + (p2.x() - p1.x()) * t
                y = p1.y() + (p2.y() - p1.y()) * t
                
                targets[limb_name] = QPointF(x, y)
        
        return targets
    
    @property
    def is_playing(self) -> bool:
        """Check if animation is currently playing."""
        return self._is_playing
    
    @property
    def current_progress(self) -> float:
        """Get current animation progress (0.0-1.0)."""
        return self._current_progress