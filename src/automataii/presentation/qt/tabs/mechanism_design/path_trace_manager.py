"""Path trace management for mechanism animations.

This module provides PathTraceManager for managing mechanism path traces during
animation. It handles point buffering, stride gating for visual updates, and
QGraphicsScene integration.

Architecture:
- PathTraceConfig: Configuration dataclass for trace parameters
- PathTraceManager: Main manager class for trace lifecycle

Pattern: Manager + Strategy (config-driven behavior)

Author: Alan Synn
Date: 2025-11-22
"""

import logging
from dataclasses import dataclass, field

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsScene

logger = logging.getLogger(__name__)


@dataclass
class PathTraceConfig:
    """Configuration for path tracing.

    Attributes:
        max_points: Maximum points to store per trace (prevents unbounded growth)
        update_stride: Update visual every N frames (reduces rendering cost)
        warmup_frames: Skip first N frames before recording trace (avoids initial glitches)
        pen_color: Trace path color
        pen_width: Trace path width in pixels
        z_value: Z-level for trace items in scene
    """

    max_points: int = 500
    update_stride: int = 2
    warmup_frames: int = 5  # Skip first 5 frames to avoid initial position glitches
    pen_color: QColor = field(default_factory=lambda: QColor("#ff3030"))
    pen_width: float = 3.0
    z_value: int = 100


class PathTraceManager:
    """Manages mechanism path traces during animation.

    Responsibilities:
    - Maintains point buffers for each mechanism
    - Enforces max point limits
    - Applies stride gating for visual updates
    - Manages QGraphicsPathItem lifecycle

    Thread Safety: NOT thread-safe (Qt UI thread only)

    Complexity:
        Time: O(N) per update_trace call (N = max_points)
        Space: O(M * max_points) where M = number of mechanisms

    Example:
        >>> config = PathTraceConfig(max_points=100, update_stride=3)
        >>> manager = PathTraceManager(config)
        >>> manager.init_trace("mech_1", scene)
        >>> for i in range(100):
        ...     manager.update_trace("mech_1", QPointF(i, i), frame_tick=i)
        >>> manager.clear_trace("mech_1", scene)
    """

    def __init__(self, config: PathTraceConfig | None = None):
        """Initialize path trace manager.

        Args:
            config: Optional configuration. Uses defaults if None.
        """
        self._config = config or PathTraceConfig()
        self._trace_items: dict[str, QGraphicsPathItem] = {}
        self._trace_points: dict[str, list[QPointF]] = {}
        self._trace_paths: dict[str, QPainterPath] = {}
        # Track path sync state for incremental updates
        self._path_point_count: dict[str, int] = {}  # Points already in path
        # Track frame count per mechanism for warmup skipping
        self._frame_counts: dict[str, int] = {}

        logger.debug(f"PathTraceManager initialized with config: {self._config}")

    def init_trace(
        self,
        mechanism_id: str,
        scene: QGraphicsScene,
        initial_position: QPointF | None = None,
    ) -> None:
        """Initialize or reinitialize trace for a mechanism.

        Clears any existing trace and creates new visual item.

        Args:
            mechanism_id: Unique identifier for mechanism.
            scene: QGraphicsScene to add trace item to.
            initial_position: Optional initial position (t=0 coupler point).
                              If provided, the trace will start from this position.

        Side Effects:
            - Removes old trace item from scene (if exists)
            - Creates new QGraphicsPathItem and adds to scene
            - Clears trace point buffer
            - If initial_position is provided, adds it as the first trace point
        """
        # Remove old item from scene if exists
        if mechanism_id in self._trace_items:
            old_item = self._trace_items[mechanism_id]
            if old_item and old_item.scene() == scene:
                scene.removeItem(old_item)

        # Initialize data structures
        self._trace_points[mechanism_id] = []
        self._trace_paths[mechanism_id] = QPainterPath()
        self._path_point_count[mechanism_id] = 0  # No points in path yet
        self._frame_counts[mechanism_id] = 0  # Reset frame counter for warmup

        # Create visual trace item
        trace_item = QGraphicsPathItem()

        # Apply pen styling from config
        trace_pen = QPen(self._config.pen_color, self._config.pen_width)
        trace_pen.setStyle(Qt.PenStyle.SolidLine)
        trace_pen.setCosmetic(True)  # Consistent width regardless of zoom
        trace_item.setPen(trace_pen)

        # Set Z-value for layering
        trace_item.setZValue(self._config.z_value)

        # Add to scene and store
        scene.addItem(trace_item)
        self._trace_items[mechanism_id] = trace_item

        # Add initial position if provided (t=0 coupler point)
        if initial_position is not None:
            # Validate position (same logic as update_trace)
            if abs(initial_position.x()) >= 10 or abs(initial_position.y()) >= 10:
                self._trace_points[mechanism_id].append(initial_position)
                logger.debug(
                    f"Initialized trace for mechanism {mechanism_id} with initial position: "
                    f"({initial_position.x():.1f}, {initial_position.y():.1f})"
                )
            else:
                logger.debug(
                    f"Initialized trace for mechanism {mechanism_id} (initial position rejected as invalid)"
                )
        else:
            logger.debug(f"Initialized trace for mechanism {mechanism_id}")

    def update_trace(
        self,
        mechanism_id: str,
        position: QPointF,
        frame_tick: int,
        scene: QGraphicsScene | None = None,
    ) -> None:
        """Update trace with new position.

        Args:
            mechanism_id: Unique identifier for mechanism.
            position: New position point to add to trace.
            frame_tick: Current animation frame tick (for stride gating).
            scene: Optional scene for auto-initialization if trace doesn't exist.

        Behavior:
            - Validates position (rejects (0,0) or very small values)
            - Skips first N frames (warmup) to avoid initial glitches
            - Appends position to point buffer
            - Enforces max_points limit (keeps last N points)
            - Updates visual path if stride condition met OR first 2 points

        Complexity: O(max_points) worst case (when trimming buffer)
        """
        # Auto-initialize if needed
        if mechanism_id not in self._trace_points:
            if scene is None:
                logger.warning(
                    f"Cannot auto-initialize trace for {mechanism_id}: no scene provided"
                )
                return
            self.init_trace(mechanism_id, scene)

        # Increment frame counter and check warmup period
        self._frame_counts[mechanism_id] = self._frame_counts.get(mechanism_id, 0) + 1
        frame_count = self._frame_counts[mechanism_id]

        # Skip recording during warmup period to avoid initial position glitches
        if frame_count <= self._config.warmup_frames:
            logger.debug(
                f"Skipping trace for {mechanism_id} during warmup (frame {frame_count}/{self._config.warmup_frames})"
            )
            return

        # Validate position - reject positions at or near (0, 0) which indicate
        # the transform function wasn't properly applied or mechanism not initialized
        if abs(position.x()) < 10 and abs(position.y()) < 10:
            logger.debug(
                f"Rejecting invalid trace position for {mechanism_id}: ({position.x():.1f}, {position.y():.1f})"
            )
            return

        # Append point to buffer
        self._trace_points[mechanism_id].append(position)

        # Enforce max points limit (triggers full rebuild when trimmed)
        needs_full_rebuild = False
        if len(self._trace_points[mechanism_id]) > self._config.max_points:
            self._trace_points[mechanism_id] = self._trace_points[mechanism_id][
                -self._config.max_points :
            ]
            needs_full_rebuild = True  # Buffer trimmed, path is now out of sync
            self._path_point_count[mechanism_id] = 0  # Reset sync state
            logger.debug(
                f"Trimmed trace for {mechanism_id}: {len(self._trace_points[mechanism_id])} points"
            )

        # Stride gating: update visual only on stride boundaries OR for first 2 points
        points_count = len(self._trace_points[mechanism_id])
        should_update = (frame_tick % self._config.update_stride == 0) or (points_count <= 2)

        if should_update:
            if needs_full_rebuild:
                self._rebuild_path_full(mechanism_id)
            else:
                self._update_path_incremental(mechanism_id)

    def clear_trace(self, mechanism_id: str, scene: QGraphicsScene) -> None:
        """Clear trace for a specific mechanism.

        Args:
            mechanism_id: Unique identifier for mechanism.
            scene: QGraphicsScene to remove trace item from.

        Side Effects:
            - Removes QGraphicsPathItem from scene
            - Clears trace point buffer
            - Clears cached QPainterPath
        """
        # Remove from scene
        if mechanism_id in self._trace_items:
            item = self._trace_items[mechanism_id]
            if item and item.scene() == scene:
                scene.removeItem(item)
            del self._trace_items[mechanism_id]

        # Remove data structures
        if mechanism_id in self._trace_points:
            del self._trace_points[mechanism_id]

        if mechanism_id in self._trace_paths:
            del self._trace_paths[mechanism_id]

        if mechanism_id in self._path_point_count:
            del self._path_point_count[mechanism_id]

        if mechanism_id in self._frame_counts:
            del self._frame_counts[mechanism_id]

        logger.debug(f"Cleared trace for mechanism {mechanism_id}")

    def clear_all_traces(self, scene: QGraphicsScene) -> None:
        """Clear all traces.

        Args:
            scene: QGraphicsScene to remove all trace items from.

        Side Effects:
            - Removes all QGraphicsPathItems from scene
            - Clears all trace point buffers
            - Clears all cached QPainterPaths
        """
        # Remove all items from scene
        for mechanism_id in list(self._trace_items.keys()):
            self.clear_trace(mechanism_id, scene)

        logger.debug("Cleared all traces")

    def clear_trace_for_part(
        self,
        part_name: str,
        mechanism_layers: dict[str, dict],
        scene: QGraphicsScene,
    ) -> None:
        """Clear traces for all mechanisms associated with a part.

        Args:
            part_name: Name of the part to clear traces for.
            mechanism_layers: Dict mapping mechanism_id to layer_data.
            scene: QGraphicsScene to remove trace items from.
        """
        for mech_id in list(self._trace_items.keys()):
            layer_data = mechanism_layers.get(mech_id)
            if layer_data and layer_data.get("part_name") == part_name:
                self.clear_trace(mech_id, scene)

    def get_trace_item(self, mechanism_id: str) -> QGraphicsPathItem | None:
        """Get trace item for mechanism.

        Args:
            mechanism_id: Unique identifier for mechanism.

        Returns:
            QGraphicsPathItem if exists, None otherwise.
        """
        return self._trace_items.get(mechanism_id)

    def set_trace_visible(self, mechanism_id: str, visible: bool) -> None:
        """Set trace visibility.

        Args:
            mechanism_id: Unique identifier for mechanism.
            visible: True to show, False to hide.

        Side Effects:
            - Calls setVisible() on QGraphicsPathItem if exists
        """
        item = self._trace_items.get(mechanism_id)
        if item:
            item.setVisible(visible)
            logger.debug(f"Set trace visibility for {mechanism_id}: {visible}")

    def get_trace_points(self, mechanism_id: str) -> list[QPointF]:
        """Get copy of trace points for mechanism.

        Args:
            mechanism_id: Unique identifier for mechanism.

        Returns:
            Copy of point buffer (empty list if not exists).
        """
        if mechanism_id in self._trace_points:
            return list(self._trace_points[mechanism_id])  # Return copy
        return []

    def get_all_mechanism_ids(self) -> list[str]:
        """Get all mechanism IDs with active traces.

        Returns:
            List of mechanism IDs that have initialized traces.

        Complexity: O(1) - returns dict keys view
        """
        return list(self._trace_items.keys())

    def has_trace(self, mechanism_id: str) -> bool:
        """Check if trace exists for mechanism.

        Args:
            mechanism_id: Unique identifier for mechanism.

        Returns:
            True if trace exists, False otherwise.

        Complexity: O(1) - dict membership check
        """
        return mechanism_id in self._trace_items

    def clear_trace_points_only(self, mechanism_id: str) -> None:
        """Clear trace points but keep visual item.

        Useful for resetting animation traces without destroying
        the QGraphicsPathItem.

        Args:
            mechanism_id: Unique identifier for mechanism.

        Side Effects:
            - Clears trace point buffer
            - Resets frame counter (warmup restarts)
            - Sets visual path to empty QPainterPath
            - Does NOT remove item from scene

        Complexity: O(1)
        """
        if mechanism_id in self._trace_points:
            self._trace_points[mechanism_id].clear()

        # Reset visual path
        empty_path = QPainterPath()
        if mechanism_id in self._trace_paths:
            self._trace_paths[mechanism_id] = empty_path

        # Reset sync state to prevent stale incremental update logic
        if mechanism_id in self._path_point_count:
            self._path_point_count[mechanism_id] = 0

        # Reset frame counter so warmup restarts
        if mechanism_id in self._frame_counts:
            self._frame_counts[mechanism_id] = 0

        # Update visual item to show empty path
        item = self._trace_items.get(mechanism_id)
        if item:
            item.setPath(empty_path)

        logger.debug(f"Cleared trace points only for mechanism {mechanism_id}")

    def _rebuild_path_full(self, mechanism_id: str) -> None:
        """Rebuild QPainterPath from entire point buffer.

        Used when buffer is trimmed and path needs complete rebuild.

        Args:
            mechanism_id: Unique identifier for mechanism.

        Side Effects:
            - Updates _trace_paths[mechanism_id]
            - Updates _path_point_count[mechanism_id]
            - Updates QGraphicsPathItem visual

        Complexity: O(N) where N = number of points
        """
        trace_points = self._trace_points[mechanism_id]

        if len(trace_points) < 2:
            # Need at least 2 points to draw a path
            self._path_point_count[mechanism_id] = len(trace_points)
            return

        # Build path from all points
        path = QPainterPath()
        path.moveTo(trace_points[0])
        for point in trace_points[1:]:
            path.lineTo(point)

        # Update cached path and sync state
        self._trace_paths[mechanism_id] = path
        self._path_point_count[mechanism_id] = len(trace_points)

        # Update visual item
        item = self._trace_items.get(mechanism_id)
        if item:
            item.setPath(path)

    def _update_path_incremental(self, mechanism_id: str) -> None:
        """Incrementally update QPainterPath with new points only.

        Only appends new points since last update, avoiding O(N) rebuild.

        Args:
            mechanism_id: Unique identifier for mechanism.

        Side Effects:
            - Updates _trace_paths[mechanism_id]
            - Updates _path_point_count[mechanism_id]
            - Updates QGraphicsPathItem visual

        Complexity: O(K) where K = new points since last update (typically 1-2)
        """
        trace_points = self._trace_points[mechanism_id]
        current_count = len(trace_points)
        synced_count = self._path_point_count.get(mechanism_id, 0)

        if current_count < 2:
            # Need at least 2 points to draw a path
            self._path_point_count[mechanism_id] = current_count
            return

        # Get or create path
        path = self._trace_paths.get(mechanism_id)

        if path is None or synced_count == 0:
            # No existing path, do full rebuild
            self._rebuild_path_full(mechanism_id)
            return

        # Append only new points (incremental update)
        if current_count > synced_count:
            for i in range(synced_count, current_count):
                path.lineTo(trace_points[i])

            # Update sync state
            self._path_point_count[mechanism_id] = current_count

            # Update visual item
            item = self._trace_items.get(mechanism_id)
            if item:
                item.setPath(path)

    # Legacy method for backwards compatibility
    def _rebuild_path(self, mechanism_id: str) -> None:
        """Legacy method - delegates to incremental update.

        Kept for backwards compatibility with any external callers.
        """
        self._update_path_incremental(mechanism_id)
