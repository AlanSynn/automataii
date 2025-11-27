#!/usr/bin/env python3
"""Static analyzer to detect broken method calls after refactoring.

This tool analyzes Python source files to detect method calls that reference
non-existent methods on known class instances. It's particularly useful after
refactoring to catch cases where:
- Methods were renamed but call sites weren't updated
- Methods were deleted but call sites remain
- Classes were refactored with different interfaces

Architecture:
- Uses Python's ast module for parsing
- Two-pass analysis: first collect class definitions, then analyze calls
- Reports findings with file:line references for easy navigation

Usage:
    python scripts/broken_method_checker.py [--path src/automataii] [--verbose]

Author: Alan Synn
Date: 2025-11-27
"""

import argparse
import ast
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeAlias

logger = logging.getLogger(__name__)

# Type aliases
MethodSet: TypeAlias = set[str]
ClassMethodMap: TypeAlias = dict[str, MethodSet]
AttributeTypeMap: TypeAlias = dict[str, str]  # attribute_name -> class_name


@dataclass
class ClassInfo:
    """Information about a class definition."""

    name: str
    file_path: Path
    line_number: int
    methods: set[str] = field(default_factory=set)
    base_classes: list[str] = field(default_factory=list)


@dataclass
class MethodCallInfo:
    """Information about a method call site."""

    file_path: Path
    line_number: int
    attribute_name: str  # e.g., "_path_trace_manager"
    method_name: str  # e.g., "clear_all"
    full_expression: str  # e.g., "self._path_trace_manager.clear_all"


@dataclass
class BrokenCallInfo:
    """Information about a broken method call."""

    call_info: MethodCallInfo
    expected_class: str
    available_methods: list[str]
    suggestion: str | None = None


class ClassDefinitionCollector(ast.NodeVisitor):
    """AST visitor to collect class definitions and their methods."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.classes: dict[str, ClassInfo] = {}
        self._current_class: str | None = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition node."""
        base_names = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_names.append(base.attr)

        class_info = ClassInfo(
            name=node.name,
            file_path=self.file_path,
            line_number=node.lineno,
            methods=set(),
            base_classes=base_names,
        )

        self._current_class = node.name

        # Collect methods
        for item in node.body:
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                class_info.methods.add(item.name)

        self.classes[node.name] = class_info
        self._current_class = None

        # Continue visiting nested classes
        self.generic_visit(node)


class TypeInferenceVisitor(ast.NodeVisitor):
    """AST visitor to infer types of instance attributes from __init__ and assignments."""

    def __init__(self, file_path: Path, known_classes: dict[str, ClassInfo]):
        self.file_path = file_path
        self.known_classes = known_classes
        # Map: (class_name, attribute_name) -> inferred_type
        self.attribute_types: dict[tuple[str, str], str] = {}
        self._current_class: str | None = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition and analyze its __init__."""
        prev_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = prev_class

    def visit_Assign(self, node: ast.Assign) -> None:
        """Analyze assignments to infer attribute types."""
        if self._current_class is None:
            return

        for target in node.targets:
            # Check for self.attribute = SomeClass(...)
            if isinstance(target, ast.Attribute):
                if isinstance(target.value, ast.Name) and target.value.id == "self":
                    attr_name = target.attr
                    inferred_type = self._infer_type_from_value(node.value)
                    if inferred_type:
                        key = (self._current_class, attr_name)
                        self.attribute_types[key] = inferred_type

        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Analyze annotated assignments."""
        if self._current_class is None:
            return

        if isinstance(node.target, ast.Attribute):
            if isinstance(node.target.value, ast.Name) and node.target.value.id == "self":
                attr_name = node.target.attr
                # Use annotation if available
                inferred_type = self._get_type_from_annotation(node.annotation)
                if inferred_type:
                    key = (self._current_class, attr_name)
                    self.attribute_types[key] = inferred_type

        self.generic_visit(node)

    def _infer_type_from_value(self, value: ast.expr) -> str | None:
        """Infer type from an assigned value."""
        if isinstance(value, ast.Call):
            if isinstance(value.func, ast.Name):
                # Direct class instantiation: PathTraceManager()
                return value.func.id
            elif isinstance(value.func, ast.Attribute):
                # Qualified instantiation: module.ClassName()
                return value.func.attr
        return None

    def _get_type_from_annotation(self, annotation: ast.expr | None) -> str | None:
        """Get type from annotation."""
        if annotation is None:
            return None
        if isinstance(annotation, ast.Name):
            return annotation.id
        if isinstance(annotation, ast.Subscript):
            # Handle Optional[ClassName], etc.
            if isinstance(annotation.value, ast.Name):
                if annotation.value.id in ("Optional", "Union"):
                    if isinstance(annotation.slice, ast.Name):
                        return annotation.slice.id
        return None


class MethodCallCollector(ast.NodeVisitor):
    """AST visitor to collect method calls on instance attributes."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.calls: list[MethodCallInfo] = []
        self._current_class: str | None = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track current class context."""
        prev_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = prev_class

    def visit_Call(self, node: ast.Call) -> None:
        """Visit method call node."""
        # Look for pattern: self.attribute.method(...)
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr

            # Check if it's on a self attribute
            if isinstance(node.func.value, ast.Attribute):
                if (
                    isinstance(node.func.value.value, ast.Name)
                    and node.func.value.value.id == "self"
                ):
                    attr_name = node.func.value.attr
                    call_info = MethodCallInfo(
                        file_path=self.file_path,
                        line_number=node.lineno,
                        attribute_name=attr_name,
                        method_name=method_name,
                        full_expression=f"self.{attr_name}.{method_name}",
                    )
                    self.calls.append(call_info)

        self.generic_visit(node)


def collect_all_classes(root_path: Path) -> dict[str, ClassInfo]:
    """Collect all class definitions from Python files."""
    all_classes: dict[str, ClassInfo] = {}

    for py_file in root_path.rglob("*.py"):
        # Skip backup directories and test files
        if ".refactor_backup" in str(py_file) or "__pycache__" in str(py_file):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
            collector = ClassDefinitionCollector(py_file)
            collector.visit(tree)

            for class_name, class_info in collector.classes.items():
                # Store with full key to handle name collisions
                key = class_name
                if key in all_classes:
                    # Handle collision by using qualified name
                    key = f"{py_file.stem}.{class_name}"
                all_classes[key] = class_info

        except SyntaxError as e:
            logger.warning(f"Syntax error in {py_file}: {e}")
        except Exception as e:
            logger.warning(f"Error parsing {py_file}: {e}")

    return all_classes


def collect_attribute_types(
    root_path: Path, known_classes: dict[str, ClassInfo]
) -> dict[tuple[str, str], str]:
    """Collect inferred types for instance attributes."""
    all_types: dict[tuple[str, str], str] = {}

    for py_file in root_path.rglob("*.py"):
        if ".refactor_backup" in str(py_file) or "__pycache__" in str(py_file):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
            visitor = TypeInferenceVisitor(py_file, known_classes)
            visitor.visit(tree)
            all_types.update(visitor.attribute_types)

        except SyntaxError as e:
            logger.warning(f"Syntax error in {py_file}: {e}")
        except Exception as e:
            logger.warning(f"Error parsing {py_file}: {e}")

    return all_types


def collect_method_calls(root_path: Path) -> list[MethodCallInfo]:
    """Collect all method calls on instance attributes."""
    all_calls: list[MethodCallInfo] = []

    for py_file in root_path.rglob("*.py"):
        if ".refactor_backup" in str(py_file) or "__pycache__" in str(py_file):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
            collector = MethodCallCollector(py_file)
            collector.visit(tree)
            all_calls.extend(collector.calls)

        except SyntaxError as e:
            logger.warning(f"Syntax error in {py_file}: {e}")
        except Exception as e:
            logger.warning(f"Error parsing {py_file}: {e}")

    return all_calls


def find_similar_method(target: str, available: set[str], threshold: float = 0.6) -> str | None:
    """Find similar method name using simple similarity metric."""
    best_match = None
    best_score = 0.0

    for method in available:
        # Skip dunder methods
        if method.startswith("__"):
            continue

        # Simple similarity: common prefix/suffix + length ratio
        common = sum(1 for a, b in zip(target, method) if a == b)
        max_len = max(len(target), len(method))
        score = common / max_len if max_len > 0 else 0

        # Boost if contains target or vice versa
        if target in method or method in target:
            score += 0.3

        if score > best_score and score >= threshold:
            best_score = score
            best_match = method

    return best_match


def analyze_broken_calls(
    classes: dict[str, ClassInfo],
    attribute_types: dict[tuple[str, str], str],
    calls: list[MethodCallInfo],
) -> list[BrokenCallInfo]:
    """Analyze calls to find broken method references."""
    broken_calls: list[BrokenCallInfo] = []

    # Build class name -> ClassInfo map
    class_by_name: dict[str, ClassInfo] = {}
    for key, info in classes.items():
        class_by_name[info.name] = info

    for call in calls:
        # Try to find the expected type for this attribute
        expected_type: str | None = None

        # Check all classes for this attribute
        for (class_name, attr_name), type_name in attribute_types.items():
            if attr_name == call.attribute_name:
                expected_type = type_name
                break

        if expected_type is None:
            # Can't determine type, skip
            continue

        # Get class info
        class_info = class_by_name.get(expected_type)
        if class_info is None:
            # Unknown class, skip
            continue

        # Check if method exists
        if call.method_name not in class_info.methods:
            # Broken call found!
            suggestion = find_similar_method(call.method_name, class_info.methods)

            broken_info = BrokenCallInfo(
                call_info=call,
                expected_class=expected_type,
                available_methods=sorted(
                    m for m in class_info.methods if not m.startswith("_")
                ),
                suggestion=suggestion,
            )
            broken_calls.append(broken_info)

    return broken_calls


def format_report(broken_calls: list[BrokenCallInfo], verbose: bool = False) -> str:
    """Format analysis report."""
    if not broken_calls:
        return "No broken method calls detected."

    lines = [
        "=" * 80,
        "BROKEN METHOD CALL ANALYSIS REPORT",
        "=" * 80,
        f"Found {len(broken_calls)} potentially broken method call(s):",
        "",
    ]

    # Group by file for readability
    by_file: dict[Path, list[BrokenCallInfo]] = {}
    for info in broken_calls:
        path = info.call_info.file_path
        if path not in by_file:
            by_file[path] = []
        by_file[path].append(info)

    for file_path, file_calls in sorted(by_file.items()):
        lines.append("-" * 80)
        lines.append(f"File: {file_path}")
        lines.append("-" * 80)

        for info in sorted(file_calls, key=lambda x: x.call_info.line_number):
            call = info.call_info
            lines.append(f"")
            lines.append(f"  Line {call.line_number}: {call.full_expression}()")
            lines.append(f"  Expected class: {info.expected_class}")
            lines.append(f"  Missing method: {call.method_name}")

            if info.suggestion:
                lines.append(f"  SUGGESTION: Did you mean '{info.suggestion}'?")

            if verbose:
                lines.append(f"  Available methods: {', '.join(info.available_methods)}")

        lines.append("")

    lines.append("=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Detect broken method calls after refactoring"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("src/automataii"),
        help="Root path to analyze (default: src/automataii)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all available methods for each broken call",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

    root_path = args.path
    if not root_path.exists():
        logger.error(f"Path does not exist: {root_path}")
        return 1

    logger.info(f"Analyzing: {root_path}")

    # Phase 1: Collect class definitions
    logger.info("Phase 1: Collecting class definitions...")
    classes = collect_all_classes(root_path)
    logger.info(f"  Found {len(classes)} classes")

    # Phase 2: Infer attribute types
    logger.info("Phase 2: Inferring attribute types...")
    attribute_types = collect_attribute_types(root_path, classes)
    logger.info(f"  Inferred {len(attribute_types)} attribute types")

    # Phase 3: Collect method calls
    logger.info("Phase 3: Collecting method calls...")
    calls = collect_method_calls(root_path)
    logger.info(f"  Found {len(calls)} method calls on instance attributes")

    # Phase 4: Analyze for broken calls
    logger.info("Phase 4: Analyzing for broken calls...")
    broken_calls = analyze_broken_calls(classes, attribute_types, calls)

    # Output report
    report = format_report(broken_calls, verbose=args.verbose)
    print("\n" + report)

    # Return non-zero if broken calls found
    return 1 if broken_calls else 0


if __name__ == "__main__":
    sys.exit(main())
