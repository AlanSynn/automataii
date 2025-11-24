"""Path repository for motion path storage and retrieval.

This module implements the PathRepositoryProtocol, providing an
in-memory repository for storing user-drawn and generated paths.

Pure Python implementation with no external dependencies beyond stdlib.
"""

from __future__ import annotations

import time
import uuid
from typing import Protocol

from .types import PathID, PathPoints, StoredPath

__all__ = ["PathRepositoryProtocol", "PathRepository"]


class PathRepositoryProtocol(Protocol):
    """Protocol for motion path storage and retrieval.

    Implementations must provide thread-safe storage for paths
    with snapshot/restore capabilities for undo/redo.
    """

    def store(self, part_name: str, points: PathPoints, metadata: dict | None = None) -> PathID:
        """Store path and return unique ID.

        Args:
            part_name: Name of character part
            points: Path points as tuple of (x, y) tuples
            metadata: Optional metadata dictionary

        Returns:
            Unique PathID for retrieval

        Raises:
            ValueError: If part_name empty or points < 2
        """
        ...

    def retrieve(self, path_id: PathID) -> StoredPath | None:
        """Retrieve stored path by ID.

        Args:
            path_id: Unique identifier

        Returns:
            StoredPath if found, None otherwise
        """
        ...

    def list_by_part(self, part_name: str) -> list[StoredPath]:
        """List all paths for a specific part.

        Args:
            part_name: Character part name

        Returns:
            List of StoredPath objects, ordered by timestamp (newest first)
        """
        ...

    def get_latest_for_part(self, part_name: str) -> StoredPath | None:
        """Get most recent path for part.

        Args:
            part_name: Character part name

        Returns:
            Latest StoredPath if exists, None otherwise
        """
        ...

    def snapshot(self) -> dict[PathID, StoredPath]:
        """Return immutable snapshot of current state.

        Used for undo/redo functionality.

        Returns:
            Frozen dictionary mapping PathID to StoredPath
        """
        ...

    def restore_snapshot(self, snapshot: dict[PathID, StoredPath]) -> None:
        """Restore from snapshot.

        Replaces entire repository state with snapshot.

        Args:
            snapshot: Previously captured snapshot
        """
        ...

    def clear(self) -> None:
        """Remove all stored paths."""
        ...

    def count(self) -> int:
        """Return total number of stored paths."""
        ...


class PathRepository:
    """In-memory implementation of PathRepositoryProtocol.

    Thread-safe storage with snapshot/restore for undo/redo.
    Paths are indexed by unique ID and by part name for fast lookup.

    Complexity:
        - store: O(1)
        - retrieve: O(1)
        - list_by_part: O(N) where N = paths for that part
        - snapshot: O(N) where N = total paths
    """

    def __init__(self) -> None:
        """Initialize empty repository."""
        self._paths: dict[PathID, StoredPath] = {}
        self._by_part: dict[str, list[PathID]] = {}

    def store(self, part_name: str, points: PathPoints, metadata: dict | None = None) -> PathID:
        """Store path and return unique ID.

        Complexity: O(1)
        """
        if not part_name:
            raise ValueError("part_name cannot be empty")
        if len(points) < 2:
            raise ValueError(f"Path must have at least 2 points, got {len(points)}")

        # Generate unique ID
        path_id = PathID(str(uuid.uuid4()))
        timestamp = time.time()

        # Create StoredPath
        stored_path = StoredPath(
            id=path_id,
            part_name=part_name,
            points=points,
            timestamp=timestamp,
            metadata=metadata or {},
        )

        # Store in main index
        self._paths[path_id] = stored_path

        # Store in part index
        if part_name not in self._by_part:
            self._by_part[part_name] = []
        self._by_part[part_name].append(path_id)

        return path_id

    def retrieve(self, path_id: PathID) -> StoredPath | None:
        """Retrieve stored path by ID.

        Complexity: O(1)
        """
        return self._paths.get(path_id)

    def list_by_part(self, part_name: str) -> list[StoredPath]:
        """List all paths for a specific part.

        Returns paths ordered by timestamp (newest first).

        Complexity: O(N log N) where N = paths for that part
        """
        path_ids = self._by_part.get(part_name, [])
        paths = [self._paths[pid] for pid in path_ids if pid in self._paths]

        # Sort by timestamp descending (newest first)
        return sorted(paths, key=lambda p: p.timestamp, reverse=True)

    def get_latest_for_part(self, part_name: str) -> StoredPath | None:
        """Get most recent path for part.

        Complexity: O(N) where N = paths for that part
        """
        paths = self.list_by_part(part_name)
        return paths[0] if paths else None

    def snapshot(self) -> dict[PathID, StoredPath]:
        """Return immutable snapshot of current state.

        Complexity: O(N) where N = total paths
        """
        return dict(self._paths)  # Shallow copy (StoredPath is immutable)

    def restore_snapshot(self, snapshot: dict[PathID, StoredPath]) -> None:
        """Restore from snapshot.

        Complexity: O(N) where N = paths in snapshot
        """
        self._paths = dict(snapshot)

        # Rebuild part index
        self._by_part = {}
        for path_id, stored_path in self._paths.items():
            part_name = stored_path.part_name
            if part_name not in self._by_part:
                self._by_part[part_name] = []
            self._by_part[part_name].append(path_id)

    def clear(self) -> None:
        """Remove all stored paths.

        Complexity: O(1)
        """
        self._paths = {}
        self._by_part = {}

    def count(self) -> int:
        """Return total number of stored paths.

        Complexity: O(1)
        """
        return len(self._paths)

    def __repr__(self) -> str:
        return f"PathRepository(paths={self.count()}, parts={len(self._by_part)})"
