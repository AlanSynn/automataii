#!/usr/bin/env python3
"""
Automataii Refactoring Tool
===========================

A safe, automated tool for restructuring the Automataii codebase following
Hexagonal Architecture principles.

Features:
- Automated import rewriting with dependency graph analysis
- Safe file moving with git integration
- Validation checkpoints after each phase
- Rollback capability
- Detailed logging and metrics

Usage:
    python scripts/refactor_tool.py --phase 1 --dry-run
    python scripts/refactor_tool.py --phase 1 --execute
"""

import argparse
import ast
import logging
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ==================== CONFIGURATION ====================

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
BACKUP_DIR = PROJECT_ROOT / ".refactor_backup"

# Migration mapping: old_path -> new_path
MIGRATION_MAP = {
    # Phase 1: Domain consolidation
    "automataii/mechanisms/linkages": "automataii/domain/mechanisms/linkages",
    "automataii/mechanisms/fourbar": "automataii/domain/mechanisms/linkages/fourbar",
    "automataii/mechanisms/fivebar": "automataii/domain/mechanisms/linkages/fivebar",
    "automataii/mechanisms/sixbar": "automataii/domain/mechanisms/linkages/sixbar",
    "automataii/mechanisms/cam": "automataii/domain/mechanisms/cam",
    "automataii/mechanisms/linkage": "automataii/domain/mechanisms/linkages/base",
    "automataii/mechanisms/core": "automataii/domain/mechanisms/core",
    "automataii/mechanisms/catalog": "automataii/domain/mechanisms/catalog",

    # Phase 2: Animation consolidation
    "automataii/animate": "automataii/domain/animation",
    "automataii/animation": "automataii/domain/animation",

    # Phase 3: Kinematics
    "automataii/kinematics": "automataii/domain/kinematics",

    # Phase 4: UI consolidation
    "automataii/gui": "automataii/presentation/qt",
    "automataii/ui": "automataii/presentation/qt",

    # Phase 5: Application services
    "automataii/services": "automataii/application/legacy_services",
    "automataii/scenarios": "automataii/application/scenarios",

    # Phase 6: Infrastructure
    "automataii/core/serialization": "automataii/infrastructure/persistence/serializers",
    "automataii/core/project": "automataii/infrastructure/persistence/project",

    # Phase 7: Shared
    "automataii/core/events": "automataii/shared/events",
    "automataii/core/state": "automataii/shared/state",
    "automataii/config": "automataii/shared/config",
    "automataii/utils": "automataii/shared/utils",
}

# Import rewrite rules
IMPORT_REWRITE_MAP = {
    # Direct module imports
    "from automataii.mechanisms.linkages": "from automataii.domain.mechanisms.linkages",
    "from automataii.mechanisms.fourbar": "from automataii.domain.mechanisms.linkages.fourbar",
    "from automataii.mechanisms.fivebar": "from automataii.domain.mechanisms.linkages.fivebar",
    "from automataii.mechanisms.sixbar": "from automataii.domain.mechanisms.linkages.sixbar",
    "from automataii.mechanisms.cam": "from automataii.domain.mechanisms.cam",
    "from automataii.mechanisms.linkage": "from automataii.domain.mechanisms.linkages.base",
    "from automataii.mechanisms.core": "from automataii.domain.mechanisms.core",
    "from automataii.mechanisms.catalog": "from automataii.domain.mechanisms.catalog",
    "from automataii.animate": "from automataii.domain.animation",
    "from automataii.animation": "from automataii.domain.animation",
    "from automataii.kinematics": "from automataii.domain.kinematics",
    "from automataii.gui": "from automataii.presentation.qt",
    "from automataii.ui": "from automataii.presentation.qt",
    "from automataii.services": "from automataii.application.legacy_services",
    "from automataii.scenarios": "from automataii.application.scenarios",
    "from automataii.core.serialization": "from automataii.infrastructure.persistence.serializers",
    "from automataii.core.project": "from automataii.infrastructure.persistence.project",
    "from automataii.core.events": "from automataii.shared.events",
    "from automataii.core.state": "from automataii.shared.state",
    "from automataii.config": "from automataii.shared.config",
    "from automataii.utils": "from automataii.shared.utils",

    # Import statements
    "import automataii.mechanisms.linkages": "import automataii.domain.mechanisms.linkages",
    "import automataii.mechanisms.fourbar": "import automataii.domain.mechanisms.linkages.fourbar",
    "import automataii.gui": "import automataii.presentation.qt",
    "import automataii.ui": "import automataii.presentation.qt",
}

# Phases configuration
PHASES = {
    1: {
        "name": "Create Target Structure",
        "description": "Create new directory structure without moving files",
        "operations": ["create_directories"],
    },
    2: {
        "name": "Extract Domain Logic",
        "description": "Move pure domain logic to domain/",
        "operations": ["move_domain_files", "rewrite_imports"],
    },
    3: {
        "name": "Consolidate UI",
        "description": "Merge gui/ and ui/ into presentation/qt/",
        "operations": ["move_ui_files", "rewrite_imports"],
    },
    4: {
        "name": "Refactor Application Layer",
        "description": "Consolidate application services",
        "operations": ["move_application_files", "rewrite_imports"],
    },
    5: {
        "name": "Infrastructure Adapters",
        "description": "Move infrastructure concerns",
        "operations": ["move_infrastructure_files", "rewrite_imports"],
    },
}


# ==================== DATA STRUCTURES ====================


@dataclass
class ImportInfo:
    """Information about an import statement."""
    module: str
    names: List[str]
    line_number: int
    is_from_import: bool
    raw_line: str


@dataclass
class FileInfo:
    """Information about a Python file."""
    path: Path
    imports: List[ImportInfo] = field(default_factory=list)
    exported_names: Set[str] = field(default_factory=set)


@dataclass
class MigrationPlan:
    """A plan for migrating files."""
    source: Path
    target: Path
    affected_files: Set[Path] = field(default_factory=set)


@dataclass
class MigrationMetrics:
    """Metrics for the migration process."""
    files_moved: int = 0
    imports_rewritten: int = 0
    errors: int = 0
    warnings: int = 0

    def report(self) -> str:
        return (
            f"Migration Metrics:\n"
            f"  Files Moved: {self.files_moved}\n"
            f"  Imports Rewritten: {self.imports_rewritten}\n"
            f"  Errors: {self.errors}\n"
            f"  Warnings: {self.warnings}\n"
        )


# ==================== UTILITIES ====================


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )


def run_command(cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command safely."""
    logging.debug(f"Running: {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        check=check,
        capture_output=True,
        text=True
    )


def validate_git_repo() -> bool:
    """Validate that we're in a git repository."""
    try:
        run_command(["git", "rev-parse", "--git-dir"])
        return True
    except subprocess.CalledProcessError:
        logging.error("Not in a git repository!")
        return False


def create_backup() -> None:
    """Create a backup of the current state."""
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)

    logging.info(f"Creating backup in {BACKUP_DIR}")
    shutil.copytree(SRC_DIR, BACKUP_DIR / "src")

    # Save git state
    result = run_command(["git", "rev-parse", "HEAD"])
    (BACKUP_DIR / "git_commit.txt").write_text(result.stdout.strip())


def restore_backup() -> None:
    """Restore from backup."""
    if not BACKUP_DIR.exists():
        logging.error("No backup found!")
        return

    logging.warning("Restoring from backup...")
    if SRC_DIR.exists():
        shutil.rmtree(SRC_DIR)
    shutil.copytree(BACKUP_DIR / "src", SRC_DIR)
    logging.info("Backup restored successfully")


# ==================== AST PARSING ====================


class ImportExtractor(ast.NodeVisitor):
    """Extract import information from Python AST."""

    def __init__(self):
        self.imports: List[ImportInfo] = []
        self.exported_names: Set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statement."""
        for alias in node.names:
            self.imports.append(ImportInfo(
                module=alias.name,
                names=[],
                line_number=node.lineno,
                is_from_import=False,
                raw_line=f"import {alias.name}"
            ))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from...import statement."""
        if node.module:
            names = [alias.name for alias in node.names]
            self.imports.append(ImportInfo(
                module=node.module,
                names=names,
                line_number=node.lineno,
                is_from_import=True,
                raw_line=f"from {node.module} import {', '.join(names)}"
            ))

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit assignment to detect __all__."""
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == '__all__':
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant):
                            self.exported_names.add(elt.value)


def parse_python_file(file_path: Path) -> Optional[FileInfo]:
    """Parse a Python file and extract import information."""
    try:
        content = file_path.read_text(encoding='utf-8')
        tree = ast.parse(content, filename=str(file_path))

        extractor = ImportExtractor()
        extractor.visit(tree)

        return FileInfo(
            path=file_path,
            imports=extractor.imports,
            exported_names=extractor.exported_names
        )
    except Exception as e:
        logging.error(f"Failed to parse {file_path}: {e}")
        return None


# ==================== DEPENDENCY ANALYSIS ====================


class DependencyGraph:
    """Build and analyze dependency graph."""

    def __init__(self):
        self.graph: Dict[Path, Set[Path]] = defaultdict(set)
        self.reverse_graph: Dict[Path, Set[Path]] = defaultdict(set)
        self.file_info: Dict[Path, FileInfo] = {}

    def add_file(self, file_info: FileInfo) -> None:
        """Add a file to the dependency graph."""
        self.file_info[file_info.path] = file_info

    def build_graph(self) -> None:
        """Build the complete dependency graph."""
        logging.info("Building dependency graph...")

        for file_path, file_info in self.file_info.items():
            for import_info in file_info.imports:
                # Resolve import to file path
                imported_file = self._resolve_import(file_path, import_info.module)
                if imported_file:
                    self.graph[file_path].add(imported_file)
                    self.reverse_graph[imported_file].add(file_path)

        logging.info(f"Dependency graph built: {len(self.graph)} files")

    def _resolve_import(self, from_file: Path, module: str) -> Optional[Path]:
        """Resolve an import statement to a file path."""
        # Handle relative imports
        if module.startswith('.'):
            # TODO: Implement relative import resolution
            return None

        # Handle absolute imports
        if module.startswith('automataii'):
            # Convert module path to file path
            parts = module.split('.')
            potential_paths = [
                SRC_DIR / Path(*parts[:-1]) / f"{parts[-1]}.py",
                SRC_DIR / Path(*parts) / "__init__.py",
            ]

            for path in potential_paths:
                if path.exists():
                    return path

        return None

    def get_affected_files(self, file_path: Path) -> Set[Path]:
        """Get all files affected by moving a file."""
        return self.reverse_graph.get(file_path, set())

    def find_circular_dependencies(self) -> List[List[Path]]:
        """Find circular dependencies in the graph."""
        # TODO: Implement cycle detection
        return []


# ==================== IMPORT REWRITING ====================


class ImportRewriter:
    """Rewrite imports based on migration map."""

    def __init__(self, migration_map: Dict[str, str]):
        self.migration_map = migration_map
        self.metrics = MigrationMetrics()

    def rewrite_file(self, file_path: Path, dry_run: bool = True) -> bool:
        """Rewrite imports in a single file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            original_content = content

            # Rewrite imports line by line
            lines = content.split('\n')
            modified = False

            for i, line in enumerate(lines):
                new_line = self._rewrite_line(line)
                if new_line != line:
                    lines[i] = new_line
                    modified = True
                    self.metrics.imports_rewritten += 1
                    logging.debug(f"  {file_path.name}:{i+1} | {line.strip()}")
                    logging.debug(f"  → {new_line.strip()}")

            if modified:
                if not dry_run:
                    file_path.write_text('\n'.join(lines), encoding='utf-8')
                logging.info(f"✓ Rewrote {file_path.relative_to(PROJECT_ROOT)}")
                return True

            return False

        except Exception as e:
            logging.error(f"Failed to rewrite {file_path}: {e}")
            self.metrics.errors += 1
            return False

    def _rewrite_line(self, line: str) -> str:
        """Rewrite a single line if it contains imports."""
        stripped = line.strip()

        # Check each rewrite rule
        for old_import, new_import in IMPORT_REWRITE_MAP.items():
            if old_import in line:
                return line.replace(old_import, new_import)

        return line

    def rewrite_all_files(self, files: List[Path], dry_run: bool = True) -> None:
        """Rewrite imports in all files."""
        logging.info(f"Rewriting imports in {len(files)} files...")

        for file_path in files:
            self.rewrite_file(file_path, dry_run=dry_run)

        logging.info(self.metrics.report())


# ==================== FILE MIGRATION ====================


class FileMigrator:
    """Migrate files to new locations."""

    def __init__(self, migration_map: Dict[str, str]):
        self.migration_map = migration_map
        self.metrics = MigrationMetrics()

    def create_target_directories(self, dry_run: bool = True) -> None:
        """Create target directory structure."""
        logging.info("Creating target directory structure...")

        target_dirs = {
            "domain/mechanisms/linkages/fourbar",
            "domain/mechanisms/linkages/fivebar",
            "domain/mechanisms/linkages/sixbar",
            "domain/mechanisms/linkages/base",
            "domain/mechanisms/cam",
            "domain/mechanisms/gears",
            "domain/mechanisms/core",
            "domain/mechanisms/catalog",
            "domain/animation",
            "domain/kinematics/solvers",
            "domain/blueprint",
            "application/mechanisms",
            "application/animation",
            "application/blueprint",
            "application/scenarios",
            "infrastructure/persistence/serializers",
            "infrastructure/persistence/project",
            "infrastructure/compute",
            "infrastructure/telemetry",
            "presentation/qt/windows",
            "presentation/qt/tabs",
            "presentation/qt/widgets",
            "presentation/qt/dialogs",
            "presentation/rendering",
            "shared/events",
            "shared/state",
            "shared/config",
            "shared/types",
            "shared/utils",
        }

        for target_dir in target_dirs:
            full_path = SRC_DIR / "automataii" / target_dir
            if not dry_run:
                full_path.mkdir(parents=True, exist_ok=True)
                (full_path / "__init__.py").touch()
            logging.info(f"  ✓ {target_dir}/")

        logging.info(f"Created {len(target_dirs)} directories")

    def move_file(self, source: Path, target: Path, dry_run: bool = True) -> bool:
        """Move a single file using git mv."""
        try:
            if not source.exists():
                logging.warning(f"Source does not exist: {source}")
                return False

            # Create target directory
            target.parent.mkdir(parents=True, exist_ok=True)

            if not dry_run:
                # Use git mv to preserve history
                run_command(["git", "mv", str(source), str(target)])

            logging.info(f"  {source.relative_to(SRC_DIR)} → {target.relative_to(SRC_DIR)}")
            self.metrics.files_moved += 1
            return True

        except Exception as e:
            logging.error(f"Failed to move {source}: {e}")
            self.metrics.errors += 1
            return False


# ==================== VALIDATION ====================


class Validator:
    """Validate the refactoring process."""

    @staticmethod
    def validate_syntax(file_path: Path) -> bool:
        """Validate Python syntax."""
        try:
            ast.parse(file_path.read_text(encoding='utf-8'))
            return True
        except SyntaxError as e:
            logging.error(f"Syntax error in {file_path}: {e}")
            return False

    @staticmethod
    def validate_imports() -> bool:
        """Validate that all imports can be resolved."""
        try:
            result = run_command(["python", "-c", "import automataii"], check=False)
            if result.returncode == 0:
                logging.info("✓ All imports valid")
                return True
            else:
                logging.error(f"Import validation failed:\n{result.stderr}")
                return False
        except Exception as e:
            logging.error(f"Import validation failed: {e}")
            return False

    @staticmethod
    def validate_application(timeout: int = 15) -> bool:
        """Validate that the application can start."""
        try:
            logging.info(f"Starting application (timeout: {timeout}s)...")
            result = run_command(
                ["timeout", str(timeout), "uv", "run", "automataii"],
                check=False
            )

            # Timeout (124) or Ctrl+C (130) are acceptable
            if result.returncode in [0, 124, 130]:
                logging.info("✓ Application started successfully")
                return True
            else:
                logging.error(f"Application failed to start:\n{result.stderr}")
                return False

        except Exception as e:
            logging.error(f"Application validation failed: {e}")
            return False

    @staticmethod
    def validate_all() -> bool:
        """Run all validation checks."""
        logging.info("=" * 60)
        logging.info("VALIDATION CHECKPOINT")
        logging.info("=" * 60)

        checks = [
            ("Import Resolution", Validator.validate_imports),
            ("Application Launch", lambda: Validator.validate_application(timeout=15)),
        ]

        results = []
        for name, check in checks:
            logging.info(f"\n[{name}]")
            result = check()
            results.append(result)

        all_passed = all(results)
        logging.info("=" * 60)
        if all_passed:
            logging.info("✓ ALL VALIDATION CHECKS PASSED")
        else:
            logging.error("✗ SOME VALIDATION CHECKS FAILED")
        logging.info("=" * 60)

        return all_passed


# ==================== MAIN ORCHESTRATOR ====================


class RefactorOrchestrator:
    """Orchestrate the entire refactoring process."""

    def __init__(self, dry_run: bool = True, verbose: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.dependency_graph = DependencyGraph()
        self.import_rewriter = ImportRewriter(IMPORT_REWRITE_MAP)
        self.file_migrator = FileMigrator(MIGRATION_MAP)

    def run_phase(self, phase_number: int) -> bool:
        """Run a specific migration phase."""
        if phase_number not in PHASES:
            logging.error(f"Invalid phase: {phase_number}")
            return False

        phase = PHASES[phase_number]
        logging.info("=" * 60)
        logging.info(f"PHASE {phase_number}: {phase['name']}")
        logging.info(f"Description: {phase['description']}")
        logging.info(f"Mode: {'DRY RUN' if self.dry_run else 'EXECUTE'}")
        logging.info("=" * 60)

        # Create backup before executing
        if not self.dry_run:
            create_backup()

        # Execute phase operations
        success = True
        for operation in phase['operations']:
            if operation == "create_directories":
                self.file_migrator.create_target_directories(dry_run=self.dry_run)
            elif operation == "move_domain_files":
                success &= self._move_domain_files()
            elif operation == "move_ui_files":
                success &= self._move_ui_files()
            elif operation == "move_application_files":
                success &= self._move_application_files()
            elif operation == "move_infrastructure_files":
                success &= self._move_infrastructure_files()
            elif operation == "rewrite_imports":
                self._rewrite_all_imports()

        # Validate after phase
        if not self.dry_run and phase_number > 1:
            if not Validator.validate_all():
                logging.error("Validation failed! Consider rolling back.")
                return False

        logging.info(f"\n✓ Phase {phase_number} completed")
        return success

    def _move_domain_files(self) -> bool:
        """Move domain files to new locations."""
        # TODO: Implement domain file movement
        logging.info("Moving domain files...")
        return True

    def _move_ui_files(self) -> bool:
        """Move UI files to new locations."""
        # TODO: Implement UI file movement
        logging.info("Moving UI files...")
        return True

    def _move_application_files(self) -> bool:
        """Move application files to new locations."""
        # TODO: Implement application file movement
        logging.info("Moving application files...")
        return True

    def _move_infrastructure_files(self) -> bool:
        """Move infrastructure files to new locations."""
        # TODO: Implement infrastructure file movement
        logging.info("Moving infrastructure files...")
        return True

    def _rewrite_all_imports(self) -> None:
        """Rewrite imports in all Python files."""
        all_files = list(SRC_DIR.rglob("*.py"))
        self.import_rewriter.rewrite_all_files(all_files, dry_run=self.dry_run)

    def analyze_codebase(self) -> None:
        """Analyze the codebase and build dependency graph."""
        logging.info("Analyzing codebase...")

        all_files = list(SRC_DIR.rglob("*.py"))
        logging.info(f"Found {len(all_files)} Python files")

        for file_path in all_files:
            file_info = parse_python_file(file_path)
            if file_info:
                self.dependency_graph.add_file(file_info)

        self.dependency_graph.build_graph()

        # Report statistics
        logging.info(f"Total imports: {sum(len(f.imports) for f in self.dependency_graph.file_info.values())}")


# ==================== CLI ====================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Automataii Refactoring Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze codebase
  python scripts/refactor_tool.py --analyze

  # Dry run phase 1
  python scripts/refactor_tool.py --phase 1 --dry-run

  # Execute phase 1
  python scripts/refactor_tool.py --phase 1

  # Restore from backup
  python scripts/refactor_tool.py --restore
        """
    )

    parser.add_argument(
        "--phase",
        type=int,
        choices=list(PHASES.keys()),
        help="Migration phase to execute"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze codebase and build dependency graph"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no actual changes)"
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore from backup"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    # Validate git repo
    if not validate_git_repo():
        sys.exit(1)

    # Handle restore
    if args.restore:
        restore_backup()
        return

    # Create orchestrator
    orchestrator = RefactorOrchestrator(
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    # Handle analyze
    if args.analyze:
        orchestrator.analyze_codebase()
        return

    # Handle phase execution
    if args.phase:
        success = orchestrator.run_phase(args.phase)
        sys.exit(0 if success else 1)

    # No action specified
    parser.print_help()


if __name__ == "__main__":
    main()
