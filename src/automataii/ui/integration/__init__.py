"""
UI Integration Layer

Provides clean integration between domain layer and PyQt6 UI layer
while maintaining architectural separation.

Key Components:
- DomainUIBridge: Converts domain callbacks to PyQt6 signals
- MechanismTargetBridge: Bridges target provision between layers
- UIIntegrationManager: Centralized integration management
"""

from .domain_ui_bridge import DomainUIBridge, MechanismTargetBridge, UIIntegrationManager

__all__ = [
    "DomainUIBridge",
    "MechanismTargetBridge",
    "UIIntegrationManager",
]
