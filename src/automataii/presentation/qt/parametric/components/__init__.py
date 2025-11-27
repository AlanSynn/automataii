"""
Parametric editor extracted components.

This package contains modules extracted from parametric_editor.py
using the LLM-native refactoring approach.

Extracted Modules:
- ConstraintSolver: Handle movement constraint calculations
- HandleStyleRegistry: Centralized handle style management
- EditorFactory: Factory for creating mechanism-specific editors
"""
from automataii.presentation.qt.parametric.components.constraint_solver import (
    ConstraintSolver,
    ConstraintResult,
)
from automataii.presentation.qt.parametric.components.handle_style_registry import (
    HandleStyle,
    HandleType,
    HandleStyleRegistry,
    get_default_registry,
)
from automataii.presentation.qt.parametric.components.editor_factory import (
    EditorFactory,
    get_default_factory,
)

__all__ = [
    "ConstraintSolver",
    "ConstraintResult",
    "HandleStyle",
    "HandleType",
    "HandleStyleRegistry",
    "get_default_registry",
    "EditorFactory",
    "get_default_factory",
]
