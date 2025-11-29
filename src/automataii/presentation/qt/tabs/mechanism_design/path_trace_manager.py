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
        pen_color: Trace path color
        pen_width: Trace path width in pixels
        z_value: Z-level for trace items in scene
    """

    max_points: int = 500
    update_stride: int = 2
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

        logger.debug(f"PathTraceManager initialized with config: {self._config}")

    def init_trace(self, mechanism_id: str, scene: QGraphicsScene) -> None:
        """Initialize or reinitialize trace for a mechanism.

        Clears any existing trace and creates new visual item.

        Args:
            mechanism_id: Unique identifier for mechanism.
            scene: QGraphicsScene to add trace item to.

        Side Effects:
            - Removes old trace item from scene (if exists)
            - Creates new QGraphicsPathItem and adds to scene
            - Clears trace point buffer
        """
        # Remove old item from scene if exists
        if mechanism_id in self._trace_items:
            old_item = self._trace_items[mechanism_id]
            if old_item and old_item.scene() == scene:
                scene.removeItem(old_item)

        # Initialize data structures
        self._trace_points[mechanism_id] = []
        self._trace_paths[mechanism_id] = QPainterPath()

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

        # Append point to buffer
        self._trace_points[mechanism_id].append(position)

        # Enforce max points limit
        if len(self._trace_points[mechanism_id]) > self._config.max_points:
            self._trace_points[mechanism_id] = self._trace_points[mechanism_id][
                -self._config.max_points :
            ]
            logger.debug(
                f"Trimmed trace for {mechanism_id}: {len(self._trace_points[mechanism_id])} points"
            )

        # Stride gating: update visual only on stride boundaries OR for first 2 points
        points_count = len(self._trace_points[mechanism_id])
        should_update = (frame_tick % self._config.update_stride == 0) or (points_count <= 2)

        if should_update:
            self._rebuild_path(mechanism_id)

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

        # Update visual item to show empty path
        item = self._trace_items.get(mechanism_id)
        if item:
            item.setPath(empty_path)

        logger.debug(f"Cleared trace points only for mechanism {mechanism_id}")

    def _rebuild_path(self, mechanism_id: str) -> None:
        """Rebuild QPainterPath from point buffer.

        Args:
            mechanism_id: Unique identifier for mechanism.

        Side Effects:
            - Updates _trace_paths[mechanism_id]
            - Updates QGraphicsPathItem visual

        Complexity: O(N) where N = number of points
        """
        trace_points = self._trace_points[mechanism_id]

        if len(trace_points) < 2:
            # Need at least 2 points to draw a path
            return

        # Build path from points
        path = QPainterPath()
        path.moveTo(trace_points[0])
        for point in trace_points[1:]:
            path.lineTo(point)

        # Update cached path
        self._trace_paths[mechanism_id] = path

        # Update visual item
        item = self._trace_items.get(mechanism_id)
        if item:
            item.setPath(path)
