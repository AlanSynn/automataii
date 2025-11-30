"""
EditorTab Adapter.

Bridges EditorTab to ProjectStateManager.

Data Flow:
- Tab → StateManager: path_data_changed, motion_path_updated
- StateManager → Tab: parts_changed, skeleton_changed, paths_changed

Architecture: Application Layer (Hexagonal)
Pattern: Adapter
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtGui import QPainterPath

from ..models import (
    PartData,
    PathData,
    Point,
    SkeletonData,
)
from .base import TabAdapter

if TYPE_CHECKING:
    from automataii.presentation.qt.models import PartInfo

logger = logging.getLogger(__name__)


class EditorTabAdapter(TabAdapter):
    """
    Adapter for EditorTab.

    Transforms:
    - path_data_changed (dict) → set_path / load_paths
    - motion_path_updated (str, QPainterPath) → set_path

    Subscribes to:
    - parts_changed → set_parts_data
    - skeleton_changed → on_skeleton_updated, cache_initial_skeleton
    - paths_changed → (external path updates if any)
    """

    def _connect_tab_signals(self) -> None:
        """Connect to EditorTab's output signals."""
        if not self._tab:
            return

        self._tab.path_data_changed.connect(self._on_path_data_changed)
        self._tab.motion_path_updated.connect(self._on_motion_path_updated)
        logger.debug("EditorTabAdapter: Connected to tab signals")

    def _subscribe_to_state(self) -> None:
        """Subscribe to state manager signals."""
        self._state_manager.parts_changed.connect(self._on_state_parts_changed)
        self._state_manager.skeleton_changed.connect(self._on_state_skeleton_changed)
        self._state_manager.paths_changed.connect(self._on_state_paths_changed)
        logger.debug("EditorTabAdapter: Subscribed to state changes")

    def _disconnect_tab_signals(self) -> None:
        """Disconnect from tab signals."""
        if not self._tab:
            return

        try:
            self._tab.path_data_changed.disconnect(self._on_path_data_changed)
            self._tab.motion_path_updated.disconnect(self._on_motion_path_updated)
        except TypeError:
            pass

    def _unsubscribe_from_state(self) -> None:
        """Unsubscribe from state manager."""
        try:
            self._state_manager.parts_changed.disconnect(self._on_state_parts_changed)
            self._state_manager.skeleton_changed.disconnect(self._on_state_skeleton_changed)
            self._state_manager.paths_changed.disconnect(self._on_state_paths_changed)
        except TypeError:
            pass

    # =========================================================================
    # TAB → STATE MANAGER
    # =========================================================================

    def _on_path_data_changed(self, path_data: dict[str, QPainterPath]) -> None:
        """
        Handle path_data_changed signal from EditorTab.

        Args:
            path_data: Dict mapping part_name to QPainterPath
        """
        logger.info(f"EditorTabAdapter: Path data changed for {len(path_data)} parts")

        try:
            # Use batch mode for multiple path updates
            self._state_manager.begin_batch()

            for part_name, qpath in path_data.items():
                path = self._transform_qpath_to_pathdata(part_name, qpath)
                if path:
                    self._state_manager.set_path(path)

            self._state_manager.end_batch()

        except Exception as e:
            logger.exception(f"Error processing path_data_changed: {e}")

    def _on_motion_path_updated(self, part_name: str, qpath: QPainterPath) -> None:
        """
        Handle single motion path update from EditorTab.

        Args:
            part_name: Name of the part
            qpath: The QPainterPath
        """
        logger.debug(f"EditorTabAdapter: Motion path updated for '{part_name}'")

        try:
            path = self._transform_qpath_to_pathdata(part_name, qpath)
            if path:
                self._state_manager.set_path(path)

        except Exception as e:
            logger.exception(f"Error processing motion_path_updated: {e}")

    # =========================================================================
    # STATE MANAGER → TAB
    # =========================================================================

    def _on_state_parts_changed(self, parts: dict[str, PartData]) -> None:
        """
        Handle parts changes from state manager.

        Transforms PartData to PartInfo and calls tab's set_parts_data.
        """
        if not self._tab:
            return

        logger.info(f"EditorTabAdapter: Forwarding {len(parts)} parts to tab")

        try:
            # Transform PartData to PartInfo format
            parts_info = self._transform_parts_to_partinfo(parts)

            # Call tab's method
            if hasattr(self._tab, "set_parts_data"):
                self._tab.set_parts_data(parts_info)

        except Exception as e:
            logger.exception(f"Error forwarding parts to tab: {e}")

    def _on_state_skeleton_changed(self, skeleton: SkeletonData | None) -> None:
        """
        Handle skeleton changes from state manager.

        Forwards to tab's on_skeleton_updated and cache_initial_skeleton.
        """
        if not self._tab:
            return

        # Convert to dict format
        skeleton_dict = skeleton.to_dict() if skeleton else None

        # Update display
        if hasattr(self._tab, "on_skeleton_updated"):
            self._tab.on_skeleton_updated(skeleton_dict)

        # Cache initial skeleton
        if hasattr(self._tab, "cache_initial_skeleton"):
            self._tab.cache_initial_skeleton(skeleton_dict)

    def _on_state_paths_changed(self, paths: dict[str, PathData]) -> None:
        """
        Handle path changes from state manager (external updates).

        This is for cases where paths are modified externally
        (e.g., loaded from project file).
        """
        if not self._tab:
            return

        # Only update if we have parts loaded
        if not hasattr(self._tab, "current_editor_items"):
            return

        # Convert PathData back to QPainterPath format if needed
        # This would be used when loading a project
        logger.debug(f"EditorTabAdapter: State paths changed ({len(paths)} paths)")

    # =========================================================================
    # DATA TRANSFORMATIONS
    # =========================================================================

    def _transform_qpath_to_pathdata(
        self,
        part_name: str,
        qpath: QPainterPath,
    ) -> PathData | None:
        """
        Transform QPainterPath to PathData.

        Args:
            part_name: Name of the part
            qpath: The QPainterPath from EditorTab

        Returns:
            PathData or None if empty path
        """
        if qpath is None or qpath.isEmpty():
            return None

        # Extract points from QPainterPath
        points: list[Point] = []

        for i in range(qpath.elementCount()):
            elem = qpath.elementAt(i)
            points.append(Point(x=elem.x, y=elem.y))

        if not points:
            return None

        # Check if path is closed
        is_closed = False
        if len(points) >= 2:
            first = points[0]
            last = points[-1]
            # Consider closed if start and end are very close
            if abs(first.x - last.x) < 1.0 and abs(first.y - last.y) < 1.0:
                is_closed = True

        return PathData(
            part_name=part_name,
            points=tuple(points),
            is_closed=is_closed,
            enabled=True,
        )

    def _transform_parts_to_partinfo(
        self,
        parts: dict[str, PartData],
    ) -> dict[str, Any]:
        """
        Transform PartData dict to PartInfo dict format.

        This creates the format expected by EditorTab.set_parts_data().

        Args:
            parts: Dict of PartData from state manager

        Returns:
            Dict in PartInfo format
        """
        from automataii.presentation.qt.models import PartInfo

        parts_info: dict[str, PartInfo] = {}

        for name, part_data in parts.items():
            try:
                # Create PartInfo from PartData
                # Note: PartInfo may have different field names
                part_info = PartInfo(
                    name=name,
                    image_path=part_data.texture_path,
                    roi=[
                        part_data.transform.x,
                        part_data.transform.y,
                        0,  # width - not stored in PartData
                        0,  # height - not stored in PartData
                    ],
                    local_pivot_offset=[0, 0],
                    z_value=float(part_data.z_index),
                    parent_joint=part_data.anchor_joint,
                )
                parts_info[name] = part_info

            except Exception as e:
                logger.warning(f"Error transforming part '{name}': {e}")
                continue

        return parts_info

    def _transform_pathdata_to_qpath(self, path_data: PathData) -> QPainterPath:
        """
        Transform PathData back to QPainterPath.

        Args:
            path_data: PathData from state manager

        Returns:
            QPainterPath
        """
        qpath = QPainterPath()

        if not path_data.points:
            return qpath

        points = list(path_data.points)

        # Move to first point
        qpath.moveTo(points[0].x, points[0].y)

        # Line to subsequent points
        for point in points[1:]:
            qpath.lineTo(point.x, point.y)

        # Close path if needed
        if path_data.is_closed and len(points) > 2:
            qpath.closeSubpath()

        return qpath
