"""
Parameter Controller for Real-time Mechanism Updates

Central controller managing parameter changes from interactive handles
and coordinating real-time mechanism recalculation and visualization.

Author: AI Engineering Assistant
Architecture: Observer Pattern + Command Pattern for Undo/Redo
"""

from typing import Dict, Any, List, Optional, Callable
import logging
from collections import deque
import time

from PyQt6.QtCore import QObject, pyqtSignal as Signal, QTimer, QPointF
from PyQt6.QtWidgets import QGraphicsScene

from ..handles.base_handle import BaseHandle


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
    visual_refresh_requested = Signal(str)          # mechanism_id
    constraint_violation = Signal(str, str, str)    # mechanism_id, param_name, error_msg
    
    def __init__(self, 
                 mechanism_tab_ref,  # Reference to MechanismDesignTab
                 update_throttle_ms: int = 50,  # Max update frequency
                 parent=None):
        """
        Initialize parameter controller.
        
        Args:
            mechanism_tab_ref: Reference to parent MechanismDesignTab instance
            update_throttle_ms: Minimum milliseconds between updates (for performance)
            parent: Qt parent object
        """
        super().__init__(parent)
        
        self.mechanism_tab = mechanism_tab_ref
        self.update_throttle_ms = update_throttle_ms
        
        # Handle management
        self.active_handles: Dict[str, List[BaseHandle]] = {}  # mechanism_id -> [handles]
        self.handle_registry: Dict[str, BaseHandle] = {}       # handle_id -> handle
        
        # Update throttling for performance (Jeff Dean principle)
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._process_pending_updates)
        
        self.pending_updates: Dict[str, Dict[str, Any]] = {}   # mechanism_id -> {param: value}
        self.last_update_time: Dict[str, float] = {}           # mechanism_id -> timestamp
        
        # Parameter change history for undo/redo (Command pattern)
        self.change_history: deque = deque(maxlen=50)  # Keep last 50 changes
        self.undo_stack: List[Dict] = []
        self.redo_stack: List[Dict] = []
        
        # Performance monitoring
        self.update_count = 0
        self.total_update_time = 0.0
        
        logging.debug("ParameterController initialized with throttle: {}ms".format(update_throttle_ms))
    
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
    
    def get_handles_for_mechanism(self, mechanism_id: str) -> List[BaseHandle]:
        """
        Get all handles associated with a mechanism.
        
        Args:
            mechanism_id: Mechanism ID to query
            
        Returns:
            List of handles for the mechanism
        """
        return self.active_handles.get(mechanism_id, [])
    
    def enable_handles_for_mechanism(self, mechanism_id: str, enabled: bool):
        """
        Enable or disable all handles for a mechanism.
        
        Args:
            mechanism_id: Mechanism ID
            enabled: Whether to enable or disable handles
        """
        handles = self.get_handles_for_mechanism(mechanism_id)
        for handle in handles:
            handle.setEnabled(enabled)
        
        logging.debug(f"{'Enabled' if enabled else 'Disabled'} {len(handles)} handles for {mechanism_id}")
    
    # Event Handlers (Observer Pattern)
    
    def _on_parameter_changed(self, mechanism_id: str, param_name: str, new_value: Any):
        """
        Handle parameter change from interactive handle.
        
        Args:
            mechanism_id: ID of mechanism being modified
            param_name: Name of parameter that changed
            new_value: New parameter value
        """
        # Record change for undo/redo
        change_record = {
            'mechanism_id': mechanism_id,
            'param_name': param_name, 
            'new_value': new_value,
            'timestamp': time.time()
        }
        self.change_history.append(change_record)
        
        # Add to pending updates (with debouncing)
        if mechanism_id not in self.pending_updates:
            self.pending_updates[mechanism_id] = {}
        self.pending_updates[mechanism_id][param_name] = new_value
        
        # Schedule throttled update
        self._schedule_update(mechanism_id)
        
        logging.debug(f"Parameter changed: {mechanism_id}:{param_name} = {new_value}")
    
    def _on_manipulation_started(self, mechanism_id: str):
        """
        Handle start of manipulation session.
        
        Args:
            mechanism_id: ID of mechanism being manipulated
        """
        # Capture initial state for undo
        self._capture_mechanism_state(mechanism_id)
        
        # Optionally disable animation during manipulation
        if hasattr(self.mechanism_tab, '_on_stop_animation'):
            self.mechanism_tab._on_stop_animation()
        
        logging.debug(f"Manipulation started for {mechanism_id}")
    
    def _on_manipulation_finished(self, mechanism_id: str):
        """
        Handle end of manipulation session.
        
        Args:
            mechanism_id: ID of mechanism that was manipulated
        """
        # Force immediate update for final state
        self._process_pending_updates()
        
        # Add to undo stack
        self._finalize_undo_state(mechanism_id)
        
        logging.debug(f"Manipulation finished for {mechanism_id}")
    
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
        
        for mechanism_id, param_changes in self.pending_updates.items():
            try:
                # Apply parameter changes to mechanism
                self._apply_parameter_changes(mechanism_id, param_changes)
                
                # Update timestamp
                self.last_update_time[mechanism_id] = time.time() * 1000
                
                # Emit update signal
                self.mechanism_update_requested.emit(mechanism_id, param_changes)
                
            except Exception as e:
                logging.error(f"Failed to update mechanism {mechanism_id}: {e}")
        
        # Clear pending updates
        self.pending_updates.clear()
        
        # Performance tracking
        update_time = time.time() - start_time
        self.update_count += 1
        self.total_update_time += update_time
        
        if self.update_count % 100 == 0:  # Log performance every 100 updates
            avg_time = self.total_update_time / self.update_count * 1000
            logging.debug(f"Average update time: {avg_time:.2f}ms ({self.update_count} updates)")
    
    def _apply_parameter_changes(self, mechanism_id: str, param_changes: Dict[str, Any]):
        """
        Apply parameter changes to mechanism data and trigger recalculation.
        
        Args:
            mechanism_id: Mechanism ID
            param_changes: Dictionary of parameter changes
        """
        try:
            # Get mechanism data
            if not hasattr(self.mechanism_tab, 'mechanism_layers'):
                return
                
            mechanism_layers = self.mechanism_tab.mechanism_layers
            if mechanism_id not in mechanism_layers:
                return
                
            layer_data = mechanism_layers[mechanism_id]
            
            # Update parameters in mechanism data
            if "params" not in layer_data:
                layer_data["params"] = {}
            
            for param_name, new_value in param_changes.items():
                layer_data["params"][param_name] = new_value
            
            # Trigger mechanism recalculation
            self._recalculate_mechanism(mechanism_id, layer_data)
            
        except Exception as e:
            logging.error(f"Failed to apply parameter changes: {e}")
    
    def _recalculate_mechanism(self, mechanism_id: str, layer_data: Dict[str, Any]):
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
    
    def _recalculate_4bar_linkage(self, mechanism_id: str, layer_data: Dict[str, Any]):
        """
        Recalculate 4-bar linkage with updated parameters.
        
        Args:
            mechanism_id: Mechanism ID
            layer_data: Mechanism layer data
        """
        # Implementation would call existing mechanism calculation functions
        # from the main mechanism_design_tab
        
        # For now, delegate to mechanism tab if method exists
        if hasattr(self.mechanism_tab, '_recalculate_mechanism_parameters'):
            self.mechanism_tab._recalculate_mechanism_parameters(mechanism_id, layer_data)
    
    def _recalculate_cam_mechanism(self, mechanism_id: str, layer_data: Dict[str, Any]):
        """Recalculate cam mechanism - placeholder for implementation."""
        pass
    
    def _recalculate_gear_mechanism(self, mechanism_id: str, layer_data: Dict[str, Any]):
        """Recalculate gear mechanism - placeholder for implementation."""
        pass
    
    def _update_mechanism_visuals(self, mechanism_id: str, layer_data: Dict[str, Any]):
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
            if hasattr(self.mechanism_tab, '_update_mechanism_visuals_realtime'):
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
            if hasattr(self.mechanism_tab, 'mechanism_layers'):
                mechanism_layers = self.mechanism_tab.mechanism_layers
                if mechanism_id in mechanism_layers:
                    # Deep copy current state
                    import copy
                    current_state = copy.deepcopy(mechanism_layers[mechanism_id])
                    
                    # Store in undo stack
                    undo_entry = {
                        'mechanism_id': mechanism_id,
                        'state': current_state,
                        'timestamp': time.time()
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
    
    def undo_last_change(self) -> bool:
        """
        Undo the last parameter change.
        
        Returns:
            True if undo was successful, False otherwise
        """
        if not self.undo_stack:
            return False
            
        try:
            # Get last state
            undo_entry = self.undo_stack.pop()
            mechanism_id = undo_entry['mechanism_id']
            
            # Capture current state for redo
            self._capture_current_state_for_redo(mechanism_id)
            
            # Restore previous state
            self._restore_mechanism_state(mechanism_id, undo_entry['state'])
            
            return True
            
        except Exception as e:
            logging.error(f"Undo failed: {e}")
            return False
    
    def redo_last_change(self) -> bool:
        """
        Redo the last undone change.
        
        Returns:
            True if redo was successful, False otherwise  
        """
        if not self.redo_stack:
            return False
            
        try:
            # Get redo state
            redo_entry = self.redo_stack.pop()
            mechanism_id = redo_entry['mechanism_id']
            
            # Capture current state for undo
            self._capture_mechanism_state(mechanism_id)
            
            # Restore redo state
            self._restore_mechanism_state(mechanism_id, redo_entry['state'])
            
            return True
            
        except Exception as e:
            logging.error(f"Redo failed: {e}")
            return False
    
    def _capture_current_state_for_redo(self, mechanism_id: str):
        """Capture current state for redo stack."""
        # Similar to _capture_mechanism_state but for redo stack
        pass
    
    def _restore_mechanism_state(self, mechanism_id: str, state: Dict[str, Any]):
        """Restore mechanism to previous state."""
        # Implementation would restore mechanism state and update visuals
        pass
    
    def get_performance_stats(self) -> Dict[str, float]:
        """
        Get performance statistics for monitoring.
        
        Returns:
            Dictionary with performance metrics
        """
        if self.update_count == 0:
            return {'average_update_time_ms': 0, 'total_updates': 0}
            
        return {
            'average_update_time_ms': (self.total_update_time / self.update_count) * 1000,
            'total_updates': self.update_count,
            'total_time_seconds': self.total_update_time
        }
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        active_mechs = len(self.active_handles)
        total_handles = len(self.handle_registry)
        return f"ParameterController({active_mechs} mechanisms, {total_handles} handles)"