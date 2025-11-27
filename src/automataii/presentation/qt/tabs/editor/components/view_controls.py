"""
View Controls - Zoom, pan, and view reset operations.

Extracted from EditorTab god class. Contains thin wrapper methods
that delegate to EditorView for actual implementation.

Design Pattern: Facade (simplifies EditorView interface for EditorTab)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSlot

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene

    from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
    from automataii.presentation.qt.views.editor_view import EditorView


class ViewControls(QObject):
    """
    Facade for view control operations.

    Provides a clean interface for zoom, pan, and view reset operations
    by delegating to the underlying EditorView. Also handles view state
    synchronization like zoom combo updates.

    Architecture: Presentation layer facade over EditorView
    """

    def __init__(
        self,
        editor_view: EditorView,
        editor_scene: QGraphicsScene,
        parent: QObject | None = None,
    ) -> None:
        """
        Initialize view controls.

        Args:
            editor_view: The EditorView to control
            editor_scene: The scene being viewed
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._editor_view = editor_view
        self._editor_scene = editor_scene

    @pyqtSlot()
    def zoom_in(self) -> None:
        """
        Increase zoom level.

        Delegates to EditorView.zoom_in() which handles
        the actual scale transformation.
        """
        if self._editor_view:
            self._editor_view.zoom_in()

    @pyqtSlot()
    def zoom_out(self) -> None:
        """
        Decrease zoom level.

        Delegates to EditorView.zoom_out() which handles
        the actual scale transformation.
        """
        if self._editor_view:
            self._editor_view.zoom_out()

    @pyqtSlot()
    def zoom_to_fit(self) -> None:
        """
        Fit all content in view.

        Delegates to EditorView.zoom_to_fit() which calculates
        the appropriate scale to show all scene content.
        """
        if self._editor_view:
            self._editor_view.zoom_to_fit()

    @pyqtSlot()
    def reset_view(self) -> None:
        """
        Reset view to default state.

        Resets zoom level, pan position, and rotation
        to initial values.
        """
        if self._editor_view:
            self._editor_view.reset_view()

    @pyqtSlot()
    def undo(self) -> None:
        """
        Undo last view/edit action.

        Delegates to EditorView's undo stack if available.
        """
        if self._editor_view:
            self._editor_view.undo()

    @pyqtSlot()
    def redo(self) -> None:
        """
        Redo last undone action.

        Delegates to EditorView's redo stack if available.
        """
        if self._editor_view:
            self._editor_view.redo()

    def center_on_character(
        self,
        editor_items: dict[str, CharacterPartItem],
    ) -> None:
        """
        Center the view on all character parts.

        Calculates the bounding box of all parts and centers
        the view on that region with padding.

        Args:
            editor_items: Dictionary of part name to CharacterPartItem

        Note:
            Does not change zoom level, only pan position.
        """
        if not self._editor_scene or not editor_items:
            return

        # Calculate bounding box of all parts
        combined_rect = None
        for part_info in editor_items.values():
            # Handle both CharacterPartItem directly and dict with graphics_item
            if hasattr(part_info, "sceneBoundingRect"):
                part_item = part_info
            elif isinstance(part_info, dict):
                part_item = part_info.get("graphics_item")
            else:
                continue

            if part_item and part_item.scene():
                part_rect = part_item.sceneBoundingRect()
                if combined_rect is None:
                    combined_rect = part_rect
                else:
                    combined_rect = combined_rect.united(part_rect)

        if combined_rect:
            # Add padding around the character
            padding = 50
            combined_rect.adjust(-padding, -padding, padding, padding)

            # Center on the character without changing zoom
            center = combined_rect.center()
            self._editor_view.centerOn(center)
            logging.debug(f"ViewControls: Centered view on {center}")

    def update_zoom_combo_from_view(self, scale_factor: float) -> None:
        """
        Update zoom combo box to reflect current scale.

        Note: This is currently a no-op as the zoom combo UI
        has been removed. Kept for API compatibility.

        Args:
            scale_factor: Current view scale factor
        """
        # UI element removed - no-op for backward compatibility
        pass
