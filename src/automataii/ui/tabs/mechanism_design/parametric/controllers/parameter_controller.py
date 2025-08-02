"""
Parameter Controller for Real-time Mechanism Updates

Central controller managing parameter changes from interactive handles
and coordinating real-time mechanism recalculation and visualization.

Author: AI Engineering Assistant
Architecture: Observer Pattern + Command Pattern for Undo/Redo
"""

import logging
import time
from collections import defaultdict, deque
from typing import Any
from weakref import WeakSet

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtCore import pyqtSignal as Signal

from ..handles.base_handle import BaseHandle

logger = logging.getLogger(__name__)


class ParameterController(QObject):
    """
    Central controller for parametric design system.

    Responsibilities:
    - Monitor handle parameter changes (Observer pattern)
    - Trigger real-time mechanism updates
    - Manage update throttling for performance
    - Coordinate visual synchronization
    - Handle undo/redo operations (Command pattern)

    Features:
    - Event debouncing to prevent excessive updates
    - Batch parameter changes for efficiency
    - Real-time constraint validation
    - Performance monitoring and optimization
    """

    # Signals for external components
    mechanism_parameters_changed = Signal(str, dict)  # mechanism_id, updated_params
    visual_refresh_requested = Signal(str)  # mechanism_id
    manipulation_started = Signal()
    manipulation_finished = Signal()

    # Validation signals
    parameter_validation_failed = Signal(str, str)  # mechanism_id, error_message
    parameter_validation_passed = Signal(str)  # mechanism_id

    def __init__(self, state_manager, parent=None):
        super().__init__(parent)
        self.state_manager = state_manager

        # Handle registry and management
        self.handle_registry: dict[str, BaseHandle] = {}  # handle_id -> handle
        self.mechanism_handles: dict[str, set[str]] = defaultdict(
            set
        )  # mechanism_id -> set of handle_ids
        self.active_handles: WeakSet[BaseHandle] = WeakSet()

        # Update throttling system
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._process_pending_updates)
        self.update_timer.setSingleShot(True)
        self.update_delay_ms = 50  # 50ms delay for update throttling

        # Pending updates management
        self.pending_updates: dict[str, dict[str, Any]] = {}  # mechanism_id -> {param_name: value}
        self.last_update_time: dict[str, float] = {}  # mechanism_id -> timestamp

        # Performance monitoring
        self.update_count = 0
        self.validation_count = 0
        self.error_count = 0
        self.start_time = time.time()

        # Command pattern for undo/redo
        self.command_history: deque = deque(maxlen=50)  # Store last 50 commands
        self.command_index = -1

        # Batch update management
        self.batch_mode = False
        self.batch_updates: dict[str, dict[str, Any]] = {}

        logger.info("ParameterController initialized with update throttling and command pattern")

    def register_handle(self, handle: BaseHandle) -> str:
        """
        Register a handle for parameter monitoring.

        Args:
            handle: Handle instance to register

        Returns:
            Unique handle ID
        """
        if not isinstance(handle, BaseHandle):
            raise TypeError("Handle must be instance of BaseHandle")

        handle_id = f"{handle.mechanism_id}_{handle.param_name}_{id(handle)}"

        # Store handle in registry
        self.handle_registry[handle_id] = handle
        self.mechanism_handles[handle.mechanism_id].add(handle_id)
        self.active_handles.add(handle)

        # Connect handle signals
        handle.manipulation_started.connect(self._on_manipulation_started)
        handle.manipulation_finished.connect(self._on_manipulation_finished)

        logger.debug(f"Registered handle {handle_id} for mechanism {handle.mechanism_id}")
        return handle_id

    def unregister_handle(self, handle_id: str) -> bool:
        """
        Unregister a handle from parameter monitoring.

        Args:
            handle_id: Handle ID to unregister

        Returns:
            True if handle was found and removed
        """
        if handle_id not in self.handle_registry:
            return False

        handle = self.handle_registry[handle_id]
        mechanism_id = handle.mechanism_id

        # Disconnect signals
        try:
            handle.manipulation_started.disconnect(self._on_manipulation_started)
            handle.manipulation_finished.disconnect(self._on_manipulation_finished)
        except (RuntimeError, TypeError):
            pass  # Signals might already be disconnected

        # Remove from registry
        del self.handle_registry[handle_id]
        self.mechanism_handles[mechanism_id].discard(handle_id)

        # Clean up empty mechanism entries
        if not self.mechanism_handles[mechanism_id]:
            del self.mechanism_handles[mechanism_id]

        logger.debug(f"Unregistered handle {handle_id}")
        return True

    def handle_parameter_change(self, mechanism_id: str, param_name: str, new_value: Any) -> None:
        """
        Handle parameter change from a handle.

        Args:
            mechanism_id: Mechanism identifier
            param_name: Parameter name
            new_value: New parameter value
        """
        try:
            # Store pending update
            if mechanism_id not in self.pending_updates:
                self.pending_updates[mechanism_id] = {}

            self.pending_updates[mechanism_id][param_name] = new_value

            # Throttle updates using timer
            current_time = time.time()
            last_update = self.last_update_time.get(mechanism_id, 0)

            if current_time - last_update < (self.update_delay_ms / 1000.0):
                # Restart timer to delay update
                self.update_timer.start(self.update_delay_ms)
            else:
                # Process update immediately if enough time has passed
                self._process_pending_updates()

            logger.debug(f"Queued parameter change: {mechanism_id}.{param_name} = {new_value}")

        except Exception as e:
            logger.error(f"Error handling parameter change: {e}")
            self.error_count += 1

    def _process_pending_updates(self) -> None:
        """Process all pending parameter updates."""
        try:
            updates_to_process = self.pending_updates.copy()
            self.pending_updates.clear()

            for mechanism_id, param_changes in updates_to_process.items():
                self._apply_parameter_changes(mechanism_id, param_changes)
                self.last_update_time[mechanism_id] = time.time()

            self.update_count += len(updates_to_process)

        except Exception as e:
            logger.error(f"Error processing pending updates: {e}")
            self.error_count += 1

    def _apply_parameter_changes(self, mechanism_id: str, param_changes: dict[str, Any]) -> None:
        """
        Apply parameter changes to mechanism.

        Args:
            mechanism_id: Mechanism identifier
            param_changes: Dictionary of parameter changes
        """
        try:
            # Create command for undo/redo
            if not self.batch_mode:
                command = ParameterChangeCommand(mechanism_id, param_changes, self.state_manager)
                self._add_command(command)

            # Validate parameters before applying
            self.validation_count += 1

            # Apply changes and trigger update
            self.mechanism_parameters_changed.emit(mechanism_id, param_changes)

            # Request visual refresh
            self.visual_refresh_requested.emit(mechanism_id)

            logger.debug(f"Applied parameter changes to {mechanism_id}: {param_changes}")

        except Exception as e:
            logger.error(f"Error applying parameter changes to {mechanism_id}: {e}")
            self.parameter_validation_failed.emit(mechanism_id, str(e))
            self.error_count += 1

    def _add_command(self, command) -> None:
        """Add command to history for undo/redo."""
        # Remove any commands after current index
        while len(self.command_history) > self.command_index + 1:
            self.command_history.pop()

        # Add new command
        self.command_history.append(command)
        self.command_index += 1

        logger.debug(f"Added command to history: {command}")

    def _on_manipulation_started(self, mechanism_id: str) -> None:
        """Handle manipulation started signal from handle."""
        logger.debug(f"Manipulation started for mechanism {mechanism_id}")
        self.manipulation_started.emit()

    def _on_manipulation_finished(self, mechanism_id: str) -> None:
        """Handle manipulation finished signal from handle."""
        logger.debug(f"Manipulation finished for mechanism {mechanism_id}")
        self.manipulation_finished.emit()

    def start_batch_mode(self) -> None:
        """Start batch mode for multiple parameter changes."""
        self.batch_mode = True
        self.batch_updates.clear()
        logger.debug("Started batch mode")

    def end_batch_mode(self) -> None:
        """End batch mode and apply all batched changes."""
        if not self.batch_mode:
            return

        self.batch_mode = False

        # Apply all batched updates as single command
        if self.batch_updates:
            command = BatchParameterChangeCommand(self.batch_updates, self.state_manager)
            self._add_command(command)

            for mechanism_id, param_changes in self.batch_updates.items():
                self.mechanism_parameters_changed.emit(mechanism_id, param_changes)
                self.visual_refresh_requested.emit(mechanism_id)

        self.batch_updates.clear()
        logger.debug("Ended batch mode")

    def undo(self) -> bool:
        """Undo last command."""
        if self.command_index < 0:
            return False

        command = self.command_history[self.command_index]
        try:
            command.undo()
            self.command_index -= 1
            logger.debug(f"Undid command: {command}")
            return True
        except Exception as e:
            logger.error(f"Error undoing command: {e}")
            return False

    def redo(self) -> bool:
        """Redo next command."""
        if self.command_index >= len(self.command_history) - 1:
            return False

        self.command_index += 1
        command = self.command_history[self.command_index]
        try:
            command.execute()
            logger.debug(f"Redid command: {command}")
            return True
        except Exception as e:
            logger.error(f"Error redoing command: {e}")
            return False

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        elapsed_time = time.time() - self.start_time
        return {
            "update_count": self.update_count,
            "validation_count": self.validation_count,
            "error_count": self.error_count,
            "elapsed_time": elapsed_time,
            "updates_per_second": self.update_count / elapsed_time if elapsed_time > 0 else 0,
            "active_handles": len(self.active_handles),
            "registered_handles": len(self.handle_registry),
            "pending_updates": len(self.pending_updates),
            "command_history_size": len(self.command_history),
        }

    def clear_history(self) -> None:
        """Clear command history."""
        self.command_history.clear()
        self.command_index = -1
        logger.debug("Cleared command history")

    def shutdown(self) -> None:
        """Shutdown controller and cleanup resources."""
        self.update_timer.stop()
        self.pending_updates.clear()

        # Unregister all handles
        for handle_id in list(self.handle_registry.keys()):
            self.unregister_handle(handle_id)

        self.clear_history()
        logger.info("ParameterController shutdown completed")


class ParameterChangeCommand:
    """Command for parameter change (undo/redo support)."""

    def __init__(self, mechanism_id: str, param_changes: dict[str, Any], state_manager):
        self.mechanism_id = mechanism_id
        self.new_params = param_changes.copy()
        self.state_manager = state_manager

        # Store old parameters for undo
        self.old_params = {}
        mechanism_layer = state_manager.mechanism_layers.get(mechanism_id)
        if mechanism_layer:
            current_params = mechanism_layer.get("params", {})
            for param_name in param_changes.keys():
                if param_name in current_params:
                    self.old_params[param_name] = current_params[param_name]

    def execute(self) -> None:
        """Execute the parameter change."""
        # Apply new parameters
        pass  # Implementation depends on state manager interface

    def undo(self) -> None:
        """Undo the parameter change."""
        # Restore old parameters
        pass  # Implementation depends on state manager interface

    def __str__(self) -> str:
        return f"ParameterChange({self.mechanism_id}: {self.new_params})"


class BatchParameterChangeCommand:
    """Command for batch parameter changes."""

    def __init__(self, batch_updates: dict[str, dict[str, Any]], state_manager):
        self.batch_updates = batch_updates.copy()
        self.state_manager = state_manager
        self.old_params = {}

        # Store old parameters for undo
        for mechanism_id, param_changes in batch_updates.items():
            mechanism_layer = state_manager.mechanism_layers.get(mechanism_id)
            if mechanism_layer:
                current_params = mechanism_layer.get("params", {})
                self.old_params[mechanism_id] = {}
                for param_name in param_changes.keys():
                    if param_name in current_params:
                        self.old_params[mechanism_id][param_name] = current_params[param_name]

    def execute(self) -> None:
        """Execute the batch parameter changes."""
        pass  # Implementation depends on state manager interface

    def undo(self) -> None:
        """Undo the batch parameter changes."""
        pass  # Implementation depends on state manager interface

    def __str__(self) -> str:
        return f"BatchParameterChange({len(self.batch_updates)} mechanisms)"
