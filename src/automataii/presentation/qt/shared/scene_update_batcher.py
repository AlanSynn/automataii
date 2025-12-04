"""
Scene update batching for Qt Graphics performance optimization.

This module provides a batching mechanism to coalesce multiple
scene.update() calls into a single update per frame, reducing
rendering overhead significantly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from weakref import WeakSet, ref

from PyQt6.QtCore import QObject, QTimer

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene


logger = logging.getLogger(__name__)


class SceneUpdateBatcher(QObject):
    """Batches multiple scene update requests into a single update per frame.

    When animations or complex operations trigger many scene.update() calls,
    this batcher coalesces them into a single update at the end of the
    current event loop iteration.

    Performance Impact:
        Without batching: 10+ scene.update() calls per frame = 10+ full redraws
        With batching: All requests coalesced = 1 full redraw per frame

    Usage:
        # Create batcher for a scene
        batcher = SceneUpdateBatcher(self.mechanism_scene)

        # Replace direct scene.update() calls with:
        batcher.request_update()

        # Or use as context manager for multiple operations:
        with batcher.batch_updates():
            self._update_joints()
            self._update_links()
            self._update_paths()
        # Single update happens here

    Thread Safety:
        This class is NOT thread-safe. All calls must be from the main Qt thread.
    """

    def __init__(self, scene: QGraphicsScene, parent: QObject | None = None):
        """Initialize the batcher.

        Args:
            scene: The QGraphicsScene to manage updates for
            parent: Optional QObject parent for lifecycle management
        """
        super().__init__(parent)
        self._scene_ref = ref(scene)
        self._update_pending = False
        self._update_count = 0  # Diagnostic counter
        self._batched_count = 0  # Count of batched requests

    @property
    def scene(self) -> QGraphicsScene | None:
        """Get the managed scene, or None if it was garbage collected."""
        return self._scene_ref()

    def request_update(self) -> None:
        """Request a scene update.

        Multiple calls within the same event loop iteration are coalesced
        into a single scene.update() call.
        """
        if self._update_pending:
            self._batched_count += 1
            return

        scene = self.scene
        if scene is None:
            logger.debug("SceneUpdateBatcher: Scene was garbage collected")
            return

        self._update_pending = True
        # Schedule update for next event loop iteration
        QTimer.singleShot(0, self._do_update)

    def _do_update(self) -> None:
        """Execute the batched scene update."""
        self._update_pending = False
        self._update_count += 1

        scene = self.scene
        if scene is None:
            return

        try:
            scene.update()
        except RuntimeError:
            # Scene may have been deleted
            logger.debug("SceneUpdateBatcher: Scene deleted during update")

    def force_update(self) -> None:
        """Force an immediate scene update, bypassing batching.

        Use sparingly - only when an immediate visual update is required.
        """
        self._update_pending = False

        scene = self.scene
        if scene is not None:
            try:
                scene.update()
                self._update_count += 1
            except RuntimeError:
                pass

    def batch_updates(self) -> BatchContext:
        """Context manager for batching multiple operations.

        Returns:
            A context manager that will trigger one update when exited.

        Example:
            with batcher.batch_updates():
                # Multiple operations that would normally call scene.update()
                self._update_joints()
                self._update_links()
            # Single update happens here
        """
        return BatchContext(self)

    def get_stats(self) -> dict[str, int]:
        """Get diagnostic statistics.

        Returns:
            Dict with 'total_updates' and 'batched_requests' counts
        """
        return {
            "total_updates": self._update_count,
            "batched_requests": self._batched_count,
        }

    def reset_stats(self) -> None:
        """Reset diagnostic counters."""
        self._update_count = 0
        self._batched_count = 0


class BatchContext:
    """Context manager for batched scene updates."""

    def __init__(self, batcher: SceneUpdateBatcher):
        self._batcher = batcher
        self._original_pending = False

    def __enter__(self) -> BatchContext:
        self._original_pending = self._batcher._update_pending
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Request update only if we weren't already pending
        if not self._original_pending:
            self._batcher.request_update()
        return None


class GlobalSceneBatcher:
    """Global manager for scene update batchers.

    Maintains weak references to batchers for multiple scenes,
    providing a centralized way to manage scene updates across
    the application.

    Usage:
        # Get or create batcher for a scene
        batcher = GlobalSceneBatcher.get_batcher(my_scene)
        batcher.request_update()

        # Or use the convenience method
        GlobalSceneBatcher.request_update(my_scene)
    """

    _batchers: WeakSet[SceneUpdateBatcher] = WeakSet()
    _scene_map: dict[int, ref[SceneUpdateBatcher]] = {}

    @classmethod
    def get_batcher(cls, scene: QGraphicsScene) -> SceneUpdateBatcher:
        """Get or create a batcher for the given scene.

        Args:
            scene: The QGraphicsScene to manage

        Returns:
            SceneUpdateBatcher instance for this scene
        """
        scene_id = id(scene)

        # Check if we have an existing batcher
        if scene_id in cls._scene_map:
            batcher_ref = cls._scene_map[scene_id]
            batcher = batcher_ref()
            if batcher is not None and batcher.scene is not None:
                return batcher
            # Clean up dead reference
            del cls._scene_map[scene_id]

        # Create new batcher
        batcher = SceneUpdateBatcher(scene)
        cls._batchers.add(batcher)
        cls._scene_map[scene_id] = ref(batcher)
        return batcher

    @classmethod
    def request_update(cls, scene: QGraphicsScene) -> None:
        """Convenience method to request an update for a scene.

        Args:
            scene: The scene to update
        """
        batcher = cls.get_batcher(scene)
        batcher.request_update()

    @classmethod
    def cleanup(cls) -> None:
        """Clean up dead references."""
        dead_ids = [
            scene_id
            for scene_id, batcher_ref in cls._scene_map.items()
            if batcher_ref() is None
        ]
        for scene_id in dead_ids:
            del cls._scene_map[scene_id]
