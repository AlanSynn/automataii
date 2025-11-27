"""
Compatibility layer: This module has moved to automataii.domain.mechanisms.catalog

This file provides backwards compatibility by re-exporting from the new location.
This will be removed in a future version.
"""

# Re-export everything from new location
from automataii.domain.mechanisms.catalog import *  # noqa: F401, F403

import warnings
warnings.warn(
    "Importing from 'src/automataii/mechanisms/catalog' is deprecated. "
    "Use 'automataii.domain.mechanisms.catalog' instead.",
    DeprecationWarning,
    stacklevel=2
)
