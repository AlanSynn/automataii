"""
Visual Item Manager for Qt graphics item lifecycle management.

Extracted from MechanismDesignTab as part of god class decomposition.
Handles safe removal, validation, and interaction state of visual items.

Design Pattern: Facade (simplifies Qt object lifecycle management)
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene


class VisualItemManager:
    """
    Manages Qt graphics item lifecycle and interaction state.

    Responsibilities:
    - Safe removal of visual items from scene
    - Validation of item state (Qt object lifecycle)
    - Enable/disable interaction on visual items
    - Visual feedback for editing modes

    Time Complexity: O(n) where n is number of visual items
    """

    def __init__(self) -> None:
        """Initialize manager."""
        self._scene_recently_cleared = False

    def set_scene_cleared_flag(self, cleared: bool) -> None:
        """Set flag indicating scene was recently cleared."""
        self._scene_recently_cleared = cleared

    def safe_remove_visual_items(
        self,
        visual_items: list[QGraphicsItem],
        scene: QGraphicsScene | None = None,
    ) -> tuple[int, int]:
        """
        Safely remove visual items from scene, handling Qt object lifecycle issues.

        Args:
            visual_items: List of visual items to remove
            scene: Optional scene reference (items will get their own scene if not provided)

        Returns:
            Tuple of (valid_items_removed, already_deleted_items)
        """
        if not visual_items:
            return (0, 0)

        # Don't attempt individual removal if scene was already cleared
        if self._scene_recently_cleared:
            return (0, 0)

        valid_items_count = 0
        deleted_items_count = 0

        for item in visual_items:
            if item is None:
                continue

            try:
                # Quick validity check without accessing properties that might crash
                if hasattr(item, 'scene'):
                    item_scene = item.scene()

                    # Only try to remove if item is actually in a scene
                    if item_scene is not None:
                        try:
                            # Quick check if scene is still valid
                            _ = item_scene.itemsBoundingRect()
                            item_scene.removeItem(item)
                            valid_items_count += 1
                        except RuntimeError as e:
                            if "wrapped C/C++ object" in str(e):
                                deleted_items_count += 1

            except RuntimeError as e:
                if "wrapped C/C++ object" in str(e):
                    deleted_items_count += 1
            except Exception:
                pass

        return (valid_items_count, deleted_items_count)

    def is_visual_item_invalid(self, item: QGraphicsItem | None) -> bool:
        """
        Check if a visual item is invalid (deleted by Qt).

        Args:
            item: Visual item to check

        Returns:
            True if item is invalid/deleted, False if valid
        """
        try:
            if item is None:
                return True

            # Try to access a simple property
            _ = item.isVisible()
            return False
        except RuntimeError:
            return True
        except Exception:
            return True

    def disable_mechanism_visual_interaction(
        self,
        mechanism_layers: dict[str, dict[str, Any]],
    ) -> None:
        """
        Disable mouse interaction on mechanism visual items.

        Used when parametric handles need to receive mouse events instead of
        the underlying mechanism visuals.

        Args:
            mechanism_layers: Dictionary of mechanism layer data
        """
        try:
            for _mechanism_id, layer_data in mechanism_layers.items():
                visual_items = layer_data.get("visual_items", [])
                for item in visual_items:
                    if hasattr(item, 'setFlag'):
                        # Disable all mouse interaction flags
                        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                        if hasattr(item, 'setAcceptedMouseButtons'):
                            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                        if hasattr(item, 'setAcceptHoverEvents'):
                            item.setAcceptHoverEvents(False)
        except Exception:
            pass

    def enable_mechanism_visual_interaction(
        self,
        mechanism_layers: dict[str, dict[str, Any]],
    ) -> None:
        """
        Re-enable mouse interaction on mechanism visual items.

        Args:
            mechanism_layers: Dictionary of mechanism layer data
        """
        try:
            for _mechanism_id, layer_data in mechanism_layers.items():
                visual_items = layer_data.get("visual_items", [])
                for item in visual_items:
                    if hasattr(item, 'setFlag'):
                        # Restore default interaction flags
                        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                        if hasattr(item, 'setAcceptedMouseButtons'):
                            item.setAcceptedMouseButtons(
                                Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
                            )
                        if hasattr(item, 'setAcceptHoverEvents'):
                            item.setAcceptHoverEvents(True)
        except Exception:
            pass

    def show_free_edit_feedback(
        self,
        handles: list[QGraphicsItem],
        scene: QGraphicsScene,
    ) -> None:
        """
        Show visual feedback for free editing mode.

        Changes handle colors to blue to indicate user-controlled mode
        (no physics constraints).

        Args:
            handles: List of parametric handles
            scene: Graphics scene for update
        """
        try:
            for handle in handles:
                if hasattr(handle, 'handle_type') and handle.handle_type == 'rotation':
                    continue  # Skip rotation handle

                # Blue color for free editing mode
                handle.setBrush(QBrush(QColor(50, 150, 255)))  # Blue - user controlled
                handle.setPen(QPen(QColor(40, 120, 200), 3))
                handle.setToolTip("🆓 Free Edit Mode: Any position allowed")

            scene.update()
        except Exception:
            pass

    def collect_visual_items_from_layers(
        self,
        mechanism_layers: dict[str, dict[str, Any]],
    ) -> list[QGraphicsItem]:
        """
        Collect all visual items from mechanism layers.

        Args:
            mechanism_layers: Dictionary of mechanism layer data

        Returns:
            List of all visual items
        """
        all_items: list[QGraphicsItem] = []
        for _mechanism_id, layer_data in mechanism_layers.items():
            visual_items = layer_data.get("visual_items", [])
            all_items.extend(visual_items)
        return all_items

    def clear_visual_items_from_layers(
        self,
        mechanism_layers: dict[str, dict[str, Any]],
    ) -> None:
        """
        Clear visual items lists from all layers (does not remove from scene).

        Args:
            mechanism_layers: Dictionary of mechanism layer data
        """
        for _mechanism_id, layer_data in mechanism_layers.items():
            layer_data["visual_items"] = []
