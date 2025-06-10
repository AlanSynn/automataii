"""Handler for simulation operations."""

import logging
from typing import Dict, Any

from PyQt6.QtCore import QObject, pyqtSignal

from automataii.gui.tabs.editor.state import EditorState, SimulationState
from automataii.services import AnimationService, AnimationState
from automataii.events import event_bus, AnimationStateChangedEvent
from automataii.interfaces import IKManagerInterface


class SimulationHandler(QObject):
    """Handles simulation and animation operations."""

    # Signals
    simulation_started = pyqtSignal()
    simulation_stopped = pyqtSignal()
    simulation_paused = pyqtSignal()
    simulation_reset = pyqtSignal()
    frame_updated = pyqtSignal(dict)  # frame_data

    def __init__(
        self,
        state: EditorState,
        animation_service: AnimationService,
        ik_manager: IKManagerInterface
    ):
        super().__init__()
        self._state = state
        self._animation_service = animation_service
        self._ik_manager = ik_manager

        # Connect to service signals
        self._animation_service.state_changed.connect(self._on_animation_state_changed)
        self._animation_service.frame_updated.connect(self._on_frame_updated)

        logging.debug("SimulationHandler initialized")

    def play(self) -> bool:
        """Start simulation playback.

        Returns:
            True if started successfully
        """
        # Prevent multiple simultaneous play calls
        if self._state.simulation_state.value == "playing":
            print("SimulationHandler: Already playing, ignoring play request")
            return True
            
        if not self._state.can_animate():
            print("SimulationHandler: Cannot animate in current state")
            return False

        # Get motion paths
        paths = {}
        initial_positions = {}

        for part_name, part_state in self._state.get_parts_with_paths().items():
            if part_state.motion_path:
                paths[part_name] = part_state.motion_path
                initial_positions[part_name] = part_state.position

        if not paths:
            print("SimulationHandler: No motion paths to animate")
            return False

        print(f"SimulationHandler: Starting animation with {len(paths)} paths")
        print(f"SimulationHandler: IK manager type: {type(self._ik_manager)}")

        # Update motion paths in IK system FIRST
        try:
            self._ik_manager.update_motion_paths(paths)
            print("SimulationHandler: Motion paths sent to IK system")
        except Exception as e:
            print(f"SimulationHandler: Error updating motion paths in IK: {e}")

        # Generate frames and start animation
        if self._animation_service.generate_frames_from_paths(paths, initial_positions):
            print("SimulationHandler: Frames generated successfully")
            
            # Start IK manager animation (IKCoordinator via IKServiceAdapter)
            try:
                self._ik_manager.start_animation()
                print("SimulationHandler: IK animation started")
            except Exception as e:
                print(f"SimulationHandler: Error starting IK animation: {e}")

            # Start animation service
            if self._animation_service.play():
                print("SimulationHandler: Animation service playing")
                return True
            else:
                print("SimulationHandler: Animation service failed to play")

        print("SimulationHandler: Failed to generate frames")
        return False

    def pause(self) -> None:
        """Pause simulation."""
        self._animation_service.pause()
        self._ik_manager.stop_animation()
        logging.info("SimulationHandler: Simulation paused")

    def stop(self) -> None:
        """Stop simulation."""
        self._animation_service.stop()
        self._ik_manager.stop_animation()
        logging.info("SimulationHandler: Simulation stopped")

    def reset(self) -> None:
        """Reset simulation to initial state."""
        self._animation_service.reset()
        self._ik_manager.reset_animation_state()

        # Reset part positions to initial
        for part_state in self._state.parts.values():
            # Reset logic would go here
            pass

        logging.info("SimulationHandler: Simulation reset")

    def seek(self, progress: float) -> None:
        """Seek to specific progress point.

        Args:
            progress: Progress value (0.0 to 1.0)
        """
        self._animation_service.seek_to_progress(progress)

    def set_duration(self, duration_ms: int) -> None:
        """Set animation duration.

        Args:
            duration_ms: Duration in milliseconds
        """
        self._animation_service.set_duration(duration_ms)
        self._ik_manager.set_animation_duration(duration_ms)
        logging.info(f"SimulationHandler: Duration set to {duration_ms}ms")

    def get_progress(self) -> float:
        """Get current simulation progress."""
        return self._animation_service.progress

    def is_playing(self) -> bool:
        """Check if simulation is playing."""
        return self._animation_service.is_playing

    def _on_animation_state_changed(self, state: AnimationState):
        """Handle animation state changes."""
        # Map animation state to simulation state
        state_map = {
            AnimationState.PLAYING: SimulationState.PLAYING,
            AnimationState.PAUSED: SimulationState.PAUSED,
            AnimationState.STOPPED: SimulationState.STOPPED,
            AnimationState.RESET: SimulationState.RESET
        }

        new_sim_state = state_map.get(state, SimulationState.STOPPED)
        previous_state = self._state.simulation_state
        self._state.simulation_state = new_sim_state

        # Emit appropriate signal
        if new_sim_state == SimulationState.PLAYING:
            self.simulation_started.emit()
        elif new_sim_state == SimulationState.STOPPED:
            self.simulation_stopped.emit()
        elif new_sim_state == SimulationState.PAUSED:
            self.simulation_paused.emit()
        elif new_sim_state == SimulationState.RESET:
            self.simulation_reset.emit()

        # Publish event
        event = AnimationStateChangedEvent(
            state=new_sim_state.value,
            previous_state=previous_state.value,
            source="simulation_handler"
        )
        event_bus.publish(event)

    def _on_frame_updated(self, frame):
        """Handle frame updates from animation service."""
        # Update part positions in state
        for part_name, position in frame.positions.items():
            if part_name in self._state.parts:
                self._state.parts[part_name].position = position

        # Update part rotations
        for part_name, rotation in frame.rotations.items():
            if part_name in self._state.parts:
                self._state.parts[part_name].rotation = rotation

        # Update progress
        self._state.simulation_progress = self._animation_service.progress

        # Emit signal with frame data
        frame_data = {
            'timestamp': frame.timestamp,
            'positions': frame.positions,
            'rotations': frame.rotations,
            'progress': self._state.simulation_progress
        }
        self.frame_updated.emit(frame_data)
        
        # Also trigger visual update through IK system if available
        if hasattr(self._ik_manager, 'character_visuals_updated'):
            # Convert frame data to part transforms format expected by IK system
            part_transforms = {}
            for part_name in frame.positions:
                if part_name in self._state.parts:
                    part_state = self._state.parts[part_name]
                    part_transforms[part_name] = {
                        'position': frame.positions.get(part_name, part_state.position),
                        'rotation': frame.rotations.get(part_name, 0.0),
                        'anchor_joint_id': part_state.anchor_joint_id
                    }
            # Emit the visual update signal
            self._ik_manager.character_visuals_updated.emit(part_transforms)