"""
Project Serializer.

Handles save/load of project state to/from JSON files.

Architecture: Application Layer (Hexagonal)
Pattern: Repository + Strategy (for format versioning)
"""
from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .models import ProjectState

logger = logging.getLogger(__name__)


# =============================================================================
# RESULT TYPES (Railway-Oriented)
# =============================================================================

@dataclass(frozen=True)
class SaveResult:
    """Result of save operation."""
    success: bool
    path: Path | None = None
    error: str | None = None

    @classmethod
    def ok(cls, path: Path) -> SaveResult:
        return cls(success=True, path=path)

    @classmethod
    def fail(cls, error: str) -> SaveResult:
        return cls(success=False, error=error)


@dataclass(frozen=True)
class LoadResult:
    """Result of load operation."""
    success: bool
    state: ProjectState | None = None
    error: str | None = None

    @classmethod
    def ok(cls, state: ProjectState) -> LoadResult:
        return cls(success=True, state=state)

    @classmethod
    def fail(cls, error: str) -> LoadResult:
        return cls(success=False, error=error)


# =============================================================================
# VERSION MIGRATION PROTOCOL
# =============================================================================

@runtime_checkable
class VersionMigrator(Protocol):
    """Protocol for version migration strategies."""

    def can_migrate(self, from_version: str, to_version: str) -> bool:
        """Check if this migrator can handle the version upgrade."""
        ...

    def migrate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Migrate data to newer version."""
        ...


class V1ToV2Migrator:
    """Migrates version 1.x projects to 2.0 format."""

    def can_migrate(self, from_version: str, to_version: str) -> bool:
        return from_version.startswith("1.") and to_version.startswith("2.")

    def migrate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Migration from v1 to v2:
        - Add metadata section
        - Rename 'layers' to 'parts' if present
        - Add paths section if missing
        """
        migrated = dict(data)

        # Add metadata if missing
        if "metadata" not in migrated:
            migrated["metadata"] = {
                "version": "2.0",
                "name": data.get("project_name", "Migrated Project"),
                "created_at": datetime.now().isoformat(),
                "modified_at": datetime.now().isoformat(),
            }

        # Rename layers to parts if needed
        if "layers" in migrated and "parts" not in migrated:
            migrated["parts"] = migrated.pop("layers")

        # Ensure paths section exists
        if "paths" not in migrated:
            migrated["paths"] = {}

        # Ensure mechanisms section exists
        if "mechanisms" not in migrated:
            migrated["mechanisms"] = {}

        logger.info("Migrated project from v1 to v2")
        return migrated


# =============================================================================
# PROJECT SERIALIZER
# =============================================================================

class ProjectSerializer:
    """
    Serializes and deserializes project state.

    Features:
    - JSON format with pretty printing
    - Version migration support
    - Backup before overwrite
    - Atomic writes (write to temp, then rename)

    Usage:
        serializer = ProjectSerializer()
        result = serializer.save(state, Path("project.automataii"))
        if not result.success:
            print(f"Save failed: {result.error}")
    """

    CURRENT_VERSION = "2.0"
    FILE_EXTENSION = ".automataii"

    def __init__(self) -> None:
        self._migrators: list[VersionMigrator] = [
            V1ToV2Migrator(),
        ]

    # =========================================================================
    # SAVE OPERATIONS
    # =========================================================================

    def save(self, state: ProjectState, path: Path) -> SaveResult:
        """
        Save project state to file.

        Args:
            state: Project state to save
            path: Target file path

        Returns:
            SaveResult with success/failure info
        """
        try:
            # Ensure correct extension
            if path.suffix != self.FILE_EXTENSION:
                path = path.with_suffix(self.FILE_EXTENSION)

            # Backup existing file
            if path.exists():
                self._create_backup(path)

            # Serialize state
            data = state.to_dict()

            # Ensure version is current
            if "metadata" in data:
                data["metadata"]["version"] = self.CURRENT_VERSION

            # Atomic write: write to temp file, then rename
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Rename to final path (atomic on most filesystems)
            temp_path.replace(path)

            logger.info(f"Project saved to {path}")
            return SaveResult.ok(path)

        except PermissionError:
            error = f"Permission denied: {path}"
            logger.error(error)
            return SaveResult.fail(error)
        except OSError as e:
            error = f"IO error saving project: {e}"
            logger.error(error)
            return SaveResult.fail(error)
        except Exception as e:
            error = f"Unexpected error saving project: {e}"
            logger.exception(error)
            return SaveResult.fail(error)

    def _create_backup(self, path: Path) -> None:
        """Create backup of existing file."""
        backup_path = path.with_suffix(f".backup{path.suffix}")
        try:
            shutil.copy2(path, backup_path)
            logger.debug(f"Backup created: {backup_path}")
        except OSError as e:
            logger.warning(f"Could not create backup: {e}")

    # =========================================================================
    # LOAD OPERATIONS
    # =========================================================================

    def load(self, path: Path) -> LoadResult:
        """
        Load project state from file.

        Args:
            path: Project file path

        Returns:
            LoadResult with state or error
        """
        try:
            if not path.exists():
                return LoadResult.fail(f"File not found: {path}")

            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            # Check version and migrate if needed
            data = self._migrate_if_needed(data)

            # Deserialize to state
            project_dir = path.parent
            state = ProjectState.from_dict(data, project_dir)

            logger.info(f"Project loaded from {path}")
            return LoadResult.ok(state)

        except json.JSONDecodeError as e:
            error = f"Invalid JSON in project file: {e}"
            logger.error(error)
            return LoadResult.fail(error)
        except KeyError as e:
            error = f"Missing required field in project file: {e}"
            logger.error(error)
            return LoadResult.fail(error)
        except Exception as e:
            error = f"Error loading project: {e}"
            logger.exception(error)
            return LoadResult.fail(error)

    def _migrate_if_needed(self, data: dict[str, Any]) -> dict[str, Any]:
        """Apply version migrations if needed."""
        version = data.get("metadata", {}).get("version", "1.0")

        if version == self.CURRENT_VERSION:
            return data

        # Find and apply migrators
        for migrator in self._migrators:
            if migrator.can_migrate(version, self.CURRENT_VERSION):
                data = migrator.migrate(data)
                version = data.get("metadata", {}).get("version", version)

        return data

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def validate_file(self, path: Path) -> tuple[bool, str | None]:
        """
        Validate project file without loading.

        Returns:
            (is_valid, error_message)
        """
        try:
            if not path.exists():
                return False, "File does not exist"

            if path.suffix != self.FILE_EXTENSION:
                return False, f"Invalid file extension (expected {self.FILE_EXTENSION})"

            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            # Check required fields
            if "metadata" not in data and "parts" not in data:
                return False, "Missing required sections"

            return True, None

        except json.JSONDecodeError:
            return False, "Invalid JSON format"
        except Exception as e:
            return False, str(e)

    def get_project_info(self, path: Path) -> dict[str, Any] | None:
        """
        Get basic project info without full load.

        Returns metadata dict or None if invalid.
        """
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            metadata = data.get("metadata", {})
            return {
                "name": metadata.get("name", path.stem),
                "version": metadata.get("version", "unknown"),
                "created_at": metadata.get("created_at"),
                "modified_at": metadata.get("modified_at"),
                "parts_count": len(data.get("parts", {})),
                "mechanisms_count": len(data.get("mechanisms", {})),
            }
        except Exception:
            return None


# =============================================================================
# AUTO-SAVE MANAGER
# =============================================================================

class AutoSaveManager:
    """
    Manages automatic project saves.

    Features:
    - Periodic auto-save to temp location
    - Crash recovery
    - Configurable interval
    """

    DEFAULT_INTERVAL_SECONDS = 60
    AUTOSAVE_DIR_NAME = ".autosave"

    def __init__(
        self,
        serializer: ProjectSerializer,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self._serializer = serializer
        self._interval = interval_seconds
        self._last_save: datetime | None = None
        self._autosave_dir: Path | None = None

    def setup(self, project_dir: Path) -> None:
        """Setup autosave directory."""
        self._autosave_dir = project_dir / self.AUTOSAVE_DIR_NAME
        self._autosave_dir.mkdir(exist_ok=True)

    def should_save(self) -> bool:
        """Check if enough time has passed for autosave."""
        if self._last_save is None:
            return True
        elapsed = (datetime.now() - self._last_save).total_seconds()
        return elapsed >= self._interval

    def autosave(self, state: ProjectState) -> SaveResult:
        """Perform autosave."""
        if not self._autosave_dir:
            return SaveResult.fail("Autosave not configured")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self._autosave_dir / f"autosave_{timestamp}.automataii"

        result = self._serializer.save(state, path)
        if result.success:
            self._last_save = datetime.now()
            self._cleanup_old_autosaves()

        return result

    def _cleanup_old_autosaves(self, keep_count: int = 5) -> None:
        """Remove old autosave files, keeping only recent ones."""
        if not self._autosave_dir:
            return

        autosaves = sorted(
            self._autosave_dir.glob("autosave_*.automataii"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for old_save in autosaves[keep_count:]:
            try:
                old_save.unlink()
                logger.debug(f"Removed old autosave: {old_save}")
            except OSError:
                pass

    def get_recovery_files(self, project_dir: Path) -> list[Path]:
        """Get list of autosave files for recovery."""
        autosave_dir = project_dir / self.AUTOSAVE_DIR_NAME
        if not autosave_dir.exists():
            return []

        return sorted(
            autosave_dir.glob("autosave_*.automataii"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
