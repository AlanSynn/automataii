"""
Tab components for the Automataii application.

Each tab is a self-contained module with its own components directory.
"""
from automataii.presentation.qt.tabs.editor.tab import EditorTab
from automataii.presentation.qt.tabs.image_processing_tab import ImageProcessingTab
from automataii.presentation.qt.tabs.lab import LabTab
from automataii.presentation.qt.tabs.landing_tab import LandingTab
from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab
from automataii.presentation.qt.tabs.options_tab import OptionsTab

__all__ = [
    "EditorTab",
    "ImageProcessingTab",
    "LabTab",
    "LandingTab",
    "MechanismDesignTab",
    "OptionsTab",
]
