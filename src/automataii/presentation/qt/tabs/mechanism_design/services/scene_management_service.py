"""
Scene Management Service for clearing and resetting mechanism scene.

Extracted from MechanismDesignTab as part of god class decomposition.
Handles scene clearing, mechanism data clearing, and skeleton reset operations.

Design Pattern: Service (encapsulates clearing operations)
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene

if TYPE_CHECKING:
    from automataii.presentation.qt.tabs.mechanism_design.path_trace_manager import PathTraceManager


class SceneManagementService:
    """
    Manages scene clearing and mechanism data operations.

    Responsibilities:
    - Clear mechanism data from scene
    - Clear scene while preserving skeleton
    - Reset skeleton to initial state
    - Safe removal of Qt graphics items
    """

    def __init__(self) -> None:
        """Initialize service."""
        # Callbacks (injected)
        self._is_visual_item_invalid_fn: Callable[[Any], bool] | None = None
        self._safe_remove_visual_items_fn: Callable[[list], None] | None = None

    def configure_callbacks(
        self,
        *,
        is_visual_item_invalid: Callable[[Any], bool],
        safe_remove_visual_items: Callable[[list], None],
    ) -> None:
        """
        Configure callbacks for service.

        Args:
            is_visual_item_invalid: Function to check if visual item is invalid
            safe_remove_visual_items: Function to safely remove visual items
        """
        self._is_visual_item_invalid_fn = is_visual_item_invalid
        self._safe_remove_visual_items_fn = safe_remove_visual_items

    def clear_mechanism_data(
        self,
        *,
        mechanism_layers: dict[str, Any],
        mechanism_enabled_state: dict[str, bool],
        path_visual_items: dict[str, Any],
        mechanism_path_items: dict[str, Any],
        mechanism_instances: dict[str, Any],
        parametric_handles: dict[str, list],
        interactive_handles: dict[str, list],
        path_trace_manager: "PathTraceManager",
        scene: QGraphicsScene,
        ik_manager: Any | None,
    ) -> None:
        """
        Clear all mechanism data and visuals.

        Args:
            mechanism_layers: Dict of mechanism layer data
            mechanism_enabled_state: Dict of mechanism enabled states
            path_visual_items: Dict of path visual items
            mechanism_path_items: Dict of mechanism path items
            mechanism_instances: Dict of mechanism instances
            parametric_handles: Dict of parametric handles
            interactive_handles: Dict of interactive handles
            path_trace_manager: Path trace manager
            scene: Graphics scene
            ik_manager: IK manager instance
        """
        # Stop IK animation if running
        if ik_manager:
            try:
                if hasattr(ik_manager, 'stop_animation'):
                    ik_manager.stop_animation()
                if hasattr(ik_manager, 'clear_mechanism_position_targets'):
                    ik_manager.clear_mechanism_position_targets()
            except Exception:
                pass

        # Collect all visual items to remove
        all_visuals: list[Any] = []

        for mechanism_id, layer_data in mechanism_layers.items():
            visual_items = layer_data.get("visual_items", [])
            all_visuals.extend(visual_items)
            layer_data["visual_items"] = []

        # Clear path visual items
        all_visuals.extend(path_visual_items.values())
        path_visual_items.clear()

        # Clear mechanism path items
        all_visuals.extend(mechanism_path_items.values())
        mechanism_path_items.clear()

        # Clear traces
        path_trace_manager.clear_all_traces(scene)

        # Clear handles
        for handles in parametric_handles.values():
            all_visuals.extend(handles)
        parametric_handles.clear()

        for handles in interactive_handles.values():
            all_visuals.extend(handles)
        interactive_handles.clear()

        # Remove visual items
        if self._safe_remove_visual_items_fn and all_visuals:
            self._safe_remove_visual_items_fn(all_visuals)

        # Clear data structures
        mechanism_layers.clear()
        mechanism_enabled_state.clear()
        mechanism_instances.clear()

    def clear_scene_preserve_skeleton(
        self,
        scene: QGraphicsScene,
        *,
        skeleton_joint_items: dict[str, Any],
        skeleton_bone_items: dict[str, Any],
        mechanism_layers: dict[str, Any],
        path_visual_items: dict[str, Any],
        mechanism_path_items: dict[str, Any],
        parametric_handles: dict[str, list],
        path_trace_manager: "PathTraceManager",
    ) -> None:
        """
        Clear scene while preserving skeleton visualization.

        Args:
            scene: Graphics scene to clear
            skeleton_joint_items: Skeleton joint items to preserve
            skeleton_bone_items: Skeleton bone items to preserve
            mechanism_layers: Mechanism layer data
            path_visual_items: Path visual items
            mechanism_path_items: Mechanism path items
            parametric_handles: Parametric handles
            path_trace_manager: Path trace manager
        """
        # Store skeleton items before clearing
        skeleton_items = list(skeleton_joint_items.values()) + list(skeleton_bone_items.values())

        # Collect items to remove (everything except skeleton)
        items_to_remove: list[Any] = []

        # Collect mechanism visual items
        for mechanism_id, layer_data in mechanism_layers.items():
            visual_items = layer_data.get("visual_items", [])
            items_to_remove.extend(visual_items)
            layer_data["visual_items"] = []

        # Collect path items
        items_to_remove.extend(path_visual_items.values())
        items_to_remove.extend(mechanism_path_items.values())

        # Collect handles
        for handles in parametric_handles.values():
            items_to_remove.extend(handles)

        # Clear traces
        path_trace_manager.clear_all_traces(scene)

        # Remove items (not skeleton)
        for item in items_to_remove:
            if item and item not in skeleton_items:
                try:
                    if item.scene():
                        scene.removeItem(item)
                except (RuntimeError, AttributeError):
                    pass

        # Clear data but not the dicts themselves
        path_visual_items.clear()
        mechanism_path_items.clear()
        parametric_handles.clear()

    def reset_skeleton_to_initial(
        self,
        *,
        ik_manager: Any | None,
        initial_skeleton_cache: dict | None,
        skeleton_joint_items: dict[str, Any],
        skeleton_bone_items: dict[str, Any],
        mechanism_layers: dict[str, Any],
        animation_timer: Any | None,
        clear_animation_cache_fn: Callable[[], None] | None,
    ) -> None:
        """
        Reset skeleton to initial state.

        Args:
            ik_manager: IK manager instance
            initial_skeleton_cache: Cached initial skeleton data
            skeleton_joint_items: Skeleton joint items
            skeleton_bone_items: Skeleton bone items
            mechanism_layers: Mechanism layers
            animation_timer: Animation timer
            clear_animation_cache_fn: Function to clear animation cache
        """
        # Stop animation if running
        if animation_timer and hasattr(animation_timer, 'isActive') and animation_timer.isActive():
            animation_timer.stop()

        # Clear animation cache
        if clear_animation_cache_fn:
            clear_animation_cache_fn()

        # Stop IK and clear targets
        if ik_manager:
            try:
                if hasattr(ik_manager, 'stop_animation'):
                    ik_manager.stop_animation()
                if hasattr(ik_manager, 'clear_mechanism_position_targets'):
                    ik_manager.clear_mechanism_position_targets()
                if hasattr(ik_manager, 'reset_animation_state'):
                    ik_manager.reset_animation_state()
            except Exception:
                pass

        # Reset skeleton positions from cache
        if initial_skeleton_cache and ik_manager:
            joints = initial_skeleton_cache.get("joints", {})
            for joint_id, joint_data in joints.items():
                if isinstance(joint_data, dict) and "position" in joint_data:
                    pos = joint_data["position"]
                    try:
                        if hasattr(ik_manager, 'reset_joint_to_initial'):
                            ik_manager.reset_joint_to_initial(joint_id)
                    except Exception:
                        pass

        # Update skeleton visualization items
        if initial_skeleton_cache:
            joints = initial_skeleton_cache.get("joints", {})
            for joint_id, joint_item in skeleton_joint_items.items():
                if joint_id in joints:
                    joint_data = joints[joint_id]
                    if isinstance(joint_data, dict) and "position" in joint_data:
                        pos = joint_data["position"]
                        try:
                            from PyQt6.QtCore import QPointF
                            joint_item.setPos(QPointF(pos[0], pos[1]))
                        except Exception:
                            pass
