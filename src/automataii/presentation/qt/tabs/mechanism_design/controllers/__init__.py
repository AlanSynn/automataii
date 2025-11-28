"""
Controllers for MechanismDesignTab.

Extracted from god class decomposition to separate animation, parametric,
layer selection, and recommendation concerns into focused controller classes.

Architecture: Hexagonal - Presentation Layer
Design Pattern: Controller (each handles a specific operational domain)

Controllers:
- AnimationModeController: Animation lifecycle, frame updates, IK coordination
- LayerSelectionController: Layer list selection, visibility toggling
- ParametricModeController: Parametric editing mode toggle and handles
- RecommendationController: Mechanism recommendation dialog workflow
"""
from .animation_mode_controller import AnimationModeController
from .layer_selection_controller import LayerSelectionController
from .parametric_mode_controller import ParametricModeController
from .recommendation_controller import RecommendationController

__all__ = [
    "AnimationModeController",
    "LayerSelectionController",
    "ParametricModeController",
    "RecommendationController",
]
