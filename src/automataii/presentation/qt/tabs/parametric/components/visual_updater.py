"""
Visual Updater - Real-time mechanism visual updates.

Extracted from ParametricEditingManager. Handles updating mechanism
visuals during parametric editing.

Design Pattern: Service (visual rendering coordination)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Protocol

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView


class VisualsFactory(Protocol):
    """Protocol for mechanism visuals factory."""

    def create_4bar_linkage_visuals(
        self,
        layer_data: dict[str, Any],
        transform_func: Callable | None,
    ) -> list: ...

    def create_cam_visuals(
        self,
        layer_data: dict[str, Any],
        transform_func: Callable | None,
        char_pos: Any | None,
    ) -> list: ...

    def create_gear_visuals(
        self,
        layer_data: dict[str, Any],
        transform_func: Callable | None,
    ) -> list: ...

    def create_planetary_gear_visuals(
        self,
        layer_data: dict[str, Any],
        transform_func: Callable | None,
    ) -> list: ...


class VisualUpdater:
    """
    Updates mechanism visuals in real-time during parametric editing.

    Responsibilities:
    - Remove old visual items from scene
    - Create new visual items with updated parameters
    - Preserve visual properties during updates
    - Coordinate with handle positions

    Time Complexity: O(n) where n = number of visual items
    """

    def __init__(
        self,
        scene: QGraphicsScene | None = None,
        view: QGraphicsView | None = None,
        visuals_factory: VisualsFactory | None = None,
    ) -> None:
        """
        Initialize visual updater.

        Args:
            scene: Graphics scene containing mechanism visuals
            view: Graphics view to update
            visuals_factory: Factory for creating mechanism visuals
        """
        self._scene = scene
        self._view = view
        self._visuals_factory = visuals_factory
        self._logger = logging.getLogger(__name__)

    def set_scene(self, scene: QGraphicsScene) -> None:
        """Set the graphics scene."""
        self._scene = scene

    def set_view(self, view: QGraphicsView) -> None:
        """Set the graphics view."""
        self._view = view

    def set_visuals_factory(self, factory: VisualsFactory) -> None:
        """Set the visuals factory."""
        self._visuals_factory = factory

    def update_mechanism_visuals(
        self,
        mechanism_id: str,
        layer_data: dict[str, Any],
        transform_func: Callable | None = None,
        char_pos: Any | None = None,
    ) -> list:
        """
        Update visuals for a mechanism.

        Args:
            mechanism_id: ID of mechanism being updated
            layer_data: Full mechanism layer data
            transform_func: Optional coordinate transform function
            char_pos: Optional character position for cam mechanisms

        Returns:
            List of new visual items
        """
        if not self._scene or not self._visuals_factory:
            return []

        try:
            # Get existing visual items
            visual_items = layer_data.get("visual_items", [])

            # Capture visual properties before removal
            original_props = self._capture_visual_properties(visual_items)

            # Remove old visuals from scene
            self._remove_old_visuals(visual_items)

            # Create new visuals
            mechanism_type = layer_data.get("type")
            new_items = self._create_mechanism_visuals(
                layer_data, mechanism_type, transform_func, char_pos
            )

            # Restore visual properties
            self._restore_visual_properties(new_items, original_props)

            # Update the view
            if self._view:
                self._view.update()

            return new_items

        except Exception as e:
            self._logger.error(f"Error updating mechanism visuals: {e}")
            return []

    def _capture_visual_properties(
        self,
        visual_items: list,
    ) -> list[dict[str, Any]]:
        """Capture visual properties from items before removal."""
        properties = []

        for item in visual_items:
            if item and self.is_item_valid(item):
                try:
                    props = {
                        "pen": item.pen() if hasattr(item, "pen") else None,
                        "brush": item.brush() if hasattr(item, "brush") else None,
                        "z_value": item.zValue(),
                        "visible": item.isVisible(),
                        "enabled": item.isEnabled(),
                    }
                    properties.append(props)
                except RuntimeError:
                    properties.append({})
            else:
                properties.append({})

        return properties

    def _remove_old_visuals(self, visual_items: list) -> None:
        """Remove old visual items from scene."""
        for item in visual_items:
            if item and self.is_item_valid(item):
                try:
                    if item.scene() == self._scene:
                        self._scene.removeItem(item)
                except RuntimeError:
                    pass

    def _create_mechanism_visuals(
        self,
        layer_data: dict[str, Any],
        mechanism_type: str,
        transform_func: Callable | None = None,
        char_pos: Any | None = None,
    ) -> list:
        """Create visual items for a mechanism based on its type."""
        if not self._visuals_factory:
            return []

        new_items = []

        try:
            if mechanism_type == "4_bar_linkage":
                if hasattr(self._visuals_factory, "create_4bar_linkage_visuals"):
                    new_items = self._visuals_factory.create_4bar_linkage_visuals(
                        layer_data, transform_func
                    )
            elif mechanism_type == "cam":
                if hasattr(self._visuals_factory, "create_cam_visuals"):
                    new_items = self._visuals_factory.create_cam_visuals(
                        layer_data, transform_func, char_pos
                    )
            elif mechanism_type == "gear":
                if hasattr(self._visuals_factory, "create_gear_visuals"):
                    new_items = self._visuals_factory.create_gear_visuals(
                        layer_data, transform_func
                    )
            elif mechanism_type == "planetary_gear":
                if hasattr(self._visuals_factory, "create_planetary_gear_visuals"):
                    new_items = self._visuals_factory.create_planetary_gear_visuals(
                        layer_data, transform_func
                    )
        except Exception as e:
            self._logger.error(f"Error creating visuals for {mechanism_type}: {e}")

        return new_items

    def _restore_visual_properties(
        self,
        new_items: list,
        original_props: list[dict[str, Any]],
    ) -> None:
        """Restore visual properties to new items."""
        for i, item in enumerate(new_items):
            if i < len(original_props) and item:
                try:
                    props = original_props[i]
                    if props.get("pen") and hasattr(item, "setPen"):
                        item.setPen(props["pen"])
                    if props.get("brush") and hasattr(item, "setBrush"):
                        item.setBrush(props["brush"])
                    if props.get("z_value") is not None:
                        item.setZValue(props["z_value"])
                    if props.get("visible") is not None:
                        item.setVisible(props["visible"])
                    if props.get("enabled") is not None:
                        item.setEnabled(props["enabled"])
                except (RuntimeError, KeyError):
                    continue

    def is_item_valid(self, item: Any) -> bool:
        """Check if a graphics item is valid and not deleted."""
        try:
            _ = item.zValue()
            return True
        except (RuntimeError, AttributeError):
            return False

    def set_item_interaction(
        self,
        items: list,
        selectable: bool = True,
        movable: bool = True,
    ) -> None:
        """
        Set interaction flags on visual items.

        Args:
            items: List of graphics items
            selectable: Whether items should be selectable
            movable: Whether items should be movable
        """
        for item in items:
            if item and hasattr(item, "setFlag"):
                try:
                    item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, selectable)
                    item.setFlag(item.GraphicsItemFlag.ItemIsMovable, movable)
                except RuntimeError:
                    pass
