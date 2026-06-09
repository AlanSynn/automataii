"""
Path Query Service - Pure query functions for motion path state.

Extracted from EditorTab god class. Contains read-only queries
about motion path existence and collection.

Time Complexity: O(n) for most operations where n = number of parts
Space Complexity: O(1) for existence queries, O(n) for collection
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from PyQt6.QtGui import QPainterPath

if TYPE_CHECKING:
    from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
    from automataii.presentation.qt.models import PartInfo
    from automataii.presentation.qt.views.editor_view import EditorView


class HasMotionPath(Protocol):
    """Protocol for objects that may have a motion path."""

    motion_path: QPainterPath | None


class PathQueryService:
    """
    Service for querying motion path state.

    This service provides read-only access to motion path information
    without mutating any state. It operates on provided state references
    rather than owning state.

    Design Pattern: Service Object (Stateless operations on external state)
    Architecture: Hexagonal - this is a domain service accessed via ports
    """

    def __init__(
        self,
        editor_items: dict[str, CharacterPartItem],
        parts_info: dict[str, PartInfo],
        editor_view: EditorView,
    ) -> None:
        """
        Initialize the path query service.

        Args:
            editor_items: Reference to current editor items (CharacterPartItem instances)
            parts_info: Reference to current parts info (PartInfo instances)
            editor_view: Reference to the editor view (for final_paths_map access)
        """
        self._editor_items = editor_items
        self._parts_info = parts_info
        self._editor_view = editor_view

    def has_any_motion_path(self) -> bool:
        """
        Check if any part has a motion path defined.

        Returns:
            True if at least one part has a non-empty motion path

        Time Complexity: O(n) worst case, O(1) best case (early exit)
        """
        for part_item in self._editor_items.values():
            if self._item_has_path(part_item):
                return True
        return False

    def has_motion_path(self, part_name: str) -> bool:
        """
        Check if a specific part has a motion path defined.

        Checks multiple sources in order of precedence:
        1. EditorView's final_paths_map (committed green paths)
        2. CharacterPartItem's motion_path attribute
        3. PartInfo's motion_path in project data

        Args:
            part_name: Name of the part to check

        Returns:
            True if the part has a non-empty motion path

        Time Complexity: O(1) amortized (dict lookups)
        """
        if not part_name:
            return False

        # Check 1: EditorView's final paths map (green paths)
        if hasattr(self._editor_view, "final_paths_map"):
            if part_name in self._editor_view.final_paths_map:
                path_item = self._editor_view.final_paths_map[part_name]
                if path_item and path_item.scene():
                    return True

        # Check 2: CharacterPartItem in current_editor_items
        if part_name in self._editor_items:
            part_item = self._editor_items[part_name]
            if self._item_has_path(part_item):
                return True

        # Check 3: PartInfo in project data
        if part_name in self._parts_info:
            part_info = self._parts_info[part_name]
            if self._part_info_has_path(part_info):
                return True

        return False

    def get_path_count(self) -> int:
        """
        Get the total number of motion paths defined.

        Returns:
            Count of parts with non-empty motion paths

        Time Complexity: O(n) where n = number of editor items
        """
        count = 0
        for part_item in self._editor_items.values():
            if self._item_has_path(part_item):
                count += 1
        return count

    def collect_path_data(self) -> dict[str, QPainterPath]:
        """
        Collect all motion paths from parts.

        Gathers paths from both project data (PartInfo) and
        editor items (CharacterPartItem), with project data
        taking precedence.

        Returns:
            Dictionary mapping part names to their QPainterPath objects

        Time Complexity: O(n) where n = max(parts_info, editor_items)
        """
        path_data: dict[str, QPainterPath] = {}

        # First check in current_parts_info (project data - higher precedence)
        if self._parts_info:
            for part_name, part_info in self._parts_info.items():
                if hasattr(part_info, "motion_path") and part_info.motion_path:
                    if isinstance(part_info.motion_path, QPainterPath):
                        if not part_info.motion_path.isEmpty():
                            path_data[part_name] = part_info.motion_path

        # Also check in current_editor_items as backup
        for part_name, part_item in self._editor_items.items():
            if part_name not in path_data:  # Don't override project data
                if self._item_has_path(part_item):
                    path_data[part_name] = part_item.motion_path

        logging.debug(
            f"PathQueryService: Collected {len(path_data)} motion paths: {list(path_data.keys())}"
        )
        return path_data

    def has_motion_paths_in_scene(self, scene_items: list) -> bool:
        """
        Check if any scene items have motion paths.

        This is an alternative check that iterates scene items directly,
        useful for validation scenarios.

        Args:
            scene_items: List of QGraphicsItem from the scene

        Returns:
            True if any CharacterPartItem has a motion path
        """
        from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem

        for item in scene_items:
            if isinstance(item, CharacterPartItem):
                if self._item_has_path(item):
                    return True
        return False

    # --- Private Helper Methods ---

    @staticmethod
    def _item_has_path(item: HasMotionPath) -> bool:
        """Check if a CharacterPartItem has a valid motion path."""
        if hasattr(item, "motion_path") and item.motion_path:
            if hasattr(item.motion_path, "isEmpty"):
                return not item.motion_path.isEmpty()
        return False

    @staticmethod
    def _part_info_has_path(part_info: PartInfo) -> bool:
        """Check if a PartInfo has a valid motion path."""
        if not hasattr(part_info, "motion_path") or not part_info.motion_path:
            return False

        motion_path = part_info.motion_path

        if hasattr(motion_path, "isEmpty"):
            return not motion_path.isEmpty()
        elif isinstance(motion_path, list):
            return len(motion_path) > 0
        else:
            return motion_path is not None
