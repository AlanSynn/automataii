#!/usr/bin/env python3
"""
Golden Master Capture for Qt GUI Classes
Captures structural signatures that must be preserved during refactoring.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MethodSignature:
    """Captured method signature."""
    name: str
    args: list[str]
    defaults_count: int
    return_annotation: str | None
    decorators: list[str]
    is_async: bool
    docstring_hash: str | None  # Hash of docstring to detect changes


@dataclass
class SignalDefinition:
    """Qt signal definition."""
    name: str
    args: str  # Signal argument types as string


@dataclass
class StateVariable:
    """Instance variable definition."""
    name: str
    type_annotation: str | None
    initial_value_repr: str | None


@dataclass
class GoldenMaster:
    """Complete golden master snapshot."""
    file_path: str
    file_hash: str
    class_name: str
    public_methods: list[MethodSignature]
    private_methods: list[MethodSignature]
    signals: list[SignalDefinition]
    state_variables: list[StateVariable]
    imports: list[str]
    base_classes: list[str]

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "class_name": self.class_name,
            "public_methods": [
                {
                    "name": m.name,
                    "args": m.args,
                    "defaults_count": m.defaults_count,
                    "return_annotation": m.return_annotation,
                    "decorators": m.decorators,
                    "is_async": m.is_async,
                    "docstring_hash": m.docstring_hash,
                }
                for m in self.public_methods
            ],
            "private_methods": [
                {
                    "name": m.name,
                    "args": m.args,
                    "defaults_count": m.defaults_count,
                    "return_annotation": m.return_annotation,
                    "decorators": m.decorators,
                    "is_async": m.is_async,
                    "docstring_hash": m.docstring_hash,
                }
                for m in self.private_methods
            ],
            "signals": [{"name": s.name, "args": s.args} for s in self.signals],
            "state_variables": [
                {
                    "name": v.name,
                    "type_annotation": v.type_annotation,
                    "initial_value_repr": v.initial_value_repr,
                }
                for v in self.state_variables
            ],
            "imports": self.imports,
            "base_classes": self.base_classes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GoldenMaster":
        return cls(
            file_path=data["file_path"],
            file_hash=data["file_hash"],
            class_name=data["class_name"],
            public_methods=[
                MethodSignature(**m) for m in data["public_methods"]
            ],
            private_methods=[
                MethodSignature(**m) for m in data["private_methods"]
            ],
            signals=[SignalDefinition(**s) for s in data["signals"]],
            state_variables=[StateVariable(**v) for v in data["state_variables"]],
            imports=data["imports"],
            base_classes=data["base_classes"],
        )


def extract_method_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> MethodSignature:
    """Extract method signature from AST node."""
    args = []
    for arg in node.args.args:
        arg_str = arg.arg
        if arg.annotation:
            arg_str += f": {ast.unparse(arg.annotation)}"
        args.append(arg_str)

    # Handle *args and **kwargs
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")

    # Return annotation
    return_ann = ast.unparse(node.returns) if node.returns else None

    # Decorators
    decorators = [ast.unparse(d) for d in node.decorator_list]

    # Docstring hash
    docstring = ast.get_docstring(node)
    docstring_hash = hashlib.md5(docstring.encode()).hexdigest()[:8] if docstring else None

    return MethodSignature(
        name=node.name,
        args=args,
        defaults_count=len(node.args.defaults),
        return_annotation=return_ann,
        decorators=decorators,
        is_async=isinstance(node, ast.AsyncFunctionDef),
        docstring_hash=docstring_hash,
    )


def extract_signals(class_node: ast.ClassDef) -> list[SignalDefinition]:
    """Extract Qt signal definitions from class body."""
    signals = []

    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if isinstance(node.value, ast.Call):
                        func = node.value.func
                        if isinstance(func, ast.Name) and func.id == "pyqtSignal":
                            # Extract signal arguments
                            args = ", ".join(ast.unparse(arg) for arg in node.value.args)
                            signals.append(SignalDefinition(name=target.id, args=args))
                        elif isinstance(func, ast.Attribute) and func.attr == "pyqtSignal":
                            args = ", ".join(ast.unparse(arg) for arg in node.value.args)
                            signals.append(SignalDefinition(name=target.id, args=args))

    return signals


def extract_state_variables(init_method: ast.FunctionDef) -> list[StateVariable]:
    """Extract instance variables from __init__ method."""
    variables = []

    for node in ast.walk(init_method):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    if isinstance(target.value, ast.Name) and target.value.id == "self":
                        var_name = target.attr
                        # Get type annotation if available (from AnnAssign)
                        type_ann = None
                        # Get initial value representation
                        try:
                            init_val = ast.unparse(node.value)[:100]  # Truncate long values
                        except Exception:
                            init_val = "<complex>"

                        variables.append(StateVariable(
                            name=var_name,
                            type_annotation=type_ann,
                            initial_value_repr=init_val,
                        ))

        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Attribute):
                if isinstance(node.target.value, ast.Name) and node.target.value.id == "self":
                    var_name = node.target.attr
                    type_ann = ast.unparse(node.annotation) if node.annotation else None
                    init_val = ast.unparse(node.value)[:100] if node.value else None

                    variables.append(StateVariable(
                        name=var_name,
                        type_annotation=type_ann,
                        initial_value_repr=init_val,
                    ))

    # Deduplicate by name
    seen = set()
    unique_vars = []
    for v in variables:
        if v.name not in seen:
            seen.add(v.name)
            unique_vars.append(v)

    return unique_vars


def extract_imports(tree: ast.Module) -> list[str]:
    """Extract all import statements."""
    imports = []

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            imports.append(f"from {module} import {names}")

    return imports


def capture_golden_master(file_path: str, class_name: str | None = None) -> GoldenMaster:
    """Capture golden master from a Python file."""
    path = Path(file_path)
    source = path.read_text()
    file_hash = hashlib.sha256(source.encode()).hexdigest()[:16]

    tree = ast.parse(source)

    # Find the target class
    target_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if class_name is None or node.name == class_name:
                target_class = node
                break

    if target_class is None:
        raise ValueError(f"Class {class_name or 'any'} not found in {file_path}")

    # Extract base classes
    base_classes = [ast.unparse(base) for base in target_class.bases]

    # Extract methods
    public_methods = []
    private_methods = []
    init_method = None

    for item in target_class.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = extract_method_signature(item)
            if item.name == "__init__":
                init_method = item
            if item.name.startswith("_") and not item.name.startswith("__"):
                private_methods.append(sig)
            else:
                public_methods.append(sig)

    # Extract signals
    signals = extract_signals(target_class)

    # Extract state variables
    state_vars = extract_state_variables(init_method) if init_method else []

    # Extract imports
    imports = extract_imports(tree)

    return GoldenMaster(
        file_path=str(path.absolute()),
        file_hash=file_hash,
        class_name=target_class.name,
        public_methods=public_methods,
        private_methods=private_methods,
        signals=signals,
        state_variables=state_vars,
        imports=imports,
        base_classes=base_classes,
    )


def verify_golden_master(
    current_file: str,
    golden_master_path: str,
    class_name: str | None = None,
    strict: bool = False
) -> tuple[bool, list[str]]:
    """
    Verify current file against golden master.

    Args:
        current_file: Path to current Python file
        golden_master_path: Path to saved golden master JSON
        class_name: Optional class name to verify
        strict: If True, require exact match including private methods

    Returns:
        Tuple of (passed, list of failure messages)
    """
    # Load golden master
    golden_data = json.loads(Path(golden_master_path).read_text())
    golden = GoldenMaster.from_dict(golden_data)

    # Capture current state
    current = capture_golden_master(current_file, class_name or golden.class_name)

    failures = []

    # Verify public methods (MUST match)
    golden_public = {m.name: m for m in golden.public_methods}
    current_public = {m.name: m for m in current.public_methods}

    for name, golden_method in golden_public.items():
        if name not in current_public:
            failures.append(f"❌ Missing public method: {name}")
        else:
            current_method = current_public[name]
            if golden_method.args != current_method.args:
                failures.append(
                    f"❌ Method {name} signature changed:\n"
                    f"   Expected: {golden_method.args}\n"
                    f"   Actual:   {current_method.args}"
                )
            if golden_method.return_annotation != current_method.return_annotation:
                failures.append(
                    f"⚠️  Method {name} return type changed: "
                    f"{golden_method.return_annotation} → {current_method.return_annotation}"
                )

    # Verify signals (MUST match)
    golden_signals = {s.name: s for s in golden.signals}
    current_signals = {s.name: s for s in current.signals}

    for name, golden_signal in golden_signals.items():
        if name not in current_signals:
            failures.append(f"❌ Missing signal: {name}")
        elif golden_signal.args != current_signals[name].args:
            failures.append(
                f"❌ Signal {name} args changed: "
                f"{golden_signal.args} → {current_signals[name].args}"
            )

    # Verify state variables (WARNING only for missing)
    golden_vars = {v.name for v in golden.state_variables}
    current_vars = {v.name for v in current.state_variables}

    missing_vars = golden_vars - current_vars
    if missing_vars:
        failures.append(f"⚠️  Missing state variables: {missing_vars}")

    # Verify base classes
    if set(golden.base_classes) != set(current.base_classes):
        failures.append(
            f"❌ Base classes changed: {golden.base_classes} → {current.base_classes}"
        )

    # Strict mode: verify private methods too
    if strict:
        golden_private = {m.name for m in golden.private_methods}
        current_private = {m.name for m in current.private_methods}
        missing_private = golden_private - current_private
        if missing_private:
            failures.append(f"⚠️  Missing private methods: {missing_private}")

    passed = len([f for f in failures if f.startswith("❌")]) == 0
    return passed, failures


def print_golden_master(gm: GoldenMaster) -> None:
    """Print golden master summary."""
    print("\n" + "=" * 60)
    print("GOLDEN MASTER SNAPSHOT")
    print("=" * 60)
    print(f"File: {gm.file_path}")
    print(f"Hash: {gm.file_hash}")
    print(f"Class: {gm.class_name}")
    print(f"Base Classes: {', '.join(gm.base_classes)}")
    print("-" * 60)

    print(f"\n📡 Signals ({len(gm.signals)}):")
    for sig in gm.signals:
        print(f"   {sig.name}({sig.args})")

    print(f"\n🔓 Public Methods ({len(gm.public_methods)}):")
    for m in gm.public_methods:
        args_str = ", ".join(m.args)
        ret = f" -> {m.return_annotation}" if m.return_annotation else ""
        print(f"   {m.name}({args_str}){ret}")

    print(f"\n🔒 Private Methods ({len(gm.private_methods)}):")
    for m in gm.private_methods:
        print(f"   {m.name}")

    print(f"\n📦 State Variables ({len(gm.state_variables)}):")
    for v in gm.state_variables:
        type_str = f": {v.type_annotation}" if v.type_annotation else ""
        print(f"   self.{v.name}{type_str}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Golden master capture for refactoring")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Capture command
    capture_parser = subparsers.add_parser("capture", help="Capture golden master")
    capture_parser.add_argument("file_path", help="Python file to capture")
    capture_parser.add_argument("-c", "--class-name", help="Class name to capture")
    capture_parser.add_argument("-o", "--output", help="Output JSON file")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify against golden master")
    verify_parser.add_argument("file_path", help="Python file to verify")
    verify_parser.add_argument("--snapshot", required=True, help="Golden master JSON file")
    verify_parser.add_argument("-c", "--class-name", help="Class name to verify")
    verify_parser.add_argument("--strict", action="store_true", help="Strict mode")

    args = parser.parse_args()

    if args.command == "capture":
        gm = capture_golden_master(args.file_path, args.class_name)
        print_golden_master(gm)

        if args.output:
            Path(args.output).write_text(json.dumps(gm.to_dict(), indent=2))
            print(f"\n✅ Golden master saved to {args.output}")

    elif args.command == "verify":
        passed, failures = verify_golden_master(
            args.file_path,
            args.snapshot,
            args.class_name,
            args.strict,
        )

        print("\n" + "=" * 60)
        print("VERIFICATION RESULTS")
        print("=" * 60)

        if failures:
            for f in failures:
                print(f)
        else:
            print("✅ All checks passed!")

        print("\n" + ("✅ PASSED" if passed else "❌ FAILED"))
        sys.exit(0 if passed else 1)

    else:
        parser.print_help()
