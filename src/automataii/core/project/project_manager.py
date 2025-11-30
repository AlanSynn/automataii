"""
Project Manager - Handles project lifecycle and operations.
"""

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from automataii.infrastructure.container import Injectable
from automataii.infrastructure.events import (
    AutoSaveTriggered,
    EventBus,
    ProjectClosed,
    ProjectModified,
    get_global_event_bus,
)

from .project_format import AtiiProject


class ProjectManager(Injectable):
    """
    Manages project lifecycle and operations.

    Features:
    - Project creation, loading, saving
    - Auto-save with crash recovery
    - Project templates
    - Recent projects tracking
    - File system watching
    - Atomic operations
    """

    def __init__(self, event_bus: EventBus = None):
        self._current_project: AtiiProject | None = None
        self._event_bus = event_bus or get_global_event_bus()
        self._logger = logging.getLogger(__name__)
        self._lock = threading.RLock()

        # Auto-save configuration
        self._auto_save_enabled = True
        self._auto_save_interval = 300  # 5 minutes
        self._auto_save_timer: threading.Timer | None = None

        # Recent projects
        self._recent_projects: list[dict[str, Any]] = []
        self._max_recent_projects = 10

        # Project templates
        self._templates: dict[str, dict[str, Any]] = {}
        self._load_default_templates()

        # File system watcher (placeholder for future implementation)
        self._project_watcher: Any | None = None

        # Recovery data
        self._recovery_data: dict[str, Any] = {}

        # Subscribe to project events
        self._event_bus.subscribe(ProjectModified, self._on_project_modified)






    def save_project(self, file_path: Path | None = None) -> bool:
        """
        Save current project.

        Args:
            file_path: Path to save to (optional)

        Returns:
            True if saved successfully
        """
        if not self._current_project:
            return False

        try:
            with self._lock:
                self._current_project.save(file_path)

                # Update recent projects
                if self._current_project.file_path:
                    self._add_to_recent_projects(
                        self._current_project.file_path,
                        self._current_project.name
                    )

                self._logger.info(f"Saved project: {self._current_project.name}")
                return True

        except Exception as e:
            self._logger.error(f"Failed to save project: {e}", exc_info=True)
            return False

    def close_project(self, save_if_modified: bool = True) -> bool:
        """
        Close current project.

        Args:
            save_if_modified: Save project if it has unsaved changes

        Returns:
            True if closed successfully
        """
        if not self._current_project:
            return True

        try:
            with self._lock:
                project_name = self._current_project.name

                # Save if modified and requested
                if save_if_modified and self._current_project.is_modified:
                    if not self.save_project():
                        return False  # Save failed

                # Stop auto-save
                self._stop_auto_save()

                # Clear current project
                self._current_project = None

                self._logger.info(f"Closed project: {project_name}")

                # Fire event
                event = ProjectClosed(
                    aggregate_id=str(id(self)),
                    project_name=project_name
                )
                self._event_bus.publish(event)

                return True

        except Exception as e:
            self._logger.error(f"Failed to close project: {e}", exc_info=True)
            return False

    def auto_save(self) -> bool:
        """
        Perform auto-save if project is modified.

        Returns:
            True if auto-save was performed or not needed
        """
        if not self._current_project or not self._current_project.is_modified:
            return True

        if not self._current_project.file_path:
            # Can't auto-save unsaved project
            return False

        try:
            # Create backup before auto-save
            backup_path = self._create_auto_save_backup()

            # Save project
            success = self.save_project()

            if success:
                self._logger.debug("Auto-save completed")

                # Fire event
                event = AutoSaveTriggered(
                    aggregate_id=str(id(self._current_project)),
                    backup_path=str(backup_path) if backup_path else None
                )
                self._event_bus.publish(event)

            return success

        except Exception as e:
            self._logger.error(f"Auto-save failed: {e}", exc_info=True)
            return False









    def _start_auto_save(self) -> None:
        """Start auto-save timer."""
        if not self._auto_save_enabled:
            return

        self._stop_auto_save()  # Stop existing timer

        def auto_save_callback():
            if self.auto_save():
                # Schedule next auto-save
                self._start_auto_save()

        self._auto_save_timer = threading.Timer(
            self._auto_save_interval,
            auto_save_callback
        )
        self._auto_save_timer.daemon = True
        self._auto_save_timer.start()

    def _stop_auto_save(self) -> None:
        """Stop auto-save timer."""
        if self._auto_save_timer:
            self._auto_save_timer.cancel()
            self._auto_save_timer = None

    def _on_project_modified(self, event: ProjectModified) -> None:
        """Handle project modification events."""
        # Could trigger immediate backup or other actions
        pass

    def _add_to_recent_projects(self, file_path: Path, project_name: str) -> None:
        """Add project to recent projects list."""
        project_info = {
            'path': str(file_path),
            'name': project_name,
            'last_opened': datetime.now().isoformat(),
            'exists': file_path.exists()
        }

        # Remove if already in list
        self._recent_projects = [
            p for p in self._recent_projects
            if p['path'] != str(file_path)
        ]

        # Add to beginning
        self._recent_projects.insert(0, project_info)

        # Limit list size
        if len(self._recent_projects) > self._max_recent_projects:
            self._recent_projects = self._recent_projects[:self._max_recent_projects]

    def _apply_template(self, project: AtiiProject, template_name: str) -> None:
        """Apply template to project."""
        template = self._templates.get(template_name, {})

        # Apply template data
        if 'project_data' in template:
            for key, value in template['project_data'].items():
                project.set_project_data(key, value)

        if 'assets' in template:
            for _asset in template['assets']:
                # Add template assets (placeholder implementation)
                pass

    def _load_default_templates(self) -> None:
        """Load default project templates."""
        self._templates = {
            'default': {
                'name': 'Default Project',
                'description': 'Empty project with basic structure',
                'project_data': {
                    'version': '1.0.0',
                    'settings': {}
                }
            },
            'tutorial': {
                'name': 'Tutorial Project',
                'description': 'Sample project for learning',
                'project_data': {
                    'version': '1.0.0',
                    'tutorial_step': 0,
                    'settings': {}
                }
            },
            'showcase': {
                'name': 'Showcase Project',
                'description': 'Demonstration of features',
                'project_data': {
                    'version': '1.0.0',
                    'demo_mode': True,
                    'settings': {}
                }
            }
        }

    def _create_auto_save_backup(self) -> Path | None:
        """Create backup before auto-save."""
        if not self._current_project or not self._current_project.file_path:
            return None

        try:
            backup_dir = Path.cwd() / ".automataii" / "auto-save"
            backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{self._current_project.file_path.stem}_auto_{timestamp}.atii"
            backup_path = backup_dir / backup_name

            # Copy current file
            import shutil
            shutil.copy2(self._current_project.file_path, backup_path)

            # Clean up old auto-save backups (keep last 5)
            auto_saves = sorted(
                backup_dir.glob(f"{self._current_project.file_path.stem}_auto_*.atii"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            for old_backup in auto_saves[5:]:
                try:
                    old_backup.unlink()
                except:
                    pass

            return backup_path

        except Exception as e:
            self._logger.warning(f"Failed to create auto-save backup: {e}")
            return None


# Global project manager instance
_global_project_manager: ProjectManager | None = None


def get_global_project_manager() -> ProjectManager:
    """Get the global project manager."""
    global _global_project_manager
    if _global_project_manager is None:
        _global_project_manager = ProjectManager()
    return _global_project_manager


