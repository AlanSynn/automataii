"""
Service class for skeleton-related business logic.

This service handles skeleton operations and part positioning
that were previously embedded in the MechanismDesignTab class.

Architecture Note:
- This is APPLICATION layer - NO direct Qt dependencies
- Position updates are done via callback/callable injection
- Callers in presentation layer provide Qt-specific implementation
"""

import math
from collections.abc import Callable, Mapping
from typing import Any

from automataii.domain.animation.part_definitions import BODY_PARTS


class SkeletonService:
    """Service for handling skeleton business logic."""

    def __init__(self) -> None:
        """Initialize the skeleton service."""
        pass

    @staticmethod
    def _resolve_joint_data(
        anchor_joint_id: object,
        joints_dict: Mapping[str, Any],
        joint_map: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        anchor = str(anchor_joint_id or "")
        candidate_ids = [anchor]
        mapped = joint_map.get(anchor)
        if isinstance(mapped, str):
            candidate_ids.append(mapped)

        for candidate_id in candidate_ids:
            joint_data = joints_dict.get(candidate_id)
            if isinstance(joint_data, Mapping):
                return joint_data

        for candidate_id in candidate_ids:
            if not candidate_id:
                continue
            for joint_id, joint_data in joints_dict.items():
                if not isinstance(joint_data, Mapping):
                    continue
                if joint_id.startswith(f"{candidate_id}_") or joint_id.startswith(
                    f"{candidate_id}."
                ):
                    return joint_data
        return None

    @staticmethod
    def _joint_position(joint_data: Mapping[str, Any]) -> tuple[float, float] | None:
        for key in ("position", "scene_position"):
            raw_pos = joint_data.get(key)
            if not isinstance(raw_pos, list | tuple) or len(raw_pos) < 2:
                continue
            try:
                x_coord = float(raw_pos[0])
                y_coord = float(raw_pos[1])
            except (TypeError, ValueError):
                continue
            if math.isfinite(x_coord) and math.isfinite(y_coord):
                return x_coord, y_coord
        return None

    @staticmethod
    def _anchor_joint_id(part_name: str, part_item: Any, part_info: Any) -> object:
        return (
            getattr(part_info, "anchor_joint_id", None)
            or getattr(part_item, "anchor_joint_id", None)
            or BODY_PARTS.get(part_name, {}).get("anchor_joint")
            or ""
        )

    def position_parts_at_anchor_joints(
        self,
        current_editor_items: dict,
        parts_data: dict,
        initial_skeleton_data_cache: dict,
        position_setter: Callable[[Any, tuple[float, float]], None] | None = None,
        rotation_setter: Callable[[Any, float], None] | None = None,
    ) -> int:
        """
        Position parts at their anchor joints using cached skeleton data.

        Args:
            current_editor_items: Dictionary of current editor items
            parts_data: Parts data dictionary
            initial_skeleton_data_cache: Cached skeleton data
            position_setter: Callable to set position on part_item (injected from presentation)
                            Signature: (part_item, (x, y)) -> None
            rotation_setter: Callable to set rotation on part_item (injected from presentation)
                            Signature: (part_item, rotation_degrees) -> None

        Returns:
            Number of parts successfully positioned
        """
        if not initial_skeleton_data_cache:
            return 0

        positioned_count = 0
        joints_dict = initial_skeleton_data_cache.get("joints", {})
        if not isinstance(joints_dict, Mapping):
            return 0
        raw_joint_map = initial_skeleton_data_cache.get("joint_map", {})
        joint_map = raw_joint_map if isinstance(raw_joint_map, Mapping) else {}

        for part_name, part_item in current_editor_items.items():
            part_info = parts_data.get(part_name)
            if not part_info:
                continue
            joint_data = self._resolve_joint_data(
                self._anchor_joint_id(part_name, part_item, part_info), joints_dict, joint_map
            )
            if joint_data is None:
                continue
            pos = self._joint_position(joint_data)
            if pos is None:
                continue
            if position_setter:
                position_setter(part_item, pos)
            # Do not apply generic skeleton joint rotation during initial placement.
            # Joint rotation is often defined in a different reference frame and can
            # rotate body-part textures unexpectedly on character replacement.
            if rotation_setter and "part_rotation_degrees" in joint_data:
                rotation_setter(part_item, float(joint_data["part_rotation_degrees"]))
            positioned_count += 1

        return positioned_count
