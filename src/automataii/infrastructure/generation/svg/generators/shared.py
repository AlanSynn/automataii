"""
Shared types for SVG generation.

BACKWARD COMPATIBILITY FACADE

Types have been moved to:
- ScaledBounds -> automataii.domain.generation.layout

This module re-exports for backward compatibility.
"""

from __future__ import annotations

# Re-export from canonical location
from automataii.domain.generation.layout import ScaledBounds

__all__ = ["ScaledBounds"]
