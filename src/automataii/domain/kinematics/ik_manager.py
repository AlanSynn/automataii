"""
DEPRECATED: IKManager has moved to presentation layer.

IKManager is Qt-coupled and has been relocated to:
    automataii.presentation.qt.kinematics.ik_manager

This stub exists for backwards compatibility during migration.
"""
import warnings

warnings.warn(
    "IKManager has moved to automataii.presentation.qt.kinematics. "
    "Update your imports to use the new location.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from new location for backwards compatibility
from automataii.presentation.qt.kinematics.ik_manager import IKManager

__all__ = ["IKManager"]
