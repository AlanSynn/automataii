"""
Project Serializer.

Handles save/load of project state to/from JSON files.

Architecture: Application Layer (Hexagonal)
Pattern: Repository + Strategy (for format versioning)
"""

from __future__ import annotations

import json
import logging
import math
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from filecmp import cmp
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
        else:
            metadata = dict(migrated["metadata"])
            metadata["version"] = "2.0"
            migrated["metadata"] = metadata

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

    def save(
        self,
        state: ProjectState,
        path: Path,
        *,
        portable_assets: bool = True,
    ) -> SaveResult:
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

            self._validate_ms4n_layer_data(state)

            # Backup existing file
            if path.exists():
                self._create_backup(path)

            # Full saves bundle assets; autosaves keep the current paths to avoid
            # duplicating large image folders every interval.
            prepared_state = (
                self._prepare_state_for_save(state, path)
                if portable_assets
                else state.with_project_dir(path.parent)
            )
            data = prepared_state.to_dict()

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

    def _validate_ms4n_layer_data(self, state: ProjectState) -> None:
        """Reject invalid MS4N payloads before permissive layer serialization."""
        from automataii.application.ms4n.layer_data_bridge import (
            MS4N_LAYER_KEY,
            validate_ms4n_payload,
        )

        for mechanism_id, mechanism in state.mechanisms.items():
            ms4n_payload = mechanism.layer_data.get(MS4N_LAYER_KEY)
            if ms4n_payload is None:
                continue
            if not isinstance(ms4n_payload, Mapping):
                raise ValueError(
                    f"MS4N layer data for mechanism {mechanism_id!r} must be an object"
                )
            try:
                validate_ms4n_payload(ms4n_payload)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid MS4N layer data for mechanism {mechanism_id!r}: {exc}"
                ) from exc

    def _prepare_state_for_save(self, state: ProjectState, path: Path) -> ProjectState:
        """
        Create a portable project snapshot by bundling referenced assets.

        Asset files are copied into '<project_stem>_assets/' next to the project file,
        and stored paths are rewritten to project-relative paths.
        """
        save_root = path.parent
        prepared_state = state.with_project_dir(save_root)
        bundle_root = save_root / f"{path.stem}_assets"
        copied_sources: dict[Path, str] = {}

        def _safe_stem_hint(stem_hint: str) -> str:
            safe = "".join(
                char if char.isalnum() or char in {"_", "-"} else "_" for char in stem_hint
            ).strip("._-")
            return safe or "asset"

        def _resolve_source_path(raw_path: str | None) -> Path | None:
            if not raw_path:
                return None
            raw = Path(raw_path)
            if raw.is_absolute():
                return raw

            if state.project_dir is not None:
                candidate = state.project_dir / raw
                if candidate.exists():
                    return candidate

            candidate = save_root / raw
            if candidate.exists():
                return candidate

            return None

        def _copy_asset(raw_path: str | None, category: str, stem_hint: str) -> str | None:
            source_path = _resolve_source_path(raw_path)
            if source_path is None or not source_path.exists():
                return raw_path if raw_path else None

            source_path = source_path.resolve()
            cached_rel = copied_sources.get(source_path)
            if cached_rel is not None:
                return cached_rel

            dest_dir = bundle_root / category
            dest_dir.mkdir(parents=True, exist_ok=True)

            source_suffix = source_path.suffix
            if not source_suffix:
                source_suffix = ".bin"
            safe_stem = _safe_stem_hint(stem_hint)
            base_name = f"{safe_stem}{source_suffix}"
            dest_path = dest_dir / base_name

            def _same_file_content(lhs: Path, rhs: Path) -> bool:
                try:
                    lhs_stat = lhs.stat()
                    rhs_stat = rhs.stat()
                except OSError:
                    return False

                # Fast reject before full byte comparison.
                if lhs_stat.st_size != rhs_stat.st_size:
                    return False

                try:
                    return cmp(lhs, rhs, shallow=False)
                except OSError:
                    return False

            if dest_path.exists() and _same_file_content(source_path, dest_path):
                relative = str(dest_path.relative_to(save_root))
                copied_sources[source_path] = relative
                return relative

            counter = 1
            while dest_path.exists() and dest_path.resolve() != source_path.resolve():
                candidate = dest_dir / f"{safe_stem}_{counter}{source_suffix}"
                if candidate.exists() and _same_file_content(source_path, candidate):
                    relative = str(candidate.relative_to(save_root))
                    copied_sources[source_path] = relative
                    return relative
                dest_path = candidate
                counter += 1

            if dest_path.resolve() != source_path.resolve():
                shutil.copy2(source_path, dest_path)
            relative = str(dest_path.relative_to(save_root))
            copied_sources[source_path] = relative
            return relative

        updated_parts = {}
        for part_name, part in prepared_state.parts.items():
            texture_rel = _copy_asset(part.texture_path, "parts", f"{part_name}_texture")
            mask_rel = _copy_asset(part.mask_path, "parts", f"{part_name}_mask")
            original_svg_rel = _copy_asset(
                part.original_svg_path, "vectors", f"{part_name}_original"
            )
            enhanced_svg_rel = _copy_asset(
                part.enhanced_svg_path, "vectors", f"{part_name}_enhanced"
            )

            updated_parts[part_name] = replace(
                part,
                texture_path=texture_rel or part.texture_path,
                mask_path=mask_rel or part.mask_path,
                original_svg_path=original_svg_rel
                if original_svg_rel is not None
                else part.original_svg_path,
                enhanced_svg_path=enhanced_svg_rel
                if enhanced_svg_rel is not None
                else part.enhanced_svg_path,
            )

        if updated_parts:
            prepared_state = prepared_state.with_parts(updated_parts)

        image_rel = _copy_asset(
            str(prepared_state.image_path) if prepared_state.image_path else None,
            "source",
            "input_image",
        )
        if image_rel:
            prepared_state = prepared_state.with_image_path(Path(image_rel))

        return prepared_state

    def _create_backup(self, path: Path) -> None:
        """Create backup of existing file."""
        backup_path = path.with_suffix(f".backup{path.suffix}")
        if backup_path.exists():
            counter = 1
            while True:
                candidate = path.with_suffix(f".backup{counter}{path.suffix}")
                if not candidate.exists():
                    backup_path = candidate
                    break
                counter += 1
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
            state = ProjectState.from_dict(data, project_dir, project_file_path=path)

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

            if not isinstance(data, dict):
                return False, "Project root must be a JSON object"

            metadata = data.get("metadata")
            if metadata is not None and not isinstance(metadata, dict):
                return False, "metadata section must be an object"

            # Check required fields
            if "metadata" not in data and "parts" not in data:
                return False, "Missing required sections"

            for section in ("parts", "mechanisms", "paths"):
                if section in data and not isinstance(data[section], dict):
                    return False, f"{section} section must be an object"

            if "skeleton" in data and not isinstance(data["skeleton"], dict):
                return False, "skeleton section must be an object"

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
            if not isinstance(data, dict):
                return None

            metadata = data.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            parts = data.get("parts", {})
            mechanisms = data.get("mechanisms", {})
            return {
                "name": metadata.get("name", path.stem),
                "version": metadata.get("version", "unknown"),
                "created_at": metadata.get("created_at"),
                "modified_at": metadata.get("modified_at"),
                "parts_count": len(parts) if isinstance(parts, dict) else 0,
                "mechanisms_count": len(mechanisms) if isinstance(mechanisms, dict) else 0,
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
        self._interval = self._normalize_interval(interval_seconds)
        self._last_save: datetime | None = None
        self._autosave_dir: Path | None = None
        self._last_state_signature: str | None = None

    @classmethod
    def _normalize_interval(cls, interval_seconds: object) -> int:
        if isinstance(interval_seconds, bool):
            return cls.DEFAULT_INTERVAL_SECONDS
        if not isinstance(interval_seconds, int | str):
            return cls.DEFAULT_INTERVAL_SECONDS
        try:
            interval = int(interval_seconds)
        except (TypeError, ValueError):
            return cls.DEFAULT_INTERVAL_SECONDS
        if not math.isfinite(float(interval)) or interval <= 0:
            return cls.DEFAULT_INTERVAL_SECONDS
        return int(interval)

    def setup(self, project_dir: Path) -> None:
        """Setup autosave directory."""
        self._autosave_dir = project_dir / self.AUTOSAVE_DIR_NAME
        self._autosave_dir.mkdir(exist_ok=True)

    def set_interval(self, interval_seconds: object) -> None:
        """Update the autosave throttle interval."""
        self._interval = self._normalize_interval(interval_seconds)

    @property
    def interval_seconds(self) -> int:
        """Current normalized autosave throttle interval."""
        return self._interval

    def should_save(self, state: ProjectState | None = None) -> bool:
        """Check if enough time has passed and content changed for autosave."""
        if self._last_save is None:
            return True
        elapsed = (datetime.now() - self._last_save).total_seconds()
        if elapsed < self._interval:
            return False
        if state is not None and self._state_signature(state) == self._last_state_signature:
            return False
        return True

    def autosave(self, state: ProjectState) -> SaveResult:
        """Perform autosave."""
        if not self._autosave_dir:
            return SaveResult.fail("Autosave not configured")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self._autosave_dir / f"autosave_{timestamp}.automataii"
        counter = 1
        while path.exists():
            path = self._autosave_dir / f"autosave_{timestamp}_{counter}.automataii"
            counter += 1

        result = self._serializer.save(state, path, portable_assets=False)
        if result.success:
            self._last_save = datetime.now()
            self._last_state_signature = self._state_signature(state)
            self._cleanup_old_autosaves()

        return result

    def _cleanup_old_autosaves(self, keep_count: int = 5) -> None:
        """Remove old autosave files, keeping only recent ones."""
        if not self._autosave_dir:
            return

        autosaves = sorted(
            self._autosave_files(self._autosave_dir),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for old_save in autosaves[keep_count:]:
            try:
                old_save.unlink()
                assets_dir = old_save.parent / f"{old_save.stem}_assets"
                if assets_dir.is_dir():
                    shutil.rmtree(assets_dir)
                logger.debug(f"Removed old autosave: {old_save}")
            except OSError:
                pass

    @staticmethod
    def _state_signature(state: ProjectState) -> str:
        """Stable content signature; ignores volatile modified timestamps."""
        data = state.to_dict()
        metadata = data.get("metadata")
        if isinstance(metadata, dict):
            metadata.pop("modified_at", None)
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def get_recovery_files(self, project_dir: Path) -> list[Path]:
        """Get list of autosave files for recovery."""
        autosave_dir = project_dir / self.AUTOSAVE_DIR_NAME
        if not autosave_dir.exists():
            return []

        return sorted(
            self._autosave_files(autosave_dir),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    @staticmethod
    def _autosave_files(autosave_dir: Path) -> list[Path]:
        """Return real autosave snapshots, excluding serializer backup artifacts."""
        return [
            path
            for path in autosave_dir.glob("autosave_*.automataii")
            if ".backup" not in path.name
        ]
