"""
EditorView extracted components.

This package contains modules extracted from EditorView
using the LLM-native refactoring approach.

Extracted Modules:
- MotionPathController: Motion path drawing and spline generation
- SkeletonVisualizer: Skeleton visualization and animation updates
"""
from automataii.presentation.qt.views.components.motion_path_controller import MotionPathController
from automataii.presentation.qt.views.components.skeleton_visualizer import SkeletonVisualizer

__all__ = [
    "MotionPathController",
    "SkeletonVisualizer",
]
