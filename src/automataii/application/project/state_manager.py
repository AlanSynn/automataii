"""
Project State Manager.

Central state store implementing Single Source of Truth pattern.
All tabs subscribe to state changes rather than holding copies.

Architecture: Application Layer (Hexagonal)
Pattern: Observer + Command (for undo/redo)

Technical Debt Note:
- This file uses PyQt6 signals for the Observer pattern
- Ideally, application layer should use pure Python event bus
- Qt dependency is acceptable here as "infrastructure" for reactivity
- Future refactor: Create EventBus in infrastructure/ and adapt with Qt signals
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from .models import (
    JointData,
    MechanismData,
    PartData,
    PathData,
    Point,
    ProjectMetadata,
    ProjectState,
    SkeletonData,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MUTATION LOG ENTRY
# =============================================================================


@dataclass
class MutationEntry:
    """Record of a state mutation for debugging/undo."""

    operation: str
    timestamp: datetime
    details: dict[str, Any]
    previous_state: ProjectState | None = None


# =============================================================================
# PROJECT STATE MANAGER
# =============================================================================


class ProjectStateManager(QObject):
    """
    Central state manager with reactive updates.

    Single Source of Truth for all cross-tab data.
    All mutations go through this class, enabling:
    - Atomic state updates
    - Undo/redo support
    - Mutation logging
    - Reactive UI updates via signals

    Usage:
        state_manager = ProjectStateManager()
        state_manager.parts_changed.connect(my_tab.on_parts_changed)
        state_manager.load_parts({"head": PartData(...)})
    """

    # =========================================================================
    # SIGNALS
    # =========================================================================

    # Full state change (use sparingly - prefer granular signals)
    state_changed = pyqtSignal(object)  # ProjectState

    # Granular signals for performance
    parts_changed = pyqtSignal(dict)  # dict[str, PartData]
    skeleton_changed = pyqtSignal(object)  # SkeletonData | None
    paths_changed = pyqtSignal(dict)  # dict[str, PathData]
    mechanisms_changed = pyqtSignal(dict)  # dict[str, MechanismData]

    # Individual item signals
    part_updated = pyqtSignal(str, object)  # (part_name, PartData)
    path_updated = pyqtSignal(str, object)  # (part_name, PathData)
    mechanism_updated = pyqtSignal(str, object)  # (mechanism_id, MechanismData)
    joint_updated = pyqtSignal(str, object)  # (joint_id, JointData)

    # Project lifecycle
    project_loaded = pyqtSignal(str)  # project_path
    project_saved = pyqtSignal(str)  # project_path
    project_cleared = pyqtSignal()
    project_modified = pyqtSignal()  # Any change (for dirty state tracking)

    # Undo/redo
    undo_available = pyqtSignal(bool)
    redo_available = pyqtSignal(bool)

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        self._state = ProjectState.empty()
        self._is_dirty = False

        # Undo/redo stacks
        self._undo_stack: deque[ProjectState] = deque(maxlen=50)
        self._redo_stack: deque[ProjectState] = deque(maxlen=50)

        # Mutation log for debugging
        self._mutation_log: list[MutationEntry] = []
        self._max_log_entries = 100

        # Batch update flag (suppress signals during batch)
        self._batch_mode = False
        self._batch_changes: set[str] = set()

        logger.info("ProjectStateManager initialized")

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def state(self) -> ProjectState:
        """Read-only access to current state."""
        return self._state

    @property
    def is_dirty(self) -> bool:
        """Check if there are unsaved changes."""
        return self._is_dirty

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    # =========================================================================
    # BATCH UPDATES
    # =========================================================================

    def begin_batch(self) -> None:
        """Begin batch update (suppresses individual signals)."""
        self._batch_mode = True
        self._batch_changes.clear()

    def end_batch(self) -> None:
        """End batch update and emit accumulated signals."""
        self._batch_mode = False
        changes = self._batch_changes.copy()
        self._batch_changes.clear()

        # Emit signals for changed categories
        if "parts" in changes:
            self.parts_changed.emit(dict(self._state.parts))
        if "skeleton" in changes:
            self.skeleton_changed.emit(self._state.skeleton)
        if "paths" in changes:
            self.paths_changed.emit(dict(self._state.paths))
        if "mechanisms" in changes:
            self.mechanisms_changed.emit(dict(self._state.mechanisms))

        if changes:
            self.state_changed.emit(self._state)

    # =========================================================================
    # STATE MUTATIONS
    # =========================================================================

    def _apply_state(
        self,
        new_state: ProjectState,
        operation: str,
        details: dict[str, Any],
        *,
        emit_signals: bool = True,
        categories: set[str] | None = None,
    ) -> None:
        """Apply new state and emit signals."""
        # Save for undo (only if not in undo/redo operation)
        if operation not in ("undo", "redo"):
            self._undo_stack.append(self._state)
            self._redo_stack.clear()
            self.undo_available.emit(True)
            self.redo_available.emit(False)

        # Update state
        old_state = self._state
        self._state = new_state
        self._is_dirty = True

        # Log mutation
        self._log_mutation(operation, details, old_state)

        # Emit signals
        if emit_signals and not self._batch_mode:
            self._emit_change_signals(old_state, new_state, categories)
            self.project_modified.emit()
        elif self._batch_mode and categories:
            self._batch_changes.update(categories)

    def replace_project_state(
        self,
        new_state: ProjectState,
        *,
        operation: str = "replace_project_state",
        clear_history: bool = True,
        mark_saved: bool = False,
        emit_signals: bool = True,
        categories: set[str] | None = None,
    ) -> None:
        """Replace state for internal load/save snapshots without undo pollution."""
        old_state = self._state
        self._state = new_state
        self._is_dirty = not mark_saved
        if clear_history:
            self._undo_stack.clear()
            self._redo_stack.clear()
            self.undo_available.emit(False)
            self.redo_available.emit(False)
        self._log_mutation(operation, {"clear_history": clear_history}, old_state)
        if emit_signals and not self._batch_mode:
            self._emit_change_signals(old_state, new_state, categories)
            if not mark_saved:
                self.project_modified.emit()
        elif self._batch_mode and categories:
            self._batch_changes.update(categories)

    def _emit_change_signals(
        self,
        old: ProjectState,
        new: ProjectState,
        categories: set[str] | None = None,
    ) -> None:
        """Emit appropriate signals based on what changed."""
        if categories is None:
            categories = {"parts", "skeleton", "paths", "mechanisms"}

        if "parts" in categories and old.parts != new.parts:
            self.parts_changed.emit(dict(new.parts))
        if "skeleton" in categories and old.skeleton != new.skeleton:
            self.skeleton_changed.emit(new.skeleton)
        if "paths" in categories and old.paths != new.paths:
            self.paths_changed.emit(dict(new.paths))
        if "mechanisms" in categories and old.mechanisms != new.mechanisms:
            self.mechanisms_changed.emit(dict(new.mechanisms))

        self.state_changed.emit(new)

    def _log_mutation(self, operation: str, details: dict, prev_state: ProjectState | None) -> None:
        """Log mutation for debugging."""
        entry = MutationEntry(
            operation=operation,
            timestamp=datetime.now(),
            details=details,
            previous_state=prev_state,
        )
        self._mutation_log.append(entry)
        if len(self._mutation_log) > self._max_log_entries:
            self._mutation_log.pop(0)
        logger.debug(f"Mutation: {operation} - {details}")

    def _preserve_runtime_project_location(self, target_state: ProjectState) -> ProjectState:
        """
        Keep project file location stable across content undo/redo.

        `project_dir` and `project_file_path` describe where the currently open
        document lives; they are runtime context, not editable project content.
        Save/Save As updates that context without clearing undo history, so
        restoring an older content snapshot must not make the app forget the
        remembered `.automataii` path.
        """
        current_state = self._state
        if current_state.project_dir is not None:
            target_state = target_state.with_project_dir(current_state.project_dir)
        if current_state.project_file_path is not None:
            target_state = target_state.with_project_file_path(current_state.project_file_path)
        return target_state

    # =========================================================================
    # PARTS MUTATIONS
    # =========================================================================

    def load_parts(self, parts: dict[str, PartData]) -> None:
        """Load all parts (typically from ImageProcessingTab)."""
        new_state = self._state.with_parts(parts)
        self._apply_state(new_state, "load_parts", {"count": len(parts)}, categories={"parts"})
        logger.info(f"Loaded {len(parts)} parts")

    def update_part(self, part: PartData) -> None:
        """Update a single part."""
        new_state = self._state.with_part(part)
        self._apply_state(new_state, "update_part", {"name": part.name}, categories={"parts"})
        self.part_updated.emit(part.name, part)

    def remove_part(self, part_name: str) -> None:
        """Remove a part."""
        new_state = self._state.without_part(part_name)
        # Also remove associated path and mechanisms
        new_state = new_state.without_path(part_name)
        mechanisms_to_remove = [
            m.id for m in self._state.mechanisms.values() if m.part_name == part_name
        ]
        for mid in mechanisms_to_remove:
            new_state = new_state.without_mechanism(mid)
        self._apply_state(
            new_state,
            "remove_part",
            {"name": part_name},
            categories={"parts", "paths", "mechanisms"},
        )

    # =========================================================================
    # SKELETON MUTATIONS
    # =========================================================================

    def load_skeleton(self, skeleton: SkeletonData) -> None:
        """Load skeleton data."""
        new_state = self._state.with_skeleton(skeleton)
        self._apply_state(
            new_state, "load_skeleton", {"joints": len(skeleton.joints)}, categories={"skeleton"}
        )
        logger.info(f"Loaded skeleton with {len(skeleton.joints)} joints")

    def clear_skeleton(self) -> None:
        """Clear skeleton data."""
        new_state = self._state.with_skeleton(None)
        self._apply_state(new_state, "clear_skeleton", {}, categories={"skeleton"})

    def update_joint(self, joint: JointData) -> None:
        """Update a single joint."""
        if not self._state.skeleton:
            logger.warning("Cannot update joint: no skeleton loaded")
            return
        new_skeleton = self._state.skeleton.with_joint(joint)
        new_state = self._state.with_skeleton(new_skeleton)
        self._apply_state(new_state, "update_joint", {"id": joint.id}, categories={"skeleton"})
        self.joint_updated.emit(joint.id, joint)

    def lock_joint(self, joint_id: str, locked: bool) -> None:
        """Lock or unlock a joint."""
        if not self._state.skeleton:
            return
        joint = self._state.skeleton.get_joint(joint_id)
        if joint:
            self.update_joint(joint.with_locked(locked))

    def update_joint_position(self, joint_id: str, position: Point) -> None:
        """Update joint position (from IK or manual edit)."""
        if not self._state.skeleton:
            return
        joint = self._state.skeleton.get_joint(joint_id)
        if joint:
            self.update_joint(joint.with_position(position))

    # =========================================================================
    # PATH MUTATIONS
    # =========================================================================

    def set_path(self, path: PathData) -> None:
        """Set motion path for a part."""
        new_state = self._state.with_path(path)
        self._apply_state(
            new_state,
            "set_path",
            {"part": path.part_name, "points": len(path.points)},
            categories={"paths"},
        )
        self.path_updated.emit(path.part_name, path)
        logger.info(f"Set path for '{path.part_name}' with {len(path.points)} points")

    def remove_path(self, part_name: str) -> None:
        """Remove motion path for a part."""
        new_state = self._state.without_path(part_name)
        self._apply_state(new_state, "remove_path", {"part": part_name}, categories={"paths"})

    def enable_path(self, part_name: str, enabled: bool) -> None:
        """Enable or disable a path."""
        path = self._state.get_path(part_name)
        if path:
            self.set_path(path.with_enabled(enabled))

    def load_paths(self, paths: dict[str, PathData]) -> None:
        """Load all paths (typically from project file)."""
        new_state = self._state.with_paths(paths)
        self._apply_state(new_state, "load_paths", {"count": len(paths)}, categories={"paths"})

    # =========================================================================
    # MECHANISM MUTATIONS
    # =========================================================================

    def add_mechanism(self, mechanism: MechanismData) -> None:
        """Add a new mechanism."""
        new_state = self._state.with_mechanism(mechanism)
        self._apply_state(
            new_state,
            "add_mechanism",
            {"id": mechanism.id, "type": mechanism.type},
            categories={"mechanisms"},
        )
        self.mechanism_updated.emit(mechanism.id, mechanism)
        logger.info(f"Added mechanism '{mechanism.id}' of type '{mechanism.type}'")

    def update_mechanism(self, mechanism: MechanismData) -> None:
        """Update an existing mechanism."""
        new_state = self._state.with_mechanism(mechanism)
        self._apply_state(
            new_state, "update_mechanism", {"id": mechanism.id}, categories={"mechanisms"}
        )
        self.mechanism_updated.emit(mechanism.id, mechanism)

    def remove_mechanism(self, mechanism_id: str) -> None:
        """Remove a mechanism."""
        new_state = self._state.without_mechanism(mechanism_id)
        self._apply_state(
            new_state, "remove_mechanism", {"id": mechanism_id}, categories={"mechanisms"}
        )

    def enable_mechanism(self, mechanism_id: str, enabled: bool) -> None:
        """Enable or disable a mechanism."""
        mechanism = self._state.get_mechanism(mechanism_id)
        if mechanism:
            self.update_mechanism(mechanism.with_enabled(enabled))

    def load_mechanisms(self, mechanisms: dict[str, MechanismData]) -> None:
        """Load all mechanisms (typically from project file)."""
        new_state = self._state.with_mechanisms(mechanisms)
        self._apply_state(
            new_state, "load_mechanisms", {"count": len(mechanisms)}, categories={"mechanisms"}
        )

    # =========================================================================
    # PROJECT CONTEXT MUTATIONS
    # =========================================================================

    def set_project_dir(self, project_dir: Path | None) -> None:
        """Set active project directory."""
        new_state = self._state.with_project_dir(project_dir)
        self._apply_state(
            new_state,
            "set_project_dir",
            {"project_dir": str(project_dir) if project_dir else None},
            categories=set(),
        )

    def set_image_path(self, image_path: Path | None) -> None:
        """Set active source image path."""
        new_state = self._state.with_image_path(image_path)
        self._apply_state(
            new_state,
            "set_image_path",
            {"image_path": str(image_path) if image_path else None},
            categories=set(),
        )

    # =========================================================================
    # PROJECT LIFECYCLE
    # =========================================================================

    def new_project(self, name: str = "Untitled") -> None:
        """Create a new empty project."""
        metadata = ProjectMetadata(name=name)
        new_state = ProjectState.empty().with_metadata(metadata)
        self._state = new_state
        self._is_dirty = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.undo_available.emit(False)
        self.redo_available.emit(False)
        self.project_cleared.emit()
        self.state_changed.emit(new_state)
        logger.info(f"New project created: {name}")

    def clear_project(self) -> None:
        """Clear current project."""
        self.new_project()

    def mark_saved(self) -> None:
        """Mark current state as saved (clears dirty flag)."""
        self._is_dirty = False

    # =========================================================================
    # UNDO/REDO
    # =========================================================================

    def undo(self) -> None:
        """Undo last mutation."""
        if not self._undo_stack:
            return
        self._redo_stack.append(self._state)
        prev_state = self._preserve_runtime_project_location(self._undo_stack.pop())
        self._apply_state(
            prev_state,
            "undo",
            {},
            emit_signals=True,
            categories={"parts", "skeleton", "paths", "mechanisms"},
        )
        self.undo_available.emit(len(self._undo_stack) > 0)
        self.redo_available.emit(True)
        logger.debug("Undo performed")

    def redo(self) -> None:
        """Redo last undone mutation."""
        if not self._redo_stack:
            return
        self._undo_stack.append(self._state)
        next_state = self._preserve_runtime_project_location(self._redo_stack.pop())
        self._apply_state(
            next_state,
            "redo",
            {},
            emit_signals=True,
            categories={"parts", "skeleton", "paths", "mechanisms"},
        )
        self.undo_available.emit(True)
        self.redo_available.emit(len(self._redo_stack) > 0)
        logger.debug("Redo performed")

    # =========================================================================
    # DEBUGGING
    # =========================================================================

    def get_mutation_log(self) -> list[MutationEntry]:
        """Get mutation log for debugging."""
        return list(self._mutation_log)

    def dump_state(self) -> dict[str, Any]:
        """Dump current state for debugging."""
        return {
            "parts_count": len(self._state.parts),
            "has_skeleton": self._state.has_skeleton(),
            "paths_count": len(self._state.paths),
            "mechanisms_count": len(self._state.mechanisms),
            "is_dirty": self._is_dirty,
            "undo_depth": len(self._undo_stack),
            "redo_depth": len(self._redo_stack),
        }
