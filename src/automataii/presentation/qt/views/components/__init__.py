"""
EditorView Components - Extracted from EditorView for SRP.

Components:
- PathDrawingHandler: Handles motion path drawing and visualization
- SkeletonVisualHandler: Handles skeleton visualization and animation
- PathVertexEditor: Handles vertex-based motion path editing
"""

from automataii.presentation.qt.views.components.path_drawing_handler import (
    PathDrawingHandler,
)
from automataii.presentation.qt.views.components.path_vertex_editor import (
    PathVertexEditor,
    PathVertexHandle,
)
from automataii.presentation.qt.views.components.skeleton_visual_handler import (
    SkeletonVisualHandler,
)

__all__ = [
    "PathDrawingHandler",
    "PathVertexEditor",
    "PathVertexHandle",
    "SkeletonVisualHandler",
]
