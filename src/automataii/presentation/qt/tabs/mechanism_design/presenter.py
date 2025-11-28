"""
MechanismDesignPresenter - MVP Presenter for MechanismDesignTab.

Extracted from MechanismDesignTab as part of MVP architecture refactoring.
Owns all business state and coordination logic, leaving View as pure UI.

Design Pattern: MVP (Model-View-Presenter) - Passive View variant
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np
from PyQt6.QtCore import QElapsedTimer, QObject, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene

from automataii.domain.kinematics.mechanism import MechanismCandidate
from automataii.presentation.qt.tabs.mechanism_design.services import (
    AnchorMovementHandler,
    AnchorPositionService,
    HandlePositionCoordinator,
    MechanismInstantiationService,
    TransformService,
    VisualItemManager,
)
from automataii.presentation.qt.tabs.mechanism_design.path_trace_manager import (
    PathTraceManager,
    PathTraceConfig,
)
from automataii.services.mechanism_service import MechanismService
from automataii.services.skeleton_service import SkeletonService

if TYPE_CHECKING:
    from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab


class MechanismDesignPresenter(QObject):
    """
    Presenter for MechanismDesignTab following MVP pattern.

    Responsibilities:
    - Own all business state (mechanism_layers, animation_time, etc.)
    - Coordinate between services
    - Handle tab lifecycle (activate/deactivate)
    - Process user actions and update View

    The View (Tab) becomes a thin wrapper that:
    - Owns Qt widgets
    - Captures user input → calls Presenter methods
    - Receives Presenter signals → updates display
    """

    # Signals for View updates
    view_update_requested = pyqtSignal(str, object)  # update_type, data
    animation_state_changed = pyqtSignal(bool)  # is_playing
    mechanism_list_changed = pyqtSignal(list)  # mechanism items

    def __init__(self, tab: "MechanismDesignTab", parent: QObject | None = None) -> None:
        """
        Initialize presenter with tab reference.

        Args:
            tab: The MechanismDesignTab view
            parent: Parent QObject for memory management
        """
        super().__init__(parent)
        self._tab = tab
        self._main_window = tab.main_window
        self._scene: QGraphicsScene | None = None  # Set after tab UI is initialized

        # === BUSINESS STATE (migrated from Tab) ===

        # Mechanism candidates and selection
        self.candidates: list[MechanismCandidate] = []
        self.selected_mechanism: MechanismCandidate | None = None

        # Path data from editor
        self.path_data: dict[str, QPainterPath] = {}
        self.selected_part_name: str | None = None
        self.parts_data: dict[str, Any] = {}
        self.part_enabled_state: dict[str, bool] = {}

        # Mechanism generation state
        self.current_mechanism_type: str | None = None
        self.mechanism_params: dict[str, Any] = {}
        self.mechanism_layers: dict[str, Any] = {}
        self.path_visual_items: dict[str, Any] = {}
        self.mechanism_paths: dict[str, QPainterPath] = {}
        self.mechanism_instances: dict[str, Any] = {}
        self.mechanism_enabled_state: dict[str, bool] = {}
        self.interactive_handles: dict[str, list[QGraphicsItem]] = {}

        # Parametric handles
        self.parametric_handles: dict[str, list[QGraphicsItem]] = {}

        # Skeleton visualization state
        self.skeleton_joint_items: dict[str, Any] = {}
        self.skeleton_bone_items: dict[str, Any] = {}
        self._initial_skeleton_data_cache: dict | None = None

        # Animation state
        self.animation_time: float = 0.0
        self.animation_speed: float = 1.0
        self.animating_mechanisms: dict[str, Any] = {}
        self._animation_timer: QTimer | None = None

        # IK throttling (performance)
        self.ik_update_rate_hz: int = 30
        self._ik_min_interval_ms: int = int(1000 / max(1, self.ik_update_rate_hz))
        self._ik_throttle_timer: QElapsedTimer = QElapsedTimer()
        self._ik_throttle_timer.invalidate()
        self._last_target_pos_by_joint: dict[str, QPointF] = {}
        self._pos_epsilon_px: float = 0.5
        self.mechanism_update_fraction: float = 0.5
        self._mech_rr_cursor: int = 0

        # Tab lifecycle state
        self._tab_active: bool = False
        self._tab_visible: bool = False
        self._scene_recently_cleared: bool = False
        self._updating_handles_programmatically: bool = False

        # Path trace
        self._trace_frame_tick: int = 0

        # === SERVICES ===

        self.mechanism_service = MechanismService()
        self.skeleton_service = SkeletonService()

        # Extracted services
        self._transform_service = TransformService()
        self._anchor_position_service = AnchorPositionService(self._transform_service)
        self._anchor_movement_handler = AnchorMovementHandler()
        self._visual_item_manager = VisualItemManager()
        self._mechanism_instantiation = MechanismInstantiationService()
        self._handle_position_coordinator = HandlePositionCoordinator()

        # Path trace manager
        self._path_trace_manager = PathTraceManager(
            config=PathTraceConfig(
                max_points=500,
                update_stride=5,
            )
        )

        # Configure callbacks
        self._configure_callbacks()

    def _configure_callbacks(self) -> None:
        """Configure service callbacks."""
        self._anchor_movement_handler.configure_callbacks(
            on_params_updated=self._on_params_updated,
            on_visuals_recreate=self._on_visuals_recreate,
            on_handles_update=self._on_handles_update,
            on_view_refresh=self._on_view_refresh,
        )

    # === TAB LIFECYCLE ===

    def activate(self) -> None:
        """Called when tab becomes active."""
        self._tab_active = True
        self._prepare_activation()
        self._tab._update_all_ui_states()

    def deactivate(self) -> None:
        """Called when tab becomes inactive."""
        self._tab_active = False
        self._cleanup_resources()

    def _prepare_activation(self) -> None:
        """Prepare tab for activation.

        Uses Tab's state directly for proper delegation pattern.
        Handles skeleton visualization and mechanism visual regeneration.
        """
        try:
            # Restore skeleton visualization
            if hasattr(self._tab, '_initial_skeleton_data_cache') and self._tab._initial_skeleton_data_cache:
                try:
                    if hasattr(self._tab, '_ensure_skeleton_visualization'):
                        self._tab._ensure_skeleton_visualization(self._tab._initial_skeleton_data_cache)
                except Exception:
                    pass

            # Regenerate mechanism visuals if needed
            enabled_mechanisms = [
                mid for mid, enabled in self._tab.mechanism_enabled_state.items()
                if enabled
            ]

            for mechanism_id in enabled_mechanisms:
                layer_data = self._tab.mechanism_layers.get(mechanism_id)
                if layer_data:
                    try:
                        # Check if visuals need regeneration
                        visual_items = layer_data.get("visual_items", [])
                        needs_regeneration = not visual_items or any(
                            item is None or self._visual_item_manager.is_visual_item_invalid(item)
                            for item in visual_items
                        )

                        if needs_regeneration and hasattr(self._tab, '_generate_mechanism_visuals_directly'):
                            self._tab._generate_mechanism_visuals_directly(
                                mechanism_id,
                                layer_data.get("type"),
                                layer_data.get("params", {}),
                                layer_data
                            )

                        # Regenerate trace items if missing
                        trace_item = self._path_trace_manager.get_trace_item(mechanism_id)
                        if trace_item is None or self._visual_item_manager.is_visual_item_invalid(trace_item):
                            self._path_trace_manager.init_trace(mechanism_id, self._scene)
                            # Restore trace points if they exist
                            from PyQt6.QtGui import QPainterPath
                            trace_points = self._path_trace_manager.get_trace_points(mechanism_id)
                            if len(trace_points) > 1:
                                path = QPainterPath()
                                path.moveTo(trace_points[0])
                                for point in trace_points[1:]:
                                    path.lineTo(point)
                                new_trace_item = self._path_trace_manager.get_trace_item(mechanism_id)
                                if new_trace_item:
                                    new_trace_item.setPath(path)

                    except Exception:
                        pass

        except Exception:
            pass

    def _cleanup_resources(self) -> None:
        """Clean up resources when deactivating.

        Uses Tab's state directly for proper delegation pattern.
        """
        # Stop IK manager
        if hasattr(self._main_window, 'ik_manager') and self._main_window.ik_manager:
            try:
                self._main_window.ik_manager.stop_animation()
            except Exception:
                pass

        # Stop animation timer (from Tab)
        if hasattr(self._tab, 'animation_timer') and self._tab.animation_timer.isActive():
            self._tab.animation_timer.stop()

        # Collect and clear visual items (from Tab's mechanism_layers)
        all_visual_items = []
        for mechanism_id, layer_data in self._tab.mechanism_layers.items():
            visual_items = layer_data.get("visual_items", [])
            all_visual_items.extend(visual_items)
            layer_data["visual_items"] = []

        # Clear traces
        self._path_trace_manager.clear_all_traces(self._scene)

        # Clear path visual items
        if hasattr(self._tab, 'path_visual_items'):
            self._tab.path_visual_items.clear()

        # Safe remove visual items
        if all_visual_items:
            self._visual_item_manager.safe_remove_visual_items(all_visual_items)

        # Update scene
        if self._scene:
            try:
                self._scene.update()
            except Exception:
                pass

    def _regenerate_visuals_if_needed(
        self,
        mechanism_id: str,
        layer_data: dict
    ) -> None:
        """Regenerate visuals if they're missing or invalid."""
        visual_items = layer_data.get("visual_items", [])
        needs_regeneration = not visual_items or any(
            item is None or self._visual_item_manager.is_visual_item_invalid(item)
            for item in visual_items
        )

        if needs_regeneration:
            self.view_update_requested.emit(
                'regenerate_visuals',
                {'mechanism_id': mechanism_id, 'layer_data': layer_data}
            )

    # === ANIMATION CONTROL ===

    def start_animation(self) -> None:
        """Start mechanism animation."""
        if self._animation_timer:
            self._animation_timer.start(33)  # ~30 FPS
        self.animation_state_changed.emit(True)

    def stop_animation(self) -> None:
        """Stop mechanism animation."""
        if self._animation_timer:
            self._animation_timer.stop()
        self.animation_state_changed.emit(False)

    def reset_animation(self) -> None:
        """Reset animation to initial state."""
        self.stop_animation()
        self.animation_time = 0.0
        self._reset_skeleton_to_initial()

    def is_animation_running(self) -> bool:
        """Check if animation is running."""
        return self._animation_timer is not None and self._animation_timer.isActive()

    def update_animation(self) -> None:
        """Update animation frame (called by timer)."""
        if not self._tab_active:
            self.stop_animation()
            return

        dt = 0.05 * self.animation_speed
        self.animation_time += dt
        if self.animation_time > 2 * math.pi:
            self.animation_time -= 2 * math.pi

        self._trace_frame_tick = (self._trace_frame_tick + 1) % 1000000

        # Process mechanisms in batches for performance
        self._process_mechanism_batch()

    def _process_mechanism_batch(self) -> None:
        """Process a batch of mechanisms for animation."""
        mech_items = list(self.mechanism_layers.items())
        total_mechs = len(mech_items)

        if total_mechs == 0:
            return

        batch_count = max(1, int(math.ceil(
            total_mechs * max(0.05, min(1.0, self.mechanism_update_fraction))
        )))

        start = self._mech_rr_cursor % total_mechs
        end = start + batch_count

        if end <= total_mechs:
            selected = mech_items[start:end]
        else:
            selected = mech_items[start:] + mech_items[: (end % total_mechs)]

        self._mech_rr_cursor = (self._mech_rr_cursor + batch_count) % total_mechs

        for mechanism_id, layer_data in selected:
            self._update_mechanism_animation(mechanism_id, layer_data)

    def _update_mechanism_animation(
        self,
        mechanism_id: str,
        layer_data: dict
    ) -> None:
        """Update a single mechanism's animation."""
        if not layer_data or not layer_data.get("part_name"):
            return

        part_name = layer_data["part_name"]
        if not self.part_enabled_state.get(part_name, True):
            return

        # Request View to update mechanism visuals
        self.view_update_requested.emit(
            'update_mechanism_animation',
            {
                'mechanism_id': mechanism_id,
                'time': self.animation_time,
                'layer_data': layer_data,
            }
        )

    def _reset_skeleton_to_initial(self) -> None:
        """Reset skeleton to initial state."""
        if hasattr(self._main_window, 'ik_manager') and self._main_window.ik_manager:
            try:
                ik = self._main_window.ik_manager
                if hasattr(ik, 'stop_animation'):
                    ik.stop_animation()
                if hasattr(ik, 'clear_mechanism_position_targets'):
                    ik.clear_mechanism_position_targets()
                if hasattr(ik, 'reset_animation_state'):
                    ik.reset_animation_state()
            except Exception:
                pass

    # === MECHANISM MANAGEMENT ===

    def add_mechanism_layer(
        self,
        mechanism_id: str,
        layer_data: dict
    ) -> None:
        """Add a mechanism layer."""
        self.mechanism_layers[mechanism_id] = layer_data
        self.mechanism_enabled_state[mechanism_id] = True
        self._update_mechanism_list()

    def remove_mechanism_layer(self, mechanism_id: str) -> None:
        """Remove a mechanism layer."""
        if mechanism_id in self.mechanism_layers:
            layer_data = self.mechanism_layers[mechanism_id]
            visual_items = layer_data.get("visual_items", [])
            self._visual_item_manager.safe_remove_visual_items(visual_items)
            del self.mechanism_layers[mechanism_id]

        self.mechanism_enabled_state.pop(mechanism_id, None)
        self.parametric_handles.pop(mechanism_id, None)
        self._update_mechanism_list()

    def toggle_mechanism(self, mechanism_id: str, enabled: bool) -> None:
        """Toggle mechanism enabled state."""
        self.mechanism_enabled_state[mechanism_id] = enabled
        self.view_update_requested.emit(
            'toggle_mechanism_visuals',
            {'mechanism_id': mechanism_id, 'enabled': enabled}
        )

    def clear_all_mechanisms(self) -> None:
        """Clear all mechanism data."""
        # Collect all visual items
        all_visuals = self._visual_item_manager.collect_visual_items_from_layers(
            self.mechanism_layers
        )
        self._visual_item_manager.safe_remove_visual_items(all_visuals)

        # Clear state
        self.mechanism_layers.clear()
        self.mechanism_enabled_state.clear()
        self.mechanism_instances.clear()
        self.parametric_handles.clear()
        self._path_trace_manager.clear_all_traces(self._scene)

        self._update_mechanism_list()

    def _update_mechanism_list(self) -> None:
        """Update mechanism list in View."""
        items = []
        for mech_id, layer_data in self.mechanism_layers.items():
            items.append({
                'id': mech_id,
                'name': layer_data.get('name', f'Mechanism {mech_id[:8]}'),
                'type': layer_data.get('type', 'unknown'),
                'part_name': layer_data.get('part_name', ''),
                'enabled': self.mechanism_enabled_state.get(mech_id, True),
            })
        self.mechanism_list_changed.emit(items)

    # === PATH DATA ===

    def set_path_data(self, path_data: dict[str, QPainterPath]) -> None:
        """Set path data from editor."""
        # Clear mechanisms for parts with changed paths
        current_parts = set(path_data.keys()) if path_data else set()
        previous_parts = set(self.path_data.keys())

        parts_to_clear = previous_parts - current_parts
        for part_name in current_parts:
            if (part_name in self.path_data and
                path_data.get(part_name) != self.path_data.get(part_name)):
                parts_to_clear.add(part_name)

        for part_name in parts_to_clear:
            self._clear_mechanism_for_part(part_name)

        self.path_data = path_data.copy() if path_data else {}

        # Update part enabled state
        for part_name in self.path_data.keys():
            if part_name not in self.part_enabled_state:
                self.part_enabled_state[part_name] = True

        # Remove state for removed parts
        for name in list(self.part_enabled_state.keys()):
            if name not in self.path_data:
                del self.part_enabled_state[name]

        self._tab._update_all_ui_states()

    def _clear_mechanism_for_part(self, part_name: str) -> None:
        """Clear mechanism associated with a part."""
        mechanisms_to_remove = [
            mech_id for mech_id, layer_data in self.mechanism_layers.items()
            if layer_data.get("part_name") == part_name
        ]

        for mech_id in mechanisms_to_remove:
            self.remove_mechanism_layer(mech_id)

    # === CALLBACK HANDLERS ===

    def _on_params_updated(self, mechanism_id: str, layer_data: dict) -> None:
        """Handle parameter updates from anchor movement."""
        pass  # State is updated in-place

    def _on_visuals_recreate(self, mechanism_id: str, layer_data: dict) -> None:
        """Handle visual recreation request."""
        self.view_update_requested.emit(
            'recreate_visuals',
            {'mechanism_id': mechanism_id, 'layer_data': layer_data}
        )

    def _on_handles_update(self, mechanism_id: str, moved_handle: str) -> None:
        """Handle request to update other handles."""
        handles = self.parametric_handles.get(mechanism_id, [])
        layer_data = self.mechanism_layers.get(mechanism_id)

        if handles and layer_data:
            self._handle_position_coordinator.update_other_handles(
                mechanism_id=mechanism_id,
                moved_handle=moved_handle,
                handles=handles,
                layer_data=layer_data,
                transform_fn=self._get_transform_function,
            )

    def _on_view_refresh(self) -> None:
        """Handle view refresh request."""
        self._scene.update()

    def _get_transform_function(self, layer_data: dict):
        """Get transform function for layer data."""
        return self._transform_service.get_scene_transform(layer_data)

    # === TRANSFORM DELEGATION ===

    def get_scene_transform_function(self, layer_data: dict):
        """Get scene transform function."""
        return self._transform_service.get_scene_transform(layer_data)

    def get_inverse_scene_transform_function(self, layer_data: dict):
        """Get inverse scene transform function."""
        return self._transform_service.get_inverse_transform(layer_data)
