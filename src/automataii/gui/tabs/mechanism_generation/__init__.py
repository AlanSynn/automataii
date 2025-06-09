"""Mechanism Generation Tab - Modular components."""

from .mechanism_generation_tab import MechanismGenerationTab
from .mechanism_editor import MechanismEditor, EditMode
from .mechanism_graphics import (
    AnimatedFourBarLinkage, AnimatedCamFollower, AnimatedGearTrain,
    MechanismColors
)
from .advanced_editing import (
    AdvancedPropertyPanel, MechanismAnalyzer, OptimizationEngine,
    MotionAnalysisWidget, EditingPreferences
)
from .editing_shortcuts import (
    ShortcutManager, ContextMenuManager, EditingToolbar
)

__all__ = [
    "MechanismGenerationTab",
    "MechanismEditor", 
    "EditMode",
    "AnimatedFourBarLinkage",
    "AnimatedCamFollower", 
    "AnimatedGearTrain",
    "MechanismColors",
    "AdvancedPropertyPanel",
    "MechanismAnalyzer",
    "OptimizationEngine",
    "MotionAnalysisWidget",
    "EditingPreferences",
    "ShortcutManager",
    "ContextMenuManager",
    "EditingToolbar"
]