"""
View Utilities Service for MechanismDesignTab.

Extracted from MechanismDesignTab as part of god class decomposition.
Handles view-related operations like centering, zooming, and bounds calculations.

Design Pattern: Service (encapsulates view utility operations)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainter

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView


class ViewUtilitiesService:
    """
    Provides utility methods for view manipulation.

    Responsibilities:
    - Calculate combined bounding rectangles
    - Center view on content
    - Apply render hints based on performance settings
    """

    DEFAULT_PADDING = 50

    def calculate_character_bounds(
        self,
        *,
        current_editor_items: dict[str, Any],
        skeleton_joint_items: dict[str, Any] | None = None,
        padding: float = DEFAULT_PADDING,
    ) -> QRectF | None:
        """
        Calculate bounding rectangle for all character elements.

        Args:
            current_editor_items: Dict of part name to CharacterPartItem
            skeleton_joint_items: Dict of joint name to QGraphicsItem
            padding: Padding to add around bounds

        Returns:
            QRectF containing all elements with padding, or None if empty
        """
        combined_rect: QRectF | None = None

        # Include parts
        if current_editor_items:
            for _part_name, part_item in current_editor_items.items():
                if part_item and hasattr(part_item, "scene") and part_item.scene():
                    try:
                        part_rect = part_item.sceneBoundingRect()
                        if combined_rect is None:
                            combined_rect = part_rect
                        else:
                            combined_rect = combined_rect.united(part_rect)
                    except RuntimeError:
                        pass  # Item deleted

        # Include skeleton joints
        if skeleton_joint_items:
            for joint_item in skeleton_joint_items.values():
                if joint_item and hasattr(joint_item, "scene") and joint_item.scene():
                    try:
                        joint_rect = joint_item.sceneBoundingRect()
                        if combined_rect is None:
                            combined_rect = joint_rect
                        else:
                            combined_rect = combined_rect.united(joint_rect)
                    except RuntimeError:
                        pass  # Item deleted

        # Add padding
        if combined_rect:
            combined_rect.adjust(-padding, -padding, padding, padding)

        return combined_rect

    def center_view_on_character(
        self,
        view: QGraphicsView,
        *,
        current_editor_items: dict[str, Any],
        skeleton_joint_items: dict[str, Any] | None = None,
        padding: float = DEFAULT_PADDING,
    ) -> bool:
        """
        Center the view on character content.

        Args:
            view: QGraphicsView to center
            current_editor_items: Dict of part items
            skeleton_joint_items: Dict of skeleton joint items
            padding: Padding around bounds

        Returns:
            True if centering succeeded, False if no content
        """
        bounds = self.calculate_character_bounds(
            current_editor_items=current_editor_items,
            skeleton_joint_items=skeleton_joint_items,
            padding=padding,
        )

        if bounds:
            center = bounds.center()
            view.centerOn(center)
            return True

        return False

    def apply_render_hints(
        self,
        view: QGraphicsView,
        *,
        antialiasing: bool = True,
    ) -> None:
        """
        Apply render hints to view.

        Args:
            view: QGraphicsView to configure
            antialiasing: Whether to enable antialiasing
        """
        if view and hasattr(view, "setRenderHint"):
            try:
                view.setRenderHint(QPainter.RenderHint.Antialiasing, antialiasing)
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

    def fit_view_to_content(
        self,
        view: QGraphicsView,
        scene: QGraphicsScene,
        *,
        margin: float = 20,
    ) -> None:
        """
        Fit view to show all scene content.

        Args:
            view: QGraphicsView to adjust
            scene: QGraphicsScene with content
            margin: Margin to preserve around content
        """
        if not view or not scene:
            return

        try:
            scene_rect = scene.itemsBoundingRect()
            if scene_rect.isValid():
                scene_rect.adjust(-margin, -margin, margin, margin)
                view.fitInView(scene_rect, 1)  # Qt.AspectRatioMode.KeepAspectRatio
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)


# Singleton instance
_default_service: ViewUtilitiesService | None = None


def get_view_utilities_service() -> ViewUtilitiesService:
    """Get or create the default view utilities service."""
    global _default_service
    if _default_service is None:
        _default_service = ViewUtilitiesService()
    return _default_service
