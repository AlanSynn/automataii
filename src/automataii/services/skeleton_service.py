"""
DEPRECATED: SkeletonService has moved to application layer.

SkeletonService has been relocated to:
    automataii.application.mechanisms.skeleton_service

This stub exists for backwards compatibility during migration.
"""
import warnings

warnings.warn(
    "SkeletonService has moved to automataii.application.mechanisms. "
    "Update your imports to use the new location.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from new location for backwards compatibility
from automataii.application.mechanisms.skeleton_service import SkeletonService

__all__ = ["SkeletonService"]
