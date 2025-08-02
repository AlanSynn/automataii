"""
UI Workflow Management

Provides interactive workflow management for the mechanism design process.
Implements the complete design pipeline from PAPER_IMPL.md.

Key Components:
- DesignWorkflowManager: Main workflow orchestrator
- WorkflowState: Workflow state enumeration
- WorkflowStep: Individual workflow step representation
- DesignResult: Final workflow results
"""

from .design_workflow_manager import (
    DesignResult,
    DesignWorkflowManager,
    WorkflowState,
    WorkflowStep,
)

__all__ = [
    "DesignWorkflowManager",
    "WorkflowState",
    "WorkflowStep",
    "DesignResult",
]
