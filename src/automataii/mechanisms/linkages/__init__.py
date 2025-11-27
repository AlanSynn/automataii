"""
Compatibility layer: This module has moved to automataii.domain.mechanisms.linkages

This file provides backwards compatibility by re-exporting from the new location.
"""

# Re-export everything from new location
from automataii.domain.mechanisms.linkages import *  # noqa: F401, F403

import warnings
warnings.warn(
    "Importing from 'automataii.mechanisms.linkages' is deprecated. "
    "Use 'automataii.domain.mechanisms.linkages' instead.",
    DeprecationWarning,
    stacklevel=2
)
