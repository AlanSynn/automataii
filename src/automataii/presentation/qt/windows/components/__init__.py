"""
Extracted components from main window.

This module contains components extracted from AutomataDesigner
to reduce god class complexity.

Components:
- TabOrchestrator: Tab lifecycle and camera state sharing
- SignalConnector: Centralized signal connection management
- ProjectController: SSOT project operations (save/load/new/undo/redo)
"""

from automataii.presentation.qt.windows.components.project_controller import (
    ProjectController,
)
from automataii.presentation.qt.windows.components.signal_connector import (
    SignalConnector,
)
from automataii.presentation.qt.windows.components.tab_orchestrator import (
    TabOrchestrator,
)

__all__ = [
    "ProjectController",
    "SignalConnector",
    "TabOrchestrator",
]
