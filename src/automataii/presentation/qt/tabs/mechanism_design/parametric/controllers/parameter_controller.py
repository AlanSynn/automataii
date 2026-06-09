"""
Parameter Controller for Real-time Mechanism Updates

Central controller managing parameter changes from interactive handles
and coordinating real-time mechanism recalculation and visualization.

Author: AI Engineering Assistant
Architecture: Observer Pattern + Command Pattern for Undo/Redo
"""

import logging
import math
import time
from collections import deque
from typing import Any, SupportsFloat, SupportsIndex, cast

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtCore import pyqtSignal as Signal

from ..handles.base_handle import BaseHandle

_FloatPayload = str | bytes | bytearray | SupportsFloat | SupportsIndex


def _finite_float(value: object, default: float) -> float:
    try:
        result = float(cast(_FloatPayload, value))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _positive_int(value: object, default: int, minimum: int = 0, maximum: int = 10_000) -> int:
    if isinstance(value, bool):
        return default
    raw = _finite_float(value, math.nan)
    if not math.isfinite(raw):
        return default
    return min(maximum, max(minimum, int(raw)))


def _bounded_float(value: object, default: float, minimum: float, maximum: float) -> float:
    raw = _finite_float(value, default)
    if raw < minimum:
        return minimum
    if raw > maximum:
        return maximum
    return raw


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

    # Signals for mechanism updates
    mechanism_update_requested = Signal(str, dict)  # mechanism_id, updated_params
    visual_refresh_requested = Signal(str)  # mechanism_id
    constraint_violation = Signal(str, str, str)  # mechanism_id, param_name, error_msg

    def __init__(
        self,
        mechanism_tab_ref,  # Reference to MechanismDesignTab
        update_throttle_ms: int = 50,  # Max update frequency
        parent=None,
    ):
        """
        Initialize parameter controller.

        Args:
            mechanism_tab_ref: Reference to parent MechanismDesignTab instance
            update_throttle_ms: Minimum milliseconds between updates (for performance)
            parent: Qt parent object
        """
        super().__init__(parent)

        self.mechanism_tab = mechanism_tab_ref
        self.update_throttle_ms = _positive_int(update_throttle_ms, 50, minimum=0)

        # Handle management
        self.active_handles: dict[str, list[BaseHandle]] = {}  # mechanism_id -> [handles]
        self.handle_registry: dict[str, BaseHandle] = {}  # handle_id -> handle

        # Update throttling for performance (Jeff Dean principle)
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._process_pending_updates)

        self.pending_updates: dict[str, dict[str, Any]] = {}  # mechanism_id -> {param: value}
        self.last_update_time: dict[str, float] = {}  # mechanism_id -> timestamp

        # Parameter change history for undo/redo (Command pattern)
        self.change_history: deque = deque(maxlen=50)  # Keep last 50 changes
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []

        # Performance monitoring
        self.update_count = 0
        self.total_update_time = 0.0

        logging.debug(f"ParameterController initialized with throttle: {update_throttle_ms}ms")

    def register_handle(self, handle: BaseHandle) -> str:
        """
        Register a handle for parameter monitoring.

        Args:
            handle: Handle instance to register

        Returns:
            Unique handle ID for tracking
        """
        handle_id = f"{handle.mechanism_id}:{handle.param_name}:{id(handle)}"

        # Store in registry
        self.handle_registry[handle_id] = handle

        # Add to mechanism's handle list
        if handle.mechanism_id not in self.active_handles:
            self.active_handles[handle.mechanism_id] = []
        self.active_handles[handle.mechanism_id].append(handle)

        # Set callback for parameter changes instead of signals
        handle.parameter_changed_callback = self._on_parameter_changed

        logging.debug(f"Registered handle: {handle_id}")
        return handle_id

    def unregister_handle(self, handle_id: str):
        """
        Unregister a handle from monitoring.

        Args:
            handle_id: Handle ID to unregister
        """
        if handle_id in self.handle_registry:
            handle = self.handle_registry[handle_id]

            # Clear callback
            handle.parameter_changed_callback = None

            # Remove from tracking
            if handle.mechanism_id in self.active_handles:
                if handle in self.active_handles[handle.mechanism_id]:
                    self.active_handles[handle.mechanism_id].remove(handle)

                # Clean up empty mechanism entries
                if not self.active_handles[handle.mechanism_id]:
                    del self.active_handles[handle.mechanism_id]

            del self.handle_registry[handle_id]
            logging.debug(f"Unregistered handle: {handle_id}")

    def get_handles_for_mechanism(self, mechanism_id: str) -> list[BaseHandle]:
        """
        Get all handles associated with a mechanism.

        Args:
            mechanism_id: Mechanism ID to query

        Returns:
            List of handles for the mechanism
        """
        return self.active_handles.get(mechanism_id, [])

    # Event Handlers (Observer Pattern)

    def _on_parameter_changed(self, mechanism_id: str, param_name: str, new_value: Any):
        """
        Handle parameter change from interactive handle.

        Args:
            mechanism_id: ID of mechanism being modified
            param_name: Name of parameter that changed
            new_value: New parameter value
        """
        if not isinstance(mechanism_id, str) or not mechanism_id:
            return
        if not isinstance(param_name, str) or not param_name:
            return
        if isinstance(new_value, float) and not math.isfinite(new_value):
            return

        # Record change for undo/redo
        change_record = {
            "mechanism_id": mechanism_id,
            "param_name": param_name,
            "new_value": new_value,
            "timestamp": time.time(),
        }
        self.change_history.append(change_record)

        # Add to pending updates (with debouncing)
        if mechanism_id not in self.pending_updates:
            self.pending_updates[mechanism_id] = {}
        self.pending_updates[mechanism_id][param_name] = new_value

        # Schedule throttled update
        self._schedule_update(mechanism_id)

        logging.debug(f"Parameter changed: {mechanism_id}:{param_name} = {new_value}")

    # Update Management (Performance Optimization)

    def _schedule_update(self, mechanism_id: str):
        """
        Schedule throttled update for mechanism.

        Args:
            mechanism_id: Mechanism to update
        """
        current_time = time.time() * 1000  # Convert to milliseconds
        last_update = self.last_update_time.get(mechanism_id, 0)

        time_since_last_update = current_time - last_update

        if time_since_last_update >= self.update_throttle_ms:
            # Update immediately if enough time has passed
            self._process_pending_updates()
        else:
            # Schedule delayed update
            remaining_time = max(1, self.update_throttle_ms - time_since_last_update)
            self.update_timer.start(int(remaining_time))

    def _process_pending_updates(self):
        """
        Process all pending parameter updates.
        """
        if not self.pending_updates:
            return

        start_time = time.time()

        pending_updates = list(self.pending_updates.items())
        self.pending_updates.clear()

        for mechanism_id, param_changes in pending_updates:
            try:
                # Apply parameter changes to mechanism
                self._apply_parameter_changes(mechanism_id, param_changes)

                # Update timestamp
                self.last_update_time[mechanism_id] = time.time() * 1000

                # Emit update signal
                self.mechanism_update_requested.emit(mechanism_id, param_changes)

            except Exception as e:
                logging.error(f"Failed to update mechanism {mechanism_id}: {e}")

        # Performance tracking
        update_time = time.time() - start_time
        self.update_count += 1
        self.total_update_time += update_time

        if self.update_count % 100 == 0:  # Log performance every 100 updates
            avg_time = self.total_update_time / self.update_count * 1000
            logging.debug(f"Average update time: {avg_time:.2f}ms ({self.update_count} updates)")

    def _apply_parameter_changes(self, mechanism_id: str, param_changes: dict[str, Any]):
        """
        Apply parameter changes to mechanism data and trigger recalculation.

        Args:
            mechanism_id: Mechanism ID
            param_changes: Dictionary of parameter changes
        """
        try:
            # Get mechanism data
            if not hasattr(self.mechanism_tab, "mechanism_layers"):
                return

            mechanism_layers = self.mechanism_tab.mechanism_layers
            if mechanism_id not in mechanism_layers:
                return

            layer_data = mechanism_layers[mechanism_id]
            if not isinstance(layer_data, dict):
                return

            # Update parameters in mechanism data
            if not isinstance(layer_data.get("params"), dict):
                layer_data["params"] = {}

            applied_any = False
            for param_name, new_value in param_changes.items():
                if isinstance(new_value, float) and not math.isfinite(new_value):
                    continue
                layer_data["params"][param_name] = new_value
                applied_any = True
            if not applied_any:
                return

            # Trigger mechanism recalculation
            self._recalculate_mechanism(mechanism_id, layer_data)

            # Notify Foundry of parameter changes (bidirectional sync)
            if hasattr(self.mechanism_tab, "_emit_mechanism_params_changed"):
                self.mechanism_tab._emit_mechanism_params_changed(mechanism_id)

        except Exception as e:
            logging.error(f"Failed to apply parameter changes: {e}")

    def _recalculate_mechanism(self, mechanism_id: str, layer_data: dict[str, Any]):
        """
        Recalculate mechanism with updated parameters.

        Args:
            mechanism_id: Mechanism ID
            layer_data: Mechanism layer data
        """
        try:
            mechanism_type = layer_data.get("type")

            if mechanism_type == "4_bar_linkage":
                self._recalculate_4bar_linkage(mechanism_id, layer_data)
            elif mechanism_type == "cam":
                self._recalculate_cam_mechanism(mechanism_id, layer_data)
            elif mechanism_type == "gear":
                self._recalculate_gear_mechanism(mechanism_id, layer_data)
            # Add other mechanism types as needed

            # Update visual representation
            self._update_mechanism_visuals(mechanism_id, layer_data)

        except Exception as e:
            logging.error(f"Failed to recalculate mechanism {mechanism_id}: {e}")

    def _recalculate_4bar_linkage(self, mechanism_id: str, layer_data: dict[str, Any]):
        """
        Recalculate 4-bar linkage with updated parameters.

        Args:
            mechanism_id: Mechanism ID
            layer_data: Mechanism layer data
        """
        # Implementation would call existing mechanism calculation functions
        # from the main mechanism_design_tab

        # For now, delegate to mechanism tab if method exists
        if hasattr(self.mechanism_tab, "_recalculate_mechanism_parameters"):
            self.mechanism_tab._recalculate_mechanism_parameters(mechanism_id, layer_data)

    def _recalculate_cam_mechanism(self, mechanism_id: str, layer_data: dict[str, Any]):
        """Recalculate cam mechanism with updated parameters and enforce gravity physics."""
        try:
            params = layer_data.get("params", {})
            if not isinstance(params, dict) or not params:
                return

            # Extract CAM parameters with gravity physics validation
            base_radius = _bounded_float(params.get("base_radius", 25.0), 25.0, 10.0, 80.0)
            eccentricity = _bounded_float(params.get("eccentricity", 10.0), 10.0, 2.0, 30.0)
            rod_length = _bounded_float(params.get("follower_rod_length", 40.0), 40.0, 15.0, 150.0)

            # Update parameters with constrained values (gravity physics enforcement)
            params["base_radius"] = base_radius
            params["eccentricity"] = eccentricity
            params["follower_rod_length"] = rod_length

            # Calculate derived parameters for gravity-compliant CAM
            # CAM center position with eccentricity offset
            cam_center_x = eccentricity
            cam_center_y = 0.0  # CAM at baseline level

            # Follower position above CAM (gravity constraint)
            follower_y = cam_center_y - (base_radius + rod_length)  # Above CAM

            # Store calculated positions for visual updates
            params["cam_center"] = [cam_center_x, cam_center_y]
            params["follower_position"] = [cam_center_x, follower_y]

            logging.debug(
                f"[CAM_PARAM] Updated {mechanism_id}: radius={base_radius:.1f}, "
                f"ecc={eccentricity:.1f}, rod={rod_length:.1f}"
            )

            # Trigger visual refresh through mechanism tab
            if hasattr(self.mechanism_tab, "_regenerate_cam_mechanism_realtime"):
                self.mechanism_tab._regenerate_cam_mechanism_realtime(mechanism_id, layer_data)

        except Exception as e:
            logging.error(f"[CAM_PARAM] Failed to recalculate CAM {mechanism_id}: {e}")

    def _recalculate_gear_mechanism(self, mechanism_id: str, layer_data: dict[str, Any]):
        """Recalculate gear mechanism - placeholder for implementation."""
        pass

    def _update_mechanism_visuals(self, mechanism_id: str, layer_data: dict[str, Any]):
        """
        Update mechanism visual representation.

        Args:
            mechanism_id: Mechanism ID
            layer_data: Mechanism layer data
        """
        try:
            # Emit signal for visual refresh
            self.visual_refresh_requested.emit(mechanism_id)

            # Call mechanism tab's visual update if available
            if hasattr(self.mechanism_tab, "_update_mechanism_visuals_realtime"):
                self.mechanism_tab._update_mechanism_visuals_realtime(mechanism_id, layer_data)

        except Exception as e:
            logging.error(f"Failed to update visuals for {mechanism_id}: {e}")

    # Undo/Redo System (Command Pattern)

    def _capture_mechanism_state(self, mechanism_id: str):
        """
        Capture current mechanism state for undo functionality.

        Args:
            mechanism_id: Mechanism to capture
        """
        try:
            if hasattr(self.mechanism_tab, "mechanism_layers"):
                mechanism_layers = self.mechanism_tab.mechanism_layers
                if mechanism_id in mechanism_layers:
                    # Deep copy current state
                    import copy

                    current_state = copy.deepcopy(mechanism_layers[mechanism_id])

                    # Store in undo stack
                    undo_entry = {
                        "mechanism_id": mechanism_id,
                        "state": current_state,
                        "timestamp": time.time(),
                    }
                    self.undo_stack.append(undo_entry)

                    # Clear redo stack when new action is performed
                    self.redo_stack.clear()

                    # Limit undo stack size
                    if len(self.undo_stack) > 20:
                        self.undo_stack.pop(0)

        except Exception as e:
            logging.error(f"Failed to capture mechanism state: {e}")

    def _finalize_undo_state(self, mechanism_id: str):
        """
        Finalize undo state after manipulation is complete.

        Args:
            mechanism_id: Mechanism ID
        """
        # Implementation for finalizing undo state
        # This could involve cleaning up intermediate states
        pass

    def _capture_current_state_for_redo(self, mechanism_id: str):
        """Capture current state for redo stack."""
        # Similar to _capture_mechanism_state but for redo stack
        pass

    def _restore_mechanism_state(self, mechanism_id: str, state: dict[str, Any]):
        """Restore mechanism to previous state."""
        # Implementation would restore mechanism state and update visuals
        pass

    def __repr__(self) -> str:
        """String representation for debugging."""
        active_mechs = len(self.active_handles)
        total_handles = len(self.handle_registry)
        return f"ParameterController({active_mechs} mechanisms, {total_handles} handles)"
