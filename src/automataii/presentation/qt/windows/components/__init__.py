"""
Extracted components from main window.

This module contains components extracted from AutomataDesigner
to reduce god class complexity.

Components:
- TabOrchestrator: Tab lifecycle and camera state sharing
- SignalConnector: Centralized signal connection management
- ProjectController: SSOT project operations (save/load/new/undo/redo)
- WorkspaceLayoutManager: Dock/tab layout customization and persistence
- WorkflowStateMachine: Non-linear workflow guidance and sequence state
- get_default_project_dir: Utility for default tmp project directory
"""

from automataii.presentation.qt.windows.components.project_controller import (
    ProjectController,
    get_default_project_dir,
)
from automataii.presentation.qt.windows.components.signal_connector import (
    SignalConnector,
)
from automataii.presentation.qt.windows.components.tab_orchestrator import (
    TabOrchestrator,
)
from automataii.presentation.qt.windows.components.workflow_state_machine import (
    WorkflowStateMachine,
)
from automataii.presentation.qt.windows.components.workspace_layout_manager import (
    WorkspaceLayoutManager,
)

__all__ = [
    "ProjectController",
    "SignalConnector",
    "TabOrchestrator",
    "WorkflowStateMachine",
    "WorkspaceLayoutManager",
    "get_default_project_dir",
]
