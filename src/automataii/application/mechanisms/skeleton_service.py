"""
Service class for skeleton-related business logic.

This service handles skeleton operations and part positioning
that were previously embedded in the MechanismDesignTab class.

Architecture Note:
- This is APPLICATION layer - NO direct Qt dependencies
- Position updates are done via callback/callable injection
- Callers in presentation layer provide Qt-specific implementation
"""

from collections.abc import Callable
from typing import Any


class SkeletonService:
    """Service for handling skeleton business logic."""

    def __init__(self) -> None:
        """Initialize the skeleton service."""
        pass

    def position_parts_at_anchor_joints(
        self,
        current_editor_items: dict,
        parts_data: dict,
        initial_skeleton_data_cache: dict,
        position_setter: Callable[[Any, tuple[float, float]], None] | None = None,
    ) -> int:
        """
        Position parts at their anchor joints using cached skeleton data.

        Args:
            current_editor_items: Dictionary of current editor items
            parts_data: Parts data dictionary
            initial_skeleton_data_cache: Cached skeleton data
            position_setter: Callable to set position on part_item (injected from presentation)
                            Signature: (part_item, (x, y)) -> None

        Returns:
            Number of parts successfully positioned
        """
        if not initial_skeleton_data_cache:
            return 0

        positioned_count = 0
        joints_dict = initial_skeleton_data_cache.get("joints", {})

        for part_name, part_item in current_editor_items.items():
            part_info = parts_data.get(part_name)
            if part_info and part_info.anchor_joint_id in joints_dict:
                joint_data = joints_dict[part_info.anchor_joint_id]
                joint_pos = joint_data.get("position", [0, 0])
                if len(joint_pos) >= 2:
                    pos = (float(joint_pos[0]), float(joint_pos[1]))
                    if position_setter:
                        position_setter(part_item, pos)
                    positioned_count += 1

        return positioned_count
