#!/usr/bin/env python3
"""
Import Analyzer and Migration Tool.

Analyzes codebase imports and provides migration recommendations
for moving from legacy core/ imports to new architectural layers.

Usage:
    python scripts/import_analyzer.py analyze    # Show analysis
    python scripts/import_analyzer.py migrate    # Generate migration script
    python scripts/import_analyzer.py apply      # Apply migrations (dry-run)
    python scripts/import_analyzer.py apply --execute  # Actually apply
"""

import ast
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ImportInfo:
    """Information about an import statement."""
    file: Path
    line: int
    module: str
    names: list[str]
    original_line: str


@dataclass
class MigrationRule:
    """Rule for migrating imports."""
    old_module: str
    new_module: str
    names: list[str] | None = None  # None means all names


# Migration rules: old -> new
MIGRATION_RULES = [
    # Models - facades that can be replaced
    MigrationRule(
        "automataii.core.models",
        "automataii.presentation.qt.models",
        ["PartInfo", "JOINT_COLORS"]
    ),
    MigrationRule(
        "automataii.core.models",
        "automataii.domain.skeleton.constants",
        ["SKELETON_JOINTS", "JOINT_CONNECTIONS"]
    ),
    MigrationRule(
        "automataii.core.models_skeleton",
        "automataii.domain.skeleton",
        ["StandardizedJointModel", "StandardizedSkeletonModel"]
    ),
    MigrationRule(
        "automataii.core.models_pydantic",
        "automataii.domain.project",
        ["ProjectMetadata"]
    ),

    # Telemetry
    MigrationRule(
        "automataii.core.telemetry",
        "automataii.infrastructure.telemetry",
        ["telemetry_span", "TelemetrySpan"]
    ),

    # Events
    MigrationRule(
        "automataii.core.events",
        "automataii.infrastructure.events",
        ["EventBus", "Event", "get_global_event_bus"]
    ),
    MigrationRule(
        "automataii.core.events.base",
        "automataii.infrastructure.events",
        ["ProjectLoaded", "ProjectSaved", "ApplicationStarted",
         "ComponentActivated", "ComponentDeactivated"]
    ),

    # State
    MigrationRule(
        "automataii.core.state",
        "automataii.infrastructure.state",
        ["StateStore", "Action", "Reducer", "get_global_store"]
    ),

    # Container
    MigrationRule(
        "automataii.core.container",
        "automataii.infrastructure.container",
        ["Container", "Injectable", "inject", "get_global_container"]
    ),

    # Managers
    MigrationRule(
        "automataii.core.skeleton_manager",
        "automataii.application.managers",
        ["SkeletonManager"]
    ),
    MigrationRule(
        "automataii.core.mechanism_manager",
        "automataii.application.managers",
        ["MechanismManager"]
    ),
    MigrationRule(
        "automataii.core.project_data_manager",
        "automataii.application.managers",
        ["ProjectDataManager"]
    ),
    MigrationRule(
        "automataii.core.blueprint_manager",
        "automataii.application.managers",
        ["BlueprintExportManager"]
    ),
]


class ImportAnalyzer:
    """Analyzes imports across the codebase."""

    def __init__(self, src_dir: Path):
        self.src_dir = src_dir
        self.imports: list[ImportInfo] = []
        self.issues: list[str] = []

    def scan(self) -> None:
        """Scan all Python files for imports."""
        for py_file in self.src_dir.rglob("*.py"):
            self._scan_file(py_file)

    def _scan_file(self, py_file: Path) -> None:
        """Scan a single file for imports."""
        try:
            content = py_file.read_text()
            lines = content.split('\n')
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("automataii.core"):
                        names = [alias.name for alias in node.names]
                        original_line = lines[node.lineno - 1].strip()
                        self.imports.append(ImportInfo(
                            file=py_file,
                            line=node.lineno,
                            module=node.module,
                            names=names,
                            original_line=original_line
                        ))
        except Exception as e:
            self.issues.append(f"Error parsing {py_file}: {e}")

    def get_migration_candidates(self) -> dict[Path, list[tuple[ImportInfo, MigrationRule]]]:
        """Get imports that can be migrated."""
        candidates: dict[Path, list[tuple[ImportInfo, MigrationRule]]] = defaultdict(list)

        for imp in self.imports:
            for rule in MIGRATION_RULES:
                if imp.module == rule.old_module or imp.module.startswith(rule.old_module + "."):
                    # Check if any imported names match the rule
                    if rule.names is None:
                        candidates[imp.file].append((imp, rule))
                    else:
                        matching_names = [n for n in imp.names if n in rule.names]
                        if matching_names:
                            candidates[imp.file].append((imp, rule))

        return candidates

    def get_statistics(self) -> dict[str, Any]:
        """Get import statistics."""
        stats = {
            "total_files": len(set(i.file for i in self.imports)),
            "total_imports": len(self.imports),
            "by_module": defaultdict(int),
            "by_name": defaultdict(int),
        }

        for imp in self.imports:
            stats["by_module"][imp.module] += 1
            for name in imp.names:
                stats["by_name"][f"{imp.module}.{name}"] += 1

        return stats


def print_analysis(analyzer: ImportAnalyzer) -> None:
    """Print analysis results."""
    stats = analyzer.get_statistics()
    candidates = analyzer.get_migration_candidates()

    print("=" * 70)
    print("IMPORT ANALYSIS REPORT")
    print("=" * 70)

    print(f"\nTotal files with core imports: {stats['total_files']}")
    print(f"Total import statements: {stats['total_imports']}")

    print("\n--- Imports by Module ---")
    for mod, count in sorted(stats["by_module"].items(), key=lambda x: -x[1]):
        print(f"  {mod}: {count}")

    print("\n--- Migration Candidates ---")
    migratable_count = sum(len(v) for v in candidates.values())
    print(f"Total imports that can be migrated: {migratable_count}")

    # Exclude core/ internal files
    external_candidates = {
        f: imps for f, imps in candidates.items()
        if "core/" not in str(f) or "__init__.py" in str(f)
    }

    print(f"\nFiles needing migration (excluding core/ internals):")
    for file, imps in sorted(external_candidates.items(), key=lambda x: str(x[0])):
        rel_path = file.relative_to(analyzer.src_dir)
        if "core/" in str(rel_path) and "__init__.py" not in str(rel_path):
            continue
        print(f"\n  {rel_path}:")
        for imp, rule in imps:
            for name in imp.names:
                if rule.names is None or name in rule.names:
                    print(f"    L{imp.line}: {imp.module}.{name} -> {rule.new_module}.{name}")


def generate_migration_script(analyzer: ImportAnalyzer) -> str:
    """Generate a migration script."""
    candidates = analyzer.get_migration_candidates()

    script_lines = [
        "#!/usr/bin/env python3",
        '"""Auto-generated import migration script."""',
        "",
        "import re",
        "from pathlib import Path",
        "",
        "def migrate_file(file_path: Path) -> bool:",
        '    """Migrate imports in a single file. Returns True if modified."""',
        "    content = file_path.read_text()",
        "    original = content",
        "",
    ]

    # Group migrations by (old_module, new_module)
    migrations: dict[tuple[str, str], set[str]] = defaultdict(set)
    for file, imps in candidates.items():
        for imp, rule in imps:
            for name in imp.names:
                if rule.names is None or name in rule.names:
                    migrations[(rule.old_module, rule.new_module)].add(name)

    for (old_mod, new_mod), names in migrations.items():
        for name in names:
            old_pattern = f"from {old_mod} import"
            script_lines.append(
                f'    # Migrate {old_mod}.{name} -> {new_mod}.{name}'
            )
            script_lines.append(
                f'    content = re.sub('
                f'r"from {re.escape(old_mod)} import (.*)\\\\b{name}\\\\b", '
                f'"from {new_mod} import \\\\1{name}", '
                f'content)'
            )

    script_lines.extend([
        "",
        "    if content != original:",
        "        file_path.write_text(content)",
        "        return True",
        "    return False",
        "",
        'if __name__ == "__main__":',
        '    src_dir = Path("src/automataii")',
        '    modified = 0',
        '    for py_file in src_dir.rglob("*.py"):',
        '        if migrate_file(py_file):',
        '            print(f"Modified: {py_file}")',
        '            modified += 1',
        '    print(f"\\nTotal files modified: {modified}")',
    ])

    return "\n".join(script_lines)


def apply_migrations(analyzer: ImportAnalyzer, dry_run: bool = True) -> None:
    """Apply migrations to files."""
    candidates = analyzer.get_migration_candidates()

    # Skip core/ internal files
    external_files = {
        f: imps for f, imps in candidates.items()
        if "core/" not in str(f)
    }

    modified_count = 0

    for file, imps in external_files.items():
        content = file.read_text()
        original = content

        for imp, rule in imps:
            # Build replacement patterns
            for name in imp.names:
                if rule.names is None or name in rule.names:
                    # Simple replacement: change module path
                    old_import = f"from {imp.module} import"
                    new_import = f"from {rule.new_module} import"

                    # Only replace if importing this specific name
                    pattern = rf"(from {re.escape(imp.module)} import .*)\b{name}\b"
                    replacement = rf"from {rule.new_module} import \1".replace(
                        f"from {imp.module} import", ""
                    ).strip()

                    # Simpler approach: just replace the module path
                    content = content.replace(
                        f"from {imp.module} import",
                        f"from {rule.new_module} import"
                    )

        if content != original:
            rel_path = file.relative_to(analyzer.src_dir)
            if dry_run:
                print(f"[DRY-RUN] Would modify: {rel_path}")
            else:
                file.write_text(content)
                print(f"Modified: {rel_path}")
            modified_count += 1

    print(f"\n{'Would modify' if dry_run else 'Modified'}: {modified_count} files")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    src_dir = Path("src/automataii")

    analyzer = ImportAnalyzer(src_dir)
    analyzer.scan()

    if command == "analyze":
        print_analysis(analyzer)
    elif command == "migrate":
        script = generate_migration_script(analyzer)
        print(script)
    elif command == "apply":
        dry_run = "--execute" not in sys.argv
        apply_migrations(analyzer, dry_run=dry_run)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
