"""
Shared Module - Cross-Cutting Concerns.

This module contains utilities and types that span multiple architectural layers.
All exports must be pure Python with NO Qt/UI dependencies.

Contents:
- result: Railway-oriented Result types for error handling
- types: Common geometric types (Point2D, etc.)
- logging: Standardized logging configuration
- config: Application configuration

Usage:
    from automataii.shared import Result, Ok, Err, Point2D
"""

from automataii.shared.result import Err, Ok, Result
from automataii.shared.types import Point2D

__all__ = [
    # Result types
    "Result",
    "Ok",
    "Err",
    # Common types
    "Point2D",
]
