"""
MechanismDesignPresenter - MVP Presenter for MechanismDesignTab.

Extracted from MechanismDesignTab as part of MVP architecture refactoring.
Owns all business state and coordination logic, leaving View as pure UI.

Design Pattern: MVP (Model-View-Presenter) - Passive View variant
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from PyQt6.QtCore import QElapsedTimer, QObject, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene

from automataii.application.mechanisms.mechanism_service import MechanismService
from automataii.application.mechanisms.skeleton_service import SkeletonService
from automataii.domain.kinematics.mechanism import MechanismCandidate
from automataii.presentation.qt.shared.scene_update_batcher import SceneUpdateBatcher
from automataii.presentation.qt.tabs.mechanism_design.path_trace_manager import (
    PathTraceConfig,
    PathTraceManager,
)
from automataii.presentation.qt.tabs.mechanism_design.services import (
    AnchorMovementHandler,
    AnchorPositionService,
    HandlePositionCoordinator,
    MechanismInstantiationService,
    TransformService,
    VisualItemManager,
)

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

    def __init__(self, tab: MechanismDesignTab, parent: QObject | None = None) -> None:
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
        self._scene_batcher: SceneUpdateBatcher | None = None  # Performance: batched scene updates

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
        self._mechanism_id_cache: tuple[str, ...] = ()
        self._mechanism_id_cache_dirty: bool = True

        # Tab lifecycle state
        self._tab_active: bool = False
        self._tab_visible: bool = False
        self._scene_recently_cleared: bool = False
        self._updating_handles_programmatically: bool = False

        # Path trace
        self._trace_frame_tick: int = 0

        # View listener pattern (for observer callbacks)
        self._view_listeners: list[Callable[[object], None]] = []

        # Animation and parametric mode state
        self._animation_running: bool = False
        self._parametric_mode_enabled: bool = False

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

    def set_scene(self, scene: QGraphicsScene) -> None:
        """Set the scene and initialize the update batcher.

        This should be called after the tab's UI is initialized.

        Args:
            scene: The QGraphicsScene to manage
        """
        self._scene = scene
        if scene is not None:
            self._scene_batcher = SceneUpdateBatcher(scene, parent=self)

    def _request_scene_update(self) -> None:
        """Request a batched scene update for performance optimization.

        Multiple calls within the same event loop iteration are coalesced
        into a single scene.update() call.
        """
        if self._scene_batcher is not None:
            self._scene_batcher.request_update()
        elif self._scene is not None:
            # Fallback if batcher not initialized
            try:
                self._scene.update()
            except RuntimeError:
                pass

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

    # === VIEW LISTENER PATTERN ===

    def add_view_listener(self, callback: Callable[[object], None]) -> None:
        """Register listener for view model updates.

        Args:
            callback: Function to call with view model updates
        """
        if callback not in self._view_listeners:
            self._view_listeners.append(callback)

    def remove_view_listener(self, callback: Callable[[object], None]) -> None:
        """Unregister listener for view model updates.

        Args:
            callback: Previously registered callback
        """
        if callback in self._view_listeners:
            self._view_listeners.remove(callback)

    def _notify_listeners(self, view_model: object) -> None:
        """Notify all registered listeners of view model update.

        Args:
            view_model: The view model to send to listeners
        """
        for callback in self._view_listeners:
            try:
                callback(view_model)
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

    # === STATE MANAGEMENT ===

    def select_part(self, part_name: str | None) -> None:
        """Update selected part name.

        Args:
            part_name: Name of selected part, or None to deselect
        """
        self.selected_part_name = part_name
        # Sync to tab for backward compatibility
        if hasattr(self._tab, "selected_part_name"):
            self._tab.selected_part_name = part_name

    def set_animation_running(self, is_running: bool) -> None:
        """Update animation running state.

        Args:
            is_running: True if animation is running
        """
        self._animation_running = is_running
        self.animation_state_changed.emit(is_running)

    def set_parametric_mode(self, enabled: bool) -> None:
        """Update parametric mode state.

        Args:
            enabled: True if parametric mode is enabled
        """
        self._parametric_mode_enabled = enabled

    def _prepare_activation(self) -> None:
        """Prepare tab for activation.

        Uses Tab's state directly for proper delegation pattern.
        Handles skeleton visualization and mechanism visual regeneration.
        """
        try:
            # Restore skeleton visualization
            if (
                hasattr(self._tab, "_initial_skeleton_data_cache")
                and self._tab._initial_skeleton_data_cache
            ):
                try:
                    if hasattr(self._tab, "_ensure_skeleton_visualization"):
                        self._tab._ensure_skeleton_visualization(
                            self._tab._initial_skeleton_data_cache
                        )
                except Exception:
                    logging.debug("Suppressed exception", exc_info=True)

            # Regenerate mechanism visuals if needed
            enabled_mechanisms = [
                mid for mid, enabled in self._tab.mechanism_enabled_state.items() if enabled
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

                        if needs_regeneration and hasattr(
                            self._tab, "_generate_mechanism_visuals_directly"
                        ):
                            self._tab._generate_mechanism_visuals_directly(
                                mechanism_id,
                                layer_data.get("type"),
                                layer_data.get("params", {}),
                                layer_data,
                            )

                        # Regenerate trace items if missing
                        trace_item = self._path_trace_manager.get_trace_item(mechanism_id)
                        if trace_item is None or self._visual_item_manager.is_visual_item_invalid(
                            trace_item
                        ):
                            self._path_trace_manager.init_trace(mechanism_id, self._scene)
                            # Restore trace points if they exist
                            from PyQt6.QtGui import QPainterPath

                            trace_points = self._path_trace_manager.get_trace_points(mechanism_id)
                            if len(trace_points) > 1:
                                path = QPainterPath()
                                path.moveTo(trace_points[0])
                                for point in trace_points[1:]:
                                    path.lineTo(point)
                                new_trace_item = self._path_trace_manager.get_trace_item(
                                    mechanism_id
                                )
                                if new_trace_item:
                                    new_trace_item.setPath(path)

                    except Exception:
                        logging.debug("Suppressed exception", exc_info=True)

        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

    def _cleanup_resources(self) -> None:
        """Clean up resources when deactivating.

        Uses Tab's state directly for proper delegation pattern.
        """
        # Stop IK manager
        if hasattr(self._main_window, "ik_manager") and self._main_window.ik_manager:
            try:
                self._main_window.ik_manager.stop_animation()
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

        # Stop animation timer (from Tab)
        if hasattr(self._tab, "animation_timer") and self._tab.animation_timer.isActive():
            self._tab.animation_timer.stop()

        # Collect and clear visual items (from Tab's mechanism_layers)
        all_visual_items = []
        for _mechanism_id, layer_data in self._tab.mechanism_layers.items():
            visual_items = layer_data.get("visual_items", [])
            all_visual_items.extend(visual_items)
            layer_data["visual_items"] = []

        # Clear traces
        self._path_trace_manager.clear_all_traces(self._scene)

        # Clear path visual items
        if hasattr(self._tab, "path_visual_items"):
            self._tab.path_visual_items.clear()

        # Safe remove visual items
        if all_visual_items:
            self._visual_item_manager.safe_remove_visual_items(all_visual_items)

        # Update scene (batched for performance)
        self._request_scene_update()

    def _regenerate_visuals_if_needed(self, mechanism_id: str, layer_data: dict) -> None:
        """Regenerate visuals if they're missing or invalid."""
        visual_items = layer_data.get("visual_items", [])
        needs_regeneration = not visual_items or any(
            item is None or self._visual_item_manager.is_visual_item_invalid(item)
            for item in visual_items
        )

        if needs_regeneration:
            self.view_update_requested.emit(
                "regenerate_visuals", {"mechanism_id": mechanism_id, "layer_data": layer_data}
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
        mech_ids = self._get_mechanism_id_cache()
        total_mechs = len(mech_ids)

        if total_mechs == 0:
            return

        batch_count = max(
            1, int(math.ceil(total_mechs * max(0.05, min(1.0, self.mechanism_update_fraction))))
        )

        start = self._mech_rr_cursor % total_mechs
        for offset in range(batch_count):
            idx = (start + offset) % total_mechs
            mechanism_id = mech_ids[idx]
            layer_data = self.mechanism_layers.get(mechanism_id)
            if layer_data is None:
                self._mark_mechanism_iteration_cache_dirty()
                continue
            self._update_mechanism_animation(mechanism_id, layer_data)
        self._mech_rr_cursor = (start + batch_count) % total_mechs

    def _mark_mechanism_iteration_cache_dirty(self) -> None:
        self._mechanism_id_cache_dirty = True

    def _get_mechanism_id_cache(self) -> tuple[str, ...]:
        if self._mechanism_id_cache_dirty or len(self._mechanism_id_cache) != len(
            self.mechanism_layers
        ):
            self._mechanism_id_cache = tuple(self.mechanism_layers.keys())
            self._mechanism_id_cache_dirty = False
            if self._mechanism_id_cache:
                self._mech_rr_cursor %= len(self._mechanism_id_cache)
            else:
                self._mech_rr_cursor = 0
        return self._mechanism_id_cache

    def _update_mechanism_animation(self, mechanism_id: str, layer_data: dict) -> None:
        """Update a single mechanism's animation."""
        if not layer_data or not layer_data.get("part_name"):
            return

        part_name = layer_data["part_name"]
        if not self.part_enabled_state.get(part_name, True):
            return

        # Request View to update mechanism visuals
        self.view_update_requested.emit(
            "update_mechanism_animation",
            {
                "mechanism_id": mechanism_id,
                "time": self.animation_time,
                "layer_data": layer_data,
            },
        )

    def _reset_skeleton_to_initial(self) -> None:
        """Reset skeleton to initial state."""
        if hasattr(self._main_window, "ik_manager") and self._main_window.ik_manager:
            try:
                ik = self._main_window.ik_manager
                if hasattr(ik, "stop_animation"):
                    ik.stop_animation()
                if hasattr(ik, "clear_mechanism_position_targets"):
                    ik.clear_mechanism_position_targets()
                if hasattr(ik, "reset_animation_state"):
                    ik.reset_animation_state()
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

    # === MECHANISM MANAGEMENT ===

    def add_mechanism_layer(self, mechanism_id: str, layer_data: dict) -> None:
        """Add a mechanism layer."""
        self.mechanism_layers[mechanism_id] = layer_data
        self.mechanism_enabled_state[mechanism_id] = True
        self._mark_mechanism_iteration_cache_dirty()
        self._update_mechanism_list()

    def remove_mechanism_layer(self, mechanism_id: str) -> None:
        """Remove a mechanism layer."""
        if mechanism_id in self.mechanism_layers:
            layer_data = self.mechanism_layers[mechanism_id]
            visual_items = layer_data.get("visual_items", [])
            self._visual_item_manager.safe_remove_visual_items(visual_items)
            del self.mechanism_layers[mechanism_id]
            self._mark_mechanism_iteration_cache_dirty()

        self.mechanism_enabled_state.pop(mechanism_id, None)
        self.parametric_handles.pop(mechanism_id, None)
        self._update_mechanism_list()

    def toggle_mechanism(self, mechanism_id: str, enabled: bool) -> None:
        """Toggle mechanism enabled state."""
        self.mechanism_enabled_state[mechanism_id] = enabled
        self.view_update_requested.emit(
            "toggle_mechanism_visuals", {"mechanism_id": mechanism_id, "enabled": enabled}
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
        self._mark_mechanism_iteration_cache_dirty()
        self._path_trace_manager.clear_all_traces(self._scene)

        self._update_mechanism_list()

    def _update_mechanism_list(self) -> None:
        """Update mechanism list in View."""
        items = []
        for mech_id, layer_data in self.mechanism_layers.items():
            items.append(
                {
                    "id": mech_id,
                    "name": layer_data.get("name", f"Mechanism {mech_id[:8]}"),
                    "type": layer_data.get("type", "unknown"),
                    "part_name": layer_data.get("part_name", ""),
                    "enabled": self.mechanism_enabled_state.get(mech_id, True),
                }
            )
        self.mechanism_list_changed.emit(items)

    # === PATH DATA ===

    def set_path_data(self, path_data: dict[str, QPainterPath]) -> None:
        """Set path data from editor."""
        # Clear mechanisms for parts with changed paths
        current_parts = set(path_data.keys()) if path_data else set()
        previous_parts = set(self.path_data.keys())

        parts_to_clear = previous_parts - current_parts
        for part_name in current_parts:
            if part_name in self.path_data and path_data.get(part_name) != self.path_data.get(
                part_name
            ):
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
        """Clear mechanism associated with a part. Full cleanup including visuals."""
        self._tab._clear_animation_cache()

        mechanisms_to_remove = [
            mech_id
            for mech_id, layer_data in self.mechanism_layers.items()
            if layer_data.get("part_name") == part_name
        ]

        for mech_id in mechanisms_to_remove:
            layer_data = self.mechanism_layers.get(mech_id)
            if layer_data:
                visual_items = layer_data.get("visual_items", [])
                self._visual_item_manager.safe_remove_visual_items(visual_items)
                self._path_trace_manager.clear_trace(mech_id, self._scene)
            self.remove_mechanism_layer(mech_id)

        # Clear path items for this part
        if part_name in self._tab.mechanism_path_items:
            path_item = self._tab.mechanism_path_items[part_name]
            if path_item and self._scene and path_item.scene() == self._scene:
                self._scene.removeItem(path_item)
            del self._tab.mechanism_path_items[part_name]

    # === CALLBACK HANDLERS ===

    def _on_params_updated(self, mechanism_id: str, layer_data: dict) -> None:
        """Handle parameter updates from anchor movement.

        Emits mechanism_parameters_changed signal to propagate changes
        to ProjectStateManager for undo/redo support and Foundry sync.
        """
        # Emit signal to propagate changes (for undo/redo and Foundry sync)
        if self._tab and hasattr(self._tab, "_emit_mechanism_params_changed"):
            self._tab._emit_mechanism_params_changed(mechanism_id)

    def _on_visuals_recreate(self, mechanism_id: str, layer_data: dict) -> None:
        """Handle visual recreation request."""
        self.view_update_requested.emit(
            "recreate_visuals", {"mechanism_id": mechanism_id, "layer_data": layer_data}
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
        self._request_scene_update()

    def _get_transform_function(
        self,
        layer_data: dict[str, Any],
    ) -> Callable[[Any], QPointF] | None:
        """Get transform function for layer data."""
        return cast(
            Callable[[Any], QPointF] | None,
            self._transform_service.get_scene_transform(layer_data),
        )

    # === TRANSFORM DELEGATION ===

    def get_scene_transform_function(
        self,
        layer_data: dict[str, Any],
    ) -> Callable[[Any], QPointF] | None:
        """Get scene transform function."""
        return cast(
            Callable[[Any], QPointF] | None,
            self._transform_service.get_scene_transform(layer_data),
        )

    def get_inverse_scene_transform_function(
        self,
        layer_data: dict[str, Any],
    ) -> Callable[[QPointF], Any] | None:
        """Get inverse scene transform function."""
        return cast(
            Callable[[QPointF], Any] | None,
            self._transform_service.get_inverse_transform(layer_data),
        )

    # === MECHANISM GENERATION (migrated from Tab) ===

    def generate_mechanism_from_candidate(self, candidate_data: dict[str, Any]) -> None:
        """Generate mechanism from candidate. Business logic moved from Tab."""
        from automataii.application.mechanism_foundry.mechanism_generation_service import (
            MechanismGenerationContext,
        )

        # Clear existing mechanism for current part
        selected_part = self.selected_part_name
        if selected_part:
            self._clear_mechanism_for_part(selected_part)
            self._path_trace_manager.clear_trace_for_part(
                selected_part,
                self.mechanism_layers,
                self._scene,
            )

        # Build generation context
        context = MechanismGenerationContext(
            selected_part_name=selected_part or "",
            target_path=self.path_data.get(selected_part) if selected_part else None,
            candidate_data=candidate_data,
            parts_data=self.parts_data,
            skeleton_cache=self._initial_skeleton_data_cache,
        )

        # Delegate generation to application service
        gen_service = self._tab._mechanism_generation_service
        result = gen_service.generate_mechanism(context)

        if not result.success or not result.layer_data:
            return

        # Store layer and enable
        layer_data = result.layer_data
        self.mechanism_layers[result.mechanism_id] = layer_data
        self.mechanism_enabled_state[result.mechanism_id] = True
        self._mark_mechanism_iteration_cache_dirty()

        # Recommendation templates may start from free-form simulation data.
        # Recompute the layer immediately after preset snapping so Design
        # visuals/animation use the same physical params that Fabrication exports.
        self._tab._regenerate_foundry_layer_simulation(result.mechanism_id, layer_data)

        # Initialize path trace
        self._path_trace_manager.init_trace(result.mechanism_id, self._scene)

        # Request View to generate visuals
        # IMPORTANT: Spread layer_data with ** to put transform_params and generated_path
        # at the top level where TransformService expects them.
        # This is consistent with _generate_mechanism_visuals_directly which uses **layer_data.
        self.view_update_requested.emit(
            "generate_mechanism_visuals",
            {
                "mechanism_id": result.mechanism_id,
                "mechanism_type": layer_data["type"],
                **layer_data,  # Spreads transform_params, generated_path, etc. at top level
            },
        )

        self._update_mechanism_list()

    def handle_mechanism_visuals(self, mechanism_graphics_data: dict) -> None:
        """Handle mechanism visualization data. Business logic moved from Tab."""
        # Clear animation cache
        self._tab._clear_animation_cache()
        self._reset_skeleton_to_initial()

        mechanism_id = mechanism_graphics_data.get(
            "mechanism_id", mechanism_graphics_data.get("id")
        )
        mechanism_type = mechanism_graphics_data.get(
            "mechanism_type", mechanism_graphics_data.get("type")
        )
        if mechanism_id is None:
            return

        layer_data = self.mechanism_layers.get(mechanism_id)

        if not layer_data:
            return

        graphics_payload = dict(mechanism_graphics_data)
        graphics_payload.setdefault("mechanism_id", mechanism_id)
        if mechanism_type is None:
            mechanism_type = layer_data.get("type")
        if mechanism_type is not None:
            graphics_payload.setdefault("mechanism_type", mechanism_type)
        for key, value in layer_data.items():
            graphics_payload.setdefault(key, value)

        # Remove existing visuals safely
        existing = layer_data.get("visual_items", [])
        self._visual_item_manager.safe_remove_visual_items(existing)

        # Request View to create visuals
        transform_func = self._transform_service.get_scene_transform(graphics_payload)
        visual_items = self._create_mechanism_visuals(
            str(mechanism_type or ""), graphics_payload, transform_func
        )

        layer_data["visual_items"] = visual_items

        # Merge computed fields back to layer_data
        for key in (
            "cam_profile_local_points",
            "cam_points_local",
            "cam_template_svg_path",
            "cam_transform_function",
            "cam_axis_local",
            "cam_scale_factor",
            "rod_length_multiplier",
            "follower_fixed_x_scene",
        ):
            if key in mechanism_graphics_data:
                layer_data[key] = mechanism_graphics_data[key]

        # Update scene (batched for performance)
        self._request_scene_update()

    def _create_mechanism_visuals(
        self,
        mechanism_type: str,
        data: dict[str, Any],
        transform_func: Callable[[Any], QPointF] | None,
    ) -> list[QGraphicsItem]:
        """Create visuals via Tab's visuals factory."""
        factory = self._tab.visuals_factory
        items: list[QGraphicsItem] = []

        if mechanism_type == "4_bar_linkage":
            items.extend(factory.create_4bar_linkage_visuals(data, transform_func))
        elif mechanism_type == "cam":
            char_pos = self._get_character_position()
            items.extend(factory.create_cam_visuals(data, transform_func, char_pos))
        elif mechanism_type == "gear":
            items.extend(factory.create_gear_visuals(data, transform_func))
        elif mechanism_type == "planetary_gear":
            items.extend(factory.create_planetary_gear_visuals(data, transform_func))
        else:
            logging.warning("No visual factory registered for mechanism type: %s", mechanism_type)

        return items

    def _get_character_position(self) -> list[float]:
        """Get character ground position from skeleton cache."""
        from automataii.domain.kinematics.joint_mapping_service import JointMappingService

        service = JointMappingService()
        return list(service.get_character_ground_position(self._initial_skeleton_data_cache))

    def clear_mechanism_data(self) -> None:
        """Clear all mechanism data. Business logic moved from Tab."""
        # Stop animation
        if hasattr(self._tab, "animation_timer") and self._tab.animation_timer.isActive():
            self._tab.animation_timer.stop()
        if (
            hasattr(self._tab, "_animation_frame_coordinator")
            and self._tab._animation_frame_coordinator
        ):
            self._tab._animation_frame_coordinator.reset_state()

        # Clear via scene management service
        ik_manager = getattr(self._main_window, "ik_manager", None)
        self._tab._scene_management_service.clear_mechanism_data(
            mechanism_layers=self.mechanism_layers,
            mechanism_enabled_state=self.mechanism_enabled_state,
            path_visual_items=self._tab.path_visual_items,
            mechanism_path_items=self._tab.mechanism_path_items,
            mechanism_instances=self._tab.mechanism_instances,
            parametric_handles=self.parametric_handles,
            interactive_handles=self._tab.interactive_handles,
            path_trace_manager=self._path_trace_manager,
            scene=self._scene,
            ik_manager=ik_manager,
        )
        self._mark_mechanism_iteration_cache_dirty()

        # Clear local state
        self.path_data.clear()
        self.selected_part_name = None
        self._tab.mechanism_path_points.clear()
        self._tab.current_editor_items.clear()
        self.parts_data.clear()
        self._tab.selected_mechanism_id = None

        # Update UI
        if self._tab.mechanism_layers_list:
            self._tab.mechanism_layers_list.clear()
        self._tab._update_all_ui_states()

    def setup_mechanism_ik_integration(self) -> bool:
        """Setup IK integration. Business logic moved from Tab."""
        from automataii.application.mechanism_foundry.mechanism_lifecycle_coordinator import (
            MechanismLifecycleContext,
        )

        ik_manager = getattr(self._main_window, "ik_manager", None)
        if not ik_manager:
            return False

        context = MechanismLifecycleContext(
            mechanism_layers=self.mechanism_layers,
            mechanism_enabled_state=self.mechanism_enabled_state,
            parts_data=self.parts_data,
            skeleton_cache=self._initial_skeleton_data_cache,
        )

        return bool(
            self._tab._lifecycle_coordinator.setup_ik_integration(
                ik_manager=ik_manager,
                context=context,
                register_controller_fn=self._register_mechanism_controller,
            )
        )

    def _register_mechanism_controller(
        self,
        mech_id: str,
        layer_data: dict,
        joint_id: str,
    ) -> None:
        """Register mechanism as IK controller."""
        ik_manager = getattr(self._main_window, "ik_manager", None)
        if not ik_manager:
            return

        # Generate motion path
        joint_motion_path = self._tab._generate_joint_motion_path(layer_data, joint_id)
        if joint_motion_path and hasattr(ik_manager, "set_joint_motion_path"):
            ik_manager.set_joint_motion_path(joint_id, joint_motion_path)
            part_name = layer_data.get("part_name")
            if part_name and hasattr(ik_manager, "set_part_motion_path"):
                ik_manager.set_part_motion_path(part_name, joint_motion_path)

        # Register callback
        def mechanism_callback(time: float) -> QPointF | None:
            result = self._tab._calculate_mechanism_output(
                layer_data.get("type"),
                layer_data.get("params", {}),
                time,
                layer_data,
            )
            return result if isinstance(result, QPointF) or result is None else None

        if hasattr(ik_manager, "register_mechanism_controller"):
            ik_manager.register_mechanism_controller(joint_id, mech_id, mechanism_callback)

        # Enable IK for part
        part_name = layer_data.get("part_name")
        if part_name and hasattr(ik_manager, "enable_ik_for_part"):
            ik_manager.enable_ik_for_part(part_name, True)

    def set_parts_data(self, parts_data: dict[str, Any]) -> dict[str, Any]:
        """Set parts data. Returns sorted parts data."""
        if parts_data:
            sorted_names = sorted(
                parts_data.keys(),
                key=lambda name: name in self.path_data,
                reverse=True,
            )
            self.parts_data = {name: parts_data[name] for name in sorted_names}
        else:
            self.parts_data = {}
        return self.parts_data

    def get_standardized_joint_id(self, abstract_joint_id: str) -> str | None:
        """Standardize joint ID with skeleton cache fallback and prefix matching.

        Handles skeleton joint IDs that have numeric suffixes (e.g., left_hand_9).
        """
        import logging

        from automataii.domain.kinematics.joint_mapping_service import JointMappingService

        service = JointMappingService()
        raw_std_id = service.standardize_joint_id(abstract_joint_id)
        std_id = raw_std_id if isinstance(raw_std_id, str) else None

        # Use presenter's cache first, then fallback to Tab's cache
        cache = self._initial_skeleton_data_cache
        if not cache:
            cache = getattr(self._tab, "_initial_skeleton_data_cache", None)

        # Debug: Log cache state (only first call)
        if not hasattr(self, "_cache_logged"):
            self._cache_logged = True
            logging.debug(
                f"[JOINT-MAP] Cache exists={cache is not None}, keys={list(cache.keys()) if cache else []}"
            )
            joints_preview = list(cache.get("joints", {}).keys())[:5] if cache else []
            logging.debug(f"[JOINT-MAP] Sample joint keys: {joints_preview}")

        raw_joints = cache.get("joints", {}) if cache else {}
        joints = raw_joints if isinstance(raw_joints, dict) else {}

        # 1. Exact match
        if std_id and std_id in joints:
            return std_id
        if abstract_joint_id in joints:
            return abstract_joint_id

        # 2. Check joint_map
        if cache:
            raw_joint_map = cache.get("joint_map", {})
            joint_map = raw_joint_map if isinstance(raw_joint_map, dict) else {}
            if abstract_joint_id in joint_map:
                mapped = joint_map[abstract_joint_id]
                return mapped if isinstance(mapped, str) else None
            if std_id and std_id in joint_map:
                mapped = joint_map[std_id]
                return mapped if isinstance(mapped, str) else None

        # 3. Prefix matching for suffixed joint IDs (e.g., left_hand_9)
        # Skeleton from Animated Drawings uses suffixed IDs
        target_id = std_id or abstract_joint_id
        if joints and target_id:
            for joint_id in joints:
                if not isinstance(joint_id, str):
                    continue
                # Check if joint_id starts with target (prefix match)
                # e.g., "left_hand_9".startswith("left_hand")
                if joint_id.startswith(target_id + "_") or joint_id == target_id:
                    logging.debug(f"[JOINT-MAP] Prefix matched '{target_id}' -> '{joint_id}'")
                    return joint_id
                # Also check if target is a prefix without underscore
                # e.g., "left_hand" matches "left_hand9" (no underscore)
                if joint_id.startswith(target_id) and len(joint_id) > len(target_id):
                    suffix = joint_id[len(target_id) :]
                    if suffix[0].isdigit() or suffix[0] == "_":
                        logging.debug(f"[JOINT-MAP] Prefix matched '{target_id}' -> '{joint_id}'")
                        return joint_id

        logging.debug(f"[JOINT-MAP] No match found for '{abstract_joint_id}' (std: '{std_id}')")
        return None

    def handle_ik_update(self, ik_results: dict[str, dict[str, Any]]) -> bool:
        """Handle IK update results. Returns True if update was processed."""
        if not self._tab_active or not ik_results:
            return False

        view = self._tab.mechanism_view
        if not view:
            return False

        try:
            if hasattr(view, "update_visuals_from_animation_data"):
                view.update_visuals_from_animation_data(ik_results)

            if self._tab_active:
                self._request_scene_update()
            return True
        except RuntimeError as e:
            if "wrapped C/C++ object" not in str(e):
                raise
            return False
        except Exception:
            return False

    def reset_skeleton_to_initial_state(self) -> None:
        """Reset skeleton to initial state. Business logic moved from Tab."""
        ik_manager = getattr(self._main_window, "ik_manager", None)
        self.animation_time = 0.0

        # Delegate IK reset to application layer
        def on_skeleton_reset(skeleton_data: dict) -> None:
            self._tab._position_parts_at_anchor_joints()
            self._tab.on_skeleton_updated(skeleton_data)
            view = self._tab.mechanism_view
            if hasattr(view, "skeleton_graphics_item") and view.skeleton_graphics_item:
                view.skeleton_graphics_item.update()

        self._tab._lifecycle_coordinator.reset_skeleton_state(
            ik_manager=ik_manager,
            skeleton_cache=self._initial_skeleton_data_cache,
            animation_timer=self._tab.animation_timer,
            on_skeleton_reset=on_skeleton_reset,
        )

        # Fallback: try to get from skeleton manager if no cache
        if not self._initial_skeleton_data_cache:
            skeleton_mgr = getattr(self._main_window, "skeleton_manager", None)
            if skeleton_mgr:
                initial_skeleton = skeleton_mgr.get_current_skeleton_data()
                if initial_skeleton:
                    self._tab.cache_initial_skeleton(initial_skeleton)
                    self._initial_skeleton_data_cache = initial_skeleton
                    on_skeleton_reset(initial_skeleton)
