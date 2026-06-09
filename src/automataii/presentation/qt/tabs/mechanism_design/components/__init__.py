"""
MechanismDesignTab extracted components.

This package contains modules extracted from the MechanismDesignTab god class
using the LLM-native refactoring approach.

Extracted Modules:
- SkeletonVisualizationHandler: Skeleton updates, visualization, and IK integration
- AnimationLifecycleController: Animation start/stop/reset and frame updates
- MechanismOutputCalculator: Mechanism output position calculation for all types
- MechanismVisualAnimator: Visual element updates during animation
- SceneTransformManager: Coordinate transformations between mechanism and scene space
- RecommendationHandler: Mechanism recommendation workflow handling
"""

from automataii.presentation.qt.tabs.mechanism_design.components.animation_lifecycle_controller import (
    AnimationLifecycleController,
)
from automataii.presentation.qt.tabs.mechanism_design.components.mechanism_output_calculator import (
    MechanismOutputCalculator,
)
from automataii.presentation.qt.tabs.mechanism_design.components.mechanism_visual_animator import (
    MechanismVisualAnimator,
)
from automataii.presentation.qt.tabs.mechanism_design.components.recommendation_handler import (
    RecommendationHandler,
)
from automataii.presentation.qt.tabs.mechanism_design.components.scene_transform_manager import (
    SceneTransformManager,
)
from automataii.presentation.qt.tabs.mechanism_design.components.skeleton_visualization_handler import (
    SkeletonVisualizationHandler,
)

__all__ = [
    "SkeletonVisualizationHandler",
    "AnimationLifecycleController",
    "MechanismOutputCalculator",
    "MechanismVisualAnimator",
    "SceneTransformManager",
    "RecommendationHandler",
]
