#!/usr/bin/env python3
"""
Import Migration Script.

Migrates all core/ imports to their proper architectural locations.
"""

import re
import sys
from pathlib import Path


# Define simple text replacements: (old_text, new_text)
REPLACEMENTS = [
    # Telemetry
    ("from automataii.core.telemetry import", "from automataii.infrastructure.telemetry import"),

    # Container
    ("from automataii.core.container import", "from automataii.infrastructure.container import"),

    # Events
    ("from automataii.core.events import", "from automataii.infrastructure.events import"),
    ("from automataii.core.events.base import", "from automataii.infrastructure.events import"),
    ("from automataii.core.events.types import", "from automataii.infrastructure.events import"),
    ("from automataii.core.events.decorators import", "from automataii.infrastructure.events import"),
    ("from automataii.core.events.event_bus import", "from automataii.infrastructure.events import"),

    # State
    ("from automataii.core.state import", "from automataii.infrastructure.state import"),
    ("from automataii.core.state.base import", "from automataii.infrastructure.state import"),
    ("from automataii.core.state.store import", "from automataii.infrastructure.state import"),
    ("from automataii.core.state.middleware import", "from automataii.infrastructure.state import"),
    ("from automataii.core.state.selectors import", "from automataii.infrastructure.state import"),

    # Models
    ("from automataii.core.models import", "from automataii.presentation.qt.models import"),

    # Skeleton models
    ("from automataii.core.models_skeleton import", "from automataii.domain.skeleton import"),

    # Pydantic models
    ("from automataii.core.models_pydantic import", "from automataii.domain.project import"),

    # Managers
    ("from automataii.core.skeleton_manager import", "from automataii.application.managers import"),
    ("from automataii.core.mechanism_manager import", "from automataii.application.managers import"),
    ("from automataii.core.project_data_manager import", "from automataii.application.managers import"),
    ("from automataii.core.blueprint_manager import", "from automataii.application.managers import"),
]


def migrate_file(file_path: Path, dry_run: bool = True) -> tuple[bool, list[str]]:
    """
    Migrate imports in a single file.

    Returns:
        (modified, changes): Whether file was modified and list of changes made
    """
    content = file_path.read_text()
    original = content
    changes = []

    for old_text, new_text in REPLACEMENTS:
        if old_text in content:
            # Find lines with the old import
            for line in content.split('\n'):
                if old_text in line:
                    new_line = line.replace(old_text, new_text)
                    if line != new_line:
                        changes.append(f"  {line.strip()}")
                        changes.append(f"    -> {new_line.strip()}")

            content = content.replace(old_text, new_text)

    if content != original:
        if not dry_run:
            file_path.write_text(content)
        return True, changes

    return False, []


def main():
    dry_run = "--execute" not in sys.argv

    if dry_run:
        print("DRY RUN - No files will be modified. Use --execute to apply changes.\n")

    src_dir = Path("src/automataii")

    # Exclude core/ internal files - we want to update consumers, not the source
    exclude_dirs = {"core", "__pycache__"}

    modified_count = 0

    for py_file in src_dir.rglob("*.py"):
        # Skip excluded directories
        if any(part in exclude_dirs for part in py_file.parts):
            continue

        # Check if file has core imports
        content = py_file.read_text()
        if "from automataii.core" not in content:
            continue

        modified, changes = migrate_file(py_file, dry_run=dry_run)

        if modified:
            rel_path = py_file.relative_to(src_dir)
            action = "Would modify" if dry_run else "Modified"
            print(f"\n{action}: {rel_path}")
            for change in changes:
                print(change)
            modified_count += 1

    print(f"\n{'Would modify' if dry_run else 'Modified'}: {modified_count} files")

    if dry_run and modified_count > 0:
        print("\nRun with --execute to apply these changes.")


if __name__ == "__main__":
    main()
