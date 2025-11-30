"""
Parametric editor extracted components.

This package contains modules extracted from parametric_editor.py
using the LLM-native refactoring approach.

Extracted Modules:
- ConstraintSolver: Handle movement constraint calculations
- HandleStyleRegistry: Centralized handle style management
- EditorFactory: Factory for creating mechanism-specific editors
- Base Editor: MechanismEditor ABC and ParametricHandle
- FourBarEditor: 4-bar linkage editor
- CamEditor: Cam mechanism editor
- GearEditor: Gear mechanism editor
- PlanetaryGearEditor: Planetary gear editor
"""
from automataii.presentation.qt.parametric.components.base_editor import (
    HandleStyle,
    MechanismEditor,
    ParametricHandle,
)
from automataii.presentation.qt.parametric.components.cam_editor import CamEditor
from automataii.presentation.qt.parametric.components.constraint_solver import (
    ConstraintResult,
    ConstraintSolver,
)
from automataii.presentation.qt.parametric.components.editor_factory import (
    EditorFactory,
    get_default_factory,
)
from automataii.presentation.qt.parametric.components.fourbar_editor import FourBarEditor
from automataii.presentation.qt.parametric.components.gear_editor import (
    GearEditor,
    PlanetaryGearEditor,
)
from automataii.presentation.qt.parametric.components.handle_style_registry import (
    HandleStyleRegistry,
    HandleType,
    get_default_registry,
)

__all__ = [
    # Base components
    "HandleStyle",
    "ParametricHandle",
    "MechanismEditor",
    # Editors
    "FourBarEditor",
    "CamEditor",
    "GearEditor",
    "PlanetaryGearEditor",
    # Utilities
    "ConstraintSolver",
    "ConstraintResult",
    "HandleType",
    "HandleStyleRegistry",
    "get_default_registry",
    "EditorFactory",
    "get_default_factory",
]
