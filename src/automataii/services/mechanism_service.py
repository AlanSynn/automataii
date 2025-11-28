"""
DEPRECATED: MechanismService has moved to application layer.

MechanismService has been relocated to:
    automataii.application.mechanisms.mechanism_service

This stub exists for backwards compatibility during migration.
"""
import warnings

warnings.warn(
    "MechanismService has moved to automataii.application.mechanisms. "
    "Update your imports to use the new location.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from new location for backwards compatibility
from automataii.application.mechanisms.mechanism_service import MechanismService

__all__ = ["MechanismService"]
