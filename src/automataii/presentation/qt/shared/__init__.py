"""
Shared Qt utilities for the presentation layer.

This module provides reusable utilities to reduce code duplication
across the Qt presentation layer.
"""

from automataii.presentation.qt.shared.layout_utils import (
    clear_layout,
    remove_widget_from_layout,
    replace_widget_in_layout,
)
from automataii.presentation.qt.shared.scene_update_batcher import (
    GlobalSceneBatcher,
    SceneUpdateBatcher,
)
from automataii.presentation.qt.shared.widget_utils import (
    SliderSpinboxSync,
    blocked_signals,
    set_combo_silently,
    set_value_silently,
)

__all__ = [
    # Widget utilities
    "blocked_signals",
    "set_value_silently",
    "set_combo_silently",
    "SliderSpinboxSync",
    # Layout utilities
    "clear_layout",
    "remove_widget_from_layout",
    "replace_widget_in_layout",
    # Scene batching
    "SceneUpdateBatcher",
    "GlobalSceneBatcher",
]
