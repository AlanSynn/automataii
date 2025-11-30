"""
Common shared widgets for the Qt presentation layer.

These widgets are designed to be reused across multiple tabs and views,
reducing code duplication and ensuring consistent UI patterns.

Components:
- ZoomControlsWidget: Inline zoom buttons (+, -, fit, reset)
- StyleFactory: Consistent button and group box styling
"""

from automataii.presentation.qt.widgets.common.zoom_controls import ZoomControlsWidget
from automataii.presentation.qt.widgets.common.styles import StyleFactory

__all__ = [
    "ZoomControlsWidget",
    "StyleFactory",
]
