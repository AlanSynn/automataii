"""Domain linkage configuration.

Pure Python configuration types for linkage mechanisms.
NO Qt dependencies allowed in this module.

Re-exports from linkages/config.py for backwards compatibility.
"""

from automataii.domain.mechanisms.linkages.config import (
    LinkageConfig,
    LinkageType,
    LinkRole,
)

__all__ = [
    "LinkageConfig",
    "LinkageType",
    "LinkRole",
]
